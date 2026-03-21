"""StateDB — SQLite-backed persistence layer for dj-ledfx state."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

# Directory containing SQL migration files
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def coerce_config_values(raw: dict[str, str]) -> dict[str, object]:
    """Parse string values as JSON where possible (handles int, float, bool)."""
    result: dict[str, object] = {}
    for k, v in raw.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, ValueError):
            result[k] = v
    return result


class StateDB:
    """Async SQLite persistence layer using asyncio.to_thread for all I/O.

    All database operations are executed in a thread pool to avoid blocking
    the asyncio event loop. A single persistent connection is held open for
    the lifetime of the StateDB instance.

    A lock serialises concurrent to_thread calls so two coroutines cannot
    race on the single sqlite3.Connection.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Open the database, apply migrations, and configure pragmas."""
        await asyncio.to_thread(self._open_sync)
        logger.info("StateDB opened: {}", self._path)

    def _open_sync(self) -> None:
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.commit()
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Apply unapplied SQL migration files in order.

        Each migration runs inside a single transaction: the migration SQL and
        version bump are committed atomically. executescript() issues an
        implicit COMMIT before running, so we use a manual BEGIN/COMMIT
        approach via the connection's isolation_level instead.
        """
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
                logger.warning(
                    "Skipping migration file with non-numeric prefix: {}",
                    migration_file.name,
                )
                continue

            if version <= current_version:
                continue

            logger.info("Applying migration {} (v{})", migration_file.name, version)
            sql = migration_file.read_text()
            # Run migration SQL and version bump in a single transaction.
            # executescript() implicitly commits, so we use explicit BEGIN/COMMIT
            # by temporarily switching to autocommit=False mode.
            try:
                self._conn.execute("BEGIN")
                for statement in sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        self._conn.execute(statement)
                self._conn.execute(
                    "INSERT OR REPLACE INTO config (section, key, value) VALUES (?, ?, ?)",
                    ("_meta", "schema_version", str(version)),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

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
        """Close the database connection.

        The connection is always released, even if the caller's pre-flush step
        raises. Callers should flush any DebouncedWriter before calling this.
        The lock is acquired to prevent races with in-flight operations.
        """
        async with self._lock:
            conn = self._conn
            if conn is not None:
                self._conn = None
                await asyncio.to_thread(conn.close)
                logger.info("StateDB closed: {}", self._path)

    async def _execute_read(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """Execute a read query and return all rows."""

        def _run() -> list[tuple[Any, ...]]:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

        async with self._lock:
            return await asyncio.to_thread(_run)

    async def _execute_write(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Execute a single write statement."""

        def _run() -> None:
            assert self._conn is not None
            self._conn.execute(sql, params)
            self._conn.commit()

        async with self._lock:
            await asyncio.to_thread(_run)

    async def _executemany_write(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
        """Execute a write statement for each set of params."""

        def _run() -> None:
            assert self._conn is not None
            self._conn.executemany(sql, params_seq)
            self._conn.commit()

        async with self._lock:
            await asyncio.to_thread(_run)

    async def load_config(self, section: str) -> dict[str, str]:
        """Return all key-value pairs for a config section."""
        rows = await self._execute_read(
            "SELECT key, value FROM config WHERE section=?", (section,)
        )
        return {row[0]: row[1] for row in rows}

    async def load_all_config(self) -> dict[tuple[str, str], Any]:
        """Return all config key-value pairs across all sections (excluding _meta).

        Keys are (section, key) tuples. Values are coerced to Python types
        via JSON parsing where possible (e.g. '90' -> 90, 'true' -> True).
        """
        rows = await self._execute_read(
            "SELECT section, key, value FROM config WHERE section != '_meta'"
        )
        result: dict[tuple[str, str], Any] = {}
        for section, key, value in rows:
            try:
                result[(section, key)] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                result[(section, key)] = value
        return result

    async def is_config_empty(self) -> bool:
        """Return True if there are no user config entries (only _meta or empty)."""
        rows = await self._execute_read("SELECT COUNT(*) FROM config WHERE section != '_meta'")
        return rows[0][0] == 0

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

    async def _upsert(
        self,
        table: str,
        allowed_columns: tuple[str, ...],
        data: dict[str, Any],
        pk_columns: tuple[str, ...],
    ) -> None:
        """Dynamic-column upsert using INSERT ... ON CONFLICT DO UPDATE SET.

        Uses INSERT ... ON CONFLICT(pk_columns) DO UPDATE SET ... instead of
        INSERT OR REPLACE to avoid the DELETE + INSERT semantics of OR REPLACE,
        which would fire FK cascade deletes (e.g. wiping group memberships and
        scene placements when updating a device's IP address).
        """
        cols = [c for c in allowed_columns if c in data]
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        values = tuple(data.get(c) for c in cols)
        pk_set = set(pk_columns)
        non_pk_cols = [c for c in cols if c not in pk_set]
        if non_pk_cols:
            update_clause = ", ".join(f"{c}=excluded.{c}" for c in non_pk_cols)
        else:
            # All columns are PKs — nothing to update; use DO NOTHING
            update_clause = None
        pk_col_list = ", ".join(pk_columns)
        if update_clause:
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT({pk_col_list}) DO UPDATE SET {update_clause}"
            )
        else:
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT({pk_col_list}) DO NOTHING"
            )
        await self._execute_write(sql, values)

    _DEVICE_COLUMNS = (
        "id",
        "name",
        "backend",
        "led_count",
        "ip",
        "mac",
        "device_id",
        "sku",
        "device_type",
        "last_latency_ms",
        "last_seen",
        "extra",
    )

    async def load_devices(self) -> list[dict[str, Any]]:
        """Return all device rows as dicts."""
        rows = await self._execute_read(f"SELECT {', '.join(self._DEVICE_COLUMNS)} FROM devices")
        return [dict(zip(self._DEVICE_COLUMNS, row, strict=True)) for row in rows]

    async def upsert_device(self, data: dict[str, Any]) -> None:
        """Insert or replace a device record. Must include 'id', 'name', 'backend'."""
        await self._upsert("devices", self._DEVICE_COLUMNS, data, pk_columns=("id",))

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

    _SCENE_COLUMNS = (
        "id",
        "name",
        "mapping_type",
        "mapping_params",
        "effect_mode",
        "effect_source",
        "is_active",
    )

    _PLACEMENT_COLUMNS = (
        "scene_id",
        "device_id",
        "position_x",
        "position_y",
        "position_z",
        "geometry_type",
        "direction_x",
        "direction_y",
        "direction_z",
        "length",
        "width",
        "rows",
        "cols",
    )

    async def load_scenes(self) -> list[dict[str, Any]]:
        """Return all scene rows as dicts."""
        rows = await self._execute_read(f"SELECT {', '.join(self._SCENE_COLUMNS)} FROM scenes")
        return [dict(zip(self._SCENE_COLUMNS, row, strict=True)) for row in rows]

    async def load_scene_by_id(self, scene_id: str) -> dict[str, Any] | None:
        """Return a single scene row by ID, or None if not found."""
        rows = await self._execute_read(
            f"SELECT {', '.join(self._SCENE_COLUMNS)} FROM scenes WHERE id=?",
            (scene_id,),
        )
        if not rows:
            return None
        return dict(zip(self._SCENE_COLUMNS, rows[0], strict=True))

    async def device_exists(self, device_id: str) -> bool:
        """Return True if a device with the given ID exists."""
        rows = await self._execute_read("SELECT 1 FROM devices WHERE id=? LIMIT 1", (device_id,))
        return bool(rows)

    async def save_scene(self, data: dict[str, Any]) -> None:
        """Insert or replace a scene record. Must include 'id', 'name'."""
        await self._upsert("scenes", self._SCENE_COLUMNS, data, pk_columns=("id",))

    async def delete_scene(self, scene_id: str) -> None:
        """Delete a scene and cascade to placements and effect state."""
        await self._execute_write("DELETE FROM scenes WHERE id=?", (scene_id,))

    async def set_scene_active(self, scene_id: str) -> None:
        """Set a single scene as active without touching other scenes.

        Multiple scenes may run concurrently; this method only flips the given
        scene to is_active=1.  Use set_scene_inactive() to deactivate a scene.
        """
        await self._execute_write(
            "UPDATE scenes SET is_active=1 WHERE id=?", (scene_id,)
        )

    async def set_scene_inactive(self, scene_id: str) -> None:
        """Deactivate a single scene without affecting other scenes."""
        await self._execute_write(
            "UPDATE scenes SET is_active=0 WHERE id=?", (scene_id,)
        )

    async def load_scene_effect_state(self, scene_id: str) -> dict[str, str] | None:
        """Return effect class + params for a scene, or None if unset."""
        rows = await self._execute_read(
            "SELECT effect_class, params FROM scene_effect_state WHERE scene_id=?",
            (scene_id,),
        )
        if not rows:
            return None
        return {"effect_class": rows[0][0], "params": rows[0][1]}

    async def save_scene_effect_state(self, scene_id: str, effect_class: str, params: str) -> None:
        """Upsert the effect state for a scene."""
        await self._execute_write(
            "INSERT OR REPLACE INTO scene_effect_state (scene_id, effect_class, params) "
            "VALUES (?, ?, ?)",
            (scene_id, effect_class, params),
        )

    async def load_scene_placements(self, scene_id: str) -> list[dict[str, Any]]:
        """Return all placements for a scene as dicts."""
        rows = await self._execute_read(
            f"SELECT {', '.join(self._PLACEMENT_COLUMNS)} FROM scene_placements WHERE scene_id=?",
            (scene_id,),
        )
        return [dict(zip(self._PLACEMENT_COLUMNS, row, strict=True)) for row in rows]

    async def save_placement(self, data: dict[str, Any]) -> None:
        """Insert or replace a placement. Must include 'scene_id' and 'device_id'."""
        await self._upsert(
            "scene_placements",
            self._PLACEMENT_COLUMNS,
            data,
            pk_columns=("scene_id", "device_id"),
        )

    async def delete_placement(self, scene_id: str, device_id: str) -> None:
        """Remove a device from a scene's placement list."""
        await self._execute_write(
            "DELETE FROM scene_placements WHERE scene_id=? AND device_id=?",
            (scene_id, device_id),
        )

    async def load_presets(self) -> list[dict[str, str]]:
        """Return all presets as dicts."""
        rows = await self._execute_read("SELECT name, effect_class, params FROM presets")
        return [{"name": row[0], "effect_class": row[1], "params": row[2]} for row in rows]

    async def save_preset(self, name: str, effect_class: str, params: str) -> None:
        """Insert or replace a preset."""
        await self._execute_write(
            "INSERT OR REPLACE INTO presets (name, effect_class, params) VALUES (?, ?, ?)",
            (name, effect_class, params),
        )

    async def delete_preset(self, name: str) -> None:
        """Delete a preset by name."""
        await self._execute_write("DELETE FROM presets WHERE name=?", (name,))
