"""Color carousel's field (looks.json "carousel"): each LED's hue is its angle around the
zone's middle, or an anchor, so a rainbow circles the room once every turn_s. A lamp with
one LED has one hue; a strip spans the part of the rainbow its angles cover."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

_CHANNELS = np.array([5.0, 3.0, 1.0])  # red, green, blue in the HSV-to-RGB formula


def hsv_float(hue: NDArray[np.floating], saturation: float, value: float) -> FloatRGB:
    """Float RGB for each hue (0..1) at one saturation and value."""
    k = (_CHANNELS + np.asarray(hue, dtype=np.float64)[:, None] * 6.0) % 6.0
    rgb = value - value * saturation * np.clip(np.minimum(k, 4.0 - k), 0.0, 1.0)
    return rgb.astype(np.float32)


class ColorCarousel(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": EffectParam(
                type="anchor",
                default="",
                label="Centre",
                description="The rainbow circles this; none: the middle of the zone",
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
            "level": EffectParam(
                type="float",
                default=0.9,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Level",
                bindable=True,
            ),
        }

    def __init__(
        self,
        anchor: str = "",
        turn_s: float = 60.0,
        saturation: float = 1.0,
        level: float = 0.9,
    ) -> None:
        self._apply_params(anchor=anchor, turn_s=turn_s, saturation=saturation, level=level)

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        offset = leds.pos.astype(np.float64) - anchor_or_centre(leds, values["anchor"])
        angle = np.arctan2(offset[:, 1], offset[:, 0]) / (2.0 * math.pi)
        hue = (angle + ctx.t / float(values["turn_s"])) % 1.0
        return hsv_float(hue, float(values["saturation"]), float(values["level"]))
