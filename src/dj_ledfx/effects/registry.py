"""Effect class registry and schema discovery."""

from __future__ import annotations

from typing import Any

from dj_ledfx.effects.base import Effect, StripEffect
from dj_ledfx.effects.params import EffectParam


def get_effect_classes() -> dict[str, type[Effect]]:
    return dict(Effect._registry)


def get_effect_class(name: str) -> type[Effect]:
    """The registered class for an effect kind. Raises KeyError if unknown."""
    return Effect._registry[name]


def get_strip_effect_classes() -> dict[str, type[StripEffect]]:
    return {name: cls for name, cls in Effect._registry.items() if issubclass(cls, StripEffect)}


def get_effect_schemas() -> dict[str, dict[str, EffectParam]]:
    """Parameter schemas of the 1D strip effects, for the old UI's effect deck."""
    return {name: cls.parameters() for name, cls in get_strip_effect_classes().items()}


def create_effect(name: str, **params: Any) -> Effect:
    return Effect._registry[name](**params)


def create_strip_effect(name: str, **params: Any) -> StripEffect:
    cls = Effect._registry[name]
    if not issubclass(cls, StripEffect):
        raise KeyError(f"{name} is not a strip effect")
    return cls(**params)
