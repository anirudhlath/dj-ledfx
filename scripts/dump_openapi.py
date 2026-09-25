"""Print the web API's OpenAPI schema, as web/src/api/generated/openapi.json holds it.

The web app's types are generated from this (cd web && npm run api:types). Nothing runs: the app
is built over stand-ins and only its schema is read, so no server or device is needed.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock

from dj_ledfx.web.app import create_app


def openapi_schema() -> dict[str, Any]:
    """The schema FastAPI serves at /openapi.json."""
    app = create_app(
        beat_clock=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"], static_dir=None)),
        config_path=None,
    )
    return app.openapi()


def schema_text(schema: dict[str, Any]) -> str:
    """The committed file's text: sorted keys, a two-space indent and one trailing newline."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    sys.stdout.write(schema_text(openapi_schema()))
