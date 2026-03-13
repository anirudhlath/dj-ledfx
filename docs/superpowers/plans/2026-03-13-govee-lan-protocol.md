# Govee LAN Protocol Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native Govee LAN device support with UDP discovery, solid color control (`colorwc`), and per-segment RGBIC control (`ptReal` BLE-over-LAN).

**Architecture:** Shared `GoveeTransport` manages UDP sockets (multicast discovery on 4001, responses on 4002, commands on 4003). Two typed adapters — `GoveeSolidAdapter` for whole-device color and `GoveeSegmentAdapter` for per-segment ptReal — both extend `DeviceAdapter` ABC. `GoveeBackend` extends `DeviceBackend` for auto-registration. Pure-function `protocol.py` handles all BLE packet encoding.

**Tech Stack:** Python 3.12+, asyncio (DatagramProtocol), numpy, loguru, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-13-govee-lan-protocol-design.md`

---

## Chunk 1: Types, Protocol, and SKU Registry (pure logic, no I/O)

### Task 1: Govee Types

**Files:**
- Create: `src/dj_ledfx/devices/govee/__init__.py`
- Create: `src/dj_ledfx/devices/govee/types.py`

- [ ] **Step 1: Create package and types module**

```python
# src/dj_ledfx/devices/govee/__init__.py
```

```python
# src/dj_ledfx/devices/govee/types.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoveeDeviceRecord:
    """Discovered Govee device on the LAN."""

    ip: str
    device_id: str
    sku: str
    wifi_version: str
    ble_version: str


@dataclass(frozen=True, slots=True)
class GoveeDeviceCapability:
    """Device capability info from SKU registry."""

    is_rgbic: bool
    segment_count: int  # 0 for non-RGBIC
```

- [ ] **Step 2: Commit**

```bash
git add src/dj_ledfx/devices/govee/__init__.py src/dj_ledfx/devices/govee/types.py
git commit -m "feat(govee): add types module with GoveeDeviceRecord and GoveeDeviceCapability"
```

---

### Task 2: Protocol Module — JSON Message Builders

**Files:**
- Create: `src/dj_ledfx/devices/govee/protocol.py`
- Create: `tests/devices/govee/__init__.py`
- Create: `tests/devices/govee/test_protocol.py`

- [ ] **Step 1: Write failing tests for JSON message builders**

```python
# tests/devices/govee/__init__.py
```

```python
# tests/devices/govee/test_protocol.py
from __future__ import annotations

from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_scan_message,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
)


class TestBuildScanMessage:
    def test_scan_message_format(self) -> None:
        msg = build_scan_message()
        assert msg == {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}


class TestBuildTurnMessage:
    def test_turn_on(self) -> None:
        msg = build_turn_message(on=True)
        assert msg == {"msg": {"cmd": "turn", "data": {"value": 1}}}

    def test_turn_off(self) -> None:
        msg = build_turn_message(on=False)
        assert msg == {"msg": {"cmd": "turn", "data": {"value": 0}}}


class TestBuildBrightnessMessage:
    def test_normal_value(self) -> None:
        msg = build_brightness_message(50)
        assert msg == {"msg": {"cmd": "brightness", "data": {"value": 50}}}

    def test_clamps_low(self) -> None:
        msg = build_brightness_message(0)
        assert msg["msg"]["data"]["value"] == 1

    def test_clamps_high(self) -> None:
        msg = build_brightness_message(150)
        assert msg["msg"]["data"]["value"] == 100


class TestBuildSolidColorMessage:
    def test_red(self) -> None:
        msg = build_solid_color_message(255, 0, 0)
        assert msg == {
            "msg": {
                "cmd": "colorwc",
                "data": {"color": {"r": 255, "g": 0, "b": 0}, "colorTemInKelvin": 0},
            }
        }


