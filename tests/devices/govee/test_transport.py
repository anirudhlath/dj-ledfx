from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from govee_fakes import STATUS, lamp_record
from loguru import logger

from dj_ledfx.devices.govee import transport as govee_transport
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
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


class TestRoundTrips:
    """A lamp's round trips come from the status reads: each matched query and reply."""

    def _timed(self) -> tuple[GoveeTransport, list[float], list[float]]:
        now = [100.0]
        transport = GoveeTransport(clock=lambda: now[0])
        transport._send_transport = MagicMock()
        rtts: list[float] = []
        transport.register_device(lamp_record(), rtt_callback=rtts.append, streaming=lambda: True)
        return transport, now, rtts

    async def test_a_status_reply_feeds_the_lamp_s_round_trip(self) -> None:
        transport, now, rtts = self._timed()
        query = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        await asyncio.sleep(0)
        now[0] += 0.04

        _reply(transport, STATUS)

        assert await query == STATUS
        assert rtts == [pytest.approx(40.0)]

    async def test_one_reply_shared_by_two_callers_is_one_round_trip(self) -> None:
        transport, now, rtts = self._timed()
        first = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        second = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        await asyncio.sleep(0)
        now[0] += 0.03
        _reply(transport, STATUS)
        await asyncio.gather(first, second)
        assert rtts == [pytest.approx(30.0)]

    async def test_a_reply_nobody_waits_for_is_no_round_trip(self) -> None:
        transport, _now, rtts = self._timed()
        _reply(transport, STATUS)  # late, or sent to another program's query
        assert rtts == []


class _Waits:
    """The probe loop's sleep: each wait is held until the test lets a round run."""

    def __init__(self) -> None:
        self.asked: list[float] = []  # how long each wait was
        self._asleep = asyncio.Event()
        self._wake: asyncio.Future[None] | None = None

    async def __call__(self, seconds: float) -> None:
        self.asked.append(seconds)
        self._wake = asyncio.get_running_loop().create_future()
        self._asleep.set()
        await self._wake

    async def round(self) -> None:
        """End the wait the loop is in, and let its round run until it waits again. A loop
        that never waits again fails the test rather than hanging it."""
        async with asyncio.timeout(1.0):
            await self._asleep.wait()
            self._asleep.clear()
            assert self._wake is not None
            self._wake.set_result(None)
            await self._asleep.wait()
        await asyncio.sleep(0)  # each probe the round started has sent its query


def _probed(
    *, can_receive: bool = True, clock: Callable[[], float] = lambda: 100.0
) -> tuple[GoveeTransport, _Waits, list[bool], list[float]]:
    """A transport that probes the test lamp on held waits; whether the lamp streams, which a
    test can change; and the lamp's round trips."""
    waits = _Waits()
    transport = GoveeTransport(clock, sleep=waits, rng=random.Random(7))
    transport._is_open = True
    transport._send_transport = MagicMock()
    transport._recv_transport = MagicMock() if can_receive else None
    streams = [True]
    rtts: list[float] = []
    transport.register_device(lamp_record(), rtts.append, streaming=lambda: streams[0])
    return transport, waits, streams, rtts


def _asked(transport: GoveeTransport) -> int:
    """How many status queries went to the lamp."""
    return transport._send_transport.sendto.call_count  # type: ignore[union-attr]


@pytest.fixture
def patient_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each probe waits a minute for its reply, so a test that holds one in flight never
    races the wall clock's PROBE_TIMEOUT_S."""
    monkeypatch.setattr(govee_transport, "PROBE_TIMEOUT_S", 60.0)


@contextmanager
def _logged_errors() -> Iterator[list[Any]]:
    """Every record logged at ERROR in the block."""
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="ERROR")
    try:
        yield records
    finally:
        logger.remove(sink)


