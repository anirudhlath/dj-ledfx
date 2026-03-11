from dataclasses import dataclass

from dj_ledfx.events import EventBus


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
