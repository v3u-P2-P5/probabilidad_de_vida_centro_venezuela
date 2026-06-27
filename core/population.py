"""Población.

- REAL local: muestrea el ráster WorldPop/Meta HRSL descargado localmente.
- REAL remoto: lee el ráster WorldPop directamente por HTTP (GDAL VSI / rasterio
  ≥1.3 con libcurl). Sin descarga total del TIF — solo las ventanas de cada zona.
- PROYECCIÓN ESTADÍSTICA (HAZUS): perfiles de ocupación por hora y tipo de uso,
  aplicados a la hora del terremoto (18:05 VET). Citados y etiquetados siempre.
- SINTÉTICO: solo modo demo, claramente rotulado.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from core.scoring import BUILDING_TYPES

ROOT = Path(__file__).resolve().parent.parent

# Hora local del sismo (VET = UTC-4): 22:05:11Z → 18:05 VET
HORA_SISMO_VET = 18.083   # 18 h + 5 min / 60


# --- Población real (local o remota) -----------------------------------------

def population_available(raster_path: str) -> bool:
    path = Path(raster_path)
    if not path.is_absolute():
        path = ROOT / raster_path
    return path.exists()


def sample_population_raster(lats, lons, raster_path: str):
    """Muestrea el ráster en cada (lat, lon). Devuelve array o None si no hay ráster local."""
    path = Path(raster_path)
    if not path.is_absolute():
        path = ROOT / raster_path
    if not path.exists():
        return None
    try:
        import rasterio
        with rasterio.open(path) as src:
            vals = np.array([v[0] for v in src.sample(zip(np.asarray(lons), np.asarray(lats)))],
                            dtype=float)
        vals[~np.isfinite(vals)] = 0.0
        vals[vals < 0] = 0.0
        return vals
    except Exception:
        return None


def sample_population_remote(lats, lons, url: str):
    """Intenta leer WorldPop por HTTP (GDAL VSI). Devuelve None si el servidor
    no soporta range requests (el archivo WorldPop VEN no es COG).
    """
    try:
        import rasterio
        with rasterio.open(f"/vsicurl/{url}") as src:
            vals = np.array([v[0] for v in src.sample(zip(np.asarray(lons), np.asarray(lats)))],
                            dtype=float)
        vals[~np.isfinite(vals)] = 0.0
        vals[vals < 0] = 0.0
        return vals
    except Exception:
        return None   # WorldPop VEN no es COG; ejecutar download_population.py


def get_population(lats, lons, config: dict):
    """Intenta obtener población real: local → remota → None.

    Devuelve (array_o_None, fuente_str).
    """
    raster_path = config["poblacion"]["raster_path"]
    # 1. Local
    pop = sample_population_raster(lats, lons, raster_path)
    if pop is not None:
        return pop, "local"
    # 2. Remota (HTTP range requests)
    url = config["poblacion"].get("worldpop_tif_url", "")
    if url:
        pop = sample_population_remote(lats, lons, url)
        if pop is not None:
            return pop, "remota"
    return None, "no_disponible"


# --- Proyección estadística de ocupación (HAZUS — citado) --------------------

def occupancy_stat(uso: str, hour: float) -> float:
    """Fracción de población presente por tipo de uso a una hora dada.

    Proyección estadística — metodología: FEMA HAZUS-MH 2.1, Tabla 3-6.
    Adaptado para Venezuela (día laborable, hora local VET).
    No es dato observado: es una estimación probabilística con incertidumbre ~±20%.
    """
    h = hour % 24
    if uso == "oficina":
        # Pico a las 10-16 h; inicio a las 7 h; fin a las 18 h
        return float(np.clip(0.05 + 0.90 * np.exp(-((h - 13.0) ** 2) / (2 * 3.5 ** 2)), 0.0, 1.0))
    if uso == "residencial":
        # Máximo de noche (3 h); mínimo al mediodía
        return float(np.clip(0.30 + 0.50 * np.cos(2 * np.pi * (h - 3) / 24), 0.10, 0.95))
    if uso == "comercio":
        return float(np.clip(0.10 + 0.75 * np.exp(-((h - 14.0) ** 2) / (2 * 4.0 ** 2)), 0.0, 1.0))
    # mixto
    return float(0.5 * (occupancy_stat("oficina", h) + occupancy_stat("residencial", h)))


def apply_occupancy(pop_base, zone_uso: str, hour: float = HORA_SISMO_VET) -> np.ndarray:
    """Población presente a la hora del sismo (proyección estadística HAZUS).

    hour: hora local VET al momento del terremoto (por defecto 18.08 h = 18:05).
    """
    frac = occupancy_stat(zone_uso, hour)
    return np.asarray(pop_base, dtype=float) * frac


# --- Vulnerabilidad estructural por zona (proyección estadística) -------------

def zone_vuln_void(zone_id: str, config: dict) -> tuple:
    """Vuln y void medios ponderados por inventario estructural de la zona.

    Proyección estadística — metodología: USGS PAGER + HAZUS fragility.
    Devuelve (vuln_media, void_media).
    """
    inv = config.get("inventario_estructural", {}).get(zone_id, {})
    if not inv:
        # Fallback: valores medios conservadores
        return 0.55, 0.45
    total = sum(inv.values()) or 1.0
    vuln = sum(inv[t] * BUILDING_TYPES[t]["vuln"] for t in inv if t in BUILDING_TYPES) / total
    void = sum(inv[t] * BUILDING_TYPES[t]["void"] for t in inv if t in BUILDING_TYPES) / total
    return float(vuln), float(void)


# --- Datos sintéticos (SOLO demo) --------------------------------------------

LAND_USE_PROFILES = {
    "oficinas": {"mix": {"highrise": 0.40, "rc_frame": 0.40, "reinforced": 0.20},
                 "base": 320, "uso": "oficina"},
    "residencial_informal": {"mix": {"informal": 0.60, "masonry": 0.30, "rc_frame": 0.10},
                             "base": 480, "uso": "residencial"},
    "mixto": {"mix": {"rc_frame": 0.40, "masonry": 0.30, "informal": 0.20, "highrise": 0.10},
              "base": 260, "uso": "mixto"},
}


def occupancy(uso: str, hour: float) -> float:
    """Solo modo demo — usar occupancy_stat() en operativo."""
    return occupancy_stat(uso, hour)


def generate_zone_population(zone: dict, grid: pd.DataFrame) -> pd.DataFrame:
    profile = LAND_USE_PROFILES.get(zone.get("perfil_uso", "mixto"), LAND_USE_PROFILES["mixto"])
    rng = np.random.default_rng(abs(hash(zone["id"])) % (2 ** 32))
    df = grid.copy()
    types = list(profile["mix"].keys())
    probs = np.array(list(profile["mix"].values()))
    probs = probs / probs.sum()
    df["building_type"] = rng.choice(types, size=len(df), p=probs)
    df["vuln"] = df["building_type"].map(lambda t: BUILDING_TYPES[t]["vuln"])
    df["void"] = df["building_type"].map(lambda t: BUILDING_TYPES[t]["void"])
    df["uso"] = profile["uso"]
    df["base_pop"] = np.round(profile["base"] * rng.lognormal(0.0, 0.5, len(df))).astype(int)
    return df


def population_present(base_pop, uso: str, hour: float):
    return np.asarray(base_pop, dtype=float) * occupancy(uso, hour)
