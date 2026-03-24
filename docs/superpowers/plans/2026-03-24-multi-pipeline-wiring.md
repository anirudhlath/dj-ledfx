# Multi-Pipeline Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up multi-pipeline rendering end-to-end so different scenes can run different effects on different device groups simultaneously.

**Architecture:** A new `PipelineManager` class orchestrates the lifecycle of `ScenePipeline` objects — building them from DB state on startup, creating/destroying them at runtime when scenes activate/deactivate, and mediating between the web layer and the engine/scheduler. The structural primitives (`ScenePipeline`, engine multi-pipeline iteration, scheduler per-device pipeline routing) already exist and need minimal changes.

**Tech Stack:** Python 3.12, asyncio, FastAPI, SQLite (StateDB), numpy, loguru, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-24-multi-pipeline-wiring-design.md`

---

## File Structure

### New files:
- `src/dj_ledfx/spatial/pipeline_manager.py` — PipelineManager class (central orchestrator)
- `tests/spatial/test_pipeline_manager.py` — PipelineManager unit tests

### Modified files:
- `src/dj_ledfx/config.py` — Add `unassigned_device_mode` to `EngineConfig`
- `src/dj_ledfx/effects/engine.py` — Add `add_pipeline()`, `remove_pipeline()`, shared-buffer dedup in `tick()`
- `src/dj_ledfx/scheduling/scheduler.py` — Add `remove_pipeline_refs()`
- `src/dj_ledfx/main.py` — Wire PipelineManager into startup, replace device event handlers
- `src/dj_ledfx/web/app.py` — Add `pipeline_manager` to `create_app()` and `app.state`
- `src/dj_ledfx/web/router_scene.py` — Wire activate/deactivate to PipelineManager, add scene effect endpoints, fix deactivate raw SQL
- `src/dj_ledfx/web/ws.py` — Add `scene_id` to `set_effect` command

### Test files:
- `tests/effects/test_engine.py` — Add shared-buffer dedup test
- `tests/scheduling/test_scheduler.py` — Add `remove_pipeline_refs` test
- `tests/web/test_router_scene.py` — Add pipeline wiring tests for activate/deactivate/effect
- `tests/web/test_ws.py` — Add `set_effect` with `scene_id` test
- `tests/test_integration.py` — Add multi-pipeline integration test

---

## Task 1: Add `unassigned_device_mode` to EngineConfig

**Files:**
- Modify: `src/dj_ledfx/config.py:12-15`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py — add to existing file or create
from dj_ledfx.config import EngineConfig

def test_engine_config_unassigned_device_mode_default():
    cfg = EngineConfig()
    assert cfg.unassigned_device_mode == "default_effect"

def test_engine_config_unassigned_device_mode_idle():
    cfg = EngineConfig(unassigned_device_mode="idle")
    assert cfg.unassigned_device_mode == "idle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v -k "unassigned_device_mode"`
Expected: FAIL — `EngineConfig` has no field `unassigned_device_mode`

- [ ] **Step 3: Write minimal implementation**

In `src/dj_ledfx/config.py`, modify `EngineConfig` (line 12):

```python
@dataclass
class EngineConfig:
    fps: int = 60
    max_lookahead_ms: int = 1000
    unassigned_device_mode: str = "default_effect"  # "default_effect" | "idle"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v -k "unassigned_device_mode"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py
git commit -m "feat: add unassigned_device_mode to EngineConfig"
```

---

## Task 2: Add `add_pipeline()`, `remove_pipeline()`, and shared-buffer dedup to EffectEngine

**Files:**
- Modify: `src/dj_ledfx/effects/engine.py:72-177`
- Test: `tests/effects/test_engine.py`

- [ ] **Step 1: Write the failing test for `add_pipeline`**

In `tests/effects/test_engine.py`, add:

```python
def test_engine_add_pipeline(clock):
    deck = EffectDeck(BeatPulse())
    engine = EffectEngine(clock=clock, deck=deck, led_count=10, fps=60, max_lookahead_s=1.0)
    assert len(engine.pipelines) == 1  # default pipeline

    new_buf = RingBuffer(60, 20)
    new_deck = EffectDeck(BeatPulse())
    pipeline = ScenePipeline(
        scene_id="test", deck=new_deck, ring_buffer=new_buf,
        compositor=None, mapping=None, devices=[], led_count=20,
    )
    engine.add_pipeline(pipeline)
    assert len(engine.pipelines) == 2
    assert engine.pipelines[1].scene_id == "test"
```

- [ ] **Step 2: Write the failing test for `remove_pipeline`**

```python
def test_engine_remove_pipeline(clock):
    deck = EffectDeck(BeatPulse())
    buf1 = RingBuffer(60, 10)
    buf2 = RingBuffer(60, 10)
    p1 = ScenePipeline(scene_id="s1", deck=deck, ring_buffer=buf1,
                        compositor=None, mapping=None, devices=[], led_count=10)
    p2 = ScenePipeline(scene_id="s2", deck=EffectDeck(BeatPulse()), ring_buffer=buf2,
                        compositor=None, mapping=None, devices=[], led_count=10)
    engine = EffectEngine(clock=clock, deck=deck, led_count=10, fps=60,
                          max_lookahead_s=1.0, pipelines=[p1, p2])

    # Write some frames
    engine.tick(0.0)
    assert buf2.count == 1

    engine.remove_pipeline("s2")
    assert len(engine.pipelines) == 1
    assert engine.pipelines[0].scene_id == "s1"
    assert buf2.count == 0  # cleared on removal
```

- [ ] **Step 3: Write the failing test for shared-buffer dedup**

```python
def test_engine_tick_shared_buffer_dedup(clock):
    """Shared-mode pipelines with same buffer only render once per tick."""
    shared_deck = EffectDeck(BeatPulse())
    shared_buf = RingBuffer(60, 10)
    p1 = ScenePipeline(scene_id="s1", deck=shared_deck, ring_buffer=shared_buf,
                        compositor=None, mapping=None, devices=[], led_count=10)
    p2 = ScenePipeline(scene_id="s2", deck=shared_deck, ring_buffer=shared_buf,
                        compositor=None, mapping=None, devices=[], led_count=10)
    engine = EffectEngine(clock=clock, deck=shared_deck, led_count=10, fps=60,
                          max_lookahead_s=1.0, pipelines=[p1, p2])

    engine.tick(0.0)
    # Only 1 frame written, not 2 (dedup by buffer identity)
    assert shared_buf.count == 1
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_engine.py -v -k "add_pipeline or remove_pipeline or shared_buffer_dedup"`
Expected: FAIL — methods don't exist

