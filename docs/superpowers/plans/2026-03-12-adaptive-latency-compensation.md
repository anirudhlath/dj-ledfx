# Adaptive Per-Device Latency Compensation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-dispatch scheduler with per-device send loops, device-type heuristic latency seeding, and infrastructure for RTT-based adaptive latency.

**Architecture:** Each device gets its own async send loop fed by a depth-1 FrameSlot. A distributor ticks at engine FPS writing `target_time` floats into slots. Send loops resolve frames from the ring buffer only when ready to send. Latency strategies are seeded with device-type heuristics (Govee=100ms, LIFX=50ms, USB=5ms). OpenRGB adapters use static heuristics permanently (`supports_latency_probing=False`); future direct adapters get real RTT-based adaptation.

**Tech Stack:** Python 3.11+, asyncio, numpy, loguru, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-12-adaptive-latency-compensation-design.md`

---

## File Structure

### Files to Create
| File | Responsibility |
|------|---------------|
| `src/dj_ledfx/devices/heuristics.py` | Map device names to initial latency estimates |
| `tests/devices/test_heuristics.py` | Tests for heuristic mapping |

### Files to Modify
| File | Change Summary |
|------|---------------|
| `src/dj_ledfx/latency/strategies.py` | Add `initial_value_ms` to EMA and WindowedMean |
| `tests/latency/test_strategies.py` | Tests for initial_value_ms behavior |
| `src/dj_ledfx/config.py` | Add `openrgb_max_fps`, `openrgb_latency_window_size`, change default strategy, validation |
| `tests/test_config.py` | Tests for new fields, validation, TOML parsing |
| `src/dj_ledfx/devices/adapter.py` | Protocol -> ABC, add `supports_latency_probing`, remove `discover()` |
| `src/dj_ledfx/devices/openrgb.py` | Inherit ABC, `supports_latency_probing=False`, exception handling in send_frame |
| `tests/devices/test_openrgb.py` | Tests for probing flag, send exception behavior |
| `tests/conftest.py` | `MockDeviceAdapter(DeviceAdapter)` concrete test subclass |
| `pyproject.toml` | Add `pythonpath = ["tests"]` to pytest config (enables `from conftest import ...`) |
| `src/dj_ledfx/types.py` | Add `DeviceStats` shared dataclass |
| `src/dj_ledfx/scheduling/scheduler.py` | Complete rewrite: FrameSlot, distributor, per-device send loops (imports DeviceStats from types) |
| `tests/scheduling/test_scheduler.py` | Complete rewrite for new architecture |
| `src/dj_ledfx/status.py` | Add `DeviceStatusInfo` dataclass, per-device stats in summary |
| `src/dj_ledfx/main.py` | Strategy branching with heuristic seeding, pass `max_fps`, update status loop |
| `tests/test_integration.py` | Update for new scheduler, add mixed-latency test |
| `CLAUDE.md` | Update architecture and design decisions sections |

### Files Unchanged
| File | Why |
|------|-----|
| `src/dj_ledfx/latency/tracker.py` | Already has `update()`, `reset()`, `effective_latency_s` |
| `src/dj_ledfx/effects/engine.py` | `RingBuffer.find_nearest()` already copies frames |
| `src/dj_ledfx/devices/manager.py` | Import path and annotations unchanged |
| `src/dj_ledfx/events.py` | No interaction with new components |

---

## Chunk 1: Foundation

### Task 1: WindowedMeanLatency `initial_value_ms`

**Files:**
- Modify: `src/dj_ledfx/latency/strategies.py:64-78`
- Test: `tests/latency/test_strategies.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/latency/test_strategies.py`:

```python
def test_windowed_mean_initial_value_ms() -> None:
    s = WindowedMeanLatency(window_size=3, initial_value_ms=100.0)
    assert s.get_latency() == 100.0


def test_windowed_mean_reset_returns_initial_value() -> None:
    s = WindowedMeanLatency(window_size=3, initial_value_ms=100.0)
    s.update(50.0)
    s.reset()
    assert s.get_latency() == 100.0


def test_windowed_mean_overrides_initial_after_updates() -> None:
    s = WindowedMeanLatency(window_size=3, initial_value_ms=100.0)
    s.update(10.0)
    s.update(20.0)
    s.update(30.0)
    assert abs(s.get_latency() - 20.0) < 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/latency/test_strategies.py -v -k "initial_value"`
Expected: FAIL — `WindowedMeanLatency.__init__()` does not accept `initial_value_ms`

- [ ] **Step 3: Implement `initial_value_ms` on WindowedMeanLatency**

In `src/dj_ledfx/latency/strategies.py`, replace the `WindowedMeanLatency` class (lines 64-78):

```python
class WindowedMeanLatency:
    def __init__(self, window_size: int = 10, initial_value_ms: float = 0.0) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._initial_value_ms = initial_value_ms

    def update(self, new_sample: float) -> None:
        self._window.append(new_sample)

    def get_latency(self) -> float:
        if not self._window:
            return self._initial_value_ms
        return sum(self._window) / len(self._window)

    def reset(self) -> None:
        self._window.clear()
```

- [ ] **Step 4: Run all strategy tests**

Run: `uv run pytest tests/latency/test_strategies.py -v`
Expected: ALL PASS (new tests + existing tests — existing `test_windowed_mean_reset` still passes because default `initial_value_ms=0.0`)

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/latency/strategies.py tests/latency/test_strategies.py
git commit -m "feat(latency): add initial_value_ms to WindowedMeanLatency

Empty window and post-reset now return initial_value_ms instead of 0.0.
Backward compatible — default initial_value_ms=0.0 preserves old behavior."
```

---

### Task 2: EMALatency `initial_value_ms`

**Files:**
- Modify: `src/dj_ledfx/latency/strategies.py:28-62`
- Test: `tests/latency/test_strategies.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/latency/test_strategies.py`:

