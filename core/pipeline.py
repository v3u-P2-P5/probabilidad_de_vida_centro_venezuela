"""Ensambla las capas y calcula el índice de prioridad por celda.

Modo OPERATIVO: solo datos reales (USGS ShakeMap + WorldPop + OSM). Si una capa
falta, se marca como NO DISPONIBLE; jamás se inventan datos.
Modo DEMO: datos sintéticos rotulados (para pruebas/capacitación).
"""
from datetime import datetime, timezone

from core import scoring, shakemap
from core.data_sources import get_sismo, synthetic_mmi
from core.geo import make_grid
from core.osm import fetch_resources
from core.population import (generate_zone_population, population_present,
                            sample_population_raster)
from core.reports import boost_for_grid, load_reports
from core.sources import fmt_vet_utc, layer, parse_iso


def hours_since(sismo: dict, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    return max((now - parse_iso(sismo["origen_iso"])).total_seconds() / 3600.0, 0.0)


def _reports_for_zone(zone_id: str):
    reps = load_reports()
    return reps[reps["zona"] == zone_id] if not reps.empty else reps


def build_zone(zone: dict, config: dict, now: datetime | None = None, with_osm: bool = True):
    """Devuelve (df_celdas, ctx). ctx incluye procedencia, recursos y resúmenes.

    with_osm=False omite la consulta a OSM (útil para el resumen del inicio).
    """
    if config.get("modo_operativo", True):
        return _build_operativo(zone, config, now, with_osm)
    return _build_demo(zone, config, now)


def _build_operativo(zone, config, now, with_osm=True):
    f = config["fuentes"]
    sismo = get_sismo(config)
    grid = make_grid(zone["bbox"], config["rejilla"]["tamano_celda_m"])
    df = grid.copy()
    layers, hs = [], hours_since(sismo, now)

    # --- Capa 1: sacudimiento real (USGS ShakeMap) ---
    sm_ok = False
    try:
        url = sismo.get("shakemap_grid_url")
        if not url:
            raise RuntimeError("sin grid.xml")
        path = shakemap.download_grid(url, ttl=config.get("shakemap_ttl_segundos", 300))
        grid_sm = shakemap.parse_grid(path)
        df["mmi"] = shakemap.interp_mmi(grid_sm, df["lat"].values, df["lon"].values)
        sm_ok = True
        layers.append(layer(f["usgs_shakemap"]["nombre"], f["usgs_shakemap"]["url"],
                            "ok", datetime.now(timezone.utc),
                            f"ShakeMap v{grid_sm.get('version')} · proc. {grid_sm.get('process_timestamp')}"))
    except Exception as e:
        df["mmi"] = float("nan")
        layers.append(layer(f["usgs_shakemap"]["nombre"], f["usgs_shakemap"]["url"],
                            "no_disponible", detalle=str(e)))

    # --- Capa 2: población real (WorldPop / Meta HRSL) ---
    pop = sample_population_raster(df["lat"].values, df["lon"].values,
                                   config["poblacion"]["raster_path"])
    pop_ok = pop is not None
    if pop_ok:
        df["pop"] = pop
        df["pop_norm"] = scoring.normalize(pop)
        layers.append(layer(f["worldpop"]["nombre"], f["worldpop"]["url"], "ok",
                            datetime.now(timezone.utc),
                            "Población residencial; el ajuste horario requiere datos de movilidad no disponibles."))
    else:
        df["pop"] = float("nan")
        df["pop_norm"] = 1.0  # neutral: no penaliza, pero se rotula la ausencia
        layers.append(layer(f["worldpop"]["nombre"], f["worldpop"]["url"], "no_disponible",
                            detalle="Ráster no descargado. Ver scripts/download_population.py"))

    # --- Capa 3: reportes de campo (tiempo real) ---
    df["boost"] = boost_for_grid(df, _reports_for_zone(zone["id"]))

    # --- Índice de prioridad (solo capas reales disponibles) ---
    if sm_ok:
        w = config["pesos"]
        df["score"] = (scoring.shaking_factor(df["mmi"].values) ** w["sacudimiento"]
                       * df["pop_norm"].values ** w["poblacion"]
                       * scoring.time_decay(hs) ** w["decaimiento_temporal"]
                       + df["boost"].values * w["factor_boost_reporte"])
        df["score_norm"] = scoring.normalize(df["score"].values)
        df["prioridad"] = scoring.priority_category(df["score_norm"].values)
    else:
        df["score"] = float("nan")
        df["score_norm"] = float("nan")
        df["prioridad"] = "—"

    # --- Recursos críticos reales (OSM) ---
    if with_osm:
        resources = fetch_resources(zone["bbox"], f["osm"]["overpass"],
                                    ttl=config.get("osm_ttl_segundos", 1800))
        layers.append(layer(
            f["osm"]["nombre"], f["osm"]["url"],
            "no_disponible" if resources.attrs.get("error") else "ok",
            None if resources.attrs.get("error") else datetime.now(timezone.utc),
            f"{len(resources)} recursos"))
    else:
        import pandas as pd
        resources = pd.DataFrame(columns=["nombre", "tipo", "etiqueta", "lat", "lon"])

    ctx = {
        "modo": "operativo", "sismo": sismo, "hours_since": hs,
        "pop_available": pop_ok, "shakemap_ok": sm_ok,
        "resources": resources, "layers": layers,
        "pager": sismo.get("pager"), "alert_pager": sismo.get("alert_pager"),
        "ground_failure": sismo.get("ground_failure"),
        "updated_at": fmt_vet_utc(), "fuentes": f,
    }
    return df, ctx


def _build_demo(zone, config, now):
    """Datos SINTÉTICOS para demostración/capacitación (rotulados)."""
    sismo = dict(config["sismo"]); sismo["fuente"] = "sintético (demo)"
    grid = make_grid(zone["bbox"], config["rejilla"]["tamano_celda_m"])
    zone = {**zone, "perfil_uso": zone.get("perfil_uso", "mixto")}
    df = generate_zone_population(zone, grid)
    df["mmi"] = synthetic_mmi(df["lat"].values, df["lon"].values, sismo)
    qhour = parse_iso(sismo["origen_iso"]).hour
    df["pop"] = population_present(df["base_pop"].values, df["uso"].iloc[0], qhour)
    df["pop_norm"] = scoring.normalize(df["pop"].values)
    df["boost"] = boost_for_grid(df, _reports_for_zone(zone["id"]))
    hs = hours_since(sismo, now)
    df["score"] = scoring.life_probability(df["mmi"].values, df["vuln"].values,
                                           df["void"].values, df["pop_norm"].values, hs,
                                           config["pesos"], df["boost"].values)
    df["score_norm"] = scoring.normalize(df["score"].values)
    df["prioridad"] = scoring.priority_category(df["score_norm"].values)
    import pandas as pd
    ctx = {"modo": "demo", "sismo": sismo, "hours_since": hs, "pop_available": True,
           "shakemap_ok": True, "resources": pd.DataFrame(), "layers": [],
           "pager": None, "alert_pager": None, "ground_failure": None,
           "updated_at": fmt_vet_utc(), "fuentes": config.get("fuentes", {})}
    return df, ctx
