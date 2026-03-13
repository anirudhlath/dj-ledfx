from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import TileInfo
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
        mock_transport,
        DeviceInfo("Tile", "lifx_tile", 320, "1.2.3.4:56700"),
        target_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
        tile_count=5,
    )
    assert adapter.led_count == 320


@pytest.mark.asyncio
async def test_send_frame_splits_into_per_tile_packets(mock_transport: MagicMock) -> None:
    adapter = LifxTileChainAdapter(
        mock_transport,
        DeviceInfo("Tile", "lifx_tile", 320, "1.2.3.4:56700"),
        target_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
        tile_count=5,
    )
    adapter._is_connected = True
    colors = np.zeros((320, 3), dtype=np.uint8)
    colors[0] = [255, 0, 0]
    await adapter.send_frame(colors)
    assert mock_transport.send_packet.call_count == 5
    for call in mock_transport.send_packet.call_args_list:
        pkt = call[0][0]
        assert pkt.msg_type == 715


def test_supports_latency_probing_false(mock_transport: MagicMock) -> None:
    adapter = LifxTileChainAdapter(
        mock_transport,
        DeviceInfo("Tile", "lifx_tile", 320, "1.2.3.4:56700"),
        target_mac=b"\xaa\xbb\xcc\xdd\xee\xff",
        tile_count=5,
    )
    assert adapter.supports_latency_probing is False