class TestBuildStatusQuery:
    def test_status_query_format(self) -> None:
        msg = build_status_query()
        assert msg == {"msg": {"cmd": "devStatus", "data": {}}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_protocol.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement JSON message builders**

```python
# src/dj_ledfx/devices/govee/protocol.py
from __future__ import annotations

import base64
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray


def build_scan_message() -> dict:
    return {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}


def build_turn_message(on: bool) -> dict:
    return {"msg": {"cmd": "turn", "data": {"value": 1 if on else 0}}}


def build_brightness_message(value: int) -> dict:
    clamped = max(1, min(100, value))
    return {"msg": {"cmd": "brightness", "data": {"value": clamped}}}


def build_solid_color_message(r: int, g: int, b: int) -> dict:
    return {
        "msg": {
            "cmd": "colorwc",
            "data": {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": 0},
        }
    }


def build_status_query() -> dict:
    return {"msg": {"cmd": "devStatus", "data": {}}}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_protocol.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/protocol.py tests/devices/govee/__init__.py tests/devices/govee/test_protocol.py
git commit -m "feat(govee): add JSON message builders with tests"
```

---

### Task 3: Protocol Module — BLE Packet Encoding

**Files:**
- Modify: `src/dj_ledfx/devices/govee/protocol.py`
- Modify: `tests/devices/govee/test_protocol.py`

- [ ] **Step 1: Write failing tests for BLE encoding**

Append to `tests/devices/govee/test_protocol.py`:

```python
from dj_ledfx.devices.govee.protocol import (
    build_ble_packet,
    build_pt_real_message,
    build_segment_color_packet,
    encode_segment_mask,
    xor_checksum,
)


class TestXorChecksum:
    def test_simple(self) -> None:
        assert xor_checksum(b"\x33\x01\x01") == 0x33

    def test_all_zeros(self) -> None:
        assert xor_checksum(b"\x00\x00\x00") == 0x00

    def test_known_power_on(self) -> None:
        # Power on packet: 33 01 01 ... checksum should be 0x33
        data = bytes([0x33, 0x01, 0x01] + [0x00] * 16)
        assert xor_checksum(data) == 0x33


class TestBuildBlePacket:
    def test_packet_length(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert len(pkt) == 20

    def test_starts_with_identifier(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert pkt[0] == 0x33

    def test_command_type_and_sub(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert pkt[1] == 0x05
        assert pkt[2] == 0x0B

    def test_checksum_valid(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert xor_checksum(pkt[:19]) == pkt[19]

    def test_payload_embedded(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xAA\xBB\xCC")
        assert pkt[3] == 0xAA
        assert pkt[4] == 0xBB
        assert pkt[5] == 0xCC


class TestEncodeSegmentMask:
    def test_segment_0(self) -> None:
        mask = encode_segment_mask([0], total_segments=15)
        assert mask == bytes([0x01, 0x00])

    def test_segment_8(self) -> None:
        mask = encode_segment_mask([8], total_segments=15)
        assert mask == bytes([0x00, 0x01])

    def test_all_15_segments(self) -> None:
        mask = encode_segment_mask(list(range(15)), total_segments=15)
        assert mask == bytes([0xFF, 0x7F])

    def test_segments_0_and_14(self) -> None:
        mask = encode_segment_mask([0, 14], total_segments=15)
        assert mask == bytes([0x01, 0x40])


class TestBuildSegmentColorPacket:
    def test_red_segment_0(self) -> None:
        mask = encode_segment_mask([0], total_segments=15)
        pkt = build_segment_color_packet(255, 0, 0, mask)
        assert len(pkt) == 20
        assert pkt[0] == 0x33
        assert pkt[1] == 0x05
        assert pkt[2] == 0x0B
        assert pkt[3:6] == bytes([255, 0, 0])
        assert pkt[8] == 0x01  # left mask
        assert pkt[9] == 0x00  # right mask
        assert xor_checksum(pkt[:19]) == pkt[19]


class TestBuildPtRealMessage:
    def test_single_packet(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        msg = build_pt_real_message([pkt])
        assert msg["msg"]["cmd"] == "ptReal"
        commands = msg["msg"]["data"]["command"]
        assert len(commands) == 1
        # Verify base64 round-trip
        import base64
        decoded = base64.b64decode(commands[0])
        assert decoded == pkt

    def test_multiple_packets(self) -> None:
        pkts = [build_ble_packet(0x05, 0x0B, bytes([i, 0, 0])) for i in range(3)]
        msg = build_pt_real_message(pkts)
        assert len(msg["msg"]["data"]["command"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_protocol.py -v -k "Xor or Ble or Segment or PtReal"`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement BLE encoding functions**

Append to `src/dj_ledfx/devices/govee/protocol.py`:

```python
def xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


def build_ble_packet(command_type: int, sub_command: int, payload: bytes) -> bytes:
    buf = bytearray(20)
    buf[0] = 0x33
    buf[1] = command_type
    buf[2] = sub_command
    end = min(3 + len(payload), 19)
    buf[3:end] = payload[: end - 3]
    buf[19] = xor_checksum(bytes(buf[:19]))
    return bytes(buf)


def encode_segment_mask(segment_indices: Sequence[int], total_segments: int = 15) -> bytes:
    left = 0  # segments 0-7
    right = 0  # segments 8+
    for idx in segment_indices:
        if 0 <= idx < 8:
            left |= 1 << idx
        elif 8 <= idx < total_segments:
            right |= 1 << (idx - 8)
    return bytes([left, right])


def build_segment_color_packet(r: int, g: int, b: int, segment_mask: bytes) -> bytes:
    payload = bytes([r, g, b, 0x00, 0x00]) + segment_mask
    return build_ble_packet(0x05, 0x0B, payload)


def build_pt_real_message(ble_packets: Sequence[bytes]) -> dict:
    encoded = [base64.b64encode(pkt).decode("ascii") for pkt in ble_packets]
    return {"msg": {"cmd": "ptReal", "data": {"command": encoded}}}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_protocol.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/protocol.py tests/devices/govee/test_protocol.py
git commit -m "feat(govee): add BLE packet encoding and ptReal message builder"
```

---

### Task 4: Protocol Module — Segment Color Downsampling

**Files:**
- Modify: `src/dj_ledfx/devices/govee/protocol.py`
- Modify: `tests/devices/govee/test_protocol.py`

- [ ] **Step 1: Write failing tests for map_colors_to_segments**

Append to `tests/devices/govee/test_protocol.py`:

```python
import numpy as np

from dj_ledfx.devices.govee.protocol import map_colors_to_segments


class TestMapColorsToSegments:
    def test_exact_match(self) -> None:
        """3 LEDs → 3 segments = no downsampling."""
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 3)
        assert result == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    def test_downsample_averaging(self) -> None:
        """4 LEDs → 2 segments: each segment averages 2 LEDs."""
        colors = np.array(
            [[200, 0, 0], [100, 0, 0], [0, 200, 0], [0, 100, 0]], dtype=np.uint8
        )
        result = map_colors_to_segments(colors, 2)
        assert result == [(150, 0, 0), (0, 150, 0)]

    def test_single_segment(self) -> None:
        """All LEDs averaged into one segment."""
        colors = np.array([[100, 0, 0], [0, 100, 0], [0, 0, 100]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 1)
        r, g, b = result[0]
        assert r == 33  # 100/3 ≈ 33
        assert g == 33
        assert b == 33

    def test_more_segments_than_leds(self) -> None:
        """2 LEDs → 4 segments: LEDs stretch across segments."""
        colors = np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 4)
        assert len(result) == 4
        # First two segments map to first LED, last two to second
        assert result[0] == (255, 0, 0)
        assert result[1] == (255, 0, 0)
        assert result[2] == (0, 0, 255)
        assert result[3] == (0, 0, 255)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_protocol.py::TestMapColorsToSegments -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement map_colors_to_segments**

Append to `src/dj_ledfx/devices/govee/protocol.py`:

```python
def map_colors_to_segments(
    colors: NDArray[np.uint8], num_segments: int
) -> list[tuple[int, int, int]]:
    n_leds = len(colors)
    result: list[tuple[int, int, int]] = []
    for seg in range(num_segments):
        start = seg * n_leds / num_segments
        end = (seg + 1) * n_leds / num_segments
        i_start = int(start)
        i_end = max(i_start + 1, int(end))
        segment_slice = colors[i_start:i_end]
        avg = segment_slice.mean(axis=0).astype(np.uint8)
        result.append((int(avg[0]), int(avg[1]), int(avg[2])))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_protocol.py::TestMapColorsToSegments -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/protocol.py tests/devices/govee/test_protocol.py
git commit -m "feat(govee): add segment color downsampling"
```

---

### Task 5: SKU Registry

**Files:**
- Create: `src/dj_ledfx/devices/govee/sku_registry.py`
- Create: `tests/devices/govee/test_sku_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/devices/govee/test_sku_registry.py
from __future__ import annotations

from dj_ledfx.devices.govee.sku_registry import (
    DEFAULT_CAPABILITY,
    get_device_capability,
    get_segment_count,
)


class TestGetDeviceCapability:
    def test_known_sku_h6076(self) -> None:
        cap = get_device_capability("H6076")
        assert cap.is_rgbic is True
        assert cap.segment_count == 15

    def test_known_sku_h61a2(self) -> None:
        cap = get_device_capability("H61A2")
        assert cap.is_rgbic is True
        assert cap.segment_count == 15

    def test_unknown_sku_returns_default(self) -> None:
        cap = get_device_capability("H9999")
        assert cap == DEFAULT_CAPABILITY
        assert cap.is_rgbic is False
        assert cap.segment_count == 0


class TestGetSegmentCount:
    def test_known_sku(self) -> None:
        assert get_segment_count("H6076") == 15

    def test_unknown_sku(self) -> None:
        assert get_segment_count("H9999") == 0

    def test_config_override_wins(self) -> None:
        assert get_segment_count("H6076", config_override=10) == 10

    def test_config_override_none_uses_registry(self) -> None:
        assert get_segment_count("H6076", config_override=None) == 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_sku_registry.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement SKU registry**

```python
# src/dj_ledfx/devices/govee/sku_registry.py
from __future__ import annotations

from dj_ledfx.devices.govee.types import GoveeDeviceCapability

SKU_REGISTRY: dict[str, GoveeDeviceCapability] = {
    "H6076": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
    "H61A2": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
}

DEFAULT_CAPABILITY = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


def get_device_capability(sku: str) -> GoveeDeviceCapability:
    return SKU_REGISTRY.get(sku, DEFAULT_CAPABILITY)


def get_segment_count(sku: str, config_override: int | None = None) -> int:
    if config_override is not None:
        return config_override
    return get_device_capability(sku).segment_count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_sku_registry.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/sku_registry.py tests/devices/govee/test_sku_registry.py
git commit -m "feat(govee): add SKU registry with capability lookup"
```

---

## Chunk 2: Transport (UDP I/O)

### Task 6: GoveeTransport — Core Socket Management

**Files:**
- Create: `src/dj_ledfx/devices/govee/transport.py`
- Create: `tests/devices/govee/test_transport.py`

- [ ] **Step 1: Write failing tests for transport open/close and send_command**

```python
# tests/devices/govee/test_transport.py
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.devices.govee.transport import GoveeTransport


@pytest.fixture
def transport() -> GoveeTransport:
    return GoveeTransport()


class TestTransportLifecycle:
    @pytest.mark.asyncio
    async def test_open_sets_is_open(self, transport: GoveeTransport) -> None:
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_transport = MagicMock()
            mock_protocol = MagicMock()
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(mock_transport, mock_protocol)
            )
            await transport.open()
            assert transport.is_open is True

    @pytest.mark.asyncio
    async def test_close_sets_not_open(self, transport: GoveeTransport) -> None:
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_send = MagicMock()
            mock_recv = MagicMock()
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                side_effect=[(mock_send, MagicMock()), (mock_recv, MagicMock())]
            )
            await transport.open()
            await transport.close()
            assert transport.is_open is False
            mock_send.close.assert_called_once()
            mock_recv.close.assert_called_once()


class TestSendCommand:
    @pytest.mark.asyncio
    async def test_sends_json_to_port_4003(self, transport: GoveeTransport) -> None:
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_udp_transport = MagicMock()
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(mock_udp_transport, MagicMock())
            )
            await transport.open()

            payload = {"msg": {"cmd": "turn", "data": {"value": 1}}}
            await transport.send_command("192.168.1.23", payload)

            mock_udp_transport.sendto.assert_called_once()
            sent_data, addr = mock_udp_transport.sendto.call_args[0]
            assert addr == ("192.168.1.23", 4003)
            assert json.loads(sent_data) == payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_transport.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement transport core**

```python
# src/dj_ledfx/devices/govee/transport.py
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.devices.govee.protocol import build_scan_message, build_status_query
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

MULTICAST_ADDR = "239.255.255.250"
DISCOVERY_PORT = 4001
RESPONSE_PORT = 4002
COMMAND_PORT = 4003


class GoveeTransport:
    """Shared UDP transport for all Govee devices on the LAN."""

    def __init__(self) -> None:
        self._send_transport: asyncio.DatagramTransport | None = None
        self._recv_transport: asyncio.DatagramTransport | None = None
        self._is_open = False
        self._probe_task: asyncio.Task[None] | None = None

        # Response routing: cmd → handler
        self._cmd_handlers: dict[str, Callable[[dict, tuple[str, int]], None]] = {}
        # Registered devices for probing
        self._devices: dict[str, GoveeDeviceRecord] = {}  # ip → record
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}  # ip → callback
        # Pending status queries: ip → (event, result_container)
        self._pending_status: dict[str, tuple[asyncio.Event, list[dict]]] = {}
        # Probe RTT tracking: ip → send_time (monotonic)
        self._probe_times: dict[str, float] = {}

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def open(self) -> None:
        loop = asyncio.get_running_loop()

        # Sender socket (for commands to port 4003 and multicast to 4001)
        send_transport, _ = await loop.create_datagram_endpoint(
            lambda: _GoveeUDPProtocol(self),
            local_addr=("0.0.0.0", 0),
        )
        self._send_transport = send_transport

        # Receiver socket (listen on port 4002 for responses)
        # Govee devices send responses to port 4002 regardless of sender port.
        recv_transport, _ = await loop.create_datagram_endpoint(
            lambda: _GoveeUDPProtocol(self),
            local_addr=("0.0.0.0", RESPONSE_PORT),
        )
        self._recv_transport = recv_transport

        self._is_open = True
        logger.debug("Govee transport opened")

    async def close(self) -> None:
        self.stop_probing()
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        if self._recv_transport:
            self._recv_transport.close()
        if self._send_transport:
            self._send_transport.close()
        self._is_open = False
        self._devices.clear()
        self._rtt_callbacks.clear()
        self._pending_status.clear()
        self._cmd_handlers.clear()
        logger.debug("Govee transport closed")

    async def send_command(self, ip: str, payload: dict) -> None:
        if self._send_transport:
            data = json.dumps(payload).encode("utf-8")
            self._send_transport.sendto(data, (ip, COMMAND_PORT))

    async def discover(self, timeout_s: float = 5.0) -> list[GoveeDeviceRecord]:
        discovered: dict[str, GoveeDeviceRecord] = {}  # device_id → record

        def _scan_handler(msg_data: dict, addr: tuple[str, int]) -> None:
            data = msg_data.get("data", {})
            device_id = data.get("device", "")
            if device_id and device_id not in discovered:
                discovered[device_id] = GoveeDeviceRecord(
                    ip=data.get("ip", addr[0]),
                    device_id=device_id,
                    sku=data.get("sku", ""),
                    wifi_version=data.get("wifiVersionSoft", ""),
                    ble_version=data.get("bleVersionSoft", ""),
                )

        self._cmd_handlers["scan"] = _scan_handler

        try:
            scan_msg = build_scan_message()
            scan_data = json.dumps(scan_msg).encode("utf-8")

            # Send scan 3 times at 1s intervals
            for i in range(3):
                if self._send_transport:
                    self._send_transport.sendto(scan_data, (MULTICAST_ADDR, DISCOVERY_PORT))
                if i < 2:
                    await asyncio.sleep(1.0)

            # Wait remaining time for stragglers
            remaining = timeout_s - 2.0
            if remaining > 0:
                await asyncio.sleep(remaining)
        finally:
            self._cmd_handlers.pop("scan", None)

        logger.info("Govee discovery found {} devices", len(discovered))
        return list(discovered.values())

    async def query_status(self, ip: str, timeout_s: float = 2.0) -> dict | None:
        event = asyncio.Event()
        result: list[dict] = []
        self._pending_status[ip] = (event, result)

        try:
            await self.send_command(ip, build_status_query())
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout_s)
            except asyncio.TimeoutError:
                return None
            return result[0] if result else None
        finally:
            self._pending_status.pop(ip, None)

    def register_device(
        self, record: GoveeDeviceRecord, rtt_callback: Callable[[float], None]
    ) -> None:
        self._devices[record.ip] = record
        self._rtt_callbacks[record.ip] = rtt_callback

    def start_probing(self, interval_s: float = 5.0) -> None:
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))

    def stop_probing(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()

    async def _probe_loop(self, interval_s: float) -> None:
        while self._is_open:
            for ip in self._devices:
                self._probe_times[ip] = time.monotonic()
                await self.send_command(ip, build_status_query())

            await asyncio.sleep(interval_s)

            # Clean stale entries
            now = time.monotonic()
            stale = [ip for ip, t in self._probe_times.items() if now - t > interval_s]
            for ip in stale:
                self._probe_times.pop(ip, None)

    def _on_datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            msg = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        inner = msg.get("msg", {})
        cmd = inner.get("cmd", "")

        # Route to registered handler
        handler = self._cmd_handlers.get(cmd)
        if handler:
            handler(inner, addr)

        # Handle devStatus responses for query_status and probing
        if cmd == "devStatus":
            self._handle_status_response(inner, addr)

    def _handle_status_response(self, msg: dict, addr: tuple[str, int]) -> None:
        ip = addr[0]

        # Check pending query_status calls first
        pending = self._pending_status.get(ip)
        if pending:
            event, result = pending
            result.append(msg.get("data", {}))
            event.set()
            return

        # Otherwise, it's a probe response — measure RTT
        send_time = self._probe_times.pop(ip, None)
        if send_time is not None:
            rtt_ms = (time.monotonic() - send_time) * 1000.0
            callback = self._rtt_callbacks.get(ip)
            if callback:
                callback(rtt_ms)
                logger.trace("Govee RTT for {}: {:.1f}ms", ip, rtt_ms)


class _GoveeUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, owner: GoveeTransport) -> None:
        self._owner = owner

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        self._owner._on_datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("Govee UDP error: {}", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_transport.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Fix linting issues**

Run: `uv run ruff check src/dj_ledfx/devices/govee/transport.py --fix`
Run: `uv run ruff format src/dj_ledfx/devices/govee/transport.py`

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/govee/transport.py tests/devices/govee/test_transport.py
git commit -m "feat(govee): add GoveeTransport with UDP discovery and command sending"
```

---

## Chunk 3: Adapters

### Task 7: GoveeSolidAdapter

**Files:**
- Create: `src/dj_ledfx/devices/govee/solid.py`
- Create: `tests/devices/govee/test_solid.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/devices/govee/test_solid.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


@pytest.fixture
def record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.23",
        device_id="AA:BB:CC:DD:EE:FF:00:11",
        sku="H6001",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


@pytest.fixture
def mock_transport() -> MagicMock:
    transport = MagicMock()
    transport.query_status = AsyncMock(return_value={"onOff": 1, "brightness": 100})
    transport.send_command = AsyncMock()
    return transport


class TestGoveeSolidAdapter:
    def test_led_count_is_1(self, mock_transport: MagicMock, record: GoveeDeviceRecord) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        assert adapter.led_count == 1

    def test_device_info(self, mock_transport: MagicMock, record: GoveeDeviceRecord) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        info = adapter.device_info
        assert info.device_type == "govee_solid"
        assert info.led_count == 1
        assert info.address == "192.168.1.23:4003"
        assert "H6001" in info.name

    def test_supports_latency_probing_false(self) -> None:
        assert GoveeSolidAdapter.supports_latency_probing is False

    @pytest.mark.asyncio
    async def test_connect_queries_status(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        await adapter.connect()
        assert adapter.is_connected is True
        mock_transport.query_status.assert_awaited_once_with(record.ip)

    @pytest.mark.asyncio
    async def test_connect_raises_on_unreachable(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        mock_transport.query_status = AsyncMock(return_value=None)
        adapter = GoveeSolidAdapter(mock_transport, record)
        with pytest.raises(ConnectionError):
            await adapter.connect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        await adapter.connect()
        await adapter.disconnect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_send_frame_uses_first_pixel(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        await adapter.connect()

        colors = np.array([[255, 128, 0], [0, 0, 0]], dtype=np.uint8)
        await adapter.send_frame(colors)

        mock_transport.send_command.assert_awaited_once()
        call_args = mock_transport.send_command.call_args
        ip = call_args[0][0]
        payload = call_args[0][1]
        assert ip == "192.168.1.23"
        assert payload["msg"]["cmd"] == "colorwc"
        assert payload["msg"]["data"]["color"] == {"r": 255, "g": 128, "b": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_solid.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement GoveeSolidAdapter**

```python
# src/dj_ledfx/devices/govee/solid.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.govee.protocol import build_solid_color_message
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSolidAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord) -> None:
        self._transport = transport
        self._record = record
        self._is_connected = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_solid",
            led_count=1,
            address=f"{self._record.ip}:4003",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return 1

    async def connect(self) -> None:
        status = await self._transport.query_status(self._record.ip)
        if status is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        msg = build_solid_color_message(r, g, b)
        await self._transport.send_command(self._record.ip, msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_solid.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/solid.py tests/devices/govee/test_solid.py
git commit -m "feat(govee): add GoveeSolidAdapter for whole-device color control"
```

---

### Task 8: GoveeSegmentAdapter

**Files:**
- Create: `src/dj_ledfx/devices/govee/segment.py`
- Create: `tests/devices/govee/test_segment.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/devices/govee/test_segment.py
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.govee.protocol import xor_checksum
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


@pytest.fixture
def record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.23",
        device_id="AA:BB:CC:DD:EE:FF:00:11",
        sku="H6076",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


@pytest.fixture
def mock_transport() -> MagicMock:
    transport = MagicMock()
    transport.query_status = AsyncMock(return_value={"onOff": 1})
    transport.send_command = AsyncMock()
    return transport


class TestGoveeSegmentAdapter:
    def test_led_count_equals_segments(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        assert adapter.led_count == 15

    def test_device_info(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        info = adapter.device_info
        assert info.device_type == "govee_segment"
        assert info.led_count == 15

    def test_supports_latency_probing_false(self) -> None:
        assert GoveeSegmentAdapter.supports_latency_probing is False

    @pytest.mark.asyncio
    async def test_connect_raises_on_unreachable(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        mock_transport.query_status = AsyncMock(return_value=None)
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        with pytest.raises(ConnectionError):
            await adapter.connect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_send_frame_sends_pt_real(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=3)
        await adapter.connect()

        colors = np.array(
            [[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8
        )
        await adapter.send_frame(colors)

        mock_transport.send_command.assert_awaited_once()
        call_args = mock_transport.send_command.call_args
        payload = call_args[0][1]
        assert payload["msg"]["cmd"] == "ptReal"
        commands = payload["msg"]["data"]["command"]
        assert len(commands) == 3

        # Verify each command is valid base64 and 20 bytes
        for cmd_b64 in commands:
            decoded = base64.b64decode(cmd_b64)
            assert len(decoded) == 20
            assert decoded[0] == 0x33
            assert decoded[1] == 0x05
            assert decoded[2] == 0x0B
            assert xor_checksum(decoded[:19]) == decoded[19]

    @pytest.mark.asyncio
    async def test_send_frame_downsamples(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        """6 LEDs → 3 segments = downsampled."""
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=3)
        await adapter.connect()

        colors = np.array(
            [[200, 0, 0], [100, 0, 0], [0, 200, 0], [0, 100, 0], [0, 0, 200], [0, 0, 100]],
            dtype=np.uint8,
        )
        await adapter.send_frame(colors)

        payload = mock_transport.send_command.call_args[0][1]
        commands = payload["msg"]["data"]["command"]
        assert len(commands) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_segment.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement GoveeSegmentAdapter**

```python
# src/dj_ledfx/devices/govee/segment.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.govee.protocol import (
    build_pt_real_message,
    build_segment_color_packet,
    encode_segment_mask,
    map_colors_to_segments,
)
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSegmentAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self, transport: GoveeTransport, record: GoveeDeviceRecord, num_segments: int
    ) -> None:
        self._transport = transport
        self._record = record
        self._num_segments = num_segments
        self._is_connected = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_segment",
            led_count=self._num_segments,
            address=f"{self._record.ip}:4003",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._num_segments

    async def connect(self) -> None:
        status = await self._transport.query_status(self._record.ip)
        if status is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        segment_colors = map_colors_to_segments(colors, self._num_segments)

        ble_packets: list[bytes] = []
        for i, (r, g, b) in enumerate(segment_colors):
            mask = encode_segment_mask([i], self._num_segments)
            ble_packets.append(build_segment_color_packet(r, g, b, mask))

        msg = build_pt_real_message(ble_packets)
        await self._transport.send_command(self._record.ip, msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_segment.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/segment.py tests/devices/govee/test_segment.py
git commit -m "feat(govee): add GoveeSegmentAdapter for per-segment ptReal control"
```

---

## Chunk 4: Backend, Config, and Integration

### Task 9: Config Additions

**Files:**
- Modify: `src/dj_ledfx/config.py`

- [ ] **Step 1: Add Govee config fields to AppConfig**

Add after the LIFX section (after line 48):

```python
    # Govee
    govee_enabled: bool = True
    govee_discovery_timeout_s: float = 5.0
    govee_latency_strategy: str = "ema"
    govee_latency_ms: float = 100.0
    govee_manual_offset_ms: float = 0.0
    govee_max_fps: int = 40
    govee_latency_window_size: int = 60
    govee_probe_interval_s: float = 5.0
    govee_segment_override: int | None = None
```

- [ ] **Step 2: Add validation rules to `__post_init__`**

Add after the LIFX validation block (after line 77):

```python
        if self.govee_max_fps <= 0:
            errors.append("govee_max_fps must be positive")
        if self.govee_latency_window_size <= 0:
            errors.append("govee_latency_window_size must be positive")
        if self.govee_latency_strategy not in {"static", "ema", "windowed_mean"}:
            errors.append("govee_latency_strategy must be one of: static, ema, windowed_mean")
        if self.govee_discovery_timeout_s <= 0:
            errors.append("govee_discovery_timeout_s must be positive")
        if self.govee_probe_interval_s <= 0:
            errors.append("govee_probe_interval_s must be positive")
        if self.govee_latency_ms < 0:
            errors.append("govee_latency_ms must be non-negative")
```

- [ ] **Step 3: Add TOML loading block to `load_config()`**

Add after the LIFX loading block (after line 154):

```python
    if "devices" in raw and "govee" in raw["devices"]:
        govee = raw["devices"]["govee"]
        if "enabled" in govee:
            kwargs["govee_enabled"] = govee["enabled"]
        if "discovery_timeout_s" in govee:
            kwargs["govee_discovery_timeout_s"] = govee["discovery_timeout_s"]
        if "latency_strategy" in govee:
            kwargs["govee_latency_strategy"] = govee["latency_strategy"]
        if "latency_ms" in govee:
            kwargs["govee_latency_ms"] = govee["latency_ms"]
        if "manual_offset_ms" in govee:
            kwargs["govee_manual_offset_ms"] = govee["manual_offset_ms"]
        if "max_fps" in govee:
            kwargs["govee_max_fps"] = govee["max_fps"]
        if "latency_window_size" in govee:
            kwargs["govee_latency_window_size"] = govee["latency_window_size"]
        if "probe_interval_s" in govee:
            kwargs["govee_probe_interval_s"] = govee["probe_interval_s"]
        if "segment_override" in govee:
            kwargs["govee_segment_override"] = govee["segment_override"]
```

- [ ] **Step 4: Write tests for Govee config validation**

Add to `tests/test_config.py`:

```python
class TestGoveeConfigValidation:
    def test_govee_defaults(self) -> None:
        config = AppConfig()
        assert config.govee_enabled is True
        assert config.govee_max_fps == 40
        assert config.govee_latency_strategy == "ema"
        assert config.govee_latency_ms == 100.0
        assert config.govee_segment_override is None

    def test_govee_max_fps_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="govee_max_fps"):
            AppConfig(govee_max_fps=0)

    def test_govee_invalid_strategy(self) -> None:
        with pytest.raises(ValueError, match="govee_latency_strategy"):
            AppConfig(govee_latency_strategy="invalid")

    def test_govee_discovery_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="govee_discovery_timeout_s"):
            AppConfig(govee_discovery_timeout_s=0)

    def test_govee_probe_interval_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="govee_probe_interval_s"):
            AppConfig(govee_probe_interval_s=0)

    def test_govee_latency_ms_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="govee_latency_ms"):
            AppConfig(govee_latency_ms=-1)
