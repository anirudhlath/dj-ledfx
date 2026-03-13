from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

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
        mock_transport,
        DeviceInfo("Bulb", "lifx", 1, "1.2.3.4:56700"),
        target_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
    )
    assert adapter.led_count == 1


def test_supports_latency_probing_false(mock_transport: MagicMock) -> None:
    adapter = LifxBulbAdapter(
        mock_transport,
        DeviceInfo("Bulb", "lifx", 1, "1.2.3.4:56700"),
        target_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
    )
    assert adapter.supports_latency_probing is False


@pytest.mark.asyncio
async def test_send_frame_sends_set_color(mock_transport: MagicMock) -> None:
    adapter = LifxBulbAdapter(
        mock_transport,
        DeviceInfo("Bulb", "lifx", 1, "1.2.3.4:56700"),
        target_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
    )
    adapter._is_connected = True
    colors = np.array([[255, 0, 0]], dtype=np.uint8)
    await adapter.send_frame(colors)
    mock_transport.send_packet.assert_called_once()
    pkt = mock_transport.send_packet.call_args[0][0]
    assert pkt.msg_type == 102  # SetColor
