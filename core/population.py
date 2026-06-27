"""Población ambiente ajustada por hora.

Datos reales recomendados: Meta HRSL (30 m) / WorldPop (100 m) + edificios OSM.
Mientras se integran, se generan datos SINTÉTICOS deterministas por zona
(reproducibles vía semilla) para que la app funcione sin descargas.
"""
import numpy as np
import pandas as pd

from core.scoring import BUILDING_TYPES

# Perfil por tipo de uso de zona: mezcla de tipos de edificio, población base
# por celda y "uso" dominante (define la ocupación por hora).
LAND_USE_PROFILES = {
    "oficinas": {
        "mix": {"highrise": 0.40, "rc_frame": 0.40, "reinforced": 0.20},
        "base": 320, "uso": "oficina",
    },
    "residencial_informal": {
        "mix": {"informal": 0.60, "masonry": 0.30, "rc_frame": 0.10},
        "base": 480, "uso": "residencial",
    },
    "mixto": {
        "mix": {"rc_frame": 0.40, "masonry": 0.30, "informal": 0.20, "highrise": 0.10},
        "base": 260, "uso": "mixto",
    },
}


def occupancy(uso: str, hour: float) -> float:
    """Fracción de población presente (0-1) según uso y hora (día laborable)."""
    h = hour % 24
    oficina = 0.05 + 0.92 * np.exp(-((h - 13) ** 2) / (2 * 3.0 ** 2))
    residencial = float(np.clip(0.35 + 0.45 * np.cos(2 * np.pi * (h - 3) / 24), 0.10, 0.95))
    if uso == "oficina":
        return float(oficina)
    if uso == "residencial":
        return residencial
    return float(0.5 * (oficina + residencial))  # mixto


def generate_zone_population(zone: dict, grid: pd.DataFrame, seed_salt: int = 0) -> pd.DataFrame:
    """Asigna tipo de edificio, vulnerabilidad, huecos y población base por celda."""
    profile = LAND_USE_PROFILES[zone["perfil_uso"]]
    rng = np.random.default_rng(abs(hash(zone["id"])) % (2 ** 32) + seed_salt)
    df = grid.copy()

    types = list(profile["mix"].keys())
    probs = np.array(list(profile["mix"].values()))
    probs = probs / probs.sum()
    df["building_type"] = rng.choice(types, size=len(df), p=probs)
    df["vuln"] = df["building_type"].map(lambda t: BUILDING_TYPES[t]["vuln"])
    df["void"] = df["building_type"].map(lambda t: BUILDING_TYPES[t]["void"])
    df["uso"] = profile["uso"]

    # Población base por celda: lognormal alrededor del valor del perfil.
    df["base_pop"] = np.round(
        profile["base"] * rng.lognormal(mean=0.0, sigma=0.5, size=len(df))
    ).astype(int)
    return df


def population_present(base_pop, uso: str, hour: float):
    """Población presente = base × ocupación(uso, hora)."""
    return np.asarray(base_pop, dtype=float) * occupancy(uso, hour)
