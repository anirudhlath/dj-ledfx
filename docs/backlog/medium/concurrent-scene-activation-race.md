# Guard concurrent scene activation/deactivation

**Summary:** The activate route's device-conflict check and PipelineManager's registration have multiple await suspension points; two concurrent activations of *conflicting* scenes can both pass the DB conflict check and leave both active. Same-scene double activation is now guarded by a re-check in `PipelineManager.activate_scene`, but the cross-scene TOCTOU remains.

**Context:** Found during code review of the multi-pipeline scene UI work (2026-06-11). The frontend re-apply pattern (deactivate→activate on placement edits of active scenes) increases concurrent traffic on these routes. Single asyncio loop, single-user UI — low probability, real consequence (two scenes driving the same device).

**Acceptance criteria:**
- A module-level `asyncio.Lock` (or equivalent) serializes the bodies of activate/deactivate routes, or the conflict check is re-validated inside `PipelineManager.activate_scene` after pipeline build.
- A test simulates interleaved activations of two conflicting scenes (e.g. asyncio.gather with a patched slow `_build_pipeline`) and asserts only one ends active.
