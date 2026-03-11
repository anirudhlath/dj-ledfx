# dj-ledfx MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a beat-synced LED effect engine driven by Pro DJ Link network data, proving the full pipeline end-to-end with a BeatPulse effect across OpenRGB devices.

**Architecture:** Passive UDP listener captures beat packets → BeatClock interpolates continuous phase → EffectEngine renders future frames into a timestamped ring buffer → LookaheadScheduler dispatches frames to each device offset by its measured latency, so all lights hit beats simultaneously.

**Tech Stack:** Python 3.11+, uv (package management), numpy (array math), openrgb-python (device control), loguru (logging), ruff (lint/format), mypy (type checking), pytest + pytest-asyncio (testing)

**Spec:** `docs/superpowers/specs/2026-03-11-dj-ledfx-mvp-design.md`

---

## Chunk 1: Project Foundation

### Task 1: Initialize project with uv

**Files:**
- Create: `pyproject.toml` (via uv init)
- Create: `src/dj_ledfx/__init__.py`
- Create: `src/dj_ledfx/__main__.py`

- [ ] **Step 1: Initialize project with src layout**

```bash
cd /Users/anirudhlath/code/private/dj-ledfx
uv init --lib --package --name dj-ledfx
```

This creates `pyproject.toml` and `src/dj_ledfx/__init__.py`.

- [ ] **Step 2: Verify the generated pyproject.toml and fix it**

The generated `pyproject.toml` needs adjustments. Replace its content with:

```toml
[project]
name = "dj-ledfx"
version = "0.1.0"
description = "Beat-synced LED effect engine driven by Pro DJ Link network data"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "loguru",
    "numpy",
    "openrgb-python",
]

[project.scripts]
dj-ledfx = "dj_ledfx.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/dj_ledfx"]

[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "TCH"]

[tool.mypy]
strict = true
python_version = "3.11"
mypy_path = "src"
packages = ["dj_ledfx"]
plugins = []

[[tool.mypy.overrides]]
module = ["openrgb.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: Add dev dependencies**

```bash
uv add --dev pytest pytest-asyncio ruff mypy
```

- [ ] **Step 4: Create __main__.py for `uv run -m dj_ledfx`**

Create `src/dj_ledfx/__main__.py`:

```python
from dj_ledfx.main import main

main()
```

This is a stub — `main.py` will be built in Task 12.

- [ ] **Step 5: Create all package directories**

```bash
mkdir -p src/dj_ledfx/prodjlink
mkdir -p src/dj_ledfx/beat
mkdir -p src/dj_ledfx/effects
mkdir -p src/dj_ledfx/scheduling
mkdir -p src/dj_ledfx/devices
mkdir -p src/dj_ledfx/latency
```

Create `__init__.py` in each:

```bash
touch src/dj_ledfx/prodjlink/__init__.py
touch src/dj_ledfx/beat/__init__.py
touch src/dj_ledfx/effects/__init__.py
touch src/dj_ledfx/scheduling/__init__.py
touch src/dj_ledfx/devices/__init__.py
touch src/dj_ledfx/latency/__init__.py
```

- [ ] **Step 6: Create test directories**

```bash
mkdir -p tests/fixtures
mkdir -p tests/prodjlink
mkdir -p tests/beat
mkdir -p tests/effects
mkdir -p tests/scheduling
mkdir -p tests/devices
mkdir -p tests/latency
```

Create `conftest.py` and `__init__.py` files:

```bash
touch tests/conftest.py
touch tests/prodjlink/__init__.py
touch tests/beat/__init__.py
touch tests/effects/__init__.py
touch tests/scheduling/__init__.py
touch tests/devices/__init__.py
touch tests/latency/__init__.py
```

- [ ] **Step 7: Create .gitignore**

Replace `.gitignore` with:

```
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.egg
.DS_Store
```

- [ ] **Step 8: Verify toolchain works**

```bash
uv run python -c "import dj_ledfx; print('ok')"
uv run ruff check src/
uv run pytest --co  # collect only, no tests yet
```

Expected: all succeed with no errors.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock src/ tests/ .gitignore .python-version
git commit -m "chore: initialize project with uv, src layout, and toolchain"
```

---

### Task 2: Shared types (`types.py`)

**Files:**
- Create: `src/dj_ledfx/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
import numpy as np

from dj_ledfx.types import RGB, BeatState, DeviceInfo, RenderedFrame


def test_rgb_type_alias() -> None:
    color: RGB = (255, 0, 128)
    assert len(color) == 3


def test_device_info() -> None:
    info = DeviceInfo(
        name="Test LED",
        device_type="openrgb",
        led_count=60,
        address="127.0.0.1:6742",
    )
    assert info.name == "Test LED"
    assert info.led_count == 60


def test_rendered_frame() -> None:
    colors = np.zeros((10, 3), dtype=np.uint8)
    frame = RenderedFrame(
        colors=colors,
        target_time=1000.0,
        beat_phase=0.5,
        bar_phase=0.125,
    )
    assert frame.colors.shape == (10, 3)
    assert frame.target_time == 1000.0


def test_beat_state() -> None:
    state = BeatState(
        beat_phase=0.25,
        bar_phase=0.0625,
        bpm=128.0,
        is_playing=True,
        next_beat_time=1000.5,
    )
    assert state.bpm == 128.0
    assert state.is_playing is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_types.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'dj_ledfx.types'`

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

RGB = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    name: str
    device_type: str
    led_count: int
    address: str


@dataclass(slots=True)
class RenderedFrame:
    colors: NDArray[np.uint8]  # shape (n_leds, 3)
    target_time: float  # monotonic time when this should be displayed
    beat_phase: float
    bar_phase: float


@dataclass(frozen=True, slots=True)
class BeatState:
    beat_phase: float  # 0.0 → 1.0
    bar_phase: float  # 0.0 → 1.0
    bpm: float
    is_playing: bool
    next_beat_time: float  # monotonic timestamp
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_types.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run linters**

```bash
uv run ruff check src/dj_ledfx/types.py
uv run mypy src/dj_ledfx/types.py
```

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/types.py tests/test_types.py
git commit -m "feat: add shared types (RGB, DeviceInfo, RenderedFrame, BeatState)"
```

---

### Task 3: Event bus (`events.py`)

**Files:**
- Create: `src/dj_ledfx/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_events.py`:

```python
from dataclasses import dataclass

from dj_ledfx.events import EventBus


@dataclass
class FakeEvent:
    value: int


@dataclass
class OtherEvent:
    name: str


def test_subscribe_and_emit() -> None:
    bus = EventBus()
    received: list[FakeEvent] = []
    bus.subscribe(FakeEvent, received.append)
    bus.emit(FakeEvent(value=42))
    assert len(received) == 1
    assert received[0].value == 42


def test_multiple_subscribers() -> None:
    bus = EventBus()
    a: list[FakeEvent] = []
    b: list[FakeEvent] = []
    bus.subscribe(FakeEvent, a.append)
    bus.subscribe(FakeEvent, b.append)
    bus.emit(FakeEvent(value=1))
    assert len(a) == 1
    assert len(b) == 1


def test_different_event_types_isolated() -> None:
    bus = EventBus()
    fakes: list[FakeEvent] = []
    others: list[OtherEvent] = []
    bus.subscribe(FakeEvent, fakes.append)
    bus.subscribe(OtherEvent, others.append)
    bus.emit(FakeEvent(value=1))
    assert len(fakes) == 1
    assert len(others) == 0


def test_unsubscribe() -> None:
    bus = EventBus()
    received: list[FakeEvent] = []
    bus.subscribe(FakeEvent, received.append)
    bus.unsubscribe(FakeEvent, received.append)
    bus.emit(FakeEvent(value=1))
    assert len(received) == 0


def test_emit_with_no_subscribers_does_not_raise() -> None:
    bus = EventBus()
    bus.emit(FakeEvent(value=1))  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_events.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/events.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from loguru import logger


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[..., Any]]] = defaultdict(list)

    def subscribe(self, event_type: type, callback: Callable[..., Any]) -> None:
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: type, callback: Callable[..., Any]) -> None:
        try:
            self._subscribers[event_type].remove(callback)
        except ValueError:
            pass

    def emit(self, event: object) -> None:
        for callback in self._subscribers.get(type(event), []):
            try:
                callback(event)
            except Exception:
                logger.exception("Event callback failed for {}", type(event).__name__)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_events.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/events.py tests/test_events.py
git commit -m "feat: add typed event bus with subscribe/unsubscribe/emit"
```

---

### Task 4: Configuration (`config.py`)

**Files:**
- Create: `src/dj_ledfx/config.py`
- Create: `config.example.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import textwrap
from pathlib import Path

from dj_ledfx.config import AppConfig, load_config


def test_default_config() -> None:
    config = AppConfig()
    assert config.network_interface == "auto"
    assert config.engine_fps == 60
    assert config.max_lookahead_ms == 1000
    assert config.active_effect == "beat_pulse"
    assert config.openrgb_host == "127.0.0.1"
    assert config.openrgb_port == 6742


