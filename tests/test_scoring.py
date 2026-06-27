"""Tests del modelo de scoring (funciones puras)."""
import numpy as np

from core import scoring
from core.population import occupancy

WEIGHTS = {
    "sacudimiento": 1.0, "colapso": 1.0, "poblacion": 1.0,
    "supervivencia": 1.0, "decaimiento_temporal": 1.0, "factor_boost_reporte": 0.5,
}


def test_shaking_factor_monotono_y_acotado():
    assert scoring.shaking_factor(2) == 0.0
    assert scoring.shaking_factor(10) == 1.0
    assert 0.0 < scoring.shaking_factor(7) < 1.0


def test_time_decay_72h():
    assert scoring.time_decay(0) == 1.0
    assert scoring.time_decay(72) < 0.1          # casi agotada la ventana de oro
    assert scoring.time_decay(24) > scoring.time_decay(48)


def test_alta_vs_baja_prioridad():
    """Alta MMI + mucha población + reciente + huecos => score mayor que el caso opuesto."""
    alto = scoring.life_probability(mmi=9, vuln=0.5, void=0.65, pop_norm=1.0,
                                    hours_since=2, weights=WEIGHTS)
    bajo = scoring.life_probability(mmi=5, vuln=0.5, void=0.30, pop_norm=0.1,
                                    hours_since=2, weights=WEIGHTS)
    assert alto > bajo


def test_boost_eleva_score():
    base = scoring.life_probability(7, 0.5, 0.6, 0.5, 5, WEIGHTS, boost=0.0)
    con_boost = scoring.life_probability(7, 0.5, 0.6, 0.5, 5, WEIGHTS, boost=1.0)
    assert con_boost > base


def test_normalize_constante_devuelve_ceros():
    assert np.all(scoring.normalize([3, 3, 3]) == 0.0)


def test_priority_category():
    cats = scoring.priority_category([0.9, 0.5, 0.1])
    assert list(cats) == ["alta", "media", "baja"]


def test_ocupacion_mediodia_vs_noche():
    """A las 11:45 (laborable) la oficina está llena y la vivienda más vacía que de noche."""
    assert occupancy("oficina", 11.75) > occupancy("oficina", 3)
    assert occupancy("residencial", 3) > occupancy("residencial", 11.75)
