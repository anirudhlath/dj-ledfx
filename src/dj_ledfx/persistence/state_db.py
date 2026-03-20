"""StateDB — SQLite-backed persistence layer for dj-ledfx state."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

# Directory containing SQL migration files
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class StateDB:
    """Async SQLite persistence layer using asyncio.to_thread for all I/O.

    All database operations are executed in a thread pool to avoid blocking
    the asyncio event loop. A single persistent connection is held open for
    the lifetime of the StateDB instance.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    async def open(self) -> None:
        """Open the database, apply migrations, and configure pragmas."""
        await asyncio.to_thread(self._open_sync)
        logger.info("StateDB opened: {}", self._path)

    def _open_sync(self) -> None:
        """Synchronous open — run in thread pool."""
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.commit()
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Apply unapplied SQL migration files in order."""
        assert self._conn is not None
        current_version = self._get_schema_version_sync()

        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        for migration_file in migration_files:
            # Extract version number from filename prefix (e.g., 001_initial.sql -> 1)
            stem = migration_file.stem
            version_str = stem.split("_")[0]
            try:
                version = int(version_str)
            except ValueError:
                logger.warning("Skipping migration file with non-numeric prefix: {}", migration_file.name)
                continue

            if version <= current_version:
                continue

            logger.info("Applying migration {} (v{})", migration_file.name, version)
            sql = migration_file.read_text()
            self._conn.executescript(sql)
            self._conn.execute(
                "INSERT OR REPLACE INTO config (section, key, value) VALUES (?, ?, ?)",
                ("_meta", "schema_version", str(version)),
            )
            self._conn.commit()

    def _get_schema_version_sync(self) -> int:
        """Return current schema version, 0 if unset."""
        assert self._conn is not None
        try:
            row = self._conn.execute(
                "SELECT value FROM config WHERE section='_meta' AND key='schema_version'"
            ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            # config table doesn't exist yet (fresh DB)
            return 0

    async def get_schema_version(self) -> int:
        """Return the current schema version number."""
        return await asyncio.to_thread(self._get_schema_version_sync)

    async def close(self) -> None:
        """Flush pending writes and close the database connection."""
        await self.flush_pending()
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
            logger.info("StateDB closed: {}", self._path)

    async def flush_pending(self) -> None:
        """Flush any pending debounced writes. No-op in base implementation."""

    # --- Low-level helpers ---

    async def _execute_read(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[tuple[Any, ...]]:
        """Execute a read query and return all rows."""

        def _run() -> list[tuple[Any, ...]]:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

        return await asyncio.to_thread(_run)

    async def _execute_write(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Execute a single write statement."""

        def _run() -> None:
            assert self._conn is not None
            self._conn.execute(sql, params)
            self._conn.commit()

        await asyncio.to_thread(_run)

    async def _executemany_write(
        self, sql: str, params_seq: list[tuple[Any, ...]]
    ) -> None:
        """Execute a write statement for each set of params."""

        def _run() -> None:
            assert self._conn is not None
            self._conn.executemany(sql, params_seq)
            self._conn.commit()

        await asyncio.to_thread(_run)
