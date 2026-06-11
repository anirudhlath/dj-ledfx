# Live Page Per-Scene Effect Deck Tabs

**Feature:** Live page — scene effect tabs, slider responsiveness, presets
**Priority:** medium
**Type:** functional

## Prerequisites
- App running with web UI, transport PLAYING
- Two scenes active in `independent` mode plus the Default pipeline, with at least one device in each
- At least one saved preset (created from the Global deck)

## Test Steps
1. Open the Live page. Verify a tabs strip appears above the effect deck: "Global" plus one tab per active scene (and that the strip is absent when no scenes are active).
2. Switch between tabs. Verify each tab shows that scene's current effect and params, and the 3D preview switches to that scene's placements (Global tab shows the legacy in-memory scene, typically empty in DB-backed runs).
3. On a scene tab, scrub a slider rapidly back and forth for several seconds, then stop at a precise value.
4. Verify the knob stays where you released it — no snap-back to a stale server value after the last response lands.
5. On a scene tab, load a preset from the preset dropdown. Verify the deck switches to the preset's effect with its params and the scene's devices/preview render it.
6. Verify the Save (preset) button is ABSENT on scene tabs and PRESENT on the Global tab; saving from Global still works.
7. While viewing a scene tab, deactivate that scene from the Scene page in another tab/window. Return to the Live page.

## Expected Result
- Tab switching is instant and never shows another scene's params (the deck remounts per tab via `key={currentTab}`).
- Fast scrubbing feels live: out-of-order responses are dropped (`seqRef` supersede) so the final value wins, and intermediate PUT responses never yank the slider backwards.
- Preset load applies effect+params through `PUT /api/scenes/{id}/effect` (client-side) and the change is persisted (survives deactivate→reactivate).
- Step 7: the UI falls back to the "Global" tab automatically (the tab for the now-inactive scene disappears) without errors. Note: fallback depends on the scenes list refreshing — a page reload is an acceptable trigger; document actual behavior.

## Notes
- Param edits merge optimistically against `activeParamsRef`, so concurrent edits of two different sliders should both stick — try scrubbing two params alternately.
- Effect mutations are REST (not WS `set_effect`) by design; latency on slow networks shows up as param-apply lag, not snap-back.
- Backlog ticket `docs/backlog/low/per-scene-effect-param-memory.md` may cover known param-memory gaps — cross-check before filing new bugs.
