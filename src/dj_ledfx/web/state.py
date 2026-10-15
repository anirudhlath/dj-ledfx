"""WebSocket subscription state management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from dj_ledfx.devices.lights import LightIndex
from dj_ledfx.prodjlink.listener import Listening

if TYPE_CHECKING:
    from fastapi import Request

    from dj_ledfx.devices.discovery import DiscoveryOrchestrator
    from dj_ledfx.home.map import HomeMap
    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.tempo.clock import TempoClock
    from dj_ledfx.zones.attention import AttentionFeed
    from dj_ledfx.zones.lights import LightMonitor
    from dj_ledfx.zones.manager import ZoneManager
    from dj_ledfx.zones.preview import PreviewManager


@dataclass
class ClientSubscription:
    """Per-client subscription state."""

    beat_fps: float = 10.0
    frame_fps: float = 0.0  # 0 = not subscribed
    frame_protocol: int = 1  # 2 once the client asks for it (web spec §12.4, ruling 3)
    frame_devices: list[str] = field(default_factory=list)  # v1: device ids; empty = all
    frame_lights: list[str] = field(default_factory=list)  # v2: light ids; empty = all
    frame_streams: list[str] = field(default_factory=lambda: ["live"])  # v1: live only
    fx: bool = False  # subscribe_fx {on}: the fx channel, while it speaks frame protocol 2
    # Bumped by every subscribe_fx {on: true} and every switch to frame protocol 2: each is a
    # subscribe, and the fx poll sends the whole picture again to a session whose epoch moved,
    # however quickly the commands came. `fx_changed` wakes a poll that sleeps while fx is off.
    fx_epoch: int = 0
    fx_changed: asyncio.Event = field(default_factory=asyncio.Event, repr=False, compare=False)

    @property
    def wants_fx(self) -> bool:
        return self.fx and self.frame_protocol == 2

    def set_fx(self, on: bool) -> None:
        self.fx = on
        if on:
            self.fx_epoch += 1
        self.fx_changed.set()

    def set_frame_protocol(self, protocol: int) -> None:
        if protocol == 2 and self.frame_protocol != 2:
            self.fx_epoch += 1
        self.frame_protocol = protocol
        self.fx_changed.set()


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


def light_index(app: Any) -> LightIndex:
    """Which devices make which light: the device manager's."""
    return cast("LightIndex", app.state.device_manager.lights)


def get_home_map(request: Request) -> HomeMap:
    return cast("HomeMap", _required(request, "home_map", "Home map edits"))


def get_previews(request: Request) -> PreviewManager:
    return cast("PreviewManager", _required(request, "previews", "Previews"))


def get_discovery(request: Request) -> DiscoveryOrchestrator:
    return cast("DiscoveryOrchestrator", _required(request, "discovery_orchestrator", "Scans"))


def listening(app: Any) -> Listening:
    """Where Pro DJ Link is heard: nowhere unless main says (--demo, and tests)."""
    return cast("Listening | None", app.state.listening) or Listening()


def get_tempo(app: Any) -> TempoClock:
    """The tempo clock: create_app always has one. It takes the app, so the socket hub reads
    it as the routes do."""
    return cast("TempoClock", app.state.tempo)
