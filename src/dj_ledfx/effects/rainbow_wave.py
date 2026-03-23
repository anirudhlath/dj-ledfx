from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hsv_to_rgb_array
from dj_ledfx.effects.easing import ease_in
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext


class RainbowWave(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "saturation": EffectParam(
                type="float", default=1.0, min=0.5, max=1.0, step=0.05, label="Saturation"
            ),
            "wave_count": EffectParam(
                type="float", default=1.0, min=0.5, max=4.0, step=0.5, label="Wave Count"
            ),
            "beat_pulse": EffectParam(
                type="float", default=0.3, min=0.0, max=1.0, step=0.05, label="Beat Pulse"
            ),
        }

    def __init__(
        self,
        saturation: float = 1.0,
        wave_count: float = 1.0,
        beat_pulse: float = 0.3,
    ) -> None:
        self._saturation = saturation
        self._wave_count = wave_count
        self._beat_pulse = beat_pulse

    def get_params(self) -> dict[str, Any]:
        return {
            "saturation": self._saturation,
            "wave_count": self._wave_count,
            "beat_pulse": self._beat_pulse,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "saturation" in kwargs:
            self._saturation = float(kwargs["saturation"])
        if "wave_count" in kwargs:
            self._wave_count = float(kwargs["wave_count"])
        if "beat_pulse" in kwargs:
            self._beat_pulse = float(kwargs["beat_pulse"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        speed = 1.0 + energy
        hues = (np.linspace(0.0, self._wave_count, led_count) + ctx.bar_phase * speed) % 1.0
        value = 1.0 - self._beat_pulse * ease_in(ctx.beat_phase, 2.0)
        return hsv_to_rgb_array(hues, self._saturation, value)
