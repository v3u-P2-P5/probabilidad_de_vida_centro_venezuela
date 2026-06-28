"""Normalización de intensidad sísmica para el mapa informativo.

Esta app es INFORMATIVA: muestra intensidad sentida (MMI), población y peligros
reales. NO modela probabilidad de sobrevivientes. Aquí solo quedan utilidades
para colorear el mapa de intensidad de forma consistente.
"""
import numpy as np


def shaking_factor(mmi):
    """Normaliza intensidad Mercalli (MMI) a 0-1 para colorear. Relevante desde ~MMI IV."""
    mmi = np.asarray(mmi, dtype=float)
    return np.clip((mmi - 4.0) / 6.0, 0.0, 1.0)


def normalize(x):
    """Min-max a 0-1. Devuelve ceros si el rango es nulo."""
    x = np.asarray(x, dtype=float)
    lo, hi = np.nanmin(x), np.nanmax(x)
    if not np.isfinite(hi - lo) or (hi - lo) < 1e-12:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)
