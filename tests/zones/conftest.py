from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest_asyncio
from conftest import FakeLight
from zone_home import Home, HomeFactory, build_home

from dj_ledfx.zones.home_view import HomeView
from dj_ledfx.zones.model import ZoneRecord


@pytest_asyncio.fixture
async def make_home(tmp_path: Path) -> AsyncIterator[HomeFactory]:
    homes: list[Home] = []

    async def factory(
        lights: Sequence[FakeLight],
        zones: Sequence[ZoneRecord],
        *,
        preview_only: bool = False,
        view: HomeView | None = None,
    ) -> Home:
        home = await build_home(tmp_path, lights, zones, preview_only=preview_only, view=view)
        homes.append(home)
        return home

    yield factory
    for home in homes:
        await home.db.close()
