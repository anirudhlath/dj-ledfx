"""Light status for the web app, and the polling behind the sharing policy (spec §6.3, §6.4).

Zone lights are read every 5 s: their power goes to the zone manager (a light switched off
elsewhere drops out and rejoins when it's back on) and their firmware effects are checked.
Idle lights are read every 30 s so the web app can show them as they are; they are never
changed. A light whose read fails three times in a row is reported offline: a light cut at
the wall switch doesn't answer, and UDP sends never fail. A light that answers but can't
say its power (OpenRGB, or Govee while HA holds its port) isn't missing.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from loguru import logger

from dj_ledfx.devices.capabilities import LightReading, try_read
from dj_ledfx.events import DeviceOfflineEvent
from dj_ledfx.timing import utcnow
from dj_ledfx.zones.model import LightsChanged, ZonesChanged
from dj_ledfx.zones.runtime import LightMode

if TYPE_CHECKING:
    from dj_ledfx.devices.lights import LightIndex
    from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
    from dj_ledfx.events import EventBus
    from dj_ledfx.types import RGB
    from dj_ledfx.zones.manager import ZoneManager

LightStatus = Literal[LightMode, "offline", "switched-off", "reconnecting", "idle"]

ZONE_POLL_S = 5.0
IDLE_POLL_S = 30.0
MISSED_POLLS_OFFLINE = 3

# Most active first (ruling 8): a light of several devices, the PC, shows the first status
# any of its parts has.
STATUS_BY_ACTIVITY: tuple[LightStatus, ...] = (
    "own-effect",
    "streamed-copy",
    "streaming",
    "switched-off",
    "idle",
    "reconnecting",
    "offline",
)
_RANK = {status: rank for rank, status in enumerate(STATUS_BY_ACTIVITY)}


def combine_states(light_id: str, states: Sequence[LightState]) -> LightState | None:
    """A light's state from its devices' states: the most active one's status, since and
    effect; on if any part is on, off only if all are; a colour only for one device."""
    if not states:
        return None
    best = min(states, key=lambda state: _RANK[state.status])
    powers = [state.power for state in states]
    power = True if True in powers else False if all(p is False for p in powers) else None
    colour = states[0].colour if len(states) == 1 else None
    return replace(best, device_id=light_id, power=power, colour=colour)


@dataclass(frozen=True, slots=True)
class LightState:
    device_id: str
    status: LightStatus
    since: datetime  # when the light got this status
    own_effect: str | None = None  # the firmware effect it runs, or streams a copy of
    power: bool | None = None  # as last read
    colour: RGB | None = None  # as last read


class LightMonitor:
    def __init__(
        self,
        *,
        devices: DeviceManager,
        zones: ZoneManager,
        event_bus: EventBus,
        zone_poll_s: float = ZONE_POLL_S,
        idle_poll_s: float = IDLE_POLL_S,
        now: Callable[[], datetime] = utcnow,
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

    def light_states(self, index: LightIndex) -> list[LightState]:
        """Each light's state, in the index's order: the PC's from its parts'."""
        out: list[LightState] = []
        for entry in index.entries:
            parts = [self._states[d] for d in entry.devices if d in self._states]
            state = combine_states(entry.id, parts)
            if state is not None:
                out.append(state)
        return out

    def refresh(self) -> None:
        """Work every light's status out again. Emits LightsChanged if anything changed."""
        states: dict[str, LightState] = {}
        for managed in self._devices.devices:
            device_id = managed.adapter.device_info.stable_id
            if not device_id:
                continue
            status, effect = self._status_of(device_id, managed)
            old = self._states.get(device_id)
            reading = self._readings.get(device_id, LightReading.UNKNOWN)
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
        await self._poll(idle=False)

    async def poll_idle_lights(self) -> None:
        """Read each reachable idle light, so the web app shows it as it is."""
        await self._poll(zones=False, idle=True)

    async def run(self) -> None:
        """Poll until stopped: zone lights every 5 s, idle lights every 30 s."""
        self._running = True
        next_idle = 0.0
        while self._running:
            started = time.monotonic()
            idle = started >= next_idle
            if idle:
                next_idle = started + self._idle_poll_s
            try:
                await self._poll(idle=idle)
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

    async def _poll(self, *, zones: bool = True, idle: bool) -> None:
        """Read the zone lights, the idle lights or both at once, then refresh once."""
        reads: list[Awaitable[object]] = []
        if zones:
            reads += [self._poll_zone_light(d, m) for d, m in self._reachable(owned=True)]
        if idle:
            reads += [self._read(d, m) for d, m in self._reachable(owned=False)]
        await asyncio.gather(*reads)
        self.refresh()

    def _reachable(self, *, owned: bool) -> list[tuple[str, ManagedDevice]]:
        """The online lights, by stable id, that a zone owns (or that none does)."""
        found: list[tuple[str, ManagedDevice]] = []
        for managed in self._devices.devices:
            device_id = managed.adapter.device_info.stable_id
            if (
                device_id
                and managed.status == "online"
                and managed.adapter.is_connected
                and (self._zones.owner_of(device_id) is not None) == owned
            ):
                found.append((device_id, managed))
        return found

    async def _poll_zone_light(self, device_id: str, managed: ManagedDevice) -> None:
        version = self._zones.power_version(device_id)
        reading = await self._read(device_id, managed)
        if reading is None:  # no answer: nothing learned, and no effect worth asking about
            return
        await self._zones.on_power_reading(device_id, reading.power, read_after=version)
        await self._zones.verify_firmware(device_id)

    async def _read(self, device_id: str, managed: ManagedDevice) -> LightReading | None:
        """Read a light. None: it didn't answer; three in a row and it's offline."""
        reading = await try_read(managed.adapter)
        if reading is None:
            missed = self._missed.get(device_id, 0) + 1
            self._missed[device_id] = missed
            if missed >= MISSED_POLLS_OFFLINE:
                del self._missed[device_id]
                name = managed.adapter.device_info.name
                logger.warning("{} stopped answering; it's offline until it's found again", name)
                self._event_bus.emit(DeviceOfflineEvent(stable_id=device_id, name=name))
            return None
        self._missed.pop(device_id, None)
        if reading != LightReading.UNKNOWN:
            self._readings[device_id] = reading
        return reading
