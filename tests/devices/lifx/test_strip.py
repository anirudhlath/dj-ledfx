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
