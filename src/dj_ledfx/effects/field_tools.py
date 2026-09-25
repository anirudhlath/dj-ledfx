"""Small helpers the field effects share (spec §5.1): anchors, distances, height and
float palettes. Pure numpy, no state."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import hex_to_rgb

if TYPE_CHECKING:
    from dj_ledfx.effects.ledset import LedSet

F32 = NDArray[np.float32]


def anchor_or_centre(leds: LedSet, anchor: str) -> F32:
    """The named anchor's position, or the middle of the zone's LEDs when the map has no
    such anchor (a zone without a map, or an anchor since deleted)."""
    point = leds.anchors.get(anchor) if anchor else None
    if point is not None:
        return np.asarray(point, dtype=np.float32)
    if leds.count == 0:
        return np.zeros(3, dtype=np.float32)
    middle = (leds.pos.min(axis=0) + leds.pos.max(axis=0)) / 2.0
    return np.asarray(middle, dtype=np.float32)


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


def palette_float(colours: Sequence[str]) -> F32:
    """Hex colours as (k, 3) floats, 0..1."""
    return np.array([hex_to_rgb(colour) for colour in colours], dtype=np.float32) / 255.0


def palette_at(palette: F32, t: NDArray[np.floating]) -> F32:
    """Colours at t (0..1, clipped) along the palette, blended between neighbouring stops."""
    stops = len(palette)
    if stops == 1:
        return np.repeat(palette, len(t), axis=0)
    x = np.clip(np.asarray(t, dtype=np.float32), 0.0, 1.0) * np.float32(stops - 1)
    low = np.minimum(x.astype(np.intp), stops - 2)
    blend = (x - low)[:, None]
    colours: F32 = (palette[low] * (1.0 - blend) + palette[low + 1] * blend).astype(np.float32)
    return colours


def smoothstep(edge0: float, edge1: float, x: NDArray[np.floating]) -> F32:
    span = edge1 - edge0 if edge1 != edge0 else 1e-9
    t = np.clip((np.asarray(x, dtype=np.float32) - edge0) / span, 0.0, 1.0)
    smooth: F32 = (t * t * (3.0 - 2.0 * t)).astype(np.float32)
    return smooth
