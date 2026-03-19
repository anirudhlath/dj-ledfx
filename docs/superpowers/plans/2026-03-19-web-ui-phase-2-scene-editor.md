# Web UI Phase 2 — 3D Scene Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **IMPORTANT — No styling directives:** This plan provides functional component code with minimal layout. The visual design of every component and page should be created from scratch by the implementer. Use shadcn/ui components and Tailwind CSS freely — there are no prescribed colors, fonts, animations, or layout constraints. Design the UI to look great for a DJ performance tool.
>
> **IMPORTANT — shadcn/ui style:** This project uses the `base-nova` shadcn style backed by `@base-ui/react` (NOT Radix). All new shadcn components must be added via `npx shadcn add <name>` from the `frontend/` directory. Do NOT mix in `@radix-ui` imports.

**Goal:** Build the 3D Scene Editor — a React Three Fiber viewport for placing LED devices in 3D space, with live LED color previews, a scene REST API, and runtime compositor rebuild.

**Architecture:** Backend adds SceneModel mutation methods + a scene REST router. The scheduler gets a compositor property setter for runtime swap. Frontend adds React Three Fiber with drei helpers for the 3D viewport, rendering devices as geometry-appropriate meshes (spheres, sphere-lines, sphere-grids) with live LED colors from binary WebSocket frame data. Three-panel layout: device list (left), 3D viewport (center), properties (right).

**Tech Stack:** Python (FastAPI, Pydantic), React Three Fiber (`@react-three/fiber`), drei (`@react-three/drei`), three.js, TypeScript, shadcn/ui, Tailwind CSS v4

**Branch:** `feature/web-ui` (has Phase 1 backend + frontend — must be checked out before starting)

**Spec:** `docs/superpowers/specs/2026-03-13-web-ui-design.md` sections 3.4, 7, 8

---

## Prerequisites

- On the `feature/web-ui` branch (has working Phase 1 backend + React frontend)
- `uv sync --extra web` (backend deps installed)
- `cd frontend && npm install` (frontend deps installed)
- Spatial mapping module exists at `src/dj_ledfx/spatial/` (merged from `feature/3d-spatial-mapping`)

## Key Dependencies Reference

**Backend spatial types (already exist):**
- `DevicePlacement` — frozen dataclass: `device_id: str`, `position: tuple[float,float,float]`, `geometry: DeviceGeometry`, `led_count: int`
- `DeviceGeometry` — union: `PointGeometry | StripGeometry | MatrixGeometry`
- `SceneModel` — `placements: dict[str, DevicePlacement]`, `get_led_positions(device_id) -> NDArray`, `get_bounds() -> (min, max)`
- `SpatialCompositor` — constructed with `(scene, mapping)`, has `composite(effect_strip, device_id) -> NDArray | None`
- `SpatialMapping` — Protocol with `map_positions(positions) -> NDArray`; impls: `LinearMapping`, `RadialMapping`

**Frontend patterns (established in Phase 1):**
- REST calls go through `fetchJson<T>()` in `src/lib/api-client.ts`
- WS subscriptions via `wsClient.on(channel, handler)` in `src/lib/ws-client.ts` returning unsubscribe fn
- Hooks follow `use-*.ts` pattern in `src/hooks/`
- Pages in `src/pages/*.tsx`, routes in `App.tsx`
- shadcn/ui uses `@base-ui/react` primitives (NOT Radix)

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `src/dj_ledfx/web/router_scene.py` | Scene REST endpoints: placements CRUD, mapping config, scene overview |

### Backend — Modified Files

| File | Change |
|------|--------|
| `src/dj_ledfx/spatial/scene.py` | Add `add_placement()`, `update_placement()`, `remove_placement()` methods |
| `src/dj_ledfx/scheduling/scheduler.py` | Add `compositor` property setter for runtime swap |
| `src/dj_ledfx/web/app.py` | Register scene router, type `scene_model` properly |
| `src/dj_ledfx/web/schemas.py` | Add Scene Pydantic models |
| `src/dj_ledfx/main.py` | Pass real `scene_model` (not `None`) to `create_app()` |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/hooks/use-scene.ts` | Scene state hook: placements, mapping, CRUD ops |
| `frontend/src/components/scene/scene-viewport.tsx` | R3F Canvas with camera, lights, grid, orbit controls |
| `frontend/src/components/scene/device-mesh.tsx` | Geometry-appropriate 3D mesh per device (sphere/strip/matrix) |
| `frontend/src/components/scene/device-list-panel.tsx` | Left panel: device list grouped by placed/unplaced |
| `frontend/src/components/scene/properties-panel.tsx` | Right panel: position XYZ, geometry info, group, latency |
| `frontend/src/components/scene/scene-toolbar.tsx` | Top toolbar: camera presets, transform mode, grid snap |
| `frontend/src/components/scene/mapping-preview.tsx` | Bottom bar: 1D gradient showing mapping result |

### Frontend — Modified Files

| File | Change |
|------|--------|
| `frontend/src/lib/types.ts` | Add scene/placement/geometry/mapping types |
| `frontend/src/lib/api-client.ts` | Add scene REST functions |
| `frontend/src/pages/scene.tsx` | Replace placeholder with full 3D scene editor |

### Test Files

| File | Tests |
|------|-------|
| `tests/spatial/test_scene.py` | Mutation method tests (add/update/remove + cache invalidation) |
| `tests/scheduling/test_scheduler.py` | Compositor property setter test |
| `tests/web/test_router_scene.py` | Scene REST endpoint integration tests |

---

## Chunk 1: Backend — SceneModel Mutations

### Task 1: Add mutation methods to SceneModel

**Files:**
- Modify: `src/dj_ledfx/spatial/scene.py`
- Test: `tests/spatial/test_scene.py`

- [ ] **Step 1: Write failing tests for add_placement**

Add to `tests/spatial/test_scene.py`:

```python
class TestSceneModelMutations:
    def test_add_placement(self) -> None:
        scene = SceneModel(placements={})
        placement = DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1)
        scene.add_placement(placement)
        assert "lamp" in scene.placements
        assert scene.placements["lamp"] is placement

    def test_add_placement_duplicate_raises(self) -> None:
        p = DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1)
        scene = SceneModel(placements={"lamp": p})
        with pytest.raises(ValueError, match="already exists"):
            scene.add_placement(p)

    def test_add_placement_invalidates_cache(self) -> None:
        scene = SceneModel(placements={
            "a": DevicePlacement("a", (0.0, 0.0, 0.0), PointGeometry(), 1),
        })
        _ = scene.get_led_positions("a")  # populate cache
        assert "a" in scene._position_cache
        p = DevicePlacement("b", (5.0, 0.0, 0.0), PointGeometry(), 1)
        scene.add_placement(p)
        # New device should not have stale cache
        assert "b" not in scene._position_cache
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_scene.py::TestSceneModelMutations -v`
Expected: FAIL with `AttributeError: 'SceneModel' object has no attribute 'add_placement'`

- [ ] **Step 3: Implement add_placement**

Add to `SceneModel` class in `src/dj_ledfx/spatial/scene.py`:

```python
def add_placement(self, placement: DevicePlacement) -> None:
    """Add a device to the scene. Raises ValueError if device_id already exists."""
    if placement.device_id in self.placements:
        raise ValueError(f"Device '{placement.device_id}' already exists in scene")
    self.placements[placement.device_id] = placement
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/spatial/test_scene.py::TestSceneModelMutations -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for update_placement**

Add to `TestSceneModelMutations`:

