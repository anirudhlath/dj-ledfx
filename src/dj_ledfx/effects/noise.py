"""Seeded 3D value noise for field effects: smooth, repeatable and vectorised.

Each whole-number lattice point gets a value 0..1 from a hash of its coordinates and the
seed; between lattice points the values blend with a smoothstep. fbm3 sums octaves.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.easing import ease_in_out

_MIX = (np.uint64(0x9E3779B1), np.uint64(0x85EBCA77), np.uint64(0xC2B2AE3D))


def _lattice(base: NDArray[np.int64], seed: int) -> NDArray[np.float64]:
    """The value 0..1 at each (N, 3) cell's eight corners, as (2, 2, 2, N): x, y and z
    each hashed once for the cell's low and high side, the sides XORed together, then
    one finaliser. (XOR is order-free, so this is the per-corner hash exactly.)"""
    sides = np.stack([base, base + 1]).astype(np.uint64)  # (2, N, 3); uint64 wraps
    hx = sides[:, :, 0] * _MIX[0]
    hy = sides[:, :, 1] * _MIX[1]
    hz = sides[:, :, 2] * _MIX[2]
    h = hx[:, None, None, :] ^ hy[None, :, None, :] ^ hz[None, None, :, :]
    h ^= np.uint64(seed & 0xFFFFFFFF) * np.uint64(0x27D4EB2F)
    h ^= h >> np.uint64(15)
    h *= np.uint64(0x2C1B3C6D)
    h ^= h >> np.uint64(12)
    h *= np.uint64(0x297A2D39)
    h ^= h >> np.uint64(15)
    values: NDArray[np.float64] = (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)
    return values


def value_noise3(points: NDArray[np.floating], seed: int) -> NDArray[np.float64]:
    """Noise 0..1 at each (N, 3) point."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    cell = np.floor(p)
    frac = p - cell
    weight = ease_in_out(frac)
    sides = np.stack([1.0 - weight, weight])  # (2, N, 3): the low side's weight, the high's
    wx = sides[:, None, None, :, 0]
    wy = sides[None, :, None, :, 1]
    wz = sides[None, None, :, :, 2]
    terms = (_lattice(cell.astype(np.int64), seed) * wx * wy * wz).reshape(8, len(p))
    total = np.zeros(len(p))
    for term in terms:  # corner by corner, x then y then z, as the sum always ran
        total += term
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
