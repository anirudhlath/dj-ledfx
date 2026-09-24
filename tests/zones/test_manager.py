from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import FakeLight
from zone_home import GLOW, TILE, HomeFactory

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.looks.model import Look, LookError
from dj_ledfx.zones.model import (
    TakeOver,
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
)

LAMP = DeviceCapabilities(protocol="Govee")


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


async def test_start_captures_switches_on_and_streams(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", power=False)
    bulb = FakeLight("bulb")
    home = await make_home([lamp, bulb], [_zone("desk", "lamp", "bulb")])

    result = await home.manager.start("desk", home.look("classic-breathe"))

    assert lamp.names() == ["capture", "power", "prepare_stream"]
    assert bulb.names() == ["capture", "prepare_stream"]
    assert result.take_overs == ()
    info = result.running
    assert (info.zone_id, info.look_id, info.look_name) == ("desk", "classic-breathe", "Breathe")
    assert (info.lights, info.brightness, info.state) == (("lamp", "bulb"), 1.0, "running")
    runtime = home.host.runtimes["desk"]
    assert home.routes.routes["lamp"].ring is runtime.ring
    assert home.routes.routes["bulb"].streaming
    [saved] = await home.store.load_assignments()
    assert (saved.zone_id, saved.look_id, saved.lights) == (
        "desk",
        "classic-breathe",
        ("lamp", "bulb"),
    )
    assert await home.db.load_device_state("lamp") == b"before"
    assert len(home.changes) == 1


async def test_a_light_that_cannot_report_its_power_is_switched_on(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", caps=LAMP, power=None)
    home = await make_home([lamp], [_zone("z", "lamp")])

    await home.manager.start("z", home.look("classic-breathe"))

    assert lamp.names() == ["capture", "power", "prepare_stream"]


# Review focus 1: overlapping zones started one after the other.
async def test_takeover_keeps_first_capture_and_off_restores_it(make_home: HomeFactory) -> None:
    a = FakeLight("a", captured=b"a-before")
    b = FakeLight("b", captured=b"b-before")
    c = FakeLight("c", captured=b"c-before")
    home = await make_home([a, b, c], [_zone("left", "a", "b"), _zone("right", "b", "c")])
    await home.manager.start("left", home.look("classic-breathe"))
    b.captured = b"b-showing-breathe"  # what capturing b again would get now

    result = await home.manager.start("right", home.look("classic-strobe"))

    assert result.take_overs == (TakeOver("left", "Left", "Breathe", ("b",), stopped=False),)
    left = home.manager.running_info("left")
    assert left is not None and left.lights == ("a",)
    assert home.host.runtimes["left"].leds.count == a.led_count
    assert home.routes.routes["a"].zone_id == "left"
    assert home.routes.routes["b"].zone_id == "right"
    assert b.names().count("capture") == 1
    saved = {x.zone_id: x.lights for x in await home.store.load_assignments()}
    assert saved == {"left": ("a",), "right": ("b", "c")}

    await home.manager.off("right")

    assert ("restore", b"b-before") in b.calls
    assert ("restore", b"c-before") in c.calls
    assert "restore" not in a.names()
    assert set(home.routes.routes) == {"a"}
    assert [x.zone_id for x in await home.store.load_assignments()] == ["left"]

    await home.manager.off("left")
    assert ("restore", b"a-before") in a.calls
    assert await home.db.load_all_device_states() == {}


async def test_a_zone_left_with_no_lights_stops(make_home: HomeFactory) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    everything = ZoneRecord(id="all", name="Everything", all_lights=True)
    home = await make_home([a, b], [_zone("desk", "a"), everything])
    await home.manager.start("desk", home.look("classic-breathe"))

    result = await home.manager.start("all", home.look("classic-strobe"))

    assert result.take_overs == (TakeOver("desk", "Desk", "Breathe", ("a",), stopped=True),)
    assert result.running.lights == ("a", "b")
    assert home.manager.running_info("desk") is None
    assert set(home.host.runtimes) == {"all"}
    assert [x.zone_id for x in await home.store.load_assignments()] == ["all"]
    assert "restore" not in a.names()  # it went straight to the newer zone


async def test_firmware_runs_on_the_lights_that_support_it(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    lamp = FakeLight("lamp", caps=LAMP)
    home = await make_home([tile, lamp], [_zone("z", "tile", "lamp")])

    await home.manager.start("z", GLOW)

    assert tile.calls == [("capture", None), ("firmware", {"level": 0.5, "brightness": 1.0})]
    assert not home.routes.routes["tile"].streaming
    assert lamp.names() == ["capture", "prepare_stream"]
    assert home.routes.routes["lamp"].streaming
    assert home.manager.light_mode("tile") == "own-effect"
    assert home.manager.light_mode("lamp") == "streamed-copy"
    assert home.manager.effect_name("lamp") == "Glow"
    assert home.manager.light_mode("nobody") is None


async def test_a_rejected_firmware_effect_streams_its_copy(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    tile.reject_firmware = True
    home = await make_home([tile], [_zone("z", "tile")])

    await home.manager.start("z", GLOW)

    assert tile.names() == ["capture", "prepare_stream"]
    assert home.routes.routes["tile"].streaming
    assert home.manager.light_mode("tile") == "streamed-copy"


# B4: no answer isn't a refusal; the light monitor's next poll tries again.
async def test_a_firmware_effect_that_got_no_answer_is_tried_again_at_the_next_poll(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    tile.silent_firmware = True
    home = await make_home([tile], [_zone("z", "tile")])

    await home.manager.start("z", GLOW)

    assert home.manager.light_mode("tile") == "own-effect"  # not a streamed copy
    assert tile.names() == ["capture"]
    assert not home.routes.routes["tile"].streaming

    tile.silent_firmware = False
    await home.manager.verify_firmware("tile")  # the next poll

    assert tile.names() == ["capture", "firmware"]
    assert home.manager.light_mode("tile") == "own-effect"


async def test_off_leaves_an_uncapturable_light_alone(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", captured=None)
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    assert await home.db.load_device_state("lamp") == b""  # control taken, nothing captured

    await home.manager.off("z")

    assert "restore" not in lamp.names()
    assert await home.db.load_device_state("lamp") is None


async def test_a_look_switches_on_a_light_switched_off_while_it_was_idle(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", captured=None)  # can't be captured, so Off leaves it as it is
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.off("z")
    lamp.power = False  # switched off elsewhere while it was idle

    await home.manager.start("z", home.look("classic-breathe"))

    assert lamp.names()[-2:] == ["power", "prepare_stream"]
    assert lamp.power is True
    assert home.routes.routes["lamp"].zone_id == "z"


# B1: Off restores a light switched off meanwhile, and leaves it off.
async def test_off_restores_a_light_switched_off_during_the_look_and_leaves_it_off(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    lamp.power = False
    await home.manager.on_power_reading("lamp", False)  # the light monitor saw it

    await home.manager.off("z")

    assert lamp.calls[-1] == ("restore_off", b"l0")  # colour and effect back, still off
    assert await home.db.load_device_state("lamp") is None


# B3: _power can be up to 5 s old; Off reads the light afresh.
async def test_a_light_switched_off_just_before_off_is_never_switched_on(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    lamp.power = False  # switched off at the wall a moment ago: no poll since

    await home.manager.off("z")

    assert lamp.calls[-1] == ("restore_off", b"l0")


# B20: a light no zone owns forgets its last power reading.
async def test_a_released_light_forgets_its_power(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", captured=None)  # Off leaves it as it is
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    assert home.manager.power_of("lamp") is True

    await home.manager.off("z")

    assert home.manager.power_of("lamp") is None


class _Watched(FakeLight):
    """Notes which captures state.db holds each time it's switched on."""

    def __init__(self, stable_id: str, db_path: Path, seen: list[set[str]]) -> None:
        super().__init__(stable_id, power=False)
        self._db_path = db_path
        self._seen = seen

    async def set_power(self, on: bool) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute("SELECT stable_id FROM device_saved_state").fetchall()
        self._seen.append({row[0] for row in rows})
        await super().set_power(on)


# E9: the captures are saved together before any light is changed.
async def test_captures_are_saved_together_before_any_light_changes(
    make_home: HomeFactory, tmp_path: Path
) -> None:
    seen: list[set[str]] = []
    lights = [_Watched(x, tmp_path / "state.db", seen) for x in ("a", "b", "c")]
    home = await make_home(lights, [_zone("z", "a", "b", "c")])

    await home.manager.start("z", home.look("classic-breathe"))

    assert seen == [{"a", "b", "c"}] * 3


async def test_off_is_idempotent_and_unknown_zones_raise(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.off("z")
    assert lamp.calls == []

    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.off("z")
    await home.manager.off("z")

    assert lamp.names().count("restore") == 1
    with pytest.raises(ZoneNotFoundError):
        await home.manager.off("nope")
    with pytest.raises(ZoneNotFoundError):
        await home.manager.start("nope", home.look("classic-breathe"))


async def test_brightness_is_saved_and_resends_firmware(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)

    info = await home.manager.set_brightness("z", 0.4)

    assert info.brightness == 0.4
    assert tile.calls[-1] == ("firmware", {"level": 0.5, "brightness": 0.4})
    assert home.host.runtimes["z"].brightness == 0.4
    [saved] = await home.store.load_assignments()
    assert saved.brightness == 0.4
    with pytest.raises(ZoneError, match="between 0 and 1"):
        await home.manager.set_brightness("z", 1.5)
    await home.manager.off("z")
    with pytest.raises(ZoneNotRunningError):
        await home.manager.set_brightness("z", 0.5)


async def test_stop_all_restores_every_light(make_home: HomeFactory) -> None:
    a, b = FakeLight("a", captured=b"a0"), FakeLight("b", captured=b"b0")
    home = await make_home([a, b], [_zone("one", "a"), _zone("two", "b")])
    await home.manager.start("one", home.look("classic-breathe"))
    await home.manager.start("two", home.look("classic-strobe"))

    await home.manager.stop_all()

    assert ("restore", b"a0") in a.calls and ("restore", b"b0") in b.calls
    assert home.manager.running() == []
    assert home.host.runtimes == {} and home.routes.routes == {}
    assert await home.store.load_assignments() == []


async def test_restart_gives_a_rejected_firmware_effect_another_try(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    tile.reject_firmware = True
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    tile.reject_firmware = False

    info = await home.manager.restart("z")

    assert tile.names()[-1] == "firmware"
    assert home.manager.light_mode("tile") == "own-effect"
    assert not home.routes.routes["tile"].streaming
    assert info.state == "running"


async def test_starting_a_running_zone_again_replaces_its_look(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.set_brightness("z", 0.3)

    result = await home.manager.start("z", home.look("classic-strobe"))

    assert (result.running.look_id, result.running.brightness) == ("classic-strobe", 0.3)
    assert lamp.names().count("capture") == 1 and "restore" not in lamp.names()
    assert list(home.host.runtimes) == ["z"]
    assert home.routes.routes["lamp"].ring is home.host.runtimes["z"].ring


async def test_a_look_starts_its_firmware_even_when_layer_ids_repeat(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    brighter = Look(
        id="glow-2",
        name="Brighter glow",
        category="firmware",
        layers=(replace(GLOW.layers[0], settings={"level": 0.9}),),  # same layer id
    )

    await home.manager.start("z", brighter)

    assert tile.names().count("firmware") == 2  # a new look always sends its effect
    assert tile.calls[-1] == ("firmware", {"level": 0.9, "brightness": 1.0})


async def test_a_zone_with_no_lights_or_a_look_m1_cannot_run_is_refused(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("empty"), _zone("z", "lamp")])
    with pytest.raises(ZoneError, match="no lights"):
        await home.manager.start("empty", home.look("classic-breathe"))
    home_look = Look(id="x", name="X", category="home", scope="whole-home", layers=GLOW.layers)
    with pytest.raises(LookError, match="M6"):
        await home.manager.start("z", home_look)
    assert lamp.calls == []
