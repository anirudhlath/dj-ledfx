"""Tests for GhostAdapter — offline device placeholder."""

import numpy as np
import pytest

from dj_ledfx.devices.ghost import GhostAdapter
from dj_ledfx.types import DeviceInfo


@pytest.fixture
def ghost():
    info = DeviceInfo(
        name="LIFX Strip (192.168.1.5)",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.5:56700",
        mac="d073d5aabbcc",
        stable_id="lifx:d073d5aabbcc",
    )
    return GhostAdapter(device_info=info, led_count=60)


def test_ghost_device_info(ghost):
    assert ghost.device_info.name == "LIFX Strip (192.168.1.5)"
    assert ghost.device_info.stable_id == "lifx:d073d5aabbcc"


def test_ghost_is_not_connected(ghost):
    assert ghost.is_connected is False


def test_ghost_led_count(ghost):
    assert ghost.led_count == 60


def test_ghost_does_not_support_latency_probing(ghost):
    assert ghost.supports_latency_probing is False


@pytest.mark.asyncio
async def test_ghost_connect_is_noop(ghost):
    await ghost.connect()
    assert ghost.is_connected is False


@pytest.mark.asyncio
async def test_ghost_disconnect_is_noop(ghost):
    await ghost.disconnect()


@pytest.mark.asyncio
async def test_ghost_send_frame_raises(ghost):
    colors = np.zeros((60, 3), dtype=np.uint8)
    with pytest.raises(ConnectionError, match="offline"):
        await ghost.send_frame(colors)
