"""Skip all web tests when the optional 'web' extra is not installed, and share their helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi", reason="web extra not installed (uv sync --extra web)")

from fastapi.testclient import TestClient  # noqa: E402

from dj_ledfx.web.app import create_app  # noqa: E402


def mock_deps() -> dict[str, Any]:
    """create_app's required arguments, mocked, with no static directory configured."""
    return {
        "beat_clock": MagicMock(),
        "effect_deck": MagicMock(),
        "effect_engine": MagicMock(),
        "device_manager": MagicMock(),
        "scheduler": MagicMock(),
        "preset_store": MagicMock(),
        "scene_model": None,
        "compositor": None,
        "config": MagicMock(web=MagicMock(cors_origins=["*"], static_dir=None)),
        "config_path": None,
    }


def write_dist(root: Path, index: str) -> None:
    """A built dist at root: index.html, a hashed asset and a favicon."""
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(index)
    (root / "assets" / "index-abc123.js").write_text("console.log('built')")
    (root / "favicon.svg").write_text("<svg/>")


def static_client(web_static_dir: Path, next_static_dir: Path | None = None) -> TestClient:
    """The old UI served from web_static_dir, and /next from next_static_dir when given."""
    extra = {} if next_static_dir is None else {"next_static_dir": next_static_dir}
    return TestClient(create_app(**mock_deps(), web_static_dir=str(web_static_dir), **extra))
