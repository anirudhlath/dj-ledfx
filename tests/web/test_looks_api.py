from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

BUILT_INS = [
    "sunset",
    "aurora",
    "lava",
    "carousel",
    "ripples",
    "focus",
    "firmware",
    "classic-beat-pulse",
    "classic-breathe",
    "classic-color-chase",
    "classic-fire-storm",
    "classic-rainbow-wave",
    "classic-strobe",
]


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a")], []) as api:
        yield api


async def test_looks_come_built_in_first_in_the_contract_shape(api: Api) -> None:
    resp = await api.client.get("/api/looks")

    assert resp.status_code == 200
    looks = resp.json()
    assert [look["id"] for look in looks] == BUILT_INS
    breathe = looks[BUILT_INS.index("classic-breathe")]
    assert {key: breathe[key] for key in ("name", "category", "builtIn", "derivedFrom")} == {
        "name": "Breathe",
        "category": "tempo",
        "builtIn": True,
        "derivedFrom": None,
    }
    assert (breathe["scope"], breathe["needs"], breathe["uses"]) == ("any-zone", [], ["tempo"])
    assert breathe["starred"] is False
    assert breathe["modifiers"] == {
        "trailsS": None,
        "downbeatFlash": False,
        "brightnessCap": None,
        "evening": False,
    }
    assert breathe["transition"] == {"kind": "cut", "durationS": 0.0}
    [layer] = breathe["layers"]
    assert (layer["id"], layer["type"], layer["kind"], layer["settings"]) == (
        "strip",
        "field",
        "breathe",
        {},
    )
    assert [entry["key"] for entry in layer["schema"]] == [
        "palette",
        "beats_per_cycle",
        "min_brightness",
        "mapping",
        "axis",
        "centre",
    ]
    assert layer["schema"][1] == {
        "key": "beats_per_cycle",
        "label": "Beats per Cycle",
        "unit": None,
        "bindable": False,
        "type": "number",
        "min": 1.0,
        "max": 4.0,
        "step": 0.5,
        "options": None,
    }


async def test_a_look_is_saved_as_new_changed_and_deleted(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["name"] = "Dim breathe"
    draft["derivedFrom"] = "classic-breathe"
    draft["layers"][0]["settings"] = {"min_brightness": {"value": 0.2}}

    created = await api.client.post("/api/looks", json=draft)

    assert created.status_code == 201
    mine = created.json()
    assert mine["id"].startswith("mine-") and mine["builtIn"] is False
    assert (mine["name"], mine["derivedFrom"]) == ("Dim breathe", "classic-breathe")
    assert mine["layers"][0]["settings"] == {"min_brightness": {"value": 0.2, "binding": None}}

    mine["name"] = "Dimmer breathe"
    updated = await api.client.put(f"/api/looks/{mine['id']}", json=mine)
    assert updated.status_code == 200 and updated.json()["name"] == "Dimmer breathe"
    listed = [look["id"] for look in (await api.client.get("/api/looks")).json()]
    assert listed == [*BUILT_INS, mine["id"]]

    assert (await api.client.delete(f"/api/looks/{mine['id']}")).status_code == 204
    assert (await api.client.get(f"/api/looks/{mine['id']}")).status_code == 404


async def test_built_in_looks_are_never_changed(api: Api) -> None:
    breathe = (await api.client.get("/api/looks/classic-breathe")).json()

    resp = await api.client.put("/api/looks/classic-breathe", json=breathe)

    assert resp.status_code == 409
    assert "save your changes as a new look" in resp.json()["detail"]
    assert (await api.client.delete("/api/looks/classic-breathe")).status_code == 409
    assert (await api.client.put("/api/looks/nope", json=breathe)).status_code == 404
    assert (await api.client.delete("/api/looks/nope")).status_code == 404
    assert (await api.client.get("/api/looks/nope")).status_code == 404


async def test_a_look_m1_cannot_run_is_refused_with_the_reason(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["scope"] = "whole-home"

    resp = await api.client.post("/api/looks", json=draft)

    assert resp.status_code == 400 and "M6" in resp.json()["detail"]


async def test_any_look_can_be_starred(api: Api) -> None:
    resp = await api.client.put("/api/looks/classic-strobe/starred", json={"starred": True})

    assert resp.status_code == 200 and resp.json()["starred"] is True
    listed = {look["id"]: look["starred"] for look in (await api.client.get("/api/looks")).json()}
    assert listed["classic-strobe"] is True and listed["classic-breathe"] is False
    resp = await api.client.put("/api/looks/nope/starred", json={"starred": True})
    assert resp.status_code == 404


async def test_the_openapi_schema_uses_the_contract_names(api: Api) -> None:
    schema = (await api.client.get("/openapi.json")).json()["components"]["schemas"]

    names = {"Look", "Layer", "SettingSchema", "SettingValue", "LookModifiers", "Transition"}
    assert names <= set(schema)
    assert {"schema", "settings"} <= set(schema["Layer"]["properties"])
    assert {"builtIn", "derivedFrom", "starred"} <= set(schema["Look"]["properties"])
