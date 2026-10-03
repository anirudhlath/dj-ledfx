"""A zone runtime plays a transition from the looks its lights showed (spec §5.3)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar

import numpy as np
import pytest
from loguru import logger
from runtime_fakes import (
    FlatField,
    field_layer,
    glow_layer,
    latest,
    look_of,
    placed_light,
    register_fields,
    runtime_of,
)

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.looks.model import Layer, Transition
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import ZoneRuntime

FADE = Transition(kind="fade", duration_s=2.0)
HORIZON = 0.02 + 1 / 60  # the fake lights' latency and a frame: every frame's lead


class BrokenField(FlatField, register=False):
    """A field that fails every frame."""

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        raise RuntimeError("boom")


class CostlyField(FlatField, register=False):
    """A flat field whose render "takes" 3 ms on the test's clock (spent)."""

    spent: ClassVar[float] = 0.0

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        CostlyField.spent += 0.003
        return super().render(ctx, leds)


@pytest.fixture(autouse=True)
def _fields() -> Iterator[None]:
    register_fields()
    Effect._registry["broken_field"] = BrokenField
    Effect._registry["costly_field"] = CostlyField
    CostlyField.spent = 0.0
    yield


def _flat(level: float, **changes: Any) -> ZoneRuntime:
    return runtime_of(look_of(field_layer(level), name=f"Level {level}"), **changes)


def _levels(runtime: ZoneRuntime) -> list[float]:
    return [round(float(x), 3) for x in latest(runtime)[:, 0]]


def test_a_fade_mixes_the_old_look_into_the_new_one() -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    assert _levels(new) == [1.0] * 8 and new.state == "transition"
    new.tick(1001.0)
    assert _levels(new) == [0.5] * 8
    new.tick(1002.0)
    assert _levels(new) == [0.0] * 8
    assert new.state == "running" and new.transition_info() is None


def test_a_wipe_switches_the_west_first() -> None:
    lights = [placed_light("lamp", *[(x, 1.0, 1.0) for x in (0.0, 1.0, 2.0, 3.0, 4.0)])]
    old, new = _flat(1.0, lights=lights), _flat(0.0, lights=lights)
    new.begin_transition(Transition(kind="wipe", duration_s=2.0), [old])

    new.tick(1000.0)
    new.tick(1001.0)

    assert _levels(new) == [0.0, 0.0, 0.5, 1.0, 1.0]


def test_lights_nothing_drove_fade_in_from_black() -> None:
    new = _flat(0.8)
    new.begin_transition(FADE, [])

    new.tick(1000.0)
    assert _levels(new) == [0.0] * 8
    new.tick(1001.0)
    assert _levels(new) == [0.4] * 8
    info = new.transition_info()
    assert info is not None and info.from_name == ""  # nothing ran there


@pytest.mark.parametrize("transition", [Transition(), Transition(kind="fade", duration_s=0.0)])
def test_a_cut_plays_nothing(transition: Transition) -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(transition, [old])

    new.tick(1000.0)

    assert new.state == "running" and _levels(new) == [0.0] * 8


def test_the_transition_says_where_it_has_got() -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(FADE, [old])
    new.tick(1000.0)
    new.tick(1000.5)

    info = new.transition_info()

    assert info is not None
    assert (info.from_name, info.kind, info.duration_s) == ("Level 1.0", "fade", 2.0)
    assert info.progress == pytest.approx(0.25)


def test_the_old_look_keeps_its_own_brightness() -> None:
    old, new = _flat(1.0, brightness=0.5), _flat(0.0)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)

    assert _levels(new) == [0.5] * 8  # sent at the new zone's 1.0: the old look's 0.5


def test_a_brightness_change_mid_transition_dims_both_looks() -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(FADE, [old])

    new.set_brightness(0.3)

    assert old.brightness == 0.3


# Review Focus 2: a light running a firmware effect keeps it until the midpoint, and only
# then goes over to the new look, whole.
def test_a_firmware_light_switches_whole_at_the_midpoint() -> None:
    old = runtime_of(look_of(field_layer(1.0), glow_layer(0.9)))  # the tile runs Glow
    switches: list[ZoneRuntime] = []
    new = _flat(0.0, on_switch=switches.append)
    new.begin_transition(FADE, [old])
    glow = old.claim_for("tile")
    assert new.claim_for("tile") == glow and not new.streams("tile")
    assert new.applied_key("tile") == old.applied_key("tile")  # Glow, not sent again
    assert new.applied_key("lamp") == (new.generation, None) and new.streams("lamp")

    new.tick(1000.0)  # the transition runs from this frame's time, 1000 + HORIZON
    new.tick(1001.0)  # this frame's time is the midpoint; now isn't there yet
    assert new.claim_for("tile") == glow
    assert _levels(new)[:4] == [0.0] * 4  # the tile's rows: new, whole
    assert _levels(new)[4:] == [0.5] * 4  # the rest: half-way, about

    new.tick(1000.0 + 1.0 + HORIZON)
    assert new.applied_key("tile") == (new.generation, None) and new.streams("tile")
    assert switches == [new] and new.handing_over == {"tile"}  # the manager applies it
    new.tick(1000.0 + 1.1 + HORIZON)
    assert switches == [new]  # told once


def test_a_light_the_new_look_runs_itself_streams_the_old_one_until_the_midpoint() -> None:
    old = _flat(1.0)
    new = runtime_of(look_of(field_layer(0.0), glow_layer(0.9)))
    new.begin_transition(FADE, [old])

    new.tick(1000.0)

    assert new.applied_key("tile") == old.applied_key("tile") and new.streams("tile")
    assert _levels(new)[:4] == [1.0] * 4
    new.tick(1000.0 + 1.0 + HORIZON)
    assert new.mode_of("tile") == "own-effect" and not new.streams("tile")


