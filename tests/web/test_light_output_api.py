"""GET and PUT /api/lights/{id}/output: a Govee lamp's own output (the light-output plan's
ruling 17)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from api_home import Api, api_home
from govee_fakes import LAMP, TEST_MODEL, UPRIGHT, govee_lamp, lamp_row

from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY

OUTPUT = f"/api/lights/{LAMP}/output"


@pytest.fixture(autouse=True)
def _test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)


class FakeDiscovery:
    """Stands in for the discovery orchestrator: each reconnect gets `answer`."""

    def __init__(self, answer: bool = True) -> None:
        self.answer = answer
        self.reconnected: list[str] = []

    async def reconnect(self, stable_id: str) -> bool:
        self.reconnected.append(stable_id)
        return self.answer


@asynccontextmanager
async def _lamp_api(tmp_path: Path, discovery: FakeDiscovery) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [govee_lamp()], [], discovery=discovery) as api:
        await api.home.db.upsert_device(lamp_row())
        yield api


async def _extra(api: Api, light_id: str = LAMP) -> Any:
    row = await api.home.db.load_device(light_id)
    assert row is not None
    return json.loads(row["extra"]) if row["extra"] is not None else None


async def test_a_lamp_plays_its_model_s_output_until_it_has_its_own(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery()) as api:
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
    discovery = FakeDiscovery()
    async with _lamp_api(tmp_path, discovery) as api:
        answer = await api.client.put(OUTPUT, json={"mode": "colour"})
        stored = await _extra(api)
        again = await api.client.get(OUTPUT)
    assert answer.status_code == 200
    assert (answer.json()["mode"], answer.json()["segments"]) == ("colour", 15)
    assert answer.json()["own"] == {"mode": "colour", "segments": None}
    assert discovery.reconnected == [LAMP]  # at once
    assert stored == {"output": {"mode": "colour"}}
    assert again.json() == answer.json()


async def test_a_segment_count_is_set_then_given_back_to_the_model(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery()) as api:
        counted = await api.client.put(OUTPUT, json={"segments": 10})
        reset = await api.client.put(OUTPUT, json={})
        stored = await _extra(api)
    assert (counted.json()["mode"], counted.json()["segments"]) == ("segments", 10)
    assert counted.json()["own"] == {"mode": None, "segments": 10}
    assert reset.json()["segments"] == 15
    assert reset.json()["own"] == {"mode": None, "segments": None}
    assert stored == {}


async def test_a_lamp_that_misses_the_reconnect_says_so_and_keeps_its_output(
    tmp_path: Path,
) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery(answer=False)) as api:
        answer = await api.client.put(OUTPUT, json={"mode": "colour"})
        stored = await _extra(api)
    assert answer.status_code == 200 and answer.json()["online"] is False
    assert stored == {"output": {"mode": "colour"}}  # for the scan that finds it


async def test_only_a_known_govee_lamp_has_an_output(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery()) as api:
        await api.home.db.upsert_device(
            {"id": "lifx:test", "name": "Test bulb", "backend": "lifx"}
        )
        unknown = await api.client.get("/api/lights/govee:nobody/output")
        bulb = await api.client.put("/api/lights/lifx:test/output", json={"mode": "colour"})
    assert (unknown.status_code, bulb.status_code) == (404, 404)
    assert bulb.json()["detail"] == "No Govee lamp 'lifx:test'"


@pytest.mark.parametrize("body", [{"segments": 1}, {"segments": 256}, {"mode": "rainbow"}])
async def test_an_output_no_lamp_plays_is_refused(tmp_path: Path, body: dict[str, Any]) -> None:
    discovery = FakeDiscovery()
    async with _lamp_api(tmp_path, discovery) as api:
        answer = await api.client.put(OUTPUT, json=body)
        stored = await _extra(api)
    assert answer.status_code == 422
    assert (discovery.reconnected, stored) == ([], None)