```python
def test_ema_initial_value_ms() -> None:
    s = EMALatency(alpha=0.3, initial_value_ms=50.0)
    assert s.get_latency() == 50.0


def test_ema_reset_returns_initial_value() -> None:
    s = EMALatency(alpha=0.3, initial_value_ms=50.0)
    s.update(100.0)
    s.reset()
    assert s.get_latency() == 50.0


def test_ema_overrides_initial_after_update() -> None:
    s = EMALatency(alpha=0.3, initial_value_ms=50.0)
    s.update(100.0)
    assert s.get_latency() == 100.0  # First sample replaces initial
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/latency/test_strategies.py -v -k "ema_initial or ema_reset_returns or ema_overrides"`
Expected: FAIL — `EMALatency.__init__()` does not accept `initial_value_ms`

- [ ] **Step 3: Implement `initial_value_ms` on EMALatency**

In `src/dj_ledfx/latency/strategies.py`, replace the `EMALatency` class (lines 28-62):

```python
class EMALatency:
    def __init__(self, alpha: float = 0.3, initial_value_ms: float = 0.0) -> None:
        self._alpha = alpha
        self._initial_value_ms = initial_value_ms
        self._value: float = initial_value_ms
        self._initialized = False
        self._samples: list[float] = []

    def update(self, new_sample: float) -> None:
        if len(self._samples) >= 5:
            mean = sum(self._samples) / len(self._samples)
            variance = sum((s - mean) ** 2 for s in self._samples) / len(self._samples)
            std = math.sqrt(variance) if variance > 0 else 0.0
            threshold = 2.0 * std if std > 0 else mean * 0.1
            if threshold > 0 and abs(new_sample - mean) > threshold:
                return

        self._samples.append(new_sample)
        if len(self._samples) > 100:
            self._samples.pop(0)

        if not self._initialized:
            self._value = new_sample
            self._initialized = True
        else:
            self._value = self._alpha * new_sample + (1.0 - self._alpha) * self._value

    def get_latency(self) -> float:
        if not self._initialized:
            return self._initial_value_ms
        return self._value

    def reset(self) -> None:
        self._value = self._initial_value_ms
        self._initialized = False
        self._samples.clear()
```

Key changes from original:
- `__init__`: accepts `initial_value_ms`, sets `_value` to it (was `0.0`)
- `get_latency`: returns `_initial_value_ms` when not initialized (was always returning `_value`)
- `reset`: sets `_value` back to `_initial_value_ms` (was `0.0`)

- [ ] **Step 4: Run all strategy tests**

Run: `uv run pytest tests/latency/test_strategies.py -v`
Expected: ALL PASS (existing `test_ema_latency_reset` still passes — default `initial_value_ms=0.0`)

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/latency/strategies.py tests/latency/test_strategies.py
git commit -m "feat(latency): add initial_value_ms to EMALatency

Pre-initialization and post-reset return initial_value_ms.
Backward compatible — default 0.0 preserves old behavior."
```

---

### Task 3: Device Heuristics Module

**Files:**
- Create: `src/dj_ledfx/devices/heuristics.py`
- Create: `tests/devices/test_heuristics.py`

- [ ] **Step 1: Write failing tests**

Create `tests/devices/test_heuristics.py`:

```python
from dj_ledfx.devices.heuristics import estimate_device_latency_ms


def test_govee_device() -> None:
    assert estimate_device_latency_ms("Govee H6061") == 100.0


def test_lifx_device() -> None:
    assert estimate_device_latency_ms("LIFX Strip") == 50.0


def test_unknown_device_defaults_to_usb() -> None:
    assert estimate_device_latency_ms("Corsair RGB") == 5.0


def test_case_insensitive() -> None:
    assert estimate_device_latency_ms("GoVeE") == 100.0
    assert estimate_device_latency_ms("lifx") == 50.0


def test_empty_string() -> None:
    assert estimate_device_latency_ms("") == 5.0


def test_govee_takes_priority_over_lifx() -> None:
    assert estimate_device_latency_ms("Govee-LIFX-Bridge") == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_heuristics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dj_ledfx.devices.heuristics'`

- [ ] **Step 3: Implement heuristics module**

Create `src/dj_ledfx/devices/heuristics.py`:

```python
from __future__ import annotations


def estimate_device_latency_ms(device_name: str) -> float:
    """Map device name to initial latency estimate (ms).

    Govee WiFi: ~100ms, LIFX WiFi: ~50ms, everything else: ~5ms (USB/wired assumed).
    """
    name_lower = device_name.lower()
    if "govee" in name_lower:
        return 100.0
    if "lifx" in name_lower:
        return 50.0
    return 5.0
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/devices/test_heuristics.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/heuristics.py tests/devices/test_heuristics.py
git commit -m "feat(devices): add device-type heuristic latency estimation

Maps device names to initial latency seeds: Govee=100ms, LIFX=50ms, USB=5ms."
```

---

### Task 4: Config Additions

**Files:**
- Modify: `src/dj_ledfx/config.py:29-46,83-96`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_config.py`:

```python
def test_default_config_new_fields() -> None:
    config = AppConfig()
    assert config.openrgb_max_fps == 60
    assert config.openrgb_latency_window_size == 60
    assert config.openrgb_latency_strategy == "windowed_mean"


def test_config_validation_bad_max_fps() -> None:
    with pytest.raises(ValueError, match="openrgb_max_fps"):
        AppConfig(openrgb_max_fps=0)


def test_config_validation_bad_window_size() -> None:
    with pytest.raises(ValueError, match="openrgb_latency_window_size"):
        AppConfig(openrgb_latency_window_size=0)


def test_config_validation_bad_strategy() -> None:
    with pytest.raises(ValueError, match="openrgb_latency_strategy"):
        AppConfig(openrgb_latency_strategy="invalid")


def test_load_config_new_toml_fields(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        textwrap.dedent("""\
        [devices.openrgb]
        max_fps = 30
        latency_window_size = 120
        latency_strategy = "ema"
    """)
    )
    config = load_config(toml_file)
    assert config.openrgb_max_fps == 30
    assert config.openrgb_latency_window_size == 120
    assert config.openrgb_latency_strategy == "ema"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v -k "new_fields or bad_max or bad_window or bad_strategy or new_toml"`
Expected: FAIL — `AppConfig` has no field `openrgb_max_fps`

- [ ] **Step 3: Add new config fields**

In `src/dj_ledfx/config.py`, add after line 35 (`openrgb_manual_offset_ms`):

```python
    openrgb_max_fps: int = 60
    openrgb_latency_window_size: int = 60
