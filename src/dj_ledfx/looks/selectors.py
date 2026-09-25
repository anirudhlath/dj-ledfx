"""Which lights a layer picks (spec §5.1's device_set): light ids, or type:<word>, which
picks every light with that whole word in its name or model (type:candle)."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from dj_ledfx.home.seed import normalise_name


@dataclass(frozen=True, slots=True)
class Selector:
    kind: Literal["id", "type"]
    value: str

    @property
    def text(self) -> str:
        """The selector as a look writes it."""
        return f"type:{self.value}" if self.kind == "type" else self.value


def parse_selector(text: str) -> Selector:
    stripped = text.strip()
    if not stripped:
        raise ValueError("A light selector can't be empty")
    if stripped.lower().startswith("type:"):
        word = stripped[len("type:") :].strip().lower()
        if not word or normalise_name(word) != word or " " in word:
            raise ValueError(
                f"Selector {stripped!r}: type: takes one word of letters and digits, "
                "such as type:candle"
            )
        return Selector("type", word)
    return Selector("id", stripped)


def selects(selectors: Sequence[Selector], ids: Collection[str], text: str) -> bool:
    """Whether any selector picks a light with these ids (its device id and light id) and
    this name and model text."""
    words: set[str] | None = None
    for selector in selectors:
        if selector.kind == "id":
            if selector.value in ids:
                return True
            continue
        if words is None:
            words = set(normalise_name(text).split())
        if selector.value in words:
            return True
    return False
