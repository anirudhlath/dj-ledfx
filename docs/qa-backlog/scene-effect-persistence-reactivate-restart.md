# Per-Scene Effect Survives Deactivate/Reactivate and App Restart

**Feature:** multi-pipeline scene management — per-scene effect persistence
**Priority:** critical
**Type:** regression

## Prerequisites
- App running with web UI (`uv run -m dj_ledfx --demo --web` is sufficient; real hardware better)
- At least one device discovered and placed in a DB scene (not Default)
- Scene is in `independent` effect mode

## Test Steps
1. On the Scene page, activate the scene ("Go" button in the Scenes panel).
2. On the Live page, select the scene's tab above the effect deck.
3. Switch the scene's effect to something other than Beat Pulse (e.g. a chase/rainbow effect).
4. Change 2-3 params to distinctly non-default values (note the exact values).
5. On the Scene page, deactivate the scene ("Stop"), then reactivate it ("Go").
6. Return to the Live page scene tab — verify effect name and all param values match step 4.
7. Leave the scene active. Stop the app (Ctrl+C) and restart it with the same command.
8. Verify the scene is auto-activated on startup (`load_active_scenes`) and the Live page scene tab shows the same effect and params again.
9. With transport playing, confirm devices/preview actually render the restored effect (not Beat Pulse).

## Expected Result
- After deactivate→reactivate: effect class AND all param values are restored exactly.
- After full app restart: same — scene comes back active with the persisted effect and params.
- The rendered output visibly matches the chosen effect (restoration is real, not just UI state).
- No warning log "Could not restore effect ... falling back to beat_pulse" unless the effect class was genuinely removed.

## Notes
- This was a real bug: `_build_deck_for_scene` always returned `EffectDeck(BeatPulse())` despite `scene_effect_state` rows being written. Now fixed via `create_effect(effect_row["effect_class"], **params)` — needs end-to-end confirmation.
- Params are persisted as canonical params (after `apply_update`), so values may be clamped/normalized — compare against what the UI showed after the edit, not the raw slider input.
- Shared-mode effect restore is explicitly out of scope (shared decks keep BeatPulse default on restart).
- Also check fallback path: manually corrupt `scene_effect_state.params` JSON in `state.db` and restart — scene should activate with Beat Pulse and a warning, not crash.
