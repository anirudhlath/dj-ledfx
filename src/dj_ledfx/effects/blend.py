"""Layer blending (spec §5.2): layers composite bottom to top in float RGB. Nothing here
clamps: colour stays float through the stack and is clamped once, at send (spec §4.1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from dj_ledfx.types import FloatRGB

BLEND_MODES = ("normal", "add", "screen", "multiply", "max")


def blend_into(base: FloatRGB, top: FloatRGB, mode: str, opacity: float) -> None:
    """Composite `top` onto `base`, in place, at `opacity` (0..1)."""
    weight = np.float32(opacity)
    if mode == "add":
        base += top * weight
        return
    if mode == "normal":
        mixed = top
    elif mode == "screen":
        mixed = base + top - base * top
    elif mode == "multiply":
        mixed = base * top
    elif mode == "max":
        mixed = np.maximum(base, top)
    else:
        raise ValueError(f"Unknown blend mode {mode!r}; expected one of {', '.join(BLEND_MODES)}")
    base += (mixed - base) * weight
