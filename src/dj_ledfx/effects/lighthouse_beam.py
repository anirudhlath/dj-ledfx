"""Shockwave's beam (looks.json "shockwave"): a lighthouse beam turns around the anchor
once a bar, on the floor plane; dark elsewhere, so it adds onto the layer below."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import anchor_or_centre, band, bearing
from dj_ledfx.effects.fx import Fx, planes
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
        off = turns - ctx.bar_phase  # turns from the beam, wrapped to -0.5 to 0.5
        off += 0.5
        off %= 1.0
        off -= 0.5
        beam = band(off, 0.0, float(values["width_deg"]) / 720.0)
        beam *= np.float32(values["level"])
        frame: FloatRGB = self._colour * beam[:, None]  # float32 times float32
        return frame

    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx:
        """The beam: the upright half-plane from the anchor towards the bar's bearing, as
        wide as the beam is 1 m from the anchor, in its colour."""
        turn = 2.0 * math.pi * ctx.bar_phase
        towards = (math.cos(turn), math.sin(turn), 0.0)
        across = (-math.sin(turn), math.cos(turn), 0.0)
        width = math.radians(float(self._values["width_deg"]))  # e^-1 either side: ±width/2
        colour = self._colour * np.float32(self._values["level"])
        point = anchor_or_centre(leds, self._values["anchor"])
        return Fx(planes=planes(point, across, width, colour, ray=towards))

    def _bearing(self, leds: LedSet) -> NDArray[np.float64]:
        return bearing(leds, self._values["anchor"])
