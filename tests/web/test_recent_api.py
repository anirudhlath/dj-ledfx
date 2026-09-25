from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from api_home import api_home
from conftest import FakeLight
from map_home import tiny_home
from zone_home import START

from dj_ledfx.zones.model import ZoneRecord

SHELF = ZoneRecord(id="shelf", name="Shelf", lights=("bulb",))
IN_THE_DESK_CORNER = {"kind": "point", "position": [1.0, 3.5, 1.0]}
BREATHE = {"lookId": "classic-breathe"}


async def test_start_again_lists_what_stopped_and_one_tap_starts_it(tmp_path: Path) -> None:
    lights = [FakeLight("lamp"), FakeLight("bulb")]
    async with api_home(tmp_path, lights, [SHELF], plan=tiny_home()) as api:
        await api.client.put("/api/lights/lamp/placement", json={"shape": IN_THE_DESK_CORNER})
        await api.client.post("/api/zones/desk/start", json=BREATHE)
        api.home.clock[0] = START + timedelta(minutes=5)
        await api.client.post("/api/zones/shelf/start", json=BREATHE)
        api.home.clock[0] = START + timedelta(minutes=9)
        await api.client.post("/api/running/stop-all")
        name = api.home.look("classic-breathe").name

        answer = await api.client.get("/api/running/recent")

        assert answer.status_code == 200
        assert answer.json() == [
            {
                "zoneId": "shelf",
                "zoneName": "Shelf",
                "lookId": "classic-breathe",
                "lookName": name,
                "startedAt": "2026-09-24T19:05:00Z",
                "stoppedAt": "2026-09-24T19:09:00Z",
            },
            {
                "zoneId": "desk",
                "zoneName": "Desk",
                "lookId": "classic-breathe",
                "lookName": name,
                "startedAt": "2026-09-24T19:00:00Z",
                "stoppedAt": "2026-09-24T19:09:00Z",
            },
        ]
        tap = await api.client.post("/api/zones/desk/start", json=BREATHE)  # one tap
        assert tap.status_code == 200
        recent = (await api.client.get("/api/running/recent")).json()
        assert [entry["zoneId"] for entry in recent] == ["shelf"]  # the desk runs it now

        await api.client.delete("/api/home/subzones/desk")
        await api.client.delete("/api/zones/groups/shelf")
        assert (await api.client.get("/api/running/recent")).json() == []


async def test_the_schema_names_start_again_as_f1_types_it(tmp_path: Path) -> None:
    async with api_home(tmp_path, [], []) as api:
        schema = api.app.openapi()

    assert "get" in schema["paths"]["/api/running/recent"]
    properties = schema["components"]["schemas"]["RecentLook"]["properties"]
    assert list(properties) == [
        "zoneId",
        "zoneName",
        "lookId",
        "lookName",
        "startedAt",
        "stoppedAt",
    ]
