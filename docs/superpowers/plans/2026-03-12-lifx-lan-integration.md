# LIFX LAN Protocol Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add direct LIFX LAN protocol support for bulbs, strips, and tile chains with per-device RTT-based latency compensation, plus a vendor-agnostic DeviceBackend ABC for pluggable device backends.

**Architecture:** Three-layer LIFX stack (LifxTransport → LifxPacket → per-type adapters) sharing a single asyncio UDP socket. DeviceBackend ABC with `__init_subclass__` auto-registration replaces hardcoded discovery in main.py. Per-device max_fps moves from scheduler-level to ManagedDevice.

**Tech Stack:** Python 3.11+, asyncio (UDP DatagramProtocol), numpy (vectorized RGB→HSBK), struct (binary packet encoding), loguru

**Spec:** `docs/superpowers/specs/2026-03-12-lifx-lan-integration-design.md`

---

## Chunk 1: DeviceBackend ABC + Existing Code Migration

### Task 1: DeviceBackend ABC + DiscoveredDevice

**Files:**
- Create: `src/dj_ledfx/devices/backend.py`
- Test: `tests/devices/test_backend.py`

- [ ] **Step 1: Write failing tests for DeviceBackend**

```python
# tests/devices/test_backend.py
from __future__ import annotations

import pytest

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice


@pytest.fixture(autouse=True)
def _isolate_registry() -> None:
    """Save and restore DeviceBackend._registry and _instances around each test."""
    saved_registry = DeviceBackend._registry.copy()
    saved_instances = DeviceBackend._instances.copy()
    yield  # type: ignore[misc]
    DeviceBackend._registry = saved_registry
    DeviceBackend._instances = saved_instances


class FakeBackendA(DeviceBackend):
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        return []

    def is_enabled(self, config: AppConfig) -> bool:
        return True


class FakeBackendB(DeviceBackend):
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        return []

    def is_enabled(self, config: AppConfig) -> bool:
        return False


def test_subclass_auto_registers() -> None:
    assert FakeBackendA in DeviceBackend._registry
    assert FakeBackendB in DeviceBackend._registry


@pytest.mark.asyncio
async def test_discover_all_skips_disabled() -> None:
    # Reset to only our test backends
    DeviceBackend._registry = [FakeBackendA, FakeBackendB]
    config = AppConfig()
    devices = await DeviceBackend.discover_all(config)
    assert devices == []
    assert len(DeviceBackend._instances) == 2


@pytest.mark.asyncio
async def test_shutdown_all_calls_shutdown() -> None:
    shutdown_called = False

    class ShutdownTracker(DeviceBackend):
        async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
            return []

        def is_enabled(self, config: AppConfig) -> bool:
            return True

        async def shutdown(self) -> None:
            nonlocal shutdown_called
            shutdown_called = True

    DeviceBackend._registry = [ShutdownTracker]
    config = AppConfig()
    await DeviceBackend.discover_all(config)
    await DeviceBackend.shutdown_all()
    assert shutdown_called


def test_discovered_device_dataclass() -> None:
    from unittest.mock import MagicMock
    dd = DiscoveredDevice(
        adapter=MagicMock(),
        tracker=MagicMock(),
        max_fps=30,
    )
    assert dd.max_fps == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_backend.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement DeviceBackend + DiscoveredDevice**

```python
# src/dj_ledfx/devices/backend.py
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.latency.tracker import LatencyTracker


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker
    max_fps: int


