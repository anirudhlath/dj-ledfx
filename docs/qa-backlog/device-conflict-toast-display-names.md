# Device Conflict on Activation Shows Display Names and Blocks Activation

**Feature:** scene activation — device conflict handling
**Priority:** high
**Type:** functional

## Prerequisites
- App running with web UI and at least one real device discovered whose `stable_id` differs from its display name (any LIFX or Govee device)
- Two DB scenes (A and B) that both contain that same device

## Test Steps
1. Activate Scene A — should succeed.
2. Attempt to activate Scene B.
3. Read the error toast text carefully.
4. Verify Scene B shows no "active" badge and `GET /api/scenes` reports `is_active: false` for it.
5. Verify Scene A continues rendering normally on the shared device (conflict attempt must not disturb the running pipeline).
6. Deactivate Scene A, then activate Scene B — should now succeed.
7. Click "Go" on an already-active scene quickly twice (double-click) — verify no error toast and no duplicate-activation 500.

## Expected Result
- Step 3: toast reads `Device conflict: <display name> already in another active scene` — the human-readable device name (e.g. "LIFX Beam"), NOT the raw MAC/stable_id.
- Step 4: second activation is fully rejected; DB `is_active` flag stays 0 for Scene B (failed activations don't corrupt DB state).
- Step 7: re-activating an active scene returns 200 `already_active` (idempotent), no error surfaced.

## Notes
- Name resolution happens client-side in `use-scenes.ts conflictMessage()` via `DeviceResponse.stable_id`; if the devices list hasn't loaded yet the toast falls back to raw stable_ids — acceptable fallback, but verify the normal path shows names.
- The previous behavior was HTTP 500 on double-activation; now `is_scene_active` short-circuits and remaining ValueErrors map to 409. Regression-check both paths.
- Backlog ticket `docs/backlog/medium/concurrent-scene-activation-race.md` tracks the concurrent-activation race; the double-click in step 7 is a light probe of it, not full coverage.
