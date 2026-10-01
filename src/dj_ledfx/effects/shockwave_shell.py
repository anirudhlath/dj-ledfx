"""Shockwave's shell (looks.json "shockwave"): a sphere of light leaves the anchor on every
beat and fades as it spreads, reaching reach_m by the next beat."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import anchor_or_centre, distances
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

SHELL_COLOUR = "#3d7bff"  # M3 ruling 17
REST_COLOUR = "#04060f"


class ShockwaveShell(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": EffectParam(
                type="anchor",
                default="",
                label="From",
                description="None: the middle of the zone",
            ),
            "colour": EffectParam(type="color", default=SHELL_COLOUR, label="Shell"),
            "rest": EffectParam(type="color", default=REST_COLOUR, label="Between"),
            "reach_m": EffectParam(
                type="float",
                default=6.0,
                min=1.0,
                max=20.0,
                step=0.5,
                label="Reach",
                description="Metres the shell travels in a beat",
                bindable=True,
            ),
            "shell_m": EffectParam(
                type="float", default=0.6, min=0.1, max=3.0, step=0.1, label="Thickness"
            ),
            "level": level_param(0.9),
        }

    def _prepare(self) -> None:
        super()._prepare()
        self._colour, self._rest = palette_float([self._values["colour"], self._values["rest"]])

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        away = self._per_leds(leds, self._away)
        front = np.float32(float(values["reach_m"]) * ctx.beat_phase)
        gap = (away - front) / np.float32(values["shell_m"])
        glow = np.exp(-(gap * gap)) * np.float32((1.0 - ctx.beat_phase) ** 2)
        out = self._rest + (self._colour - self._rest) * glow[:, None]
        frame: FloatRGB = (out * np.float32(values["level"])).astype(np.float32)
        return frame

    def _away(self, leds: LedSet) -> NDArray[np.float32]:
        return distances(leds, anchor_or_centre(leds, self._values["anchor"]))
