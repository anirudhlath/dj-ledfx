import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from tempo_fakes import PLAYER, START, FakeTime, play, tempo_clock

from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.types import DeviceStats
from dj_ledfx.web.app import create_app
from dj_ledfx.web.ws import beat_message, close_all, stats_message


@pytest.fixture
def ws_app():
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []

    app = create_app(
        tempo=TempoClock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=scheduler,
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"])),
        config_path=None,
    )
    return app


@pytest.fixture
def client(ws_app):
    return TestClient(ws_app)


def _until(ws: WebSocketTestSession, channel: str) -> dict[str, Any]:
    """The next message on one channel; the pushed snapshots come first."""
    for _ in range(20):
        message: dict[str, Any] = json.loads(ws.receive_text())
        if message["channel"] == channel:
            return message
    pytest.fail(f"no {channel} message")


def test_ws_connect_and_receive_beat(client):
    with client.websocket_connect("/ws") as ws:
        beat = _until(ws, "beat")
    assert (beat["bpm"], beat["source"], beat["stale"]) == (120.0, "internal", False)


def test_the_beat_channel_speaks_v2_and_today_s_ui() -> None:
    fake = FakeTime()
    tempo = tempo_clock(fake)  # the internal clock: 120 BPM, beat 0 at START
    fake.now = START + 2.75  # five and a half beats on: the second bar's second beat

    message = beat_message(tempo)

    assert message["channel"] == "beat"
    assert (message["bpm"], message["bar"], message["beat_in_bar"]) == (120.0, 2, 2)
    assert message["beat_phase"] == pytest.approx(0.5)
    assert message["bar_phase"] == pytest.approx(0.375)
    assert (message["source"], message["stale"], message["pitch_percent"]) == (
        "internal",
        False,
        0.0,
    )
    assert abs(message["server_time"] - time.time()) < 60  # seconds since the epoch
    # Today's UI, until F11:
    assert (message["is_playing"], message["beat_pos"], message["deck_number"]) == (True, 2, None)

    play(tempo, fake, 4, deck=2)

    message = beat_message(tempo)
    assert (message["source"], message["deck_number"], message["deck_name"]) == (
        "prodjlink",
        2,
        PLAYER,
    )


def test_ws_subscribe_beat_command(client):
    with client.websocket_connect("/ws") as ws:
        # Send subscribe command
        ws.send_text(json.dumps({"action": "subscribe_beat", "fps": 5, "id": 1}))
        # Read messages until we get an ack
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack":
                assert msg["id"] == 1
                break


def test_ws_the_old_deck_and_transport_commands_are_gone(client):
    """set_effect and set_transport went with the global deck and transport (M1)."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "set_transport", "id": "t1", "state": "playing"})
        for _ in range(10):
            msg = json.loads(ws.receive_text())
            if msg.get("channel") == "error" and msg.get("id") == "t1":
                assert msg["detail"] == "Unknown action: set_transport"
                break
        else:
            pytest.fail("no error for set_transport")


def test_ws_sessions_close_going_away_when_the_server_stops(ws_app) -> None:
    """granian abandons an open websocket when it stops, so each session closes itself first."""
    with TestClient(ws_app) as client, client.websocket_connect("/ws") as ws:
        ws.receive_text()  # connected
        assert client.portal is not None
        client.portal.call(close_all, ws_app)
        with pytest.raises(WebSocketDisconnect) as closed:
            while True:
                ws.receive_text()
    assert closed.value.code == 1001  # going away


def test_ws_refuses_a_connection_once_the_server_is_stopping(ws_app) -> None:
    with TestClient(ws_app) as client:
        assert client.portal is not None
        client.portal.call(close_all, ws_app)
        with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect("/ws"):
            pass
    assert refused.value.code == 1001


# B10 and B11: the stats channel carries send_fps (web spec §12.4), and status by stable id.
def test_stats_carry_send_fps_and_each_devices_status_by_stable_id() -> None:
    stick = MagicMock(status="offline")
    stick.adapter.device_info.name = "RAM"
    stick.adapter.device_info.effective_id = "openrgb:ram:1"
    twin = MagicMock(status="online")
    twin.adapter.device_info.name = "RAM"
    twin.adapter.device_info.effective_id = "openrgb:ram:0"
    stats = [
        DeviceStats(
            device_name="RAM",
            effective_latency_ms=5.0,
            send_fps=58.0,
            frames_dropped=0,
            connected=True,
            device_id=device_id,
            dropped_pct=0.0,
        )
        for device_id in ("openrgb:ram:0", "openrgb:ram:1")
    ]
    app = MagicMock()
    app.state.scheduler.get_device_stats.return_value = stats
    app.state.device_manager.devices = [stick, twin]

    message = stats_message(app)

    [first, second] = message["devices"]
    assert (first["id"], first["send_fps"], first["status"]) == ("openrgb:ram:0", 58.0, "online")
    assert (second["id"], second["status"]) == ("openrgb:ram:1", "offline")
    assert "fps" not in first
