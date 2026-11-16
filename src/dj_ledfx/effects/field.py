"""Field effects render every LED of a zone at its position (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect, ParamSettings

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

F32 = NDArray[np.float32]


class FieldEffect(Effect):
    @abstractmethod
    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Return shape (leds.count, 3) float32, 0..1 per channel, vectorised numpy."""

    def lights_out(self, leds: LedSet) -> F32 | None:
        """Each LED's elapsed time (RenderContext.elapsed_s) from which the effect has it
        black for good, shape (leds.count,); inf: never. None, the default: the effect never
        has a light out. Asked of the LEDs the effect renders (the layer's view), so an
        effect that keeps per-LED work with `_per_leds` uses the render's own builder."""
        return None


class ParamField(ParamSettings, FieldEffect):
    """A field effect that keeps its settings in one dict (ParamSettings): render reads
    self._values."""
