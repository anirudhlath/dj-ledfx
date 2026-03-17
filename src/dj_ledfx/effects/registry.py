"""Effect class registry and schema discovery."""

from __future__ import annotations

from typing import Any

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.params import EffectParam


def get_effect_classes() -> dict[str, type[Effect]]:
    return dict(Effect._registry)


def get_effect_schemas() -> dict[str, dict[str, EffectParam]]:
    return {name: cls.parameters() for name, cls in Effect._registry.items()}


def create_effect(name: str, **params: Any) -> Effect:
    cls = Effect._registry[name]
    return cls(**params)