```python
def test_update_placement_position(self) -> None:
    geo = PointGeometry()
    p = DevicePlacement("lamp", (0.0, 0.0, 0.0), geo, 1)
    scene = SceneModel(placements={"lamp": p})
    scene.update_placement("lamp", position=(5.0, 3.0, 1.0))
    assert scene.placements["lamp"].position == (5.0, 3.0, 1.0)
    assert scene.placements["lamp"].geometry is geo  # unchanged

def test_update_placement_geometry(self) -> None:
    p = DevicePlacement("strip", (0.0, 0.0, 0.0), PointGeometry(), 10)
    scene = SceneModel(placements={"strip": p})
    new_geo = StripGeometry(direction=(0.0, 1.0, 0.0), length=2.0)
    scene.update_placement("strip", geometry=new_geo)
    assert scene.placements["strip"].geometry is new_geo
    assert scene.placements["strip"].position == (0.0, 0.0, 0.0)  # unchanged

def test_update_placement_invalidates_cache(self) -> None:
    p = DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1)
    scene = SceneModel(placements={"lamp": p})
    _ = scene.get_led_positions("lamp")
    assert "lamp" in scene._position_cache
    scene.update_placement("lamp", position=(5.0, 0.0, 0.0))
    assert "lamp" not in scene._position_cache

def test_update_placement_unknown_raises(self) -> None:
    scene = SceneModel(placements={})
    with pytest.raises(KeyError, match="nonexistent"):
        scene.update_placement("nonexistent", position=(0.0, 0.0, 0.0))
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_scene.py::TestSceneModelMutations::test_update_placement_position -v`
Expected: FAIL with `AttributeError`

- [ ] **Step 7: Implement update_placement**

Add to `SceneModel` class:

```python
def update_placement(
    self,
    device_id: str,
    position: tuple[float, float, float] | None = None,
    geometry: DeviceGeometry | None = None,
) -> None:
    """Update an existing placement. Raises KeyError if device_id not found."""
    old = self.placements[device_id]  # raises KeyError if missing
    self.placements[device_id] = DevicePlacement(
        device_id=device_id,
        position=position if position is not None else old.position,
        geometry=geometry if geometry is not None else old.geometry,
        led_count=old.led_count,
    )
    self._position_cache.pop(device_id, None)
```

Note: `DevicePlacement` is frozen, so we reconstruct it with the changed fields.

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/spatial/test_scene.py::TestSceneModelMutations -v`
Expected: PASS

- [ ] **Step 9: Write failing tests for remove_placement**

Add to `TestSceneModelMutations`:

```python
def test_remove_placement(self) -> None:
    p = DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1)
    scene = SceneModel(placements={"lamp": p})
    scene.remove_placement("lamp")
    assert "lamp" not in scene.placements

def test_remove_placement_clears_cache(self) -> None:
    p = DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1)
    scene = SceneModel(placements={"lamp": p})
    _ = scene.get_led_positions("lamp")
    assert "lamp" in scene._position_cache
    scene.remove_placement("lamp")
    assert "lamp" not in scene._position_cache

def test_remove_placement_unknown_raises(self) -> None:
    scene = SceneModel(placements={})
    with pytest.raises(KeyError, match="nonexistent"):
        scene.remove_placement("nonexistent")
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_scene.py::TestSceneModelMutations::test_remove_placement -v`
Expected: FAIL

- [ ] **Step 11: Implement remove_placement**

Add to `SceneModel` class:

```python
def remove_placement(self, device_id: str) -> None:
    """Remove a device from the scene. Raises KeyError if device_id not found."""
    del self.placements[device_id]  # raises KeyError if missing
    self._position_cache.pop(device_id, None)
```

- [ ] **Step 12: Run all mutation tests**

Run: `uv run pytest tests/spatial/test_scene.py -v`
Expected: ALL PASS

- [ ] **Step 13: Commit**

```bash
git add src/dj_ledfx/spatial/scene.py tests/spatial/test_scene.py
git commit -m "feat(spatial): add mutation methods to SceneModel (add/update/remove placement)"
```

### Task 2: Add compositor property setter to LookaheadScheduler

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py`
- Test: `tests/scheduling/test_scheduler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/scheduling/test_scheduler.py`. The existing tests construct objects inline (no fixtures). Follow the same pattern:

```python
def test_compositor_property_setter():
    """Compositor can be swapped at runtime via property setter."""
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.spatial.compositor import SpatialCompositor
    from dj_ledfx.spatial.geometry import PointGeometry
    from dj_ledfx.spatial.mapping import LinearMapping
    from dj_ledfx.spatial.scene import DevicePlacement, SceneModel

    buf = RingBuffer(capacity=60, led_count=10)
    scheduler = LookaheadScheduler(ring_buffer=buf, devices=[])
    assert scheduler.compositor is None

    scene = SceneModel(placements={
        "a": DevicePlacement("a", (0.0, 0.0, 0.0), PointGeometry(), 1),
    })
    new_comp = SpatialCompositor(scene, LinearMapping())
    scheduler.compositor = new_comp
    assert scheduler.compositor is new_comp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scheduling/test_scheduler.py::test_compositor_property_setter -v`
Expected: FAIL — either `AttributeError` for missing property or test not found

- [ ] **Step 3: Implement compositor property**

In `src/dj_ledfx/scheduling/scheduler.py`, add a property with getter and setter to `LookaheadScheduler`:

```python
@property
def compositor(self) -> SpatialCompositor | None:
    return self._compositor

@compositor.setter
def compositor(self, value: SpatialCompositor | None) -> None:
    self._compositor = value
```

Place these right after the `frame_snapshots` property (around line 78).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scheduling/test_scheduler.py::test_compositor_property_setter -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat(scheduler): add compositor property setter for runtime swap"
```

---

## Chunk 2: Backend — Scene REST API

### Task 3: Wire scene_model through main.py

**Files:**
- Modify: `src/dj_ledfx/main.py`

- [ ] **Step 1: Pass scene_model to create_app**

In `src/dj_ledfx/main.py`, find the `create_app()` call (around line 190). The `scene_model=None` argument needs to pass the real `scene` variable. The `scene` variable is created around line 116 inside the `if config.scene_config is not None:` block.

Change the variable scope: move `scene` declaration before the `if` block so it's accessible at the `create_app()` call:

Replace:
```python
    # Build spatial scene if configured
    compositor: SpatialCompositor | None = None
    if config.scene_config is not None:
        adapters = [d.adapter for d in device_manager.devices]
        scene = SceneModel.from_config(config.scene_config, adapters)
```

With:
```python
    # Build spatial scene if configured
    scene: SceneModel | None = None
    compositor: SpatialCompositor | None = None
    if config.scene_config is not None:
        adapters = [d.adapter for d in device_manager.devices]
        scene = SceneModel.from_config(config.scene_config, adapters)
```

Then in the `create_app()` call, change `scene_model=None` to `scene_model=scene`.

- [ ] **Step 2: Run existing tests to confirm no regression**

Run: `uv run pytest -x -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "fix(main): pass real scene_model to create_app instead of None"
```

### Task 4: Add Scene Pydantic schemas

**Files:**
- Modify: `src/dj_ledfx/web/schemas.py`

- [ ] **Step 1: Add scene schemas**

Append to `src/dj_ledfx/web/schemas.py`:

```python
# Scene

class GeometrySchema(BaseModel):
    type: str  # "point", "strip", "matrix"
    direction: list[float] | None = None  # strip only
    length: float | None = None  # strip only
    pixel_pitch: float | None = None  # matrix only
    tiles: list[dict[str, Any]] | None = None  # matrix only


