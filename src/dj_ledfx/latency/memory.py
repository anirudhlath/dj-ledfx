"""Each light's link memory (light-sync spec §7): the latency and mode it last had, kept in
state.db's link_memory table, so the first look after a restart starts every light where it
was. A cache, measured again within seconds of a start: backups leave it out."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB, Statement
from dj_ledfx.timing import utc_text, utcnow
from dj_ledfx.types import is_finite_number

LINK_MEMORY_EVERY_S = 30.0  # how often the writer writes what changed
MOVED_MS = 5.0  # a latency that moved by more than this since its row was written is written

# Each light's stable id and tracker, as the device manager has them now.
Trackers = Callable[[], Iterable[tuple[str, LatencyTracker]]]


@dataclass(frozen=True, slots=True)
class Link:
    """A light's row: its strategy's latency, before display and offset, and its mode."""

    latency_ms: float
    dozing: bool


class LinkMemory:
    """The lights' rows, read once at start and written as they change."""

    def __init__(self, db: StateDB) -> None:
        self._db = db
        self._links: dict[str, Link] = {}  # the rows as last read or written

    async def load(self) -> None:
        """Read the rows, once, at start. The table isn't STRICT, so a row can hold what the
        app never writes (a hand-edited state.db): a row whose latency isn't a finite number
        of at least 0 ms, or whose mode isn't 0 or 1, is skipped with one warning, and never
        stops the start. That light starts at its seed, awake, and its next write replaces
        the row."""
        rows = await self._db.fetch_all("SELECT stable_id, latency_ms, dozing FROM link_memory")
        links: dict[str, Link] = {}
        skipped = 0
        for stable_id, latency_ms, dozing in rows:
            if _usable(latency_ms) and dozing in (0, 1):
                links[stable_id] = Link(float(latency_ms), bool(dozing))
            else:
                skipped += 1
        if skipped:
            logger.warning(
                "Skipped {} link memory row(s) the app can't use: those lights start at "
                "their seed, awake",
                skipped,
            )
        self._links = links

    def recall(
        self, stable_id: str, tracker: LatencyTracker, *, had: LatencyTracker | None = None
    ) -> None:
        """Start a light's tracker from the latency and mode it last had, before its first
        frame: what the tracker it `had` before measured, when it measured any (a light
        found again within a run, whose row can be a write behind), else its row. A light
        with neither keeps its seed, awake."""
        link = _measured(had) if had is not None else None
        if link is None:
            link = self._links.get(stable_id)
        if link is None:
            return
        tracker.recall(link.latency_ms, link.dozing)
        mode = "dozing" if link.dozing else "awake"
        if tracker.static:  # the mode is recalled, and the latency stays the configured one
            logger.info(
                "{} starts in the mode it last had ({}): its latency stays the configured one",
                tracker.name,
                mode,
            )
            return
        logger.info(
            "{} starts from the latency it last had: {:.0f} ms, {}",
            tracker.name,
            link.latency_ms,
            mode,
        )

    async def save(self, trackers: Iterable[tuple[str, LatencyTracker]]) -> int:
        """Write the row of each light measured since it came online whose mode changed, or
        whose latency moved by more than MOVED_MS, since its row was last written. Returns
        how many rows it wrote. A latency no row can hold, one that isn't a finite number of
        at least 0 ms, is never written: a NaN would fail the whole write, and every light's
        row with it."""
        due: dict[str, Link] = {}
        for stable_id, tracker in trackers:
            link = _measured(tracker)
            if link is not None and _moved(self._links.get(stable_id), link):
                due[stable_id] = link
        if not due:
            return 0
        when = utc_text(utcnow())
        await self._db.write_many([_upsert(sid, link, when) for sid, link in due.items()])
        self._links.update(due)
        return len(due)

    async def run(self, trackers: Trackers, every_s: float = LINK_MEMORY_EVERY_S) -> None:
        """Write what changed every every_s, and once more when cancelled: at shutdown,
        while state.db is still open. A write that fails is logged, and the next one tries
        again."""
        try:
            while True:
                await asyncio.sleep(every_s)
                await self._save_logged(trackers)
        finally:
            await self._save_logged(trackers)

    async def _save_logged(self, trackers: Trackers) -> None:
        try:
            await self.save(trackers())
        except Exception:
            logger.exception("Writing the lights' link memory failed; the next write retries")


def _usable(latency_ms: object) -> bool:
    """A latency a row can hold: a finite number of at least 0 ms."""
    return is_finite_number(latency_ms) and latency_ms >= 0


def _measured(tracker: LatencyTracker) -> Link | None:
    """The latency and mode a tracker measured since it came online. None while its latency
    is still a seed or a recalled one, or when it's one no row can hold."""
    if not tracker.measured or not _usable(tracker.link_latency_ms):
        return None
    return Link(tracker.link_latency_ms, tracker.dozing)


def _moved(row: Link | None, now: Link) -> bool:
    if row is None or row.dozing != now.dozing:
        return True
    return abs(now.latency_ms - row.latency_ms) > MOVED_MS


def _upsert(stable_id: str, link: Link, when: str) -> Statement:
    return (
        "INSERT INTO link_memory (stable_id, latency_ms, dozing, updated_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(stable_id) DO UPDATE SET "
        "latency_ms=excluded.latency_ms, dozing=excluded.dozing, updated_at=excluded.updated_at",
        (stable_id, link.latency_ms, int(link.dozing), when),
    )
