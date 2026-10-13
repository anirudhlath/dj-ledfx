from __future__ import annotations

import numpy as np
import pytest
from conftest import builtin_look
from map_home import upright
from runtime_fakes import (
    DotParticles,
    FlatField,
    dot_layer,
    field_layer,
    glow_layer,
    latest,
    look_of,
    placed_light,
    runtime_of,
)

from dj_ledfx.looks.model import HeightMask, Layer, LayerType, Mirror, Transform
from dj_ledfx.zones.runtime import ZoneRuntime

pytestmark = pytest.mark.usefixtures("_fields")

# One light of 9 LEDs, 0.5 m apart along x from 0 to 4 m, 1 m up.
ROW_LIGHT = placed_light("row", *[(0.5 * i, 0.0, 1.0) for i in range(9)])
# Lamps a-d: four upright lamps at the corners of a 4 x 4 m room.
CORNERS = [
    placed_light(f"lamp-{name}", *upright(x, y))
    for name, (x, y) in zip("abcd", [(0.5, 0.5), (3.5, 0.5), (3.5, 3.5), (0.5, 3.5)], strict=True)
]
PARTICLE_LOOKS = [
    "fireflies",
    "embers",
    "rain",
    "snow",
    "spotlights",
    "bursts",
    "vortex",
    "comets",
    "fountain",
    "flock",
    "ball",
]


def _lit(runtime: ZoneRuntime) -> list[int]:
    """The LEDs the newest frame lights at least half."""
    return [int(i) for i in np.flatnonzero(latest(runtime)[:, 0] >= 0.5)]


def test_a_particle_layer_lights_the_leds_near_its_particles() -> None:
    runtime = runtime_of(look_of(dot_layer(x=2.0)), [ROW_LIGHT])
    runtime.tick(100.0)
    frame = latest(runtime)
    np.testing.assert_allclose(frame[4], 1.0)  # the LED at 2 m
    assert _lit(runtime) == [4]
    assert not frame[[0, 8]].any()  # 2 m off: past its reach


def test_particle_and_field_layers_blend_bottom_to_top() -> None:
    look = look_of(field_layer(level=0.2), dot_layer(x=2.0, level=0.5, blend="add"))
    runtime = runtime_of(look, [ROW_LIGHT])
    runtime.tick(100.0)
    frame = latest(runtime)
    np.testing.assert_allclose(frame[4], 0.7)
    np.testing.assert_allclose(frame[0], 0.2)


def test_a_layers_transform_and_mirror_move_its_particles_as_they_move_a_field() -> None:
    shifted = runtime_of(
        look_of(dot_layer(x=2.0, transform=Transform(offset=(1.0, 0.0, 0.0)))), [ROW_LIGHT]
    )
    mirrored = runtime_of(look_of(dot_layer(x=1.0, mirror=Mirror(axis="x"))), [ROW_LIGHT])
    shifted.tick(100.0)
    mirrored.tick(100.0)
    assert _lit(shifted) == [6]  # 1 m further east
    assert _lit(mirrored) == [2, 6]  # at 1 m, and across the middle at 3 m


def test_a_particle_layers_mask_weighs_the_leds_it_lights() -> None:
    # Two LEDs 0.2 m under and over the dot: a mask from 1 m up keeps its light off the lower.
    stack = placed_light("stack", (1.0, 0.0, 0.8), (1.0, 0.0, 1.2))
    field = field_layer(level=0.2)
    bare = runtime_of(look_of(field, dot_layer(x=1.0, level=0.5, blend="add")), [stack])
    masked = runtime_of(
        look_of(field, dot_layer(x=1.0, level=0.5, blend="add", mask=HeightMask(1.0, 2.0))),
        [stack],
    )
    bare.tick(100.0)
    masked.tick(100.0)
    # Each layer's ground holds both LEDs, the masked one's too: its particles move among
    # every LED of its view, and the mask only weighs what they light.
    assert DotParticles.ground_led_counts == [2, 2]
    assert latest(bare)[0, 0] > 0.3  # the dot lights both LEDs
    np.testing.assert_allclose(latest(masked)[0], 0.2)  # under the band: the field alone
    np.testing.assert_allclose(latest(masked)[1], latest(bare)[1])  # in it: the field and the dot


def test_a_hidden_particle_layer_draws_nothing() -> None:
    runtime = runtime_of(
        look_of(field_layer(level=0.2), dot_layer(x=2.0, visible=False)), [ROW_LIGHT]
    )
    runtime.tick(100.0)
    np.testing.assert_allclose(latest(runtime), 0.2)


def test_the_classic_field_effect_is_the_bottom_layers_only_when_that_is_a_field() -> None:
    field_below = runtime_of(look_of(field_layer(), dot_layer()), [ROW_LIGHT])
    particles_below = runtime_of(look_of(dot_layer(), field_layer()), [ROW_LIGHT])
    assert isinstance(field_below.field_effect, FlatField)
    assert particles_below.field_effect is None


def test_update_look_tunes_a_particle_layer_in_place() -> None:
    runtime = runtime_of(look_of(dot_layer(x=1.0), glow_layer()), [ROW_LIGHT])
    generation = runtime.generation
    runtime.update_look(look_of(dot_layer(x=3.0), glow_layer()))
    runtime.tick(100.0)
    assert runtime.generation == generation
    assert _lit(runtime) == [6]


def test_a_particle_layer_that_gives_nan_crashes_its_zone() -> None:
    runtime = runtime_of(look_of(dot_layer()), [ROW_LIGHT])
    FlatField.mode = "nan"
    runtime.tick(100.0)
    assert runtime.crash is not None and runtime.crash.layer == "Dots"
    assert "NaN" in runtime.crash.message
    assert runtime.ring.count == 0


@pytest.mark.parametrize(
    ("layer_type", "kind", "reason"),
    [
        ("particles", "flat_field", "isn't a particle effect"),
        ("field", "dot_particles", "isn't a field effect"),
    ],
)
def test_a_saved_layer_of_the_wrong_kind_crashes_its_zone_with_the_reason(
    layer_type: LayerType, kind: str, reason: str
) -> None:
    layer = Layer(id="odd", name="Odd", type=layer_type, kind=kind)
    runtime = runtime_of(look_of(layer), [ROW_LIGHT])
    assert runtime.state == "crashed"
    assert runtime.crash is not None and runtime.crash.layer == "Odd"
    assert reason in runtime.crash.message
    runtime.tick(100.0)
    assert runtime.ring.count == 0


def test_a_light_a_firmware_layer_cannot_run_shows_the_particle_layer() -> None:
    runtime = runtime_of(look_of(dot_layer(x=2.0), glow_layer()), [ROW_LIGHT])
    assert runtime.mode_of("row") == "streaming"  # a lamp can't run Glow: the dots play
    assert runtime.field_effect is None  # no classic effect to tune


# Two beats at the internal clock's 120 BPM, a twelfth of a beat apart, then a jump ahead:
# whatever phase the clock is at, some frame falls near a landing (a lone ball is dark while
# it flies between two lamps).
MOMENTS = [1000.0 + k / 24 for k in range(24)] + [1003.25]


@pytest.mark.parametrize("look_id", PARTICLE_LOOKS)
def test_a_twin_of_a_particle_look_draws_what_its_runtime_draws(look_id: str) -> None:
    original = runtime_of(builtin_look(look_id), CORNERS)
    twin = original.twin()

    lit = False
    for moment in MOMENTS:
        original.tick(moment)
        twin.tick(moment)
        np.testing.assert_array_equal(latest(twin), latest(original))
        lit = lit or bool(latest(original).any())
    assert lit  # on the lamps
