from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight
from zone_home import FakeHome

from dj_ledfx.looks.builtin import handoff_looks
from dj_ledfx.web.contract import overlay_out
from dj_ledfx.zones.model import OverlayInfo, ZoneRecord
from tests.web.conftest import raw_json

OVERLAY = "/api/running/overlay"
WISP = handoff_looks()["wisp"]


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    view = FakeHome(rooms={"west": ["a", "b"]})
    async with api_home(
        tmp_path,
        [FakeLight("a"), FakeLight("b")],
        [ZoneRecord(id="g", name="G", lights=("a",))],
        view=view,
    ) as api:
        await api.client.post("/api/zones/west/start", json={"lookId": "classic-breathe"})
        yield api


async def test_post_overlay_plays_a_home_look_over_everything(api: Api) -> None:
    started = api.home.clock[0]

    resp = await api.client.post(OVERLAY, json={"lookId": "wisp", "durationS": 8})

    assert resp.status_code == 201
    body = resp.json()
    assert body == {
        "lookId": "wisp",
        "name": WISP["name"],
        "trigger": "api",
        "endsAt": (started + timedelta(seconds=8)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "progress": 0.0,
    }
    running = (await api.client.get("/api/running")).json()
    assert running["overlays"] == [body]
    assert [zone["zoneId"] for zone in running["zones"]] == ["west"]


async def test_an_overlay_takes_a_draft_and_names_its_trigger(api: Api) -> None:
    draft = (await api.client.get("/api/looks/wisp")).json()

    resp = await api.client.post(
        OVERLAY, json={"look": {**draft, "id": ""}, "durationS": 3, "trigger": "test"}
    )

    assert resp.status_code == 201
    assert (resp.json()["lookId"], resp.json()["trigger"]) == ("draft", "test")


async def test_bad_overlays_are_refused_with_the_reason(api: Api) -> None:
    wisp = (await api.client.get("/api/looks/wisp")).json()
    breathe = (await api.client.get("/api/looks/classic-breathe")).json()

    async def post(body: dict[str, object]) -> tuple[int, object]:
        resp = await api.client.post(OVERLAY, json=body)
        return resp.status_code, resp.json().get("detail")

    assert await post({"lookId": "wisp", "look": wisp, "durationS": 5}) == (
        400,
        "Send either lookId or look",
    )
    assert await post({"durationS": 5}) == (400, "Send either lookId or look")
    assert (await post({"lookId": "nope", "durationS": 5}))[0] == 404
    assert await post({"lookId": "classic-breathe", "durationS": 5}) == (
        400,
        "Only a Home look plays over everything",
    )
    assert (await post({"look": breathe, "durationS": 5}))[0] == 400
    for duration in (0, 3601, "eight"):
        assert (await post({"lookId": "wisp", "durationS": duration}))[0] == 422
    nan = await api.client.post(
        OVERLAY, **raw_json(json.dumps({"lookId": "wisp", "durationS": float("nan")}))
    )
    assert nan.status_code == 422
    assert (await post({"lookId": "wisp", "durationS": 5, "trigger": "x" * 201}))[0] == 422
    assert (await post({"lookId": "wisp", "durationS": 5, "trigger": ""}))[0] == 422
    assert (await api.client.get("/api/running")).json()["overlays"] == []


async def test_delete_overlay_ends_it_and_answers_204_either_way(api: Api) -> None:
    await api.client.post(OVERLAY, json={"lookId": "wisp", "durationS": 8})

    first = await api.client.delete(OVERLAY)
    second = await api.client.delete(OVERLAY)

    assert (first.status_code, second.status_code) == (204, 204)
    assert (await api.client.get("/api/running")).json()["overlays"] == []


def test_progress_is_the_share_of_the_overlay_played() -> None:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    info = OverlayInfo("wisp", "Wisp", "api", start, start + timedelta(seconds=10))

    assert overlay_out(info, start + timedelta(seconds=5)).progress == 0.5
    assert overlay_out(info, start - timedelta(seconds=5)).progress == 0.0
    assert overlay_out(info, start + timedelta(seconds=15)).progress == 1.0
    assert overlay_out(info, start).ends_at.utcoffset() == timedelta(0)


async def test_progress_follows_the_managers_clock(api: Api) -> None:
    await api.client.post(OVERLAY, json={"lookId": "wisp", "durationS": 10})
    api.home.clock[0] += timedelta(seconds=4)

    running = (await api.client.get("/api/running")).json()

    assert running["overlays"][0]["progress"] == pytest.approx(0.4)
