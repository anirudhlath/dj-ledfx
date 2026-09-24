from __future__ import annotations

import asyncio
from datetime import timedelta

from conftest import FakeLight
from zone_home import BREATHE_AND_GLOW, GLOW, TILE, Home, HomeFactory

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.events import DeviceOfflineEvent
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.model import LightsChanged, ZoneRecord

LAMP = DeviceCapabilities(protocol="Govee")


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


def _monitor(home: Home, **kwargs: float) -> LightMonitor:
    return LightMonitor(
        devices=home.devices,
        zones=home.manager,
        event_bus=home.bus,
        now=lambda: home.clock[0],
        **kwargs,
    )


def _status(monitor: LightMonitor) -> dict[str, tuple[str, str | None]]:
    return {s.device_id: (s.status, s.own_effect) for s in monitor.states()}


async def test_statuses_follow_zones_power_and_connection(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    lamp = FakeLight("lamp", caps=LAMP)
    bulb = FakeLight("bulb")
    spare = FakeLight("spare", colour=(10, 20, 30))
    gone = FakeLight("gone", connected=False)
    wobbly = FakeLight("wobbly")
    home = await make_home(
        [tile, lamp, bulb, spare, gone, wobbly], [_zone("z", "tile", "lamp", "bulb")]
    )
    monitor = _monitor(home)
    await home.manager.start("z", BREATHE_AND_GLOW)
    managed = home.devices.get_by_stable_id("wobbly")
    assert managed is not None
    managed.status = "reconnecting"
    bulb.power = False

    await monitor.poll_zone_lights()
    await monitor.poll_idle_lights()

    assert _status(monitor) == {
        "tile": ("own-effect", "Glow"),
        "lamp": ("streaming", None),
        "bulb": ("switched-off", None),
        "spare": ("idle", None),
        "gone": ("offline", None),
        "wobbly": ("reconnecting", None),
    }
    idle = monitor.state("spare")
    assert idle is not None and (idle.power, idle.colour) == (True, (10, 20, 30))
    assert spare.calls == []  # idle lights are only read


async def test_a_light_that_cannot_run_the_firmware_look_shows_its_copy(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("lamp", caps=LAMP)], [_zone("z", "lamp")])
    monitor = _monitor(home)

    await home.manager.start("z", GLOW)  # ZonesChanged makes the monitor refresh

    assert _status(monitor) == {"lamp": ("streamed-copy", "Glow")}


async def test_zone_polls_drop_switched_off_lights_and_resend_stopped_effects(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    monitor = _monitor(home)
    await home.manager.start("z", GLOW)

    tile.firmware_running = False  # something else changed the light
    await monitor.poll_zone_lights()
    assert tile.names().count("firmware") == 2

    tile.power = False
    await monitor.poll_zone_lights()
    assert "tile" not in home.routes.routes
    assert _status(monitor) == {"tile": ("switched-off", None)}

    tile.power = True
    await monitor.poll_zone_lights()
    assert _status(monitor) == {"tile": ("own-effect", "Glow")}
    assert "power" not in tile.names()


# B8: a reading older than the last power change is ignored.
async def test_a_reading_taken_before_a_start_switched_the_light_on_is_ignored(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    monitor = _monitor(home)
    await home.manager.start("z", home.look("classic-breathe"))
    lamp.power = False  # switched off elsewhere
    hold = lamp.hold("read_light")
    poll = asyncio.create_task(monitor.poll_zone_lights())
    await hold.entered.wait()  # the poll has read "off"

    await home.manager.start("z", home.look("classic-strobe"))  # this switches it on
    hold.release.set()
    await poll

    assert home.manager.power_of("lamp") is True
    assert home.routes.routes["lamp"].streaming


# B5: no answer, no question about the effect.
async def test_a_light_that_did_not_answer_the_poll_is_not_asked_about_its_effect(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    monitor = _monitor(home)
    await home.manager.start("z", GLOW)
    tile.silent = True

    await monitor.poll_zone_lights()

    assert tile.firmware_checks == 0


# B15: a zone whose saved look can't be read leaves its lights alone: they show idle.
async def test_the_lights_of_a_zone_whose_look_cannot_be_read_show_idle(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.db.write("UPDATE zone_assignments SET look='{not json' WHERE zone_id='z'")
    home = await home.restart()
    monitor = _monitor(home)

    monitor.refresh()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "crashed"
    assert _status(monitor) == {"lamp": ("idle", None)}


async def test_status_since_moves_only_when_the_status_changes(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    monitor = _monitor(home)
    monitor.refresh()
    first = monitor.state("lamp")
    assert first is not None and first.status == "idle"

    home.clock[0] += timedelta(minutes=1)
    monitor.refresh()
    assert monitor.state("lamp") == first

    home.clock[0] += timedelta(minutes=1)
    await home.manager.start("z", home.look("classic-breathe"))
    started = monitor.state("lamp")
    assert started is not None and started.status == "streaming"
    assert started.since == home.clock[0]


async def test_lights_changed_is_emitted_only_on_change(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [_zone("z", "lamp")])
    monitor = _monitor(home)
    events: list[LightsChanged] = []
    home.bus.subscribe(LightsChanged, events.append)

    monitor.refresh()
    monitor.refresh()
    assert len(events) == 1

    await home.manager.start("z", home.look("classic-breathe"))
    assert len(events) == 2


async def test_a_light_that_misses_three_reads_is_reported_offline(
    make_home: HomeFactory,
) -> None:
    bulb = FakeLight("bulb")
    lamp = FakeLight("lamp", caps=LAMP)
    shy = FakeLight("shy", power=None, colour=None)  # answers, but can't say its power
    home = await make_home([bulb, lamp, shy], [])
    monitor = _monitor(home)
    offline: list[DeviceOfflineEvent] = []
    home.bus.subscribe(DeviceOfflineEvent, offline.append)
    bulb.silent = lamp.silent = True  # they no longer answer, whatever their protocol

    for _ in range(2):
        await monitor.poll_idle_lights()
    assert offline == []
    await monitor.poll_idle_lights()

    assert offline == [
        DeviceOfflineEvent(stable_id="bulb", name="bulb"),
        DeviceOfflineEvent(stable_id="lamp", name="lamp"),
    ]


async def test_run_polls_zone_lights_often_and_idle_lights_rarely(
    make_home: HomeFactory,
) -> None:
    a = FakeLight("a")
    spare = FakeLight("spare", colour=(1, 1, 1))
    home = await make_home([a, spare], [_zone("z", "a")])
    await home.manager.start("z", home.look("classic-breathe"))
    monitor = _monitor(home, zone_poll_s=0.01, idle_poll_s=60.0)
    task = asyncio.create_task(monitor.run())
    await asyncio.sleep(0.05)

    a.power = False
    spare.colour = (2, 2, 2)
    await asyncio.sleep(0.05)
    monitor.stop()
    await task

    assert home.manager.power_of("a") is False  # read again within 50 ms
    idle = monitor.state("spare")
    assert idle is not None and idle.colour == (1, 1, 1)  # not read again for 60 s
