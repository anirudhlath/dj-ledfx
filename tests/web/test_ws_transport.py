import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi", reason="web extra not installed (uv sync --extra web)")

from fastapi.testclient import TestClient

from dj_ledfx.events import EventBus
from dj_ledfx.transport import TransportState
from dj_ledfx.types import BeatState
from dj_ledfx.web.app import create_app


def _make_app():
    clock = MagicMock()
    clock.get_state.return_value = BeatState(
        bpm=128.0,
        beat_phase=0.5,
        bar_phase=0.25,
        is_playing=True,
        next_beat_time=0.0,
    )
    clock.pitch_percent = 0.0
    clock.last_deck_number = 1
    clock.last_deck_name = "CDJ-3000"

    engine = MagicMock()
    engine.transport_state = TransportState.STOPPED

    scheduler = MagicMock()
    scheduler.frame_snapshots = {}
    scheduler.get_device_stats.return_value = []

    bus = EventBus()

    app = create_app(
        beat_clock=clock,
        effect_deck=MagicMock(),
        effect_engine=engine,
        device_manager=MagicMock(),
        scheduler=scheduler,
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"])),
        config_path=None,
        event_bus=bus,
    )
    return app, engine


def test_ws_set_transport_ack():
    app, engine = _make_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"action": "set_transport", "state": "playing", "id": 42}))
        # Read messages until we find the ack
        for _ in range(20):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack" and msg.get("id") == 42:
                assert msg["action"] == "set_transport"
                engine.set_transport_state.assert_called_once_with(TransportState.PLAYING)
                return
        pytest.fail("Did not receive ack for set_transport")


def test_ws_set_transport_invalid():
    app, _engine = _make_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"action": "set_transport", "state": "bogus", "id": 99}))
        for _ in range(20):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "error" and msg.get("id") == 99:
                assert "bogus" in msg["detail"].lower() or "not a valid" in msg["detail"].lower()
                return
        pytest.fail("Did not receive error for invalid set_transport")
