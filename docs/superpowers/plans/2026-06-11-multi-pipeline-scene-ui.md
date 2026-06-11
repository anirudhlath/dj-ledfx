# Multi-Pipeline Scene Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make multi-pipeline rendering usable end-to-end from the web UI: scene CRUD/activate/deactivate with conflict handling, a per-scene 3D editor, and per-scene effect decks — plus the backend fixes that feature depends on.

**Architecture:** Backend-first (TDD): fix PipelineManager effect restore + compositor keying, harden the activate route, fix placement deletion, add a SceneDetail read endpoint and `mapping_params` write path, expose `stable_id` on devices. Then frontend: structured API errors + scene methods in the client, a `useScenes` list hook, parameterize `useScene(sceneId)`, add a ScenesPanel to the Scene page, and tab the Live effect deck per active scene. Spec: `docs/superpowers/specs/2026-06-11-multi-pipeline-scene-ui-design.md`.

**Tech Stack:** FastAPI + Pydantic v2 + SQLite (backend), pytest with sync `fastapi.testclient.TestClient` (NOT httpx.AsyncClient — all existing web tests use TestClient), React 19 + TypeScript + shadcn/ui (base-ui) + sonner toasts (frontend). `uv run` for all Python commands.

**Conventions that apply to every task:**
- Python: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run mypy src/` must stay green. loguru for logging.
- Frontend: `cd frontend && npx tsc --noEmit` and `npm run build` must stay green.
- Commit after each task with the message given in the task. All commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Tests live in `tests/spatial/test_pipeline_manager.py` and `tests/web/test_router_scene.py` / `tests/web/test_router_devices.py` — reuse the helper functions already at the top of those files (`_make_manager`, `_make_db_mock`, `_make_db_client`, `_make_test_app`). Read the helpers before writing tests.

---

### Task 1: PipelineManager — restore persisted per-scene effect on activation

`_build_deck_for_scene` (`src/dj_ledfx/spatial/pipeline_manager.py:312-314`) ignores the `scene_effect_state` row and always returns `EffectDeck(BeatPulse())`, despite its docstring. Scenes lose their effect on every restart/reactivation.

**Files:**
- Modify: `src/dj_ledfx/spatial/pipeline_manager.py`
- Test: `tests/spatial/test_pipeline_manager.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/spatial/test_pipeline_manager.py` (reuse `_make_manager`, `_make_db_mock`, and the existing placement-row dict shape used by `test_activate_scene` — copy the scene_row/placement fixtures from that test). The DB mock already has `load_scene_effect_state` as an AsyncMock; set its return value:

```python
class TestEffectRestore:
    async def test_activate_restores_persisted_effect(self) -> None:
        pm, db, engine, scheduler = _make_manager_for_activation()  # see note below
        db.load_scene_effect_state.return_value = {
            "effect_class": "rainbow_wave",
            "params": "{}",
        }
        await pm.activate_scene("s1")
        assert pm._pipelines["s1"].deck.effect_name == "rainbow_wave"

    async def test_activate_falls_back_to_beat_pulse_on_unknown_effect(self) -> None:
        pm, db, engine, scheduler = _make_manager_for_activation()
        db.load_scene_effect_state.return_value = {
            "effect_class": "does_not_exist",
            "params": "{}",
        }
        await pm.activate_scene("s1")
        assert pm._pipelines["s1"].deck.effect_name == "beat_pulse"

    async def test_activate_with_no_saved_effect_uses_beat_pulse(self) -> None:
        pm, db, engine, scheduler = _make_manager_for_activation()
        db.load_scene_effect_state.return_value = None
        await pm.activate_scene("s1")
        assert pm._pipelines["s1"].deck.effect_name == "beat_pulse"
```

Note: if no `_make_manager_for_activation` helper exists, inline the same setup the existing `TestActivateScene` test uses (scene row with `id="s1"`, `effect_mode="independent"`, one placement row resolving to a registered mock device, `pm.bind(MagicMock(), scheduler_mock_with_has_device_False)`), or extract that setup into a small local helper. Do not change existing tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_pipeline_manager.py -k EffectRestore -v`
Expected: `test_activate_restores_persisted_effect` FAILS (`beat_pulse != rainbow_wave`); the other two may already pass — that is fine, they are regression guards.

- [ ] **Step 3: Implement**

In `src/dj_ledfx/spatial/pipeline_manager.py`:

Add import:
```python
from dj_ledfx.effects.registry import create_effect
```

Change `_build_pipeline` signature and the deck branch (currently `deck = self._build_deck_for_scene(scene_id)`):
```python
    def _build_pipeline(
        self,
        scene_row: dict[str, Any],
        placements: list[dict[str, Any]],
        effect_row: dict[str, str] | None = None,
    ) -> ScenePipeline | None:
```
```python
        if effect_mode == "shared":
            deck, ring_buffer = self._get_or_create_shared(led_count)
        else:
            deck = self._build_deck_for_scene(scene_id, effect_row)
```

Replace `_build_deck_for_scene`:
```python
    def _build_deck_for_scene(
        self, scene_id: str, effect_row: dict[str, str] | None
    ) -> EffectDeck:
        """Build an EffectDeck for an independent scene, restoring saved state."""
        if effect_row is not None:
            try:
                params = json.loads(effect_row.get("params") or "{}")
                effect = create_effect(effect_row["effect_class"], **params)
            except (KeyError, TypeError, ValueError):
                logger.warning(
                    "Could not restore effect '{}' for scene {}, falling back to beat_pulse",
                    effect_row.get("effect_class"),
                    scene_id,
                )
            else:
                return EffectDeck(effect)
        return EffectDeck(BeatPulse())
```

In `activate_scene`, before the `_build_pipeline` call:
```python
        placements = await self._state_db.load_scene_placements(scene_id)
        effect_row = await self._state_db.load_scene_effect_state(scene_id)
        pipeline = self._build_pipeline(scene_row, placements, effect_row)
```