def test_load_config_from_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(textwrap.dedent("""\
        [network]
        interface = "eth0"

        [engine]
        fps = 30
        max_lookahead_ms = 500

        [effect]
        active = "beat_pulse"

        [effect.beat_pulse]
        gamma = 3.0

        [devices.openrgb]
        host = "192.168.1.100"
        port = 6742
        latency_ms = 20
    """))
    config = load_config(toml_file)
    assert config.network_interface == "eth0"
    assert config.engine_fps == 30
    assert config.max_lookahead_ms == 500
    assert config.openrgb_host == "192.168.1.100"
    assert config.beat_pulse_gamma == 3.0
    assert config.openrgb_latency_ms == 20


def test_load_config_missing_file_returns_defaults() -> None:
    config = load_config(Path("/nonexistent/config.toml"))
    assert config.engine_fps == 60


def test_config_validation_bad_fps() -> None:
    import pytest

    with pytest.raises(ValueError, match="fps"):
        AppConfig(engine_fps=0)


def test_config_validation_bad_lookahead() -> None:
    import pytest

    with pytest.raises(ValueError, match="max_lookahead_ms"):
        AppConfig(max_lookahead_ms=-1)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/config.py`:

```python
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class AppConfig:
    # Network
    network_interface: str = "auto"

    # Pro DJ Link
    passive_mode: bool = True

    # Engine
    engine_fps: int = 60
    max_lookahead_ms: int = 1000

    # Effect
    active_effect: str = "beat_pulse"
    beat_pulse_palette: list[str] = field(
        default_factory=lambda: ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
    )
    beat_pulse_gamma: float = 2.0

    # OpenRGB
    openrgb_enabled: bool = True
    openrgb_host: str = "127.0.0.1"
    openrgb_port: int = 6742
    openrgb_latency_strategy: str = "static"
    openrgb_latency_ms: float = 10.0
    openrgb_manual_offset_ms: float = 0.0

    def __post_init__(self) -> None:
        errors: list[str] = []
        if self.engine_fps <= 0:
            errors.append("fps must be positive")
        if self.max_lookahead_ms < 0:
            errors.append("max_lookahead_ms must be non-negative")
        if self.beat_pulse_gamma <= 0:
            errors.append("beat_pulse gamma must be positive")
        if errors:
            raise ValueError(f"Config validation failed: {'; '.join(errors)}")


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        logger.info("No config file at {}, using defaults", path)
        return AppConfig()

    logger.info("Loading config from {}", path)
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    kwargs: dict[str, object] = {}

    if "network" in raw:
        if "interface" in raw["network"]:
            kwargs["network_interface"] = raw["network"]["interface"]

    if "prodjlink" in raw:
        if "passive_mode" in raw["prodjlink"]:
            kwargs["passive_mode"] = raw["prodjlink"]["passive_mode"]

    if "engine" in raw:
        if "fps" in raw["engine"]:
            kwargs["engine_fps"] = raw["engine"]["fps"]
        if "max_lookahead_ms" in raw["engine"]:
            kwargs["max_lookahead_ms"] = raw["engine"]["max_lookahead_ms"]

    if "effect" in raw:
        if "active" in raw["effect"]:
            kwargs["active_effect"] = raw["effect"]["active"]
        bp = raw["effect"].get("beat_pulse", {})
        if "palette" in bp:
            kwargs["beat_pulse_palette"] = bp["palette"]
        if "gamma" in bp:
            kwargs["beat_pulse_gamma"] = bp["gamma"]

    if "devices" in raw and "openrgb" in raw["devices"]:
        orgb = raw["devices"]["openrgb"]
        if "enabled" in orgb:
            kwargs["openrgb_enabled"] = orgb["enabled"]
        if "host" in orgb:
            kwargs["openrgb_host"] = orgb["host"]
        if "port" in orgb:
            kwargs["openrgb_port"] = orgb["port"]
        if "latency_strategy" in orgb:
            kwargs["openrgb_latency_strategy"] = orgb["latency_strategy"]
        if "latency_ms" in orgb:
            kwargs["openrgb_latency_ms"] = orgb["latency_ms"]
        if "manual_offset_ms" in orgb:
            kwargs["openrgb_manual_offset_ms"] = orgb["manual_offset_ms"]

    return AppConfig(**kwargs)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Create config.example.toml**

Create `config.example.toml` at project root:

```toml
[network]
interface = "auto"

[prodjlink]
passive_mode = true

[engine]
fps = 60
max_lookahead_ms = 1000

[effect]
active = "beat_pulse"

[effect.beat_pulse]
palette = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
gamma = 2.0

[devices.openrgb]
enabled = true
host = "127.0.0.1"
port = 6742
latency_strategy = "static"
latency_ms = 10
manual_offset_ms = 0
```

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py config.example.toml
git commit -m "feat: add TOML config loading with validation and defaults"
```

---

## Chunk 2: Pro DJ Link Protocol

### Task 5: ProDJLink constants (`prodjlink/constants.py`)

**Files:**
- Create: `src/dj_ledfx/prodjlink/constants.py`

- [ ] **Step 1: Write the implementation**

Create `src/dj_ledfx/prodjlink/constants.py`:

```python
# Pro DJ Link protocol constants
# Reference: https://djl-analysis.deepsymmetry.org/djl-analysis/beats.html

# Network
PRODJLINK_PORT = 50001  # Beat/sync broadcast port (passive, no handshake)
STATUS_PORT = 50002  # Status port (requires virtual CDJ — not used in MVP)

# Packet header
MAGIC_HEADER = b"Qspt1WmJOL"  # 10 bytes, all Pro DJ Link packets start with this
MAGIC_HEADER_LEN = 10

# Packet type byte (offset 0x0A, after magic header)
PACKET_TYPE_BEAT = 0x28  # Beat packet

# Beat packet structure (96 bytes total)
BEAT_PACKET_LEN = 96

# Byte offsets within beat packet (after magic header)
OFFSET_PACKET_TYPE = 0x0A  # 1 byte: packet type
OFFSET_DEVICE_NAME = 0x0B  # 20 bytes: device name (null-padded ASCII)
OFFSET_DEVICE_NUMBER = 0x21  # 1 byte: player/device number (1-6)
OFFSET_NEXT_BEAT_MS = 0x24  # 4 bytes: ms until next beat (big-endian uint32)
OFFSET_SECOND_BEAT_MS = 0x28  # 4 bytes: ms until 2nd next beat
OFFSET_NEXT_BAR_MS = 0x34  # 4 bytes: ms until next bar downbeat
OFFSET_BPM = 0x5A  # 2 bytes: BPM × 100 (big-endian uint16), e.g., 12800 = 128.00
OFFSET_PITCH = 0x54  # 4 bytes: pitch adjustment (see below)
OFFSET_BEAT_NUMBER = 0x5C  # 1 byte: beat within bar (1-4)

# Pitch encoding: value is centered at 0x00100000 (1048576)
# pitch_percent = (raw - 1048576) / 10485.76
PITCH_CENTER = 0x00100000
PITCH_SCALE = 10485.76

# Capability byte for CDJ-3000 generation
CAPABILITY_CDJ3000 = 0x1F
OFFSET_CAPABILITY = 0x25  # 1 byte
```

- [ ] **Step 2: Run linter**

```bash
uv run ruff check src/dj_ledfx/prodjlink/constants.py
```

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/prodjlink/constants.py
git commit -m "feat: add Pro DJ Link protocol constants and byte offsets"
```

---

### Task 6: Packet parsing (`prodjlink/packets.py`)

**Files:**
- Create: `src/dj_ledfx/prodjlink/packets.py`
- Create: `tests/prodjlink/test_packets.py`
- Create: `tests/fixtures/beat_packet_128bpm.bin` (generated in test)

- [ ] **Step 1: Write the failing test**

Create `tests/prodjlink/test_packets.py`:

