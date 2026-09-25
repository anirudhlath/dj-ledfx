"""Lava's field (looks.json "lava"): a slow 3D plasma in lava colours.

Time moves through the noise along a slant of irrational steps, so the field never lines
up with an earlier one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.field_tools import palette_at, palette_float, smoothstep
from dj_ledfx.effects.noise import fbm3
from dj_ledfx.effects.params import EffectParam

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
            "level": EffectParam(
                type="float",
                default=1.0,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Level",
                bindable=True,
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        speed: float = 0.3,
        scale_m: float = 1.2,
        level: float = 1.0,
    ) -> None:
        self._seed = 0
        self._apply_params(
            palette=list(palette or LAVA_PALETTE), speed=speed, scale_m=scale_m, level=level
        )

    def reseed(self, seed: int) -> None:
        self._seed = seed

    def _prepare(self) -> None:
        self._palette = palette_float(self._values["palette"])

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        points = leds.pos.astype(np.float64) / float(values["scale_m"])
        flow = ctx.t * float(values["speed"]) * _FLOW
        heat = smoothstep(0.3, 0.72, fbm3(points + _SLANT * flow, self._seed, octaves=3))
        return (palette_at(self._palette, heat) * np.float32(values["level"])).astype(np.float32)
