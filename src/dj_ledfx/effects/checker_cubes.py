"""3D checker's cubes (looks.json "checker"): the space is cut into cubes, coloured like a
chessboard in 3D, and neighbours swap colours on every beat, like a disco floor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.params import EffectParam, level_param

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

CHECKER_PALETTE = ("#ff2d95", "#21d4fd")  # M3 ruling 17


class CheckerCubes(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list",
                default=list(CHECKER_PALETTE),
                label="Colours",
                description="Neighbouring cubes take turns through these",
            ),
            "size_m": EffectParam(
                type="float", default=1.0, min=0.25, max=4.0, step=0.25, label="Cube size"
            ),
            "punch": EffectParam(
                type="float",
                default=0.4,
                min=0.0,
                max=1.0,
                step=0.05,
                label="Punch",
                description="How far each beat's flash falls before the next",
                bindable=True,
            ),
            "level": level_param(0.9),
        }

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        values = self._values
        colourings = self._per_leds(leds, self._colourings)
        flash = 1.0 - float(values["punch"]) * ctx.beat_phase
        frame: FloatRGB = colourings[ctx.beat_index % len(colourings)] * np.float32(
            flash * float(values["level"])
        )
        return frame

    def _colourings(self, leds: LedSet) -> list[FloatRGB]:
        """The cubes' colours on each beat, one colouring per palette colour: each LED's
        cube's parity (0 or 1, alternating between neighbours on every axis) moves one step
        through the palette a beat."""
        cubes = np.floor(leds.pos / np.float32(self._values["size_m"])).astype(np.int64)
        parity: NDArray[np.int64] = cubes.sum(axis=1) % 2
        stops = len(self._palette)
        return [self._palette[(parity + shift) % stops] for shift in range(stops)]