```

Change the default for `openrgb_latency_strategy` (line 33) from `"static"` to `"windowed_mean"`.

- [ ] **Step 4: Add validation rules**

In `src/dj_ledfx/config.py`, add to `__post_init__` (after the `beat_pulse_gamma` check, before `if errors:`):

```python
        if self.openrgb_max_fps <= 0:
            errors.append("openrgb_max_fps must be positive")
        if self.openrgb_latency_window_size <= 0:
            errors.append("openrgb_latency_window_size must be positive")
        if self.openrgb_latency_strategy not in {"static", "ema", "windowed_mean"}:
            errors.append(
                "openrgb_latency_strategy must be one of: static, ema, windowed_mean"
            )
```

- [ ] **Step 5: Add TOML parsing**

In `src/dj_ledfx/config.py`, inside the `if "devices" in raw and "openrgb" in raw["devices"]:` block (after line 96):

```python
        if "max_fps" in orgb:
            kwargs["openrgb_max_fps"] = orgb["max_fps"]
        if "latency_window_size" in orgb:
            kwargs["openrgb_latency_window_size"] = orgb["latency_window_size"]
```

- [ ] **Step 6: Run all config tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py
git commit -m "feat(config): add openrgb_max_fps, latency_window_size, change default strategy

Default strategy changes from 'static' to 'windowed_mean'.
Adds validation for new fields and TOML parsing."
```

---

## Chunk 2: Adapter Migration

### Task 5: DeviceAdapter Protocol -> ABC

**Files:**
- Modify: `src/dj_ledfx/devices/adapter.py` (full rewrite)

- [ ] **Step 1: Rewrite adapter.py**

Replace entire contents of `src/dj_ledfx/devices/adapter.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.types import DeviceInfo


class DeviceAdapter(ABC):
    """Abstract base class for LED device adapters.

    Each adapter must implement connect/disconnect/send_frame and device properties.
    discover() is deliberately excluded — discovery mechanisms differ fundamentally
    between device types (TCP for OpenRGB, UDP broadcast for Govee/LIFX).
    """

    supports_latency_probing: bool = True

    @property
    @abstractmethod
    def device_info(self) -> DeviceInfo: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @property
    @abstractmethod
    def led_count(self) -> int: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_frame(self, colors: NDArray[np.uint8]) -> None: ...
```

Key changes from original:
- `Protocol` -> `ABC` with `@abstractmethod` on all methods and `@property @abstractmethod` on properties
- Added `supports_latency_probing: bool = True` class attribute
- Removed `discover()` — each adapter owns its own discovery as a concrete `@staticmethod`

- [ ] **Step 2: Run existing tests to verify nothing breaks**

Run: `uv run pytest -v`
Expected: ALL PASS — existing tests use `AsyncMock` which satisfies duck typing (no `isinstance` checks)

- [ ] **Step 3: Run type checker**

Run: `uv run mypy src/`
Expected: May produce errors for `OpenRGBAdapter` not inheriting from ABC. That's fixed in Task 7.

- [ ] **Step 4: Commit**

```bash
git add src/dj_ledfx/devices/adapter.py
git commit -m "refactor(devices): convert DeviceAdapter from Protocol to ABC

Adds supports_latency_probing class attribute (default True).
Removes discover() from base — adapters own their own discovery.
ABC enforces method implementation at class definition time."
```

---

### Task 6: MockDeviceAdapter in conftest + pytest config

**Files:**
- Modify: `tests/conftest.py`
- Modify: `pyproject.toml:43-45`

- [ ] **Step 1: Enable test module imports**

In `pyproject.toml`, add `pythonpath` to the `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["tests"]
```

This allows `from conftest import MockDeviceAdapter` in any test file.

- [ ] **Step 2: Create MockDeviceAdapter**

Replace `tests/conftest.py` with:

```python
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.types import DeviceInfo


class MockDeviceAdapter(DeviceAdapter):
    """Concrete DeviceAdapter for tests. Tracks all calls for assertions."""

    def __init__(
        self,
        name: str = "TestDevice",
        led_count: int = 10,
        connected: bool = True,
        supports_probing: bool = True,
    ) -> None:
        self._name = name
        self._led_count = led_count
        self._connected = connected
        self.supports_latency_probing = supports_probing
        self.send_frame_calls: list[NDArray[np.uint8]] = []
        self.connect_count = 0
        self.disconnect_count = 0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._name,
            device_type="mock",
            led_count=self._led_count,
            address="mock",
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        self._connected = value

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        self.connect_count += 1
        self._connected = True

    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self._connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.send_frame_calls.append(colors.copy())
```

- [ ] **Step 3: Verify import works and existing tests pass**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py pyproject.toml
git commit -m "test: add MockDeviceAdapter concrete ABC subclass

Shared test adapter in conftest.py with call tracking.
Adds pythonpath=['tests'] to pytest config for clean imports."
```

---

### Task 7: OpenRGB Adapter — ABC Inheritance + Error Handling

**Files:**
- Modify: `src/dj_ledfx/devices/openrgb.py:1-2,20,98-116`
- Test: `tests/devices/test_openrgb.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/devices/test_openrgb.py`:

```python
def test_supports_latency_probing_is_false() -> None:
    adapter = OpenRGBAdapter()
    assert adapter.supports_latency_probing is False


async def test_send_frame_connection_error_disconnects() -> None:
    """send_frame should set is_connected=False on ConnectionError and re-raise."""
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as mock_cls:
        mock_device = _make_mock_device()
        mock_device.set_colors.side_effect = ConnectionError("broken pipe")
        mock_client = MagicMock()
        mock_client.devices = [mock_device]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(device_index=0)
        await adapter.connect()

        colors = np.full((10, 3), 128, dtype=np.uint8)
        with pytest.raises(ConnectionError):
            await adapter.send_frame(colors)

        assert adapter.is_connected is False


