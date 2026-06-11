# Scene Editor Full Flow: Create, Place, Activate, Edit While Active

**Feature:** Scene page — ScenesPanel + per-scene 3D editor + active-scene re-apply
**Priority:** high
**Type:** e2e

## Prerequisites
- App running with web UI and at least 2 devices discovered (real hardware preferred so re-apply is visible on lights)
- Transport PLAYING so devices render output

## Test Steps
1. On the Scene page, type a name in the "New scene name" input and press Enter (also try the "+" button).
2. Verify the scene appears in the list, is auto-selected, and a success toast shows.
3. Add 2 devices to the scene from the device list panel; verify they appear in the 3D viewport at origin.
4. Drag each device to a distinct position with the transform gizmo; verify positions persist after a page reload.
5. Activate the scene ("Go"). Verify the "active" badge appears and physical devices switch to this scene's effect.
6. While the scene is active, drag a device placement to a new position. Watch the physical lights during the drag/commit.
7. While active, drag a mapping handle (e.g. radial center/radius or linear axis) and verify the spatial pattern on the lights updates after commit.
8. Double-click the scene name, rename it, press Enter; verify rename persists and Escape cancels an in-progress rename.
9. Remove one device from the scene while active; verify that device falls back to the default pipeline.
10. Deactivate, then delete the scene; verify it disappears and selection returns to Default.

## Expected Result
- Each step completes with a toast (success or descriptive error) and no console errors.
- Steps 6-7: edits on an active scene trigger an automatic deactivate→activate re-apply; lights pick up the new placement/mapping within ~1-2 seconds. A brief blink/dropout during re-apply is acceptable; lights must NOT stay dark or stay on the old layout.
- Step 4: positions survive reload exactly (placements are DB-backed via `GET /api/scenes/{id}`).
- Mapping handle drags use optimistic updates — handles must not jump back during the API round-trip.

## Notes
- Re-apply is frontend-owned (`use-scene.ts reapply()`): it re-fetches scene detail, and only cycles deactivate→activate if `is_active`. If activation fails mid-cycle (e.g. a conflict appeared), the scene may end up deactivated — check the error toast and that the UI badge reflects reality after `refresh()`.
- The duplicate-commit guard on rename (Enter then blur) should produce exactly one PUT — watch the network tab.
- `mapping_params` per-scene editing is new API surface (`PUT /api/scenes/{id}` with `mapping_params`); verify radial center/radius round-trip for a DB scene, not just the legacy Default scene.
