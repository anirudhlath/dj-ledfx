"""WebSocket subscription state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from fastapi import Request

    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.zones.attention import AttentionFeed
    from dj_ledfx.zones.lights import LightMonitor
    from dj_ledfx.zones.manager import ZoneManager


@dataclass
class ClientSubscription:
    """Per-client subscription state."""

    beat_fps: float = 10.0
    frame_fps: float = 0.0  # 0 = not subscribed
    frame_protocol: int = 1  # 2 once the client asks for it (web spec §12.4, ruling 3)
    frame_devices: list[str] = field(default_factory=list)  # v1: device ids; empty = all
    frame_lights: list[str] = field(default_factory=list)  # v2: light ids; empty = all
    frame_streams: list[str] = field(default_factory=lambda: ["live"])  # v1: live only


def get_db(request: Request) -> StateDB:
    return cast("StateDB", _required(request, "state_db", "Saved settings"))


def _required(request: Request, name: str, what: str) -> Any:
    from fastapi import HTTPException

    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(503, f"{what} aren't available")
    return value


def get_looks(request: Request) -> LookStore:
    return cast("LookStore", _required(request, "look_store", "Looks"))


def get_zones(request: Request) -> ZoneManager:
    return cast("ZoneManager", _required(request, "zone_manager", "Zones"))


def get_light_monitor(request: Request) -> LightMonitor:
    return cast("LightMonitor", _required(request, "light_monitor", "Light statuses"))


def get_attention(request: Request) -> AttentionFeed:
    return cast("AttentionFeed", _required(request, "attention_feed", "Attention items"))
