"""The light-sync spec's §7: each light's latency and mode, remembered across restarts."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any

import pytest
from conftest import as_schema
from govee_fakes import LAMP
from loguru import logger

from dj_ledfx.latency.memory import LinkMemory
from dj_ledfx.latency.strategies import LATENCY_WINDOW, StaticLatency, WindowedMedianLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import export_toml


def measured(latency_ms: float, *, dozing: bool = False) -> LatencyTracker:
    """A tracker whose light measured latency_ms while it streamed, in the mode given."""
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0), name="test-lamp")
    tracker.recall(latency_ms, dozing)
    tracker.note_send()
    tracker.update_rtt(latency_ms if dozing else 2 * latency_ms)
    assert tracker.measured and tracker.link_latency_ms == latency_ms
    return tracker


async def _rows(db: StateDB) -> list[tuple[Any, ...]]:
    return await db.fetch_all("SELECT stable_id, latency_ms, dozing FROM link_memory")


async def test_a_light_s_row_is_read_back_into_its_tracker_at_the_next_start(
    db: StateDB,
) -> None:
    assert await LinkMemory(db).save([(LAMP, measured(250.0, dozing=True))]) == 1

    memory = LinkMemory(db)  # the next start
    await memory.load()
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0), display_ms=10.0)
    memory.recall(LAMP, tracker)

    assert (tracker.link_latency_ms, tracker.dozing) == (250.0, True)
    assert tracker.effective_latency_ms == 260.0 and not tracker.measured


async def test_a_light_with_no_row_starts_at_its_seed_awake(db: StateDB) -> None:
    memory = LinkMemory(db)
    await memory.load()
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    memory.recall(LAMP, tracker)
    assert (tracker.link_latency_ms, tracker.dozing) == (100.0, False)


# The table isn't STRICT, so a hand-edited state.db can hold anything. A stored row the app
# can't use never stops it starting (the reason behind ruling 3): it's skipped, its light
# starts at its seed, awake, and the light's next write replaces it.
async def test_rows_the_app_can_t_use_are_skipped_with_one_warning(db: StateDB) -> None:
    bad = [
        ("govee:text", "fast", 0),
        ("govee:infinite", math.inf, 0),
        ("govee:negative", -5.0, 0),
        ("govee:mode", 250.0, "yes"),
    ]
    await db.write_many(
        [
            (
                "INSERT INTO link_memory (stable_id, latency_ms, dozing, updated_at) "
                "VALUES (?, ?, ?, '2026-10-06T00:00:00+00:00')",
                row,
            )
            for row in [*bad, (LAMP, 250.0, 1)]
        ]
    )
    memory = LinkMemory(db)
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        await memory.load()
    finally:
        logger.remove(sink)

    assert [(record["level"].name, record["message"]) for record in records] == [
        (
            "WARNING",
            "Skipped 4 link memory row(s) the app can't use: those lights start at their"
            " seed, awake",
        ),
    ]
    for stable_id, *_ in bad:
        tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
        memory.recall(stable_id, tracker)
        assert (tracker.link_latency_ms, tracker.dozing) == (100.0, False)
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    memory.recall(LAMP, tracker)
    assert (tracker.link_latency_ms, tracker.dozing) == (250.0, True)

    assert await memory.save([("govee:infinite", measured(120.0))]) == 1
    assert ("govee:infinite", 120.0, 0) in await _rows(db)


# Ruling 16: a recall is logged at INFO, with the latency and the mode. Under a static
# strategy the latency stays the configured one, and the line says so, as the tracker's
# change of mode does. A light with no row keeps its seed and gets no line.
@pytest.mark.parametrize(
    ("dozing", "static", "line"),
    [
        (True, False, "test-lamp starts from the latency it last had: 250 ms, dozing"),
        (False, False, "test-lamp starts from the latency it last had: 250 ms, awake"),
        (
            True,
            True,
            "test-lamp starts in the mode it last had (dozing): its latency stays the"
            " configured one",
        ),
    ],
    ids=["dozing", "awake", "static"],
)
async def test_a_recall_is_logged_with_the_latency_and_the_mode(
    db: StateDB, dozing: bool, static: bool, line: str
) -> None:
    await LinkMemory(db).save([(LAMP, measured(250.0, dozing=dozing))])
    memory = LinkMemory(db)
    await memory.load()
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        for stable_id in (LAMP, "govee:no-row"):
            strategy = (
                StaticLatency(5.0) if static else WindowedMedianLatency(LATENCY_WINDOW, 100.0)
            )
            memory.recall(stable_id, LatencyTracker(strategy, name="test-lamp"))
    finally:
        logger.remove(sink)
    assert [(record["level"].name, record["message"]) for record in records] == [("INFO", line)]


async def test_a_row_is_written_when_the_mode_changes_or_the_latency_moves_over_5_ms(
    db: StateDB,
) -> None:
    memory = LinkMemory(db)
    assert await memory.save([(LAMP, measured(100.0))]) == 1
    assert await memory.save([(LAMP, measured(104.0))]) == 0  # moved 4 ms
    assert await memory.save([(LAMP, measured(105.0))]) == 0  # 5 ms: not more than 5
    assert await memory.save([(LAMP, measured(94.5))]) == 1  # 5.5 ms
    assert await _rows(db) == [(LAMP, 94.5, 0)]
    assert await memory.save([(LAMP, measured(94.5, dozing=True))]) == 1  # its mode changed
    assert await memory.save([(LAMP, measured(97.0, dozing=True))]) == 0
    assert await _rows(db) == [(LAMP, 94.5, 1)]


async def test_a_light_not_measured_since_it_came_online_writes_nothing(db: StateDB) -> None:
    seeded = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    recalled = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    recalled.recall(250.0, dozing=True)
    static = LatencyTracker(StaticLatency(5.0))
    static.note_send()
    static.update_rtt(40.0)  # a static strategy ignores it: never measured

    lights = [("govee:seeded", seeded), ("govee:recalled", recalled), ("openrgb:pc:0", static)]
    assert await LinkMemory(db).save(lights) == 0
    assert await _rows(db) == []


async def test_a_latency_that_isn_t_a_number_holds_up_no_other_light_s_row(db: StateDB) -> None:
    """NaN would bind as NULL and fail the row's NOT NULL, rolling back every light's write
    in the same transaction, every period."""
    broken = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0), name="test-lamp")
    broken.note_send()
    broken.update_rtt(math.nan)
    assert broken.measured and math.isnan(broken.link_latency_ms)

    lights = [("govee:broken", broken), (LAMP, measured(250.0, dozing=True))]
    assert await LinkMemory(db).save(lights) == 1
    assert await _rows(db) == [(LAMP, 250.0, 1)]


async def test_the_writer_writes_every_period_and_once_more_at_shutdown(db: StateDB) -> None:
    lights = [(LAMP, measured(250.0, dozing=True))]
    writer = asyncio.create_task(LinkMemory(db).run(lambda: lights, every_s=0.01))
    await asyncio.sleep(0.1)
    assert await _rows(db) == [(LAMP, 250.0, 1)]

    lights = [(LAMP, measured(120.0))]  # its mode changed since
    writer.cancel()  # shutdown
    await asyncio.wait([writer])

    assert await _rows(db) == [(LAMP, 120.0, 0)]


async def test_a_write_that_fails_is_logged_and_the_next_one_retries(
    db: StateDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_many = db.write_many
    failures = [RuntimeError("disk full")]

    async def failing_once(statements: Any) -> None:
        if failures:
            raise failures.pop()
        await write_many(statements)

    monkeypatch.setattr(db, "write_many", failing_once)
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="ERROR")
    try:
        writer = asyncio.create_task(
            LinkMemory(db).run(lambda: [(LAMP, measured(250.0))], every_s=0.01)
        )
        await asyncio.sleep(0.1)
        writer.cancel()
        await asyncio.wait([writer])
    finally:
        logger.remove(sink)

    assert [record["message"] for record in records] == [
        "Writing the lights' link memory failed; the next write retries"
    ]
    assert await _rows(db) == [(LAMP, 250.0, 0)]


async def test_backups_leave_the_link_memory_out(db: StateDB) -> None:
    await LinkMemory(db).save([(LAMP, measured(250.0, dozing=True))])
    backup = await export_toml(db)
    assert "link_memory" not in backup and LAMP not in backup


async def test_a_database_from_before_light_sync_gains_the_table(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.db")
    await db.open()
    await db.write("DROP TABLE link_memory")
    await as_schema(db, 9)
    await db.close()

    db = StateDB(tmp_path / "state.db")
    await db.open()
    try:
        assert await db.get_schema_version() == 10
        assert await _rows(db) == []
    finally:
        await db.close()
