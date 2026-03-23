"""Easing functions for effect animations. All accept float or NDArray."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def lerp(
    a: float, b: float, t: float | NDArray[np.float64]
) -> float | NDArray[np.float64]:
    return a + (b - a) * t


def ease_in(
    t: float | NDArray[np.float64], power: float = 2.0
) -> float | NDArray[np.float64]:
    return t**power


def ease_out(
    t: float | NDArray[np.float64], power: float = 2.0
) -> float | NDArray[np.float64]:
    return 1.0 - (1.0 - t) ** power


def ease_in_out(
    t: float | NDArray[np.float64],
) -> float | NDArray[np.float64]:
    return 3.0 * t**2 - 2.0 * t**3


def sine_ease(
    t: float | NDArray[np.float64],
) -> float | NDArray[np.float64]:
    if isinstance(t, np.ndarray):
        return np.sin(t * (np.pi / 2.0))
    return math.sin(t * (math.pi / 2.0))
