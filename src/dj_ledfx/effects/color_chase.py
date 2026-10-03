from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import StripEffect
from dj_ledfx.effects.color import hex_to_rgb, palette_loop, rgb_to_hex
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]


class ColorChase(StripEffect):
    """Bands of the palette chased along the strip: each light glides one colour along every
    `beats_per_step` beats, from the last colour back to the first, so the tempo sets the
    pace and nothing else."""

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"
            ),
            "band_count": EffectParam(
                type="float", default=2.0, min=1.0, max=8.0, step=0.5, label="Band count"
            ),
            # At least half a beat, so a light swings from dark to bright and back at most
            # once a beat, as Beat pulse flashes
            "beats_per_step": EffectParam(
                type="float", default=1.0, min=0.5, max=8.0, step=0.25, label="Beats per step"
            ),
            "direction": EffectParam(
                type="choice", default="forward", choices=["forward", "reverse"], label="Direction"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        band_count: float = 2.0,
        beats_per_step: float = 1.0,
        direction: str = "forward",
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._band_count = band_count
        self._beats_per_step = beats_per_step
        self._direction = direction
        self._places: NDArray[np.float64] | None = None  # _places_for()'s, for an LED count

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [rgb_to_hex(r, g, b) for r, g, b in self._palette],
            "band_count": self._band_count,
            "beats_per_step": self._beats_per_step,
            "direction": self._direction,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "band_count" in kwargs:
            self._band_count = float(kwargs["band_count"])
        if "beats_per_step" in kwargs:
            self._beats_per_step = float(kwargs["beats_per_step"])
        if "direction" in kwargs:
            self._direction = str(kwargs["direction"])
        self._places = None

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        # A light runs through the palette in time (a step a colour) while the colours lie
        # the other way along the strip, so they travel forward.
        palettes = ctx.beats / (self._beats_per_step * len(self._palette))
        return palette_loop(self._palette, palettes - self._places_for(led_count))

    def _places_for(self, led_count: int) -> NDArray[np.float64]:
        """Each LED's place along the strip in bands, 0 to band_count (from the far end in
        reverse), kept until the LED count or a setting changes."""
        places = self._places
        if places is None or len(places) != led_count:
            places = np.linspace(0.0, self._band_count, led_count)
            self._places = places = places[::-1] if self._direction == "reverse" else places
        return places
