from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path

import numpy as np
import pytest
from map_home import seeded_ledset, tiny_home

from dj_ledfx.effects.aurora_curtains import AURORA_PALETTE
from dj_ledfx.effects.context import NO_SIGNALS, RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.registry import get_strip_effect_classes
from dj_ledfx.home.seed import seed_home
from dj_ledfx.looks.builtin import (
    CLASSIC_NAMES,
    FIRMWARE_LOOK_ID,
    anchor_named_in,
    builtin_looks,
    classic_look_id,
    handoff_looks,
)
from dj_ledfx.looks.model import (
    LIGHTS_SETTING,
    Look,
    firmware_layers,
    make_effect,
    validate_look,
    visible_field_layers,
)
from dj_ledfx.types import FloatRGB

DESIGN = Path(__file__).parents[2] / "docs" / "design" / "web-app"
VENDORED = files("dj_ledfx.looks") / "data" / "looks.json"
SHOWCASE = ["sunset", "aurora", "lava", "carousel", "ripples", "focus", FIRMWARE_LOOK_ID]


def _look(look_id: str) -> Look:
    return next(look for look in builtin_looks() if look.id == look_id)


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


def test_the_handoff_looks_come_first_in_its_order_with_its_metadata() -> None:
    handoff = handoff_looks()
    looks = builtin_looks()[: len(SHOWCASE)]

    assert [look.id for look in looks] == SHOWCASE
    assert SHOWCASE == [look_id for look_id in handoff if look_id in SHOWCASE]  # looks.json order
    for look in looks:
        entry = handoff[look.id]
        assert (look.name, look.category, look.description) == (
            entry["name"],
            entry["category"],
            entry["description"],
        )
        assert (look.thumbnail, look.scope, list(look.needs)) == (
            entry["thumbnail"],
            entry["scope"],
            entry["inputs"],
        )
        assert look.built_in


def test_each_showcase_look_has_its_fields_and_firmware() -> None:
    layers = {
        look.id: [(layer.type, layer.kind) for layer in look.layers] for look in builtin_looks()
    }

    assert layers["sunset"] == [("field", "sunset_gradient"), ("firmware", "lifx_flame")]
    assert layers["aurora"] == [("field", "aurora_curtains"), ("firmware", "lifx_morph")]
    assert layers["lava"] == [("field", "lava_plasma")]
    assert layers["carousel"] == [("field", "color_carousel")]
    assert layers["ripples"] == [("field", "ripples")]
    assert layers["focus"] == [("field", "focus_field")]
    assert _look("sunset").layers[1].settings == {LIGHTS_SETTING: "type:candle"}
    assert _look("aurora").layers[1].settings == {
        LIGHTS_SETTING: ["type:candle", "type:tube"],
        "palette": list(AURORA_PALETTE),  # the curtains' palette
    }


def test_focus_is_calm_around_the_anchor_its_description_names() -> None:
    focus = _look("focus")

    anchor = seed_home().anchor(focus.layers[0].settings["anchor"])

    assert anchor is not None
    assert anchor.name.lower() in focus.description.lower()


def test_an_anchor_is_found_by_the_name_a_text_mentions() -> None:
    anchors = tiny_home().anchors  # "Sofa" and "Speakers"

    assert anchor_named_in("Calm near the sofa, busy further off.", anchors) == "sofa"
    assert anchor_named_in("Between the sofa and the speakers", anchors) == ""  # which one?
    assert anchor_named_in("Two sofas", anchors) == ""  # whole words only
    assert anchor_named_in("", anchors) == ""


def test_the_firmware_showcase_layers_bottom_to_top() -> None:
    showcase = _look(FIRMWARE_LOOK_ID)
    assert [layer.kind for layer in showcase.layers] == [
        "openrgb_mode",
        "lifx_waveform",
        "lifx_move",
        "lifx_flame",
    ]
    assert all(layer.type == "firmware" for layer in showcase.layers)
    assert visible_field_layers(showcase) == []


def test_classics_cover_the_six_strip_effects() -> None:
    classics = builtin_looks()[len(SHOWCASE) :]
    assert set(CLASSIC_NAMES) == set(get_strip_effect_classes())
    assert [look.id for look in classics] == [classic_look_id(kind) for kind in CLASSIC_NAMES]
    assert classic_look_id("beat_pulse") == "classic-beat-pulse"
    for look in classics:
        [layer] = visible_field_layers(look)
        assert look.name == CLASSIC_NAMES[layer.kind]
        assert look.category == "tempo"
        assert look.uses == ("tempo",)
        assert look.needs == ()
        assert look.thumbnail == look.id
        assert look.built_in


def test_ids_are_unique_and_every_builtin_validates() -> None:
    looks = builtin_looks()
    assert len({look.id for look in looks}) == len(looks) == len(SHOWCASE) + len(CLASSIC_NAMES)
    for look in looks:
        validate_look(look)


def _frames(look: Look, seed: int) -> list[FloatRGB]:
    """Render every streamed layer, and every firmware layer's copy, for 3 s on this home."""
    leds = seeded_ledset()
    effects = [
        make_effect(layer) for layer in [*visible_field_layers(look), *firmware_layers(look)]
    ]
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


# Spec §9's looks sweep (ruling 15).
@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_every_builtin_is_finite_in_range_and_repeats_with_a_fixed_seed(look: Look) -> None:
    count = seeded_ledset().count
    first = _frames(look, seed=7)
    again = _frames(look, seed=7)
    for frame, repeat in zip(first, again, strict=True):
        assert frame.shape == (count, 3)
        assert frame.dtype == np.float32
        assert np.isfinite(frame).all()
        assert frame.min() >= 0.0 and frame.max() <= 1.0
        assert np.array_equal(frame, repeat)
