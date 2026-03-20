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

    # --- Config CRUD ---

    async def load_config(self, section: str) -> dict[str, str]:
        """Return all key-value pairs for a config section."""
        rows = await self._execute_read(
            "SELECT key, value FROM config WHERE section=?", (section,)
        )
        return {row[0]: row[1] for row in rows}

    async def save_config_key(self, section: str, key: str, value: str) -> None:
        """Upsert a single config key-value in a section."""
        await self._execute_write(
            "INSERT OR REPLACE INTO config (section, key, value) VALUES (?, ?, ?)",
            (section, key, value),
        )

    async def save_config_bulk(self, section: str, data: dict[str, str]) -> None:
        """Upsert multiple config key-values in a section."""
        await self._executemany_write(
            "INSERT OR REPLACE INTO config (section, key, value) VALUES (?, ?, ?)",
            [(section, k, v) for k, v in data.items()],
        )

    # --- Device CRUD ---

    _DEVICE_COLUMNS = (
        "id", "name", "backend", "led_count", "ip", "mac",
        "device_id", "sku", "last_latency_ms", "last_seen", "extra",
    )

    async def load_devices(self) -> list[dict[str, Any]]:
        """Return all device rows as dicts."""
        rows = await self._execute_read(
            f"SELECT {', '.join(self._DEVICE_COLUMNS)} FROM devices"
        )
        return [dict(zip(self._DEVICE_COLUMNS, row)) for row in rows]

    async def upsert_device(self, data: dict[str, Any]) -> None:
        """Insert or replace a device record. Must include 'id', 'name', 'backend'."""
        cols = [c for c in self._DEVICE_COLUMNS if c in data]
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        values = tuple(data.get(c) for c in cols)
        await self._execute_write(
            f"INSERT OR REPLACE INTO devices ({col_list}) VALUES ({placeholders})",
            values,
        )

    async def delete_device(self, device_id: str) -> None:
        """Delete a device by stable ID."""
        await self._execute_write("DELETE FROM devices WHERE id=?", (device_id,))

    async def update_device_last_seen(self, device_id: str, timestamp: str) -> None:
        """Update the last_seen timestamp for a device."""
        await self._execute_write(
            "UPDATE devices SET last_seen=? WHERE id=?", (timestamp, device_id)
        )

    async def update_device_latency(self, device_id: str, latency_ms: float) -> None:
        """Update the last known latency for a device."""
        await self._execute_write(
            "UPDATE devices SET last_latency_ms=? WHERE id=?", (latency_ms, device_id)
        )

    # --- Groups CRUD ---

    async def load_groups(self) -> list[dict[str, str]]:
        """Return all groups as dicts with 'name' and 'color'."""
        rows = await self._execute_read("SELECT name, color FROM groups")
        return [{"name": row[0], "color": row[1]} for row in rows]

    async def save_group(self, name: str, color: str) -> None:
        """Insert or replace a group."""
        await self._execute_write(
            "INSERT OR REPLACE INTO groups (name, color) VALUES (?, ?)", (name, color)
        )

    async def delete_group(self, name: str) -> None:
        """Delete a group (cascades to device_groups)."""
        await self._execute_write("DELETE FROM groups WHERE name=?", (name,))

    async def load_device_groups(self) -> dict[str, list[str]]:
        """Return mapping of group_name -> list of device_ids."""
        rows = await self._execute_read(
            "SELECT dg.group_name, dg.device_id FROM device_groups dg "
            "JOIN groups g ON g.name = dg.group_name"
        )
        result: dict[str, list[str]] = {}
        for group_name, device_id in rows:
            result.setdefault(group_name, []).append(device_id)
        # Also include groups with no members
        all_groups = await self.load_groups()
        for g in all_groups:
            result.setdefault(g["name"], [])
        return result

    async def assign_device_group(self, group_name: str, device_id: str) -> None:
        """Add a device to a group (idempotent)."""
        await self._execute_write(
            "INSERT OR IGNORE INTO device_groups (group_name, device_id) VALUES (?, ?)",
            (group_name, device_id),
        )

    async def unassign_device_group(self, group_name: str, device_id: str) -> None:
        """Remove a device from a group."""
        await self._execute_write(
            "DELETE FROM device_groups WHERE group_name=? AND device_id=?",
            (group_name, device_id),
        )
