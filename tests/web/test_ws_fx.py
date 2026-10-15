"""The `fx` channel (web spec §12.4): what each zone draws in space, to the sessions that ask
for it and speak frame protocol 2, at most 30 times a second and only on a change."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.web import ws as ws_module
from dj_ledfx.web.app import create_app
from dj_ledfx.web.fx import FX_FPS
from dj_ledfx.web.state import ClientSubscription
from dj_ledfx.web.ws import _fx_poll, fx_text
from dj_ledfx.zones.frames import Watchers, ZoneFx
from tests.web.conftest import mock_deps, until


def _dot(x: float = 1.0) -> Fx:
    return Fx(particles=swarm([[x, 0.0, 1.0]], (1.0, 1.0, 1.0), 0.2))


class FxFeed:
    """A FrameFeed whose zones draw what a test sets in `shown`; `reads` counts the poll's
    ticks that reached it."""

    def __init__(self, *shown: ZoneFx) -> None:
        self.shown = list(shown)
        self.reads = 0

    def frames(self, stream: str, wanted: Any = None) -> dict[str, Any]:
        return {}

    def fx(self) -> list[ZoneFx]:
        self.reads += 1
        return list(self.shown)


class Socket:
    """A session's socket: the texts sent to it, and when."""

    def __init__(self) -> None:
        self.texts: list[dict[str, Any]] = []
        self.times: list[float] = []

    async def send_text(self, text: str) -> None:
        self.texts.append(json.loads(text))
        self.times.append(time.perf_counter())


class BrokenSocket(Socket):
    async def send_text(self, text: str) -> None:
        raise ConnectionError("gone")


def _app(feed: FxFeed) -> Any:
    return SimpleNamespace(state=SimpleNamespace(frame_feed=feed, fx_cache=None))


async def _until(condition: Callable[[], bool], deadline_s: float = 10.0) -> None:
    """Wait for a condition, as long as a loaded machine needs: a deadline, not a duration."""
    end = time.monotonic() + deadline_s
    while not condition():
        assert time.monotonic() < end, "timed out waiting"
        await asyncio.sleep(0.005)


async def _polled(
    feed: FxFeed, sub: ClientSubscription, *steps: Callable[[], None]
) -> list[list[dict[str, Any]]]:
    """Run the session's fx poll; after each step (callables, the first doing nothing), wait
    for three ticks of the poll to reach the feed, or, when the session doesn't ask for fx,
    a moment in which the poll must not touch it. The messages sent during each wait."""
    socket = Socket()
    task = asyncio.create_task(_fx_poll(socket, _app(feed), sub))  # type: ignore[arg-type]
    sent: list[list[dict[str, Any]]] = []
    try:
        for step in (lambda: None, *steps):
            step()
            seen, reads = len(socket.texts), feed.reads
            if sub.wants_fx:
                await _until(lambda reads=reads: feed.reads >= reads + 3)
            else:
                await asyncio.sleep(0.15)
                assert feed.reads == reads, "the poll woke for a session that doesn't ask"
            sent.append(socket.texts[seen:])
    finally:
        task.cancel()
        await asyncio.wait([task])
    return sent


async def test_a_session_gets_the_picture_once_then_nothing_while_nothing_changes() -> None:
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    sub = ClientSubscription(frame_protocol=2, fx=True)

    def moved() -> None:
        feed.shown = [ZoneFx("live", "z", _dot(2.0), 1.0)]

    def stopped() -> None:
        feed.shown = []

    first, *_, after_move, after_stop, quiet = await _polled(
        feed, sub, lambda: None, moved, stopped, lambda: None
    )

    assert [m["zones"][0]["particles"][0][0] for m in first] == [1.0]
    assert [m["zones"][0]["particles"][0][0] for m in after_move] == [2.0]
    assert after_stop == [{"channel": "fx", "zones": []}]  # once, as the last zone stops
    assert quiet == []


async def test_a_brightness_change_is_a_change() -> None:
    dot = _dot()
    feed = FxFeed(ZoneFx("live", "z", dot, 1.0))

    def dimmed() -> None:
        feed.shown = [ZoneFx("live", "z", dot, 0.5)]

    first, after = await _polled(feed, ClientSubscription(frame_protocol=2, fx=True), dimmed)
    assert first[0]["zones"][0]["particles"][0][3] == 1.0
    assert [m["zones"][0]["particles"][0][3] for m in after] == [0.5]


