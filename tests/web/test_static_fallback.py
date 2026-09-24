"""The old UI's SPA fallback must never serve a file from outside its dist directory."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.web.app import create_app

INDEX = "<!doctype html><title>old</title>"
SECRET = "not for the web"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """frontend/dist with an index, a hashed asset and a favicon, and a secret beside it."""
    (tmp_path / "secret.txt").write_text(SECRET)
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets" / "index-abc123.js").write_text("console.log('built')")
    (dist / "favicon.svg").write_text("<svg/>")
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"], static_dir=None)),
        config_path=None,
        web_static_dir=str(dist),
    )
    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/..%2f..%2fsecret.txt",
        "/%2e%2e/%2e%2e/secret.txt",
        "/favicon.svg%2f..%2f..%2f..%2fsecret.txt",
    ],
)
def test_encoded_dot_segments_fall_back_to_the_app(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert SECRET not in response.text
    assert response.text == INDEX


def test_encoded_dot_segments_under_assets_are_not_found(client: TestClient) -> None:
    """/assets is Starlette's StaticFiles mount, which refuses paths that leave it."""
    response = client.get("/assets%2f..%2f..%2f..%2fsecret.txt")
    assert response.status_code == 404
    assert SECRET not in response.text


def test_files_inside_dist_are_still_served(client: TestClient) -> None:
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.get("/assets/index-abc123.js").text == "console.log('built')"


@pytest.mark.parametrize("path", ["/", "/scene", "/devices/abc"])
def test_app_routes_get_the_index(client: TestClient, path: str) -> None:
    assert client.get(path).text == INDEX
