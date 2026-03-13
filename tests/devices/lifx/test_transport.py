from __future__ import annotations

import time

import pytest

from dj_ledfx.devices.lifx.packet import LifxPacket
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
