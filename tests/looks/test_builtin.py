from __future__ import annotations

import hashlib
from importlib.resources import files

import numpy as np
import pytest
from conftest import builtin_look, tempo_ctx
from map_home import DESIGN, handoff_pins, seeded_ledset, tiny_home

from dj_ledfx.effects.aurora_curtains import AURORA_PALETTE
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.particles import ParticleEffect, drawn
from dj_ledfx.effects.registry import get_strip_effect_classes
from dj_ledfx.home.model import Home
from dj_ledfx.home.seed import seed_home
from dj_ledfx.looks import builtin
from dj_ledfx.looks.builtin import (
    CLASSIC_NAMES,
    FIRMWARE_LOOK_ID,
    NEEDS_UNTIL_M7,
    STARTS_BY_HAND,
    anchor_named_in,
    builtin_looks,
    classic_look_id,
    handoff_looks,
    room_named_in,
)
from dj_ledfx.looks.model import (
    Look,
    firmware_layers,
    make_effect,
    streamed_layers,
    validate_look,
    visible_field_layers,
)
from dj_ledfx.looks.selectors import Selector
from dj_ledfx.types import FloatRGB

VENDORED = files("dj_ledfx.looks") / "data" / "looks.json"
M2 = ("sunset", "aurora", "lava", "carousel", "ripples", "focus")
M3 = ("shockwave", "scanner", "checker", "speakers")
M5_AMBIENT = ("fireflies", "embers", "rain", "snow", "spotlights")
M5_TEMPO = ("bursts", "vortex", "comets", "fountain", "flock", "ball")
M6 = ("homesunset", "wisp", "goodnight")  # the Home looks built so far
SHOWCASE = [  # in looks.json's order
    look_id
    for look_id in handoff_looks()
    if look_id in {*M2, *M3, *M5_AMBIENT, *M5_TEMPO, *M6, FIRMWARE_LOOK_ID}
]
PARTICLE_KINDS = {
    "fireflies": "fireflies",
    "embers": "embers",
    "rain": "rain_storm",
    "snow": "snowfall",
    "spotlights": "spotlights",
    "bursts": "beat_bursts",
    "vortex": "vortex",
    "comets": "twin_comets",
    "fountain": "fountain",
    "flock": "flock",
    "ball": "bouncing_ball",
    "wisp": "wisp",
}


def test_vendored_looks_json_is_a_byte_copy_of_the_handoff() -> None:
    vendored = VENDORED.read_bytes()
    assert vendored == (DESIGN / "looks.json").read_bytes()
    pinned = handoff_pins()
    assert hashlib.sha256(vendored).hexdigest() == pinned["looks.json"]


