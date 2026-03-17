"""Effect parameter descriptor for runtime introspection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class EffectParam:
    """Describes a tunable effect parameter with type, range, and metadata."""

    type: Literal["float", "int", "color", "color_list", "bool", "choice"]
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None
    label: str | None = None
    description: str | None = None