class TestProbeLoop:
    """The light-sync spec's §4: a lamp that streams is asked for its status about every
    probe interval, and its reply times a round trip."""

    async def test_only_a_lamp_that_streams_is_probed(self) -> None:
        transport, waits, streams, _ = _probed()
        streams[0] = False
        transport.start_probing(0.5)
        await waits.round()
        assert _asked(transport) == 0  # idle: its round trip wouldn't count
        streams[0] = True
        await waits.round()
        assert _asked(transport) == 1
        await transport.close()

    async def test_each_wait_is_75_to_125_percent_of_the_interval(self) -> None:
        transport, waits, streams, _ = _probed()
        streams[0] = False
        transport.start_probing(0.5)
        for _ in range(40):
            await waits.round()
        assert all(0.375 <= wait <= 0.625 for wait in waits.asked)
        assert min(waits.asked) < 0.4 and max(waits.asked) > 0.6  # random, not one wait
        await transport.close()

    async def test_a_query_in_flight_is_shared_never_doubled(self) -> None:
        transport, waits, _, rtts = _probed()
        read = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=5.0))
        await asyncio.sleep(0)  # the light monitor's read is in flight
        transport.start_probing(0.5)
        await waits.round()
        assert _asked(transport) == 1  # the read's query, not a probe's
        _reply(transport, STATUS)
        assert await read == STATUS and len(rtts) == 1
        await waits.round()
        assert _asked(transport) == 2  # answered: the next round asks again
        await transport.close()

    @pytest.mark.usefixtures("patient_probes")
    async def test_a_silent_lamp_holds_up_no_round(self) -> None:
        transport, waits, _, _ = _probed()
        transport.start_probing(0.5)
        for _ in range(5):
            await waits.round()
        assert len(waits.asked) == 6  # the rounds go on
        assert _asked(transport) == 1  # while its one probe waits for the reply
        await transport.close()

    def test_a_probe_waits_a_second_for_its_reply(self) -> None:
        assert govee_transport.PROBE_TIMEOUT_S == 1.0  # ruling 5

    async def test_a_probe_gives_up_at_its_timeout_having_asked_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(govee_transport, "PROBE_TIMEOUT_S", 0.01)
        transport, waits, _, _ = _probed()
        transport.start_probing(0.5)
        await waits.round()
        probes = set(transport._probes)
        assert probes  # the round's probe is in flight
        # It gives up at its timeout, with no reply. The test waits for the probe itself, not
        # a sleep past its timeout: on Python 3.11 wait_for's cancel takes more passes of the
        # event loop, so a stall of a few tens of ms left it in _probes. Its done-callback,
        # added first, has taken it out by the time this wait ends.
        await asyncio.wait(probes, timeout=1.0)
        assert _asked(transport) == 1 and not transport._probes  # it gave up, asking once
        await waits.round()
        assert _asked(transport) == 2  # the next round asks again
        await transport.close()

    @pytest.mark.usefixtures("patient_probes")
    async def test_a_probe_s_reply_times_the_lamp_s_round_trip(self) -> None:
        now = [100.0]
        transport, waits, _, rtts = _probed(clock=lambda: now[0])
        transport.start_probing(0.5)
        await waits.round()
        now[0] += 0.25
        _reply(transport, STATUS)
        assert rtts == [pytest.approx(250.0)]
        await transport.close()

    async def test_nothing_is_probed_while_another_program_holds_the_reply_port(self) -> None:
        transport, waits, _, _ = _probed(can_receive=False)
        transport.start_probing(0.5)
        for _ in range(3):
            await waits.round()
        assert _asked(transport) == 0
        await transport.close()

    @pytest.mark.usefixtures("patient_probes")
    async def test_the_loop_and_its_probes_stop_at_close(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        transport, waits, _, _ = _probed()
        transport.start_probing(0.5)
        loop = transport._probe_task
        transport.start_probing(0.5)
        assert transport._probe_task is loop  # one loop
        await waits.round()
        probes = set(transport._probes)
        assert len(probes) == 1  # in flight

        with _logged_errors() as errors:
            await transport.close()

        assert loop is not None and loop.cancelled()
        assert all(probe.cancelled() for probe in probes) and not transport._probes
        assert errors == [] and caplog.records == []  # a loop cancelled at close ends quietly

    async def test_a_loop_that_fails_logs_it_once(self) -> None:
        async def nan_sleep(seconds: float) -> None:
            raise ValueError("Invalid delay: NaN (not a number)")  # as asyncio.sleep(nan)

        transport = GoveeTransport(sleep=nan_sleep)
        transport._is_open = True
        with _logged_errors() as errors:
            transport.start_probing(0.5)
            assert transport._probe_task is not None
            await asyncio.wait([transport._probe_task])
        assert [error["exception"].type for error in errors] == [ValueError]
        assert "probe loop" in errors[0]["message"]
        await transport.close()


class TestHeardFrom:
    async def test_every_status_reply_stamps_when_the_lamp_was_heard(self) -> None:
        now = [100.0]
        transport = GoveeTransport(clock=lambda: now[0])
        transport._send_transport = MagicMock()
        assert transport.last_heard(LAMP_IP) is None

        _reply(transport, STATUS)  # nobody waits for this one: it's late
        assert transport.last_heard(LAMP_IP) == 100.0

        now[0] = 105.0
        query = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=1.0))
        await asyncio.sleep(0)
        _reply(transport, STATUS)
        await query
        assert transport.last_heard(LAMP_IP) == 105.0

    def test_a_lamp_was_last_heard_when_its_transport_last_heard_it(self) -> None:
        transport = GoveeTransport(clock=lambda: 7.0)
        lamp = GoveeColourAdapter(transport, lamp_record())
        assert lamp.last_heard is None
        _reply(transport, STATUS)
        assert lamp.last_heard == 7.0