```python
import struct

from dj_ledfx.prodjlink.constants import (
    BEAT_PACKET_LEN,
    CAPABILITY_CDJ3000,
    MAGIC_HEADER,
    OFFSET_BEAT_NUMBER,
    OFFSET_BPM,
    OFFSET_CAPABILITY,
    OFFSET_DEVICE_NAME,
    OFFSET_DEVICE_NUMBER,
    OFFSET_NEXT_BEAT_MS,
    OFFSET_PACKET_TYPE,
    OFFSET_PITCH,
    PACKET_TYPE_BEAT,
    PITCH_CENTER,
)
from dj_ledfx.prodjlink.packets import BeatPacket, parse_beat_packet


def _build_beat_packet(
    *,
    bpm_raw: int = 12800,  # 128.00 BPM
    pitch_raw: int = PITCH_CENTER,  # 0% pitch
    beat_number: int = 1,
    next_beat_ms: int = 468,
    device_number: int = 1,
    device_name: str = "XDJ-AZ",
    capability: int = CAPABILITY_CDJ3000,
) -> bytes:
    """Build a synthetic beat packet for testing."""
    buf = bytearray(BEAT_PACKET_LEN)
    buf[0:10] = MAGIC_HEADER
    buf[OFFSET_PACKET_TYPE] = PACKET_TYPE_BEAT
    name_bytes = device_name.encode("ascii")[:20].ljust(20, b"\x00")
    buf[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20] = name_bytes
    buf[OFFSET_DEVICE_NUMBER] = device_number
    struct.pack_into(">I", buf, OFFSET_NEXT_BEAT_MS, next_beat_ms)
    struct.pack_into(">I", buf, OFFSET_PITCH, pitch_raw)
    struct.pack_into(">H", buf, OFFSET_BPM, bpm_raw)
    buf[OFFSET_BEAT_NUMBER] = beat_number
    buf[OFFSET_CAPABILITY] = capability
    return bytes(buf)


def test_parse_basic_beat_packet() -> None:
    data = _build_beat_packet()
    result = parse_beat_packet(data)
    assert result is not None
    assert isinstance(result, BeatPacket)
    assert result.bpm == 128.0
    assert result.pitch_percent == 0.0
    assert result.beat_number == 1
    assert result.next_beat_ms == 468
    assert result.device_number == 1
    assert result.device_name == "XDJ-AZ"


def test_parse_pitched_bpm() -> None:
    # +6% pitch: pitch_raw = PITCH_CENTER + 6 * 10485.76
    pitch_raw = PITCH_CENTER + int(6.0 * 10485.76)
    data = _build_beat_packet(bpm_raw=12800, pitch_raw=pitch_raw)
    result = parse_beat_packet(data)
    assert result is not None
    assert abs(result.pitch_percent - 6.0) < 0.01
    assert abs(result.pitch_adjusted_bpm - 128.0 * 1.06) < 0.1


def test_parse_rejects_wrong_magic() -> None:
    data = b"\x00" * BEAT_PACKET_LEN
    result = parse_beat_packet(data)
    assert result is None


def test_parse_rejects_short_packet() -> None:
    result = parse_beat_packet(b"\x00" * 10)
    assert result is None


def test_parse_rejects_non_beat_packet() -> None:
    data = bytearray(_build_beat_packet())
    data[OFFSET_PACKET_TYPE] = 0x0A  # not a beat packet
    result = parse_beat_packet(bytes(data))
    assert result is None


def test_parse_rejects_old_hardware() -> None:
    data = _build_beat_packet(capability=0x11)  # NXS2, not CDJ-3000
    result = parse_beat_packet(data)
    assert result is None


def test_beat_number_values() -> None:
    for beat in (1, 2, 3, 4):
        data = _build_beat_packet(beat_number=beat)
        result = parse_beat_packet(data)
        assert result is not None
        assert result.beat_number == beat
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/prodjlink/test_packets.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/prodjlink/packets.py`:

```python
from __future__ import annotations

import struct
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.prodjlink.constants import (
    BEAT_PACKET_LEN,
    CAPABILITY_CDJ3000,
    MAGIC_HEADER,
    OFFSET_BEAT_NUMBER,
    OFFSET_BPM,
    OFFSET_CAPABILITY,
    OFFSET_DEVICE_NAME,
    OFFSET_DEVICE_NUMBER,
    OFFSET_NEXT_BEAT_MS,
    OFFSET_PACKET_TYPE,
    OFFSET_PITCH,
    PACKET_TYPE_BEAT,
    PITCH_CENTER,
    PITCH_SCALE,
)


@dataclass(frozen=True, slots=True)
class BeatPacket:
    device_name: str
    device_number: int
    bpm: float  # raw BPM from packet (not pitch-adjusted)
    pitch_percent: float  # pitch adjustment as percentage (-100 to +100)
    beat_number: int  # 1-4 within bar
    next_beat_ms: int  # ms until next beat

    @property
    def pitch_adjusted_bpm(self) -> float:
        return self.bpm * (1.0 + self.pitch_percent / 100.0)


def parse_beat_packet(data: bytes) -> BeatPacket | None:
    if len(data) < BEAT_PACKET_LEN:
        return None

    if data[:len(MAGIC_HEADER)] != MAGIC_HEADER:
        return None

    if data[OFFSET_PACKET_TYPE] != PACKET_TYPE_BEAT:
        return None

    capability = data[OFFSET_CAPABILITY]
    if capability != CAPABILITY_CDJ3000:
        logger.debug("Ignoring packet from non-CDJ3000 hardware (capability=0x{:02X})", capability)
        return None

    device_name = data[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20].split(b"\x00")[0].decode(
        "ascii", errors="replace"
    )
    device_number = data[OFFSET_DEVICE_NUMBER]
    (next_beat_ms,) = struct.unpack_from(">I", data, OFFSET_NEXT_BEAT_MS)
    (pitch_raw,) = struct.unpack_from(">I", data, OFFSET_PITCH)
    (bpm_raw,) = struct.unpack_from(">H", data, OFFSET_BPM)
    beat_number = data[OFFSET_BEAT_NUMBER]

    bpm = bpm_raw / 100.0
    pitch_percent = (pitch_raw - PITCH_CENTER) / PITCH_SCALE

    return BeatPacket(
        device_name=device_name,
        device_number=device_number,
        bpm=bpm,
        pitch_percent=pitch_percent,
        beat_number=beat_number,
        next_beat_ms=next_beat_ms,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/prodjlink/test_packets.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/prodjlink/packets.py tests/prodjlink/test_packets.py
git commit -m "feat: add Pro DJ Link beat packet parser with validation"
```

---

### Task 7: ProDJLink UDP listener (`prodjlink/listener.py`)

**Files:**
- Create: `src/dj_ledfx/prodjlink/listener.py`
- Test: `tests/prodjlink/test_listener.py`

- [ ] **Step 1: Write the failing test**

Create `tests/prodjlink/test_listener.py`:

```python
import asyncio
import struct

from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.constants import (
    BEAT_PACKET_LEN,
    CAPABILITY_CDJ3000,
    MAGIC_HEADER,
    OFFSET_BEAT_NUMBER,
    OFFSET_BPM,
    OFFSET_CAPABILITY,
    OFFSET_DEVICE_NAME,
    OFFSET_DEVICE_NUMBER,
    OFFSET_NEXT_BEAT_MS,
    OFFSET_PACKET_TYPE,
    OFFSET_PITCH,
    PACKET_TYPE_BEAT,
    PITCH_CENTER,
)
from dj_ledfx.prodjlink.listener import BeatEvent, ProDJLinkListener


def _build_beat_packet(
    bpm_raw: int = 12800,
    beat_number: int = 1,
    device_number: int = 1,
) -> bytes:
    buf = bytearray(BEAT_PACKET_LEN)
    buf[0:10] = MAGIC_HEADER
    buf[OFFSET_PACKET_TYPE] = PACKET_TYPE_BEAT
    name = b"XDJ-AZ".ljust(20, b"\x00")
    buf[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20] = name
    buf[OFFSET_DEVICE_NUMBER] = device_number
    struct.pack_into(">I", buf, OFFSET_NEXT_BEAT_MS, 468)
    struct.pack_into(">I", buf, OFFSET_PITCH, PITCH_CENTER)
    struct.pack_into(">H", buf, OFFSET_BPM, bpm_raw)
    buf[OFFSET_BEAT_NUMBER] = beat_number
    buf[OFFSET_CAPABILITY] = CAPABILITY_CDJ3000
    return bytes(buf)


async def test_listener_emits_beat_event() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    listener = ProDJLinkListener(event_bus=bus)

    # Simulate receiving a packet by calling the protocol method directly
    listener.datagram_received(_build_beat_packet(), ("192.168.1.1", 50001))

    assert len(events) == 1
    assert events[0].bpm == 128.0
    assert events[0].beat_position == 1


async def test_listener_ignores_invalid_packets() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    listener = ProDJLinkListener(event_bus=bus)
    listener.datagram_received(b"\x00" * 50, ("192.168.1.1", 50001))

    assert len(events) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/prodjlink/test_listener.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/prodjlink/listener.py`:

```python
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.packets import parse_beat_packet


@dataclass(frozen=True, slots=True)
class BeatEvent:
    bpm: float  # pitch-adjusted BPM
    beat_position: int  # 1-4
    next_beat_ms: int
    device_number: int
    device_name: str
    timestamp: float  # time.monotonic()


class ProDJLinkListener(asyncio.DatagramProtocol):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport  # type: ignore[assignment]
        logger.info("ProDJLink listener started")

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("ProDJLink listener stopped")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        packet = parse_beat_packet(data)
        if packet is None:
            return

        event = BeatEvent(
            bpm=packet.pitch_adjusted_bpm,
            beat_position=packet.beat_number,
            next_beat_ms=packet.next_beat_ms,
            device_number=packet.device_number,
            device_name=packet.device_name,
            timestamp=time.monotonic(),
        )
        logger.debug(
            "Beat: {} BPM={:.1f} beat={}/4 from {}",
            event.device_name,
            event.bpm,
            event.beat_position,
            addr[0],
        )
        self._event_bus.emit(event)

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()


async def start_listener(
    event_bus: EventBus,
    interface: str = "0.0.0.0",
    port: int = 50001,
) -> ProDJLinkListener:
    loop = asyncio.get_running_loop()
    _transport, protocol = await loop.create_datagram_endpoint(
        lambda: ProDJLinkListener(event_bus),
        local_addr=(interface, port),
        allow_broadcast=True,
    )
    logger.info("Listening for Pro DJ Link beats on {}:{}", interface, port)
    return protocol  # type: ignore[return-value]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/prodjlink/test_listener.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/prodjlink/listener.py tests/prodjlink/test_listener.py
git commit -m "feat: add ProDJLink passive UDP listener with beat event emission"
```

