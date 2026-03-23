"""Tests for StateDB device_saved_state persistence methods."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> StateDB:  # type: ignore[misc]
    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()
    yield state_db  # type: ignore[misc]
    await state_db.close()


def _make_state(led_count: int = 5, fill: int = 128) -> bytes:
    return np.full((led_count, 3), fill, dtype=np.uint8).tobytes()


@pytest.mark.asyncio
async def test_save_and_load_device_state(db: StateDB) -> None:
    state = _make_state(led_count=5, fill=200)
    await db.save_device_state("device:aa:bb:cc", state)

    loaded = await db.load_device_state("device:aa:bb:cc")
    assert loaded == state


@pytest.mark.asyncio
async def test_load_missing_device_state_returns_none(db: StateDB) -> None:
    result = await db.load_device_state("does:not:exist")
    assert result is None


@pytest.mark.asyncio
async def test_load_all_device_states_empty(db: StateDB) -> None:
    result = await db.load_all_device_states()
    assert result == {}


@pytest.mark.asyncio
async def test_load_all_device_states_multiple(db: StateDB) -> None:
    state_a = _make_state(led_count=3, fill=50)
    state_b = _make_state(led_count=10, fill=255)
    await db.save_device_state("device:aa", state_a)
    await db.save_device_state("device:bb", state_b)

    result = await db.load_all_device_states()
    assert len(result) == 2
    assert result["device:aa"] == state_a
    assert result["device:bb"] == state_b


@pytest.mark.asyncio
async def test_save_device_state_upsert(db: StateDB) -> None:
    """Second save with same stable_id must overwrite, not create duplicate."""
    state_v1 = _make_state(led_count=4, fill=10)
    state_v2 = _make_state(led_count=4, fill=240)

    await db.save_device_state("device:cc", state_v1)
    await db.save_device_state("device:cc", state_v2)

    loaded = await db.load_device_state("device:cc")
    assert loaded == state_v2

    all_states = await db.load_all_device_states()
    # Should only have one entry for this stable_id
    assert len([k for k in all_states if k == "device:cc"]) == 1


@pytest.mark.asyncio
async def test_schema_version_is_3_after_migration(db: StateDB) -> None:
    """Migration 003 should have been applied, bumping schema to version 3."""
    version = await db.get_schema_version()
    assert version == 3
