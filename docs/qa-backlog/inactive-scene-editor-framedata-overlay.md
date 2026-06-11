# Inactive Scene Editor Shows Default-Pipeline Frame Data (Known Cosmetic Oddity)

**Feature:** Scene page — LED preview on inactive scene layouts
**Priority:** medium
**Type:** functional

## Prerequisites
- App running with web UI, transport PLAYING (default pipeline rendering)
- An INACTIVE scene containing devices that are currently assigned to the default pipeline

## Test Steps
1. On the Scene page, select the inactive scene in the Scenes panel.
2. Observe the LED colors on the device meshes in the 3D viewport.
3. Activate the scene and set a distinct effect for it; observe the meshes again.
4. Deactivate the scene and re-observe.

## Expected Result
- Step 2: device meshes on the inactive scene's layout light up with LIVE frame data from whatever pipeline currently drives those devices (the default pipeline). This is EXPECTED, documented behavior — the WS binary frame channel is keyed by device name, not by scene, and `frameData` from `useDevices` is global.
- Step 3: once active, mesh colors switch to the scene's own effect.
- Step 4: after deactivation, meshes show default-pipeline colors again (not frozen on the scene effect's last frame).
- No crashes or warnings either way.

## Notes
- This is a known cosmetic oddity, accepted in the design: an inactive scene's editor is a layout editor, and the preview overlays whatever the devices are really showing right now. Do NOT file it as a rendering bug.
- If a device in the inactive scene belongs to ANOTHER active scene, the preview shows that scene's effect — also expected.
- Re-evaluate UX after hardware use: if this confuses real workflows, promote to a backlog ticket proposing a "preview off for inactive scenes" toggle.