- [ ] **Step 5: Implement `add_pipeline`, `remove_pipeline`, and shared-buffer dedup**

In `src/dj_ledfx/effects/engine.py`, add methods to `EffectEngine` after `stop()` (around line 181):

```python
def add_pipeline(self, pipeline: ScenePipeline) -> None:
    """Add a pipeline to the render loop."""
    self.pipelines.append(pipeline)

def remove_pipeline(self, scene_id: str) -> None:
    """Remove a pipeline by scene_id and clear its ring buffer."""
    for i, p in enumerate(self.pipelines):
        if p.scene_id == scene_id:
            p.ring_buffer.clear()
            self.pipelines.pop(i)
            return
```

Modify `tick()` (around line 158) to add shared-buffer dedup. Replace the existing pipeline loop:

```python
        seen_buffers: set[int] = set()
        for pipeline in self.pipelines:
            buf_id = id(pipeline.ring_buffer)
            if buf_id in seen_buffers:
                continue
            seen_buffers.add(buf_id)
            colors = pipeline.deck.render(ctx, pipeline.led_count)
            frame = RenderedFrame(
                colors=colors,
                target_time=target_time,
                beat_phase=ctx.beat_phase,
                bar_phase=ctx.bar_phase,
            )
            pipeline.ring_buffer.write(frame)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_engine.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/effects/engine.py tests/effects/test_engine.py
git commit -m "feat: add pipeline lifecycle methods and shared-buffer dedup to EffectEngine"
```

---

## Task 3: Add `remove_pipeline_refs()` to LookaheadScheduler

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py:189-195`
- Test: `tests/scheduling/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

In `tests/scheduling/test_scheduler.py`, add:

```python
async def test_remove_pipeline_refs():
    """remove_pipeline_refs nulls out pipeline for devices referencing that scene."""
    from dj_ledfx.spatial.pipeline import ScenePipeline
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.effects.beat_pulse import BeatPulse

    d1 = _make_device("Dev1", latency_ms=10.0)
    d2 = _make_device("Dev2", latency_ms=10.0)
    buf = RingBuffer(60, 10)
    deck = EffectDeck(BeatPulse())
    pipeline = ScenePipeline(
        scene_id="scene1", deck=deck, ring_buffer=buf,
        compositor=None, mapping=None, devices=[d1, d2], led_count=10,
    )
    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[], fps=60)
    scheduler.add_device(d1, pipeline=pipeline)
    scheduler.add_device(d2, pipeline=pipeline)

    # Both devices should have pipeline set
    for state in scheduler._device_state.values():
        assert state.pipeline is pipeline

    scheduler.remove_pipeline_refs("scene1")

    # Both devices should have pipeline cleared
    for state in scheduler._device_state.values():
        assert state.pipeline is None
```

- [ ] **Step 2: Write a test for remove_pipeline_refs with mixed pipelines**

```python
async def test_remove_pipeline_refs_only_affects_target_scene():
    """remove_pipeline_refs only nulls devices in the target scene, not others."""
    from dj_ledfx.spatial.pipeline import ScenePipeline
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.effects.beat_pulse import BeatPulse

    d1 = _make_device("Dev1", latency_ms=10.0)
    d2 = _make_device("Dev2", latency_ms=10.0)
    buf = RingBuffer(60, 10)
    deck = EffectDeck(BeatPulse())
    pipeline_a = ScenePipeline(
        scene_id="sceneA", deck=deck, ring_buffer=buf,
        compositor=None, mapping=None, devices=[d1], led_count=10,
    )
    pipeline_b = ScenePipeline(
        scene_id="sceneB", deck=deck, ring_buffer=buf,
        compositor=None, mapping=None, devices=[d2], led_count=10,
    )
    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[], fps=60)
    scheduler.add_device(d1, pipeline=pipeline_a)
    scheduler.add_device(d2, pipeline=pipeline_b)

    scheduler.remove_pipeline_refs("sceneA")

    d1_key = d1.adapter.device_info.effective_id
    d2_key = d2.adapter.device_info.effective_id
    assert scheduler._device_state[d1_key].pipeline is None
    assert scheduler._device_state[d2_key].pipeline is pipeline_b
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v -k "remove_pipeline_refs"`
Expected: FAIL — method doesn't exist

- [ ] **Step 4: Implement `remove_pipeline_refs`**

In `src/dj_ledfx/scheduling/scheduler.py`, add after `set_device_pipeline` (around line 195):

```python
def remove_pipeline_refs(self, scene_id: str) -> None:
    """Null out pipeline for all devices referencing the given scene."""
    for state in self._device_state.values():
        if state.pipeline is not None and state.pipeline.scene_id == scene_id:
            state.pipeline = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v -k "remove_pipeline_refs"`
Expected: PASS