async def test_only_a_protocol_2_session_that_asked_gets_fx_and_turning_on_resends() -> None:
    feed = FxFeed(ZoneFx("preview", "z", _dot(), 1.0))
    sub = ClientSubscription(frame_protocol=1, fx=True)

    def speaks_2() -> None:
        sub.set_frame_protocol(2)

    def off() -> None:
        sub.set_fx(False)

    def on() -> None:
        sub.set_fx(True)

    v1, v2, after_off, after_on = await _polled(feed, sub, speaks_2, off, on)

    assert v1 == []
    assert [m["zones"][0]["stream"] for m in v2] == ["preview"]
    assert after_off == []
    assert len(after_on) == 1  # the whole picture again, though nothing changed


async def test_every_subscribe_sends_the_whole_picture_however_fast_the_commands_came() -> None:
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    sub = ClientSubscription(frame_protocol=2, fx=True)

    def off_and_on() -> None:  # both handled between two ticks
        sub.set_fx(False)
        sub.set_fx(True)

    def on_again() -> None:
        sub.set_fx(True)

    def protocol_2_1_2() -> None:
        sub.set_frame_protocol(1)
        sub.set_frame_protocol(2)

    def protocol_2_again() -> None:  # not a switch: nothing to resend
        sub.set_frame_protocol(2)

    first, after_off_on, after_on_again, after_switch, after_again, quiet = await _polled(
        feed, sub, off_and_on, on_again, protocol_2_1_2, protocol_2_again, lambda: None
    )
    assert [len(first), len(after_off_on), len(after_on_again), len(after_switch)] == [1] * 4
    assert after_again == [] and quiet == []


class CountedSubscription(ClientSubscription):
    """A subscription that counts the poll's wake-ups: it asks wants_fx once each time."""

    asked = 0

    @property
    def wants_fx(self) -> bool:
        self.asked += 1
        return super().wants_fx


async def test_the_poll_sleeps_while_the_session_doesnt_ask_and_wakes_when_it_does() -> None:
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    sub = CountedSubscription(frame_protocol=2, fx=False)
    socket = Socket()
    task = asyncio.create_task(_fx_poll(socket, _app(feed), sub))  # type: ignore[arg-type]
    try:
        await _until(lambda: sub.asked >= 1)  # its first tick: then it sleeps
        await asyncio.sleep(0.3)  # nine ticks of a loop that polled at FX_FPS
        assert sub.asked == 1 and feed.reads == 0
        sub.set_fx(True)
        await _until(lambda: len(socket.texts) == 1)  # woken: the picture at once
        sub.set_fx(False)
        await _until(lambda: not sub.fx_changed.is_set())  # asleep again
        asked = sub.asked
        await asyncio.sleep(0.3)
        assert sub.asked == asked
    finally:
        task.cancel()
        await asyncio.wait([task])


async def test_fx_go_out_at_most_30_times_a_second() -> None:
    class Moving(FxFeed):
        def fx(self) -> list[ZoneFx]:  # another picture every time it's asked
            self.reads += 1
            return [ZoneFx("live", "z", _dot(self.reads / 1000.0), 1.0)]

    socket = Socket()
    sub = ClientSubscription(frame_protocol=2, fx=True)
    task = asyncio.create_task(_fx_poll(socket, _app(Moving()), sub))  # type: ignore[arg-type]
    try:
        await _until(lambda: len(socket.texts) >= 8)
    finally:
        task.cancel()
        await asyncio.wait([task])
    gaps = [b - a for a, b in zip(socket.times, socket.times[1:], strict=False)]
    assert min(gaps) >= 1.0 / FX_FPS - 0.005  # a loaded machine only widens the gaps


