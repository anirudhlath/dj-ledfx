from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.devices.lights import LightIndex
from dj_ledfx.web.contract import running_zone_out
from dj_ledfx.zones.model import RunningZoneInfo, ZoneRecord

ZONES = [
    ZoneRecord(id="desk", name="Desk", lights=("a", "b")),
    ZoneRecord(id="left", name="Left", lights=("a",)),
    ZoneRecord(id="all", name="All lights", all_lights=True),
]


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a"), FakeLight("b")], ZONES) as api:
        yield api


async def test_zones_list_every_zone_with_its_lights(api: Api) -> None:
    resp = await api.client.get("/api/zones")

    assert resp.status_code == 200
    assert resp.json() == [
        {"id": "desk", "name": "Desk", "kind": "group", "lights": ["a", "b"]},
        {"id": "left", "name": "Left", "kind": "group", "lights": ["a"]},
        {"id": "all", "name": "All lights", "kind": "group", "lights": ["a", "b"]},
    ]


async def test_a_start_answers_the_running_zone_and_its_take_overs(api: Api) -> None:
    first = await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    assert first.status_code == 200
    assert first.json() == {
        "zoneId": "desk",
        "lookId": "classic-breathe",
        "lookName": "Breathe",
        "since": "2026-09-24T19:00:00Z",
        "brightness": 1.0,
        "lights": ["a", "b"],
        "covers": [],
        "state": "running",
        "transition": None,
        "fps": {"actual": 0.0, "target": 60},
        "error": None,
        "waitingFor": None,
        "takeOvers": [],
    }

    second = await api.client.post("/api/zones/left/start", json={"lookId": "classic-strobe"})

    assert second.json()["takeOvers"] == [
        {
            "zoneId": "desk",
            "zoneName": "Desk",
            "lookName": "Breathe",
            "lights": ["a"],
            "stopped": False,
        }
    ]
    running = (await api.client.get("/api/running")).json()
    assert [(zone["zoneId"], zone["lights"]) for zone in running["zones"]] == [
        ("desk", ["b"]),
        ("left", ["a"]),
    ]
    assert running["overlays"] == []


