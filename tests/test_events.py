from dataclasses import dataclass

import pytest

from dj_ledfx.events import (
    DeviceDiscoveredEvent,
    DeviceOfflineEvent,
    DeviceOnlineEvent,
    EventBus,
    SceneActivatedEvent,
    SceneDeactivatedEvent,
)


@dataclass
class FakeEvent:
    value: int


@dataclass
class OtherEvent:
    name: str


def test_subscribe_and_emit() -> None:
    bus = EventBus()
    received: list[FakeEvent] = []
    bus.subscribe(FakeEvent, received.append)
    bus.emit(FakeEvent(value=42))
    assert len(received) == 1
    assert received[0].value == 42


def test_multiple_subscribers() -> None:
    bus = EventBus()
    a: list[FakeEvent] = []
    b: list[FakeEvent] = []
    bus.subscribe(FakeEvent, a.append)
    bus.subscribe(FakeEvent, b.append)
    bus.emit(FakeEvent(value=1))
    assert len(a) == 1
    assert len(b) == 1


def test_different_event_types_isolated() -> None:
    bus = EventBus()
    fakes: list[FakeEvent] = []
    others: list[OtherEvent] = []
    bus.subscribe(FakeEvent, fakes.append)
    bus.subscribe(OtherEvent, others.append)
    bus.emit(FakeEvent(value=1))
    assert len(fakes) == 1
    assert len(others) == 0


def test_unsubscribe() -> None:
    bus = EventBus()
    received: list[FakeEvent] = []
    bus.subscribe(FakeEvent, received.append)
    bus.unsubscribe(FakeEvent, received.append)
    bus.emit(FakeEvent(value=1))
    assert len(received) == 0


def test_emit_with_no_subscribers_does_not_raise() -> None:
    bus = EventBus()
    bus.emit(FakeEvent(value=1))  # should not raise


@pytest.fixture
def event_bus():
    return EventBus()


def test_device_discovered_event():
    e = DeviceDiscoveredEvent(stable_id="lifx:aabb", name="LIFX Strip")
    assert e.stable_id == "lifx:aabb"
    assert e.name == "LIFX Strip"


def test_device_online_event():
    e = DeviceOnlineEvent(stable_id="govee:1234", name="Govee H6159")
    assert e.stable_id == "govee:1234"


def test_device_offline_event():
    e = DeviceOfflineEvent(stable_id="lifx:aabb", name="LIFX Strip")
    assert e.stable_id == "lifx:aabb"


def test_scene_activated_event():
    e = SceneActivatedEvent(scene_id="dj-booth")
    assert e.scene_id == "dj-booth"


def test_scene_deactivated_event():
    e = SceneDeactivatedEvent(scene_id="dj-booth")
    assert e.scene_id == "dj-booth"


def test_event_bus_emits_new_event_types(event_bus):
    received = []
    event_bus.subscribe(DeviceDiscoveredEvent, received.append)
    event_bus.emit(DeviceDiscoveredEvent(stable_id="lifx:aa", name="Test"))
    assert len(received) == 1
    assert received[0].stable_id == "lifx:aa"
