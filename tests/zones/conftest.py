from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

import pytest
import pytest_asyncio
from conftest import FakeLight
from runtime_fakes import register_fields
from zone_home import Home, HomeFactory, build_home

from dj_ledfx.zones.home_view import HomeView
from dj_ledfx.zones.model import ZoneRecord


@pytest.fixture
def _fields() -> None:
    """The fake field effects (runtime_fakes), registered and working; the root conftest
    drops them after each test."""
    register_fields()


@pytest_asyncio.fixture
async def make_home(tmp_path: Path) -> AsyncIterator[HomeFactory]:
    homes: list[Home] = []

    async def factory(
        lights: Sequence[FakeLight],
        zones: Sequence[ZoneRecord],
        *,
        preview_only: bool = False,
        view: HomeView | None = None,
        frames_watched: Callable[[], bool] | None = None,
        evening: Callable[[], float] | None = None,
    ) -> Home:
        home = await build_home(
            tmp_path,
            lights,
            zones,
            preview_only=preview_only,
            view=view,
            frames_watched=frames_watched,
            evening=evening,
        )
        homes.append(home)
        return home

    yield factory
    for home in homes:
        await home.db.close()