- [ ] **Step 6: Run full scheduler test suite**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat: add remove_pipeline_refs to LookaheadScheduler"
```

---

## Task 4: Implement PipelineManager

This is the largest task. The PipelineManager is the central orchestrator.

**Files:**
- Create: `src/dj_ledfx/spatial/pipeline_manager.py`
- Test: `tests/spatial/test_pipeline_manager.py`

- [ ] **Step 1: Write failing tests for PipelineManager construction and load_active_scenes**

Create `tests/spatial/test_pipeline_manager.py`:

```python
"""Tests for PipelineManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig, EngineConfig
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.events import EventBus
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.pipeline import ScenePipeline
from dj_ledfx.spatial.pipeline_manager import PipelineManager
from tests.conftest import MockDeviceAdapter


def _make_managed(name: str, led_count: int = 10, stable_id: str | None = None) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, led_count=led_count)
    if stable_id:
        from dj_ledfx.types import DeviceInfo
        patched_info = DeviceInfo(
            name=name, device_type="mock", led_count=led_count,
            address="mock", stable_id=stable_id,
        )
        # Override the property to return our patched info with stable_id
        type(adapter).device_info = property(lambda self, _info=patched_info: _info)
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    return ManagedDevice(adapter=adapter, tracker=tracker)


def _make_db_mock(scenes=None, placements=None, effect_state=None):
    """Create a mock StateDB with scene data."""
    db = AsyncMock()
    db.load_scenes = AsyncMock(return_value=scenes or [])
    db.load_scene_placements = AsyncMock(return_value=placements or [])
    db.load_scene_by_id = AsyncMock(return_value=None)
    db.load_scene_effect_state = AsyncMock(return_value=effect_state)
    db.save_scene_effect_state = AsyncMock()
    db.set_scene_active = AsyncMock()
    db.set_scene_inactive = AsyncMock()
    return db


def _make_manager(
    config: AppConfig | None = None,
    scenes=None,
    placements=None,
    devices: list[ManagedDevice] | None = None,
):
    """Create PipelineManager with mocked dependencies."""
    config = config or AppConfig()
    event_bus = EventBus()
    device_manager = DeviceManager(event_bus)
    for d in (devices or []):
        device_manager._devices.append(d)
    db = _make_db_mock(scenes=scenes, placements=placements)
    pm = PipelineManager(
        device_manager=device_manager,
        state_db=db,
        event_bus=event_bus,
        config=config,
    )
    return pm, db, device_manager


class TestPipelineManagerConstruction:
    def test_initial_state(self):
        pm, _, _ = _make_manager()
        assert pm.all_pipelines == []
        assert pm.default_deck is None

    def test_not_bound_raises_on_activate(self):
        pm, _, _ = _make_manager()
        with pytest.raises(RuntimeError, match="bind"):
            asyncio.run(pm.activate_scene("test"))


class TestLoadActiveScenes:
    async def test_no_active_scenes_creates_default_pipeline(self):
        pm, db, _ = _make_manager(
            devices=[_make_managed("Dev1", stable_id="dev1")],
        )
        db.load_scenes.return_value = []  # no scenes

        await pm.load_active_scenes()

        assert len(pm.all_pipelines) == 1
        assert pm.all_pipelines[0].scene_id == "__default__"
        assert pm.default_deck is not None

    async def test_no_active_scenes_idle_mode_no_default(self):
        config = AppConfig(engine=EngineConfig(unassigned_device_mode="idle"))
        pm, db, _ = _make_manager(config=config)
        db.load_scenes.return_value = []

        await pm.load_active_scenes()

        assert len(pm.all_pipelines) == 0
        assert pm.default_deck is None

    async def test_loads_active_independent_scene(self):
        scenes = [{"id": "s1", "name": "Scene1", "mapping_type": "linear",
                    "mapping_params": "{}", "effect_mode": "independent",
                    "effect_source": None, "is_active": 1}]
        placements = [{"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
                        "position_z": 0.0, "geometry_type": "strip",
                        "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                        "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}]
        managed = _make_managed("Dev1", led_count=20, stable_id="dev1")
        pm, db, _ = _make_manager(scenes=scenes, placements=placements, devices=[managed])
        db.load_scene_placements.return_value = placements

        await pm.load_active_scenes()

        # Should have the scene pipeline + default pipeline
        scene_pipelines = [p for p in pm.all_pipelines if p.scene_id != "__default__"]
        assert len(scene_pipelines) == 1
        assert scene_pipelines[0].scene_id == "s1"
        assert scene_pipelines[0].led_count == 20
        assert scene_pipelines[0].compositor is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_pipeline_manager.py -v`
Expected: FAIL — `pipeline_manager` module doesn't exist

- [ ] **Step 3: Implement PipelineManager core**

Create `src/dj_ledfx/spatial/pipeline_manager.py`:

```python
"""PipelineManager — orchestrates multi-pipeline lifecycle."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.effects.registry import create_effect
from dj_ledfx.events import EventBus
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.mapping import LinearMapping, mapping_from_config
from dj_ledfx.spatial.pipeline import ScenePipeline
from dj_ledfx.spatial.geometry import StripGeometry
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
    from dj_ledfx.effects.engine import EffectEngine
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.scheduling.scheduler import LookaheadScheduler


