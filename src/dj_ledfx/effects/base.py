"""Effect base classes with parameter introspection and auto-registry."""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext


def _to_snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class Effect(ABC):  # noqa: B024
    """Registry and parameters shared by every effect kind (strip, field, firmware).

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
        if params:
            sig = inspect.signature(cls.__init__)
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
            param = schema[key]
            if param.type in ("float", "int"):
                if param.min is not None and value < param.min:
                    raise ValueError(f"{key}={value} below min {param.min}")
                if param.max is not None and value > param.max:
                    raise ValueError(f"{key}={value} above max {param.max}")
            if param.type == "choice" and value not in (param.choices or []):
                raise ValueError(f"{key}={value} not in {param.choices}")
        self._apply_params(**kwargs)

    def _apply_params(self, **kwargs: Any) -> None:  # noqa: B027
        pass

    def reseed(self, seed: int) -> None:  # noqa: B027
        """Make the effect's randomness repeatable. Default: it has none."""


class StripEffect(Effect):
    """Today's 1D effects: a strip of `led_count` LEDs in 8-bit RGB."""

    @abstractmethod
    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        """Return shape (led_count, 3) uint8 RGB array."""