---

## Chunk 3: Beat Tracking

### Task 8: BeatClock (`beat/clock.py`)

**Files:**
- Create: `src/dj_ledfx/beat/clock.py`
- Test: `tests/beat/test_clock.py`

- [ ] **Step 1: Write the failing test**

Create `tests/beat/test_clock.py`:

```python
import time

from dj_ledfx.beat.clock import BeatClock


def test_initial_state() -> None:
    clock = BeatClock()
    state = clock.get_state()
    assert state.is_playing is False
    assert state.bpm == 0.0
    assert state.beat_phase == 0.0
    assert state.bar_phase == 0.0


def test_on_beat_starts_playing() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=128.0, beat_number=1, next_beat_ms=468, timestamp=now)
    state = clock.get_state()
    assert state.is_playing is True
    assert state.bpm == 128.0


def test_phase_advances_between_beats() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    # Simulate time passing by querying at a future time
    # beat_period = 60/120 = 0.5s. Half a beat period = 0.25s
    state = clock.get_state_at(now + 0.25)
    assert 0.4 < state.beat_phase < 0.6  # roughly half way


def test_bar_phase_tracks_beat_position() -> None:
    clock = BeatClock()
    now = time.monotonic()
    # beat 3 of 4 → bar_phase should be around 0.5 (2/4)
    clock.on_beat(bpm=120.0, beat_number=3, next_beat_ms=500, timestamp=now)
    state = clock.get_state_at(now)
    assert 0.49 < state.bar_phase < 0.51


def test_stops_after_timeout() -> None:
    clock = BeatClock(timeout_s=2.0)
    now = time.monotonic()
    clock.on_beat(bpm=128.0, beat_number=1, next_beat_ms=468, timestamp=now)
    # 3 seconds later, no new beats → should be stopped
    state = clock.get_state_at(now + 3.0)
    assert state.is_playing is False


def test_hard_snap_on_large_drift() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    # Second beat arrives 10ms late (drift >= 5ms → hard snap)
    clock.on_beat(bpm=120.0, beat_number=2, next_beat_ms=500, timestamp=now + 0.510)
    state = clock.get_state_at(now + 0.510)
    # After hard snap, phase should be near 0.0 (just got a beat)
    assert state.beat_phase < 0.05


def test_extrapolate_future_phase() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    # 1 second in the future = 2 full beats at 120 BPM
    state = clock.get_state_at(now + 1.0)
    # Should wrap around: 2 beats = phase back near 0.0
    assert state.beat_phase < 0.05 or state.beat_phase > 0.95
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/beat/test_clock.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/beat/clock.py`:

```python
from __future__ import annotations

from loguru import logger

from dj_ledfx.types import BeatState

_DRIFT_HARD_SNAP_MS = 5.0


class BeatClock:
    def __init__(self, timeout_s: float = 2.0) -> None:
        self._timeout_s = timeout_s
        self._bpm: float = 0.0
        self._beat_period: float = 0.0  # seconds per beat
        self._last_beat_time: float = 0.0  # monotonic timestamp of last beat
        self._last_beat_number: int = 1  # 1-4
        self._is_playing: bool = False
        self._last_packet_time: float = 0.0

    def on_beat(
        self,
        bpm: float,
        beat_number: int,
        next_beat_ms: int,
        timestamp: float,
    ) -> None:
        if bpm <= 0:
            return

        new_beat_period = 60.0 / bpm

        if self._is_playing and self._beat_period > 0:
            # Calculate drift: where we predicted this beat vs where it actually is
            predicted_beat_time = self._last_beat_time + self._beat_period
            drift_ms = abs(timestamp - predicted_beat_time) * 1000.0

            if drift_ms < _DRIFT_HARD_SNAP_MS:
                # Soft correction: adjust BPM slightly to converge
                correction = (timestamp - predicted_beat_time) / new_beat_period
                adjusted_period = new_beat_period * (1.0 + correction * 0.1)
                self._beat_period = adjusted_period
                logger.trace("Beat drift {:.1f}ms — soft correction", drift_ms)
            else:
                # Hard snap
                self._beat_period = new_beat_period
                logger.debug("Beat drift {:.1f}ms — hard snap", drift_ms)
        else:
            self._beat_period = new_beat_period

        self._bpm = bpm
        self._last_beat_time = timestamp
        self._last_beat_number = beat_number
        self._last_packet_time = timestamp
        self._is_playing = True

    def get_state(self) -> BeatState:
        import time

        return self.get_state_at(time.monotonic())

    def get_state_at(self, at_time: float) -> BeatState:
        if not self._is_playing or self._bpm <= 0:
            return BeatState(
                beat_phase=0.0,
                bar_phase=0.0,
                bpm=0.0,
                is_playing=False,
                next_beat_time=0.0,
            )

        # Check timeout
        elapsed_since_packet = at_time - self._last_packet_time
        if elapsed_since_packet > self._timeout_s:
            return BeatState(
                beat_phase=0.0,
                bar_phase=0.0,
                bpm=self._bpm,
                is_playing=False,
                next_beat_time=0.0,
            )

        # Interpolate phase
        elapsed = at_time - self._last_beat_time
        beats_elapsed = elapsed / self._beat_period
        beat_phase = beats_elapsed % 1.0

        # Bar phase: beat_number is 1-4, each beat is 0.25 of the bar
        # At the moment of beat N, bar_phase = (N-1)/4
        # Then it advances within the beat
        bar_beat_index = (self._last_beat_number - 1 + beats_elapsed) % 4.0
        bar_phase = bar_beat_index / 4.0

        # Next beat time
        beats_to_next = 1.0 - beat_phase
        next_beat_time = at_time + beats_to_next * self._beat_period

        return BeatState(
            beat_phase=beat_phase,
            bar_phase=bar_phase,
            bpm=self._bpm,
            is_playing=True,
            next_beat_time=next_beat_time,
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/beat/test_clock.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/beat/clock.py tests/beat/test_clock.py
git commit -m "feat: add BeatClock with phase interpolation and drift correction"
```

---

### Task 9: BeatSimulator (`beat/simulator.py`)

**Files:**
- Create: `src/dj_ledfx/beat/simulator.py`
- Test: `tests/beat/test_simulator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/beat/test_simulator.py`:

```python
import asyncio

from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.listener import BeatEvent


async def test_simulator_emits_beats() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    sim = BeatSimulator(event_bus=bus, bpm=300.0)  # fast BPM for quick test
    task = asyncio.create_task(sim.run())

    await asyncio.sleep(0.5)  # ~2.5 beats at 300 BPM
    sim.stop()
    await task

    assert len(events) >= 2
    assert all(e.bpm == 300.0 for e in events)


async def test_simulator_cycles_beat_positions() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    sim = BeatSimulator(event_bus=bus, bpm=600.0)  # very fast for test
    task = asyncio.create_task(sim.run())

    await asyncio.sleep(0.5)  # ~5 beats
    sim.stop()
    await task

    positions = [e.beat_position for e in events]
    # Should cycle 1, 2, 3, 4, 1, 2, ...
    assert positions[0] == 1
    if len(positions) >= 4:
        assert positions[3] == 4
    if len(positions) >= 5:
        assert positions[4] == 1


async def test_simulator_stop() -> None:
    bus = EventBus()
    sim = BeatSimulator(event_bus=bus, bpm=120.0)
    task = asyncio.create_task(sim.run())
    sim.stop()
    await asyncio.wait_for(task, timeout=1.0)  # should finish quickly
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/beat/test_simulator.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/beat/simulator.py`:

```python
from __future__ import annotations

import asyncio
import time

from loguru import logger

from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.listener import BeatEvent


class BeatSimulator:
    def __init__(
        self,
        event_bus: EventBus,
        bpm: float = 128.0,
    ) -> None:
        self._event_bus = event_bus
        self._bpm = bpm
        self._running = False
        self._beat_number = 0  # will start at 1

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        beat_period = 60.0 / self._bpm
        logger.info("BeatSimulator started at {:.1f} BPM", self._bpm)

        next_beat = time.monotonic()

        while self._running:
            now = time.monotonic()
            if now < next_beat:
                await asyncio.sleep(next_beat - now)
                if not self._running:
                    break

            self._beat_number = (self._beat_number % 4) + 1
            ts = time.monotonic()
            next_beat_ms = int(beat_period * 1000)

            event = BeatEvent(
                bpm=self._bpm,
                beat_position=self._beat_number,
                next_beat_ms=next_beat_ms,
                device_number=0,
                device_name="BeatSimulator",
                timestamp=ts,
            )
            self._event_bus.emit(event)
            logger.debug("Sim beat {}/4 at {:.1f} BPM", self._beat_number, self._bpm)

            next_beat += beat_period

        logger.info("BeatSimulator stopped")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/beat/test_simulator.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/beat/simulator.py tests/beat/test_simulator.py
git commit -m "feat: add BeatSimulator for demo/testing mode"
```