```

- [ ] **Step 5: Run config tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: All tests PASS (existing + new Govee tests)

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/config.py tests/test_config.py
git commit -m "feat(govee): add Govee config fields, validation, and TOML loading"
```

---

### Task 10: GoveeBackend

**Files:**
- Create: `src/dj_ledfx/devices/govee/backend.py`
- Create: `tests/devices/govee/test_backend.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/devices/govee/test_backend.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


@pytest.fixture
def config() -> AppConfig:
    return AppConfig()


@pytest.fixture
def rgbic_record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.10",
        device_id="AA:BB:CC:DD:EE:FF:00:11",
        sku="H6076",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


@pytest.fixture
def unknown_record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.20",
        device_id="11:22:33:44:55:66:77:88",
        sku="H9999",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


class TestGoveeBackend:
    def test_is_enabled_default(self, config: AppConfig) -> None:
        backend = GoveeBackend()
        assert backend.is_enabled(config) is True

    def test_is_enabled_disabled(self) -> None:
        config = AppConfig(govee_enabled=False)
        backend = GoveeBackend()
        assert backend.is_enabled(config) is False

    @pytest.mark.asyncio
    async def test_discover_creates_segment_adapter_for_rgbic(
        self, config: AppConfig, rgbic_record: GoveeDeviceRecord
    ) -> None:
        backend = GoveeBackend()
        with patch("dj_ledfx.devices.govee.backend.GoveeTransport") as MockTransport:
            mock_transport = MagicMock()
            mock_transport.open = AsyncMock()
            mock_transport.discover = AsyncMock(return_value=[rgbic_record])
            mock_transport.query_status = AsyncMock(return_value={"onOff": 1})
            mock_transport.register_device = MagicMock()
            mock_transport.start_probing = MagicMock()
            MockTransport.return_value = mock_transport

            results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeSegmentAdapter)
        assert results[0].max_fps == 40

    @pytest.mark.asyncio
    async def test_discover_creates_solid_adapter_for_unknown(
        self, config: AppConfig, unknown_record: GoveeDeviceRecord
    ) -> None:
        backend = GoveeBackend()
        with patch("dj_ledfx.devices.govee.backend.GoveeTransport") as MockTransport:
            mock_transport = MagicMock()
            mock_transport.open = AsyncMock()
            mock_transport.discover = AsyncMock(return_value=[unknown_record])
            mock_transport.query_status = AsyncMock(return_value={"onOff": 1})
            mock_transport.register_device = MagicMock()
            mock_transport.start_probing = MagicMock()
            MockTransport.return_value = mock_transport

            results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeSolidAdapter)

    @pytest.mark.asyncio
    async def test_shutdown_stops_probing_and_closes(self) -> None:
        backend = GoveeBackend()
        mock_transport = MagicMock()
        mock_transport.stop_probing = MagicMock()
        mock_transport.close = AsyncMock()
        backend._transport = mock_transport

        await backend.shutdown()

        mock_transport.stop_probing.assert_called_once()
        mock_transport.close.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/devices/govee/test_backend.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement GoveeBackend**

```python
# src/dj_ledfx/devices/govee/backend.py
from __future__ import annotations

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import get_device_capability, get_segment_count
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker


class GoveeBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: GoveeTransport | None = None

    def is_enabled(self, config: AppConfig) -> bool:
        return config.govee_enabled

    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        self._transport = GoveeTransport()
        await self._transport.open()

        records = await self._transport.discover(timeout_s=config.govee_discovery_timeout_s)
        logger.info("Govee discovery found {} devices", len(records))

        results: list[DiscoveredDevice] = []
        for record in records:
            try:
                capability = get_device_capability(record.sku)
                segment_count = get_segment_count(
                    record.sku, config_override=config.govee_segment_override
                )

                if capability.is_rgbic and segment_count > 0:
                    adapter = GoveeSegmentAdapter(
                        self._transport, record, num_segments=segment_count
                    )
                else:
                    adapter = GoveeSolidAdapter(self._transport, record)

                await adapter.connect()
                tracker = self._create_tracker(config)

                self._transport.register_device(
                    record,
                    rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
                )

                results.append(
                    DiscoveredDevice(
                        adapter=adapter,
                        tracker=tracker,
                        max_fps=config.govee_max_fps,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to set up Govee device {} (sku={})",
                    record.ip,
                    record.sku,
                )
                continue

        if results:
            self._transport.start_probing(interval_s=config.govee_probe_interval_s)

        return results

    async def shutdown(self) -> None:
        if self._transport:
            self._transport.stop_probing()
            await self._transport.close()
            self._transport = None

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        strategy: StaticLatency | EMALatency | WindowedMeanLatency
        if config.govee_latency_strategy == "static":
            strategy = StaticLatency(config.govee_latency_ms)
        elif config.govee_latency_strategy == "ema":
            strategy = EMALatency(initial_value_ms=config.govee_latency_ms)
        else:
            strategy = WindowedMeanLatency(
                window_size=config.govee_latency_window_size,
                initial_value_ms=config.govee_latency_ms,
            )
        return LatencyTracker(
            strategy=strategy, manual_offset_ms=config.govee_manual_offset_ms
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/devices/govee/test_backend.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/backend.py tests/devices/govee/test_backend.py
git commit -m "feat(govee): add GoveeBackend with discovery and adapter creation"
```

---

### Task 11: Wire Up Auto-Registration

**Files:**
- Modify: `src/dj_ledfx/devices/govee/__init__.py`
- Modify: `src/dj_ledfx/devices/__init__.py`

- [ ] **Step 1: Export GoveeBackend from govee package**

```python
# src/dj_ledfx/devices/govee/__init__.py
from dj_ledfx.devices.govee.backend import GoveeBackend as GoveeBackend
```

- [ ] **Step 2: Import govee package in devices __init__**

Modify `src/dj_ledfx/devices/__init__.py` to add:

```python
from dj_ledfx.devices import govee as _govee  # noqa: F401
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests PASS (existing + new Govee tests)

- [ ] **Step 4: Run linting and type checking**

Run: `uv run ruff check src/dj_ledfx/devices/govee/ && uv run ruff format --check src/dj_ledfx/devices/govee/`
Run: `uv run mypy src/dj_ledfx/devices/govee/`

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/devices/govee/__init__.py src/dj_ledfx/devices/__init__.py
git commit -m "feat(govee): wire up auto-registration via DeviceBackend"
```

---

### Task 12: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Run formatting**

Run: `uv run ruff format --check .`
Expected: No formatting issues

- [ ] **Step 4: Run type checking**

Run: `uv run mypy src/`
Expected: No errors

- [ ] **Step 5: Verify demo mode still works**

Run: `uv run -m dj_ledfx --demo`
Expected: App starts, no Govee errors (just "found 0 devices" log since no hardware present)
