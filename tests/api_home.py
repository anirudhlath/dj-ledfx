"""The web app over a test home (zone_home.py), served through httpx's ASGI transport so
the app, the stores and the test share one event loop. Import it from tests/web only:
tests/web/conftest.py skips those tests when the web extra isn't installed."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import httpx
from conftest import FakeLight
from fastapi import FastAPI
from zone_home import Home, build_home

from dj_ledfx.config import AppConfig
from dj_ledfx.types import DeviceStats
from dj_ledfx.web.app import create_app
from dj_ledfx.zones.attention import AttentionFeed
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.model import ZoneRecord


@dataclass
class Api:
    home: Home
    app: FastAPI
    client: httpx.AsyncClient
    monitor: LightMonitor
    feed: AttentionFeed
    stats: list[DeviceStats]  # what the scheduler reports; tests append to it


@asynccontextmanager
async def api_home(
    tmp_path: Path, lights: Sequence[FakeLight], zones: Sequence[ZoneRecord]
) -> AsyncIterator[Api]:
    home = await build_home(tmp_path, lights, zones)
    stats: list[DeviceStats] = []
    monitor = LightMonitor(
        devices=home.devices, zones=home.manager, event_bus=home.bus, now=lambda: home.clock[0]
    )
    feed = AttentionFeed(
        zones=home.manager,
        lights=monitor,
        devices=home.devices,
        stats=lambda: stats,
        event_bus=home.bus,
        now=lambda: home.clock[0],
        tz=UTC,
    )
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=home.devices,
        scheduler=MagicMock(get_device_stats=lambda: stats),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=AppConfig(),
        config_path=None,
        state_db=home.db,
        event_bus=home.bus,
        look_store=home.looks,
        zone_manager=home.manager,
        light_monitor=monitor,
        attention_feed=feed,
    )
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Api(home, app, client, monitor, feed, stats)
    finally:
        await home.db.close()
