"""The tempo settings in state.db: the config table's `tempo` section (M3 ruling 9).

That section rides in backups with the rest of the config. TOML has no null, so a time
that isn't set is a key that isn't there, and a value that can't be read is the default:
a bad value never stops the app (spec §8).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.tempo.model import (
    HOWS,
    LOCKS,
    DjSet,
    InternalHow,
    InternalTempo,
    TempoError,
    TempoSettings,
    check_bpm,
)
from dj_ledfx.timing import parse_utc, utc_text

SECTION = "tempo"


class TempoStore:
    def __init__(self, db: StateDB) -> None:
        self._db = db

    async def load(self) -> TempoSettings:
        values: dict[str, Any] = {}
        for key, text in (await self._db.load_config(SECTION)).items():
            try:
                values[key] = json.loads(text)
            except (TypeError, ValueError):
                continue  # this value is unreadable; the others still count
        return settings_from(values)

    async def save(self, settings: TempoSettings) -> None:
        """Replace the section, so a time that's no longer set goes with it."""
        insert = "INSERT INTO config (section, key, value) VALUES (?, ?, ?)"
        await self._db.write_many(
            [
                ("DELETE FROM config WHERE section = ?", (SECTION,)),
                *(
                    (insert, (SECTION, key, json.dumps(value)))
                    for key, value in settings_to(settings).items()
                ),
            ]
        )


def settings_to(settings: TempoSettings) -> dict[str, Any]:
    values: dict[str, Any] = {
        "lock": settings.lock,
        "internal_bpm": settings.internal.bpm,
        "internal_how": settings.internal.how,
    }
    if settings.internal.at is not None:
        values["internal_at"] = utc_text(settings.internal.at)
    if settings.last_set is not None:
        values["last_set_from"] = utc_text(settings.last_set.started)
        values["last_set_to"] = utc_text(settings.last_set.ended)
    return values


def settings_from(values: Mapping[str, Any]) -> TempoSettings:
    lock = values.get("lock")
    started, ended = parse_utc(values.get("last_set_from")), parse_utc(values.get("last_set_to"))
    last_set = None
    if started is not None and ended is not None and started <= ended:
        last_set = DjSet(started, ended)
    return TempoSettings(
        lock=lock if lock in LOCKS else "auto",
        internal=_internal(values),
        last_set=last_set,
    )


def _internal(values: Mapping[str, Any]) -> InternalTempo:
    try:
        bpm = check_bpm(values.get("internal_bpm"))
    except TempoError:
        return InternalTempo()  # without its BPM the rest means nothing
    given = values.get("internal_how")
    how: InternalHow = given if given in HOWS else "set"
    at = None if how == "default" else parse_utc(values.get("internal_at"))
    return InternalTempo(bpm, how, at)
