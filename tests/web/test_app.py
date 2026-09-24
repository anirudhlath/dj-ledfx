from dj_ledfx.web.app import create_app
from tests.web.conftest import mock_deps


def test_create_app_returns_fastapi():
    app = create_app(**mock_deps())
    assert app.title == "dj-ledfx"


def test_create_app_has_api_routes():
    app = create_app(**mock_deps())
    paths = [r.path for r in app.routes]
    assert any("/api" in str(p) for p in paths)
