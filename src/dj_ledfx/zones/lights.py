"""Light status for the web app, and the polling behind the sharing policy (spec §6.3, §6.4).

Zone lights are read every 5 s: their power goes to the zone manager (a light switched off
elsewhere drops out and rejoins when it's back on) and their firmware effects are checked.
Idle lights are read every 30 s so the web app can show them as they are; they are never
changed. A LIFX light that misses three reads in a row is reported offline: a light cut at
the wall switch is unreachable, and UDP sends never fail.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from loguru import logger

from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.events import DeviceOfflineEvent
from dj_ledfx.zones.model import LightsChanged, ZonesChanged

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
    from dj_ledfx.events import EventBus
    from dj_ledfx.zones.manager import ZoneManager

LightStatus = Literal[
    "streaming", "own-effect", "streamed-copy", "offline", "switched-off", "reconnecting", "idle"
]

ZONE_POLL_S = 5.0
IDLE_POLL_S = 30.0
MISSED_POLLS_OFFLINE = 3
_UNKNOWN = LightReading(power=None, colour=None)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class LightState:
    device_id: str
    status: LightStatus
    since: datetime  # when the light got this status
    own_effect: str | None = None  # the firmware effect it runs, or streams a copy of
    power: bool | None = None  # as last read
    colour: tuple[int, int, int] | None = None  # as last read


class LightMonitor:
    def __init__(
        self,
        *,
        devices: DeviceManager,
        zones: ZoneManager,
        event_bus: EventBus,
        zone_poll_s: float = ZONE_POLL_S,
        idle_poll_s: float = IDLE_POLL_S,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._devices = devices
        self._zones = zones
        self._event_bus = event_bus
        self._zone_poll_s = zone_poll_s
        self._idle_poll_s = idle_poll_s
        self._now = now
        self._states: dict[str, LightState] = {}
        self._readings: dict[str, LightReading] = {}
        self._missed: dict[str, int] = {}
        self._running = False
        event_bus.subscribe(ZonesChanged, lambda _event: self.refresh())

    def states(self) -> list[LightState]:
        return list(self._states.values())

    def state(self, device_id: str) -> LightState | None:
        return self._states.get(device_id)

    def refresh(self) -> None:
        """Work every light's status out again. Emits LightsChanged if anything changed."""
        states: dict[str, LightState] = {}
        for managed in self._devices.devices:
            device_id = managed.adapter.device_info.stable_id
            if not device_id:
                continue
            status, effect = self._status_of(device_id, managed)
            old = self._states.get(device_id)
            reading = self._readings.get(device_id, _UNKNOWN)
            states[device_id] = LightState(
                device_id=device_id,
                status=status,
                since=old.since if old is not None and old.status == status else self._now(),
                own_effect=effect,
                power=reading.power,
                colour=reading.colour,
            )
        changed = states != self._states
        self._states = states
        if changed:
            self._event_bus.emit(LightsChanged())

    async def poll_zone_lights(self) -> None:
        """Read each reachable zone light; its power and firmware go to the zone manager."""
        await asyncio.gather(*(self._poll_zone_light(m) for m in self._reachable(owned=True)))
        self.refresh()

    async def poll_idle_lights(self) -> None:
        """Read each reachable idle light, so the web app shows it as it is."""
        await asyncio.gather(*(self._read(m) for m in self._reachable(owned=False)))
        self.refresh()

    async def run(self) -> None:
        """Poll until stopped: zone lights every 5 s, idle lights every 30 s."""
        self._running = True
        next_idle = 0.0
        while self._running:
            started = time.monotonic()
            try:
                await self.poll_zone_lights()
                if started >= next_idle:
                    next_idle = started + self._idle_poll_s
                    await self.poll_idle_lights()
            except Exception:
                logger.exception("Light poll failed")
            await asyncio.sleep(max(0.0, self._zone_poll_s - (time.monotonic() - started)))

    def stop(self) -> None:
        self._running = False

    def _status_of(self, device_id: str, managed: ManagedDevice) -> tuple[LightStatus, str | None]:
        if managed.status == "reconnecting":
            return "reconnecting", None
        if managed.status == "offline" or not managed.adapter.is_connected:
            return "offline", None
        mode = self._zones.light_mode(device_id)
        if mode is None:
            return "idle", None
        if self._zones.power_of(device_id) is False:
            return "switched-off", None
        return mode, self._zones.effect_name(device_id)

    def _reachable(self, *, owned: bool) -> list[ManagedDevice]:
        return [
            managed
            for managed in self._devices.devices
            if managed.status == "online"
            and managed.adapter.is_connected
            and managed.adapter.device_info.stable_id
            and (self._zones.owner_of(managed.adapter.device_info.stable_id) is not None) == owned
        ]

    async def _poll_zone_light(self, managed: ManagedDevice) -> None:
        reading = await self._read(managed)
        device_id = managed.adapter.device_info.effective_id
        await self._zones.on_power_reading(device_id, reading.power)
        await self._zones.verify_firmware(device_id)

    async def _read(self, managed: ManagedDevice) -> LightReading:
        adapter = managed.adapter
        info = adapter.device_info
        try:
            reading = await adapter.read_light()
        except Exception as exc:
            logger.debug("Couldn't read {}: {}", info.name, exc)
            reading = _UNKNOWN
        if reading.power is None and adapter.capabilities.protocol == "LIFX":
            missed = self._missed.get(info.effective_id, 0) + 1
            self._missed[info.effective_id] = missed
            if missed >= MISSED_POLLS_OFFLINE:
                del self._missed[info.effective_id]
                logger.warning(
                    "{} stopped answering; it's offline until it's found again", info.name
                )
                self._event_bus.emit(
                    DeviceOfflineEvent(stable_id=info.effective_id, name=info.name)
                )
            return reading
        self._missed.pop(info.effective_id, None)
        if reading != _UNKNOWN:
            self._readings[info.effective_id] = reading
        return reading
