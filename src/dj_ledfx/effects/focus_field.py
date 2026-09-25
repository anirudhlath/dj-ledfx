"""Focus's field (looks.json "focus"): calm and warm near an anchor, busier and more
colourful further away.

Inside calm_m of the anchor the LEDs hold one warm colour. From calm_m to twice that they
blend into a moving field of saturated colours whose brightness pulses.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import (
    anchor_or_centre,
    distances,
    palette_at,
    palette_float,
    smoothstep,
)
from dj_ledfx.effects.noise import fbm3
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

CALM_COLOUR = "#ffb070"
FOCUS_PALETTE = ("#ff3d7f", "#ffb000", "#27e0a3", "#3d7bff", "#b44dff")  # ruling 17


class FocusField(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": EffectParam(
                type="anchor",
                default="",
                label="Calm around",
                description="None: the middle of the zone",
            ),
            "calm": EffectParam(type="color", default=CALM_COLOUR, label="Calm colour"),
            "palette": EffectParam(
                type="color_list", default=list(FOCUS_PALETTE), label="Busy colours"
            ),
            "calm_m": EffectParam(
                type="float",
                default=2.0,
                min=0.5,
                max=8.0,
                step=0.1,
                label="Calm radius",
                description="Metres of calm; the busy colours take over by twice this",
                bindable=True,
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
        calm: str = CALM_COLOUR,
        palette: list[str] | None = None,
        calm_m: float = 2.0,
        level: float = 0.9,
    ) -> None:
        self._seed = 0
        self._apply_params(
            anchor=anchor,
            calm=calm,
            palette=list(palette or FOCUS_PALETTE),
            calm_m=calm_m,
            level=level,
        )

    def reseed(self, seed: int) -> None:
        self._seed = seed

    def _prepare(self) -> None:
        self._calm = palette_float([self._values["calm"]])[0]
        self._palette = palette_float(self._values["palette"])

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        calm_m = float(values["calm_m"])
        away = distances(leds, anchor_or_centre(leds, values["anchor"]))
        busy = smoothstep(calm_m, 2.0 * calm_m, away)[:, None]
        moving = leds.pos.astype(np.float64) * 0.8 + np.array([ctx.t * 0.3, 0.0, ctx.t * 0.2])
        swirl = fbm3(moving, self._seed, octaves=2)
        lively = palette_at(self._palette, (swirl * 1.5 + ctx.t * 0.05) % 1.0)
        pulse = 0.55 + 0.45 * np.sin(2.0 * math.pi * (ctx.t * 0.8 + swirl * 3.0))
        out = self._calm * (1.0 - busy) + lively * pulse[:, None] * busy
        frame: FloatRGB = (out * np.float32(values["level"])).astype(np.float32)
        return frame
