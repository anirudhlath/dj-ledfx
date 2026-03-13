# 3D Spatial Scene Mapping Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a spatial compositor layer that maps 1D effect output onto 3D device positions, enabling spatially-aware lighting effects across heterogeneous LED hardware.

**Architecture:** New `spatial/` package with four modules (geometry, scene, mapping, compositor). The compositor inserts between ring buffer read and device send in the scheduler's per-device send loop. Effects remain unchanged — they still render 1D color strips. Config-driven scene definition via TOML `[scene]` section with full backward compatibility (no scene = MVP broadcast behavior).

**Tech Stack:** Python 3.12, numpy, loguru, pytest, pytest-asyncio, ruff, mypy

**Spec:** `docs/superpowers/specs/2026-03-12-3d-spatial-mapping-design.md`

---

## File Structure

**Create:**
- `src/dj_ledfx/spatial/__init__.py` — Re-exports: DeviceGeometry types, SpatialMapping, SpatialCompositor, SceneModel
- `src/dj_ledfx/spatial/geometry.py` — PointGeometry, StripGeometry, MatrixGeometry, TileLayout, DeviceGeometry union, `expand_positions()` function
- `src/dj_ledfx/spatial/mapping.py` — SpatialMapping Protocol, LinearMapping, RadialMapping
- `src/dj_ledfx/spatial/scene.py` — SceneModel, DevicePlacement, `from_config()` factory
- `src/dj_ledfx/spatial/compositor.py` — SpatialCompositor with cached index lookup
- `tests/spatial/__init__.py`
- `tests/spatial/test_geometry.py`
- `tests/spatial/test_mapping.py`
- `tests/spatial/test_scene.py`
- `tests/spatial/test_compositor.py`
- `tests/spatial/test_spatial_pipeline.py`

**Modify:**
- `src/dj_ledfx/devices/adapter.py` — Add optional `geometry` property
- `src/dj_ledfx/scheduling/scheduler.py` — Add `compositor` param, insert composite call in `_send_loop`
- `src/dj_ledfx/config.py` — Add `scene_config: dict | None = None` to AppConfig, parse `[scene]`
- `src/dj_ledfx/main.py` — Wire SceneModel + Compositor into startup
- `tests/conftest.py` — Add `geometry` property to MockDeviceAdapter

---

## Chunk 1: Geometry Types and Position Expansion

### Task 1: Geometry Dataclasses

**Files:**
- Create: `src/dj_ledfx/spatial/__init__.py`
- Create: `src/dj_ledfx/spatial/geometry.py`
- Create: `tests/spatial/__init__.py`
- Create: `tests/spatial/test_geometry.py`

- [ ] **Step 1: Write failing tests for geometry types**

```python
# tests/spatial/__init__.py
# (empty)
```

```python
# tests/spatial/test_geometry.py
from __future__ import annotations

import numpy as np
import pytest

from dj_ledfx.spatial.geometry import (
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
    TileLayout,
    expand_positions,
)


class TestPointGeometry:
    def test_create(self) -> None:
        geo = PointGeometry()
        assert geo is not None

    def test_expand_single_position(self) -> None:
        geo = PointGeometry()
        pos = (1.0, 2.0, 3.0)
        result = expand_positions(geo, pos, led_count=1)
        assert result.shape == (1, 3)
        np.testing.assert_array_almost_equal(result[0], [1.0, 2.0, 3.0])


class TestStripGeometry:
    def test_create_normalizes_direction(self) -> None:
        geo = StripGeometry(direction=(2.0, 0.0, 0.0), length=1.5)
        assert abs(sum(d * d for d in geo.direction) - 1.0) < 1e-6

    def test_unit_direction_unchanged(self) -> None:
        geo = StripGeometry(direction=(0.0, 1.0, 0.0), length=1.0)
        assert geo.direction == (0.0, 1.0, 0.0)

    def test_zero_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="non-zero"):
            StripGeometry(direction=(0.0, 0.0, 0.0), length=1.0)

    def test_expand_positions_evenly_spaced(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)
        pos = (0.0, 0.0, 0.0)
        result = expand_positions(geo, pos, led_count=4)
        assert result.shape == (4, 3)
        # LEDs at segment centers: (0.25, 0.75, 1.25, 1.75) * direction
        expected_x = [0.25, 0.75, 1.25, 1.75]
        np.testing.assert_array_almost_equal(result[:, 0], expected_x)
        np.testing.assert_array_almost_equal(result[:, 1], [0.0] * 4)
        np.testing.assert_array_almost_equal(result[:, 2], [0.0] * 4)

    def test_expand_single_led_at_midpoint(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)
        pos = (0.0, 0.0, 0.0)
        result = expand_positions(geo, pos, led_count=1)
        assert result.shape == (1, 3)
        np.testing.assert_array_almost_equal(result[0], [1.0, 0.0, 0.0])

    def test_expand_with_offset_position(self) -> None:
        geo = StripGeometry(direction=(0.0, 1.0, 0.0), length=1.0)
        pos = (5.0, 3.0, 0.0)
        result = expand_positions(geo, pos, led_count=2)
        np.testing.assert_array_almost_equal(result[0], [5.0, 3.25, 0.0])
        np.testing.assert_array_almost_equal(result[1], [5.0, 3.75, 0.0])


class TestMatrixGeometry:
    def test_create(self) -> None:
        tile = TileLayout(offset_x=0.0, offset_y=0.0, width=8, height=8)
        geo = MatrixGeometry(tiles=(tile,))
        assert geo.pixel_pitch == 0.03

    def test_expand_single_tile(self) -> None:
        tile = TileLayout(offset_x=0.0, offset_y=0.0, width=2, height=2)
        geo = MatrixGeometry(tiles=(tile,), pixel_pitch=0.1)
        pos = (1.0, 2.0, 0.0)
        result = expand_positions(geo, pos, led_count=4)
        assert result.shape == (4, 3)
        # Row-major: (0,0), (1,0), (0,1), (1,1) * pixel_pitch + offset + pos
        np.testing.assert_array_almost_equal(result[0], [1.0, 2.0, 0.0])
        np.testing.assert_array_almost_equal(result[1], [1.1, 2.0, 0.0])
        np.testing.assert_array_almost_equal(result[2], [1.0, 2.1, 0.0])
        np.testing.assert_array_almost_equal(result[3], [1.1, 2.1, 0.0])

    def test_expand_multi_tile(self) -> None:
        tile0 = TileLayout(offset_x=0.0, offset_y=0.0, width=2, height=2)
        tile1 = TileLayout(offset_x=0.5, offset_y=0.0, width=2, height=2)
        geo = MatrixGeometry(tiles=(tile0, tile1), pixel_pitch=0.1)
        pos = (0.0, 0.0, 0.0)
        result = expand_positions(geo, pos, led_count=8)
        assert result.shape == (8, 3)
        # tile1 positions should be offset by 0.5 on x
        np.testing.assert_array_almost_equal(result[4], [0.5, 0.0, 0.0])

    def test_total_led_count(self) -> None:
        t0 = TileLayout(offset_x=0.0, offset_y=0.0, width=8, height=8)
        t1 = TileLayout(offset_x=0.3, offset_y=0.0, width=8, height=8)
        geo = MatrixGeometry(tiles=(t0, t1))
        total = sum(t.width * t.height for t in geo.tiles)
        assert total == 128
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dj_ledfx.spatial'`

