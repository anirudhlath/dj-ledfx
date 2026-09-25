"""Effect parameter descriptor for runtime introspection (spec §5.1)."""

from __future__ import annotations

import math
import re
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


# A palette holds 1 to this many colours: what a LIFX matrix's own effects take (the tile
# effect packet's palette), so every palette setting fits every light.
MAX_PALETTE_COLOURS = 16
_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


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


def _is_colour(value: Any) -> bool:
    return isinstance(value, str) and _HEX_COLOUR.fullmatch(value) is not None


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
    elif param.type == "color":
        if not _is_colour(value):
            raise ValueError(f"{key} must be a hex colour such as #ff6a00")
    elif param.type == "color_list":
        if (
            isinstance(value, str)
            or not isinstance(value, Sequence)
            or not 1 <= len(value) <= MAX_PALETTE_COLOURS
            or not all(_is_colour(item) for item in value)
        ):
            raise ValueError(
                f"{key} must be 1 to {MAX_PALETTE_COLOURS} hex colours such as #ff6a00"
            )
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