class PipelineManager:
    """Orchestrates ScenePipeline lifecycle between DB/web and engine/scheduler."""

    def __init__(
        self,
        device_manager: DeviceManager,
        state_db: StateDB,
        event_bus: EventBus,
        config: AppConfig,
    ) -> None:
        self._device_manager = device_manager
        self._state_db = state_db
        self._event_bus = event_bus
        self._config = config

        self._pipelines: dict[str, ScenePipeline] = {}
        self._default_pipeline: ScenePipeline | None = None

        # Shared mode state
        self._shared_deck: EffectDeck | None = None
        self._shared_buffer: RingBuffer | None = None

        # Late-bound references
        self._engine: EffectEngine | None = None
        self._scheduler: LookaheadScheduler | None = None

    def bind(self, engine: EffectEngine, scheduler: LookaheadScheduler) -> None:
        """Bind engine and scheduler after they are created."""
        self._engine = engine
        self._scheduler = scheduler

    def _require_bound(self) -> None:
        if self._engine is None or self._scheduler is None:
            msg = "PipelineManager.bind() must be called before runtime operations"
            raise RuntimeError(msg)

    # ── Properties ──────────────────────────────────────────────

    @property
    def all_pipelines(self) -> list[ScenePipeline]:
        """All pipelines including default."""
        pipelines = list(self._pipelines.values())
        if self._default_pipeline is not None:
            pipelines.append(self._default_pipeline)
        return pipelines

    @property
    def default_deck(self) -> EffectDeck | None:
        """The default pipeline's effect deck (for backward compat)."""
        if self._default_pipeline is not None:
            return self._default_pipeline.deck
        return None

    @property
    def default_pipeline(self) -> ScenePipeline | None:
        return self._default_pipeline

    # ── Startup ─────────────────────────────────────────────────

    async def load_active_scenes(self) -> None:
        """Load all active scenes from DB and build pipelines."""
        scenes = await self._state_db.load_scenes()
        active_scenes = [s for s in scenes if s.get("is_active")]

        for scene_row in active_scenes:
            placements = await self._state_db.load_scene_placements(scene_row["id"])
            pipeline = self._build_pipeline(scene_row, placements)
            if pipeline is not None:
                self._pipelines[scene_row["id"]] = pipeline

        self._rebuild_default_pipeline()

    # ── Runtime lifecycle ───────────────────────────────────────

    async def activate_scene(self, scene_id: str) -> ScenePipeline:
        """Build and register a pipeline for a newly activated scene."""
        self._require_bound()
        assert self._engine is not None  # for type narrowing
        assert self._scheduler is not None

        scene_row = await self._state_db.load_scene_by_id(scene_id)
        if scene_row is None:
            msg = f"Scene {scene_id} not found"
            raise ValueError(msg)

        placements = await self._state_db.load_scene_placements(scene_id)
        pipeline = self._build_pipeline(scene_row, placements)
        if pipeline is None:
            msg = f"Could not build pipeline for scene {scene_id}"
            raise ValueError(msg)

        self._pipelines[scene_id] = pipeline
        self._engine.add_pipeline(pipeline)

        # Assign devices to this pipeline in the scheduler
        for managed in pipeline.devices:
            sid = managed.adapter.device_info.effective_id
            if sid in self._scheduler._device_state:
                self._scheduler.set_device_pipeline(sid, pipeline)
            else:
                self._scheduler.add_device(managed, pipeline=pipeline)

        self._rebuild_default_pipeline()
        logger.info("Activated scene pipeline: {} ({} devices)", scene_id, len(pipeline.devices))
        return pipeline

    async def deactivate_scene(self, scene_id: str) -> None:
        """Tear down and unregister a scene's pipeline."""
        self._require_bound()
        assert self._engine is not None
        assert self._scheduler is not None

        pipeline = self._pipelines.pop(scene_id, None)
        if pipeline is None:
            return

        self._engine.remove_pipeline(scene_id)
        self._scheduler.remove_pipeline_refs(scene_id)

        # Clean up shared mode state if this was the last shared scene
        if self._shared_buffer is not None and pipeline.ring_buffer is self._shared_buffer:
            has_shared = any(
                p.ring_buffer is self._shared_buffer for p in self._pipelines.values()
            )
            if not has_shared:
                self._shared_deck = None
                self._shared_buffer = None

        self._rebuild_default_pipeline()
        logger.info("Deactivated scene pipeline: {}", scene_id)

    # ── Effect control ──────────────────────────────────────────

    def set_scene_effect(self, scene_id: str, effect_name: str, params: dict[str, Any]) -> None:
        """Set the effect for a scene's pipeline."""
        pipeline = self._pipelines.get(scene_id)
        if pipeline is None:
            msg = f"No active pipeline for scene {scene_id}"
            raise ValueError(msg)
        pipeline.deck.apply_update(effect_name, params)
        # Persist effect state
        import asyncio
        asyncio.create_task(
            self._state_db.save_scene_effect_state(
                scene_id, effect_name, json.dumps(params)
            )
        )

    def get_scene_effect(self, scene_id: str) -> dict[str, Any]:
        """Get the current effect info for a scene's pipeline."""
        pipeline = self._pipelines.get(scene_id)
        if pipeline is None:
            msg = f"No active pipeline for scene {scene_id}"
            raise ValueError(msg)
        return {
            "effect_name": pipeline.deck.effect_name,
            "params": pipeline.deck.effect.get_params(),
        }

    # ── Device assignment ───────────────────────────────────────

    def reassign_devices(self) -> None:
        """Recompute device assignments across all pipelines."""
        if self._scheduler is None:
            return

        assigned_ids: set[str] = set()
        for pipeline in self._pipelines.values():
            for managed in pipeline.devices:
                sid = managed.adapter.device_info.effective_id
                assigned_ids.add(sid)
                if sid in self._scheduler._device_state:
                    self._scheduler.set_device_pipeline(sid, pipeline)
                else:
                    self._scheduler.add_device(managed, pipeline=pipeline)

        # Handle unassigned devices
        self._rebuild_default_pipeline()

    # ── Pipeline construction ───────────────────────────────────

    def _build_pipeline(
        self, scene_row: dict[str, Any], placements: list[dict[str, Any]]
    ) -> ScenePipeline | None:
        """Build a ScenePipeline from DB scene data and placements."""
        scene_id = scene_row["id"]
        effect_mode = scene_row.get("effect_mode", "independent")

        # Resolve devices from placements
        devices: list[ManagedDevice] = []
        scene_placements: dict[str, DevicePlacement] = {}
        for p in placements:
            managed = self._device_manager.get_by_stable_id(p["device_id"])
            if managed is None:
                continue
            devices.append(managed)
            # Build geometry based on type (StripGeometry is the common case)
            geometry = StripGeometry(
                direction=(
                    p.get("direction_x", 1.0),
                    p.get("direction_y", 0.0),
                    p.get("direction_z", 0.0),
                ),
                length=p.get("length", 1.0),
            )
            placement = DevicePlacement(
                device_id=p["device_id"],
                position=(
                    p.get("position_x", 0.0),
                    p.get("position_y", 0.0),
                    p.get("position_z", 0.0),
                ),
                geometry=geometry,
                led_count=managed.adapter.device_info.led_count,
            )
            scene_placements[p["device_id"]] = placement

        led_count = max(
            (d.adapter.device_info.led_count for d in devices),
            default=self._device_manager.max_led_count or 60,
        )

        # Build spatial components
        scene_model = SceneModel(scene_placements)
        mapping_config = {
            "mapping": scene_row.get("mapping_type", "linear"),
            "mapping_params": json.loads(scene_row.get("mapping_params", "{}") or "{}"),
        }
        mapping = mapping_from_config(mapping_config)
        compositor: SpatialCompositor | None = None
        if scene_placements:
            compositor = SpatialCompositor(scene_model, mapping)

        # Build effect deck and ring buffer based on mode
        if effect_mode == "shared":
            deck, ring_buffer = self._get_or_create_shared(led_count)
        else:
            deck = self._build_deck_for_scene(scene_id)
            ring_buffer = RingBuffer(
                capacity=self._config.engine.fps, led_count=led_count,
            )

        return ScenePipeline(
            scene_id=scene_id,
            deck=deck,
            ring_buffer=ring_buffer,
            compositor=compositor,
            mapping=mapping,
            devices=devices,
            led_count=led_count,
        )

    def _get_or_create_shared(self, led_count: int) -> tuple[EffectDeck, RingBuffer]:
        """Get or create the shared deck and buffer for shared-mode scenes."""
        if self._shared_deck is None:
            self._shared_deck = EffectDeck(BeatPulse())
        if self._shared_buffer is None:
            self._shared_buffer = RingBuffer(
                capacity=self._config.engine.fps, led_count=led_count,
            )
        elif self._shared_buffer._led_count < led_count:
            # Resize: create new buffer, swap references atomically (single event loop)
            old_buffer = self._shared_buffer
            new_buffer = RingBuffer(
                capacity=self._config.engine.fps, led_count=led_count,
            )
            self._shared_buffer = new_buffer
            # Update all sharing pipelines that referenced the old buffer
            for p in self._pipelines.values():
                if p.ring_buffer is old_buffer:
                    p.ring_buffer = new_buffer
                    p.led_count = led_count
        return self._shared_deck, self._shared_buffer

    def _build_deck_for_scene(self, scene_id: str) -> EffectDeck:
        """Build an EffectDeck for an independent scene, restoring saved state."""
        return EffectDeck(BeatPulse())

    def _rebuild_default_pipeline(self) -> None:
        """Create or update the default pipeline for unassigned devices."""
        if self._config.engine.unassigned_device_mode == "idle":
            # Remove default pipeline if it exists
            if self._default_pipeline is not None:
                if self._engine is not None:
                    self._engine.remove_pipeline("__default__")
                # Cancel send tasks for devices that were on the default pipeline
                if self._scheduler is not None:
                    for managed in self._default_pipeline.devices:
                        sid = managed.adapter.device_info.effective_id
                        self._scheduler.remove_device(sid)
                self._default_pipeline = None
            return

        # Find unassigned devices
        assigned_ids: set[str] = set()
        for pipeline in self._pipelines.values():
            for managed in pipeline.devices:
                assigned_ids.add(managed.adapter.device_info.effective_id)

        unassigned = [
            d for d in self._device_manager.devices
            if d.adapter.device_info.effective_id not in assigned_ids
        ]

        led_count = max(
            (d.adapter.device_info.led_count for d in unassigned),
            default=self._device_manager.max_led_count or 60,
        )

        if self._default_pipeline is None:
            deck = EffectDeck(BeatPulse())
            ring_buffer = RingBuffer(
                capacity=self._config.engine.fps, led_count=led_count,
            )
            self._default_pipeline = ScenePipeline(
                scene_id="__default__",
                deck=deck,
                ring_buffer=ring_buffer,
                compositor=None,
                mapping=None,
                devices=unassigned,
                led_count=led_count,
            )
        else:
            self._default_pipeline.devices = unassigned

        # Update scheduler: assign unassigned devices to default pipeline
        if self._scheduler is not None:
            for managed in unassigned:
                sid = managed.adapter.device_info.effective_id
                if sid in self._scheduler._device_state:
                    self._scheduler.set_device_pipeline(sid, self._default_pipeline)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/spatial/test_pipeline_manager.py -v`
Expected: PASS

- [ ] **Step 5: Write additional tests for activate/deactivate**

Add to `tests/spatial/test_pipeline_manager.py`:

```python
class TestActivateDeactivate:
    async def test_activate_scene_creates_pipeline(self):
        scenes = [{"id": "s1", "name": "Scene1", "mapping_type": "linear",
                    "mapping_params": "{}", "effect_mode": "independent",
                    "effect_source": None, "is_active": 0}]
        managed = _make_managed("Dev1", led_count=10, stable_id="dev1")
        pm, db, _ = _make_manager(devices=[managed])
        db.load_scene_by_id.return_value = scenes[0]
        db.load_scene_placements.return_value = [
            {"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
             "position_z": 0.0, "geometry_type": "strip",
             "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
             "length": 1.0, "width": 0.0, "rows": 1, "cols": 1},
        ]

        # Bind mock engine and scheduler
        engine = MagicMock()
        scheduler = MagicMock()
        scheduler._device_state = {}
        pm.bind(engine, scheduler)

        pipeline = await pm.activate_scene("s1")

        assert pipeline.scene_id == "s1"
        assert len(pipeline.devices) == 1
        engine.add_pipeline.assert_called_once_with(pipeline)
        scheduler.add_device.assert_called_once()

    async def test_deactivate_scene_removes_pipeline(self):
        managed = _make_managed("Dev1", led_count=10, stable_id="dev1")
        pm, db, _ = _make_manager(devices=[managed])
        db.load_scene_by_id.return_value = {
            "id": "s1", "name": "Scene1", "mapping_type": "linear",
            "mapping_params": "{}", "effect_mode": "independent",
            "effect_source": None, "is_active": 1,
        }
        db.load_scene_placements.return_value = [
            {"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
             "position_z": 0.0, "geometry_type": "strip",
             "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
             "length": 1.0, "width": 0.0, "rows": 1, "cols": 1},
        ]

        engine = MagicMock()
        scheduler = MagicMock()
        scheduler._device_state = {}
        pm.bind(engine, scheduler)

        await pm.activate_scene("s1")
        assert "s1" in pm._pipelines

        await pm.deactivate_scene("s1")
        assert "s1" not in pm._pipelines
        engine.remove_pipeline.assert_called_once_with("s1")
        scheduler.remove_pipeline_refs.assert_called_once_with("s1")


