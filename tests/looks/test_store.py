from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import (
    BuiltInLookError,
    Layer,
    Look,
    LookError,
    LookNotFoundError,
    look_to_dict,
)
from dj_ledfx.looks.store import INSERT_LOOK, LookStore
from dj_ledfx.persistence.state_db import StateDB

BUILT_INS = len(builtin_looks())


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


def _mine(name: str = "My breathe", **settings: Any) -> Look:
    return Look(
        id="",
        name=name,
        category="tempo",
        uses=("tempo",),
        layers=(Layer(id="l1", name="Breathe", type="field", kind="breathe", settings=settings),),
        derived_from="classic-breathe",
    )


async def _loaded(db: StateDB) -> LookStore:
    store = LookStore(db)
    await store.load()
    return store


async def test_builtins_come_first(db: StateDB) -> None:
    store = await _loaded(db)
    await store.create(_mine())
    looks = store.looks()
    assert [look.id for look in looks[:BUILT_INS]] == [look.id for look in builtin_looks()]
    assert looks[BUILT_INS].id.startswith("mine-")


async def test_create_saves_a_new_look_that_survives_a_reload(db: StateDB) -> None:
    store = await _loaded(db)
    saved = await store.create(_mine(beats_per_cycle=2.0))
    assert saved.id.startswith("mine-") and len(saved.id) == len("mine-") + 8
    assert not saved.built_in
    assert saved.derived_from == "classic-breathe"
    assert (await _loaded(db)).get(saved.id) == saved


async def test_create_refuses_a_look_m1_cannot_run(db: StateDB) -> None:
    store = await _loaded(db)
    with pytest.raises(LookError, match="above max"):
        await store.create(_mine(beats_per_cycle=99.0))
    assert len(store.looks()) == BUILT_INS


async def test_update_changes_saved_looks_only(db: StateDB) -> None:
    store = await _loaded(db)
    saved = await store.create(_mine())
    updated = await store.update(saved.id, _mine(name="Slower", beats_per_cycle=4.0))
    assert updated.id == saved.id and updated.name == "Slower"
    assert (await _loaded(db)).get(saved.id).name == "Slower"
    with pytest.raises(BuiltInLookError):
        await store.update("firmware", _mine())
    with pytest.raises(LookNotFoundError):
        await store.update("mine-missing", _mine())


async def test_delete_removes_the_look_and_its_star(db: StateDB) -> None:
    store = await _loaded(db)
    saved = await store.create(_mine())
    await store.set_starred(saved.id, True)
    await store.delete(saved.id)
    with pytest.raises(LookNotFoundError):
        store.get(saved.id)
    assert await db.fetch_all("SELECT look_id FROM look_stars") == []
    with pytest.raises(BuiltInLookError):
        await store.delete("firmware")


async def test_any_look_can_be_starred(db: StateDB) -> None:
    store = await _loaded(db)
    await store.set_starred("firmware", True)
    assert store.is_starred("firmware")
    assert (await _loaded(db)).is_starred("firmware")
    await store.set_starred("firmware", False)
    assert not (await _loaded(db)).is_starred("firmware")
    with pytest.raises(LookNotFoundError):
        await store.set_starred("nope", True)


async def test_load_skips_corrupt_saved_look(db: StateDB) -> None:
    removed_kind = look_to_dict(_mine())
    removed_kind["layers"][0]["kind"] = "retired_effect"
    now = "2026-09-24T00:00:00+00:00"
    await db.write_many(
        [
            (INSERT_LOOK, ("mine-good", json.dumps(look_to_dict(_mine())), now, now)),
            (INSERT_LOOK, ("mine-json", "{not json", now, now)),
            (INSERT_LOOK, ("mine-kind", json.dumps(removed_kind), now, now)),
        ]
    )
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        store = await _loaded(db)
    finally:
        logger.remove(sink)
    assert [look.id for look in store.looks()[BUILT_INS:]] == ["mine-good"]
    assert any("mine-json" in warning for warning in warnings)
    assert any("mine-kind" in w and "retired_effect" in w for w in warnings)
