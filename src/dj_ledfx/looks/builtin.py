"""Built-in looks (spec §5.2).

The Firmware showcase takes its metadata from the handoff's looks.json (vendored in
data/looks.json, byte for byte). The six classic looks are today's effects; the handoff
has no entry for them, so their names and descriptions live here.
"""

from __future__ import annotations

import functools
import json
from importlib.resources import files
from typing import Any

from dj_ledfx.looks.model import Layer, Look

FIRMWARE_LOOK_ID = "firmware"

# Bottom to top. Claims go top down, so the most specific effect wins each light.
SHOWCASE_LAYERS: tuple[tuple[str, str, str], ...] = (
    ("openrgb", "OpenRGB mode", "openrgb_mode"),
    ("waveform", "LIFX waveform", "lifx_waveform"),
    ("move", "LIFX Move", "lifx_move"),
    ("flame", "LIFX Flame", "lifx_flame"),
)

CLASSIC_NAMES: dict[str, str] = {
    "beat_pulse": "Beat pulse",
    "breathe": "Breathe",
    "color_chase": "Colour chase",
    "fire_storm": "Fire storm",
    "rainbow_wave": "Rainbow wave",
    "strobe": "Strobe",
}


def classic_look_id(kind: str) -> str:
    return "classic-" + kind.replace("_", "-")


@functools.cache
def handoff_looks() -> dict[str, dict[str, Any]]:
    raw = (files("dj_ledfx.looks") / "data" / "looks.json").read_bytes()
    return {str(entry["id"]): entry for entry in json.loads(raw)["looks"]}


def _showcase() -> Look:
    entry = handoff_looks()[FIRMWARE_LOOK_ID]
    return Look(
        id=entry["id"],
        name=entry["name"],
        category=entry["category"],
        description=entry["description"],
        thumbnail=entry["thumbnail"],
        scope=entry["scope"],
        needs=tuple(entry["inputs"]),
        layers=tuple(
            Layer(id=layer_id, name=name, type="firmware", kind=kind)
            for layer_id, name, kind in SHOWCASE_LAYERS
        ),
        built_in=True,
    )


def _classic(kind: str, name: str) -> Look:
    look_id = classic_look_id(kind)
    return Look(
        id=look_id,
        name=name,
        category="tempo",
        description=f"The classic {name.lower()} effect, played along the zone's lights in order.",
        thumbnail=look_id,
        uses=("tempo",),
        layers=(Layer(id="strip", name=name, type="field", kind=kind),),
        built_in=True,
    )


@functools.cache
def builtin_looks() -> tuple[Look, ...]:
    return (_showcase(), *(_classic(kind, name) for kind, name in CLASSIC_NAMES.items()))
