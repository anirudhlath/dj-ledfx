"""Built-in and saved looks, and which ones are starred (spec §5.2)."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import (
    BuiltInLookError,
    Look,
    LookNotFoundError,
    look_from_dict,
    look_to_dict,
    validate_look,
)

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB


def _now() -> str:
    return datetime.now(UTC).isoformat()


def look_body(look: Look) -> str:
    """A look as saved in state.db: its contract shape, without schema or star."""
    data = look_to_dict(look)
    data.pop("starred")
    for layer in data["layers"]:
        layer.pop("schema")
    return json.dumps(data)


class LookStore:
    def __init__(self, db: StateDB) -> None:
        self._db = db
        self._builtins: dict[str, Look] = {look.id: look for look in builtin_looks()}
        self._saved: dict[str, Look] = {}
        self._stars: set[str] = set()

    async def load(self) -> None:
        self._saved = {}
        rows = await self._db.fetch_all("SELECT id, body FROM looks ORDER BY created_at, id")
        for look_id, body in rows:
            try:
                look = replace(look_from_dict(json.loads(body)), id=look_id, built_in=False)
                validate_look(look)
            except Exception as exc:  # a bad saved look never stops the app (spec §8)
                logger.warning("Skipping saved look {}: {}", look_id, exc)
                continue
            self._saved[look_id] = look
        stars = await self._db.fetch_all("SELECT look_id FROM look_stars")
        self._stars = {row[0] for row in stars}
        logger.info("Looks: {} built in, {} saved", len(self._builtins), len(self._saved))

    def looks(self) -> list[Look]:
        return [*self._builtins.values(), *self._saved.values()]

    def get(self, look_id: str) -> Look:
        look = self._builtins.get(look_id) or self._saved.get(look_id)
        if look is None:
            raise LookNotFoundError(look_id)
        return look

    def is_starred(self, look_id: str) -> bool:
        return look_id in self._stars

    async def create(self, look: Look) -> Look:
        """Save a look as a new one ("Mine"). Built-ins are never overwritten."""
        saved = replace(look, id=f"mine-{uuid.uuid4().hex[:8]}", built_in=False)
        validate_look(saved)
        now = _now()
        await self._db.write(
            "INSERT INTO looks (id, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (saved.id, look_body(saved), now, now),
        )
        self._saved[saved.id] = saved
        return saved

    async def update(self, look_id: str, look: Look) -> Look:
        self._check_saved(look_id)
        updated = replace(look, id=look_id, built_in=False)
        validate_look(updated)
        await self._db.write(
            "UPDATE looks SET body=?, updated_at=? WHERE id=?",
            (look_body(updated), _now(), look_id),
        )
        self._saved[look_id] = updated
        return updated

    async def delete(self, look_id: str) -> None:
        self._check_saved(look_id)
        await self._db.write_many(
            [
                ("DELETE FROM looks WHERE id=?", (look_id,)),
                ("DELETE FROM look_stars WHERE look_id=?", (look_id,)),
            ]
        )
        del self._saved[look_id]
        self._stars.discard(look_id)

    async def set_starred(self, look_id: str, starred: bool) -> None:
        self.get(look_id)
        if starred:
            await self._db.write(
                "INSERT INTO look_stars (look_id) VALUES (?) ON CONFLICT(look_id) DO NOTHING",
                (look_id,),
            )
            self._stars.add(look_id)
        else:
            await self._db.write("DELETE FROM look_stars WHERE look_id=?", (look_id,))
            self._stars.discard(look_id)

    def _check_saved(self, look_id: str) -> None:
        if look_id in self._builtins:
            raise BuiltInLookError(f"'{look_id}' is built in; save your changes as a new look")
        if look_id not in self._saved:
            raise LookNotFoundError(look_id)