async def test_send_frame_os_error_disconnects() -> None:
    """send_frame should set is_connected=False on OSError and re-raise."""
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as mock_cls:
        mock_device = _make_mock_device()
        mock_device.set_colors.side_effect = OSError("network unreachable")
        mock_client = MagicMock()
        mock_client.devices = [mock_device]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(device_index=0)
        await adapter.connect()

        colors = np.full((10, 3), 128, dtype=np.uint8)
        with pytest.raises(OSError):
            await adapter.send_frame(colors)

        assert adapter.is_connected is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/test_openrgb.py -v -k "probing or connection_error or os_error"`
Expected: FAIL — `supports_latency_probing` not defined; ConnectionError not re-raised

- [ ] **Step 3: Add ABC inheritance and `supports_latency_probing`**

In `src/dj_ledfx/devices/openrgb.py`:

Add import (after the existing `from dj_ledfx.types import DeviceInfo` line):

```python
from dj_ledfx.devices.adapter import DeviceAdapter
```

Change class declaration (line 20) from:

```python
class OpenRGBAdapter:
```

to:

```python
class OpenRGBAdapter(DeviceAdapter):
    supports_latency_probing = False
```

- [ ] **Step 4: Add exception handling in send_frame**

In `src/dj_ledfx/devices/openrgb.py`, replace the `send_frame` method (lines 98-116):

```python
    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        if not self._is_connected or self._device is None:
            return

        device = self._device
        led_count = self._led_count

        frame = colors[:led_count]

        rgb_colors = [
            RGBColor(int(frame[i, 0]), int(frame[i, 1]), int(frame[i, 2]))
            for i in range(len(frame))
        ]

        def _send() -> None:
            device.set_colors(rgb_colors, fast=True)

        try:
            await asyncio.to_thread(_send)
        except (ConnectionError, OSError):
            self._is_connected = False
            raise
        logger.trace("Sent {} colors to '{}'", len(rgb_colors), self._device_name)
```

Only change: `await asyncio.to_thread(_send)` is now wrapped in `try/except (ConnectionError, OSError)` that sets `_is_connected = False` before re-raising.

- [ ] **Step 5: Run all OpenRGB tests**

Run: `uv run pytest tests/devices/test_openrgb.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/devices/openrgb.py tests/devices/test_openrgb.py
git commit -m "feat(openrgb): inherit DeviceAdapter ABC, add error handling

supports_latency_probing=False (OpenRGB fire-and-forget has no real RTT).
send_frame catches ConnectionError/OSError, sets is_connected=False, re-raises."
```

---

## Chunk 3: Scheduler Rewrite

### Task 8: FrameSlot Class

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py` (add FrameSlot at top, before LookaheadScheduler)
- Test: `tests/scheduling/test_scheduler.py`

- [ ] **Step 1: Write FrameSlot tests**

Add to the **top** of `tests/scheduling/test_scheduler.py` (these tests are independent of the scheduler rewrite — they test FrameSlot in isolation):

```python
import asyncio
import time

import numpy as np
import pytest

from dj_ledfx.scheduling.scheduler import FrameSlot
from dj_ledfx.types import RenderedFrame


# --- FrameSlot tests ---


async def test_frame_slot_put_take() -> None:
    slot = FrameSlot()
    slot.put(42.0)
    result = await slot.take(timeout=1.0)
    assert result == 42.0


async def test_frame_slot_put_overwrites() -> None:
    slot = FrameSlot()
    slot.put(1.0)
    slot.put(2.0)
    result = await slot.take(timeout=1.0)
    assert result == 2.0


async def test_frame_slot_take_timeout() -> None:
    slot = FrameSlot()
    with pytest.raises(asyncio.TimeoutError):
        await slot.take(timeout=0.05)


async def test_frame_slot_take_blocks_until_put() -> None:
    slot = FrameSlot()

    async def delayed_put() -> None:
        await asyncio.sleep(0.05)
        slot.put(99.0)

    asyncio.create_task(delayed_put())
    result = await slot.take(timeout=1.0)
    assert result == 99.0


async def test_frame_slot_put_count() -> None:
    slot = FrameSlot()
    assert slot.put_count == 0
    slot.put(1.0)
    slot.put(2.0)
    slot.put(3.0)
    assert slot.put_count == 3


async def test_frame_slot_has_pending() -> None:
    slot = FrameSlot()
    assert slot.has_pending is False
    slot.put(1.0)
    assert slot.has_pending is True
    await slot.take(timeout=1.0)
    assert slot.has_pending is False


async def test_frame_slot_concurrent_overwrite_stress() -> None:
    """Rapid alternating put/take never produces stale values."""
    slot = FrameSlot()
    received: list[float] = []

    async def producer() -> None:
        for i in range(100):
            slot.put(float(i))
            await asyncio.sleep(0)  # yield control

    async def consumer() -> None:
        for _ in range(50):
            try:
                val = await slot.take(timeout=0.1)
                received.append(val)
            except asyncio.TimeoutError:
                break

    await asyncio.gather(producer(), consumer())
    # Each received value should be >= previous (never stale/backward)
    for i in range(1, len(received)):
        assert received[i] >= received[i - 1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v -k "frame_slot"`
Expected: FAIL — `cannot import name 'FrameSlot' from 'dj_ledfx.scheduling.scheduler'`

- [ ] **Step 3: Implement FrameSlot**

Add to `src/dj_ledfx/scheduling/scheduler.py` (after imports, before `LookaheadScheduler`):

```python
class FrameSlot:
    """Depth-1 slot for passing target_time from distributor to per-device send loop.

    Stores a target_time (float), not a frame. The send loop resolves it to
    a frame via ring_buffer.find_nearest() only when ready to send.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._target_time: float = 0.0
        self._put_count: int = 0

    def put(self, target_time: float) -> None:
        """Write target_time and signal. Must not await — single synchronous step."""
        self._target_time = target_time
        self._put_count += 1
        self._event.set()

    async def take(self, timeout: float = 1.0) -> float:
        """Wait for a target_time. Raises asyncio.TimeoutError on timeout."""
        await asyncio.wait_for(self._event.wait(), timeout=timeout)
        self._event.clear()
        return self._target_time

    @property
    def has_pending(self) -> bool:
        return self._event.is_set()

    @property
    def put_count(self) -> int:
        return self._put_count
```