In `load_active_scenes`, inside the loop, same change:
```python
        for scene_row in active_scenes:
            placements = await self._state_db.load_scene_placements(scene_row["id"])
            effect_row = await self._state_db.load_scene_effect_state(scene_row["id"])
            try:
                pipeline = self._build_pipeline(scene_row, placements, effect_row)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/spatial/test_pipeline_manager.py -v`
Expected: ALL PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/spatial/pipeline_manager.py tests/spatial/test_pipeline_manager.py
git commit -m "fix: restore persisted per-scene effect when building pipelines"
```

---

### Task 2: PipelineManager — key compositor placements by device name

`_build_pipeline` keys the in-memory `SceneModel` by DB `device_id` (= stable_id, `pipeline_manager.py:252`), but the scheduler hot path calls `compositor.composite(colors, device_info.name)` (`scheduling/scheduler.py:325`). Any device whose `stable_id != name` (all LIFX/Govee) gets `None` back and renders uncomposited. Fix the keying at build time — do NOT touch the scheduler hot path.

**Files:**
- Modify: `src/dj_ledfx/spatial/pipeline_manager.py` (in `_build_pipeline`)
- Test: `tests/spatial/test_pipeline_manager.py`

- [ ] **Step 1: Write the failing test**

Use the existing `_StableIdAdapter` helper (adds a `stable_id` without class-level property patching). The device must have `name` ≠ `stable_id`, the placement row must use the stable_id (as the DB does), and the placement must be a strip so the compositor produces strip indices:

```python
class TestCompositorKeying:
    async def test_compositor_keyed_by_display_name(self) -> None:
        # Setup mirrors TestActivateScene but with stable_id != name and strip geometry
        pm, db, engine, scheduler = ...  # same local helper/inline setup as Task 1
        # device: name="My Strip", stable_id="lifx:abc123"
        # placement row: device_id="lifx:abc123", geometry_type="strip"
        await pm.activate_scene("s1")
        pipeline = pm._pipelines["s1"]
        assert pipeline.compositor is not None
        indices = pipeline.compositor.get_strip_indices()
        assert "My Strip" in indices
        assert "lifx:abc123" not in indices
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/spatial/test_pipeline_manager.py -k compositor_keyed -v`
Expected: FAIL — `"My Strip" not in indices` (keys are stable_ids today).

- [ ] **Step 3: Implement**

In `_build_pipeline`, the placement loop currently builds `DevicePlacement(device_id=p["device_id"], ...)` and stores `scene_placements[p["device_id"]] = placement`. Change both to use the device's display name (the DB row keeps stable_id; only the in-memory model is renamed):

```python
        for p in placements:
            managed = self._device_manager.get_by_stable_id(p["device_id"])
            if managed is None:
                continue
            devices.append(managed)
            # Key the in-memory model by display name: the scheduler composites
            # frames by device_info.name, not by stable_id.
            display_name = managed.adapter.device_info.name
            geo_type = p.get("geometry_type") or "point"
            ...
            placement = DevicePlacement(
                device_id=display_name,
                position=(...unchanged...),
                geometry=geometry,
                led_count=managed.adapter.device_info.led_count,
            )
            scene_placements[display_name] = placement
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/spatial/ -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/spatial/pipeline_manager.py tests/spatial/test_pipeline_manager.py
git commit -m "fix: key pipeline compositor placements by device name to match scheduler lookups"
```

---

### Task 3: Idempotent scene activation + 409 on build failure + atomicity test

`PipelineManager.activate_scene` raises `ValueError` for an already-active scene (`pipeline_manager.py:115-117`) and the route (`web/router_scene.py:392-427`) lets it escape as HTTP 500.

**Files:**
- Modify: `src/dj_ledfx/spatial/pipeline_manager.py` (add `is_scene_active`)
- Modify: `src/dj_ledfx/web/router_scene.py` (activate route)
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Update the shared test helper FIRST**

In `tests/web/test_router_scene.py`, the `_make_db_client` helper creates `pm = MagicMock()` with AsyncMock activate/deactivate. A bare `MagicMock().is_scene_active(...)` returns a truthy MagicMock, which would make the new route short-circuit every activation and break existing tests. Add one line where the pm mock is configured:

```python
    pm.is_scene_active.return_value = False
