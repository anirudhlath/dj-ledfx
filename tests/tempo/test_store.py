"""The tempo settings in state.db (M3 ruling 9), and the clock that saves and reloads them."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from tempo_fakes import START_WALL, FakeTime, events, play, tempo_clock

from dj_ledfx.events import EventBus
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import export_toml, import_toml
from dj_ledfx.tempo.model import (
    QUIET_S,
    DjSet,
    InternalTempo,
    TempoChanged,
    TempoSettings,
)
from dj_ledfx.tempo.store import TempoStore, settings_to

SETTINGS = TempoSettings(
    lock="internal",
    internal=InternalTempo(96.5, "tapped", START_WALL),
    last_set=DjSet(START_WALL - timedelta(hours=3), START_WALL - timedelta(hours=1)),
)


async def test_the_settings_come_back_as_they_were_saved(db: StateDB) -> None:
    store = TempoStore(db)

    assert await store.load() == TempoSettings()  # nothing saved yet
    await store.save(SETTINGS)
    assert await store.load() == SETTINGS
    await store.save(TempoSettings())
    assert await store.load() == TempoSettings()  # the times that went went with them


# Review Focus 5: settings nobody can read.
async def test_unreadable_tempo_settings_fall_back_to_defaults(db: StateDB) -> None:
    await db.save_config_bulk(
        "tempo",
        {
            "lock": json.dumps("sideways"),
            "internal_bpm": "NaN",
            "internal_how": json.dumps("tapped"),
            "internal_at": json.dumps("yesterday"),
            "last_set_from": json.dumps("2026-10-01T22:00:00+00:00"),
            "last_set_to": json.dumps("2026-10-01T21:00:00+00:00"),  # before it began
        },
    )
    assert await TempoStore(db).load() == TempoSettings()

    await db.save_config_bulk(
        "tempo",
        {
            "lock": json.dumps("prodjlink"),
            "internal_bpm": "100",
            "internal_how": json.dumps("guessed"),
            "internal_at": "{not json",
        },
    )
    assert await TempoStore(db).load() == TempoSettings(
        lock="prodjlink", internal=InternalTempo(100.0, "set", None)
    )


async def test_the_settings_never_hold_a_null_so_a_backup_can_carry_them(db: StateDB) -> None:
    store = TempoStore(db)
    await store.save(TempoSettings())

    assert None not in settings_to(TempoSettings()).values()
    text = await export_toml(db)  # TOML has no null: this would raise
    await store.save(SETTINGS)
    await import_toml(db, text)  # the backup's keys over the current ones

    assert (await store.load()).internal == InternalTempo()


async def test_tempo_settings_are_not_the_app_s_config(db: StateDB) -> None:
    await TempoStore(db).save(SETTINGS)

    assert await db.is_config_empty()  # a fresh start still migrates config.toml


async def test_the_clock_saves_what_changed_and_starts_from_it(db: StateDB) -> None:
    store = TempoStore(db)
    clock = tempo_clock(FakeTime(), store=store)
    clock.set_tempo("internal", 90.0)
    await clock.save()

    again = tempo_clock(FakeTime(), settings=await store.load(), store=store)

    assert (again.lock, again.bpm, again.internal.how) == ("internal", 90.0, "set")
    assert again.sample().bpm == 90.0


async def test_run_saves_a_hand_back(db: StateDB) -> None:
    store = TempoStore(db)
    time = FakeTime()
    clock = tempo_clock(time, store=store)
    *_, last = play(clock, time, 4, bpm=125.0)
    time.now = last + QUIET_S + 0.5

    task = asyncio.create_task(clock.run())
    async with asyncio.timeout(2.0):
        while (await store.load()).internal.how != "kept":
            await asyncio.sleep(0.05)
    clock.stop()
    await task

    assert (await store.load()).internal.bpm == 125.0
    assert (await store.load()).last_set is not None


class WaitingStore(TempoStore):
    """A store whose saves wait until the test lets them go on, as a save waits for
    state.db's lock while another write holds it."""

    def __init__(self, db: StateDB) -> None:
        super().__init__(db)
        self.waiting, self.go = asyncio.Event(), asyncio.Event()

    async def save(self, settings: TempoSettings) -> None:
        self.waiting.set()
        await self.go.wait()
        await super().save(settings)


async def test_a_change_just_before_shutdown_is_saved(db: StateDB) -> None:
    store = WaitingStore(db)
    clock = tempo_clock(FakeTime(), store=store)
    task = asyncio.create_task(clock.run())
    clock.set_tempo("internal", 90.0)
    async with asyncio.timeout(2.0):
        await store.waiting.wait()  # run() is saving it, and waits for state.db

    task.cancel()  # shutdown
    await asyncio.wait([task])
    store.go.set()
    await clock.save()  # main's last save, before state.db closes

    assert (await TempoStore(db).load()).internal.bpm == 90.0


async def test_reload_takes_a_restored_backup_at_once(db: StateDB) -> None:
    bus = EventBus()
    changed = events(bus, TempoChanged)
    store = TempoStore(db)
    time = FakeTime()
    clock = tempo_clock(time, store=store, event_bus=bus)
    await store.save(SETTINGS)  # what a restore writes

    await clock.reload()

    assert (clock.lock, clock.bpm, clock.internal, clock.last_set) == (
        "internal",
        96.5,
        SETTINGS.internal,
        SETTINGS.last_set,
    )
    assert clock.sample_at(time.now + 60.0 / 96.5).beat_index == 1
    assert len(changed) == 1
