"""Población.

- REAL (modo operativo): muestrea el ráster WorldPop/Meta HRSL (personas por
  píxel ~100 m). Descargar una vez con scripts/download_population.py.
- SINTÉTICA (modo demo): generador determinista, claramente rotulado.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from core.scoring import BUILDING_TYPES

ROOT = Path(__file__).resolve().parent.parent

# --- Población real -------------------------------------------------------
def population_available(raster_path: str) -> bool:
    return (ROOT / raster_path).exists() if not Path(raster_path).is_absolute() \
        else Path(raster_path).exists()


def sample_population_raster(lats, lons, raster_path: str):
    """Muestrea el ráster en cada (lat, lon). Devuelve array o None si no hay ráster."""
    path = Path(raster_path)
    if not path.is_absolute():
        path = ROOT / raster_path
    if not path.exists():
        return None
    import rasterio  # importación perezosa: la app corre aunque no esté el ráster
    with rasterio.open(path) as src:
        vals = np.array([v[0] for v in src.sample(zip(np.asarray(lons), np.asarray(lats)))],
                        dtype=float)
    nodata = src.nodata if 'src' in dir() else None
    vals[~np.isfinite(vals)] = 0.0
    vals[vals < 0] = 0.0
    return vals


# --- Población sintética (SOLO demo) --------------------------------------
LAND_USE_PROFILES = {
    "oficinas": {"mix": {"highrise": 0.40, "rc_frame": 0.40, "reinforced": 0.20},
                 "base": 320, "uso": "oficina"},
    "residencial_informal": {"mix": {"informal": 0.60, "masonry": 0.30, "rc_frame": 0.10},
                             "base": 480, "uso": "residencial"},
    "mixto": {"mix": {"rc_frame": 0.40, "masonry": 0.30, "informal": 0.20, "highrise": 0.10},
              "base": 260, "uso": "mixto"},
}


def occupancy(uso: str, hour: float) -> float:
    """Fracción presente (0-1) por uso y hora (día laborable). Solo modo demo."""
    h = hour % 24
    oficina = 0.05 + 0.92 * np.exp(-((h - 13) ** 2) / (2 * 3.0 ** 2))
    residencial = float(np.clip(0.35 + 0.45 * np.cos(2 * np.pi * (h - 3) / 24), 0.10, 0.95))
    if uso == "oficina":
        return float(oficina)
    if uso == "residencial":
        return residencial
    return float(0.5 * (oficina + residencial))


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