class TestEffectControl:
    async def test_set_scene_effect(self):
        scenes = [{"id": "s1", "name": "Scene1", "mapping_type": "linear",
                    "mapping_params": "{}", "effect_mode": "independent",
                    "effect_source": None, "is_active": 1}]
        managed = _make_managed("Dev1", led_count=10, stable_id="dev1")
        pm, db, _ = _make_manager(
            scenes=scenes, devices=[managed],
            placements=[{"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
                          "position_z": 0.0, "geometry_type": "strip",
                          "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                          "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}],
        )
        db.load_scene_placements.return_value = pm._state_db.load_scene_placements.return_value

        await pm.load_active_scenes()

        pm.set_scene_effect("s1", "rainbow_wave", {})
        info = pm.get_scene_effect("s1")
        assert info["effect_name"] == "rainbow_wave"

    def test_set_effect_no_active_pipeline_raises(self):
        pm, _, _ = _make_manager()
        with pytest.raises(ValueError, match="No active pipeline"):
            pm.set_scene_effect("nonexistent", "beat_pulse", {})


class TestSharedMode:
    async def test_shared_scenes_use_same_deck_and_buffer(self):
        scenes = [
            {"id": "s1", "name": "Scene1", "mapping_type": "linear",
             "mapping_params": "{}", "effect_mode": "shared",
             "effect_source": None, "is_active": 1},
            {"id": "s2", "name": "Scene2", "mapping_type": "linear",
             "mapping_params": "{}", "effect_mode": "shared",
             "effect_source": None, "is_active": 1},
        ]
        d1 = _make_managed("Dev1", led_count=10, stable_id="dev1")
        d2 = _make_managed("Dev2", led_count=10, stable_id="dev2")
        pm, db, _ = _make_manager(scenes=scenes, devices=[d1, d2])

        # First scene gets dev1, second gets dev2
        call_count = 0
        async def load_placements(scene_id):
            if scene_id == "s1":
                return [{"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
                          "position_z": 0.0, "geometry_type": "strip",
                          "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                          "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}]
            return [{"device_id": "dev2", "position_x": 1.0, "position_y": 0.0,
                      "position_z": 0.0, "geometry_type": "strip",
                      "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                      "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}]
        db.load_scene_placements = AsyncMock(side_effect=load_placements)

        await pm.load_active_scenes()

        p1 = pm._pipelines["s1"]
        p2 = pm._pipelines["s2"]
        assert p1.deck is p2.deck  # same shared deck
        assert p1.ring_buffer is p2.ring_buffer  # same shared buffer
        assert p1.compositor is not p2.compositor  # different compositors
