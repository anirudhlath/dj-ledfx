from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from api_home import api_home
from conftest import SERVER, FakeLight, device_stats, pc_lights

from dj_ledfx.web.ws import _lights_message, stats_message
from dj_ledfx.zones.model import ZoneRecord

KEYBOARD, RAM, HUB = f"{SERVER}:0", f"{SERVER}:1", f"{SERVER}:2"
DESK = [ZoneRecord(id="desk", name="Desk", lights=(KEYBOARD, RAM))]


def _lights() -> list[FakeLight]:
    return [
        *pc_lights(("Keyboard", 4), ("RAM", 2), ("Hub", 0)),  # the hub has no LEDs: no part
        FakeLight("lamp"),
    ]


async def test_the_pc_is_one_light_with_parts(tmp_path: Path) -> None:
    async with api_home(tmp_path, _lights(), DESK) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))
        api.stats.extend(
            [
                device_stats(KEYBOARD, send_fps=58.0),
                device_stats(RAM, send_fps=50.0, dropped_pct=2.0),
                device_stats(HUB, send_fps=0.0),
            ]
        )

        pc, lamp = (await api.client.get("/api/lights")).json()

    assert (pc["id"], pc["name"], pc["model"], pc["protocol"], pc["leds"]) == (
        SERVER,
        "PC",
        "OpenRGB",
        "OpenRGB",
        6,
    )
    assert pc["parts"] == [
        {"id": KEYBOARD, "name": "Keyboard", "leds": 4, "shape": None},
        {"id": RAM, "name": "RAM", "leds": 2, "shape": None},
    ]
    assert (pc["status"], pc["sendFps"], pc["droppedPct"]) == ("streaming", 50.0, 2.0)
    assert pc["address"] == f"fake://{KEYBOARD}"
    assert (lamp["id"], lamp["parts"]) == ("lamp", None)


async def test_zones_speak_of_the_pc_and_a_group_of_it_holds_every_part(tmp_path: Path) -> None:
    async with api_home(tmp_path, _lights(), DESK) as api:
        start = await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
        zones = (await api.client.get("/api/zones")).json()
        running = (await api.client.get("/api/running")).json()
        created = await api.client.post(
            "/api/zones/groups", json={"name": "Gaming", "lights": [SERVER, "lamp"]}
        )
        members = api.home.manager.get_zone(created.json()["id"]).lights

    assert start.json()["lights"] == [SERVER]
    assert zones == [{"id": "desk", "name": "Desk", "kind": "group", "lights": [SERVER]}]
    assert running["zones"][0]["lights"] == [SERVER]
    assert created.status_code == 201 and created.json()["lights"] == [SERVER, "lamp"]
    assert members == (KEYBOARD, RAM, HUB, "lamp")


async def test_a_part_offline_is_news_about_the_pc(tmp_path: Path) -> None:
    async with api_home(tmp_path, _lights(), DESK) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))
        api.home.devices.demote_device(RAM)
        api.monitor.refresh()
        api.home.clock[0] += timedelta(minutes=2)
        api.feed.update()
        api.stats.extend([device_stats(KEYBOARD, send_fps=58.0), device_stats(RAM, send_fps=0.0)])

        attention = (await api.client.get("/api/attention")).json()
        channel = _lights_message(api.app)
        stats = stats_message(api.app)

    [item] = attention
    assert (item["id"], item["subject"], item["title"]) == (
        f"light-offline:{RAM}",
        {"type": "light", "id": SERVER},
        "PC RAM offline",
    )
    assert channel is not None
    assert [(light["id"], light["status"]) for light in channel["lights"]] == [
        (SERVER, "streaming"),  # the keyboard still streams
        ("lamp", "idle"),
    ]
    assert stats["lights"] == [
        {"id": SERVER, "send_fps": 58.0, "latency_ms": 20.0, "dropped_pct": 0.0}
    ]
