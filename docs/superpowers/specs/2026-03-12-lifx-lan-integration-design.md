# LIFX LAN Protocol Integration Design

## Overview

Direct integration with LIFX devices over the LAN protocol, supporting bulbs (A19), strips, and tile chains with per-device latency compensation via EchoRequest probing. Reimplements the LIFX binary protocol from scratch (no third-party library) for full control over packet timing, native asyncio UDP, and tile-specific message support.

Also introduces a vendor-agnostic `DeviceBackend` ABC with auto-registration, enabling future backends (Govee, etc.) to plug in without modifying core code.

## Hardware Targets

- 2x LIFX Tile chains (5 tiles per chain, 8x8 LEDs each = 320 LEDs per chain)
- LIFX Strips (zone-based addressing)
- ~8x LIFX A19 bulbs (single color each)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Protocol approach | Reimplement from scratch | Full control over timing, native asyncio, no dependency risk. Same approach as Pro DJ Link. |
| Device handling | All device types at once | LIFX discovery finds everything; adapters handle type-specific frame mapping. |
| Tile chain model | Each chain = independent adapter + spatial metadata | Per-chain RTT tracking; tile layout stored for future spatial mapping. |
| Bulb model | Each bulb = independent adapter | Per-device RTT for perfect sync; future logical grouping at effect layer. |
| RTT measurement | Periodic EchoRequest(58) probes | Clean separation from frame delivery; measures pure network latency. |
| Color space | RGB->HSBK conversion in adapter | Effect engine stays RGB; adapter converts at send time. |
| Discovery lifecycle | Once at startup | Matches existing OpenRGB pattern; scheduler handles disconnects. |

## LIFX LAN Protocol Summary

### Packet Header (36 bytes, little-endian)

| Bytes | Field | Size | Notes |
|-------|-------|------|-------|
| 0-1 | size | uint16 | Total packet length |
| 2-3 | flags | uint16 | origin(2) + tagged(1) + addressable(1) + protocol(12). Protocol=1024, addressable=1. |
| 4-7 | source | uint32 | Unique client ID. Non-zero for unicast responses. |
| 8-15 | target | 8 bytes | 6-byte MAC + 2 padding. All zeros = broadcast. |
| 16-21 | reserved | 6 bytes | Must be zero. |
| 22 | flags | uint8 | reserved(6) + ack_required(1) + res_required(1) |
| 23 | sequence | uint8 | Per-device counter for correlating responses. Wraps at 255. |
| 24-31 | reserved | uint64 | Must be zero. |
| 32-33 | type | uint16 | Message type ID. |
| 34-35 | reserved | uint16 | Must be zero. |

### Message Types Used

| Message | Type ID | Payload Size | Purpose |
|---------|---------|--------------|---------|
| GetService | 2 | 0B | Discovery broadcast |
| StateService | 3 | 5B | Discovery response (service + port) |
| GetVersion | 32 | 0B | Query product ID |
| StateVersion | 33 | 12B | vendor + product + version |
| Acknowledgement | 45 | 0B | Ack response (when ack_required=1) |
| EchoRequest | 58 | 64B | RTT probe |
| EchoResponse | 59 | 64B | RTT probe response |
| SetColor | 102 | 13B | Set single bulb color (reserved + HSBK + duration) |
| GetExtendedColorZones | 511 | 0B | Query strip zone count and colors |
| StateExtendedColorZones | 512 | ~664B | Strip zone state response (zone count, colors) |
| SetExtendedColorZones | 510 | ~664B | Set up to 82 strip zones (duration + apply + index + count + 82x HSBK) |
| GetDeviceChain | 701 | 0B | Query tile chain layout |
| StateDeviceChain | 702 | large | Tile positions (user_x, user_y, width, height per tile) |
| GetTileState64 | 707 | 6B | Query tile pixel state |
| SetTileState64 | 715 | ~522B | Set 64 pixels on one tile (index + length + x + y + width + duration + 64x HSBK) |

### HSBK Color Format

Each color is 4x uint16 (8 bytes total):
- Hue: 0-65535 (maps to 0-360 degrees)
- Saturation: 0-65535 (0=white, 65535=full color)
- Brightness: 0-65535 (0=off, 65535=max)
- Kelvin: 2500-9000 (color temperature, used when saturation is low)

### Packet Sizes Per Device Type

