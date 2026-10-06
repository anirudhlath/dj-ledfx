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
        rows = await self._db.fetch_all("SELECT stable_id, latency_ms, dozing FROM link_memory")
        self._links = {row[0]: Link(float(row[1]), bool(row[2])) for row in rows}

    def recall(self, stable_id: str, tracker: LatencyTracker) -> None:
        """Start a light's tracker from its row, before its first frame. A light with no row
        keeps its seed, awake."""
        link = self._links.get(stable_id)
        if link is None:
            return
        tracker.recall(link.latency_ms, link.dozing)
        mode = "dozing" if link.dozing else "awake"
        logger.info(
            "{} starts from the latency it last had: {:.0f} ms, {}",
            tracker.name,
            link.latency_ms,
            mode,
        )

    async def save(self, trackers: Iterable[tuple[str, LatencyTracker]]) -> int:
        """Write the row of each light measured since it came online whose mode changed, or
        whose latency moved by more than MOVED_MS, since its row was last written. Returns
        how many rows it wrote."""
        due: dict[str, Link] = {}
        for stable_id, tracker in trackers:
            if not tracker.measured:
                continue  # its latency is still a seed or a recalled one
            link = Link(tracker.link_latency_ms, tracker.dozing)
            if _moved(self._links.get(stable_id), link):
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
