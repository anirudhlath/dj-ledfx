"""Small helpers the field effects share (spec §5.1): anchors, distances, bearings, height,
a soft band and smoothstep (float palettes are in color.py). Pure numpy, no state."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, overload

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.types import clamp01

if TYPE_CHECKING:
    from dj_ledfx.effects.ledset import LedSet

F32 = NDArray[np.float32]


def anchor_or_centre(leds: LedSet, anchor: str) -> F32:
    """The named anchor's position, or the middle of the zone's LEDs when the map has no
    such anchor (a zone without a map, or an anchor since deleted)."""
    point = leds.anchors.get(anchor) if anchor else None
    return leds.centre if point is None else np.asarray(point, dtype=np.float32)


def distances(leds: LedSet, point: F32) -> F32:
    """Each LED's distance from the point, in metres."""
    return np.asarray(np.linalg.norm(leds.pos - point, axis=1), dtype=np.float32)


def reach(
    leds: LedSet, point: NDArray[np.floating[Any]], least: float = 0.0
) -> NDArray[np.float64] | None:
    """Each LED's distance from the point as a share of the zone's reach from it, 0..1: 0 at
    the point, 1 at the zone's frame's farthest corner (LedSet.bounds). A moved set keeps
    the frame, so a layer's mirror or transform moves the reach with the LEDs rather than
    fitting it to them again. None: the frame reaches no farther than `least`."""
    centre = np.asarray(point, dtype=np.float64)
    low, high = (corner.astype(np.float64) for corner in leds.bounds)
    radius = float(np.linalg.norm(np.maximum(np.abs(centre - low), np.abs(high - centre))))
    if radius < max(least, 1e-9):
        return None
    away = np.linalg.norm(leds.pos.astype(np.float64) - centre, axis=1)
    shares: NDArray[np.float64] = np.clip(away / radius, 0.0, 1.0)
    return shares


def bearing(leds: LedSet, anchor: str) -> NDArray[np.float64]:
    """Each LED's bearing around the anchor (the middle of the zone without one), seen from
    above, in turns: 0 east, a quarter north, -0.5 to 0.5."""
    offset = leds.pos.astype(np.float64) - anchor_or_centre(leds, anchor)
    turns: NDArray[np.float64] = np.arctan2(offset[:, 1], offset[:, 0]) / (2.0 * math.pi)
    return turns


def band(x: NDArray[np.floating[Any]], centre: float, width: float) -> F32:
    """A soft band of light along x: 1 at the centre, falling away as a Gaussian, e^-1 one
    width out. Float32, in an array of its own."""
    gap: F32 = np.subtract(x, np.float32(centre), dtype=np.float32)
    gap /= np.float32(width)
    gap *= gap
    np.negative(gap, out=gap)
    np.exp(gap, out=gap)
    return gap


def height01(leds: LedSet) -> F32:
    """Each LED's height, 0 on the floor to 1 at the ceiling. Without a ceiling (no map),
    the zone's own bottom to top."""
    ceiling = leds.space.ceiling
    if ceiling is None or ceiling <= 0.0:
        return leds.npos[:, 2].copy()
    heights: F32 = np.clip(leds.pos[:, 2] / np.float32(ceiling), 0.0, 1.0).astype(np.float32)
    return heights


@overload
def smoothstep(edge0: float, edge1: float, x: float) -> float: ...


@overload
def smoothstep(edge0: float, edge1: float, x: NDArray[np.floating[Any]]) -> F32: ...


def smoothstep(edge0: float, edge1: float, x: float | NDArray[np.floating[Any]]) -> float | F32:
    """0 below edge0, 1 above edge1, and easing's cubic between: the one soft edge, for
    each LED (float32) or for one number (a transition's, the evening's)."""
    span = edge1 - edge0 if edge1 != edge0 else 1e-9
    if isinstance(x, float | int):
        return ease_in_out(clamp01((x - edge0) / span))
    t: NDArray[np.float64] = np.clip((np.asarray(x, dtype=np.float64) - edge0) / span, 0.0, 1.0)
    return np.asarray(ease_in_out(t), dtype=np.float32)
