"""The `fx` channel (web spec §12.4): what each zone draws in space, to the sessions that ask
for it and speak frame protocol 2, at most 30 times a second and only on a change."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from loguru import logger

from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.web.app import create_app
from dj_ledfx.web.fx import FX_FPS
from dj_ledfx.web.state import ClientSubscription
from dj_ledfx.web.ws import _fx_poll, fx_text
from dj_ledfx.zones.frames import Watchers, ZoneFx
from tests.web.conftest import mock_deps, until


def _dot(x: float = 1.0) -> Fx:
    return Fx(particles=swarm([[x, 0.0, 1.0]], (1.0, 1.0, 1.0), 0.2))


class FxFeed:
    """A FrameFeed whose zones draw what a test sets in `shown`."""

    def __init__(self, *shown: ZoneFx) -> None:
        self.shown = list(shown)

    def frames(self, stream: str, wanted: Any = None) -> dict[str, Any]:
        return {}

    def fx(self) -> list[ZoneFx]:
        return list(self.shown)


class Socket:
    """A session's socket: the texts sent to it."""

    def __init__(self) -> None:
        self.texts: list[dict[str, Any]] = []

    async def send_text(self, text: str) -> None:
        self.texts.append(json.loads(text))


def _app(feed: FxFeed) -> Any:
    return SimpleNamespace(state=SimpleNamespace(frame_feed=feed, fx_cache=None))


async def _polled(
    feed: FxFeed, sub: ClientSubscription, *steps: Any, each_s: float = 0.1
) -> list[list[dict[str, Any]]]:
    """Run the session's fx poll; between steps (callables), wait `each_s`. The messages
    sent during each wait, in order."""
    socket = Socket()
    task = asyncio.create_task(_fx_poll(socket, _app(feed), sub))  # type: ignore[arg-type]
    sent: list[list[dict[str, Any]]] = []
    try:
        for step in (lambda: None, *steps):
            step()
            seen = len(socket.texts)
            await asyncio.sleep(each_s)
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
        sub.frame_protocol = 2

    def off() -> None:
        sub.fx = False

    def on() -> None:
        sub.fx = True

    v1, v2, after_off, after_on = await _polled(feed, sub, speaks_2, off, on)

    assert v1 == []
    assert [m["zones"][0]["stream"] for m in v2] == ["preview"]
    assert after_off == []
    assert len(after_on) == 1  # the whole picture again, though nothing changed


async def test_fx_go_out_at_most_30_times_a_second() -> None:
    feed = FxFeed()
    sub = ClientSubscription(frame_protocol=2, fx=True)
    socket = Socket()

    class Moving(FxFeed):
        def fx(self) -> list[ZoneFx]:  # a new frame every time it's asked
            return [ZoneFx("live", "z", _dot(), 1.0)]

    del feed
    task = asyncio.create_task(_fx_poll(socket, _app(Moving()), sub))  # type: ignore[arg-type]
    await asyncio.sleep(0.5)
    task.cancel()
    await asyncio.wait([task])
    assert 0 < len(socket.texts) <= 0.5 * FX_FPS + 1


def test_every_session_shares_one_message_until_a_frame_changes() -> None:
    dot = _dot()
    feed = FxFeed(ZoneFx("live", "z", dot, 1.0))
    app = _app(feed)
    text = fx_text(app)
    assert text is not None and fx_text(app) is text  # made once
    feed.shown = [ZoneFx("live", "z", _dot(), 1.0)]  # the same place, another frame
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
