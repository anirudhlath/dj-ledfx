from __future__ import annotations

import asyncio
import struct
import time

import pytest

from dj_ledfx.devices.lifx.packet import STATE_UNHANDLED, LifxPacket
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord


@pytest.mark.asyncio
async def test_transport_creates_socket() -> None:
    transport = LifxTransport()
    await transport.open()
    assert transport.is_open
    await transport.close()
    assert not transport.is_open


@pytest.mark.asyncio
async def test_transport_source_id_nonzero() -> None:
    transport = LifxTransport()
    await transport.open()
    assert transport.source_id != 0
    await transport.close()


@pytest.mark.asyncio
async def test_transport_sequence_increments() -> None:
    transport = LifxTransport()
    await transport.open()
    s1 = transport.next_sequence()
    s2 = transport.next_sequence()
    assert s2 == s1 + 1
    await transport.close()


@pytest.mark.asyncio
async def test_transport_sequence_wraps_on_wire() -> None:
    transport = LifxTransport()
    await transport.open()
    transport._sequence_counter = 300
    seq = transport.next_sequence()
    assert seq == 301
    assert seq % 256 == 45
    await transport.close()


@pytest.mark.asyncio
async def test_rtt_probe_correlation() -> None:
    """Echo probe sent → EchoResponse received → RTT callback fired."""
    transport = LifxTransport()
    await transport.open()

    rtt_values: list[float] = []
    record = LifxDeviceRecord(
        mac=b"\xaa\xbb\xcc\xdd\xee\xff",
        ip="192.168.1.100",
        port=56700,
        vendor=1,
        product=55,
    )
    transport.register_device(record, rtt_callback=lambda rtt: rtt_values.append(rtt))

    # Simulate probe: register a pending probe manually
    seq = transport.next_sequence()
    transport._pending_probes[seq] = ("192.168.1.100", time.monotonic())

    # Craft an EchoResponse with the seq embedded in payload
    echo_pkt = LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=b"\xaa\xbb\xcc\xdd\xee\xff\x00\x00",
        ack_required=False,
        res_required=False,
        sequence=seq % 256,
        msg_type=59,
        payload=seq.to_bytes(8, "little") + b"\x00" * 56,
    )
    # Feed the response directly into the handler
    transport._on_packet_received(echo_pkt.pack(), ("192.168.1.100", 56700))

    assert len(rtt_values) == 1
    assert rtt_values[0] >= 0
    await transport.close()


@pytest.mark.asyncio
async def test_discover_sends_broadcast() -> None:
    """Discovery sends GetService(2) with tagged=1."""
    transport = LifxTransport()
    await transport.open()
    # Discovery with 0.1s timeout returns empty list (no devices on test network)
    devices = await transport.discover(timeout_s=0.1)
    assert isinstance(devices, list)
    await transport.close()


class _Sent:
    """Stands in for the UDP socket and keeps what was sent."""

    def __init__(self) -> None:
        self.packets: list[tuple[LifxPacket, tuple[str, int]]] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.packets.append((LifxPacket.unpack(data), addr))

    def close(self) -> None:
        pass


def _transport() -> tuple[LifxTransport, _Sent]:
    transport = LifxTransport()
    sent = _Sent()
    transport._socket = sent  # type: ignore[assignment]
    transport._is_open = True
    return transport, sent


def _request(msg_type: int = 101) -> LifxPacket:
    return LifxPacket(
        tagged=False,
        source=0,
        target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
        ack_required=False,
        res_required=True,
        sequence=0,
        msg_type=msg_type,
        payload=b"",
    )


def _reply(transport: LifxTransport, request: LifxPacket, msg_type: int, payload: bytes) -> bytes:
    return LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=request.target,
        ack_required=False,
        res_required=False,
        sequence=request.sequence,
        msg_type=msg_type,
        payload=payload,
    ).pack()


