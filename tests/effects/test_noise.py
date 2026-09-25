from __future__ import annotations

import numpy as np

from dj_ledfx.effects.noise import fbm3, value_noise3

GRID = np.random.default_rng(3).uniform(-5.0, 5.0, size=(500, 3))


def test_value_noise_is_repeatable_in_range_and_seeded() -> None:
    first = value_noise3(GRID, seed=7)
    assert first.shape == (500,)
    assert np.array_equal(first, value_noise3(GRID, seed=7))
    assert first.min() >= 0.0 and first.max() <= 1.0
    assert not np.allclose(first, value_noise3(GRID, seed=8))
    assert first.std() > 0.1  # not flat


def test_value_noise_is_smooth() -> None:
    step = value_noise3(GRID + 1e-3, seed=7) - value_noise3(GRID, seed=7)
    assert np.abs(step).max() < 0.02


def test_value_noise_hits_its_lattice_values_at_whole_coordinates() -> None:
    corners = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [-1.0, -2.0, -3.0]])
    nudged = corners + 1e-9
    assert np.allclose(value_noise3(corners, seed=1), value_noise3(nudged, seed=1), atol=1e-6)


def test_fbm_is_in_range_and_repeatable() -> None:
    first = fbm3(GRID, seed=5)
    assert first.min() >= 0.0 and first.max() <= 1.0
    assert np.array_equal(first, fbm3(GRID, seed=5))
    assert np.array_equal(fbm3(np.zeros((0, 3)), seed=5), np.zeros(0))
