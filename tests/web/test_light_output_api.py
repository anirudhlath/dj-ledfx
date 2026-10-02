"""GET and PUT /api/lights/{id}/output: a Govee lamp's own output (the light-output plan's
ruling 17), through a real discovery orchestrator over a transport that hears the test lamp."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from api_home import Api, api_home
from govee_fakes import LAMP, TEST_MODEL, UPRIGHT, lamp_row, lamp_transport

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY

OUTPUT = f"/api/lights/{LAMP}/output"


@pytest.fixture(autouse=True)
def _test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)


@asynccontextmanager
async def _lamp_api(tmp_path: Path, *, online: bool = True) -> AsyncIterator[Api]:
    """The app over the test lamp, known by its row. online: set up from it as a start
    does; else it didn't answer then, and a scan finds it later."""
    govee = GoveeBackend()
    govee._transport = lamp_transport()
    async with api_home(tmp_path, [], [], backends=[govee]) as api:
        await api.home.db.upsert_device(lamp_row())
        if online:
            await api.discovery.connect_known_devices(await api.home.db.load_devices())
        yield api


def _adapter(api: Api) -> DeviceAdapter:
    """The lamp's adapter, which plays its output."""
    managed = api.home.devices.get_by_stable_id(LAMP)
    assert managed is not None
    return managed.adapter


async def _extra(api: Api, light_id: str = LAMP) -> Any:
    row = await api.home.db.load_device(light_id)
    assert row is not None
    return json.loads(row["extra"]) if row["extra"] is not None else None


async def test_a_lamp_plays_its_model_s_output_until_it_has_its_own(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path) as api:
        answer = await api.client.get(OUTPUT)
    assert answer.status_code == 200
    assert answer.json() == {
        "lightId": LAMP,
        "mode": "segments",
        "segments": 15,
        "own": {"mode": None, "segments": None},
        "online": True,
    }


# Review Focus 5: a lamp that ignores razer can be set to one colour, which applies at once.
async def test_a_lamp_that_ignores_razer_can_be_switched_to_one_colour(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path) as api:
        answer = await api.client.put(OUTPUT, json={"mode": "colour"})
        stored = await _extra(api)
        again = await api.client.get(OUTPUT)
        adapter = _adapter(api)
    assert answer.status_code == 200
    assert (answer.json()["mode"], answer.json()["segments"]) == ("colour", 15)
    assert answer.json()["own"] == {"mode": "colour", "segments": None}
    assert isinstance(adapter, GoveeColourAdapter)  # at once
    assert stored == {"output": {"mode": "colour"}}
    assert again.json() == answer.json()


async def test_a_segment_count_is_set_then_given_back_to_the_model(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path) as api:
        counted = await api.client.put(OUTPUT, json={"segments": 10})
        playing = _adapter(api).led_count
        reset = await api.client.put(OUTPUT, json={})
        stored = await _extra(api)
    assert (counted.json()["mode"], counted.json()["segments"], playing) == ("segments", 10, 10)
    assert counted.json()["own"] == {"mode": None, "segments": 10}
    assert reset.json()["segments"] == 15
    assert reset.json()["own"] == {"mode": None, "segments": None}
    assert stored == {}


async def test_an_offline_lamp_keeps_its_output_for_the_scan_that_finds_it(
    tmp_path: Path,
) -> None:
    async with _lamp_api(tmp_path, online=False) as api:
        answer = await api.client.put(OUTPUT, json={"mode": "colour"})
        stored = await _extra(api)
        await api.discovery.run_scan()
        found = await api.client.get(OUTPUT)
        adapter = _adapter(api)
    assert answer.status_code == 200 and answer.json()["online"] is False
    assert (answer.json()["mode"], answer.json()["segments"]) == ("colour", 15)  # its plan
    assert stored == {"output": {"mode": "colour"}}
    assert found.json() == {**answer.json(), "online": True}
    assert isinstance(adapter, GoveeColourAdapter)


async def test_a_restored_backup_s_output_plays_at_once(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path) as api:
        await api.client.put(OUTPUT, json={"mode": "colour"})
        backup = (await api.client.get("/api/state/export")).text
        await api.client.put(OUTPUT, json={})  # back to razer
        restored = await api.client.post("/api/state/import", content=backup)
        answer = await api.client.get(OUTPUT)
        adapter = _adapter(api)
    assert restored.status_code == 200
    assert (answer.json()["mode"], answer.json()["online"]) == ("colour", True)
    assert answer.json()["own"] == {"mode": "colour", "segments": None}
    assert isinstance(adapter, GoveeColourAdapter)


async def test_a_lamp_plays_as_it_was_set_up_until_a_config_change_applies(
    tmp_path: Path,
) -> None:
    """The config's segment count applies at the next start, so the answer is what the lamp
    plays now, not what the new count would make it."""
    async with _lamp_api(tmp_path) as api:
        changed = await api.client.put(
            "/api/config", json={"devices": {"govee": {"segment_override": 10}}}
        )
        answer = await api.client.get(OUTPUT)
        playing = _adapter(api).led_count
    assert changed.status_code == 200
    assert (answer.json()["segments"], playing) == (15, 15)


async def test_only_a_known_govee_lamp_has_an_output(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path) as api:
        await api.home.db.upsert_device(
            {"id": "lifx:test", "name": "Test bulb", "backend": "lifx"}
        )
        unknown = await api.client.get("/api/lights/govee:nobody/output")
        bulb = await api.client.put("/api/lights/lifx:test/output", json={"mode": "colour"})
        stored = await _extra(api, "lifx:test")
    assert (unknown.status_code, bulb.status_code) == (404, 404)
    assert bulb.json()["detail"] == "No Govee lamp 'lifx:test'"
    assert stored is None


@pytest.mark.parametrize("body", [{"segments": 1}, {"segments": 256}, {"mode": "rainbow"}])
async def test_an_output_no_lamp_plays_is_refused(tmp_path: Path, body: dict[str, Any]) -> None:
    async with _lamp_api(tmp_path) as api:
        before = _adapter(api)
        answer = await api.client.put(OUTPUT, json=body)
        stored = await _extra(api)
        after = _adapter(api)
    assert answer.status_code == 422
    assert (stored, after) == (None, before)
