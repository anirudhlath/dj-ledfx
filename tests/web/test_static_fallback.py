"""The old UI's SPA fallback must never serve a file from outside its dist directory."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.web.conftest import static_client, write_dist

INDEX = "<!doctype html><title>old</title>"
SECRET = "not for the web"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """frontend/dist with an index, a hashed asset and a favicon, and a secret beside it."""
    (tmp_path / "secret.txt").write_text(SECRET)
    dist = tmp_path / "frontend" / "dist"
    write_dist(dist, INDEX)
    return static_client(dist)


@pytest.mark.parametrize(
    "path",
    [
        "/..%2f..%2fsecret.txt",
        "/%2e%2e/%2e%2e/secret.txt",
        "/favicon.svg%2f..%2f..%2f..%2fsecret.txt",
        # A NUL byte can't name a file, so the path gets the app rather than a 500.
        pytest.param("/%00", id="nul-byte"),
    ],
)
def test_encoded_dot_segments_fall_back_to_the_app(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
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