```

Also add the same line to any test that builds its own pm MagicMock (search the file for `MagicMock()` assigned to a pipeline-manager variable — e.g. the conflict tests and `test_activate_scene_calls_pipeline_manager`).

- [ ] **Step 2: Write the failing tests**

```python
class TestActivateHardening:
    def test_activate_already_active_returns_200(self, tmp_path) -> None:
        client, db, pm = ...  # _make_db_client pattern
        pm.is_scene_active.return_value = True
        resp = client.post("/api/scenes", json={"name": "A"})
        scene_id = resp.json()["id"]
        resp = client.post(f"/api/scenes/{scene_id}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_active"
        pm.activate_scene.assert_not_called()

    def test_activate_pipeline_failure_returns_409_and_db_unchanged(self, tmp_path) -> None:
        client, db, pm = ...
        pm.is_scene_active.return_value = False
        pm.activate_scene.side_effect = ValueError("Could not build pipeline")
        resp = client.post("/api/scenes", json={"name": "A"})
        scene_id = resp.json()["id"]
        resp = client.post(f"/api/scenes/{scene_id}/activate")
        assert resp.status_code == 409
        # Atomicity: failed activation must not flip the DB flag (CLAUDE.md invariant)
        resp = client.get(f"/api/scenes/{scene_id}")
        assert resp.json()["is_active"] is False
```

(Adapt the `...` to the exact `_make_db_client` return shape in the file — it may return only `client`; in that case follow the existing pattern for reaching `db`/`pm`.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_router_scene.py -k ActivateHardening -v`
Expected: first FAILS with 500 (AttributeError or unhandled ValueError path), second FAILS with 500 instead of 409.

- [ ] **Step 4: Implement**

`pipeline_manager.py` — add next to the other properties/accessors:
```python
    def is_scene_active(self, scene_id: str) -> bool:
        """True if a pipeline is currently registered for this scene."""
        return scene_id in self._pipelines
```

`router_scene.py` — replace the tail of `activate_scene` (after the conflict check):
```python
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is not None:
        if pm.is_scene_active(scene_id):
            # Self-heal the DB flag and treat as success (idempotent activate).
            await db.set_scene_active(scene_id)
            return {"status": "already_active", "scene_id": scene_id}
        try:
            await pm.activate_scene(scene_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    await db.set_scene_active(scene_id)
    return {"status": "activated", "scene_id": scene_id}
```

- [ ] **Step 5: Run the full web test file**

Run: `uv run pytest tests/web/test_router_scene.py -v`
Expected: ALL PASS (including pre-existing activate/conflict tests).

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/spatial/pipeline_manager.py src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "fix: make scene activation idempotent and return 409 on pipeline build failure"
```

---

### Task 4: Resolve display name → stable_id when deleting a placement

`DELETE /api/scenes/{id}/devices/{name}` (`router_scene.py:565-574`) passes the display name straight to `db.delete_placement`, but placements are stored under stable_id — deletion silently no-ops for real hardware. (The PUT route resolves correctly at `router_scene.py:480-490`; mirror it.)

**Files:**
- Modify: `src/dj_ledfx/web/router_scene.py`
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Write the failing test**

Mirror `test_placement_uses_stable_id` (real `DeviceManager` + `MagicMock(spec=DeviceAdapter)` with `device_info=DeviceInfo(..., stable_id="lifx:my_strip")`):

```python
    def test_remove_placement_resolves_stable_id(self, tmp_path) -> None:
        # same app setup as test_placement_uses_stable_id
        client.put(f"/api/scenes/{scene_id}/devices/My Strip", json={"position": [0, 0, 0]})
        resp = client.delete(f"/api/scenes/{scene_id}/devices/My Strip")
        assert resp.status_code == 200
        detail = client.get(f"/api/scenes/{scene_id}")
        # After Task 5 this asserts placements == []; until then assert directly on DB:
        rows = asyncio.run(db.load_scene_placements(scene_id))
        assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_router_scene.py -k remove_placement_resolves -v`
Expected: FAIL — the row keyed `lifx:my_strip` survives.

- [ ] **Step 3: Implement**

Replace the body of `remove_scene_placement`:
```python
    db = get_db(request)
    await _get_scene_row(db, scene_id)

    # Resolve display name to stable_id (placements are stored by stable_id).
    device_id = device_name
    device_manager = request.app.state.device_manager
    from dj_ledfx.devices.manager import ManagedDevice as _MD

    managed = device_manager.get_device(device_name)
    if isinstance(managed, _MD):
        device_id = managed.adapter.device_info.effective_id

    await db.delete_placement(scene_id, device_id)
    return {"status": "removed", "device_name": device_name}
```
(The `isinstance` guard matches the PUT route's pattern — it protects tests that stub `device_manager` with a bare MagicMock.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/web/test_router_scene.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "fix: resolve display name to stable_id when deleting scene placements"
```

---

### Task 5: SceneDetail endpoint + mapping_params write path

The UI cannot display a DB scene: there is no read for placements, and `scenes.mapping_params` is unreachable. Grow `GET /api/scenes/{scene_id}` into a `SceneDetail` (superset of `SceneListItem` — backward compatible) and add `mapping_params` to `UpdateSceneRequest`.

**Files:**
- Modify: `src/dj_ledfx/web/schemas.py`
- Modify: `src/dj_ledfx/web/router_scene.py`
- Test: `tests/web/test_router_scene.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestSceneDetail:
    def test_get_scene_detail_includes_placements_and_mapping(self, tmp_path) -> None:
        # app with real DeviceManager + adapter name="My Strip", stable_id="lifx:my_strip",
        # led_count=30 (same setup as test_placement_uses_stable_id)
        scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
        client.put(
            f"/api/scenes/{scene_id}/devices/My Strip",
            json={"position": [1.0, 2.0, 3.0], "geometry": "strip", "direction": [1, 0, 0], "length": 2.0},
        )
        client.put(f"/api/scenes/{scene_id}", json={"mapping_type": "radial", "mapping_params": {"center": [0, 0, 0]}})
        detail = client.get(f"/api/scenes/{scene_id}").json()
        assert detail["name"] == "A"
        assert len(detail["placements"]) == 1
        p = detail["placements"][0]
        assert p["device_id"] == "My Strip"          # display name, not stable_id
        assert p["position"] == [1.0, 2.0, 3.0]
        assert p["geometry"]["type"] == "strip"
        assert p["led_count"] == 30                   # from the adapter, not the DB
        assert p["strip_index"] is not None
        assert detail["mapping"] == {"type": "radial", "params": {"center": [0, 0, 0]}}
        assert detail["bounds"] is not None

    def test_get_scene_detail_unknown_device_falls_back_to_stable_id(self, tmp_path) -> None:
        # _make_db_client pattern (device_manager is a bare MagicMock -> no resolution)
        scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
        client.put(f"/api/scenes/{scene_id}/devices/ghost", json={"position": [0, 0, 0]})
        detail = client.get(f"/api/scenes/{scene_id}").json()
        assert detail["placements"][0]["device_id"] == "ghost"

    def test_update_scene_persists_mapping_params(self, tmp_path) -> None:
        scene_id = client.post("/api/scenes", json={"name": "A"}).json()["id"]
        client.put(f"/api/scenes/{scene_id}", json={"mapping_params": {"origin": [1, 1, 1]}})
        detail = client.get(f"/api/scenes/{scene_id}").json()
        assert detail["mapping"]["params"] == {"origin": [1.0, 1.0, 1.0]}
        # and a second update of another field must not wipe it
        client.put(f"/api/scenes/{scene_id}", json={"name": "B"})
        detail = client.get(f"/api/scenes/{scene_id}").json()
        assert detail["mapping"]["params"] == {"origin": [1.0, 1.0, 1.0]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_router_scene.py -k SceneDetail -v`
Expected: FAIL — response has no `placements` key / `mapping_params` rejected by Pydantic.

- [ ] **Step 3: Implement schemas**

`src/dj_ledfx/web/schemas.py`:
```python
class SceneDetail(SceneListItem):
    placements: list[PlacementResponse] = []
    mapping: MappingResponse | None = None
    bounds: list[list[float]] | None = None
```
and add to `UpdateSceneRequest`:
```python
    mapping_params: dict[str, Any] | None = None
```

- [ ] **Step 4: Implement the routes**

`router_scene.py` — add `SceneDetail` to the schema imports and `import json` at the top. Replace `get_scene_by_id`:

```python
@router_scenes.get("/{scene_id}", response_model=SceneDetail)
async def get_scene_by_id(request: Request, scene_id: str) -> SceneDetail:
    db = get_db(request)
    row = await _get_scene_row(db, scene_id)
    placement_rows = await db.load_scene_placements(scene_id)

    from dj_ledfx.devices.manager import ManagedDevice as _MD
    from dj_ledfx.spatial.scene import DevicePlacement, SceneModel

    device_manager = request.app.state.device_manager
    scene_placements: dict[str, DevicePlacement] = {}
    for p in placement_rows:
        display_name = p["device_id"]
        led_count = 1
        managed = device_manager.get_by_stable_id(p["device_id"])
        if isinstance(managed, _MD):
            display_name = managed.adapter.device_info.name
            led_count = managed.adapter.led_count
        geometry: PointGeometry | StripGeometry = PointGeometry()
        if (p.get("geometry_type") or "point") == "strip":
            geometry = StripGeometry(
                direction=(
                    p.get("direction_x") or 1.0,
                    p.get("direction_y") or 0.0,
                    p.get("direction_z") or 0.0,
                ),
                length=p.get("length") or 1.0,
            )
        scene_placements[display_name] = DevicePlacement(
            device_id=display_name,
            position=(
                p.get("position_x") or 0.0,
                p.get("position_y") or 0.0,
                p.get("position_z") or 0.0,
            ),
            geometry=geometry,
            led_count=led_count,
        )

    mapping_type = row.get("mapping_type") or "linear"
    mapping_params = json.loads(row.get("mapping_params") or "{}")
    strip_indices: dict[str, float] = {}
    bounds = None
    if scene_placements:
        model = SceneModel(scene_placements)
        mapping = mapping_from_config(
            {"mapping": mapping_type, "mapping_params": mapping_params}
        )
        compositor = SpatialCompositor(model, mapping)
        for device_id, indices in compositor.get_strip_indices().items():
            strip_indices[device_id] = float(indices.mean())
        bounds_min, bounds_max = model.get_bounds()
        bounds = [bounds_min.tolist(), bounds_max.tolist()]

    return SceneDetail(
        id=row["id"],
        name=row["name"],
        is_active=bool(row.get("is_active", 0)),
        mapping_type=row.get("mapping_type"),
        effect_mode=row.get("effect_mode"),
        placements=[
            _placement_to_response(p, strip_index=strip_indices.get(p.device_id))
            for p in scene_placements.values()
        ],
        mapping=MappingResponse(type=mapping_type, params=mapping_params),
        bounds=bounds,
    )
```

In `update_scene`, carry `mapping_params` through (after the `effect_mode` line):
```python
    updated["mapping_params"] = (
        json.dumps(body.mapping_params)
        if body.mapping_params is not None
        else existing.get("mapping_params")
    )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/web/test_router_scene.py -v && uv run mypy src/`
Expected: ALL PASS, mypy clean. If `test_get_scene_by_id` (existing) asserts the exact response keys, adding keys is compatible — it checks `name`/`id` only.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/web/schemas.py src/dj_ledfx/web/router_scene.py tests/web/test_router_scene.py
git commit -m "feat: SceneDetail endpoint with placements/mapping/bounds and mapping_params updates"
```

---

### Task 6: Expose stable_id on DeviceResponse

The activate-conflict payload contains stable_ids; the UI needs to map them to display names.

**Files:**
- Modify: `src/dj_ledfx/web/schemas.py` (`DeviceResponse`)
- Modify: `src/dj_ledfx/web/router_devices.py` (`list_devices`)
- Test: `tests/web/test_router_devices.py`

- [ ] **Step 1: Write the failing test** — in the existing list-devices test (real DeviceManager pattern at the top of the file), add/extend:

```python
    def test_list_devices_includes_stable_id(self) -> None:
        # reuse the existing fixture that registers a device with stable_id
        resp = client.get("/api/devices")
        body = resp.json()
        assert body[0]["stable_id"] == body[0].get("stable_id")  # replace with the fixture's actual stable_id
```
Use the actual fixture's stable_id value (read the file's `_make_*` helper; if its adapter has no stable_id, `effective_id` falls back to the name — assert that).

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/web/test_router_devices.py -k stable_id -v` → KeyError/None.

- [ ] **Step 3: Implement** — `schemas.py` `DeviceResponse` add field:
```python
    stable_id: str | None = None
```
`router_devices.py` `list_devices`, in the `DeviceResponse(` constructor add:
```python
                stable_id=info.effective_id,
```

- [ ] **Step 4: Run** — `uv run pytest tests/web/ -v` → ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/web/schemas.py src/dj_ledfx/web/router_devices.py tests/web/test_router_devices.py
git commit -m "feat: expose stable_id in device list responses"
```

---

### Task 7: Frontend — types, ApiError, and scene API methods

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-client.ts`

- [ ] **Step 1: types.ts** — add after the existing scene types, and add `stable_id: string | null` to `Device`:

```ts
export interface SceneListItem {
  id: string
  name: string
  is_active: boolean
  mapping_type: "linear" | "radial" | null
  effect_mode: "independent" | "shared" | null
}

export interface SceneDetail extends SceneListItem {
  placements: Placement[]
  mapping: MappingInfo | null
  bounds: [[number, number, number], [number, number, number]] | null
}

export interface SceneEffect {
  effect_name: string
  params: Record<string, unknown>
}
```

- [ ] **Step 2: api-client.ts** — structured errors. Replace the `if (!resp.ok)` block in `fetchJson` and export the class:

```ts
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}
```
```ts
  if (!resp.ok) {
    const body = (await resp.json().catch(() => ({}))) as { detail?: unknown }
    const message =
      typeof body.detail === "string" ? body.detail : `HTTP ${resp.status}`
    throw new ApiError(message, resp.status, body.detail)
  }
```
(Existing call sites read `e.message` — behavior is unchanged for string details.)

- [ ] **Step 3: api-client.ts** — scene methods (new section after the legacy `// Scene` block); import `SceneDetail`, `SceneListItem`, `SceneEffect` from `./types`:

```ts
// Multi-scene
export async function listScenes(): Promise<SceneListItem[]> {
  return fetchJson("/scenes")
}

export async function createScene(name: string): Promise<SceneListItem> {
  return fetchJson("/scenes", { method: "POST", body: JSON.stringify({ name }) })
}

export async function updateScene(
  sceneId: string,
  updates: {
    name?: string
    mapping_type?: "linear" | "radial"
    effect_mode?: "independent" | "shared"
    mapping_params?: Record<string, unknown>
  },
): Promise<SceneListItem> {
  return fetchJson(`/scenes/${encodeURIComponent(sceneId)}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  })
}

