"""EffectDeck — thin wrapper for active effect with hot-swap."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect, _to_snake_case
from dj_ledfx.types import BeatContext


class EffectDeck:
    def __init__(
        self,
        effect: Effect,
        on_change: Callable[[EffectDeck], None] | None = None,
    ) -> None:
        self._effect = effect
        self._on_change = on_change

    @property
    def effect_name(self) -> str:
        return _to_snake_case(type(self._effect).__name__)

    @property
    def effect(self) -> Effect:
        return self._effect

    def swap_effect(self, new_effect: Effect) -> None:
        self._effect = new_effect

    def apply_update(self, effect_name: str | None, params: dict[str, Any]) -> None:
        """Swap effect or update params. Shared by REST and WS handlers."""
        from dj_ledfx.effects.registry import create_effect

        if effect_name and effect_name != self.effect_name:
            new_effect = create_effect(effect_name, **params)
            self.swap_effect(new_effect)
        elif params:
            self._effect.set_params(**params)

        if self._on_change is not None:
            self._on_change(self)

    def render(
        self,
        ctx: BeatContext,
        led_count: int,
    ) -> NDArray[np.uint8]:
        return self._effect.render(ctx, led_count)