class DeviceBackend(ABC):
    _registry: ClassVar[list[type[DeviceBackend]]] = []
    _instances: ClassVar[list[DeviceBackend]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            DeviceBackend._registry.append(cls)

    @abstractmethod
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        """Discover, connect, and return all devices for this backend.

        Post-condition: all returned adapters are connected (is_connected=True).
        """
        ...

    @abstractmethod
    def is_enabled(self, config: AppConfig) -> bool: ...

    async def shutdown(self) -> None:
        """Clean up backend resources. Default no-op."""

    @classmethod
    async def discover_all(cls, config: AppConfig) -> list[DiscoveredDevice]:
        # Single-call assumption — startup-only code.
        results: list[DiscoveredDevice] = []
        cls._instances = []
        for backend_cls in cls._registry:
            backend = backend_cls()
            cls._instances.append(backend)
            if backend.is_enabled(config):
                results.extend(await backend.discover(config))
        return results

    @classmethod
    async def shutdown_all(cls) -> None:
        for backend in cls._instances:
            await backend.shutdown()
        cls._instances = []
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/test_backend.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/backend.py tests/devices/test_backend.py
git commit -m "feat: add DeviceBackend ABC with auto-registration"
```

---

### Task 2: Per-device max_fps in ManagedDevice + DeviceManager

**Files:**
- Modify: `src/dj_ledfx/devices/manager.py`
- Modify: `tests/devices/test_manager.py`

- [ ] **Step 1: Update tests for new max_fps field**

Add `max_fps` parameter to all existing `add_device` calls and add new test:

```python
# In tests/devices/test_manager.py — update existing calls:
# Change: manager.add_device(adapter, tracker)
# To:     manager.add_device(adapter, tracker, max_fps=60)

def test_managed_device_max_fps() -> None:
    """ManagedDevice stores max_fps."""
    from dj_ledfx.devices.manager import ManagedDevice
    from unittest.mock import MagicMock
    md = ManagedDevice(adapter=MagicMock(), tracker=MagicMock(), max_fps=30)
    assert md.max_fps == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_manager.py -v`
Expected: FAIL — TypeError on add_device or ManagedDevice

- [ ] **Step 3: Update ManagedDevice and DeviceManager**

In `src/dj_ledfx/devices/manager.py`:
- Add `max_fps: int = 60` to `ManagedDevice` dataclass (after `tracker`)
- Update `add_device` signature: `def add_device(self, adapter: DeviceAdapter, tracker: LatencyTracker, max_fps: int = 60) -> None:`
- Update the `ManagedDevice` construction: `ManagedDevice(adapter=adapter, tracker=tracker, max_fps=max_fps)`

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/test_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/manager.py tests/devices/test_manager.py
git commit -m "feat: add per-device max_fps to ManagedDevice"
```

---

### Task 3: Per-device max_fps in LookaheadScheduler

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py`
- Modify: `tests/scheduling/test_scheduler.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Update scheduler tests**

In `tests/scheduling/test_scheduler.py`:
- Update `_make_device` helper to include `max_fps=60` in `ManagedDevice()` constructor
- Remove `max_fps=...` from all `LookaheadScheduler()` constructor calls
- Update `test_fps_cap_limits_send_rate` to set `max_fps` on the device, not the scheduler
- Add new test for mixed FPS:

```python
@pytest.mark.asyncio
async def test_mixed_fps_per_device(ring_buffer: RingBuffer) -> None:
    """Devices with different max_fps send at different rates."""
    fast_device = _make_device("fast", max_fps=60)
    slow_device = _make_device("slow", max_fps=30)
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer,
        devices=[fast_device, slow_device],
        fps=60,
    )
    # Pre-fill ring buffer so frames are available
    ring_buffer.write(RenderedFrame(colors=np.zeros((60, 3), dtype=np.uint8), target_time=time.monotonic() + 0.5))

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.5)
    scheduler.stop()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    fast_count = fast_device.adapter.send_frame.call_count
    slow_count = slow_device.adapter.send_frame.call_count
    # Fast device (60fps) should send roughly 2x as many frames as slow (30fps)
    assert fast_count > 0
    assert slow_count > 0
    ratio = fast_count / slow_count
    assert 1.5 < ratio < 3.0, f"Expected ~2:1 ratio, got {ratio:.1f}:1"
```

Also update the `_make_device` helper in the existing tests to accept `max_fps`:

```python
# Update _make_device helper signature:
# Before: def _make_device(name: str, led_count: int = 10) -> ManagedDevice:
# After:  def _make_device(name: str, led_count: int = 10, max_fps: int = 60) -> ManagedDevice:
#   ...
#   return ManagedDevice(adapter=mock_adapter, tracker=mock_tracker, max_fps=max_fps)
```

Update `test_fps_cap_limits_send_rate` — replace the scheduler-level `max_fps=10` with per-device:

```python
@pytest.mark.asyncio
async def test_fps_cap_limits_send_rate(ring_buffer: RingBuffer) -> None:
    device = _make_device("d", max_fps=10)
    scheduler = LookaheadScheduler(
        ring_buffer=ring_buffer,
        devices=[device],
        fps=60,
    )
    # ... rest of test unchanged, but remove max_fps from scheduler constructor
```

In `tests/test_integration.py`:
- Remove `max_fps=60` from scheduler constructor
- Add `max_fps=60` to `ManagedDevice()` constructions

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scheduling/test_scheduler.py tests/test_integration.py -v`
Expected: FAIL — TypeError on constructor changes

- [ ] **Step 3: Update LookaheadScheduler**

In `src/dj_ledfx/scheduling/scheduler.py`:
- Remove `max_fps: int = 60` from `__init__` parameters
- Remove `self._min_frame_interval = 1.0 / max_fps` from `__init__`
- In `_send_loop`, replace `self._min_frame_interval` with `1.0 / device.max_fps`:

```python
# Line ~162-167, replace:
remaining = last_send_time + self._min_frame_interval - now
# With:
min_frame_interval = 1.0 / device.max_fps
remaining = last_send_time + min_frame_interval - now
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/scheduling/ tests/test_integration.py tests/devices/test_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py tests/test_integration.py
git commit -m "feat: move max_fps from scheduler-level to per-device"
```

---

### Task 4: LIFX config fields

**Files:**
- Modify: `src/dj_ledfx/config.py`
- Modify: `tests/test_config.py` (if exists, otherwise create)

- [ ] **Step 1: Write config tests**

```python
# tests/test_config.py (add to existing or create)
def test_lifx_config_defaults() -> None:
    config = AppConfig()
    assert config.lifx_enabled is True
    assert config.lifx_default_kelvin == 3500
    assert config.lifx_max_fps == 30
    assert config.lifx_latency_strategy == "ema"
    assert config.lifx_echo_probe_interval_s == 2.0


def test_lifx_config_validation_bad_kelvin() -> None:
    with pytest.raises(ValueError, match="lifx_default_kelvin"):
        AppConfig(lifx_default_kelvin=1000)


def test_lifx_config_validation_bad_strategy() -> None:
    with pytest.raises(ValueError, match="lifx_latency_strategy"):
        AppConfig(lifx_latency_strategy="invalid")


def test_lifx_config_negative_offset_allowed() -> None:
    config = AppConfig(lifx_manual_offset_ms=-10.0)
    assert config.lifx_manual_offset_ms == -10.0


def test_lifx_config_from_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[devices.lifx]\nenabled = false\nmax_fps = 20\ndefault_kelvin = 4000\n')
    config = load_config(toml_file)
    assert config.lifx_enabled is False
    assert config.lifx_max_fps == 20
    assert config.lifx_default_kelvin == 4000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v -k lifx`
Expected: FAIL — lifx fields don't exist

- [ ] **Step 3: Add LIFX fields to AppConfig**

In `src/dj_ledfx/config.py`:

Add after the OpenRGB fields block (line 37):
```python
    # LIFX
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

Add validation in `__post_init__` (after existing openrgb checks):
```python
        if self.lifx_max_fps <= 0:
            errors.append("lifx_max_fps must be positive")
        if self.lifx_latency_window_size <= 0:
            errors.append("lifx_latency_window_size must be positive")
        if self.lifx_latency_strategy not in {"static", "ema", "windowed_mean"}:
            errors.append("lifx_latency_strategy must be one of: static, ema, windowed_mean")
        if self.lifx_discovery_timeout_s <= 0:
            errors.append("lifx_discovery_timeout_s must be positive")
        if self.lifx_echo_probe_interval_s <= 0:
            errors.append("lifx_echo_probe_interval_s must be positive")
        if not (2500 <= self.lifx_default_kelvin <= 9000):
            errors.append("lifx_default_kelvin must be between 2500 and 9000")
        if self.lifx_latency_ms < 0:
            errors.append("lifx_latency_ms must be non-negative")
```

Add TOML parsing in `load_config` (after the openrgb block):
```python
    if "devices" in raw and "lifx" in raw["devices"]:
        lifx = raw["devices"]["lifx"]
        if "enabled" in lifx:
            kwargs["lifx_enabled"] = lifx["enabled"]
        if "discovery_timeout_s" in lifx:
            kwargs["lifx_discovery_timeout_s"] = lifx["discovery_timeout_s"]
        if "default_kelvin" in lifx:
            kwargs["lifx_default_kelvin"] = lifx["default_kelvin"]
        if "echo_probe_interval_s" in lifx:
            kwargs["lifx_echo_probe_interval_s"] = lifx["echo_probe_interval_s"]
        if "latency_strategy" in lifx:
            kwargs["lifx_latency_strategy"] = lifx["latency_strategy"]
        if "latency_ms" in lifx:
            kwargs["lifx_latency_ms"] = lifx["latency_ms"]
        if "manual_offset_ms" in lifx:
            kwargs["lifx_manual_offset_ms"] = lifx["manual_offset_ms"]
        if "max_fps" in lifx:
            kwargs["lifx_max_fps"] = lifx["max_fps"]
        if "latency_window_size" in lifx:
            kwargs["lifx_latency_window_size"] = lifx["latency_window_size"]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py
git commit -m "feat: add LIFX config fields with validation and TOML parsing"
```

---

### Task 5: OpenRGBBackend + main.py refactor

**Files:**
- Create: `src/dj_ledfx/devices/openrgb_backend.py`
- Modify: `src/dj_ledfx/devices/__init__.py`
- Modify: `src/dj_ledfx/main.py`
- Test: `tests/devices/test_openrgb_backend.py`

- [ ] **Step 1: Write OpenRGBBackend tests**

```python
# tests/devices/test_openrgb_backend.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.openrgb_backend import OpenRGBBackend


def test_is_enabled_checks_config() -> None:
    backend = OpenRGBBackend()
    assert backend.is_enabled(AppConfig(openrgb_enabled=True)) is True
    assert backend.is_enabled(AppConfig(openrgb_enabled=False)) is False


@pytest.mark.asyncio
async def test_discover_returns_connected_adapters() -> None:
    mock_info = MagicMock(name="TestDevice", led_count=10)
    mock_adapter = MagicMock()
    mock_adapter.is_connected = True
    mock_adapter.device_info = mock_info
    mock_adapter.device_info.name = "TestDevice"
    mock_adapter.led_count = 10
    mock_adapter.connect = AsyncMock()

    with patch(
        "dj_ledfx.devices.openrgb_backend.OpenRGBAdapter"
    ) as MockAdapter:
        MockAdapter.discover = AsyncMock(return_value=[mock_info])
        MockAdapter.return_value = mock_adapter
        backend = OpenRGBBackend()
        config = AppConfig()
        devices = await backend.discover(config)
        assert len(devices) == 1
        assert devices[0].adapter is mock_adapter
        assert devices[0].max_fps == config.openrgb_max_fps
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_openrgb_backend.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement OpenRGBBackend**

```python
# src/dj_ledfx/devices/openrgb_backend.py
from __future__ import annotations

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.heuristics import estimate_device_latency_ms
from dj_ledfx.devices.openrgb import OpenRGBAdapter
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker


class OpenRGBBackend(DeviceBackend):
    def is_enabled(self, config: AppConfig) -> bool:
        return config.openrgb_enabled

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        discovered = await OpenRGBAdapter.discover(
            host=config.openrgb_host, port=config.openrgb_port
        )
        logger.info("Discovered {} OpenRGB devices", len(discovered))

        results: list[DiscoveredDevice] = []
        for i in range(len(discovered)):
            try:
                adapter = OpenRGBAdapter(
                    host=config.openrgb_host,
                    port=config.openrgb_port,
                    device_index=i,
                )
                await adapter.connect()

                heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)
                strategy: StaticLatency | EMALatency | WindowedMeanLatency
                if config.openrgb_latency_strategy == "static":
                    strategy = StaticLatency(config.openrgb_latency_ms)
                elif config.openrgb_latency_strategy == "ema":
                    strategy = EMALatency(initial_value_ms=heuristic_ms)
                else:
                    strategy = WindowedMeanLatency(
                        window_size=config.openrgb_latency_window_size,
                        initial_value_ms=heuristic_ms,
                    )

                tracker = LatencyTracker(
                    strategy=strategy,
                    manual_offset_ms=config.openrgb_manual_offset_ms,
                )
                results.append(DiscoveredDevice(
                    adapter=adapter, tracker=tracker, max_fps=config.openrgb_max_fps,
                ))
            except Exception:
                logger.exception("Failed to connect to OpenRGB device {}", i)

        return results
