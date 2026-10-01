"""Shockwave's beam (looks.json "shockwave"): a lighthouse beam turns around the anchor
once a bar, on the floor plane; dark elsewhere, so it adds onto the layer below."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

BEAM_COLOUR = "#fff1d6"  # M3 ruling 17


class LighthouseBeam(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": EffectParam(
                type="anchor",
                default="",
                label="Around",
                description="None: the middle of the zone",
            ),
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
        bearing = self._per_leds(leds, self._bearing)
        turn = np.float32(2.0 * math.pi)
        off = (bearing - turn * np.float32(ctx.bar_phase) + turn / 2) % turn - turn / 2
        half = np.float32(math.radians(float(values["width_deg"])) / 2.0)
        beam = np.exp(-np.square(off / half)) * np.float32(values["level"])
        frame: FloatRGB = (self._colour * beam[:, None]).astype(np.float32)
        return frame

    def _bearing(self, leds: LedSet) -> NDArray[np.float32]:
        """Each LED's bearing around the anchor, seen from above: 0 east, π/2 north."""
        centre = anchor_or_centre(leds, self._values["anchor"])
        east, north = leds.pos[:, 0] - centre[0], leds.pos[:, 1] - centre[1]
        bearing: NDArray[np.float32] = np.arctan2(north, east).astype(np.float32)
        return bearing
