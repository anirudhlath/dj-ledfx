"""Color math utilities for effects."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.types import RGB, FloatRGB


def hex_to_rgb(hex_color: str) -> RGB:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def to_float_rgb(colours: NDArray[np.uint8]) -> FloatRGB:
    """8-bit colours as the 0..1 floats that field effects render."""
    out = colours.astype(np.float32)
    out *= np.float32(1.0 / 255.0)
    return out


_HSV_CHANNELS = np.array([5.0, 3.0, 1.0])  # red, green, blue in the HSV-to-RGB formula


def hsv_float(
    h: NDArray[np.floating[Any]],
    s: float | NDArray[np.floating[Any]],
    v: float | NDArray[np.floating[Any]],
) -> NDArray[np.float64]:
    """Vectorised HSV to RGB floats, 0..1. h, s and v in [0, 1]; s and v are one value or
    one per hue. A hue outside [0, 1] wraps round."""
    hue = np.asarray(h, dtype=np.float64)[:, None]
    sat = np.asarray(s, dtype=np.float64)[..., None]
    val = np.asarray(v, dtype=np.float64)[..., None]
    k = (_HSV_CHANNELS + hue * 6.0) % 6.0
    rgb: NDArray[np.float64] = val - val * sat * np.clip(np.minimum(k, 4.0 - k), 0.0, 1.0)
    return rgb


def palette_float(colours: Sequence[str]) -> FloatRGB:
    """Hex colours as (k, 3) floats, 0..1."""
    return np.array([hex_to_rgb(colour) for colour in colours], dtype=np.float32) / 255.0


def palette_at(palette: FloatRGB, t: NDArray[np.floating[Any]]) -> FloatRGB:
    """Colours at t (0..1, clipped) along the palette, blended between neighbouring stops.
    Linear, so the palette may be in any scale: palette_lerp passes 0..255."""
    stops = len(palette)
    if stops == 1:
        return np.repeat(palette, len(t), axis=0)
    x = np.clip(np.asarray(t, dtype=np.float32), 0.0, 1.0) * np.float32(stops - 1)
    low = np.minimum(x.astype(np.intp), stops - 2)
    blend = (x - low)[:, None]
    colours: FloatRGB = (palette[low] * (1.0 - blend) + palette[low + 1] * blend).astype(
        np.float32
    )
    return colours


def hsv_to_rgb_array(
    h: NDArray[np.float64],
    s: float | NDArray[np.float64],
    v: float | NDArray[np.float64],
) -> NDArray[np.uint8]:
    """hsv_float in 8 bits (truncated). h in [0,1], s in [0,1], v in [0,1]."""
    return _eight_bit(hsv_float(h, s, v) * 255.0)


def palette_lerp(
    palette: list[RGB],
    positions: NDArray[np.float64],
) -> NDArray[np.uint8]:
    """palette_at on 8-bit colours, in 8 bits (truncated)."""
    return _eight_bit(palette_at(np.asarray(palette, dtype=np.float32), positions))


def _eight_bit(values: NDArray[np.floating[Any]]) -> NDArray[np.uint8]:
    out: NDArray[np.uint8] = np.clip(values, 0, 255).astype(np.uint8)
    return out
