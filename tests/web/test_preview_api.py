from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight
from map_home import tiny_home
from zone_home import zone_record

IN_THE_WEST_ROOM = {"kind": "point", "position": [1.0, 1.0, 1.0]}
IN_THE_EAST_ROOM = {"kind": "point", "position": [6.0, 3.0, 1.0]}


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("lamp")], [zone_record("desk", "lamp")]) as api:
        yield api


async def _draft(api: Api, name: str) -> dict[str, Any]:
    """An unsaved look, as the editor sends it."""
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    return {**draft, "id": "", "name": name}


async def test_a_preview_renders_for_the_web_app_only(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    api.home.lights["lamp"].calls.clear()

    started = await api.client.post(
        "/api/preview", json={"zoneId": "desk", "lookId": "classic-strobe"}
    )

    assert started.status_code == 201
    preview_id = started.json()["previewId"]
    [runtime] = api.previews.runtimes()
    assert (runtime.key, runtime.look.id) == (f"preview:{preview_id}", "classic-strobe")
    assert set(api.home.host.runtimes) == {"desk", f"preview:{preview_id}"}
    assert api.home.lights["lamp"].calls == []  # the zone's own look runs on, untouched
    running = (await api.client.get("/api/running")).json()["zones"]
    assert [zone["lookId"] for zone in running] == ["classic-breathe"]


async def test_the_editor_changes_a_draft_preview_then_ends_it(api: Api) -> None:
    started = await api.client.post(
        "/api/preview", json={"zoneId": "desk", "look": await _draft(api, "Slow breathe")}
    )
    preview_id = started.json()["previewId"]
    [runtime] = api.previews.runtimes()
    assert (runtime.look.id, runtime.look.name) == ("draft", "Slow breathe")

    changed = await api.client.put(
        f"/api/preview/{preview_id}", json={"look": await _draft(api, "Slower breathe")}
    )
    assert changed.status_code == 204 and runtime.look.name == "Slower breathe"

    assert (await api.client.delete(f"/api/preview/{preview_id}")).status_code == 204
    assert api.previews.runtimes() == [] and set(api.home.host.runtimes) == set()
    gone = await api.client.delete(f"/api/preview/{preview_id}")
    assert gone.status_code == 404 and gone.json()["detail"] == f"No preview '{preview_id}'"


async def test_a_new_preview_replaces_the_last(api: Api) -> None:
    body = {"zoneId": "desk", "lookId": "classic-strobe"}
    first = (await api.client.post("/api/preview", json=body)).json()["previewId"]

    second = (await api.client.post("/api/preview", json=body)).json()["previewId"]

    assert first != second and len(api.previews.runtimes()) == 1
    stale = await api.client.put(f"/api/preview/{first}", json={"look": await _draft(api, "x")})
    assert stale.status_code == 404


async def test_a_bad_preview_request_says_why(api: Api) -> None:
    both = {"zoneId": "desk", "lookId": "classic-strobe", "look": await _draft(api, "x")}
    home_look = {**await _draft(api, "x"), "scope": "whole-home"}

    answers = [
        await api.client.post("/api/preview", json=both),
        await api.client.post("/api/preview", json={"zoneId": "desk"}),
        await api.client.post("/api/preview", json={"zoneId": "nope", "lookId": "classic-strobe"}),
        await api.client.post("/api/preview", json={"zoneId": "desk", "lookId": "nope"}),
        await api.client.post("/api/preview", json={"zoneId": "desk", "look": home_look}),
    ]

    assert [(a.status_code, a.json()["detail"]) for a in answers] == [
        (400, "Send either lookId or look"),
        (400, "Send either lookId or look"),
        (404, "No zone 'nope'"),
        (404, "No look 'nope'"),
        (400, "Home looks (whole-home scope) arrive in M6"),
    ]
    assert api.previews.runtimes() == []


async def test_a_room_preview_ends_when_its_last_light_leaves_the_room(tmp_path: Path) -> None:
    async with api_home(tmp_path, [FakeLight("lamp")], [], plan=tiny_home()) as api:
        place = "/api/lights/lamp/placement"
        await api.client.put(place, json={"shape": IN_THE_WEST_ROOM})
        started = await api.client.post(
            "/api/preview", json={"zoneId": "west", "lookId": "classic-strobe"}
        )
        preview_id = started.json()["previewId"]

        await api.client.put(place, json={"shape": IN_THE_EAST_ROOM})

        assert api.previews.runtimes() == [] and api.home.host.runtimes == {}
        gone = await api.client.delete(f"/api/preview/{preview_id}")
        assert gone.status_code == 404


async def test_a_preview_change_with_an_empty_palette_is_refused(api: Api) -> None:
    started = await api.client.post(
        "/api/preview", json={"zoneId": "desk", "look": await _draft(api, "Breathe")}
    )
    preview_id = started.json()["previewId"]
    empty = await _draft(api, "Breathe")
    empty["layers"][0]["settings"] = {"palette": {"value": []}}

    changed = await api.client.put(f"/api/preview/{preview_id}", json={"look": empty})

    assert changed.status_code == 400 and "1 to 16 hex colours" in changed.json()["detail"]
    [runtime] = api.previews.runtimes()
    assert runtime.look.name == "Breathe"  # the preview plays on as it was