---

## Chunk 4: Effects System

### Task 10: Effect ABC (`effects/base.py`)

**Files:**
- Create: `src/dj_ledfx/effects/base.py`

- [ ] **Step 1: Write the implementation**

Create `src/dj_ledfx/effects/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray


class Effect(ABC):
    @abstractmethod
    def render(
        self,
        beat_phase: float,
        bar_phase: float,
        dt: float,
        led_count: int,
    ) -> NDArray[np.uint8]:
        """Return shape (led_count, 3) uint8 RGB array."""
        ...
```

- [ ] **Step 2: Commit**

```bash
git add src/dj_ledfx/effects/base.py
git commit -m "feat: add Effect ABC for LED effects"
```

---

### Task 11: BeatPulse effect (`effects/beat_pulse.py`)

**Files:**
- Create: `src/dj_ledfx/effects/beat_pulse.py`
- Test: `tests/effects/test_beat_pulse.py`

- [ ] **Step 1: Write the failing test**

Create `tests/effects/test_beat_pulse.py`:

```python
import numpy as np

from dj_ledfx.effects.beat_pulse import BeatPulse


def test_beat_pulse_on_beat_is_bright() -> None:
    effect = BeatPulse()
    # beat_phase=0.0 means exactly on the beat → max brightness
    result = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8
    # On beat, brightness should be max (255 in at least one channel)
    assert result.max() == 255


def test_beat_pulse_decays_after_beat() -> None:
    effect = BeatPulse()
    on_beat = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=10)
    mid_beat = effect.render(beat_phase=0.5, bar_phase=0.0, dt=0.016, led_count=10)
    # Mid-beat should be dimmer than on-beat
    assert mid_beat.max() < on_beat.max()


def test_beat_pulse_near_next_beat_is_dark() -> None:
    effect = BeatPulse()
    result = effect.render(beat_phase=0.99, bar_phase=0.0, dt=0.016, led_count=10)
    # Near next beat, should be very dim
    assert result.max() < 20


def test_beat_pulse_color_changes_with_bar_phase() -> None:
    effect = BeatPulse()
    beat1 = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=1)
    beat3 = effect.render(beat_phase=0.0, bar_phase=0.5, dt=0.016, led_count=1)
    # Different bar positions should produce different colors
    assert not np.array_equal(beat1, beat3)


def test_beat_pulse_custom_palette() -> None:
    effect = BeatPulse(palette=["#ffffff", "#000000", "#ff0000", "#00ff00"], gamma=1.0)
    result = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=1)
    # First color is white at gamma=1.0 → [255, 255, 255]
    assert result[0, 0] == 255
    assert result[0, 1] == 255
    assert result[0, 2] == 255
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/effects/test_beat_pulse.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/effects/beat_pulse.py`:

```python
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect

_DEFAULT_PALETTE = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class BeatPulse(Effect):
    def __init__(
        self,
        palette: list[str] | None = None,
        gamma: float = 2.0,
    ) -> None:
        colors = palette or _DEFAULT_PALETTE
        self._palette = [_hex_to_rgb(c) for c in colors]
        self._gamma = gamma

    def render(
        self,
        beat_phase: float,
        bar_phase: float,
        dt: float,
        led_count: int,
    ) -> NDArray[np.uint8]:
        # Brightness: flash on beat (phase=0), exponential decay
        brightness = (1.0 - beat_phase) ** self._gamma

        # Color: index by bar phase into 4-color palette
        color_index = int(bar_phase * len(self._palette)) % len(self._palette)
        r, g, b = self._palette[color_index]

        # Apply brightness
        out = np.empty((led_count, 3), dtype=np.uint8)
        out[:, 0] = int(r * brightness)
        out[:, 1] = int(g * brightness)
        out[:, 2] = int(b * brightness)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/effects/test_beat_pulse.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/effects/beat_pulse.py tests/effects/test_beat_pulse.py
git commit -m "feat: add BeatPulse effect with palette cycling and exponential decay"
```

---

### Task 12: Effect engine with ring buffer (`effects/engine.py`)

**Files:**
- Create: `src/dj_ledfx/effects/engine.py`
- Test: `tests/effects/test_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/effects/test_engine.py`:

```python
import numpy as np

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.types import RenderedFrame


def test_ring_buffer_write_and_read() -> None:
    buf = RingBuffer(capacity=10, led_count=5)
    frame = RenderedFrame(
        colors=np.zeros((5, 3), dtype=np.uint8),
        target_time=100.0,
        beat_phase=0.0,
        bar_phase=0.0,
    )
    buf.write(frame)
    result = buf.find_nearest(100.0)
    assert result is not None
    assert result.target_time == 100.0


def test_ring_buffer_find_nearest() -> None:
    buf = RingBuffer(capacity=60, led_count=5)
    for i in range(10):
        frame = RenderedFrame(
            colors=np.zeros((5, 3), dtype=np.uint8),
            target_time=100.0 + i * 0.0167,  # ~60fps
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)

    # Find frame nearest to 100.05 → should be ~frame 3 (100.0501)
    result = buf.find_nearest(100.05)
    assert result is not None
    assert abs(result.target_time - 100.05) < 0.02


def test_ring_buffer_returns_copy() -> None:
    buf = RingBuffer(capacity=10, led_count=5)
    colors = np.full((5, 3), 42, dtype=np.uint8)
    frame = RenderedFrame(colors=colors, target_time=100.0, beat_phase=0.0, bar_phase=0.0)
    buf.write(frame)

    result = buf.find_nearest(100.0)
    assert result is not None
    # Modify the returned frame — should not affect buffer
    result.colors[0, 0] = 0
    original = buf.find_nearest(100.0)
    assert original is not None
    assert original.colors[0, 0] == 42


def test_ring_buffer_empty_returns_none() -> None:
    buf = RingBuffer(capacity=10, led_count=5)
    assert buf.find_nearest(100.0) is None


def test_engine_render_tick_populates_buffer() -> None:
    clock = BeatClock()
    import time

    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)

    effect = BeatPulse()
    engine = EffectEngine(
        clock=clock,
        effect=effect,
        led_count=10,
        fps=60,
        max_lookahead_s=1.0,
    )

    # Manually tick the engine
    engine.tick(now)

    # Buffer should have one frame
    frame = engine.ring_buffer.find_nearest(now + 1.0)
    assert frame is not None
    assert frame.colors.shape == (10, 3)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/effects/test_engine.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/effects/engine.py`:

```python
from __future__ import annotations

import asyncio
import time

import numpy as np
from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.base import Effect
from dj_ledfx.types import RenderedFrame


class RingBuffer:
    def __init__(self, capacity: int, led_count: int) -> None:
        self._capacity = capacity
        self._led_count = led_count
        self._frames: list[RenderedFrame | None] = [None] * capacity
        self._write_index = 0
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    @property
    def capacity(self) -> int:
        return self._capacity

    def write(self, frame: RenderedFrame) -> None:
        self._frames[self._write_index] = frame
        self._write_index = (self._write_index + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    def find_nearest(self, target_time: float) -> RenderedFrame | None:
        best: RenderedFrame | None = None
        best_diff = float("inf")

        for frame in self._frames:
            if frame is None:
                continue
            diff = abs(frame.target_time - target_time)
            if diff < best_diff:
                best_diff = diff
                best = frame

        if best is None:
            return None

        # Return a copy to prevent race conditions
        return RenderedFrame(
            colors=best.colors.copy(),
            target_time=best.target_time,
            beat_phase=best.beat_phase,
            bar_phase=best.bar_phase,
        )

    @property
    def fill_level(self) -> float:
        return self._count / self._capacity


class EffectEngine:
    def __init__(
        self,
        clock: BeatClock,
        effect: Effect,
        led_count: int,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
    ) -> None:
        self._clock = clock
        self._effect = effect
        self._led_count = led_count
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._max_lookahead_s = max_lookahead_s
        self.ring_buffer = RingBuffer(capacity=fps, led_count=led_count)
        self._running = False
        self._last_tick_time = 0.0
        self._render_times: list[float] = []

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0.0
        return sum(self._render_times) / len(self._render_times) * 1000.0

    def tick(self, now: float) -> None:
        target_time = now + self._max_lookahead_s
        state = self._clock.get_state_at(target_time)

        render_start = time.monotonic()
        colors = self._effect.render(
            beat_phase=state.beat_phase,
            bar_phase=state.bar_phase,
            dt=self._frame_period,
            led_count=self._led_count,
        )
        render_elapsed = time.monotonic() - render_start

        self._render_times.append(render_elapsed)
        if len(self._render_times) > 600:  # keep last 10s at 60fps
            self._render_times.pop(0)

        frame = RenderedFrame(
            colors=colors,
            target_time=target_time,
            beat_phase=state.beat_phase,
            bar_phase=state.bar_phase,
        )
        self.ring_buffer.write(frame)
        logger.trace("Rendered frame for t+{:.0f}ms", self._max_lookahead_s * 1000)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        self._last_tick_time = time.monotonic()
        logger.info(
            "EffectEngine started: {}fps, {}ms lookahead, {} LEDs",
            self._fps,
            int(self._max_lookahead_s * 1000),
            self._led_count,
        )

        while self._running:
            now = time.monotonic()
            self.tick(now)

            self._last_tick_time += self._frame_period
            sleep_time = self._last_tick_time + self._frame_period - time.monotonic()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # Running late — stay on grid
                self._last_tick_time = time.monotonic()
                await asyncio.sleep(0)

        logger.info("EffectEngine stopped")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/effects/test_engine.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/effects/engine.py tests/effects/test_engine.py
git commit -m "feat: add EffectEngine with ring buffer and 60fps render loop"
```

