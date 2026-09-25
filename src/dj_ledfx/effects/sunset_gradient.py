"""Sunset's field (looks.json "sunset"): warm at the floor to deep blue at the ceiling.

The horizon rises and settles once every drift_s. With a sun anchor, the gradient also
cools with the distance from it (engine spec §9: "Sunset is warmest at its anchor").
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import distances, height01, palette_at, palette_float
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# Floor to ceiling, each stop less red and more blue than the one below it (ruling 17).
SUNSET_PALETTE = ("#ff9a3c", "#f0603c", "#b8386e", "#4c2c8c", "#101c60")
HORIZON_SWAY = 0.06  # how far the horizon rises and settles, as a share of the gradient
ANCHOR_SHARE = 0.3  # with a sun anchor, the share of the gradient that is distance from it


class SunsetGradient(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list",
                default=list(SUNSET_PALETTE),
                label="Palette",
                description="Floor to ceiling",
            ),
            "level": EffectParam(
                type="float",
                default=0.85,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Level",
                bindable=True,
            ),
            "warmth": EffectParam(
                type="float",
                default=0.5,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Warmth",
                description="How high the warm colours reach",
                bindable=True,
            ),
            "anchor": EffectParam(
                type="anchor",
                default="",
                label="Sun",
                description="Warmest here; none: the floor alone",
            ),
            "drift_s": EffectParam(
                type="float",
                default=90.0,
                min=10.0,
                max=600.0,
                step=5.0,
                label="Drift",
                description="Seconds for the horizon to rise and settle",
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        level: float = 0.85,
        warmth: float = 0.5,
        anchor: str = "",
        drift_s: float = 90.0,
    ) -> None:
        self._apply_params(
            palette=list(palette or SUNSET_PALETTE),
            level=level,
            warmth=warmth,
            anchor=anchor,
            drift_s=drift_s,
        )

    def _prepare(self) -> None:
        self._palette = palette_float(self._values["palette"])

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        # warmth 0.5 is a straight gradient; more bends it so the warm stops climb higher
        along = height01(leds) ** np.float32(2.0 ** (2.0 * float(values["warmth"]) - 1.0))
        sun = leds.anchors.get(values["anchor"]) if values["anchor"] else None
        if sun is not None:
            reach = distances(leds, sun)
            far = float(reach.max())
            if far > 0.0:
                along = (1.0 - ANCHOR_SHARE) * along + ANCHOR_SHARE * reach / np.float32(far)
        sway = HORIZON_SWAY * math.sin(2.0 * math.pi * ctx.t / float(values["drift_s"]))
        colours = palette_at(self._palette, along - np.float32(sway))
        return (colours * np.float32(values["level"])).astype(np.float32)
