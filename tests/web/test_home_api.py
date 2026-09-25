from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight
from map_home import tiny_home

from dj_ledfx.devices.capabilities import DeviceCapabilities

SERVER = "openrgb:localhost:6742"
MOUSE = f"{SERVER}:1"
OPENRGB = DeviceCapabilities(protocol="OpenRGB")
IN_THE_DESK_CORNER = {"kind": "point", "position": [1.0, 3.5, 1.0]}
IN_THE_EAST_ROOM = {"kind": "point", "position": [6.0, 3.0, 1.0]}
IN_THE_NOOK = {"kind": "point", "position": [5.5, 0.5, 1.0]}


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    lights = [
        FakeLight("lamp", captured=b"lamp0"),
        FakeLight("bulb"),
        FakeLight(f"{SERVER}:0", name="Keyboard", led_count=4, caps=OPENRGB),
        FakeLight(MOUSE, name="Mouse", led_count=2, caps=OPENRGB),
    ]
    async with api_home(tmp_path, lights, [], plan=tiny_home()) as api:
        yield api


async def _light(api: Api, light_id: str) -> dict[str, Any]:
    lights = (await api.client.get("/api/lights")).json()
    return next(light for light in lights if light["id"] == light_id)


async def _place(api: Api, light_id: str, shape: dict[str, Any]) -> Any:
    return await api.client.put(f"/api/lights/{light_id}/placement", json={"shape": shape})


async def test_the_map_is_read_and_its_settings_changed(api: Api) -> None:
    home = (await api.client.get("/api/home")).json()
    assert [room["id"] for room in home["rooms"]] == ["west", "east"]
    desk = [[0, 3], [2, 3], [2, 4], [0, 4]]
    assert home["subZones"] == [{"id": "desk", "name": "Desk", "room": "west", "polygon": desk}]
    assert home["anchors"][1]["points"] == [[7.5, 1.0, 1.0], [7.5, 3.0, 1.0]]

    changed = await api.client.put("/api/home", json={"ceiling": 2.7, "northOffsetDeg": 12})
    refused = await api.client.put("/api/home", json={"ceiling": -1})

    assert changed.status_code == 200
    assert (changed.json()["ceiling"], changed.json()["northOffsetDeg"]) == (2.7, 12.0)
    assert refused.status_code == 400 and "greater than 0" in refused.json()["detail"]
    assert (await api.client.get("/api/home")).json()["ceiling"] == 2.7


async def test_anchors_are_added_changed_and_deleted(api: Api) -> None:
    added = await api.client.post(
        "/api/home/anchors", json={"name": "Reading chair", "position": [1.0, 1.0, 0.5]}
    )
    assert added.status_code == 201
    assert added.json() == {
        "id": "reading-chair",
        "name": "Reading chair",
        "position": [1.0, 1.0, 0.5],
        "points": None,
        "confirmed": False,
    }

    confirmed = await api.client.put("/api/home/anchors/reading-chair", json={"confirmed": True})
    assert confirmed.json()["confirmed"] is True
    assert (await api.client.delete("/api/home/anchors/reading-chair")).status_code == 204
    gone = await api.client.delete("/api/home/anchors/reading-chair")
    assert gone.status_code == 404 and gone.json()["detail"] == "No anchor 'reading-chair'"
    short = await api.client.post("/api/home/anchors", json={"name": "Bad", "position": [1, 2]})
    assert short.status_code == 422


async def test_a_sub_zone_with_a_light_in_it_becomes_a_zone(api: Api) -> None:
    nook = [[5.0, 0.0], [6.0, 0.0], [6.0, 1.0], [5.0, 1.0]]
    added = await api.client.post(
        "/api/home/subzones", json={"name": "Reading nook", "room": "east", "polygon": nook}
    )
    assert added.status_code == 201 and added.json()["id"] == "reading-nook"

    placed = await _place(api, "lamp", IN_THE_NOOK)
    zones = (await api.client.get("/api/zones")).json()

    assert placed.status_code == 200
    nook_zone = {"id": "reading-nook", "name": "Reading nook", "kind": "sub-zone"}
    assert {**nook_zone, "lights": ["lamp"]} in zones
    moved = await api.client.put("/api/home/subzones/reading-nook", json={"room": "attic"})
    assert moved.status_code == 400 and "unknown room" in moved.json()["detail"]
    assert (await api.client.delete("/api/home/subzones/reading-nook")).status_code == 204
    zone_ids = {zone["id"] for zone in (await api.client.get("/api/zones")).json()}
    assert "reading-nook" not in zone_ids


