"""Modelo de Probabilidad de Vida (índice de prioridad SAR).

Funciones PURAS y testeables. La probabilidad de sobrevivientes NO se observa
del satélite: se modela combinando capas. Ver README / plan.

    P_vida = sacudimiento × colapso × poblacion_presente × supervivencia
             × decaimiento_temporal  + boost_reportes
"""
import numpy as np

# Vulnerabilidad estructural por tipo constructivo:
#   vuln = probabilidad relativa de colapso (0-1)
#   void = proporción esperada de huecos de supervivencia tras colapso (0-1)
# El concreto armado con colapso "panqueque" deja huecos donde puede haber
# sobrevivientes localizables; la autoconstrucción/mampostería, menos.
BUILDING_TYPES = {
    "informal":   {"vuln": 0.95, "void": 0.25},  # autoconstrucción de ladera
    "masonry":    {"vuln": 0.75, "void": 0.30},  # mampostería no confinada
    "rc_frame":   {"vuln": 0.50, "void": 0.65},  # pórtico de concreto armado
    "highrise":   {"vuln": 0.45, "void": 0.70},  # edificio alto
    "reinforced": {"vuln": 0.20, "void": 0.55},  # sismorresistente moderno
}


def shaking_factor(mmi):
    """Normaliza intensidad Mercalli (MMI) a 0-1. Relevante desde ~MMI IV-V."""
    mmi = np.asarray(mmi, dtype=float)
    return np.clip((mmi - 4.0) / 6.0, 0.0, 1.0)


def collapse_probability(mmi, vuln):
    """Probabilidad de colapso: crece con sacudimiento y vulnerabilidad."""
    return np.clip(shaking_factor(mmi) * np.asarray(vuln, dtype=float), 0.0, 1.0)


def survivability(void):
    """Mayor proporción de huecos => más probabilidad de sobrevivientes."""
    return np.clip(np.asarray(void, dtype=float), 0.0, 1.0)


def time_decay(hours_since, golden: float = 72.0):
    """Decaimiento de supervivencia. ~0.05 al acercarse a las 72 h de oro."""
    h = np.maximum(np.asarray(hours_since, dtype=float), 0.0)
    k = np.log(20.0) / golden
    return np.clip(np.exp(-k * h), 0.0, 1.0)


def normalize(x):
    """Min-max a 0-1. Devuelve ceros si el rango es nulo."""
    x = np.asarray(x, dtype=float)
    lo, hi = np.nanmin(x), np.nanmax(x)
    if not np.isfinite(hi - lo) or (hi - lo) < 1e-12:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def life_probability(mmi, vuln, void, pop_norm, hours_since, weights, boost=0.0):
    """Índice compuesto de prioridad SAR (sin normalizar).

    pop_norm: población presente ya normalizada 0-1 (por zona).
    weights:  exponentes por factor + 'factor_boost_reporte' (aditivo).
    boost:    realce 0-1 por reportes de campo confirmados.
    """
    s = shaking_factor(mmi) ** weights["sacudimiento"]
    c = collapse_probability(mmi, vuln) ** weights["colapso"]
    p = np.clip(pop_norm, 0.0, 1.0) ** weights["poblacion"]
    surv = survivability(void) ** weights["supervivencia"]
    decay = time_decay(hours_since) ** weights["decaimiento_temporal"]
    base = s * c * p * surv * decay
    return base + np.asarray(boost, dtype=float) * weights["factor_boost_reporte"]


def priority_category(score_norm):
    """Clasifica score normalizado en alta/media/baja."""
    x = np.asarray(score_norm, dtype=float)
    cats = np.where(x >= 0.66, "alta", np.where(x >= 0.33, "media", "baja"))
    return cats
