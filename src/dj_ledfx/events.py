from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from dj_ledfx.transport import TransportState


@dataclass(frozen=True, slots=True)
class BeatEvent:
    bpm: float  # pitch-adjusted BPM
    beat_position: int  # 1-4
    next_beat_ms: int
    device_number: int
    device_name: str
    timestamp: float  # time.monotonic()
    pitch_percent: float = 0.0


@dataclass(frozen=True, slots=True)
class DeviceDiscoveredEvent:
    stable_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DeviceOnlineEvent:
    stable_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DeviceOfflineEvent:
    stable_id: str
    name: str


@dataclass(frozen=True, slots=True)
class SceneActivatedEvent:
    scene_id: str


@dataclass(frozen=True, slots=True)
class SceneDeactivatedEvent:
    scene_id: str


@dataclass(frozen=True, slots=True)
class TransportStateChangedEvent:
    old_state: TransportState
    new_state: TransportState


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[..., Any]]] = defaultdict(list)

    def subscribe(self, event_type: type, callback: Callable[..., Any]) -> None:
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: type, callback: Callable[..., Any]) -> None:
        try:
            self._subscribers[event_type].remove(callback)
        except ValueError:
            pass

    def emit(self, event: object) -> None:
        for callback in self._subscribers.get(type(event), []):
            try:
                callback(event)
            except Exception:
                logger.exception("Event callback failed for {}", type(event).__name__)
