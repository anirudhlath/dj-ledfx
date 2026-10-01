"""Shockwave's beam (looks.json "shockwave"): a lighthouse beam turns around the anchor
once a bar, on the floor plane; dark elsewhere, so it adds onto the layer below."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import band, bearing
from dj_ledfx.effects.params import EffectParam, anchor_param, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

BEAM_COLOUR = "#fff1d6"  # M3 ruling 17


class LighthouseBeam(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": anchor_param("Around"),
            "colour": EffectParam(type="color", default=BEAM_COLOUR, label="Beam"),
            "width_deg": EffectParam(
                type="float",
                default=20.0,
                min=5.0,
                max=120.0,
                step=1.0,
                label="Width",
                description="Degrees",
            ),
            "level": level_param(0.8),
        }

    def _prepare(self) -> None:
        super()._prepare()
        self._colour = palette_float([self._values["colour"]])[0]

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        turns = self._per_leds(leds, self._bearing)
        off = (turns - ctx.bar_phase + 0.5) % 1.0 - 0.5  # turns from the beam, -0.5 to 0.5
        beam = band(off, 0.0, float(values["width_deg"]) / 720.0) * np.float32(values["level"])
        frame: FloatRGB = (self._colour * beam[:, None]).astype(np.float32)
        return frame

    def _bearing(self, leds: LedSet) -> NDArray[np.float64]:
        return bearing(leds, self._values["anchor"])