---

## Chunk 5: Device & Latency Layer

### Task 13: Latency strategies (`latency/strategies.py`)

**Files:**
- Create: `src/dj_ledfx/latency/strategies.py`
- Test: `tests/latency/test_strategies.py`

- [ ] **Step 1: Write the failing test**

Create `tests/latency/test_strategies.py`:

```python
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency


def test_static_latency() -> None:
    s = StaticLatency(latency_ms=10.0)
    assert s.get_latency() == 10.0
    s.update(20.0)  # should be ignored
    assert s.get_latency() == 10.0


def test_ema_latency_basic() -> None:
    s = EMALatency(alpha=0.3)
    s.update(100.0)
    assert s.get_latency() == 100.0
    s.update(200.0)
    # EMA: 0.3 * 200 + 0.7 * 100 = 130
    assert abs(s.get_latency() - 130.0) < 0.1


def test_ema_latency_outlier_rejection() -> None:
    s = EMALatency(alpha=0.3)
    for _ in range(10):
        s.update(100.0)
    # Outlier: 3000ms is >2σ from mean of ~100
    s.update(3000.0)
    # Should still be near 100
    assert s.get_latency() < 150.0


def test_ema_latency_reset() -> None:
    s = EMALatency(alpha=0.3)
    s.update(100.0)
    s.reset()
    assert s.get_latency() == 0.0


def test_windowed_mean_basic() -> None:
    s = WindowedMeanLatency(window_size=3)
    s.update(100.0)
    s.update(200.0)
    s.update(300.0)
    assert abs(s.get_latency() - 200.0) < 0.1


def test_windowed_mean_rolls_over() -> None:
    s = WindowedMeanLatency(window_size=3)
    s.update(100.0)
    s.update(200.0)
    s.update(300.0)
    s.update(400.0)
    # Window: [200, 300, 400] → mean 300
    assert abs(s.get_latency() - 300.0) < 0.1


def test_windowed_mean_reset() -> None:
    s = WindowedMeanLatency(window_size=3)
    s.update(100.0)
    s.reset()
    assert s.get_latency() == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/latency/test_strategies.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/latency/strategies.py`:

```python
from __future__ import annotations

import math
from collections import deque
from typing import Protocol


class ProbeStrategy(Protocol):
    def update(self, new_sample: float) -> None: ...
    def get_latency(self) -> float: ...
    def reset(self) -> None: ...


class StaticLatency:
    def __init__(self, latency_ms: float = 10.0) -> None:
        self._latency = latency_ms

    def update(self, new_sample: float) -> None:
        pass  # Static — ignores updates

    def get_latency(self) -> float:
        return self._latency

    def reset(self) -> None:
        pass


class EMALatency:
    def __init__(self, alpha: float = 0.3) -> None:
        self._alpha = alpha
        self._value: float = 0.0
        self._initialized = False
        self._samples: list[float] = []

    def update(self, new_sample: float) -> None:
        # Outlier rejection: reject if >2σ from current mean (needs ≥5 samples)
        if len(self._samples) >= 5:
            mean = sum(self._samples) / len(self._samples)
            variance = sum((s - mean) ** 2 for s in self._samples) / len(self._samples)
            std = math.sqrt(variance) if variance > 0 else 0.0
            if std > 0 and abs(new_sample - mean) > 2.0 * std:
                return  # reject outlier

        self._samples.append(new_sample)
        if len(self._samples) > 100:
            self._samples.pop(0)

        if not self._initialized:
            self._value = new_sample
            self._initialized = True
        else:
            self._value = self._alpha * new_sample + (1.0 - self._alpha) * self._value

    def get_latency(self) -> float:
        return self._value

    def reset(self) -> None:
        self._value = 0.0
        self._initialized = False
        self._samples.clear()


class WindowedMeanLatency:
    def __init__(self, window_size: int = 10) -> None:
        self._window: deque[float] = deque(maxlen=window_size)

    def update(self, new_sample: float) -> None:
        self._window.append(new_sample)

    def get_latency(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    def reset(self) -> None:
        self._window.clear()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/latency/test_strategies.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/latency/strategies.py tests/latency/test_strategies.py
git commit -m "feat: add latency probe strategies (Static, EMA, WindowedMean)"
```

---

### Task 14: LatencyTracker (`latency/tracker.py`)

**Files:**
- Create: `src/dj_ledfx/latency/tracker.py`
- Test: `tests/latency/test_tracker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/latency/test_tracker.py`:

```python
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker


def test_tracker_effective_latency() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy, manual_offset_ms=5.0)
    assert tracker.effective_latency_ms == 15.0


def test_tracker_effective_latency_seconds() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy, manual_offset_ms=5.0)
    assert abs(tracker.effective_latency_s - 0.015) < 0.0001


def test_tracker_update_delegates() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy)
    tracker.update(20.0)  # StaticLatency ignores this
    assert tracker.effective_latency_ms == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/latency/test_tracker.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/latency/tracker.py`:

```python
from __future__ import annotations

from dj_ledfx.latency.strategies import ProbeStrategy


class LatencyTracker:
    def __init__(
        self,
        strategy: ProbeStrategy,
        manual_offset_ms: float = 0.0,
    ) -> None:
        self._strategy = strategy
        self._manual_offset_ms = manual_offset_ms

    @property
    def effective_latency_ms(self) -> float:
        return self._strategy.get_latency() + self._manual_offset_ms

    @property
    def effective_latency_s(self) -> float:
        return self.effective_latency_ms / 1000.0

    def update(self, sample_ms: float) -> None:
        self._strategy.update(sample_ms)

    def reset(self) -> None:
        self._strategy.reset()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/latency/test_tracker.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/latency/tracker.py tests/latency/test_tracker.py
git commit -m "feat: add LatencyTracker with strategy delegation and manual offset"
```

---

### Task 15: Device adapter protocol (`devices/adapter.py`)

**Files:**
- Create: `src/dj_ledfx/devices/adapter.py`

- [ ] **Step 1: Write the implementation**

Create `src/dj_ledfx/devices/adapter.py`:

```python
from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.types import DeviceInfo


class DeviceAdapter(Protocol):
    @property
    def device_info(self) -> DeviceInfo: ...

    @property
    def is_connected(self) -> bool: ...

    @property
    def led_count(self) -> int: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def send_frame(self, colors: NDArray[np.uint8]) -> None: ...
```

- [ ] **Step 2: Commit**

```bash
git add src/dj_ledfx/devices/adapter.py
git commit -m "feat: add DeviceAdapter protocol for vendor-agnostic device control"
```

---

### Task 16: OpenRGB adapter (`devices/openrgb.py`)

**Files:**
- Create: `src/dj_ledfx/devices/openrgb.py`
- Test: `tests/devices/test_openrgb.py`

- [ ] **Step 1: Write the failing test**

Create `tests/devices/test_openrgb.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from dj_ledfx.devices.openrgb import OpenRGBAdapter


async def test_openrgb_connect() -> None:
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.devices = [MagicMock(name="Test Device", colors=[None] * 10)]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(host="127.0.0.1", port=6742, device_index=0)
        await adapter.connect()

        assert adapter.is_connected is True


async def test_openrgb_send_frame() -> None:
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as mock_cls:
        mock_device = MagicMock()
        mock_device.colors = [None] * 10
        mock_client = MagicMock()
        mock_client.devices = [mock_device]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(host="127.0.0.1", port=6742, device_index=0)
        await adapter.connect()

        colors = np.full((10, 3), 128, dtype=np.uint8)
        await adapter.send_frame(colors)

        mock_device.set_colors.assert_called_once()


async def test_openrgb_disconnect() -> None:
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.devices = [MagicMock(colors=[None] * 5)]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(host="127.0.0.1", port=6742, device_index=0)
        await adapter.connect()
        await adapter.disconnect()

        assert adapter.is_connected is False
        mock_client.disconnect.assert_called_once()


async def test_openrgb_truncates_colors() -> None:
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as mock_cls:
        mock_device = MagicMock()
        mock_device.colors = [None] * 5  # device has 5 LEDs
        mock_client = MagicMock()
        mock_client.devices = [mock_device]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(host="127.0.0.1", port=6742, device_index=0)
        await adapter.connect()

        # Send 10 LEDs to a 5-LED device
        colors = np.full((10, 3), 128, dtype=np.uint8)
        await adapter.send_frame(colors)

        # Should truncate to 5
        call_args = mock_device.set_colors.call_args
        sent_colors = call_args[0][0]
        assert len(sent_colors) == 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/devices/test_openrgb.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/devices/openrgb.py`:

