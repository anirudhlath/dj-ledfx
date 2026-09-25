"""Seeded 3D value noise for field effects: smooth, repeatable and vectorised.

Each whole-number lattice point gets a value 0..1 from a hash of its coordinates and the
seed; between lattice points the values blend with a smoothstep. fbm3 sums octaves.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

_MIX = (np.uint64(0x9E3779B1), np.uint64(0x85EBCA77), np.uint64(0xC2B2AE3D))
_CORNERS = [(dx, dy, dz) for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]


def _lattice(
    ix: NDArray[np.int64], iy: NDArray[np.int64], iz: NDArray[np.int64], seed: int
) -> NDArray[np.float64]:
    # uint64 arithmetic wraps, which is what a hash wants (numpy doesn't warn for arrays).
    h = ix.astype(np.uint64) * _MIX[0]
    h ^= iy.astype(np.uint64) * _MIX[1]
    h ^= iz.astype(np.uint64) * _MIX[2]
    h ^= np.uint64(seed & 0xFFFFFFFF) * np.uint64(0x27D4EB2F)
    h ^= h >> np.uint64(15)
    h *= np.uint64(0x2C1B3C6D)
    h ^= h >> np.uint64(12)
    h *= np.uint64(0x297A2D39)
    h ^= h >> np.uint64(15)
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)


def value_noise3(points: NDArray[np.floating], seed: int) -> NDArray[np.float64]:
    """Noise 0..1 at each (N, 3) point."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    cell = np.floor(p)
    frac = p - cell
    base = cell.astype(np.int64)
    weight = frac * frac * (3.0 - 2.0 * frac)
    total = np.zeros(len(p))
    for dx, dy, dz in _CORNERS:
        value = _lattice(base[:, 0] + dx, base[:, 1] + dy, base[:, 2] + dz, seed)
        wx = weight[:, 0] if dx else 1.0 - weight[:, 0]
        wy = weight[:, 1] if dy else 1.0 - weight[:, 1]
        wz = weight[:, 2] if dz else 1.0 - weight[:, 2]
        total += value * wx * wy * wz
    return total


def fbm3(points: NDArray[np.floating], seed: int, octaves: int = 4) -> NDArray[np.float64]:
    """Octaves of value noise, each twice the frequency and half the weight, 0..1."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    total = np.zeros(len(p))
    weight, scale, weights = 1.0, 1.0, 0.0
    for octave in range(octaves):
        total += weight * value_noise3(p * scale, seed + octave)
        weights += weight
        weight *= 0.5
        scale *= 2.0
    return total / weights
