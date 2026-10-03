from __future__ import annotations

import json
from typing import Any

import pytest
from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import (
    BuiltInLookError,
    Layer,
    Look,
    LookError,
    LookNotFoundError,
    Transform,
    look_to_dict,
)
from dj_ledfx.looks.store import INSERT_LOOK, LookStore
from dj_ledfx.persistence.state_db import StateDB

BUILT_INS = len(builtin_looks())


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


# H6: a saved look whose numbers are out of bounds (a hand-edited backup, a limit narrowed
# later) loads clamped, never dropped.
async def test_saved_looks_with_numbers_out_of_bounds_load_clamped(db: StateDB) -> None:
    now = "2026-09-24T00:00:00+00:00"
    long_trails, far = look_to_dict(_mine()), look_to_dict(_mine())
    long_trails["modifiers"]["trailsS"] = 12.0
    far["layers"][0]["transform"] = {"offset": [1e39, 0.0, 0.0], "rotateDeg": 0.0, "scale": 1.0}
    await db.write_many(
        [
            (INSERT_LOOK, ("mine-trails", json.dumps(long_trails), now, now)),
            (INSERT_LOOK, ("mine-far", json.dumps(far), now, now)),
        ]
    )

    store = await _loaded(db)

    loaded = {look.id: look for look in store.looks()[BUILT_INS:]}
    assert loaded.keys() == {"mine-trails", "mine-far"}
    assert loaded["mine-trails"].modifiers.trails_s == 10.0
    assert loaded["mine-far"].layers[0].transform == Transform((1000.0, 0.0, 0.0))


# M8: a request can't give two layers one id, but a saved look that has them still loads.
async def test_a_saved_look_whose_layers_share_an_id_loads(db: StateDB) -> None:
    now = "2026-09-24T00:00:00+00:00"
    body = look_to_dict(_mine())
    body["layers"] = [body["layers"][0], body["layers"][0]]
    await db.write_many([(INSERT_LOOK, ("mine-twice", json.dumps(body), now, now))])

    store = await _loaded(db)

    assert [layer.id for layer in store.get("mine-twice").layers] == ["l1", "l1"]


# Review Focus 1: a look saved before M4 checked transitions loads, clamped, never dropped.
async def test_saved_looks_with_odd_transition_durations_load_clamped(db: StateDB) -> None:
    now = "2026-09-24T00:00:00+00:00"
    rows = []
    for look_id, seconds in [("mine-nan", float("nan")), ("mine-minus", -3), ("mine-long", 99)]:
        body = look_to_dict(_mine())
        body["transition"] = {"kind": "fade", "durationS": seconds}
        rows.append((INSERT_LOOK, (look_id, json.dumps(body), now, now)))  # NaN as JSON's
    await db.write_many(rows)

    store = await _loaded(db)

    durations = {look.id: look.transition.duration_s for look in store.looks()[BUILT_INS:]}
    assert durations == {"mine-nan": 0.0, "mine-minus": 0.0, "mine-long": 10.0}