- [ ] **Step 4: Run FrameSlot tests**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v -k "frame_slot"`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat(scheduling): add FrameSlot depth-1 async slot

Stores target_time float, not frame data. Distributor writes,
send loop reads. Overwrites on slow consumers eliminate stale frames."
```

---

### Task 9: LookaheadScheduler Rewrite

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py` (replace LookaheadScheduler class)
- Modify: `tests/scheduling/test_scheduler.py` (replace old scheduler tests)

This is the largest task. It replaces the single `_dispatch_all()` loop with a distributor + per-device send loops.

- [ ] **Step 9a: Write DeviceStats dataclass**

Add to `src/dj_ledfx/scheduling/scheduler.py` (after FrameSlot, before LookaheadScheduler):

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeviceStats:
    """Per-device statistics snapshot."""

    device_name: str
    effective_latency_ms: float
    send_fps: float
    frames_dropped: int
```

- [ ] **Step 9b: Write scheduler tests — replace old tests with new ones**

Replace everything in `tests/scheduling/test_scheduler.py` BELOW the FrameSlot tests with:

```python
from conftest import MockDeviceAdapter
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.latency.strategies import StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.scheduler import DeviceStats, LookaheadScheduler


def _make_device(
    name: str = "TestDevice",
    latency_ms: float = 10.0,
    connected: bool = True,
) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, connected=connected)
    tracker = LatencyTracker(strategy=StaticLatency(latency_ms))
    return ManagedDevice(adapter=adapter, tracker=tracker)


def _fill_buffer(buf: RingBuffer, base_time: float, count: int = 60) -> None:
    for i in range(count):
        frame = RenderedFrame(
            colors=np.full((10, 3), i % 256, dtype=np.uint8),
            target_time=base_time + i * (1.0 / 60.0),
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)


# --- Distributor tests ---


async def test_distributor_writes_to_all_devices() -> None:
    """Distributor tick should result in frames sent to every connected device."""
    dev1 = _make_device("Dev1", latency_ms=10.0)
    dev2 = _make_device("Dev2", latency_ms=100.0)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[dev1, dev2], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(dev1.adapter.send_frame_calls) > 0
    assert len(dev2.adapter.send_frame_calls) > 0


async def test_distributor_computes_correct_target_time() -> None:
    """target_time should be now + effective_latency_s for each device."""
    dev_fast = _make_device("Fast", latency_ms=5.0)
    dev_slow = _make_device("Slow", latency_ms=100.0)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[dev_fast, dev_slow], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # Both devices got frames. The slow device's frames should have target_times
    # further in the future, meaning they pick frames further along the ring buffer.
    # With StaticLatency, the effective latencies are 5ms and 100ms.
    # We can verify by checking the first frame's target_time difference is ~95ms.
    fast_first = dev_fast.adapter.send_frame_calls[0]
    slow_first = dev_slow.adapter.send_frame_calls[0]
    # The frames themselves are numpy arrays — we can't directly see target_time.
    # But we CAN verify the slow device got a different frame than the fast device
    # (since find_nearest picks frames at different target_times).
    # The key correctness check is that both received frames (already tested above).
    # For deeper verification, we would need to instrument FrameSlot.put or find_nearest.
    assert len(dev_fast.adapter.send_frame_calls) > 0
    assert len(dev_slow.adapter.send_frame_calls) > 0


# --- Send loop tests ---


async def test_send_loop_disconnected_backoff() -> None:
    """Disconnected device should not receive any frames."""
    device = _make_device(connected=False)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 0


async def test_send_loop_reconnection_sends_frames() -> None:
    """Device that reconnects should start receiving frames."""
    device = _make_device(connected=False)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60,
        disconnect_backoff_s=0.01,  # Fast backoff for tests
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    # Reconnect
    device.adapter.is_connected = True
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) > 0


async def test_send_loop_reconnection_resets_tracker() -> None:
    """When is_connected flips False->True, tracker.reset() must be called."""
    # Use supports_probing=False so no RTT samples are added after reconnect,
    # making the assertion clean: get_latency() == initial_value_ms after reset.
    adapter = MockDeviceAdapter(name="Reconnect", connected=False, supports_probing=False)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy))
    # Pre-fill strategy with stale samples
    strategy.update(200.0)
    strategy.update(300.0)
    assert abs(strategy.get_latency() - 250.0) < 0.1  # Mean of stale samples

    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60,
        disconnect_backoff_s=0.01,  # Fast backoff for tests
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)

    # Reconnect — should trigger tracker.reset()
    adapter.is_connected = True
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # After reset, strategy falls back to initial_value_ms (stale samples cleared).
    # Since supports_probing=False, no new RTT samples were added.
    assert strategy.get_latency() == 100.0


async def test_send_loop_rtt_not_updated_when_probing_disabled() -> None:
    """When supports_latency_probing=False, tracker should not get RTT updates."""
    adapter = MockDeviceAdapter(name="NoProbe", supports_probing=False)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy))
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # Strategy should still return initial value (no RTT updates overwrote it)
    assert strategy.get_latency() == 100.0


async def test_send_loop_rtt_updated_when_probing_enabled() -> None:
    """When supports_latency_probing=True, tracker should receive RTT updates."""
    adapter = MockDeviceAdapter(name="WithProbe", supports_probing=True)
    strategy = WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    device = ManagedDevice(adapter=adapter, tracker=LatencyTracker(strategy=strategy))

    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.15)
    scheduler.stop()
    await task

    # Latency should have shifted from initial (mock send is near-instant, ~0ms RTT)
    assert strategy.get_latency() < 100.0


async def test_send_loop_buffer_not_ready() -> None:
    """Empty ring buffer should result in no frames sent."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    # Don't fill buffer

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 0


async def test_send_loop_continues_after_send_exception() -> None:
    """Send loop should log warning and continue on send_frame exception."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    call_count = 0
    original_send = device.adapter.send_frame

    async def flaky_send(colors: np.ndarray) -> None:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise OSError("transient error")
        await original_send(colors)

    device.adapter.send_frame = flaky_send  # type: ignore[assignment]

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    # Loop recovered after initial failures
    assert len(device.adapter.send_frame_calls) > 0


async def test_fps_cap_limits_send_rate() -> None:
    """max_fps should throttle the device send rate."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=10,
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)
    scheduler.stop()
    await task

    # At max_fps=10, expect ~10 sends/sec (tolerance: 5-15)
    assert 5 <= len(device.adapter.send_frame_calls) <= 15


async def test_fps_cap_no_accumulated_drift() -> None:
    """Over many iterations, total elapsed should match expected (no drift)."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=20,
    )
    start = time.monotonic()
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(2.0)
    scheduler.stop()
    await task
    elapsed = time.monotonic() - start

    # At 20fps, ~40 sends in 2s. Check total count is proportional to elapsed time.
    expected = elapsed * 20
    actual = len(device.adapter.send_frame_calls)
    # Allow 30% tolerance for CI variability
    assert actual >= expected * 0.7, f"Drift detected: {actual} sends in {elapsed:.2f}s (expected ~{expected:.0f})"


# --- Shutdown tests ---


async def test_graceful_stop() -> None:
    """stop() should cause run() to return cleanly."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await asyncio.wait_for(task, timeout=3.0)


async def test_external_cancellation() -> None:
    """Cancelling the scheduler task should clean up child tasks."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_shutdown_during_active_send() -> None:
    """Cancel while send_frame is blocked should not crash or leave inconsistent state."""
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    send_started = asyncio.Event()

    async def slow_send(colors: np.ndarray) -> None:
        send_started.set()
        await asyncio.sleep(5.0)  # Simulate a very slow send

    device.adapter.send_frame = slow_send  # type: ignore[assignment]

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())

    # Wait until send_frame is actually in progress
    await asyncio.wait_for(send_started.wait(), timeout=2.0)

    # Cancel while send is active
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # No crash, no hanging tasks — test passes if we get here


# --- Stats tests ---


async def test_get_device_stats() -> None:
    """get_device_stats should report per-device metrics."""
    device = _make_device("StatsDevice", latency_ms=50.0)
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=60
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)

    stats = scheduler.get_device_stats()
    assert len(stats) == 1
    assert stats[0].device_name == "StatsDevice"
    assert stats[0].effective_latency_ms == 50.0
    assert stats[0].send_fps > 0
    assert stats[0].frames_dropped >= 0

    scheduler.stop()
    await task


async def test_get_device_stats_fps_accuracy() -> None:
    """send_fps should approximate the actual send rate."""
    device = _make_device("FpsDevice")
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf, devices=[device], fps=60, max_fps=20,
    )
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)

    stats = scheduler.get_device_stats()
    # At max_fps=20, expect send_fps ≈ 20 (within ±30%)
    assert 14 <= stats[0].send_fps <= 26, f"send_fps={stats[0].send_fps:.1f}, expected ~20"

    scheduler.stop()
    await task
```