export async function deleteScene(sceneId: string): Promise<void> {
  await fetchJson(`/scenes/${encodeURIComponent(sceneId)}`, { method: "DELETE" })
}

export async function activateScene(sceneId: string): Promise<void> {
  await fetchJson(`/scenes/${encodeURIComponent(sceneId)}/activate`, { method: "POST" })
}

export async function deactivateScene(sceneId: string): Promise<void> {
  await fetchJson(`/scenes/${encodeURIComponent(sceneId)}/deactivate`, { method: "POST" })
}

export async function getSceneDetail(sceneId: string): Promise<SceneDetail> {
  return fetchJson(`/scenes/${encodeURIComponent(sceneId)}`)
}

export async function getSceneEffect(sceneId: string): Promise<SceneEffect> {
  return fetchJson(`/scenes/${encodeURIComponent(sceneId)}/effect`)
}

export async function setSceneEffect(
  sceneId: string,
  effectName: string,
  params: Record<string, unknown>,
): Promise<void> {
  await fetchJson(`/scenes/${encodeURIComponent(sceneId)}/effect`, {
    method: "PUT",
    body: JSON.stringify({ effect_name: effectName, params }),
  })
}

export async function updateScenePlacement(
  sceneId: string,
  deviceName: string,
  opts: {
    position?: [number, number, number]
    geometry?: string
    direction?: number[]
    length?: number
    led_count?: number
  },
): Promise<void> {
  await fetchJson(
    `/scenes/${encodeURIComponent(sceneId)}/devices/${encodeURIComponent(deviceName)}`,
    { method: "PUT", body: JSON.stringify(opts) },
  )
}

