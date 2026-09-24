"""F0: the rebuilt web app (web/dist) is served at /next, beside the old UI, until F11."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.web.app import create_app

NEW_INDEX = "<!doctype html><title>next</title>"
OLD_INDEX = "<!doctype html><title>old</title>"
SECRET = "not for the web"


def _dist(root: Path, index: str) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(index)
    (root / "assets" / "index-abc123.js").write_text("console.log('built')")
    (root / "favicon.svg").write_text("<svg/>")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A checkout-like tree: web/dist (new), frontend/dist (old) and a file outside both."""
    (tmp_path / "secret.txt").write_text(SECRET)
    _dist(tmp_path / "web" / "dist", NEW_INDEX)
    _dist(tmp_path / "frontend" / "dist", OLD_INDEX)
    return tmp_path


def _client(tree: Path, next_dir: Path | None = None) -> TestClient:
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
        web_static_dir=str(tree / "frontend" / "dist"),
        next_static_dir=next_dir or tree / "web" / "dist",
    )
    return TestClient(app)


# Review focus: /next without a trailing slash, and reloaded deep links, load the app.
@pytest.mark.parametrize(
    "path", ["/next", "/next/", "/next/live", "/next/looks/fireflies", "/next/lookz"]
)
def test_app_paths_get_the_new_index(tree: Path, path: str) -> None:
    response = _client(tree).get(path)
    assert response.status_code == 200
    assert response.text == NEW_INDEX
    assert response.headers["cache-control"] == "no-cache"


def test_built_assets_are_served_for_a_year(tree: Path) -> None:
    response = _client(tree).get("/next/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.text == "console.log('built')"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


# Review focus: a tab left open across a rebuild asks for an old hash. index.html with a 200
# would break it; a 404 lets the browser fail cleanly.
def test_a_missing_asset_is_a_404_not_the_index(tree: Path) -> None:
    response = _client(tree).get("/next/assets/index-old999.js")
    assert response.status_code == 404


def test_other_files_in_dist_are_served(tree: Path) -> None:
    response = _client(tree).get("/next/favicon.svg")
    assert response.status_code == 200
    assert response.text == "<svg/>"
    assert response.headers["cache-control"] == "no-cache"


# A NUL byte can't name a file. It gets the app, like any other unknown path, not a 500.
def test_a_nul_byte_gets_the_index(tree: Path) -> None:
    response = _client(tree).get("/next/%00")
    assert response.status_code == 200
    assert response.text == NEW_INDEX


# The cache rule follows the file served, not the path that reached it.
def test_the_index_reached_through_assets_is_not_cached(tree: Path) -> None:
    response = _client(tree).get("/next/assets/..%2findex.html")
    assert response.text == NEW_INDEX
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "path",
    [
        "/next/..%2f..%2fsecret.txt",
        "/next/%2e%2e/%2e%2e/secret.txt",
        "/next/assets/..%2f..%2f..%2fsecret.txt",
    ],
)
def test_next_paths_cannot_leave_dist(tree: Path, path: str) -> None:
    assert SECRET not in _client(tree).get(path).text


def test_the_old_ui_keeps_its_paths(tree: Path) -> None:
    client = _client(tree)
    assert client.get("/").text == OLD_INDEX
    assert client.get("/scene").text == OLD_INDEX
    assert client.get("/assets/index-abc123.js").status_code == 200


def test_an_unbuilt_web_app_says_how_to_build_it(tree: Path) -> None:
    response = _client(tree, next_dir=tree / "missing").get("/next/live")
    assert response.status_code == 404
    assert "npm run build" in response.json()["detail"]
