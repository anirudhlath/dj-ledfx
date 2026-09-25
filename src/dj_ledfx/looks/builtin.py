"""Built-in looks (spec §5.2).

The handoff's looks take their metadata from its looks.json (vendored in data/looks.json,
byte for byte), in its order: M2's six showcase looks and the Firmware showcase. The
handoff has no layers, so they live here. The six classic looks are today's effects; the
handoff has no entry for them, so their names and descriptions live here too.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any

from dj_ledfx.effects.aurora_curtains import AURORA_PALETTE
from dj_ledfx.home.model import Anchor
from dj_ledfx.home.seed import normalise_name, seed_home
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.looks.selectors import parse_selector

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


def anchor_named_in(text: str, anchors: Sequence[Anchor]) -> str:
    """The id of the one anchor whose name the text mentions as whole words, or "" when
    it names none or more than one."""
    words = f" {normalise_name(text)} "
    named = [anchor.id for anchor in anchors if f" {normalise_name(anchor.name)} " in words]
    return named[0] if len(named) == 1 else ""


def _field(layer_id: str, name: str, kind: str, **settings: Any) -> Layer:
    return Layer(id=layer_id, name=name, type="field", kind=kind, settings=settings)


def _firmware(
    layer_id: str, name: str, kind: str, *, lights: Sequence[str] = (), **settings: Any
) -> Layer:
    return Layer(
        id=layer_id,
        name=name,
        type="firmware",
        kind=kind,
        settings=settings,
        lights=tuple(parse_selector(text) for text in lights) or None,
    )


def _handoff_layers() -> Mapping[str, tuple[Layer, ...]]:
    """The layers of each handoff look this milestone can run, by look id."""
    focus = handoff_looks()["focus"]["description"]
    return {
        "sunset": (
            _field("sky", "Gradient", "sunset_gradient"),
            _firmware("flame", "Candles", "lifx_flame", lights=["type:candle"]),
        ),
        "aurora": (
            _field("curtains", "Curtains", "aurora_curtains"),
            _firmware(
                "morph",
                "Morph",
                "lifx_morph",
                lights=["type:candle", "type:tube"],
                palette=list(AURORA_PALETTE),
            ),
        ),
        "lava": (_field("plasma", "Plasma", "lava_plasma"),),
        "carousel": (_field("carousel", "Carousel", "color_carousel"),),
        "ripples": (_field("ripples", "Ripples", "ripples"),),
        "focus": (
            _field(
                "focus", "Focus", "focus_field", anchor=anchor_named_in(focus, seed_home().anchors)
            ),
        ),
        FIRMWARE_LOOK_ID: tuple(
            _firmware(layer_id, name, kind) for layer_id, name, kind in SHOWCASE_LAYERS
        ),
    }


def _from_handoff(entry: Mapping[str, Any], layers: tuple[Layer, ...]) -> Look:
    return Look(
        id=entry["id"],
        name=entry["name"],
        category=entry["category"],
        description=entry["description"],
        thumbnail=entry["thumbnail"],
        scope=entry["scope"],
        needs=tuple(entry["inputs"]),
        layers=layers,
        built_in=True,
    )


def _classic(kind: str, name: str) -> Look:
    look_id = classic_look_id(kind)
    return Look(
        id=look_id,
        name=name,
        category="tempo",
        description=f"The classic {name.lower()} effect, swept across the zone from west to east.",
        thumbnail=look_id,
        uses=("tempo",),
        layers=(Layer(id="strip", name=name, type="field", kind=kind),),
        built_in=True,
    )


@functools.cache
def builtin_looks() -> tuple[Look, ...]:
    """The handoff's looks that have layers here, in looks.json's order, then the classics."""
    layers = _handoff_layers()
    handoff = tuple(
        _from_handoff(entry, layers[look_id])
        for look_id, entry in handoff_looks().items()
        if look_id in layers
    )
    return (*handoff, *(_classic(kind, name) for kind, name in CLASSIC_NAMES.items()))