async def test_a_draft_look_runs_without_being_saved(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["id"] = ""
    draft["name"] = "Slow breathe"

    resp = await api.client.post("/api/zones/desk/start", json={"look": draft})

    assert resp.status_code == 200
    assert (resp.json()["lookId"], resp.json()["lookName"]) == ("draft", "Slow breathe")
    saved = [look["id"] for look in (await api.client.get("/api/looks")).json()]
    assert "draft" not in saved


async def test_bad_starts_are_refused_with_the_reason(api: Api) -> None:
    breathe = (await api.client.get("/api/looks/classic-breathe")).json()
    start = "/api/zones/desk/start"

    both = await api.client.post(start, json={"lookId": "classic-breathe", "look": breathe})
    neither = await api.client.post(start, json={})
    no_zone = await api.client.post("/api/zones/nope/start", json={"lookId": "classic-breathe"})
    no_look = await api.client.post(start, json={"lookId": "nope"})
    too_big = await api.client.post(start, json={"look": {**breathe, "scope": "whole-home"}})

    codes = [resp.status_code for resp in (both, neither, no_zone, no_look, too_big)]
    assert codes == [400, 400, 404, 404, 400]
    assert both.json()["detail"] == "Send either lookId or look"
    assert no_zone.json()["detail"] == "No zone 'nope'"
    assert no_look.json()["detail"] == "No look 'nope'"
    assert "M6" in too_big.json()["detail"]


async def test_brightness_restart_off_and_stop_all(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    dim = await api.client.put("/api/zones/desk/brightness", json={"value": 0.5})
    too_bright = await api.client.put("/api/zones/desk/brightness", json={"value": 2})
    restarted = await api.client.post("/api/zones/desk/restart")

    assert (dim.status_code, dim.json()["brightness"]) == (200, 0.5)
    assert too_bright.status_code == 400
    assert (restarted.status_code, restarted.json()["state"]) == (200, "running")

    assert (await api.client.post("/api/zones/desk/off")).status_code == 204
    assert (await api.client.post("/api/zones/desk/off")).status_code == 204  # idempotent
    assert (await api.client.post("/api/zones/nope/off")).status_code == 404
    not_running = await api.client.post("/api/zones/desk/restart")
    assert (not_running.status_code, not_running.json()["detail"]) == (409, "Desk isn't running")

    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    assert (await api.client.post("/api/running/stop-all")).status_code == 204
    assert (await api.client.get("/api/running")).json() == {"zones": [], "overlays": []}
    assert api.home.lights["b"].names()[-1] == "restore"


async def test_groups_are_created_changed_and_deleted(api: Api) -> None:
    created = await api.client.post(
        "/api/zones/groups", json={"name": "Shelf", "lights": ["b", "a"]}
    )

    assert created.status_code == 201
    group = created.json()
    assert group["id"].startswith("group-")
    assert (group["name"], group["kind"], group["lights"]) == ("Shelf", "group", ["b", "a"])

    url = f"/api/zones/groups/{group['id']}"
    renamed = await api.client.put(url, json={"name": "Shelves"})
    unknown = await api.client.put(url, json={"lights": ["zzz"]})

    assert (renamed.status_code, renamed.json()["name"]) == (200, "Shelves")
    assert (unknown.status_code, unknown.json()["detail"]) == (400, "Unknown light 'zzz'")
    assert (await api.client.delete(url)).status_code == 204
    assert (await api.client.delete(url)).status_code == 404
    zone_ids = [zone["id"] for zone in (await api.client.get("/api/zones")).json()]
    assert group["id"] not in zone_ids


async def test_the_openapi_schema_uses_the_contract_names(api: Api) -> None:
    schema = (await api.client.get("/openapi.json")).json()["components"]["schemas"]

    assert {"Zone", "RunningZone", "Running", "Overlay", "TakeOver", "StartRequest"} <= set(schema)
    assert {"zoneId", "lookName", "covers", "waitingFor"} <= set(
        schema["RunningZone"]["properties"]
    )


def test_a_running_zone_says_which_rooms_it_covers() -> None:
    info = RunningZoneInfo(
        zone_id="home",
        look_id="classic-breathe",
        look_name="Breathe",
        since=datetime(2026, 9, 24, 19, 0, tzinfo=UTC),
        brightness=1.0,
        lights=("a",),
        state="running",
        covers=("Kitchen", "Bedroom"),
    )
    assert running_zone_out(info, LightIndex(())).covers == ["Kitchen", "Bedroom"]


async def test_a_start_plays_the_transition_it_asks_for(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    resp = await api.client.post(
        "/api/zones/desk/start",
        json={"lookId": "classic-strobe", "transition": {"kind": "fade", "durationS": 2.0}},
    )

    assert resp.status_code == 200
    assert resp.json()["state"] == "transition"
    expected = {"from": "Breathe", "kind": "fade", "progress": 0.0, "durationS": 2.0}
    assert resp.json()["transition"] == expected
    [zone] = (await api.client.get("/api/running")).json()["zones"]
    assert zone["transition"] == expected


# Review Focus 4 (M6): a draft whose numbers are out of bounds is refused, and nothing starts.
async def test_a_draft_out_of_bounds_is_refused_and_nothing_starts(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["layers"][0]["transform"] = {"offset": [1e39, 0.0, 0.0], "rotateDeg": 0.0, "scale": 1.0}

    resp = await api.client.post("/api/zones/desk/start", json={"look": draft})

    assert resp.status_code == 422 and "less than or equal to 1000" in str(resp.json()["detail"])
    assert (await api.client.get("/api/running")).json()["zones"] == []


# Review Focus 4: a garbage transition is refused with the reason, and nothing starts.
@pytest.mark.parametrize(
    ("transition", "says"),
    [
        ({"kind": "melt", "durationS": 1.0}, "melt"),
        ({"kind": "fade", "durationS": -1.0}, "greater than or equal to 0"),
        ({"kind": "fade", "durationS": 11.0}, "less than or equal to 10"),
        ({"kind": "fade", "durationS": float("nan")}, "nan"),
        ({"kind": "fade", "durationS": float("inf")}, "inf"),
    ],
)
async def test_a_garbage_transition_is_refused_and_nothing_starts(
    api: Api, transition: dict[str, Any], says: str
) -> None:
    body = json.dumps({"lookId": "classic-breathe", "transition": transition})

    resp = await api.client.post(
        "/api/zones/desk/start", content=body, headers={"content-type": "application/json"}
    )

    assert resp.status_code == 422 and says in str(resp.json()["detail"])
    assert (await api.client.get("/api/running")).json()["zones"] == []
