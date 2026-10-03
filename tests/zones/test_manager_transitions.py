"""The zone manager plays a start's transition (spec §5.3): from what the lights showed,
with the lights that run firmware effects switching at the midpoint."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from typing import Any, ClassVar

import pytest
from conftest import FakeLight, events
from loguru import logger
from runtime_fakes import FADE, LAMP, TILE, FlatField
from zone_home import GLOW, HomeFactory, zone_record

from dj_ledfx.effects.base import Effect
from dj_ledfx.looks.model import Layer, Look, Transition
from dj_ledfx.looks.store import look_body
from dj_ledfx.main import _switch_at_midpoints
from dj_ledfx.zones.model import LightsChanged, TransitionInfo, TransitionSwitched
from dj_ledfx.zones.runtime import ZoneRuntime


def _past_midpoint(runtime: ZoneRuntime) -> None:
    """The transition's first frame, then a tick at its midpoint."""
    horizon = runtime.horizon_s
    runtime.tick(1000.0)  # the transition runs from this frame's time: 1000 + horizon
    runtime.tick(1000.0 + horizon + FADE.duration_s / 2)


async def test_a_start_plays_the_transition_asked_for_or_the_looks_own(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", caps=LAMP)
    home = await make_home([lamp], [zone_record("z", "lamp")])
    first = await home.manager.start("z", home.look("classic-breathe"))
    assert first.running.state == "running" and first.running.transition is None  # a cut

    result = await home.manager.start("z", home.look("classic-strobe"), FADE)

    assert result.running.state == "transition"
    assert result.running.transition == TransitionInfo("Breathe", "fade", 0.0, 2.0)
    wipe = Transition(kind="wipe", duration_s=1.0)
    own = await home.manager.start("z", replace(home.look("classic-breathe"), transition=wipe))
    assert own.running.transition == TransitionInfo("Strobe", "wipe", 0.0, 1.0)


async def test_a_take_over_plays_from_the_zone_it_took_the_lights_from(
    make_home: HomeFactory,
) -> None:
    a, b, c = FakeLight("a"), FakeLight("b"), FakeLight("c")
    home = await make_home(
        [a, b, c], [zone_record("left", "a", "b"), zone_record("right", "b", "c")]
    )
    await home.manager.start("left", home.look("classic-breathe"))

    result = await home.manager.start("right", home.look("classic-strobe"), FADE)

    assert result.running.transition is not None
    assert result.running.transition.from_name == "Breathe"  # c was idle: it fades in
    left = home.manager.running_info("left")
    assert left is not None and left.state == "running" and left.lights == ("a",)


# Review Focus 2: a light running a firmware effect keeps it, unsent again, until the
# midpoint; then it goes over to the new look.
async def test_a_firmware_light_keeps_its_effect_until_the_midpoint(
    make_home: HomeFactory,
) -> None:
    tile, lamp = FakeLight("tile", caps=TILE), FakeLight("lamp", caps=LAMP)
    home = await make_home([tile, lamp], [zone_record("z", "tile", "lamp")])
    await home.manager.start("z", GLOW)
    sent = len(tile.calls)

    await home.manager.start("z", home.look("classic-breathe"), FADE)

    assert tile.calls[sent:] == []
    assert not home.routes.routes["tile"].streaming
    assert home.manager.light_mode("tile") == "own-effect"
    assert home.manager.effect_name("tile") == "Glow"

    _past_midpoint(home.host.runtimes["z"])
    await home.manager.switch("z")

    assert tile.names()[sent:] == ["prepare_stream"]
    assert home.routes.routes["tile"].streaming
    assert home.manager.light_mode("tile") == "streaming"


# Review Focus 2: the new look's firmware effect, refused at the midpoint, is streamed.
async def test_a_light_that_refuses_the_new_effect_at_the_midpoint_streams_a_copy(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", home.look("classic-breathe"))
    tile.reject_firmware = True

    await home.manager.start("z", GLOW, FADE)
    assert home.routes.routes["tile"].streaming  # the old look, until the midpoint
    _past_midpoint(home.host.runtimes["z"])
    await home.manager.switch("z")

    assert home.manager.light_mode("tile") == "streamed-copy"
    assert home.routes.routes["tile"].streaming


# Review Focus 2: a light back online mid-transition gets the look it follows now.
async def test_a_light_back_online_mid_transition_gets_the_look_it_follows(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)

    home.devices.demote_device("tile")
    await asyncio.sleep(0)  # let the demoted adapter's disconnect run
    await home.manager.on_device_offline("tile")
    await tile.connect()
    home.devices.promote_device("tile", tile)
    await home.manager.on_device_online("tile")

    assert tile.names()[-1] == "firmware"  # Glow again: it holds until the midpoint
    info = home.manager.running_info("z")
    assert info is not None and info.state == "transition"


# Review Focus 3: Off and Stop all mid-transition put the lights back, and a midpoint
# that comes after changes nothing.
@pytest.mark.parametrize("stop", ["off", "stop_all"])
async def test_off_mid_transition_puts_the_lights_back(make_home: HomeFactory, stop: str) -> None:
    tile, lamp = FakeLight("tile", caps=TILE), FakeLight("lamp", caps=LAMP)
    home = await make_home([tile, lamp], [zone_record("z", "tile", "lamp")])
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)
    _past_midpoint(home.host.runtimes["z"])  # its switch is due

    await (home.manager.off("z") if stop == "off" else home.manager.stop_all())
    calls = len(tile.calls)
    await home.manager.switch("z")

    assert ("restore", b"before") in tile.calls and ("restore", b"before") in lamp.calls
    assert len(tile.calls) == calls
    assert home.manager.running_info("z") is None and not home.routes.routes


# Review Focus 3: a zone mid-transition that loses lights cuts to its new look on the rest;
# the zone that took them plays its own transition from that look.
async def test_a_take_over_of_a_zone_in_transition_cuts_it_on_the_lights_it_keeps(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    home = await make_home([a, b], [zone_record("left", "a", "b"), zone_record("right", "b")])
    await home.manager.start("left", home.look("classic-breathe"))
    await home.manager.start("left", home.look("classic-strobe"), FADE)

    result = await home.manager.start("right", home.look("classic-breathe"), FADE)

    left = home.manager.running_info("left")
    assert left is not None and left.state == "running" and left.lights == ("a",)
    assert result.running.transition is not None
    assert result.running.transition.from_name == "Strobe"


# M4: a light taken from a zone mid-transition keeps the firmware effect that zone's old
# look runs on it, not sent again, until the new transition's midpoint; then it switches.
async def test_a_light_taken_mid_transition_keeps_its_effect_until_the_new_midpoint(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a", caps=TILE), FakeLight("b", caps=TILE)
    home = await make_home([a, b], [zone_record("left", "a", "b"), zone_record("right", "b")])
    await home.manager.start("left", GLOW)
    await home.manager.start("left", home.look("classic-breathe"), FADE)  # b keeps Glow
    sent = len(b.calls)

    await home.manager.start("right", home.look("classic-strobe"), FADE)

    assert b.calls[sent:] == []  # Glow stays on it, not sent again
    assert home.manager.effect_name("b") == "Glow" and not home.routes.routes["b"].streaming
    _past_midpoint(home.host.runtimes["right"])
    await home.manager.switch("right")
    assert b.names()[sent:] == ["prepare_stream"]  # then the strobe streams to it


class CountedField(FlatField, register=False):
    """A flat field that counts the effects made of it: every runtime it's compiled in,
    a twin's too."""

    made: ClassVar[int] = 0

    def __init__(self, level: float = 0.5) -> None:
        super().__init__(level)
        CountedField.made += 1


# E8 = H9: a start whose transition doesn't play builds no twin of the zones it takes from.
@pytest.mark.parametrize(
    ("transition", "twins"),
    [(Transition(), 0), (Transition(kind="fade", duration_s=0.0), 0), (FADE, 1)],
)
async def test_only_a_start_whose_transition_plays_builds_twins(
    make_home: HomeFactory, transition: Transition, twins: int
) -> None:
    Effect._registry["counted_field"] = CountedField  # conftest drops it after each test
    CountedField.made = 0
    a, b = FakeLight("a"), FakeLight("b")
    home = await make_home([a, b], [zone_record("left", "a", "b"), zone_record("right", "b")])
    layer = Layer(id="counted", name="Counted", type="field", kind="counted_field")
    await home.manager.start("left", Look("counted", "Counted", "ambient", layers=(layer,)))
    made = CountedField.made

    await home.manager.start("right", home.look("classic-breathe"), transition)

    assert CountedField.made - made == twins


# Review Focus 2 (I2): a light the new look runs itself streams the old look past the
# midpoint, until the zone manager has started its effect.
async def test_a_light_the_new_look_runs_itself_streams_until_its_effect_starts(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.start("z", GLOW, FADE)
    runtime = home.host.runtimes["z"]

    _past_midpoint(runtime)
    assert home.routes.routes["tile"].streaming and runtime.handing_over == {"tile"}
    await home.manager.switch("z")

    assert tile.names()[-1] == "firmware" and not home.routes.routes["tile"].streaming
    assert runtime.handing_over == set()


# I2, cut short: a transition that ends before its midpoint (here another zone takes one
# of its lights) stops the frames of a light the new look runs itself until it's applied.
async def test_a_transition_cut_short_stops_frames_to_a_light_the_new_look_runs_itself(
    make_home: HomeFactory,
) -> None:
    tile, lamp = FakeLight("tile", caps=TILE), FakeLight("lamp", caps=LAMP)
    home = await make_home(
        [tile, lamp], [zone_record("z", "tile", "lamp"), zone_record("other", "lamp")]
    )
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.start("z", GLOW, FADE)
    switches = events(home.bus, TransitionSwitched)
    assert home.routes.routes["tile"].streaming  # the old look, until the midpoint

    await home.manager.start("other", home.look("classic-breathe"))  # z cuts to Glow

    assert switches == [TransitionSwitched("z")]
    assert not home.routes.routes["tile"].streaming  # never the new look's rows
    await home.manager.switch("z")
    assert tile.names()[-1] == "firmware"


async def _spawned(background: set[asyncio.Task[object]]) -> None:
    """Wait for the tasks main's wiring spawned (each lets go of its own once done)."""
    assert background, "nothing was spawned"
    await asyncio.wait(set(background))


async def test_the_manager_applies_the_midpoint_by_itself(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    background: set[asyncio.Task[object]] = set()
    _switch_at_midpoints(home.bus, home.manager, background)  # as main wires it
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)

    _past_midpoint(home.host.runtimes["z"])
    await _spawned(background)

    assert tile.names()[-1] == "prepare_stream"


# I1: each midpoint's switch is a task of its own, so one that fails is logged and the next
# midpoint still applies.
async def test_a_switch_that_fails_is_logged_and_the_next_midpoint_still_applies(
    make_home: HomeFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    tile = FakeLight("tile", caps=TILE, connected=False)  # offline at the starts: uncaptured
    home = await make_home([tile], [zone_record("z", "tile")])
    background: set[asyncio.Task[object]] = set()
    _switch_at_midpoints(home.bus, home.manager, background)
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.start("z", GLOW, FADE)
    tile.connected = True  # back, before the zone manager has heard
    save = home.db.save_device_states
    failures = [sqlite3.OperationalError("database is locked")]

    async def save_once_failing(states: Mapping[str, bytes]) -> None:
        if failures:
            raise failures.pop()
        await save(states)

    monkeypatch.setattr(home.db, "save_device_states", save_once_failing)
    errors: list[Any] = []
    sink = logger.add(lambda message: errors.append(message.record), level="ERROR")
    try:
        _past_midpoint(home.host.runtimes["z"])  # its switch captures the tile: it fails
        await _spawned(background)
        await home.manager.start("z", home.look("classic-breathe"), FADE)
        _past_midpoint(home.host.runtimes["z"])
        await _spawned(background)
    finally:
        logger.remove(sink)

    assert [record["exception"].type for record in errors] == [sqlite3.OperationalError]
    assert tile.names()[-2:] == ["firmware", "prepare_stream"]  # Glow, then the midpoint


# E9: a midpoint with no light held applies nothing; the running channel still pushes it.
async def test_a_transition_that_holds_no_light_switches_nothing_at_its_midpoint(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", caps=LAMP)
    home = await make_home([lamp], [zone_record("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.start("z", home.look("classic-strobe"), FADE)
    switches = events(home.bus, TransitionSwitched)
    lights = events(home.bus, LightsChanged)
    route, pushes = home.routes.routes["lamp"], len(home.changes)

    _past_midpoint(home.host.runtimes["z"])
    await home.manager.switch("z")

    assert switches == [] and lights == []
    assert home.routes.routes["lamp"] is route  # its route isn't set again
    assert len(home.changes) == pushes + 1


async def test_a_resumed_zone_plays_no_transition(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [zone_record("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"), FADE)

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "running" and info.transition is None


# Review Focus 1: an assignment saved with a transition no request could send now resumes,
# its duration clamped.
async def test_an_assignment_saved_with_an_odd_transition_resumes(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [zone_record("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    saved = json.loads(look_body(home.look("classic-breathe")))
    saved["transition"] = {"kind": "dissolve", "durationS": float("nan")}  # dumped as NaN
    await home.db.write(
        "UPDATE zone_assignments SET look=? WHERE zone_id='z'", (json.dumps(saved),)
    )

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "running"
    assert home.host.runtimes["z"].look.transition == Transition(kind="dissolve")