| Device | Message | Payload | Total | Per-frame packets |
|--------|---------|---------|-------|-------------------|
| A19 Bulb | SetColor(102) | 13B | 49B | 1 |
| Strip | SetExtendedColorZones(510) | ~664B | ~700B | 1 (up to 82 zones) |
| Tile chain (5) | SetTileState64(715) | ~522B | ~558B | 5 (one per tile) |

All within UDP MTU limit of 1500 bytes.

## Architecture

### Layer 1: LifxTransport (shared singleton)

**File:** `src/dj_ledfx/devices/lifx/transport.py`

Owns the single asyncio UDP socket for all LIFX communication.

**Ownership and lifecycle:**
- Created by `LifxBackend.discover()` before any device discovery occurs
- Passed to all LIFX adapters via constructor injection
- `LifxBackend.discover()` returns the transport as part of the backend's internal state
- Shutdown: `LifxTransport.close()` cancels the receive loop and echo probe tasks, then closes the UDP socket. Called from `LifxBackend.shutdown()`, which is invoked by `DeviceBackend.shutdown_all()` (new class method called from `main.py` after `device_manager.disconnect_all()`)

**Responsibilities:**
- UDP socket lifecycle (bind once, talk to all devices on subnet)
- Packet construction via LifxPacket, packet send/receive
- Discovery: broadcast GetService(2), collect responses, query GetVersion(32)
- RTT probing: periodic EchoRequest(58) per registered device, correlate EchoResponse(59), feed RTT samples to device callbacks
- Source ID management (random uint32 at startup)
- Per-device sequence counters (uint8, wraps at 255)
- Receive loop: single async task demuxes incoming packets by (source_ip, port) tuple to identify the device, then matches sequence number to correlate with outstanding requests

**Receive loop demux strategy:**
- Maintains a `dict[tuple[str, int], LifxDeviceRecord]` mapping (IP, port) to registered devices
- When a packet arrives, looks up the sender's (IP, port) to identify which device sent it
- For EchoResponse correlation: the transport maintains a `dict[int, tuple[str, float]]` mapping sequence number to (device_ip, send_time). On EchoResponse, looks up the sequence to find the original send_time and compute RTT. Sequence numbers are allocated from a global counter (not per-device) to avoid collisions in the pending response map.
- Stale entries in the pending map are cleaned on each probe cycle (any entry older than probe_interval is dropped)

**RTT probe design:**
- Runs as async task at configurable interval (default 2s)
- Iterates registered devices, sends EchoRequest with unique sequence per device
- On EchoResponse: computes `rtt_ms = (now - send_time) * 1000`, calls registered callback
- Callbacks registered by adapters on connect, forward to their LatencyTracker

### Layer 2: LifxPacket (encoding/decoding)

**File:** `src/dj_ledfx/devices/lifx/packet.py`

Dataclass + builder for LIFX binary packets.

**Header construction:**
- `pack() -> bytes` — serialize all fields to 36-byte header + payload
- `unpack(data: bytes) -> LifxPacket` — classmethod, parse from wire format

**Payload builders** (static methods):
- `build_set_color(hsbk, duration) -> bytes`
- `build_set_tile_state64(tile_index, length, x, y, width, duration, colors_hsbk) -> bytes`
- `build_set_extended_color_zones(duration, apply, zone_index, count, colors_hsbk) -> bytes`
- `build_echo_request(payload_bytes) -> bytes`

**Payload parsers** (static methods):
- `parse_state_service(payload) -> tuple[int, int]`
- `parse_state_version(payload) -> tuple[int, int, int]`
- `parse_state_device_chain(payload) -> list[TileInfo]`
- `parse_state_extended_color_zones(payload) -> tuple[int, int, list[tuple[int,int,int,int]]]` — returns (zone_count, zone_index, list of HSBK tuples)
- `parse_echo_response(payload) -> bytes`

**Color conversion** (standalone functions):
- `rgb_to_hsbk(r, g, b, kelvin=3500) -> tuple[int, int, int, int]`
- `rgb_array_to_hsbk(colors: NDArray[np.uint8], kelvin=3500) -> NDArray[np.uint16]` — pure vectorized numpy (no Python loops, no colorsys). On the hot path for strips (82 zones) and tile chains (320 pixels) at 30fps.

### Layer 3: Device Adapters

All inherit from `DeviceAdapter` ABC, receive shared `LifxTransport` instance.

#### LifxBulbAdapter

**File:** `src/dj_ledfx/devices/lifx/bulb.py`

