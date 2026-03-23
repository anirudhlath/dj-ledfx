from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi", reason="web extra not installed (uv sync --extra web)")

from fastapi.testclient import TestClient

from dj_ledfx.transport import TransportState
from dj_ledfx.web.app import create_app


def _make_app():
    engine = MagicMock()
    engine.transport_state = TransportState.STOPPED
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=engine,
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"])),
        config_path=None,
    )
    return app, engine


def test_get_transport():
    app, _engine = _make_app()
    client = TestClient(app)
    resp = client.get("/api/transport")
    assert resp.status_code == 200
    assert resp.json()["state"] == "stopped"


def test_put_transport_playing():
    app, engine = _make_app()
    client = TestClient(app)
    resp = client.put("/api/transport", json={"state": "playing"})
    assert resp.status_code == 200
    engine.set_transport_state.assert_called_once_with(TransportState.PLAYING)


def test_put_transport_invalid():
    app, _engine = _make_app()
    client = TestClient(app)
    resp = client.put("/api/transport", json={"state": "invalid_state"})
    assert resp.status_code == 422