```python
from __future__ import annotations

import asyncio

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.types import DeviceInfo

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:
    OpenRGBClient = None  # type: ignore[assignment,misc]
    RGBColor = None  # type: ignore[assignment,misc]


class OpenRGBAdapter:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6742,
        device_index: int = 0,
    ) -> None:
        self._host = host
        self._port = port
        self._device_index = device_index
        self._client: object | None = None
        self._device: object | None = None
        self._is_connected = False
        self._led_count = 0
        self._device_name = ""

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._device_name or f"OpenRGB:{self._device_index}",
            device_type="openrgb",
            led_count=self._led_count,
            address=f"{self._host}:{self._port}",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        def _connect() -> None:
            if OpenRGBClient is None:
                raise ImportError("openrgb-python is not installed")
            client = OpenRGBClient(self._host, self._port)
            if self._device_index >= len(client.devices):
                raise ConnectionError(
                    f"Device index {self._device_index} not found "
                    f"(server has {len(client.devices)} devices)"
                )
            device = client.devices[self._device_index]
            self._client = client
            self._device = device
            self._led_count = len(device.colors)
            self._device_name = getattr(device, "name", f"Device {self._device_index}")

        await asyncio.to_thread(_connect)
        self._is_connected = True
        logger.info(
            "Connected to OpenRGB device '{}' ({} LEDs) at {}:{}",
            self._device_name,
            self._led_count,
            self._host,
            self._port,
        )

    async def disconnect(self) -> None:
        if self._client is not None:

            def _disconnect() -> None:
                self._client.disconnect()  # type: ignore[union-attr]

            await asyncio.to_thread(_disconnect)

        self._is_connected = False
        self._client = None
        self._device = None
        logger.info("Disconnected from OpenRGB device '{}'", self._device_name)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        if not self._is_connected or self._device is None:
            return

        device = self._device
        led_count = self._led_count

        # Truncate to device LED count
        frame = colors[:led_count]

        # Convert numpy array to list of RGBColor
        rgb_colors = [RGBColor(int(frame[i, 0]), int(frame[i, 1]), int(frame[i, 2])) for i in range(len(frame))]

        def _send() -> None:
            device.set_colors(rgb_colors, fast=True)  # type: ignore[union-attr]

        await asyncio.to_thread(_send)
        logger.trace("Sent {} colors to '{}'", len(rgb_colors), self._device_name)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/devices/test_openrgb.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/openrgb.py tests/devices/test_openrgb.py
git commit -m "feat: add OpenRGB adapter with asyncio.to_thread wrapping"
```

---

### Task 17: DeviceManager (`devices/manager.py`)

**Files:**
- Create: `src/dj_ledfx/devices/manager.py`
- Test: `tests/devices/test_manager.py`

- [ ] **Step 1: Write the failing test**

Create `tests/devices/test_manager.py`:

```python
from unittest.mock import AsyncMock, PropertyMock

import numpy as np

from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo


def _make_mock_adapter(name: str = "TestDevice", led_count: int = 10) -> AsyncMock:
    adapter = AsyncMock()
    type(adapter).is_connected = PropertyMock(return_value=True)
    type(adapter).led_count = PropertyMock(return_value=led_count)
    type(adapter).device_info = PropertyMock(
        return_value=DeviceInfo(name=name, device_type="mock", led_count=led_count, address="mock")
    )
    return adapter


def test_device_manager_add_device() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)
    adapter = _make_mock_adapter()
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    manager.add_device(adapter, tracker)  # type: ignore[arg-type]
    assert len(manager.devices) == 1


def test_device_manager_max_led_count() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    a1 = _make_mock_adapter("Dev1", led_count=10)
    a2 = _make_mock_adapter("Dev2", led_count=30)
    t1 = LatencyTracker(strategy=StaticLatency(10.0))
    t2 = LatencyTracker(strategy=StaticLatency(10.0))

    manager.add_device(a1, t1)  # type: ignore[arg-type]
    manager.add_device(a2, t2)  # type: ignore[arg-type]

    assert manager.max_led_count == 30
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/devices/test_manager.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/devices/manager.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.events import EventBus
from dj_ledfx.latency.tracker import LatencyTracker


@dataclass
class ManagedDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker


class DeviceManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._devices: list[ManagedDevice] = []

    @property
    def devices(self) -> list[ManagedDevice]:
        return list(self._devices)

    @property
    def max_led_count(self) -> int:
        if not self._devices:
            return 0
        return max(d.adapter.led_count for d in self._devices)

    def add_device(self, adapter: DeviceAdapter, tracker: LatencyTracker) -> None:
        self._devices.append(ManagedDevice(adapter=adapter, tracker=tracker))
        logger.info(
            "Added device '{}' ({} LEDs, latency={:.0f}ms)",
            adapter.device_info.name,
            adapter.led_count,
            tracker.effective_latency_ms,
        )

    async def connect_all(self) -> None:
        for device in self._devices:
            try:
                await device.adapter.connect()
            except Exception:
                logger.exception("Failed to connect to '{}'", device.adapter.device_info.name)

    async def disconnect_all(self) -> None:
        for device in self._devices:
            try:
                await device.adapter.disconnect()
            except Exception:
                logger.exception(
                    "Failed to disconnect from '{}'", device.adapter.device_info.name
                )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/devices/test_manager.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/manager.py tests/devices/test_manager.py
git commit -m "feat: add DeviceManager for device lifecycle management"
```

---

## Chunk 6: Scheduler & Orchestration

### Task 18: LookaheadScheduler (`scheduling/scheduler.py`)

**Files:**
- Create: `src/dj_ledfx/scheduling/scheduler.py`
- Test: `tests/scheduling/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/scheduling/test_scheduler.py`:

```python
import asyncio
import time
from unittest.mock import AsyncMock, PropertyMock

import numpy as np

from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.types import DeviceInfo, RenderedFrame


def _make_device(latency_ms: float = 10.0) -> ManagedDevice:
    adapter = AsyncMock()
    type(adapter).is_connected = PropertyMock(return_value=True)
    type(adapter).led_count = PropertyMock(return_value=10)
    type(adapter).device_info = PropertyMock(
        return_value=DeviceInfo(
            name="TestDevice", device_type="mock", led_count=10, address="mock"
        )
    )
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


async def test_scheduler_dispatches_frame() -> None:
    device = _make_device(latency_ms=10.0)
    buf = RingBuffer(capacity=60, led_count=10)
    now = time.monotonic()
    _fill_buffer(buf, now, 60)

    scheduler = LookaheadScheduler(
        ring_buffer=buf,
        devices=[device],
        fps=60,
    )

    # Run scheduler briefly
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    scheduler.stop()
    await task

    # Should have sent at least one frame
    assert device.adapter.send_frame.call_count >= 1


async def test_scheduler_picks_correct_frame_for_latency() -> None:
    buf = RingBuffer(capacity=60, led_count=10)
    now = time.monotonic()
    _fill_buffer(buf, now, 60)

    # Device with 500ms latency should pick a frame ~500ms into the future
    device = _make_device(latency_ms=500.0)
    frame = buf.find_nearest(now + 0.5)
    assert frame is not None
    # The frame's target_time should be close to now + 0.5
    assert abs(frame.target_time - (now + 0.5)) < 0.02
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/scheduling/test_scheduler.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/scheduling/scheduler.py`:

```python
from __future__ import annotations

import asyncio
import time

from loguru import logger

from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import RingBuffer


class LookaheadScheduler:
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
    ) -> None:
        self._ring_buffer = ring_buffer
        self._devices = devices
        self._frame_period = 1.0 / fps
        self._running = False

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info(
            "LookaheadScheduler started with {} devices",
            len(self._devices),
        )

        while self._running:
            tick_start = time.monotonic()
            await self._dispatch_all()
            elapsed = time.monotonic() - tick_start
            sleep_time = self._frame_period - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0)

        logger.info("LookaheadScheduler stopped")

    async def _dispatch_all(self) -> None:
        now = time.monotonic()
        tasks: list[asyncio.Task[None]] = []

        for device in self._devices:
            if not device.adapter.is_connected:
                continue

            target_time = now + device.tracker.effective_latency_s
            frame = self._ring_buffer.find_nearest(target_time)

            if frame is None:
                logger.debug(
                    "No frame for '{}' (latency={:.0f}ms, buffer fill={:.0%})",
                    device.adapter.device_info.name,
                    device.tracker.effective_latency_ms,
                    self._ring_buffer.fill_level,
                )
                continue

            # Frame data is already copied by find_nearest
            task = asyncio.create_task(
                self._send_to_device(device, frame.colors)
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _send_to_device(device: ManagedDevice, colors: object) -> None:
        try:
            await device.adapter.send_frame(colors)  # type: ignore[arg-type]
        except Exception:
            logger.exception(
                "Failed to send frame to '{}'",
                device.adapter.device_info.name,
            )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/scheduling/test_scheduler.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat: add LookaheadScheduler with per-device latency-compensated dispatch"
```

