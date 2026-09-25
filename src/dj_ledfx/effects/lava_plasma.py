"""Lava's field (looks.json "lava"): a slow 3D plasma in lava colours.

Time moves through the noise along a slant of irrational steps, so the field never lines
up with an earlier one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import smoothstep
from dj_ledfx.effects.noise import fbm3
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# Crust to core; every stop has red >= green >= blue (ruling 17).
LAVA_PALETTE = ("#140200", "#6e0c00", "#d42a00", "#ff7a00", "#ffd04a")
_SLANT = np.array([(5**0.5 - 1) / 2, 2**0.5 - 1, 1.0])  # golden ratio and silver ratio steps
_FLOW = 0.2  # noise units a speed of 1 moves in a second


class LavaPlasma(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(LAVA_PALETTE), label="Palette"),
            "speed": EffectParam(
                type="float",
                default=0.3,
                min=0.05,
                max=2.0,
                step=0.05,
                label="Speed",
                bindable=True,
            ),
            "scale_m": EffectParam(
                type="float", default=1.2, min=0.3, max=5.0, step=0.1, label="Blob size"
            ),
            "level": level_param(1.0),
        }

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        points = self._per_leds(leds, self._points)
        flow = ctx.t * float(values["speed"]) * _FLOW
        heat = smoothstep(0.3, 0.72, fbm3(points + _SLANT * flow, self._seed, octaves=3))
        return (palette_at(self._palette, heat) * np.float32(values["level"])).astype(np.float32)

    def _points(self, leds: LedSet) -> NDArray[np.float64]:
        """Each LED's place in the noise: its position in blob sizes."""
        points: NDArray[np.float64] = leds.pos.astype(np.float64) / float(self._values["scale_m"])
        return points
