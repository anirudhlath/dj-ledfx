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
