"""Small helpers the field effects share (spec §5.1): anchors, distances, height and
smoothstep (float palettes are in color.py). Pure numpy, no state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.easing import ease_in_out

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


def height01(leds: LedSet) -> F32:
    """Each LED's height, 0 on the floor to 1 at the ceiling. Without a ceiling (no map),
    the zone's own bottom to top."""
    ceiling = leds.space.ceiling
    if ceiling is None or ceiling <= 0.0:
        return leds.npos[:, 2].copy()
    heights: F32 = np.clip(leds.pos[:, 2] / np.float32(ceiling), 0.0, 1.0).astype(np.float32)
    return heights


def smoothstep(edge0: float, edge1: float, x: NDArray[np.floating[Any]]) -> F32:
    """0 below edge0, 1 above edge1, and easing's cubic between."""
    span = edge1 - edge0 if edge1 != edge0 else 1e-9
    t: NDArray[np.float64] = np.clip((np.asarray(x, dtype=np.float64) - edge0) / span, 0.0, 1.0)
    return np.asarray(ease_in_out(t), dtype=np.float32)