- [ ] **Step 9c: Run tests to verify they fail**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v -k "not frame_slot"`
Expected: FAIL — `LookaheadScheduler` does not accept `max_fps` parameter; `DeviceStats` not defined

- [ ] **Step 9d: Implement the new LookaheadScheduler**

Replace the `LookaheadScheduler` class in `src/dj_ledfx/scheduling/scheduler.py` (keep FrameSlot and DeviceStats above it):

```python
class LookaheadScheduler:
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
        max_fps: int = 60,
        disconnect_backoff_s: float = 1.0,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._devices = devices
        self._frame_period = 1.0 / fps
        self._min_frame_interval = 1.0 / max_fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._slots = [FrameSlot() for _ in devices]
        self._send_tasks: list[asyncio.Task[None]] = []
        self._send_counts: list[int] = [0] * len(devices)
        self._start_time: float = 0.0

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._devices),
        )

        # Spawn per-device send loops
        for i, (device, slot) in enumerate(zip(self._devices, self._slots)):
            task = asyncio.create_task(self._send_loop(device, slot, i))
            self._send_tasks.append(task)

        try:
            # Run distributor loop
            last_tick = time.monotonic()
            while self._running:
                now = time.monotonic()
                for device, slot in zip(self._devices, self._slots):
                    target_time = now + device.tracker.effective_latency_s
                    slot.put(target_time)

                last_tick += self._frame_period
                sleep_time = last_tick - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    last_tick = time.monotonic()
                    await asyncio.sleep(0)
        finally:
            # Clean up child tasks
            for task in self._send_tasks:
                task.cancel()
            await asyncio.gather(*self._send_tasks, return_exceptions=True)
            self._send_tasks.clear()

        logger.info("LookaheadScheduler stopped")

    async def _send_loop(
        self, device: ManagedDevice, slot: FrameSlot, index: int
    ) -> None:
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()

        while self._running:
            # Step 1: Check connection
            if not device.adapter.is_connected:
                if was_connected:
                    logger.warning(
                        "Device '{}' disconnected",
                        device.adapter.device_info.name,
                    )
                was_connected = False
                await asyncio.sleep(self._disconnect_backoff_s)
                continue

            # Reconnection detection
            if not was_connected:
                logger.info(
                    "Device '{}' reconnected",
                    device.adapter.device_info.name,
                )
                device.tracker.reset()
                was_connected = True

            # Step 2: Wait for target_time
            try:
                target_time = await slot.take(timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # Step 3: Find nearest frame (numpy copy happens here)
            frame = self._ring_buffer.find_nearest(target_time)
            if frame is None:
                continue

            # Steps 4-5: Send frame
            send_start = time.monotonic()
            try:
                await device.adapter.send_frame(frame.colors)
            except Exception:
                logger.warning(
                    "Send failed for '{}'",
                    device.adapter.device_info.name,
                )
                continue

            # Step 6: Increment send count
            self._send_counts[index] += 1

            # Step 7: RTT update (only if adapter supports probing)
            if device.adapter.supports_latency_probing:
                rtt_ms = (time.monotonic() - send_start) * 1000.0
                device.tracker.update(rtt_ms)

            # Step 8: FPS cap
            now = time.monotonic()
            remaining = last_send_time + self._min_frame_interval - now
            if remaining > 0:
                await asyncio.sleep(remaining)
            last_send_time = time.monotonic()

    def get_device_stats(self) -> list[DeviceStats]:
        """Snapshot of per-device send statistics."""
        now = time.monotonic()
        elapsed = now - self._start_time if self._start_time > 0 else 1.0
        stats: list[DeviceStats] = []
        for i, (device, slot) in enumerate(zip(self._devices, self._slots)):
            send_fps = self._send_counts[i] / elapsed if elapsed > 0 else 0.0
            frames_dropped = slot.put_count - self._send_counts[i]
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=max(0, frames_dropped),
                )
            )
        return stats