export async function deleteScenePlacement(
  sceneId: string,
  deviceName: string,
): Promise<void> {
  await fetchJson(
    `/scenes/${encodeURIComponent(sceneId)}/devices/${encodeURIComponent(deviceName)}`,
    { method: "DELETE" },
  )
}
```

- [ ] **Step 4: Verify** — `cd frontend && npx tsc --noEmit` → clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api-client.ts
git commit -m "feat(web): scene API client methods, SceneDetail types, structured ApiError"
```

---

### Task 8: Frontend — useScenes hook + parameterize useScene

**Files:**
- Create: `frontend/src/hooks/use-scenes.ts`
- Modify: `frontend/src/hooks/use-scene.ts`

- [ ] **Step 1: Create `frontend/src/hooks/use-scenes.ts`**

```ts
import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import type { Device, SceneListItem } from "@/lib/types"
import * as api from "@/lib/api-client"
import { ApiError } from "@/lib/api-client"

function conflictMessage(detail: unknown, devices: Device[]): string | null {
  if (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { error?: string }).error === "device_conflict"
  ) {
    const ids = (detail as { conflicting_devices?: string[] }).conflicting_devices ?? []
    const names = ids.map(
      (id) => devices.find((d) => d.stable_id === id)?.name ?? id,
    )
    return `Device conflict: ${names.join(", ")} already in another active scene`
  }
  return null
}

export function useScenes(devices: Device[] = []) {
  const [scenes, setScenes] = useState<SceneListItem[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setScenes(await api.listScenes())
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load scenes")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const create = useCallback(
    async (name: string) => {
      const scene = await api.createScene(name)
      await refresh()
      return scene
    },
    [refresh],
  )

  const rename = useCallback(
    async (sceneId: string, name: string) => {
      await api.updateScene(sceneId, { name })
      await refresh()
    },
    [refresh],
  )

  const setEffectMode = useCallback(
    async (sceneId: string, mode: "independent" | "shared") => {
      await api.updateScene(sceneId, { effect_mode: mode })
      await refresh()
    },
    [refresh],
  )

  const remove = useCallback(
    async (sceneId: string) => {
      await api.deleteScene(sceneId)
      await refresh()
    },
    [refresh],
  )

  const activate = useCallback(
    async (sceneId: string): Promise<boolean> => {
      try {
        await api.activateScene(sceneId)
        await refresh()
        return true
      } catch (e) {
        const msg =
          e instanceof ApiError
            ? (conflictMessage(e.detail, devices) ?? e.message)
            : "Failed to activate scene"
        toast.error(msg)
        return false
      }
    },
    [refresh, devices],
  )

  const deactivate = useCallback(
    async (sceneId: string) => {
      await api.deactivateScene(sceneId)
      await refresh()
    },
    [refresh],
  )

  return { scenes, loading, refresh, create, rename, remove, setEffectMode, activate, deactivate }
}
```

