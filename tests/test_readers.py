"""The shared readers raise the error of the model they read for."""

from __future__ import annotations

from typing import Any

import pytest

from dj_ledfx.home.model import HomeError
from dj_ledfx.looks.model import LookError
from dj_ledfx.readers import Reader


@pytest.mark.parametrize("error", [HomeError, LookError])
@pytest.mark.parametrize(
    ("read", "value", "says"),
    [
        (lambda r, v: r.finite(v, "The height"), 10**400, "The height must be a finite number"),
        (lambda r, v: r.finite(v, "The height"), float("nan"), "must be a finite number"),
        (lambda r, v: r.number(v, "The scale"), True, "The scale must be a number"),
        (lambda r, v: r.positive(v, "The ceiling"), 0.0, "must be greater than 0"),
        (lambda r, v: r.non_negative(v, "The radius"), -1, "must be 0 or more"),
        (lambda r, v: r.text(v, "A room's id"), " ", "must be a non-empty string"),
        (lambda r, v: r.vec3(v, "The position"), [1, 2], "must be 3 numbers"),
        (lambda r, v: r.mapping(v, "The size"), [8, 4], "The size must be an object"),
    ],
)
def test_a_reader_refuses_with_its_models_error(
    error: type[Exception], read: Any, value: Any, says: str
) -> None:
    with pytest.raises(error, match=says):
        read(Reader(error), value)


def test_any_number_reads_as_itself_however_big() -> None:
    read = Reader(LookError)

    assert read.number(10**400, "The offset") == 10**400
    assert read.items([1, "x"], 2, "The range") == (1, "x")  # each read on its own
    assert read.vec2([1, 2.5], "A point") == (1.0, 2.5)
