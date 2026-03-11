from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect

_DEFAULT_PALETTE = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class BeatPulse(Effect):
    def __init__(
        self,
        palette: list[str] | None = None,
        gamma: float = 2.0,
    ) -> None:
        colors = palette or _DEFAULT_PALETTE
        self._palette = [_hex_to_rgb(c) for c in colors]
        self._gamma = gamma

    def render(
        self,
        beat_phase: float,
        bar_phase: float,
        dt: float,
        led_count: int,
    ) -> NDArray[np.uint8]:
        brightness = (1.0 - beat_phase) ** self._gamma

        color_index = int(bar_phase * len(self._palette)) % len(self._palette)
        r, g, b = self._palette[color_index]

        out = np.empty((led_count, 3), dtype=np.uint8)
        out[:, 0] = int(r * brightness)
        out[:, 1] = int(g * brightness)
        out[:, 2] = int(b * brightness)
        return out