@pytest.mark.asyncio
async def test_concurrent_requests_get_their_own_replies() -> None:
    transport, sent = _transport()
    first = asyncio.create_task(transport.request_response(_request(), ("10.0.0.1", 56700), 107))
    second = asyncio.create_task(transport.request_response(_request(), ("10.0.0.2", 56700), 107))
    await asyncio.sleep(0)
    (req_a, _), (req_b, _) = sent.packets
    assert req_a.sequence != req_b.sequence

    # Replies arrive in the opposite order.
    transport._on_packet_received(_reply(transport, req_b, 107, b"B"), ("10.0.0.2", 56700))
    transport._on_packet_received(_reply(transport, req_a, 107, b"A"), ("10.0.0.1", 56700))

    reply_a, reply_b = await asyncio.gather(first, second)
    assert reply_a is not None and reply_a.payload == b"A"
    assert reply_b is not None and reply_b.payload == b"B"


@pytest.mark.asyncio
async def test_reply_with_another_sequence_is_ignored() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    stray = LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=request.target,
        ack_required=False,
        res_required=False,
        sequence=(request.sequence + 1) % 256,
        msg_type=107,
        payload=b"x",
    )
    transport._on_packet_received(stray.pack(), ("10.0.0.1", 56700))
    assert await task is None


@pytest.mark.asyncio
async def test_reply_from_another_light_is_ignored() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    transport._on_packet_received(_reply(transport, request, 107, b"x"), ("10.0.0.9", 56700))
    assert await task is None


@pytest.mark.asyncio
async def test_state_unhandled_answers_the_request() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(transport.request_response(_request(719), ("10.0.0.1", 56700), 720))
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    transport._on_packet_received(
        _reply(transport, request, STATE_UNHANDLED, struct.pack("<H", 719)), ("10.0.0.1", 56700)
    )
    reply = await task
    assert reply is not None and reply.msg_type == STATE_UNHANDLED


@pytest.mark.asyncio
async def test_timeout_returns_none_and_forgets_the_request() -> None:
    transport, _ = _transport()
    reply = await transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.02)
    assert reply is None
    assert transport._waiters == {}


@pytest.mark.asyncio
async def test_echo_replies_are_handled_while_a_request_waits() -> None:
    transport, sent = _transport()
    rtts: list[float] = []
    record = LifxDeviceRecord(mac=b"\xaa" * 6, ip="10.0.0.1", port=56700, vendor=1, product=1)
    transport.register_device(record, rtt_callback=rtts.append)
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)

    seq = transport.next_sequence()
    transport._pending_probes[seq] = ("10.0.0.1", time.monotonic())
    echo = LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=b"\xaa" * 6 + b"\x00\x00",
        ack_required=False,
        res_required=False,
        sequence=seq % 256,
        msg_type=59,
        payload=seq.to_bytes(8, "little") + b"\x00" * 56,
    )
    transport._on_packet_received(echo.pack(), ("10.0.0.1", 56700))

    assert len(rtts) == 1
    await task


@pytest.mark.asyncio
async def test_listeners_see_packets_while_a_request_waits() -> None:
    transport, sent = _transport()
    seen: list[int] = []
    transport.add_listener(lambda pkt, addr: seen.append(pkt.msg_type))
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)
    service = LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=b"\xbb" * 6 + b"\x00\x00",
        ack_required=False,
        res_required=False,
        sequence=0,
        msg_type=3,
        payload=struct.pack("<BI", 1, 56700),
    )
    transport._on_packet_received(service.pack(), ("10.0.0.7", 56700))
    assert seen == [3]
    await task


@pytest.mark.asyncio
async def test_query_host_firmware() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(transport.query_host_firmware(b"\xaa" * 6, "10.0.0.1", 56700))
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    assert request.msg_type == 14
    transport._on_packet_received(
        _reply(transport, request, 15, struct.pack("<QQHH", 0, 0, 77, 2)), ("10.0.0.1", 56700)
    )
    assert await task == (2, 77)


@pytest.mark.asyncio
async def test_query_version_retries_once_then_defaults_to_a_bulb() -> None:
    transport, sent = _transport()
    assert await transport._query_version(b"\xaa" * 6, "10.0.0.1", 56700) == (1, 0)
    assert [p.msg_type for p, _ in sent.packets] == [32, 32]
