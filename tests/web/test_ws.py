import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.types import BeatState
from dj_ledfx.web.app import create_app


@pytest.fixture
def ws_app():
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

    deck = EffectDeck(BeatPulse())
    scheduler = MagicMock()
    scheduler.frame_snapshots = {}
    scheduler.get_device_stats.return_value = []

    app = create_app(
        beat_clock=clock,
        effect_deck=deck,
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


def test_ws_connect_and_receive_beat(client):
    with client.websocket_connect("/ws") as ws:
        # Should receive a beat message within a reasonable time
        data = ws.receive_text()
        msg = json.loads(data)
        assert msg["channel"] == "beat"
        assert "bpm" in msg


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


def test_ws_set_effect_with_scene_id(client):
    """set_effect with scene_id targets that scene's pipeline."""
    mock_pm = MagicMock()
    client.app.state.pipeline_manager = mock_pm

    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # drain beat

        ws.send_json(
            {
                "action": "set_effect",
                "id": "test1",
                "scene_id": "scene1",
                "effect": "rainbow_wave",
                "params": {},
            }
        )
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack" and msg.get("id") == "test1":
                break
        mock_pm.set_scene_effect.assert_called_once_with("scene1", "rainbow_wave", {})


def test_ws_set_effect_without_scene_id(client):
    """set_effect without scene_id targets the global deck (backward compat)."""
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # drain beat
        ws.send_json(
            {
                "action": "set_effect",
                "id": "test2",
                "effect": "beat_pulse",
                "params": {},
            }
        )
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack" and msg.get("id") == "test2":
                break
        assert client.app.state.effect_deck.effect_name == "beat_pulse"
