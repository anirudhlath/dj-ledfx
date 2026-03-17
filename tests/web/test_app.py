import pytest
from unittest.mock import MagicMock
from dj_ledfx.web.app import create_app


def _mock_deps():
    return {
        "beat_clock": MagicMock(),
        "effect_deck": MagicMock(),
        "effect_engine": MagicMock(),
        "device_manager": MagicMock(),
        "scheduler": MagicMock(),
        "preset_store": MagicMock(),
        "scene_model": None,
        "compositor": None,
        "config": MagicMock(web=MagicMock(cors_origins=["*"])),
        "config_path": None,
    }


def test_create_app_returns_fastapi():
    app = create_app(**_mock_deps())
    assert app.title == "dj-ledfx"


def test_create_app_has_api_routes():
    app = create_app(**_mock_deps())
    paths = [r.path for r in app.routes]
    assert any("/api" in str(p) for p in paths)
