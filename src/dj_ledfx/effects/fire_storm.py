from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb, palette_lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ff1500", "#ff6600", "#ff9900", "#ffcc00"]


class FireStorm(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"
            ),
            "intensity": EffectParam(
                type="float", default=0.7, min=0.3, max=1.0, step=0.05, label="Intensity"
            ),
            "smoothing": EffectParam(
                type="float", default=0.3, min=0.0, max=0.9, step=0.05, label="Smoothing"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        intensity: float = 0.7,
        smoothing: float = 0.3,
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._intensity = intensity
        self._smoothing = smoothing
        self._rng = np.random.default_rng()
        self._prev_frame: NDArray[np.float64] | None = None

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette],
            "intensity": self._intensity,
            "smoothing": self._smoothing,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "intensity" in kwargs:
            self._intensity = float(kwargs["intensity"])
        if "smoothing" in kwargs:
            self._smoothing = float(kwargs["smoothing"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        effective_intensity = self._intensity * (0.5 + 0.5 * energy)

        noise = self._rng.random(led_count)

        # Apply temporal smoothing
        if self._prev_frame is not None and len(self._prev_frame) == led_count:
            smoothed = self._prev_frame * self._smoothing + noise * (1.0 - self._smoothing)
        else:
            smoothed = noise

        self._prev_frame = smoothed.copy()

        # palette_lerp for color, brightness for flicker
        brightness = (1.0 - effective_intensity) + smoothed * effective_intensity
        colors = palette_lerp(self._palette, smoothed)
        result = (colors.astype(np.float64) * brightness[:, np.newaxis]).astype(np.uint8)
        return result
