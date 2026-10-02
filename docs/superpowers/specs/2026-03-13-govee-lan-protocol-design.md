# Govee LAN Protocol Integration Design

## Overview

Direct integration with Govee RGBIC devices over the Govee LAN UDP protocol, supporting both whole-device color control (`colorwc`) and per-segment color control (razer, Govee's DreamView protocol; `ptReal` BLE-over-LAN until the light-output fixes). Uses shared transport + typed adapter architecture mirroring the existing LIFX pattern. Fully automatic multicast discovery with SKU-based capability detection.

> **Amended 2026-10-01** by [the light-output plan](../plans/2026-10-01-light-output-fixes.md) (the owner's ruling O2): per-segment colour goes by razer (DreamView) to UDP 4003, which sends no replies, instead of `ptReal`, which is removed; `colorwc` is the fallback, at most 10 a second; latency is a windowed median of one-way samples; a lamp that stops answering goes offline; each lamp can set its own output. The `ptReal` sections below are kept as the record of what was built first.

## Hardware Targets

- Govee H6076 RGBIC Corner Floor Lamp (RGBICW, ~15 segments, LAN API confirmed)
- Govee H61A2 RGBIC Neon Rope Light (RGBIC, ~15 segments, LAN API TBD)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Protocols | Core (`colorwc`) + Segment (razer, DreamView) | The owner's ruling O2 (light-output fixes): a razer frame carries one colour per segment and gets no reply. `ptReal` is removed. `colorwc`, at most 10 a second, is the fallback for a model without razer. The SKU registry says which models take razer, and `scripts/govee_razer_check.py` checks a lamp by eye. |
| Architecture | Shared transport + typed adapters | Mirrors LIFX pattern. Clean separation of concerns. Extensible for future adapter types. |
| Discovery | Fully automatic multicast | No manual IP config. Scan sent 3x at 1s intervals to handle UDP loss. |
| Segment detection | Lamp's own output + config override + SKU registry | A lamp's own output (its device row, set by `PUT /api/lights/{id}/output`) first, then the TOML config's segment override, then the SKU registry, which also says whether a model takes razer, its form and which end its first segment is at. Unknown SKU falls back to solid adapter. |
| Latency strategy | Windowed median of 9, seeded at 100 ms | One way: half of each `devStatus` round trip measured while frames stream. Same as LIFX. User can switch to ema, windowed_mean or static. |
| Transport abstraction | None | Transport is internal to Govee backend. No shared Transport ABC — YAGNI, protocols differ too much. |
| Default FPS cap | 30 by razer, 10 by `colorwc` | Measured: `colorwc` at 40 a second ran 9 commands behind, and may have hung two lamps for about ten minutes; at 10, 1 behind. The `colorwc` cap holds whatever the config says. |
| Reconnection | Ghosts and scans | A lamp that misses three status reads goes offline; a scan (every 30 s) brings it back. Setting a lamp's own output reconnects it. |
| Latency probing | The status reads' round trips | `supports_latency_probing = False` on both adapters. The transport times each `devStatus` query to its reply (connect, capture and the light monitor's reads all ask one) and hands the round trip to that lamp's LatencyTracker; there is no probe loop. `send_frame` is fire-and-forget UDP — timing it only measures local socket write, not device latency. |
| Auto power-on | No | `connect()` queries `devStatus` to verify reachability but does not send `turn(on)`. User controls power state via Govee app. |

## Govee LAN Protocol Summary

### Network Architecture

| Port | Direction | Protocol | Purpose |
|------|-----------|----------|---------|
| 4001 | Client → Multicast `239.255.255.250` | UDP | Device discovery scan |
| 4002 | Device → Client (unicast) | UDP | Responses (scan, devStatus) |
| 4003 | Client → Device IP (unicast) | UDP | Control commands |

All communication is JSON-serialized UDP datagrams. No TCP. No acknowledgments on control commands (fire-and-forget).

### Discovery Protocol

**Scan request** (sent to multicast `239.255.255.250:4001`):
```json
{"msg":{"cmd":"scan","data":{"account_topic":"reserve"}}}
```

**Scan response** (received on port 4002):
```json
{
  "msg":{
    "cmd":"scan",
    "data":{
      "ip":"192.168.1.23",
      "device":"1F:80:C5:32:32:36:72:4E",
      "sku":"H6076",
      "bleVersionHard":"3.01.01",
      "bleVersionSoft":"1.03.01",
      "wifiVersionHard":"1.00.10",
      "wifiVersionSoft":"1.02.03"
    }
  }
}
```

### Standard Control Commands (sent to device IP on port 4003)

**Power on/off:**
```json
{"msg":{"cmd":"turn","data":{"value":1}}}
```
Value: 0 (off) or 1 (on).

**Brightness:**
```json
{"msg":{"cmd":"brightness","data":{"value":50}}}
```
Value: 1-100 (percentage).

**Solid color:**
```json
{"msg":{"cmd":"colorwc","data":{"color":{"r":255,"g":0,"b":0},"colorTemInKelvin":0}}}
```
RGB: 0-255 each. If `colorTemInKelvin` is non-zero, device converts temperature to RGB and ignores the color field.

**Device status query:**
```json
{"msg":{"cmd":"devStatus","data":{}}}
```

**Status response** (received on port 4002):
```json
{"msg":{"cmd":"devStatus","data":{"onOff":1,"brightness":100,"color":{"r":255,"g":0,"b":0},"colorTemInKelvin":0}}}
```

### Per-Segment Control via ptReal (BLE-over-LAN)

> Removed by the light-output fixes: razer replaced it. Kept as the record of what was built first.

BLE commands are base64-encoded and sent over LAN UDP:

```json
{"msg":{"cmd":"ptReal","data":{"command":["base64_packet_1","base64_packet_2"]}}}
```

Multiple BLE packets can be batched in a single `command` array — one UDP send per frame.

#### BLE Packet Format (20 bytes)

| Byte | Field | Value |
|------|-------|-------|
| 0 | Identifier | `0x33` (always) |
| 1 | Command domain | `0x05` (LED control) |
| 2 | Sub-command | `0x0B` (segment color) |
| 3-5 | R, G, B | 0x00-0xFF each |
| 6-7 | Reserved | `0x00, 0x00` |
| 8 | Left segment mask | Bitmask for segments 1-8 |
| 9 | Right segment mask | Bitmask for segments 9-15 |
| 10-18 | Padding | `0x00` |
| 19 | Checksum | XOR of bytes 0-18 |

All segments selected: LEFT=`0xFF`, RIGHT=`0x7F`.

#### XOR Checksum

```
checksum = byte[0] ^ byte[1] ^ byte[2] ^ ... ^ byte[18]
```

#### Segment Mask Encoding

Segments are 0-indexed. Each segment maps to a bit in a little-endian bitmask:
- Segments 0-7 → byte 8 (LEFT), bits 0-7
- Segments 8-14 → byte 9 (RIGHT), bits 0-6

Example: segment 0 only → LEFT=`0x01`, RIGHT=`0x00`.

### Packet Size Analysis

| Scenario | Payload | Total JSON | Within MTU? |
|----------|---------|------------|-------------|
| Solid color (`colorwc`) | ~80 bytes | ~80 bytes | Yes |
| 15-segment ptReal | 15 × 28B base64 | ~800 bytes | Yes (MTU 1472) |
| 255-segment razer frame | 772 bytes, 1032 as base64 | ~1.1 KB | Yes (MTU 1472) |
| devStatus query | ~50 bytes | ~50 bytes | Yes |

## File Layout

```
src/dj_ledfx/devices/govee/
├── __init__.py          # Exports GoveeBackend (triggers auto-registration)
├── types.py             # GoveeDeviceRecord, GoveeDeviceCapability dataclasses
├── transport.py         # GoveeTransport — UDP socket management, discovery, probing
├── protocol.py          # Pure functions: razer frames, base64, checksums, JSON builders
├── solid.py             # GoveeSolidAdapter — whole-device color via colorwc
├── segment.py           # GoveeSegmentAdapter — per-segment color via razer
├── output.py            # GoveeOutput (a lamp's own output), lamp_plan(), lamp_fps()
├── sku_registry.py      # SKU → capability lookup (imports types from types.py)
└── backend.py           # GoveeBackend(DeviceBackend) — discovery orchestration

tests/devices/govee/
├── test_protocol.py     # Razer frames, checksum, base64 (pure function tests)
├── test_transport.py    # UDP socket mocking, discovery flow
├── test_solid.py        # Solid adapter send_frame
├── test_segment.py      # Segment adapter: razer frames, one colour
├── test_output.py       # Lamp plans, rates and stored outputs
├── test_sku_registry.py # SKU lookups, defaults, unknown SKUs
└── test_backend.py      # Backend discovery → adapter creation
```

## Component Designs

### Govee Types (`types.py`)

Shared dataclasses used across the Govee subpackage.

```python
@dataclass(frozen=True)
class GoveeDeviceRecord:
    ip: str                # Device LAN IP
    device_id: str         # Unique ID "1F:80:C5:32:32:36:72:4E"
    sku: str               # Model number "H6076"
    wifi_version: str      # WiFi firmware version
    ble_version: str       # BLE firmware version (for future BLE fallback)

@dataclass(frozen=True)
class GoveeDeviceCapability:
    is_rgbic: bool
    segment_count: int     # 0 for non-RGBIC
```

### GoveeTransport

Shared UDP socket manager — one instance owns all Govee network I/O.

```python
class GoveeTransport:
    async def open(self) -> None
    async def close(self) -> None
    async def discover(self, timeout_s: float = 5.0) -> list[GoveeDeviceRecord]
    async def send_command(self, ip: str, payload: dict) -> None
    async def query_status(self, ip: str, timeout_s: float = 2.0) -> dict | None
    def register_device(self, record: GoveeDeviceRecord, rtt_callback: Callable[[float], None]) -> None
```

- Binds receiver socket on port 4002 for responses.
- Sends discovery to multicast `239.255.255.250:4001`. Sends scan 3 times at 1s intervals to handle UDP loss. Deduplicates responses by `device_id`.
- `send_command()` JSON-serializes and sends UDP to `ip:4003`. Fire-and-forget.
- `query_status()` sends devStatus and awaits the reply on 4002, with a timeout; queries to one lamp that overlap share one query and its reply. Connect, capture and the light monitor's reads use it.
- Response routing: incoming JSON on port 4002 is dispatched via a `dict[str, Callable]` handler registry keyed by `cmd` field — `"scan"` routes to discovery handler, `"devStatus"` routes to status handler (the pending query, whose round trip goes to the lamp's callback). This avoids the LIFX transport's handler-swap pattern which is non-reentrant.
- `register_device()` names a lamp's `rtt_callback`, which gets the round trip of each status query matched to its reply, in milliseconds.
- All socket ops use `asyncio.DatagramProtocol` — no blocking.

### Protocol Module (pure functions)

Zero I/O. All packet encoding: razer frames and the JSON commands.

```python
def xor_checksum(data: bytes) -> int
def build_razer_switch(on: bool) -> dict
def build_razer_frame(colors: NDArray[np.uint8]) -> dict  # 1 to 255 segments
def build_solid_color_message(r: int, g: int, b: int) -> dict
def build_brightness_message(value: int) -> dict
def build_turn_message(on: bool) -> dict
def build_scan_message() -> dict
def build_status_query() -> dict
```

- `build_razer_frame()` packs a header, the segment count, one RGB triple per segment and an XOR checksum, base64-encoded; `build_razer_switch()` turns razer on or off.
- The light-output fixes removed `ptReal`'s builders (`build_ble_packet`, `encode_segment_mask`, `build_segment_color_packet`, `build_pt_real_message`) and `map_colors_to_segments()`: a lamp's frame already has one colour per segment.

### GoveeSolidAdapter

For non-RGBIC devices. Whole-device color via `colorwc`.

```python
class GoveeSolidAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord): ...

    # device_info: device_type="govee_solid", led_count=1
    # connect: queries devStatus to verify reachability (does NOT send turn-on)
    # disconnect: sets is_connected=False (UDP is connectionless)
    # send_frame: takes first pixel color, sends colorwc message via transport
```

### GoveeSegmentAdapter

For RGBIC devices. Per-segment color via razer, or one colour by `colorwc` for a model without it (its `LampPlan`).

```python
class GoveeSegmentAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord, num_segments: int): ...

    # device_info: device_type="govee_segment", led_count=num_segments
    # connect: queries devStatus to verify reachability (does NOT send turn-on)
    # disconnect: sets is_connected=False
    # send_frame:
    #   1. The frame has one colour per segment (led_count is the segment count)
    #   2. Razer: razer on before the first frame and after 2 s without one, then
    #      one razer frame (an RGB triple per segment, XOR checksum) to port 4003
    #   3. One colour: the frame's average as one colorwc command
```

### SKU Registry

```python
# GoveeDeviceCapability imported from types.py

SKU_REGISTRY: dict[str, GoveeDeviceCapability] = {
    "H6076": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
    "H61A2": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
}

DEFAULT_CAPABILITY = GoveeDeviceCapability(is_rgbic=False, segment_count=0)

def get_device_capability(sku: str) -> GoveeDeviceCapability
def get_segment_count(sku: str, config_override: int | None = None) -> int
```

- Exact match first, then falls back to `DEFAULT_CAPABILITY` for unknown SKUs.
- `config_override` wins over registry when set.

### GoveeBackend

```python
class GoveeBackend(DeviceBackend):
    def is_enabled(self, config: AppConfig) -> bool
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]
    async def shutdown(self) -> None
        # Closes the transport
```

Discovery flow:
1. Create and open `GoveeTransport`.
2. Run multicast discovery, collect `GoveeDeviceRecord` list.
3. For each record:
   - Look up SKU capability, choose adapter type (segment or solid).
   - Connect adapter (devStatus reachability check).
   - Create `LatencyTracker` (windowed median, seeded at 100 ms one way).
   - Register the lamp with the transport, so its status reads' round trips feed the tracker: `transport.register_device(record, rtt_callback=tracker.update_rtt)`.
   - Wrap in `DiscoveredDevice`.
4. Return all successfully connected devices. Log and skip failures.

Auto-registered via `DeviceBackend.__init_subclass__()`. The `govee/__init__.py` must re-export `GoveeBackend` using explicit `as` syntax (`from .backend import GoveeBackend as GoveeBackend`) for ruff F401 compliance. The parent `devices/__init__.py` must import `dj_ledfx.devices.govee` to trigger registration.

### Config Additions

```python
# In AppConfig:
govee_enabled: bool = True
govee_discovery_timeout_s: float = 5.0
govee_latency_strategy: str = "windowed_median"
govee_latency_ms: float = 100.0
govee_manual_offset_ms: float = 0.0
govee_max_fps: int = 30  # razer; colorwc is capped at 10 whatever this says
govee_latency_window_size: int = 9
govee_probe_interval_s: float = 5.0  # unread: round trips come from the status reads; kept so configs that carry it load
govee_segment_override: int | None = None
```

TOML section: `[devices.govee]`.

**Validation** (in `AppConfig.__post_init__`, matching existing backend patterns):
- `govee_max_fps > 0`
- `govee_latency_strategy in {"static", "ema", "windowed_mean", "windowed_median"}`
- `govee_discovery_timeout_s > 0`
- `govee_latency_ms >= 0`
- `govee_latency_window_size > 0`

**TOML key mapping** (in `load_config()`, under `raw["devices"]["govee"]`):
- `enabled` → `govee_enabled`
- `discovery_timeout_s` → `govee_discovery_timeout_s`
- `latency_strategy` → `govee_latency_strategy`
- `latency_ms` → `govee_latency_ms`
- `manual_offset_ms` → `govee_manual_offset_ms`
- `max_fps` → `govee_max_fps`
- `latency_window_size` → `govee_latency_window_size`
- `probe_interval_s` → `govee_probe_interval_s` (unread)
- `segment_override` → `govee_segment_override`

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No devices found during discovery | Log warning, return empty list. App runs with other backends. |
| Individual device fails connect | Log error, skip device, continue with others. |
| UDP packet loss during scan | Mitigated by 3x scan at 1s intervals. |
| send_frame socket error | Set `is_connected = False`, log warning. Scheduler stops sending. |
| Device goes offline mid-session | Its status reads go unanswered: three missed reads (about 15 s) take it offline (a read asks twice, and a lamp heard from since its last read hasn't missed it), and it gets no frames until a scan finds it. While another program holds UDP 4002 no reply arrives at all, so this can't be told and frames keep going. |
| Razer frame exceeds MTU | Not possible — at most 255 segments: 772 bytes, about 1.1 KB as base64 in JSON, within the 1472-byte MTU. |
| Unknown SKU discovered | Falls back to solid adapter with colorwc. Logs suggestion to set segment_override. |

## Testing Strategy

| Test file | Scope | Approach |
|-----------|-------|----------|
| `test_protocol.py` | Razer frames and switches, checksums, base64, JSON builders | Pure function tests. No mocking. Verify known byte sequences from reverse-engineering docs. |
| `test_transport.py` | UDP socket operations, discovery flow, response parsing | Mock `asyncio.DatagramProtocol`. Verify multicast target, port numbers, JSON serialization. |
| `test_solid.py` | Solid adapter send_frame, connect/disconnect | Mock transport. Verify colorwc message format, first-pixel extraction. |
| `test_segment.py` | Segment adapter: razer frames and arming, one colour | Mock transport. Verify razer on and off, frame bytes, the colour fallback. |
| `test_output.py` | Lamp plans, rates and stored outputs | Pure logic. Razer or one colour, segment counts, the colour cap, a stored output read as far as it can be used. |
| `test_sku_registry.py` | SKU lookups, defaults, config overrides | Pure logic. Test known SKUs, unknown SKUs, override precedence. |
| `test_backend.py` | Discovery → adapter creation, config-driven behavior | Mock transport discovery. Verify adapter type selection, latency strategy, FPS cap. |

## Future Extensions (Out of Scope)

- **Razer/DreamView protocol** (`cmd:"razer"`): built by the light-output fixes, in `GoveeSegmentAdapter` rather than a third adapter type, one colour per segment.
- **Reconnection logic**: built: a lamp back from a drop-out rejoins at the next scan, and setting a lamp's own output reconnects it.
- **Per-device config overrides**: a lamp's own output (razer or one colour, and a segment count) is built, kept in its device row; per-device FPS caps and latency strategies are not.
- **BLE fallback**: Direct Bluetooth control for devices without LAN API support.