async def test_one_sessions_failed_send_ends_its_poll_alone() -> None:
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    app = _app(feed)
    broken, good = BrokenSocket(), Socket()
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="DEBUG")
    bad_task = asyncio.create_task(
        _fx_poll(broken, app, ClientSubscription(frame_protocol=2, fx=True))  # type: ignore[arg-type]
    )
    good_task = asyncio.create_task(
        _fx_poll(good, app, ClientSubscription(frame_protocol=2, fx=True))  # type: ignore[arg-type]
    )
    try:
        await _until(lambda: bad_task.done() and len(good.texts) == 1)
        feed.shown = [ZoneFx("live", "z", _dot(2.0), 1.0)]
        await _until(lambda: len(good.texts) == 2)  # fx_cache is shared, the good poll goes on
        assert not good_task.done()
    finally:
        good_task.cancel()
        await asyncio.wait([good_task])
        logger.remove(sink)
    assert bad_task.exception() is None
    assert any("The fx channel ended" in message for message in messages)


def test_polls_within_one_engine_frame_share_one_message() -> None:
    dot = _dot()
    feed = FxFeed(ZoneFx("live", "z", dot, 1.0))
    app = _app(feed)
    text = fx_text(app)
    assert text is not None and fx_text(app) is text  # made once for the frame
    feed.shown = [ZoneFx("live", "z", _dot(), 1.0)]  # the same place, another frame: again
    assert fx_text(app) is not text
    assert fx_text(SimpleNamespace(state=SimpleNamespace(frame_feed=None, fx_cache=None))) is None


def test_subscribe_fx_is_acked_and_sends_fx_over_the_socket() -> None:
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    app = create_app(**mock_deps(scheduler=scheduler, frame_feed=feed, frame_watchers=Watchers()))

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "subscribe_fx", "on": "yes", "id": 1})
        error = until(ws, "error")
        assert error == {
            "channel": "error",
            "id": 1,
            "detail": "subscribe_fx takes on: true or false",
        }
        ws.send_json({"action": "subscribe_frames", "protocol": 2, "id": 2})
        until(ws, "ack")
        ws.send_json({"action": "subscribe_fx", "on": True, "id": 3})
        assert until(ws, "ack") == {
            "channel": "ack",
            "id": 3,
            "action": "subscribe_fx",
            "on": True,
        }
        message = until(ws, "fx")

    assert message["zones"] == [
        {"zoneId": "z", "stream": "live", "particles": [[1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.2]]}
    ]


async def test_a_message_that_cant_be_made_ends_the_channel_once_with_a_log() -> None:
    class Broken(FxFeed):
        def fx(self) -> list[ZoneFx]:
            raise RuntimeError("no fx")

    errors: list[str] = []
    sink = logger.add(lambda message: errors.append(str(message)), level="ERROR")
    socket = Socket()
    sub = ClientSubscription(frame_protocol=2, fx=True)
    try:
        await asyncio.wait_for(_fx_poll(socket, _app(Broken()), sub), 1.0)  # type: ignore[arg-type]
    finally:
        logger.remove(sink)
    assert socket.texts == [] and len(errors) == 1 and "RuntimeError: no fx" in errors[0]


def _recording_polls(monkeypatch: pytest.MonkeyPatch) -> list[asyncio.Task[Any]]:
    """The fx poll tasks the app starts, as they start."""
    started: list[asyncio.Task[Any]] = []
    real = ws_module._fx_poll

    async def recording(ws: Any, app: Any, sub: Any) -> None:
        task = asyncio.current_task()
        assert task is not None
        started.append(task)
        await real(ws, app, sub)

    monkeypatch.setattr(ws_module, "_fx_poll", recording)
    return started


def _fx_app() -> Any:
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    return create_app(**mock_deps(scheduler=scheduler, frame_feed=feed, frame_watchers=Watchers()))


def test_repeated_toggles_keep_one_poll_task_and_closing_the_socket_ends_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _recording_polls(monkeypatch)
    with TestClient(_fx_app()) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"action": "subscribe_frames", "protocol": 2, "id": 1})
            until(ws, "ack")
            for n, on in enumerate([True, False, True, True, False, True], start=2):
                ws.send_json({"action": "subscribe_fx", "on": on, "id": n})
                assert until(ws, "ack")["on"] is on
            assert len(started) == 1 and not started[0].done()
        deadline = time.monotonic() + 10
        while not started[0].done() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started[0].done()  # cancelled with the session, the app still running