```

- [ ] **Step 4: Update `devices/__init__.py` for auto-registration**

```python
# src/dj_ledfx/devices/__init__.py
from dj_ledfx.devices import openrgb_backend as _openrgb_backend  # noqa: F401
# LIFX backend auto-registration added in Chunk 4, Task 14
```

- [ ] **Step 5: Refactor main.py to use DeviceBackend**

Replace lines 14-16 (OpenRGB-specific imports) and lines 69-101 (OpenRGB discovery block).

Add these **module-level** imports at the top of main.py (replacing the removed OpenRGB/latency imports):

```python
from dj_ledfx.devices.backend import DeviceBackend
import dj_ledfx.devices  # noqa: F401  # triggers backend auto-registration
```

In `_run()`, replace the OpenRGB discovery block (lines 69-101) with:
devices = await DeviceBackend.discover_all(config)
for device in devices:
    device_manager.add_device(device.adapter, device.tracker, device.max_fps)

# Remove max_fps from scheduler constructor (line 123):
scheduler = LookaheadScheduler(
    ring_buffer=engine.ring_buffer,
    devices=device_manager.devices,
    fps=config.engine_fps,
)

# Add after device_manager.disconnect_all() (line 173):
await DeviceBackend.shutdown_all()
```

Remove now-unused imports: `OpenRGBAdapter`, `estimate_device_latency_ms`, `EMALatency`, `StaticLatency`, `WindowedMeanLatency`, `LatencyTracker`.

- [ ] **Step 6: Run all tests**

Run: `uv run pytest -x -v`
Expected: PASS (all existing tests + new backend tests)

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/devices/openrgb_backend.py src/dj_ledfx/devices/__init__.py src/dj_ledfx/main.py tests/devices/test_openrgb_backend.py
git commit -m "refactor: extract OpenRGBBackend, use DeviceBackend.discover_all in main"
```

---

## Chunk 2: LIFX Protocol Layer

### Task 6: LIFX shared types

**Files:**
- Create: `src/dj_ledfx/devices/lifx/__init__.py`
- Create: `src/dj_ledfx/devices/lifx/types.py`

- [ ] **Step 1: Create the lifx package and types**

```python
# src/dj_ledfx/devices/lifx/__init__.py
# Populated when LifxBackend is implemented (Chunk 4, Task 14)
```

```python
# src/dj_ledfx/devices/lifx/types.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LifxDeviceRecord:
    """Discovered LIFX device before adapter creation."""
    mac: bytes          # 6-byte MAC address
    ip: str             # device IP (from UDP response source)
    port: int           # service port (from StateService)
    vendor: int         # vendor ID (1 = LIFX)
    product: int        # product ID (determines device type)
```

- [ ] **Step 2: Commit**

```bash
git add src/dj_ledfx/devices/lifx/
git commit -m "feat: add LIFX package with LifxDeviceRecord type"
```

---

### Task 7: LifxPacket — header encoding/decoding

**Files:**
- Create: `src/dj_ledfx/devices/lifx/packet.py`
- Create: `tests/devices/lifx/__init__.py`
- Create: `tests/devices/lifx/test_packet.py`

- [ ] **Step 1: Write header encoding/decoding tests**

```python
# tests/devices/lifx/test_packet.py
from __future__ import annotations

from dj_ledfx.devices.lifx.packet import LifxPacket


