"""Field effects render every LED of a zone at its position (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from dj_ledfx.effects.base import Effect

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class FieldEffect(Effect):
    @abstractmethod
    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Return shape (leds.count, 3) float32, 0..1 per channel, vectorised numpy."""


class ParamField(FieldEffect):
    """A field effect that keeps its settings in one dict. A subclass's __init__ names
    every setting (the registry checks that) and hands them to _apply_params; render
    reads self._values, and _prepare() rebuilds what's derived from them."""

    _values: dict[str, Any]

    def get_params(self) -> dict[str, Any]:
        return dict(self._values)

    def _apply_params(self, **kwargs: Any) -> None:
        self._values = {**getattr(self, "_values", {}), **kwargs}
        self._prepare()

    def _prepare(self) -> None:  # noqa: B027
        """Rebuild anything derived from the settings, such as a float palette."""