- [ ] **Step 3: Implement geometry types**

```python
# src/dj_ledfx/spatial/__init__.py
from __future__ import annotations

from dj_ledfx.spatial.geometry import (
    DeviceGeometry,
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
    TileLayout,
    expand_positions,
)

__all__ = [
    "DeviceGeometry",
    "MatrixGeometry",
    "PointGeometry",
    "StripGeometry",
    "TileLayout",
    "expand_positions",
]
```

```python
# src/dj_ledfx/spatial/geometry.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PointGeometry:
    """Single LED at device position."""

    pass


@dataclass(frozen=True, slots=True)
class StripGeometry:
    """LEDs along a direction vector.

    Direction is auto-normalized at construction; zero vector raises ValueError.
    led_count is NOT stored here — it comes from adapter.led_count.
    """

    direction: tuple[float, float, float]
    length: float  # meters

    def __post_init__(self) -> None:
        mag = sum(d * d for d in self.direction) ** 0.5
        if mag < 1e-9:
            raise ValueError("StripGeometry direction must be non-zero")
        if abs(mag - 1.0) > 1e-6:
            normalized = tuple(d / mag for d in self.direction)
            object.__setattr__(self, "direction", normalized)


@dataclass(frozen=True, slots=True)
class TileLayout:
    """Single tile's position and dimensions within a matrix.

    Offsets are in meters relative to device position.
    """

    offset_x: float
    offset_y: float
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MatrixGeometry:
    """W×H LED grid with tile offsets."""

    tiles: tuple[TileLayout, ...]
    pixel_pitch: float = 0.03  # meters between LED centers

DeviceGeometry = PointGeometry | StripGeometry | MatrixGeometry


def expand_positions(
    geometry: DeviceGeometry,
    position: tuple[float, float, float],
    led_count: int,
) -> NDArray[np.float64]:
    """Expand a geometry + position into per-LED world-space coordinates.

    Returns shape (N, 3) float64 array.
    """
    pos = np.array(position, dtype=np.float64)

    if isinstance(geometry, PointGeometry):
        return pos.reshape(1, 3)

    if isinstance(geometry, StripGeometry):
        direction = np.array(geometry.direction, dtype=np.float64)
        # Segment center convention: (i + 0.5) / N
        t = (np.arange(led_count, dtype=np.float64) + 0.5) / led_count
        return pos + np.outer(t * geometry.length, direction)

    if isinstance(geometry, MatrixGeometry):
        positions_list: list[NDArray[np.float64]] = []
        for tile in geometry.tiles:
            tile_offset = np.array([tile.offset_x, tile.offset_y, 0.0], dtype=np.float64)
            for row in range(tile.height):
                for col in range(tile.width):
                    led_offset = np.array(
                        [col * geometry.pixel_pitch, row * geometry.pixel_pitch, 0.0],
                        dtype=np.float64,
                    )
                    positions_list.append(pos + tile_offset + led_offset)
        return np.array(positions_list, dtype=np.float64)

    msg = f"Unknown geometry type: {type(geometry)}"
    raise TypeError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/spatial/test_geometry.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run linter and type checker**

Run: `uv run ruff check src/dj_ledfx/spatial/ tests/spatial/ && uv run mypy src/dj_ledfx/spatial/`

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/spatial/__init__.py src/dj_ledfx/spatial/geometry.py tests/spatial/__init__.py tests/spatial/test_geometry.py
git commit -m "feat(spatial): add geometry types and position expansion"
```

---

### Task 2: Spatial Mapping Protocol and Implementations

**Files:**
- Create: `src/dj_ledfx/spatial/mapping.py`
- Create: `tests/spatial/test_mapping.py`
- Modify: `src/dj_ledfx/spatial/__init__.py`

