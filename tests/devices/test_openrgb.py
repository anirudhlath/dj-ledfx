from unittest.mock import MagicMock, patch

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
        mock_device.colors = [None] * 5
        mock_client = MagicMock()
        mock_client.devices = [mock_device]
        mock_cls.return_value = mock_client

        adapter = OpenRGBAdapter(host="127.0.0.1", port=6742, device_index=0)
        await adapter.connect()

        colors = np.full((10, 3), 128, dtype=np.uint8)
        await adapter.send_frame(colors)

        call_args = mock_device.set_colors.call_args
        sent_colors = call_args[0][0]
        assert len(sent_colors) == 5
