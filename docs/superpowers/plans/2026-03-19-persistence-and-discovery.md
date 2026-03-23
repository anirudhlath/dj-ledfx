# Persistence & Robust Device Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ephemeral in-memory state with SQLite persistence, add multi-scene support, and implement robust multi-wave device discovery with offline/reconnect handling.

**Architecture:** A new `persistence/` package owns the SQLite database (`state.db`) with WAL mode, schema migrations, and debounced writes. `DeviceInfo` gains stable IDs for cross-session matching. `GhostAdapter` represents offline devices. `ScenePipeline` bundles per-scene effect/buffer/compositor. `DiscoveryOrchestrator` replaces ad-hoc discovery with multi-wave subnet scanning. The `LookaheadScheduler` switches from positional arrays to a `dict[str, DeviceSendState]` for dynamic device add/remove. `main.py` startup loads persisted state before discovery runs in background.

**Tech Stack:** Python 3.12, SQLite (stdlib `sqlite3`), `asyncio.to_thread()` for DB I/O, `pytest` + `pytest-asyncio`, existing FastAPI/Pydantic web layer.

**Spec:** `docs/superpowers/specs/2026-03-19-persistence-and-discovery-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/dj_ledfx/persistence/__init__.py` | Package init |
| `src/dj_ledfx/persistence/state_db.py` | `StateDB` class: SQLite connection, schema init, migrations, all load/save methods, debounce logic |
| `src/dj_ledfx/persistence/migrations/001_initial.sql` | Initial schema (config, devices, groups, device_groups, scenes, scene_effect_state, scene_placements, presets) |
| `src/dj_ledfx/persistence/toml_io.py` | TOML import/export marshaling (DB ↔ structured TOML, display name ↔ stable ID resolution) |
| `src/dj_ledfx/devices/ghost.py` | `GhostAdapter(DeviceAdapter)`: offline placeholder with stored `DeviceInfo`/`led_count`, `is_connected=False` |
| `src/dj_ledfx/devices/discovery.py` | `DiscoveryOrchestrator`: backend lifecycle, multi-wave scanning, subnet probing, reconnect loop |
| `src/dj_ledfx/spatial/pipeline.py` | `ScenePipeline` dataclass: bundles `EffectDeck`, `RingBuffer`, `SpatialCompositor`, device list, mapping per active scene |
| `tests/persistence/__init__.py` | Test package init |
| `tests/persistence/test_state_db.py` | StateDB unit tests (schema, CRUD, migrations, debounce) |
| `tests/persistence/test_toml_io.py` | TOML import/export round-trip tests |
| `tests/devices/test_ghost.py` | GhostAdapter tests |
| `tests/devices/__init__.py` | Test package init |
| `tests/devices/test_discovery.py` | DiscoveryOrchestrator tests |
| `tests/spatial/test_pipeline.py` | ScenePipeline tests |

### Modified Files

| File | Changes |
|------|---------|
| `src/dj_ledfx/types.py` | `DeviceInfo` gains `mac: str \| None = None`, `stable_id: str \| None = None` |
| `src/dj_ledfx/config.py` | Add `DiscoveryConfig` dataclass, add to `AppConfig`; DB config helpers (`_load_config_from_db`, `_save_config_to_db`) live in `main.py` |
| `src/dj_ledfx/events.py` | Add event dataclasses: `DeviceDiscoveredEvent`, `DeviceOnlineEvent`, `DeviceOfflineEvent`, `DiscoveryWaveCompleteEvent`, `DiscoveryCompleteEvent`, `SceneActivatedEvent`, `SceneDeactivatedEvent` |
| `src/dj_ledfx/devices/manager.py` | `ManagedDevice` gains `status` field; add `promote_device()`, `demote_device()`, `remove_device()`, `get_by_stable_id()` |
| `src/dj_ledfx/devices/lifx/discovery.py` | Pass `mac`/`stable_id` to `DeviceInfo` construction |
| `src/dj_ledfx/devices/govee/segment.py` | Pass `stable_id` to `DeviceInfo` in `device_info` property |
| `src/dj_ledfx/devices/govee/solid.py` | Pass `stable_id` to `DeviceInfo` in `device_info` property |
| `src/dj_ledfx/devices/openrgb_backend.py` | Pass `stable_id` to `DeviceInfo`; add 5s connection timeout, retry |
| `src/dj_ledfx/devices/lifx/transport.py` | Add `unicast_sweep()` method, increase GetVersion timeout to 500ms, broadcast 3x per wave |
| `src/dj_ledfx/devices/govee/transport.py` | Add `unicast_sweep()` method, port 4002 bind retry with backoff, increase window to 10s |
| `src/dj_ledfx/effects/engine.py` | `EffectEngine` gains `pipelines: list[ScenePipeline]`, iterates pipelines in `tick()` |
| `src/dj_ledfx/effects/deck.py` | Add optional `on_change` callback for auto-save |
| `src/dj_ledfx/effects/presets.py` | `PresetStore` backed by `StateDB` instead of TOML file |
| `src/dj_ledfx/scheduling/scheduler.py` | Replace positional lists with `_device_state: dict[str, DeviceSendState]`; add `add_device()`/`remove_device()`; per-device pipeline reference |
| `src/dj_ledfx/web/app.py` | `create_app()` accepts `StateDB`; store on `app.state` |
| `src/dj_ledfx/web/router_config.py` | Read/write config via StateDB |
| `src/dj_ledfx/web/router_devices.py` | `POST /devices/scan` replaces `POST /devices/discover`; device status in responses; `DELETE`/`PUT` device endpoints |
| `src/dj_ledfx/web/router_effects.py` | Effect changes trigger auto-save via deck callback |
| `src/dj_ledfx/web/router_scene.py` | Rewrite for multi-scene CRUD, activation/deactivation, per-scene effect/mapping |
| `src/dj_ledfx/web/ws.py` | Device stats include `status` field |
| `src/dj_ledfx/main.py` | New startup flow: DB init → load state → build ScenePipelines → background discovery → reconnect loop |
| `tests/test_events.py` | Tests for new event types |
| `tests/test_config.py` | Tests for `DiscoveryConfig`, `load_config_from_db()` |
| `tests/scheduling/test_scheduler.py` | Tests for dict-based device state, dynamic add/remove |
| `tests/effects/test_engine.py` | Tests for multi-pipeline rendering |
| `tests/effects/test_deck.py` | Tests for `on_change` callback |
| `tests/effects/test_presets.py` | Tests for DB-backed PresetStore |
| `tests/web/test_router_scene.py` | Tests for multi-scene API |
| `tests/web/test_router_devices.py` | Tests for scan endpoint, device status |
| `tests/web/test_router_config.py` | Tests for DB-backed config |

---

## Phase 1: Foundation (Types, Events, StateDB, GhostAdapter)

### Task 1: DeviceInfo Stable Identity Fields

**Files:**
- Modify: `src/dj_ledfx/types.py:11-16`
- Test: `tests/test_types.py` (create)

- [ ] **Step 1: Write tests for new DeviceInfo fields**

Create `tests/test_types.py`:

```python
"""Tests for types module."""
from dj_ledfx.types import DeviceInfo


def test_device_info_defaults_backward_compatible():
    """Existing 4-arg construction still works."""
    info = DeviceInfo(name="Test", device_type="test", led_count=10, address="1.2.3.4:80")
    assert info.mac is None
    assert info.stable_id is None


def test_device_info_with_mac_and_stable_id():
    info = DeviceInfo(
        name="LIFX Strip (192.168.1.5)",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.5:56700",
        mac="d073d5aabbcc",
        stable_id="lifx:d073d5aabbcc",
    )
    assert info.mac == "d073d5aabbcc"
    assert info.stable_id == "lifx:d073d5aabbcc"


def test_device_info_frozen():
    info = DeviceInfo(name="Test", device_type="test", led_count=10, address="1.2.3.4:80")
    try:
        info.name = "Changed"  # type: ignore[misc]
        assert False, "Should have raised"
    except AttributeError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL — `DeviceInfo` doesn't accept `mac`/`stable_id` kwargs

- [ ] **Step 3: Add fields to DeviceInfo**

In `src/dj_ledfx/types.py`, add two fields with defaults after `address`:

```python
@dataclass(frozen=True, slots=True)
class DeviceInfo:
    name: str
    device_type: str
    led_count: int
    address: str
    mac: str | None = None
    stable_id: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_types.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `uv run pytest -x -v`
Expected: All existing tests pass (frozen dataclass with defaults is backward-compatible)

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/types.py tests/test_types.py
git commit -m "feat: add mac and stable_id fields to DeviceInfo"
```

---

### Task 2: New Event Types

**Files:**
- Modify: `src/dj_ledfx/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write tests for new event types**

Append to `tests/test_events.py`:

```python
from dj_ledfx.events import (
    DeviceDiscoveredEvent,
    DeviceOfflineEvent,
    DeviceOnlineEvent,
    DiscoveryCompleteEvent,
    DiscoveryWaveCompleteEvent,
    SceneActivatedEvent,
    SceneDeactivatedEvent,
)


def test_device_discovered_event():
    e = DeviceDiscoveredEvent(stable_id="lifx:aabb", name="LIFX Strip")
    assert e.stable_id == "lifx:aabb"
    assert e.name == "LIFX Strip"


def test_device_online_event():
    e = DeviceOnlineEvent(stable_id="govee:1234", name="Govee H6159")
    assert e.stable_id == "govee:1234"


def test_device_offline_event():
    e = DeviceOfflineEvent(stable_id="lifx:aabb", name="LIFX Strip")
    assert e.stable_id == "lifx:aabb"


def test_discovery_wave_complete_event():
    e = DiscoveryWaveCompleteEvent(wave=2, devices_found=5)
    assert e.wave == 2
    assert e.devices_found == 5


def test_discovery_complete_event():
    e = DiscoveryCompleteEvent(total_devices=8)
    assert e.total_devices == 8


def test_scene_activated_event():
    e = SceneActivatedEvent(scene_id="dj-booth")
    assert e.scene_id == "dj-booth"


def test_scene_deactivated_event():
    e = SceneDeactivatedEvent(scene_id="dj-booth")
    assert e.scene_id == "dj-booth"


def test_event_bus_emits_new_event_types(event_bus):
    received = []
    event_bus.subscribe(DeviceDiscoveredEvent, received.append)
    event_bus.emit(DeviceDiscoveredEvent(stable_id="lifx:aa", name="Test"))
    assert len(received) == 1
    assert received[0].stable_id == "lifx:aa"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_events.py -v -k "device_discovered or device_online or device_offline or discovery_wave or discovery_complete or scene_activated or scene_deactivated or new_event_types"`