```

- [ ] **Step 6: Run all PipelineManager tests**

Run: `uv run pytest tests/spatial/test_pipeline_manager.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/spatial/pipeline_manager.py tests/spatial/test_pipeline_manager.py
git commit -m "feat: implement PipelineManager for multi-pipeline lifecycle"
```

---

## Task 5: Wire PipelineManager into main.py startup

**Files:**
- Modify: `src/dj_ledfx/main.py:129-488`

- [ ] **Step 1: Add PipelineManager import**

At the top of `main.py`, add:

```python
from dj_ledfx.spatial.pipeline_manager import PipelineManager
```

- [ ] **Step 2: Replace single-pipeline startup with PipelineManager**

In `_run()`, after DeviceManager setup and before EffectEngine creation (around lines 209-299), replace the scene loading and engine/scheduler creation with:

1. Create PipelineManager after DeviceManager (around line 207):

```python
        pipeline_manager = PipelineManager(
            device_manager=device_manager,
            state_db=state_db,
            event_bus=event_bus,
            config=config,
        )
        await pipeline_manager.load_active_scenes()
```

2. Replace the EffectEngine creation (around line 292) to use pipelines:

```python
        default_deck = pipeline_manager.default_deck or EffectDeck(BeatPulse())
        default_pipeline = pipeline_manager.default_pipeline
        led_count = device_manager.max_led_count or 60

        engine = EffectEngine(
            clock=clock,
            deck=default_deck,
            led_count=led_count,
            fps=config.engine.fps,
            max_lookahead_s=config.engine.max_lookahead_ms / 1000,
            pipelines=pipeline_manager.all_pipelines or None,
            event_bus=event_bus,
        )
```

3. Replace scheduler creation (around line 301) — use default pipeline's ring buffer and compositor:

```python
        default_ring_buffer = default_pipeline.ring_buffer if default_pipeline else engine.ring_buffer
        default_compositor = default_pipeline.compositor if default_pipeline else compositor

        scheduler = LookaheadScheduler(
            ring_buffer=default_ring_buffer,
            devices=[],  # devices added via pipeline assignments below
            fps=config.engine.fps,
            compositor=default_compositor,
            event_bus=event_bus,
            state_db=state_db,
        )
```

4. Bind and assign devices to pipelines:

```python
        pipeline_manager.bind(engine, scheduler)

        # Add all devices to scheduler with correct pipeline assignments
        for pipeline in pipeline_manager.all_pipelines:
            for managed in pipeline.devices:
                scheduler.add_device(managed, pipeline=pipeline)

        # Add any remaining devices not in a pipeline
        assigned_ids = {
            m.adapter.device_info.effective_id
            for p in pipeline_manager.all_pipelines
            for m in p.devices
        }
        for managed in device_manager.devices:
            eid = managed.adapter.device_info.effective_id
            if eid not in assigned_ids:
                if pipeline_manager.default_pipeline is not None:
                    scheduler.add_device(managed, pipeline=pipeline_manager.default_pipeline)
```

- [ ] **Step 3: Update device event handlers**

Replace the existing device event handlers (around lines 310-333) to go through PipelineManager:

```python
        def _on_device_offline(event: DeviceOfflineEvent) -> None:
            # Preserve existing demote logic (ghost lifecycle)
            if event.stable_id:
                try:
                    device_manager.demote_device(event.stable_id)
                except KeyError:
                    logger.debug(
                        "demote_device: stable_id '{}' not found (already removed?)",
                        event.stable_id,
                    )
            scheduler.remove_device(event.stable_id)

        def _on_device_discovered(event: DeviceDiscoveredEvent) -> None:
            managed = device_manager.get_by_stable_id(event.stable_id)
            if managed is not None:
                pipeline_manager.reassign_devices()

        def _on_device_online(event: DeviceOnlineEvent) -> None:
            managed = device_manager.get_by_stable_id(event.stable_id)
            if managed is not None:
                pipeline_manager.reassign_devices()
```

- [ ] **Step 4: Remove the old single-scene loading code**

Remove the block that builds a single SceneModel + SpatialCompositor from config or DB (approximately lines 209-281). The PipelineManager now handles this.

Keep the `compositor` and `scene_model` variables for backward compat with `create_app()` — derive them from the default pipeline:

```python
        scene_model = default_pipeline.compositor._scene if (default_pipeline and default_pipeline.compositor) else None
        compositor = default_pipeline.compositor if default_pipeline else None
```

- [ ] **Step 5: Pass pipeline_manager to create_app**

Update the `create_app()` call (around line 349) to include `pipeline_manager`:

```python
            app = create_app(
                beat_clock=clock,
                effect_deck=default_deck,
                effect_engine=engine,
                device_manager=device_manager,
                scheduler=scheduler,
                preset_store=preset_store,
                scene_model=scene_model,
                compositor=compositor,
                config=config,
                config_path=config_path,
                web_static_dir=web_static_dir,
                state_db=state_db,
                event_bus=event_bus,
                pipeline_manager=pipeline_manager,
            )
```

- [ ] **Step 6: Run existing tests to verify nothing is broken**

Run: `uv run pytest tests/ -x -v`
Expected: ALL PASS (backward compatible — default pipeline matches previous single-pipeline behavior)

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat: wire PipelineManager into main.py startup"
```

---

## Task 6: Update web layer — create_app and app.state

**Files:**
- Modify: `src/dj_ledfx/web/app.py:46-83`

- [ ] **Step 1: Add pipeline_manager to create_app signature**

In `src/dj_ledfx/web/app.py`, add the import and parameter:

```python
# Add to imports
from dj_ledfx.spatial.pipeline_manager import PipelineManager
```

Add to `create_app()` signature (after `event_bus` parameter):

```python
    pipeline_manager: PipelineManager | None = None,
```

Add to app.state assignments (after `app.state.event_bus`):

```python
    app.state.pipeline_manager = pipeline_manager
```

- [ ] **Step 2: Run existing web tests to verify backward compat**

