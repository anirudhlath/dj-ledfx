"""Readers for the JSON the app stores and is sent: the home map's and the looks'. Each
checks one value and returns it typed, or raises its model's own error (a HomeError, a
LookError) saying what's wrong with `what`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dj_ledfx.types import is_finite_number


class Reader:
    """The readers for a model whose error is `error`."""

    def __init__(self, error: type[Exception]) -> None:
        self.error = error

    def number(self, value: Any, what: str) -> int | float:
        """Any number: NaN, an infinity and an integer too big for a float too."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise self.error(f"{what} must be a number")
        number: int | float = value
        return number

    def finite(self, value: Any, what: str) -> float:
        if not is_finite_number(value):
            raise self.error(f"{what} must be a finite number")
        return float(value)

    def positive(self, value: Any, what: str) -> float:
        number = self.finite(value, what)
        if number <= 0.0:
            raise self.error(f"{what} must be greater than 0")
        return number

    def non_negative(self, value: Any, what: str) -> float:
        number = self.finite(value, what)
        if number < 0.0:
            raise self.error(f"{what} must be 0 or more")
        return number

    def text(self, value: Any, what: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self.error(f"{what} must be a non-empty string")
        return value.strip()

    def items(self, value: Any, size: int, what: str) -> tuple[Any, ...]:
        """`size` numbers in a list, each still to be read."""
        if isinstance(value, str) or not isinstance(value, Sequence) or len(value) != size:
            raise self.error(f"{what} must be {size} numbers")
        return tuple(value)

    def numbers(self, value: Any, size: int, what: str) -> tuple[float, ...]:
        return tuple(self.finite(item, what) for item in self.items(value, size, what))

    def vec2(self, value: Any, what: str) -> tuple[float, float]:
        x, y = self.numbers(value, 2, what)
        return (x, y)

    def vec3(self, value: Any, what: str) -> tuple[float, float, float]:
        x, y, z = self.numbers(value, 3, what)
        return (x, y, z)

    def mapping(self, value: Any, what: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise self.error(f"{what} must be an object")
        return value