def test_the_handoff_looks_come_first_in_its_order_with_its_metadata() -> None:
    handoff = handoff_looks()
    looks = builtin_looks()[: len(SHOWCASE)]

    assert [look.id for look in looks] == SHOWCASE
    assert len(SHOWCASE) == len(M2) + len(M3) + len(M5_AMBIENT) + len(M5_TEMPO) + len(M6) + 1
    for look in looks:
        entry = handoff[look.id]
        assert (look.name, look.category, look.description) == (
            entry["name"],
            entry["category"],
            entry["description"],
        )
        inputs = tuple(entry["inputs"])
        needs_and_uses = (
            ((), inputs)  # a look that starts by hand waits for nothing and uses its inputs
            if look.id in STARTS_BY_HAND
            else (tuple(NEEDS_UNTIL_M7.get(look.id, inputs)), ())
        )
        assert (look.thumbnail, look.scope, look.needs, look.uses) == (
            entry["thumbnail"],
            entry["scope"],
            *needs_and_uses,
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
    assert layers["shockwave"] == [("field", "shockwave_shell"), ("field", "lighthouse_beam")]
    assert layers["scanner"] == [("field", "scanner_plane")]
    assert layers["checker"] == [("field", "checker_cubes")]
    assert layers["speakers"] == [("field", "speaker_waves")]
    assert layers["homesunset"] == [("field", "home_sunset"), ("firmware", "lifx_flame")]
    assert layers["goodnight"] == [("field", "goodnight")]
    assert builtin_look("shockwave").layers[1].blend == "add"  # the beam adds onto the shell
    sunset_flame, aurora_morph = builtin_look("sunset").layers[1], builtin_look("aurora").layers[1]
    assert (sunset_flame.lights, sunset_flame.settings) == ((Selector("type", "candle"),), {})
    assert aurora_morph.lights == (Selector("type", "candle"), Selector("type", "tube"))
    assert aurora_morph.settings == {"palette": list(AURORA_PALETTE)}  # the curtains' palette
    home_sunset = builtin_look("homesunset")
    home_flame = home_sunset.layers[1]  # the candles are Sunset's, on the same lights
    assert (home_flame.id, home_flame.name) == (sunset_flame.id, sunset_flame.name)
    assert (home_flame.lights, home_flame.settings) == (sunset_flame.lights, sunset_flame.settings)
    assert (home_sunset.scope, home_sunset.needs) == ("whole-home", ("sun",))


@pytest.mark.parametrize("look_id", PARTICLE_KINDS)
def test_each_particle_look_has_its_particle_layer_named_after_it(look_id: str) -> None:
    look = builtin_look(look_id)

    particles, *others = look.layers
    assert (particles.id, particles.type, particles.kind) == (
        "particles",
        "particles",
        PARTICLE_KINDS[look_id],
    )
    assert particles.name == handoff_looks()[look_id]["name"]
    assert isinstance(make_effect(particles), ParticleEffect)
    # The embers alone have a second layer: LIFX Flame, on the lights that run it.
    if look_id == "embers":
        [flame] = others
        assert (flame.id, flame.name, flame.type, flame.kind) == (
            "flame",
            "Flame",
            "firmware",
            "lifx_flame",
        )
        assert flame.lights == (Selector("type", "candle"), Selector("type", "tube"))
    else:
        assert others == []
    if look_id in M5_AMBIENT:
        assert look.category == "ambient"
    elif look_id in M6:  # a Home look runs on seconds, not beats
        assert look.category == "home"
        assert look.needs == ()
    else:
        assert look.needs == ("tempo",)


@pytest.mark.parametrize("look_id", ["focus", "shockwave", "speakers", "bursts", "fountain"])
def test_anchored_looks_start_from_the_anchor_their_description_names(look_id: str) -> None:
    look = builtin_look(look_id)

    [anchor_id] = {layer.settings["anchor"] for layer in streamed_layers(look)}
    anchor = seed_home().anchor(anchor_id)

    assert anchor is not None
    assert anchor.name.lower() in look.description.lower()


def test_goodnights_night_room_is_the_room_its_description_names() -> None:
    look = builtin_look("goodnight")

    [walk] = streamed_layers(look)
    room = seed_home().room(walk.settings["night_room"])

    assert (walk.id, walk.name) == ("walk", "Goodnight")
    assert room is not None
    assert room.name.lower() in look.description.lower()


def test_goodnight_starts_by_hand_and_uses_home_assistant() -> None:
    goodnight = builtin_look("goodnight")

    assert STARTS_BY_HAND == frozenset({"goodnight"})
    assert handoff_looks()["goodnight"]["inputs"] == ["home-assistant"]  # what M7's bedtime brings
    assert (goodnight.category, goodnight.scope) == ("home", "whole-home")
    assert (goodnight.needs, goodnight.uses) == ((), ("home-assistant",))


def test_the_handoff_layers_seed_the_map_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seeded: list[Home] = []

    def counted() -> Home:
        seeded.append(seed_home())
        return seeded[-1]

    monkeypatch.setattr(builtin, "seed_home", counted)
    builtin._handoff_layers()

    assert len(seeded) == 1  # one map serves every anchored look


def test_speaker_waves_plays_on_the_beat_until_m7() -> None:
    speakers = builtin_look("speakers")

    assert handoff_looks()["speakers"]["inputs"] == ["music"]  # what M7 brings
    assert (speakers.category, speakers.needs) == ("audio", ("tempo",))


def test_an_anchor_is_found_by_the_name_a_text_mentions() -> None:
    anchors = tiny_home().anchors  # "Sofa" and "Speakers"

    assert anchor_named_in("Calm near the sofa, busy further off.", anchors) == "sofa"
    assert anchor_named_in("Between the sofa and the speakers", anchors) == ""  # which one?
    assert anchor_named_in("Two sofas", anchors) == ""  # whole words only
    assert anchor_named_in("", anchors) == ""


def test_a_room_is_found_by_the_name_a_text_mentions() -> None:
    rooms = tiny_home().rooms
    first, second = rooms[0], rooms[1]

    assert room_named_in(f"Calm in the {first.name.lower()}, busy further off.", rooms) == first.id
    assert room_named_in(f"Between the {first.name} and the {second.name}", rooms) == ""  # which?
    assert room_named_in(f"Two {first.name.lower()}s", rooms) == ""  # whole words only
    assert room_named_in("", rooms) == ""


def test_the_firmware_showcase_layers_bottom_to_top() -> None:
    showcase = builtin_look(FIRMWARE_LOOK_ID)
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
    effects = [make_effect(layer) for layer in [*streamed_layers(look), *firmware_layers(look)]]
    for effect in effects:
        effect.reseed(seed)
    frames: list[FloatRGB] = []
    for step in range(180):
        ctx = tempo_ctx(2.0 * (1000.0 + step / 60))  # 120 BPM, from 1000 s on
        for effect in effects:
            if isinstance(effect, FirmwareEffect):
                frames.append(effect.emulate(ctx, leds))
            elif isinstance(effect, ParticleEffect):
                frames.append(drawn(effect, ctx, leds))
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
    if look.id in PARTICLE_KINDS:
        # None of that fails a look that is black everywhere. The particle layer draws the
        # first frame of each step (the embers' Flame copy comes after it, and could light
        # the LEDs without it).
        assert any(frame.any() for frame in first[:: len(look.layers)]), "the particles are dark"