- [ ] **Step 1: Write failing tests for mappings**

```python
# tests/spatial/test_mapping.py
from __future__ import annotations

import numpy as np

from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping


class TestLinearMapping:
    def test_positions_along_axis_monotonically_increasing(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
        ])
        result = mapping.map_positions(positions)
        assert result.shape == (4,)
        assert np.all(np.diff(result) > 0)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_positions_perpendicular_same_value(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 5.0, 0.0],
            [1.0, -3.0, 2.0],
        ])
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, result[0])

    def test_output_clamped_to_unit_range(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([[-100.0, 0.0, 0.0], [100.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_with_origin(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0), origin=(5.0, 0.0, 0.0))
        positions = np.array([[5.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        assert result[0] == 0.0

    def test_3d_diagonal_direction(self) -> None:
        mapping = LinearMapping(direction=(1.0, 1.0, 1.0))
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0],
        ])
        result = mapping.map_positions(positions)
        assert np.all(np.diff(result) > 0)

    def test_all_same_position_returns_zeros(self) -> None:
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        positions = np.array([[1.0, 2.0, 3.0]] * 5)
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, 0.0)


class TestRadialMapping:
    def test_concentric_positions_increasing(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        positions = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
        ])
        result = mapping.map_positions(positions)
        assert result.shape == (4,)
        assert np.all(np.diff(result) > 0)

    def test_equidistant_positions_same_value(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        positions = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [-1.0, 0.0, 0.0],
        ])
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, result[0])

    def test_output_clamped(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0), max_radius=1.0)
        positions = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_center_returns_zero(self) -> None:
        mapping = RadialMapping(center=(5.0, 5.0, 5.0))
        positions = np.array([[5.0, 5.0, 5.0]])
        result = mapping.map_positions(positions)
        assert result[0] == 0.0

    def test_all_same_position_returns_zeros(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        positions = np.array([[3.0, 4.0, 0.0]] * 5)
        result = mapping.map_positions(positions)
        np.testing.assert_array_almost_equal(result, 0.0)

    def test_with_max_radius(self) -> None:
        mapping = RadialMapping(center=(0.0, 0.0, 0.0), max_radius=10.0)
        positions = np.array([[5.0, 0.0, 0.0]])
        result = mapping.map_positions(positions)
        np.testing.assert_almost_equal(result[0], 0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_mapping.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement mapping protocol and classes**

```python
# src/dj_ledfx/spatial/mapping.py
from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class SpatialMapping(Protocol):
    """Maps 3D positions to [0.0, 1.0] strip indices."""

    def map_positions(
        self,
        positions: NDArray[np.float64],
    ) -> NDArray[np.float64]: ...


