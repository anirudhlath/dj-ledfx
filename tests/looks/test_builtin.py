from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path

import numpy as np
import pytest

from dj_ledfx.effects.context import NO_SIGNALS, RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.ledset import LedSet, LedSource, build_ledset
from dj_ledfx.effects.registry import get_strip_effect_classes
from dj_ledfx.looks.builtin import (
    CLASSIC_NAMES,
    FIRMWARE_LOOK_ID,
    builtin_looks,
    classic_look_id,
    handoff_looks,
)
from dj_ledfx.looks.model import (
    Look,
    firmware_layers,
    make_effect,
    validate_look,
    visible_field_layer,
)
from dj_ledfx.spatial.geometry import MatrixGeometry, StripGeometry, TileLayout
from dj_ledfx.types import FloatRGB

DESIGN = Path(__file__).parents[2] / "docs" / "design" / "web-app"
VENDORED = files("dj_ledfx.looks") / "data" / "looks.json"


def test_vendored_looks_json_is_a_byte_copy_of_the_handoff() -> None:
    vendored = VENDORED.read_bytes()
    assert vendored == (DESIGN / "looks.json").read_bytes()
    pinned = {
        name: digest
        for digest, name in (
            line.split() for line in (DESIGN / "HANDOFF.sha256").read_text().splitlines() if line
        )
    }
    assert hashlib.sha256(vendored).hexdigest() == pinned["looks.json"]


def test_showcase_keeps_the_handoff_metadata() -> None:
    entry = handoff_looks()[FIRMWARE_LOOK_ID]
    showcase = builtin_looks()[0]
    assert showcase.id == entry["id"]
    assert showcase.name == entry["name"]
    assert showcase.category == entry["category"]
    assert showcase.description == entry["description"]
    assert showcase.thumbnail == entry["thumbnail"]
    assert showcase.scope == entry["scope"]
    assert list(showcase.needs) == entry["inputs"]
    assert showcase.built_in


def test_showcase_layers_bottom_to_top() -> None:
    showcase = builtin_looks()[0]
    assert [layer.kind for layer in showcase.layers] == [
        "openrgb_mode",
        "lifx_waveform",
        "lifx_move",
        "lifx_flame",
    ]
    assert all(layer.type == "firmware" for layer in showcase.layers)
    assert visible_field_layer(showcase) is None


def test_classics_cover_the_six_strip_effects() -> None:
    classics = builtin_looks()[1:]
    assert set(CLASSIC_NAMES) == set(get_strip_effect_classes())
    assert [look.id for look in classics] == [classic_look_id(kind) for kind in CLASSIC_NAMES]
    assert classic_look_id("beat_pulse") == "classic-beat-pulse"
    for look in classics:
        layer = visible_field_layer(look)
        assert layer is not None
        assert look.name == CLASSIC_NAMES[layer.kind]
        assert look.category == "tempo"
        assert look.uses == ("tempo",)
        assert look.needs == ()
        assert look.thumbnail == look.id
        assert look.built_in


def test_ids_are_unique_and_every_builtin_validates() -> None:
    looks = builtin_looks()
    assert len({look.id for look in looks}) == len(looks) == 7
    for look in looks:
        validate_look(look)


def _ledset() -> LedSet:
    return build_ledset(
        [
            LedSource("candle", 30, MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 5, 6),))),
            LedSource("bulb", 1),
            LedSource("neon", 12, StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)),
            LedSource("lamp", 20),
        ]
    )


def _frames(look: Look, seed: int) -> list[FloatRGB]:
    """Render the look's streamed layer, or every firmware layer's copy, for 3 s."""
    leds = _ledset()
    field_layer = visible_field_layer(look)
    layers = [field_layer] if field_layer is not None else firmware_layers(look)
    effects = [make_effect(layer) for layer in layers]
    for effect in effects:
        effect.reseed(seed)
    frames: list[FloatRGB] = []
    for step in range(180):
        t = 1000.0 + step / 60
        ctx = RenderContext(
            t=t,
            dt=1 / 60,
            beat_phase=(t * 2.0) % 1.0,
            bar_phase=(t / 2.0) % 1.0,
            bpm=120.0,
            beat_index=0,
            bar_index=0,
            signals=NO_SIGNALS,
        )
        for effect in effects:
            if isinstance(effect, FirmwareEffect):
                frames.append(effect.emulate(ctx, leds))
            else:
                frames.append(effect.render(ctx, leds))
    return frames


@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_every_builtin_is_finite_in_range_and_repeats_with_a_fixed_seed(look: Look) -> None:
    count = _ledset().count
    first = _frames(look, seed=7)
    again = _frames(look, seed=7)
    for frame, repeat in zip(first, again, strict=True):
        assert frame.shape == (count, 3)
        assert frame.dtype == np.float32
        assert np.isfinite(frame).all()
        assert frame.min() >= 0.0 and frame.max() <= 1.0
        assert np.array_equal(frame, repeat)