- `led_count` -> 1
- `send_frame(colors)` -> `colors[0]` -> RGB->HSBK -> one SetColor(102) packet
- `supports_latency_probing = False` (RTT managed by transport's echo probes, not scheduler)
- `connect()` -> no-op beyond power check
- `disconnect()` -> clears internal state

#### LifxStripAdapter

**File:** `src/dj_ledfx/devices/lifx/strip.py`

- `led_count` -> actual zone count (queried on connect via GetExtendedColorZones)
- `send_frame(colors)` -> RGB array -> HSBK array -> SetExtendedColorZones(510), up to 82 zones per packet
- `supports_latency_probing = False` (RTT via transport echo probes)
- `connect()` -> queries zone count from device

#### LifxTileChainAdapter

**File:** `src/dj_ledfx/devices/lifx/tile_chain.py`

- `led_count` -> `tiles_in_chain * 64` (e.g., 5 * 64 = 320)
- `send_frame(colors)` -> splits 320-LED array into 5x 64-pixel chunks -> RGB->HSBK each -> 5x SetTileState64(715) packets
- `supports_latency_probing = False` (RTT via transport echo probes)
- `connect()` -> queries StateDeviceChain(702), stores TileInfo metadata
- TileInfo stored but not used yet — available for future spatial mapping and Taichi matrix effects

**TileInfo dataclass** (defined in `src/dj_ledfx/devices/lifx/tile_chain.py`):
```python
@dataclass(frozen=True, slots=True)
class TileInfo:
    user_x: float       # tile position X (float32 from device)
    user_y: float       # tile position Y (float32 from device)
    width: int          # LED grid width (8 for standard tiles)
    height: int         # LED grid height (8 for standard tiles)
    accel_x: int        # accelerometer X (int16, indicates orientation)
    accel_y: int        # accelerometer Y
    accel_z: int        # accelerometer Z
```

**Common constructor pattern:**
```python
def __init__(self, transport: LifxTransport, device_info: DeviceInfo, target_mac: bytes)
```

**RTT flow for all LIFX adapters:**
1. `LifxBackend.discover()` creates each adapter's LatencyTracker with the configured strategy:
   - Reads `config.lifx_latency_strategy` to select StaticLatency/EMALatency/WindowedMeanLatency
   - Seeds initial value from `config.lifx_latency_ms` (default 50ms for WiFi devices)
   - Applies `config.lifx_manual_offset_ms` to LatencyTracker
   - Window size from `config.lifx_latency_window_size` (for windowed_mean strategy)
2. Adapter registers RTT callback with transport on `connect()`
3. Transport periodically sends EchoRequest(58), receives EchoResponse(59)
4. Transport computes `rtt_ms`, calls adapter's registered callback
5. Adapter callback calls `self._tracker.update(rtt_ms)` (adapter holds a reference to its tracker)
6. Scheduler reads `tracker.effective_latency_s` as normal — no scheduler changes needed

Note: `supports_latency_probing = False` on all LIFX adapters prevents the scheduler from measuring `send_frame()` RTT. The transport's echo probes are the sole source of latency samples.

### DeviceBackend ABC (vendor-agnostic discovery)

**File:** `src/dj_ledfx/devices/backend.py`

Auto-registering ABC for vendor backends:

```python
class DeviceBackend(ABC):
    _registry: ClassVar[list[type[DeviceBackend]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            DeviceBackend._registry.append(cls)

    @abstractmethod
    async def discover(self, config: AppConfig) -> list[tuple[DeviceAdapter, LatencyTracker, int]]:
        """Returns list of (adapter, tracker, max_fps) tuples."""
        ...

    @abstractmethod
    def is_enabled(self, config: AppConfig) -> bool:
        ...

    async def shutdown(self) -> None:
        """Clean up backend resources (e.g., shared transport). Default no-op."""
        pass

    @classmethod
    async def discover_all(cls, config: AppConfig) -> list[tuple[DeviceAdapter, LatencyTracker, int]]:
        results = []
        cls._instances = []
        for backend_cls in cls._registry:
            backend = backend_cls()
            cls._instances.append(backend)
            if backend.is_enabled(config):
                results.extend(await backend.discover(config))
        return results

    @classmethod
    async def shutdown_all(cls) -> None:
        """Shut down all backend instances. Called from main.py after device_manager.disconnect_all()."""
        for backend in getattr(cls, '_instances', []):
            await backend.shutdown()
        cls._instances = []
```

Each backend creates its own LatencyTracker instances inside `discover()` using the config fields prefixed for that backend (e.g., `config.lifx_latency_strategy`, `config.openrgb_latency_strategy`). This is explicit coupling — each backend knows its config prefix.

**Implementations:**
- `LifxBackend` in `src/dj_ledfx/devices/lifx/discovery.py` — overrides `shutdown()` to call `LifxTransport.close()`
- `OpenRGBBackend` in `src/dj_ledfx/devices/openrgb_backend.py` (refactored from main.py) — `shutdown()` is no-op (adapters own their TCP connections)

**Note on connect() timing:** The "unconnected adapters" contract applies to LIFX (UDP, connectionless — connect() queries device metadata but doesn't establish a persistent connection). OpenRGB is different: `OpenRGBBackend.discover()` must call `adapter.connect()` internally during discovery because it needs the connected device's name for heuristic latency seeding and actual LED count. The integration loop in main.py should call `connect()` only on adapters where `not adapter.is_connected`. This is consistent — each backend handles its own connection semantics.

### LIFX Discovery Flow

**LifxDeviceRecord** (defined in `src/dj_ledfx/devices/lifx/discovery.py`):
```python
@dataclass(frozen=True, slots=True)
class LifxDeviceRecord:
    mac: bytes          # 6-byte MAC address
    ip: str             # device IP address (from UDP response source)
    port: int           # service port (from StateService)
    vendor: int         # vendor ID (1 = LIFX)
    product: int        # product ID (determines device type)
```

1. `LifxTransport.discover()` broadcasts GetService(2) with tagged=1, target=all-zeros
2. Collects StateService(3) responses for configurable timeout (~1s)
3. For each device, sends GetVersion(32) to get vendor/product IDs
4. Returns `list[LifxDeviceRecord]`
5. `LifxBackend.discover()` classifies by product ID:
   - Products with matrix zones capability -> LifxTileChainAdapter
   - Products with extended linear zones capability -> LifxStripAdapter
   - Everything else -> LifxBulbAdapter (safe default)
6. Creates appropriate adapter + LatencyTracker for each device

### Integration with main.py

Discovery collapses to:
```python
# Startup
devices = await DeviceBackend.discover_all(config)
for adapter, tracker, max_fps in devices:
    if not adapter.is_connected:
        await adapter.connect()
    device_manager.add_device(adapter, tracker, max_fps)

# Shutdown (after device_manager.disconnect_all())
await DeviceBackend.shutdown_all()  # closes shared resources like LifxTransport
```

Existing OpenRGB discovery moves from main.py to OpenRGBBackend. No changes to scheduler, effect engine, or ring buffer.

**Scheduler note:** The existing `LookaheadScheduler` takes a single `max_fps` parameter. With LIFX at 30fps and OpenRGB at 60fps, the per-device send loop's `_min_frame_interval` must become per-device. This requires two small changes:

1. **`ManagedDevice`** (in `devices/manager.py`) — add a `max_fps: int` field alongside `adapter` and `tracker`. Update `DeviceManager.add_device()` signature to accept `(adapter, tracker, max_fps)`.
2. **`LookaheadScheduler`** — remove the `max_fps` constructor parameter. In `_send_loop()`, compute `min_frame_interval = 1.0 / device.max_fps` per-device instead of using the current `self._min_frame_interval` scheduler-level field.

Each backend sets `max_fps` from its config (e.g., `config.lifx_max_fps`, `config.openrgb_max_fps`) when creating device tuples in `discover()`.

## Configuration

**New TOML section:**
```toml
[devices.lifx]
enabled = true
discovery_timeout_s = 1.0
default_kelvin = 3500
echo_probe_interval_s = 2.0
latency_strategy = "ema"
latency_ms = 50.0
manual_offset_ms = 0.0
max_fps = 30
latency_window_size = 60
```

**New AppConfig fields:**
```python
lifx_enabled: bool = True
lifx_discovery_timeout_s: float = 1.0
lifx_default_kelvin: int = 3500
lifx_echo_probe_interval_s: float = 2.0
lifx_latency_strategy: str = "ema"
lifx_latency_ms: float = 50.0
lifx_manual_offset_ms: float = 0.0
lifx_max_fps: int = 30
lifx_latency_window_size: int = 60
```

**max_fps defaults to 30:** WiFi RTT for SetTileState64 (558B) is ~10-20ms. At 60fps (16.6ms/frame) there's no headroom. 30fps (33ms) is smooth and sustainable.

**Validation rules** (enforced in `AppConfig.__post_init__`):
- `lifx_discovery_timeout_s > 0`
- `lifx_default_kelvin` in range 2500-9000
- `lifx_echo_probe_interval_s > 0`
- `lifx_latency_strategy` in `{"static", "ema", "windowed_mean"}`
- `lifx_latency_ms >= 0`
- `lifx_manual_offset_ms` — any float (can be negative for manual adjustment)
- `lifx_max_fps > 0`
- `lifx_latency_window_size > 0`

## File Structure

```
src/dj_ledfx/devices/
├── adapter.py              # DeviceAdapter ABC (existing, unchanged)
├── backend.py              # DeviceBackend ABC (NEW)
├── manager.py              # DeviceManager (existing, unchanged)
├── heuristics.py           # estimate_device_latency_ms (existing, unchanged)
├── openrgb.py              # OpenRGBAdapter (existing, unchanged)
├── openrgb_backend.py      # OpenRGBBackend (NEW — wraps existing discovery)
└── lifx/
    ├── __init__.py          # exports LifxBackend
    ├── transport.py         # LifxTransport
    ├── packet.py            # LifxPacket + RGB->HSBK conversion
    ├── discovery.py         # LifxBackend (DeviceBackend subclass)
    ├── bulb.py              # LifxBulbAdapter
    ├── strip.py             # LifxStripAdapter
    └── tile_chain.py        # LifxTileChainAdapter
```

**Test structure mirrors:**
```
tests/devices/
├── lifx/
│   ├── test_transport.py
│   ├── test_packet.py
│   ├── test_discovery.py
│   ├── test_bulb.py
│   ├── test_strip.py
│   └── test_tile_chain.py
├── test_backend.py
└── test_openrgb_backend.py
```

## Testing Strategy

### Unit Tests — Protocol Layer

- **test_packet.py** — Packet construction and parsing with known byte sequences. Verify header fields at correct offsets, little-endian encoding, HSBK conversion accuracy. Hex fixtures.
- **test_transport.py** — Mock UDP socket (asyncio.DatagramProtocol). Discovery broadcast, echo probe send/receive correlation, sequence wrapping at 255, response demuxing by source IP.

### Unit Tests — Adapters

- **test_bulb.py** — send_frame() with 1-LED array produces one SetColor packet with correct HSBK
- **test_strip.py** — send_frame() with N-zone array produces correct SetExtendedColorZones payload, zone count boundaries (<=82 per packet)
- **test_tile_chain.py** — send_frame() with 320-LED array splits into 5 SetTileState64 packets, each with 64 HSBK values, tile_index increments correctly

### Unit Tests — Discovery

- **test_discovery.py** — Mock transport returns fake device records with known product IDs, verify correct adapter type for each
- **test_backend.py** — __init_subclass__ auto-registration, discover_all() skips disabled backends, multiple backends coexist

### RGB->HSBK Conversion Tests

- Pure red (255,0,0) -> hue=0, sat=65535, bri=65535
- Pure white (255,255,255) -> sat=0, bri=65535, kelvin=default
- Black (0,0,0) -> bri=0
- Round-trip accuracy: RGB->HSBK->RGB within +/-1 per channel

### Integration Test

- BeatSimulator -> EffectEngine -> RingBuffer -> Scheduler -> mock LifxTransport
- Verify packets arrive at correct timing with correct content across all three adapter types simultaneously

## Performance Analysis

With 8 bulbs + 2 tile chains + strips = ~11 adapters:

- **Scheduler:** 11 async send loops, 11 FrameSlots — trivial for asyncio
- **UDP traffic:** ~400 packets/sec total — well within UDP capacity
- **Ring buffer:** 11 find_nearest() calls per frame, each scanning ~60 entries — sub-millisecond
- **RTT probing:** 11 EchoRequests every 2s = 5.5 packets/sec — negligible
- **Scales comfortably to 50+ devices**

## Future Considerations (out of scope)

- **Spatial mapping:** TileInfo metadata (user_x, user_y) stored now, used when spatial effects are implemented
- **Taichi matrix effects:** Per-pixel tile control is ready; Taichi integration would replace the numpy RGB->HSBK path with GPU-accelerated kernels
- **Logical bulb grouping:** Effect-layer concept — group bulbs to receive same color while maintaining per-device RTT
- **Govee backend:** Separate DeviceBackend subclass, same pattern
- **Periodic re-discovery:** Can be added to DeviceBackend.discover_all() as a background task later