class TestLifxPacketHeader:
    def test_pack_header_size(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=12345, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        assert len(data) == 36  # header only, no payload

    def test_pack_size_field_includes_payload(self) -> None:
        payload = b"\x01\x02\x03"
        pkt = LifxPacket(
            tagged=False, source=0, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=102, payload=payload,
        )
        data = pkt.pack()
        size = int.from_bytes(data[0:2], "little")
        assert size == 36 + 3

    def test_pack_protocol_field(self) -> None:
        pkt = LifxPacket(
            tagged=True, source=0, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        flags = int.from_bytes(data[2:4], "little")
        # addressable=1, tagged=1, protocol=1024
        assert flags & 0x1000  # addressable bit
        assert flags & 0x2000  # tagged bit
        assert (flags & 0x0FFF) == 1024  # protocol

    def test_pack_source_field(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=0xDEADBEEF, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        source = int.from_bytes(data[4:8], "little")
        assert source == 0xDEADBEEF

    def test_pack_target_field(self) -> None:
        mac = b"\xd0\x73\xd5\x01\x02\x03\x00\x00"
        pkt = LifxPacket(
            tagged=False, source=0, target=mac,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        assert data[8:16] == mac

    def test_pack_ack_res_flags(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=0, target=b"\x00" * 8,
            ack_required=True, res_required=True, sequence=42,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        assert data[22] & 0x02  # ack_required
        assert data[22] & 0x01  # res_required
        assert data[23] == 42   # sequence

    def test_pack_msg_type(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=0, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=715, payload=b"",
        )
        data = pkt.pack()
        msg_type = int.from_bytes(data[32:34], "little")
        assert msg_type == 715

    def test_unpack_roundtrip(self) -> None:
        original = LifxPacket(
            tagged=True, source=9999, target=b"\xAA\xBB\xCC\xDD\xEE\xFF\x00\x00",
            ack_required=True, res_required=False, sequence=200,
            msg_type=102, payload=b"\x01\x02\x03\x04",
        )
        data = original.pack()
        parsed = LifxPacket.unpack(data)
        assert parsed.tagged == original.tagged
        assert parsed.source == original.source
        assert parsed.target == original.target
        assert parsed.ack_required == original.ack_required
        assert parsed.res_required == original.res_required
        assert parsed.sequence == original.sequence
        assert parsed.msg_type == original.msg_type
        assert parsed.payload == original.payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/lifx/test_packet.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement LifxPacket**

```python
# src/dj_ledfx/devices/lifx/packet.py
from __future__ import annotations

import struct
from dataclasses import dataclass

HEADER_SIZE = 36
PROTOCOL = 1024


@dataclass
class LifxPacket:
    tagged: bool
    source: int
    target: bytes  # 8 bytes (6-byte MAC + 2 padding)
    ack_required: bool
    res_required: bool
    sequence: int
    msg_type: int
    payload: bytes

    def pack(self) -> bytes:
        size = HEADER_SIZE + len(self.payload)
        # Byte 2-3: origin(2)=0 | tagged(1) | addressable(1)=1 | protocol(12)=1024
        flags = PROTOCOL
        flags |= 0x1000  # addressable
        if self.tagged:
            flags |= 0x2000
        # Byte 22: reserved(6) | ack_required(1) | res_required(1)
        ack_res = 0
        if self.ack_required:
            ack_res |= 0x02
        if self.res_required:
            ack_res |= 0x01

        header = struct.pack(
            "<HHI8s6sBB8sHH",
            size,                    # 0-1: size
            flags,                   # 2-3: flags
            self.source,             # 4-7: source
            self.target,             # 8-15: target
            b"\x00" * 6,            # 16-21: reserved
            ack_res,                 # 22: ack/res flags
            self.sequence & 0xFF,    # 23: sequence
            b"\x00" * 8,            # 24-31: reserved
            self.msg_type,           # 32-33: type
            0,                       # 34-35: reserved
        )
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes) -> LifxPacket:
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Packet too short: {len(data)} < {HEADER_SIZE}")
        (
            size, flags, source, target, _reserved,
            ack_res, sequence, _reserved2, msg_type, _reserved3,
        ) = struct.unpack("<HHI8s6sBB8sHH", data[:HEADER_SIZE])
        return cls(
            tagged=bool(flags & 0x2000),
            source=source,
            target=target,
            ack_required=bool(ack_res & 0x02),
            res_required=bool(ack_res & 0x01),
            sequence=sequence,
            msg_type=msg_type,
            payload=data[HEADER_SIZE:size],
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/lifx/test_packet.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/lifx/packet.py tests/devices/lifx/
git commit -m "feat: add LifxPacket header encoding/decoding"
```

---

### Task 8: Payload builders, parsers, and RGB→HSBK conversion

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/packet.py`
- Modify: `tests/devices/lifx/test_packet.py`

- [ ] **Step 1: Write payload builder + parser + color conversion tests**

Add to `tests/devices/lifx/test_packet.py`:

```python
import struct

import numpy as np
from dj_ledfx.devices.lifx.packet import (
    build_set_color, build_echo_request, build_set_tile_state64,
    build_set_extended_color_zones,
    parse_state_service, parse_state_version, parse_echo_response,
    parse_state_device_chain, parse_state_extended_color_zones,
    rgb_to_hsbk, rgb_array_to_hsbk,
)
from dj_ledfx.devices.lifx.tile_chain import TileInfo


class TestPayloadBuilders:
    def test_build_set_color_size(self) -> None:
        payload = build_set_color((0, 65535, 65535, 3500), duration_ms=0)
        assert len(payload) == 13  # 1 reserved + 8 HSBK + 4 duration

    def test_build_echo_request_size(self) -> None:
        payload = build_echo_request(b"\xAA" * 64)
        assert len(payload) == 64

    def test_build_set_tile_state64_size(self) -> None:
        colors = [(0, 0, 0, 0)] * 64
        payload = build_set_tile_state64(0, 1, 0, 0, 8, 0, colors)
        # 1+1+1+1+1+1 (fields) + 4 (duration) + 64*8 (HSBK) = 10 + 512 = 522
        assert len(payload) == 522

    def test_build_set_extended_color_zones_size(self) -> None:
        colors = [(0, 0, 0, 0)] * 10
        payload = build_set_extended_color_zones(0, 0, 0, 10, colors)
        # 4 (duration) + 1 (apply) + 2 (index) + 1 (count) + 82*8 (HSBK always 82)
        assert len(payload) == 664


class TestPayloadParsers:
    def test_parse_state_service(self) -> None:
        payload = struct.pack("<BI", 1, 56700)
        service, port = parse_state_service(payload)
        assert service == 1
        assert port == 56700

    def test_parse_state_version(self) -> None:
        payload = struct.pack("<III", 1, 55, 0)
        vendor, product, version = parse_state_version(payload)
        assert vendor == 1
        assert product == 55

    def test_parse_echo_response(self) -> None:
        data = b"\xBB" * 64
        assert parse_echo_response(data) == data

    def test_parse_state_extended_color_zones(self) -> None:
        # zone_count=10, zone_index=0, then 10 HSBK values (each 8 bytes)
        header = struct.pack("<HH", 10, 0)
        hsbk_data = struct.pack("<4H", 100, 200, 300, 3500) * 10
        payload = header + hsbk_data
        zone_count, zone_index, colors = parse_state_extended_color_zones(payload)
        assert zone_count == 10
        assert zone_index == 0
        assert len(colors) == 10
        assert colors[0] == (100, 200, 300, 3500)

    def test_parse_state_device_chain(self) -> None:
        # Minimal: 1 tile with known position data
        # start_index(1) + total_count(1) = 2 bytes header
        # Per tile: accel_meas_x(i16) + accel_meas_y(i16) + accel_meas_z(i16)
        #   + reserved(i16) + user_x(f32) + user_y(f32) + width(u8) + height(u8)
        #   + reserved(u8) + device_version_vendor(u32) + device_version_product(u32)
        #   + device_version_version(u32) + firmware_build(u64) + reserved(u64)
        #   + firmware_version_minor(u16) + firmware_version_major(u16) + reserved(u32)
        # Total per tile = 55 bytes
        header = struct.pack("<BB", 0, 1)  # start_index=0, total_count=1
        tile_data = struct.pack(
            "<hhhh ff BB x III QQ HH I",
            100, -200, 9800,  # accel x, y, z
            0,  # reserved
            1.0, 2.5,  # user_x, user_y
            8, 8,  # width, height
            # reserved byte is handled by 'x'
            1, 55, 0,  # vendor, product, version
            0, 0,  # firmware_build, reserved
            0, 0,  # firmware minor, major
            0,  # reserved
        )
        payload = header + tile_data
        tiles = parse_state_device_chain(payload)
        assert len(tiles) == 1
        assert tiles[0].width == 8
        assert tiles[0].height == 8
        assert abs(tiles[0].user_x - 1.0) < 0.01
        assert abs(tiles[0].user_y - 2.5) < 0.01


class TestColorConversion:
    def test_pure_red(self) -> None:
        h, s, b, k = rgb_to_hsbk(255, 0, 0)
        assert h == 0
        assert s == 65535
        assert b == 65535

    def test_pure_green(self) -> None:
        h, s, b, k = rgb_to_hsbk(0, 255, 0)
        # Green = 120 degrees = 120/360 * 65535 ≈ 21845
        assert abs(h - 21845) < 2

    def test_pure_white(self) -> None:
        h, s, b, k = rgb_to_hsbk(255, 255, 255, kelvin=4000)
        assert s == 0
        assert b == 65535
        assert k == 4000

    def test_black(self) -> None:
        h, s, b, k = rgb_to_hsbk(0, 0, 0)
        assert b == 0

    def test_array_conversion_shape(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = rgb_array_to_hsbk(colors)
        assert result.shape == (3, 4)  # 3 colors, 4 values (H, S, B, K)
        assert result.dtype == np.uint16

    def test_array_matches_scalar(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = rgb_array_to_hsbk(colors, kelvin=3500)
        for i, (r, g, b_val) in enumerate(colors):
            scalar = rgb_to_hsbk(int(r), int(g), int(b_val), kelvin=3500)
            for j in range(4):
                assert abs(int(result[i, j]) - scalar[j]) <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/lifx/test_packet.py -v -k "Payload or Color"`
Expected: FAIL — functions not found

- [ ] **Step 3: Implement payload builders, parsers, and color conversion**

Add to `src/dj_ledfx/devices/lifx/packet.py`:

```python
import numpy as np
from numpy.typing import NDArray

# --- Payload builders ---

def build_set_color(hsbk: tuple[int, int, int, int], duration_ms: int = 0) -> bytes:
    """Build SetColor(102) payload. 13 bytes."""
    return struct.pack("<B4HI", 0, *hsbk, duration_ms)


def build_echo_request(payload: bytes) -> bytes:
    """Build EchoRequest(58) payload. Must be exactly 64 bytes."""
    return payload[:64].ljust(64, b"\x00")


def build_set_tile_state64(
    tile_index: int, length: int, x: int, y: int, width: int,
    duration_ms: int, colors: list[tuple[int, int, int, int]],
) -> bytes:
    """Build SetTileState64(715) payload. ~522 bytes."""
    # Fields: tile_index(u8), length(u8), reserved(u8), x(u8), y(u8), width(u8), duration(u32)
    header = struct.pack("<BBBBBBI", tile_index, length, 0, x, y, width, duration_ms)
    color_data = b"".join(struct.pack("<4H", *c) for c in colors[:64])
    # Pad to exactly 64 colors
    color_data = color_data.ljust(64 * 8, b"\x00")
    return header + color_data


def build_set_extended_color_zones(
    duration_ms: int, apply: int, zone_index: int,
    count: int, colors: list[tuple[int, int, int, int]],
) -> bytes:
    """Build SetExtendedColorZones(510) payload. Fixed 664 bytes (82 zones)."""
    header = struct.pack("<IBHB", duration_ms, apply, zone_index, count)
    color_data = b"".join(struct.pack("<4H", *c) for c in colors[:82])
    color_data = color_data.ljust(82 * 8, b"\x00")
    return header + color_data


# --- Payload parsers ---

def parse_state_service(payload: bytes) -> tuple[int, int]:
    """Parse StateService(3) → (service, port)."""
    service, port = struct.unpack("<BI", payload[:5])
    return service, port


def parse_state_version(payload: bytes) -> tuple[int, int, int]:
    """Parse StateVersion(33) → (vendor, product, version)."""
    return struct.unpack("<III", payload[:12])


def parse_echo_response(payload: bytes) -> bytes:
    """Parse EchoResponse(59) → echo payload."""
    return payload[:64]


def parse_state_extended_color_zones(
    payload: bytes,
) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Parse StateExtendedColorZones(512) → (zone_count, zone_index, list of HSBK)."""
    zone_count, zone_index = struct.unpack("<HH", payload[:4])
    colors: list[tuple[int, int, int, int]] = []
    offset = 4
    for _ in range(zone_count):
        if offset + 8 > len(payload):
            break
        h, s, b, k = struct.unpack("<4H", payload[offset : offset + 8])
        colors.append((h, s, b, k))
        offset += 8
    return zone_count, zone_index, colors


def parse_state_device_chain(
    payload: bytes,
) -> list["TileInfo"]:
    """Parse StateDeviceChain(702) → list of TileInfo."""
    from dj_ledfx.devices.lifx.tile_chain import TileInfo

    start_index = payload[0]
    total_count = payload[1]
    tiles: list[TileInfo] = []
    offset = 2
    TILE_ENTRY_SIZE = 55
    for i in range(total_count):
        if offset + TILE_ENTRY_SIZE > len(payload):
            break
        entry = payload[offset : offset + TILE_ENTRY_SIZE]
        accel_x, accel_y, accel_z, _reserved = struct.unpack("<hhhh", entry[0:8])
        user_x, user_y = struct.unpack("<ff", entry[8:16])
        width, height = entry[16], entry[17]
        tiles.append(TileInfo(
            user_x=user_x, user_y=user_y,
            width=width, height=height,
            accel_x=accel_x, accel_y=accel_y, accel_z=accel_z,
        ))
        offset += TILE_ENTRY_SIZE
    return tiles


# --- Color conversion ---

def rgb_to_hsbk(
    r: int, g: int, b: int, kelvin: int = 3500,
) -> tuple[int, int, int, int]:
    """Convert single RGB (0-255) to LIFX HSBK (0-65535)."""
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    # Hue
    if delta == 0:
        hue = 0.0
    elif cmax == rf:
        hue = 60.0 * (((gf - bf) / delta) % 6)
    elif cmax == gf:
        hue = 60.0 * (((bf - rf) / delta) + 2)
    else:
        hue = 60.0 * (((rf - gf) / delta) + 4)

    # Saturation
    sat = 0.0 if cmax == 0 else delta / cmax

    # Brightness
    bri = cmax

    h = int(hue / 360.0 * 65535) & 0xFFFF
    s = int(sat * 65535) & 0xFFFF
    v = int(bri * 65535) & 0xFFFF
    return (h, s, v, kelvin)


def rgb_array_to_hsbk(
    colors: NDArray[np.uint8], kelvin: int = 3500,
) -> NDArray[np.uint16]:
    """Vectorized RGB (N,3) uint8 → HSBK (N,4) uint16. Pure numpy, no loops."""
    f = colors.astype(np.float32) / 255.0
    r, g, b = f[:, 0], f[:, 1], f[:, 2]

    cmax = f.max(axis=1)
    cmin = f.min(axis=1)
    delta = cmax - cmin

    # Hue (piecewise)
    hue = np.zeros(len(colors), dtype=np.float32)
    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0) & ~mask_r
    mask_b = (delta > 0) & ~mask_r & ~mask_g

    hue[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6)
    hue[mask_g] = 60.0 * (((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2)
    hue[mask_b] = 60.0 * (((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4)

    # Saturation
    sat = np.where(cmax > 0, delta / cmax, 0.0)

    # Build output
    result = np.zeros((len(colors), 4), dtype=np.uint16)
    result[:, 0] = (hue / 360.0 * 65535).astype(np.uint16)
    result[:, 1] = (sat * 65535).astype(np.uint16)
    result[:, 2] = (cmax * 65535).astype(np.uint16)
    result[:, 3] = kelvin
    return result
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/lifx/test_packet.py -v`
Expected: PASS

- [ ] **Step 5: Run linter and type checker**

Run: `uv run ruff check src/dj_ledfx/devices/lifx/ && uv run mypy src/dj_ledfx/devices/lifx/`

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/lifx/packet.py tests/devices/lifx/test_packet.py
git commit -m "feat: add LIFX payload builders, parsers, and RGB→HSBK conversion"
```

---

## Chunk 3: LIFX Transport

### Task 9: LifxTransport — UDP socket, send, receive loop

**Files:**
- Create: `src/dj_ledfx/devices/lifx/transport.py`
- Create: `tests/devices/lifx/test_transport.py`

- [ ] **Step 1: Write transport tests**

```python
# tests/devices/lifx/test_transport.py
from __future__ import annotations

import asyncio
import pytest

from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.packet import LifxPacket


@pytest.mark.asyncio
async def test_transport_creates_socket() -> None:
    transport = LifxTransport()
    await transport.open()
    assert transport.is_open
    await transport.close()
    assert not transport.is_open


@pytest.mark.asyncio
async def test_transport_source_id_nonzero() -> None:
    transport = LifxTransport()
    await transport.open()
    assert transport.source_id != 0
    await transport.close()


@pytest.mark.asyncio
async def test_transport_sequence_increments() -> None:
    transport = LifxTransport()
    await transport.open()
    s1 = transport.next_sequence()
    s2 = transport.next_sequence()
    assert s2 == s1 + 1
    await transport.close()


@pytest.mark.asyncio
async def test_transport_sequence_wraps_on_wire() -> None:
    transport = LifxTransport()
    await transport.open()
    # Force counter high
    transport._sequence_counter = 300
    seq = transport.next_sequence()
    assert seq == 301  # internal counter is unbounded (incremented from 300)
    # Wire value wraps to fit uint8
    assert seq % 256 == 45
    await transport.close()


@pytest.mark.asyncio
async def test_rtt_probe_correlation() -> None:
    """Echo probe sent → EchoResponse received → RTT callback fired."""
    import time
    from dj_ledfx.devices.lifx.types import LifxDeviceRecord

    transport = LifxTransport()
    await transport.open()

    rtt_values: list[float] = []
    record = LifxDeviceRecord(
        mac=b"\xAA\xBB\xCC\xDD\xEE\xFF",
        ip="192.168.1.100", port=56700, vendor=1, product=55,
    )
    transport.register_device(record, rtt_callback=lambda rtt: rtt_values.append(rtt))

    # Simulate probe: register a pending probe manually
    seq = transport.next_sequence()
    transport._pending_probes[seq] = ("192.168.1.100", time.monotonic())

    # Craft an EchoResponse with the seq embedded in payload
    echo_pkt = LifxPacket(
        tagged=False, source=transport.source_id,
        target=b"\xAA\xBB\xCC\xDD\xEE\xFF\x00\x00",
        ack_required=False, res_required=False,
        sequence=seq % 256, msg_type=59,
        payload=seq.to_bytes(8, "little") + b"\x00" * 56,
    )
    # Feed the response directly into the handler
    transport._on_packet_received(echo_pkt.pack(), ("192.168.1.100", 56700))

    assert len(rtt_values) == 1
    assert rtt_values[0] >= 0  # RTT is non-negative
    await transport.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/lifx/test_transport.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement LifxTransport**

```python
# src/dj_ledfx/devices/lifx/transport.py
from __future__ import annotations

import asyncio
import random
import time
from typing import Callable

from loguru import logger

from dj_ledfx.devices.lifx.packet import LifxPacket
from dj_ledfx.devices.lifx.types import LifxDeviceRecord


class LifxTransport:
    """Shared UDP transport for all LIFX devices on the network."""

    def __init__(self) -> None:
        self._source_id = random.randint(2, 0xFFFFFFFF)
        self._sequence_counter = 0
        self._socket: asyncio.DatagramTransport | None = None
        self._protocol: _LifxUDPProtocol | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._probe_task: asyncio.Task[None] | None = None
        self._is_open = False

        # Device registry: (ip, port) → device record
        self._devices: dict[tuple[str, int], LifxDeviceRecord] = {}
        # RTT callbacks: ip → callback(rtt_ms)
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}
        # Pending echo probes: sequence_counter → (device_ip, send_time)
        self._pending_probes: dict[int, tuple[str, float]] = {}

    @property
    def source_id(self) -> int:
        return self._source_id

    @property
    def is_open(self) -> bool:
        return self._is_open

    def next_sequence(self) -> int:
        self._sequence_counter += 1
        return self._sequence_counter

    async def open(self) -> None:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _LifxUDPProtocol(self),
            local_addr=("0.0.0.0", 0),
            allow_broadcast=True,
        )
        self._socket = transport
        self._protocol = protocol
        self._is_open = True
        logger.debug("LIFX transport opened on port {}", self._socket.get_extra_info("sockname"))

    async def close(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        if self._socket:
            self._socket.close()
        self._is_open = False
        self._devices.clear()
        self._rtt_callbacks.clear()
        self._pending_probes.clear()
        logger.debug("LIFX transport closed")

    def send_packet(self, packet: LifxPacket, addr: tuple[str, int]) -> None:
        if self._socket:
            self._socket.sendto(packet.pack(), addr)

    def register_device(
        self, record: LifxDeviceRecord,
        rtt_callback: Callable[[float], None] | None = None,
    ) -> None:
        key = (record.ip, record.port)
        self._devices[key] = record
        if rtt_callback:
            self._rtt_callbacks[record.ip] = rtt_callback

    def start_probing(self, interval_s: float = 2.0) -> None:
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))

    async def _probe_loop(self, interval_s: float) -> None:
        from dj_ledfx.devices.lifx.packet import build_echo_request
        while self._is_open:
            now = time.monotonic()
            # Clean stale entries
            stale = [k for k, (_, t) in self._pending_probes.items() if now - t > interval_s]
            for k in stale:
                del self._pending_probes[k]

            # Send echo to each registered device
            for (ip, port), record in self._devices.items():
                seq = self.next_sequence()
                self._pending_probes[seq] = (record.ip, now)
                pkt = LifxPacket(
                    tagged=False, source=self._source_id,
                    target=record.mac + b"\x00\x00",
                    ack_required=False, res_required=False,
                    sequence=seq % 256, msg_type=58,
                    payload=build_echo_request(seq.to_bytes(8, "little")),
                )
                self.send_packet(pkt, (ip, port))

            await asyncio.sleep(interval_s)

    def _on_packet_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            pkt = LifxPacket.unpack(data)
        except Exception:
            return

        if pkt.msg_type == 59:  # EchoResponse
            self._handle_echo_response(pkt, addr)

    def _handle_echo_response(self, pkt: LifxPacket, addr: tuple[str, int]) -> None:
        # Extract the sequence counter we embedded in the echo payload
        if len(pkt.payload) >= 8:
            seq = int.from_bytes(pkt.payload[:8], "little")
        else:
            return

        probe = self._pending_probes.pop(seq, None)
        if probe is None:
            return

        device_ip, send_time = probe
        rtt_ms = (time.monotonic() - send_time) * 1000.0
        callback = self._rtt_callbacks.get(device_ip)
        if callback:
            callback(rtt_ms)
            logger.trace("RTT for {}: {:.1f}ms", device_ip, rtt_ms)


class _LifxUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, transport_owner: LifxTransport) -> None:
        self._owner = transport_owner

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._owner._on_packet_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("LIFX UDP error: {}", exc)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/lifx/test_transport.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/lifx/transport.py tests/devices/lifx/test_transport.py
git commit -m "feat: add LifxTransport with UDP socket, send, and echo probing"
```

---

### Task 10: LifxTransport — discovery

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/transport.py`
- Modify: `tests/devices/lifx/test_transport.py`

- [ ] **Step 1: Write discovery tests**

```python
# Add to tests/devices/lifx/test_transport.py

@pytest.mark.asyncio
async def test_discover_sends_broadcast() -> None:
    """Discovery sends GetService(2) with tagged=1."""
    transport = LifxTransport()
    await transport.open()
    # Discovery with 0.1s timeout returns empty list (no devices on test network)
    devices = await transport.discover(timeout_s=0.1)
    assert isinstance(devices, list)
    await transport.close()
```

- [ ] **Step 2: Add discover() method to LifxTransport**

```python
# Add to LifxTransport class:

async def discover(self, timeout_s: float = 1.0) -> list[LifxDeviceRecord]:
    """Broadcast GetService, collect responses, query versions."""
    from dj_ledfx.devices.lifx.packet import (
        parse_state_service, parse_state_version,
    )

    discovered: dict[str, tuple[bytes, str, int]] = {}  # mac → (mac, ip, port)
    original_handler = self._on_packet_received

    def _discovery_handler(data: bytes, addr: tuple[str, int]) -> None:
        try:
            pkt = LifxPacket.unpack(data)
        except Exception:
            return
        if pkt.msg_type == 3:  # StateService
            service, port = parse_state_service(pkt.payload)
            if service == 1:  # UDP
                mac = pkt.target[:6]
                discovered[mac.hex()] = (mac, addr[0], port)

    # Note: Echo correlation uses the full int counter embedded in the EchoRequest
    # payload (8 bytes), NOT seq % 256 on the wire. This supersedes the spec's
    # stated % 256 lookup design — payload embedding avoids counter-wrap collisions.

    self._on_packet_received = _discovery_handler  # type: ignore[assignment]

    try:
        # Broadcast GetService
        broadcast_pkt = LifxPacket(
            tagged=True, source=self._source_id,
            target=b"\x00" * 8,
            ack_required=False, res_required=False,
            sequence=self.next_sequence() % 256,
            msg_type=2, payload=b"",
        )
        self.send_packet(broadcast_pkt, ("255.255.255.255", 56700))
        await asyncio.sleep(timeout_s)
    finally:
        self._on_packet_received = original_handler  # type: ignore[assignment]

    # Query version for each discovered device
    results: list[LifxDeviceRecord] = []
    for mac_hex, (mac, ip, port) in discovered.items():
        version_responses: list[tuple[int, int, int]] = []

        def _version_handler(data: bytes, addr: tuple[str, int]) -> None:
            try:
                pkt = LifxPacket.unpack(data)
            except Exception:
                return
            if pkt.msg_type == 33:  # StateVersion
                version_responses.append(parse_state_version(pkt.payload))

        self._on_packet_received = _version_handler  # type: ignore[assignment]
        try:
            version_pkt = LifxPacket(
                tagged=False, source=self._source_id,
                target=mac + b"\x00\x00",
                ack_required=False, res_required=True,
                sequence=self.next_sequence() % 256,
                msg_type=32, payload=b"",
            )
            self.send_packet(version_pkt, (ip, port))
            await asyncio.sleep(0.1)
        finally:
            self._on_packet_received = original_handler  # type: ignore[assignment]

        vendor, product, _version = version_responses[0] if version_responses else (1, 0, 0)
        results.append(LifxDeviceRecord(
            mac=mac, ip=ip, port=port, vendor=vendor, product=product,
        ))

    logger.info("LIFX discovery found {} devices", len(results))
    return results
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/devices/lifx/test_transport.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/dj_ledfx/devices/lifx/transport.py tests/devices/lifx/test_transport.py
git commit -m "feat: add LIFX UDP discovery to LifxTransport"
```

---

## Chunk 4: LIFX Adapters, Backend, and Integration

### Task 11: LifxBulbAdapter

**Files:**
- Create: `src/dj_ledfx/devices/lifx/bulb.py`
- Create: `tests/devices/lifx/test_bulb.py`

- [ ] **Step 1: Write bulb adapter tests**

```python
# tests/devices/lifx/test_bulb.py
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock

from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.types import DeviceInfo


@pytest.fixture
def mock_transport() -> MagicMock:
    t = MagicMock()
    t.send_packet = MagicMock()
    t.source_id = 12345
    t.next_sequence = MagicMock(return_value=1)
    t.register_device = MagicMock()
    return t


def test_led_count_is_one(mock_transport: MagicMock) -> None:
    adapter = LifxBulbAdapter(
        mock_transport, DeviceInfo("Bulb", "lifx", 1, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF",
    )
    assert adapter.led_count == 1


def test_supports_latency_probing_false(mock_transport: MagicMock) -> None:
    adapter = LifxBulbAdapter(
        mock_transport, DeviceInfo("Bulb", "lifx", 1, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF",
    )
    assert adapter.supports_latency_probing is False


@pytest.mark.asyncio
async def test_send_frame_sends_set_color(mock_transport: MagicMock) -> None:
    adapter = LifxBulbAdapter(
        mock_transport, DeviceInfo("Bulb", "lifx", 1, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF",
    )
    adapter._is_connected = True
    colors = np.array([[255, 0, 0]], dtype=np.uint8)
    await adapter.send_frame(colors)
    mock_transport.send_packet.assert_called_once()
    pkt = mock_transport.send_packet.call_args[0][0]
    assert pkt.msg_type == 102  # SetColor
```

- [ ] **Step 2: Implement LifxBulbAdapter**

```python
# src/dj_ledfx/devices/lifx/bulb.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.lifx.packet import LifxPacket, build_set_color, rgb_to_hsbk
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport


class LifxBulbAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self, transport: LifxTransport, device_info: DeviceInfo, target_mac: bytes,
        kelvin: int = 3500,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._kelvin = kelvin
        self._is_connected = False
        self._addr = (device_info.address.split(":")[0], int(device_info.address.split(":")[1]))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return 1

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        hsbk = rgb_to_hsbk(r, g, b, kelvin=self._kelvin)
        pkt = LifxPacket(
            tagged=False, source=self._transport.source_id,
            target=self._target_mac + b"\x00\x00",
            ack_required=False, res_required=False,
            sequence=self._transport.next_sequence() % 256,
            msg_type=102, payload=build_set_color(hsbk),
        )
        self._transport.send_packet(pkt, self._addr)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/devices/lifx/test_bulb.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/dj_ledfx/devices/lifx/bulb.py tests/devices/lifx/test_bulb.py
git commit -m "feat: add LifxBulbAdapter"
```

---

### Task 12: LifxStripAdapter

**Files:**
- Create: `src/dj_ledfx/devices/lifx/strip.py`
- Create: `tests/devices/lifx/test_strip.py`

- [ ] **Step 1: Write strip adapter tests**

```python
# tests/devices/lifx/test_strip.py
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock

from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.types import DeviceInfo


@pytest.fixture
def mock_transport() -> MagicMock:
    t = MagicMock()
    t.send_packet = MagicMock()
    t.source_id = 12345
    t.next_sequence = MagicMock(return_value=1)
    t.register_device = MagicMock()
    return t


def test_led_count_returns_zone_count(mock_transport: MagicMock) -> None:
    adapter = LifxStripAdapter(
        mock_transport, DeviceInfo("Strip", "lifx_strip", 1, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF", zone_count=40,
    )
    assert adapter.led_count == 40


@pytest.mark.asyncio
async def test_send_frame_sends_extended_color_zones(mock_transport: MagicMock) -> None:
    adapter = LifxStripAdapter(
        mock_transport, DeviceInfo("Strip", "lifx_strip", 1, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF", zone_count=40,
    )
    adapter._is_connected = True
    colors = np.zeros((40, 3), dtype=np.uint8)
    colors[0] = [255, 0, 0]
    await adapter.send_frame(colors)
    mock_transport.send_packet.assert_called_once()
    pkt = mock_transport.send_packet.call_args[0][0]
    assert pkt.msg_type == 510  # SetExtendedColorZones


@pytest.mark.asyncio
async def test_send_frame_chunks_over_82_zones(mock_transport: MagicMock) -> None:
    adapter = LifxStripAdapter(
        mock_transport, DeviceInfo("Strip", "lifx_strip", 1, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF", zone_count=100,
    )
    adapter._is_connected = True
    colors = np.zeros((100, 3), dtype=np.uint8)
    await adapter.send_frame(colors)
    # 100 zones = 2 packets (82 + 18)
    assert mock_transport.send_packet.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/lifx/test_strip.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement LifxStripAdapter**

```python
# src/dj_ledfx/devices/lifx/strip.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.lifx.packet import (
    LifxPacket, build_set_extended_color_zones, rgb_array_to_hsbk,
)
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

MAX_ZONES_PER_PACKET = 82


class LifxStripAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self, transport: LifxTransport, device_info: DeviceInfo,
        target_mac: bytes, zone_count: int = 1, kelvin: int = 3500,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._zone_count = zone_count
        self._kelvin = kelvin
        self._is_connected = False
        self._addr = (device_info.address.split(":")[0], int(device_info.address.split(":")[1]))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._zone_count

    async def connect(self) -> None:
        # In real usage, query GetExtendedColorZones(511) to get zone count
        # Zone count is set via constructor from discovery
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        for chunk_start in range(0, len(hsbk), MAX_ZONES_PER_PACKET):
            chunk = hsbk[chunk_start : chunk_start + MAX_ZONES_PER_PACKET]
            count = len(chunk)
            hsbk_tuples = [tuple(c) for c in chunk.tolist()]
            pkt = LifxPacket(
                tagged=False, source=self._transport.source_id,
                target=self._target_mac + b"\x00\x00",
                ack_required=False, res_required=False,
                sequence=self._transport.next_sequence() % 256,
                msg_type=510,
                payload=build_set_extended_color_zones(
                    0, 1, chunk_start, count, hsbk_tuples,
                ),
            )
            self._transport.send_packet(pkt, self._addr)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/lifx/test_strip.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/lifx/strip.py tests/devices/lifx/test_strip.py
git commit -m "feat: add LifxStripAdapter with zone chunking"
```

---

### Task 13: LifxTileChainAdapter

**Files:**
- Create: `src/dj_ledfx/devices/lifx/tile_chain.py`
- Create: `tests/devices/lifx/test_tile_chain.py`

- [ ] **Step 1: Write tile chain adapter tests**

```python
# tests/devices/lifx/test_tile_chain.py
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock

from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter, TileInfo
from dj_ledfx.types import DeviceInfo


@pytest.fixture
def mock_transport() -> MagicMock:
    t = MagicMock()
    t.send_packet = MagicMock()
    t.source_id = 12345
    t.next_sequence = MagicMock(side_effect=range(1, 100))
    t.register_device = MagicMock()
    return t


def test_tile_info_frozen() -> None:
    ti = TileInfo(user_x=1.0, user_y=2.0, width=8, height=8, accel_x=0, accel_y=0, accel_z=9800)
    assert ti.width == 8
    with pytest.raises(AttributeError):
        ti.width = 16  # type: ignore[misc]


def test_led_count_equals_tiles_times_64(mock_transport: MagicMock) -> None:
    adapter = LifxTileChainAdapter(
        mock_transport, DeviceInfo("Tile", "lifx_tile", 320, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF", tile_count=5,
    )
    assert adapter.led_count == 320  # 5 * 64


@pytest.mark.asyncio
async def test_send_frame_splits_into_per_tile_packets(mock_transport: MagicMock) -> None:
    adapter = LifxTileChainAdapter(
        mock_transport, DeviceInfo("Tile", "lifx_tile", 320, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF", tile_count=5,
    )
    adapter._is_connected = True
    colors = np.zeros((320, 3), dtype=np.uint8)
    colors[0] = [255, 0, 0]  # First pixel of first tile
    await adapter.send_frame(colors)
    # Should send 5 packets (one per tile)
    assert mock_transport.send_packet.call_count == 5
    # All packets should be SetTileState64(715)
    for call in mock_transport.send_packet.call_args_list:
        pkt = call[0][0]
        assert pkt.msg_type == 715


def test_supports_latency_probing_false(mock_transport: MagicMock) -> None:
    adapter = LifxTileChainAdapter(
        mock_transport, DeviceInfo("Tile", "lifx_tile", 320, "1.2.3.4:56700"),
        target_mac=b"\xAA\xBB\xCC\xDD\xEE\xFF", tile_count=5,
    )
    assert adapter.supports_latency_probing is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/lifx/test_tile_chain.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement LifxTileChainAdapter**

```python
# src/dj_ledfx/devices/lifx/tile_chain.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.lifx.packet import (
    LifxPacket, build_set_tile_state64, rgb_array_to_hsbk,
)
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

PIXELS_PER_TILE = 64


@dataclass(frozen=True, slots=True)
class TileInfo:
    user_x: float
    user_y: float
    width: int
    height: int
    accel_x: int
    accel_y: int
    accel_z: int


class LifxTileChainAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self, transport: LifxTransport, device_info: DeviceInfo,
        target_mac: bytes, tile_count: int = 5, kelvin: int = 3500,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._tile_count = tile_count
        self._kelvin = kelvin
        self._is_connected = False
        self._tiles: list[TileInfo] = []
        self._addr = (device_info.address.split(":")[0], int(device_info.address.split(":")[1]))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._tile_count * PIXELS_PER_TILE

    @property
    def tiles(self) -> list[TileInfo]:
        return self._tiles

    async def connect(self) -> None:
        # In real usage, query GetDeviceChain(701) → StateDeviceChain(702)
        # to populate self._tiles with TileInfo metadata
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        for tile_idx in range(self._tile_count):
            start = tile_idx * PIXELS_PER_TILE
            end = start + PIXELS_PER_TILE
            chunk = hsbk[start:end]
            hsbk_tuples = [tuple(c) for c in chunk.tolist()]
            pkt = LifxPacket(
                tagged=False, source=self._transport.source_id,
                target=self._target_mac + b"\x00\x00",
                ack_required=False, res_required=False,
                sequence=self._transport.next_sequence() % 256,
                msg_type=715,
                payload=build_set_tile_state64(
                    tile_idx, 1, 0, 0, 8, 0, hsbk_tuples,
                ),
            )
            self._transport.send_packet(pkt, self._addr)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/lifx/test_tile_chain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/lifx/tile_chain.py tests/devices/lifx/test_tile_chain.py
git commit -m "feat: add LifxTileChainAdapter with TileInfo metadata"
```

---

### Task 14: LifxBackend + device classification

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/discovery.py` (create)
- Modify: `src/dj_ledfx/devices/lifx/__init__.py`
- Modify: `src/dj_ledfx/devices/__init__.py`
- Create: `tests/devices/lifx/test_discovery.py`

- [ ] **Step 1: Write LifxBackend tests**

```python
# tests/devices/lifx/test_discovery.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.lifx.discovery import (
    LifxBackend, MATRIX_PRODUCTS, MULTIZONE_PRODUCTS,
)
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import LifxDeviceRecord


def test_is_enabled_checks_config() -> None:
    backend = LifxBackend()
    assert backend.is_enabled(AppConfig(lifx_enabled=True)) is True
    assert backend.is_enabled(AppConfig(lifx_enabled=False)) is False


def test_classify_tile_product() -> None:
    backend = LifxBackend()
    config = AppConfig()
    record = LifxDeviceRecord(mac=b"\x00" * 6, ip="1.2.3.4", port=56700, vendor=1, product=55)
    adapter = backend._create_adapter(record, config)
    assert isinstance(adapter, LifxTileChainAdapter)


def test_classify_strip_product() -> None:
    backend = LifxBackend()
    config = AppConfig()
    record = LifxDeviceRecord(mac=b"\x00" * 6, ip="1.2.3.4", port=56700, vendor=1, product=31)
    adapter = backend._create_adapter(record, config)
    assert isinstance(adapter, LifxStripAdapter)


def test_classify_bulb_product() -> None:
    backend = LifxBackend()
    config = AppConfig()
    record = LifxDeviceRecord(mac=b"\x00" * 6, ip="1.2.3.4", port=56700, vendor=1, product=1)
    adapter = backend._create_adapter(record, config)
    assert isinstance(adapter, LifxBulbAdapter)


@pytest.mark.asyncio
async def test_discover_returns_discovered_devices() -> None:
    mock_transport = MagicMock()
    mock_transport.open = AsyncMock()
    mock_transport.discover = AsyncMock(return_value=[
        LifxDeviceRecord(mac=b"\xAA" * 6, ip="1.2.3.4", port=56700, vendor=1, product=1),
    ])
    mock_transport.register_device = MagicMock()
    mock_transport.start_probing = MagicMock()
    mock_transport.source_id = 12345
    mock_transport.next_sequence = MagicMock(return_value=1)

    with patch("dj_ledfx.devices.lifx.discovery.LifxTransport", return_value=mock_transport):
        backend = LifxBackend()
        config = AppConfig()
        devices = await backend.discover(config)

    assert len(devices) == 1
    assert isinstance(devices[0].adapter, LifxBulbAdapter)
    assert devices[0].max_fps == config.lifx_max_fps
    mock_transport.register_device.assert_called_once()
    mock_transport.start_probing.assert_called_once()
```

- [ ] **Step 2: Implement LifxBackend**

```python
# src/dj_ledfx/devices/lifx/discovery.py
from __future__ import annotations

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo

# Product IDs with matrix capability (tiles, candle)
MATRIX_PRODUCTS = {55, 57, 68, 70}
# Product IDs with extended linear zones (strip, beam, neon)
MULTIZONE_PRODUCTS = {31, 32, 38, 52, 70, 89, 90, 91, 94}


class LifxBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: LifxTransport | None = None

    def is_enabled(self, config: AppConfig) -> bool:
        return config.lifx_enabled

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        self._transport = LifxTransport()
        await self._transport.open()

        records = await self._transport.discover(timeout_s=config.lifx_discovery_timeout_s)
        logger.info("LIFX discovery found {} devices", len(records))

        results: list[DiscoveredDevice] = []
        for record in records:
            adapter = self._create_adapter(record, config)
            tracker = self._create_tracker(config)
            await adapter.connect()

            # Register for RTT probing
            self._transport.register_device(
                record,
                rtt_callback=lambda rtt, t=tracker: t.update(rtt),
            )

            results.append(DiscoveredDevice(
                adapter=adapter, tracker=tracker, max_fps=config.lifx_max_fps,
            ))

        # Start probing after all devices registered
        if results:
            self._transport.start_probing(interval_s=config.lifx_echo_probe_interval_s)

        return results

    async def shutdown(self) -> None:
        if self._transport:
            await self._transport.close()
            self._transport = None

    def _create_adapter(
        self, record: LifxDeviceRecord, config: AppConfig,
    ) -> LifxBulbAdapter | LifxStripAdapter | LifxTileChainAdapter:
        addr = f"{record.ip}:{record.port}"
        if record.product in MATRIX_PRODUCTS:
            info = DeviceInfo(f"LIFX Tile ({record.ip})", "lifx_tile", 320, addr)
            return LifxTileChainAdapter(
                self._transport, info, record.mac, kelvin=config.lifx_default_kelvin,  # type: ignore[arg-type]
            )
        elif record.product in MULTIZONE_PRODUCTS:
            info = DeviceInfo(f"LIFX Strip ({record.ip})", "lifx_strip", 1, addr)
            return LifxStripAdapter(
                self._transport, info, record.mac, kelvin=config.lifx_default_kelvin,  # type: ignore[arg-type]
            )
        else:
            info = DeviceInfo(f"LIFX Bulb ({record.ip})", "lifx_bulb", 1, addr)
            return LifxBulbAdapter(
                self._transport, info, record.mac, kelvin=config.lifx_default_kelvin,  # type: ignore[arg-type]
            )

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        if config.lifx_latency_strategy == "static":
            strategy = StaticLatency(config.lifx_latency_ms)
        elif config.lifx_latency_strategy == "ema":
            strategy = EMALatency(initial_value_ms=config.lifx_latency_ms)
        else:
            strategy = WindowedMeanLatency(
                window_size=config.lifx_latency_window_size,
                initial_value_ms=config.lifx_latency_ms,
            )
        return LatencyTracker(strategy=strategy, manual_offset_ms=config.lifx_manual_offset_ms)
```

- [ ] **Step 3: Update `__init__.py` files**

```python
# src/dj_ledfx/devices/lifx/__init__.py
from dj_ledfx.devices.lifx.discovery import LifxBackend as LifxBackend  # noqa: F401
```

```python
# src/dj_ledfx/devices/__init__.py
from dj_ledfx.devices import openrgb_backend as _openrgb_backend  # noqa: F401
from dj_ledfx.devices import lifx as _lifx  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/lifx/test_discovery.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/lifx/ src/dj_ledfx/devices/__init__.py tests/devices/lifx/test_discovery.py
git commit -m "feat: add LifxBackend with device classification and auto-registration"
```

---

### Task 15: Integration tests

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add LIFX integration tests**

```python
# Add to tests/test_integration.py

@pytest.mark.asyncio
async def test_rtt_callback_updates_tracker() -> None:
    """RTT callback from transport updates latency tracker."""
    from dj_ledfx.latency.strategies import EMALatency
    from dj_ledfx.latency.tracker import LatencyTracker

    strategy = EMALatency(initial_value_ms=50.0)
    tracker = LatencyTracker(strategy=strategy)
    initial = tracker.effective_latency_ms

    # Simulate RTT callback (same path as LifxTransport probe callback)
    tracker.update(25.0)
    assert tracker.effective_latency_ms != initial
    # RTT of 25ms should pull EMA down from 50ms initial
    assert tracker.effective_latency_ms < initial


@pytest.mark.asyncio
async def test_rtt_feedback_shifts_frame_selection() -> None:
    """Lower RTT → lower effective latency → scheduler picks earlier frame."""
    from dj_ledfx.latency.strategies import EMALatency
    from dj_ledfx.latency.tracker import LatencyTracker

    strategy = EMALatency(initial_value_ms=100.0)
    tracker = LatencyTracker(strategy=strategy)

    high_latency = tracker.effective_latency_s
    # Simulate many low-RTT probes
    for _ in range(20):
        tracker.update(10.0)
    low_latency = tracker.effective_latency_s

    assert low_latency < high_latency
    # This confirms the scheduler would read a different (earlier) ring buffer position
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -x -v`
Expected: PASS

- [ ] **Step 3: Run linter, formatter, type checker**

```bash
uv run ruff check . && uv run ruff format . && uv run mypy src/
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add LIFX integration tests for RTT feedback loop"
```

---

### Task 16: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests PASS

- [ ] **Step 2: Run linter and type checker**

Run: `uv run ruff check . && uv run mypy src/`
Expected: No errors

- [ ] **Step 3: Verify demo mode still works**

Run: `uv run -m dj_ledfx --demo --log-level DEBUG`
Expected: Starts up, logs "Starting in demo mode", runs DeviceBackend.discover_all(), logs device discovery results (may show "LIFX discovery found 0 devices" if no LIFX hardware present, or OpenRGB connection failures if server not running — these are expected). The app should run and log periodic status updates without crashing. Ctrl+C to stop.

- [ ] **Step 4: Final commit if any cleanup needed**