# Review Focus 2 (I2): through its route, at its latency, a light the new look runs itself
# reads the old look until the zone manager has started its effect, though the frames'
# times pass the midpoint before now does. It never reads the new look's rows.
def test_a_light_the_new_look_runs_itself_reads_the_old_look_until_its_effect_starts() -> None:
    switches: list[ZoneRuntime] = []
    old = _flat(1.0)
    new = runtime_of(look_of(field_layer(0.0), glow_layer(0.9)), on_switch=switches.append)
    new.begin_transition(FADE, [old])
    route = new.route_for("tile")  # the scheduler's until the manager applies the tile
    assert route is not None and route.streaming

    for step in range(100):  # to 1001.65: the midpoint, 1001 + HORIZON, has passed
        now = 1000.0 + step / 60
        new.tick(now)
        read = route.colors_at(now + 0.02, 4)  # the tile's latency
        assert read is not None and (read == 255).all(), f"at {now}: {read.tolist()}"

    assert switches == [new] and new.handing_over == {"tile"}
    new.handed_over({"tile"})  # the manager started Glow: frames no longer reach it
    new.tick(1001.7)
    assert _levels(new)[:4] == [0.9] * 4 and new.handing_over == set()  # the preview's Glow


def test_a_midpoint_with_no_light_held_switches_nothing() -> None:
    switches: list[ZoneRuntime] = []
    pushes: list[ZoneRuntime] = []
    old = _flat(1.0)
    new = _flat(0.0, on_switch=switches.append, on_state_change=pushes.append)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    new.tick(1000.0 + 1.0 + HORIZON)

    assert switches == [] and new.handing_over == set()
    assert pushes == [new]  # the running channel still pushes the zone at its midpoint


def test_a_light_nothing_drove_runs_its_firmware_effect_at_once() -> None:
    new = runtime_of(look_of(field_layer(0.0), glow_layer(0.9)))
    new.begin_transition(FADE, [])

    assert new.mode_of("tile") == "own-effect" and not new.streams("tile")


def test_an_old_look_that_fails_ends_the_transition_not_the_zone() -> None:
    broken = Layer(id="broken", name="Broken", type="field", kind="broken_field")
    old, new = runtime_of(look_of(broken)), _flat(0.4)
    new.begin_transition(FADE, [old])
    warnings: list[str] = []
    sink = logger.add(warnings.append, level="WARNING", format="{message}")
    try:
        new.tick(1000.0)
    finally:
        logger.remove(sink)

    assert new.state == "running" and new.crash is None
    assert _levels(new) == [0.4] * 8
    assert any("cutting to" in line for line in warnings)


# Review Focus 3: a map change mid-transition cuts to the new look on the lights it keeps.
def test_new_lights_mid_transition_end_it() -> None:
    old = runtime_of(look_of(field_layer(1.0), glow_layer(0.9)))
    switches: list[ZoneRuntime] = []
    new = _flat(0.0, on_switch=switches.append)
    new.begin_transition(FADE, [old])
    new.tick(1000.0)

    new.set_lights(new.lights[:2])  # the lamp leaves
    new.tick(1000.1)

    assert new.state == "running" and _levels(new) == [0.0] * 5
    assert switches == [new] and new.handing_over == {"tile"}  # the manager applies it


# Review Focus 3: a start mid-transition takes the mix on; a third ends the oldest one.
def test_a_start_mid_transition_takes_the_mix_on_and_three_looks_at_most_render() -> None:
    first, second, third, fourth = _flat(1.0), _flat(0.0), _flat(0.5), _flat(0.2)
    second.begin_transition(FADE, [first])
    second.tick(1000.0)
    second.tick(1001.0)  # half-way: 0.5

    third.begin_transition(FADE, [second])
    third.tick(1001.0)
    assert _levels(third) == [0.5] * 8  # no jump: it starts from the mix
    assert third.transition_sources == (second,) and second.transition_sources == (first,)

    fourth.begin_transition(FADE, [third])
    assert second.transition_sources == ()  # the oldest look is dropped
    assert second.state == "running"


def test_a_twin_draws_what_its_runtime_draws_under_the_same_generation() -> None:
    original = runtime_of(look_of(field_layer(0.7), glow_layer(0.9)))
    twin = original.twin()

    original.tick(1000.0)
    twin.tick(1000.0)

    assert twin.generation == original.generation
    assert twin.claim_for("tile") is not None
    np.testing.assert_array_equal(latest(twin), latest(original))


# Spec §5.3: during a transition the zone renders both looks, so both count against the
# frame budget; with one look again it goes back to every tick.
def test_both_looks_count_against_the_frame_budget() -> None:
    costly = Layer(id="costly", name="Costly", type="field", kind="costly_field")
    old = runtime_of(look_of(costly))
    new = runtime_of(look_of(costly), timer=lambda: CostlyField.spent)
    new.begin_transition(Transition(kind="fade", duration_s=1.0), [old])

    new.tick(1000.0)  # 6 ms: both looks, over the 5 ms budget
    assert new.horizon_s == pytest.approx(0.02 + 2 / 60)  # every other tick
    for step in range(1, 120):
        new.tick(1000.0 + step / 60)
    assert new.state == "running"
    assert new.horizon_s == pytest.approx(0.02 + 1 / 60)  # 3 ms: every tick again


def test_a_zone_at_no_brightness_stays_dark_mid_transition() -> None:
    old, new = _flat(1.0), _flat(0.5, brightness=0.0)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    new.tick(1001.0)

    assert new.state == "transition" and _levels(new) == [0.25] * 8  # sent at 0: dark