- [ ] **Step 2: Parameterize `frontend/src/hooks/use-scene.ts`**

Keep the exact return shape. `sceneId === null` → legacy endpoints (today's behavior, the "Default" TOML scene). A DB id → per-scene endpoints; after mutating an *active* scene, re-apply (deactivate→activate) so the running pipeline picks up the change:

```ts
import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import type { SceneData } from "@/lib/types"
import * as api from "@/lib/api-client"

export function useScene(sceneId: string | null = null) {
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isActive, setIsActive] = useState(false)

  const refresh = useCallback(async () => {
    try {
      if (sceneId === null) {
        setScene(await api.getScene())
        setIsActive(false)
      } else {
        const detail = await api.getSceneDetail(sceneId)
        setScene(detail)
        setIsActive(detail.is_active)
      }
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scene")
    } finally {
      setLoading(false)
    }
  }, [sceneId])

  useEffect(() => {
    setLoading(true)
    setScene(null)
    refresh()
  }, [refresh])

  // Rebuild the running pipeline after editing an active scene (placements and
  // mapping are read only at activation).
  const reapply = useCallback(async () => {
    if (sceneId === null || !isActive) return
    await api.deactivateScene(sceneId)
    await api.activateScene(sceneId)
    toast.info("Scene re-applied")
  }, [sceneId, isActive])

  const movePlacement = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      try {
        if (sceneId === null) {
          await api.updateSceneDevice(deviceId, { position })
        } else {
          await api.updateScenePlacement(sceneId, deviceId, { position })
          await reapply()
        }
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update placement")
      }
    },
    [sceneId, reapply, refresh],
  )

  const removePlacement = useCallback(
    async (deviceId: string) => {
      try {
        if (sceneId === null) {
          await api.deleteSceneDevice(deviceId)
        } else {
          await api.deleteScenePlacement(sceneId, deviceId)
          await reapply()
        }
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to remove placement")
      }
    },
    [sceneId, reapply, refresh],
  )

  const changeMapping = useCallback(
    async (type: "linear" | "radial", params: Record<string, unknown>) => {
      try {
        // Optimistically update mapping so handle positions don't jump
        setScene((prev) => (prev ? { ...prev, mapping: { type, params } } : prev))
        if (sceneId === null) {
          await api.updateSceneMapping(type, params)
        } else {
          await api.updateScene(sceneId, { mapping_type: type, mapping_params: params })
          await reapply()
        }
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update mapping")
      }
    },
    [sceneId, reapply, refresh],
  )

  const addPlacement = useCallback(
    async (deviceId: string, ledCount?: number) => {
      try {
        const opts = { position: [0, 0, 0] as [number, number, number], led_count: ledCount ?? 1 }
        if (sceneId === null) {
          await api.updateSceneDevice(deviceId, opts)
        } else {
          await api.updateScenePlacement(sceneId, deviceId, opts)
          await reapply()
        }
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to add placement")
      }
    },
    [sceneId, reapply, refresh],
  )

  return { scene, loading, error, isActive, refresh, movePlacement, removePlacement, changeMapping, addPlacement }
}
```

Note: keep importing named functions OR switch to `* as api` — pick `* as api` (shown above) and update the import; do not leave both styles.

- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit` → clean (existing call sites pass no argument; the default `null` preserves behavior).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-scenes.ts frontend/src/hooks/use-scene.ts
git commit -m "feat(web): useScenes hook and scene-parameterized useScene with active re-apply"
```

---

### Task 9: Frontend — ScenesPanel + Scene page wiring

**Files:**
- Create: `frontend/src/components/scene/scenes-panel.tsx`
- Modify: `frontend/src/pages/scene.tsx`

- [ ] **Step 1: Create `frontend/src/components/scene/scenes-panel.tsx`**

Follow the panel conventions (Card + compact `h-7 text-xs` controls, sonner toasts). The "Default" pseudo-scene is client-side (`id: null`), always active, not deletable/renamable:

```tsx
import { useState } from "react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { SceneListItem } from "@/lib/types"

interface ScenesPanelProps {
  scenes: SceneListItem[]
  selectedSceneId: string | null
  onSelectScene: (sceneId: string | null) => void
  onCreate: (name: string) => Promise<SceneListItem>
  onRename: (sceneId: string, name: string) => Promise<void>
  onDelete: (sceneId: string) => Promise<void>
  onActivate: (sceneId: string) => Promise<boolean>
  onDeactivate: (sceneId: string) => Promise<void>
  onEffectModeChange: (sceneId: string, mode: "independent" | "shared") => Promise<void>
}

export default function ScenesPanel({
  scenes,
  selectedSceneId,
  onSelectScene,
  onCreate,
  onRename,
  onDelete,
  onActivate,
  onDeactivate,
  onEffectModeChange,
}: ScenesPanelProps) {
  const [newName, setNewName] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")

  const handleCreate = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      const scene = await onCreate(name)
      setNewName("")
      onSelectScene(scene.id)
      toast.success(`Created scene "${name}"`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to create scene")
    }
  }

  const handleRename = async (sceneId: string) => {
    const name = editName.trim()
    setEditingId(null)
    if (!name) return
    try {
      await onRename(sceneId, name)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to rename scene")
    }
  }

  const selected = scenes.find((s) => s.id === selectedSceneId) ?? null

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Scenes</CardTitle>
      </CardHeader>
      <CardContent className="p-0 px-3 pb-3 space-y-0.5">
        {/* Default pseudo-scene (legacy TOML scene) */}
        <button
          onClick={() => onSelectScene(null)}
          className={cn(
            "w-full text-left px-2 py-1.5 rounded text-sm transition-colors flex items-center justify-between",
            selectedSceneId === null ? "bg-primary/15 text-primary" : "hover:bg-muted",
          )}
        >
          <span className="truncate">Default</span>
          <Badge variant="outline" className="text-[10px] ml-1 shrink-0">
            active
          </Badge>
        </button>

        {scenes.map((s) => (
          <div
            key={s.id}
            className={cn(
              "w-full px-2 py-1.5 rounded text-sm transition-colors flex items-center justify-between gap-1",
              selectedSceneId === s.id ? "bg-primary/15 text-primary" : "hover:bg-muted",
            )}
          >
            {editingId === s.id ? (
              <Input
                autoFocus
                className="h-6 text-xs"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onBlur={() => handleRename(s.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRename(s.id)
                  if (e.key === "Escape") setEditingId(null)
                }}
              />
            ) : (
              <button
                className="truncate text-left flex-1"
                onClick={() => onSelectScene(s.id)}
                onDoubleClick={() => {
                  setEditingId(s.id)
                  setEditName(s.name)
                }}
                title="Double-click to rename"
              >
                {s.name}
              </button>
            )}
            <span className="flex items-center gap-1 shrink-0">
              {s.is_active && (
                <Badge className="text-[10px]" variant="default">
                  active
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                className="h-5 px-1.5 text-[10px]"
                onClick={async (e) => {
                  e.stopPropagation()
                  if (s.is_active) {
                    await onDeactivate(s.id)
                    toast.success(`Deactivated "${s.name}"`)
                  } else if (await onActivate(s.id)) {
                    toast.success(`Activated "${s.name}"`)
                  }
                }}
              >
                {s.is_active ? "Stop" : "Go"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-5 w-5 p-0 text-xs text-muted-foreground"
                onClick={async (e) => {
                  e.stopPropagation()
                  await onDelete(s.id)
                  if (selectedSceneId === s.id) onSelectScene(null)
                  toast.success(`Deleted "${s.name}"`)
                }}
              >
                ×
              </Button>
            </span>
          </div>
        ))}

        {selected && (
          <div className="pt-1.5 flex items-center gap-2">
            <span className="text-xs text-muted-foreground shrink-0">Effect mode</span>
            <Select
              value={selected.effect_mode ?? "independent"}
              onValueChange={(v) =>
                onEffectModeChange(selected.id, v as "independent" | "shared").catch(
                  (e: unknown) =>
                    toast.error(e instanceof Error ? e.message : "Failed to change mode"),
                )
              }
              disabled={selected.is_active}
            >
              <SelectTrigger className="h-7 text-xs flex-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="independent">independent</SelectItem>
                <SelectItem value="shared">shared</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="pt-1.5 flex items-center gap-1">
          <Input
            className="h-7 text-xs"
            placeholder="New scene name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={handleCreate}>
            +
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
```

(Check the exact `Select` import names against `frontend/src/components/ui/select.tsx` and `scene-toolbar.tsx` usage before writing — base-ui shadcn variants can differ from Radix.)

- [ ] **Step 2: Wire into `frontend/src/pages/scene.tsx`**

- Add imports: `ScenesPanel`, `useScenes`.
- Add state + hooks (replace the existing `useScene()` call):
```tsx
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null)
  const { scene, loading, movePlacement, removePlacement, changeMapping, addPlacement } =
    useScene(selectedSceneId)
  const { devices, frameData } = useDevices()
  const scenesApi = useScenes(devices)
```
- When switching scenes, clear selection: wrap `setSelectedSceneId` in a handler that also calls `setSelectedId(null)` and `setSelectedHandle(null)`.
- In the left column, render ScenesPanel above DeviceListPanel:
```tsx
        <div className="w-52 shrink-0 flex flex-col gap-2 min-h-0">
          <ScenesPanel
            scenes={scenesApi.scenes}
            selectedSceneId={selectedSceneId}
            onSelectScene={handleSelectScene}
            onCreate={scenesApi.create}
            onRename={scenesApi.rename}
            onDelete={scenesApi.remove}
            onActivate={scenesApi.activate}
            onDeactivate={scenesApi.deactivate}
            onEffectModeChange={scenesApi.setEffectMode}
          />
          <div className="flex-1 min-h-0">
            <DeviceListPanel ... (unchanged props) />
          </div>
        </div>
```
- Everything else (viewport, toolbar, properties, mapping preview) is unchanged — it reads from `scene`, which now reflects the selected scene.
- Note: `useScenes` list excludes the Default pseudo-scene; when the backend has no DB, `listScenes` returns `[{id:"default", ...}]` — filter that sentinel out in the page (`scenesApi.scenes.filter((s) => s.id !== "default")`) so it doesn't duplicate the client-side Default row.

- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit && npm run build` → clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/scene/scenes-panel.tsx frontend/src/pages/scene.tsx
git commit -m "feat(web): scene management panel with per-scene 3D editing"
```

---

### Task 10: Frontend — per-scene effect tabs on the Live page

**Files:**
- Create: `frontend/src/hooks/use-scene-effects.ts`
- Modify: `frontend/src/pages/live.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/use-scene-effects.ts`**

Provides the same prop surface `EffectDeck` consumes, but driving `GET/PUT /api/scenes/{id}/effect`. `EffectDeck` itself is NOT modified:

```ts
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import * as api from "@/lib/api-client"
import type { EffectParamSchema, Preset } from "@/lib/types"

export function useSceneEffects(sceneId: string) {
  const [schemas, setSchemas] = useState<Record<string, Record<string, EffectParamSchema>>>({})
  const [activeEffect, setActiveEffect] = useState("")
  const [activeParams, setActiveParams] = useState<Record<string, unknown>>({})
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([api.getEffects(), api.getSceneEffect(sceneId), api.getPresets()])
      .then(([effects, active, presetList]) => {
        if (cancelled) return
        setSchemas(effects)
        setActiveEffect(active.effect_name)
        setActiveParams(active.params)
        setPresets(presetList)
      })
      .catch((e) => console.error("Failed to init scene effects:", e))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [sceneId])

  const apply = useCallback(
    async (effectName: string, params: Record<string, unknown>) => {
      await api.setSceneEffect(sceneId, effectName, params)
      const active = await api.getSceneEffect(sceneId)
      setActiveEffect(active.effect_name)
      setActiveParams(active.params)
    },
    [sceneId],
  )

  const switchEffect = useCallback(
    (name: string, params?: Record<string, unknown>) => apply(name, params ?? {}),
    [apply],
  )

  const updateParam = useCallback(
    (key: string, value: unknown) => apply(activeEffect, { [key]: value }),
    [apply, activeEffect],
  )

  const loadPreset = useCallback(
    async (name: string) => {
      const preset = presets.find((p) => p.name === name)
      if (!preset) return
      await apply(preset.effect_class, preset.params)
    },
    [apply, presets],
  )

  const savePreset = useCallback(async (_name: string) => {
    toast.info("Presets can only be saved from the Default deck")
  }, [])

  return { schemas, activeEffect, activeParams, presets, loading, switchEffect, updateParam, loadPreset, savePreset }
}
```

- [ ] **Step 2: Rework `frontend/src/pages/live.tsx`**

Tabs: "Default" + one per *active* scene. Hooks must not be called conditionally, so each scene deck is its own component. The viewport follows the selected tab:

```tsx
import { useState } from "react"
import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useSceneEffects } from "@/hooks/use-scene-effects"
import { useScenes } from "@/hooks/use-scenes"
import { useDevices } from "@/hooks/use-devices"
import { useScene } from "@/hooks/use-scene"
import { useTransport } from "@/hooks/use-transport"
import { TransportSection } from "@/components/transport-section"
import { EffectDeck } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function SceneEffectDeck({ sceneId }: { sceneId: string }) {
  const effects = useSceneEffects(sceneId)
  return (
    <EffectDeck
      schemas={effects.schemas}
      activeEffect={effects.activeEffect}
      activeParams={effects.activeParams}
      presets={effects.presets}
      loading={effects.loading}
      switchEffect={effects.switchEffect}
      updateParam={effects.updateParam}
      loadPreset={effects.loadPreset}
      savePreset={effects.savePreset}
    />
  )
}

export default function LivePage() {
  const beat = useBeat()
  const effects = useEffects()
  const { devices, frameData } = useDevices()
  const { transportState, setTransportState } = useTransport()
  const { scenes } = useScenes(devices)
  const [selectedTab, setSelectedTab] = useState("default")

  const activeScenes = scenes.filter((s) => s.is_active && s.id !== "default")
  // Fall back to Default if the selected scene was deactivated elsewhere
  const currentTab = activeScenes.some((s) => s.id === selectedTab) ? selectedTab : "default"
  const { scene } = useScene(currentTab === "default" ? null : currentTab)

  const placements = scene?.placements ?? []

  return (
    <div className="flex flex-col gap-3 h-full">
      <TransportSection beat={beat} transportState={transportState} onTransportChange={setTransportState} />

      <div className="flex gap-3 flex-1 min-h-0">
        <div className="flex-1 min-w-0 min-h-0 rounded-lg border border-border overflow-hidden">
          <SceneViewport>
            {placements.map((p) => (
              <DeviceMesh
                key={p.device_id}
                position={p.position}
                geometry={p.geometry}
                ledCount={p.led_count}
                frameData={frameData.get(p.device_id) ?? null}
              />
            ))}
          </SceneViewport>
        </div>

        <div className="w-80 shrink-0 min-h-0 flex flex-col gap-2">
          {activeScenes.length > 0 && (
            <Tabs value={currentTab} onValueChange={setSelectedTab}>
              <TabsList className="w-full">
                <TabsTrigger value="default" className="text-xs">
                  Default
                </TabsTrigger>
                {activeScenes.map((s) => (
                  <TabsTrigger key={s.id} value={s.id} className="text-xs">
                    {s.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}
          <div className="flex-1 min-h-0">
            {currentTab === "default" ? (
              <EffectDeck
                schemas={effects.schemas}
                activeEffect={effects.activeEffect}
                activeParams={effects.activeParams}
                presets={effects.presets}
                loading={effects.loading}
                switchEffect={effects.switchEffect}
                updateParam={effects.updateParam}
                loadPreset={effects.loadPreset}
                savePreset={effects.savePreset}
              />
            ) : (
              <SceneEffectDeck key={currentTab} sceneId={currentTab} />
            )}
          </div>
        </div>
      </div>

      <DeviceMonitor devices={devices} frameData={frameData} />
    </div>
  )
}
```

(Check `frontend/src/components/ui/tabs.tsx` and `pages/config.tsx` for the exact Tabs API before writing — base-ui shadcn.)

- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit && npm run build` → clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-scene-effects.ts frontend/src/pages/live.tsx
git commit -m "feat(web): per-scene effect decks with tabs on the Live page"
```

---

### Task 11: Full verification

- [ ] **Step 1:** `uv run pytest -q` → all pass (baseline was 680; expect ~690+).
- [ ] **Step 2:** `uv run ruff check . && uv run ruff format --check .` → clean (run `uv run ruff format .` if needed).
- [ ] **Step 3:** `uv run mypy src/` → clean.
- [ ] **Step 4:** `cd frontend && npx tsc --noEmit && npm run build` → clean.
- [ ] **Step 5:** Commit any formatting fallout: `git commit -am "chore: format"` (only if needed).

---

## Self-Review Notes

- Spec coverage: defects 1-3 → Tasks 1-3; gap 4 (placement read) → Task 5; gap 5 (mapping_params) → Task 5; placement-delete bug → Task 4; stable_id exposure → Task 6; client/types → Task 7; hooks → Task 8; Scene page UI → Task 9; Live page tabs → Task 10. WS deviation documented in spec (REST kept).
- Type consistency: `SceneDetail` (py + ts) field names match; `useScene` return adds `isActive` without removing fields; `useSceneEffects` matches `EffectDeck` props as consumed in `live.tsx:45-55`.
- Known intentional behaviors: re-apply cycle blinks devices on active-scene edits (documented in spec); Default pseudo-scene is client-side; preset save disabled on scene decks.
