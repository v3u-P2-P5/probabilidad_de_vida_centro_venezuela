"""Ensambla las capas y calcula el índice de prioridad SAR por celda.

Modo OPERATIVO: datos reales de USGS (ShakeMap doble combinado, PAGER, OSM) +
  proyecciones estadísticas respaldadas (vulnerabilidad HAZUS, ocupación HAZUS)
  cuando están habilitadas en config.yaml. Cada capa citada y fechada.
  Layers marcadas NO DISPONIBLE solo si son REAL e irrecuperablemente ausentes.

Modo DEMO: datos sintéticos rotulados (capacitación, sin datos USGS).

El índice estima PROBABILIDAD DE SOBREVIVIENTES CON VIDA, no ubicación de víctimas.
"""
from datetime import datetime, timezone

import numpy as np

from core import scoring, shakemap
from core.data_sources import get_sismo, get_sismos, synthetic_mmi
from core.geo import make_grid
from core.osm import _geo_sector, assign_areas, fetch_resources
from core.population import (
    HORA_SISMO_VET, apply_occupancy, generate_zone_population,
    get_population, population_present, zone_vuln_void,
)
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
    # Área/sector geográfico de cada celda (mismos sectores que los recursos OSM,
    # para que una brigada cruce "Sector Este" de celdas con recursos del mismo).
    df["area"] = [_geo_sector(la, lo, zone["bbox"])
                  for la, lo in zip(df["lat"].values, df["lon"].values)]
    layers, hs = [], hours_since(sismo, now)
    proyec_cfg = config.get("proyecciones_estadisticas", {})
    proyec_ok = proyec_cfg.get("habilitadas", False)

    # --- Capa 1: ShakeMaps reales (USGS) — sismo doble combinado ---
    sm_ok = False
    n_grids_ok = 0
    try:
        eventos = get_sismos(config)
        grids = []
        for ev in eventos:
            url = ev.get("shakemap_grid_url")
            if not url:
                continue
            path = shakemap.download_grid_for_event(
                ev["id"], url, ttl=config.get("shakemap_ttl_segundos", 300))
            grids.append(shakemap.parse_grid(path))
            n_grids_ok += 1

        if not grids:
            raise RuntimeError("Ningún ShakeMap disponible en USGS")

        df["mmi"] = shakemap.interp_mmi_max(grids, df["lat"].values, df["lon"].values)
        sm_ok = True
        sm_label = f"ShakeMap combinado ({n_grids_ok} evento{'s' if n_grids_ok>1 else ''})"
        layers.append(layer(f["usgs_shakemap"]["nombre"], f["usgs_shakemap"]["url"],
                            "ok", datetime.now(timezone.utc), sm_label))
        if n_grids_ok > 1 and "usgs_shakemap_secundario" in f:
            layers.append(layer(f["usgs_shakemap_secundario"]["nombre"],
                                f["usgs_shakemap_secundario"]["url"], "ok",
                                datetime.now(timezone.utc), "ShakeMap M7.2 incluido"))
    except Exception as e:
        df["mmi"] = float("nan")
        layers.append(layer(f["usgs_shakemap"]["nombre"], f["usgs_shakemap"]["url"],
                            "no_disponible", detalle=str(e)))

    # --- Capa 2: Población (local → remota → API → censo INE 2011) ---
    pop_raw, pop_src = get_population(df["lat"].values, df["lon"].values, config, zone)
    pop_ok = pop_raw is not None
    if pop_ok:
        zone_uso = zone.get("uso", "mixto")
        pop_presente = apply_occupancy(pop_raw, zone_uso, HORA_SISMO_VET) if proyec_ok else pop_raw
        df["pop"] = np.round(pop_presente).astype(float)
        df["pop_norm"] = scoring.normalize(df["pop"].values)
        src_label = {"local": "WorldPop TIF local", "remota": "WorldPop HTTP",
                     "api": "WorldPop API", "censo_ine": "Censo INE Venezuela 2011"}.get(pop_src, pop_src)
        pop_url = (f["worldpop"]["url"] if pop_src != "censo_ine"
                   else "https://www.ine.gov.ve/index.php/estadisticas-sociales/demograficas-y-vitales/censo-de-poblacion-y-vivienda")
        layers.append(layer(src_label, pop_url, "ok" if pop_src != "censo_ine" else "proyeccion",
                            datetime.now(timezone.utc),
                            f"{src_label} × ocupación HAZUS 18:05 VET"))
    else:
        df["pop"] = float("nan")
        df["pop_norm"] = 1.0
        layers.append(layer(f["worldpop"]["nombre"], f["worldpop"]["url"], "no_disponible"))

    # --- Capa 3: Vulnerabilidad estructural (proyección estadística HAZUS) ---
    vuln_proj, void_proj = None, None
    if proyec_ok:
        vuln_z, void_z = zone_vuln_void(zone["id"], config)
        df["vuln"] = vuln_z
        df["void"] = void_z
        vuln_proj = vuln_z
        void_proj = void_z
        layers.append(layer(
            "Vulnerabilidad estructural (proyección estadística HAZUS+PAGER)",
            proyec_cfg.get("ref_pager", f["pager_inventory"]["url"]),
            "ok", datetime.now(timezone.utc),
            f"vuln={vuln_z:.2f} void={void_z:.2f} · zona {zone['id']} · método: {proyec_cfg.get('metodo_inventario', '')}"))

    # --- Capa 4: Reportes de campo (tiempo real) ---
    df["boost"] = boost_for_grid(df, _reports_for_zone(zone["id"]))

    # Población uniforme (p. ej. fallback censal) → normalize() daría ceros y
    # anularía todo el score. En ese caso pop_norm es neutral (1.0): no aporta
    # variación espacial pero tampoco elimina la señal de sacudimiento/colapso.
    if np.allclose(np.nan_to_num(df["pop_norm"].values), 0.0):
        df["pop_norm"] = 1.0

    # --- Índice de prioridad de sobrevivientes ---
    if sm_ok:
        w = config["pesos"]
        if proyec_ok and vuln_proj is not None:
            # Modelo completo: sacudimiento × colapso × población × supervivencia × decaimiento
            df["score"] = scoring.life_probability(
                df["mmi"].values, df["vuln"].values, df["void"].values,
                df["pop_norm"].values, hs, w, df["boost"].values)
        else:
            # Modelo reducido: sacudimiento × población × decaimiento + reportes
            df["score"] = (scoring.shaking_factor(df["mmi"].values) ** w["sacudimiento"]
                           * df["pop_norm"].values ** w["poblacion"]
                           * scoring.time_decay(hs) ** w["decaimiento_temporal"]
                           + df["boost"].values * w["factor_boost_reporte"])
        df["score_norm"] = scoring.normalize(df["score"].values)
        df["prioridad"] = scoring.priority_category(df["score_norm"].values)

        # Probabilidad ABSOLUTA de hallar sobrevivientes con vida (0-1),
        # independiente del ranking de zona. Filtra celdas sin esperanza
        # (sin sacudimiento → sin colapso → sin atrapados): valen exactamente 0.
        shaking = scoring.shaking_factor(df["mmi"].values)
        decay = scoring.time_decay(hs)
        if proyec_ok and vuln_proj is not None:
            collapse = scoring.collapse_probability(df["mmi"].values, df["vuln"].values)
            surv = scoring.survivability(df["void"].values)
            df["p_vida"] = shaking * collapse * surv * decay
        else:
            df["p_vida"] = shaking * decay
        # Reportes de campo confirmados elevan la esperanza directamente
        df["p_vida"] = np.clip(df["p_vida"].values
                               + df["boost"].values * (1.0 - df["p_vida"].values), 0.0, 1.0)
    else:
        df["score"] = float("nan")
        df["score_norm"] = float("nan")
        df["p_vida"] = float("nan")
        df["prioridad"] = "—"

    # --- Recursos críticos reales (OSM) ---
    if with_osm:
        resources = fetch_resources(zone["bbox"], f["osm"]["overpass"],
                                    ttl=config.get("osm_ttl_segundos", 1800))
        if not resources.empty and not resources.attrs.get("error"):
            resources = assign_areas(resources, zone["bbox"])
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
        "pop_available": pop_ok, "pop_src": pop_src,
        "shakemap_ok": sm_ok, "n_shakemaps": n_grids_ok,
        "proyec_ok": proyec_ok,
        "resources": resources, "layers": layers,
        "pager": sismo.get("pager"), "alert_pager": sismo.get("alert_pager"),
        "ground_failure": sismo.get("ground_failure"),
        "sismos_adicionales": sismo.get("sismos_adicionales", []),
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
           "pop_src": "sintético", "shakemap_ok": True, "n_shakemaps": 0,
           "proyec_ok": False,
           "resources": pd.DataFrame(), "layers": [],
           "pager": None, "alert_pager": None, "ground_failure": None,
           "sismos_adicionales": [],
           "updated_at": fmt_vet_utc(), "fuentes": config.get("fuentes", {})}
    return df, ctx
