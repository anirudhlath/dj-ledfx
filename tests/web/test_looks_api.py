from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
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
    "shockwave",
    "scanner",
    "checker",
    "speakers",
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
        "max": 8.0,
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


async def test_a_look_with_a_colour_it_cannot_use_is_refused(api: Api) -> None:
    breathe = (await api.client.get("/api/looks/classic-breathe")).json()
    breathe["layers"][0]["settings"] = {"palette": {"value": []}}
    focus = (await api.client.get("/api/looks/focus")).json()
    focus["layers"][0]["settings"]["calm"] = {"value": "red"}

    no_colours = await api.client.post("/api/looks", json={**breathe, "name": "Empty"})
    not_hex = await api.client.post("/api/looks", json={**focus, "name": "Red"})

    assert no_colours.status_code == 400 and "1 to 16 hex colours" in no_colours.json()["detail"]
    assert not_hex.status_code == 400 and "hex colour" in not_hex.json()["detail"]


def _raw(body: dict[str, Any]) -> dict[str, Any]:
    """A body as Python's json writes it, NaN and all, which httpx's json= won't send."""
    return {"content": json.dumps(body), "headers": {"content-type": "application/json"}}


MODIFIERS = {
    "mask": {"kind": "height", "range": [0.0, 1.0]},
    "mirror": {"axis": "x", "at": None},
    "transform": {"offset": [1.0, 0.0, 0.0], "rotateDeg": 90.0, "scale": 2.0},
}


async def test_a_look_with_layer_modifiers_is_saved_and_served(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["name"] = "Low breathe"
    draft["layers"][0].update(MODIFIERS)

    created = await api.client.post("/api/looks", json=draft)

    assert created.status_code == 201
    layer = (await api.client.get(f"/api/looks/{created.json()['id']}")).json()["layers"][0]
    assert {key: layer[key] for key in MODIFIERS} == MODIFIERS


# Review Focus 4: garbage modifiers from a script or an old client are refused with the
# reason, and nothing is saved.
@pytest.mark.parametrize(
    ("change", "status", "says"),
    [
        ({"mask": {"kind": "outdoors"}}, 422, "outdoors"),
        ({"mask": {"kind": "height", "range": [float("nan"), 1.0]}}, 422, "nan"),
        ({"mask": {"kind": "height", "range": [2.0, 1.0]}}, 400, "from low to high"),
        ({"mask": {"kind": "anchor", "anchor": "sofa", "radius": 0.0}}, 422, "greater than 0"),
        ({"mirror": {"axis": "w"}}, 422, "'x', 'y' or 'z'"),
        ({"transform": {"scale": 50.0}}, 422, "less than or equal to 10"),
        ({"transform": {"offset": [1.0, float("inf"), 0.0]}}, 422, "inf"),
        ({"transform": {"offset": [1e39, 0.0, 0.0]}}, 422, "less than or equal to 1000"),
        ({"mirror": {"axis": "x", "at": -1e39}}, 422, "greater than or equal to -1000"),
        ({"mask": {"kind": "height", "range": [0.0, 5000.0]}}, 422, "less than or equal to 1000"),
        (
            {"mask": {"kind": "anchor", "anchor": "sofa", "radius": 5000.0}},
            422,
            "less than or equal to 1000",
        ),
        ({"opacity": 1.5}, 422, "less than or equal to 1"),
    ],
)
async def test_garbage_layer_modifiers_are_refused_with_the_reason(
    api: Api, change: dict[str, Any], status: int, says: str
) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["name"] = "Broken"
    draft["layers"][0].update(change)

    resp = await api.client.post("/api/looks", **_raw(draft))

    assert resp.status_code == status
    assert says in str(resp.json()["detail"])
    listed = [look["id"] for look in (await api.client.get("/api/looks")).json()]
    assert listed == BUILT_INS


async def test_a_firmware_layer_with_a_mask_is_refused(api: Api) -> None:
    firmware = (await api.client.get("/api/looks/firmware")).json()
    firmware["name"] = "Masked"
    firmware["layers"][0]["mask"] = {"kind": "room", "room": "kitchen"}

    resp = await api.client.post("/api/looks", json=firmware)

    assert resp.status_code == 400 and "takes no mask" in resp.json()["detail"]


async def test_a_look_with_look_modifiers_is_saved_and_served(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["name"] = "Evening breathe"
    modifiers = {"trailsS": 0.5, "downbeatFlash": True, "brightnessCap": 0.6, "evening": True}
    draft["modifiers"] = modifiers

    created = await api.client.post("/api/looks", json=draft)

    assert created.status_code == 201
    saved = await api.client.get(f"/api/looks/{created.json()['id']}")
    assert saved.json()["modifiers"] == modifiers


# Review Focus 4: garbage look modifiers are refused with the reason, and nothing is saved.
@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"trailsS": 0.0}, "greater than 0"),
        ({"trailsS": 11.0}, "less than or equal to 10"),
        ({"trailsS": float("nan")}, "nan"),
        ({"brightnessCap": 1.5}, "less than or equal to 1"),
        ({"brightnessCap": -0.1}, "greater than or equal to 0"),
        ({"brightnessCap": float("inf")}, "inf"),
        ({"evening": "tonight"}, "boolean"),
    ],
)
async def test_garbage_look_modifiers_are_refused_with_the_reason(
    api: Api, change: dict[str, Any], says: str
) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["name"] = "Broken"
    draft["modifiers"] = {**draft["modifiers"], **change}

    resp = await api.client.post("/api/looks", **_raw(draft))

    assert resp.status_code == 422
    assert says in str(resp.json()["detail"])
    listed = [look["id"] for look in (await api.client.get("/api/looks")).json()]
    assert listed == BUILT_INS
