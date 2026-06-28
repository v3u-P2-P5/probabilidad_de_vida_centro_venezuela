"""Ensambla las capas REALES para la app informativa post-terremoto.

Solo datos reales y atribuidos:
- ShakeMap USGS (intensidad MMI por celda, sismo doble combinado).
- Población residente (WorldPop precomputado / censo INE).
- Ground-failure USGS (licuefacción/deslizamiento por celda) cuando está precomputado.
- Recursos críticos OSM (hospitales, refugios, bomberos) por área.

NO modela probabilidad de sobrevivientes. Produce agregados por barrio/área para
la vista informativa orientada al público.
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core import scoring, shakemap
from core.data_sources import get_sismo, get_sismos
from core.geo import make_grid
from core.osm import _geo_sector, assign_areas, fetch_resources
from core.population import get_population, load_precomputed
from core.sources import fmt_vet_utc, layer, parse_iso


def hours_since(sismo: dict, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    return max((now - parse_iso(sismo["origen_iso"])).total_seconds() / 3600.0, 0.0)


def build_zone(zone: dict, config: dict, now: datetime | None = None, with_osm: bool = True):
    """Devuelve (df_celdas, ctx). ctx incluye procedencia, recursos y agregados por área."""
    f = config["fuentes"]
    sismo = get_sismo(config)
    grid = make_grid(zone["bbox"], config["rejilla"]["tamano_celda_m"])
    df = grid.copy()
    layers, hs = [], hours_since(sismo, now)

    # --- Población + área + ground-failure precomputados (reales por celda) ---
    precomp = load_precomputed(zone["id"])
    if precomp is not None:
        m = precomp.set_index("cell_id")
        df["area"] = df["cell_id"].map(m["area"]).fillna("")
        df["pop_precomp"] = df["cell_id"].map(m["pop"])
        for col in ("liquefaccion", "deslizamiento"):
            if col in precomp.columns:
                df[col] = df["cell_id"].map(m[col])
    else:
        df["area"] = ""
        df["pop_precomp"] = None
    # Celdas sin nombre de área → sector geográfico
    idx = df["area"].isna() | (df["area"] == "")
    if idx.any():
        df.loc[idx, "area"] = [_geo_sector(la, lo, zone["bbox"])
                               for la, lo in zip(df.loc[idx, "lat"], df.loc[idx, "lon"])]

    # --- Capa 1: ShakeMap real (USGS) — sismo doble combinado (MMI máx) ---
    sm_ok, n_grids_ok = False, 0
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
        df["intensidad"] = scoring.shaking_factor(df["mmi"].values)   # 0-1 para colorear
        sm_ok = True
        sm_label = f"ShakeMap combinado ({n_grids_ok} evento{'s' if n_grids_ok > 1 else ''})"
        layers.append(layer(f["usgs_shakemap"]["nombre"], f["usgs_shakemap"]["url"],
                            "ok", datetime.now(timezone.utc), sm_label))
        if n_grids_ok > 1 and "usgs_shakemap_secundario" in f:
            layers.append(layer(f["usgs_shakemap_secundario"]["nombre"],
                                f["usgs_shakemap_secundario"]["url"], "ok",
                                datetime.now(timezone.utc), "ShakeMap M7.2 incluido"))
    except Exception as e:
        df["mmi"] = float("nan")
        df["intensidad"] = float("nan")
        layers.append(layer(f["usgs_shakemap"]["nombre"], f["usgs_shakemap"]["url"],
                            "no_disponible", detalle=str(e)))

    # --- Capa 2: Población residente real por celda ---
    if precomp is not None and df["pop_precomp"].notna().any():
        pop_raw, pop_src = df["pop_precomp"].fillna(0.0).values, "worldpop_precomp"
    else:
        pop_raw, pop_src = get_population(df["lat"].values, df["lon"].values, config, zone)
    pop_ok = pop_raw is not None
    if pop_ok:
        df["pop"] = np.round(np.asarray(pop_raw, dtype=float)).astype(float)
        src_label = {"worldpop_precomp": "WorldPop por celda (precomputado)",
                     "local": "WorldPop TIF local", "remota": "WorldPop HTTP",
                     "api": "WorldPop API", "censo_ine": "Censo INE Venezuela 2011"}.get(pop_src, pop_src)
        pop_url = (f["worldpop"]["url"] if pop_src != "censo_ine"
                   else "https://www.ine.gov.ve/index.php/estadisticas-sociales/demograficas-y-vitales/censo-de-poblacion-y-vivienda")
        layers.append(layer(src_label, pop_url,
                            "proyeccion" if pop_src == "censo_ine" else "ok",
                            datetime.now(timezone.utc), f"Población residente — {src_label}"))
    else:
        df["pop"] = float("nan")
        layers.append(layer(f["worldpop"]["nombre"], f["worldpop"]["url"], "no_disponible"))

    # --- Capa 3: Ground-failure (peligro real por ubicación) ---
    gf_cell = ("liquefaccion" in df.columns) or ("deslizamiento" in df.columns)
    if gf_cell:
        layers.append(layer(f["usgs_ground_failure"]["nombre"], f["usgs_ground_failure"]["url"],
                            "ok", datetime.now(timezone.utc),
                            "Licuefacción (Zhu 2017) + deslizamiento (Jessee 2018) por celda"))

    # --- Recursos críticos reales (OSM) ---
    if with_osm:
        resources = fetch_resources(tuple(zone["bbox"]), f["osm"]["overpass"],
                                    ttl=config.get("osm_ttl_segundos", 1800))
        if not resources.empty and not resources.attrs.get("error"):
            resources = assign_areas(resources, zone["bbox"])
        layers.append(layer(
            f["osm"]["nombre"], f["osm"]["url"],
            "no_disponible" if resources.attrs.get("error") else "ok",
            None if resources.attrs.get("error") else datetime.now(timezone.utc),
            f"{len(resources)} recursos"))
    else:
        resources = pd.DataFrame(columns=["nombre", "tipo", "etiqueta", "lat", "lon"])

    # --- Agregados por área/barrio (vista informativa) ---
    areas = _area_aggregates(df) if sm_ok else []

    ctx = {
        "modo": "operativo", "sismo": sismo, "hours_since": hs,
        "pop_available": pop_ok, "pop_src": pop_src,
        "shakemap_ok": sm_ok, "n_shakemaps": n_grids_ok,
        "gf_cell": gf_cell,
        "areas": areas,
        "mmi_max": float(np.nanmax(df["mmi"].values)) if sm_ok else None,
        "poblacion_total": int(np.nansum(df["pop"].values)) if pop_ok else None,
        "resources": resources, "layers": layers,
        "pager": sismo.get("pager"), "alert_pager": sismo.get("alert_pager"),
        "ground_failure": sismo.get("ground_failure"),
        "sismos_adicionales": sismo.get("sismos_adicionales", []),
        "updated_at": fmt_vet_utc(), "fuentes": f,
    }
    return df, ctx


def _area_aggregates(df: pd.DataFrame) -> list:
    """Resumen por área/barrio: intensidad, población y peligro. Ordenado por MMI."""
    agg = {
        "poblacion": ("pop", "sum"),
        "mmi_max": ("mmi", "max"),
        "mmi_mean": ("mmi", "mean"),
        "n_celdas": ("cell_id", "count"),
    }
    if "liquefaccion" in df.columns:
        agg["liquefaccion_max"] = ("liquefaccion", "max")
    if "deslizamiento" in df.columns:
        agg["deslizamiento_max"] = ("deslizamiento", "max")
    g = df.groupby("area").agg(**agg).reset_index()
    g = g.sort_values("mmi_max", ascending=False)
    return g.to_dict("records")
