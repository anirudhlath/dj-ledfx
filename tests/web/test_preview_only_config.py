"""Preview only is a config value the zone manager applies at once (spec §6.4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.config import AppConfig, DiscoveryConfig


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a")], []) as api:
        yield api


async def test_preview_only_applies_without_a_restart(api: Api) -> None:
    resp = await api.client.put("/api/config", json={"engine": {"preview_only": True}})

    assert resp.status_code == 200
    assert resp.headers["X-Requires-Restart"] == "false"
    assert api.home.manager.preview_only
    assert (await api.client.get("/api/config")).json()["engine"]["preview_only"] is True
    assert (await api.home.db.load_config("engine"))["preview_only"] == "true"


async def test_preview_only_must_be_true_or_false(api: Api) -> None:
    resp = await api.client.put("/api/config", json={"engine": {"preview_only": "yes"}})

    assert resp.status_code == 400
    assert api.home.manager.preview_only is False


async def test_other_changes_need_a_restart_and_keep_every_section(api: Api) -> None:
    api.app.state.config = AppConfig(discovery=DiscoveryConfig(subnet_mask=16))

    resp = await api.client.put("/api/config", json={"engine": {"fps": 30}})

    assert resp.headers["X-Requires-Restart"] == "true"
    assert resp.json()["discovery"]["subnet_mask"] == 16