Expected: FAIL — import errors (event classes don't exist yet)

- [ ] **Step 3: Add event dataclasses**

In `src/dj_ledfx/events.py`, add after `BeatEvent`:

```python
@dataclass(frozen=True, slots=True)
class DeviceDiscoveredEvent:
    stable_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DeviceOnlineEvent:
    stable_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DeviceOfflineEvent:
    stable_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DiscoveryWaveCompleteEvent:
    wave: int
    devices_found: int


@dataclass(frozen=True, slots=True)
class DiscoveryCompleteEvent:
    total_devices: int


@dataclass(frozen=True, slots=True)
class SceneActivatedEvent:
    scene_id: str


@dataclass(frozen=True, slots=True)
class SceneDeactivatedEvent:
    scene_id: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/events.py tests/test_events.py
git commit -m "feat: add discovery, device lifecycle, and scene event types"
```

---

### Task 3: DiscoveryConfig Dataclass

**Files:**
- Modify: `src/dj_ledfx/config.py:86-100`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write tests for DiscoveryConfig**

Add to `tests/test_config.py`:

```python
from dj_ledfx.config import AppConfig, DiscoveryConfig


def test_discovery_config_defaults():
    dc = DiscoveryConfig()
    assert dc.waves == 3
    assert dc.wave_interval_s == 5.0
    assert dc.unicast_concurrency == 50
    assert dc.unicast_timeout_s == 0.5
    assert dc.subnet_mask == 24
    assert dc.reconnect_interval_s == 30.0


def test_app_config_has_discovery():
    config = AppConfig()
    assert isinstance(config.discovery, DiscoveryConfig)
    assert config.discovery.waves == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py::test_discovery_config_defaults tests/test_config.py::test_app_config_has_discovery -v`
Expected: FAIL — `DiscoveryConfig` does not exist

- [ ] **Step 3: Add DiscoveryConfig**

In `src/dj_ledfx/config.py`, add after `DevicesConfig`:

```python
@dataclass
class DiscoveryConfig:
    waves: int = 3
    wave_interval_s: float = 5.0
    unicast_concurrency: int = 50
    unicast_timeout_s: float = 0.5
    subnet_mask: int = 24
    reconnect_interval_s: float = 30.0
```

Add to `AppConfig` (after `devices` field, before `scene_config`):

```python
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
```

In `load_config()`, add before the `scene_config` line:

```python
    discovery = DiscoveryConfig(
        **_filter_fields(DiscoveryConfig, data.get("discovery", {}))
    )
```

And pass `discovery=discovery` to the `AppConfig(...)` constructor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py
git commit -m "feat: add DiscoveryConfig dataclass to AppConfig"
```

---

### Task 4: GhostAdapter

**Files:**
- Create: `src/dj_ledfx/devices/ghost.py`
- Test: `tests/devices/test_ghost.py`

- [ ] **Step 1: Create test directory**

```bash
mkdir -p tests/devices && touch tests/devices/__init__.py
```

- [ ] **Step 2: Write tests for GhostAdapter**

Create `tests/devices/test_ghost.py`:

```python
"""Tests for GhostAdapter — offline device placeholder."""
import numpy as np
import pytest

from dj_ledfx.devices.ghost import GhostAdapter
from dj_ledfx.types import DeviceInfo


@pytest.fixture
def ghost():
    info = DeviceInfo(
        name="LIFX Strip (192.168.1.5)",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.5:56700",
        mac="d073d5aabbcc",
        stable_id="lifx:d073d5aabbcc",
    )
    return GhostAdapter(device_info=info, led_count=60)


def test_ghost_device_info(ghost):
    assert ghost.device_info.name == "LIFX Strip (192.168.1.5)"
    assert ghost.device_info.stable_id == "lifx:d073d5aabbcc"


def test_ghost_is_not_connected(ghost):
    assert ghost.is_connected is False


def test_ghost_led_count(ghost):
    assert ghost.led_count == 60


def test_ghost_does_not_support_latency_probing(ghost):
    assert ghost.supports_latency_probing is False


@pytest.mark.asyncio
async def test_ghost_connect_is_noop(ghost):
    await ghost.connect()  # should not raise
    assert ghost.is_connected is False  # still offline


@pytest.mark.asyncio
async def test_ghost_disconnect_is_noop(ghost):
    await ghost.disconnect()  # should not raise


@pytest.mark.asyncio
async def test_ghost_send_frame_raises(ghost):
    colors = np.zeros((60, 3), dtype=np.uint8)
    with pytest.raises(ConnectionError, match="offline"):
        await ghost.send_frame(colors)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_ghost.py -v`
Expected: FAIL — `dj_ledfx.devices.ghost` does not exist

- [ ] **Step 4: Implement GhostAdapter**

Create `src/dj_ledfx/devices/ghost.py`:

```python
"""GhostAdapter — placeholder for offline devices."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.types import DeviceInfo


class GhostAdapter(DeviceAdapter):
    """Concrete DeviceAdapter for devices that are registered but offline.

    Provides stored device_info/led_count, is_connected=False.
    send_frame() raises ConnectionError. connect()/disconnect() are no-ops.
    Avoids null-safety refactoring across scheduler, web, and all code
    that accesses device.adapter.*.
    """

    supports_latency_probing = False

    def __init__(self, device_info: DeviceInfo, led_count: int) -> None:
        self._device_info = device_info
        self._led_count = led_count

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return False

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        pass  # offline — nothing to connect to

    async def disconnect(self) -> None:
        pass  # offline — nothing to disconnect from

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        raise ConnectionError(
            f"Device '{self._device_info.name}' is offline — cannot send frames"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/devices/test_ghost.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/ghost.py tests/devices/__init__.py tests/devices/test_ghost.py
git commit -m "feat: add GhostAdapter for offline device placeholders"
```

---

### Task 5: StateDB — Schema and Connection

**Files:**
- Create: `src/dj_ledfx/persistence/__init__.py`
- Create: `src/dj_ledfx/persistence/state_db.py`
- Create: `src/dj_ledfx/persistence/migrations/001_initial.sql`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Create directories**

```bash
mkdir -p src/dj_ledfx/persistence/migrations tests/persistence
touch src/dj_ledfx/persistence/__init__.py tests/persistence/__init__.py
```

- [ ] **Step 2: Write the initial migration SQL**

Create `src/dj_ledfx/persistence/migrations/001_initial.sql`:

```sql
-- Initial schema for dj-ledfx state database

CREATE TABLE config (
    section TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (section, key)
);

CREATE TABLE devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    backend TEXT NOT NULL,
    led_count INTEGER,
    ip TEXT,
    mac TEXT,
    device_id TEXT,
    sku TEXT,
    last_latency_ms REAL,
    last_seen TEXT,
    extra TEXT
);

CREATE TABLE groups (
    name TEXT PRIMARY KEY,
    color TEXT NOT NULL DEFAULT '#888888'
);

CREATE TABLE device_groups (
    group_name TEXT NOT NULL REFERENCES groups(name) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    PRIMARY KEY (group_name, device_id)
);

CREATE TABLE scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mapping_type TEXT NOT NULL DEFAULT 'linear',
    mapping_params TEXT,
    effect_mode TEXT NOT NULL DEFAULT 'independent',
    effect_source TEXT REFERENCES scenes(id) ON DELETE SET NULL,
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE scene_effect_state (
    scene_id TEXT PRIMARY KEY REFERENCES scenes(id) ON DELETE CASCADE,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL
);

CREATE TABLE scene_placements (
    scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    position_x REAL NOT NULL DEFAULT 0,
    position_y REAL NOT NULL DEFAULT 0,
    position_z REAL NOT NULL DEFAULT 0,
    geometry_type TEXT NOT NULL DEFAULT 'point',
    direction_x REAL,
    direction_y REAL,
    direction_z REAL,
    length REAL,
    width REAL,
    rows INTEGER,
    cols INTEGER,
    PRIMARY KEY (scene_id, device_id)
);

CREATE TABLE presets (
    name TEXT PRIMARY KEY,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL
);
```

- [ ] **Step 3: Write tests for StateDB init and schema**

Create `tests/persistence/test_state_db.py`:

```python
"""Tests for StateDB — SQLite persistence layer."""
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()
    yield state_db
    await state_db.close()


@pytest.mark.asyncio
async def test_creates_db_file(tmp_path):
    db_path = tmp_path / "state.db"
    assert not db_path.exists()
    state_db = StateDB(db_path)
    await state_db.open()
    assert db_path.exists()
    await state_db.close()


@pytest.mark.asyncio
async def test_schema_version_is_1(db):
    version = await db.get_schema_version()
    assert version == 1


@pytest.mark.asyncio
async def test_wal_mode_enabled(db):
    mode = await db._execute_read("PRAGMA journal_mode")
    assert mode[0][0] == "wal"


@pytest.mark.asyncio
async def test_foreign_keys_enabled(db):
    result = await db._execute_read("PRAGMA foreign_keys")
    assert result[0][0] == 1


@pytest.mark.asyncio
async def test_tables_created(db):
    rows = await db._execute_read(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [r[0] for r in rows]
    expected = [
        "config", "device_groups", "devices", "groups",
        "presets", "scene_effect_state", "scene_placements", "scenes",
    ]
    assert table_names == expected


@pytest.mark.asyncio
async def test_idempotent_open(tmp_path):
    """Opening an already-initialized DB does not error."""
    db_path = tmp_path / "state.db"
    db1 = StateDB(db_path)
    await db1.open()
    await db1.close()

    db2 = StateDB(db_path)
    await db2.open()
    version = await db2.get_schema_version()
    assert version == 1
    await db2.close()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 5: Implement StateDB shell (open/close/schema)**

Create `src/dj_ledfx/persistence/state_db.py`:

```python
"""StateDB — SQLite persistence layer for dj-ledfx state."""
from __future__ import annotations

import asyncio
import importlib.resources
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class StateDB:
    """Owns the SQLite connection. All I/O wrapped in asyncio.to_thread()."""

    CURRENT_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    async def open(self) -> None:
        self._conn = await asyncio.to_thread(self._open_sync)

    def _open_sync(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < self.CURRENT_VERSION:
            self._run_migrations(conn, version)
        return conn

    def _run_migrations(self, conn: sqlite3.Connection, from_version: int) -> None:
        migrations_dir = Path(__file__).parent / "migrations"
        for target in range(from_version + 1, self.CURRENT_VERSION + 1):
            migration_file = migrations_dir / f"{target:03d}_initial.sql"
            if not migration_file.exists():
                raise FileNotFoundError(f"Migration file not found: {migration_file}")
            sql = migration_file.read_text()
            conn.executescript(sql)
            logger.info("Applied migration {}", migration_file.name)
        conn.execute(f"PRAGMA user_version={self.CURRENT_VERSION}")
        conn.commit()

    async def close(self) -> None:
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    async def get_schema_version(self) -> int:
        rows = await self._execute_read("PRAGMA user_version")
        return rows[0][0]

    async def _execute_read(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        assert self._conn is not None

        def _read() -> list[Any]:
            assert self._conn is not None
            return self._conn.execute(sql, params).fetchall()

        return await asyncio.to_thread(_read)

    async def _execute_write(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        assert self._conn is not None

        def _write() -> None:
            assert self._conn is not None
            self._conn.execute(sql, params)
            self._conn.commit()

        await asyncio.to_thread(_write)

    async def _executemany_write(
        self, sql: str, param_list: list[tuple[Any, ...]]
    ) -> None:
        assert self._conn is not None

        def _write() -> None:
            assert self._conn is not None
            self._conn.executemany(sql, param_list)
            self._conn.commit()

        await asyncio.to_thread(_write)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/persistence/ tests/persistence/
git commit -m "feat: add StateDB with schema init and migrations"
```

---

### Task 6: StateDB — Config CRUD

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for config load/save**

Append to `tests/persistence/test_state_db.py`:

```python
@pytest.mark.asyncio
async def test_save_and_load_config_key(db):
    await db.save_config_key("engine", "fps", 120)
    result = await db.load_config()
    assert result[("engine", "fps")] == 120


@pytest.mark.asyncio
async def test_save_config_key_upserts(db):
    await db.save_config_key("engine", "fps", 60)
    await db.save_config_key("engine", "fps", 120)
    result = await db.load_config()
    assert result[("engine", "fps")] == 120


@pytest.mark.asyncio
async def test_load_config_empty(db):
    result = await db.load_config()
    assert result == {}


@pytest.mark.asyncio
async def test_save_config_key_complex_value(db):
    await db.save_config_key("web", "cors_origins", ["http://localhost:5173"])
    result = await db.load_config()
    assert result[("web", "cors_origins")] == ["http://localhost:5173"]


@pytest.mark.asyncio
async def test_save_config_bulk(db):
    pairs = [
        ("engine", "fps", 60),
        ("engine", "max_lookahead_ms", 1000),
        ("network", "interface", "auto"),
    ]
    await db.save_config_bulk(pairs)
    result = await db.load_config()
    assert result[("engine", "fps")] == 60
    assert result[("network", "interface")] == "auto"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "config"`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement config methods**

Add to `StateDB`:

```python
    # ── Config ──────────────────────────────────────────────────

    async def load_config(self) -> dict[tuple[str, str], Any]:
        """Load all config key-value pairs. Returns {(section, key): value}."""
        rows = await self._execute_read("SELECT section, key, value FROM config")
        return {(section, key): json.loads(value) for section, key, value in rows}

    async def save_config_key(self, section: str, key: str, value: Any) -> None:
        await self._execute_write(
            "INSERT OR REPLACE INTO config (section, key, value) VALUES (?, ?, ?)",
            (section, key, json.dumps(value)),
        )

    async def save_config_bulk(
        self, triples: list[tuple[str, str, Any]]
    ) -> None:
        params = [(s, k, json.dumps(v)) for s, k, v in triples]
        await self._executemany_write(
            "INSERT OR REPLACE INTO config (section, key, value) VALUES (?, ?, ?)",
            params,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "config"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add config CRUD to StateDB"
```

---

### Task 7: StateDB — Device CRUD

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for device operations**

Append to `tests/persistence/test_state_db.py`:

```python
@pytest.mark.asyncio
async def test_upsert_and_load_device(db):
    await db.upsert_device(
        id="lifx:aabbcc",
        name="LIFX Strip",
        backend="lifx",
        led_count=60,
        ip="192.168.1.5",
        mac="aabbcc",
    )
    devices = await db.load_devices()
    assert len(devices) == 1
    d = devices[0]
    assert d["id"] == "lifx:aabbcc"
    assert d["name"] == "LIFX Strip"
    assert d["backend"] == "lifx"
    assert d["led_count"] == 60
    assert d["ip"] == "192.168.1.5"
    assert d["mac"] == "aabbcc"


@pytest.mark.asyncio
async def test_upsert_device_updates_existing(db):
    await db.upsert_device(id="lifx:aa", name="Old", backend="lifx", ip="1.1.1.1")
    await db.upsert_device(id="lifx:aa", name="New", backend="lifx", ip="2.2.2.2")
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "New"
    assert devices[0]["ip"] == "2.2.2.2"


@pytest.mark.asyncio
async def test_delete_device(db):
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    await db.delete_device("lifx:aa")
    devices = await db.load_devices()
    assert len(devices) == 0


@pytest.mark.asyncio
async def test_update_device_last_seen(db):
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    await db.update_device_last_seen("lifx:aa", "2026-03-19T12:00:00Z")
    devices = await db.load_devices()
    assert devices[0]["last_seen"] == "2026-03-19T12:00:00Z"


@pytest.mark.asyncio
async def test_update_device_latency(db):
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    await db.update_device_latency("lifx:aa", 48.5)
    devices = await db.load_devices()
    assert devices[0]["last_latency_ms"] == 48.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "device"`
Expected: FAIL

- [ ] **Step 3: Implement device methods**

Add to `StateDB`:

```python
    # ── Devices ─────────────────────────────────────────────────

    async def load_devices(self) -> list[dict[str, Any]]:
        rows = await self._execute_read(
            "SELECT id, name, backend, led_count, ip, mac, device_id, sku, "
            "last_latency_ms, last_seen, extra FROM devices"
        )
        columns = [
            "id", "name", "backend", "led_count", "ip", "mac", "device_id",
            "sku", "last_latency_ms", "last_seen", "extra",
        ]
        return [dict(zip(columns, row)) for row in rows]

    async def upsert_device(
        self,
        id: str,
        name: str,
        backend: str,
        led_count: int | None = None,
        ip: str | None = None,
        mac: str | None = None,
        device_id: str | None = None,
        sku: str | None = None,
        last_latency_ms: float | None = None,
        last_seen: str | None = None,
        extra: str | None = None,
    ) -> None:
        await self._execute_write(
            """INSERT INTO devices (id, name, backend, led_count, ip, mac, device_id,
                                    sku, last_latency_ms, last_seen, extra)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, backend=excluded.backend,
                   led_count=COALESCE(excluded.led_count, devices.led_count),
                   ip=COALESCE(excluded.ip, devices.ip),
                   mac=COALESCE(excluded.mac, devices.mac),
                   device_id=COALESCE(excluded.device_id, devices.device_id),
                   sku=COALESCE(excluded.sku, devices.sku),
                   last_latency_ms=COALESCE(excluded.last_latency_ms, devices.last_latency_ms),
                   last_seen=COALESCE(excluded.last_seen, devices.last_seen),
                   extra=COALESCE(excluded.extra, devices.extra)""",
            (id, name, backend, led_count, ip, mac, device_id, sku,
             last_latency_ms, last_seen, extra),
        )

    async def delete_device(self, device_id: str) -> None:
        await self._execute_write("DELETE FROM devices WHERE id = ?", (device_id,))

    async def update_device_last_seen(self, device_id: str, timestamp: str) -> None:
        await self._execute_write(
            "UPDATE devices SET last_seen = ? WHERE id = ?", (timestamp, device_id)
        )

    async def update_device_latency(self, device_id: str, latency_ms: float) -> None:
        await self._execute_write(
            "UPDATE devices SET last_latency_ms = ? WHERE id = ?",
            (latency_ms, device_id),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "device"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add device CRUD to StateDB"
```

---

### Task 8: StateDB — Groups CRUD

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for group operations**

Append to `tests/persistence/test_state_db.py`:

```python
@pytest.mark.asyncio
async def test_save_and_load_group(db):
    await db.save_group("main-stage", "#ff6600")
    groups = await db.load_groups()
    assert groups == {"main-stage": "#ff6600"}


@pytest.mark.asyncio
async def test_delete_group(db):
    await db.save_group("test", "#000000")
    await db.delete_group("test")
    groups = await db.load_groups()
    assert groups == {}


@pytest.mark.asyncio
async def test_assign_device_to_group(db):
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    await db.save_group("stage", "#ff0000")
    await db.assign_device_group("stage", "lifx:aa")
    memberships = await db.load_device_groups()
    assert memberships == {"lifx:aa": "stage"}


@pytest.mark.asyncio
async def test_delete_group_cascades_memberships(db):
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    await db.save_group("stage", "#ff0000")
    await db.assign_device_group("stage", "lifx:aa")
    await db.delete_group("stage")
    memberships = await db.load_device_groups()
    assert memberships == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "group"`
Expected: FAIL

- [ ] **Step 3: Implement group methods**

Add to `StateDB`:

```python
    # ── Groups ──────────────────────────────────────────────────

    async def load_groups(self) -> dict[str, str]:
        """Returns {group_name: color}."""
        rows = await self._execute_read("SELECT name, color FROM groups")
        return {name: color for name, color in rows}

    async def save_group(self, name: str, color: str) -> None:
        await self._execute_write(
            "INSERT OR REPLACE INTO groups (name, color) VALUES (?, ?)",
            (name, color),
        )

    async def delete_group(self, name: str) -> None:
        await self._execute_write("DELETE FROM groups WHERE name = ?", (name,))

    async def load_device_groups(self) -> dict[str, str]:
        """Returns {device_id: group_name}. One group per device."""
        rows = await self._execute_read(
            "SELECT device_id, group_name FROM device_groups"
        )
        return {device_id: group_name for device_id, group_name in rows}

    async def assign_device_group(self, group_name: str, device_id: str) -> None:
        # Remove any existing assignment for this device first
        await self._execute_write(
            "DELETE FROM device_groups WHERE device_id = ?", (device_id,)
        )
        await self._execute_write(
            "INSERT INTO device_groups (group_name, device_id) VALUES (?, ?)",
            (group_name, device_id),
        )

    async def unassign_device_group(self, device_id: str) -> None:
        await self._execute_write(
            "DELETE FROM device_groups WHERE device_id = ?", (device_id,)
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "group"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add group CRUD to StateDB"
```

---

### Task 9: StateDB — Scenes CRUD

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for scene operations**

Append to `tests/persistence/test_state_db.py`:

```python
@pytest.mark.asyncio
async def test_save_and_load_scene(db):
    await db.save_scene(
        id="dj-booth",
        name="DJ Booth",
        mapping_type="linear",
        mapping_params=None,
        effect_mode="independent",
        effect_source=None,
        is_active=True,
    )
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    s = scenes[0]
    assert s["id"] == "dj-booth"
    assert s["name"] == "DJ Booth"
    assert s["mapping_type"] == "linear"
    assert s["is_active"] == 1


@pytest.mark.asyncio
async def test_save_scene_upserts(db):
    await db.save_scene(id="s1", name="Old", mapping_type="linear")
    await db.save_scene(id="s1", name="New", mapping_type="radial")
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["name"] == "New"
    assert scenes[0]["mapping_type"] == "radial"


@pytest.mark.asyncio
async def test_delete_scene(db):
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    await db.delete_scene("s1")
    scenes = await db.load_scenes()
    assert len(scenes) == 0


@pytest.mark.asyncio
async def test_set_scene_active(db):
    await db.save_scene(id="s1", name="Test", mapping_type="linear", is_active=False)
    await db.set_scene_active("s1", True)
    scenes = await db.load_scenes()
    assert scenes[0]["is_active"] == 1


@pytest.mark.asyncio
async def test_save_and_load_scene_effect_state(db):
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    await db.save_scene_effect_state("s1", "beat_pulse", {"gamma": 2.5, "palette": ["#ff0000"]})
    state = await db.load_scene_effect_state("s1")
    assert state is not None
    assert state["effect_class"] == "beat_pulse"
    assert state["params"]["gamma"] == 2.5


@pytest.mark.asyncio
async def test_load_scene_effect_state_missing(db):
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    state = await db.load_scene_effect_state("s1")
    assert state is None


@pytest.mark.asyncio
async def test_save_and_load_placement(db):
    await db.upsert_device(id="lifx:aa", name="Strip", backend="lifx", led_count=60)
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    await db.save_placement(
        scene_id="s1",
        device_id="lifx:aa",
        position_x=1.0, position_y=2.0, position_z=3.0,
        geometry_type="strip",
        direction_x=1.0, direction_y=0.0, direction_z=0.0,
        length=1.5,
    )
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 1
    p = placements[0]
    assert p["device_id"] == "lifx:aa"
    assert p["position_x"] == 1.0
    assert p["geometry_type"] == "strip"
    assert p["length"] == 1.5


@pytest.mark.asyncio
async def test_delete_placement(db):
    await db.upsert_device(id="lifx:aa", name="Strip", backend="lifx")
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    await db.save_placement(scene_id="s1", device_id="lifx:aa")
    await db.delete_placement("s1", "lifx:aa")
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 0


@pytest.mark.asyncio
async def test_delete_scene_cascades_placements(db):
    await db.upsert_device(id="lifx:aa", name="Strip", backend="lifx")
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    await db.save_placement(scene_id="s1", device_id="lifx:aa")
    await db.save_scene_effect_state("s1", "beat_pulse", {})
    await db.delete_scene("s1")
    placements = await db.load_scene_placements("s1")
    assert len(placements) == 0
    state = await db.load_scene_effect_state("s1")
    assert state is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "scene"`
Expected: FAIL

- [ ] **Step 3: Implement scene methods**

Add to `StateDB`:

```python
    # ── Scenes ──────────────────────────────────────────────────

    async def load_scenes(self) -> list[dict[str, Any]]:
        rows = await self._execute_read(
            "SELECT id, name, mapping_type, mapping_params, effect_mode, "
            "effect_source, is_active FROM scenes"
        )
        columns = [
            "id", "name", "mapping_type", "mapping_params", "effect_mode",
            "effect_source", "is_active",
        ]
        result = []
        for row in rows:
            d = dict(zip(columns, row))
            if d["mapping_params"]:
                d["mapping_params"] = json.loads(d["mapping_params"])
            result.append(d)
        return result

    async def save_scene(
        self,
        id: str,
        name: str,
        mapping_type: str = "linear",
        mapping_params: dict[str, Any] | None = None,
        effect_mode: str = "independent",
        effect_source: str | None = None,
        is_active: bool = False,
    ) -> None:
        await self._execute_write(
            """INSERT OR REPLACE INTO scenes
               (id, name, mapping_type, mapping_params, effect_mode, effect_source, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (id, name, mapping_type,
             json.dumps(mapping_params) if mapping_params else None,
             effect_mode, effect_source, int(is_active)),
        )

    async def delete_scene(self, scene_id: str) -> None:
        await self._execute_write("DELETE FROM scenes WHERE id = ?", (scene_id,))

    async def set_scene_active(self, scene_id: str, active: bool) -> None:
        await self._execute_write(
            "UPDATE scenes SET is_active = ? WHERE id = ?",
            (int(active), scene_id),
        )

    async def load_scene_effect_state(
        self, scene_id: str
    ) -> dict[str, Any] | None:
        rows = await self._execute_read(
            "SELECT effect_class, params FROM scene_effect_state WHERE scene_id = ?",
            (scene_id,),
        )
        if not rows:
            return None
        return {"effect_class": rows[0][0], "params": json.loads(rows[0][1])}

    async def save_scene_effect_state(
        self, scene_id: str, effect_class: str, params: dict[str, Any]
    ) -> None:
        await self._execute_write(
            """INSERT OR REPLACE INTO scene_effect_state (scene_id, effect_class, params)
               VALUES (?, ?, ?)""",
            (scene_id, effect_class, json.dumps(params)),
        )

    async def load_scene_placements(
        self, scene_id: str
    ) -> list[dict[str, Any]]:
        rows = await self._execute_read(
            """SELECT device_id, position_x, position_y, position_z,
                      geometry_type, direction_x, direction_y, direction_z,
                      length, width, rows, cols
               FROM scene_placements WHERE scene_id = ?""",
            (scene_id,),
        )
        columns = [
            "device_id", "position_x", "position_y", "position_z",
            "geometry_type", "direction_x", "direction_y", "direction_z",
            "length", "width", "rows", "cols",
        ]
        return [dict(zip(columns, row)) for row in rows]

    async def save_placement(
        self,
        scene_id: str,
        device_id: str,
        position_x: float = 0.0,
        position_y: float = 0.0,
        position_z: float = 0.0,
        geometry_type: str = "point",
        direction_x: float | None = None,
        direction_y: float | None = None,
        direction_z: float | None = None,
        length: float | None = None,
        width: float | None = None,
        rows: int | None = None,
        cols: int | None = None,
    ) -> None:
        await self._execute_write(
            """INSERT OR REPLACE INTO scene_placements
               (scene_id, device_id, position_x, position_y, position_z,
                geometry_type, direction_x, direction_y, direction_z,
                length, width, rows, cols)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scene_id, device_id, position_x, position_y, position_z,
             geometry_type, direction_x, direction_y, direction_z,
             length, width, rows, cols),
        )

    async def delete_placement(self, scene_id: str, device_id: str) -> None:
        await self._execute_write(
            "DELETE FROM scene_placements WHERE scene_id = ? AND device_id = ?",
            (scene_id, device_id),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "scene"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add scene CRUD to StateDB"
```

---

### Task 10: StateDB — Presets CRUD

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for preset operations**

Append to `tests/persistence/test_state_db.py`:

```python
@pytest.mark.asyncio
async def test_save_and_load_preset(db):
    await db.save_preset("My Preset", "beat_pulse", {"gamma": 2.5})
    presets = await db.load_presets()
    assert len(presets) == 1
    assert presets["My Preset"]["effect_class"] == "beat_pulse"
    assert presets["My Preset"]["params"]["gamma"] == 2.5


@pytest.mark.asyncio
async def test_delete_preset(db):
    await db.save_preset("Temp", "beat_pulse", {})
    await db.delete_preset("Temp")
    presets = await db.load_presets()
    assert len(presets) == 0


@pytest.mark.asyncio
async def test_load_presets_empty(db):
    presets = await db.load_presets()
    assert presets == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "preset"`
Expected: FAIL

- [ ] **Step 3: Implement preset methods**

Add to `StateDB`:

```python
    # ── Presets ─────────────────────────────────────────────────

    async def load_presets(self) -> dict[str, dict[str, Any]]:
        """Returns {name: {"effect_class": str, "params": dict}}."""
        rows = await self._execute_read(
            "SELECT name, effect_class, params FROM presets"
        )
        return {
            name: {"effect_class": ec, "params": json.loads(params)}
            for name, ec, params in rows
        }

    async def save_preset(
        self, name: str, effect_class: str, params: dict[str, Any]
    ) -> None:
        await self._execute_write(
            "INSERT OR REPLACE INTO presets (name, effect_class, params) VALUES (?, ?, ?)",
            (name, effect_class, json.dumps(params)),
        )

    async def delete_preset(self, name: str) -> None:
        await self._execute_write("DELETE FROM presets WHERE name = ?", (name,))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "preset"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add preset CRUD to StateDB"
```

---

### Task 11: StateDB — Debounced Writes

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for debounce**

Append to `tests/persistence/test_state_db.py`:

```python
import asyncio as _asyncio


@pytest.mark.asyncio
async def test_debounced_latency_write(db):
    """Debounced latency write coalesces rapid updates."""
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    # Fire multiple rapid latency updates
    db.schedule_latency_update("lifx:aa", 10.0)
    db.schedule_latency_update("lifx:aa", 20.0)
    db.schedule_latency_update("lifx:aa", 30.0)
    # Wait for debounce to fire (10s is the debounce; we force flush)
    await db.flush_pending()
    devices = await db.load_devices()
    # Should have the last value
    assert devices[0]["last_latency_ms"] == 30.0


@pytest.mark.asyncio
async def test_debounced_effect_state_write(db):
    """Debounced effect state write coalesces rapid param changes."""
    await db.save_scene(id="s1", name="Test", mapping_type="linear")
    db.schedule_effect_state_update("s1", "beat_pulse", {"gamma": 1.0})
    db.schedule_effect_state_update("s1", "beat_pulse", {"gamma": 2.0})
    db.schedule_effect_state_update("s1", "beat_pulse", {"gamma": 3.0})
    await db.flush_pending()
    state = await db.load_scene_effect_state("s1")
    assert state is not None
    assert state["params"]["gamma"] == 3.0


@pytest.mark.asyncio
async def test_flush_on_close(tmp_path):
    """Close flushes all pending debounced writes."""
    db_path = tmp_path / "state.db"
    db = StateDB(db_path)
    await db.open()
    await db.upsert_device(id="lifx:aa", name="Test", backend="lifx")
    db.schedule_latency_update("lifx:aa", 99.0)
    await db.close()  # should flush

    # Reopen and verify
    db2 = StateDB(db_path)
    await db2.open()
    devices = await db2.load_devices()
    assert devices[0]["last_latency_ms"] == 99.0
    await db2.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "debounce or flush"`
Expected: FAIL

- [ ] **Step 3: Implement debounce logic**

Add to `StateDB.__init__`:

```python
        self._pending_latency: dict[str, float] = {}
        self._pending_effect_state: dict[str, tuple[str, dict[str, Any]]] = {}
        self._latency_timer: asyncio.TimerHandle | None = None
        self._effect_timer: asyncio.TimerHandle | None = None
```

Add methods:

```python
    # ── Debounced writes ────────────────────────────────────────

    def schedule_latency_update(self, device_id: str, latency_ms: float) -> None:
        """Schedule a debounced latency write (10s coalesce window)."""
        self._pending_latency[device_id] = latency_ms
        if self._latency_timer is not None:
            self._latency_timer.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._latency_timer = loop.call_later(
                10.0, lambda: loop.create_task(self._flush_latency())
            )
        except RuntimeError:
            pass  # no running loop (testing without event loop)

    def schedule_effect_state_update(
        self, scene_id: str, effect_class: str, params: dict[str, Any]
    ) -> None:
        """Schedule a debounced effect state write (2s coalesce window)."""
        self._pending_effect_state[scene_id] = (effect_class, params)
        if self._effect_timer is not None:
            self._effect_timer.cancel()
        try:
            loop = asyncio.get_running_loop()
            self._effect_timer = loop.call_later(
                2.0, lambda: loop.create_task(self._flush_effect_state())
            )
        except RuntimeError:
            pass

    async def _flush_latency(self) -> None:
        pending = dict(self._pending_latency)
        self._pending_latency.clear()
        for device_id, latency_ms in pending.items():
            await self.update_device_latency(device_id, latency_ms)

    async def _flush_effect_state(self) -> None:
        pending = dict(self._pending_effect_state)
        self._pending_effect_state.clear()
        for scene_id, (effect_class, params) in pending.items():
            await self.save_scene_effect_state(scene_id, effect_class, params)

    async def flush_pending(self) -> None:
        """Flush all pending debounced writes immediately."""
        if self._latency_timer is not None:
            self._latency_timer.cancel()
            self._latency_timer = None
        if self._effect_timer is not None:
            self._effect_timer.cancel()
            self._effect_timer = None
        await self._flush_latency()
        await self._flush_effect_state()
```

Update `close()`:

```python
    async def close(self) -> None:
        await self.flush_pending()
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "debounce or flush"`
Expected: PASS

- [ ] **Step 5: Run all StateDB tests**

Run: `uv run pytest tests/persistence/test_state_db.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add debounced writes to StateDB with flush on close"
```

---

## Phase 2: Device Identity & Lifecycle

### Task 12: LIFX DeviceInfo Stable ID

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/discovery.py:88-154`

- [ ] **Step 1: Write test**

Create or append to `tests/devices/test_lifx_stable_id.py`:

```python
"""Test that LIFX discovery populates stable_id and mac on DeviceInfo."""
from dj_ledfx.types import DeviceInfo


def test_lifx_stable_id_format():
    mac_hex = b"\xd0\x73\xd5\xaa\xbb\xcc".hex()
    stable_id = f"lifx:{mac_hex}"
    info = DeviceInfo(
        name="LIFX Strip (192.168.1.5)",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.5:56700",
        mac=mac_hex,
        stable_id=stable_id,
    )
    assert info.stable_id == "lifx:d073d5aabbcc"
    assert info.mac == "d073d5aabbcc"
```

- [ ] **Step 2: Run test to verify it passes** (tests pure data model, should pass already)

Run: `uv run pytest tests/devices/test_lifx_stable_id.py -v`
Expected: PASS

- [ ] **Step 3: Modify LIFX discovery to pass mac/stable_id**

In `src/dj_ledfx/devices/lifx/discovery.py`, update all three `DeviceInfo(...)` construction sites:

For the tile adapter (around line 112):
```python
            mac_hex = record.mac.hex()
            info = DeviceInfo(
                f"LIFX Tile ({record.ip})", "lifx_tile", led_count, str_addr,
                mac=mac_hex, stable_id=f"lifx:{mac_hex}",
            )
```

For the strip adapter (around line 138):
```python
            mac_hex = record.mac.hex()
            info = DeviceInfo(
                f"LIFX Strip ({record.ip})", "lifx_strip", zone_count, str_addr,
                mac=mac_hex, stable_id=f"lifx:{mac_hex}",
            )
```

For the bulb adapter (around line 148):
```python
            mac_hex = record.mac.hex()
            info = DeviceInfo(
                f"LIFX Bulb ({record.ip})", "lifx_bulb", 1, str_addr,
                mac=mac_hex, stable_id=f"lifx:{mac_hex}",
            )
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/lifx/discovery.py tests/devices/test_lifx_stable_id.py
git commit -m "feat: populate mac and stable_id on LIFX DeviceInfo"
```

---

### Task 13: Govee DeviceInfo Stable ID

**Files:**
- Modify: `src/dj_ledfx/devices/govee/segment.py:44-50`
- Modify: `src/dj_ledfx/devices/govee/solid.py:33-39`

- [ ] **Step 1: Write test**

Create `tests/devices/test_govee_stable_id.py`:

```python
"""Test that Govee adapters populate stable_id on DeviceInfo."""
from unittest.mock import AsyncMock, MagicMock

from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


def _make_record():
    return GoveeDeviceRecord(
        ip="192.168.1.10",
        device_id="1F:80:C5:32:32:36:72:4E",
        sku="H6159",
        wifi_version="1.0",
        ble_version="1.0",
    )


def test_segment_adapter_stable_id():
    transport = MagicMock()
    adapter = GoveeSegmentAdapter(transport, _make_record(), num_segments=10)
    info = adapter.device_info
    assert info.stable_id == "govee:1F:80:C5:32:32:36:72:4E"


def test_solid_adapter_stable_id():
    transport = MagicMock()
    adapter = GoveeSolidAdapter(transport, _make_record())
    info = adapter.device_info
    assert info.stable_id == "govee:1F:80:C5:32:32:36:72:4E"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_govee_stable_id.py -v`
Expected: FAIL — `stable_id` is None

- [ ] **Step 3: Update Govee adapters**

In `src/dj_ledfx/devices/govee/segment.py`, update `device_info` property:

```python
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_segment",
            led_count=self._num_segments,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
        )
```

In `src/dj_ledfx/devices/govee/solid.py`, update `device_info` property:

```python
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_solid",
            led_count=1,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/test_govee_stable_id.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/segment.py src/dj_ledfx/devices/govee/solid.py tests/devices/test_govee_stable_id.py
git commit -m "feat: populate stable_id on Govee DeviceInfo"
```

---

### Task 14: OpenRGB DeviceInfo Stable ID

**Files:**
- Modify: `src/dj_ledfx/devices/openrgb_backend.py`

- [ ] **Step 1: Understand current code**

Read `src/dj_ledfx/devices/openrgb_backend.py` to find where `DeviceInfo` is constructed. The OpenRGB adapter constructs `DeviceInfo` inside the `OpenRGBAdapter` class. The stable ID format is `openrgb:{host}:{port}:{index}`.

- [ ] **Step 2: Write test**

Create `tests/devices/test_openrgb_stable_id.py`:

```python
"""Test that OpenRGB adapters populate stable_id on DeviceInfo."""
from dj_ledfx.types import DeviceInfo


def test_openrgb_stable_id_format():
    info = DeviceInfo(
        name="My Keyboard",
        device_type="openrgb",
        led_count=100,
        address="127.0.0.1:6742",
        stable_id="openrgb:127.0.0.1:6742:0",
    )
    assert info.stable_id == "openrgb:127.0.0.1:6742:0"
```

- [ ] **Step 3: Run test**

Run: `uv run pytest tests/devices/test_openrgb_stable_id.py -v`
Expected: PASS (pure data model test)

- [ ] **Step 4: Modify OpenRGB adapter**

In `src/dj_ledfx/devices/openrgb_backend.py`, find where `DeviceInfo` is constructed in the adapter and add `stable_id=f"openrgb:{self._host}:{self._port}:{self._device_index}"`. The exact location depends on whether `device_info` is a stored field or computed property — read the file to determine. Add `stable_id` kwarg to the `DeviceInfo(...)` call.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/openrgb_backend.py tests/devices/test_openrgb_stable_id.py
git commit -m "feat: populate stable_id on OpenRGB DeviceInfo"
```

---

### Task 15: ManagedDevice Status and DeviceManager Promote/Demote

**Files:**
- Modify: `src/dj_ledfx/devices/manager.py`
- Test: `tests/devices/test_manager.py` (create)

- [ ] **Step 1: Write tests**

Create `tests/devices/test_manager.py`:

```python
"""Tests for DeviceManager promote/demote lifecycle."""
import pytest

from dj_ledfx.devices.ghost import GhostAdapter
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo


def _make_tracker(latency_ms=50.0):
    return LatencyTracker(StaticLatency(latency_ms))


def _make_info(name="Test", stable_id="lifx:aabb"):
    return DeviceInfo(
        name=name, device_type="lifx_strip", led_count=60,
        address="192.168.1.5:56700", stable_id=stable_id,
    )


def test_managed_device_has_status():
    ghost = GhostAdapter(_make_info(), led_count=60)
    md = ManagedDevice(adapter=ghost, tracker=_make_tracker(), status="offline")
    assert md.status == "offline"


def test_managed_device_status_default():
    ghost = GhostAdapter(_make_info(), led_count=60)
    md = ManagedDevice(adapter=ghost, tracker=_make_tracker())
    assert md.status == "online"


def test_add_device_with_info_creates_ghost():
    mgr = DeviceManager(event_bus=EventBus())
    info = _make_info()
    mgr.add_device_from_info(info, led_count=60, tracker=_make_tracker(), status="offline")
    device = mgr.get_by_stable_id("lifx:aabb")
    assert device is not None
    assert device.status == "offline"
    assert isinstance(device.adapter, GhostAdapter)
    assert device.adapter.is_connected is False


def test_promote_device():
    mgr = DeviceManager(event_bus=EventBus())
    info = _make_info()
    mgr.add_device_from_info(info, led_count=60, tracker=_make_tracker(), status="offline")

    # Create a mock "real" adapter
    from unittest.mock import MagicMock
    real_adapter = MagicMock()
    real_adapter.device_info = info
    real_adapter.is_connected = True
    real_adapter.led_count = 60

    mgr.promote_device("lifx:aabb", real_adapter)
    device = mgr.get_by_stable_id("lifx:aabb")
    assert device is not None
    assert device.status == "online"
    assert device.adapter is real_adapter


def test_demote_device():
    mgr = DeviceManager(event_bus=EventBus())
    from unittest.mock import MagicMock
    real_adapter = MagicMock()
    info = _make_info()
    real_adapter.device_info = info
    real_adapter.is_connected = True
    real_adapter.led_count = 60

    mgr.add_device(real_adapter, _make_tracker())
    # Need to get the stable_id — adapter has it
    mgr.demote_device("lifx:aabb")
    device = mgr.get_by_stable_id("lifx:aabb")
    assert device is not None
    assert device.status == "offline"
    assert isinstance(device.adapter, GhostAdapter)


def test_remove_device():
    mgr = DeviceManager(event_bus=EventBus())
    info = _make_info()
    mgr.add_device_from_info(info, led_count=60, tracker=_make_tracker())
    mgr.remove_device("lifx:aabb")
    assert mgr.get_by_stable_id("lifx:aabb") is None


def test_get_by_stable_id_returns_none():
    mgr = DeviceManager(event_bus=EventBus())
    assert mgr.get_by_stable_id("nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_manager.py -v`
Expected: FAIL

- [ ] **Step 3: Implement changes**

In `src/dj_ledfx/devices/manager.py`:

Update `ManagedDevice`:

```python
from typing import Literal

@dataclass
class ManagedDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker
    max_fps: int = 60
    status: Literal["online", "offline", "reconnecting"] = "online"
```

Add import for `GhostAdapter` and new methods to `DeviceManager`:

```python
from dj_ledfx.devices.ghost import GhostAdapter
```

Add methods:

```python
    def get_by_stable_id(self, stable_id: str) -> ManagedDevice | None:
        for d in self._devices:
            if d.adapter.device_info.stable_id == stable_id:
                return d
        return None

    def add_device_from_info(
        self,
        device_info: DeviceInfo,
        led_count: int,
        tracker: LatencyTracker,
        max_fps: int = 60,
        status: Literal["online", "offline", "reconnecting"] = "online",
    ) -> None:
        """Add a device from persisted DeviceInfo (creates GhostAdapter if offline)."""
        if status == "offline":
            adapter = GhostAdapter(device_info=device_info, led_count=led_count)
        else:
            raise ValueError("Use add_device() for online devices with real adapters")
        self._devices.append(
            ManagedDevice(adapter=adapter, tracker=tracker, max_fps=max_fps, status=status)
        )
        logger.info("Registered device '{}' (status={})", device_info.name, status)

    def promote_device(self, stable_id: str, adapter: DeviceAdapter) -> None:
        """Swap ghost adapter for real adapter, set status to online."""
        device = self.get_by_stable_id(stable_id)
        if device is None:
            raise KeyError(f"Device not found: {stable_id}")
        device.adapter = adapter
        device.status = "online"
        logger.info("Device '{}' promoted to online", adapter.device_info.name)

    def demote_device(self, stable_id: str) -> None:
        """Swap real adapter for ghost, set status to offline."""
        device = self.get_by_stable_id(stable_id)
        if device is None:
            raise KeyError(f"Device not found: {stable_id}")
        info = device.adapter.device_info
        led_count = device.adapter.led_count
        device.adapter = GhostAdapter(device_info=info, led_count=led_count)
        device.status = "offline"
        logger.info("Device '{}' demoted to offline", info.name)

    def remove_device(self, stable_id: str) -> None:
        """Remove a device entirely from the managed list."""
        self._devices = [
            d for d in self._devices
            if d.adapter.device_info.stable_id != stable_id
        ]
```

Also add `DeviceInfo` import at top and add the `Literal` import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/test_manager.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass (existing tests still work since `status` defaults to `"online"`)

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/manager.py tests/devices/test_manager.py
git commit -m "feat: add ManagedDevice status, promote/demote/remove to DeviceManager"
```

---

## Phase 3: Multi-Scene Pipeline

### Task 16: ScenePipeline Dataclass

**Files:**
- Create: `src/dj_ledfx/spatial/pipeline.py`
- Test: `tests/spatial/test_pipeline.py`

- [ ] **Step 1: Write tests**

Create `tests/spatial/test_pipeline.py`:

```python
"""Tests for ScenePipeline."""
import numpy as np
import pytest

from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.spatial.pipeline import ScenePipeline


def test_scene_pipeline_creation():
    deck = EffectDeck(BeatPulse())
    buf = RingBuffer(capacity=60, led_count=60)
    pipeline = ScenePipeline(
        scene_id="dj-booth",
        deck=deck,
        ring_buffer=buf,
        compositor=None,
        mapping=None,
        devices=[],
        led_count=60,
    )
    assert pipeline.scene_id == "dj-booth"
    assert pipeline.led_count == 60
    assert pipeline.deck is deck
    assert pipeline.ring_buffer is buf


def test_scene_pipeline_shared_deck():
    """Two pipelines can share the same EffectDeck."""
    deck = EffectDeck(BeatPulse())
    p1 = ScenePipeline(
        scene_id="booth", deck=deck, ring_buffer=RingBuffer(60, 60),
        compositor=None, mapping=None, devices=[], led_count=60,
    )
    p2 = ScenePipeline(
        scene_id="floor", deck=deck, ring_buffer=RingBuffer(60, 100),
        compositor=None, mapping=None, devices=[], led_count=100,
    )
    assert p1.deck is p2.deck
    assert p1.ring_buffer is not p2.ring_buffer
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_pipeline.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement ScenePipeline**

Create `src/dj_ledfx/spatial/pipeline.py`:

```python
"""ScenePipeline — bundles per-scene rendering state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import ManagedDevice
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.spatial.compositor import SpatialCompositor
    from dj_ledfx.spatial.mapping import SpatialMapping


@dataclass
class ScenePipeline:
    """One per active scene. Bundles all rendering state."""

    scene_id: str
    deck: EffectDeck
    ring_buffer: RingBuffer
    compositor: SpatialCompositor | None
    mapping: SpatialMapping | None
    devices: list[ManagedDevice]
    led_count: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/spatial/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/spatial/pipeline.py tests/spatial/test_pipeline.py
git commit -m "feat: add ScenePipeline dataclass"
```

---

### Task 17: EffectEngine Multi-Pipeline Rendering

**Files:**
- Modify: `src/dj_ledfx/effects/engine.py:64-142`
- Test: `tests/effects/test_engine.py`

- [ ] **Step 1: Write tests for multi-pipeline**

Add to `tests/effects/test_engine.py`:

```python
from dj_ledfx.spatial.pipeline import ScenePipeline


def test_engine_tick_renders_to_pipelines(clock):
    """Engine tick renders each pipeline into its own ring buffer."""
    from dj_ledfx.effects.beat_pulse import BeatPulse
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import EffectEngine, RingBuffer

    deck1 = EffectDeck(BeatPulse())
    buf1 = RingBuffer(60, 30)
    p1 = ScenePipeline(
        scene_id="s1", deck=deck1, ring_buffer=buf1,
        compositor=None, mapping=None, devices=[], led_count=30,
    )

    deck2 = EffectDeck(BeatPulse())
    buf2 = RingBuffer(60, 50)
    p2 = ScenePipeline(
        scene_id="s2", deck=deck2, ring_buffer=buf2,
        compositor=None, mapping=None, devices=[], led_count=50,
    )

    engine = EffectEngine(
        clock=clock,
        deck=deck1,  # legacy default deck
        led_count=30,
        fps=60,
        max_lookahead_s=1.0,
        pipelines=[p1, p2],
    )

    engine.tick(0.0)

    assert buf1.count == 1
    assert buf2.count == 1


def test_engine_empty_pipelines_uses_legacy_buffer(clock):
    """When no pipelines, engine uses legacy single-buffer mode."""
    from dj_ledfx.effects.beat_pulse import BeatPulse
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import EffectEngine

    deck = EffectDeck(BeatPulse())
    engine = EffectEngine(clock=clock, deck=deck, led_count=60, fps=60)
    engine.tick(0.0)
    assert engine.ring_buffer.count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_engine.py -v -k "pipelines"`
Expected: FAIL — `pipelines` param not accepted

- [ ] **Step 3: Modify EffectEngine**

In `src/dj_ledfx/effects/engine.py`, update `EffectEngine.__init__` to accept optional `pipelines`:

```python
from dj_ledfx.spatial.pipeline import ScenePipeline

class EffectEngine:
    def __init__(
        self,
        clock: BeatClock,
        deck: EffectDeck,
        led_count: int,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        pipelines: list[ScenePipeline] | None = None,
    ) -> None:
        self._clock = clock
        self._deck = deck
        self._led_count = led_count
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._max_lookahead_s = max_lookahead_s
        self.ring_buffer = RingBuffer(capacity=fps, led_count=led_count)
        self._running = False
        self._last_tick_time = 0.0
        self._render_times: deque[float] = deque(maxlen=fps * 10)
        self.pipelines: list[ScenePipeline] = pipelines or []
```

Update `tick()`:

```python
    def tick(self, now: float) -> None:
        target_time = now + self._max_lookahead_s
        state = self._clock.get_state_at(target_time)

        if self.pipelines:
            # Multi-pipeline mode: render each scene pipeline
            for pipeline in self.pipelines:
                render_start = time.monotonic()
                colors = pipeline.deck.render(
                    beat_phase=state.beat_phase,
                    bar_phase=state.bar_phase,
                    dt=self._frame_period,
                    led_count=pipeline.led_count,
                )
                render_elapsed = time.monotonic() - render_start
                self._render_times.append(render_elapsed)

                frame = RenderedFrame(
                    colors=colors,
                    target_time=target_time,
                    beat_phase=state.beat_phase,
                    bar_phase=state.bar_phase,
                )
                pipeline.ring_buffer.write(frame)
        else:
            # Legacy single-buffer mode
            render_start = time.monotonic()
            colors = self._deck.render(
                beat_phase=state.beat_phase,
                bar_phase=state.bar_phase,
                dt=self._frame_period,
                led_count=self._led_count,
            )
            render_elapsed = time.monotonic() - render_start
            self._render_times.append(render_elapsed)

            frame = RenderedFrame(
                colors=colors,
                target_time=target_time,
                beat_phase=state.beat_phase,
                bar_phase=state.bar_phase,
            )
            self.ring_buffer.write(frame)

        metrics.RENDER_DURATION.observe(render_elapsed)
        metrics.FRAMES_RENDERED.inc()
        logger.trace("Rendered frame for t+{:.0f}ms", self._max_lookahead_s * 1000)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/engine.py tests/effects/test_engine.py
git commit -m "feat: add multi-pipeline rendering to EffectEngine"
```

---

### Task 18: EffectDeck on_change Callback

**Files:**
- Modify: `src/dj_ledfx/effects/deck.py`
- Test: `tests/effects/test_deck.py`

- [ ] **Step 1: Write tests**

Add to `tests/effects/test_deck.py`:

```python
def test_on_change_callback_fires_on_swap():
    from dj_ledfx.effects.beat_pulse import BeatPulse
    from dj_ledfx.effects.deck import EffectDeck

    calls = []
    deck = EffectDeck(BeatPulse(), on_change=lambda d: calls.append(d.effect_name))
    deck.apply_update("beat_pulse", {"gamma": 3.0})
    assert len(calls) == 1


def test_on_change_callback_fires_on_param_update():
    from dj_ledfx.effects.beat_pulse import BeatPulse
    from dj_ledfx.effects.deck import EffectDeck

    calls = []
    deck = EffectDeck(BeatPulse(), on_change=lambda d: calls.append("changed"))
    deck.apply_update(None, {"gamma": 5.0})
    assert len(calls) == 1


def test_no_callback_no_error():
    from dj_ledfx.effects.beat_pulse import BeatPulse
    from dj_ledfx.effects.deck import EffectDeck

    deck = EffectDeck(BeatPulse())
    deck.apply_update(None, {"gamma": 5.0})  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_deck.py -v -k "on_change"`
Expected: FAIL — `on_change` kwarg not accepted

- [ ] **Step 3: Implement on_change**

In `src/dj_ledfx/effects/deck.py`:

```python
from collections.abc import Callable

class EffectDeck:
    def __init__(
        self,
        effect: Effect,
        on_change: Callable[[EffectDeck], None] | None = None,
    ) -> None:
        self._effect = effect
        self._on_change = on_change
```

Update `apply_update`:

```python
    def apply_update(self, effect_name: str | None, params: dict[str, Any]) -> None:
        from dj_ledfx.effects.registry import create_effect

        if effect_name and effect_name != self.effect_name:
            new_effect = create_effect(effect_name, **params)
            self.swap_effect(new_effect)
        elif params:
            self._effect.set_params(**params)

        if self._on_change is not None:
            self._on_change(self)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_deck.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/effects/deck.py tests/effects/test_deck.py
git commit -m "feat: add on_change callback to EffectDeck"
```

---

### Task 19: PresetStore Backed by StateDB

**Files:**
- Modify: `src/dj_ledfx/effects/presets.py`
- Test: `tests/effects/test_presets.py`

- [ ] **Step 1: Write tests for DB-backed PresetStore**

Add to `tests/effects/test_presets.py`:

```python
import pytest
import pytest_asyncio
from pathlib import Path

from dj_ledfx.effects.presets import Preset, PresetStore
from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db_store(tmp_path):
    db = StateDB(tmp_path / "state.db")
    await db.open()
    store = PresetStore(state_db=db)
    await store.load_from_db()
    yield store
    await db.close()


@pytest.mark.asyncio
async def test_db_store_save_and_list(db_store):
    await db_store.save_async(Preset("P1", "beat_pulse", {"gamma": 2.5}))
    presets = db_store.list()
    assert len(presets) == 1
    assert presets[0].name == "P1"


@pytest.mark.asyncio
async def test_db_store_delete(db_store):
    await db_store.save_async(Preset("P1", "beat_pulse", {}))
    await db_store.delete_async("P1")
    assert len(db_store.list()) == 0


@pytest.mark.asyncio
async def test_db_store_persistence(tmp_path):
    """Presets survive DB close/reopen."""
    db = StateDB(tmp_path / "state.db")
    await db.open()
    store = PresetStore(state_db=db)
    await store.load_from_db()
    await store.save_async(Preset("P1", "beat_pulse", {"gamma": 3.0}))
    await db.close()

    db2 = StateDB(tmp_path / "state.db")
    await db2.open()
    store2 = PresetStore(state_db=db2)
    await store2.load_from_db()
    presets = store2.list()
    assert len(presets) == 1
    assert presets[0].params["gamma"] == 3.0
    await db2.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_presets.py -v -k "db_store"`
Expected: FAIL — `state_db` kwarg not accepted

- [ ] **Step 3: Update PresetStore to support both backends**

In `src/dj_ledfx/effects/presets.py`, update to support both TOML (legacy) and DB:

```python
"""Named effect presets with TOML or StateDB persistence."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dj_ledfx.config import atomic_toml_write

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB


@dataclass(frozen=True)
class Preset:
    name: str
    effect_class: str
    params: dict[str, Any]


class PresetStore:
    """Persists effect presets. Supports TOML file (legacy) or StateDB backend."""

    def __init__(
        self,
        path: Path | None = None,
        state_db: StateDB | None = None,
    ) -> None:
        self._path = path
        self._state_db = state_db
        self._presets: dict[str, Preset] = {}
        if path and path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        with open(self._path, "rb") as f:
            data = tomllib.load(f)
        for name, entry in data.get("presets", {}).items():
            self._presets[name] = Preset(
                name=name,
                effect_class=entry["effect_class"],
                params=entry.get("params", {}),
            )

    async def load_from_db(self) -> None:
        """Load presets from StateDB."""
        assert self._state_db is not None
        raw = await self._state_db.load_presets()
        self._presets = {
            name: Preset(name=name, effect_class=d["effect_class"], params=d["params"])
            for name, d in raw.items()
        }

    def _persist(self) -> None:
        if self._path is None:
            return
        data: dict[str, Any] = {"presets": {}}
        for name, preset in self._presets.items():
            data["presets"][name] = {
                "effect_class": preset.effect_class,
                "params": preset.params,
            }
        atomic_toml_write(data, self._path)

    def list(self) -> list[Preset]:
        return list(self._presets.values())

    def save(self, preset: Preset) -> None:
        self._presets[preset.name] = preset
        self._persist()

    async def save_async(self, preset: Preset) -> None:
        """Save preset to in-memory cache and DB."""
        self._presets[preset.name] = preset
        if self._state_db is not None:
            await self._state_db.save_preset(
                preset.name, preset.effect_class, preset.params
            )
        else:
            self._persist()

    def delete(self, name: str) -> None:
        if name not in self._presets:
            raise KeyError(f"Preset not found: {name}")
        del self._presets[name]
        self._persist()

    async def delete_async(self, name: str) -> None:
        if name not in self._presets:
            raise KeyError(f"Preset not found: {name}")
        del self._presets[name]
        if self._state_db is not None:
            await self._state_db.delete_preset(name)
        else:
            self._persist()

    def load(self, name: str) -> Preset:
        if name not in self._presets:
            raise KeyError(f"Preset not found: {name}")
        return self._presets[name]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_presets.py -v`
Expected: PASS (both old TOML tests and new DB tests)

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/effects/presets.py tests/effects/test_presets.py
git commit -m "feat: add StateDB backend to PresetStore"
```

---

## Phase 4: Scheduler Dynamic Devices

### Task 20: DeviceSendState and Dict-Based Scheduler

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py`
- Test: `tests/scheduling/test_scheduler.py`

- [ ] **Step 1: Write tests for dynamic device management**

Add to `tests/scheduling/test_scheduler.py`:

```python
from dj_ledfx.scheduling.scheduler import DeviceSendState


def test_device_send_state_creation():
    """DeviceSendState bundles per-device send state."""
    from unittest.mock import MagicMock
    from dj_ledfx.scheduling.scheduler import FrameSlot

    managed = MagicMock()
    managed.adapter.device_info.stable_id = "lifx:aa"
    slot = FrameSlot()
    state = DeviceSendState(
        managed=managed, slot=slot, send_count=0, send_task=None, pipeline=None,
    )
    assert state.managed is managed
    assert state.slot is slot
    assert state.send_count == 0
```

```python
import pytest

@pytest.mark.asyncio
async def test_scheduler_add_device_during_run():
    """Devices added after construction get send tasks."""
    from unittest.mock import MagicMock, AsyncMock
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.scheduling.scheduler import LookaheadScheduler
    from dj_ledfx.devices.ghost import GhostAdapter
    from dj_ledfx.latency.strategies import StaticLatency
    from dj_ledfx.latency.tracker import LatencyTracker
    from dj_ledfx.types import DeviceInfo
    from dj_ledfx.devices.manager import ManagedDevice
    import asyncio

    buf = RingBuffer(60, 60)
    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[], fps=60)

    # Start scheduler, let it run briefly
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    info = DeviceInfo("Ghost", "test", 10, "1.2.3.4:80", stable_id="test:aa")
    ghost = GhostAdapter(info, 10)
    managed = ManagedDevice(adapter=ghost, tracker=LatencyTracker(StaticLatency(50.0)), status="offline")
    scheduler.add_device(managed)

    assert "test:aa" in scheduler._device_state
    await asyncio.sleep(0.05)

    scheduler.remove_device("test:aa")
    assert "test:aa" not in scheduler._device_state

    scheduler.stop()
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v -k "send_state or add_device_during"`
Expected: FAIL

- [ ] **Step 3: Implement DeviceSendState and refactor scheduler**

In `src/dj_ledfx/scheduling/scheduler.py`, add dataclass and refactor:

```python
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx import metrics
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.types import DeviceStats

if TYPE_CHECKING:
    from dj_ledfx.spatial.pipeline import ScenePipeline


@dataclass
class DeviceSendState:
    """Per-device send state, keyed by stable_id."""
    managed: ManagedDevice
    slot: FrameSlot
    send_count: int = 0
    send_task: asyncio.Task[None] | None = None
    pipeline: ScenePipeline | None = None
```

Refactor `LookaheadScheduler.__init__` to build `_device_state` dict from the provided device list (for backward compat), while also keeping `add_device`/`remove_device` methods. The key change:

- `_device_state: dict[str, DeviceSendState]` replaces `_devices`, `_slots`, `_send_counts`
- `run()` iterates `_device_state.values()` for the distributor loop
- `_send_loop` captures `stable_id` instead of positional index
- `add_device(managed, pipeline=None)` creates state + spawns send task if running
- `remove_device(stable_id)` cancels task + removes from dict
- `get_device_stats()` iterates `_device_state.values()`

The full implementation should preserve the existing send loop logic (connection check, frame find, compositor, FPS cap) but reference state by `stable_id` key instead of positional index.

**Important backward compatibility:** Constructor still accepts `devices: list[ManagedDevice]` and builds the dict from it. Devices without `stable_id` use `device_info.name` as fallback key.

```python
class LookaheadScheduler:
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
        compositor: SpatialCompositor | None = None,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._frame_period = 1.0 / fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._compositor = compositor
        self._frame_snapshots: dict[str, tuple[NDArray[np.uint8], int]] = {}
        self._frame_seq: dict[str, int] = {}
        self._start_time: float = 0.0

        # Build device state dict from initial device list
        self._device_state: dict[str, DeviceSendState] = {}
        for device in devices:
            key = device.adapter.device_info.stable_id or device.adapter.device_info.name
            self._device_state[key] = DeviceSendState(
                managed=device, slot=FrameSlot(),
            )

    @property
    def frame_snapshots(self) -> dict[str, tuple[NDArray[np.uint8], int]]:
        return self._frame_snapshots

    @property
    def compositor(self) -> SpatialCompositor | None:
        return self._compositor

    @compositor.setter
    def compositor(self, value: SpatialCompositor | None) -> None:
        self._compositor = value

    def stop(self) -> None:
        self._running = False

    def add_device(
        self,
        managed: ManagedDevice,
        pipeline: ScenePipeline | None = None,
    ) -> None:
        """Add a device dynamically. Spawns send task if scheduler is running."""
        key = managed.adapter.device_info.stable_id or managed.adapter.device_info.name
        state = DeviceSendState(managed=managed, slot=FrameSlot(), pipeline=pipeline)
        self._device_state[key] = state
        if self._running:
            state.send_task = asyncio.create_task(
                self._send_loop(state, key)
            )

    def remove_device(self, stable_id: str) -> None:
        """Remove a device dynamically. Cancels its send task."""
        state = self._device_state.pop(stable_id, None)
        if state and state.send_task:
            state.send_task.cancel()

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._device_state),
        )

        # Spawn per-device send loops
        for key, state in self._device_state.items():
            state.send_task = asyncio.create_task(self._send_loop(state, key))

        try:
            last_tick = time.monotonic()
            while self._running:
                now = time.monotonic()
                for key, state in self._device_state.items():
                    if state.slot.has_pending:
                        logger.trace(
                            "Frame overwritten for '{}' — device draining slower than engine",
                            state.managed.adapter.device_info.name,
                        )
                        metrics.FRAMES_DROPPED.labels(
                            device=state.managed.adapter.device_info.name
                        ).inc()
                    target_time = now + state.managed.tracker.effective_latency_s
                    state.slot.put(target_time)

                last_tick += self._frame_period
                sleep_time = last_tick - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    last_tick = time.monotonic()
                    await asyncio.sleep(0)
        finally:
            tasks = [
                s.send_task for s in self._device_state.values() if s.send_task
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for state in self._device_state.values():
                state.send_task = None

        logger.info("LookaheadScheduler stopped")

    async def _send_loop(self, state: DeviceSendState, key: str) -> None:
        device = state.managed
        slot = state.slot
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()
        device_name = device.adapter.device_info.name

        while self._running:
            if not device.adapter.is_connected:
                if was_connected:
                    logger.warning("Device '{}' disconnected", device_name)
                was_connected = False
                await asyncio.sleep(self._disconnect_backoff_s)
                continue

            if not was_connected:
                logger.info("Device '{}' reconnected", device_name)
                device.tracker.reset()
                was_connected = True

            try:
                target_time = await slot.take(timeout=1.0)
            except TimeoutError:
                continue

            # Determine which ring buffer to read from
            ring_buffer = (
                state.pipeline.ring_buffer if state.pipeline else self._ring_buffer
            )
            frame = ring_buffer.find_nearest(target_time)
            if frame is None:
                logger.warning(
                    "No frame in ring buffer for '{}' (target_time={:.3f})",
                    device_name, target_time,
                )
                continue

            colors = frame.colors
            # Use pipeline compositor if available, else global
            compositor = (
                state.pipeline.compositor if state.pipeline and state.pipeline.compositor
                else self._compositor
            )
            if compositor is not None:
                mapped = compositor.composite(frame.colors, device_name)
                if mapped is not None:
                    colors = mapped

            send_start = time.monotonic()
            try:
                await device.adapter.send_frame(colors)
            except Exception:
                logger.warning("Send failed for '{}'", device_name)
                continue

            send_elapsed = time.monotonic() - send_start
            metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(send_elapsed)

            state.send_count += 1
            seq = self._frame_seq.get(device_name, 0) + 1
            self._frame_seq[device_name] = seq
            self._frame_snapshots[device_name] = (colors, seq)
            metrics.DEVICE_LATENCY.labels(device=device_name).set(
                device.tracker.effective_latency_s
            )
            metrics.DEVICE_FPS.labels(device=device_name).set(device.max_fps)

            if device.adapter.supports_latency_probing:
                rtt_ms = (time.monotonic() - send_start) * 1000.0
                device.tracker.update(rtt_ms)

            min_frame_interval = 1.0 / device.max_fps
            last_send_time += min_frame_interval
            remaining = last_send_time - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            else:
                last_send_time = time.monotonic()

    def get_device_stats(self) -> list[DeviceStats]:
        now = time.monotonic()
        elapsed = now - self._start_time if self._start_time > 0 else 1.0
        stats: list[DeviceStats] = []
        for key, state in self._device_state.items():
            device = state.managed
            send_fps = state.send_count / elapsed if elapsed > 0 else 0.0
            frames_dropped = state.slot.put_count - state.send_count
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=max(0, frames_dropped),
                    connected=device.adapter.is_connected,
                )
            )
        return stats
```

- [ ] **Step 4: Run scheduler tests**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat: refactor scheduler to dict-based DeviceSendState with dynamic add/remove"
```

---

## Phase 5: TOML Migration & Import/Export

### Task 21: TOML Import/Export Marshaling

**Files:**
- Create: `src/dj_ledfx/persistence/toml_io.py`
- Test: `tests/persistence/test_toml_io.py`

- [ ] **Step 1: Write tests for TOML export**

Create `tests/persistence/test_toml_io.py`:

```python
"""Tests for TOML import/export marshaling."""
import pytest
import pytest_asyncio
from pathlib import Path

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import export_toml, import_toml


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()
    yield state_db
    await state_db.close()


@pytest.mark.asyncio
async def test_export_empty_db(db):
    result = await export_toml(db)
    assert isinstance(result, str)
    assert "[config]" not in result  # empty DB produces minimal TOML


@pytest.mark.asyncio
async def test_export_round_trip_config(db):
    await db.save_config_key("engine", "fps", 120)
    await db.save_config_key("network", "interface", "192.168.1.1")
    toml_str = await export_toml(db)
    assert "fps = 120" in toml_str
    assert 'interface = "192.168.1.1"' in toml_str


@pytest.mark.asyncio
async def test_export_round_trip_devices(db):
    await db.upsert_device(
        id="lifx:aabb", name="Kitchen Strip", backend="lifx",
        led_count=60, ip="192.168.1.42", mac="d073d5aabb",
        last_latency_ms=48.5,
    )
    toml_str = await export_toml(db)
    assert "Kitchen Strip" in toml_str
    assert "lifx" in toml_str


@pytest.mark.asyncio
async def test_import_config(db):
    toml_str = """
[config.engine]
fps = 90

[config.network]
interface = "10.0.0.1"
"""
    await import_toml(db, toml_str)
    config = await db.load_config()
    assert config[("engine", "fps")] == 90
    assert config[("network", "interface")] == "10.0.0.1"


@pytest.mark.asyncio
async def test_import_devices(db):
    toml_str = '''
[devices."Kitchen Strip"]
backend = "lifx"
led_count = 60
ip = "192.168.1.42"
mac = "d073d5aabb"
'''
    await import_toml(db, toml_str)
    devices = await db.load_devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "Kitchen Strip"
    assert devices[0]["backend"] == "lifx"


@pytest.mark.asyncio
async def test_import_scenes(db):
    # Need a device first for placement FK
    await db.upsert_device(id="lifx:aa", name="Strip", backend="lifx", led_count=60)

    toml_str = '''
[scenes."dj-booth"]
name = "DJ Booth"
mapping_type = "linear"
effect_mode = "independent"
is_active = true

[scenes."dj-booth".effect]
effect_class = "beat_pulse"
params = { gamma = 3.0 }

[scenes."dj-booth".placements."Strip"]
position = [1.0, 2.0, 3.0]
geometry = "strip"
direction = [1.0, 0.0, 0.0]
length = 1.5
'''
    await import_toml(db, toml_str)
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["name"] == "DJ Booth"

    state = await db.load_scene_effect_state("dj-booth")
    assert state is not None
    assert state["params"]["gamma"] == 3.0

    placements = await db.load_scene_placements("dj-booth")
    assert len(placements) == 1
    assert placements[0]["position_x"] == 1.0


@pytest.mark.asyncio
async def test_import_presets(db):
    toml_str = '''
[presets."My Preset"]
effect_class = "beat_pulse"
params = { gamma = 2.5 }
'''
    await import_toml(db, toml_str)
    presets = await db.load_presets()
    assert "My Preset" in presets
    assert presets["My Preset"]["params"]["gamma"] == 2.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_toml_io.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement toml_io.py**

Create `src/dj_ledfx/persistence/toml_io.py`:

```python
"""TOML import/export marshaling for StateDB."""
from __future__ import annotations

from typing import Any

import tomli_w
import tomllib

from dj_ledfx.persistence.state_db import StateDB


async def export_toml(db: StateDB) -> str:
    """Export entire DB state as structured TOML."""
    data: dict[str, Any] = {}

    # Config: group by section into nested tables
    config = await db.load_config()
    if config:
        config_dict: dict[str, dict[str, Any]] = {}
        for (section, key), value in config.items():
            config_dict.setdefault(section, {})[key] = value
        data["config"] = config_dict

    # Devices: keyed by display name
    devices = await db.load_devices()
    if devices:
        devices_dict: dict[str, dict[str, Any]] = {}
        for d in devices:
            entry: dict[str, Any] = {}
            for k in ("backend", "led_count", "ip", "mac", "device_id", "sku", "last_latency_ms"):
                if d.get(k) is not None:
                    entry[k] = d[k]
            devices_dict[d["name"]] = entry
        data["devices"] = devices_dict

    # Scenes
    scenes = await db.load_scenes()
    if scenes:
        scenes_dict: dict[str, dict[str, Any]] = {}
        for s in scenes:
            entry = {
                "name": s["name"],
                "mapping_type": s["mapping_type"],
                "effect_mode": s["effect_mode"],
                "is_active": bool(s["is_active"]),
            }
            if s.get("mapping_params"):
                entry["mapping_params"] = s["mapping_params"]
            if s.get("effect_source"):
                entry["effect_source"] = s["effect_source"]

            # Effect state
            effect_state = await db.load_scene_effect_state(s["id"])
            if effect_state:
                entry["effect"] = {
                    "effect_class": effect_state["effect_class"],
                    "params": effect_state["params"],
                }

            # Placements
            placements = await db.load_scene_placements(s["id"])
            if placements:
                # Resolve device_id to display name
                all_devices = await db.load_devices()
                id_to_name = {d["id"]: d["name"] for d in all_devices}
                pl_dict: dict[str, dict[str, Any]] = {}
                for p in placements:
                    name = id_to_name.get(p["device_id"], p["device_id"])
                    pl_entry: dict[str, Any] = {
                        "position": [p["position_x"], p["position_y"], p["position_z"]],
                        "geometry": p["geometry_type"],
                    }
                    if p.get("direction_x") is not None:
                        pl_entry["direction"] = [
                            p["direction_x"], p["direction_y"], p["direction_z"]
                        ]
                    for k in ("length", "width", "rows", "cols"):
                        if p.get(k) is not None:
                            pl_entry[k] = p[k]
                    pl_dict[name] = pl_entry
                entry["placements"] = pl_dict

            scenes_dict[s["id"]] = entry
        data["scenes"] = scenes_dict

    # Groups
    groups = await db.load_groups()
    device_group_map = await db.load_device_groups()
    if groups:
        all_devices = await db.load_devices()
        id_to_name = {d["id"]: d["name"] for d in all_devices}
        groups_dict: dict[str, dict[str, Any]] = {}
        for gname, color in groups.items():
            members = [
                id_to_name.get(did, did)
                for did, gn in device_group_map.items()
                if gn == gname
            ]
            groups_dict[gname] = {"color": color, "devices": members}
        data["groups"] = groups_dict

    # Presets
    presets = await db.load_presets()
    if presets:
        data["presets"] = {
            name: {"effect_class": p["effect_class"], "params": p["params"]}
            for name, p in presets.items()
        }

    return tomli_w.dumps(data)


async def import_toml(db: StateDB, toml_str: str) -> None:
    """Import structured TOML into StateDB. Partial imports supported."""
    data = tomllib.loads(toml_str)

    # Config
    config_data = data.get("config", {})
    if config_data:
        triples = []
        for section, keys in config_data.items():
            if isinstance(keys, dict):
                for key, value in keys.items():
                    triples.append((section, key, value))
        if triples:
            await db.save_config_bulk(triples)

    # Devices
    devices_data = data.get("devices", {})
    for name, entry in devices_data.items():
        backend = entry.get("backend", "unknown")
        # Build stable ID from available data
        mac = entry.get("mac")
        device_id_field = entry.get("device_id")
        if mac:
            stable_id = f"{backend}:{mac}"
        elif device_id_field:
            stable_id = f"{backend}:{device_id_field}"
        else:
            stable_id = f"{backend}:{name}"

        await db.upsert_device(
            id=stable_id,
            name=name,
            backend=backend,
            led_count=entry.get("led_count"),
            ip=entry.get("ip"),
            mac=mac,
            device_id=device_id_field,
            sku=entry.get("sku"),
            last_latency_ms=entry.get("last_latency_ms"),
        )

    # Scenes
    scenes_data = data.get("scenes", {})
    for scene_id, entry in scenes_data.items():
        await db.save_scene(
            id=scene_id,
            name=entry.get("name", scene_id),
            mapping_type=entry.get("mapping_type", "linear"),
            mapping_params=entry.get("mapping_params"),
            effect_mode=entry.get("effect_mode", "independent"),
            effect_source=entry.get("effect_source"),
            is_active=entry.get("is_active", False),
        )

        # Effect state
        effect = entry.get("effect")
        if effect:
            await db.save_scene_effect_state(
                scene_id,
                effect["effect_class"],
                effect.get("params", {}),
            )

        # Placements (resolve display name to device stable_id)
        placements = entry.get("placements", {})
        all_devices = await db.load_devices()
        name_to_id = {d["name"]: d["id"] for d in all_devices}
        for device_name, pl in placements.items():
            device_stable_id = name_to_id.get(device_name)
            if not device_stable_id:
                continue  # device not registered, skip

            pos = pl.get("position", [0.0, 0.0, 0.0])
            direction = pl.get("direction")
            await db.save_placement(
                scene_id=scene_id,
                device_id=device_stable_id,
                position_x=pos[0], position_y=pos[1], position_z=pos[2],
                geometry_type=pl.get("geometry", "point"),
                direction_x=direction[0] if direction else None,
                direction_y=direction[1] if direction else None,
                direction_z=direction[2] if direction else None,
                length=pl.get("length"),
                width=pl.get("width"),
                rows=pl.get("rows"),
                cols=pl.get("cols"),
            )

    # Groups
    groups_data = data.get("groups", {})
    all_devices = await db.load_devices()
    name_to_id = {d["name"]: d["id"] for d in all_devices}
    for gname, entry in groups_data.items():
        await db.save_group(gname, entry.get("color", "#888888"))
        for device_name in entry.get("devices", []):
            device_id = name_to_id.get(device_name)
            if device_id:
                await db.assign_device_group(gname, device_id)

    # Presets
    presets_data = data.get("presets", {})
    for name, entry in presets_data.items():
        await db.save_preset(name, entry["effect_class"], entry.get("params", {}))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_toml_io.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/toml_io.py tests/persistence/test_toml_io.py
git commit -m "feat: add TOML import/export marshaling for StateDB"
```

---

### Task 22: First-Launch TOML Migration

**Files:**
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Test: `tests/persistence/test_state_db.py`

- [ ] **Step 1: Write tests for migration**

Add to `tests/persistence/test_state_db.py`:

```python
@pytest.mark.asyncio
async def test_migrate_from_config_toml(tmp_path):
    """Auto-import config.toml into fresh DB."""
    import tomli_w

    config_toml = tmp_path / "config.toml"
    config_data = {
        "engine": {"fps": 90},
        "effect": {"active_effect": "beat_pulse", "beat_pulse": {"gamma": 3.0, "palette": ["#ff0000"]}},
        "network": {"interface": "192.168.1.100"},
    }
    config_toml.write_bytes(tomli_w.dumps(config_data).encode())

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await db.migrate_from_toml(config_path=config_toml)

    config = await db.load_config()
    assert config[("engine", "fps")] == 90

    # Effect config should create a default scene with effect state
    scenes = await db.load_scenes()
    assert len(scenes) == 1
    assert scenes[0]["id"] == "default"

    state = await db.load_scene_effect_state("default")
    assert state is not None
    assert state["effect_class"] == "beat_pulse"
    assert state["params"]["gamma"] == 3.0

    # Original file renamed to .bak
    assert not config_toml.exists()
    assert (tmp_path / "config.toml.bak").exists()

    await db.close()


@pytest.mark.asyncio
async def test_migrate_from_presets_toml(tmp_path):
    """Auto-import presets.toml into fresh DB."""
    import tomli_w

    presets_toml = tmp_path / "presets.toml"
    presets_data = {
        "presets": {
            "My Preset": {"effect_class": "beat_pulse", "params": {"gamma": 2.5}}
        }
    }
    presets_toml.write_bytes(tomli_w.dumps(presets_data).encode())

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await db.migrate_from_toml(presets_path=presets_toml)

    presets = await db.load_presets()
    assert "My Preset" in presets
    assert presets["My Preset"]["params"]["gamma"] == 2.5

    assert not presets_toml.exists()
    assert (tmp_path / "presets.toml.bak").exists()

    await db.close()


@pytest.mark.asyncio
async def test_migrate_skips_if_no_toml(tmp_path):
    """Migration is no-op if TOML files don't exist."""
    db = StateDB(tmp_path / "state.db")
    await db.open()
    await db.migrate_from_toml(
        config_path=tmp_path / "config.toml",
        presets_path=tmp_path / "presets.toml",
    )
    # No error, DB is empty
    config = await db.load_config()
    assert config == {}
    await db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "migrate"`
Expected: FAIL

- [ ] **Step 3: Implement migration**

Add to `StateDB`:

```python
    async def migrate_from_toml(
        self,
        config_path: Path | None = None,
        presets_path: Path | None = None,
    ) -> None:
        """Auto-import config.toml and presets.toml into DB if they exist."""
        if config_path and config_path.exists():
            await self._migrate_config_toml(config_path)
            config_path.rename(config_path.with_suffix(".toml.bak"))
            logger.info("Migrated {} → DB (renamed to .bak)", config_path)

        if presets_path and presets_path.exists():
            await self._migrate_presets_toml(presets_path)
            presets_path.rename(presets_path.with_suffix(".toml.bak"))
            logger.info("Migrated {} → DB (renamed to .bak)", presets_path)

    async def _migrate_config_toml(self, path: Path) -> None:
        import tomllib as _tomllib

        with open(path, "rb") as f:
            data = _tomllib.load(f)

        # Migrate config sections
        triples: list[tuple[str, str, Any]] = []
        for section in ("engine", "network", "web"):
            for key, value in data.get(section, {}).items():
                triples.append((section, key, value))
        # Devices config (nested)
        for backend in ("openrgb", "lifx", "govee"):
            for key, value in data.get("devices", {}).get(backend, {}).items():
                triples.append((f"devices.{backend}", key, value))
        # Discovery config
        for key, value in data.get("discovery", {}).items():
            triples.append(("discovery", key, value))
        if triples:
            await self.save_config_bulk(triples)

        # Migrate effect config → default scene + scene_effect_state
        effect_data = data.get("effect", {})
        active_effect = effect_data.get("active_effect", effect_data.get("active", "beat_pulse"))
        params: dict[str, Any] = {}
        if active_effect == "beat_pulse":
            bp = effect_data.get("beat_pulse", {})
            palette = bp.get("palette", effect_data.get("beat_pulse_palette"))
            gamma = bp.get("gamma", effect_data.get("beat_pulse_gamma"))
            if palette:
                params["palette"] = palette
            if gamma:
                params["gamma"] = gamma

        await self.save_scene(id="default", name="Default", mapping_type="linear", is_active=True)
        await self.save_scene_effect_state("default", active_effect, params)

        # Migrate scene_config if present
        scene_config = data.get("scene_config") or data.get("scene")
        if scene_config and scene_config.get("devices"):
            mapping_type = scene_config.get("mapping", "linear")
            mapping_params = scene_config.get("mapping_params")
            await self.save_scene(
                id="default", name="Default",
                mapping_type=mapping_type,
                mapping_params=mapping_params,
                is_active=True,
            )

    async def _migrate_presets_toml(self, path: Path) -> None:
        import tomllib as _tomllib

        with open(path, "rb") as f:
            data = _tomllib.load(f)

        for name, entry in data.get("presets", {}).items():
            await self.save_preset(name, entry["effect_class"], entry.get("params", {}))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/persistence/test_state_db.py -v -k "migrate"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/persistence/state_db.py tests/persistence/test_state_db.py
git commit -m "feat: add TOML-to-DB first-launch migration"
```

---

## Phase 6: Discovery Orchestrator

### Task 23: DiscoveryOrchestrator — Core Multi-Wave Logic

**Files:**
- Create: `src/dj_ledfx/devices/discovery.py`
- Test: `tests/devices/test_discovery.py`

- [ ] **Step 1: Write tests**

Create `tests/devices/test_discovery.py`:

```python
"""Tests for DiscoveryOrchestrator."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig, DiscoveryConfig
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus, DiscoveryWaveCompleteEvent, DiscoveryCompleteEvent


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def device_manager(event_bus):
    return DeviceManager(event_bus=event_bus)


@pytest.fixture
def config():
    return AppConfig(discovery=DiscoveryConfig(waves=2, wave_interval_s=0.1))


@pytest.mark.asyncio
async def test_orchestrator_runs_waves(config, device_manager, event_bus):
    """Orchestrator runs configured number of waves."""
    wave_events = []
    event_bus.subscribe(DiscoveryWaveCompleteEvent, wave_events.append)

    complete_events = []
    event_bus.subscribe(DiscoveryCompleteEvent, complete_events.append)

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    # Mock backends to return empty
    orchestrator._backends = []

    await orchestrator.run_discovery()

    assert len(wave_events) == 2
    assert wave_events[0].wave == 1
    assert wave_events[1].wave == 2
    assert len(complete_events) == 1


@pytest.mark.asyncio
async def test_orchestrator_single_wave(config, device_manager, event_bus):
    """Single-wave mode."""
    config.discovery.waves = 1
    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    wave_events = []
    event_bus.subscribe(DiscoveryWaveCompleteEvent, wave_events.append)
    await orchestrator.run_discovery(waves=1)
    assert len(wave_events) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_discovery.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement DiscoveryOrchestrator**

Create `src/dj_ledfx/devices/discovery.py`:

```python
"""DiscoveryOrchestrator — multi-wave device discovery."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import (
    DeviceDiscoveredEvent,
    DeviceOnlineEvent,
    DiscoveryCompleteEvent,
    DiscoveryWaveCompleteEvent,
    EventBus,
)

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB


class DiscoveryOrchestrator:
    """Owns backend lifecycle and multi-wave discovery logic."""

    def __init__(
        self,
        config: AppConfig,
        device_manager: DeviceManager,
        event_bus: EventBus,
        state_db: StateDB | None = None,
    ) -> None:
        self._config = config
        self._manager = device_manager
        self._event_bus = event_bus
        self._state_db = state_db
        self._running = False
        self._reconnect_task: asyncio.Task[None] | None = None

        # Instantiate backends once — reused across waves
        self._backends: list[DeviceBackend] = []
        for cls in DeviceBackend._registry:
            backend = cls()
            if backend.is_enabled(config):
                self._backends.append(backend)

    async def run_discovery(self, waves: int | None = None) -> int:
        """Run multi-wave discovery. Returns total devices found."""
        num_waves = waves or self._config.discovery.waves
        total_found = 0

        for wave_num in range(1, num_waves + 1):
            logger.info("Discovery wave {}/{}", wave_num, num_waves)
            found = await self._run_wave()
            total_found += found
            self._event_bus.emit(
                DiscoveryWaveCompleteEvent(wave=wave_num, devices_found=found)
            )
            if wave_num < num_waves:
                await asyncio.sleep(self._config.discovery.wave_interval_s)

        self._event_bus.emit(DiscoveryCompleteEvent(total_devices=total_found))
        logger.info("Discovery complete: {} total devices", total_found)
        return total_found

    async def _run_wave(self) -> int:
        """Run one discovery wave across all backends. Returns devices found."""
        results = await asyncio.gather(
            *(self._discover_backend(b) for b in self._backends),
            return_exceptions=True,
        )
        found = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error("Backend discovery failed: {}", result)
                continue
            found += result
        return found

    async def _discover_backend(self, backend: DeviceBackend) -> int:
        """Discover devices from a single backend. Returns count of new devices."""
        try:
            discovered = await backend.discover(self._config)
        except Exception:
            logger.exception("Discovery failed for {}", type(backend).__name__)
            return 0

        new_count = 0
        for device in discovered:
            stable_id = device.adapter.device_info.stable_id
            name = device.adapter.device_info.name
            if not stable_id:
                stable_id = name

            existing = self._manager.get_by_stable_id(stable_id)
            if existing is None:
                # Also check by name for backward compat
                existing_by_name = self._manager.get_device(name)
                if existing_by_name is None:
                    self._manager.add_device(device.adapter, device.tracker, device.max_fps)
                    self._event_bus.emit(
                        DeviceDiscoveredEvent(stable_id=stable_id, name=name)
                    )
                    new_count += 1
                    # Persist to DB
                    if self._state_db:
                        await self._persist_device(device.adapter)
            elif existing.status == "offline":
                # Promote offline → online
                self._manager.promote_device(stable_id, device.adapter)
                self._event_bus.emit(
                    DeviceOnlineEvent(stable_id=stable_id, name=name)
                )
                if self._state_db:
                    await self._persist_device(device.adapter)

        return new_count

    async def _persist_device(self, adapter: object) -> None:
        """Persist discovered device to DB."""
        if not self._state_db:
            return
        from datetime import datetime, timezone
        info = adapter.device_info  # type: ignore[attr-defined]
        await self._state_db.upsert_device(
            id=info.stable_id or info.name,
            name=info.name,
            backend=info.device_type.split("_")[0],  # "lifx_strip" → "lifx"
            led_count=adapter.led_count,  # type: ignore[attr-defined]
            ip=info.address.split(":")[0] if ":" in info.address else info.address,
            mac=info.mac,
            last_seen=datetime.now(timezone.utc).isoformat(),
        )

    async def start_reconnect_loop(self) -> None:
        """Start background reconnect loop for offline devices."""
        self._running = True
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        interval = self._config.discovery.reconnect_interval_s
        while self._running:
            await asyncio.sleep(interval)
            # For now, just re-run a single wave
            offline_count = sum(
                1 for d in self._manager.devices if d.status == "offline"
            )
            if offline_count > 0:
                logger.debug("Reconnect loop: {} offline devices", offline_count)
                await self._run_wave()

    async def shutdown(self) -> None:
        """Stop reconnect loop and shut down backends."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        for backend in self._backends:
            try:
                await backend.shutdown()
            except Exception:
                logger.exception("Backend shutdown failed")
        self._backends.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/test_discovery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/discovery.py tests/devices/test_discovery.py
git commit -m "feat: add DiscoveryOrchestrator with multi-wave scanning"
```

---

## Phase 7: Web API Updates

### Task 24: Web App — Accept StateDB

**Files:**
- Modify: `src/dj_ledfx/web/app.py`

- [ ] **Step 1: Update create_app signature**

In `src/dj_ledfx/web/app.py`, add `state_db` parameter (optional for backward compat):

```python
if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB

def create_app(
    *,
    beat_clock: BeatClock,
    effect_deck: EffectDeck,
    effect_engine: EffectEngine,
    device_manager: DeviceManager,
    scheduler: LookaheadScheduler,
    preset_store: PresetStore,
    scene_model: object | None,
    compositor: object | None,
    config: AppConfig,
    config_path: Path | None,
    web_static_dir: str | None = None,
    state_db: StateDB | None = None,
) -> FastAPI:
```

Add to state storage:

```python
    app.state.state_db = state_db
```

- [ ] **Step 2: Run existing web tests**

Run: `uv run pytest tests/web/ -v`
Expected: All pass (new param is optional, defaults to None)

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/web/app.py
git commit -m "feat: add state_db parameter to create_app"
```

---

### Task 25: Config Router — DB Backend

**Files:**
- Modify: `src/dj_ledfx/web/router_config.py`
- Test: `tests/web/test_router_config.py`

- [ ] **Step 1: Read current router**

Read `src/dj_ledfx/web/router_config.py` to understand current implementation.

- [ ] **Step 2: Update config router**

Update `PUT /api/config` to save to StateDB when available (falling back to TOML). The key change is: when `request.app.state.state_db` is not None, call `save_config_key()` for each changed field instead of `save_config()` to TOML.

Add state import/export endpoints:

```python
@router.get("/state/export")
async def export_state(request: Request) -> Response:
    from dj_ledfx.persistence.toml_io import export_toml
    db = request.app.state.state_db
    if db is None:
        raise HTTPException(503, "StateDB not available")
    toml_str = await export_toml(db)
    return Response(content=toml_str, media_type="application/toml")


@router.post("/state/import")
async def import_state(request: Request) -> dict[str, str]:
    from dj_ledfx.persistence.toml_io import import_toml
    db = request.app.state.state_db
    if db is None:
        raise HTTPException(503, "StateDB not available")
    body = await request.body()
    await import_toml(db, body.decode())
    return {"status": "ok"}
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/web/test_router_config.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/dj_ledfx/web/router_config.py tests/web/test_router_config.py
git commit -m "feat: add DB-backed config persistence and state import/export endpoints"
```

---

### Task 26: Device Router — Scan Endpoint and Status

**Files:**
- Modify: `src/dj_ledfx/web/router_devices.py`
- Test: `tests/web/test_router_devices.py`

- [ ] **Step 1: Read current router**

Read `src/dj_ledfx/web/router_devices.py`.

- [ ] **Step 2: Update device router**

Key changes:
- Replace `POST /devices/discover` with `POST /devices/scan` that uses `DiscoveryOrchestrator` if available on `app.state`, falls back to `manager.rediscover()`
- Add `status` field to device responses (include `ManagedDevice.status` in JSON response body)
- Add `DELETE /devices/{device_name}` to unregister device (deletes from DB, cascades to groups/placements)
- Add `PUT /devices/{device_name}` to edit metadata (rename, override LED count)
- **Also update `src/dj_ledfx/web/ws.py`:** Include `status` string field in the device stats JSON broadcast alongside the existing `connected` boolean. The `status` field comes from `ManagedDevice.status` ("online"/"offline"/"reconnecting") and provides more detail than the boolean `connected`.

- [ ] **Step 3: Update tests**

Update `tests/web/test_router_devices.py` to test new endpoints and ensure old tests still work.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_router_devices.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/router_devices.py tests/web/test_router_devices.py
git commit -m "feat: add device scan endpoint and status to device router"
```

---

### Task 27: Scene Router — Multi-Scene CRUD

**Files:**
- Modify: `src/dj_ledfx/web/router_scene.py`
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Read current router**

Read `src/dj_ledfx/web/router_scene.py` to understand the single-scene implementation.

- [ ] **Step 2: Rewrite scene router for multi-scene**

The existing scene router operates on a single `app.state.scene_model`. The new router needs to:

- Store `pipelines: dict[str, ScenePipeline]` on `app.state` (keyed by scene_id)
- `GET /scenes` — list all scenes from DB
- `POST /scenes` — create scene in DB
- `GET /scenes/{scene_id}` — scene details
- `PUT /scenes/{scene_id}` — update scene
- `DELETE /scenes/{scene_id}` — delete scene from DB
- `POST /scenes/{scene_id}/activate` — build ScenePipeline, add to engine, check device conflicts
- `POST /scenes/{scene_id}/deactivate` — remove from engine
- `PUT /scenes/{scene_id}/devices/{device_name}` — add/update placement
- `DELETE /scenes/{scene_id}/devices/{device_name}` — remove placement
- `PUT /scenes/{scene_id}/mapping` — update mapping
- `PUT /scenes/{scene_id}/effect` — set effect
- `POST /scenes/{scene_id}/effect/share/{source_scene_id}` — share effect

**Backward compatibility:** Keep legacy `GET /scene` as redirect to default scene for any frontend code not yet updated.

- [ ] **Step 3: Update tests**

Rewrite `tests/web/test_router_scene.py` for multi-scene API. At minimum test:
- Create scene
- List scenes
- Add placement
- Activate scene (success + 409 conflict)
- Deactivate scene
- Delete scene

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_router_scene.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "feat: rewrite scene router for multi-scene CRUD with activation"
```

---

### Task 28: Effects Router — Auto-Save

**Files:**
- Modify: `src/dj_ledfx/web/router_effects.py`
- Test: `tests/web/test_router_effects.py`

- [ ] **Step 1: Read current router**

Read `src/dj_ledfx/web/router_effects.py`.

- [ ] **Step 2: Update to trigger auto-save**

When `app.state.state_db` is available and a scene is active:
- After `deck.apply_update()`, the `on_change` callback (set up in main.py) schedules a debounced write via `state_db.schedule_effect_state_update()`
- Preset save/delete uses `preset_store.save_async()`/`delete_async()` instead of sync methods

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/web/test_router_effects.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/dj_ledfx/web/router_effects.py tests/web/test_router_effects.py
git commit -m "feat: add auto-save to effects router via deck callback"
```

---

## Phase 8: Main Startup Integration

### Task 29: Rewrite main.py Startup Flow

**Files:**
- Modify: `src/dj_ledfx/main.py`

This is the critical integration task. The new startup flow:

1. Open `state.db` (create if missing, run migrations)
2. Run TOML migration if `config.toml`/`presets.toml` exist and DB is fresh
3. Load config from DB → build `AppConfig`
4. Load registered devices → create `ManagedDevice` entries with `status="offline"` and `GhostAdapter`
5. Load active scenes → build `ScenePipeline` per active scene (independent first, then shared)
6. Start engine, scheduler
7. Launch `DiscoveryOrchestrator` background discovery
8. Launch reconnect loop

- [ ] **Step 1: Read current main.py**

Already read. Current flow: `load_config` → discover devices → build scene → build engine → build scheduler → start.

- [ ] **Step 2: Implement new startup flow**

Update `_run()` in `src/dj_ledfx/main.py`:

```python
async def _run(args: argparse.Namespace) -> None:
    from dj_ledfx.persistence.state_db import StateDB

    # Step 1: Open StateDB
    db_dir = args.config.parent
    state_db = StateDB(db_dir / "state.db")
    await state_db.open()

    # Step 2: TOML migration (first launch only)
    config_toml = args.config
    presets_toml = db_dir / "presets.toml"
    if await state_db.get_schema_version() == 1:
        # Check if DB is empty (fresh migration)
        config_data = await state_db.load_config()
        if not config_data:
            await state_db.migrate_from_toml(
                config_path=config_toml if config_toml.exists() else None,
                presets_path=presets_toml if presets_toml.exists() else None,
            )

    # Step 3: Load config
    config = await _load_config_from_db(state_db, args)
    metrics.init(enabled=args.metrics, port=args.metrics_port)

    event_bus = EventBus()
    clock = BeatClock()

    # Beat handling (unchanged)
    def on_beat(event: BeatEvent) -> None:
        metrics.BEATS_RECEIVED.inc()
        clock.on_beat(
            bpm=event.bpm, beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms, timestamp=event.timestamp,
            pitch_percent=event.pitch_percent,
            device_number=event.device_number, device_name=event.device_name,
        )
    event_bus.subscribe(BeatEvent, on_beat)

    simulator: BeatSimulator | None = None
    if args.demo:
        logger.info("Starting in demo mode at {:.1f} BPM", args.bpm)
        simulator = BeatSimulator(event_bus=event_bus, bpm=args.bpm)
    else:
        logger.info("Starting Pro DJ Link listener")
        await start_listener(event_bus=event_bus)

    # Step 4: Load registered devices (offline with GhostAdapters)
    device_manager = DeviceManager(event_bus=event_bus)
    persisted_devices = await state_db.load_devices()
    for d in persisted_devices:
        from dj_ledfx.devices.ghost import GhostAdapter
        from dj_ledfx.latency.strategies import StaticLatency
        from dj_ledfx.latency.tracker import LatencyTracker

        info = DeviceInfo(
            name=d["name"],
            device_type=d["backend"],
            led_count=d.get("led_count") or 1,
            address=d.get("ip") or "",
            mac=d.get("mac"),
            stable_id=d["id"],
        )
        latency_ms = d.get("last_latency_ms") or 50.0
        tracker = LatencyTracker(StaticLatency(latency_ms))
        device_manager.add_device_from_info(
            info, led_count=info.led_count, tracker=tracker, status="offline"
        )

    # Step 5: Load active scenes → build ScenePipelines
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import EffectEngine, RingBuffer
    from dj_ledfx.effects.registry import create_effect
    from dj_ledfx.spatial.pipeline import ScenePipeline

    pipelines: list[ScenePipeline] = []
    pipeline_map: dict[str, ScenePipeline] = {}
    scenes = await state_db.load_scenes()
    active_scenes = [s for s in scenes if s["is_active"]]

    # Sort: independent first, then shared
    independent = [s for s in active_scenes if s["effect_mode"] == "independent"]
    shared = [s for s in active_scenes if s["effect_mode"] == "shared"]

    for scene_data in independent:
        effect_state = await state_db.load_scene_effect_state(scene_data["id"])
        if effect_state:
            effect = create_effect(effect_state["effect_class"], **effect_state["params"])
        else:
            effect = BeatPulse()
        deck = EffectDeck(
            effect,
            on_change=lambda d, sid=scene_data["id"]: state_db.schedule_effect_state_update(
                sid, d.effect_name, d.effect.get_params()
            ),
        )
        # Compute led_count from scene's devices
        placements = await state_db.load_scene_placements(scene_data["id"])
        scene_led_count = max(
            (device_manager.get_by_stable_id(p["device_id"]).adapter.led_count
             for p in placements
             if device_manager.get_by_stable_id(p["device_id"])),
            default=60,
        )
        buf = RingBuffer(capacity=config.engine.fps, led_count=scene_led_count)
        pipeline = ScenePipeline(
            scene_id=scene_data["id"],
            deck=deck,
            ring_buffer=buf,
            compositor=None,  # TODO: build from mapping
            mapping=None,
            devices=[
                device_manager.get_by_stable_id(p["device_id"])
                for p in placements
                if device_manager.get_by_stable_id(p["device_id"])
            ],
            led_count=scene_led_count,
        )
        pipelines.append(pipeline)
        pipeline_map[scene_data["id"]] = pipeline

    for scene_data in shared:
        source_id = scene_data.get("effect_source")
        source_pipeline = pipeline_map.get(source_id) if source_id else None
        if source_pipeline:
            deck = source_pipeline.deck  # shared reference
        else:
            deck = EffectDeck(BeatPulse())  # fallback

        placements = await state_db.load_scene_placements(scene_data["id"])
        scene_led_count = max(
            (device_manager.get_by_stable_id(p["device_id"]).adapter.led_count
             for p in placements
             if device_manager.get_by_stable_id(p["device_id"])),
            default=60,
        )
        buf = RingBuffer(capacity=config.engine.fps, led_count=scene_led_count)
        pipeline = ScenePipeline(
            scene_id=scene_data["id"],
            deck=deck,
            ring_buffer=buf,
            compositor=None,
            mapping=None,
            devices=[
                device_manager.get_by_stable_id(p["device_id"])
                for p in placements
                if device_manager.get_by_stable_id(p["device_id"])
            ],
            led_count=scene_led_count,
        )
        pipelines.append(pipeline)
        pipeline_map[scene_data["id"]] = pipeline

    # Fallback: if no scenes, use legacy single-deck mode
    if not pipelines:
        default_deck = EffectDeck(BeatPulse())
        led_count = device_manager.max_led_count or 60
    else:
        default_deck = pipelines[0].deck
        led_count = pipelines[0].led_count

    engine = EffectEngine(
        clock=clock,
        deck=default_deck,
        led_count=led_count,
        fps=config.engine.fps,
        max_lookahead_s=config.engine.max_lookahead_ms / 1000.0,
        pipelines=pipelines,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=device_manager.devices,
        fps=config.engine.fps,
    )

    # Assign pipeline references to scheduler device states
    for pipeline in pipelines:
        for managed in pipeline.devices:
            key = managed.adapter.device_info.stable_id or managed.adapter.device_info.name
            if key in scheduler._device_state:
                scheduler._device_state[key].pipeline = pipeline

    # Step 6: Web server (if enabled)
    # ... (same web setup as before, but pass state_db)
    # PresetStore now uses DB backend
    # create_app now receives state_db=state_db

    # Step 7: Background discovery
    from dj_ledfx.devices.discovery import DiscoveryOrchestrator
    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
        state_db=state_db,
    )

    # ... (start tasks, including orchestrator.run_discovery() as background task)
    # ... (start reconnect loop)
    # ... (shutdown: await state_db.close())
```

This is a sketch — the implementer should preserve the full web server setup, signal handling, profiling, and shutdown logic from the existing `main.py` while integrating the new DB-backed flow.

- [ ] **Step 3: Add helper function for loading config from DB**

```python
async def _load_config_from_db(state_db: StateDB, args: argparse.Namespace) -> AppConfig:
    """Build AppConfig from StateDB, falling back to TOML if DB is empty."""
    config_data = await state_db.load_config()
    if not config_data:
        # DB empty — use TOML as fallback
        return load_config(args.config)

    from dj_ledfx.config import (
        AppConfig, EngineConfig, NetworkConfig, WebConfig,
        DevicesConfig, OpenRGBConfig, LIFXConfig, GoveeConfig,
        DiscoveryConfig, EffectConfig, _filter_fields,
    )

    def _section_dict(section: str) -> dict[str, Any]:
        return {k: v for (s, k), v in config_data.items() if s == section}

    return AppConfig(
        engine=EngineConfig(**_filter_fields(EngineConfig, _section_dict("engine"))),
        effect=EffectConfig(**_filter_fields(EffectConfig, _section_dict("effect"))),
        network=NetworkConfig(**_filter_fields(NetworkConfig, _section_dict("network"))),
        web=WebConfig(**_filter_fields(WebConfig, _section_dict("web"))),
        devices=DevicesConfig(
            openrgb=OpenRGBConfig(**_filter_fields(OpenRGBConfig, _section_dict("devices.openrgb"))),
            lifx=LIFXConfig(**_filter_fields(LIFXConfig, _section_dict("devices.lifx"))),
            govee=GoveeConfig(**_filter_fields(GoveeConfig, _section_dict("devices.govee"))),
        ),
        discovery=DiscoveryConfig(**_filter_fields(DiscoveryConfig, _section_dict("discovery"))),
    )


async def _save_config_to_db(state_db: StateDB, config: AppConfig) -> None:
    """Serialize AppConfig into StateDB config table rows."""
    import dataclasses

    triples: list[tuple[str, str, Any]] = []
    for section_name, section_obj in [
        ("engine", config.engine),
        ("network", config.network),
        ("web", config.web),
        ("discovery", config.discovery),
    ]:
        for f in dataclasses.fields(section_obj):
            triples.append((section_name, f.name, getattr(section_obj, f.name)))
    # Nested device configs
    for backend_name, backend_obj in [
        ("devices.openrgb", config.devices.openrgb),
        ("devices.lifx", config.devices.lifx),
        ("devices.govee", config.devices.govee),
    ]:
        for f in dataclasses.fields(backend_obj):
            triples.append((backend_name, f.name, getattr(backend_obj, f.name)))
    await state_db.save_config_bulk(triples)
```

This helper is used by the config router (Task 25) when `PUT /api/config` saves changes to the DB. The router should call `await _save_config_to_db(state_db, updated_config)` instead of `save_config(config, path)` when `state_db` is available. Place this function in `src/dj_ledfx/config.py` alongside `load_config()`, or inline in `main.py` — the implementer should choose based on import hygiene.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat: rewrite main.py startup flow for DB-backed persistence"
```

---

### Task 30: Integration Test — Full Startup with DB

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Add to `tests/test_integration.py`:

```python
@pytest.mark.asyncio
async def test_startup_with_fresh_db(tmp_path):
    """Full startup with empty DB (no TOML migration)."""
    from dj_ledfx.persistence.state_db import StateDB

    db = StateDB(tmp_path / "state.db")
    await db.open()

    # DB should be empty but have schema
    version = await db.get_schema_version()
    assert version == 1

    devices = await db.load_devices()
    assert devices == []

    scenes = await db.load_scenes()
    assert scenes == []

    await db.close()


@pytest.mark.asyncio
async def test_startup_with_migrated_toml(tmp_path):
    """Full startup migrates config.toml into DB."""
    import tomli_w
    from dj_ledfx.persistence.state_db import StateDB

    # Create config.toml
    config_toml = tmp_path / "config.toml"
    config_toml.write_bytes(tomli_w.dumps({
        "engine": {"fps": 90},
        "effect": {"active_effect": "beat_pulse", "beat_pulse": {"gamma": 3.0}},
    }).encode())

    # Create presets.toml
    presets_toml = tmp_path / "presets.toml"
    presets_toml.write_bytes(tomli_w.dumps({
        "presets": {"Test": {"effect_class": "beat_pulse", "params": {"gamma": 2.0}}}
    }).encode())

    db = StateDB(tmp_path / "state.db")
    await db.open()
    await db.migrate_from_toml(config_path=config_toml, presets_path=presets_toml)

    config = await db.load_config()
    assert config[("engine", "fps")] == 90

    presets = await db.load_presets()
    assert "Test" in presets

    # TOML files renamed
    assert not config_toml.exists()
    assert (tmp_path / "config.toml.bak").exists()

    await db.close()
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for DB-backed startup"
```

---

### Task 31: Transport Layer Improvements (LIFX)

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/transport.py`

- [ ] **Step 1: Increase GetVersion timeout**

In `src/dj_ledfx/devices/lifx/transport.py`, find the `request_response` call for GetVersion (msg_type 32) and increase timeout from 100ms to 500ms. Add retry logic: if first attempt returns None, retry once.

- [ ] **Step 2: Add broadcast retries**

In the `discover()` method, send GetService broadcast 3 times (1 second apart) instead of once. Collect all responses, dedup by MAC.

- [ ] **Step 3: Add unicast_sweep method stub**

```python
    async def unicast_sweep(
        self,
        subnet_hosts: list[str],
        concurrency: int = 50,
        timeout_s: float = 0.5,
    ) -> list[LifxDeviceRecord]:
        """Send GetService to every IP in the list. Rate-limited."""
        # Implementation: asyncio.Semaphore for concurrency, gather results
        ...
```

- [ ] **Step 4: Run existing tests**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/lifx/transport.py
git commit -m "feat: increase LIFX timeouts, add broadcast retries and unicast sweep"
```

---

### Task 32: Transport Layer Improvements (Govee)

**Files:**
- Modify: `src/dj_ledfx/devices/govee/transport.py`

- [ ] **Step 1: Add port 4002 bind retry**

In `GoveeTransport`, when binding the receiver socket to port 4002, add retry with exponential backoff (3 attempts, 1s/2s/4s). Log warning if bind fails after retries.

- [ ] **Step 2: Increase discovery window**

Change default `timeout_s` from 5.0 to 10.0 in `discover()`.

- [ ] **Step 3: Add unicast_sweep method stub**

```python
    async def unicast_sweep(
        self,
        hosts: list[str],
        concurrency: int = 50,
        timeout_s: float = 0.5,
    ) -> list[GoveeDeviceRecord]:
        """Send scan command to every IP on port 4001."""
        ...
```

- [ ] **Step 4: Run existing tests**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/transport.py
git commit -m "feat: add Govee port retry, increased window, and unicast sweep"
```

---

### Task 33: OpenRGB Connection Timeout and Retry

**Files:**
- Modify: `src/dj_ledfx/devices/openrgb_backend.py`

- [ ] **Step 1: Add connection timeout**

Wrap the OpenRGB client connection in `asyncio.wait_for(..., timeout=5.0)`. If it times out, log warning and retry once.

- [ ] **Step 2: Run tests**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/devices/openrgb_backend.py
git commit -m "feat: add 5s connection timeout and retry for OpenRGB"
```

---

### Task 34: Final Full Test Suite and Lint

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All pass

- [ ] **Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Run formatter**

Run: `uv run ruff format .`

- [ ] **Step 4: Run type checker**

Run: `uv run mypy src/`
Expected: No new errors (existing ones acceptable)

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: lint, format, and type-check cleanup"
```

---

## Summary

| Phase | Tasks | What's Delivered |
|-------|-------|-----------------|
| 1: Foundation | 1-11 | DeviceInfo stable IDs, events, DiscoveryConfig, GhostAdapter, StateDB with full CRUD + debounce |
| 2: Device Lifecycle | 12-15 | All backends populate stable_id; DeviceManager promote/demote/remove |
| 3: Multi-Scene | 16-19 | ScenePipeline, multi-pipeline EffectEngine, EffectDeck on_change, DB-backed PresetStore |
| 4: Scheduler | 20 | Dict-based DeviceSendState, dynamic add/remove, per-device pipeline refs |
| 5: Migration | 21-22 | TOML import/export marshaling, first-launch TOML→DB migration |
| 6: Discovery | 23 | DiscoveryOrchestrator with multi-wave scanning and reconnect loop |
| 7: Web API | 24-28 | Updated routers: config (DB), devices (scan/status), scenes (multi-scene CRUD), effects (auto-save) |
| 8: Integration | 29-34 | main.py rewrite, integration tests, transport improvements, lint |
