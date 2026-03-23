"""Tests for DeviceAdapter.capture_state() and restore_state() default implementations."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.types import DeviceInfo


class FakeAdapter(DeviceAdapter):
    """Minimal concrete DeviceAdapter for testing default state methods."""

    def __init__(self, led_count: int = 10) -> None:
        self._led_count = led_count
        self._connected = True
        self.sent_frames: list[NDArray[np.uint8]] = []

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name="FakeDevice",
            device_type="fake",
            led_count=self._led_count,
            address="fake",
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.sent_frames.append(colors.copy())


@pytest.mark.asyncio
async def test_capture_state_default_returns_50pct_white() -> None:
    adapter = FakeAdapter(led_count=5)
    state = await adapter.capture_state()

    # Should be led_count * 3 bytes
    assert len(state) == 5 * 3

    colors = np.frombuffer(state, dtype=np.uint8).reshape(-1, 3)
    assert colors.shape == (5, 3)
    assert np.all(colors == 128)


@pytest.mark.asyncio
async def test_capture_state_default_shape_matches_led_count() -> None:
    for led_count in (1, 10, 144):
        adapter = FakeAdapter(led_count=led_count)
        state = await adapter.capture_state()
        assert len(state) == led_count * 3


@pytest.mark.asyncio
async def test_restore_state_calls_send_frame() -> None:
    adapter = FakeAdapter(led_count=3)
    # Build a custom state: solid red
    state = np.array([[255, 0, 0], [255, 0, 0], [255, 0, 0]], dtype=np.uint8).tobytes()

    await adapter.restore_state(state)

    assert len(adapter.sent_frames) == 1
    sent = adapter.sent_frames[0]
    assert sent.shape == (3, 3)
    assert np.all(sent[:, 0] == 255)  # R
    assert np.all(sent[:, 1] == 0)  # G
    assert np.all(sent[:, 2] == 0)  # B


@pytest.mark.asyncio
async def test_restore_state_round_trip() -> None:
    """capture_state bytes can be fed back to restore_state."""
    adapter = FakeAdapter(led_count=8)
    state = await adapter.capture_state()
    await adapter.restore_state(state)

    assert len(adapter.sent_frames) == 1
    restored = adapter.sent_frames[0]
    assert restored.shape == (8, 3)
    assert np.all(restored == 128)
