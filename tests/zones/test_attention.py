from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, timedelta

import pytest
from conftest import FakeLight
from zone_home import START, Home, HomeFactory

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.types import DeviceStats, FloatRGB
from dj_ledfx.zones.attention import AttentionFeed, AttentionItem
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.model import AttentionChanged, ZoneRecord


class Exploding(FieldEffect, register=False):
    """A field effect whose every frame raises."""

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _exploding() -> None:
    Effect._registry["exploding"] = Exploding  # conftest drops it after each test


SPARKS = Look(
    id="sparks",
    name="Sparks",
    category="ambient",
    layers=(Layer(id="f", name="Spark field", type="field", kind="exploding"),),
)


def _zone(zone_id: str, name: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=name, lights=lights)


def _stats(device_id: str, dropped_pct: float) -> DeviceStats:
    return DeviceStats(
        device_name=device_id,
        effective_latency_ms=20.0,
        send_fps=55.0,
        frames_dropped=0,
        device_id=device_id,
        dropped_pct=dropped_pct,
    )


def _feed(
    home: Home, stats: Callable[[], Sequence[DeviceStats]] = list, interval_s: float = 1.0
) -> tuple[LightMonitor, AttentionFeed]:
    monitor = LightMonitor(
        devices=home.devices, zones=home.manager, event_bus=home.bus, now=lambda: home.clock[0]
    )
    feed = AttentionFeed(
        zones=home.manager,
        lights=monitor,
        devices=home.devices,
        stats=stats,
        event_bus=home.bus,
        interval_s=interval_s,
        now=lambda: home.clock[0],
        tz=UTC,
    )
    return monitor, feed


async def test_an_offline_zone_light_needs_attention_after_two_minutes(
    make_home: HomeFactory,
) -> None:
    rope, spare = FakeLight("rope", name="Rope"), FakeLight("spare", name="Spare")
    home = await make_home([rope, spare], [_zone("z", "Living room", "rope")])
    await home.manager.start("z", home.look("classic-breathe"))
    monitor, feed = _feed(home)
    home.devices.demote_device("rope")
    home.devices.demote_device("spare")  # offline too, but in no running zone
    monitor.refresh()

    home.clock[0] += timedelta(minutes=1, seconds=59)
    feed.update()
    assert feed.items() == []

    home.clock[0] += timedelta(seconds=1)
    feed.update()

    assert feed.items() == [
        AttentionItem(
            id="light-offline:rope",
            severity="normal",
            kind="light-offline",
            subject_type="light",
            subject_id="rope",
            title="Rope offline",
            detail="Rope offline since 19:00. It rejoins by itself when it's back.",
            since=START,
            actions=("details",),
        )
    ]


async def test_crashed_zones_come_first_and_slow_zones_after(make_home: HomeFactory) -> None:
    home = await make_home(
        [FakeLight("a"), FakeLight("b"), FakeLight("c")],
        [
            _zone("desk", "Desk", "a"),
            _zone("porch", "Porch lights", "b"),
            _zone("kitchen", "Kitchen", "c"),
        ],
    )
    _, feed = _feed(home)
    for zone_id in ("desk", "porch"):
        await home.manager.start(zone_id, SPARKS)
    await home.manager.start("kitchen", home.look("classic-breathe"))
    home.clock[0] += timedelta(minutes=1)
    home.host.runtimes["desk"].tick(100.0)  # raises: the zone crashes now
    home.clock[0] += timedelta(minutes=1)
    home.host.runtimes["porch"].tick(100.0)
    home.host.runtimes["kitchen"].slow_since = home.clock[0]
    zone_events = len(home.changes)

    feed.update()
    feed.update()

    assert len(home.changes) == zone_events  # the crashes told the running channel already
    porch, desk, kitchen = feed.items()
    assert (porch.kind, desk.kind, kitchen.kind) == ("zone-crashed", "zone-crashed", "zone-slow")
    assert (desk.severity, desk.title, desk.actions) == (
        "high",
        "Sparks crashed",
        ("restart", "details"),
    )
    assert (
        desk.detail
        == "The Desk lights are holding the last frame. Spark field: RuntimeError: boom"
    )
    assert desk.since == START + timedelta(minutes=1)
    assert porch.detail.startswith("Porch lights are holding the last frame.")
    assert (kitchen.severity, kitchen.title, kitchen.subject_id) == (
        "normal",
        "Kitchen is running slow",
        "kitchen",
    )


# B21: a crash reaches the running channel as it happens, with no attention tick.
async def test_a_crash_reaches_the_running_channel_without_an_attention_tick(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("a")], [_zone("desk", "Desk", "a")])
    await home.manager.start("desk", SPARKS)
    before = len(home.changes)

    home.host.runtimes["desk"].tick(100.0)  # raises: the zone crashes now

    assert len(home.changes) == before + 1
    info = home.manager.running_info("desk")
    assert info is not None and info.state == "crashed"
    home.host.runtimes["desk"].tick(100.1)  # still crashed: nothing new to say
    assert len(home.changes) == before + 1


async def test_a_light_dropping_frames_for_a_minute_needs_attention(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("lamp", name="Lamp")], [])
    stats = [_stats("lamp", 8.0)]
    _, feed = _feed(home, stats=lambda: stats)

    feed.update()
    home.clock[0] += timedelta(seconds=59)
    feed.update()
    assert feed.items() == []

    home.clock[0] += timedelta(seconds=1)
    feed.update()
    [item] = feed.items()
    assert (item.kind, item.title, item.since) == (
        "frames-dropping",
        "Lamp is dropping frames",
        START,
    )

    stats[0] = _stats("lamp", 2.0)
    feed.update()
    assert feed.items() == []


async def test_attention_changed_is_emitted_only_when_the_list_changes(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("lamp")], [])
    stats: list[DeviceStats] = []
    _, feed = _feed(home, stats=lambda: stats)
    events: list[AttentionChanged] = []
    home.bus.subscribe(AttentionChanged, events.append)

    feed.update()
    stats.append(_stats("lamp", 9.0))
    feed.update()  # dropping, but not for a minute yet
    assert events == []

    home.clock[0] += timedelta(minutes=1)
    feed.update()
    feed.update()
    assert len(events) == 1


async def test_run_updates_until_stopped(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [])
    stats = [_stats("lamp", 9.0)]
    _, feed = _feed(home, stats=lambda: stats, interval_s=0.01)
    task = asyncio.create_task(feed.run())
    await asyncio.sleep(0.03)
    home.clock[0] += timedelta(minutes=2)
    await asyncio.sleep(0.03)
    feed.stop()
    await task

    assert [item.kind for item in feed.items()] == ["frames-dropping"]
