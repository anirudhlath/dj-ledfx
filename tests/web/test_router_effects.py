"""The old UI's effect controls, aimed at a zone's classic effect (spec §6.5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.effects.presets import PresetStore
from dj_ledfx.zones.model import ZoneRecord

DESK = {"zone": "desk"}


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("a",))]
    async with api_home(tmp_path, [FakeLight("a")], zones) as api:
        api.app.state.preset_store = PresetStore(state_db=api.home.db)
        yield api


async def test_list_effects(api: Api) -> None:
    resp = await api.client.get("/api/effects")

    assert resp.status_code == 200
    assert "beat_pulse" in resp.json()


async def test_choosing_an_effect_starts_its_classic_look_on_the_zone(api: Api) -> None:
    resp = await api.client.get("/api/effects/active", params=DESK)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Desk isn't playing a classic effect"

    resp = await api.client.put("/api/effects/active", params=DESK, json={"effect": "beat_pulse"})

    assert resp.status_code == 200
    assert resp.json()["effect"] == "beat_pulse"
    running = (await api.client.get("/api/running")).json()["zones"]
    assert [(zone["zoneId"], zone["lookId"]) for zone in running] == [
        ("desk", "classic-beat-pulse")
    ]


async def test_settings_change_in_place(api: Api) -> None:
    await api.client.put("/api/effects/active", params=DESK, json={"effect": "beat_pulse"})

    resp = await api.client.put(
        "/api/effects/active", params=DESK, json={"params": {"gamma": 3.0}}
    )

    assert resp.status_code == 200
    active = (await api.client.get("/api/effects/active", params=DESK)).json()
    assert (active["effect"], active["params"]["gamma"]) == ("beat_pulse", 3.0)


async def test_unknown_effects_unknown_zones_and_no_zone(api: Api) -> None:
    resp = await api.client.put("/api/effects/active", params=DESK, json={"effect": "nope"})
    assert (resp.status_code, resp.json()["detail"]) == (404, "Unknown effect: nope")

    resp = await api.client.get("/api/effects/active", params={"zone": "zzz"})
    assert (resp.status_code, resp.json()["detail"]) == (404, "No zone 'zzz'")

    resp = await api.client.get("/api/effects/active")
    assert resp.status_code == 422


async def test_presets_save_and_load_on_a_zone(api: Api) -> None:
    body = {"effect": "beat_pulse", "params": {"gamma": 3.0}}
    await api.client.put("/api/effects/active", params=DESK, json=body)

    resp = await api.client.post("/api/presets", params=DESK, json={"name": "Test"})
    assert resp.status_code == 200
    assert (resp.json()["effect_class"], resp.json()["params"]["gamma"]) == ("beat_pulse", 3.0)

    await api.client.put("/api/effects/active", params=DESK, json={"effect": "rainbow_wave"})
    resp = await api.client.post("/api/presets/Test/load", params=DESK)
    assert resp.status_code == 200
    assert (resp.json()["effect"], resp.json()["params"]["gamma"]) == ("beat_pulse", 3.0)

    resp = await api.client.put("/api/presets/Test", json={"params": {"gamma": 4.0}})
    assert (resp.status_code, resp.json()["params"]["gamma"]) == (200, 4.0)
    assert [p["name"] for p in (await api.client.get("/api/presets")).json()] == ["Test"]
    assert (await api.client.delete("/api/presets/Test")).status_code == 200
    assert (await api.client.get("/api/presets")).json() == []
    assert (await api.client.post("/api/presets/Test/load", params=DESK)).status_code == 404
