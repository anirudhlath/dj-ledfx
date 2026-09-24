"""Zones and what runs on them (engine spec §4.3; web spec §12.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneState

ZoneKind = Literal["home", "room", "sub-zone", "group"]

ALL_LIGHTS_ZONE_ID = "all-lights"


@dataclass(frozen=True, slots=True)
class ZoneRecord:
    id: str
    name: str
    kind: ZoneKind = "group"
    lights: tuple[str, ...] = ()  # stable ids, in LED order
    all_lights: bool = False  # follows every known light, in discovery order


@dataclass(frozen=True, slots=True)
class Assignment:
    """What a running zone runs, as saved in state.db (spec §7.1)."""

    zone_id: str
    look_id: str
    look_json: str  # the contract-shaped look as it was started
    brightness: float
    lights: tuple[str, ...]  # the lights the zone owns after take-overs
    started_at: datetime


@dataclass(frozen=True, slots=True)
class CrashInfo:
    """Why a zone's look stopped rendering (spec §8)."""

    layer: str  # the failing layer's name
    message: str
    at: datetime


@dataclass(frozen=True, slots=True)
class TakeOver:
    """A running zone that lost lights to a newer start (spec §4.3)."""

    zone_id: str
    zone_name: str
    look_name: str
    lights: tuple[str, ...]  # the lights it lost
    stopped: bool  # it had none left, so it stopped


@dataclass(frozen=True, slots=True)
class RunningZoneInfo:
    """A running zone as the web app sees it (web spec §12.2 RunningZone)."""

    zone_id: str
    look_id: str
    look_name: str
    since: datetime
    brightness: float
    lights: tuple[str, ...]  # the lights it owns after take-overs
    state: ZoneState
    fps_actual: float | None = None
    fps_target: int | None = None
    error: CrashInfo | None = None
    waiting_for: tuple[str, ...] = ()
    slow_since: datetime | None = None  # for the attention feed; not in the contract


@dataclass(frozen=True, slots=True)
class StartResult:
    running: RunningZoneInfo
    take_overs: tuple[TakeOver, ...]


class ZoneNotFoundError(KeyError):
    """No zone has that id."""


class ZoneError(ValueError):
    """A zone request that can't be carried out, with the reason."""


class ZoneNotRunningError(ZoneError):
    pass


@dataclass(frozen=True, slots=True)
class ZonesChanged:
    """Running zones changed: started, stopped, taken over, brightness or state."""


@dataclass(frozen=True, slots=True)
class PreviewOnlyChanged:
    on: bool
