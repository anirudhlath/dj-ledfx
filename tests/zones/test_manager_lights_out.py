"""Lights out (M6 ruling 19): when a look has a light dark for good, the zone manager switches
the light off, and leaves it alone until a new run takes it. Time is a fake clock the tests
move (zone_home.FakeClock): the timer's sleeps wake as it advances, nothing waits for real."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeLight
from loguru import logger
from map_home import tiny_home
from runtime_fakes import field_layer, look_of, out_layer
from zone_home import START, FakeClock, FakeHome, Home, HomeFactory, build_home

from dj_ledfx.effects.goodnight import FADE_S, OFF_AFTER_S
from dj_ledfx.home.shapes import PointShape
from dj_ledfx.looks.model import Layer, Look, Transition
from dj_ledfx.zones.manager import LIGHTS_OUT_RETRY_S
from dj_ledfx.zones.model import HOME_ZONE_ID

pytestmark = pytest.mark.usefixtures("_fields")


def _out_look(out: Mapping[str, float] | None = None) -> Look:
    """A look that has these lights out at these seconds (a: 5 s) and nothing else lit."""
    return look_of(out_layer(out or {"a": 5.0}))


async def _started(
    make_home: HomeFactory,
    clock: FakeClock,
    *,
    lights: list[FakeLight] | None = None,
    out: Mapping[str, float] | None = None,
    preview_only: bool = False,
) -> Home:
    """Whole home over the west room's light a and the east room's b, running a look that has
    a out at 5 s (or `out`), on the fake clock."""
    view = FakeHome(rooms={"west": ["a"], "east": ["b"]})
    home = await make_home(
        lights if lights is not None else [FakeLight("a"), FakeLight("b")],
        [],
        view=view,
        preview_only=preview_only,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    await home.manager.start(HOME_ZONE_ID, _out_look(out))
    return home


def _powers(light: FakeLight) -> list[object]:
    return [value for name, value in light.calls if name == "power"]


async def test_a_light_is_switched_off_once_its_look_has_it_dark_for_good(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b])
    seen: list[tuple[bool, bool]] = []
    real = a.set_power

    async def watched(on: bool) -> None:
        seen.append(("a" in home.routes.routes, a.send_lock.locked()))
        await real(on)

    a.set_power = watched  # type: ignore[method-assign]
    assert home.routes.routes["a"].streaming and home.routes.routes["b"].streaming

    await clock.advance(4.9)
    assert home.routes.routes["a"].streaming and _powers(a) == []

    await clock.advance(0.1)

    assert "a" not in home.routes.routes
    assert a.calls[-1] == ("power", False) and home.manager.power_of("a") is False
    assert seen == [(False, True)]  # its route gone first, and the command under its send lock
    assert home.routes.routes["b"].streaming and _powers(b) == []


async def test_a_light_that_cant_switch_power_keeps_streaming_black(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a = FakeLight("a", switches_power=False)
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])

    await clock.advance(30.0)

    assert _powers(a) == [] and home.routes.routes["a"].streaming


async def test_an_out_light_switched_on_elsewhere_is_left_alone(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    await clock.advance(5.0)
    a.calls.clear()
    a.frames.clear()
    a.power = True  # someone switched it back on

    await home.manager.on_power_reading("a", True)
    await home.manager.verify_firmware("a")

    assert a.calls == [] and a.frames == []  # no prepare, no frame, no power call
    assert "a" not in home.routes.routes


async def test_a_later_start_switches_it_back_on_and_keeps_its_capture(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    await clock.advance(5.0)
    a.calls.clear()

    await home.manager.start("west", look_of(field_layer()))

    assert a.names() == ["power", "prepare_stream"] and a.calls[0] == ("power", True)
    assert home.routes.routes["a"].streaming
    assert a.power is True and home.manager.power_of("a") is True
    await home.manager.off("west")
    assert a.calls[-1] == ("restore", b"before")  # the capture from the first start, once
    assert a.names().count("capture") == 0


@pytest.mark.parametrize(
    "end",
    [
        pytest.param(lambda home: home.manager.off(HOME_ZONE_ID), id="off"),
        pytest.param(lambda home: home.manager.stop_all(), id="stop-all"),
    ],
)
async def test_off_and_stop_all_restore_an_out_light_power_included(
    make_home: HomeFactory, end: Callable[[Home], Awaitable[None]]
) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b])
    await clock.advance(5.0)
    assert a.power is False

    await end(home)

    assert a.calls[-1] == ("restore", b"before")  # not restore_off: it comes back on
    assert "restore_off" not in a.names() and a.power is True
    assert b.calls[-1] == ("restore", b"before")  # as before
    assert home.manager.running() == []


async def test_an_out_light_with_nothing_captured_stays_off_at_off(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a = FakeLight("a", captured=None)
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    await clock.advance(5.0)

    await home.manager.off(HOME_ZONE_ID)

    assert "restore" not in a.names() and "restore_off" not in a.names()
    assert a.power is False and a.calls[-1] == ("power", False)


async def test_preview_only_sends_nothing_power_included(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b], preview_only=True)

    await clock.advance(10.0)  # a's moment passes
    assert a.calls == [] and b.calls == []

    await home.manager.set_preview_only(False)

    assert a.calls == []  # it went out meanwhile: no prepare, no capture, no power
    assert "a" not in home.routes.routes
    assert b.names() == ["capture", "prepare_stream"] and home.routes.routes["b"].streaming


async def test_a_resume_after_the_walk_leaves_out_lights_alone(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b])
    home.clock[0] = START + timedelta(seconds=60)  # the app was down for a minute
    clock.now += 60.0

    home = await home.restart()

    assert a.calls == []  # neither captured, prepared nor switched
    assert "a" not in home.routes.routes
    assert home.routes.routes["b"].streaming
    await clock.advance(60.0)
    assert a.calls == []


async def test_a_resume_mid_walk_switches_off_only_the_lights_still_to_come(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b], out={"a": 5.0, "b": 20.0})
    home.clock[0] = START + timedelta(seconds=10)
    clock.now += 10.0

    home = await home.restart()

    assert a.calls == [] and home.routes.routes["b"].streaming
    await clock.advance(9.9)
    assert _powers(b) == []
    await clock.advance(0.1)  # 20 s into the look
    assert b.calls[-1] == ("power", False) and "b" not in home.routes.routes
    assert a.calls == []


async def test_a_restart_keeps_the_walk(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    await clock.advance(5.0)
    a.calls.clear()

    await home.manager.restart(HOME_ZONE_ID)

    assert a.calls == [] and "a" not in home.routes.routes  # it doesn't switch a back on


@pytest.mark.parametrize("later", [False, True])
async def test_a_take_over_of_another_light_leaves_an_out_light_out(
    make_home: HomeFactory, monkeypatch: pytest.MonkeyPatch, later: bool
) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b])
    await clock.advance(5.0)
    a.calls.clear()

    await home.manager.start("east", look_of(field_layer()))  # takes b: Whole home keeps a
    whole = home.host.runtimes[HOME_ZONE_ID]
    assert [light.device_id for light in whole.lights] == ["a"]
    if later:  # its look would have a out later than now: only the run's mark keeps it out
        monkeypatch.setattr(whole, "out_after", lambda device_id: 50.0)
    await home.manager.restart(HOME_ZONE_ID)

    assert a.calls == [] and "a" not in home.routes.routes
    assert home.routes.routes["b"].streaming
    await home.manager.off(HOME_ZONE_ID)
    assert a.calls == [("restore", b"before")] and a.power is True  # with its power


async def test_an_out_light_the_map_takes_out_of_the_zone_is_put_back_with_its_power(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b])
    await clock.advance(5.0)
    assert a.power is False
    a.calls.clear()

    assert isinstance(home.view, FakeHome)
    home.view.rooms["west"].remove("a")  # a leaves the map, so no zone has it
    await home.manager.home_changed()

    assert a.calls == [("restore", b"before")] and a.power is True  # with its power


async def test_a_zone_the_map_leaves_with_no_lights_puts_back_the_lights_it_switched_off(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a, b = FakeLight("a"), FakeLight("b")
    home = await _started(make_home, clock, lights=[a, b], out={"a": 5.0, "b": 6.0})
    await clock.advance(6.0)
    assert a.power is False and b.power is False
    a.calls.clear()
    b.calls.clear()

    assert isinstance(home.view, FakeHome)
    home.view.rooms.clear()  # nothing is on the map: Whole home has no lights and stops
    await home.manager.home_changed()

    assert HOME_ZONE_ID not in home.host.runtimes
    for light in (a, b):
        assert light.calls == [("restore", b"before")] and light.power is True


async def test_no_light_is_switched_off_mid_transition(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    view = FakeHome(rooms={"west": ["a"], "east": ["b"]})
    home = await make_home(
        [a, FakeLight("b")], [], view=view, monotonic=clock.monotonic, sleep=clock.sleep
    )
    await home.manager.start(HOME_ZONE_ID, look_of(field_layer()))
    ten = Transition(kind="fade", duration_s=10.0)
    await home.manager.start(HOME_ZONE_ID, _out_look(), ten)
    runtime = home.host.runtimes[HOME_ZONE_ID]
    assert runtime.transitioning

    await clock.advance(8.0)  # a's moment passed three seconds ago, the fade is still on
    assert _powers(a) == [] and home.routes.routes["a"].streaming

    runtime.tick(1000.0)  # the fade runs from this frame's time
    runtime.tick(1000.0 + runtime.horizon_s + 10.0)  # and has ended at this one
    assert not runtime.transitioning
    await clock.advance(LIGHTS_OUT_RETRY_S)

    assert a.calls[-1] == ("power", False) and "a" not in home.routes.routes


async def test_a_light_offline_at_its_moment_is_left_as_it_comes_back(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    await clock.advance(4.0)
    a.connected = False
    await home.manager.on_device_offline("a")
    await clock.advance(2.0)  # its moment passes while it's away
    a.calls.clear()
    assert _powers(a) == []

    a.connected = True
    await home.manager.on_device_online("a")

    assert a.calls == [] and "a" not in home.routes.routes  # not switched off, prepared or on
    await clock.advance(30.0)
    assert a.calls == []


async def test_close_ends_the_lights_out_timer(make_home: HomeFactory) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    await clock.settle()
    assert clock.waiting() == 1  # the timer, asleep until a's moment

    home.manager.close()
    await clock.settle()
    assert clock.waiting() == 0
    await home.manager.restart(HOME_ZONE_ID)  # a sync after close starts no new one
    await clock.advance(30.0)

    assert clock.waiting() == 0 and _powers(a) == [] and home.routes.routes["a"].streaming


async def test_goodnight_switches_the_far_room_off_and_leaves_the_night_room_on(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    near, far = FakeLight("near"), FakeLight("far")
    home = await build_home(
        tmp_path,
        [near, far],
        [],
        plan=tiny_home(),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    try:
        home_map = home.home_map
        assert home_map is not None
        await home_map.set_placement("near", PointShape((1.0, 1.0, 1.0)))  # the west room
        await home_map.set_placement("far", PointShape((6.0, 1.0, 1.0)))  # the east room
        walk_s = 10.0
        walk = Layer(
            id="walk",
            name="Goodnight",
            type="field",
            kind="goodnight",
            settings={"night_room": "west", "walk_s": walk_s},
        )
        await home.manager.start(HOME_ZONE_ID, look_of(walk))

        # The east room is the one room walked off of two, so its switch comes half way
        # through the walk; the light then fades and takes OFF_AFTER_S more.
        moment = walk_s / 2 + FADE_S + OFF_AFTER_S
        await clock.advance(moment - 0.1)  # just before it
        assert _powers(far) == []

        await clock.advance(0.1)  # at it

        assert far.calls[-1] == ("power", False) and "far" not in home.routes.routes
        assert _powers(near) == [] and home.routes.routes["near"].streaming
    finally:
        home.manager.close()
        await home.db.close()


@pytest.mark.parametrize("reads_on", [False, True])
@pytest.mark.parametrize("case", ["offline-at-its-moment", "resumed-after-the-walk"])
async def test_off_puts_back_an_out_light_it_never_switched_off_as_it_reads(
    make_home: HomeFactory, case: str, reads_on: bool
) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    if case == "offline-at-its-moment":
        await clock.advance(4.0)
        a.connected = False
        await home.manager.on_device_offline("a")
        await clock.advance(2.0)  # its moment passes while it's away
        await home.manager.off(HOME_ZONE_ID)  # a is still away: its release waits
        a.calls.clear()
        a.connected = True
        a.power = reads_on  # what it reads as it comes back
        await home.manager.on_device_online("a")
    else:
        home.clock[0] = START + timedelta(seconds=60)
        clock.now += 60.0
        home = await home.restart()
        a.power = reads_on
        await home.manager.off(HOME_ZONE_ID)

    if reads_on:
        assert a.calls[-1] == ("restore", b"before")
    else:  # switched off elsewhere: Off leaves it off
        assert a.calls[-1] == ("restore_off", b"before")
        assert ("power", True) not in a.calls and ("restore", b"before") not in a.calls


async def test_a_light_that_wont_switch_off_stays_on_dark_and_says_so(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    a = FakeLight("a")
    home = await _started(make_home, clock, lights=[a, FakeLight("b")])
    tries: list[bool] = []

    async def refuses(on: bool) -> None:
        tries.append(on)
        raise OSError("no answer")

    a.set_power = refuses  # type: ignore[method-assign]
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        await clock.advance(5.0)
        await clock.advance(3 * LIGHTS_OUT_RETRY_S)  # later wakes, if any
    finally:
        logger.remove(sink)

    [warning] = [r for r in records if "switch off" in r["message"]]
    assert (
        warning["message"].startswith("Couldn't switch off a:")
        and "no answer" in warning["message"]
    )
    assert "a" not in home.routes.routes and a.power is True  # dark, but still on
    assert tries == [False]  # no second attempt
    del a.set_power  # the real one back
    await home.manager.off(HOME_ZONE_ID)
    assert a.calls[-1] == ("restore", b"before")
