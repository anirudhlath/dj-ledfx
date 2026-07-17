# Scene Switch Keeps 3D Viewport Mounted

**Feature:** Scene page — viewport continuity across scene selection
**Priority:** medium
**Type:** functional

## Prerequisites
- App running with web UI
- At least two scenes with different device placements, plus the Default scene

## Test Steps
1. On the Scene page, orbit/zoom the camera to a distinctly non-default angle.
2. Click a different scene row in the Scenes panel.
3. Observe the viewport during the switch.
4. Switch back and forth between Default and DB scenes several times quickly.
5. While a device is selected (gizmo visible), switch scenes; verify selection and mapping-handle selection are cleared and no gizmo orphan remains.

## Expected Result
- The WebGL canvas stays mounted: no white/black flash, no WebGL context loss, no "Loading scene..." full-page swap when a scene is already loaded (loading screen only appears on first load, per `loading && !scene` guard).
- Camera position/orientation is preserved across scene switches (no reset to the default angle).
- Placements swap to the newly selected scene's content; meshes from the previous scene disappear.
- Rapid switching produces no React key warnings or console errors (check devtools console).

## Notes
- A stale-response race is possible: `useScene` refetches on `sceneId` change without aborting the in-flight previous fetch — switch scenes very fast and confirm the displayed placements always match the selected row.
- Selecting a scene clears `selectedId`/`selectedHandle` in `handleSelectScene`; if a TransformControls gizmo survives the switch attached to a removed mesh, that's a bug (R3F crash risk).
