# Demo Mode Smoke Test: Full Scene Management Flow Without DJ Hardware

**Feature:** multi-pipeline scene management UI — demo mode
**Priority:** low
**Type:** e2e

## Prerequisites
- No DJ hardware required: `uv sync --extra web` then `uv run -m dj_ledfx --demo --web`
- Browser at the served web UI

## Test Steps
1. Press Play; verify simulated beats drive the beat indicator and the Global deck's preview.
2. Create a scene, add whatever devices are available (real LAN devices may still be discovered; OpenRGB optional), position them, activate.
3. Switch the scene's effect from the Live page tab, scrub params.
4. Edit a placement while active (re-apply cycle), deactivate, reactivate, delete the scene.
5. Restart the app with a scene left active; confirm it loads active with its effect.
6. Watch the terminal throughout for tracebacks, repeated warnings, or unhandled task exceptions.

## Expected Result
- Every step from the other scene-management QA cases works identically under `--demo`: BeatSimulator feeds all pipelines, scene decks animate in the 3D preview at 60fps.
- No errors caused specifically by the absence of Pro DJ Link packets.
- Clean shutdown on Ctrl+C (no hung tasks from pipeline teardown).

## Notes
- This is the regression safety-net case: run it after any backend pipeline change when hardware isn't on hand.
- If no devices are discoverable at all, scene creation still works but pipelines build with zero devices — activation of an empty scene should either succeed harmlessly or fail with a clear 409, not a 500; note which.
