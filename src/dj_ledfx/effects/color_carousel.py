"""Color carousel's field (looks.json "carousel"): each LED's hue is its angle around the
zone's middle, or an anchor, so a rainbow circles the room once every turn_s. A lamp with
one LED has one hue; a strip spans the part of the rainbow its angles cover."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import hsv_float
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import bearing
from dj_ledfx.effects.params import EffectParam, anchor_param, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class ColorCarousel(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": anchor_param(
                "Centre", description="The rainbow circles this; none: the middle of the zone"
            ),
            "turn_s": EffectParam(
                type="float",
                default=60.0,
                min=10.0,
                max=600.0,
                step=5.0,
                label="Turn",
                description="Seconds for one full turn",
            ),
            "saturation": EffectParam(
                type="float", default=1.0, min=0.0, max=1.0, step=0.01, label="Saturation"
            ),
            "level": level_param(0.9),
        }

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        hue = (self._per_leds(leds, self._bearing) + ctx.t / float(values["turn_s"])) % 1.0
        rgb = hsv_float(hue, float(values["saturation"]), float(values["level"]))
        return rgb.astype(np.float32)

    def _bearing(self, leds: LedSet) -> NDArray[np.float64]:
        """Each LED's angle round the centre, in turns."""
        return bearing(leds, self._values["anchor"])
