from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from govee_fakes import STATUS

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


LAMP_IP = "127.0.0.1"


def _listening() -> GoveeTransport:
    """A transport whose sends go nowhere; a test hands it the lamp's replies."""
    transport = GoveeTransport()
    transport._send_transport = MagicMock()
    return transport


def _reply(transport: GoveeTransport, status: dict[str, object]) -> None:
    message = {"msg": {"cmd": "devStatus", "data": status}}
    transport._on_datagram_received(json.dumps(message).encode(), (LAMP_IP, 4003))


class TestStatusQueries:
    async def test_two_overlapping_queries_to_one_lamp_both_get_its_one_reply(self) -> None:
        transport = _listening()
        first = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        second = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        await asyncio.sleep(0)  # both are waiting

        _reply(transport, STATUS)

        assert (await first, await second) == (STATUS, STATUS)
        assert transport._send_transport.sendto.call_count == 1  # one query went out

    async def test_a_caller_that_gives_up_leaves_the_query_to_the_others(self) -> None:
        transport = _listening()
        impatient = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=0.01))
        patient = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        assert await impatient is None

        _reply(transport, STATUS)

        assert await patient == STATUS

    async def test_a_query_after_a_reply_asks_the_lamp_again(self) -> None:
        transport = _listening()
        first = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        await asyncio.sleep(0)
        _reply(transport, STATUS)
        assert await first == STATUS

        again = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        await asyncio.sleep(0)
        _reply(transport, {**STATUS, "onOff": 1})

        assert await again == {**STATUS, "onOff": 1}
        assert transport._send_transport.sendto.call_count == 2
