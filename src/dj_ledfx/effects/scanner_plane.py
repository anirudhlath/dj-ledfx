"""Scanner's plane (looks.json "scanner"): a level plane of light sweeps from the floor to
the ceiling and back every two beats."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_at, palette_float
from dj_ledfx.effects.easing import raised_cosine
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import band, height01
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

PLANE_COLOUR = "#7cf3ff"  # M3 ruling 17
REST_COLOUR = "#03050a"


class ScannerPlane(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "colour": EffectParam(type="color", default=PLANE_COLOUR, label="Plane"),
            "rest": EffectParam(type="color", default=REST_COLOUR, label="Between"),
            "width": EffectParam(
                type="float",
                default=0.12,
                min=0.02,
                max=0.5,
                step=0.01,
                label="Thickness",
                description="A share of the floor-to-ceiling height",
                bindable=True,
            ),
            "level": level_param(0.9),
        }

    def _prepare(self) -> None:
        super()._prepare()
        self._ramp = palette_float([self._values["rest"], self._values["colour"]])

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        heights: NDArray[np.float32] = self._per_leds(leds, height01)
        cycle = ctx.beats % 2.0 / 2.0  # up in one beat, down in the next
        glow = band(heights, raised_cosine(cycle), float(values["width"]))
        frame = palette_at(self._ramp, glow)  # an array of its own, float32
        frame *= np.float32(values["level"])
        return frame
