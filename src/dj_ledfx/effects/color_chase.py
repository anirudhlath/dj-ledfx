from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb, palette_lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]


class ColorChase(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"),
            "band_count": EffectParam(
                type="float", default=2.0, min=1.0, max=8.0, step=0.5, label="Band Count"
            ),
            "direction": EffectParam(
                type="choice", default="forward", choices=["forward", "reverse"], label="Direction"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        band_count: float = 2.0,
        direction: str = "forward",
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._band_count = band_count
        self._direction = direction

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette],
            "band_count": self._band_count,
            "direction": self._direction,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "band_count" in kwargs:
            self._band_count = float(kwargs["band_count"])
        if "direction" in kwargs:
            self._direction = str(kwargs["direction"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        speed = 1.0 + energy * 2.0
        effective_bands = self._band_count + energy * 2.0

        positions = np.linspace(0.0, 1.0, led_count) + ctx.beat_phase * speed
        if self._direction == "reverse":
            positions = -positions

        normalized = (positions * effective_bands) % 1.0
        return palette_lerp(self._palette, normalized)
