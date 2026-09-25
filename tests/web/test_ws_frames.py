from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import numpy as np
from conftest import FakeLight
from fastapi import FastAPI
from fastapi.testclient import TestClient
from numpy.typing import NDArray
from starlette.testclient import WebSocketTestSession

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
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


SERVER = "openrgb:localhost:6742"


def _light_id(frame: bytes) -> str:
    (length,) = struct.unpack_from("<H", frame, 1)
    return frame[3 : 3 + length].decode()


def _rgb(frame: bytes) -> bytes:
    (length,) = struct.unpack_from("<H", frame, 1)
    return frame[7 + length :]


def test_v2_frames_carry_the_stream_and_the_light_id() -> None:
    devices = DeviceManager()
    openrgb = DeviceCapabilities(protocol="OpenRGB")
    for light in (
        FakeLight(f"{SERVER}:0", led_count=2, caps=openrgb),
        FakeLight(f"{SERVER}:1", led_count=1, caps=openrgb),
        FakeLight("lamp", led_count=1),
        FakeLight("other", led_count=1),
    ):
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(5.0)))
    feed = StubFeed(
        {
            "live": {f"{SERVER}:1": colours(1, 5), "lamp": colours(1, 9), "other": colours(1, 1)},
            "preview": {"lamp": colours(1, 3)},
        }
    )
    watchers = Watchers()
    app = ws_app(feed, watchers, devices)

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "action": "subscribe_frames",
                "protocol": 2,
                "fps": 60,
                "streams": ["live", "preview"],
                "lights": [SERVER, "lamp"],
                "id": 7,
            }
        )
        texts, frames = receive(ws)
        assert watchers.watching_live() and watchers.watching_preview()

    assert {"channel": "ack", "id": 7, "action": "subscribe_frames", "protocol": 2} in texts
    got = {(frame[0], _light_id(frame)): _rgb(frame) for frame in frames}
    assert got == {
        (0x01, SERVER): bytes([0] * 6 + [5] * 3),  # the keyboard has no frame: black
        (0x01, "lamp"): bytes([9] * 3),
        (0x02, "lamp"): bytes([3] * 3),
    }  # "other" wasn't asked for


def test_a_bad_frame_subscription_is_refused_with_the_reason() -> None:
    watchers = Watchers()
    app = ws_app(StubFeed({}), watchers)

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "subscribe_frames", "protocol": 2, "streams": ["fx"], "id": 8})
        ws.send_json({"action": "subscribe_frames", "protocol": 3, "id": 9})
        texts, _ = receive(ws, 2)

    assert texts == [
        {
            "channel": "error",
            "id": 8,
            "detail": "Unknown frame stream 'fx'; expected live or preview",
        },
        {"channel": "error", "id": 9, "detail": "Unknown frame protocol 3; expected 1 or 2"},
    ]
    assert not watchers.watching()
