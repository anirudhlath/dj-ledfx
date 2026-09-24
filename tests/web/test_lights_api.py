from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from api_home import api_home
from conftest import FakeLight
from zone_home import GLOW

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.types import DeviceStats
from dj_ledfx.zones.model import ZoneRecord

TILE = DeviceCapabilities(protocol="LIFX", model="LIFX Tile", matrix=True, firmware_version="3.70")
LAMP = DeviceCapabilities(protocol="Govee", model="H6076")


def _stats(device_id: str, send_fps: float, dropped_pct: float) -> DeviceStats:
    return DeviceStats(
        device_name=device_id,
        effective_latency_ms=20.0,
        send_fps=send_fps,
        frames_dropped=0,
        device_id=device_id,
        dropped_pct=dropped_pct,
    )


async def test_lights_come_with_their_status_and_numbers(tmp_path: Path) -> None:
    tile = FakeLight("tile", name="Tile", led_count=64, caps=TILE)
    lamp = FakeLight("lamp", name="Lamp", caps=LAMP)
    zones = [ZoneRecord(id="desk", name="Desk", lights=("tile",))]
    async with api_home(tmp_path, [tile, lamp], zones) as api:
        await api.home.manager.start("desk", GLOW)
        await api.monitor.poll_idle_lights()
        api.stats.extend([_stats("tile", 0.0, 0.0), _stats("lamp", 39.46, 1.25)])

        resp = await api.client.get("/api/lights")

    assert resp.status_code == 200
    tile_out, lamp_out = resp.json()
    assert {"LIFX Flame", "LIFX Morph", "LIFX waveform", "Glow"} <= set(
        tile_out.pop("builtInEffects")
    )
    assert tile_out == {
        "id": "tile",
        "name": "Tile",
        "room": None,
        "subZone": None,
        "model": "LIFX Tile",
        "protocol": "LIFX",
        "leds": 64,
        "capabilities": ["colour", "matrix", "effects"],
        "parts": None,
        "shape": None,
        "ledOrder": "",
        "confirmed": False,
        "status": "own-effect",
        "statusSince": "2026-09-24T19:00:00Z",
        "ownEffect": "Glow",
        "latency": {"measuredMs": 20.0, "overrideMs": None, "estimated": True},
        "sendFps": 0.0,
        "droppedPct": 0.0,
        "address": "fake://tile",
        "mac": None,
        "firmware": "3.70",
        "power": None,
        "colour": None,
    }
    assert {key: lamp_out[key] for key in ("status", "ownEffect", "power", "colour")} == {
        "status": "idle",
        "ownEffect": None,
        "power": True,
        "colour": "#FFC896",
    }
    assert (lamp_out["capabilities"], lamp_out["builtInEffects"]) == (["colour"], [])
    assert (lamp_out["protocol"], lamp_out["sendFps"], lamp_out["droppedPct"]) == (
        "Govee",
        39.5,
        1.25,
    )


async def test_attention_lists_what_needs_the_owner(tmp_path: Path) -> None:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("rope",))]
    async with api_home(tmp_path, [FakeLight("rope", name="Rope")], zones) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))
        api.home.devices.demote_device("rope")
        api.monitor.refresh()
        api.home.clock[0] += timedelta(minutes=2)
        api.feed.update()

        resp = await api.client.get("/api/attention")

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "id": "light-offline:rope",
            "severity": "normal",
            "kind": "light-offline",
            "subject": {"type": "light", "id": "rope"},
            "title": "Rope offline",
            "detail": "Rope offline since 19:00. It rejoins by itself when it's back.",
            "since": "2026-09-24T19:00:00Z",
            "actions": ["details"],
        }
    ]
