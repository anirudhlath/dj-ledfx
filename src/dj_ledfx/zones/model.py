"""Zones and what runs on them (engine spec §4.3; web spec §12.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneState

ZoneKind = Literal["home", "room", "sub-zone", "group"]

ALL_LIGHTS_ZONE_ID = "all-lights"
HOME_ZONE_ID = "home"
HOME_ZONE_NAME = "Whole home"  # web spec §6.3's zone picker
# Zones the home map derives (Task 11). state.db mirrors them only so their assignments
# have a row to belong to; the map says which lights they hold.
DERIVED_KINDS: tuple[ZoneKind, ...] = ("home", "room", "sub-zone")


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
    covers: tuple[str, ...] = ()  # the rooms its lights are in, by name, in map order
    slow_since: datetime | None = None  # for the attention feed; not in the contract


@dataclass(frozen=True, slots=True)
class StartResult:
    running: RunningZoneInfo
    take_overs: tuple[TakeOver, ...]


# "Start again" keeps this many looks (ruling 19). The render shows three, and the read leaves
# out gone zones, deleted looks and what runs now, so ten still fills it and stays a short list.
RECENT_LIMIT = 10


@dataclass(frozen=True, slots=True)
class StoppedLook:
    """A look that stopped on a zone, as state.db remembers it for "Start again"."""

    zone_id: str
    look_id: str
    started_at: datetime
    stopped_at: datetime


@dataclass(frozen=True, slots=True)
class RecentLookInfo:
    """A look one tap can start again, as the web app sees it (ruling 19)."""

    zone_id: str
    zone_name: str
    look_id: str
    look_name: str
    started_at: datetime
    stopped_at: datetime


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


@dataclass(frozen=True, slots=True)
class LightsChanged:
    """A light's status, power or colour changed."""


@dataclass(frozen=True, slots=True)
class AttentionChanged:
    """The attention list changed."""
