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


def _eight_pass_noise(points: np.ndarray, seed: int) -> np.ndarray:
    """value_noise3 as it was before E1: each corner hashed in its own pass."""
    mix = (np.uint64(0x9E3779B1), np.uint64(0x85EBCA77), np.uint64(0xC2B2AE3D))

    def lattice(ix: np.ndarray, iy: np.ndarray, iz: np.ndarray) -> np.ndarray:
        h = ix.astype(np.uint64) * mix[0]
        h ^= iy.astype(np.uint64) * mix[1]
        h ^= iz.astype(np.uint64) * mix[2]
        h ^= np.uint64(seed & 0xFFFFFFFF) * np.uint64(0x27D4EB2F)
        h ^= h >> np.uint64(15)
        h *= np.uint64(0x2C1B3C6D)
        h ^= h >> np.uint64(12)
        h *= np.uint64(0x297A2D39)
        h ^= h >> np.uint64(15)
        return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)

    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    cell = np.floor(p)
    frac = p - cell
    base = cell.astype(np.int64)
    weight = frac * frac * (3.0 - 2.0 * frac)
    total = np.zeros(len(p))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                value = lattice(base[:, 0] + dx, base[:, 1] + dy, base[:, 2] + dz)
                wx = weight[:, 0] if dx else 1.0 - weight[:, 0]
                wy = weight[:, 1] if dy else 1.0 - weight[:, 1]
                wz = weight[:, 2] if dz else 1.0 - weight[:, 2]
                total += value * wx * wy * wz
    return total


def test_value_noise_is_bit_identical_to_the_eight_pass_hash() -> None:
    far = np.random.default_rng(5).uniform(-1e6, 1e6, size=(200, 3))
    for points in (GRID, far, GRID * 0.37):
        for seed in (0, 7, 2**40 + 3, -5):
            assert np.array_equal(value_noise3(points, seed), _eight_pass_noise(points, seed))
