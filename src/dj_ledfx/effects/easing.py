"""Easing functions for effect animations. All accept float or NDArray."""

from __future__ import annotations

import math
from typing import Any, overload

import numpy as np
from numpy.typing import NDArray


@overload
def lerp(a: float, b: float, t: float | NDArray[np.float64]) -> float | NDArray[np.float64]: ...


@overload
def lerp(a: NDArray[np.float32], b: NDArray[np.float32], t: float) -> NDArray[np.float32]: ...


def lerp(
    a: float | NDArray[np.float32],
    b: float | NDArray[np.float32],
    t: float | NDArray[np.float64],
) -> float | NDArray[np.floating[Any]]:
    return a + (b - a) * t


def ease_in(t: float | NDArray[np.float64], power: float = 2.0) -> float | NDArray[np.float64]:
    return t**power


def ease_out(t: float | NDArray[np.float64], power: float = 2.0) -> float | NDArray[np.float64]:
    return 1.0 - (1.0 - t) ** power


@overload
def ease_in_out(t: float) -> float: ...


@overload
def ease_in_out(t: NDArray[np.float64]) -> NDArray[np.float64]: ...


def ease_in_out(t: float | NDArray[np.float64]) -> float | NDArray[np.float64]:
    """The smoothstep cubic, 3t² - 2t³: field_tools.smoothstep and the noise's blend use
    it too."""
    return t * t * (3.0 - 2.0 * t)


def raised_cosine(p: float) -> float:
    """0 at p = 0, rising smoothly to 1 at p = 0.5 and back to 0 at p = 1: one breath, or
    one there-and-back, per unit of p."""
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * p)


def sine_ease(
    t: float | NDArray[np.float64],
) -> float | NDArray[np.float64]:
    if isinstance(t, np.ndarray):
        return np.sin(t * (np.pi / 2.0))
    return math.sin(t * (math.pi / 2.0))
