"""F0: the rebuilt web app (web/dist) is served at /next, beside the old UI, until F11."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.web.conftest import static_client, write_dist

NEW_INDEX = "<!doctype html><title>next</title>"
OLD_INDEX = "<!doctype html><title>old</title>"
SECRET = "not for the web"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A checkout-like tree: web/dist (new), frontend/dist (old) and a file outside both."""
    (tmp_path / "secret.txt").write_text(SECRET)
    write_dist(tmp_path / "web" / "dist", NEW_INDEX)
    write_dist(tmp_path / "frontend" / "dist", OLD_INDEX)
    return tmp_path


def _client(tree: Path, next_dir: Path | None = None) -> TestClient:
    return static_client(tree / "frontend" / "dist", next_dir or tree / "web" / "dist")


# Review focus: /next without a trailing slash, and reloaded deep links, load the app.
@pytest.mark.parametrize(
    "path",
    [
        "/next",
        "/next/",
        "/next/live",
        "/next/looks/fireflies",
        "/next/lookz",
        # A NUL byte can't name a file, so it gets the app like any unknown path, not a 500.
        pytest.param("/next/%00", id="nul-byte"),
        # The cache rule follows the file served, not the path that reached it.
        pytest.param("/next/assets/..%2findex.html", id="index-reached-through-assets"),
    ],
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


# Unbuilt, the app's routes say how to build it; an asset is simply missing, as it is when built.
@pytest.mark.parametrize(
    ("path", "detail"),
    [("/next/live", "npm run build"), ("/next/assets/index-abc123.js", "Not found")],
)
def test_an_unbuilt_web_app_says_how_to_build_it(tree: Path, path: str, detail: str) -> None:
    response = _client(tree, next_dir=tree / "missing").get(path)
    assert response.status_code == 404
    assert detail in response.json()["detail"]
