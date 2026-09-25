"""Effect parameter descriptor for runtime introspection (spec §5.1)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

ParamType = Literal[
    "float",
    "int",
    "color",
    "color_list",
    "bool",
    "choice",
    "anchor",  # a named home-map point
    "point",  # any xyz position
    "zone",
    "device_set",  # light ids or a selector such as type:candle
    "range",  # a low-high pair, e.g. a height band
]


@dataclass(frozen=True)
class EffectParam:
    """Describes a tunable effect parameter with type, range, and metadata."""

    type: ParamType
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None
    label: str | None = None
    description: str | None = None
    bindable: bool = False  # can be bound to a signal (spec §7.5); bindings arrive in M7


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value)


def _numbers(value: Any, count: int) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, str)
        and len(value) == count
        and all(_is_number(item) for item in value)
    )


def _within(key: str, param: EffectParam, value: Any, number: float) -> None:
    if param.min is not None and number < param.min:
        raise ValueError(f"{key}={value} below min {param.min}")
    if param.max is not None and number > param.max:
        raise ValueError(f"{key}={value} above max {param.max}")


def check_setting(key: str, param: EffectParam, value: Any) -> None:
    """Raise ValueError, naming the setting, when the value doesn't fit its type."""
    if param.type in ("float", "int"):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{key} must be a number")
        _within(key, param, value, value)
    elif param.type == "choice":
        if value not in (param.choices or []):
            raise ValueError(f"{key}={value} not in {param.choices}")
    elif param.type == "anchor":
        if not isinstance(value, str):
            raise ValueError(f"{key} must be an anchor id")
    elif param.type == "zone":
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a zone id")
    elif param.type == "point":
        if not _numbers(value, 3):
            raise ValueError(f"{key} must be 3 numbers: x, y and z")
    elif param.type == "range":
        if not _numbers(value, 2) or value[0] > value[1]:
            raise ValueError(f"{key} must be two numbers, low first")
        _within(key, param, value, value[0])
        _within(key, param, value, value[1])
    elif param.type == "device_set":
        items = [value] if isinstance(value, str) else value
        if not isinstance(items, Sequence) or not all(isinstance(item, str) for item in items):
            raise ValueError(f"{key} must be light ids or a selector such as type:candle")