class PlacementResponse(BaseModel):
    device_id: str
    position: list[float]  # [x, y, z]
    geometry: GeometrySchema
    led_count: int


class UpdatePlacementRequest(BaseModel):
    position: list[float] | None = None  # [x, y, z]
    geometry: str | None = None  # "point", "strip", "matrix"
    direction: list[float] | None = None  # for strip
    length: float | None = None  # for strip
    led_count: int | None = None  # required when adding a new device


class MappingResponse(BaseModel):
    type: str  # "linear" or "radial"
    params: dict[str, Any]


class UpdateMappingRequest(BaseModel):
    type: str  # "linear" or "radial"
    params: dict[str, Any] = {}


class SceneResponse(BaseModel):
    placements: list[PlacementResponse]
    mapping: MappingResponse | None = None
    bounds: list[list[float]] | None = None  # [[min_x,min_y,min_z],[max_x,max_y,max_z]]
```

- [ ] **Step 2: Verify schemas import cleanly**

Run: `uv run python -c "from dj_ledfx.web.schemas import SceneResponse, PlacementResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/web/schemas.py
git commit -m "feat(web): add Scene Pydantic schemas"
```

### Task 5: Create router_scene.py

**Files:**
- Create: `src/dj_ledfx/web/router_scene.py`
- Create: `tests/web/test_router_scene.py` (and `tests/web/__init__.py` if needed)

- [ ] **Step 1: Write integration tests**

Create `tests/web/__init__.py` (empty) if it doesn't exist.

Create `tests/web/test_router_scene.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry
from dj_ledfx.spatial.mapping import LinearMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from dj_ledfx.web.app import create_app


def _make_test_app(scene: SceneModel | None = None) -> TestClient:
    """Create a test FastAPI app with a scene model."""
    from unittest.mock import MagicMock

    compositor = None
    if scene and scene.placements:
        compositor = SpatialCompositor(scene, LinearMapping())

    # Minimal mocks for required create_app args
    mock_config = MagicMock()
    mock_config.web.cors_origins = ["*"]
    mock_config.web.static_dir = None

    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=scene,
        compositor=compositor,
        config=mock_config,
        config_path=None,
    )
    return TestClient(app)


