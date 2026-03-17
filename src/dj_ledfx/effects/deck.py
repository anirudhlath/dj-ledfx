"""EffectDeck — thin wrapper for active effect with hot-swap."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect, _to_snake_case


class EffectDeck:
    def __init__(self, effect: Effect) -> None:
        self._effect = effect

    @property
    def effect_name(self) -> str:
        return _to_snake_case(type(self._effect).__name__)

    @property
    def effect(self) -> Effect:
        return self._effect

    def swap_effect(self, new_effect: Effect) -> None:
        self._effect = new_effect

    def render(
        self,
        beat_phase: float,
        bar_phase: float,
        dt: float,
        led_count: int,
    ) -> NDArray[np.uint8]:
        return self._effect.render(beat_phase, bar_phase, dt, led_count)
