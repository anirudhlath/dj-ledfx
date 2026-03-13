# 3D Spatial Scene Mapping Design

## Overview

Spatial compositor layer that maps 1D effect output onto 3D device positions, enabling spatially-aware lighting effects (directional sweeps, radial pulses, etc.) across heterogeneous LED hardware. Effects remain unchanged — they still render a 1D color strip. A new compositor sits between effect output and device delivery, sampling each LED's color based on its world-space position.

## Hardware Targets

- LIFX A19 bulbs (1 LED each, point geometry)
- LIFX strips (N zones, linear geometry)
- LIFX tile chains (5 tiles × 8×8 LEDs, matrix geometry)
- OpenRGB devices (strips/matrices, geometry from config)
- Govee lights (point geometry)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Full pipeline (scene + spatial effects) | Layout definition and spatial effects together |
| Scene input | TOML config first, UI later | Get spatial engine right before building frontend |
| Coordinate system | 2D + optional Z (full 3D math) | Pragmatic — z defaults to 0.0, compositor always uses all 3 axes |
| Effect integration | Spatial compositor layer | Effects unchanged; compositor maps 1D strip → 3D positions |
| Mapping interface | Protocol (pluggable) | Stateless strategy, matches ProbeStrategy precedent |
| Initial mappings | Linear + Radial | Covers sweeps + pulses, expand later |
| Device granularity | Per-LED sampling | Max fidelity, trivial numpy math at 60fps |
| Device organization | Flat device list | No zones/tags/hierarchy for now |
| Backward compat | Full — no scene = MVP behavior | Compositor is None when no [scene] configured |

## Architecture

### Pipeline Change

The compositor inserts between the ring buffer read and device send in the per-device send loop:

```
BeatClock → Effect.render() → 1D Color Strip → RingBuffer
                                                    ↓
                                          Per-device send loop:
                                          1. Pick frame from ring buffer (unchanged)
                                          2. NEW: compositor.composite(frame.colors, device_id)
                                          3. Send per-device colors to adapter (unchanged)
```

No compositor configured → step 2 is skipped, broadcast behavior preserved.

Modified send loop pseudocode:

```python
# In _send_loop (scheduler.py)
colors = frame.colors
if compositor is not None:
    mapped = compositor.composite(frame.colors, device_id)
    if mapped is not None:
        colors = mapped
# send_frame as before — adapters handle their own LED count
await device.adapter.send_frame(colors)
```

### New Module: `src/dj_ledfx/spatial/`

```
spatial/
    __init__.py
    geometry.py      # DeviceGeometry types, LED position expansion
    scene.py         # SceneModel, DevicePlacement, from_config
    mapping.py       # SpatialMapping protocol, LinearMapping, RadialMapping
    compositor.py    # SpatialCompositor — sampling + caching
```

### Modified Existing Files

- `devices/adapter.py` — Add optional `geometry` property to DeviceAdapter ABC, importing `DeviceGeometry` from `spatial.geometry`
- `scheduling/scheduler.py` — Add `compositor: SpatialCompositor | None = None` to `__init__`, call compositor in per-device send loop
- `config.py` — Add `scene_config: dict | None = None` field to `AppConfig`, parsed via `raw.get("scene")` (raw dict passthrough — scene validation happens in `SceneModel.from_config` which needs adapter info)
- `main.py` — Wire SceneModel + Compositor into startup after device discovery

## Device Geometry Types

Defined in `spatial/geometry.py` (not `types.py` — these are spatial-domain types, not cross-cutting primitives). Re-exported from `spatial/__init__.py`.

Three geometry types cover all current and planned hardware:

```python
@dataclass(frozen=True, slots=True)
class PointGeometry:
    """Single LED at device position. LIFX bulbs, single-color Govee."""
    pass

@dataclass(frozen=True, slots=True)
class StripGeometry:
    """LEDs along a direction vector. LIFX strips, OpenRGB LED strips.
    Direction is auto-normalized at construction; zero vector raises ValueError.
    Note: led_count is NOT stored here — it comes from adapter.led_count
    and is passed to SceneModel.get_led_positions() at expansion time."""
    direction: tuple[float, float, float]  # unit vector along strip (auto-normalized)
    length: float  # meters

    def __post_init__(self) -> None:
        mag = sum(d * d for d in self.direction) ** 0.5
        if mag < 1e-9:
            raise ValueError("StripGeometry direction must be non-zero")
        if abs(mag - 1.0) > 1e-6:
            normalized = tuple(d / mag for d in self.direction)
            object.__setattr__(self, "direction", normalized)

@dataclass(frozen=True, slots=True)
class MatrixGeometry:
    """W×H LED grid with tile offsets. LIFX tile chains."""
    tiles: tuple[TileLayout, ...]
    pixel_pitch: float = 0.03  # meters between LED centers (LIFX default ~30mm)

@dataclass(frozen=True, slots=True)
class TileLayout:
    """Single tile's position and dimensions within a matrix.
    Offsets are in meters relative to device position.
    Note: LIFX TileInfo uses raw user_x/user_y values — the adapter's
    geometry property must convert: offset = user_x * pixel_pitch."""
    offset_x: float  # relative to device position (meters)
    offset_y: float
    width: int   # 8 for LIFX tiles
    height: int  # 8 for LIFX tiles

DeviceGeometry = PointGeometry | StripGeometry | MatrixGeometry
```

**Dependency graph** (no cycles): `spatial.geometry` → (no deps), `devices.adapter` → `spatial.geometry`, `spatial.scene` → `devices.adapter`.

### World-Space LED Position Expansion

Each geometry type expands to per-LED world coordinates:

- **PointGeometry** → 1 position: `device.position`
- **StripGeometry** → N positions: `position + direction * (i / N) * length`
- **MatrixGeometry** → W×H positions per tile: `position + tile.offset + (col, row) * geometry.pixel_pitch`

Positions computed once at scene load, cached as numpy `(N, 3)` float64 arrays.

**LED count source**: `led_count` is not stored on geometry types. Instead, `DevicePlacement` carries `led_count: int` sourced from `adapter.led_count` at `from_config` time. `SceneModel.get_led_positions()` uses this to expand strip positions. For MatrixGeometry, led_count = `sum(tile.width * tile.height for tile in tiles)` (validated against adapter at construction). This ensures the compositor always produces exactly the right number of colors for the adapter.

**Strip position convention**: LEDs are placed at segment centers — `position + direction * ((i + 0.5) / N) * length`. This avoids placing a LED at exactly the device origin or strip endpoint, distributes N LEDs evenly across the full strip length, and is well-defined for N=1 (single LED at strip midpoint).

**Matrix LED ordering**: Row-major within each tile (row 0 left-to-right, then row 1, etc.), tiles in chain order. Adapters are responsible for translating to hardware-specific ordering (e.g., LIFX serpentine) in their `send_frame()` implementation.

## Scene Model

```python
class SceneModel:
    placements: dict[str, DevicePlacement]  # device_id → placement

    def get_led_positions(self, device_id: str) -> NDArray[np.float64]:
        """Returns (N, 3) world-space positions for all LEDs.
        Expands geometry → per-LED coords, cached after first call.
        Uses placement.led_count (sourced from adapter at from_config time)
        for strip position expansion."""

    def get_bounds(self) -> tuple[NDArray, NDArray]:
        """Returns (min_xyz, max_xyz) bounding box of entire scene.
        Used by mappings for auto-normalization."""

    @staticmethod
    def from_config(scene_config: dict, adapters: list[DeviceAdapter]) -> SceneModel:
        """Merges TOML placements with adapter-reported geometry.
        Config provides: position, geometry type.
        Adapter provides: led_count, tile layout (for matrix).
        Called after device discovery — see Startup Sequence.
        Accepts list[DeviceAdapter] (not DeviceManager) to keep
        spatial/ decoupled from the scheduling layer."""
```

### DevicePlacement

```python
@dataclass(frozen=True, slots=True)
class DevicePlacement:
    device_id: str  # matches DeviceInfo.name (unique within a backend)
    position: tuple[float, float, float]  # (x, y, z) meters
    geometry: DeviceGeometry
    led_count: int  # from adapter.led_count — ensures compositor output matches adapter
```

### Device Identity

`device_id` is a user-defined string in the TOML config `[[scene.devices]]` `name` field. It is matched against `DeviceInfo.name` from discovered adapters. Within a single backend (OpenRGB, LIFX), device names are unique — OpenRGB uses the controller name from the hardware, LIFX uses the user-assigned label.

