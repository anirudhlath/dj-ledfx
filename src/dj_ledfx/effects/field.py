"""Field effects render every LED of a zone at its position (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import palette_float

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

T = TypeVar("T")


class FieldEffect(Effect):
    @abstractmethod
    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Return shape (leds.count, 3) float32, 0..1 per channel, vectorised numpy."""


class ParamField(FieldEffect):
    """A field effect that keeps its settings in one dict.

    parameters() states each setting and its default once: __init__ takes settings by
    name and fills in the defaults (None, or an empty list for a list setting, is the
    default). render reads self._values. _prepare() rebuilds what's derived from the
    settings (here, a "palette" setting's float palette in self._palette), and
    _per_leds() keeps what depends only on the LEDs and the settings until either
    changes. Randomness goes through reseed(), which sets self._seed.
    """

    _values: dict[str, Any]
    _palette: FloatRGB
    _seed: int = 0

    def __init__(self, **settings: Any) -> None:
        schema = self.parameters()
        unknown = sorted(set(settings) - set(schema))
        if unknown:
            raise TypeError(f"{type(self).__name__} has no setting {', '.join(unknown)}")
        values: dict[str, Any] = {}
        for name, param in schema.items():
            value = settings.get(name)
            if isinstance(param.default, list):
                values[name] = list(value or param.default)
            else:
                values[name] = param.default if value is None else value
        self._apply_params(**values)

    def get_params(self) -> dict[str, Any]:
        return dict(self._values)

    def reseed(self, seed: int) -> None:
        self._seed = seed

    def _apply_params(self, **kwargs: Any) -> None:
        self._values = {**getattr(self, "_values", {}), **kwargs}
        self._kept_for: LedSet | None = None
        self._prepare()

    def _prepare(self) -> None:
        """Rebuild anything derived from the settings. A subclass that adds to this calls
        super()._prepare()."""
        if "palette" in self._values:
            self._palette = palette_float(self._values["palette"])

    def _per_leds(self, leds: LedSet, build: Callable[[LedSet], T]) -> T:
        """What build makes of these LEDs with the current settings, kept until the LED
        set or a setting changes."""
        if self._kept_for is not leds:
            self._kept: Any = build(leds)
            self._kept_for = leds
        return cast(T, self._kept)
