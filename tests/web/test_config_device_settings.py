"""PUT /api/config saves the device settings a request names in state.db, where the next
start reads them (light-sync spec §8, as the owner decided: the plan's ruling 20)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.config import AppConfig
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


async def test_a_nan_device_setting_gets_a_400_and_saves_nothing(api: Api) -> None:
    await api.client.put("/api/config", json={"devices": {"govee": {"max_fps": 20}}})
    body = json.dumps({"devices": {"govee": {"latency_ms": float("nan")}}})

    response = await api.client.put("/api/config", **raw_json(body))

    assert response.status_code == 400
    assert response.json() == {"detail": "govee latency_ms must be a finite number"}
    assert await api.home.db.load_config("devices.govee") == {"max_fps": "20"}


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
