from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb, rgb_to_hex
from dj_ledfx.effects.easing import lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ffffff"]


class Strobe(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"
            ),
            "duty_cycle": EffectParam(
                type="float", default=0.15, min=0.05, max=0.5, step=0.01, label="Duty Cycle"
            ),
            "max_subdivision": EffectParam(
                type="int", default=4, min=1, max=4, step=1, label="Max Subdivision"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        duty_cycle: float = 0.15,
        max_subdivision: int = 4,
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._duty_cycle = duty_cycle
        self._max_subdivision = max_subdivision

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [rgb_to_hex(r, g, b) for r, g, b in self._palette],
            "duty_cycle": self._duty_cycle,
            "max_subdivision": self._max_subdivision,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "duty_cycle" in kwargs:
            self._duty_cycle = float(kwargs["duty_cycle"])
        if "max_subdivision" in kwargs:
            self._max_subdivision = int(kwargs["max_subdivision"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        raw_sub = lerp(1.0, float(self._max_subdivision), energy)
        subdivision = 2 ** round(math.log2(max(raw_sub, 1.0)))

        sub_phase = (ctx.beat_phase * subdivision) % 1.0
        on = sub_phase < self._duty_cycle

        out = np.zeros((led_count, 3), dtype=np.uint8)
        if on:
            beat_index = int(ctx.bar_phase * 4) % len(self._palette)
            r, g, b = self._palette[beat_index]
            out[:, 0] = r
            out[:, 1] = g
            out[:, 2] = b
        return out
