"""The web app's generated API types follow the backend's schema (web/src/api/generated/)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.web.conftest import static_client, write_dist

REPO = Path(__file__).resolve().parents[2]
COMMITTED = REPO / "web" / "src" / "api" / "generated" / "openapi.json"
FIX = "the API changed: run `cd web && npm run api:types` and commit web/src/api/generated/"


def dumped_schema() -> str:
    result = subprocess.run(
        [sys.executable, "scripts/dump_openapi.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_the_committed_schema_is_the_backends() -> None:
    assert COMMITTED.read_text(encoding="utf-8") == dumped_schema(), FIX


def test_the_old_ui_catch_all_stays_out_of_the_schema(tmp_path: Path) -> None:
    # A deployed server has the old UI's dist, so its catch-all route is registered there and
    # would make the served schema differ from the code's (npm run api:check -- --url).
    write_dist(tmp_path, "<html>old</html>")
    paths = static_client(tmp_path).get("/openapi.json").json()["paths"]
    assert "/{full_path}" not in paths
    assert "/api/running" in paths
