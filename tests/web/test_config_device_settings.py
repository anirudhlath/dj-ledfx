"""PUT /api/config saves the device settings a request names in state.db, where the next
start reads them (light-sync spec §8, as the owner decided: the plan's ruling 20)."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.config import AppConfig, EngineConfig
from dj_ledfx.main import _load_config_from_db
from tests.web.conftest import raw_json


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a")], []) as api:
        yield api


async def test_a_device_setting_saved_in_the_app_applies_from_the_next_start(api: Api) -> None:
    body = {"devices": {"govee": {"max_fps": 20, "probe_interval_s": 0.8}}}
    assert (await api.client.put("/api/config", json=body)).status_code == 200

    config = await _load_config_from_db(api.home.db)

    assert config is not None
    assert (config.devices.govee.max_fps, config.devices.govee.probe_interval_s) == (20, 0.8)
    assert config.devices == api.app.state.config.devices
    # As config.toml's migration writes them: in the kind's own section, as JSON
    saved = await api.home.db.load_config("devices.govee")
    assert saved == {"max_fps": "20", "probe_interval_s": "0.8"}


async def test_a_save_that_names_no_device_setting_pins_no_default(api: Api) -> None:
    """Preview only's switch saves no device setting, so a default the code changes later
    still reaches each setting no one set."""
    body = {"engine": {"preview_only": True}}
    assert (await api.client.put("/api/config", json=body)).status_code == 200

    saved = await api.home.db.load_all_config()

    assert saved[("engine", "preview_only")] is True
    assert [section for section, _ in saved if section.startswith("devices.")] == []


@pytest.mark.parametrize("refused", [{"probe_interval_s": 0}, {"max_fps": "fast"}])
async def test_a_device_setting_the_config_refuses_saves_nothing(
    api: Api, refused: dict[str, Any]
) -> None:
    await api.client.put("/api/config", json={"devices": {"govee": {"max_fps": 20}}})
    body = {"devices": {"govee": {"latency_ms": 50.0, **refused}}}

    assert (await api.client.put("/api/config", json=body)).status_code == 400
    assert await api.home.db.load_config("devices.govee") == {"max_fps": "20"}


NOT_FINITE = (math.nan, math.inf, -math.inf)
# A number that isn't finite where a body can hold one: a flat section's setting, a device
# setting, and deep in a value the old UI sends back whole (the old scene page's mapping).
HOLDING: dict[str, Callable[[float], dict[str, Any]]] = {
    "flat": lambda number: {"engine": {"fps": number}},
    "device": lambda number: {"devices": {"govee": {"latency_ms": number}}},
    "deep": lambda number: {"scene_config": {"mapping_params": {"origin": [0.0, number, 0.0]}}},
}


@pytest.mark.parametrize("holding", HOLDING.values(), ids=list(HOLDING))
async def test_a_body_holding_a_number_that_isn_t_finite_gets_a_400_and_changes_nothing(
    api: Api, holding: Callable[[float], dict[str, Any]]
) -> None:
    """No setting can use NaN or an infinity, and no answer can carry one back: a saved one
    answered that save and every later one with a 500."""
    await api.client.put("/api/config", json={"devices": {"govee": {"max_fps": 20}}})
    saved, running = await api.home.db.load_all_config(), api.app.state.config

    for number in NOT_FINITE:
        response = await api.client.put("/api/config", **raw_json(json.dumps(holding(number))))
        refused = (response.status_code, response.json())
        assert refused == (400, {"detail": "config numbers must be finite"}), number

    assert await api.home.db.load_all_config() == saved
    assert api.app.state.config is running


async def test_a_refused_save_leaves_the_next_save_and_read_answering(api: Api) -> None:
    refused = json.dumps({"engine": {"fps": math.nan}})
    assert (await api.client.put("/api/config", **raw_json(refused))).status_code == 400

    saved = await api.client.put("/api/config", json={"engine": {"fps": 30}})
    read = await api.client.get("/api/config")

    assert (saved.status_code, read.status_code) == (200, 200)
    assert read.json()["engine"]["fps"] == 30


async def test_a_save_state_db_fails_leaves_the_running_config_as_it_was(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A config is saved before it replaces the running one."""

    async def fail(section: str, data: dict[str, str]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(api.home.db, "save_config_bulk", fail)
    running = api.app.state.config

    with pytest.raises(OSError, match="disk full"):
        await api.client.put("/api/config", json={"engine": {"fps": 30}})

    assert api.app.state.config is running


async def test_a_save_it_can_t_answer_saves_nothing_and_leaves_the_running_config(
    api: Api,
) -> None:
    """A number that isn't finite already running (config.toml's nan) can't be answered with,
    and the answer is written first: the save stops before anything is saved or replaced."""
    running = AppConfig(engine=EngineConfig(fps=math.nan))
    api.app.state.config = running
    saved = await api.home.db.load_all_config()

    with pytest.raises(ValueError, match="not JSON compliant"):
        await api.client.put("/api/config", json={"devices": {"govee": {"max_fps": 20}}})

    assert await api.home.db.load_all_config() == saved
    assert api.app.state.config is running


async def test_a_config_import_while_a_save_is_on_its_way_waits_its_turn(api: Api) -> None:
    """A save replaces the running config only once it's saved, so config writes take turns:
    neither of two at once is lost."""
    save = api.client.put("/api/config", json={"engine": {"fps": 30}})
    load = api.client.post("/api/config/import", content="[engine]\nmax_lookahead_ms = 500\n")

    answers = await asyncio.gather(save, load)

    assert [answer.status_code for answer in answers] == [200, 200]
    engine = api.app.state.config.engine
    assert (engine.fps, engine.max_lookahead_ms) == (30, 500)


def _as_javascript_sends(value: Any) -> Any:
    """A value through JSON.parse and JSON.stringify, as the old UI sends it back: a whole
    float comes back an int."""
    if isinstance(value, dict):
        return {key: _as_javascript_sends(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_as_javascript_sends(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


async def test_the_old_ui_s_save_still_saves_every_device_setting_it_shows(api: Api) -> None:
    """The old UI's Config page sends back the whole config it read, but preview only
    (config.tsx's handleApply), as JavaScript writes it: every device setting passes the
    config's checks and is saved (the plan's ruling 20)."""
    draft = _as_javascript_sends((await api.client.get("/api/config")).json())
    engine = {key: draft["engine"][key] for key in ("fps", "max_lookahead_ms")}

    response = await api.client.put("/api/config", json={**draft, "engine": engine})

    assert response.status_code == 200
    config = await _load_config_from_db(api.home.db)
    assert config is not None and config.devices == AppConfig().devices
    for kind, settings in draft["devices"].items():
        assert set(await api.home.db.load_config(f"devices.{kind}")) == set(settings)
