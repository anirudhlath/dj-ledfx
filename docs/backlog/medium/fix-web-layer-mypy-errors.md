# Fix 26 pre-existing mypy errors in the web layer

**Summary:** `uv run mypy src/` reports 26 errors across 8 files (router_scene.py, router_config.py, web/app.py, presets, state_db, spatial/mapping.py, others). They predate the multi-pipeline UI branch and only surface when the `web` extra is installed (without fastapi present, mypy skips those modules), which is why the documented "mypy strict must pass" convention drifted.

**Context:** Discovered 2026-06-11 while gating the scene-management-ui branch ("no NEW errors" was used as the gate). Examples: `JSONResponse` returned where `dict[str, Any]` declared (router_config.py:145), type-declared assignment to non-self attribute (app.py:86), missing generic params.

**Acceptance criteria:**
- `uv run mypy src/` exits clean with the web extra installed.
- CI (or the documented gate) runs mypy with the web extra so the regression can't silently return.
- Remove the mypy-baseline note from CLAUDE.md Gotchas once clean.