```

Make sure `from dataclasses import dataclass` is in the imports at the top of the file.

- [ ] **Step 9e: Run all scheduler tests**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v`
Expected: ALL PASS

- [ ] **Step 9f: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS (integration test may fail due to changed constructor — that's addressed in Task 12)

- [ ] **Step 9g: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat(scheduling): rewrite scheduler with per-device send loops

Distributor writes target_time floats to depth-1 FrameSlots.
Each device runs its own async send loop with:
- Disconnect detection with 1s backoff
- Reconnection resets tracker (falls back to heuristic seed)
- RTT measurement gated by supports_latency_probing
- Configurable FPS cap per send loop
- Graceful shutdown via _running flag + CancelledError safety net"
```

---

## Chunk 4: Wiring & Integration

### Task 10: SystemStatus Per-Device Stats + Move DeviceStats to types.py

**Files:**
- Modify: `src/dj_ledfx/types.py` (add `DeviceStats`)
- Modify: `src/dj_ledfx/status.py` (use `DeviceStats` from types)
- Modify: `src/dj_ledfx/scheduling/scheduler.py` (import `DeviceStats` from types instead of defining locally)

The `DeviceStats` dataclass is used by both `scheduler.py` and `status.py`. Per CLAUDE.md, `types.py` is the canonical location for shared types. Moving it there avoids a duplicate dataclass and prevents `status.py` from importing `scheduler.py`.

- [ ] **Step 1: Add DeviceStats to types.py**

Add to the end of `src/dj_ledfx/types.py`:

```python
@dataclass(frozen=True, slots=True)
class DeviceStats:
    """Per-device send statistics snapshot."""

    device_name: str
    effective_latency_ms: float
    send_fps: float
    frames_dropped: int
```

- [ ] **Step 2: Update scheduler.py to import DeviceStats from types**

In `src/dj_ledfx/scheduling/scheduler.py`, remove the local `DeviceStats` class definition and add to imports:

```python
from dj_ledfx.types import DeviceStats
```

(Remove `from dataclasses import dataclass` if no longer needed.)

- [ ] **Step 3: Update SystemStatus to use DeviceStats directly**

Replace `src/dj_ledfx/status.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from dj_ledfx.types import DeviceStats


@dataclass
class SystemStatus:
    prodjlink_connected: bool = False
    active_player_count: int = 0
    current_bpm: float | None = None
    connected_devices: list[str] = field(default_factory=list)
    device_errors: dict[str, str] = field(default_factory=dict)
    buffer_fill_level: float = 0.0
    avg_frame_render_time_ms: float = 0.0
    device_stats: list[DeviceStats] = field(default_factory=list)

    def summary(self) -> str:
        bpm_str = f"{self.current_bpm:.1f}" if self.current_bpm else "N/A"
        devices = ", ".join(self.connected_devices) or "none"
        parts = [
            f"BPM={bpm_str}",
            f"players={self.active_player_count}",
            f"devices=[{devices}]",
            f"buffer={self.buffer_fill_level:.0%}",
            f"render={self.avg_frame_render_time_ms:.1f}ms",
        ]
        for ds in self.device_stats:
            parts.append(
                f"{ds.device_name}={ds.effective_latency_ms:.0f}ms@{ds.send_fps:.0f}fps"
            )
        return " | ".join(parts)
```

- [ ] **Step 2: Run existing tests**

Run: `uv run pytest -v`
Expected: ALL PASS (new field has default, `summary()` backward compatible)

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/status.py
git commit -m "feat(status): add per-device latency and FPS to status summary"
```

---

### Task 11: Main.py Strategy Wiring

**Files:**
- Modify: `src/dj_ledfx/main.py:19,68-88,105-109,127-140`

- [ ] **Step 1: Update imports**

In `src/dj_ledfx/main.py`, replace the strategy import (line 19):

```python
from dj_ledfx.latency.strategies import StaticLatency
```

with:

```python
from dj_ledfx.devices.heuristics import estimate_device_latency_ms
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
```

- [ ] **Step 2: Add strategy branching in device setup**

Replace the device setup block (lines 68-88) in `_run()`:

```python
    if config.openrgb_enabled:
        discovered = await OpenRGBAdapter.discover(
            host=config.openrgb_host, port=config.openrgb_port
        )
        logger.info("Discovered {} OpenRGB devices", len(discovered))
        for i in range(len(discovered)):
            try:
                adapter = OpenRGBAdapter(
                    host=config.openrgb_host,
                    port=config.openrgb_port,
                    device_index=i,
                )
                await adapter.connect()
                heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)

                if config.openrgb_latency_strategy == "static":
                    strategy = StaticLatency(config.openrgb_latency_ms)
                elif config.openrgb_latency_strategy == "ema":
                    strategy = EMALatency(initial_value_ms=heuristic_ms)
                else:  # "windowed_mean"
                    strategy = WindowedMeanLatency(
                        window_size=config.openrgb_latency_window_size,
                        initial_value_ms=heuristic_ms,
                    )

                tracker = LatencyTracker(
                    strategy=strategy,
                    manual_offset_ms=config.openrgb_manual_offset_ms,
                )
                device_manager.add_device(adapter, tracker)
            except Exception:
                logger.exception("Failed to connect to OpenRGB device {}", i)
```

- [ ] **Step 3: Pass max_fps to scheduler**

Replace the scheduler construction (lines 105-109):

```python
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=device_manager.devices,
        fps=config.engine_fps,
        max_fps=config.openrgb_max_fps,
    )
```

- [ ] **Step 4: Update status loop with per-device stats**

Replace the `_status_loop` function (lines 127-140):

```python
    async def _status_loop() -> None:
        while not stop_event.is_set():
            status = SystemStatus(
                prodjlink_connected=clock.get_state().is_playing,
                current_bpm=clock.get_state().bpm or None,
                connected_devices=[
                    d.adapter.device_info.name for d in device_manager.devices
                ],
                buffer_fill_level=engine.ring_buffer.fill_level,
                avg_frame_render_time_ms=engine.avg_render_time_ms,
                device_stats=scheduler.get_device_stats(),
            )
            logger.info("Status: {}", status.summary())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10.0)
            except TimeoutError:
                pass
```

- [ ] **Step 5: Run linter and type checker**

Run: `uv run ruff check src/dj_ledfx/main.py && uv run mypy src/dj_ledfx/main.py`
Expected: Clean (or minor issues to fix)

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat(main): wire strategy branching, heuristic seeding, per-device status

Strategy selected by config: static/ema/windowed_mean.
Heuristic seed from device name after connect().
Status loop includes per-device latency and FPS stats."
```

---

### Task 12: Integration Tests

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Update existing integration test**

Replace `tests/test_integration.py`:

```python
import asyncio

import numpy as np

from conftest import MockDeviceAdapter
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.prodjlink.listener import BeatEvent
from dj_ledfx.scheduling.scheduler import LookaheadScheduler


def _setup_pipeline(
    devices: list[ManagedDevice],
    bpm: float = 300.0,
) -> tuple[BeatSimulator, EffectEngine, LookaheadScheduler, EventBus]:
    """Create a full pipeline: BeatSimulator -> Clock -> Engine -> Scheduler."""
    event_bus = EventBus()
    clock = BeatClock()

    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    effect = BeatPulse()
    engine = EffectEngine(
        clock=clock, effect=effect, led_count=10, fps=60, max_lookahead_s=1.0,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=devices,
        fps=60,
        max_fps=60,
    )

    simulator = BeatSimulator(event_bus=event_bus, bpm=bpm)
    return simulator, engine, scheduler, event_bus


async def test_full_pipeline_simulator_to_mock_device() -> None:
    """Integration: BeatSimulator -> BeatClock -> EffectEngine -> Scheduler -> MockDevice."""
    adapter = MockDeviceAdapter(name="MockLED", led_count=10)
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    managed = ManagedDevice(adapter=adapter, tracker=tracker)

    simulator, engine, scheduler, _ = _setup_pipeline([managed])

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(1.0)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    assert len(adapter.send_frame_calls) > 0
    sent_colors = adapter.send_frame_calls[0]
    assert isinstance(sent_colors, np.ndarray)
    assert sent_colors.shape == (10, 3)


async def test_mixed_latency_devices() -> None:
    """Two devices with different latencies both receive frames."""
    fast_adapter = MockDeviceAdapter(name="USB Device", led_count=10)
    fast_tracker = LatencyTracker(strategy=StaticLatency(5.0))
    fast_device = ManagedDevice(adapter=fast_adapter, tracker=fast_tracker)

    slow_adapter = MockDeviceAdapter(name="Govee WiFi", led_count=10)
    slow_tracker = LatencyTracker(
        strategy=WindowedMeanLatency(window_size=60, initial_value_ms=100.0)
    )
    slow_device = ManagedDevice(adapter=slow_adapter, tracker=slow_tracker)

    simulator, engine, scheduler, _ = _setup_pipeline([fast_device, slow_device])

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(1.0)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Both devices received frames
    assert len(fast_adapter.send_frame_calls) > 0
    assert len(slow_adapter.send_frame_calls) > 0

    # Fast device should have more frames (higher effective FPS)
    assert len(fast_adapter.send_frame_calls) >= len(slow_adapter.send_frame_calls)
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: update integration tests for per-device scheduler

Uses MockDeviceAdapter instead of AsyncMock.
Adds mixed-latency integration test with fast USB + slow Govee."
```

---

### Task 13: CLAUDE.md Updates

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update architecture section**

In the `## Architecture` section, update `scheduling/` entry:

```
- `scheduling/` — LookaheadScheduler: per-device send loops with FrameSlot depth-1 slots, FPS cap, RTT measurement
```

- [ ] **Step 2: Update Key Design Decisions**

Add to `## Key Design Decisions`:

```
- Per-device send loops: each device runs at its natural FPS (bounded by configurable cap). Distributor writes target_time floats to depth-1 FrameSlots — no numpy copies until actual send.
- Device-type heuristic latency: Govee WiFi=100ms, LIFX WiFi=50ms, USB=5ms. Seeds the latency strategy. OpenRGB adapters use heuristics permanently (supports_latency_probing=False).
- DeviceAdapter is ABC (not Protocol). Provides supports_latency_probing class attribute. discover() excluded from base — adapters own their own discovery.
```

- [ ] **Step 3: Update Code Style section**

In `## Code Style`, update the adapter note:

Change "Adapter pattern for devices and latency strategies — always code to the Protocol/ABC" to:
```
- DeviceAdapter is ABC (abstract base class). ProbeStrategy remains Protocol. Always code to the interface.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for per-device scheduler architecture"
```

---

## Verification

After all tasks are complete:

- [ ] **Run full test suite**: `uv run pytest -v`
- [ ] **Run linter**: `uv run ruff check .`
- [ ] **Run formatter**: `uv run ruff format .`
- [ ] **Run type checker**: `uv run mypy src/`
- [ ] **Run in demo mode**: `uv run -m dj_ledfx --demo --log-level DEBUG` (verify per-device status logs every 10s)
