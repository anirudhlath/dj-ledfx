from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from numpy.typing import NDArray
from starlette.testclient import WebSocketTestSession

from dj_ledfx.web.app import create_app
from dj_ledfx.zones.frames import Watchers

Frames = Mapping[str, Mapping[str, NDArray[np.uint8]]]


class StubFeed:
    """A FrameFeed with fixed frames per stream."""

    def __init__(self, frames: Frames) -> None:
        self._frames = frames

    def frames(self, stream: str) -> dict[str, NDArray[np.uint8]]:
        return dict(self._frames.get(stream, {}))


def colours(count: int, value: int) -> NDArray[np.uint8]:
    return np.full((count, 3), value, dtype=np.uint8)


def ws_app(feed: StubFeed, watchers: Watchers, devices: Any = None) -> FastAPI:
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    return create_app(
        beat_clock=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=devices if devices is not None else MagicMock(),
        scheduler=scheduler,
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"])),
        config_path=None,
        frame_feed=feed,
        frame_watchers=watchers,
    )


def receive(ws: WebSocketTestSession, count: int = 10) -> tuple[list[dict[str, Any]], list[bytes]]:
    """The next messages, split into JSON and binary. The beat channel sends nothing here
    (the clock is a mock), so they are the ack and frames, and a stats message a second."""
    texts: list[dict[str, Any]] = []
    frames: list[bytes] = []
    for _ in range(count):
        message = ws.receive()
        if message.get("bytes") is not None:
            frames.append(message["bytes"])
        elif message.get("text") is not None:
            texts.append(json.loads(message["text"]))
    return texts, frames


def test_v1_frames_come_from_the_live_stream_while_the_session_watches_it() -> None:
    watchers = Watchers()
    feed = StubFeed({"live": {"lamp": colours(2, 7)}, "preview": {"lamp": colours(2, 1)}})
    app = ws_app(feed, watchers)

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "subscribe_frames", "fps": 30, "id": 1})
        texts, frames = receive(ws)
        assert watchers.watching_live() and not watchers.watching_preview()

    assert {"channel": "ack", "id": 1, "action": "subscribe_frames", "protocol": 1} in texts
    name, seq = b"lamp", 1
    assert frames[0] == struct.pack("<H", len(name)) + name + struct.pack("<I", seq) + bytes(
        [7] * 6
    )
    assert not watchers.watching()  # the session ended, so it watches nothing