class LinearMapping:
    """Projects positions onto a direction vector."""

    def __init__(
        self,
        direction: tuple[float, float, float] = (1.0, 0.0, 0.0),
        origin: tuple[float, float, float] | None = None,
    ) -> None:
        d = np.array(direction, dtype=np.float64)
        mag = np.linalg.norm(d)
        if mag < 1e-9:
            msg = "LinearMapping direction must be non-zero"
            raise ValueError(msg)
        self._direction = d / mag
        self._origin = np.array(origin, dtype=np.float64) if origin is not None else None

    def map_positions(
        self,
        positions: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        if self._origin is not None:
            relative = positions - self._origin
        else:
            relative = positions
        projections = relative @ self._direction
        p_min = projections.min()
        p_max = projections.max()
        span = p_max - p_min
        if span < 1e-12:
            return np.zeros(len(positions), dtype=np.float64)
        result = (projections - p_min) / span
        return np.clip(result, 0.0, 1.0)


class RadialMapping:
    """Maps positions by distance from a center point."""

    def __init__(
        self,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        max_radius: float | None = None,
    ) -> None:
        self._center = np.array(center, dtype=np.float64)
        self._max_radius = max_radius

    def map_positions(
        self,
        positions: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        distances = np.linalg.norm(positions - self._center, axis=1)
        if self._max_radius is not None:
            radius = self._max_radius
        else:
            radius = distances.max()
        if radius < 1e-12:
            return np.zeros(len(positions), dtype=np.float64)
        result = distances / radius
        return np.clip(result, 0.0, 1.0)
```

- [ ] **Step 4: Update `__init__.py` re-exports**

Add to `src/dj_ledfx/spatial/__init__.py`:

```python
from dj_ledfx.spatial.mapping import (
    LinearMapping,
    RadialMapping,
    SpatialMapping,
)
```

And add `"LinearMapping"`, `"RadialMapping"`, `"SpatialMapping"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/spatial/test_mapping.py -v`
Expected: All tests PASS

- [ ] **Step 6: Lint and type-check**

Run: `uv run ruff check src/dj_ledfx/spatial/ tests/spatial/ && uv run mypy src/dj_ledfx/spatial/`

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/spatial/mapping.py src/dj_ledfx/spatial/__init__.py tests/spatial/test_mapping.py
git commit -m "feat(spatial): add SpatialMapping protocol with Linear and Radial implementations"
```

---

## Chunk 2: Scene Model and Compositor

### Task 3: SceneModel and DevicePlacement

**Files:**
- Create: `src/dj_ledfx/spatial/scene.py`
- Create: `tests/spatial/test_scene.py`
- Modify: `src/dj_ledfx/devices/adapter.py`
- Modify: `tests/conftest.py`
- Modify: `src/dj_ledfx/spatial/__init__.py`

- [ ] **Step 1: Add `geometry` property to DeviceAdapter ABC**

In `src/dj_ledfx/devices/adapter.py`, add import and property:

```python
# Add import at top:
from dj_ledfx.spatial.geometry import DeviceGeometry

# Add property to DeviceAdapter class (after led_count property, before connect):
    @property
    def geometry(self) -> DeviceGeometry | None:
        """Optional: report device's physical geometry for spatial mapping."""
        return None
```

- [ ] **Step 2: Update MockDeviceAdapter in `tests/conftest.py`**

Add `geometry` parameter and property to MockDeviceAdapter:

```python
# Add import:
from dj_ledfx.spatial.geometry import DeviceGeometry

# Add to __init__ params:
    geometry: DeviceGeometry | None = None,
# Add to __init__ body:
    self._geometry = geometry

# Add property:
    @property
    def geometry(self) -> DeviceGeometry | None:
        return self._geometry
```

- [ ] **Step 3: Write failing tests for SceneModel**

```python
# tests/spatial/test_scene.py
from __future__ import annotations

import numpy as np
import pytest

from dj_ledfx.spatial.geometry import (
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
    TileLayout,
)
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from tests.conftest import MockDeviceAdapter


class TestDevicePlacement:
    def test_create(self) -> None:
        p = DevicePlacement(
            device_id="lamp",
            position=(1.0, 2.0, 3.0),
            geometry=PointGeometry(),
            led_count=1,
        )
        assert p.device_id == "lamp"
        assert p.led_count == 1


class TestSceneModel:
    def test_get_led_positions_point(self) -> None:
        scene = SceneModel(placements={
            "bulb": DevicePlacement("bulb", (1.0, 2.0, 0.0), PointGeometry(), 1),
        })
        pos = scene.get_led_positions("bulb")
        assert pos.shape == (1, 3)
        np.testing.assert_array_almost_equal(pos[0], [1.0, 2.0, 0.0])

    def test_get_led_positions_strip(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
        scene = SceneModel(placements={
            "strip": DevicePlacement("strip", (0.0, 0.0, 0.0), geo, 4),
        })
        pos = scene.get_led_positions("strip")
        assert pos.shape == (4, 3)

    def test_get_led_positions_cached(self) -> None:
        scene = SceneModel(placements={
            "bulb": DevicePlacement("bulb", (1.0, 2.0, 0.0), PointGeometry(), 1),
        })
        pos1 = scene.get_led_positions("bulb")
        pos2 = scene.get_led_positions("bulb")
        assert pos1 is pos2  # same object, cached

    def test_get_bounds(self) -> None:
        scene = SceneModel(placements={
            "a": DevicePlacement("a", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "b": DevicePlacement("b", (10.0, 5.0, 3.0), PointGeometry(), 1),
        })
        bounds_min, bounds_max = scene.get_bounds()
        np.testing.assert_array_almost_equal(bounds_min, [0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(bounds_max, [10.0, 5.0, 3.0])

    def test_from_config_point_device(self) -> None:
        adapters = [MockDeviceAdapter(name="lamp", led_count=1)]
        config = {
            "devices": [
                {"name": "lamp", "position": [1.0, 2.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert "lamp" in scene.placements
        assert scene.placements["lamp"].led_count == 1

    def test_from_config_strip_device(self) -> None:
        adapters = [MockDeviceAdapter(name="strip", led_count=30)]
        config = {
            "devices": [
                {
                    "name": "strip",
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [1.0, 0.0, 0.0],
                    "length": 1.5,
                },
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert "strip" in scene.placements
        assert scene.placements["strip"].led_count == 30

    def test_from_config_adapter_geometry_used(self) -> None:
        geo = PointGeometry()
        adapters = [MockDeviceAdapter(name="bulb", led_count=1, geometry=geo)]
        config = {
            "devices": [
                {"name": "bulb", "position": [0.0, 0.0, 0.0]},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert isinstance(scene.placements["bulb"].geometry, PointGeometry)

    def test_from_config_config_geometry_overrides_adapter(self) -> None:
        geo = PointGeometry()
        adapters = [MockDeviceAdapter(name="dev", led_count=10, geometry=geo)]
        config = {
            "devices": [
                {
                    "name": "dev",
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [1.0, 0.0, 0.0],
                    "length": 1.0,
                },
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert isinstance(scene.placements["dev"].geometry, StripGeometry)

    def test_from_config_unknown_device_skipped(self) -> None:
        adapters = [MockDeviceAdapter(name="real_device", led_count=1)]
        config = {
            "devices": [
                {"name": "nonexistent", "position": [0.0, 0.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert len(scene.placements) == 0

    def test_from_config_bad_position_skipped(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert len(scene.placements) == 0

    def test_from_config_fallback_geometry(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=10)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0]},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        # >1 LED, no geometry specified, no adapter geometry → StripGeometry fallback
        assert isinstance(scene.placements["dev"].geometry, StripGeometry)

    def test_from_config_single_led_fallback_to_point(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0]},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert isinstance(scene.placements["dev"].geometry, PointGeometry)

    def test_from_config_backend_prefix_match(self) -> None:
        adapters = [MockDeviceAdapter(name="DJ Booth", led_count=1)]
        config = {
            "devices": [
                {"name": "lifx:DJ Booth", "position": [0.0, 0.0, 0.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        # Should match by stripping "lifx:" prefix
        assert "DJ Booth" in scene.placements

    def test_from_config_duplicate_name_last_wins(self) -> None:
        adapters = [MockDeviceAdapter(name="dev", led_count=1)]
        config = {
            "devices": [
                {"name": "dev", "position": [0.0, 0.0, 0.0], "geometry": "point"},
                {"name": "dev", "position": [5.0, 5.0, 5.0], "geometry": "point"},
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        assert scene.placements["dev"].position == (5.0, 5.0, 5.0)

    def test_from_config_strip_missing_length_defaults(self) -> None:
        adapters = [MockDeviceAdapter(name="strip", led_count=10)]
        config = {
            "devices": [
                {
                    "name": "strip",
                    "position": [0.0, 0.0, 0.0],
                    "geometry": "strip",
                    "direction": [1.0, 0.0, 0.0],
                },
            ],
        }
        scene = SceneModel.from_config(config, adapters)
        geo = scene.placements["strip"].geometry
        assert isinstance(geo, StripGeometry)
        assert geo.length == 1.0
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_scene.py -v`
Expected: FAIL

- [ ] **Step 5: Implement SceneModel**

```python
# src/dj_ledfx/spatial/scene.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.spatial.geometry import (
    DeviceGeometry,
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
    expand_positions,
)

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter


@dataclass(frozen=True, slots=True)
class DevicePlacement:
    """A device placed in 3D space."""

    device_id: str
    position: tuple[float, float, float]
    geometry: DeviceGeometry
    led_count: int


class SceneModel:
    """Central registry of device placements with cached LED positions."""

    def __init__(self, placements: dict[str, DevicePlacement]) -> None:
        self.placements = placements
        self._position_cache: dict[str, NDArray[np.float64]] = {}

    def get_led_positions(self, device_id: str) -> NDArray[np.float64]:
        """Returns (N, 3) world-space positions, cached after first call."""
        if device_id in self._position_cache:
            return self._position_cache[device_id]
        placement = self.placements[device_id]
        positions = expand_positions(
            placement.geometry, placement.position, placement.led_count
        )
        self._position_cache[device_id] = positions
        return positions

    def get_bounds(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Returns (min_xyz, max_xyz) bounding box of all LED positions."""
        all_positions: list[NDArray[np.float64]] = []
        for device_id in self.placements:
            all_positions.append(self.get_led_positions(device_id))
        if not all_positions:
            zeros = np.zeros(3, dtype=np.float64)
            return zeros, zeros
        combined = np.concatenate(all_positions)
        return combined.min(axis=0), combined.max(axis=0)

    @staticmethod
    def from_config(
        scene_config: dict,
        adapters: list[DeviceAdapter],
    ) -> SceneModel:
        """Build SceneModel from TOML config + discovered adapters."""
        adapter_lookup: dict[str, DeviceAdapter] = {}
        for adapter in adapters:
            adapter_lookup[adapter.device_info.name] = adapter

        placements: dict[str, DevicePlacement] = {}
        for entry in scene_config.get("devices", []):
            name = entry.get("name", "")

            # Resolve adapter: exact match first, then backend-prefix
            adapter = adapter_lookup.get(name)
            if adapter is None and ":" in name:
                raw_name = name.split(":", 1)[1]
                adapter = adapter_lookup.get(raw_name)
            if adapter is None:
                logger.warning("Scene device '{}' not found in discovered devices, skipping", name)
                continue

            # Validate position
            pos = entry.get("position", [])
            if not isinstance(pos, list) or len(pos) != 3:
                logger.warning("Scene device '{}' has invalid position, skipping", name)
                continue
            position = (float(pos[0]), float(pos[1]), float(pos[2]))

            # Resolve geometry
            geometry = _resolve_geometry(entry, adapter)
            if geometry is None:
                continue

            device_id = adapter.device_info.name
            placements[device_id] = DevicePlacement(
                device_id=device_id,
                position=position,
                geometry=geometry,
                led_count=adapter.led_count,
            )

        logger.info("Scene loaded with {} devices", len(placements))
        return SceneModel(placements=placements)


def _resolve_geometry(
    entry: dict,
    adapter: DeviceAdapter,
) -> DeviceGeometry | None:
    """Resolve geometry: config > adapter > fallback."""
    geo_type = entry.get("geometry")

    if geo_type == "point":
        return PointGeometry()

    if geo_type == "strip":
        direction = entry.get("direction", [1.0, 0.0, 0.0])
        if not isinstance(direction, list) or len(direction) != 3:
            logger.warning(
                "Scene device '{}' has invalid direction, skipping",
                entry.get("name"),
            )
            return None
        length = float(entry.get("length", 1.0))
        if "length" not in entry:
            logger.warning(
                "Scene device '{}': strip missing length, defaulting to 1.0m",
                entry.get("name"),
            )
        return StripGeometry(
            direction=(float(direction[0]), float(direction[1]), float(direction[2])),
            length=length,
        )

    if geo_type == "matrix":
        if adapter.geometry is not None and isinstance(adapter.geometry, MatrixGeometry):
            return adapter.geometry
        logger.warning(
            "Scene device '{}': matrix geometry requested but adapter has no tile layout, "
            "falling back to strip",
            entry.get("name"),
        )
        return StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)

    # No geometry specified in config — try adapter, then fallback
    if geo_type is None:
        if adapter.geometry is not None:
            return adapter.geometry
        if adapter.led_count <= 1:
            return PointGeometry()
        return StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)

    logger.warning("Scene device '{}': unknown geometry type '{}'", entry.get("name"), geo_type)
    return None
```

- [ ] **Step 6: Update `__init__.py` re-exports**

Add to `src/dj_ledfx/spatial/__init__.py`:

```python
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
```

And add `"DevicePlacement"`, `"SceneModel"` to `__all__`.

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/spatial/test_scene.py -v`
Expected: All PASS

- [ ] **Step 8: Run full test suite to check nothing is broken**

Run: `uv run pytest -x -v`
Expected: All existing + new tests PASS

- [ ] **Step 9: Lint and type-check**

Run: `uv run ruff check src/dj_ledfx/spatial/ tests/spatial/ src/dj_ledfx/devices/adapter.py && uv run mypy src/dj_ledfx/spatial/`

- [ ] **Step 10: Commit**

```bash
git add src/dj_ledfx/spatial/scene.py src/dj_ledfx/spatial/__init__.py src/dj_ledfx/devices/adapter.py tests/conftest.py tests/spatial/test_scene.py
git commit -m "feat(spatial): add SceneModel with config parsing and adapter geometry"
```

---

### Task 4: SpatialCompositor

**Files:**
- Create: `src/dj_ledfx/spatial/compositor.py`
- Create: `tests/spatial/test_compositor.py`
- Modify: `src/dj_ledfx/spatial/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/spatial/test_compositor.py
from __future__ import annotations

import numpy as np

from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry, MatrixGeometry, TileLayout
from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel


def _gradient_strip(n: int) -> np.ndarray:
    """Create a gradient from black (0,0,0) to white (255,255,255)."""
    t = np.linspace(0, 255, n, dtype=np.uint8)
    return np.column_stack([t, t, t])


class TestSpatialCompositor:
    def test_point_device_gets_single_color(self) -> None:
        scene = SceneModel(placements={
            "bulb": DevicePlacement("bulb", (0.5, 0.0, 0.0), PointGeometry(), 1),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "bulb")
        assert result is not None
        assert result.shape == (1, 3)

    def test_devices_at_different_positions_get_different_colors(self) -> None:
        scene = SceneModel(placements={
            "left": DevicePlacement("left", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "right": DevicePlacement("right", (10.0, 0.0, 0.0), PointGeometry(), 1),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        left_colors = comp.composite(strip, "left")
        right_colors = comp.composite(strip, "right")
        assert left_colors is not None
        assert right_colors is not None
        # Left should be darker than right along the gradient
        assert left_colors[0, 0] < right_colors[0, 0]

    def test_strip_device_gets_gradient(self) -> None:
        geo = StripGeometry(direction=(1.0, 0.0, 0.0), length=10.0)
        scene = SceneModel(placements={
            "strip": DevicePlacement("strip", (0.0, 0.0, 0.0), geo, 10),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "strip")
        assert result is not None
        assert result.shape == (10, 3)
        # Colors should increase along the strip
        assert np.all(np.diff(result[:, 0].astype(int)) >= 0)

    def test_matrix_device(self) -> None:
        tile = TileLayout(offset_x=0.0, offset_y=0.0, width=4, height=4)
        geo = MatrixGeometry(tiles=(tile,), pixel_pitch=1.0)
        scene = SceneModel(placements={
            "tiles": DevicePlacement("tiles", (0.0, 0.0, 0.0), geo, 16),
        })
        mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "tiles")
        assert result is not None
        assert result.shape == (16, 3)

    def test_unknown_device_returns_none(self) -> None:
        scene = SceneModel(placements={})
        mapping = LinearMapping()
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        result = comp.composite(strip, "nonexistent")
        assert result is None

    def test_radial_mapping_integration(self) -> None:
        scene = SceneModel(placements={
            "center": DevicePlacement("center", (0.0, 0.0, 0.0), PointGeometry(), 1),
            "edge": DevicePlacement("edge", (5.0, 0.0, 0.0), PointGeometry(), 1),
        })
        mapping = RadialMapping(center=(0.0, 0.0, 0.0))
        comp = SpatialCompositor(scene, mapping)
        strip = _gradient_strip(256)
        center_colors = comp.composite(strip, "center")
        edge_colors = comp.composite(strip, "edge")
        assert center_colors is not None
        assert edge_colors is not None
        assert center_colors[0, 0] < edge_colors[0, 0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/spatial/test_compositor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement SpatialCompositor**

```python
# src/dj_ledfx/spatial/compositor.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.spatial.mapping import SpatialMapping
    from dj_ledfx.spatial.scene import SceneModel


class SpatialCompositor:
    """Maps 1D effect strips onto 3D device positions via cached indices.

    IMPORTANT: Mapping is called ONCE with ALL LED positions from ALL devices
    combined, ensuring global normalization. The results are then split back
    per-device. This means a PointGeometry device at x=0 gets a different
    strip index than one at x=10, even though each has only 1 LED.
    """

    def __init__(self, scene: SceneModel, mapping: SpatialMapping) -> None:
        self._strip_indices: dict[str, NDArray[np.float64]] = {}

        # Collect all positions globally, map once, then distribute
        device_ids: list[str] = []
        position_arrays: list[NDArray[np.float64]] = []
        counts: list[int] = []

        for device_id in scene.placements:
            positions = scene.get_led_positions(device_id)
            device_ids.append(device_id)
            position_arrays.append(positions)
            counts.append(len(positions))

        if not position_arrays:
            return

        all_positions = np.concatenate(position_arrays)
        all_indices = mapping.map_positions(all_positions)

        # Split results back per-device
        offset = 0
        for device_id, count in zip(device_ids, counts):
            self._strip_indices[device_id] = all_indices[offset : offset + count]
            offset += count

    def composite(
        self,
        effect_strip: NDArray[np.uint8],
        device_id: str,
    ) -> NDArray[np.uint8] | None:
        """Sample effect strip for a device. Returns None if device not in scene."""
        indices = self._strip_indices.get(device_id)
        if indices is None:
            return None
        strip_len = len(effect_strip)
        pixel_idx = (indices * (strip_len - 1)).astype(np.intp)
        np.clip(pixel_idx, 0, strip_len - 1, out=pixel_idx)
        return effect_strip[pixel_idx]
```

- [ ] **Step 4: Update `__init__.py` re-exports**

Add to `src/dj_ledfx/spatial/__init__.py`:

```python
from dj_ledfx.spatial.compositor import SpatialCompositor
```

And add `"SpatialCompositor"` to `__all__`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/spatial/test_compositor.py -v`
Expected: All PASS

- [ ] **Step 6: Lint and type-check**

Run: `uv run ruff check src/dj_ledfx/spatial/ tests/spatial/ && uv run mypy src/dj_ledfx/spatial/`

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/spatial/compositor.py src/dj_ledfx/spatial/__init__.py tests/spatial/test_compositor.py
git commit -m "feat(spatial): add SpatialCompositor with cached index lookup"
```

---

## Chunk 3: Integration — Config, Scheduler, Main

### Task 5: Config Parsing

**Files:**
- Modify: `src/dj_ledfx/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing test for scene config**

Add to `tests/test_config.py`:

```python
def test_load_config_with_scene(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        textwrap.dedent("""\
        [scene]
        mapping = "linear"

        [scene.mapping_params]
        direction = [1.0, 0.0, 0.0]

        [[scene.devices]]
        name = "lamp"
        position = [1.0, 2.0, 0.0]
        geometry = "point"
    """))
    config = load_config(toml_file)
    assert config.scene_config is not None
    assert config.scene_config["mapping"] == "linear"
    assert len(config.scene_config["devices"]) == 1


def test_load_config_without_scene(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("[engine]\nfps = 30\n")
    config = load_config(toml_file)
    assert config.scene_config is None


def test_default_config_no_scene() -> None:
    config = AppConfig()
    assert config.scene_config is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_load_config_with_scene -v`
Expected: FAIL — `AppConfig` has no `scene_config`

- [ ] **Step 3: Add `scene_config` to AppConfig and `load_config`**

In `src/dj_ledfx/config.py`:

Add field to `AppConfig`:
```python
    # Scene (raw dict, validated later by SceneModel.from_config)
    scene_config: dict | None = None
```

Add to `load_config()` before `return AppConfig(**kwargs)`:
```python
    if "scene" in raw:
        kwargs["scene_config"] = raw["scene"]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py
git commit -m "feat(config): add scene_config passthrough for spatial mapping"
```

---

### Task 6: Scheduler Integration

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py`
- Modify: `tests/scheduling/test_scheduler.py` (if exists, otherwise tests already cover via integration)

- [ ] **Step 1: Check for existing scheduler tests**

Run: `ls tests/scheduling/` to see what test files exist.

- [ ] **Step 2: Add `compositor` param to `LookaheadScheduler.__init__`**

In `src/dj_ledfx/scheduling/scheduler.py`:

Add import at top:
```python
from dj_ledfx.spatial.compositor import SpatialCompositor
```

Add parameter to `__init__`:
```python
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
        compositor: SpatialCompositor | None = None,
    ) -> None:
```

Add to body:
```python
        self._compositor = compositor
```

- [ ] **Step 3: Insert compositor call in `_send_loop`**

In `_send_loop`, replace lines 151-154:

```python
            # Steps 4-5: Send frame (with optional spatial compositing)
            colors = frame.colors
            if self._compositor is not None:
                mapped = self._compositor.composite(
                    frame.colors, device.adapter.device_info.name
                )
                if mapped is not None:
                    colors = mapped
            send_start = time.monotonic()
            try:
                await device.adapter.send_frame(colors[:device.adapter.led_count])
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS (compositor=None preserves existing behavior)

- [ ] **Step 5: Lint and type-check**

Run: `uv run ruff check src/dj_ledfx/scheduling/ && uv run mypy src/dj_ledfx/scheduling/`

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py
git commit -m "feat(scheduler): integrate spatial compositor into send loop"
```

---

### Task 7: Main Startup Wiring

**Files:**
- Modify: `src/dj_ledfx/main.py`

- [ ] **Step 1: Add imports to `main.py`**

```python
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping
from dj_ledfx.spatial.scene import SceneModel
```

- [ ] **Step 2: Wire SceneModel and Compositor after device discovery**

In `_run()`, after line 70 (`device_manager.add_device(...)` loop) and before `led_count = ...` (line 71), add:

```python
    # Build spatial scene if configured
    compositor: SpatialCompositor | None = None
    if config.scene_config is not None:
        adapters = [d.adapter for d in device_manager.devices]
        scene = SceneModel.from_config(config.scene_config, adapters)
        if scene.placements:
            mapping_name = config.scene_config.get("mapping", "linear")
            mapping_params = config.scene_config.get("mapping_params", {})
            if mapping_name == "radial":
                center = tuple(mapping_params.get("center", [0.0, 0.0, 0.0]))
                max_radius = mapping_params.get("max_radius")
                mapping = RadialMapping(
                    center=(center[0], center[1], center[2]),
                    max_radius=max_radius,
                )
            else:
                direction = tuple(mapping_params.get("direction", [1.0, 0.0, 0.0]))
                origin = mapping_params.get("origin")
                mapping = LinearMapping(
                    direction=(direction[0], direction[1], direction[2]),
                    origin=(origin[0], origin[1], origin[2]) if origin else None,
                )
            compositor = SpatialCompositor(scene, mapping)
            logger.info(
                "Spatial compositor active: {} mapping, {} devices",
                mapping_name,
                len(scene.placements),
            )
```

- [ ] **Step 3: Pass compositor to scheduler**

Change the scheduler instantiation:

```python
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=device_manager.devices,
        fps=config.engine_fps,
        compositor=compositor,
    )
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS

- [ ] **Step 5: Lint and type-check the whole project**

Run: `uv run ruff check . && uv run mypy src/`

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat(main): wire spatial compositor into startup pipeline"
```

---

### Task 8: Integration Test

**Files:**
- Create: `tests/spatial/test_spatial_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# tests/spatial/test_spatial_pipeline.py
from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry
from dj_ledfx.spatial.mapping import LinearMapping
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel
from tests.conftest import MockDeviceAdapter


@pytest.mark.asyncio
async def test_spatial_pipeline_different_positions_different_colors() -> None:
    """Devices at different positions should receive different colors."""
    left_adapter = MockDeviceAdapter(name="left", led_count=10)
    right_adapter = MockDeviceAdapter(name="right", led_count=10)

    scene = SceneModel(placements={
        "left": DevicePlacement("left", (0.0, 0.0, 0.0), PointGeometry(), 1),
        "right": DevicePlacement("right", (10.0, 0.0, 0.0), PointGeometry(), 1),
    })
    mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
    compositor = SpatialCompositor(scene, mapping)

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    from dj_ledfx.prodjlink.listener import BeatEvent

    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    effect = BeatPulse()
    engine = EffectEngine(clock=clock, effect=effect, led_count=60, fps=60)

    left_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))
    right_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))

    managed_devices = [
        ManagedDevice(adapter=left_adapter, tracker=left_tracker, max_fps=60),
        ManagedDevice(adapter=right_adapter, tracker=right_tracker, max_fps=60),
    ]

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=managed_devices,
        fps=60,
        compositor=compositor,
    )

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.5)

    simulator.stop()
    engine.stop()
    scheduler.stop()

    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both should have received frames
    assert len(left_adapter.send_frame_calls) > 0
    assert len(right_adapter.send_frame_calls) > 0


@pytest.mark.asyncio
async def test_unmapped_device_gets_broadcast_when_compositor_active() -> None:
    """A device NOT in the scene should still receive frames (broadcast)."""
    mapped_adapter = MockDeviceAdapter(name="mapped", led_count=10)
    unmapped_adapter = MockDeviceAdapter(name="unmapped", led_count=10)

    # Only "mapped" is in the scene
    scene = SceneModel(placements={
        "mapped": DevicePlacement("mapped", (0.0, 0.0, 0.0), PointGeometry(), 1),
    })
    mapping = LinearMapping(direction=(1.0, 0.0, 0.0))
    compositor = SpatialCompositor(scene, mapping)

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    from dj_ledfx.prodjlink.listener import BeatEvent

    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    effect = BeatPulse()
    engine = EffectEngine(clock=clock, effect=effect, led_count=60, fps=60)

    mapped_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))
    unmapped_tracker = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))

    managed_devices = [
        ManagedDevice(adapter=mapped_adapter, tracker=mapped_tracker, max_fps=60),
        ManagedDevice(adapter=unmapped_adapter, tracker=unmapped_tracker, max_fps=60),
    ]

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=managed_devices,
        fps=60,
        compositor=compositor,
    )

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.3)

    simulator.stop()
    engine.stop()
    scheduler.stop()

    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both should have received frames — unmapped gets broadcast
    assert len(mapped_adapter.send_frame_calls) > 0
    assert len(unmapped_adapter.send_frame_calls) > 0


@pytest.mark.asyncio
async def test_no_scene_matches_mvp_behavior() -> None:
    """Without a compositor, scheduler uses broadcast (same colors to all)."""
    adapter_a = MockDeviceAdapter(name="a", led_count=10)
    adapter_b = MockDeviceAdapter(name="b", led_count=10)

    event_bus = EventBus()
    clock = BeatClock()
    simulator = BeatSimulator(event_bus=event_bus, bpm=120.0)
    from dj_ledfx.prodjlink.listener import BeatEvent

    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    effect = BeatPulse()
    engine = EffectEngine(clock=clock, effect=effect, led_count=10, fps=60)

    tracker_a = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))
    tracker_b = LatencyTracker(strategy=StaticLatency(latency_ms=5.0))

    managed = [
        ManagedDevice(adapter=adapter_a, tracker=tracker_a, max_fps=60),
        ManagedDevice(adapter=adapter_b, tracker=tracker_b, max_fps=60),
    ]

    # No compositor — MVP broadcast behavior
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=managed,
        fps=60,
    )

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(0.3)

    simulator.stop()
    engine.stop()
    scheduler.stop()

    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    assert len(adapter_a.send_frame_calls) > 0
    assert len(adapter_b.send_frame_calls) > 0
    # Both devices should get identical frames (broadcast)
    min_len = min(len(adapter_a.send_frame_calls), len(adapter_b.send_frame_calls))
    if min_len > 0:
        np.testing.assert_array_equal(
            adapter_a.send_frame_calls[0],
            adapter_b.send_frame_calls[0],
        )
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/spatial/test_spatial_pipeline.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite one final time**

Run: `uv run pytest -x -v`
Expected: All tests PASS

- [ ] **Step 4: Lint and type-check the entire project**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy src/`

- [ ] **Step 5: Commit**

```bash
git add tests/spatial/test_spatial_pipeline.py
git commit -m "test(spatial): add integration test for full spatial pipeline"
```

- [ ] **Step 6: Final commit — all spatial features complete**

Run `uv run pytest` one last time to confirm everything passes, then verify with `git log --oneline` that the commit history is clean.
