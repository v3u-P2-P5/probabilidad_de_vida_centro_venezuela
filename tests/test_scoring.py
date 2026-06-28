"""Tests de utilidades de intensidad (app informativa)."""
import numpy as np

from core import scoring


def test_shaking_factor_monotono_y_acotado():
    assert scoring.shaking_factor(2) == 0.0
    assert scoring.shaking_factor(10) == 1.0
    assert 0.0 < scoring.shaking_factor(7) < 1.0


def test_normalize_constante_devuelve_ceros():
    assert np.all(scoring.normalize([3, 3, 3]) == 0.0)


def test_normalize_rango():
    out = scoring.normalize([0.0, 5.0, 10.0])
    assert out[0] == 0.0 and out[-1] == 1.0 and 0.0 < out[1] < 1.0
