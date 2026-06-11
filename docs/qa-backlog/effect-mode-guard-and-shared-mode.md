# Effect Mode Guard While Active + Shared-Mode Behavior

**Feature:** ScenesPanel — effect_mode select guard; shared-mode pipelines
**Priority:** medium
**Type:** functional

## Prerequisites
- App running with web UI, transport PLAYING
- Two scenes with devices placed (real or demo devices)

## Test Steps
1. Select an INACTIVE scene in the Scenes panel. Change "Effect mode" between Independent and Shared — verify both directions succeed and persist after page reload.
2. Activate the scene. Hover the effect-mode select.
3. Verify the select is disabled and a tooltip reads "Deactivate the scene to change effect mode".
4. Attempt the backstop: while the scene is active, send `PUT /api/scenes/{id}` with `{"effect_mode": "shared"}` via curl — verify a 409 and that the UI would toast the error.
5. Set BOTH scenes to `shared` mode (while inactive), then activate both.
6. On the Live page, change the effect/params on one shared scene's tab.
7. Observe devices in both shared scenes.

## Expected Result
- Steps 1-3: mode is editable only when inactive; disabled control + tooltip when active; changes persist.
- Step 4: API rejects effect_mode change on an active scene (409), UI state stays consistent after refresh.
- Steps 5-7: shared-mode scenes share ONE deck and ring buffer — changing the effect from either scene's tab changes output on devices in BOTH scenes simultaneously.

## Notes
- The "tooltip" is a native `title` attribute on the wrapping div — it appears after a hover delay; that's acceptable.
- Shared-deck effect state is NOT restored across app restart (out of scope by design) — shared scenes come back with the default Beat Pulse. Don't file as a bug.
- Switching a scene from shared back to independent (then activating) should give it its own deck again — verify params edited on the shared deck don't leak into the new independent deck.
