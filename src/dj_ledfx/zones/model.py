"""Zones and what runs on them (engine spec §4.3; web spec §12.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

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