Run: `uv run pytest tests/web/ -v`
Expected: ALL PASS (pipeline_manager defaults to None, existing tests don't pass it)

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/web/app.py
git commit -m "feat: add pipeline_manager to create_app and app.state"
```

---

## Task 7: Wire activate/deactivate scene endpoints to PipelineManager

**Files:**
- Modify: `src/dj_ledfx/web/router_scene.py:368-417`
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Write failing tests for pipeline-wired activate/deactivate**

Add to `tests/web/test_router_scene.py` in `TestMultiSceneEndpoints`:

```python
    def test_activate_scene_calls_pipeline_manager(self, tmp_path):
        """activate endpoint should call pipeline_manager.activate_scene."""
        client, db = self._make_db_client(tmp_path)
        try:
            # Create a scene
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]

            # Verify pipeline_manager.activate_scene was called
            pm = client.app.state.pipeline_manager
            assert pm is not None
            pm.activate_scene.assert_called_once_with(scene_id)
        finally:
            asyncio.run(db.close())

    def test_deactivate_scene_calls_pipeline_manager(self, tmp_path):
        """deactivate endpoint should call pipeline_manager.deactivate_scene."""
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.post(f"/api/scenes/{scene_id}/deactivate")
            assert resp.status_code == 200

            pm = client.app.state.pipeline_manager
            pm.deactivate_scene.assert_called_once_with(scene_id)
        finally:
            asyncio.run(db.close())

    def test_delete_active_scene_deactivates_first(self, tmp_path):
        """Deleting an active scene should deactivate it first."""
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.delete(f"/api/scenes/{scene_id}")
            assert resp.status_code == 200

            pm = client.app.state.pipeline_manager
            pm.deactivate_scene.assert_called_once_with(scene_id)
        finally:
            asyncio.run(db.close())
```

Note: The `_make_db_client` helper will need to be updated to pass a mock `pipeline_manager` to `create_app`. Update it:

```python
    def _make_db_client(self, tmp_path):
        db = StateDB(tmp_path / "state.db")
        asyncio.run(db.open())
        mock_pm = AsyncMock()
        mock_pm.activate_scene = AsyncMock()
        mock_pm.deactivate_scene = AsyncMock()
        # ... existing create_app call, add pipeline_manager=mock_pm ...
        return client, db
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_router_scene.py -v -k "pipeline_manager"`
Expected: FAIL

- [ ] **Step 3: Modify activate_scene endpoint**

In `src/dj_ledfx/web/router_scene.py`, update `activate_scene` (around line 377):

After the existing `await db.set_scene_active(scene_id)` line, add:

```python
    pm = request.app.state.pipeline_manager
    if pm is not None:
        await pm.activate_scene(scene_id)
```

- [ ] **Step 4: Modify deactivate_scene endpoint**

Replace the raw SQL call with proper method and add pipeline teardown (around line 411):

```python
@router_scenes.post("/{scene_id}/deactivate")
async def deactivate_scene(request: Request, scene_id: str) -> dict[str, str]:
    db = get_db(request)
    await _get_scene_row(db, scene_id)
    await db.set_scene_inactive(scene_id)
    pm = request.app.state.pipeline_manager
    if pm is not None:
        await pm.deactivate_scene(scene_id)
    return {"status": "deactivated", "scene_id": scene_id}
```

- [ ] **Step 5: Modify delete_scene to deactivate first**

Update `delete_scene` (around line 368):

```python
@router_scenes.delete("/{scene_id}")
async def delete_scene(request: Request, scene_id: str) -> dict[str, str]:
    db = get_db(request)
    scene = await _get_scene_row(db, scene_id)
    if scene.get("is_active"):
        pm = request.app.state.pipeline_manager
        if pm is not None:
            await pm.deactivate_scene(scene_id)
        await db.set_scene_inactive(scene_id)
    await db.delete_scene(scene_id)
    return {"status": "deleted", "scene_id": scene_id}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_router_scene.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "feat: wire activate/deactivate/delete endpoints to PipelineManager"
```

---

## Task 8: Add scene effect REST endpoints

**Files:**
- Modify: `src/dj_ledfx/web/router_scene.py`
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/test_router_scene.py`:

```python
    def test_get_scene_effect(self, tmp_path):
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            pm = client.app.state.pipeline_manager
            pm.get_scene_effect.return_value = {"effect_name": "beat_pulse", "params": {}}

            resp = client.get(f"/api/scenes/{scene_id}/effect")
            assert resp.status_code == 200
            assert resp.json()["effect_name"] == "beat_pulse"
        finally:
            asyncio.run(db.close())

    def test_put_scene_effect(self, tmp_path):
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.put(
                f"/api/scenes/{scene_id}/effect",
                json={"effect_name": "rainbow_wave", "params": {}},
            )
            assert resp.status_code == 200

            pm = client.app.state.pipeline_manager
            pm.set_scene_effect.assert_called_once_with(scene_id, "rainbow_wave", {})
        finally:
            asyncio.run(db.close())

    def test_put_scene_effect_no_pipeline_manager(self, tmp_path):
        """Without pipeline_manager, scene effect endpoints return 501."""
        client, db = self._make_db_client(tmp_path)
        client.app.state.pipeline_manager = None
        try:
            resp = client.put(
                "/api/scenes/fake/effect",
                json={"effect_name": "beat_pulse", "params": {}},
            )
            assert resp.status_code == 501
        finally:
            asyncio.run(db.close())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_router_scene.py -v -k "scene_effect"`
Expected: FAIL — endpoints don't exist

- [ ] **Step 3: Implement scene effect endpoints**

Add to `src/dj_ledfx/web/router_scene.py` in the `router_scenes` section:

```python
@router_scenes.get("/{scene_id}/effect")
async def get_scene_effect(request: Request, scene_id: str) -> dict:
    pm = request.app.state.pipeline_manager
    if pm is None:
        raise HTTPException(501, "Pipeline manager not available")
    try:
        return pm.get_scene_effect(scene_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


class SetSceneEffectRequest(BaseModel):
    effect_name: str
    params: dict[str, Any] = {}


@router_scenes.put("/{scene_id}/effect")
async def set_scene_effect(request: Request, scene_id: str, body: SetSceneEffectRequest) -> dict:
    pm = request.app.state.pipeline_manager
    if pm is None:
        raise HTTPException(501, "Pipeline manager not available")
    try:
        pm.set_scene_effect(scene_id, body.effect_name, body.params)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"status": "ok", "scene_id": scene_id, "effect_name": body.effect_name}
```

Add `HTTPException` to imports if not already present:

```python
from fastapi import HTTPException
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_router_scene.py -v -k "scene_effect"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "feat: add GET/PUT /scenes/{id}/effect endpoints"
```

---

## Task 9: Add `scene_id` to WebSocket `set_effect` command

**Files:**
- Modify: `src/dj_ledfx/web/ws.py:212-218`
- Test: `tests/web/test_ws.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/test_ws.py`:

