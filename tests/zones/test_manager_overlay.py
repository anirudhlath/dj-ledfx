"""Overlays in the zone manager (M6 rulings 10-14): a Home look played over every running
zone for a set time, mixed by screen, then gone. Time is zone_home.FakeClock."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
from conftest import FakeLight
from runtime_fakes import TILE, field_layer, look_of, out_layer
from zone_home import BREATHE_AND_GLOW, GLOW_LAYER, FakeClock, FakeHome, Home, HomeFactory

from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.model import Look
from dj_ledfx.scheduling.route import overlaid, to_device_colors
from dj_ledfx.zones.model import HOME_ZONE_ID, ZoneError
from dj_ledfx.zones.overlay import MAX_OVERLAY_S, OVERLAY_EDGE_S

pytestmark = pytest.mark.usefixtures("_fields")

MID = 1004.0  # mid-overlay on the fake clock, whose overlays begin at 1000


def _home_flat(level: float = 0.4) -> Look:
    return look_of(field_layer(level), id="home-flat", name="Home flat", scope="whole-home")


async def _home(
    make_home: HomeFactory,
    clock: FakeClock,
    *,
    lights: list[FakeLight] | None = None,
    rooms: dict[str, list[str]] | None = None,
    preview_only: bool = False,
    sun: object = None,
) -> Home:
    view = FakeHome(rooms=rooms if rooms is not None else {"west": ["a", "b"], "east": ["c"]})
    return await make_home(
        lights if lights is not None else [FakeLight(x) for x in "abc"],
        [],
        view=view,
        preview_only=preview_only,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        sun=sun,  # type: ignore[arg-type]
    )


def _tick(home: Home, at: float = MID) -> None:
    for runtime in list(home.host.hosted):
        runtime.tick(at)


def _screen(zone: float, top: float, amount: float = 1.0) -> np.ndarray:
    return to_device_colors(
        overlaid(
            np.full((4, 3), zone, dtype=np.float32),
            1.0,
            np.full((4, 3), top, dtype=np.float32),
            amount,
        ),
        4,
    )


def _sent(home: Home, device_id: str, at: float = MID) -> np.ndarray:
    colors = home.routes.routes[device_id].colors_at(at, 4)
    assert colors is not None
    return colors


async def _two_zones(home: Home) -> None:
    await home.manager.start("west", look_of(field_layer(0.5)))
    await home.manager.start("east", look_of(field_layer(0.2), id="other", name="Other"))


async def test_an_overlay_plays_over_every_running_zone_and_they_keep_running(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await _two_zones(home)
    running = [info.zone_id for info in home.manager.running()]
    changes = len(home.changes)

    info = await home.manager.start_overlay(_home_flat(), 8)
    await clock.advance(4.0)
    _tick(home)

    assert [i.zone_id for i in home.manager.running()] == running
    assert home.manager.overlays() == [info]
    assert info.trigger == "api" and info.look_id == "home-flat"
    assert (info.ends_at - info.started_at).total_seconds() == 8.0
    assert len(home.changes) == changes + 1
    for device_id in "ab":
        assert np.array_equal(_sent(home, device_id), _screen(0.5, 0.4))
    assert np.array_equal(_sent(home, "c"), _screen(0.2, 0.4))
    assert np.array_equal(_sent(home, "a", 1000.0), to_device_colors(np.full((4, 3), 0.5), 4))


async def test_only_a_home_look_plays_over_everything(make_home: HomeFactory) -> None:
    home = await _home(make_home, FakeClock())
    await _two_zones(home)

    with pytest.raises(ZoneError, match="Only a Home look plays over everything"):
        await home.manager.start_overlay(look_of(field_layer()), 8)

    assert home.manager.overlays() == []


@pytest.mark.parametrize("duration", [0.0, -1.0, math.inf, math.nan, MAX_OVERLAY_S + 1])
async def test_an_overlays_duration_is_more_than_nothing_and_at_most_an_hour(
    make_home: HomeFactory, duration: float
) -> None:
    home = await _home(make_home, FakeClock())

    with pytest.raises(ZoneError):
        await home.manager.start_overlay(_home_flat(), duration)

    assert home.manager.overlays() == [] and home.host.hosted == []


async def test_an_overlay_may_last_exactly_an_hour(make_home: HomeFactory) -> None:
    home = await _home(make_home, FakeClock())

    info = await home.manager.start_overlay(_home_flat(), MAX_OVERLAY_S)

    assert (info.ends_at - info.started_at).total_seconds() == MAX_OVERLAY_S


async def test_an_overlay_needs_lights_and_its_inputs(make_home: HomeFactory) -> None:
    clock = FakeClock()
    needs_sun = replace(_home_flat(), needs=("sun",))
    home = await _home(make_home, clock, sun=lambda: None)
    with pytest.raises(ZoneError, match="waits for"):
        await home.manager.start_overlay(needs_sun, 8)
    assert home.manager.overlays() == [] and home.host.hosted == []

    empty = await _home(make_home, FakeClock(), lights=[], rooms={})
    with pytest.raises(ZoneError, match="has no lights"):
        await empty.manager.start_overlay(_home_flat(), 8)


async def test_a_newer_overlay_replaces_the_one_playing(make_home: HomeFactory) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await _two_zones(home)
    first = await home.manager.start_overlay(_home_flat(), 8)
    first_runtime = home.host.hosted[-1]

    second = await home.manager.start_overlay(
        replace(_home_flat(0.6), id="second", name="Second"), 20
    )
    await clock.advance(10.0)  # the first one's end has come and gone

    assert first_runtime not in home.host.hosted
    assert home.manager.overlays() == [second] and second != first
    assert home.host.hosted.count(home.host.hosted[-1]) == 1
    assert len([r for r in home.host.hosted if r.look.id == "second"]) == 1


async def test_an_overlay_ends_by_itself_and_says_so(make_home: HomeFactory) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await _two_zones(home)
    await home.manager.start_overlay(_home_flat(), 8)
    runtime = home.host.hosted[-1]
    lead = runtime.horizon_s  # the span, and so its end, begins one lead after the request
    assert 0 < lead < 0.1
    changes = len(home.changes)

    await clock.advance(7.9 + lead)
    assert home.manager.overlays() != []
    await clock.advance(0.1)
    _tick(home, 1008.0 + lead)

    assert home.manager.overlays() == [] and runtime not in home.host.hosted
    assert len(home.changes) == changes + 1
    assert np.array_equal(
        _sent(home, "a", 1008.0 + lead), to_device_colors(np.full((4, 3), 0.5), 4)
    )
    assert clock.waiting() == 0


async def test_stop_all_ends_the_overlay_even_with_nothing_running(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await home.manager.start_overlay(_home_flat(), 8)
    changes = len(home.changes)

    await home.manager.stop_all()

    assert home.manager.overlays() == [] and home.host.hosted == []
    assert len(home.changes) == changes + 1
    assert clock.waiting() == 0


async def test_stop_overlay_is_idempotent(make_home: HomeFactory) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await home.manager.stop_overlay()  # none playing
    assert home.changes == []
    await home.manager.start_overlay(_home_flat(), 8)
    changes = len(home.changes)

    await home.manager.stop_overlay()
    await home.manager.stop_overlay()

    assert home.manager.overlays() == [] and home.host.hosted == []
    assert len(home.changes) == changes + 1
    await clock.advance(10.0)
    assert len(home.changes) == changes + 1  # the cancelled end says nothing more


async def test_a_zone_started_under_an_overlay_is_overlaid_from_its_first_send(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await home.manager.start_overlay(_home_flat(), 8)

    await home.manager.start("west", look_of(field_layer(0.5)))
    await clock.advance(4.0)
    _tick(home)

    assert home.routes.routes["a"].over is home.manager.overlay_slot
    assert np.array_equal(_sent(home, "a"), _screen(0.5, 0.4))


async def test_an_overlay_reaches_no_idle_light_and_no_light_running_its_own_effect(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    lights = [FakeLight("a"), FakeLight("b"), FakeLight("c", caps=TILE)]
    home = await _home(make_home, clock, lights=lights, rooms={"west": ["a", "b"], "east": ["c"]})
    await home.manager.start("west", look_of(field_layer(0.5)))
    await home.manager.start("east", BREATHE_AND_GLOW)
    await home.manager.start_overlay(_home_flat(), 8)
    await home.manager.off("west")

    assert set(home.routes.routes) == {"c"}  # a and b are idle: no route to mix into
    assert home.routes.routes["c"].streaming is False  # runs Glow itself: never sent a frame

    preview = await _home(
        make_home, FakeClock(), preview_only=True, rooms={"west": ["a", "b"], "east": ["c"]}
    )
    await preview.manager.start("west", look_of(field_layer(0.5)))
    await preview.manager.start_overlay(_home_flat(), 8)
    assert preview.routes.routes and not any(r.streaming for r in preview.routes.routes.values())


async def test_the_overlay_follows_the_whole_homes_lights_when_the_map_changes(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    lights = [FakeLight("a", caps=TILE), FakeLight("b", caps=TILE)]
    home = await _home(make_home, clock, lights=lights, rooms={"west": ["a"]})
    assert isinstance(home.view, FakeHome)
    glow_home = Look(
        id="glow-home",
        name="Glow home",
        category="firmware",
        layers=(GLOW_LAYER,),
        scope="whole-home",
    )
    await home.manager.start_overlay(glow_home, 8)
    runtime = home.host.hosted[-1]
    assert [light.device_id for light in runtime.lights] == ["a"]

    home.view.rooms["west"].append("b")
    await home.manager.home_changed()

    assert [light.device_id for light in runtime.lights] == ["a", "b"]
    assert runtime.streams("b") and runtime.claim_for("b") is None  # emulated: claimed by nothing
    runtime.tick(MID)
    a, b = runtime.route_for("a"), runtime.route_for("b")
    assert a is not None and b is not None
    got_a, got_b = a.colors_at(MID, 4), b.colors_at(MID, 4)
    assert got_a is not None and got_b is not None and got_a.any()  # the layer's copy, lit
    assert np.array_equal(got_a, got_b)


async def test_close_ends_the_overlays_timer(make_home: HomeFactory) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await home.manager.start_overlay(_home_flat(), 8)
    await clock.settle()
    assert clock.waiting() == 1

    home.manager.close()
    await clock.settle()

    assert clock.waiting() == 0
    await clock.advance(10.0)
    assert len(home.manager.overlays()) == 1  # nothing ended it: close leaves the run alone


async def test_an_overlay_never_reaches_a_light_its_look_switched_off(
    make_home: HomeFactory,
) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    await home.manager.start("west", look_of(out_layer({"a": 5.0})))
    await home.manager.start("east", look_of(field_layer(0.2), id="other", name="Other"))
    await clock.advance(5.0)
    await home.manager.start_overlay(_home_flat(), 8)  # from 1005 to 1013
    await clock.advance(1.0)
    _tick(home, 1006.0)

    assert "a" not in home.routes.routes
    assert home.manager.overlay_slot.over_at("a", 1006.0, 4) is None
    assert home.manager.overlay_slot.over_at("b", 1006.0, 4) is not None
    assert np.array_equal(_sent(home, "b", 1006.0), _screen(0.0, 0.4))
    assert np.array_equal(_sent(home, "c", 1006.0), _screen(0.2, 0.4))
    assert HOME_ZONE_ID not in {i.zone_id for i in home.manager.running()}


async def test_an_overlay_ends_when_whole_home_loses_every_light(make_home: HomeFactory) -> None:
    clock = FakeClock()
    home = await _home(make_home, clock)
    assert isinstance(home.view, FakeHome)
    await home.manager.start_overlay(_home_flat(), 8)
    runtime = home.host.hosted[-1]
    changes = len(home.changes)

    home.view.rooms.clear()
    await home.manager.home_changed()

    assert home.manager.overlays() == [] and runtime not in home.host.hosted
    assert len(home.changes) == changes + 1
    assert home.manager.overlay_slot.over_at("a", MID, 4) is None
    assert clock.waiting() == 0


async def test_an_overlay_eases_in_on_a_slow_light_too(make_home: HomeFactory) -> None:
    """The span begins one lead after the request, so a light 0.4 s ahead of the wall clock
    sends its first overlaid frame at amount ~0, as a fast one does, not at full."""
    clock = FakeClock()
    home = await _home(make_home, clock)
    await _two_zones(home)
    slow = home.devices.get_by_stable_id("a")
    assert slow is not None
    slow.tracker = LatencyTracker(strategy=StaticLatency(400.0))

    await home.manager.start_overlay(_home_flat(), 8)

    run = home.manager.overlay_slot.run
    assert run is not None and run.runtime.horizon_s > 0.4
    asked = 1000.0  # the request, on the fake clock
    assert run.started_t == pytest.approx(asked + run.runtime.horizon_s)
    first = asked + 0.4  # the slow light's first send reads a moment 0.4 s ahead
    # Before the span begins the amount is 0, so the first send carries no overlay at all.
    assert home.manager.overlay_slot.over_at("a", first, 4) is None
    # Half an edge into the span, at that light's moment, it is part way in.
    _tick(home, run.started_t + OVERLAY_EDGE_S / 2 - run.runtime.horizon_s)  # a frame for it
    half = home.manager.overlay_slot.over_at("a", run.started_t + OVERLAY_EDGE_S / 2, 4)
    assert half is not None and 0.0 < half[1] < 1.0
