"""Effect base classes with parameter introspection and auto-registry."""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.params import EffectParam, check_setting
from dj_ledfx.types import BeatContext

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.fx import Fx
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

T = TypeVar("T")


def _to_snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class Effect(ABC):  # noqa: B024
    """Registry and parameters shared by every effect kind (strip, field, particle, firmware).

    The kinds below declare the abstract methods, so this class has none of its own.
    Concrete subclasses register under their snake_case class name unless the name
    starts with "_" or the class is declared with `register=False`.
    """

    _registry: ClassVar[dict[str, type[Effect]]] = {}

    def __init_subclass__(cls, register: bool = True, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        params = cls.parameters()
        sig = inspect.signature(cls.__init__)
        takes_any = any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())
        if params and not takes_any:
            init_params = {p for p in sig.parameters if p != "self"}
            missing = set(params.keys()) - init_params
            if missing:
                raise TypeError(
                    f"{cls.__name__} parameters() declares {missing} "
                    f"but __init__ does not accept them"
                )
        if register and not cls.__name__.startswith("_"):
            Effect._registry[_to_snake_case(cls.__name__)] = cls

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def set_params(self, **kwargs: Any) -> None:
        schema = self.parameters()
        for key, value in kwargs.items():
            if key not in schema:
                raise ValueError(f"Unknown parameter: {key}")
            check_setting(key, schema[key], value)
        self._apply_params(**kwargs)

    def _apply_params(self, **kwargs: Any) -> None:  # noqa: B027
        pass

    def reseed(self, seed: int) -> None:  # noqa: B027
        """Make the effect's randomness repeatable. Default: it has none."""

    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
        """What the effect's last frame on these LEDs, at ctx's moment, draws in space, for
        the web app's stage (effects/fx.py); None: nothing to draw, the default. Called
        right after the frame, with the same moment and LEDs."""
        return None


class ParamSettings(Effect, register=False):
    """An effect that keeps its settings in one dict: the field effects (ParamField) and
    the particle effects (ParamParticles).

    parameters() states each setting and its default once: __init__ takes settings by
    name and fills in the defaults (None, or an empty list for a list setting, is the
    default). The effect reads self._values. _prepare() rebuilds what's derived from the
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

    def _rng(self, k: int) -> np.random.Generator:
        """The random numbers of draw k (a drop, a beat): the same seed and k always give
        the same ones, however the frames fall."""
        return np.random.default_rng([self._seed % 2**32, k % 2**63])

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


class StripEffect(Effect):
    """Today's 1D effects: a strip of `led_count` LEDs in 8-bit RGB."""

    @abstractmethod
    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        """Return shape (led_count, 3) uint8 RGB array."""
