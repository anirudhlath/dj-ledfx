"""The attention list, derived on the server so every screen agrees (spec §8; web §9.5).

M1's items: a zone light offline for 2 minutes, a zone crashed, a zone slow, and a light
dropping more than 5% of its frames for a minute. Input items arrive with the inputs (M3,
M7). Switched off elsewhere is never an item.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from typing import TYPE_CHECKING, Literal

from loguru import logger

from dj_ledfx.timing import utcnow
from dj_ledfx.zones.model import AttentionChanged

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.events import EventBus
    from dj_ledfx.types import DeviceStats
    from dj_ledfx.zones.lights import LightMonitor
    from dj_ledfx.zones.manager import ZoneManager
    from dj_ledfx.zones.model import RunningZoneInfo

Severity = Literal["high", "normal"]
AttentionKind = Literal[
    "light-offline",
    "zone-crashed",
    "zone-slow",
    "input-disconnected",
    "input-stale",
    "frames-dropping",
]
SubjectType = Literal["light", "zone", "input"]
AttentionAction = Literal["restart", "details", "retry", "open"]

OFFLINE_AFTER = timedelta(minutes=2)
DROPPING_AFTER = timedelta(minutes=1)
DROPPING_PCT = 5.0


@dataclass(frozen=True, slots=True)
class AttentionItem:
    severity: Severity
    kind: AttentionKind
    subject_type: SubjectType
    subject_id: str
    title: str
    detail: str
    since: datetime
    actions: tuple[AttentionAction, ...]

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.subject_id}"


class AttentionFeed:
    def __init__(
        self,
        *,
        zones: ZoneManager,
        lights: LightMonitor,
        devices: DeviceManager,
        stats: Callable[[], Sequence[DeviceStats]],
        event_bus: EventBus,
        interval_s: float = 1.0,
        now: Callable[[], datetime] = utcnow,
        tz: tzinfo | None = None,
    ) -> None:
        self._zones = zones
        self._lights = lights
        self._devices = devices
        self._stats = stats
        self._event_bus = event_bus
        self._interval_s = interval_s
        self._now = now
        self._tz = tz
        self._items: list[AttentionItem] = []
        self._dropping_since: dict[str, datetime] = {}
        self._running = False

    def items(self) -> list[AttentionItem]:
        return list(self._items)

    def update(self) -> None:
        """Derive the list again. Emits AttentionChanged when it changed."""
        now = self._now()
        items = [*self._offline_lights(now), *self._zone_items(), *self._dropping(now)]
        items.sort(key=lambda item: (item.severity != "high", -item.since.timestamp()))
        if items != self._items:
            self._items = items
            self._event_bus.emit(AttentionChanged())

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                self.update()
            except Exception:
                logger.exception("Attention update failed")
            await asyncio.sleep(self._interval_s)

    def stop(self) -> None:
        self._running = False

    def _name(self, device_id: str) -> str:
        """A light's name; a PC part's is the PC's and the part's ("PC RAM")."""
        managed = self._devices.get_by_stable_id(device_id)
        if managed is None:
            return device_id
        name = managed.adapter.device_info.name
        light_id = self._devices.lights.light_of(device_id)
        entry = self._devices.lights.get(light_id)
        return f"{entry.name} {name}" if entry is not None and light_id != device_id else name

    def _offline_lights(self, now: datetime) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for state in self._lights.states():
            if state.status != "offline" or now - state.since < OFFLINE_AFTER:
                continue
            if self._zones.owner_of(state.device_id) is None:
                continue
            name = self._name(state.device_id)
            at = state.since.astimezone(self._tz).strftime("%H:%M")
            items.append(
                AttentionItem(
                    severity="normal",
                    kind="light-offline",
                    subject_type="light",
                    subject_id=state.device_id,
                    title=f"{name} offline",
                    detail=f"{name} offline since {at}. It rejoins by itself when it's back.",
                    since=state.since,
                    actions=("details",),
                )
            )
        return items

    def _zone_items(self) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for info in self._zones.running():
            name = self._zones.get_zone(info.zone_id).name
            if info.state == "crashed":
                items.append(self._crashed(info, name))
            elif info.state == "slow" and info.slow_since is not None:
                items.append(
                    AttentionItem(
                        severity="normal",
                        kind="zone-slow",
                        subject_type="zone",
                        subject_id=info.zone_id,
                        title=f"{name} is running slow",
                        detail=(
                            f"{info.look_name} can't keep up with {info.fps_target} fps, "
                            "so it runs at a lower frame rate."
                        ),
                        since=info.slow_since,
                        actions=("details",),
                    )
                )
        return items

    @staticmethod
    def _crashed(info: RunningZoneInfo, name: str) -> AttentionItem:
        lights = f"{name} are" if name.lower().endswith("lights") else f"The {name} lights are"
        error = info.error
        reason = ""
        if error is not None:
            reason = f" {error.layer}: {error.message}" if error.layer else f" {error.message}"
        return AttentionItem(
            severity="high",
            kind="zone-crashed",
            subject_type="zone",
            subject_id=info.zone_id,
            title=f"{info.look_name} crashed",
            detail=f"{lights} holding the last frame.{reason}",
            since=error.at if error is not None else info.since,
            actions=("restart", "details"),
        )

    def _dropping(self, now: datetime) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        dropping: dict[str, datetime] = {}
        for stat in self._stats():
            if not stat.device_id or stat.dropped_pct <= DROPPING_PCT:
                continue
            since = self._dropping_since.get(stat.device_id, now)
            dropping[stat.device_id] = since
            if now - since < DROPPING_AFTER:
                continue
            name = self._name(stat.device_id)
            items.append(
                AttentionItem(
                    severity="normal",
                    kind="frames-dropping",
                    subject_type="light",
                    subject_id=stat.device_id,
                    title=f"{name} is dropping frames",
                    detail=f"{name} has dropped more than 5% of its frames for a minute.",
                    since=since,
                    actions=("details",),
                )
            )
        self._dropping_since = dropping
        return items