async def test_a_light_is_placed_confirmed_and_taken_off_the_map(api: Api) -> None:
    placed = await _place(api, "lamp", IN_THE_DESK_CORNER)
    assert placed.json() == {
        "shape": IN_THE_DESK_CORNER,
        "ledOrder": "",
        "confirmed": False,  # moving a light doesn't confirm it
        "confirmedAt": None,
    }
    lamp = await _light(api, "lamp")
    assert (lamp["room"], lamp["subZone"], lamp["shape"], lamp["confirmed"]) == (
        "west",
        "desk",
        IN_THE_DESK_CORNER,
        False,
    )

    confirmed = await api.client.post("/api/lights/lamp/placement/confirm")
    assert confirmed.json()["confirmed"] is True
    assert confirmed.json()["confirmedAt"] == "2026-09-24T19:00:00Z"

    grid = {"kind": "grid", "center": [1, 1, 1], "width": 1, "depth": 1, "rotation": [0, 90, 0]}
    wrong_order = await api.client.put(
        "/api/lights/lamp/placement", json={"shape": grid, "ledOrder": "along-path"}
    )
    assert wrong_order.status_code == 400 and "rows, columns" in wrong_order.json()["detail"]
    assert (await _place(api, "lamp", {"kind": "star"})).status_code == 422
    nope = await _place(api, "nope", IN_THE_DESK_CORNER)
    assert nope.status_code == 404 and nope.json()["detail"] == "No light 'nope'"

    assert (await api.client.delete("/api/lights/lamp/placement")).status_code == 204
    lamp = await _light(api, "lamp")
    assert (lamp["room"], lamp["shape"], lamp["confirmed"]) == (None, None, False)


async def test_a_pc_part_is_placed_on_its_own(api: Api) -> None:
    await _place(api, SERVER, IN_THE_EAST_ROOM)

    part = await _place(api, MOUSE, IN_THE_DESK_CORNER)

    assert part.status_code == 200
    pc = await _light(api, SERVER)
    assert (pc["room"], pc["shape"]) == ("east", IN_THE_EAST_ROOM)
    assert [p["shape"] for p in pc["parts"]] == [None, IN_THE_DESK_CORNER]  # None: the PC's


async def test_a_guess_places_every_unplaced_light_unconfirmed(api: Api) -> None:
    await _place(api, "lamp", IN_THE_DESK_CORNER)

    guessed = await api.client.post("/api/lights/placement/guess")

    assert guessed.status_code == 200
    assert set(guessed.json()) == {"bulb", SERVER}  # the lamp is placed already
    assert not any(placement["confirmed"] for placement in guessed.json().values())


async def test_moving_a_light_out_of_its_running_room_puts_it_back(api: Api) -> None:
    await _place(api, "lamp", IN_THE_DESK_CORNER)
    started = await api.client.post("/api/zones/west/start", json={"lookId": "classic-breathe"})
    assert started.status_code == 200 and started.json()["lights"] == ["lamp"]

    await _place(api, "lamp", IN_THE_EAST_ROOM)

    assert (await api.client.get("/api/running")).json()["zones"] == []  # nothing left in west
    assert ("restore", b"lamp0") in api.home.lights["lamp"].calls


async def test_the_openapi_schema_names_the_home_types(api: Api) -> None:
    schema = (await api.client.get("/openapi.json")).json()["components"]["schemas"]

    names = {"Home", "Room", "SubZone", "Anchor", "Placement", "PointShape", "GridShape"}
    assert names <= set(schema)
    # F1's hand-written Home and Room (its contract.ts), field for field
    assert set(schema["Room"]["properties"]) == {"id", "name", "polygon", "labelAt", "hasLights"}
    assert set(schema["Home"]["properties"]) == {
        "outline",
        "rooms",
        "subZones",
        "walls",
        "columns",
        "furniture",
        "anchors",
        "ceiling",
        "beams",
        "northOffsetDeg",
        "location",
        "size",
        "wallCutHeight",
        "outdoor",
    }
    assert set(schema["HomeSize"]["properties"]) == {"eastWest", "northSouth"}
    assert {"hasLights"} <= set(schema["Room"]["required"])
    assert {"size"} <= set(schema["Home"]["required"])


async def test_the_map_serves_its_size_and_which_rooms_hold_lights(api: Api) -> None:
    before = (await api.client.get("/api/home")).json()
    assert before["size"] == {"eastWest": 8.0, "northSouth": 4.0}
    assert {room["id"]: room["hasLights"] for room in before["rooms"]} == {
        "west": False,
        "east": False,
    }

    await _place(api, "lamp", IN_THE_DESK_CORNER)
    await _place(api, MOUSE, IN_THE_EAST_ROOM)  # a PC part placed on its own counts
    after = (await api.client.get("/api/home")).json()
    changed = (await api.client.put("/api/home", json={"ceiling": 2.7})).json()

    assert {room["id"]: room["hasLights"] for room in after["rooms"]} == {
        "west": True,
        "east": True,
    }
    assert changed["size"] == {"eastWest": 8.0, "northSouth": 4.0}
    assert [room["hasLights"] for room in changed["rooms"]] == [True, True]
