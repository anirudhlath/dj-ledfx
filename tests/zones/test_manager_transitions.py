"""The zone manager plays a start's transition (spec §5.3): from what the lights showed,
with the lights that run firmware effects switching at the midpoint."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from conftest import FakeLight
from zone_home import GLOW, TILE, HomeFactory, zone_record

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.looks.model import Transition
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import TransitionInfo
from dj_ledfx.zones.runtime import ZoneRuntime

FADE = Transition(kind="fade", duration_s=2.0)
LAMP = DeviceCapabilities(protocol="Govee")


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
    await home.manager.switch_due()

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
    await home.manager.switch_due()

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
    await home.manager.switch_due()

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


async def test_the_manager_applies_the_midpoint_by_itself(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)
    task = asyncio.create_task(home.manager.run())
    try:
        _past_midpoint(home.host.runtimes["z"])
        for _ in range(50):
            await asyncio.sleep(0)
            if tile.names()[-1] == "prepare_stream":
                break
        assert tile.names()[-1] == "prepare_stream"
    finally:
        task.cancel()
        await asyncio.wait([task])


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
    saved["transition"] = {"kind": "dissolve", "durationS": 0.0}
    text = json.dumps(saved).replace('"durationS": 0.0', '"durationS": NaN')
    await home.db.write("UPDATE zone_assignments SET look=? WHERE zone_id='z'", (text,))

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "running"
    assert home.host.runtimes["z"].look.transition == Transition(kind="dissolve")
