"""Field effects render every LED of a zone at its position (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from dj_ledfx.effects.base import Effect

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class FieldEffect(Effect):
    @abstractmethod
    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Return shape (leds.count, 3) float32, 0..1 per channel, vectorised numpy."""
