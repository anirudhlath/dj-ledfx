"""Sunset's field (looks.json "sunset"): warm at the floor to deep blue at the ceiling.

The horizon rises and settles once every drift_s. With a sun anchor, the gradient also
cools with the distance from it (engine spec §9: "Sunset is warmest at its anchor").
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import height01
from dj_ledfx.effects.params import EffectParam, level_param
from dj_ledfx.spatial.mapping import RadialMapping

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
            "level": level_param(0.85),
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

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        sway = HORIZON_SWAY * math.sin(2.0 * math.pi * ctx.t / float(values["drift_s"]))
        colours = palette_at(self._palette, self._per_leds(leds, self._along) - np.float32(sway))
        return (colours * np.float32(values["level"])).astype(np.float32)

    def _along(self, leds: LedSet) -> NDArray[np.float32]:
        """Each LED's place on the gradient before the horizon sways: its height, bent by
        warmth (0.5 is straight; more bends it so the warm stops climb higher), and with
        a sun, partly its distance from the sun."""
        values = self._values
        along = height01(leds) ** np.float32(2.0 ** (2.0 * float(values["warmth"]) - 1.0))
        sun = leds.anchors.get(values["anchor"]) if values["anchor"] else None
        if sun is not None:
            centre = (float(sun[0]), float(sun[1]), float(sun[2]))
            reach = RadialMapping(center=centre).map_positions(leds.pos.astype(np.float64))
            if reach.any():  # every LED at the sun: nothing to cool
                along = ((1.0 - ANCHOR_SHARE) * along + ANCHOR_SHARE * reach).astype(np.float32)
        return along