The user writes the `name` exactly as the adapter reports it. If two backends happen to have a device with the same name, the user disambiguates in config by prefixing with backend name (e.g., `"openrgb:Motherboard"`, `"lifx:DJ Booth"`). `from_config` first tries an exact match on `DeviceInfo.name`, then tries stripping a `"backend:"` prefix. Unmatched names log WARNING and are skipped.

The scheduler passes `device.adapter.device_info.name` to `compositor.composite()`. The compositor's `_strip_indices` cache is keyed by the raw `DeviceInfo.name` (not the user's config name). During `from_config`, after resolving a config entry to an adapter, the cache is keyed by `adapter.device_info.name`. This means the scheduler never needs to know about backend prefixes — it just passes the adapter's name directly.

### Startup Sequence

SceneModel construction happens after device discovery in `main.py`:

```
1. Load config                              (existing)
2. Create DeviceManager                     (existing)
3. Discover devices via backends            (existing)
4. Add devices to manager                   (existing)
5. NEW: Build SceneModel from config + [d.adapter for d in device_manager.devices]
6. NEW: Create SpatialCompositor (if scene exists)
7. Create EffectEngine and Scheduler        (existing, compositor passed to scheduler)
```

`LookaheadScheduler.__init__` gains a new optional parameter:
```python
compositor: SpatialCompositor | None = None
```

### Adapter Geometry Reporting

New optional property on DeviceAdapter ABC:

```python
@property
def geometry(self) -> DeviceGeometry | None:
    return None  # default: adapter doesn't know its geometry
```

Adapter implementations:
- **OpenRGBAdapter** → returns `None` (geometry from config only)
- **LIFXBulbAdapter** → returns `PointGeometry()`
- **LIFXStripAdapter** → returns `StripGeometry(direction, length)` from zone data
- **LIFXTileChainAdapter** → returns `MatrixGeometry(tiles=...)` from discovery, converting LIFX `TileInfo` → spatial `TileLayout`:
  ```python
  TileLayout(
      offset_x=tile.user_x * pixel_pitch,
      offset_y=tile.user_y * pixel_pitch,
      width=tile.width,
      height=tile.height,
  )
  ```
  This conversion lives in the adapter's `geometry` property, not in `SceneModel`.

Geometry resolution order:
1. TOML config explicit geometry → wins
2. Adapter-reported geometry → auto-discovered
3. Fallback → `PointGeometry()` if 1 LED, `StripGeometry(direction=(1,0,0), length=1.0)` otherwise

## Spatial Mapping Protocol

```python
class SpatialMapping(Protocol):
    def map_positions(
        self,
        positions: NDArray[np.float64],  # (N, 3) world coords
    ) -> NDArray[np.float64]:  # (N,) values in [0.0, 1.0]
        ...
```

Both initial mappings (Linear, Radial) are static — positions always map to the same [0,1] values. This means the compositor can cache mapping results per device at init time. Animated mappings (e.g., rotating sweep) are a future extension that would require adding a `time` parameter and a cache-invalidation mechanism.

### Built-in Mappings

**LinearMapping**: Projects positions onto a direction vector.
- `dot(pos - origin, direction)` → normalized to [0.0, 1.0]
- Parameters: `direction: tuple[float, float, float]`, `origin: tuple[float, float, float]` (optional, defaults to scene min)

**RadialMapping**: Distance from a center point.
- `dist(pos, center)` → normalized to [0.0, 1.0]
- Parameters: `center: tuple[float, float, float]`, `max_radius: float` (optional, auto-computed from scene bounds)

Both mappings clamp output to [0.0, 1.0]. All positions at the same point return 0.0.

## Spatial Compositor

```python
class SpatialCompositor:
    scene: SceneModel
    mapping: SpatialMapping
    # Pre-computed at init (static mappings → computed once, cached forever):
    _strip_indices: dict[str, NDArray]   # device_id → (N,) int indices into effect strip

    def __init__(self, scene: SceneModel, mapping: SpatialMapping) -> None:
        # For each placed device:
        #   1. Get per-LED world positions from scene
        #   2. Map to [0.0, 1.0] via mapping.map_positions()
        #   3. Cache as _strip_indices[device_id]

    def composite(
        self,
        effect_strip: NDArray[np.uint8],  # (led_count, 3) from Effect.render()
        device_id: str,
    ) -> NDArray[np.uint8] | None:  # (device_led_count, 3) or None if unmapped
        # 1. Look up cached strip indices for this device (O(1) dict lookup)
        # 2. Scale to strip length: pixel_idx = (indices * (strip_len - 1)).astype(int)
        # 3. Sample: colors = effect_strip[pixel_idx]  → (N, 3)
        # Returns None if device_id not in scene placements
```

