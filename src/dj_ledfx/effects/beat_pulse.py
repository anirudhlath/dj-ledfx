from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb, rgb_to_hex
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]


class BeatPulse(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "gamma": EffectParam(
                type="float", default=2.0, min=0.5, max=5.0, step=0.1, label="Gamma"
            ),
            "palette": EffectParam(
                type="color_list",
                default=["#ff0000", "#00ff00", "#0000ff", "#ffff00"],
                label="Palette",
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        gamma: float = 2.0,
    ) -> None:
        colors = palette or _DEFAULT_PALETTE
        self._palette = [hex_to_rgb(c) for c in colors]
        self._gamma = gamma

    def get_params(self) -> dict[str, Any]:
        return {
            "gamma": self._gamma,
            "palette": [rgb_to_hex(r, g, b) for r, g, b in self._palette],
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "gamma" in kwargs:
            self._gamma = float(kwargs["gamma"])
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]

    def render(
        self,
        ctx: BeatContext,
        led_count: int,
    ) -> NDArray[np.uint8]:
        brightness = (1.0 - ctx.beat_phase) ** self._gamma

        color_index = int(ctx.bar_phase * len(self._palette)) % len(self._palette)
        r, g, b = self._palette[color_index]

        out = np.empty((led_count, 3), dtype=np.uint8)
        out[:, 0] = int(r * brightness)
        out[:, 1] = int(g * brightness)
        out[:, 2] = int(b * brightness)
        return out
