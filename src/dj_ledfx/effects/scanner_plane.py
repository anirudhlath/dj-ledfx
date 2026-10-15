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
from dj_ledfx.effects.fx import Fx, planes
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
        glow = band(heights, _height(ctx), float(values["width"]))
        frame = palette_at(self._ramp, glow)  # an array of its own, float32
        frame *= np.float32(values["level"])
        return frame

    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
        """The plane: level, at its height between the floor and the ceiling (with no
        ceiling, the zone's bottom and top, as height01 has them), in its own colour. None
        when that span is nothing (no ceiling, and every LED at one height): a plane of no
        thickness isn't drawn."""
        ceiling = leds.space.ceiling
        if ceiling is None or ceiling <= 0.0:
            low, high = (float(corner[2]) for corner in leds.bounds)
        else:
            low, high = 0.0, ceiling
        span = high - low
        if span <= 0.0:
            return None
        point = (*leds.centre[:2], low + _height(ctx) * span)
        colour = self._ramp[-1] * np.float32(self._values["level"])
        return Fx(
            planes=planes(point, (0.0, 0.0, 1.0), 2.0 * self._values["width"] * span, colour)
        )


def _height(ctx: RenderContext) -> float:
    """Where the plane is, 0 on the floor to 1 at the ceiling: up in one beat, down in the
    next."""
    return raised_cosine(ctx.beats % 2.0 / 2.0)