Compositing is a single numpy fancy-index operation — sub-microsecond for typical device sizes. All mapping math happens once at init.

## TOML Configuration

```toml
[scene]
mapping = "linear"           # default spatial mapping

# Linear mapping parameters
[scene.mapping_params]
direction = [1.0, 0.0, 0.0]  # sweep along X axis

# LIFX bulb — point in space
[[scene.devices]]
name = "living_room_lamp"
position = [2.0, 1.5, 1.2]
geometry = "point"

# LED strip along a shelf
[[scene.devices]]
name = "shelf_strip"
position = [0.0, 3.0, 0.8]
geometry = "strip"
direction = [1.0, 0.0, 0.0]  # runs along X axis
length = 1.5                  # meters

# LIFX tile chain — tile layout auto-discovered from device
[[scene.devices]]
name = "dj_booth_tiles"
position = [1.0, 0.0, 1.5]
geometry = "matrix"           # tile layout from LIFX discovery
```

## Config Validation

Scene config entries are validated at `SceneModel.from_config()` time. Invalid entries log WARNING and are skipped (never crash):

| Condition | Behavior |
|-----------|----------|
| `name` doesn't match any discovered device | WARNING, skip entry |
| `position` not exactly 3 elements | WARNING, skip entry |
| `direction` not exactly 3 elements | WARNING, skip entry |
| `geometry = "matrix"` but adapter reports no tile layout | WARNING, fall back to StripGeometry |
| `geometry = "strip"` but no `length` specified | WARNING, default to 1.0m |
| Duplicate device name in `[[scene.devices]]` | WARNING, last entry wins |

## Fallback Behavior

Three tiers of graceful degradation:

| Scenario | Behavior |
|----------|----------|
| **Full scene**: `[scene]` defined with device placements | Compositor active, per-LED spatial sampling |
| **Partial**: `[scene]` exists but some devices missing | Unmapped devices get broadcast behavior, log WARNING |
| **No scene**: no `[scene]` in config | Compositor is `None`, pipeline unchanged from MVP |

Zero breaking changes. Existing configs with no `[scene]` section work exactly as before.

## Testing Strategy

### Unit Tests (`tests/spatial/`)

**test_geometry.py** — LED position expansion:
- PointGeometry → single position
- StripGeometry → N evenly-spaced positions along direction vector
- MatrixGeometry → W×H positions per tile with correct offsets
- Multi-tile chain produces correct total LED count

**test_mapping.py** — Spatial mapping correctness:
- LinearMapping: positions along axis → monotonically increasing [0,1]
- LinearMapping: positions perpendicular to axis → same value
- RadialMapping: concentric positions → increasing values
- RadialMapping: equidistant positions → same value
- Both mappings: output clamped to [0.0, 1.0]
- Edge case: all positions at same point → all return 0.0

**test_compositor.py** — End-to-end sampling:
- Gradient effect strip + linear mapping → devices get different colors by position
- Point device → single color sampled at device position
- Strip device → gradient across its length
- Matrix device → 2D color pattern across tile grid
- No scene configured → returns None (caller uses broadcast)
- Unknown device_id → returns None

**test_scene.py** — Scene model construction:
- from_config merges TOML positions with adapter geometry
- Config geometry overrides adapter geometry
- Missing adapter geometry falls back to defaults
- Bounding box correct across all placements
- LED positions cached after first access
- Invalid config entries skipped with warning (unknown device, bad position, etc.)
- StripGeometry direction auto-normalized
- StripGeometry zero-vector direction raises ValueError

### Integration Test

**test_spatial_pipeline.py**:
- BeatSimulator → Effect → Compositor → mock DeviceAdapters
- Devices at different positions receive different colors
- Unmapped devices get broadcast behavior
- No-scene config matches MVP behavior exactly
