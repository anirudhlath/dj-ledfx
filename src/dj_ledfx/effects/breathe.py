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

_DEFAULT_PALETTE = ["#ffbf47", "#ff8c00", "#ffd700", "#ffaa33"]


class Breathe(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"
            ),
            "beats_per_cycle": EffectParam(
                type="float", default=4.0, min=1.0, max=4.0, step=0.5, label="Beats per Cycle"
            ),
            "min_brightness": EffectParam(
                type="float", default=0.05, min=0.0, max=0.5, step=0.01, label="Min Brightness"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        beats_per_cycle: float = 4.0,
        min_brightness: float = 0.05,
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._beats_per_cycle = beats_per_cycle
        self._min_brightness = min_brightness

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [rgb_to_hex(r, g, b) for r, g, b in self._palette],
            "beats_per_cycle": self._beats_per_cycle,
            "min_brightness": self._min_brightness,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "beats_per_cycle" in kwargs:
            self._beats_per_cycle = float(kwargs["beats_per_cycle"])
        if "min_brightness" in kwargs:
            self._min_brightness = float(kwargs["min_brightness"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        effective_beats = lerp(self._beats_per_cycle, 1.0, energy)
        cycles_per_bar = 4.0 / effective_beats
        cycle_phase = (ctx.bar_phase * cycles_per_bar) % 1.0

        brightness = self._min_brightness + (1.0 - self._min_brightness) * (
            0.5 + 0.5 * math.sin(cycle_phase * 2.0 * math.pi)
        )

        color_index = int(ctx.bar_phase * cycles_per_bar) % len(self._palette)
        r, g, b = self._palette[color_index]

        out = np.empty((led_count, 3), dtype=np.uint8)
        out[:, 0] = int(r * brightness)
        out[:, 1] = int(g * brightness)
        out[:, 2] = int(b * brightness)
        return out