```python
def test_ws_set_effect_with_scene_id(client):
    """set_effect with scene_id targets that scene's pipeline."""
    mock_pm = MagicMock()
    client.app.state.pipeline_manager = mock_pm

    with client.websocket_connect("/ws") as ws:
        # Drain initial beat message
        ws.receive_text()

        ws.send_json({
            "action": "set_effect",
            "id": "test1",
            "scene_id": "scene1",
            "effect": "rainbow_wave",
            "params": {},
        })
        # Read messages until we get our ack
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack" and msg.get("id") == "test1":
                break
        mock_pm.set_scene_effect.assert_called_once_with("scene1", "rainbow_wave", {})


def test_ws_set_effect_without_scene_id(client):
    """set_effect without scene_id targets the global deck (backward compat)."""
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # drain beat
        ws.send_json({
            "action": "set_effect",
            "id": "test2",
            "effect": "beat_pulse",
            "params": {},
        })
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack" and msg.get("id") == "test2":
                break
        # Global deck should have been updated
        assert client.app.state.effect_deck.effect_name == "beat_pulse"
```

Add `import json` to test file if not present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_ws.py -v -k "set_effect"`
Expected: FAIL

- [ ] **Step 3: Modify set_effect command handler**

In `src/dj_ledfx/web/ws.py`, replace the `set_effect` handler (around line 212):

```python
        elif action == "set_effect":
            scene_id = msg.get("scene_id")
            try:
                if scene_id and app.state.pipeline_manager is not None:
                    app.state.pipeline_manager.set_scene_effect(
                        scene_id, msg.get("effect"), msg.get("params", {})
                    )
                else:
                    deck = app.state.effect_deck
                    deck.apply_update(msg.get("effect"), msg.get("params", {}))
                await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})
            except (KeyError, ValueError, TypeError) as e:
                await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": str(e)})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_ws.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/ws.py tests/web/test_ws.py
git commit -m "feat: add scene_id support to WebSocket set_effect command"
```

---

## Task 10: Add `effect_mode` change guard

**Files:**
- Modify: `src/dj_ledfx/web/router_scene.py`
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Write failing test**

```python
    def test_update_active_scene_effect_mode_returns_409(self, tmp_path):
        client, db = self._make_db_client(tmp_path)
        try:
            resp = client.post("/api/scenes", json={"name": "TestScene", "effect_mode": "independent"})
            scene_id = resp.json()["id"]
            client.post(f"/api/scenes/{scene_id}/activate")

            resp = client.put(
                f"/api/scenes/{scene_id}",
                json={"name": "TestScene", "effect_mode": "shared"},
            )
            assert resp.status_code == 409
        finally:
            asyncio.run(db.close())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_router_scene.py -v -k "effect_mode_returns_409"`
Expected: FAIL — no guard exists

- [ ] **Step 3: Implement the guard**

In `src/dj_ledfx/web/router_scene.py`, in the `update_scene` endpoint, add before the DB write:

```python
    # Guard: can't change effect_mode while scene is active
    existing = await _get_scene_row(db, scene_id)
    if existing.get("is_active") and body.get("effect_mode") and body["effect_mode"] != existing.get("effect_mode"):
        raise HTTPException(409, "Cannot change effect_mode while scene is active. Deactivate first.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_router_scene.py -v -k "effect_mode"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "feat: guard against effect_mode change on active scenes (409)"
```

---

## Task 11: Multi-pipeline integration test

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Write multi-pipeline integration test**

Add to `tests/test_integration.py`:

```python
async def test_multi_pipeline_renders_to_separate_devices() -> None:
    """Two pipelines with different effects render to different devices."""
    from dj_ledfx.effects.beat_pulse import BeatPulse
    from dj_ledfx.effects.rainbow_wave import RainbowWave
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import EffectEngine, RingBuffer
    from dj_ledfx.scheduling.scheduler import LookaheadScheduler
    from dj_ledfx.spatial.pipeline import ScenePipeline

    # Two devices, each in a different pipeline
    adapter1 = MockDeviceAdapter(name="LED1", led_count=10)
    tracker1 = LatencyTracker(strategy=StaticLatency(10.0))
    managed1 = ManagedDevice(adapter=adapter1, tracker=tracker1, max_fps=60)

    adapter2 = MockDeviceAdapter(name="LED2", led_count=10)
    tracker2 = LatencyTracker(strategy=StaticLatency(10.0))
    managed2 = ManagedDevice(adapter=adapter2, tracker=tracker2, max_fps=60)

    # Pipeline A: BeatPulse
    deck_a = EffectDeck(BeatPulse())
    buf_a = RingBuffer(60, 10)
    pipeline_a = ScenePipeline(
        scene_id="scene_a", deck=deck_a, ring_buffer=buf_a,
        compositor=None, mapping=None, devices=[managed1], led_count=10,
    )

    # Pipeline B: RainbowWave
    deck_b = EffectDeck(RainbowWave())
    buf_b = RingBuffer(60, 10)
    pipeline_b = ScenePipeline(
        scene_id="scene_b", deck=deck_b, ring_buffer=buf_b,
        compositor=None, mapping=None, devices=[managed2], led_count=10,
    )

    # Setup
    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    simulator._clock = clock
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=time.monotonic())

    engine = EffectEngine(
        clock=clock, deck=deck_a, led_count=10, fps=60,
        max_lookahead_s=1.0, pipelines=[pipeline_a, pipeline_b],
        event_bus=event_bus,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=buf_a, devices=[], fps=60, event_bus=event_bus,
    )
    scheduler.add_device(managed1, pipeline=pipeline_a)
    scheduler.add_device(managed2, pipeline=pipeline_b)

    engine._resume_event.set()
    scheduler._resume_event.set()
    scheduler._transport_state = TransportState.PLAYING

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.5)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both devices should have received frames
    assert len(adapter1.send_frame_calls) > 0
    assert len(adapter2.send_frame_calls) > 0

    # Frames should differ (different effects)
    frame1 = adapter1.send_frame_calls[-1]
    frame2 = adapter2.send_frame_calls[-1]
    # They won't be identical since BeatPulse and RainbowWave produce different colors
    assert not (frame1 == frame2).all(), "Different effects should produce different frames"
```

- [ ] **Step 2: Run integration test**

Run: `uv run pytest tests/test_integration.py -v -k "multi_pipeline"`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add multi-pipeline integration test"
```

---

## Task 12: Run full test suite, lint, and type check

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Run formatter**

Run: `uv run ruff format .`

- [ ] **Step 4: Run type checker**

Run: `uv run mypy src/`
Expected: No new errors (fix any that appear)

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: address lint and type check issues"
```

---

## Task 13: Code architect review

Run `@feature-dev:code-architect` review on all changes. Fix every issue found.

---

## Task 14: Simplify review

Run `/simplify` on all changed code. Fix every issue found.

---

## Task 15: Update CLAUDE.md

Run `@claude-md-management:revise-claude-md` to update project documentation with multi-pipeline architecture details.

---

## Task 16: Create PR

Create a pull request with all changes. Title: "feat: wire up multi-pipeline rendering end-to-end"