---

### Task 19: SystemStatus (`status.py`)

**Files:**
- Create: `src/dj_ledfx/status.py`
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_status.py`:

```python
from dj_ledfx.status import SystemStatus


def test_system_status_defaults() -> None:
    status = SystemStatus()
    assert status.prodjlink_connected is False
    assert status.active_player_count == 0
    assert status.current_bpm is None
    assert status.connected_devices == []
    assert status.buffer_fill_level == 0.0


def test_system_status_log_summary() -> None:
    status = SystemStatus(
        prodjlink_connected=True,
        active_player_count=2,
        current_bpm=128.0,
        connected_devices=["OpenRGB:0"],
        buffer_fill_level=0.95,
        avg_frame_render_time_ms=0.5,
    )
    summary = status.summary()
    assert "128.0" in summary
    assert "OpenRGB:0" in summary
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_status.py -v
```

Expected: FAIL

- [ ] **Step 3: Write the implementation**

Create `src/dj_ledfx/status.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SystemStatus:
    prodjlink_connected: bool = False
    active_player_count: int = 0
    current_bpm: float | None = None
    connected_devices: list[str] = field(default_factory=list)
    device_errors: dict[str, str] = field(default_factory=dict)
    buffer_fill_level: float = 0.0
    avg_frame_render_time_ms: float = 0.0

    def summary(self) -> str:
        bpm_str = f"{self.current_bpm:.1f}" if self.current_bpm else "N/A"
        devices = ", ".join(self.connected_devices) or "none"
        return (
            f"BPM={bpm_str} | "
            f"players={self.active_player_count} | "
            f"devices=[{devices}] | "
            f"buffer={self.buffer_fill_level:.0%} | "
            f"render={self.avg_frame_render_time_ms:.1f}ms"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_status.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/status.py tests/test_status.py
git commit -m "feat: add SystemStatus health tracking with summary"
```

---

### Task 20: Application coordinator (`main.py`)

**Files:**
- Create: `src/dj_ledfx/main.py`
- Modify: `src/dj_ledfx/__main__.py`

- [ ] **Step 1: Write the implementation**

Create `src/dj_ledfx/main.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.config import AppConfig, load_config
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.devices.openrgb import OpenRGBAdapter
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.prodjlink.listener import BeatEvent, start_listener
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.status import SystemStatus

from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dj-ledfx: Beat-synced LED effects")
    parser.add_argument("--demo", action="store_true", help="Run with simulated beats")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="Config file path")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    parser.add_argument("--bpm", type=float, default=128.0, help="Demo mode BPM")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    config = load_config(args.config)

    # Event bus
    event_bus = EventBus()

    # BeatClock
    clock = BeatClock()

    # Wire beat events to clock
    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    # Start beat source
    simulator: BeatSimulator | None = None
    if args.demo:
        logger.info("Starting in demo mode at {:.1f} BPM", args.bpm)
        simulator = BeatSimulator(event_bus=event_bus, bpm=args.bpm)
    else:
        logger.info("Starting Pro DJ Link listener")
        await start_listener(event_bus=event_bus)

    # Device manager
    device_manager = DeviceManager(event_bus=event_bus)

    if config.openrgb_enabled:
        try:
            adapter = OpenRGBAdapter(
                host=config.openrgb_host,
                port=config.openrgb_port,
            )
            await adapter.connect()
            tracker = LatencyTracker(
                strategy=StaticLatency(config.openrgb_latency_ms),
                manual_offset_ms=config.openrgb_manual_offset_ms,
            )
            device_manager.add_device(adapter, tracker)  # type: ignore[arg-type]
        except Exception:
            logger.exception("Failed to connect to OpenRGB")

    # LED count
    led_count = device_manager.max_led_count or 60  # fallback default
    logger.info("Using {} LEDs", led_count)

    # Effect
    effect = BeatPulse(
        palette=config.beat_pulse_palette,
        gamma=config.beat_pulse_gamma,
    )

    # Effect engine
    engine = EffectEngine(
        clock=clock,
        effect=effect,
        led_count=led_count,
        fps=config.engine_fps,
        max_lookahead_s=config.max_lookahead_ms / 1000.0,
    )

    # Scheduler
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=device_manager.devices,
        fps=config.engine_fps,
    )

    # Shutdown event
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Start tasks
    tasks: list[asyncio.Task[None]] = []
    if simulator is not None:
        tasks.append(asyncio.create_task(simulator.run()))
    tasks.append(asyncio.create_task(engine.run()))
    tasks.append(asyncio.create_task(scheduler.run()))

    # Status logging
    async def _status_loop() -> None:
        while not stop_event.is_set():
            status = SystemStatus(
                prodjlink_connected=clock.get_state().is_playing,
                current_bpm=clock.get_state().bpm or None,
                connected_devices=[d.adapter.device_info.name for d in device_manager.devices],
                buffer_fill_level=engine.ring_buffer.fill_level,
                avg_frame_render_time_ms=engine.avg_render_time_ms,
            )
            logger.info("Status: {}", status.summary())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                pass

    tasks.append(asyncio.create_task(_status_loop()))

    logger.info("dj-ledfx started")
    await stop_event.wait()

    # Shutdown
    logger.info("Shutting down...")
    scheduler.stop()
    engine.stop()
    if simulator is not None:
        simulator.stop()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await device_manager.disconnect_all()
    logger.info("dj-ledfx stopped")


def main() -> None:
    args = _parse_args()

    # Configure loguru
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update `__main__.py`**

Replace `src/dj_ledfx/__main__.py`:

```python
from dj_ledfx.main import main

main()
```

- [ ] **Step 3: Verify the app starts in demo mode**

```bash
timeout 3 uv run -m dj_ledfx --demo --log-level DEBUG || true
```

Expected: App starts, logs beat events, then exits on timeout. No crashes.

- [ ] **Step 4: Commit**

```bash
git add src/dj_ledfx/main.py src/dj_ledfx/__main__.py
git commit -m "feat: add application coordinator with startup/shutdown orchestration"
```

---

### Task 21: Integration test — full pipeline

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the integration test**

Create `tests/test_integration.py`:

```python
import asyncio
import time
from unittest.mock import AsyncMock, PropertyMock

import numpy as np

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.prodjlink.listener import BeatEvent
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.types import DeviceInfo


async def test_full_pipeline_simulator_to_mock_device() -> None:
    """Integration test: BeatSimulator → BeatClock → EffectEngine → Scheduler → MockDevice."""
    # Setup
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

    # Mock device
    mock_adapter = AsyncMock()
    type(mock_adapter).is_connected = PropertyMock(return_value=True)
    type(mock_adapter).led_count = PropertyMock(return_value=10)
    type(mock_adapter).device_info = PropertyMock(
        return_value=DeviceInfo(
            name="MockLED", device_type="mock", led_count=10, address="mock"
        )
    )

    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    managed = ManagedDevice(adapter=mock_adapter, tracker=tracker)

    # Effect engine
    effect = BeatPulse()
    engine = EffectEngine(
        clock=clock,
        effect=effect,
        led_count=10,
        fps=60,
        max_lookahead_s=1.0,
    )

    # Scheduler
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=[managed],
        fps=60,
    )

    # Simulator at 300 BPM for fast beats
    simulator = BeatSimulator(event_bus=event_bus, bpm=300.0)

    # Run everything
    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    # Let it run for 1 second
    await asyncio.sleep(1.0)

    # Stop
    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    # Verify: mock device should have received frames
    assert mock_adapter.send_frame.call_count > 0

    # Verify: frames sent to device should be valid numpy arrays
    first_call = mock_adapter.send_frame.call_args_list[0]
    sent_colors = first_call[0][0]
    assert isinstance(sent_colors, np.ndarray)
    assert sent_colors.shape == (10, 3)
```

- [ ] **Step 2: Run the integration test**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass.

- [ ] **Step 4: Run all linters**

```bash
uv run ruff check src/
uv run ruff format --check src/
```

Fix any issues.

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add full pipeline integration test (simulator → mock device)"
```

---

### Task 22: Final verification and cleanup

- [ ] **Step 1: Run complete test suite**

```bash
uv run pytest -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 2: Run linters and formatters**

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

- [ ] **Step 3: Run type checker**

```bash
uv run mypy src/
```

Fix any type errors.

- [ ] **Step 4: Verify demo mode runs**

```bash
timeout 5 uv run -m dj_ledfx --demo --log-level DEBUG 2>&1 | head -30 || true
```

Expected: App starts, BeatSimulator emits beats, engine renders frames, scheduler dispatches. Clean exit.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup — lint, format, type-check all passing"
```
