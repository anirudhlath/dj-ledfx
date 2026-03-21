"""DebouncedWriter — coalescing write buffer on top of StateDB.

Collects high-frequency updates (latency measurements, effect state changes)
and flushes them to the DB in batches. The caller must await flush_pending()
before closing the DB to ensure no data is lost.
"""

from __future__ import annotations

from dj_ledfx.persistence.state_db import StateDB


class DebouncedWriter:
    """Coalesces rapid DB writes so the hot path never blocks on I/O.

    Holds in-memory pending maps for:
    - latency updates: device_id -> latency_ms (last value wins)
    - effect state updates: scene_id -> (effect_class, params) (last value wins)

    Call flush_pending() to write all pending updates to the DB.
    """

    def __init__(self, db: StateDB) -> None:
        self._db = db
        self._pending_latency: dict[str, float] = {}
        self._pending_effect_state: dict[str, tuple[str, str]] = {}

    def schedule_latency_update(self, device_id: str, latency_ms: float) -> None:
        """Coalesce a latency update — last value wins, flushed on flush_pending()."""
        self._pending_latency[device_id] = latency_ms

    def schedule_effect_state_update(self, scene_id: str, effect_class: str, params: str) -> None:
        """Coalesce an effect state update — last value wins, flushed on flush_pending()."""
        self._pending_effect_state[scene_id] = (effect_class, params)

    async def flush_pending(self) -> None:
        """Write all pending updates to the DB and clear the buffers."""
        await self._flush_latency()
        await self._flush_effect_state()

    async def _flush_latency(self) -> None:
        """Write all pending latency updates and clear the buffer."""
        if not self._pending_latency:
            return
        pending = self._pending_latency.copy()
        self._pending_latency.clear()
        await self._db._executemany_write(
            "UPDATE devices SET last_latency_ms=? WHERE id=?",
            [(v, k) for k, v in pending.items()],
        )

    async def _flush_effect_state(self) -> None:
        """Write all pending effect state updates and clear the buffer."""
        if not self._pending_effect_state:
            return
        pending = self._pending_effect_state.copy()
        self._pending_effect_state.clear()
        await self._db._executemany_write(
            "INSERT OR REPLACE INTO scene_effect_state (scene_id, effect_class, params) "
            "VALUES (?, ?, ?)",
            [(k, v[0], v[1]) for k, v in pending.items()],
        )
