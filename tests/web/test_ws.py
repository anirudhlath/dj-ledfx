import json
import time
from unittest.mock import MagicMock

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from tempo_fakes import PLAYER, START, FakeTime, play, tempo_clock

from dj_ledfx.events import EventBus
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.types import DeviceStats
from dj_ledfx.web import ws as hub
from dj_ledfx.web.app import create_app
from dj_ledfx.web.ws import beat_message, close_all, stats_message
from tests.web.conftest import until


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
        event_bus=EventBus(),  # the pushes and the inputs heartbeat
    )
    return app


@pytest.fixture
def client(ws_app):
    return TestClient(ws_app)


def test_ws_connect_and_receive_beat(client):
    with client.websocket_connect("/ws") as ws:
        beat = until(ws, "beat")
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
    # Today's UI, until F11; its LIVE badge lights on a deck's name, so none without a DJ:
    assert (message["is_playing"], message["beat_pos"]) == (True, 2)
    assert (message["deck_number"], message["deck_name"]) == (None, None)

    play(tempo, fake, 4, deck=2)

    message = beat_message(tempo)
    assert (message["source"], message["deck_number"], message["deck_name"]) == (
        "prodjlink",
        2,
        PLAYER,
    )


def test_a_tap_is_acked_and_sets_the_tempo(ws_app) -> None:
    with TestClient(ws_app) as client, client.websocket_connect("/ws") as ws:
        sent = time.time()  # the client's clock: within a day of the server's
        for k in range(4):  # 0.4 s apart on the client's clock: 150 BPM
            ws.send_json({"action": "tap", "id": k, "client_time": sent + 0.4 * k})
            assert until(ws, "ack") == {"channel": "ack", "id": k, "action": "tap"}

    tempo = ws_app.state.tempo
    assert tempo.bpm == pytest.approx(150.0)
    assert (tempo.source, tempo.internal.how) == ("internal", "tapped")


class _CountingStore:
    """A tempo store that counts its saves."""

    def __init__(self) -> None:
        self.saves = 0

    async def save(self, settings: object) -> None:
        self.saves += 1


def test_a_socket_tap_leaves_the_save_to_the_clock_s_run(ws_app) -> None:
    """run() saves what changed within 0.25 s; only the REST controls save before answering."""
    store = _CountingStore()
    ws_app.state.tempo = TempoClock(store=store)
    with TestClient(ws_app) as client, client.websocket_connect("/ws") as ws:
        sent = time.time()
        for k in range(4):  # 150 BPM
            ws.send_json({"action": "tap", "id": k, "client_time": sent + 0.4 * k})
            until(ws, "ack")
        ws.send_json({"action": "subscribe_beat", "id": "after", "fps": 5})
        until(ws, "ack")  # the hub has finished with every tap

    assert ws_app.state.tempo.bpm == pytest.approx(150.0)
    assert store.saves == 0


# Review Focus 2: a tap's time the clock can't use is timed by its arrival, one that isn't
# a number is refused as REST refuses it; never a crash.
def test_a_bad_tap_is_answered_and_the_session_lives(ws_app) -> None:
    arrival = ["NaN", "-Infinity", "1e400", "true", "null"]  # true reads as 1.0: 1970
    refused = ['"soon"', "1" + "0" * 400, "[]"]  # not a number, or none a float can hold
    with TestClient(ws_app) as client, client.websocket_connect("/ws") as ws:
        for k, client_time in enumerate(arrival + refused):
            ws.send_text(f'{{"action": "tap", "id": {k}, "client_time": {client_time}}}')
            answer = until(ws, "ack" if k < len(arrival) else "error")
            assert answer["id"] == k
        ws_app.state.tempo.set_tempo("prodjlink")
        ws.send_json({"action": "tap", "id": "locked", "client_time": 1_790_000_000.0})
        locked = until(ws, "error")
        ws.send_json({"action": "subscribe_beat", "id": "alive", "fps": 5})
        alive = until(ws, "ack")

    assert locked["id"] == "locked" and "Pro DJ Link" in locked["detail"]
    assert alive["id"] == "alive"


# Review Focus 2: a command the hub can't use is refused; the session and its beat go on.
@pytest.mark.parametrize(
    "command",
    [
        pytest.param('{"action": "subscribe_beat", "id": 7, "fps": NaN}', id="beat-nan"),
        pytest.param('{"action": "subscribe_frames", "id": 7, "fps": NaN}', id="frames-nan"),
        pytest.param(
            '{"action": "subscribe_frames", "id": 7, "fps": Infinity, "protocol": 2}',
            id="frames-v2-infinity",
        ),
        pytest.param("[]", id="not-an-object"),
    ],
)
def test_a_command_the_hub_can_t_use_is_refused_and_the_beat_goes_on(ws_app, command) -> None:
    with TestClient(ws_app) as client, client.websocket_connect("/ws") as ws:
        ws.send_text(command)
        refused = until(ws, "error")
        beats = [until(ws, "beat"), until(ws, "beat")]  # at its rate, as before

    assert refused.get("id") == (None if command == "[]" else 7)
    assert all(beat["bpm"] == 120.0 for beat in beats)


def test_the_inputs_beat_once_a_second(ws_app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hub, "INPUTS_HEARTBEAT_S", 0.01)
    with TestClient(ws_app) as client, client.websocket_connect("/ws") as ws:
        on_connect = until(ws, "inputs")
        heartbeat = until(ws, "inputs")

    assert on_connect["inputs"]["tempo"]["source"] == "internal"
    assert heartbeat["inputs"] == on_connect["inputs"]


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