class TestSceneEndpoints:
    def test_get_scene_empty(self) -> None:
        client = _make_test_app(SceneModel(placements={}))
        resp = client.get("/api/scene")
        assert resp.status_code == 200
        data = resp.json()
        assert data["placements"] == []

    def test_get_scene_with_placements(self) -> None:
        scene = SceneModel(placements={
            "lamp": DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1),
        })
        client = _make_test_app(scene)
        resp = client.get("/api/scene")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["placements"]) == 1
        assert data["placements"][0]["device_id"] == "lamp"
        assert data["placements"][0]["position"] == [1.0, 2.0, 0.0]

    def test_get_scene_devices(self) -> None:
        scene = SceneModel(placements={
            "lamp": DevicePlacement("lamp", (1.0, 2.0, 0.0), PointGeometry(), 1),
            "strip": DevicePlacement("strip", (0.0, 0.0, 0.0), StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0), 10),
        })
        client = _make_test_app(scene)
        resp = client.get("/api/scene/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_put_scene_device_update_position(self) -> None:
        scene = SceneModel(placements={
            "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
        })
        client = _make_test_app(scene)
        resp = client.put("/api/scene/devices/lamp", json={"position": [5.0, 3.0, 1.0]})
        assert resp.status_code == 200
        assert resp.json()["position"] == [5.0, 3.0, 1.0]
        # Verify scene was mutated
        assert scene.placements["lamp"].position == (5.0, 3.0, 1.0)

    def test_delete_scene_device(self) -> None:
        scene = SceneModel(placements={
            "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
        })
        client = _make_test_app(scene)
        resp = client.delete("/api/scene/devices/lamp")
        assert resp.status_code == 200
        assert "lamp" not in scene.placements

    def test_delete_scene_device_not_found(self) -> None:
        scene = SceneModel(placements={})
        client = _make_test_app(scene)
        resp = client.delete("/api/scene/devices/nonexistent")
        assert resp.status_code == 404

    def test_put_scene_device_add_new(self) -> None:
        """PUT should add a device if it's not already in the scene (spec: 'Add/update')."""
        scene = SceneModel(placements={})
        client = _make_test_app(scene)
        resp = client.put("/api/scene/devices/new_lamp", json={
            "position": [1.0, 2.0, 0.0],
            "geometry": "point",
            "led_count": 1,
        })
        assert resp.status_code == 200
        assert "new_lamp" in scene.placements
        assert resp.json()["device_id"] == "new_lamp"

    def test_update_mapping(self) -> None:
        scene = SceneModel(placements={
            "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
        })
        client = _make_test_app(scene)
        resp = client.put("/api/scene/mapping", json={"type": "radial", "params": {"center": [0, 0, 0]}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "radial"

    def test_compositor_rebuilt_after_mutation(self) -> None:
        """Verify scheduler.compositor is updated after a device position change."""
        from unittest.mock import MagicMock

        scene = SceneModel(placements={
            "lamp": DevicePlacement("lamp", (0.0, 0.0, 0.0), PointGeometry(), 1),
        })
        mock_config = MagicMock()
        mock_config.web.cors_origins = ["*"]
        mock_config.web.static_dir = None
        mock_config.scene_config = {"mapping": "linear", "mapping_params": {}}
        mock_scheduler = MagicMock()

        app = create_app(
            beat_clock=MagicMock(),
            effect_deck=MagicMock(),
            effect_engine=MagicMock(),
            device_manager=MagicMock(),
            scheduler=mock_scheduler,
            preset_store=MagicMock(),
            scene_model=scene,
            compositor=SpatialCompositor(scene, LinearMapping()),
            config=mock_config,
            config_path=None,
        )
        client = TestClient(app)
        client.put("/api/scene/devices/lamp", json={"position": [5.0, 0.0, 0.0]})
        # Verify compositor was reassigned on the scheduler mock
        assert mock_scheduler.compositor is not None

    def test_get_scene_no_scene_model(self) -> None:
        client = _make_test_app(None)
        resp = client.get("/api/scene")
        assert resp.status_code == 200
        data = resp.json()
        assert data["placements"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_router_scene.py -v`
Expected: FAIL (router_scene doesn't exist yet)

- [ ] **Step 3: Create router_scene.py**

Create `src/dj_ledfx/web/router_scene.py`:

```python
"""Scene REST endpoints for 3D device placement and spatial mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import (
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
)
from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping
from dj_ledfx.web.schemas import (
    GeometrySchema,
    MappingResponse,
    PlacementResponse,
    SceneResponse,
    UpdateMappingRequest,
    UpdatePlacementRequest,
)

if TYPE_CHECKING:
    from dj_ledfx.spatial.scene import SceneModel

router = APIRouter(prefix="/scene", tags=["scene"])


def _get_scene(request: Request) -> SceneModel | None:
    return request.app.state.scene_model


def _placement_to_response(p) -> PlacementResponse:
    geo = p.geometry
    if isinstance(geo, PointGeometry):
        geo_schema = GeometrySchema(type="point")
    elif isinstance(geo, StripGeometry):
        geo_schema = GeometrySchema(
            type="strip",
            direction=list(geo.direction),
            length=geo.length,
        )
    elif isinstance(geo, MatrixGeometry):
        geo_schema = GeometrySchema(
            type="matrix",
            pixel_pitch=geo.pixel_pitch,
            tiles=[
                {"offset_x": t.offset_x, "offset_y": t.offset_y, "width": t.width, "height": t.height}
                for t in geo.tiles
            ],
        )
    else:
        geo_schema = GeometrySchema(type="unknown")

    return PlacementResponse(
        device_id=p.device_id,
        position=list(p.position),
        geometry=geo_schema,
        led_count=p.led_count,
    )


def _rebuild_compositor(request: Request, scene: SceneModel) -> None:
    """Rebuild the spatial compositor after a scene mutation."""
    scheduler = request.app.state.scheduler
    if not scene.placements:
        scheduler.compositor = None
        request.app.state.compositor = None
        return

    # Use existing mapping type or default to linear
    old_compositor = request.app.state.compositor
    mapping = LinearMapping()  # default
    # Preserve mapping from config if available
    config = request.app.state.config
    if config.scene_config is not None:
        mapping_name = config.scene_config.get("mapping", "linear")
        mapping_params = config.scene_config.get("mapping_params", {})
        if mapping_name == "radial":
            center = mapping_params.get("center", [0.0, 0.0, 0.0])
            max_radius = mapping_params.get("max_radius")
            mapping = RadialMapping(
                center=(float(center[0]), float(center[1]), float(center[2])),
                max_radius=float(max_radius) if max_radius is not None else None,
            )
        else:
            direction = mapping_params.get("direction", [1.0, 0.0, 0.0])
            origin = mapping_params.get("origin")
            origin_tuple = (
                (float(origin[0]), float(origin[1]), float(origin[2])) if origin else None
            )
            mapping = LinearMapping(
                direction=(float(direction[0]), float(direction[1]), float(direction[2])),
                origin=origin_tuple,
            )

    new_compositor = SpatialCompositor(scene, mapping)
    scheduler.compositor = new_compositor
    request.app.state.compositor = new_compositor


@router.get("", response_model=SceneResponse)
async def get_scene(request: Request) -> SceneResponse:
    scene = _get_scene(request)
    if scene is None or not scene.placements:
        return SceneResponse(placements=[], mapping=None, bounds=None)

    placements = [_placement_to_response(p) for p in scene.placements.values()]
    bounds_min, bounds_max = scene.get_bounds()

    # Derive mapping info from config
    mapping_resp = None
    config = request.app.state.config
    if config.scene_config is not None:
        mapping_name = config.scene_config.get("mapping", "linear")
        mapping_params = config.scene_config.get("mapping_params", {})
        mapping_resp = MappingResponse(type=mapping_name, params=mapping_params)

    return SceneResponse(
        placements=placements,
        mapping=mapping_resp,
        bounds=[bounds_min.tolist(), bounds_max.tolist()],
    )


@router.get("/devices", response_model=list[PlacementResponse])
async def get_scene_devices(request: Request) -> list[PlacementResponse]:
    scene = _get_scene(request)
    if scene is None:
        return []
    return [_placement_to_response(p) for p in scene.placements.values()]


@router.put("/devices/{device_name}", response_model=PlacementResponse)
async def update_scene_device(
    request: Request, device_name: str, body: UpdatePlacementRequest
) -> PlacementResponse:
    """Add or update a device placement (spec: 'Add/update device placement')."""
    scene = _get_scene(request)
    if scene is None:
        raise HTTPException(status_code=404, detail="No scene configured")

    # Resolve geometry from request
    geometry = None
    if body.geometry == "point":
        geometry = PointGeometry()
    elif body.geometry == "strip":
        direction = tuple(body.direction) if body.direction else (1.0, 0.0, 0.0)
        length = body.length if body.length is not None else 1.0
        geometry = StripGeometry(direction=direction, length=length)

    if device_name in scene.placements:
        # Update existing placement
        position = tuple(body.position) if body.position is not None else None
        scene.update_placement(device_name, position=position, geometry=geometry)
    else:
        # Add new placement — position and led_count are required
        if body.position is None:
            raise HTTPException(status_code=400, detail="position is required when adding a new device")
        from dj_ledfx.spatial.scene import DevicePlacement
        led_count = body.led_count or 1
        scene.add_placement(DevicePlacement(
            device_id=device_name,
            position=tuple(body.position),
            geometry=geometry or PointGeometry(),
            led_count=led_count,
        ))

    _rebuild_compositor(request, scene)
    return _placement_to_response(scene.placements[device_name])


@router.delete("/devices/{device_name}")
async def delete_scene_device(request: Request, device_name: str) -> dict:
    scene = _get_scene(request)
    if scene is None:
        raise HTTPException(status_code=404, detail="No scene configured")
    if device_name not in scene.placements:
        raise HTTPException(status_code=404, detail=f"Device '{device_name}' not in scene")
    scene.remove_placement(device_name)
    _rebuild_compositor(request, scene)
    return {"removed": device_name}


@router.put("/mapping", response_model=MappingResponse)
async def update_mapping(request: Request, body: UpdateMappingRequest) -> MappingResponse:
    scene = _get_scene(request)
    if scene is None:
        raise HTTPException(status_code=404, detail="No scene configured")

    # Update config's scene mapping
    config = request.app.state.config
    if config.scene_config is None:
        config.scene_config = {}
    config.scene_config["mapping"] = body.type
    config.scene_config["mapping_params"] = body.params

    # Rebuild compositor with new mapping
    _rebuild_compositor(request, scene)

    return MappingResponse(type=body.type, params=body.params)
```

- [ ] **Step 4: Do NOT commit yet** — tests will fail until the router is registered in app.py (next steps)

### Task 6: Register scene router in app.py, type scene_model properly, and commit

**Files:**
- Modify: `src/dj_ledfx/web/app.py`

- [ ] **Step 1: Add scene router import and registration**

In `src/dj_ledfx/web/app.py`, in the `create_app()` function, add:

After the existing router imports (around line 81):
```python
from dj_ledfx.web.router_scene import router as scene_router
```

After the existing `app.include_router(config_router, prefix="/api")` line:
```python
app.include_router(scene_router, prefix="/api")
```

Also update the `scene_model` and `compositor` type annotations in the function signature from `object | None` to their real types:

```python
scene_model: SceneModel | None,
compositor: SpatialCompositor | None,
```

Add to the `TYPE_CHECKING` imports at the top:
```python
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.scene import SceneModel
```

- [ ] **Step 2: Run scene router tests**

Run: `uv run pytest tests/web/test_router_scene.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -x -v`
Expected: ALL PASS

- [ ] **Step 4: Run lint and type check**

Run: `uv run ruff check src/dj_ledfx/web/ && uv run ruff format src/dj_ledfx/web/`

- [ ] **Step 5: Commit (includes router + tests + app.py wiring from Tasks 5-6)**

```bash
git add src/dj_ledfx/web/router_scene.py src/dj_ledfx/web/app.py tests/web/test_router_scene.py tests/web/__init__.py
git commit -m "feat(web): add Scene REST router with placement CRUD, mapping update, and integration tests"
```

---

## Chunk 3: Frontend — Types, API Client, Hook

### Task 7: Add scene types to types.ts

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Add scene types**

Append to `frontend/src/lib/types.ts`:

```typescript
// Scene types

export interface GeometryInfo {
  type: "point" | "strip" | "matrix"
  direction?: number[] // strip only
  length?: number // strip only
  pixel_pitch?: number // matrix only
  tiles?: { offset_x: number; offset_y: number; width: number; height: number }[] // matrix only
}

export interface Placement {
  device_id: string
  position: [number, number, number]
  geometry: GeometryInfo
  led_count: number
}

export interface MappingInfo {
  type: "linear" | "radial"
  params: Record<string, unknown>
}

export interface SceneData {
  placements: Placement[]
  mapping: MappingInfo | null
  bounds: [[number, number, number], [number, number, number]] | null
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat(frontend): add scene/placement/geometry TypeScript types"
```

### Task 8: Add scene REST functions to api-client.ts

**Files:**
- Modify: `frontend/src/lib/api-client.ts`

- [ ] **Step 1: Add scene API functions**

Add the import for the new types at the top of `frontend/src/lib/api-client.ts`:

```typescript
import type {
  // ... existing imports ...
  MappingInfo,
  Placement,
  SceneData,
} from "./types"
```

Append the scene functions:

```typescript
// Scene
export async function getScene(): Promise<SceneData> {
  return fetchJson("/scene")
}

export async function getSceneDevices(): Promise<Placement[]> {
  return fetchJson("/scene/devices")
}

export async function updateSceneDevice(
  deviceName: string,
  update: { position?: number[]; geometry?: string; direction?: number[]; length?: number }
): Promise<Placement> {
  return fetchJson(`/scene/devices/${encodeURIComponent(deviceName)}`, {
    method: "PUT",
    body: JSON.stringify(update),
  })
}

export async function deleteSceneDevice(deviceName: string): Promise<void> {
  await fetchJson(`/scene/devices/${encodeURIComponent(deviceName)}`, {
    method: "DELETE",
  })
}

export async function updateSceneMapping(
  type: string,
  params: Record<string, unknown>
): Promise<MappingInfo> {
  return fetchJson("/scene/mapping", {
    method: "PUT",
    body: JSON.stringify({ type, params }),
  })
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api-client.ts
git commit -m "feat(frontend): add scene REST API functions"
```

### Task 9: Create use-scene.ts hook

**Files:**
- Create: `frontend/src/hooks/use-scene.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/use-scene.ts`:

```typescript
import { useState, useEffect, useCallback } from "react"
import type { Placement, SceneData, MappingInfo } from "@/lib/types"
import {
  getScene,
  updateSceneDevice,
  deleteSceneDevice,
  updateSceneMapping,
} from "@/lib/api-client"

export function useScene() {
  const [scene, setScene] = useState<SceneData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await getScene()
      setScene(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scene")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const movePlacement = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      try {
        await updateSceneDevice(deviceId, { position })
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update placement")
      }
    },
    [refresh]
  )

  const removePlacement = useCallback(
    async (deviceId: string) => {
      try {
        await deleteSceneDevice(deviceId)
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to remove placement")
      }
    },
    [refresh]
  )

  const changeMapping = useCallback(
    async (type: string, params: Record<string, unknown>) => {
      try {
        await updateSceneMapping(type, params)
        await refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update mapping")
      }
    },
    [refresh]
  )

  return {
    scene,
    loading,
    error,
    refresh,
    movePlacement,
    removePlacement,
    changeMapping,
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-scene.ts
git commit -m "feat(frontend): add use-scene hook for scene state management"
```

---

## Chunk 4: Frontend — R3F Setup & Device Rendering

### Task 10: Install React Three Fiber dependencies

**Files:**
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install R3F packages**

```bash
cd frontend && npm install three @react-three/fiber @react-three/drei
```

- [ ] **Step 2: Install Three.js types**

```bash
cd frontend && npm install -D @types/three
```

- [ ] **Step 3: Verify build works**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "build(frontend): add React Three Fiber, drei, and three.js"
```

### Task 11: Create SceneViewport component

**Files:**
- Create: `frontend/src/components/scene/scene-viewport.tsx`

- [ ] **Step 1: Create the viewport component**

Create directory: `frontend/src/components/scene/`

Create `frontend/src/components/scene/scene-viewport.tsx`:

```tsx
import { Canvas } from "@react-three/fiber"
import { OrbitControls, Grid, GizmoHelper, GizmoViewport, Environment } from "@react-three/drei"
import { type ReactNode, Suspense } from "react"

interface SceneViewportProps {
  children?: ReactNode
  onPointerMissed?: () => void
}

function SceneContent({ children, onPointerMissed }: SceneViewportProps) {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[10, 10, 5]} intensity={0.8} />
      <Grid
        args={[20, 20]}
        cellSize={0.5}
        cellThickness={0.5}
        cellColor="#404040"
        sectionSize={2}
        sectionThickness={1}
        sectionColor="#606060"
        fadeDistance={30}
        infiniteGrid
      />
      <OrbitControls makeDefault />
      <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
        <GizmoViewport axisColors={["#f44", "#4f4", "#44f"]} labelColor="white" />
      </GizmoHelper>
      {children}
    </>
  )
}

export default function SceneViewport({ children, onPointerMissed }: SceneViewportProps) {
  return (
    <Canvas
      camera={{ position: [5, 5, 5], fov: 60 }}
      onPointerMissed={onPointerMissed}
      className="rounded-lg"
      style={{ background: "hsl(var(--background))" }}
    >
      <Suspense fallback={null}>
        <SceneContent onPointerMissed={onPointerMissed}>
          {children}
        </SceneContent>
      </Suspense>
    </Canvas>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/scene/scene-viewport.tsx
git commit -m "feat(frontend): add SceneViewport with R3F Canvas, grid, orbit controls"
```

### Task 12: Create DeviceMesh component

This component renders a device as geometry-appropriate 3D meshes with live LED colors.

**Files:**
- Create: `frontend/src/components/scene/device-mesh.tsx`

- [ ] **Step 1: Create the device mesh component**

Create `frontend/src/components/scene/device-mesh.tsx`:

```tsx
import { useRef, useMemo } from "react"
import * as THREE from "three"
import { type ThreeEvent } from "@react-three/fiber"
import type { GeometryInfo, FrameData } from "@/lib/types"

interface DeviceMeshProps {
  deviceId: string
  position: [number, number, number]
  geometry: GeometryInfo
  ledCount: number
  frameData?: FrameData | null
  selected?: boolean
  onClick?: (e: ThreeEvent<MouseEvent>) => void
  onPointerOver?: (e: ThreeEvent<PointerEvent>) => void
  onPointerOut?: (e: ThreeEvent<PointerEvent>) => void
}

/** Convert RGB byte at index to THREE.Color */
function rgbAt(rgb: Uint8Array | undefined, index: number): THREE.Color {
  if (!rgb || index * 3 + 2 >= rgb.length) return new THREE.Color(0.3, 0.3, 0.3)
  const r = rgb[index * 3] / 255
  const g = rgb[index * 3 + 1] / 255
  const b = rgb[index * 3 + 2] / 255
  return new THREE.Color(r, g, b)
}

const SPHERE_RADIUS = 0.04
const SELECTED_EMISSIVE = new THREE.Color(0.15, 0.15, 0.3)
const DEFAULT_EMISSIVE = new THREE.Color(0, 0, 0)

function PointDevice({ rgb, selected }: { rgb?: Uint8Array; selected?: boolean }) {
  const color = useMemo(() => rgbAt(rgb, 0), [rgb])
  return (
    <mesh>
      <sphereGeometry args={[SPHERE_RADIUS * 3, 16, 16]} />
      <meshStandardMaterial
        color={color}
        emissive={selected ? SELECTED_EMISSIVE : DEFAULT_EMISSIVE}
        roughness={0.4}
      />
    </mesh>
  )
}

function StripDevice({
  geometry,
  ledCount,
  rgb,
  selected,
}: {
  geometry: GeometryInfo
  ledCount: number
  rgb?: Uint8Array
  selected?: boolean
}) {
  const direction = geometry.direction ?? [1, 0, 0]
  const length = geometry.length ?? 1.0
  const dir = useMemo(() => new THREE.Vector3(...direction).normalize(), [direction])

  const positions = useMemo(() => {
    const pts: [number, number, number][] = []
    for (let i = 0; i < ledCount; i++) {
      const t = ledCount > 1 ? (i + 0.5) / ledCount : 0.5
      pts.push([dir.x * length * t, dir.y * length * t, dir.z * length * t])
    }
    return pts
  }, [dir, length, ledCount])

  return (
    <group>
      {positions.map((pos, i) => {
        const color = rgbAt(rgb, i)
        return (
          <mesh key={i} position={pos}>
            <sphereGeometry args={[SPHERE_RADIUS, 8, 8]} />
            <meshStandardMaterial
              color={color}
              emissive={selected ? SELECTED_EMISSIVE : DEFAULT_EMISSIVE}
              roughness={0.4}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function MatrixDevice({
  geometry,
  ledCount,
  rgb,
  selected,
}: {
  geometry: GeometryInfo
  ledCount: number
  rgb?: Uint8Array
  selected?: boolean
}) {
  const pitch = geometry.pixel_pitch ?? 0.03

  const positions = useMemo(() => {
    const pts: [number, number, number][] = []
    if (geometry.tiles) {
      for (const tile of geometry.tiles) {
        for (let row = 0; row < tile.height; row++) {
          for (let col = 0; col < tile.width; col++) {
            pts.push([
              tile.offset_x + col * pitch,
              tile.offset_y + row * pitch,
              0,
            ])
          }
        }
      }
    } else {
      // Fallback: square grid
      const side = Math.ceil(Math.sqrt(ledCount))
      for (let i = 0; i < ledCount; i++) {
        pts.push([(i % side) * pitch, Math.floor(i / side) * pitch, 0])
      }
    }
    return pts
  }, [geometry.tiles, ledCount, pitch])

  return (
    <group>
      {positions.map((pos, i) => {
        const color = rgbAt(rgb, i)
        return (
          <mesh key={i} position={pos}>
            <sphereGeometry args={[SPHERE_RADIUS * 0.8, 6, 6]} />
            <meshStandardMaterial
              color={color}
              emissive={selected ? SELECTED_EMISSIVE : DEFAULT_EMISSIVE}
              roughness={0.4}
            />
          </mesh>
        )
      })}
    </group>
  )
}

export default function DeviceMesh({
  deviceId,
  position,
  geometry,
  ledCount,
  frameData,
  selected,
  onClick,
  onPointerOver,
  onPointerOut,
}: DeviceMeshProps) {
  const groupRef = useRef<THREE.Group>(null!)
  const rgb = frameData?.rgb

  return (
    <group
      ref={groupRef}
      position={position}
      onClick={onClick}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
    >
      {geometry.type === "point" && <PointDevice rgb={rgb} selected={selected} />}
      {geometry.type === "strip" && (
        <StripDevice geometry={geometry} ledCount={ledCount} rgb={rgb} selected={selected} />
      )}
      {geometry.type === "matrix" && (
        <MatrixDevice geometry={geometry} ledCount={ledCount} rgb={rgb} selected={selected} />
      )}
    </group>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/scene/device-mesh.tsx
git commit -m "feat(frontend): add DeviceMesh component with Point/Strip/Matrix rendering"
```

---

## Chunk 5: Frontend — Scene Editor Layout

### Task 13: Create DeviceListPanel component

**Files:**
- Create: `frontend/src/components/scene/device-list-panel.tsx`

- [ ] **Step 1: Create the device list panel**

Create `frontend/src/components/scene/device-list-panel.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { Placement, Device } from "@/lib/types"

interface DeviceListPanelProps {
  placements: Placement[]
  allDevices: Device[]
  selectedDeviceId: string | null
  onSelectDevice: (deviceId: string) => void
}

export default function DeviceListPanel({
  placements,
  allDevices,
  selectedDeviceId,
  onSelectDevice,
}: DeviceListPanelProps) {
  const placedIds = new Set(placements.map((p) => p.device_id))
  const unplacedDevices = allDevices.filter((d) => !placedIds.has(d.name))

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Devices</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        <ScrollArea className="h-full px-3 pb-3">
          {/* Placed devices */}
          {placements.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-muted-foreground font-medium mb-1.5 px-1">
                In Scene
              </p>
              {placements.map((p) => (
                <button
                  key={p.device_id}
                  onClick={() => onSelectDevice(p.device_id)}
                  className={cn(
                    "w-full text-left px-2 py-1.5 rounded text-sm transition-colors",
                    selectedDeviceId === p.device_id
                      ? "bg-primary/15 text-primary"
                      : "hover:bg-muted"
                  )}
                >
                  <span className="flex items-center justify-between">
                    <span className="truncate">{p.device_id}</span>
                    <Badge variant="outline" className="text-[10px] ml-1 shrink-0">
                      {p.geometry.type}
                    </Badge>
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Unplaced devices */}
          {unplacedDevices.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1.5 px-1">
                Unplaced
              </p>
              {unplacedDevices.map((d) => (
                <div
                  key={d.name}
                  className="px-2 py-1.5 text-sm text-muted-foreground flex items-center justify-between"
                >
                  <span className="truncate">{d.name}</span>
                  <Badge variant="outline" className="text-[10px] ml-1 shrink-0 opacity-50">
                    {d.device_type}
                  </Badge>
                </div>
              ))}
            </div>
          )}

          {placements.length === 0 && unplacedDevices.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">
              No devices found
            </p>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/scene/device-list-panel.tsx
git commit -m "feat(frontend): add DeviceListPanel with placed/unplaced grouping"
```

### Task 14: Create PropertiesPanel component

**Files:**
- Create: `frontend/src/components/scene/properties-panel.tsx`

- [ ] **Step 1: Create the properties panel**

Create `frontend/src/components/scene/properties-panel.tsx`:

```tsx
import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { Placement } from "@/lib/types"
import { identifyDevice } from "@/lib/api-client"
import { toast } from "sonner"

interface PropertiesPanelProps {
  placement: Placement | null
  onPositionChange: (deviceId: string, position: [number, number, number]) => void
  onRemove: (deviceId: string) => void
}

export default function PropertiesPanel({
  placement,
  onPositionChange,
  onRemove,
}: PropertiesPanelProps) {
  const [pos, setPos] = useState<[string, string, string]>(["0", "0", "0"])

  useEffect(() => {
    if (placement) {
      setPos([
        placement.position[0].toFixed(2),
        placement.position[1].toFixed(2),
        placement.position[2].toFixed(2),
      ])
    }
  }, [placement])

  if (!placement) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full">
          <p className="text-sm text-muted-foreground">Select a device</p>
        </CardContent>
      </Card>
    )
  }

  const commitPosition = () => {
    const parsed: [number, number, number] = [
      parseFloat(pos[0]) || 0,
      parseFloat(pos[1]) || 0,
      parseFloat(pos[2]) || 0,
    ]
    onPositionChange(placement.device_id, parsed)
  }

  const handleIdentify = async () => {
    try {
      await identifyDevice(placement.device_id)
      toast.success(`Identifying ${placement.device_id}`)
    } catch {
      toast.error("Failed to identify device")
    }
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">{placement.device_id}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 flex-1">
        {/* Geometry info */}
        <div>
          <Label className="text-xs text-muted-foreground">Geometry</Label>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">{placement.geometry.type}</Badge>
            <span className="text-xs text-muted-foreground">
              {placement.led_count} LEDs
            </span>
          </div>
        </div>

        {/* Position */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">Position (meters)</Label>
          {(["X", "Y", "Z"] as const).map((axis, i) => (
            <div key={axis} className="flex items-center gap-2">
              <Label className="text-xs w-4 text-center">{axis}</Label>
              <Input
                type="number"
                step="0.1"
                value={pos[i]}
                onChange={(e) => {
                  const next = [...pos] as [string, string, string]
                  next[i] = e.target.value
                  setPos(next)
                }}
                onBlur={commitPosition}
                onKeyDown={(e) => e.key === "Enter" && commitPosition()}
                className="h-7 text-xs"
              />
            </div>
          ))}
        </div>

        {/* Strip-specific info */}
        {placement.geometry.type === "strip" && placement.geometry.direction && (
          <div>
            <Label className="text-xs text-muted-foreground">Direction</Label>
            <p className="text-xs mt-1">
              [{placement.geometry.direction.map((v) => v.toFixed(1)).join(", ")}]
            </p>
            {placement.geometry.length && (
              <>
                <Label className="text-xs text-muted-foreground mt-2 block">Length</Label>
                <p className="text-xs mt-1">{placement.geometry.length.toFixed(2)}m</p>
              </>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={handleIdentify}>
            Identify
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={() => onRemove(placement.device_id)}
          >
            Remove from Scene
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
```

Note: If `Button` is not already installed as a shadcn component, add it first:
```bash
cd frontend && npx shadcn add button
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors (may need to install `button` component first)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/scene/properties-panel.tsx
git commit -m "feat(frontend): add PropertiesPanel with position editing and identify"
```

### Task 15: Create SceneToolbar component

**Files:**
- Create: `frontend/src/components/scene/scene-toolbar.tsx`

- [ ] **Step 1: Create the toolbar**

Create `frontend/src/components/scene/scene-toolbar.tsx`:

```tsx
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

interface SceneToolbarProps {
  transformMode: "translate" | "rotate"
  onTransformModeChange: (mode: "translate" | "rotate") => void
  mappingType: string
  onMappingTypeChange: (type: string) => void
}

export default function SceneToolbar({
  transformMode,
  onTransformModeChange,
  mappingType,
  onMappingTypeChange,
}: SceneToolbarProps) {
  return (
    <div className="flex items-center gap-3 px-3 py-1.5 border-b border-border">
      {/* Transform mode */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Tool</span>
        <ToggleGroup
          type="single"
          value={transformMode}
          onValueChange={(v) => {
            if (v === "translate" || v === "rotate") onTransformModeChange(v)
          }}
        >
          <ToggleGroupItem value="translate" className="text-xs h-7 px-2">
            Move
          </ToggleGroupItem>
          <ToggleGroupItem value="rotate" className="text-xs h-7 px-2">
            Rotate
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div className="w-px h-5 bg-border" />

      {/* Mapping type */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Mapping</span>
        <Select value={mappingType} onValueChange={onMappingTypeChange}>
          <SelectTrigger className="h-7 w-24 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="linear">Linear</SelectItem>
            <SelectItem value="radial">Radial</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/scene/scene-toolbar.tsx
git commit -m "feat(frontend): add SceneToolbar with transform mode and mapping selector"
```

### Task 16: Wire up scene.tsx as full editor

**Files:**
- Modify: `frontend/src/pages/scene.tsx`

- [ ] **Step 1: Replace placeholder with full scene editor**

Replace the entire content of `frontend/src/pages/scene.tsx`:

```tsx
import { useState, useCallback } from "react"
import { toast } from "sonner"
import { useScene } from "@/hooks/use-scene"
import { useDevices } from "@/hooks/use-devices"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"
import DeviceListPanel from "@/components/scene/device-list-panel"
import PropertiesPanel from "@/components/scene/properties-panel"
import SceneToolbar from "@/components/scene/scene-toolbar"
import type { Placement, FrameData } from "@/lib/types"

export default function ScenePage() {
  const { scene, loading, movePlacement, removePlacement, changeMapping, refresh } = useScene()
  const { devices, frameData } = useDevices()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [transformMode, setTransformMode] = useState<"translate" | "rotate">("translate")

  const selectedPlacement: Placement | null =
    scene?.placements.find((p) => p.device_id === selectedId) ?? null

  const handlePositionChange = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      await movePlacement(deviceId, position)
      toast.success(`Moved ${deviceId}`)
    },
    [movePlacement]
  )

  const handleRemove = useCallback(
    async (deviceId: string) => {
      await removePlacement(deviceId)
      setSelectedId(null)
      toast.success(`Removed ${deviceId}`)
    },
    [removePlacement]
  )

  const handleMappingChange = useCallback(
    async (type: string) => {
      await changeMapping(type, {})
      toast.success(`Mapping set to ${type}`)
    },
    [changeMapping]
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Loading scene...</p>
      </div>
    )
  }

  const placements = scene?.placements ?? []
  const mappingType = scene?.mapping?.type ?? "linear"

  return (
    <div className="flex flex-col h-full gap-0">
      {/* Toolbar */}
      <SceneToolbar
        transformMode={transformMode}
        onTransformModeChange={setTransformMode}
        mappingType={mappingType}
        onMappingTypeChange={handleMappingChange}
      />

      {/* Main 3-panel layout */}
      <div className="flex-1 flex gap-2 min-h-0 p-2">
        {/* Left: Device list */}
        <div className="w-52 shrink-0">
          <DeviceListPanel
            placements={placements}
            allDevices={devices}
            selectedDeviceId={selectedId}
            onSelectDevice={setSelectedId}
          />
        </div>

        {/* Center: 3D viewport */}
        <div className="flex-1 min-w-0 rounded-lg border border-border overflow-hidden">
          <SceneViewport onPointerMissed={() => setSelectedId(null)}>
            {placements.map((p) => (
              <DeviceMesh
                key={p.device_id}
                deviceId={p.device_id}
                position={p.position}
                geometry={p.geometry}
                ledCount={p.led_count}
                frameData={frameData.get(p.device_id) ?? null}
                selected={selectedId === p.device_id}
                onClick={(e) => {
                  e.stopPropagation()
                  setSelectedId(p.device_id)
                }}
              />
            ))}
          </SceneViewport>
        </div>

        {/* Right: Properties */}
        <div className="w-56 shrink-0">
          <PropertiesPanel
            placement={selectedPlacement}
            onPositionChange={handlePositionChange}
            onRemove={handleRemove}
          />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Check that useDevices exposes frameData**

The `useDevices` hook should return `frameData: Map<string, FrameData>`. Check `frontend/src/hooks/use-devices.ts` — the return value should include `frameData`. If it uses a different structure, adjust the `scene.tsx` code to match (e.g., `frameData.get(p.device_id)`).

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Verify dev build works**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/scene.tsx
git commit -m "feat(frontend): replace Scene placeholder with full 3D scene editor"
```

---

## Chunk 6: Frontend — Interactions & Mapping Preview

### Task 17: Add TransformControls for drag-to-reposition

**Files:**
- Modify: `frontend/src/components/scene/scene-viewport.tsx`
- Modify: `frontend/src/pages/scene.tsx`

- [ ] **Step 1: Add TransformControls to SceneViewport**

Update `frontend/src/components/scene/scene-viewport.tsx` to accept and forward a `transformTarget` ref and mode:

Add to imports:
```tsx
import { TransformControls } from "@react-three/drei"
import { useRef, forwardRef, useImperativeHandle } from "react"
import * as THREE from "three"
```

Add to `SceneViewportProps`:
```tsx
interface SceneViewportProps {
  children?: ReactNode
  onPointerMissed?: () => void
  transformTarget?: THREE.Object3D | null
  transformMode?: "translate" | "rotate"
  onTransformEnd?: (position: [number, number, number]) => void
}
```

Inside `SceneContent`, after `<OrbitControls makeDefault />`, add:
```tsx
{transformTarget && (
  <TransformControls
    object={transformTarget}
    mode={transformMode ?? "translate"}
    onMouseUp={() => {
      if (transformTarget && onTransformEnd) {
        const pos = transformTarget.position
        onTransformEnd([pos.x, pos.y, pos.z])
      }
    }}
  />
)}
```

- [ ] **Step 2: Update DeviceMesh to expose its group ref**

In `frontend/src/components/scene/device-mesh.tsx`, update to use `forwardRef` so the parent can get a ref to the `<group>`:

```tsx
import { forwardRef } from "react"

const DeviceMesh = forwardRef<THREE.Group, DeviceMeshProps>(function DeviceMesh(
  { deviceId, position, geometry, ledCount, frameData, selected, onClick, onPointerOver, onPointerOut },
  ref
) {
  const rgb = frameData?.rgb

  return (
    <group
      ref={ref}
      position={position}
      onClick={onClick}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
    >
      {/* ... same render logic ... */}
    </group>
  )
})

export default DeviceMesh
```

- [ ] **Step 3: Update scene.tsx to track selected device ref for TransformControls**

In `frontend/src/pages/scene.tsx`, add ref tracking:

```tsx
import { useRef, useCallback } from "react"
import * as THREE from "three"

// Inside ScenePage:
const deviceRefs = useRef<Map<string, THREE.Group>>(new Map())
const transformTarget = selectedId ? deviceRefs.current.get(selectedId) ?? null : null

const handleTransformEnd = useCallback(
  async (position: [number, number, number]) => {
    if (selectedId) {
      await movePlacement(selectedId, position)
    }
  },
  [selectedId, movePlacement]
)
```

Update the `<SceneViewport>` to pass transform props:
```tsx
<SceneViewport
  onPointerMissed={() => setSelectedId(null)}
  transformTarget={transformTarget}
  transformMode={transformMode}
  onTransformEnd={handleTransformEnd}
>
```

Update `<DeviceMesh>` to store ref:
```tsx
<DeviceMesh
  ref={(el) => {
    if (el) deviceRefs.current.set(p.device_id, el)
    else deviceRefs.current.delete(p.device_id)
  }}
  // ... other props
/>
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/scene/scene-viewport.tsx frontend/src/components/scene/device-mesh.tsx frontend/src/pages/scene.tsx
git commit -m "feat(frontend): add TransformControls for drag-to-reposition devices in 3D"
```

### Task 18: Create MappingPreview component

The bottom bar showing a 1D gradient of the effect→spatial mapping result with device position markers.

**Files:**
- Create: `frontend/src/components/scene/mapping-preview.tsx`
- Modify: `frontend/src/pages/scene.tsx` (add to layout)

- [ ] **Step 1: Create the mapping preview**

Create `frontend/src/components/scene/mapping-preview.tsx`:

```tsx
import { useMemo } from "react"
import type { Placement, FrameData } from "@/lib/types"
import { cn } from "@/lib/utils"

interface MappingPreviewProps {
  placements: Placement[]
  frameData: Map<string, FrameData>
  selectedDeviceId: string | null
  onSelectDevice: (deviceId: string) => void
}

/**
 * Renders a 1D gradient bar showing the effect strip with device position markers.
 * The bar represents the [0, 1] mapping range. Each device marker is positioned
 * based on its average spatial position projected to the mapping direction.
 */
export default function MappingPreview({
  placements,
  frameData,
  selectedDeviceId,
  onSelectDevice,
}: MappingPreviewProps) {
  // Compute normalized X positions for each device (simplified: use x / max_x)
  const devicePositions = useMemo(() => {
    if (placements.length === 0) return []
    const xs = placements.map((p) => p.position[0])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const span = maxX - minX
    return placements.map((p) => ({
      deviceId: p.device_id,
      normalized: span > 0.001 ? (p.position[0] - minX) / span : 0.5,
    }))
  }, [placements])

  if (placements.length === 0) return null

  return (
    <div className="h-10 border-t border-border px-3 py-1.5 flex items-center gap-2">
      <span className="text-[10px] text-muted-foreground shrink-0">Mapping</span>
      <div className="relative flex-1 h-5 rounded bg-muted overflow-hidden">
        {/* Gradient bar — show first device's frame as a sampled color bar */}
        <GradientBar frameData={frameData} placements={placements} />

        {/* Device position markers */}
        {devicePositions.map(({ deviceId, normalized }) => (
          <button
            key={deviceId}
            onClick={() => onSelectDevice(deviceId)}
            className={cn(
              "absolute top-0 h-full w-1 -translate-x-1/2 transition-colors",
              selectedDeviceId === deviceId
                ? "bg-primary"
                : "bg-foreground/50 hover:bg-foreground/80"
            )}
            style={{ left: `${normalized * 100}%` }}
            title={deviceId}
          />
        ))}
      </div>
    </div>
  )
}

function GradientBar({
  frameData,
  placements,
}: {
  frameData: Map<string, FrameData>
  placements: Placement[]
}) {
  // Sample colors from the first device's frame data to visualize the effect strip
  const gradient = useMemo(() => {
    // Find any device with frame data
    for (const p of placements) {
      const frame = frameData.get(p.device_id)
      if (!frame?.rgb || frame.rgb.length < 3) continue

      const ledCount = frame.rgb.length / 3
      const samples = Math.min(ledCount, 32)
      const stops: string[] = []
      for (let i = 0; i < samples; i++) {
        const idx = Math.floor((i / samples) * ledCount)
        const r = frame.rgb[idx * 3]
        const g = frame.rgb[idx * 3 + 1]
        const b = frame.rgb[idx * 3 + 2]
        const pct = (i / (samples - 1)) * 100
        stops.push(`rgb(${r},${g},${b}) ${pct.toFixed(1)}%`)
      }
      return `linear-gradient(to right, ${stops.join(", ")})`
    }
    return "linear-gradient(to right, hsl(var(--muted)), hsl(var(--muted)))"
  }, [frameData, placements])

  return (
    <div className="absolute inset-0" style={{ background: gradient }} />
  )
}
```

- [ ] **Step 2: Add MappingPreview to scene.tsx**

In `frontend/src/pages/scene.tsx`, import and add at the bottom of the layout (after the 3-panel `div`, inside the outer flex-col `div`):

```tsx
import MappingPreview from "@/components/scene/mapping-preview"

// Inside the return, after the 3-panel layout div:
<MappingPreview
  placements={placements}
  frameData={frameData}
  selectedDeviceId={selectedId}
  onSelectDevice={setSelectedId}
/>
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Verify production build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/scene/mapping-preview.tsx frontend/src/pages/scene.tsx
git commit -m "feat(frontend): add MappingPreview bar with effect gradient and device markers"
```

### Task 19: Final integration verification

- [ ] **Step 1: Run full backend test suite**

Run: `uv run pytest -x -v`
Expected: ALL PASS

- [ ] **Step 2: Run lint and format**

Run: `uv run ruff check . && uv run ruff format .`

- [ ] **Step 3: Run TypeScript type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Run frontend production build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Manual smoke test**

Run: `uv run -m dj_ledfx --demo --web dev`
Open http://localhost:5173, navigate to Scene tab. Verify:
- 3D viewport renders with grid and gizmo
- Placed devices appear (if scene config exists in config.toml)
- Orbit controls work (click-drag to rotate, scroll to zoom)
- Device list shows placed/unplaced devices

- [ ] **Step 6: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fix: address integration issues from smoke test"
```
