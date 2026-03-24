# Multi-Pipeline Wiring Design

Wire up multi-pipeline rendering end-to-end so different scenes can run different effects on different device groups simultaneously.

## Context

The structural primitives for multi-pipeline rendering already exist:
- `ScenePipeline` dataclass bundles deck, ring buffer, compositor, mapping, and devices
- `EffectEngine.tick()` iterates over all pipelines
- `LookaheadScheduler._send_loop()` reads from per-device pipeline ring buffers and compositors
- Multi-scene DB CRUD with `effect_mode` (independent/shared) and activate/deactivate with conflict detection

The gap is orchestration: `main.py` never constructs `ScenePipeline` objects, the engine always uses a single default pipeline, and scene activate/deactivate endpoints only mutate the DB without creating runtime pipelines.

## Design

### PipelineManager

New file: `src/dj_ledfx/spatial/pipeline_manager.py`

Central orchestrator for pipeline lifecycle. Owns the mapping from scene_id to `ScenePipeline` and mediates between the DB/web layer and the engine/scheduler.

```python
class PipelineManager:
    def __init__(self, device_manager, state_db, event_bus, config)

    # State
    _pipelines: dict[str, ScenePipeline]     # scene_id -> pipeline
    _default_pipeline: ScenePipeline | None   # for unassigned devices
    _shared_deck: EffectDeck | None           # shared across shared-mode scenes
    _shared_buffer: RingBuffer | None         # shared across shared-mode scenes

    # Startup
    async def load_active_scenes(self) -> None

    # Late binding (engine/scheduler created after pipelines are loaded)
    def bind(self, engine: EffectEngine, scheduler: LookaheadScheduler) -> None

    # Runtime lifecycle
    async def activate_scene(self, scene_id: str) -> ScenePipeline
    async def deactivate_scene(self, scene_id: str) -> None

    # Effect control
    def set_scene_effect(self, scene_id: str, effect_name: str, params: dict) -> None
    def get_scene_effect(self, scene_id: str) -> dict

    # Device assignment
    def reassign_devices(self) -> None

    # Properties
    @property
    def all_pipelines(self) -> list[ScenePipeline]
    @property
    def default_deck(self) -> EffectDeck | None

    # Internal
    def _build_pipeline(self, scene_row, placements, devices) -> ScenePipeline
    def _build_default_pipeline(self, unassigned_devices) -> ScenePipeline
    def _teardown_pipeline(self, scene_id: str) -> None
```

### Shared Mode Semantics

When `effect_mode = "shared"`, the pipeline gets a reference to a shared `EffectDeck` and shared `RingBuffer`. Multiple shared-mode scenes point to the same deck/buffer but each has its own `SpatialCompositor` (built from that scene's placements and mapping).

One effect renders once into the shared buffer. Each scene's compositor samples it differently based on spatial position, giving coherent effects across device groups (e.g., a rainbow wave sweeping across the room hits devices in the correct spatial order regardless of which scene they belong to).

When `effect_mode = "independent"`, the pipeline gets its own deck and ring buffer. Its effect renders independently.

### Config Change

One new field in `EngineConfig`:

```python
unassigned_device_mode: str = "default_effect"  # "default_effect" | "idle"
```

- `"default_effect"`: PipelineManager creates a default pipeline with BeatPulse for devices not in any active scene.
- `"idle"`: No default pipeline. Unassigned devices receive no frames.

### Engine Changes

- `add_pipeline(pipeline: ScenePipeline)` — append to pipelines list
- `remove_pipeline(scene_id: str)` — remove by scene_id, clear that pipeline's ring buffer
- Shared-buffer dedup in `tick()`: track rendered buffer IDs to avoid rendering the same shared buffer twice per tick

```python
def tick(self, now: float) -> None:
    seen_buffers: set[int] = set()
    for pipeline in self.pipelines:
        buf_id = id(pipeline.ring_buffer)
        if buf_id in seen_buffers:
            continue
        seen_buffers.add(buf_id)
        colors = pipeline.deck.render(ctx, pipeline.led_count)
        frame = RenderedFrame(colors=colors, target_time=target_time, ...)
        pipeline.ring_buffer.write(frame)
```

### Scheduler Changes

- `remove_pipeline_refs(scene_id: str)` — null out `state.pipeline` for any device that referenced the deactivated scene's pipeline (falls back to default or idle)
- Existing `set_device_pipeline()` and per-device pipeline routing in `_send_loop` are unchanged

### Web API Changes

**New endpoints in `router_scene.py`:**

```
GET  /scenes/{id}/effect   -> {effect_name, params}
PUT  /scenes/{id}/effect   -> {effect_name, params?} -> sets scene's effect
```

**Modified endpoints:**

- `POST /scenes/{id}/activate` — after DB write + conflict check, calls `pipeline_manager.activate_scene(scene_id)`
- `POST /scenes/{id}/deactivate` — after DB write, calls `pipeline_manager.deactivate_scene(scene_id)`

**WebSocket `set_effect` command:**

Add optional `scene_id` field. When omitted, targets the default pipeline (backward compatible). When provided, calls `pipeline_manager.set_scene_effect()`.

**`app.state` additions:**

```python
app.state.pipeline_manager = pipeline_manager
# Keep app.state.effect_deck as alias for default pipeline's deck (backward compat)
```

### main.py Startup Flow

1. (unchanged) Open StateDB, migrate, load config, create EventBus, BeatClock, beat source
2. (unchanged) Create DeviceManager, load registered devices, connect, start discovery
3. Create `PipelineManager(device_manager, state_db, event_bus, config)`
4. `await pipeline_manager.load_active_scenes()` — builds pipelines for all active DB scenes, builds default pipeline based on `unassigned_device_mode`
5. Create `EffectEngine(clock, deck=default_deck, led_count, fps, max_lookahead_s, pipelines=pipeline_manager.all_pipelines)`
6. Create `LookaheadScheduler(ring_buffer=default_ring_buffer, compositor=default_compositor, ...)`
7. `pipeline_manager.bind(engine, scheduler)` — back-references for runtime add/remove
8. For each pipeline's devices, call `scheduler.add_device(managed, pipeline=pipeline)`
9. (unchanged) Subscribe device events, start web server, launch engine/scheduler tasks

Device lifecycle events (discovered/offline) trigger `pipeline_manager.reassign_devices()`.

Backward compatible: if no scenes exist in DB, one default pipeline with BeatPulse, all devices assigned.

## Testing Strategy

**Unit tests:**
- PipelineManager: activate, deactivate, set_scene_effect, reassign_devices with mock engine/scheduler/DB
- Shared mode: two shared scenes reference same deck/buffer, different compositors
- Default pipeline: creation/omission based on `unassigned_device_mode`
- Engine dedup: shared-buffer pipelines only render once per tick

**Integration tests:**
- Full startup with 2 active scenes -> devices get frames from correct pipelines
- Activate scene at runtime -> pipeline created, devices reassigned, frames flowing
- Deactivate scene -> pipeline torn down, devices fall back to default (or idle)
- Scene effect change via REST -> only that scene's devices change
- Device discovered mid-run in an active scene's placements -> auto-assigned to pipeline

**Web API tests:**
- `PUT /scenes/{id}/effect` -> effect changes for that scene only
- `POST /scenes/{id}/activate` -> pipeline wired up (not just DB flag)
- WS `set_effect` with `scene_id` -> targets correct pipeline
- WS `set_effect` without `scene_id` -> targets default pipeline (backward compat)

Existing single-pipeline tests continue to work unchanged.
