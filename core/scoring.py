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


def impact_exposure(mmi, pop, liq=None, desl=None):
    """Índice de AFECTACIÓN probable (sin normalizar) para colorear el mapa de calor.

    Combina capas REALES para resaltar DÓNDE se concentra el daño y la gente —
    es decir, a dónde conviene ir a prestar ayuda:

        afectación = sacudimiento(MMI) × población_expuesta × (1 + realce_terreno)

    Dentro de una zona pequeña la MMI apenas varía (el epicentro está lejos), así
    que la población expuesta es el discriminador real: los barrios densos pesan
    mucho más que parques o el mar (población ≈ 0 → afectación 0). El fallo de
    terreno (licuefacción/deslizamiento USGS) realza los puntos susceptibles.

    NO es probabilidad de supervivientes ni un recuento de víctimas: es un índice
    relativo para orientar la respuesta.
    """
    shaking = shaking_factor(mmi)                              # 0-1
    pop = np.asarray(pop, dtype=float)
    pop = np.where(np.isfinite(pop), np.clip(pop, 0.0, None), 0.0)
    realce = np.zeros_like(shaking, dtype=float)
    for capa in (liq, desl):
        if capa is not None:
            realce = np.maximum(realce, np.nan_to_num(np.asarray(capa, dtype=float)))
    return shaking * pop * (1.0 + 3.0 * realce)
