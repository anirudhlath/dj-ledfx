# M4 Modifiers and Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every look can use the layer modifiers (mask, mirror, transform) and the look modifiers (trails, downbeat flash, brightness cap, evening), and every start plays a transition (cut, fade, wipe, spread or dissolve) from what the zone's lights showed, the lights that run their own effect switching at its midpoint. The API takes and serves all of it.

**Architecture:** The look model parses, checks and writes back the modifiers, and clamps a saved transition's length rather than refusing it. Layer modifiers change where a field is drawn, never the effect: `zones/layer_view.py` turns a layer's mask into a weight for each LED, which `blend_into` takes as a per-LED opacity, and its mirror and transform into moved positions (`LedSet.moved()`, which keeps the zone's bounds). The runtime keeps each layer's view until its modifiers or the LEDs change, and masks by room and sub-zone read the outlines the map now puts in each zone's `Space`. Look modifiers are steps in `zones/look_modifiers.py` that the runtime runs on each new frame after its layers, in a fixed order, each making a new array; the brightness cap also lowers the brightness each firmware effect starts at. `home/sun.py` works out how far into the evening it is at the home's location, with astral, and the zone manager hands that to every runtime. For a transition, `zones/transition.py` gives each LED its place in the switch and its share of the new look. The new runtime renders the looks it replaces (its zone's previous runtime, and twins of the runtimes of the zones it takes lights from) and mixes them in LED by LED. A light that runs a firmware effect in either look follows the old look (`holder()`) until the frame at the midpoint, and the manager's new `run()` task applies its new look then. `POST /zones/{id}/start` plays its `transition`, or else the look's own; `RunningZone.transition` gains `durationS`, and the running channel pushes a zone as its transition starts, passes the midpoint and ends.

**Tech Stack:** Python 3.11+ (3.14 in the venv and the container), asyncio, numpy, FastAPI and Pydantic v2, loguru, pytest with pytest-asyncio, and one new dependency, astral 3.2 (Apache-2.0, pure Python). The web app's gate (Vitest, ESLint, `tsc -b`, the build, Playwright) runs in Tasks 3, 4, 9 and 12, after each API change. Context7 is unavailable, so external APIs were checked against current docs with WebFetch: astral 3.2's `astral.Observer(latitude, longitude)`; `astral.sun.dawn`, `sunrise`, `sunset` and `dusk(observer, date, tzinfo=...)`, `dawn` and `dusk` at the civil depression (6°) by default, each raising `ValueError` for a date on which the sun never gets there (polar day and night); `astral.sun.elevation(observer, dateandtime)`; and Pydantic v2's `Field(gt=..., ge=..., le=..., allow_inf_nan=False)` and discriminated unions (`Field(discriminator="kind")`), which FastAPI answers with 422.

**Spec:** `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: the M4 row in §2, §4.1, §4.3, §5.2, §5.3, §8, §9 and §10. API names and shapes come from `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`: §6.3 (`ZoneCard`'s transition state), §8.2 (the transition select), §8.5 (the look editor's modifiers), §11.1 and §12 (types §12.2, REST §12.3, WebSocket §12.4). Read both before starting.

**What exists.** What M4 starts from:

- Looks have carried `modifiers` (`LookModifiers`: trails, downbeat flash, brightness cap, evening) and a `transition` (a kind and a duration) since M1, in the model, in `state.db` and in the API. `validate_look` refuses any look modifier ("Look modifiers arrive in M4"), parsing refuses a layer's `mask`, `mirror` or `transform` ("Layer modifiers (…) arrive in M4"), and a streamed layer that picks lights is refused ("masks for streamed layers arrive in M4"). The contract's `Layer.mask`, `mirror` and `transform` are untyped objects, always null.
- Every start is a cut. `StartRequest.transition` is accepted and ignored ("M1 plays every transition as a cut"), and `RunningZone.state` lists `transition` beside the engine's four states, with `transition` always null.
- A transition's duration was only checked to be a number, so a saved look or a zone's saved assignment may hold one that no request should send, NaN included.
- A zone's `Space` carries its rooms, anchors, ceiling and centre, but not the rooms' outlines; `blend_into` takes one opacity for the whole layer; a `LedSet`'s positions are its placements'.
- There is no sun code, and no sun library in `uv.lock`. The home's location is the map's (`Home.location`: a name, `lat` and `lon`), seeded from `home.json` and changed with `PUT /api/home`.
- F1's mock plays one transition, in its `transition` scenario, as `{from, kind, progress}`.

**Execution:** `/executing-plans` in a new worktree, `~/code/.worktrees/dj-ledfx/m4-modifiers` on branch `feature/m4-modifiers-transitions`. Branch it from `origin/master` after the docs PR with this plan has merged; Before Task 1 sets it up.

F3, the web app's Live page, is planned and built at the same time and may merge first. Under `web/`, this plan changes the generated API types (Tasks 3, 4 and 9, each with its API change) and, in Task 9, `contract.ts` and the mock, which F3 may change too. Task 12 rebases over whatever has merged, settles any conflict there, makes F3's code follow what M4 serves, and runs every gate again.

**How to read the code.** A new file is given whole, in a `python` block after "Create". A change to an existing file is a unified diff, in a `diff` block, against the file as master at `98ecbee` and the earlier tasks leave it; apply the blocks in the order given. Save a block to a file and run `git apply` on it (`git apply /tmp/m4-step.diff`), or make the same edit by hand. If master has moved past `98ecbee` and a block no longer applies, make the edit by hand: its hunks say where. Generated files (`web/src/api/generated/*` and `uv.lock`) are never given; a command makes them. The test counts were measured on `98ecbee`, and a newer master may add to them.

---


## Global Constraints

Every task's requirements include these. Quotes are verbatim from the specs.

- M4 scope (engine spec §2): "Layer and look modifiers; cut, fade, wipe, spread, dissolve". It brings no looks of its own.
- §5.3, all of it:
  - "**Layer modifiers:** mask (height band, room, sub-zone, or distance from an anchor), mirror (across a plane), transform (translate, rotate or scale the field's space)."
  - "**Look modifiers:** trails (per-LED decay), downbeat flash, brightness cap (also caps firmware devices), evening (warmer and dimmer from an hour before sunset to the end of civil twilight, off again at sunrise)."
  - "**Transitions:** cut; fade; wipe (a plane sweeps across the zone); spread (outward from an anchor); dissolve (per-LED random threshold). Firmware devices switch at the transition's midpoint. During a transition the zone renders both looks, so both count against the frame budget."
- The evening's times are the owner's decision: from an hour before sunset to the end of civil twilight, and off again at sunrise. Sun times come from the home's location.
- Build nothing from M5 or later: no particles, whole-home scope, overlays, sun position input (`GET /inputs` serves no `sun` until M6), bedtime flow, signals, bindings or `fx` stream. `validate_look` keeps refusing particle layers and whole-home looks with the milestones that bring them.
- §4.1: "Colour stays float RGB through the whole layer stack and is clamped and converted once, at send." "Everything stays on the single asyncio event loop. Budget: under 5 ms per zone frame on one core."
- §4.3: "Assigning a look starts it at once (with the look's transition)". "Each running zone has a brightness (0–1) that scales its streamed frames, at send (the zone's ring holds its frames before brightness), and its firmware effects." "A running zone is in one of five states: running, transition, slow, crashed, or waiting".
- §5.2: "A firmware layer claims its devices; streamed layers skip them."
- §8: "A zone that keeps exceeding its 5 ms budget drops to a lower frame rate, so it cannot stall the shared event loop." "A bad or missing home map, or a bad look, never crashes the app. It starts with what it has and reports the problem."
- §9: "**Performance:** a benchmark test on this home's 412-LED map asserts each zone renders in under 5 ms. It is marked as a performance test and run locally." "**Each milestone** ends with a short checklist run on the real lights; preview-only mode allows a dry run first."
- §2: "Each milestone also extends backup and restore to the data it adds."
- §10: "Where this spec and the contract name the same thing differently, the contract's name wins."
- The contract (web spec §12.2–12.4):
  - "`interface LookModifiers { trailsS: number | null; downbeatFlash: boolean; brightnessCap: number | null; evening: boolean }`"
  - "`interface Transition { kind: 'cut' | 'fade' | 'wipe' | 'spread' | 'dissolve'; durationS: number }`"
  - `Layer`: "`mask?: Mask; mirror?: Mirror; transform?: Transform`". The contract never defines the three types (ruling 1).
  - `RunningZone`: "`state: 'running' | 'transition' | 'slow' | 'crashed' | 'waiting'`" and "`transition?: { from: string; kind: Transition['kind']; progress: number }`".
  - REST: "`POST   /zones/{id}/start             { lookId | look (draft), transition? } → RunningZone, with takeOvers[]`".
  - WebSocket: `running` pushes "on change", with "`RunningZone[]`, `Overlay[]`".
- The screens that will show it (built by F3 and F8, not here): §6.3, "**transition** (old name struck through → new name, progress bar with kind and %)"; §8.2, "transition select (Cut, Fade, Wipe, Spread, Dissolve + duration; default the look's own)"; §8.5, "Look modifiers (Trails with time, Downbeat flash, Brightness cap with %, Evening), Transition (segmented kind + duration slider)" and "Layer modifiers: Mask (height band, room, sub-zone, distance from an anchor), Mirror, Transform (offset, rotate, scale)".
- The home's location: tests use made-up coordinates, and nothing in code, tests, commits, the PR or this plan says where the home is.
- Design files (CLAUDE.md, "Web App Design"): never retype a look's name or description, an anchor, or any other design value, in code, docs or this plan. M4 adds no looks.
- The repo is public: no LAN addresses, MACs, light names, light model names or AI model names in code, tests, commits, the PR or this plan. Loopback, `0.0.0.0` and port numbers are fine.
- Old endpoints, frame protocol v1 and the old UI stay until F11. The old UI's look picker sends no transition, so it gets each look's own.
- Code style (CLAUDE.md): `uv` for everything (the new dependency goes in with `uv add`), `loguru` for logging, `mypy --strict`, render paths synchronous and lock-free, numpy on whole arrays in the render path (no loop over LEDs), a frame in a ring never changed after it's written, event bus callbacks non-blocking.
- Gates, per task before commit: `uv run ruff check .` clean and `uv run pytest -q` green; `uv run ruff format --check .` no findings and `uv run mypy src/` no worse than the baseline from Before Task 1 (16 errors when this plan was written). An error in a file the task touched is the task's to fix unless the baseline had it. During a task, run only its test files; run the full gate once, before the commit. The plan's code isn't guaranteed to be formatter-exact: run `uv run ruff format` and `uv run ruff check --fix` on the files the task touched before the gate, never on the whole tree. `uv run pytest -m perf -q` stays under the 5 ms per-zone budget: Tasks 4, 7 and 12 run it.
- Wherever M4 changes what the backend serves (Tasks 3, 4 and 9), that task regenerates the API types (`cd web && npm run api:types`), brings the mock and any pending type in `contract.ts` up to them, and runs the web gate: `npm run api:check`, `npm test`, `npm run lint`, `npx tsc -b`, `npm run build` and `npm run e2e`, in `web/`. Task 12 runs it again after the rebase. e2e serves on :4174 and :4175, so only one worktree can run it at a time: check `ss -ltn | grep -cE ':(4174|4175) '` first, and while it isn't `0`, wait (a Monitor on `until ! ss -ltn | grep -qE ':(4174|4175) '; do sleep 10; done`), never a foreground sleep.
- Live system: the deployed `dj-ledfx-app-1` and the lights are touched only in Task 10, each such step with the owner's yes. The deployed app holds TCP 8080 and UDP 50001 on this host, and 8081 belongs to another service: a branch run serves on `PORT=8098`, set once in Task 10.

## Spec Rulings

The specs disagree, or say nothing, in a few places. These are the rulings this plan builds on. Task 12 lists them in the PR.

1. **Modifier shapes.** The contract names `Mask`, `Mirror` and `Transform` without defining them. `Mask` is one of `{kind: "height", range: [low, high]}` (metres above the floor), `{kind: "room", room}` and `{kind: "sub-zone", subZone}` (ids from the map), and `{kind: "anchor", anchor, radius}` (an anchor id and metres). `Mirror` is `{axis: "x" | "y" | "z", at}`: a plane square to the axis, `at` metres along it, or through the zone's centre when `at` is null. `Transform` is `{offset: [x, y, z], rotateDeg, scale}`. The axes are the map's: x east, y south, z up. Every number is finite, a radius is above 0 and a scale is from 0.1 to 10 (`MIN_SCALE`, `MAX_SCALE`).
2. **Masks.** A mask weighs each LED from 0 to 1 by where it sits, and the layer blends at that weight times its opacity, LED by LED. A height band and an anchor's reach fade out over 0.1 m at their edges (`MASK_EDGE_M`); a room or a sub-zone is its floor outline, in or out. A room or sub-zone the map no longer has shows the layer nowhere; an anchor it doesn't have is the zone's middle, as it is for the effects. The weights follow the map: a moved light or an edited outline redraws them with the zone's LEDs.
3. **Mirror and transform** move where the effect looks, never the LEDs: each LED shows what the unmoved field has at its mirrored, then transformed, place. A mirror folds the high side onto the low, so the low side shows on both. A transform shifts the field by its offset, and turns it clockwise seen from above and grows it by its scale, both about the zone's centre. A moved LED set keeps the zone's bounds and normalisation, so an effect fitted to the zone moves with the field instead of stretching to fit it again, and a 1D effect on a strip runs along the zone's bounds, held at its ends.
4. **Firmware layers take no layer modifiers.** A firmware effect runs whole on the lights it picks, so a firmware layer with a mask, mirror or transform is refused with the reason (400). A streamed layer that picks lights is still refused, and the reason now points at masks.
5. **The order of the look modifiers.** After the layers, each new frame gets trails, then the downbeat flash, then the evening; then the copy of what the firmware lights show (drawn only while the live stream is watched, as before); then the brightness cap, over every LED. So a flash leaves a trail, the evening warms the flash too, and nothing passes the cap. Trails, the flash and the evening change streamed colours only: a light that runs a firmware effect shows the effect as the light runs it, and only the cap reaches it (ruling 9).
6. **Trails.** Each LED shows the brighter of the look's colour and its own last colour fading, channel by channel; a colour fades to 5% (e^-3, `TRAILS_FALL`) over `trailsS`, which is above 0 and at most 10 s (`MAX_TRAILS_S`). A frame rendered for an earlier moment than the last (the zone's horizon shrank) fades nothing. Trails start afresh when the look turns them off, when the zone's LEDs change and when the zone restarts.
7. **Downbeat flash.** The first beat of every bar flashes every streamed LED towards white, 0.8 of the way (`FLASH_LEVEL`), fading out over half a beat (`FLASH_BEATS`), quadratically. It follows the tempo clock's bars: the internal clock's when no DJ plays.
8. **Evening.** A look with `evening` on turns warmer, towards a warm white (`EVENING_TINT`), and dimmer, to 75% (`EVENING_LEVEL`), by the evening's amount from 0 to 1. The amount rises from an hour before sunset to civil dusk, the end of civil twilight; stays at 1 through the night; and falls from civil dawn to 0 at sunrise, each change eased. Where the sun stays within civil twilight all night, the middle of the night stands in for dusk and dawn; where it doesn't set for days the amount is 0, and where it doesn't rise, 1. With no home location it's 0, and the log says so once.
9. **The brightness cap** holds each LED at or below the cap (0–1), its hue kept: a colour whose brightest channel is over the cap is scaled down until that channel is at it, and the zone's brightness scales it at send as before. A light that runs a firmware effect starts it at the zone's brightness times the cap (`firmware_brightness`), so both kinds of light end up at most brightness × cap. A new cap starts the zone's firmware effects again (a new generation), and only when the look has any.
10. **Transition timing.** A transition runs for `durationS` from its first frame's time, which is the zone's horizon ahead of the start; `progress` is how far the newest frame has got, 0 to 1. A fade moves every LED together, eased. A wipe sweeps along the zone's longer side on the floor, west to east or north to south; a spread grows outward from the anchor nearest the zone's middle, or from the middle on a map without anchors; a dissolve gives each LED its own random moment, seeded by the new look's generation. Each LED changes over a soft edge, a quarter of the transition for a wipe or a spread and a tenth for a dissolve (`EDGES`), eased. A transition lasts at most 10 s (`MAX_TRANSITION_S`).
11. **What a transition plays from.** What the zone's lights showed: the zone's own running look, and the look of each zone it takes lights from. For those it renders a twin, a copy of that zone's runtime as it is (the same look, LEDs, seed and generation) that only the new zone renders, so the zone that lost the lights runs on undisturbed. A light takes the first of those looks that drove it with the same number of LEDs, at that look's own brightness; a light no look drove (idle), or that a crashed zone drove, fades in from black. `from` names the look that drove most of the zone's lights, and is "" when none did.
12. **Firmware lights.** A light that runs a firmware effect in the old look or in the new one keeps the old look whole until the frame at the midpoint: its old effect stays on it, not sent again, or the old look streams to it. Then it switches whole: the new effect starts, or the new look streams. A light that refuses the new effect then streams its copy, as at any start. A light no look drove starts the new look's effect at once.
13. **Interruptions.** A start on a zone whose transition is playing takes the mix on from where it is, with no jump, and the lights the older transition held go over to its look at once. At most three looks render: a start that would make a fourth ends the oldest look's part in the mix. A change to the zone's lights (the map, or a take-over by another zone) and a restart cut to the new look on the lights it keeps. A brightness change dims every look in the mix. Off and Stop all put every light back as before, and a midpoint that passes after them changes nothing. A light back online mid-transition gets the look it follows then. A replaced look that fails ends the transition with a warning ("cutting to" the new look), never the zone.
14. **Lengths and garbage.** A transition in a request (a start's, or a look's in `POST` and `PUT /looks` and in a preview) needs a known kind and a finite `durationS` from 0 to 10; anything else is refused with 422 and changes nothing. A look read back from `state.db` or from a restored backup is never refused for its transition: a duration that isn't finite or isn't above 0 is a cut, and one over 10 s plays for 10 s (Review Focus 1). Modifiers work the same way: 422 for what the contract's limits catch, and 400 with the reason for what only the model can check (a height range from high to low, a firmware layer with a mask).
15. **The running zone's transition.** `RunningZone.transition` is `{from, kind, progress, durationS}` while the state is `transition`, and null otherwise, with `progress` rounded to three places. The contract's shape has no length, so `durationS` is this plan's addition: the `running` channel pushes the zone as its transition starts, passes the midpoint and ends, not every frame, and a client moves the bar on by itself from `progress` and `durationS`.
16. **Which transition plays.** A start plays the transition it's given, or else the look's own. A zone resumed when the app starts plays none.
17. **The built-in looks keep their cuts.** `looks.json` gives no transitions, and §5.2's sample with a 2 s fade shows the format, so every built-in still comes in with a cut. A look saved from one can have any transition.
18. **Backups.** The modifiers and transitions live inside the looks and zone assignments that backups already carry, so M4 adds no table. Task 9's test pins the round trip.
19. **The home's location** is the map's (`Home.location`), read by the evening at most once a second. The seeded map's is the location the handoff assumed (engine spec §10, open question 2), not this home's, until the owner sets the real one with `PUT /api/home`. Taking it from Home Assistant, as that question says, waits for the milestone that connects Home Assistant. Task 10 asks the owner.
20. **The budget mid-transition.** `pytest -m perf` proves it on all of this home's seeded LEDs: the two heaviest looks with every modifier on, mid-transition for each kind but the cut (10 s transitions, 4 s of ticks), and three looks at once. Each test asserts a median tick under 5 ms and that the zone never dropped to a lower frame rate (`fps_actual >= 59`). A tick times the whole render, every look in the mix included, so a zone over its budget mid-transition drops its rate as §8 says (Task 7's `test_both_looks_count_against_the_frame_budget`).
21. **State order.** A zone's state is `crashed` before `waiting`, `waiting` before `transition`, and `transition` before `slow` and `running`.

## Review Focus

These are the five inputs the specs imply that are most likely to bite someone using this, most likely first. Each has a test in the task that owns the code.

1. **Saved data from before M4.** A saved look, or a zone's saved assignment, holds a transition no request can send now (NaN, negative, a minute long). It loads and resumes, clamped (a cut, or 10 s), and is never refused, so the app starts as it did. Tests: Task 1, `test_transition_durations_are_clamped_never_refused` and `test_saved_looks_with_odd_transition_durations_load_clamped`; Task 8, `test_an_assignment_saved_with_an_odd_transition_resumes`.
2. **A light that runs its own effect, mid-transition.** It keeps its old effect, not sent again, until the midpoint and then switches whole; a light the new look runs itself streams the old look until then; one that refuses the new effect at the midpoint streams its copy; one that comes back online mid-transition gets the look it follows. Tests: Task 7, `test_a_firmware_light_switches_whole_at_the_midpoint` and `test_a_light_the_new_look_runs_itself_streams_the_old_one_until_the_midpoint`; Task 8, `test_a_firmware_light_keeps_its_effect_until_the_midpoint`, `test_a_light_that_refuses_the_new_effect_at_the_midpoint_streams_a_copy` and `test_a_light_back_online_mid_transition_gets_the_look_it_follows`.
3. **Something else happens mid-transition.** Another start on the zone, a take-over of some of its lights, a map change, Off or Stop all. A start takes the mix on with no jump and at most three looks render; a take-over or a map change cuts to the new look on the lights the zone keeps; Off and Stop all put every light back, and the midpoint that comes after changes nothing. Tests: Task 7, `test_a_start_mid_transition_takes_the_mix_on_and_three_looks_at_most_render` and `test_new_lights_mid_transition_end_it`; Task 8, `test_off_mid_transition_puts_the_lights_back` and `test_a_take_over_of_a_zone_in_transition_cuts_it_on_the_lights_it_keeps`.
4. **Garbage modifiers and transitions** from a client, a script or a hand-edited look: NaN, infinite or out-of-range numbers, an unknown kind, a height band from high to low, a mask without its room, a firmware layer with a mask. Each is refused with the reason (422 or 400), and nothing is saved or started. Tests: Task 1, `test_layer_modifier_problems_are_refused` and `test_look_modifier_problems_are_refused`; Task 3, `test_garbage_layer_modifiers_are_refused_with_the_reason` and `test_a_firmware_layer_with_a_mask_is_refused`; Task 4, `test_garbage_look_modifiers_are_refused_with_the_reason`; Task 9, `test_a_garbage_transition_is_refused_and_nothing_starts`.
5. **The evening at odd places and times.** Sunsets after UTC midnight, either side of the date line, far north and south, midsummer nights with no civil dusk, polar day and night, and a home with no location. The amount stays from 0 to 1, moves without a jump, comes once a night, and is 0 through polar day and 1 through polar night; with no location it's 0 and the looks play as they are. Tests: Task 5, `test_the_evening_is_in_range_and_continuous_anywhere`, `test_every_day_has_one_evening`, `test_polar_day_has_no_evening_and_polar_night_is_all_evening`, `test_with_no_civil_dusk_the_evening_is_full_at_the_middle_of_the_night` and `test_evening_reads_the_homes_location_once_a_second`.

---

## File Structure

New backend modules (paths under `src/dj_ledfx/`):

| File | Responsibility |
|---|---|
| `zones/layer_view.py` | A layer's view of its zone's LEDs: `mask_weights()`, `mirrored()`, `transformed()`, `LayerView` and `layer_view()` |
| `zones/look_modifiers.py` | The look modifiers as steps on a frame: `Trails`, `flashed()`, `warmed()`, `capped()` and their constants |
| `home/sun.py` | The evening: `evening_amount(lat, lon, at)` from astral's sun times, and `Evening`, the amount now at the home's location, worked out at most once a second |
| `zones/transition.py` | The transitions' maths: `switch_order()` (each LED's place in a wipe, spread or dissolve), `new_share()` (each LED's share of the new look) and `EDGES` |

Modified: `looks/model.py`, `effects/{blend,ledset,strip_adapter}.py`, `home/map.py`, `zones/{runtime,manager,model}.py`, `web/{contract,router_zones}.py`, `main.py`, `pyproject.toml` and `uv.lock` (Task 5), `web/src/api/generated/*` (Tasks 3, 4 and 9), `web/src/api/{contract,contract.test}.ts` and `web/src/api/mocks/{mock-server,mock-server.test,scenarios,scenarios.test}.ts` (Task 9), `CLAUDE.md` and `README.md` (Task 11).

Shared test helpers:

- `tests/map_home.py`'s `leds_at()` gains `space=`, a whole `Space` with its rooms' outlines (Task 2).
- `tests/runtime_fakes.py` (new, Task 3): the zone runtime fakes `tests/zones/test_runtime.py` kept to itself until now, so the modifier and transition tests share them: `LIGHTS` (a tile, a bulb and a lamp), `FlatField`, `PlaceField` (each LED's colour is the place the effect sees it at), `register_fields()`, `field_layer()`, `place_layer()`, `glow_layer()`, `look_of()`, `placed_light()`, `runtime_of()`, `latest()` and `sent()`.
- `tests/zone_home.py`'s `build_home()` and `assemble()`, and `tests/zones/conftest.py`'s `make_home`, gain `evening=` (Task 5).
- `tests/zones/test_runtime_perf.py` gains `EVERY_LOOK_MODIFIER`, `with_every_modifier()`, `home_runtime()` and `tick_times()` (Task 4).

New test files: `tests/zones/test_layer_view.py` and `tests/zones/test_runtime_modifiers.py` (Task 3), `tests/zones/test_look_modifiers.py` (Task 4), `tests/home/test_sun.py` (Task 5), `tests/zones/test_transition.py` (Task 6), `tests/zones/test_runtime_transitions.py` (Task 7) and `tests/zones/test_manager_transitions.py` (Task 8).

---

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/m4-modifiers-transitions /home/anirudhlath/code/.worktrees/dj-ledfx/m4-modifiers origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/m4-modifiers
cd "$W"
test -f docs/superpowers/plans/2026-10-03-m4-modifiers-transitions.md && test -f docs/design/web-app/looks.json && echo "plan and design present"
test -d src/dj_ledfx/tempo && test -d web/src/stage && echo "M3 and F2 present"
grep -q 'Look modifiers arrive in M4' src/dj_ledfx/looks/model.py && echo "M4's refusals still here"
git log --oneline -5 origin/master
```

Expected: `plan and design present`, `M3 and F2 present` and `M4's refusals still here`. If one is missing, stop and tell the owner. The log shows whether F3 has merged; either is fine, since Task 12 rebases over it. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
(cd web && npm ci)
```

Without the `web` extra, the web tests skip silently and mypy reports dozens of extra errors. Tasks 3, 4 and 9 need the web app's packages to regenerate the API types and run the web gate.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tee /tmp/m4-baseline-mypy.txt | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm test 2>&1 | tail -3 && npx tsc -b && npm run lint && echo "web gate green")
ss -ltn | grep -cE ':(4174|4175) '
```

If the `ss` count isn't `0`, another worktree is running e2e: wait until both ports are free (Global Constraints), then:

```bash
(cd web && npx playwright install chromium && npm run e2e)
```

Write the six results down: the test count (1553 passed and 1 skipped on `98ecbee`), the format findings, mypy's error count (16), the perf run (18 tests), the web tests' count (534) and e2e's (60 passed and 20 skipped). Every gate compares with these. `ruff check` should be clean, and the web gate and e2e green. If any isn't, tell the owner before starting.

- [ ] **Step 4: Check the design files**

```bash
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256)
```

Expected: `looks.json: OK` and `home.json: OK`, among the others. A mismatch means someone hand-edited a design file: stop and tell the owner.

---


### Task 1: Modifiers and transitions in the look model

The look model learns the modifiers' shapes (ruling 1), reads and writes them, and refuses a bad one with the reason. A transition's length is clamped, never refused, so a look saved before M4 always loads (ruling 14, Review Focus 1). The engine can't draw a modifier yet, so `validate_look` keeps refusing them for now: layer modifiers until Task 3, look modifiers until Task 4.

**Files:**
- Modify: `src/dj_ledfx/looks/model.py`
- Test: `tests/looks/test_model.py`, `tests/looks/test_store.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (`looks.model`):
  - `MaskKind = Literal["height", "room", "sub-zone", "anchor"]`, `MirrorAxis = Literal["x", "y", "z"]`; `MAX_TRANSITION_S = 10.0`, `MAX_TRAILS_S = 10.0`, `MIN_SCALE = 0.1`, `MAX_SCALE = 10.0`.
  - Frozen dataclasses `HeightMask(low: float, high: float)`, `RoomMask(room: str)`, `SubZoneMask(sub_zone: str)` and `AnchorMask(anchor: str, radius: float)`, with `Mask = HeightMask | RoomMask | SubZoneMask | AnchorMask`; `Mirror(axis: MirrorAxis = "x", at: float | None = None)`; `Transform(offset: tuple[float, float, float] = (0.0, 0.0, 0.0), rotate_deg: float = 0.0, scale: float = 1.0)`.
  - `Layer` gains `mask: Mask | None = None`, `mirror: Mirror | None = None` and `transform: Transform | None = None`.
  - `look_from_dict()` reads the layer modifiers and the look modifiers, raising `LookError` with the reason for a bad one (trails above 0 and at most 10 s, a cap from 0 to 1, finite numbers), and clamps a transition's `durationS`: not finite or not above 0 is 0, over 10 is 10, and only a value that isn't a number is refused ("Transition duration must be a number"). `look_to_dict()` writes the layer modifiers in the contract's shapes, null where unset.
  - `validate_look()` refuses a layer with any modifier ("layer modifiers arrive in M4") as well as look modifiers, as before.

- [ ] **Step 1: Write the failing tests**

In `tests/looks/test_model.py`:

```diff
--- a/tests/looks/test_model.py
+++ b/tests/looks/test_model.py
@@ -14,10 +14,17 @@ from dj_ledfx.effects.params import EffectParam
 from dj_ledfx.effects.strip_adapter import StripAdapter
 from dj_ledfx.looks.model import (
     LIGHTS_SETTING,
+    MAX_TRANSITION_S,
+    AnchorMask,
+    HeightMask,
     Layer,
     Look,
     LookError,
     LookModifiers,
+    Mirror,
+    RoomMask,
+    SubZoneMask,
+    Transform,
     Transition,
     firmware_layers,
     look_from_dict,
@@ -138,7 +145,7 @@ def test_setting_schema_types() -> None:
         ({"needs": ["weather"]}, "input"),
         ({"layers": [_layer(type="particles", kind="fireflies")]}, "M5"),
         ({"layers": [_layer(settings={"beats_per_cycle": {"value": 2.0, "binding": {}}})]}, "M7"),
-        ({"layers": [_layer(mask={"kind": "height"})]}, "M4"),
+        ({"layers": [_layer(mask={"kind": "height", "range": [0.0, 1.0]})]}, "M4"),
         ({"layers": [_layer(settings={"beats_per_cycle": 2.0})]}, "value"),
         (
             {
@@ -345,3 +352,115 @@ def test_a_strip_layer_takes_its_projection_from_its_settings() -> None:
         )
     )
     assert isinstance(effect, StripAdapter) and effect.get_params()["beats_per_cycle"] == 2.0
+
+
+MASKS = [
+    ({"kind": "height", "range": [0.5, 1.5]}, HeightMask(0.5, 1.5)),
+    ({"kind": "room", "room": "west"}, RoomMask("west")),
+    ({"kind": "sub-zone", "subZone": "desk"}, SubZoneMask("desk")),
+    ({"kind": "anchor", "anchor": "sofa", "radius": 2.0}, AnchorMask("sofa", 2.0)),
+]
+
+
+@pytest.mark.parametrize(("written", "mask"), MASKS)
+def test_layer_modifiers_round_trip(written: dict[str, Any], mask: object) -> None:
+    mirror = {"axis": "y", "at": 2.5}
+    transform = {"offset": [1.0, 0.0, -0.5], "rotateDeg": 90.0, "scale": 2.0}
+    look = look_from_dict(_look(layers=[_layer(mask=written, mirror=mirror, transform=transform)]))
+    layer = look.layers[0]
+    assert layer.mask == mask
+    assert layer.mirror == Mirror("y", 2.5)
+    assert layer.transform == Transform((1.0, 0.0, -0.5), 90.0, 2.0)
+    out = look_to_dict(look)["layers"][0]
+    assert (out["mask"], out["mirror"], out["transform"]) == (written, mirror, transform)
+    assert look_from_dict(look_to_dict(look)) == look
+
+
+def test_a_layer_without_modifiers_writes_nulls() -> None:
+    out = look_to_dict(look_from_dict(_look()))["layers"][0]
+    assert (out["mask"], out["mirror"], out["transform"]) == (None, None, None)
+    defaults = look_from_dict(_look(layers=[_layer(mirror={}, transform={})])).layers[0]
+    assert (defaults.mirror, defaults.transform) == (Mirror(), Transform())
+
+
+@pytest.mark.parametrize(
+    ("modifier", "reason"),
+    [
+        ({"mask": {"kind": "outdoors"}}, "Unknown mask"),
+        ({"mask": "height"}, "must be an object"),
+        ({"mask": {"kind": "height", "range": [1.0]}}, "must be 2 numbers"),
+        ({"mask": {"kind": "height", "range": [2.0, 1.0]}}, "from low to high"),
+        ({"mask": {"kind": "height", "range": [0.0, float("nan")]}}, "finite"),
+        ({"mask": {"kind": "room", "room": ""}}, "needs an id"),
+        ({"mask": {"kind": "sub-zone"}}, "needs an id"),
+        ({"mask": {"kind": "anchor", "anchor": "sofa", "radius": 0.0}}, "above 0"),
+        ({"mask": {"kind": "anchor", "anchor": "sofa", "radius": float("inf")}}, "finite"),
+        ({"mask": {"kind": "anchor", "anchor": "sofa"}}, "must be a number"),
+        ({"mirror": {"axis": "w"}}, "Unknown mirror axis"),
+        ({"mirror": {"axis": "x", "at": float("nan")}}, "finite"),
+        ({"transform": {"offset": [1.0, 2.0]}}, "must be 3 numbers"),
+        ({"transform": {"scale": 0.0}}, "between 0.1 and 10"),
+        ({"transform": {"scale": 100.0}}, "between 0.1 and 10"),
+        ({"transform": {"rotateDeg": float("inf")}}, "finite"),
+        ({"transform": {"rotateDeg": True}}, "must be a number"),
+    ],
+)
+def test_layer_modifier_problems_are_refused(modifier: dict[str, Any], reason: str) -> None:
+    with pytest.raises(LookError, match=reason):
+        look_from_dict(_look(layers=[_layer(**modifier)]))
+
+
+def _modifiers(**changes: Any) -> dict[str, Any]:
+    return {
+        "trailsS": None,
+        "downbeatFlash": False,
+        "brightnessCap": None,
+        "evening": False,
+        **changes,
+    }
+
+
+def test_look_modifiers_are_read() -> None:
+    modifiers = _modifiers(trailsS=0.5, downbeatFlash=True, brightnessCap=0.6, evening=True)
+    look = look_from_dict(_look(modifiers=modifiers))
+    assert look.modifiers == LookModifiers(0.5, True, 0.6, True)
+    assert look_to_dict(look)["modifiers"] == modifiers
+
+
+@pytest.mark.parametrize(
+    ("changes", "reason"),
+    [
+        ({"trailsS": 0.0}, "longer than 0"),
+        ({"trailsS": -1.0}, "longer than 0"),
+        ({"trailsS": 11.0}, "at most 10"),
+        ({"trailsS": float("nan")}, "finite"),
+        ({"trailsS": "long"}, "must be a number"),
+        ({"brightnessCap": 1.5}, "between 0 and 1"),
+        ({"brightnessCap": -0.1}, "between 0 and 1"),
+        ({"brightnessCap": float("inf")}, "finite"),
+    ],
+)
+def test_look_modifier_problems_are_refused(changes: dict[str, Any], reason: str) -> None:
+    with pytest.raises(LookError, match=reason):
+        look_from_dict(_look(modifiers=_modifiers(**changes)))
+
+
+@pytest.mark.parametrize(
+    ("written", "read"),
+    [
+        (2.5, 2.5),
+        (0.0, 0.0),
+        (-1.0, 0.0),
+        (99.0, MAX_TRANSITION_S),
+        (float("nan"), 0.0),
+        (float("inf"), 0.0),
+    ],
+)
+def test_transition_durations_are_clamped_never_refused(written: float, read: float) -> None:
+    look = look_from_dict(_look(transition={"kind": "fade", "durationS": written}))
+    assert look.transition == Transition("fade", read)
+
+
+def test_a_transition_duration_that_is_not_a_number_is_refused() -> None:
+    with pytest.raises(LookError, match="Transition duration must be a number"):
+        look_from_dict(_look(transition={"kind": "fade", "durationS": "2"}))
```

In `tests/looks/test_store.py`:

```diff
--- a/tests/looks/test_store.py
+++ b/tests/looks/test_store.py
@@ -117,3 +117,20 @@ async def test_load_skips_corrupt_saved_look(db: StateDB) -> None:
     assert [look.id for look in store.looks()[BUILT_INS:]] == ["mine-good"]
     assert any("mine-json" in warning for warning in warnings)
     assert any("mine-kind" in w and "retired_effect" in w for w in warnings)
+
+
+# Review Focus 1: a look saved before M4 checked transitions loads, clamped, never dropped.
+async def test_saved_looks_with_odd_transition_durations_load_clamped(db: StateDB) -> None:
+    now = "2026-09-24T00:00:00+00:00"
+    rows = []
+    for look_id, seconds in [("mine-nan", "NaN"), ("mine-minus", "-3"), ("mine-long", "99")]:
+        body = look_to_dict(_mine())
+        body["transition"] = {"kind": "fade", "durationS": 0.0}
+        text = json.dumps(body).replace('"durationS": 0.0', f'"durationS": {seconds}')
+        rows.append((INSERT_LOOK, (look_id, text, now, now)))
+    await db.write_many(rows)
+
+    store = await _loaded(db)
+
+    durations = {look.id: look.transition.duration_s for look in store.looks()[BUILT_INS:]}
+    assert durations == {"mine-nan": 0.0, "mine-minus": 0.0, "mine-long": 10.0}
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/looks -q`
Expected: FAIL: a collection error, `ImportError: cannot import name 'MAX_TRANSITION_S' from 'dj_ledfx.looks.model'`.

- [ ] **Step 3: The modifiers in the model**

`src/dj_ledfx/looks/model.py`:

```diff
--- a/src/dj_ledfx/looks/model.py
+++ b/src/dj_ledfx/looks/model.py
@@ -6,6 +6,7 @@ the contract can describe is refused with the milestone that brings it.

 from __future__ import annotations

+import math
 from collections.abc import Mapping
 from dataclasses import dataclass, field
 from typing import Any, Literal, get_args
@@ -24,6 +25,13 @@ TransitionKind = Literal["cut", "fade", "wipe", "spread", "dissolve"]
 Category = Literal["ambient", "tempo", "audio", "home", "firmware"]
 Scope = Literal["any-zone", "whole-home"]
 InputKind = Literal["tempo", "music", "home-assistant", "sun"]
+MaskKind = Literal["height", "room", "sub-zone", "anchor"]
+MirrorAxis = Literal["x", "y", "z"]
+
+MAX_TRANSITION_S = 10.0  # the longest transition; a saved look's longer one plays this long
+MAX_TRAILS_S = 10.0  # the longest trail
+MIN_SCALE = 0.1  # a transform's scale, smallest and largest
+MAX_SCALE = 10.0


 class LookError(ValueError):
@@ -52,6 +60,58 @@ class LookModifiers:
     evening: bool = False


+@dataclass(frozen=True, slots=True)
+class HeightMask:
+    """The layer shows between two heights, metres above the floor."""
+
+    low: float
+    high: float
+
+
+@dataclass(frozen=True, slots=True)
+class RoomMask:
+    """The layer shows in one room of the home map, by id."""
+
+    room: str
+
+
+@dataclass(frozen=True, slots=True)
+class SubZoneMask:
+    """The layer shows in one sub-zone of the home map, by id."""
+
+    sub_zone: str
+
+
+@dataclass(frozen=True, slots=True)
+class AnchorMask:
+    """The layer shows within `radius` metres of an anchor."""
+
+    anchor: str
+    radius: float
+
+
+Mask = HeightMask | RoomMask | SubZoneMask | AnchorMask
+
+
+@dataclass(frozen=True, slots=True)
+class Mirror:
+    """The field reflected across a plane square to `axis`, `at` metres along it (None: the
+    zone's centre). The low side shows on both."""
+
+    axis: MirrorAxis = "x"
+    at: float | None = None
+
+
+@dataclass(frozen=True, slots=True)
+class Transform:
+    """The field's space moved: shifted by `offset` metres, turned `rotate_deg` clockwise
+    seen from above and grown `scale` times, both about the zone's centre."""
+
+    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
+    rotate_deg: float = 0.0
+    scale: float = 1.0
+
+
 @dataclass(frozen=True, slots=True)
 class Layer:
     id: str
@@ -65,6 +125,9 @@ class Layer:
     # The lights a firmware layer picks (None: all of them). The contract carries it as
     # the layer's `lights` setting (ruling 13).
     lights: tuple[Selector, ...] | None = None
+    mask: Mask | None = None  # the layer modifiers (spec §5.3)
+    mirror: Mirror | None = None
+    transform: Transform | None = None


 @dataclass(frozen=True, slots=True)
@@ -96,6 +159,104 @@ def _float(value: Any, what: str) -> float:
     return float(value)


+def _finite(value: Any, what: str) -> float:
+    number = _float(value, what)
+    if not math.isfinite(number):
+        raise LookError(f"{what} must be a finite number")
+    return number
+
+
+def _ident(value: Any, what: str) -> str:
+    if not isinstance(value, str) or not value.strip():
+        raise LookError(f"{what} needs an id")
+    return value.strip()
+
+
+def _numbers(value: Any, count: int, what: str) -> tuple[float, ...]:
+    if not isinstance(value, list | tuple) or len(value) != count:
+        raise LookError(f"{what} must be {count} numbers")
+    return tuple(_finite(item, what) for item in value)
+
+
+def _mask(layer: str, data: Any) -> Mask | None:
+    if data is None:
+        return None
+    if not isinstance(data, Mapping):
+        raise LookError(f"Layer '{layer}': a mask must be an object")
+    kind = _choice(data.get("kind"), get_args(MaskKind), "mask")
+    what = f"Layer '{layer}': the {kind} mask"
+    if kind == "height":
+        low, high = _numbers(data.get("range"), 2, f"{what}'s range")
+        if low >= high:
+            raise LookError(f"{what}'s range must run from low to high")
+        return HeightMask(low, high)
+    if kind == "room":
+        return RoomMask(_ident(data.get("room"), what))
+    if kind == "sub-zone":
+        return SubZoneMask(_ident(data.get("subZone"), what))
+    radius = _finite(data.get("radius"), f"{what}'s radius")
+    if radius <= 0.0:
+        raise LookError(f"{what}'s radius must be above 0")
+    return AnchorMask(_ident(data.get("anchor"), what), radius)
+
+
+def _mirror(layer: str, data: Any) -> Mirror | None:
+    if data is None:
+        return None
+    if not isinstance(data, Mapping):
+        raise LookError(f"Layer '{layer}': a mirror must be an object")
+    at = data.get("at")
+    return Mirror(
+        axis=_choice(data.get("axis", "x"), get_args(MirrorAxis), "mirror axis"),
+        at=None if at is None else _finite(at, f"Layer '{layer}': the mirror's place"),
+    )
+
+
+def _transform(layer: str, data: Any) -> Transform | None:
+    if data is None:
+        return None
+    if not isinstance(data, Mapping):
+        raise LookError(f"Layer '{layer}': a transform must be an object")
+    what = f"Layer '{layer}': the transform"
+    x, y, z = _numbers(data.get("offset", (0.0, 0.0, 0.0)), 3, f"{what}'s offset")
+    scale = _finite(data.get("scale", 1.0), f"{what}'s scale")
+    if not MIN_SCALE <= scale <= MAX_SCALE:
+        raise LookError(f"{what}'s scale must be between {MIN_SCALE:g} and {MAX_SCALE:g}")
+    return Transform(
+        offset=(x, y, z),
+        rotate_deg=_finite(data.get("rotateDeg", 0.0), f"{what}'s rotation"),
+        scale=scale,
+    )
+
+
+def _modifiers(data: Mapping[str, Any]) -> LookModifiers:
+    trails = data.get("trailsS")
+    if trails is not None:
+        trails = _finite(trails, "Trails")
+        if not 0.0 < trails <= MAX_TRAILS_S:
+            raise LookError(f"Trails must be longer than 0 s and at most {MAX_TRAILS_S:g} s")
+    cap = data.get("brightnessCap")
+    if cap is not None:
+        cap = _finite(cap, "The brightness cap")
+        if not 0.0 <= cap <= 1.0:
+            raise LookError("The brightness cap must be between 0 and 1")
+    return LookModifiers(
+        trails_s=trails,
+        downbeat_flash=bool(data.get("downbeatFlash", False)),
+        brightness_cap=cap,
+        evening=bool(data.get("evening", False)),
+    )
+
+
+def _duration(value: Any) -> float:
+    """A transition's length. A saved look may hold one no request could send now (from
+    before M4 checked them): out of range it's clamped, and not finite it's a cut."""
+    seconds = _float(value, "Transition duration")
+    if not math.isfinite(seconds) or seconds <= 0.0:
+        return 0.0
+    return min(seconds, MAX_TRANSITION_S)
+
+
 def _inputs(values: Any, what: str) -> tuple[Any, ...]:
     if not isinstance(values, list):
         raise LookError(f"'{what}' must be a list of inputs")
@@ -108,9 +269,6 @@ def _layer_from_dict(data: Mapping[str, Any], index: int) -> Layer:
     layer_type = _choice(data.get("type"), get_args(LayerType), "layer type")
     if layer_type == "particles":
         raise LookError("Particle layers arrive in M5")
-    for modifier in ("mask", "mirror", "transform"):
-        if data.get(modifier) is not None:
-            raise LookError(f"Layer modifiers ({modifier}) arrive in M4")
     raw_settings = data.get("settings") or {}
     if not isinstance(raw_settings, Mapping):
         raise LookError("Layer settings must be an object")
@@ -137,6 +295,9 @@ def _layer_from_dict(data: Mapping[str, Any], index: int) -> Layer:
         opacity=opacity,
         settings=settings,
         lights=lights,
+        mask=_mask(name, data.get("mask")),
+        mirror=_mirror(name, data.get("mirror")),
+        transform=_transform(name, data.get("transform")),
     )


@@ -177,15 +338,10 @@ def look_from_dict(data: Mapping[str, Any]) -> Look:
         needs=_inputs(data.get("needs", []), "needs"),
         uses=_inputs(data.get("uses", []), "uses"),
         layers=tuple(_layer_from_dict(layer, i) for i, layer in enumerate(layers)),
-        modifiers=LookModifiers(
-            trails_s=modifiers.get("trailsS"),
-            downbeat_flash=bool(modifiers.get("downbeatFlash", False)),
-            brightness_cap=modifiers.get("brightnessCap"),
-            evening=bool(modifiers.get("evening", False)),
-        ),
+        modifiers=_modifiers(modifiers),
         transition=Transition(
             kind=_choice(transition.get("kind", "cut"), get_args(TransitionKind), "transition"),
-            duration_s=_float(transition.get("durationS", 0.0), "Transition duration"),
+            duration_s=_duration(transition.get("durationS", 0.0)),
         ),
         derived_from=str(data["derivedFrom"]) if data.get("derivedFrom") else None,
     )
@@ -245,6 +401,35 @@ def setting_schema(kind: str) -> list[dict[str, Any]]:
     return entries


+def _mask_to_dict(mask: Mask | None) -> dict[str, Any] | None:
+    match mask:
+        case HeightMask(low, high):
+            return {"kind": "height", "range": [low, high]}
+        case RoomMask(room):
+            return {"kind": "room", "room": room}
+        case SubZoneMask(sub_zone):
+            return {"kind": "sub-zone", "subZone": sub_zone}
+        case AnchorMask(anchor, radius):
+            return {"kind": "anchor", "anchor": anchor, "radius": radius}
+    return None
+
+
+def _modifiers_to_dict(layer: Layer) -> dict[str, Any]:
+    """A layer's mask, mirror and transform in the contract's shapes, None where unset."""
+    mirror, transform = layer.mirror, layer.transform
+    return {
+        "mask": _mask_to_dict(layer.mask),
+        "mirror": None if mirror is None else {"axis": mirror.axis, "at": mirror.at},
+        "transform": None
+        if transform is None
+        else {
+            "offset": list(transform.offset),
+            "rotateDeg": transform.rotate_deg,
+            "scale": transform.scale,
+        },
+    }
+
+
 def _layer_to_dict(layer: Layer, *, for_storage: bool) -> dict[str, Any]:
     data: dict[str, Any] = {
         "id": layer.id,
@@ -255,9 +440,7 @@ def _layer_to_dict(layer: Layer, *, for_storage: bool) -> dict[str, Any]:
         "blend": layer.blend,
         "opacity": layer.opacity,
         "settings": {key: {"value": value} for key, value in layer.settings.items()},
-        "mask": None,
-        "mirror": None,
-        "transform": None,
+        **_modifiers_to_dict(layer),
     }
     if layer.lights is not None:
         data["settings"][LIGHTS_SETTING] = {"value": [s.text for s in layer.lights]}
@@ -346,6 +529,8 @@ def validate_look(look: Look) -> None:
         raise LookError("Look modifiers arrive in M4")
     for layer in look.layers:
         make_effect(layer)
+        if (layer.mask, layer.mirror, layer.transform) != (None, None, None):
+            raise LookError(f"Layer '{layer.name}': layer modifiers arrive in M4")
         if layer.type != "firmware" and layer.lights is not None:
             raise LookError(
                 f"Layer '{layer.name}': only a firmware layer picks its lights; "
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/looks -q`
Expected: PASS (112 tests).

- [ ] **Step 5: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/looks/model.py tests/looks
uv run ruff check --fix src/dj_ledfx/looks/model.py tests/looks
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/looks/model.py tests/looks
git commit -m "feat(looks): layer and look modifiers in the look model, transitions clamped"
```

---


### Task 2: Moved LEDs, per-LED opacity and the rooms' outlines

The pieces under the layer modifiers (rulings 2 and 3). `LedSet.moved()` gives the same LEDs at other positions, keeping the zone's bounds and normalisation, for a mirror or a transform to hand an effect. `blend_into` takes an opacity for each LED, for a mask. Each zone's `Space` carries the rooms' and sub-zones' floor outlines, for a room or sub-zone mask, and two spaces whose outlines differ are different spaces, so an edited outline redraws a zone. A strip effect's linear projection runs along the set's bounds, so a moved set moves the strip.

**Files:**
- Modify: `src/dj_ledfx/effects/blend.py`, `src/dj_ledfx/effects/ledset.py`, `src/dj_ledfx/effects/strip_adapter.py`, `src/dj_ledfx/home/map.py`
- Test: `tests/map_home.py`, `tests/effects/test_blend.py`, `tests/effects/test_ledset.py`, `tests/effects/test_effect_kinds.py`, `tests/home/test_map.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `effects.blend.blend_into(base: FloatRGB, top: FloatRGB, mode: str, opacity: float | NDArray[np.float32]) -> None`: an opacity of shape (N, 1) weighs each LED.
  - `effects.ledset`: `Outline = tuple[tuple[float, float], ...]`; `Space.room_outlines` and `Space.sub_zone_outlines: Mapping[str, Outline]` (empty by default, compared by value); `LedSet.frame: tuple[NDArray[np.float32], NDArray[np.float32]] | None = None`, the bounds a moved set keeps; `LedSet.moved(pos: NDArray[np.float32]) -> LedSet`; `LedSet.bounds` is `frame` when it's set.
  - `home.map.space_of(home)` fills both outline maps from the home's rooms and sub-zones.
  - `StripAdapter`'s linear projection runs along the set's bounds, clipped to 0..1.
  - Test helper: `tests/map_home.py`'s `leds_at(points, ..., space: Space | None = None)`; a space given whole replaces the ceiling and anchor arguments.

- [ ] **Step 1: Write the failing tests**

In `tests/map_home.py`, the test helper:

```diff
--- a/tests/map_home.py
+++ b/tests/map_home.py
@@ -135,9 +135,14 @@ def leds_at(
     ceiling: float | None = 3.0,
     anchors: Mapping[str, Sequence[float]] | None = None,
     anchor_points: Mapping[str, Sequence[Sequence[float]]] | None = None,
+    space: Space | None = None,
 ) -> LedSet:
     """One light's LEDs at these map positions, in a zone with this ceiling and anchors;
-    anchor_points gives an anchor more than one point (the speaker pair has two)."""
+    anchor_points gives an anchor more than one point (the speaker pair has two). A space
+    given whole (space_of(tiny_home()), with its rooms' outlines) replaces those three."""
+    placed = PlacedLeds.from_positions(np.asarray(points, dtype=np.float64).reshape(-1, 3))
+    if space is not None:
+        return build_ledset([LedSource("light", len(points), placed=placed)], space)
     space = Space(
         anchors=MappingProxyType(
             {name: np.asarray(p, dtype=np.float32) for name, p in (anchors or {}).items()}
@@ -150,7 +155,6 @@ def leds_at(
         ),
         ceiling=ceiling,
     )
-    placed = PlacedLeds.from_positions(np.asarray(points, dtype=np.float64).reshape(-1, 3))
     return build_ledset([LedSource("light", len(points), placed=placed)], space)


```

In `tests/effects/test_blend.py`:

```diff
--- a/tests/effects/test_blend.py
+++ b/tests/effects/test_blend.py
@@ -32,3 +32,14 @@ def test_each_blend_mode(mode: str, opacity: float, expected: tuple[float, ...])
 def test_an_unknown_blend_mode_is_refused() -> None:
     with pytest.raises(ValueError, match="dodge"):
         blend_into(np.zeros((1, 3), np.float32), np.zeros((1, 3), np.float32), "dodge", 1.0)
+
+
+@pytest.mark.parametrize(("mode", "expected"), [("normal", 0.5), ("add", 0.5)])
+def test_each_led_can_have_its_own_opacity(mode: str, expected: float) -> None:
+    base = np.zeros((3, 3), dtype=np.float32)
+    weights = np.array([[0.0], [0.5], [1.0]], dtype=np.float32)
+
+    blend_into(base, np.ones((3, 3), dtype=np.float32), mode, weights)
+
+    assert base.dtype == np.float32
+    assert np.allclose(base[:, 0], [0.0, expected, 1.0])
```

In `tests/effects/test_ledset.py`:

```diff
--- a/tests/effects/test_ledset.py
+++ b/tests/effects/test_ledset.py
@@ -171,3 +171,26 @@ def test_placed_leds_compare_by_value() -> None:
     assert PlacedLeds.from_positions(points) == same
     assert hash(PlacedLeds.from_positions(points)) == hash(same)
     assert PlacedLeds.from_positions(points) != PlacedLeds.from_positions(points * 2)
+
+
+def test_a_moved_set_keeps_its_bounds_and_normalisation() -> None:
+    leds = build_ledset([LedSource("a", 2, placed=_placed((0.0, 0.0, 0.0), (4.0, 2.0, 1.0)))])
+    shifted = leds.pos + np.float32(1.0)
+
+    moved = leds.moved(shifted)
+
+    assert np.allclose(moved.pos, shifted)
+    assert all(np.allclose(m, b) for m, b in zip(moved.bounds, leds.bounds, strict=True))
+    assert np.allclose(moved.centre, leds.centre)
+    assert np.allclose(moved.npos, [[0.25, 0.5, 1.0], [1.25, 1.5, 2.0]])  # past the bounds
+    assert moved.slices == leds.slices and moved.space is leds.space
+    assert leds.frame is None and np.allclose(leds.bounds[1], [4.0, 2.0, 1.0])  # unchanged
+
+
+def test_spaces_differ_when_an_outline_changes() -> None:
+    west = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0))
+    space = Space(rooms=("west",), room_outlines=MappingProxyType({"west": west}))
+    same = Space(rooms=("west",), room_outlines=MappingProxyType({"west": west}))
+    assert space == same
+    assert space != Space(rooms=("west",), room_outlines=MappingProxyType({"west": west[:2]}))
+    assert space != Space(rooms=("west",), sub_zone_outlines=MappingProxyType({"desk": west}))
```

In `tests/effects/test_effect_kinds.py`:

```diff
--- a/tests/effects/test_effect_kinds.py
+++ b/tests/effects/test_effect_kinds.py
@@ -167,6 +167,18 @@ def test_leds_spanning_under_5_cm_along_the_projection_play_in_led_order(
     assert np.allclose(adapter.render(render_ctx(), leds_at(points, ceiling=None))[:, 0], RAMP)


+def test_a_moved_set_moves_the_strip_along_the_zone() -> None:
+    leds = leds_at([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
+    adapter = StripAdapter(_Ramp())
+    assert np.allclose(adapter.render(render_ctx(), leds)[:, 0], RAMP)
+
+    # A layer's transform moves the field 1 m east: each LED sees the strip a metre west of
+    # it, and the LED past the west end takes the strip's first sample.
+    moved = leds.moved(leds.pos - np.array([1.0, 0.0, 0.0], dtype=np.float32))
+
+    assert np.allclose(adapter.render(render_ctx(), moved)[:, 0], RAMP[[0, 0, 1, 2]])
+
+
 def test_strip_adapter_forwards_parameters() -> None:
     inner = _Ramp()
     adapter = StripAdapter(inner)
```

In `tests/home/test_map.py`:

```diff
--- a/tests/home/test_map.py
+++ b/tests/home/test_map.py
@@ -7,10 +7,13 @@ import numpy as np
 import pytest
 from conftest import KEYBOARD_AND_MOUSE, SERVER, FakeLight, pc_lights
 from map_home import (
+    DESK,
     DESK_CORNER,
+    EAST,
     ROUND_MATRIX,
     SMALL_MATRIX,
     UPRIGHT_LAMP,
+    WEST,
     devices_of,
     open_map,
     tiny_home,
@@ -131,6 +134,20 @@ async def test_the_space_has_the_anchors_rooms_ceiling_and_centre(db: StateDB) -
     assert (space.rooms, space.ceiling, space.centre) == (("west", "east"), 3.0, (4.0, 2.0, 1.0))


+async def test_the_space_has_the_rooms_and_sub_zones_outlines(db: StateDB) -> None:
+    home_map = await _map(db, [])
+    space = home_map.space()
+    assert dict(space.room_outlines) == {"west": WEST, "east": EAST}
+    assert dict(space.sub_zone_outlines) == {"desk": DESK}
+
+    nook = ((0.0, 0.0), (1.5, 0.0), (1.5, 1.0))
+    await home_map.update_sub_zone("desk", polygon=nook)
+
+    moved = home_map.space()
+    assert moved.sub_zone_outlines["desk"] == nook
+    assert moved != space  # a running zone redraws its masks (zone manager's _follow)
+
+
 async def test_anchors_are_added_changed_and_deleted(db: StateDB) -> None:
     home_map = await _map(db, [])

```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects tests/home/test_map.py -q`
Expected: FAIL: 4 failed, 278 passed, with `AttributeError: 'LedSet' object has no attribute 'moved'` twice, `TypeError: Space.__init__() got an unexpected keyword argument 'room_outlines'` and `AttributeError: 'Space' object has no attribute 'room_outlines'`. The per-LED opacity tests pass already, because numpy broadcasts an (N, 1) opacity; Step 3 puts it in `blend_into`'s signature, for mypy.

- [ ] **Step 3: Moved sets, outlines and per-LED opacity**

`src/dj_ledfx/effects/blend.py`:

```diff
--- a/src/dj_ledfx/effects/blend.py
+++ b/src/dj_ledfx/effects/blend.py
@@ -8,14 +8,19 @@ from typing import TYPE_CHECKING
 import numpy as np

 if TYPE_CHECKING:
+    from numpy.typing import NDArray
+
     from dj_ledfx.types import FloatRGB

 BLEND_MODES = ("normal", "add", "screen", "multiply", "max")


-def blend_into(base: FloatRGB, top: FloatRGB, mode: str, opacity: float) -> None:
-    """Composite `top` onto `base`, in place, at `opacity` (0..1)."""
-    weight = np.float32(opacity)
+def blend_into(
+    base: FloatRGB, top: FloatRGB, mode: str, opacity: float | NDArray[np.float32]
+) -> None:
+    """Composite `top` onto `base`, in place, at `opacity` (0..1): one for every LED, or
+    each LED its own, shape (N, 1) (a layer's mask)."""
+    weight = np.float32(opacity) if isinstance(opacity, float | int) else opacity
     if mode == "add":
         base += top * weight
         return
```

`src/dj_ledfx/effects/ledset.py`:

```diff
--- a/src/dj_ledfx/effects/ledset.py
+++ b/src/dj_ledfx/effects/ledset.py
@@ -11,7 +11,7 @@ the anchors, rooms and ceiling its effects can ask about.
 from __future__ import annotations

 from collections.abc import Collection, Mapping, Sequence
-from dataclasses import dataclass, field
+from dataclasses import dataclass, field, replace
 from functools import cached_property
 from types import MappingProxyType

@@ -30,12 +30,17 @@ DEVICE_GAP_M = 0.5
 NO_ROOM = -1

 Vec3 = tuple[float, float, float]
+Outline = tuple[tuple[float, float], ...]  # a room's or sub-zone's floor polygon, x/y metres


 def _no_points() -> Mapping[str, NDArray[np.float32]]:
     return MappingProxyType({})


+def _no_outlines() -> Mapping[str, Outline]:
+    return MappingProxyType({})
+
+
 def _same_points(
     one: Mapping[str, NDArray[np.float32]], other: Mapping[str, NDArray[np.float32]]
 ) -> bool:
@@ -95,7 +100,8 @@ class Space:
     anchors: each anchor's position, (3,). anchor_points: every point of each anchor,
     (k, 3), so the speaker pair has two. rooms: room ids, indexed by LedSet.room.
     ceiling: metres, None without a map. centre: where unplaced lights gather when
-    none of the zone's lights is placed.
+    none of the zone's lights is placed. room_outlines and sub_zone_outlines: each room's
+    and sub-zone's floor polygon by id, for a layer's mask.
     """

     anchors: Mapping[str, NDArray[np.float32]] = field(default_factory=_no_points)
@@ -103,6 +109,8 @@ class Space:
     rooms: tuple[str, ...] = ()
     ceiling: float | None = None
     centre: Vec3 | None = None
+    room_outlines: Mapping[str, Outline] = field(default_factory=_no_outlines)
+    sub_zone_outlines: Mapping[str, Outline] = field(default_factory=_no_outlines)

     # By value, so a map edit that leaves the geometry as it was (a rename, a light moved
     # elsewhere) leaves the running zones as they are.
@@ -115,6 +123,8 @@ class Space:
             and self.centre == other.centre
             and _same_points(self.anchors, other.anchors)
             and _same_points(self.anchor_points, other.anchor_points)
+            and dict(self.room_outlines) == dict(other.room_outlines)
+            and dict(self.sub_zone_outlines) == dict(other.sub_zone_outlines)
         )

     def __hash__(self) -> int:
@@ -146,6 +156,8 @@ class LedSet:
     device: NDArray[np.int32]  # (N,) index into `slices`
     slices: tuple[DeviceSlice, ...]
     space: Space = NO_SPACE
+    # The bounds a moved set keeps (moved()); None: the LEDs' own.
+    frame: tuple[NDArray[np.float32], NDArray[np.float32]] | None = None

     @property
     def count(self) -> int:
@@ -157,12 +169,26 @@ class LedSet:

     @cached_property
     def bounds(self) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
-        """The LEDs' lowest and highest corner; the origin for no LEDs."""
+        """The LEDs' lowest and highest corner (a moved set's are the set's it was moved
+        from); the origin for no LEDs."""
+        if self.frame is not None:
+            return self.frame
         if self.count == 0:
             origin = np.zeros(3, dtype=np.float32)
             return origin, origin
         return self.pos.min(axis=0), self.pos.max(axis=0)

+    def moved(self, pos: NDArray[np.float32]) -> LedSet:
+        """These LEDs at other positions, as a layer's mirror or transform sees them. The
+        bounds and the normalisation stay this set's, so an effect that fits itself to the
+        zone moves with the positions rather than stretching to fit them again."""
+        low, high = self.bounds
+        points = np.asarray(pos, dtype=np.float64)
+        npos = _normalise(points, low.astype(np.float64), high.astype(np.float64))
+        return replace(
+            self, pos=points.astype(np.float32), npos=npos.astype(np.float32), frame=(low, high)
+        )
+
     @cached_property
     def centre(self) -> NDArray[np.float32]:
         """The middle of the LEDs' bounds."""
```

`src/dj_ledfx/effects/strip_adapter.py`:

```diff
--- a/src/dj_ledfx/effects/strip_adapter.py
+++ b/src/dj_ledfx/effects/strip_adapter.py
@@ -92,11 +92,15 @@ class StripAdapter(FieldEffect, register=False):
             centre = anchor_or_centre(leds, self._projection["centre"]).astype(np.float64)
             along = np.linalg.norm(positions - centre, axis=1)
             low = 0.0
+            span = float(along.max())
         else:
-            along = positions @ np.asarray(AXES[self._projection["axis"]], dtype=np.float64)
-            low = float(along.min())
-        span = float(along.max()) - low
+            # Along the zone's bounds, so a layer's mirror or transform moves the strip (a
+            # moved set keeps the bounds it was moved from; LedSet.moved).
+            axis = np.asarray(AXES[self._projection["axis"]], dtype=np.float64)
+            lowest, highest = (float(corner.astype(np.float64) @ axis) for corner in leds.bounds)
+            along = positions @ axis
+            low, span = lowest, highest - lowest
         if span < MIN_SPAN_M:
             return None
-        place: NDArray[np.float64] = (along - low) / span
+        place: NDArray[np.float64] = np.clip((along - low) / span, 0.0, 1.0)
         return place
```

`src/dj_ledfx/home/map.py`:

```diff
--- a/src/dj_ledfx/home/map.py
+++ b/src/dj_ledfx/home/map.py
@@ -91,7 +91,8 @@ def _checked(home: Home) -> Home:


 def space_of(home: Home) -> Space:
-    """What a zone's effects know of the map: anchors, rooms, ceiling and the centre."""
+    """What a zone's effects know of the map: anchors, rooms, ceiling, the centre, and the
+    rooms' and sub-zones' outlines."""
     anchors = {a.id: np.asarray(a.position, dtype=np.float32) for a in home.anchors}
     points = {
         a.id: np.asarray(a.points or (a.position,), dtype=np.float32).reshape(-1, 3)
@@ -105,6 +106,8 @@ def space_of(home: Home) -> Space:
         rooms=tuple(room.id for room in home.rooms),
         ceiling=home.ceiling,
         centre=((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, GUESS_HEIGHT_M),
+        room_outlines=MappingProxyType({room.id: room.polygon for room in home.rooms}),
+        sub_zone_outlines=MappingProxyType({sub.id: sub.polygon for sub in home.sub_zones}),
     )


```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/effects tests/home/test_map.py -q`
Expected: PASS (282 tests, and the ripples perf test deselected).

- [ ] **Step 5: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/effects src/dj_ledfx/home/map.py tests/map_home.py tests/effects tests/home/test_map.py
uv run ruff check --fix src/dj_ledfx/effects src/dj_ledfx/home/map.py tests/map_home.py tests/effects tests/home/test_map.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/effects src/dj_ledfx/home/map.py tests/map_home.py tests/effects tests/home/test_map.py
git commit -m "feat(effects): moved LED sets, per-LED opacity, and the rooms' outlines in a zone's space"
```

---


### Task 3: Layer modifiers in the zone runtime

The runtime draws each field layer through its view of the zone's LEDs (rulings 2–4): the mask's weight times the layer's opacity, LED by LED, and the effect rendered on the moved LEDs when the layer has a mirror or a transform. A view is made again only when the layer's modifiers or the zone's LEDs change, so an effect's per-LED work (`ParamField._per_leds()`) is kept between frames. `validate_look` now lets a streamed layer have all three and refuses them on a firmware layer, and the contract types them, so the API takes and serves them.

The runtime fakes in `tests/zones/test_runtime.py` move to `tests/runtime_fakes.py` first, unchanged, so this task's tests and Task 7's can share them.

**Files:**
- Create: `src/dj_ledfx/zones/layer_view.py`, `tests/runtime_fakes.py`, `tests/zones/test_layer_view.py`, `tests/zones/test_runtime_modifiers.py`
- Modify: `src/dj_ledfx/zones/runtime.py`, `src/dj_ledfx/looks/model.py`, `src/dj_ledfx/web/contract.py`, `web/src/api/generated/*` (generated)
- Test: `tests/zones/test_runtime.py`, `tests/looks/test_model.py`, `tests/web/test_looks_api.py`

**Interfaces:**
- Consumes: Task 1's `Mask` (`HeightMask`, `RoomMask`, `SubZoneMask`, `AnchorMask`), `Mirror`, `Transform` and `Layer.mask`, `.mirror`, `.transform`; Task 2's `LedSet.moved(pos)`, `Space.room_outlines` and `Space.sub_zone_outlines`, and `blend_into(base, top, mode, opacity: float | NDArray[np.float32])`.
- Produces:
  - `zones.layer_view`: `MASK_EDGE_M = 0.1`; `LayerView(leds: LedSet, weight: NDArray[np.float32] | None = None)`, a frozen dataclass compared by identity, whose `weight` has shape (N, 1) and is None when every LED shows the layer in full; `layer_view(layer: Layer, leds: LedSet) -> LayerView`; `mask_weights(mask: Mask, leds: LedSet) -> NDArray[np.float32]`, shape (N,); `mirrored(mirror: Mirror, pos: NDArray[np.float64], centre: NDArray[np.float32]) -> NDArray[np.float64]`; `transformed(transform: Transform, pos: NDArray[np.float64], centre: NDArray[np.float32]) -> NDArray[np.float64]`.
  - `ZoneRuntime._view(layer: Layer) -> LayerView`, kept in `self._views: dict[str, tuple[object, LayerView]]` (layer id to the modifiers it was made for and the view), cleared by `_place()`.
  - `validate_look()` refuses a firmware layer with a modifier ("a firmware layer runs whole on the lights it picks; it takes no mask, mirror or transform") and still refuses a streamed layer that picks lights ("give a streamed layer a mask instead").
  - `web.contract`: `Finite = Annotated[float, Field(allow_inf_nan=False)]`; `HeightMask` (`kind: Literal["height"]`, `range: tuple[Finite, Finite]`), `RoomMask` (`room`), `SubZoneMask` (`sub_zone`, served as `subZone`), `AnchorMask` (`anchor`, `radius > 0`), `Mask` (the four, discriminated by `kind`), `Mirror` (`axis`, `at: Finite | None`) and `Transform` (`offset: tuple[Finite, Finite, Finite]`, `rotate_deg`, `scale` from `MIN_SCALE` to `MAX_SCALE`); `Layer.mask: Mask | None`, `Layer.mirror: Mirror | None`, `Layer.transform: Transform | None`.
  - Test helpers in `tests/runtime_fakes.py`: `TILE`, `BULB`, `LAMP`, `LIGHTS`, `FlatField`, `PlaceField`, `register_fields()`, `field_layer(level=0.5, opacity=1.0, **changes)`, `place_layer(**changes)`, `glow_layer(level=0.5)`, `look_of(*layers, needs=(), **changes)`, `placed_light(...)`, `runtime_of(...)`, `latest(runtime)` and `sent(runtime, light, at, leds)`.

- [ ] **Step 1: Move the runtime fakes into a module of their own**

Create `tests/runtime_fakes.py`:

```python
"""Fakes for zone runtime tests: three lights, field effects that are easy to read, and
looks and runtimes made of them. A test file registers the fields with an autouse fixture
that calls register_fields() (conftest drops them after each test)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

import numpy as np
from conftest import nearest_frame

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import NO_ROOM, LedSet, PlacedLeds
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime

TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
BULB = DeviceCapabilities(protocol="LIFX")
LAMP = DeviceCapabilities(protocol="Govee")
LIGHTS = (ZoneLight("tile", 4, TILE), ZoneLight("bulb", 1, BULB), ZoneLight("lamp", 3, LAMP))


class FlatField(FieldEffect, register=False):
    """Flat grey at `level`; raises or returns NaN when the test asks it to."""

    mode: ClassVar[str] = "ok"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"level": EffectParam(type="float", default=0.5, min=0.0, max=1.0)}

    def __init__(self, level: float = 0.5) -> None:
        self.level = level

    def get_params(self) -> dict[str, Any]:
        return {"level": self.level}

    def _apply_params(self, **kwargs: Any) -> None:
        self.level = float(kwargs.get("level", self.level))

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        if FlatField.mode == "raise":
            raise RuntimeError("boom")
        value = np.nan if FlatField.mode == "nan" else self.level
        return np.full((leds.count, 3), value, dtype=np.float32)


class PlaceField(FieldEffect, register=False):
    """Each LED's colour is the position the effect sees it at, x, y and z in metres: a
    layer's mirror and transform show in the frame as moved positions. `seen` keeps every
    LED set it rendered, in order."""

    seen: ClassVar[list[LedSet]] = []

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def _apply_params(self, **kwargs: Any) -> None:
        pass

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        PlaceField.seen.append(leds)
        return np.array(leds.pos, dtype=np.float32)


def register_fields() -> None:
    Effect._registry["flat_field"] = FlatField
    Effect._registry["place_field"] = PlaceField
    FlatField.mode = "ok"
    PlaceField.seen = []


def field_layer(level: float = 0.5, opacity: float = 1.0, **changes: Any) -> Layer:
    """A flat field layer; changes set any other field of the Layer (a mask, a blend)."""
    return Layer(
        id=changes.pop("id", "field"),
        name=changes.pop("name", "Flat"),
        type="field",
        kind="flat_field",
        opacity=opacity,
        settings={"level": level},
        **changes,
    )


def place_layer(**changes: Any) -> Layer:
    return Layer(id="place", name="Place", type="field", kind="place_field", **changes)


def glow_layer(level: float = 0.5) -> Layer:
    return Layer(
        id="glow", name="Glow", type="firmware", kind="glow_firmware", settings={"level": level}
    )


def look_of(*layers: Layer, needs: tuple[Any, ...] = (), **changes: Any) -> Look:
    return Look(
        id=changes.pop("id", "test"),
        name=changes.pop("name", "Test"),
        category="ambient",
        layers=layers,
        needs=needs,
        **changes,
    )


def placed_light(
    device_id: str,
    *points: tuple[float, float, float],
    caps: DeviceCapabilities = LAMP,
    room: int = NO_ROOM,
) -> ZoneLight:
    """A light whose LEDs the map puts at these points."""
    placed = PlacedLeds.from_positions(np.array(points, dtype=np.float64))
    return ZoneLight(device_id, len(points), caps, placed=placed, room=room)


def runtime_of(
    look: Look,
    lights: Sequence[ZoneLight] = LIGHTS,
    latencies: dict[str, float | None] | None = None,
    clock: TempoClock | None = None,
    **kwargs: Any,
) -> ZoneRuntime:
    known = latencies or {}
    return ZoneRuntime(
        kwargs.pop("zone_id", "zone"),
        look,
        lights,
        clock=clock or TempoClock(),
        latency_s=lambda device_id: known.get(device_id, 0.02),
        **kwargs,
    )


def latest(runtime: ZoneRuntime) -> np.ndarray:
    """The newest frame the runtime rendered."""
    return nearest_frame(runtime.ring, 1e9).colors


def sent(runtime: ZoneRuntime, light: str, at: float, leds: int) -> np.ndarray:
    """What a light's route sends at `at`, to a device of `leds` LEDs."""
    route = runtime.route_for(light)
    assert route is not None
    colors = route.colors_at(at, leds)
    assert colors is not None
    return colors
```

In `tests/zones/test_runtime.py`, the fakes go and the module's imports take their place:

```diff
--- a/tests/zones/test_runtime.py
+++ b/tests/zones/test_runtime.py
@@ -1,7 +1,7 @@
 from __future__ import annotations

 import itertools
-from collections.abc import Iterator, Sequence
+from collections.abc import Iterator
 from dataclasses import replace
 from types import MappingProxyType
 from typing import Any, ClassVar
@@ -10,9 +10,15 @@ import numpy as np
 import pytest
 from conftest import builtin_look, nearest_frame, span
 from loguru import logger
+from runtime_fakes import BULB, LAMP, TILE, FlatField, register_fields
+from runtime_fakes import field_layer as _field
+from runtime_fakes import glow_layer as _glow
+from runtime_fakes import latest as _latest
+from runtime_fakes import look_of as _look
+from runtime_fakes import runtime_of as _runtime
+from runtime_fakes import sent as _sent
 from tempo_fakes import START, FakeTime, tempo_clock

-from dj_ledfx.devices.capabilities import DeviceCapabilities
 from dj_ledfx.effects.base import Effect
 from dj_ledfx.effects.context import RenderContext, render_context
 from dj_ledfx.effects.field import FieldEffect
@@ -20,104 +26,21 @@ from dj_ledfx.effects.firmware_lifx import LifxFlame
 from dj_ledfx.effects.ledset import LedSet, PlacedLeds, Space
 from dj_ledfx.effects.params import EffectParam
 from dj_ledfx.looks.builtin import classic_look_id
-from dj_ledfx.looks.model import Layer, Look
+from dj_ledfx.looks.model import Layer
 from dj_ledfx.looks.selectors import parse_selector
 from dj_ledfx.scheduling.route import to_device_colors
 from dj_ledfx.tempo.clock import TempoClock
 from dj_ledfx.types import FloatRGB, RenderedFrame
-from dj_ledfx.zones.runtime import HORIZON_CAP_S, ZoneLight, ZoneRuntime
-
-TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
-BULB = DeviceCapabilities(protocol="LIFX")
-LAMP = DeviceCapabilities(protocol="Govee")
-LIGHTS = (ZoneLight("tile", 4, TILE), ZoneLight("bulb", 1, BULB), ZoneLight("lamp", 3, LAMP))
-
-
-class FlatField(FieldEffect, register=False):
-    """Flat grey at `level`; raises or returns NaN when the test asks it to."""
-
-    mode: ClassVar[str] = "ok"
-
-    @classmethod
-    def parameters(cls) -> dict[str, EffectParam]:
-        return {"level": EffectParam(type="float", default=0.5, min=0.0, max=1.0)}
-
-    def __init__(self, level: float = 0.5) -> None:
-        self.level = level
-
-    def get_params(self) -> dict[str, Any]:
-        return {"level": self.level}
-
-    def _apply_params(self, **kwargs: Any) -> None:
-        self.level = float(kwargs.get("level", self.level))
-
-    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
-        if FlatField.mode == "raise":
-            raise RuntimeError("boom")
-        value = np.nan if FlatField.mode == "nan" else self.level
-        return np.full((leds.count, 3), value, dtype=np.float32)
+from dj_ledfx.zones.runtime import HORIZON_CAP_S, ZoneLight


 @pytest.fixture(autouse=True)
-def _flat_field() -> Iterator[None]:
-    Effect._registry["flat_field"] = FlatField  # conftest drops it after each test
-    FlatField.mode = "ok"
+def _fields() -> Iterator[None]:
+    register_fields()  # conftest drops them after each test
     yield
     FlatField.mode = "ok"


-def _field(level: float = 0.5, opacity: float = 1.0) -> Layer:
-    return Layer(
-        id="field",
-        name="Flat",
-        type="field",
-        kind="flat_field",
-        opacity=opacity,
-        settings={"level": level},
-    )
-
-
-def _glow(level: float = 0.5) -> Layer:
-    return Layer(
-        id="glow", name="Glow", type="firmware", kind="glow_firmware", settings={"level": level}
-    )
-
-
-def _look(*layers: Layer, needs: tuple[Any, ...] = ()) -> Look:
-    return Look(id="test", name="Test", category="ambient", layers=layers, needs=needs)
-
-
-def _runtime(
-    look: Look,
-    lights: Sequence[ZoneLight] = LIGHTS,
-    latencies: dict[str, float | None] | None = None,
-    clock: TempoClock | None = None,
-    **kwargs: Any,
-) -> ZoneRuntime:
-    known = latencies or {}
-    return ZoneRuntime(
-        "zone",
-        look,
-        lights,
-        clock=clock or TempoClock(),
-        latency_s=lambda device_id: known.get(device_id, 0.02),
-        **kwargs,
-    )
-
-
-def _latest(runtime: ZoneRuntime) -> np.ndarray:
-    return nearest_frame(runtime.ring, 1e9).colors
-
-
-def _sent(runtime: ZoneRuntime, light: str, at: float, leds: int) -> np.ndarray:
-    """What a light's route sends at `at`, to a device of `leds` LEDs."""
-    route = runtime.route_for(light)
-    assert route is not None
-    sent = route.colors_at(at, leds)
-    assert sent is not None
-    return sent
-
-
 def test_firmware_runs_where_supported_and_the_field_plays_elsewhere() -> None:
     runtime = _runtime(_look(_field(), _glow()))
     claim = runtime.claim_for("tile")
```

Run: `uv run pytest tests/zones/test_runtime.py -q`
Expected: PASS (31 tests). Nothing has changed but where the fakes live.

- [ ] **Step 2: Write the failing tests**

Create `tests/zones/test_layer_view.py`:

```python
"""Layer modifiers (spec §5.3): where a mask shows a layer, and where a mirror and a
transform make the effect look."""

from __future__ import annotations

import numpy as np
import pytest
from map_home import DESK_CORNER, leds_at, tiny_home

from dj_ledfx.home.map import space_of
from dj_ledfx.looks.model import (
    AnchorMask,
    HeightMask,
    Layer,
    Mirror,
    RoomMask,
    SubZoneMask,
    Transform,
)
from dj_ledfx.zones.layer_view import layer_view, mask_weights, mirrored, transformed

SPACE = space_of(tiny_home())  # west and east rooms, the desk in the west, the sofa at 6, 2


def test_a_height_mask_shows_the_layer_between_its_heights_with_a_soft_edge() -> None:
    leds = leds_at(
        [[1.0, 1.0, 0.2], [1.0, 1.0, 1.0], [1.0, 1.0, 0.5], [1.0, 1.0, 2.0], [1.0, 1.0, 2.5]],
        space=SPACE,
    )
    assert np.allclose(mask_weights(HeightMask(0.5, 2.0), leds), [0.0, 1.0, 0.5, 0.5, 0.0])


def test_a_room_or_sub_zone_mask_shows_the_layer_inside_its_outline() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [6.0, 1.0, 1.0], DESK_CORNER], space=SPACE)
    assert mask_weights(RoomMask("west"), leds).tolist() == [1.0, 0.0, 1.0]
    assert mask_weights(RoomMask("east"), leds).tolist() == [0.0, 1.0, 0.0]
    assert mask_weights(SubZoneMask("desk"), leds).tolist() == [0.0, 0.0, 1.0]


@pytest.mark.parametrize("mask", [RoomMask("attic"), SubZoneMask("nook")])
def test_a_room_or_sub_zone_the_map_lacks_shows_the_layer_nowhere(
    mask: RoomMask | SubZoneMask,
) -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [6.0, 1.0, 1.0]], space=SPACE)
    assert mask_weights(mask, leds).tolist() == [0.0, 0.0]


def test_an_anchor_mask_shows_the_layer_within_its_reach() -> None:
    sofa = (6.0, 2.0, 0.5)
    leds = leds_at([[6.5, 2.0, 0.5], [7.0, 2.0, 0.5], [8.0, 2.0, 0.5]], space=SPACE)
    assert np.allclose(mask_weights(AnchorMask("sofa", 1.0), leds), [1.0, 0.5, 0.0])
    # An anchor the map lacks is the zone's middle, as it is for the effects.
    middle = leds_at([sofa, [6.0, 2.0, 3.5]], space=SPACE)  # the middle is at z 2.0
    assert np.allclose(mask_weights(AnchorMask("gone", 1.0), middle), [0.0, 0.0])
    assert np.allclose(mask_weights(AnchorMask("gone", 2.0), middle), [1.0, 1.0])


def test_a_mirror_folds_the_high_side_onto_the_low_side() -> None:
    pos = np.array([[1.0, 0.0, 0.0], [5.0, 3.0, 0.0], [7.0, 1.0, 2.0]])
    centre = np.array([3.0, 1.0, 1.0], dtype=np.float32)
    assert np.allclose(mirrored(Mirror("x", 4.0), pos, centre), [[1, 0, 0], [3, 3, 0], [1, 1, 2]])
    assert np.allclose(mirrored(Mirror("y"), pos, centre), [[1, 0, 0], [5, -1, 0], [7, 1, 2]])
    assert np.allclose(mirrored(Mirror("z"), pos, centre), [[1, 0, 0], [5, 3, 0], [7, 1, 0]])


def test_a_transform_moves_turns_and_grows_the_field_about_the_zones_centre() -> None:
    centre = np.array([4.0, 2.0, 1.0], dtype=np.float32)
    east_of_it = np.array([[5.0, 2.0, 1.0]])
    # Moved a metre east, the field the LED shows is the one at the centre.
    assert np.allclose(
        transformed(Transform(offset=(1.0, 0.0, 0.0)), east_of_it, centre), [centre]
    )
    # Turned a quarter clockwise seen from above, the LED east of the centre shows what was
    # north of it (y points south).
    assert np.allclose(transformed(Transform(rotate_deg=90.0), east_of_it, centre), [[4, 1, 1]])
    # Grown twice as big, the LED shows what was half as far out.
    assert np.allclose(transformed(Transform(scale=2.0), east_of_it, centre), [[4.5, 2, 1]])


def test_a_layer_without_modifiers_draws_on_the_zones_own_leds() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [6.0, 1.0, 1.0]], space=SPACE)
    view = layer_view(Layer(id="a", name="A", type="field", kind="breathe"), leds)
    assert view.leds is leds and view.weight is None


def test_a_moved_view_keeps_the_zones_bounds_and_weighs_by_where_the_leds_are() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=SPACE)
    layer = Layer(
        id="a",
        name="A",
        type="field",
        kind="breathe",
        mask=RoomMask("west"),
        mirror=Mirror("x", 4.0),
    )
    view = layer_view(layer, leds)
    assert np.allclose(view.leds.pos[:, 0], [1.0, 1.0])  # the east LED sees the west side
    assert all(np.allclose(a, b) for a, b in zip(view.leds.bounds, leds.bounds, strict=True))
    assert view.weight is not None and view.weight.tolist() == [[1.0], [0.0]]  # where it is
```

Create `tests/zones/test_runtime_modifiers.py` (Task 4 adds the look modifiers' tests to it):

```python
"""A zone runtime plays its layers' and its look's modifiers (spec §5.3)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pytest
from map_home import tiny_home
from runtime_fakes import (
    FlatField,
    PlaceField,
    field_layer,
    latest,
    look_of,
    place_layer,
    placed_light,
    register_fields,
    runtime_of,
)

from dj_ledfx.home.map import space_of
from dj_ledfx.looks.model import Mirror, RoomMask, SubZoneMask, Transform

SPACE = space_of(tiny_home())  # west and east rooms, the desk in the west's north-west
WEST = placed_light("west-lamp", (1.0, 1.0, 1.0), (2.0, 1.0, 1.0), room=0)
EAST = placed_light("east-lamp", (6.0, 1.0, 1.0), (7.0, 1.0, 1.0), room=1)


@pytest.fixture(autouse=True)
def _fields() -> Iterator[None]:
    register_fields()
    yield
    FlatField.mode = "ok"


def test_a_masked_layer_draws_only_where_its_mask_lets_it() -> None:
    look = look_of(field_layer(0.2, id="base"), field_layer(0.8, id="top", mask=RoomMask("east")))
    runtime = runtime_of(look, [WEST, EAST], space=SPACE)

    runtime.tick(100.0)

    assert np.allclose(latest(runtime)[:, 0], [0.2, 0.2, 0.8, 0.8])


def test_a_masked_bottom_layer_draws_over_black() -> None:
    runtime = runtime_of(
        look_of(field_layer(0.8, mask=RoomMask("west"))), [WEST, EAST], space=SPACE
    )

    runtime.tick(100.0)

    assert np.allclose(latest(runtime)[:, 0], [0.8, 0.8, 0.0, 0.0])


def test_mirror_and_transform_move_where_the_effect_looks() -> None:
    mirror = runtime_of(look_of(place_layer(mirror=Mirror("x", 4.0))), [WEST, EAST], space=SPACE)
    moved = runtime_of(
        look_of(place_layer(transform=Transform(offset=(1.0, 0.0, 0.0)))),
        [WEST, EAST],
        space=SPACE,
    )

    mirror.tick(100.0)
    moved.tick(100.0)

    assert np.allclose(latest(mirror)[:, 0], [1.0, 2.0, 2.0, 1.0])  # east folded onto west
    assert np.allclose(latest(moved)[:, 0], [0.0, 1.0, 5.0, 6.0])  # each LED sees 1 m west


def test_a_layers_view_is_kept_until_its_modifiers_or_the_leds_change() -> None:
    look = look_of(place_layer(mirror=Mirror("x", 4.0)))
    runtime = runtime_of(look, [WEST, EAST], space=SPACE)
    runtime.tick(100.0)
    runtime.tick(100.1)
    first, again = PlaceField.seen
    assert again is first  # the effect's per-LED work is kept between frames

    runtime.update_look(look_of(place_layer(mirror=Mirror("x", 3.0))))
    runtime.tick(100.2)
    assert PlaceField.seen[-1] is not first
    assert np.allclose(latest(runtime)[:, 0], [1.0, 2.0, 0.0, -1.0])  # folded at 3 m now


def test_a_map_change_redraws_a_masked_layer() -> None:
    runtime = runtime_of(look_of(field_layer(0.8, mask=SubZoneMask("desk"))), [WEST], space=SPACE)
    runtime.tick(100.0)
    assert np.allclose(latest(runtime)[:, 0], [0.0, 0.0])  # the desk is in the room's corner

    nook = ((0.0, 0.0), (3.0, 0.0), (3.0, 2.0), (0.0, 2.0))
    bigger = replace(SPACE, sub_zone_outlines=MappingProxyType({"desk": nook}))
    runtime.set_lights([WEST], bigger)
    runtime.tick(100.1)

    assert np.allclose(latest(runtime)[:, 0], [0.8, 0.8])
```

In `tests/looks/test_model.py`, the M4 refusals go, and a firmware layer with a mask is refused:

```diff
--- a/tests/looks/test_model.py
+++ b/tests/looks/test_model.py
@@ -145,7 +145,6 @@ def test_setting_schema_types() -> None:
         ({"needs": ["weather"]}, "input"),
         ({"layers": [_layer(type="particles", kind="fireflies")]}, "M5"),
         ({"layers": [_layer(settings={"beats_per_cycle": {"value": 2.0, "binding": {}}})]}, "M7"),
-        ({"layers": [_layer(mask={"kind": "height", "range": [0.0, 1.0]})]}, "M4"),
         ({"layers": [_layer(settings={"beats_per_cycle": 2.0})]}, "value"),
         (
             {
@@ -180,7 +179,18 @@ def test_looks_m1_cannot_run_are_refused_with_the_reason(
             [_layer(type="firmware", kind="lifx_flame", settings={"lights": {"value": "type:"}})],
             "one word",
         ),
-        ([_layer(settings={"lights": {"value": ["lamp"]}})], "M4"),
+        ([_layer(settings={"lights": {"value": ["lamp"]}})], "give a streamed layer a mask"),
+        (
+            [
+                _layer(
+                    type="firmware",
+                    kind="lifx_flame",
+                    settings={},
+                    mask={"kind": "room", "room": "west"},
+                )
+            ],
+            "takes no mask",
+        ),
     ],
 )
 def test_layer_problems_are_refused(layers: list[dict[str, Any]], reason: str) -> None:
@@ -367,6 +377,7 @@ def test_layer_modifiers_round_trip(written: dict[str, Any], mask: object) -> No
     mirror = {"axis": "y", "at": 2.5}
     transform = {"offset": [1.0, 0.0, -0.5], "rotateDeg": 90.0, "scale": 2.0}
     look = look_from_dict(_look(layers=[_layer(mask=written, mirror=mirror, transform=transform)]))
+    validate_look(look)  # a streamed layer takes all three
     layer = look.layers[0]
     assert layer.mask == mask
     assert layer.mirror == Mirror("y", 2.5)
```

In `tests/web/test_looks_api.py`:

```diff
--- a/tests/web/test_looks_api.py
+++ b/tests/web/test_looks_api.py
@@ -1,8 +1,11 @@
 from __future__ import annotations

+import json
 from collections.abc import AsyncIterator
 from pathlib import Path
+from typing import Any

+import pytest
 import pytest_asyncio
 from api_home import Api, api_home
 from conftest import FakeLight
@@ -160,3 +163,66 @@ async def test_a_look_with_a_colour_it_cannot_use_is_refused(api: Api) -> None:

     assert no_colours.status_code == 400 and "1 to 16 hex colours" in no_colours.json()["detail"]
     assert not_hex.status_code == 400 and "hex colour" in not_hex.json()["detail"]
+
+
+def _raw(body: dict[str, Any]) -> dict[str, Any]:
+    """A body as Python's json writes it, NaN and all, which httpx's json= won't send."""
+    return {"content": json.dumps(body), "headers": {"content-type": "application/json"}}
+
+
+MODIFIERS = {
+    "mask": {"kind": "height", "range": [0.0, 1.0]},
+    "mirror": {"axis": "x", "at": None},
+    "transform": {"offset": [1.0, 0.0, 0.0], "rotateDeg": 90.0, "scale": 2.0},
+}
+
+
+async def test_a_look_with_layer_modifiers_is_saved_and_served(api: Api) -> None:
+    draft = (await api.client.get("/api/looks/classic-breathe")).json()
+    draft["name"] = "Low breathe"
+    draft["layers"][0].update(MODIFIERS)
+
+    created = await api.client.post("/api/looks", json=draft)
+
+    assert created.status_code == 201
+    layer = (await api.client.get(f"/api/looks/{created.json()['id']}")).json()["layers"][0]
+    assert {key: layer[key] for key in MODIFIERS} == MODIFIERS
+
+
+# Review Focus 4: garbage modifiers from a script or an old client are refused with the
+# reason, and nothing is saved.
+@pytest.mark.parametrize(
+    ("change", "status", "says"),
+    [
+        ({"mask": {"kind": "outdoors"}}, 422, "outdoors"),
+        ({"mask": {"kind": "height", "range": [float("nan"), 1.0]}}, 422, "nan"),
+        ({"mask": {"kind": "height", "range": [2.0, 1.0]}}, 400, "from low to high"),
+        ({"mask": {"kind": "anchor", "anchor": "sofa", "radius": 0.0}}, 422, "greater than 0"),
+        ({"mirror": {"axis": "w"}}, 422, "'x', 'y' or 'z'"),
+        ({"transform": {"scale": 50.0}}, 422, "less than or equal to 10"),
+        ({"transform": {"offset": [1.0, float("inf"), 0.0]}}, 422, "inf"),
+    ],
+)
+async def test_garbage_layer_modifiers_are_refused_with_the_reason(
+    api: Api, change: dict[str, Any], status: int, says: str
+) -> None:
+    draft = (await api.client.get("/api/looks/classic-breathe")).json()
+    draft["name"] = "Broken"
+    draft["layers"][0].update(change)
+
+    resp = await api.client.post("/api/looks", **_raw(draft))
+
+    assert resp.status_code == status
+    assert says in str(resp.json()["detail"])
+    listed = [look["id"] for look in (await api.client.get("/api/looks")).json()]
+    assert listed == BUILT_INS
+
+
+async def test_a_firmware_layer_with_a_mask_is_refused(api: Api) -> None:
+    firmware = (await api.client.get("/api/looks/firmware")).json()
+    firmware["name"] = "Masked"
+    firmware["layers"][0]["mask"] = {"kind": "room", "room": "kitchen"}
+
+    resp = await api.client.post("/api/looks", json=firmware)
+
+    assert resp.status_code == 400 and "takes no mask" in resp.json()["detail"]
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/zones/test_layer_view.py tests/zones/test_runtime_modifiers.py tests/zones/test_runtime.py tests/looks tests/web/test_looks_api.py tests/web/test_openapi_types.py -q`
Expected: FAIL: a collection error, `ModuleNotFoundError: No module named 'dj_ledfx.zones.layer_view'`.

- [ ] **Step 4: The layer's view**

Create `src/dj_ledfx/zones/layer_view.py`:

```python
"""A layer's view of its zone's LEDs: its mask, mirror and transform (spec §5.3).

Layer modifiers change where a field is drawn, never the effect. The mask weighs each LED
by where it sits (a height band, a room, a sub-zone, or the reach of an anchor), with a
soft edge where the band or the reach ends. The mirror and the transform move the
positions the effect sees: an LED shows what the field has at its mirrored and
transformed place. A view depends only on the LEDs and the modifiers, so the runtime keeps
one per layer until either changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field_tools import anchor_or_centre, distances, smoothstep
from dj_ledfx.home.geometry import points_in_polygon
from dj_ledfx.looks.model import (
    AnchorMask,
    HeightMask,
    Layer,
    Mask,
    Mirror,
    RoomMask,
    SubZoneMask,
    Transform,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.ledset import LedSet

MASK_EDGE_M = 0.1  # a height band's or an anchor's reach fades out over this many metres
_AXIS = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True, eq=False)
class LayerView:
    """What a layer draws on: the LEDs its effect renders (the zone's own, or moved) and
    each LED's share of the layer, shape (N, 1); None: every LED in full."""

    leds: LedSet
    weight: NDArray[np.float32] | None = None


def layer_view(layer: Layer, leds: LedSet) -> LayerView:
    weight = None if layer.mask is None else mask_weights(layer.mask, leds)[:, None]
    if layer.mirror is None and layer.transform is None:
        return LayerView(leds, weight)
    pos = leds.pos.astype(np.float64)
    if layer.mirror is not None:
        pos = mirrored(layer.mirror, pos, leds.centre)
    if layer.transform is not None:
        pos = transformed(layer.transform, pos, leds.centre)
    return LayerView(leds.moved(pos.astype(np.float32)), weight)


def mask_weights(mask: Mask, leds: LedSet) -> NDArray[np.float32]:
    """Each LED's share of a masked layer, 0..1, from where the LED sits. A room or a
    sub-zone the map doesn't have (any more) shows the layer nowhere; an anchor it doesn't
    have is the zone's middle, as it is for the effects."""
    half = MASK_EDGE_M / 2.0
    match mask:
        case HeightMask(low, high):
            z = leds.pos[:, 2]
            inside = smoothstep(low - half, low + half, z) * (
                1.0 - smoothstep(high - half, high + half, z)
            )
            weights: NDArray[np.float32] = inside.astype(np.float32)
            return weights
        case AnchorMask(anchor, radius):
            reach = distances(leds, anchor_or_centre(leds, anchor))
            near: NDArray[np.float32] = (
                1.0 - smoothstep(radius - half, radius + half, reach)
            ).astype(np.float32)
            return near
        case RoomMask(room):
            outline = leds.space.room_outlines.get(room)
        case SubZoneMask(sub_zone):
            outline = leds.space.sub_zone_outlines.get(sub_zone)
    if not outline:
        return np.zeros(leds.count, dtype=np.float32)
    inside_outline = points_in_polygon(leds.pos[:, :2].astype(np.float64), outline)
    return inside_outline.astype(np.float32)


def mirrored(
    mirror: Mirror, pos: NDArray[np.float64], centre: NDArray[np.float32]
) -> NDArray[np.float64]:
    """Positions folded across the mirror's plane: an LED on the high side sees the field
    at its reflection, so the low side shows on both."""
    axis = _AXIS[mirror.axis]
    at = float(centre[axis]) if mirror.at is None else mirror.at
    folded = pos.copy()
    high = folded[:, axis] > at
    folded[high, axis] = 2.0 * at - folded[high, axis]
    return folded


def transformed(
    transform: Transform, pos: NDArray[np.float64], centre: NDArray[np.float32]
) -> NDArray[np.float64]:
    """Where in the field each LED looks once the field is moved: shifted by the offset,
    turned clockwise seen from above (x east, y south) and grown by the scale, both about
    the zone's centre. An LED shows what the unmoved field has at the returned place."""
    middle = centre.astype(np.float64)
    back = (pos - np.asarray(transform.offset, dtype=np.float64) - middle) / transform.scale
    turn = math.radians(transform.rotate_deg)
    cos, sin = math.cos(turn), math.sin(turn)
    # Undo a clockwise turn: (x, y) -> (x cos + y sin, -x sin + y cos) with y pointing south.
    x, y = back[:, 0].copy(), back[:, 1].copy()
    back[:, 0] = x * cos + y * sin
    back[:, 1] = -x * sin + y * cos
    placed: NDArray[np.float64] = back + middle
    return placed
```

- [ ] **Step 5: Draw each layer through its view**

`src/dj_ledfx/zones/runtime.py`:

```diff
--- a/src/dj_ledfx/zones/runtime.py
+++ b/src/dj_ledfx/zones/runtime.py
@@ -39,6 +39,7 @@ from dj_ledfx.looks.selectors import selects
 from dj_ledfx.scheduling.route import DeviceRoute
 from dj_ledfx.timing import trim_window, utcnow
 from dj_ledfx.types import RenderedFrame
+from dj_ledfx.zones.layer_view import LayerView, layer_view
 from dj_ledfx.zones.model import CrashInfo

 if TYPE_CHECKING:
@@ -148,6 +149,9 @@ class ZoneRuntime:
         self._copy_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
         self._claim_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
         self._lights: tuple[ZoneLight, ...] = ()
+        # Each field layer's view of the LEDs (its mask, mirror and transform), with the
+        # modifiers it was made for; a new LED set clears them (_place).
+        self._views: dict[str, tuple[object, LayerView]] = {}
         self._rendering = ""
         self._last_crash_log = float("-inf")
         self._render_s = 0.0  # moving average of the render time
@@ -325,13 +329,16 @@ class ZoneRuntime:
         frame: FloatRGB | None = None
         for layer, field_effect in self._fields:
             self._rendering = layer.name
-            colors = _finite(field_effect.render(ctx, self.leds))
-            if frame is None and layer.blend == "normal" and layer.opacity == 1.0:
+            view = self._view(layer)
+            colors = _finite(field_effect.render(ctx, view.leds))
+            whole = view.weight is None
+            if frame is None and whole and layer.blend == "normal" and layer.opacity == 1.0:
                 frame = np.array(colors, dtype=np.float32)  # over black: its own colours
                 continue
             if frame is None:
                 frame = np.zeros((count, 3), dtype=np.float32)
-            blend_into(frame, colors, layer.blend, layer.opacity)
+            opacity = layer.opacity if view.weight is None else view.weight * layer.opacity
+            blend_into(frame, colors, layer.blend, opacity)
         if frame is None:
             frame = np.zeros((count, 3), dtype=np.float32)
         targets = self._copy_targets
@@ -343,6 +350,17 @@ class ZoneRuntime:
             frame[where] = _finite(firmware.emulate(ctx, leds)) * np.float32(layer.opacity)
         return frame

+    def _view(self, layer: Layer) -> LayerView:
+        """The layer's view of the zone's LEDs, made again only when its modifiers or the
+        LED set change, so the effect's per-LED work is kept between frames."""
+        modifiers = (layer.mask, layer.mirror, layer.transform)
+        kept = self._views.get(layer.id)
+        if kept is not None and kept[0] == modifiers:
+            return kept[1]
+        view = layer_view(layer, self.leds)
+        self._views[layer.id] = (modifiers, view)
+        return view
+
     def _compile(self) -> None:
         self.generation = next(_GENERATIONS)
         self.crash = None
@@ -377,6 +395,7 @@ class ZoneRuntime:
         )
         if before is None or before.slices != self.leds.slices:
             self.ring = RingBuffer(self._capacity)
+        self._views = {}
         self._emulated &= {light.device_id for light in self._lights}

     def _picks(self, index: int, light: ZoneLight) -> bool:
```

- [ ] **Step 6: Let streamed layers have modifiers, and type them in the contract**

`src/dj_ledfx/looks/model.py`:

```diff
--- a/src/dj_ledfx/looks/model.py
+++ b/src/dj_ledfx/looks/model.py
@@ -529,10 +529,14 @@ def validate_look(look: Look) -> None:
         raise LookError("Look modifiers arrive in M4")
     for layer in look.layers:
         make_effect(layer)
-        if (layer.mask, layer.mirror, layer.transform) != (None, None, None):
-            raise LookError(f"Layer '{layer.name}': layer modifiers arrive in M4")
+        modified = (layer.mask, layer.mirror, layer.transform) != (None, None, None)
+        if layer.type == "firmware" and modified:
+            raise LookError(
+                f"Layer '{layer.name}': a firmware layer runs whole on the lights it picks; "
+                "it takes no mask, mirror or transform"
+            )
         if layer.type != "firmware" and layer.lights is not None:
             raise LookError(
                 f"Layer '{layer.name}': only a firmware layer picks its lights; "
-                "masks for streamed layers arrive in M4"
+                "give a streamed layer a mask instead"
             )
```

`src/dj_ledfx/web/contract.py`:

```diff
--- a/src/dj_ledfx/web/contract.py
+++ b/src/dj_ledfx/web/contract.py
@@ -25,7 +25,17 @@ from dj_ledfx.home import shapes
 from dj_ledfx.home.map import HomeMap
 from dj_ledfx.home.model import WallKind
 from dj_ledfx.looks import model as looks
-from dj_ledfx.looks.model import Blend, Category, InputKind, LayerType, Scope, TransitionKind
+from dj_ledfx.looks.model import (
+    MAX_SCALE,
+    MIN_SCALE,
+    Blend,
+    Category,
+    InputKind,
+    LayerType,
+    MirrorAxis,
+    Scope,
+    TransitionKind,
+)
 from dj_ledfx.prodjlink.listener import Listening
 from dj_ledfx.tempo.clock import TempoClock
 from dj_ledfx.tempo.model import (
@@ -89,6 +99,58 @@ class SettingSchema(ContractModel):
     options: list[str] | None = None


+Finite = Annotated[float, Field(allow_inf_nan=False)]
+
+
+class HeightMask(ContractModel):
+    """The layer shows between two heights, metres above the floor, low then high."""
+
+    kind: Literal["height"]
+    range: tuple[Finite, Finite]
+
+
+class RoomMask(ContractModel):
+    """The layer shows in one room, by id."""
+
+    kind: Literal["room"]
+    room: str
+
+
+class SubZoneMask(ContractModel):
+    """The layer shows in one sub-zone, by id."""
+
+    kind: Literal["sub-zone"]
+    sub_zone: str
+
+
+class AnchorMask(ContractModel):
+    """The layer shows within `radius` metres of an anchor."""
+
+    kind: Literal["anchor"]
+    anchor: str
+    radius: float = Field(gt=0.0, allow_inf_nan=False)
+
+
+Mask = Annotated[HeightMask | RoomMask | SubZoneMask | AnchorMask, Field(discriminator="kind")]
+
+
+class Mirror(ContractModel):
+    """The field reflected across a plane square to `axis`, `at` metres along it (null:
+    the zone's centre); the low side shows on both."""
+
+    axis: MirrorAxis = "x"
+    at: Finite | None = None
+
+
+class Transform(ContractModel):
+    """The field shifted by `offset` metres, turned `rotateDeg` clockwise seen from above
+    and grown `scale` times, both about the zone's centre."""
+
+    offset: tuple[Finite, Finite, Finite] = (0.0, 0.0, 0.0)
+    rotate_deg: Finite = 0.0
+    scale: float = Field(default=1.0, ge=MIN_SCALE, le=MAX_SCALE, allow_inf_nan=False)
+
+
 class Layer(ContractModel):
     id: str
     name: str
@@ -99,9 +161,9 @@ class Layer(ContractModel):
     opacity: float = 1.0
     settings: dict[str, SettingValue] = Field(default_factory=dict)
     setting_schema: list[SettingSchema] = Field(default_factory=list, alias="schema")
-    mask: dict[str, Any] | None = None
-    mirror: dict[str, Any] | None = None
-    transform: dict[str, Any] | None = None
+    mask: Mask | None = None
+    mirror: Mirror | None = None
+    transform: Transform | None = None


 class LookModifiers(ContractModel):
```

- [ ] **Step 7: Regenerate the API types, and run the web gate**

```bash
(cd web && npm run api:types)
git status --short web
(cd web && npm run api:check && npm test && npx tsc -b && npm run lint && npm run build)
ss -ltn | grep -cE ':(4174|4175) '
```

If the `ss` count isn't `0`, another worktree is running e2e: wait until both ports are free (Global Constraints), then:

```bash
(cd web && npx playwright install chromium && npm run e2e)
```

Expected: only `web/src/api/generated/openapi.json` and `web/src/api/generated/schema.d.ts` changed, and every web step passes with Before Task 1's counts (534 web tests and 60 e2e passed, 20 skipped, on `98ecbee`). Neither the mock nor a pending type needs a change: the mock's looks carry no layer modifiers, nothing in the web app reads them yet, and `contract.ts` has no pending type for them (Task 9 names the new types there).

- [ ] **Step 8: Run the tests to see them pass**

Run: `uv run pytest tests/zones/test_layer_view.py tests/zones/test_runtime_modifiers.py tests/zones/test_runtime.py tests/looks tests/web/test_looks_api.py tests/web/test_openapi_types.py -q`
Expected: PASS (175 tests). The warnings are FastAPI's `on_event` deprecation, as on master.

- [ ] **Step 9: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/zones src/dj_ledfx/looks/model.py src/dj_ledfx/web/contract.py tests/runtime_fakes.py tests/zones tests/looks tests/web/test_looks_api.py
uv run ruff check --fix src/dj_ledfx/zones src/dj_ledfx/looks/model.py src/dj_ledfx/web/contract.py tests/runtime_fakes.py tests/zones tests/looks tests/web/test_looks_api.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones src/dj_ledfx/looks/model.py src/dj_ledfx/web/contract.py web/src/api/generated tests/runtime_fakes.py tests/zones tests/looks tests/web/test_looks_api.py
git commit -m "feat(zones): layer modifiers: masks, mirrors and transforms"
```

---


### Task 4: Look modifiers

The look modifiers (rulings 5–9), as steps in `zones/look_modifiers.py` that the runtime runs on each new frame after its layers: trails, the downbeat flash and the evening, then the copy of what the firmware lights show, then the brightness cap. Each step makes a new array, so a frame in the ring is never changed (CLAUDE.md, "Key Design Decisions"), and the trails keep their own copy of what they showed. The cap also lowers the brightness every firmware effect starts at, and a new cap starts them again. The runtime and the zone manager take an `evening` callable, the evening's amount from 0 to 1, which stays at 0 until Task 5 gives it the sun. `validate_look` stops refusing look modifiers, and the contract checks their limits.

**Files:**
- Create: `src/dj_ledfx/zones/look_modifiers.py`, `tests/zones/test_look_modifiers.py`
- Modify: `src/dj_ledfx/zones/runtime.py`, `src/dj_ledfx/zones/manager.py`, `src/dj_ledfx/looks/model.py`, `src/dj_ledfx/web/contract.py`, `web/src/api/generated/*` (generated)
- Test: `tests/zones/test_runtime_modifiers.py`, `tests/zones/test_manager.py`, `tests/looks/test_model.py`, `tests/web/test_looks_api.py`, `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: `LookModifiers(trails_s: float | None, downbeat_flash: bool, brightness_cap: float | None, evening: bool)` (since M1, read by Task 1); `MAX_TRAILS_S`; Task 3's `ZoneRuntime._view()` and `tests/runtime_fakes.py`; `RenderContext`'s `t` and `bar_phase` (the tempo clock's, since M3).
- Produces:
  - `zones.look_modifiers`: `TRAILS_FALL = 3.0`, `FLASH_BEATS = 0.5`, `FLASH_LEVEL = 0.8`, `EVENING_TINT = (1.0, 0.77, 0.54)`, `EVENING_LEVEL = 0.75`; `Trails()` with `apply(frame: FloatRGB, t: float, trails_s: float) -> FloatRGB` and `reset() -> None`; `flashed(frame: FloatRGB, ctx: RenderContext) -> FloatRGB`; `warmed(frame: FloatRGB, amount: float) -> FloatRGB`; `capped(frame: FloatRGB, cap: float) -> FloatRGB`. None changes its input.
  - `ZoneRuntime(..., evening: Callable[[], float] = lambda: 0.0)`; the property `ZoneRuntime.firmware_brightness -> float` (the zone's brightness times the cap); `_render_look(ctx)` (the layers, then the look modifiers) over `_render_layers(ctx)` and `_draw_firmware(frame, ctx, targets)`; `update_look()` resets the trails when the look turns them off, and moves the generation on when the cap changes and the look has firmware lights.
  - `ZoneManager(..., evening: Callable[[], float] = lambda: 0.0)` hands it to every runtime it makes, and starts each firmware effect at `runtime.firmware_brightness`.
  - `validate_look()` takes look modifiers. `web.contract.LookModifiers`: `trails_s` above 0 and at most `MAX_TRAILS_S`, `brightness_cap` from 0 to 1, both finite or null.
  - Perf helpers in `tests/zones/test_runtime_perf.py`: `EVERY_LOOK_MODIFIER`, `with_every_modifier(look)`, `home_runtime(look, **kwargs)` (the look on every seeded LED of this home) and `tick_times(runtime, ticks=240, start=1000.0)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/zones/test_look_modifiers.py`:

```python
"""Spec §5.3's look modifiers, a frame at a time: trails, the downbeat flash, the evening
and the brightness cap."""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx

from dj_ledfx.zones.look_modifiers import (
    EVENING_LEVEL,
    EVENING_TINT,
    FLASH_LEVEL,
    TRAILS_FALL,
    Trails,
    capped,
    flashed,
    warmed,
)


def _frame(*levels: float) -> np.ndarray:
    return np.array([[level] * 3 for level in levels], dtype=np.float32)


def test_trails_fade_what_was_shown() -> None:
    trails = Trails()
    trails.apply(_frame(1.0, 0.2), t=10.0, trails_s=1.0)

    shown = trails.apply(_frame(0.0, 0.5), t=10.5, trails_s=1.0)

    np.testing.assert_allclose(shown, _frame(math.exp(-TRAILS_FALL * 0.5), 0.5), rtol=1e-6)


def test_trails_keep_their_own_copy_and_never_change_a_frame() -> None:
    trails = Trails()
    shown = trails.apply(_frame(1.0), t=10.0, trails_s=1.0)
    shown[:] = 0.0  # the runtime draws on the frame it gets back
    given = _frame(0.0)

    after = trails.apply(given, t=10.1, trails_s=1.0)

    assert after[0, 0] == pytest.approx(math.exp(-TRAILS_FALL * 0.1))
    np.testing.assert_array_equal(given, _frame(0.0))


def test_trails_let_go_after_their_time_and_on_new_leds() -> None:
    trails = Trails()
    trails.apply(_frame(1.0), t=10.0, trails_s=1.0)
    np.testing.assert_array_equal(trails.apply(_frame(0.0), t=11.0, trails_s=1.0), _frame(0.0))

    trails.apply(_frame(1.0), t=12.0, trails_s=1.0)
    two = trails.apply(_frame(0.0, 0.0), t=12.1, trails_s=1.0)  # a light joined the zone
    np.testing.assert_array_equal(two, _frame(0.0, 0.0))


def test_a_frame_rendered_for_an_earlier_moment_keeps_the_whole_trail() -> None:
    trails = Trails()  # a shorter horizon renders the next frame a little earlier
    trails.apply(_frame(1.0), t=10.0, trails_s=1.0)

    np.testing.assert_array_equal(trails.apply(_frame(0.0), t=9.99, trails_s=1.0), _frame(1.0))


def test_the_downbeat_flashes_towards_white_and_fades_by_half_a_beat() -> None:
    grey = _frame(0.5)

    np.testing.assert_allclose(flashed(grey, tempo_ctx(4.0)), _frame(0.5 + 0.5 * FLASH_LEVEL))
    quarter = 0.5 + 0.5 * FLASH_LEVEL * 0.25  # a quarter of a beat in: (1 - 0.5)² of it
    np.testing.assert_allclose(flashed(grey, tempo_ctx(4.25)), _frame(quarter), rtol=1e-6)
    for beats in (4.5, 5.0, 6.0, 7.0):  # the rest of the bar, its other beats included
        np.testing.assert_array_equal(flashed(grey, tempo_ctx(beats)), grey)
    np.testing.assert_array_equal(flashed(_frame(1.5), tempo_ctx(4.0)), _frame(1.5))


def test_the_evening_warms_and_dims_by_its_amount() -> None:
    white = _frame(1.0)
    fullest = np.asarray(EVENING_TINT, dtype=np.float32) * np.float32(EVENING_LEVEL)

    np.testing.assert_array_equal(warmed(white, 0.0), white)
    np.testing.assert_allclose(warmed(white, 1.0)[0], fullest, rtol=1e-6)
    np.testing.assert_allclose(warmed(white, 0.5)[0], (1.0 + fullest) / 2.0, rtol=1e-6)
    red, _, blue = warmed(white, 1.0)[0]
    assert red > blue  # warmer


def test_the_cap_lowers_only_what_is_over_it_and_keeps_the_hue() -> None:
    frame = np.array([[1.0, 0.5, 0.0], [0.3, 0.3, 0.3], [2.0, 1.0, 0.0], [0, 0, 0]], np.float32)

    np.testing.assert_allclose(
        capped(frame, 0.6),
        [[0.6, 0.3, 0.0], [0.3, 0.3, 0.3], [0.6, 0.3, 0.0], [0.0, 0.0, 0.0]],
        rtol=1e-6,
    )
    np.testing.assert_array_equal(capped(frame, 0.0), np.zeros_like(frame))
```

In `tests/zones/test_runtime_modifiers.py`:

```diff
--- a/tests/zones/test_runtime_modifiers.py
+++ b/tests/zones/test_runtime_modifiers.py
@@ -2,6 +2,7 @@

 from __future__ import annotations

+import math
 from collections.abc import Iterator
 from dataclasses import replace
 from types import MappingProxyType
@@ -13,6 +14,7 @@ from runtime_fakes import (
     FlatField,
     PlaceField,
     field_layer,
+    glow_layer,
     latest,
     look_of,
     place_layer,
@@ -20,9 +22,11 @@ from runtime_fakes import (
     register_fields,
     runtime_of,
 )
+from tempo_fakes import START, FakeTime, tempo_clock

 from dj_ledfx.home.map import space_of
-from dj_ledfx.looks.model import Mirror, RoomMask, SubZoneMask, Transform
+from dj_ledfx.looks.model import LookModifiers, Mirror, RoomMask, SubZoneMask, Transform
+from dj_ledfx.zones.look_modifiers import EVENING_LEVEL, EVENING_TINT, TRAILS_FALL

 SPACE = space_of(tiny_home())  # west and east rooms, the desk in the west's north-west
 WEST = placed_light("west-lamp", (1.0, 1.0, 1.0), (2.0, 1.0, 1.0), room=0)
@@ -95,3 +99,75 @@ def test_a_map_change_redraws_a_masked_layer() -> None:
     runtime.tick(100.1)

     assert np.allclose(latest(runtime)[:, 0], [0.8, 0.8])
+
+
+def test_trails_hold_a_light_that_drops() -> None:
+    look = look_of(field_layer(1.0), modifiers=LookModifiers(trails_s=1.0))
+    runtime = runtime_of(look)
+    runtime.tick(1000.0)
+
+    runtime.update_look(replace(look, layers=(field_layer(0.0),)))
+    runtime.tick(1000.5)
+
+    assert latest(runtime)[0, 0] == pytest.approx(math.exp(-TRAILS_FALL * 0.5), rel=1e-5)
+
+
+def test_trails_turned_off_forget_what_they_held() -> None:
+    look = look_of(field_layer(1.0), modifiers=LookModifiers(trails_s=1.0))
+    runtime = runtime_of(look)
+    runtime.tick(1000.0)
+
+    runtime.update_look(replace(look, layers=(field_layer(0.0),), modifiers=LookModifiers()))
+    runtime.tick(1000.1)
+    runtime.update_look(replace(look, layers=(field_layer(0.0),)))
+    runtime.tick(1000.2)
+
+    assert latest(runtime)[0, 0] == 0.0
+
+
+def test_the_downbeat_flash_follows_the_tempo_clock() -> None:
+    clock = tempo_clock(FakeTime())  # beat 0 at START, 120 BPM: a bar every 2 s
+    look = look_of(field_layer(0.5), modifiers=LookModifiers(downbeat_flash=True))
+    runtime = runtime_of(look, clock=clock)
+
+    runtime.tick(START + 2.0)  # renders a few hundredths of a beat past the downbeat
+    assert latest(runtime)[0, 0] > 0.75
+    runtime.tick(START + 2.5)  # a beat later
+    assert latest(runtime)[0, 0] == pytest.approx(0.5)
+
+
+@pytest.mark.parametrize("on", [True, False])
+def test_a_look_follows_the_evening_only_when_it_asks(on: bool) -> None:
+    look = look_of(field_layer(0.5), modifiers=LookModifiers(evening=on))
+    runtime = runtime_of(look, evening=lambda: 1.0)
+
+    runtime.tick(1000.0)
+
+    fullest = 0.5 * np.asarray(EVENING_TINT) * EVENING_LEVEL
+    np.testing.assert_allclose(latest(runtime)[0], fullest if on else [0.5] * 3, rtol=1e-6)
+
+
+def test_the_cap_caps_streamed_lights_and_the_preview_of_firmware_ones() -> None:
+    look = look_of(field_layer(0.9), glow_layer(0.9), modifiers=LookModifiers(brightness_cap=0.6))
+    runtime = runtime_of(look, brightness=0.5)
+
+    runtime.tick(1000.0)
+
+    assert runtime.mode_of("tile") == "own-effect"  # drawn for the preview, capped too
+    np.testing.assert_allclose(latest(runtime), 0.6, rtol=1e-6)
+    assert runtime.firmware_brightness == pytest.approx(0.3)  # brightness × cap
+
+
+def test_a_new_cap_starts_the_firmware_effects_again() -> None:
+    look = look_of(field_layer(), glow_layer(), modifiers=LookModifiers(brightness_cap=0.6))
+    runtime = runtime_of(look)
+    before = runtime.generation
+
+    runtime.update_look(replace(look, modifiers=LookModifiers(brightness_cap=0.8)))
+
+    assert runtime.generation != before
+    assert runtime.firmware_brightness == pytest.approx(0.8)
+    streamed = runtime_of(look_of(field_layer(), modifiers=LookModifiers(brightness_cap=0.6)))
+    kept = streamed.generation
+    streamed.update_look(replace(streamed.look, modifiers=LookModifiers(brightness_cap=0.8)))
+    assert streamed.generation == kept  # no light to start again
```

In `tests/zones/test_manager.py`:

```diff
--- a/tests/zones/test_manager.py
+++ b/tests/zones/test_manager.py
@@ -13,7 +13,7 @@ from zone_home import BREATHE_AND_GLOW, GLOW, TILE, HomeFactory, zone_record
 from dj_ledfx.devices.capabilities import DeviceCapabilities
 from dj_ledfx.latency.strategies import StaticLatency
 from dj_ledfx.latency.tracker import LatencyTracker
-from dj_ledfx.looks.model import Look, LookError
+from dj_ledfx.looks.model import Look, LookError, LookModifiers
 from dj_ledfx.types import DeviceInfo
 from dj_ledfx.zones.model import (
     TakeOver,
@@ -380,6 +380,18 @@ async def test_starting_a_running_zone_again_replaces_its_look(make_home: HomeFa
     assert home.routes.routes["lamp"].source is home.host.runtimes["z"]


+# Spec §5.3: the brightness cap also caps firmware devices.
+async def test_the_brightness_cap_caps_the_firmware_lights_too(make_home: HomeFactory) -> None:
+    tile = FakeLight("tile", caps=TILE)
+    home = await make_home([tile], [zone_record("z", "tile")])
+
+    await home.manager.start("z", replace(GLOW, modifiers=LookModifiers(brightness_cap=0.6)))
+    assert tile.calls[-1] == ("firmware", {"level": 0.5, "brightness": 0.6})
+
+    await home.manager.set_brightness("z", 0.5)
+    assert tile.calls[-1] == ("firmware", {"level": 0.5, "brightness": pytest.approx(0.3)})
+
+
 async def test_a_look_starts_its_firmware_even_when_layer_ids_repeat(
     make_home: HomeFactory,
 ) -> None:
```

In `tests/looks/test_model.py`, the last M4 refusal goes:

```diff
--- a/tests/looks/test_model.py
+++ b/tests/looks/test_model.py
@@ -146,17 +146,6 @@ def test_setting_schema_types() -> None:
         ({"layers": [_layer(type="particles", kind="fireflies")]}, "M5"),
         ({"layers": [_layer(settings={"beats_per_cycle": {"value": 2.0, "binding": {}}})]}, "M7"),
         ({"layers": [_layer(settings={"beats_per_cycle": 2.0})]}, "value"),
-        (
-            {
-                "modifiers": {
-                    "trailsS": 0.5,
-                    "downbeatFlash": False,
-                    "brightnessCap": None,
-                    "evening": False,
-                }
-            },
-            "M4",
-        ),
         ({"transition": {"kind": "melt", "durationS": 1.0}}, "transition"),
     ],
 )
```

In `tests/web/test_looks_api.py`:

```diff
--- a/tests/web/test_looks_api.py
+++ b/tests/web/test_looks_api.py
@@ -226,3 +226,44 @@ async def test_a_firmware_layer_with_a_mask_is_refused(api: Api) -> None:
     resp = await api.client.post("/api/looks", json=firmware)

     assert resp.status_code == 400 and "takes no mask" in resp.json()["detail"]
+
+
+async def test_a_look_with_look_modifiers_is_saved_and_served(api: Api) -> None:
+    draft = (await api.client.get("/api/looks/classic-breathe")).json()
+    draft["name"] = "Evening breathe"
+    modifiers = {"trailsS": 0.5, "downbeatFlash": True, "brightnessCap": 0.6, "evening": True}
+    draft["modifiers"] = modifiers
+
+    created = await api.client.post("/api/looks", json=draft)
+
+    assert created.status_code == 201
+    saved = await api.client.get(f"/api/looks/{created.json()['id']}")
+    assert saved.json()["modifiers"] == modifiers
+
+
+# Review Focus 4: garbage look modifiers are refused with the reason, and nothing is saved.
+@pytest.mark.parametrize(
+    ("change", "says"),
+    [
+        ({"trailsS": 0.0}, "greater than 0"),
+        ({"trailsS": 11.0}, "less than or equal to 10"),
+        ({"trailsS": float("nan")}, "nan"),
+        ({"brightnessCap": 1.5}, "less than or equal to 1"),
+        ({"brightnessCap": -0.1}, "greater than or equal to 0"),
+        ({"brightnessCap": float("inf")}, "inf"),
+        ({"evening": "tonight"}, "boolean"),
+    ],
+)
+async def test_garbage_look_modifiers_are_refused_with_the_reason(
+    api: Api, change: dict[str, Any], says: str
+) -> None:
+    draft = (await api.client.get("/api/looks/classic-breathe")).json()
+    draft["name"] = "Broken"
+    draft["modifiers"] = {**draft["modifiers"], **change}
+
+    resp = await api.client.post("/api/looks", **_raw(draft))
+
+    assert resp.status_code == 422
+    assert says in str(resp.json()["detail"])
+    listed = [look["id"] for look in (await api.client.get("/api/looks")).json()]
+    assert listed == BUILT_INS
```

In `tests/zones/test_runtime_perf.py`, every built-in look again with every modifier on (spec §5.3's modifiers inside §4.1's budget):

```diff
--- a/tests/zones/test_runtime_perf.py
+++ b/tests/zones/test_runtime_perf.py
@@ -4,34 +4,78 @@ from __future__ import annotations

 import statistics
 import time
+from dataclasses import replace
+from typing import Any

 import pytest
 from map_home import seeded_space, seeded_zone_lights

 from dj_ledfx.home.seed import handoff_home_json
 from dj_ledfx.looks.builtin import builtin_looks
-from dj_ledfx.looks.model import Look
+from dj_ledfx.looks.model import HeightMask, Look, LookModifiers, Mirror, Transform
 from dj_ledfx.tempo.clock import TempoClock
-from dj_ledfx.zones.runtime import ZoneRuntime
+from dj_ledfx.zones.runtime import FRAME_BUDGET_S, ZoneRuntime

 pytestmark = pytest.mark.perf

+EVERY_LOOK_MODIFIER = LookModifiers(
+    trails_s=1.0, downbeat_flash=True, brightness_cap=0.8, evening=True
+)

-@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
-def test_a_zone_frame_renders_in_under_5_ms(look: Look) -> None:
+
+def with_every_modifier(look: Look) -> Look:
+    """The look with every look modifier on, and a mask, a mirror and a transform on each
+    streamed layer (a firmware layer takes none)."""
+    layers = tuple(
+        layer
+        if layer.type == "firmware"
+        else replace(
+            layer,
+            mask=HeightMask(0.3, 2.0),
+            mirror=Mirror("x"),
+            transform=Transform(offset=(0.5, 0.0, 0.0), rotate_deg=30.0, scale=1.5),
+        )
+        for layer in look.layers
+    )
+    return replace(look, layers=layers, modifiers=EVERY_LOOK_MODIFIER)
+
+
+def home_runtime(look: Look, **kwargs: Any) -> ZoneRuntime:
+    """The look on every seeded LED of this home, as the whole-home zone runs it."""
     lights = seeded_zone_lights()
     assert sum(light.led_count for light in lights) == handoff_home_json()["totals"]["leds"]
-    runtime = ZoneRuntime(
+    return ZoneRuntime(
         "home",
         look,
         lights,
         clock=TempoClock(),
         latency_s=lambda _: 0.05,
         space=seeded_space(),
+        **kwargs,
     )
+
+
+def tick_times(runtime: ZoneRuntime, ticks: int = 240, start: float = 1000.0) -> list[float]:
+    """How long each of `ticks` ticks took, 60 a second from `start`."""
     durations = []
-    for step in range(240):
+    for step in range(ticks):
         started = time.perf_counter()
-        runtime.tick(1000.0 + step / 60)
+        runtime.tick(start + step / 60)
         durations.append(time.perf_counter() - started)
-    assert statistics.median(durations) < 0.005
+    return durations
+
+
+@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
+def test_a_zone_frame_renders_in_under_5_ms(look: Look) -> None:
+    runtime = home_runtime(look)
+
+    assert statistics.median(tick_times(runtime)) < FRAME_BUDGET_S
+
+
+# Spec §5.3: the modifiers run inside the same budget.
+@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
+def test_a_zone_frame_with_every_modifier_renders_in_under_5_ms(look: Look) -> None:
+    runtime = home_runtime(with_every_modifier(look), evening=lambda: 0.5)
+
+    assert statistics.median(tick_times(runtime)) < FRAME_BUDGET_S
+    assert runtime.fps_actual >= 59  # it never dropped to a lower frame rate
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/zones/test_look_modifiers.py tests/zones/test_runtime_modifiers.py tests/zones/test_manager.py tests/looks tests/web/test_looks_api.py tests/web/test_openapi_types.py -q`
Expected: FAIL: two collection errors, `ModuleNotFoundError: No module named 'dj_ledfx.zones.look_modifiers'`.

- [ ] **Step 3: The look modifiers**

Create `src/dj_ledfx/zones/look_modifiers.py`:

```python
"""A look's modifiers (spec §5.3): trails, the downbeat flash, the evening and the
brightness cap. The runtime applies them to the zone's frame after its layers, in that
order, each one making a new array, so a frame the ring holds never changes."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.types import FloatRGB

TRAILS_FALL = 3.0  # a trail fades by e^-3, to 5%, over the look's trail time
FLASH_BEATS = 0.5  # the downbeat flash fades out over half a beat
FLASH_LEVEL = 0.8  # how far towards white the flash starts
EVENING_TINT = (1.0, 0.77, 0.54)  # warm white (about 3500 K) against the look's own white
EVENING_LEVEL = 0.75  # the look's brightness at the evening's fullest


class Trails:
    """Per-LED decay: each LED shows the brighter of the look's colour and its own last
    colour fading, channel by channel, so a light that drops leaves a trail. It keeps a
    copy of what it showed, so nothing after it can change its memory."""

    def __init__(self) -> None:
        self._held: FloatRGB | None = None
        self._at = 0.0

    def reset(self) -> None:
        self._held = None

    def apply(self, frame: FloatRGB, t: float, trails_s: float) -> FloatRGB:
        held, gap = self._held, max(t - self._at, 0.0)  # a shorter horizon: no time passed
        if held is not None and held.shape == frame.shape and gap < trails_s:
            fading = held * np.float32(math.exp(-TRAILS_FALL * gap / trails_s))
            frame = np.maximum(frame, fading)
        self._held, self._at = frame.copy(), t
        return frame


def flashed(frame: FloatRGB, ctx: RenderContext) -> FloatRGB:
    """A flash towards white on the first beat of every bar, fading over FLASH_BEATS."""
    since = ctx.bar_phase * BEATS_PER_BAR  # beats since the bar began
    if since >= FLASH_BEATS:
        return frame
    amount = np.float32(FLASH_LEVEL * (1.0 - since / FLASH_BEATS) ** 2)
    flashed: FloatRGB = frame + np.maximum(1.0 - frame, 0.0) * amount
    return flashed


def warmed(frame: FloatRGB, amount: float) -> FloatRGB:
    """Warmer and dimmer by the evening's amount, 0 (day) to 1 (its fullest)."""
    if amount <= 0.0:
        return frame
    fullest = np.asarray(EVENING_TINT, dtype=np.float32) * np.float32(EVENING_LEVEL)
    factor = 1.0 + (fullest - 1.0) * np.float32(min(amount, 1.0))
    warmed: FloatRGB = frame * factor
    return warmed


def capped(frame: FloatRGB, cap: float) -> FloatRGB:
    """Each LED no brighter than the cap, its hue kept: a colour whose brightest channel
    is over the cap is scaled down until that channel is at it."""
    peak = frame.max(axis=1, keepdims=True)
    scale = np.minimum(1.0, np.float32(cap) / np.maximum(peak, np.float32(1e-6)))
    limited: FloatRGB = frame * scale.astype(np.float32)
    return limited
```

- [ ] **Step 4: Run them in the runtime, and cap the firmware lights**

`src/dj_ledfx/zones/runtime.py`:

```diff
--- a/src/dj_ledfx/zones/runtime.py
+++ b/src/dj_ledfx/zones/runtime.py
@@ -40,6 +40,7 @@ from dj_ledfx.scheduling.route import DeviceRoute
 from dj_ledfx.timing import trim_window, utcnow
 from dj_ledfx.types import RenderedFrame
 from dj_ledfx.zones.layer_view import LayerView, layer_view
+from dj_ledfx.zones.look_modifiers import Trails, capped, flashed, warmed
 from dj_ledfx.zones.model import CrashInfo

 if TYPE_CHECKING:
@@ -118,6 +119,7 @@ class ZoneRuntime:
         now: Callable[[], datetime] = utcnow,
         on_state_change: Callable[[ZoneRuntime], None] | None = None,
         watched: Callable[[], bool] = lambda: True,
+        evening: Callable[[], float] = lambda: 0.0,
     ) -> None:
         self.zone_id = zone_id
         # Called when the zone crashes, turns slow or recovers by itself; the zone
@@ -138,6 +140,10 @@ class ZoneRuntime:
         # Whether anyone watches this zone's frames (Task 13). Lights that run their
         # own effect are drawn only for the preview, so only while someone watches.
         self._watched = watched
+        # How far into the evening it is now, 0..1 (home/sun.py); a look with its evening
+        # modifier on reads it every frame.
+        self._evening = evening
+        self._trails = Trails()
         self._fields: list[tuple[Layer, FieldEffect]] = []  # bottom to top
         self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
         self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
@@ -215,6 +221,15 @@ class ZoneRuntime:
                     latency = light_s
         return min(latency + self._stride / self._fps, HORIZON_CAP_S, self._max_lookahead_s)

+    @property
+    def firmware_brightness(self) -> float:
+        """The brightness a light running its own effect is started at: the zone's, under
+        the look's brightness cap (spec §5.3: the cap also caps firmware devices). Streamed
+        colours are capped in the frame and scaled by the zone's brightness at send, so both
+        kinds of light end up at most brightness × cap."""
+        cap = self.look.modifiers.brightness_cap
+        return self.brightness if cap is None else self.brightness * cap
+
     def claim_for(self, device_id: str) -> tuple[Layer, FirmwareEffect] | None:
         index = self._claims.get(device_id)
         return None if index is None else self._firmware[index]
@@ -261,6 +276,8 @@ class ZoneRuntime:
         on only when firmware lights need their effect again.
         """
         old, self.look = self.look, look
+        if look.modifiers.trails_s is None:
+            self._trails.reset()
         if self.crash is not None or _layout(old) != _layout(look) or old.needs != look.needs:
             self._compile()
             return
@@ -276,7 +293,9 @@ class ZoneRuntime:
                 firmware.set_params(**layer.settings)
                 resend = True
             self._firmware[index] = (layer, firmware)
-        if resend:
+        # A new cap changes the brightness the firmware effects run at.
+        recapped = old.modifiers.brightness_cap != look.modifiers.brightness_cap
+        if resend or (recapped and self._claims):
             self.generation = next(_GENERATIONS)

     def restart(self) -> None:
@@ -305,7 +324,7 @@ class ZoneRuntime:
         ctx = render_context(self._clock, target, self._stride / self._fps)
         started = self._timer()
         try:
-            colors = self._render(ctx)
+            colors = self._render_look(ctx)
         except Exception as exc:  # a look never takes the engine down (spec §8)
             self._fail(self._rendering, f"{type(exc).__name__}: {exc}")
             return
@@ -320,12 +339,33 @@ class ZoneRuntime:
         )
         self._track_speed(now, elapsed)

-    def _render(self, ctx: RenderContext) -> FloatRGB:
-        """A new frame every tick: the ring keeps it. The field layers blend bottom to top;
-        then each firmware layer's emulation is drawn on its lights. Waiting, it's dark."""
+    def _render_look(self, ctx: RenderContext) -> FloatRGB:
+        """A new frame every tick: the ring keeps it. The look's streamed colours (its
+        layers), then its modifiers on them (spec §5.3): trails, the downbeat flash and the
+        evening. The lights that run their own effect are drawn after those, as they show
+        (for the preview, while it's watched), and the brightness cap goes over every LED.
+        The trails keep their own copy of what they showed. Waiting, it's dark."""
         count = self.leds.count
         if self.waiting_for or count == 0:
             return np.zeros((count, 3), dtype=np.float32)
+        frame = self._render_layers(ctx)
+        modifiers = self.look.modifiers
+        if modifiers.trails_s is not None:
+            frame = self._trails.apply(frame, ctx.t, modifiers.trails_s)
+        if modifiers.downbeat_flash:
+            frame = flashed(frame, ctx)
+        if modifiers.evening:
+            frame = warmed(frame, self._evening())
+        if self._claim_targets and self._watched():
+            self._draw_firmware(frame, ctx, self._claim_targets)
+        if modifiers.brightness_cap is not None:
+            frame = capped(frame, modifiers.brightness_cap)
+        return frame
+
+    def _render_layers(self, ctx: RenderContext) -> FloatRGB:
+        """The field layers blended bottom to top, then each firmware layer's copy drawn on
+        the lights that stream it."""
+        count = self.leds.count
         frame: FloatRGB | None = None
         for layer, field_effect in self._fields:
             self._rendering = layer.name
@@ -341,14 +381,20 @@ class ZoneRuntime:
             blend_into(frame, colors, layer.blend, opacity)
         if frame is None:
             frame = np.zeros((count, 3), dtype=np.float32)
-        targets = self._copy_targets
-        if self._claim_targets and self._watched():
-            targets = [*targets, *self._claim_targets]
+        self._draw_firmware(frame, ctx, self._copy_targets)
+        return frame
+
+    def _draw_firmware(
+        self,
+        frame: FloatRGB,
+        ctx: RenderContext,
+        targets: Sequence[tuple[int, NDArray[np.intp], LedSet]],
+    ) -> None:
+        """Each firmware layer's emulation, in place, on the rows of the lights given."""
         for index, where, leds in targets:
             layer, firmware = self._firmware[index]
             self._rendering = layer.name
             frame[where] = _finite(firmware.emulate(ctx, leds)) * np.float32(layer.opacity)
-        return frame

     def _view(self, layer: Layer) -> LayerView:
         """The layer's view of the zone's LEDs, made again only when its modifiers or the
@@ -364,6 +410,7 @@ class ZoneRuntime:
     def _compile(self) -> None:
         self.generation = next(_GENERATIONS)
         self.crash = None
+        self._trails.reset()
         self._fields = []
         self._firmware = []
         layers = visible_field_layers(self.look) + list(reversed(firmware_layers(self.look)))
@@ -396,6 +443,7 @@ class ZoneRuntime:
         if before is None or before.slices != self.leds.slices:
             self.ring = RingBuffer(self._capacity)
         self._views = {}
+        self._trails.reset()
         self._emulated &= {light.device_id for light in self._lights}

     def _picks(self, index: int, light: ZoneLight) -> bool:
```

`src/dj_ledfx/zones/manager.py`:

```diff
--- a/src/dj_ledfx/zones/manager.py
+++ b/src/dj_ledfx/zones/manager.py
@@ -148,6 +148,7 @@ class ZoneManager:
         now: Callable[[], datetime] = utcnow,
         home: HomeView = NO_HOME,
         frames_watched: Callable[[], bool] = lambda: True,
+        evening: Callable[[], float] = lambda: 0.0,
     ) -> None:
         self._store = store
         self._looks = looks
@@ -165,6 +166,7 @@ class ZoneManager:
         # Whether anyone watches the live stream: zones draw lights that run their own
         # effect only then (M1 review, constraint 3). main passes Watchers.watching_live.
         self._frames_watched = frames_watched
+        self._evening = evening  # how far into the evening it is, for looks that follow it
         self._zones: dict[str, ZoneRecord] = {}
         self._running: dict[str, _Running] = {}
         self._captured: dict[str, bytes] = {}  # b"": control taken, nothing captured
@@ -814,6 +816,7 @@ class ZoneManager:
             now=self._now,
             on_state_change=self._state_changed,
             watched=watched or self._frames_watched,
+            evening=self._evening,
         )

     def _state_changed(self, runtime: ZoneRuntime) -> None:
@@ -1133,7 +1136,7 @@ class ZoneManager:
             self._routes.set_route(device_id, runtime.route_for(device_id))  # stop frames first
             try:
                 async with adapter.send_lock:
-                    await effect.start(adapter, effect.start_params(runtime.brightness))
+                    await effect.start(adapter, effect.start_params(runtime.firmware_brightness))
             except FirmwareRejected as exc:  # it can't run it: stream a copy (spec §8)
                 logger.warning(
                     "{} refused {} ({}); streaming a copy instead",
```

- [ ] **Step 5: Take look modifiers, and check their limits in the contract**

`src/dj_ledfx/looks/model.py`:

```diff
--- a/src/dj_ledfx/looks/model.py
+++ b/src/dj_ledfx/looks/model.py
@@ -520,13 +520,11 @@ def firmware_layers(look: Look) -> list[Layer]:


 def validate_look(look: Look) -> None:
-    """Raise LookError if M2 can't run the look."""
+    """Raise LookError if the engine can't run the look."""
     if not look.layers:
         raise LookError("A look needs at least one layer")
     if look.scope != "any-zone":
         raise LookError("Home looks (whole-home scope) arrive in M6")
-    if look.modifiers != LookModifiers():
-        raise LookError("Look modifiers arrive in M4")
     for layer in look.layers:
         make_effect(layer)
         modified = (layer.mask, layer.mirror, layer.transform) != (None, None, None)
```

`src/dj_ledfx/web/contract.py`:

```diff
--- a/src/dj_ledfx/web/contract.py
+++ b/src/dj_ledfx/web/contract.py
@@ -27,6 +27,7 @@ from dj_ledfx.home.model import WallKind
 from dj_ledfx.looks import model as looks
 from dj_ledfx.looks.model import (
     MAX_SCALE,
+    MAX_TRAILS_S,
     MIN_SCALE,
     Blend,
     Category,
@@ -167,9 +168,13 @@ class Layer(ContractModel):


 class LookModifiers(ContractModel):
-    trails_s: float | None = None
+    """The look's modifiers (engine spec §5.3): trails (per-LED decay over `trailsS`
+    seconds), a flash on every downbeat, a brightness cap (0..1, firmware lights too) and
+    evening (warmer and dimmer from an hour before sunset)."""
+
+    trails_s: float | None = Field(default=None, gt=0.0, le=MAX_TRAILS_S, allow_inf_nan=False)
     downbeat_flash: bool = False
-    brightness_cap: float | None = None
+    brightness_cap: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
     evening: bool = False


```

Then regenerate the API types, and run the web gate:

```bash
(cd web && npm run api:types)
git status --short web
(cd web && npm run api:check && npm test && npx tsc -b && npm run lint && npm run build)
ss -ltn | grep -cE ':(4174|4175) '
```

If the `ss` count isn't `0`, another worktree is running e2e: wait until both ports are free (Global Constraints), then:

```bash
(cd web && npx playwright install chromium && npm run e2e)
```

Expected: only the two files under `web/src/api/generated/` changed (the limits), and every web step passes with Before Task 1's counts. The mock's looks have no look modifiers set, and `contract.ts` already names `LookModifiers`, so neither changes.

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/zones/test_look_modifiers.py tests/zones/test_runtime_modifiers.py tests/zones/test_manager.py tests/looks tests/web/test_looks_api.py tests/web/test_openapi_types.py -q`
Expected: PASS (179 tests).

- [ ] **Step 7: Run the perf tests**

Run: `uv run pytest -m perf -q`
Expected: PASS (35 tests: Before Task 1's 18 and every built-in look again with every modifier). Each asserts a median tick under 5 ms; the new ones also assert the zone never dropped to a lower frame rate. A failure here is a finding: profile the look (`uv run python -m cProfile -s cumtime`) and make the modifier cheaper, never the test looser.

- [ ] **Step 8: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/zones src/dj_ledfx/looks/model.py src/dj_ledfx/web/contract.py tests/zones tests/looks tests/web/test_looks_api.py
uv run ruff check --fix src/dj_ledfx/zones src/dj_ledfx/looks/model.py src/dj_ledfx/web/contract.py tests/zones tests/looks tests/web/test_looks_api.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones src/dj_ledfx/looks/model.py src/dj_ledfx/web/contract.py web/src/api/generated tests/zones tests/looks tests/web/test_looks_api.py
git commit -m "feat(zones): look modifiers: trails, downbeat flash, evening and the brightness cap"
```

---


### Task 5: The evening

The evening's amount at the home (ruling 8, the owner's times): up from an hour before sunset to civil dusk, 1 through the night, and down from civil dawn to 0 at sunrise, each change eased. The sun's times come from astral, worked out for the home's location (`Home.location`), which `Evening` reads at most once a second (ruling 19), so a location the owner sets applies within a second. The repo has no sun code and no sun library (What exists), and astral is small, pure Python and maintained, so it is the one new dependency. Working the amount out takes about 0.2 ms, once a second, on the render path of whichever zone asks first. `main.py` hands an `Evening` to the zone manager, and from then on looks with `evening` on follow it.

Every location in the tests is made up (Global Constraints).

**Files:**
- Create: `src/dj_ledfx/home/sun.py`, `tests/home/test_sun.py`
- Modify: `pyproject.toml`, `uv.lock` (generated), `src/dj_ledfx/main.py`
- Test: `tests/zone_home.py`, `tests/zones/conftest.py`, `tests/zones/test_manager.py`

**Interfaces:**
- Consumes: Task 4's `ZoneManager(..., evening: Callable[[], float])`; `Home.location: Location | None` (`Location`'s `lat` and `lon`) in `home/model.py`; `effects.easing.ease_in_out`; `timing.utcnow`; astral 3.2's `Observer(latitude, longitude)` and `sun.dawn`, `sun.sunrise`, `sun.sunset`, `sun.dusk(observer, date, tzinfo=...)` (`dawn` and `dusk` civil by default; each raises `ValueError` when the sun never gets there that day) and `sun.elevation(observer, dateandtime)`.
- Produces:
  - `home.sun`: `LEAD = timedelta(hours=1)`, `HORIZON_DEG = -0.833`, `CACHE_S = 1.0`; `evening_amount(lat: float, lon: float, at: datetime) -> float`, 0 (day) to 1 (night), which never raises; `Evening(location: Callable[[], Location | None], *, now: Callable[[], datetime] = utcnow, clock: Callable[[], float] = time.monotonic)`, a callable giving the amount now, 0 with no location (and one warning in the log).
  - `main._run()` passes `evening=Evening(lambda: home_map.home.location)` to the `ZoneManager`.
  - Test helpers: `build_home(..., evening=...)`, `assemble(..., evening=...)` in `tests/zone_home.py`, and `make_home(..., evening=...)` in `tests/zones/conftest.py`.

- [ ] **Step 1: Add astral**

```bash
uv add "astral>=3.2"
uv sync --extra web
git diff --stat pyproject.toml uv.lock
uv run python -c "import astral; print(astral.__version__)"
```

Expected: `pyproject.toml` gains `"astral>=3.2"` in `dependencies`, `uv.lock` gains astral 3.2 (and `tzdata`, which only Windows installs), and the version prints `3.2`. `uv add` syncs without the `web` extra, so the `uv sync --extra web` after it puts the web packages back; without it the web tests skip silently.

- [ ] **Step 2: Write the failing tests**

Create `tests/home/test_sun.py`:

```python
"""Spec §5.3's evening, from the sun's times at made-up places (never the home's)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from astral import Observer, sun

from dj_ledfx.home.model import Location
from dj_ledfx.home.sun import CACHE_S, LEAD, Evening, evening_amount

GREENWICH = (51.48, 0.0)
DAY = datetime(2026, 10, 3, tzinfo=UTC)


def _sun(lat: float, lon: float, day: datetime, *events: str) -> list[datetime]:
    """The sun's events of that UTC date, in the order asked (astral's dawn, sunrise,
    sunset or dusk)."""
    observer = Observer(latitude=lat, longitude=lon)
    return [getattr(sun, event)(observer, day.date(), tzinfo=UTC) for event in events]


def _samples(lat: float, lon: float, start: datetime, hours: int = 48) -> list[float]:
    """The evening every two minutes from `start`."""
    return [
        evening_amount(lat, lon, start + timedelta(minutes=minute))
        for minute in range(0, hours * 60, 2)
    ]


def test_the_evening_through_one_night() -> None:
    lat, lon = GREENWICH
    sunset, dusk = _sun(lat, lon, DAY, "sunset", "dusk")
    dawn, sunrise = _sun(lat, lon, DAY + timedelta(days=1), "dawn", "sunrise")

    def at(when: datetime) -> float:
        return evening_amount(lat, lon, when)

    assert at(sunset - LEAD - timedelta(minutes=1)) == 0.0
    assert at(sunset - LEAD) == 0.0
    assert at(sunset - LEAD + (dusk - sunset + LEAD) / 2) == pytest.approx(0.5)
    assert at(dusk) == 1.0
    assert at(dusk + (dawn - dusk) / 2) == 1.0  # the middle of the night
    assert at(dawn) == 1.0
    assert at(dawn + (sunrise - dawn) / 2) == pytest.approx(0.5)
    assert at(sunrise) == 0.0
    assert at(sunrise + timedelta(hours=6)) == 0.0


# Review Focus 5: anywhere, any time, the evening is a number from 0 to 1 that moves
# continuously, across UTC midnight and the date line, through polar days and nights.
@pytest.mark.parametrize(
    ("lat", "lon", "start"),
    [
        (40.0, -120.0, datetime(2026, 6, 20, tzinfo=UTC)),  # sunset after UTC midnight
        (40.0, -120.0, datetime(2026, 12, 20, tzinfo=UTC)),
        (-34.0, 151.0, datetime(2026, 6, 20, tzinfo=UTC)),  # sunset before UTC noon
        (0.0, 179.9, datetime(2026, 3, 20, tzinfo=UTC)),  # either side of the date line
        (0.0, -179.9, datetime(2026, 3, 20, tzinfo=UTC)),
        (62.0, 10.0, datetime(2026, 6, 20, tzinfo=UTC)),  # no civil dusk at midsummer
        (68.0, 20.0, datetime(2026, 5, 20, tzinfo=UTC)),  # the last sunsets before polar day
        (89.0, 0.0, datetime(2026, 9, 22, tzinfo=UTC)),  # the sun along the horizon
        (-90.0, 0.0, datetime(2026, 3, 20, tzinfo=UTC)),
    ],
)
def test_the_evening_is_in_range_and_continuous_anywhere(
    lat: float, lon: float, start: datetime
) -> None:
    amounts = _samples(lat, lon, start)

    assert all(0.0 <= amount <= 1.0 for amount in amounts)
    steps = [abs(after - before) for before, after in zip(amounts, amounts[1:], strict=False)]
    assert max(steps) < 0.2  # two minutes never jump more than the fastest dawn moves


@pytest.mark.parametrize(("lat", "lon"), [(40.0, -120.0), (-34.0, 151.0), (0.0, 179.9)])
def test_every_day_has_one_evening(lat: float, lon: float) -> None:
    amounts = _samples(lat, lon, datetime(2026, 6, 20, 12, tzinfo=UTC), hours=24)

    assert min(amounts) == 0.0 and max(amounts) == 1.0
    starts = [i for i in range(1, len(amounts)) if amounts[i - 1] == 0.0 < amounts[i]]
    assert len(starts) == 1


def test_polar_day_has_no_evening_and_polar_night_is_all_evening() -> None:
    assert set(_samples(70.0, 20.0, datetime(2026, 6, 20, tzinfo=UTC), hours=24)) == {0.0}
    assert set(_samples(70.0, 20.0, datetime(2026, 12, 20, tzinfo=UTC), hours=24)) == {1.0}


def test_with_no_civil_dusk_the_evening_is_full_at_the_middle_of_the_night() -> None:
    lat, lon = 62.0, 10.0  # midsummer: the sun stays within 6° of the horizon all night
    day = datetime(2026, 6, 20, tzinfo=UTC)
    [sunset] = _sun(lat, lon, day, "sunset")
    [sunrise] = _sun(lat, lon, day + timedelta(days=1), "sunrise")
    middle = sunset + (sunrise - sunset) / 2

    assert evening_amount(lat, lon, middle) == 1.0
    assert 0.0 < evening_amount(lat, lon, sunset) < 1.0
    assert evening_amount(lat, lon, sunrise) == 0.0


def test_evening_reads_the_homes_location_once_a_second() -> None:
    lat, lon = GREENWICH
    [dusk] = _sun(lat, lon, DAY, "dusk")
    night = dusk + timedelta(hours=1)
    place: list[Location | None] = [Location("Test", lat, lon)]
    stamp = [100.0]
    evening = Evening(lambda: place[0], now=lambda: night, clock=lambda: stamp[0])

    assert evening() == 1.0
    place[0] = None
    assert evening() == 1.0  # worked out less than a second ago
    stamp[0] += CACHE_S
    assert evening() == 0.0  # no location: looks play as they are
    place[0] = Location("Test", 0.0, 179.0)  # where it's morning at that moment
    stamp[0] += CACHE_S
    assert evening() == 0.0
    place[0] = Location("Test", lat, lon)
    stamp[0] += CACHE_S
    assert evening() == 1.0
```

In `tests/zone_home.py`, the test home takes an evening:

```diff
--- a/tests/zone_home.py
+++ b/tests/zone_home.py
@@ -194,6 +194,7 @@ async def build_home(
     view: HomeView | None = None,
     frames_watched: Callable[[], bool] | None = None,
     plan: HomeModel | None = None,
+    evening: Callable[[], float] = lambda: 0.0,
 ) -> Home:
     db = StateDB(tmp_path / "state.db")
     await db.open()
@@ -212,6 +213,7 @@ async def build_home(
         view=view,
         frames_watched=frames_watched,
         with_map=plan is not None,
+        evening=evening,
     )


@@ -225,6 +227,7 @@ async def assemble(
     view: HomeView | None = None,
     frames_watched: Callable[[], bool] | None = None,
     with_map: bool = False,
+    evening: Callable[[], float] = lambda: 0.0,
 ) -> Home:
     """The app's objects around an open state.db and a set of lights."""
     bus = EventBus()
@@ -269,6 +272,7 @@ async def assemble(
         now=lambda: clock[0],
         home=view or NO_HOME,
         frames_watched=frames_watched or (lambda: True),
+        evening=evening,
     )
     host.zones = manager
     if home_map is not None:
```

In `tests/zones/conftest.py`:

```diff
--- a/tests/zones/conftest.py
+++ b/tests/zones/conftest.py
@@ -22,6 +22,7 @@ async def make_home(tmp_path: Path) -> AsyncIterator[HomeFactory]:
         preview_only: bool = False,
         view: HomeView | None = None,
         frames_watched: Callable[[], bool] | None = None,
+        evening: Callable[[], float] = lambda: 0.0,
     ) -> Home:
         home = await build_home(
             tmp_path,
@@ -30,6 +31,7 @@ async def make_home(tmp_path: Path) -> AsyncIterator[HomeFactory]:
             preview_only=preview_only,
             view=view,
             frames_watched=frames_watched,
+            evening=evening,
         )
         homes.append(home)
         return home
```

In `tests/zones/test_manager.py`:

```diff
--- a/tests/zones/test_manager.py
+++ b/tests/zones/test_manager.py
@@ -392,6 +392,23 @@ async def test_the_brightness_cap_caps_the_firmware_lights_too(make_home: HomeFa
     assert tile.calls[-1] == ("firmware", {"level": 0.5, "brightness": pytest.approx(0.3)})


+async def test_running_zones_follow_the_managers_evening(make_home: HomeFactory) -> None:
+    asked: list[float] = []
+
+    def evening() -> float:
+        asked.append(1.0)
+        return 1.0
+
+    lamp = FakeLight("lamp", caps=LAMP)
+    home = await make_home([lamp], [zone_record("z", "lamp")], evening=evening)
+    look = replace(home.look("classic-breathe"), modifiers=LookModifiers(evening=True))
+    await home.manager.start("z", look)
+
+    home.host.runtimes["z"].tick(1000.0)
+
+    assert asked
+
+
 async def test_a_look_starts_its_firmware_even_when_layer_ids_repeat(
     make_home: HomeFactory,
 ) -> None:
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/home/test_sun.py tests/zones/test_manager.py -q`
Expected: FAIL: a collection error, `ModuleNotFoundError: No module named 'dj_ledfx.home.sun'`.

- [ ] **Step 4: The evening's amount**

Create `src/dj_ledfx/home/sun.py`:

```python
"""The evening at the home (engine spec §5.3): it warms in from an hour before sunset to
the end of civil twilight, stays through the night, and is off again at sunrise (the
owner's decision), fading out from civil dawn. The sun's times come from the home's
location, worked out with astral."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from astral import Observer, sun
from loguru import logger

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.timing import utcnow

if TYPE_CHECKING:
    from dj_ledfx.home.model import Location

LEAD = timedelta(hours=1)  # the evening starts an hour before sunset
HORIZON_DEG = -0.833  # the sun's centre at sunrise and sunset, refraction included
CACHE_S = 1.0  # Evening works the amount out at most this often
_EVENTS: dict[str, Callable[..., datetime]] = {
    "dawn": sun.dawn,  # civil, the sun 6° below the horizon
    "sunrise": sun.sunrise,
    "sunset": sun.sunset,
    "dusk": sun.dusk,
}
_SAME_EVENT = timedelta(hours=2)  # astral's answers for two dates closer than this are one


def _ramp(fraction: float) -> float:
    return ease_in_out(min(max(fraction, 0.0), 1.0))


def _times(observer: Observer, around: date) -> dict[str, list[datetime]]:
    """Each kind of event from two days before to two days after, each once, in order.
    astral answers per UTC date, so one date can hold two sunsets and the next none."""
    found: dict[str, list[datetime]] = {name: [] for name in _EVENTS}
    for offset in range(-2, 3):
        day = around + timedelta(days=offset)
        for name, event in _EVENTS.items():
            try:
                at = event(observer, day, tzinfo=UTC)
            except ValueError:  # the sun doesn't get there that day (polar day or night)
                continue
            if all(abs(at - seen) > _SAME_EVENT for seen in found[name]):
                found[name].append(at)
    return {name: sorted(times) for name, times in found.items()}


def evening_amount(lat: float, lon: float, at: datetime) -> float:
    """How far into the evening it is at `at` (aware), 0 (day) to 1 (night). It follows
    the night that began with the last sunset whose hour before has started: up from an
    hour before that sunset to civil dusk, 1 until civil dawn, down to 0 at sunrise. Where
    the sun gets no lower than civil twilight, the middle of the night stands in for dusk
    and dawn; where it doesn't set or rise for days, it's day or night by the sun's
    height. Never raises, and moves continuously."""
    observer = Observer(latitude=lat, longitude=lon)
    times = _times(observer, at.astimezone(UTC).date())
    begun = [sunset for sunset in times["sunset"] if sunset - LEAD <= at]
    if not begun:  # no sunset for days: polar day (0) or polar night (1)
        return 0.0 if sun.elevation(observer, at) > HORIZON_DEG else 1.0
    sunset = begun[-1]
    sunrise = next((rise for rise in times["sunrise"] if rise > sunset), None)
    if sunrise is not None and sunrise <= at:
        return 0.0
    middle = None if sunrise is None else sunset + (sunrise - sunset) / 2
    night_end = sunrise or datetime.max.replace(tzinfo=UTC)
    dusk = next((d for d in times["dusk"] if sunset < d < night_end), None)
    full = dusk or middle or sunset + LEAD
    dawn = next((d for d in reversed(times["dawn"]) if full < d < night_end), None)
    fade = max(dawn or middle or full, full)
    start = sunset - LEAD
    if at < full:
        return _ramp((at - start) / (full - start))
    if sunrise is None or at < fade:
        return 1.0
    return 1.0 - _ramp((at - fade) / (sunrise - fade))


class Evening:
    """How far into the evening it is now at the home, 0..1, for the zones' runtimes.
    It reads the home's location each time it works the amount out, at most once a
    second, so a location the owner changes applies within a second. With no location
    it's always 0: looks that follow the evening play as they are."""

    def __init__(
        self,
        location: Callable[[], Location | None],
        *,
        now: Callable[[], datetime] = utcnow,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._location = location
        self._now = now
        self._clock = clock
        self._worked_out = -math.inf
        self._amount = 0.0
        self._told = False

    def __call__(self) -> float:
        stamp = self._clock()
        if stamp - self._worked_out < CACHE_S:
            return self._amount
        self._worked_out = stamp
        place = self._location()
        if place is None:
            if not self._told:
                logger.warning("The home has no location: looks play as they are at evening")
                self._told = True
            self._amount = 0.0
        else:
            self._told = False
            self._amount = evening_amount(place.lat, place.lon, self._now())
        return self._amount
```

- [ ] **Step 5: Give the zones the evening at the home**

`src/dj_ledfx/main.py`:

```diff
--- a/src/dj_ledfx/main.py
+++ b/src/dj_ledfx/main.py
@@ -31,6 +31,7 @@ from dj_ledfx.effects.engine import EffectEngine
 from dj_ledfx.events import DeviceDiscoveredEvent, DeviceOfflineEvent, DeviceOnlineEvent, EventBus
 from dj_ledfx.home.map import HomeMap
 from dj_ledfx.home.store import HomeStore
+from dj_ledfx.home.sun import Evening
 from dj_ledfx.latency.strategies import StaticLatency
 from dj_ledfx.latency.tracker import LatencyTracker
 from dj_ledfx.looks.store import LookStore
@@ -303,6 +304,7 @@ async def _run(args: argparse.Namespace) -> None:
         preview_only=config.engine.preview_only is True,
         home=MapZones(home_map),
         frames_watched=partial(watchers.watching, "live"),
+        evening=Evening(lambda: home_map.home.location),  # looks with evening (spec §5.3)
     )
     await zone_manager.load()
     # Before any light connects, so no light is restored and then taken over again.
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/home/test_sun.py tests/zones/test_manager.py -q`
Expected: PASS (40 tests).

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/home/sun.py src/dj_ledfx/main.py tests/home/test_sun.py tests/zone_home.py tests/zones/conftest.py tests/zones/test_manager.py
uv run ruff check --fix src/dj_ledfx/home/sun.py src/dj_ledfx/main.py tests/home/test_sun.py tests/zone_home.py tests/zones/conftest.py tests/zones/test_manager.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add pyproject.toml uv.lock src/dj_ledfx/home/sun.py src/dj_ledfx/main.py tests/home/test_sun.py tests/zone_home.py tests/zones/conftest.py tests/zones/test_manager.py
git commit -m "feat(home): the evening at the home's location, for looks that follow it"
```

---


### Task 6: The transitions' maths

Where each LED switches, and how much of the new look it shows as the transition goes (ruling 10). `switch_order()` gives each LED its place in the switch, 0 (first) to 1 (last): along the zone's longer side for a wipe, outward from the anchor nearest the zone's middle for a spread, at random for a dissolve (seeded, so the same generation always dissolves alike), and none for a fade, where every LED moves together. `new_share()` turns the progress into each LED's share of the new look, over a soft edge (`EDGES`), eased. Both are pure numpy on whole arrays, for the render path. Task 7 mixes the looks with them.

**Files:**
- Create: `src/dj_ledfx/zones/transition.py`, `tests/zones/test_transition.py`

**Interfaces:**
- Consumes: `LedSet`'s `count`, `npos`, `bounds`, `centre` and `anchors`; `effects.field_tools.distances(leds, point)`; `effects.easing.ease_in_out`; `looks.model.TransitionKind`.
- Produces (`zones.transition`): `EDGES: dict[str, float] = {"wipe": 0.25, "spread": 0.25, "dissolve": 0.1}`; `switch_order(kind: TransitionKind, leds: LedSet, seed: int) -> NDArray[np.float32] | None`, shape (N,), None for a fade or a cut and for a zone with no LEDs; `new_share(kind: TransitionKind, order: NDArray[np.float32] | None, progress: float, count: int) -> NDArray[np.float32]`, shape (count, 1), from 0 (the old look) to 1 (the new), every LED at 0 when the progress is 0 and at 1 when it is 1.

- [ ] **Step 1: Write the failing tests**

Create `tests/zones/test_transition.py`:

```python
"""Spec §5.3's transitions: which LEDs switch when, and how much of the new look each
shows part-way."""

from __future__ import annotations

import numpy as np
import pytest
from map_home import leds_at

from dj_ledfx.looks.model import TransitionKind
from dj_ledfx.zones.transition import new_share, switch_order

Point = tuple[float, float, float]
ROW: list[Point] = [(x, 1.0, 1.0) for x in (0.0, 1.0, 2.0, 3.0, 4.0)]  # west to east
COLUMN: list[Point] = [(1.0, y, 1.0) for y in (0.0, 1.0, 2.0, 3.0, 4.0)]  # north to south


def _share(kind: TransitionKind, points: list[Point], p: float) -> list[float]:
    leds = leds_at(points)
    return [round(float(x), 3) for x in new_share(kind, switch_order(kind, leds, 7), p, 5)[:, 0]]


@pytest.mark.parametrize("kind", ["fade", "cut"])
def test_a_fade_moves_every_led_together(kind: TransitionKind) -> None:
    assert switch_order(kind, leds_at(ROW), 7) is None
    assert _share(kind, ROW, 0.0) == [0.0] * 5
    assert _share(kind, ROW, 0.5) == [0.5] * 5
    assert _share(kind, ROW, 1.0) == [1.0] * 5


def test_a_wipe_sweeps_along_the_zones_longer_side() -> None:
    assert _share("wipe", ROW, 0.5) == [1.0, 1.0, 0.5, 0.0, 0.0]  # west first
    assert _share("wipe", COLUMN, 0.5) == [1.0, 1.0, 0.5, 0.0, 0.0]  # north first


def test_a_spread_grows_from_the_anchor_nearest_the_middle() -> None:
    leds = leds_at(ROW, anchors={"lamp": (2.2, 1.0, 1.0), "door": (9.0, 1.0, 1.0)})

    order = switch_order("spread", leds, 7)

    assert order is not None
    assert np.argsort(order).tolist()[:3] == [2, 3, 1]  # nearest the lamp first
    assert float(order.max()) == pytest.approx(1.0)


def test_a_spread_on_a_map_without_anchors_grows_from_the_middle() -> None:
    order = switch_order("spread", leds_at(ROW), 7)

    assert order is not None
    assert order.round(3).tolist() == [1.0, 0.5, 0.0, 0.5, 1.0]


def test_a_dissolve_is_random_but_the_same_for_the_same_seed() -> None:
    leds = leds_at(ROW)
    first, again, other = (switch_order("dissolve", leds, seed) for seed in (7, 7, 8))

    assert first is not None and again is not None and other is not None
    assert first.tolist() == again.tolist() and first.tolist() != other.tolist()
    assert ((0.0 <= first) & (first < 1.0)).all()


@pytest.mark.parametrize("kind", ["wipe", "spread", "dissolve"])
def test_every_led_starts_old_and_ends_new(kind: TransitionKind) -> None:
    assert _share(kind, ROW, 0.0) == [0.0] * 5
    assert _share(kind, ROW, 1.0) == [1.0] * 5
    assert _share(kind, ROW, 1.5) == [1.0] * 5  # past the end: still new


def test_a_zone_with_no_leds_has_no_order() -> None:
    assert switch_order("wipe", leds_at([]), 7) is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/zones/test_transition.py -q`
Expected: FAIL: a collection error, `ModuleNotFoundError: No module named 'dj_ledfx.zones.transition'`.

- [ ] **Step 3: The switch order and the shares**

Create `src/dj_ledfx/zones/transition.py`:

```python
"""How a zone moves from one look to the next (engine spec §5.3).

Each LED goes from the old look's colour to the new look's as the transition's progress
passes its place in the switch order, over a soft edge: a wipe sweeps a plane across the
zone, a spread grows outward from an anchor, and a dissolve gives each LED its own random
moment. A fade moves every LED together, and a cut has no transition at all. The runtime
mixes the two looks' frames with these shares (runtime.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.field_tools import distances

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.looks.model import TransitionKind

# How much of the transition an LED's own change takes: a soft edge, not a hard line.
EDGES: dict[str, float] = {"wipe": 0.25, "spread": 0.25, "dissolve": 0.1}


def switch_order(kind: TransitionKind, leds: LedSet, seed: int) -> NDArray[np.float32] | None:
    """Each LED's place in the switch, 0 (first) to 1 (last). A wipe runs along the zone's
    longer side on the floor, west to east or north to south; a spread runs outward from
    the anchor nearest the zone's middle (the middle itself on a map without anchors); a
    dissolve's places are random, the same for the same seed. None: every LED together (a
    fade or a cut)."""
    if leds.count == 0 or kind not in EDGES:
        return None
    if kind == "wipe":
        low, high = leds.bounds
        axis = 0 if high[0] - low[0] >= high[1] - low[1] else 1  # x east, y south
        along: NDArray[np.float32] = leds.npos[:, axis].astype(np.float32)
        return along
    if kind == "spread":
        reach = distances(leds, _nearest_anchor(leds))
        farthest = float(reach.max())
        spread: NDArray[np.float32] = (
            reach / np.float32(farthest) if farthest > 1e-6 else np.zeros_like(reach)
        )
        return spread
    order: NDArray[np.float32] = np.random.default_rng(seed).random(leds.count, np.float32)
    return order


def _nearest_anchor(leds: LedSet) -> NDArray[np.float32]:
    middle = leds.centre
    points = [np.asarray(point, dtype=np.float32) for point in leds.anchors.values()]
    if not points:
        return middle
    return min(points, key=lambda point: float(np.linalg.norm(point - middle)))


def new_share(
    kind: TransitionKind, order: NDArray[np.float32] | None, progress: float, count: int
) -> NDArray[np.float32]:
    """How much of the new look each LED shows at `progress` (0..1), shape (count, 1): an
    LED changes over the kind's edge, from where its place in the order meets the sweep."""
    p = min(max(progress, 0.0), 1.0)
    if order is None:
        return np.full((count, 1), ease_in_out(p), dtype=np.float32)
    edge = EDGES[kind]
    reached = np.clip((p * (1.0 + edge) - order.astype(np.float64)) / edge, 0.0, 1.0)
    share: NDArray[np.float32] = ease_in_out(reached).astype(np.float32)[:, None]
    return share
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/zones/test_transition.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/zones/transition.py tests/zones/test_transition.py
uv run ruff check --fix src/dj_ledfx/zones/transition.py tests/zones/test_transition.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones/transition.py tests/zones/test_transition.py
git commit -m "feat(zones): where each LED switches in a wipe, spread or dissolve"
```

---


### Task 7: Transitions in the zone runtime

The runtime plays a transition (rulings 10–13, 20 and 21). `begin_transition()` takes the runtimes that drove the zone's lights (the zone's own last look, and twins of the zones it takes lights from, which Task 8 gathers), works out which of them drew each light, and from then on `render()` mixes their frames under the new look's, LED by LED, with Task 6's shares. A light that runs a firmware effect in either look follows the old look (`holder()`) until the frame at the midpoint, then switches whole; `take_switch()` tells the zone manager when to apply its new look. A twin is a copy of a runtime as it is (same look, LEDs, seed and generation) that only the new zone renders, so the zone that lost the lights runs on undisturbed. Changing the zone's lights or restarting it ends the transition, a brightness change dims every look in the mix, and a replaced look that fails ends the transition with a warning, never the zone.

`tick()` times the whole render, every look in the mix included, so a zone over its budget mid-transition drops to a lower rate as §8 says. `pytest -m perf` proves the budget holds (ruling 20): the two heaviest looks with every modifier, through the first 4 s of a 10 s transition of each kind but the cut, and three looks at once, each on all of this home's seeded LEDs.

**Files:**
- Create: `tests/zones/test_runtime_transitions.py`
- Modify: `src/dj_ledfx/zones/model.py`, `src/dj_ledfx/zones/runtime.py`
- Test: `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: Task 6's `switch_order()` and `new_share()`; Task 4's `_render_look()`, `firmware_brightness` and the `evening` argument; `looks.model.Transition(kind: TransitionKind, duration_s: float)` and `MAX_TRANSITION_S`; `LedSet.slice_for(device_id)`; Task 3's `tests/runtime_fakes.py`; Task 4's perf helpers.
- Produces:
  - `zones.model.TransitionInfo(from_name: str, kind: TransitionKind, progress: float, duration_s: float)` (frozen); `RunningZoneInfo.transition: TransitionInfo | None = None`.
  - `zones.runtime`: `ZoneState = Literal["running", "slow", "crashed", "waiting", "transition"]`; `ZoneRuntime.state` is `crashed`, then `waiting`, then `transition`, then `slow` or `running` (ruling 21).
  - `ZoneRuntime.begin_transition(transition: Transition, sources: Sequence[ZoneRuntime]) -> None`: nothing for a cut, a transition of no time or a look that failed to build; each source settles first, and a source's own older transition ends, so at most three looks render.
  - `ZoneRuntime.twin() -> ZoneRuntime`, `settle() -> None`, `end_transition() -> None`, `take_switch() -> bool` (whether lights went over to this look since the last call), `holder(device_id: str) -> ZoneRuntime`, `streams(device_id: str) -> bool`, the property `transition_sources -> tuple[ZoneRuntime, ...]`, `transition_info() -> TransitionInfo | None` (`from_name`: the look that drove most of the zone's LEDs, "" when none did) and `render(ctx: RenderContext) -> FloatRGB`, public now that a new zone renders a twin.
  - `route_for()` and `horizon_s` ask `streams()`, so a light held by a firmware effect gets no frames; `set_lights()` and `restart()` end the transition; `set_brightness()` dims the transition's sources too.

- [ ] **Step 1: Write the failing tests**

Create `tests/zones/test_runtime_transitions.py`:

```python
"""A zone runtime plays a transition from the looks its lights showed (spec §5.3)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar

import numpy as np
import pytest
from loguru import logger
from runtime_fakes import (
    FlatField,
    field_layer,
    glow_layer,
    latest,
    look_of,
    placed_light,
    register_fields,
    runtime_of,
)

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.looks.model import Layer, Transition
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import ZoneRuntime

FADE = Transition(kind="fade", duration_s=2.0)
HORIZON = 0.02 + 1 / 60  # the fake lights' latency and a frame: every frame's lead


class BrokenField(FlatField, register=False):
    """A field that fails every frame."""

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        raise RuntimeError("boom")


class CostlyField(FlatField, register=False):
    """A flat field whose render "takes" 3 ms on the test's clock (spent)."""

    spent: ClassVar[float] = 0.0

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        CostlyField.spent += 0.003
        return super().render(ctx, leds)


@pytest.fixture(autouse=True)
def _fields() -> Iterator[None]:
    register_fields()
    Effect._registry["broken_field"] = BrokenField
    Effect._registry["costly_field"] = CostlyField
    CostlyField.spent = 0.0
    yield


def _flat(level: float, **changes: Any) -> ZoneRuntime:
    return runtime_of(look_of(field_layer(level), name=f"Level {level}"), **changes)


def _levels(runtime: ZoneRuntime) -> list[float]:
    return [round(float(x), 3) for x in latest(runtime)[:, 0]]


def test_a_fade_mixes_the_old_look_into_the_new_one() -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    assert _levels(new) == [1.0] * 8 and new.state == "transition"
    new.tick(1001.0)
    assert _levels(new) == [0.5] * 8
    new.tick(1002.0)
    assert _levels(new) == [0.0] * 8
    assert new.state == "running" and new.transition_info() is None


def test_a_wipe_switches_the_west_first() -> None:
    lights = [placed_light("lamp", *[(x, 1.0, 1.0) for x in (0.0, 1.0, 2.0, 3.0, 4.0)])]
    old, new = _flat(1.0, lights=lights), _flat(0.0, lights=lights)
    new.begin_transition(Transition(kind="wipe", duration_s=2.0), [old])

    new.tick(1000.0)
    new.tick(1001.0)

    assert _levels(new) == [0.0, 0.0, 0.5, 1.0, 1.0]


def test_lights_nothing_drove_fade_in_from_black() -> None:
    new = _flat(0.8)
    new.begin_transition(FADE, [])

    new.tick(1000.0)
    assert _levels(new) == [0.0] * 8
    new.tick(1001.0)
    assert _levels(new) == [0.4] * 8
    info = new.transition_info()
    assert info is not None and info.from_name == ""  # nothing ran there


@pytest.mark.parametrize("transition", [Transition(), Transition(kind="fade", duration_s=0.0)])
def test_a_cut_plays_nothing(transition: Transition) -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(transition, [old])

    new.tick(1000.0)

    assert new.state == "running" and _levels(new) == [0.0] * 8


def test_the_transition_says_where_it_has_got() -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(FADE, [old])
    new.tick(1000.0)
    new.tick(1000.5)

    info = new.transition_info()

    assert info is not None
    assert (info.from_name, info.kind, info.duration_s) == ("Level 1.0", "fade", 2.0)
    assert info.progress == pytest.approx(0.25)


def test_the_old_look_keeps_its_own_brightness() -> None:
    old, new = _flat(1.0, brightness=0.5), _flat(0.0)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)

    assert _levels(new) == [0.5] * 8  # sent at the new zone's 1.0: the old look's 0.5


def test_a_brightness_change_mid_transition_dims_both_looks() -> None:
    old, new = _flat(1.0), _flat(0.0)
    new.begin_transition(FADE, [old])

    new.set_brightness(0.3)

    assert old.brightness == 0.3


# Review Focus 2: a light running a firmware effect keeps it until the midpoint, and only
# then goes over to the new look, whole.
def test_a_firmware_light_switches_whole_at_the_midpoint() -> None:
    old = runtime_of(look_of(field_layer(1.0), glow_layer(0.9)))  # the tile runs Glow
    new = _flat(0.0)
    new.begin_transition(FADE, [old])
    assert new.holder("tile") is old and not new.streams("tile")
    assert new.holder("lamp") is new and new.streams("lamp")

    new.tick(1000.0)  # the transition runs from this frame's time, 1000 + HORIZON
    new.tick(1001.0)  # this frame's time is the midpoint; now isn't there yet
    assert new.holder("tile") is old
    assert _levels(new)[:4] == [0.0] * 4  # the tile's rows: new, whole
    assert _levels(new)[4:] == [0.5] * 4  # the rest: half-way, about

    new.tick(1000.0 + 1.0 + HORIZON)
    assert new.holder("tile") is new and new.streams("tile")
    assert new.take_switch() and not new.take_switch()  # the manager is told once


def test_a_light_the_new_look_runs_itself_streams_the_old_one_until_the_midpoint() -> None:
    old = _flat(1.0)
    new = runtime_of(look_of(field_layer(0.0), glow_layer(0.9)))
    new.begin_transition(FADE, [old])

    new.tick(1000.0)

    assert new.holder("tile") is old and new.streams("tile")
    assert _levels(new)[:4] == [1.0] * 4
    new.tick(1000.0 + 1.0 + HORIZON)
    assert new.holder("tile") is new and not new.streams("tile")


def test_a_light_nothing_drove_runs_its_firmware_effect_at_once() -> None:
    new = runtime_of(look_of(field_layer(0.0), glow_layer(0.9)))
    new.begin_transition(FADE, [])

    assert new.holder("tile") is new and not new.streams("tile")


def test_an_old_look_that_fails_ends_the_transition_not_the_zone() -> None:
    broken = Layer(id="broken", name="Broken", type="field", kind="broken_field")
    old, new = runtime_of(look_of(broken)), _flat(0.4)
    new.begin_transition(FADE, [old])
    warnings: list[str] = []
    sink = logger.add(warnings.append, level="WARNING", format="{message}")
    try:
        new.tick(1000.0)
    finally:
        logger.remove(sink)

    assert new.state == "running" and new.crash is None
    assert _levels(new) == [0.4] * 8
    assert any("cutting to" in line for line in warnings)


# Review Focus 3: a map change mid-transition cuts to the new look on the lights it keeps.
def test_new_lights_mid_transition_end_it() -> None:
    old = runtime_of(look_of(field_layer(1.0), glow_layer(0.9)))
    new = _flat(0.0)
    new.begin_transition(FADE, [old])
    new.tick(1000.0)

    new.set_lights(new.lights[1:])
    new.tick(1000.1)

    assert new.state == "running" and _levels(new) == [0.0] * 4
    assert new.take_switch()  # the tile it held goes over: the manager applies it


# Review Focus 3: a start mid-transition takes the mix on; a third ends the oldest one.
def test_a_start_mid_transition_takes_the_mix_on_and_three_looks_at_most_render() -> None:
    first, second, third, fourth = _flat(1.0), _flat(0.0), _flat(0.5), _flat(0.2)
    second.begin_transition(FADE, [first])
    second.tick(1000.0)
    second.tick(1001.0)  # half-way: 0.5

    third.begin_transition(FADE, [second])
    third.tick(1001.0)
    assert _levels(third) == [0.5] * 8  # no jump: it starts from the mix
    assert third.transition_sources == (second,) and second.transition_sources == (first,)

    fourth.begin_transition(FADE, [third])
    assert second.transition_sources == ()  # the oldest look is dropped
    assert second.state == "running"


def test_a_twin_draws_what_its_runtime_draws_under_the_same_generation() -> None:
    original = runtime_of(look_of(field_layer(0.7), glow_layer(0.9)))
    twin = original.twin()

    original.tick(1000.0)
    twin.tick(1000.0)

    assert twin.generation == original.generation
    assert twin.claim_for("tile") is not None
    np.testing.assert_array_equal(latest(twin), latest(original))


# Spec §5.3: during a transition the zone renders both looks, so both count against the
# frame budget; with one look again it goes back to every tick.
def test_both_looks_count_against_the_frame_budget() -> None:
    costly = Layer(id="costly", name="Costly", type="field", kind="costly_field")
    old = runtime_of(look_of(costly))
    new = runtime_of(look_of(costly), timer=lambda: CostlyField.spent)
    new.begin_transition(Transition(kind="fade", duration_s=1.0), [old])

    new.tick(1000.0)  # 6 ms: both looks, over the 5 ms budget
    assert new.horizon_s == pytest.approx(0.02 + 2 / 60)  # every other tick
    for step in range(1, 120):
        new.tick(1000.0 + step / 60)
    assert new.state == "running"
    assert new.horizon_s == pytest.approx(0.02 + 1 / 60)  # 3 ms: every tick again


def test_a_zone_at_no_brightness_stays_dark_mid_transition() -> None:
    old, new = _flat(1.0), _flat(0.5, brightness=0.0)
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    new.tick(1001.0)

    assert new.state == "transition" and _levels(new) == [0.25] * 8  # sent at 0: dark
```

In `tests/zones/test_runtime_perf.py`, the budget mid-transition:

```diff
--- a/tests/zones/test_runtime_perf.py
+++ b/tests/zones/test_runtime_perf.py
@@ -12,7 +12,16 @@ from map_home import seeded_space, seeded_zone_lights

 from dj_ledfx.home.seed import handoff_home_json
 from dj_ledfx.looks.builtin import builtin_looks
-from dj_ledfx.looks.model import HeightMask, Look, LookModifiers, Mirror, Transform
+from dj_ledfx.looks.model import (
+    MAX_TRANSITION_S,
+    HeightMask,
+    Look,
+    LookModifiers,
+    Mirror,
+    Transform,
+    Transition,
+    TransitionKind,
+)
 from dj_ledfx.tempo.clock import TempoClock
 from dj_ledfx.zones.runtime import FRAME_BUDGET_S, ZoneRuntime

@@ -79,3 +88,36 @@ def test_a_zone_frame_with_every_modifier_renders_in_under_5_ms(look: Look) -> N

     assert statistics.median(tick_times(runtime)) < FRAME_BUDGET_S
     assert runtime.fps_actual >= 59  # it never dropped to a lower frame rate
+
+
+def _heavy(look_id: str) -> ZoneRuntime:
+    """One of the heaviest looks, every modifier on, on every LED of this home."""
+    look = next(look for look in builtin_looks() if look.id == look_id)
+    return home_runtime(with_every_modifier(look), evening=lambda: 0.5)
+
+
+# Spec §5.3: during a transition the zone renders both looks, and both count against the
+# budget. The two heaviest looks with every modifier, 4 s into the longest transition.
+@pytest.mark.parametrize("kind", ["fade", "wipe", "spread", "dissolve"])
+def test_a_zone_frame_mid_transition_renders_in_under_5_ms(kind: TransitionKind) -> None:
+    old, new = _heavy("aurora"), _heavy("lava")
+    new.begin_transition(Transition(kind=kind, duration_s=MAX_TRANSITION_S), [old])
+
+    durations = tick_times(new)
+
+    assert new.state == "transition"
+    assert statistics.median(durations) < FRAME_BUDGET_S
+    assert new.fps_actual >= 59  # it never dropped to a lower frame rate
+
+
+# The most a zone renders at once: a start while its transition plays mixes three looks.
+def test_three_looks_mid_transition_render_in_under_5_ms() -> None:
+    first, second, third = _heavy("aurora"), _heavy("lava"), _heavy("focus")
+    second.begin_transition(Transition(kind="dissolve", duration_s=MAX_TRANSITION_S), [first])
+    third.begin_transition(Transition(kind="spread", duration_s=MAX_TRANSITION_S), [second])
+
+    durations = tick_times(third)
+
+    assert third.state == "transition" and second.state == "transition"
+    assert statistics.median(durations) < FRAME_BUDGET_S
+    assert third.fps_actual >= 59
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/zones/test_runtime_transitions.py tests/zones/test_runtime.py tests/zones/test_runtime_modifiers.py -q`
Expected: FAIL: 17 failed, 43 passed, with `AttributeError: 'ZoneRuntime' object has no attribute 'begin_transition'` among the reasons. The runtime's and the modifiers' tests still pass.

- [ ] **Step 3: The transition's state in the zone model**

`src/dj_ledfx/zones/model.py`:

```diff
--- a/src/dj_ledfx/zones/model.py
+++ b/src/dj_ledfx/zones/model.py
@@ -7,6 +7,7 @@ from datetime import datetime
 from typing import TYPE_CHECKING, Literal

 if TYPE_CHECKING:
+    from dj_ledfx.looks.model import TransitionKind
     from dj_ledfx.zones.runtime import ZoneState

 ZoneKind = Literal["home", "room", "sub-zone", "group"]
@@ -49,6 +50,18 @@ class CrashInfo:
     at: datetime


+@dataclass(frozen=True, slots=True)
+class TransitionInfo:
+    """A zone's transition while it plays (spec §5.3): the look it replaces (the one that
+    drove most of its lights; "" when they were idle), its kind, how far it has got (0..1)
+    and how long it takes in all."""
+
+    from_name: str
+    kind: TransitionKind
+    progress: float
+    duration_s: float
+
+
 @dataclass(frozen=True, slots=True)
 class TakeOver:
     """A running zone that lost lights to a newer start (spec §4.3)."""
@@ -77,6 +90,7 @@ class RunningZoneInfo:
     waiting_for: tuple[str, ...] = ()
     covers: tuple[str, ...] = ()  # the rooms its lights are in, by name, in map order
     slow_since: datetime | None = None  # for the attention feed; not in the contract
+    transition: TransitionInfo | None = None  # while its state is "transition"


 @dataclass(frozen=True, slots=True)
```

- [ ] **Step 4: Play transitions in the runtime**

`src/dj_ledfx/zones/runtime.py`:

```diff
--- a/src/dj_ledfx/zones/runtime.py
+++ b/src/dj_ledfx/zones/runtime.py
@@ -7,7 +7,7 @@ import math
 import time
 from collections import deque
 from collections.abc import Callable, Mapping, Sequence
-from dataclasses import dataclass
+from dataclasses import dataclass, field
 from datetime import datetime
 from typing import TYPE_CHECKING, Literal

@@ -31,6 +31,8 @@ from dj_ledfx.looks.model import (
     Layer,
     Look,
     LookError,
+    Transition,
+    TransitionKind,
     firmware_layers,
     make_effect,
     visible_field_layers,
@@ -41,7 +43,8 @@ from dj_ledfx.timing import trim_window, utcnow
 from dj_ledfx.types import RenderedFrame
 from dj_ledfx.zones.layer_view import LayerView, layer_view
 from dj_ledfx.zones.look_modifiers import Trails, capped, flashed, warmed
-from dj_ledfx.zones.model import CrashInfo
+from dj_ledfx.zones.model import CrashInfo, TransitionInfo
+from dj_ledfx.zones.transition import new_share, switch_order

 if TYPE_CHECKING:
     from numpy.typing import NDArray
@@ -67,7 +70,7 @@ HORIZON_CAP_S = 0.12
 # runtime always sees a new look as new.
 _GENERATIONS = itertools.count(1)

-ZoneState = Literal["running", "slow", "crashed", "waiting"]
+ZoneState = Literal["running", "slow", "crashed", "waiting", "transition"]
 LightMode = Literal["streaming", "own-effect", "streamed-copy"]


@@ -84,6 +87,28 @@ def _layout(look: Look) -> list[tuple[str, str, str, bool, object]]:
     ]


+@dataclass(eq=False)
+class _Transition:
+    """A transition while it plays (spec §5.3). `rows` says where each look it replaces
+    drew the zone's lights: rows of this zone's frame and of that runtime's. `held` lights
+    run a firmware effect in one of the two looks, so they stay with the look they had
+    until the midpoint and then switch whole."""
+
+    kind: TransitionKind
+    duration_s: float
+    rows: list[tuple[ZoneRuntime, NDArray[np.intp], NDArray[np.intp]]]
+    order: NDArray[np.float32] | None  # each LED's place in the switch; None: all at once
+    held: dict[str, ZoneRuntime]  # light -> the runtime whose look it keeps until then
+    held_rows: NDArray[np.intp]
+    started: float | None = None  # the first frame's time: the transition runs from it
+    progress: float = 0.0  # of the newest frame, 0..1
+    switched: bool = False  # the held lights went over to the new look
+    covered: dict[ZoneRuntime, int] = field(default_factory=dict)  # each look's LEDs
+
+    def past_midpoint(self, t: float) -> bool:
+        return self.started is not None and t >= self.started + self.duration_s / 2.0
+
+
 @dataclass(frozen=True, slots=True)
 class ZoneLight:
     """One light as its zone sees it: where the home map puts its LEDs (None: not placed)
@@ -144,6 +169,8 @@ class ZoneRuntime:
         # modifier on reads it every frame.
         self._evening = evening
         self._trails = Trails()
+        self._transition: _Transition | None = None
+        self._switch_due = False  # lights went over to this look: the manager applies them
         self._fields: list[tuple[Layer, FieldEffect]] = []  # bottom to top
         self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
         self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
@@ -197,6 +224,8 @@ class ZoneRuntime:
             return "crashed"
         if self.waiting_for:
             return "waiting"
+        if self._transition is not None:
+            return "transition"
         return "slow" if self.slow_since is not None else "running"

     @property
@@ -215,7 +244,7 @@ class ZoneRuntime:
         none."""
         latency = 0.0
         for light in self._lights:
-            if light.device_id not in self._claims:
+            if self.streams(light.device_id):
                 light_s = self._latency_s(light.device_id)
                 if light_s is not None and light_s > latency:
                     latency = light_s
@@ -249,7 +278,41 @@ class ZoneRuntime:
         piece = self.leds.slice_for(device_id)
         if piece is None or piece.count == 0:
             return None
-        return DeviceRoute(self, device_id, streaming=device_id not in self._claims)
+        return DeviceRoute(self, device_id, streaming=self.streams(device_id))
+
+    def streams(self, device_id: str) -> bool:
+        """Whether the light takes this zone's frames now: it runs no firmware effect of
+        the look it follows (holder())."""
+        return self.holder(device_id).claim_for(device_id) is None
+
+    def holder(self, device_id: str) -> ZoneRuntime:
+        """The runtime whose look the light follows now: this one, but during a transition
+        a light that runs a firmware effect in either look keeps the look it had until the
+        midpoint (spec §5.3). The zone manager applies the holder's firmware effect, at its
+        brightness, under its generation, so a light keeps the effect it already runs."""
+        transition = self._transition
+        if transition is None or transition.switched:
+            return self
+        return transition.held.get(device_id, self)
+
+    @property
+    def transition_sources(self) -> tuple[ZoneRuntime, ...]:
+        """The runtimes whose looks this one's transition mixes in, while it plays."""
+        transition = self._transition
+        return () if transition is None else tuple(transition.covered)
+
+    def transition_info(self) -> TransitionInfo | None:
+        transition = self._transition
+        if transition is None:
+            return None
+        covered = transition.covered
+        replaced = max(covered, key=covered.__getitem__).look.name if covered else ""
+        return TransitionInfo(
+            from_name=replaced,
+            kind=transition.kind,
+            progress=transition.progress,
+            duration_s=transition.duration_s,
+        )

     # --- changes --------------------------------------------------------------------

@@ -258,15 +321,20 @@ class ZoneRuntime:
         the LED set at each send, so they need nothing. A new ring starts only when the
         frame's layout changed (which device's LEDs sit where): a light moved or a new
         space keeps the frames coming, with no warm-up."""
+        self.end_transition()  # its rows were this LED set's
         if space is not None:
             self._space = space
         self._place(lights)
         self._plan_claims()

     def set_brightness(self, value: float) -> None:
+        """The zone's brightness, for the looks a transition replaces too: the whole zone
+        dims together."""
         self.brightness = value
         if self._claims:
             self.generation = next(_GENERATIONS)  # firmware effects take it when they start
+        for source in self.transition_sources:
+            source.set_brightness(value)

     def update_look(self, look: Look) -> None:
         """Take new settings in place when the layers are the same, else rebuild the look.
@@ -300,6 +368,7 @@ class ZoneRuntime:

     def restart(self) -> None:
         """Re-create the look (spec §8), and give rejected firmware effects another try."""
+        self.end_transition()
         self._emulated.clear()
         self._compile()

@@ -311,12 +380,112 @@ class ZoneRuntime:
             self._copies[device_id] = index
             self._retarget()

+    # --- transitions ----------------------------------------------------------------
+
+    def begin_transition(self, transition: Transition, sources: Sequence[ZoneRuntime]) -> None:
+        """Play this look in over what the zone's lights showed (spec §5.3). `sources` are
+        the runtimes that drove them: the zone's own last look, and copies (twin()) of the
+        zones it took lights from. A light keeps the first source that has it, with the
+        same number of LEDs; a light none had (idle) fades in from black, and runs its
+        firmware effect at once. A cut, a transition of no time or a look that failed to
+        build plays nothing."""
+        if transition.kind == "cut" or transition.duration_s <= 0.0 or self.crash is not None:
+            return
+        rows: list[tuple[ZoneRuntime, NDArray[np.intp], NDArray[np.intp]]] = []
+        held: dict[str, ZoneRuntime] = {}
+        held_rows: list[NDArray[np.intp]] = []
+        covered: set[str] = set()
+        for source in sources:
+            source.settle()  # this transition takes its lights on from here
+            mine: list[NDArray[np.intp]] = []
+            theirs: list[NDArray[np.intp]] = []
+            for piece in self.leds.slices:
+                device_id = piece.device_id
+                old = source.leds.slice_for(device_id)
+                if device_id in covered or old is None or old.count != piece.count:
+                    continue
+                covered.add(device_id)
+                here = np.arange(piece.start, piece.stop, dtype=np.intp)
+                mine.append(here)
+                theirs.append(np.arange(old.start, old.stop, dtype=np.intp))
+                if source.claim_for(device_id) is not None or device_id in self._claims:
+                    held[device_id] = source
+                    held_rows.append(here)
+            if mine:
+                rows.append((source, np.concatenate(mine), np.concatenate(theirs)))
+        for source in sources:  # at most three looks at once: older transitions end now
+            for older in source.transition_sources:
+                older.end_transition()
+        self._transition = _Transition(
+            kind=transition.kind,
+            duration_s=transition.duration_s,
+            rows=rows,
+            order=switch_order(transition.kind, self.leds, self.generation),
+            held=held,
+            held_rows=np.concatenate(held_rows) if held_rows else np.zeros(0, np.intp),
+            covered={source: len(mine_rows) for source, mine_rows, _ in rows},
+        )
+
+    def twin(self) -> ZoneRuntime:
+        """This runtime as it is now, for a zone that takes some of its lights: the same
+        look on the same LEDs, so the same frames (effects are seeded alike), and the same
+        firmware effects under the same generation, so a light that runs one isn't sent it
+        again. It is never ticked or told about: the new zone renders it while its
+        transition plays."""
+        twin = ZoneRuntime(
+            self.zone_id,
+            self.look,
+            self._lights,
+            clock=self._clock,
+            latency_s=self._latency_s,
+            fps=self._fps,
+            max_lookahead_s=self._max_lookahead_s,
+            brightness=self.brightness,
+            seed=self._seed,
+            space=self._space,
+            timer=self._timer,
+            now=self._now,
+            watched=self._watched,
+            evening=self._evening,
+        )
+        twin._emulated = set(self._emulated)
+        twin._plan_claims()
+        twin.generation = self.generation
+        return twin
+
+    def settle(self) -> None:
+        """Let the lights this runtime's transition holds go over to its look now: a newer
+        start takes them on from here. Its colours keep mixing until the transition ends."""
+        if self._transition is not None and not self._transition.switched:
+            self._transition.switched = True
+            self._switch_due = True
+
+    def end_transition(self) -> None:
+        """Show this look alone from the next frame: a transition ending, or cut short."""
+        transition, self._transition = self._transition, None
+        if transition is None:
+            return
+        if not transition.switched:
+            self._switch_due = True
+        self._state_changed()
+
+    def take_switch(self) -> bool:
+        """Whether lights went over to this look since the last call (its transition passed
+        the midpoint or ended): the zone manager applies their firmware effects then."""
+        due, self._switch_due = self._switch_due, False
+        return due
+
     # --- rendering ------------------------------------------------------------------

     def tick(self, now: float) -> None:
         """Render the frame shown at now + horizon, unless crashed or skipping for budget."""
         if self.crash is not None:
             return
+        transition = self._transition
+        if transition is not None and not transition.switched and transition.past_midpoint(now):
+            transition.switched = True  # the frame showing now is past it
+            self._switch_due = True
+            self._state_changed()
         self._ticks += 1
         if self._ticks % self._stride:
             return
@@ -324,7 +493,7 @@ class ZoneRuntime:
         ctx = render_context(self._clock, target, self._stride / self._fps)
         started = self._timer()
         try:
-            colors = self._render_look(ctx)
+            colors = self.render(ctx)
         except Exception as exc:  # a look never takes the engine down (spec §8)
             self._fail(self._rendering, f"{type(exc).__name__}: {exc}")
             return
@@ -339,6 +508,51 @@ class ZoneRuntime:
         )
         self._track_speed(now, elapsed)

+    def render(self, ctx: RenderContext) -> FloatRGB:
+        """The zone's frame for ctx.t: its look, and while a transition plays, the looks it
+        replaces under it, LED by LED (spec §5.3). Both count against the frame budget: tick
+        times this whole call. A replaced look that fails ends the transition, never the
+        zone."""
+        frame = self._render_look(ctx)
+        transition = self._transition
+        if transition is None:
+            return frame
+        if transition.started is None:
+            transition.started = ctx.t
+        progress = (ctx.t - transition.started) / transition.duration_s
+        transition.progress = min(max(progress, 0.0), 1.0)
+        if progress >= 1.0:
+            self.end_transition()
+            return frame
+        try:
+            old = self._replaced(ctx, transition)
+        except Exception as exc:
+            logger.warning(
+                "Zone {}: the look it replaces failed ({}: {}); cutting to {}",
+                self.zone_id,
+                type(exc).__name__,
+                exc,
+                self.look.name,
+            )
+            self.end_transition()
+            return frame
+        share = new_share(transition.kind, transition.order, progress, len(frame))
+        if len(transition.held_rows):  # firmware lights switch whole, at the midpoint
+            new = transition.switched or transition.past_midpoint(ctx.t)
+            share[transition.held_rows] = 1.0 if new else 0.0
+        mixed: FloatRGB = old + (frame - old) * share
+        return mixed
+
+    def _replaced(self, ctx: RenderContext, transition: _Transition) -> FloatRGB:
+        """What the zone's lights showed: each replaced look's rows, at that look's own
+        brightness (frames are scaled by this zone's at send); black where none was."""
+        old = np.zeros((self.leds.count, 3), dtype=np.float32)
+        for source, mine, theirs in transition.rows:
+            colours = source.render(ctx)
+            scale = source.brightness / self.brightness if self.brightness > 0.0 else 0.0
+            old[mine] = colours[theirs] * np.float32(scale)
+        return old
+
     def _render_look(self, ctx: RenderContext) -> FloatRGB:
         """A new frame every tick: the ring keeps it. The look's streamed colours (its
         layers), then its modifiers on them (spec §5.3): trails, the downbeat flash and the
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/zones/test_runtime_transitions.py tests/zones/test_runtime.py tests/zones/test_runtime_modifiers.py -q`
Expected: PASS (60 tests).

- [ ] **Step 6: Run the perf tests**

Run: `uv run pytest -m perf -q`
Expected: PASS (40 tests: Task 4's 35, the four kinds mid-transition and the three looks). Each new one asserts a median tick under 5 ms and `fps_actual >= 59`. A failure is a finding, not noise: profile it, make the mix cheaper (the replaced looks' renders are the cost), and never loosen the test.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/zones tests/zones
uv run ruff check --fix src/dj_ledfx/zones tests/zones
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones tests/zones
git commit -m "feat(zones): transitions in the zone runtime, firmware lights switching at the midpoint"
```

---


### Task 8: Transitions in the zone manager

A start plays a transition (rulings 11–13 and 16): the one it's given, or else the look's own. Before any light changes hands, the manager gathers what the zone's lights show (`_sources()`: the zone's own runtime, and a twin of each zone it takes lights from; a crashed zone's lights fade in from black) and hands it to the new runtime's `begin_transition()`. Everything that applies a look to a light asks the runtime's `holder()`, so a light that runs a firmware effect keeps the old look's, under the old generation and not sent again, until the midpoint. When a transition passes its midpoint or ends, the runtime tells the manager (`take_switch()` in `_state_changed`), and the manager's new `run()` task applies those zones' lights then: each new firmware effect starts, or the light streams. A resumed zone plays no transition, and an assignment saved with an odd transition resumes clamped (Review Focus 1).

**Files:**
- Create: `tests/zones/test_manager_transitions.py`
- Modify: `src/dj_ledfx/zones/manager.py`, `src/dj_ledfx/main.py`

**Interfaces:**
- Consumes: Task 7's `ZoneRuntime.begin_transition()`, `twin()`, `holder()`, `take_switch()`, `transition_info()` and `TransitionInfo`; Task 5's `make_home(..., evening=...)`; `looks.model.Transition`; `LightsChanged` in `zones/model.py`.
- Produces:
  - `ZoneManager.start(zone_id: str, look: Look, transition: Transition | None = None) -> StartResult`: None plays the look's own transition.
  - `ZoneManager.run() -> None` (until cancelled) and `ZoneManager.switch_due() -> None`, which applies the lights of the zones whose transitions passed their midpoints and emits `LightsChanged`.
  - `RunningZoneInfo.transition`, filled from `runtime.transition_info()`.
  - `light_mode()`, `effect_name()`, `verify_firmware()`, `_publish()`, `_apply()` and `_applied_key()` read the light's `holder()`.
  - `main._run()` runs `zone_manager.run()` beside the engine's tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/zones/test_manager_transitions.py`:

```python
"""The zone manager plays a start's transition (spec §5.3): from what the lights showed,
with the lights that run firmware effects switching at the midpoint."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from conftest import FakeLight
from zone_home import GLOW, TILE, HomeFactory, zone_record

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.looks.model import Transition
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import TransitionInfo
from dj_ledfx.zones.runtime import ZoneRuntime

FADE = Transition(kind="fade", duration_s=2.0)
LAMP = DeviceCapabilities(protocol="Govee")


def _past_midpoint(runtime: ZoneRuntime) -> None:
    """The transition's first frame, then a tick at its midpoint."""
    horizon = runtime.horizon_s
    runtime.tick(1000.0)  # the transition runs from this frame's time: 1000 + horizon
    runtime.tick(1000.0 + horizon + FADE.duration_s / 2)


async def test_a_start_plays_the_transition_asked_for_or_the_looks_own(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", caps=LAMP)
    home = await make_home([lamp], [zone_record("z", "lamp")])
    first = await home.manager.start("z", home.look("classic-breathe"))
    assert first.running.state == "running" and first.running.transition is None  # a cut

    result = await home.manager.start("z", home.look("classic-strobe"), FADE)

    assert result.running.state == "transition"
    assert result.running.transition == TransitionInfo("Breathe", "fade", 0.0, 2.0)
    wipe = Transition(kind="wipe", duration_s=1.0)
    own = await home.manager.start("z", replace(home.look("classic-breathe"), transition=wipe))
    assert own.running.transition == TransitionInfo("Strobe", "wipe", 0.0, 1.0)


async def test_a_take_over_plays_from_the_zone_it_took_the_lights_from(
    make_home: HomeFactory,
) -> None:
    a, b, c = FakeLight("a"), FakeLight("b"), FakeLight("c")
    home = await make_home(
        [a, b, c], [zone_record("left", "a", "b"), zone_record("right", "b", "c")]
    )
    await home.manager.start("left", home.look("classic-breathe"))

    result = await home.manager.start("right", home.look("classic-strobe"), FADE)

    assert result.running.transition is not None
    assert result.running.transition.from_name == "Breathe"  # c was idle: it fades in
    left = home.manager.running_info("left")
    assert left is not None and left.state == "running" and left.lights == ("a",)


# Review Focus 2: a light running a firmware effect keeps it, unsent again, until the
# midpoint; then it goes over to the new look.
async def test_a_firmware_light_keeps_its_effect_until_the_midpoint(
    make_home: HomeFactory,
) -> None:
    tile, lamp = FakeLight("tile", caps=TILE), FakeLight("lamp", caps=LAMP)
    home = await make_home([tile, lamp], [zone_record("z", "tile", "lamp")])
    await home.manager.start("z", GLOW)
    sent = len(tile.calls)

    await home.manager.start("z", home.look("classic-breathe"), FADE)

    assert tile.calls[sent:] == []
    assert not home.routes.routes["tile"].streaming
    assert home.manager.light_mode("tile") == "own-effect"
    assert home.manager.effect_name("tile") == "Glow"

    _past_midpoint(home.host.runtimes["z"])
    await home.manager.switch_due()

    assert tile.names()[sent:] == ["prepare_stream"]
    assert home.routes.routes["tile"].streaming
    assert home.manager.light_mode("tile") == "streaming"


# Review Focus 2: the new look's firmware effect, refused at the midpoint, is streamed.
async def test_a_light_that_refuses_the_new_effect_at_the_midpoint_streams_a_copy(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", home.look("classic-breathe"))
    tile.reject_firmware = True

    await home.manager.start("z", GLOW, FADE)
    assert home.routes.routes["tile"].streaming  # the old look, until the midpoint
    _past_midpoint(home.host.runtimes["z"])
    await home.manager.switch_due()

    assert home.manager.light_mode("tile") == "streamed-copy"
    assert home.routes.routes["tile"].streaming


# Review Focus 2: a light back online mid-transition gets the look it follows now.
async def test_a_light_back_online_mid_transition_gets_the_look_it_follows(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)

    home.devices.demote_device("tile")
    await asyncio.sleep(0)  # let the demoted adapter's disconnect run
    await home.manager.on_device_offline("tile")
    await tile.connect()
    home.devices.promote_device("tile", tile)
    await home.manager.on_device_online("tile")

    assert tile.names()[-1] == "firmware"  # Glow again: it holds until the midpoint
    info = home.manager.running_info("z")
    assert info is not None and info.state == "transition"


# Review Focus 3: Off and Stop all mid-transition put the lights back, and a midpoint
# that comes after changes nothing.
@pytest.mark.parametrize("stop", ["off", "stop_all"])
async def test_off_mid_transition_puts_the_lights_back(make_home: HomeFactory, stop: str) -> None:
    tile, lamp = FakeLight("tile", caps=TILE), FakeLight("lamp", caps=LAMP)
    home = await make_home([tile, lamp], [zone_record("z", "tile", "lamp")])
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)
    _past_midpoint(home.host.runtimes["z"])  # its switch is due

    await (home.manager.off("z") if stop == "off" else home.manager.stop_all())
    calls = len(tile.calls)
    await home.manager.switch_due()

    assert ("restore", b"before") in tile.calls and ("restore", b"before") in lamp.calls
    assert len(tile.calls) == calls
    assert home.manager.running_info("z") is None and not home.routes.routes


# Review Focus 3: a zone mid-transition that loses lights cuts to its new look on the rest;
# the zone that took them plays its own transition from that look.
async def test_a_take_over_of_a_zone_in_transition_cuts_it_on_the_lights_it_keeps(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    home = await make_home([a, b], [zone_record("left", "a", "b"), zone_record("right", "b")])
    await home.manager.start("left", home.look("classic-breathe"))
    await home.manager.start("left", home.look("classic-strobe"), FADE)

    result = await home.manager.start("right", home.look("classic-breathe"), FADE)

    left = home.manager.running_info("left")
    assert left is not None and left.state == "running" and left.lights == ("a",)
    assert result.running.transition is not None
    assert result.running.transition.from_name == "Strobe"


async def test_the_manager_applies_the_midpoint_by_itself(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [zone_record("z", "tile")])
    await home.manager.start("z", GLOW)
    await home.manager.start("z", home.look("classic-breathe"), FADE)
    task = asyncio.create_task(home.manager.run())
    try:
        _past_midpoint(home.host.runtimes["z"])
        for _ in range(50):
            await asyncio.sleep(0)
            if tile.names()[-1] == "prepare_stream":
                break
        assert tile.names()[-1] == "prepare_stream"
    finally:
        task.cancel()
        await asyncio.wait([task])


async def test_a_resumed_zone_plays_no_transition(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [zone_record("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"), FADE)

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "running" and info.transition is None


# Review Focus 1: an assignment saved with a transition no request could send now resumes,
# its duration clamped.
async def test_an_assignment_saved_with_an_odd_transition_resumes(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [zone_record("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    saved = json.loads(look_body(home.look("classic-breathe")))
    saved["transition"] = {"kind": "dissolve", "durationS": 0.0}
    text = json.dumps(saved).replace('"durationS": 0.0', '"durationS": NaN')
    await home.db.write("UPDATE zone_assignments SET look=? WHERE zone_id='z'", (text,))

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "running"
    assert home.host.runtimes["z"].look.transition == Transition(kind="dissolve")
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/zones/test_manager_transitions.py tests/zones/test_manager.py -q`
Expected: FAIL: 10 failed, 25 passed, each with `TypeError: ZoneManager.start() takes 3 positional arguments but 4 were given`. `test_an_assignment_saved_with_an_odd_transition_resumes` passes already, from Task 1's clamp, and pins it here.

- [ ] **Step 3: Start with a transition, and apply the midpoint**

`src/dj_ledfx/zones/manager.py`:

```diff
--- a/src/dj_ledfx/zones/manager.py
+++ b/src/dj_ledfx/zones/manager.py
@@ -38,6 +38,7 @@ from dj_ledfx.zones.model import (
     DERIVED_KINDS,
     Assignment,
     CrashInfo,
+    LightsChanged,
     PreviewOnlyChanged,
     RecentLookInfo,
     RunningZoneInfo,
@@ -59,7 +60,7 @@ if TYPE_CHECKING:
     from dj_ledfx.effects.field import FieldEffect
     from dj_ledfx.effects.ledset import Space
     from dj_ledfx.events import EventBus
-    from dj_ledfx.looks.model import Look
+    from dj_ledfx.looks.model import Look, Transition
     from dj_ledfx.looks.store import LookStore
     from dj_ledfx.persistence.state_db import StateDB
     from dj_ledfx.scheduling.route import DeviceRoute
@@ -88,9 +89,12 @@ class RouteTable(Protocol):


 def _applied_key(runtime: ZoneRuntime, device_id: str) -> AppliedKey:
-    """What a light is given once its zone's look is applied to it."""
-    claim = runtime.claim_for(device_id)
-    return runtime.generation, claim[0].id if claim is not None else None
+    """What a light is given once its zone's look is applied to it: the look it follows
+    now (mid-transition, a light that runs a firmware effect keeps the old look's until
+    the midpoint; ZoneRuntime.holder)."""
+    holder = runtime.holder(device_id)
+    claim = holder.claim_for(device_id)
+    return holder.generation, claim[0].id if claim is not None else None


 def _brightness_of(running: _Running) -> float:
@@ -179,6 +183,9 @@ class ZoneManager:
         # is gone or has no lights.
         self._previews: dict[ZoneRuntime, Callable[[], None]] = {}
         self._lock = asyncio.Lock()
+        # Zones whose transitions passed their midpoints: run() applies their lights.
+        self._switching: set[str] = set()
+        self._switched = asyncio.Event()

     async def load(self) -> None:
         await self._load_zones()
@@ -273,12 +280,12 @@ class ZoneManager:
         """How a light shows its zone's look. None when no look drives it: no running zone
         owns it, or its zone's saved look can't be read, which leaves it as it is."""
         runtime = self._runtime_of(device_id)
-        return None if runtime is None else runtime.mode_of(device_id)
+        return None if runtime is None else runtime.holder(device_id).mode_of(device_id)

     def effect_name(self, device_id: str) -> str | None:
         """The firmware effect a light runs, or streams a copy of."""
         runtime = self._runtime_of(device_id)
-        return None if runtime is None else runtime.effect_name(device_id)
+        return None if runtime is None else runtime.holder(device_id).effect_name(device_id)

     def power_of(self, device_id: str) -> bool | None:
         return self._power.get(device_id)
@@ -290,11 +297,14 @@ class ZoneManager:

     # --- commands ---------------------------------------------------------------------

-    async def start(self, zone_id: str, look: Look) -> StartResult:
-        """Put a look on a zone. It takes its lights over from running zones (spec §4.3)."""
+    async def start(
+        self, zone_id: str, look: Look, transition: Transition | None = None
+    ) -> StartResult:
+        """Put a look on a zone. It takes its lights over from running zones (spec §4.3),
+        with the transition asked for, or else the look's own (spec §5.3)."""
         validate_look(look)
         async with self._lock:
-            result = await self._start(zone_id, look)
+            result = await self._start(zone_id, look, transition)
         self._event_bus.emit(ZonesChanged())
         return result

@@ -460,7 +470,7 @@ class ZoneManager:
             if self._applied.get(device_id) != key:
                 await self._sync([device_id])
                 return
-            claim = runtime.claim_for(device_id)
+            claim = runtime.holder(device_id).claim_for(device_id)
             if claim is None:
                 return
             effect = claim[1]
@@ -767,12 +777,15 @@ class ZoneManager:
             raise ZoneNotRunningError(f"{zone.name} isn't running")
         return running

-    async def _start(self, zone_id: str, look: Look) -> StartResult:
+    async def _start(
+        self, zone_id: str, look: Look, transition: Transition | None = None
+    ) -> StartResult:
         validate_look(look)
         zone = self.get_zone(zone_id)
         lights = [light for light in zone.lights if self._adapter(light) is not None]
         if not lights:
             raise ZoneError(f"{zone.name} has no lights")
+        sources = self._sources(zone_id, lights)  # before any light changes hands
         take_overs = await self._take_over(zone_id, lights)
         previous: _Running | None = None
         stopped: list[StoppedLook] = []
@@ -780,6 +793,7 @@ class ZoneManager:
             previous, stopped = self._end_run(zone_id, remember=True)
         brightness = _brightness_of(previous) if previous is not None else 1.0
         runtime = self._new_runtime(zone_id, look, lights, brightness)
+        runtime.begin_transition(look.transition if transition is None else transition, sources)
         running = _Running(
             since=self._now(), lights=lights, runtime=runtime, members=tuple(lights)
         )
@@ -791,6 +805,19 @@ class ZoneManager:
         await self._sync([*lights, *released], power_on=lights)
         return StartResult(self._info(zone_id, running), tuple(take_overs))

+    def _sources(self, zone_id: str, lights: Sequence[str]) -> list[ZoneRuntime]:
+        """What a start's lights show now, for its transition (spec §5.3): the zone's own
+        runtime, and a twin of each zone it takes lights from (its runtime is about to lose
+        them). A crashed zone's lights fade in from black."""
+        sources: list[ZoneRuntime] = []
+        wanted = set(lights)
+        for other_id, running in self._running.items():
+            runtime = running.runtime
+            if runtime is None or runtime.crash is not None or not wanted & set(running.lights):
+                continue
+            sources.append(runtime if other_id == zone_id else runtime.twin())
+        return sources
+
     def _new_runtime(
         self,
         zone_id: str,
@@ -820,10 +847,40 @@ class ZoneManager:
         )

     def _state_changed(self, runtime: ZoneRuntime) -> None:
-        """A running zone crashed, turned slow or recovered by itself (spec §8)."""
+        """A running zone crashed, turned slow or recovered by itself (spec §8), or its
+        transition passed the midpoint or ended (spec §5.3): run() applies its lights."""
         running = self._running.get(runtime.zone_id)
-        if running is not None and running.runtime is runtime:  # not one still starting
-            self._event_bus.emit(ZonesChanged())
+        if running is None or running.runtime is not runtime:  # not one still starting
+            return
+        if runtime.take_switch():
+            self._switching.add(runtime.zone_id)
+            self._switched.set()
+        self._event_bus.emit(ZonesChanged())
+
+    async def run(self) -> None:
+        """Apply the lights' new looks as transitions pass their midpoints, until
+        cancelled (main runs it beside the engine)."""
+        while True:
+            await self._switched.wait()
+            await self.switch_due()
+
+    async def switch_due(self) -> None:
+        """The lights of the zones whose transitions passed their midpoints go over to the
+        new look: each firmware effect starts, or the light streams (spec §5.3)."""
+        self._switched.clear()
+        async with self._lock:
+            zones, self._switching = self._switching, set()
+            lights = [
+                light
+                for zone_id in zones
+                if (running := self._running.get(zone_id)) is not None
+                and running.runtime is not None
+                for light in running.lights
+            ]
+            if not lights:
+                return
+            await self._sync(lights)
+        self._event_bus.emit(LightsChanged())

     def _rebuild_broken(self, zone_id: str, running: _Running) -> bool:
         """A zone whose saved look can't be read tries the look saved under its id."""
@@ -974,6 +1031,7 @@ class ZoneManager:
             waiting_for=runtime.waiting_for,
             slow_since=runtime.slow_since,
             covers=self._home.covers(running.lights),
+            transition=runtime.transition_info(),
         )

     # --- lights -----------------------------------------------------------------------
@@ -1120,7 +1178,7 @@ class ZoneManager:
         every routed slice either way."""
         route = runtime.route_for(device_id)
         applied = self._applied.get(device_id)
-        ready = applied is not None and applied[0] == runtime.generation
+        ready = applied is not None and applied[0] == runtime.holder(device_id).generation
         if route is not None and route.streaming and (self._preview_only or not ready):
             route = replace(route, streaming=False)
         self._routes.set_route(device_id, route)
@@ -1130,13 +1188,14 @@ class ZoneManager:
         key = _applied_key(runtime, device_id)
         if self._applied.get(device_id) == key:
             return
-        claim = runtime.claim_for(device_id)
+        holder = runtime.holder(device_id)  # the look the light follows now
+        claim = holder.claim_for(device_id)
         if claim is not None:
             layer, effect = claim
             self._routes.set_route(device_id, runtime.route_for(device_id))  # stop frames first
             try:
                 async with adapter.send_lock:
-                    await effect.start(adapter, effect.start_params(runtime.firmware_brightness))
+                    await effect.start(adapter, effect.start_params(holder.firmware_brightness))
             except FirmwareRejected as exc:  # it can't run it: stream a copy (spec §8)
                 logger.warning(
                     "{} refused {} ({}); streaming a copy instead",
@@ -1144,9 +1203,9 @@ class ZoneManager:
                     effect.display_name,
                     exc,
                 )
-                runtime.mark_emulated(device_id)
+                holder.mark_emulated(device_id)
                 claim = None
-                key = (runtime.generation, None)
+                key = (holder.generation, None)
             except Exception as exc:  # no answer: left unapplied, the next poll tries again
                 logger.warning(
                     "{} didn't start {} ({}); trying again at the next poll",
```

`src/dj_ledfx/main.py`:

```diff
--- a/src/dj_ledfx/main.py
+++ b/src/dj_ledfx/main.py
@@ -474,6 +474,7 @@ async def _run(args: argparse.Namespace) -> None:
     tasks.append(asyncio.create_task(light_monitor.run()))
     tasks.append(asyncio.create_task(attention_feed.run()))
     tasks.append(asyncio.create_task(previews.run()))
+    tasks.append(asyncio.create_task(zone_manager.run()))  # transitions' midpoints

     discovery_orchestrator.start()

```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/zones/test_manager_transitions.py tests/zones/test_manager.py -q`
Expected: PASS (35 tests).

- [ ] **Step 5: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/zones/manager.py src/dj_ledfx/main.py tests/zones/test_manager_transitions.py
uv run ruff check --fix src/dj_ledfx/zones/manager.py src/dj_ledfx/main.py tests/zones/test_manager_transitions.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones/manager.py src/dj_ledfx/main.py tests/zones/test_manager_transitions.py
git commit -m "feat(zones): starts play transitions; the manager applies the midpoint"
```

---


### Task 9: Transitions in the API, the web app's mock, and backups

`POST /zones/{id}/start` plays the transition it's given, or else the look's own (ruling 16), and the contract's `Transition` checks its limits, so a garbage one is refused with 422 and nothing starts (ruling 14, Review Focus 4). The same model carries a look's transition in `POST` and `PUT /looks` and in a preview, so those refuse it too. A running zone serves its transition, `{from, kind, progress, durationS}` (ruling 15), and the `running` channel already pushes on every `ZonesChanged`: a start, and Task 7's midpoint and end. Backups carry the modifiers and transitions inside the looks and assignments they already hold (ruling 18); a test pins the round trip.

The generated `RunningZone` transition now needs `durationS`, so the web app follows in this task: `contract.ts` names what M4 serves (F1's decision 6: the milestone that serves a type makes it the generated alias), the mock plays a start's transition as the engine now does, and its `transition` scenario gets a length.

**Files:**
- Modify: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_zones.py`, `web/src/api/generated/*` (generated), `web/src/api/contract.ts`, `web/src/api/mocks/mock-server.ts`, `web/src/api/mocks/scenarios.ts`
- Test: `tests/web/test_zones_api.py`, `tests/web/test_ws_channels.py`, `tests/web/test_backup_api.py`, `web/src/api/contract.test.ts`, `web/src/api/mocks/mock-server.test.ts`, `web/src/api/mocks/scenarios.test.ts`

**Interfaces:**
- Consumes: Task 8's `ZoneManager.start(zone_id, look, transition)`; Task 7's `RunningZoneInfo.transition` (`TransitionInfo`) and `ZoneState`; `MAX_TRANSITION_S`; the generated schemas Tasks 3 and 4 added (`HeightMask`, `RoomMask`, `SubZoneMask`, `AnchorMask`, `Mirror`, `Transform`).
- Produces:
  - `web.contract.Transition`: `kind` (a `TransitionKind`, `"cut"` by default) and `duration_s` (`durationS`), finite, from 0 to `MAX_TRANSITION_S`.
  - `web.contract.transition_in(body: Transition | None) -> looks.Transition | None`: None plays the look's own.
  - `RunningZoneTransition`: `from`, `kind`, `progress` and `duration_s` (`durationS`); `RunningZone.state: ZoneState`, `transition` set while the state is `transition`, its `progress` rounded to three places.
  - The router passes `api.transition_in(body.transition)` to `start()`.
  - `web/src/api/contract.ts`: `HeightMask`, `RoomMask`, `SubZoneMask`, `AnchorMask`, `Mask`, `Mirror`, `Transform` and `RunningZoneTransition`, the generated types.
  - The mock (`MockServer`): a start plays the transition it asks for, or else the look's own, as a `transition` state that ends after `durationS` and pushes `running` as it ends; the `transition` scenario's zone has `durationS: 3`.

- [ ] **Step 1: Write the failing tests**

In `tests/web/test_zones_api.py`:

```diff
--- a/tests/web/test_zones_api.py
+++ b/tests/web/test_zones_api.py
@@ -1,9 +1,12 @@
 from __future__ import annotations

+import json
 from collections.abc import AsyncIterator
 from datetime import UTC, datetime
 from pathlib import Path
+from typing import Any

+import pytest
 import pytest_asyncio
 from api_home import Api, api_home
 from conftest import FakeLight
@@ -172,3 +175,43 @@ def test_a_running_zone_says_which_rooms_it_covers() -> None:
         covers=("Kitchen", "Bedroom"),
     )
     assert running_zone_out(info, LightIndex(())).covers == ["Kitchen", "Bedroom"]
+
+
+async def test_a_start_plays_the_transition_it_asks_for(api: Api) -> None:
+    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
+
+    resp = await api.client.post(
+        "/api/zones/desk/start",
+        json={"lookId": "classic-strobe", "transition": {"kind": "fade", "durationS": 2.0}},
+    )
+
+    assert resp.status_code == 200
+    assert resp.json()["state"] == "transition"
+    expected = {"from": "Breathe", "kind": "fade", "progress": 0.0, "durationS": 2.0}
+    assert resp.json()["transition"] == expected
+    [zone] = (await api.client.get("/api/running")).json()["zones"]
+    assert zone["transition"] == expected
+
+
+# Review Focus 4: a garbage transition is refused with the reason, and nothing starts.
+@pytest.mark.parametrize(
+    ("transition", "says"),
+    [
+        ({"kind": "melt", "durationS": 1.0}, "melt"),
+        ({"kind": "fade", "durationS": -1.0}, "greater than or equal to 0"),
+        ({"kind": "fade", "durationS": 11.0}, "less than or equal to 10"),
+        ({"kind": "fade", "durationS": float("nan")}, "nan"),
+        ({"kind": "fade", "durationS": float("inf")}, "inf"),
+    ],
+)
+async def test_a_garbage_transition_is_refused_and_nothing_starts(
+    api: Api, transition: dict[str, Any], says: str
+) -> None:
+    body = json.dumps({"lookId": "classic-breathe", "transition": transition})
+
+    resp = await api.client.post(
+        "/api/zones/desk/start", content=body, headers={"content-type": "application/json"}
+    )
+
+    assert resp.status_code == 422 and says in str(resp.json()["detail"])
+    assert (await api.client.get("/api/running")).json()["zones"] == []
```

In `tests/web/test_ws_channels.py`:

```diff
--- a/tests/web/test_ws_channels.py
+++ b/tests/web/test_ws_channels.py
@@ -85,6 +85,17 @@ async def test_running_zones_are_pushed_when_they_change(api: Api, socket: FakeS
     assert message["overlays"] == []


+async def test_a_transition_is_pushed_as_it_starts(api: Api, socket: FakeSocket) -> None:
+    body = {"lookId": "classic-breathe", "transition": {"kind": "fade", "durationS": 2.0}}
+    await api.client.post("/api/zones/desk/start", json=body)
+    await until(lambda: bool(socket.on("running")))
+
+    [message] = socket.on("running")
+    [zone] = message["zones"]
+    assert zone["state"] == "transition"
+    assert zone["transition"] == {"from": "", "kind": "fade", "progress": 0.0, "durationS": 2.0}
+
+
 async def test_changes_that_arrive_together_are_pushed_once(api: Api, socket: FakeSocket) -> None:
     api.home.bus.emit(ZonesChanged())
     api.home.bus.emit(ZonesChanged())
```

In `tests/web/test_backup_api.py`:

```diff
--- a/tests/web/test_backup_api.py
+++ b/tests/web/test_backup_api.py
@@ -10,7 +10,14 @@ from api_home import Api, api_home
 from conftest import FakeLight
 from map_home import IN_THE_DESK_CORNER, tiny_home

-from dj_ledfx.looks.model import Look
+from dj_ledfx.looks.model import (
+    HeightMask,
+    Look,
+    LookModifiers,
+    Mirror,
+    Transform,
+    Transition,
+)
 from dj_ledfx.zones.model import ZoneRecord

 DESK = ZoneRecord(id="desk", name="Desk", lights=("a",))
@@ -45,6 +52,38 @@ async def test_restore_brings_back_zones_looks_stars_and_what_ran(tmp_path: Path
         assert [p["name"] for p in await new.home.db.load_presets()] == ["Slow"]


+# Spec §2: each milestone extends backup and restore to the data it adds. M4's lives in the
+# looks: their layer modifiers, look modifiers and transitions.
+async def test_a_backup_carries_a_looks_modifiers_and_transition(tmp_path: Path) -> None:
+    (tmp_path / "old").mkdir()
+    (tmp_path / "new").mkdir()
+    async with api_home(tmp_path / "old", [FakeLight("a")], [DESK]) as old:
+        breathe = _mine(old)
+        layer = replace(
+            breathe.layers[0],
+            mask=HeightMask(0.5, 1.5),
+            mirror=Mirror("y", 2.0),
+            transform=Transform(offset=(1.0, 0.0, 0.0), rotate_deg=45.0, scale=2.0),
+        )
+        mine = await old.home.looks.create(
+            replace(
+                breathe,
+                layers=(layer,),
+                modifiers=LookModifiers(0.5, True, 0.6, True),
+                transition=Transition(kind="dissolve", duration_s=3.0),
+            )
+        )
+        backup = (await old.client.get("/api/state/export")).text
+
+    async with api_home(tmp_path / "new", [FakeLight("a")], []) as new:
+        resp = await new.client.post("/api/state/import", content=backup)
+
+        assert resp.status_code == 200
+        restored = new.home.looks.get(mine.id)
+        assert restored.layers == mine.layers
+        assert (restored.modifiers, restored.transition) == (mine.modifiers, mine.transition)
+
+
 # B6: a restored look is applied as a start is: its lights end up on and running.
 async def test_restored_looks_switch_their_lights_on_and_run(tmp_path: Path) -> None:
     lamp = FakeLight("a", power=False)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/web/test_zones_api.py tests/web/test_ws_channels.py tests/web/test_backup_api.py tests/web/test_openapi_types.py -q`
Expected: FAIL: 6 failed, 34 passed: the start plays a cut (`assert 'running' == 'transition'`, twice), and the four garbage transitions get 200 where 422 is expected. The backup test passes already: the modifiers and transitions ride inside the looks.

- [ ] **Step 3: The transition in the contract and the start route**

`src/dj_ledfx/web/contract.py`:

```diff
--- a/src/dj_ledfx/web/contract.py
+++ b/src/dj_ledfx/web/contract.py
@@ -28,6 +28,7 @@ from dj_ledfx.looks import model as looks
 from dj_ledfx.looks.model import (
     MAX_SCALE,
     MAX_TRAILS_S,
+    MAX_TRANSITION_S,
     MIN_SCALE,
     Blend,
     Category,
@@ -179,8 +180,11 @@ class LookModifiers(ContractModel):


 class Transition(ContractModel):
+    """How a look comes in (engine spec §5.3): a cut, or a fade, wipe, spread or dissolve
+    over `durationS` seconds, at most 10."""
+
     kind: TransitionKind = "cut"
-    duration_s: float = 0.0
+    duration_s: float = Field(default=0.0, ge=0.0, le=MAX_TRANSITION_S, allow_inf_nan=False)


 class Look(ContractModel):
@@ -213,6 +217,11 @@ def look_in(body: Look) -> looks.Look:
     return looks.look_from_dict(body.model_dump(by_alias=True))


+def transition_in(body: Transition | None) -> looks.Transition | None:
+    """A start's transition as the engine plays it; None: the look's own."""
+    return None if body is None else looks.Transition(kind=body.kind, duration_s=body.duration_s)
+
+
 # --- zones -------------------------------------------------------------------------


@@ -224,9 +233,15 @@ class Zone(ContractModel):


 class RunningZoneTransition(ContractModel):
+    """A zone's transition while it plays: the look it replaces ("" when its lights were
+    idle), the kind, how far it has got (0..1) when this was sent, and how long it takes in
+    all, so a client moves the bar on by itself. The running channel pushes it as the
+    transition starts, at its midpoint and as it ends."""
+
     from_: str = Field(alias="from")
     kind: TransitionKind
     progress: float
+    duration_s: float


 class RunningZoneFps(ContractModel):
@@ -249,8 +264,8 @@ class RunningZone(ContractModel):
     lights: list[str]  # the lights it owns after take-overs
     # the rooms it still covers, by name, in map order
     covers: list[str] = Field(default_factory=list)
-    state: Literal[ZoneState, "transition"]  # transitions arrive in M4
-    transition: RunningZoneTransition | None = None  # transitions arrive in M4
+    state: ZoneState
+    transition: RunningZoneTransition | None = None  # while its state is "transition"
     fps: RunningZoneFps | None = None
     error: RunningZoneError | None = None
     waiting_for: list[InputKind] | None = None
@@ -292,7 +307,7 @@ class RecentLook(ContractModel):
 class StartRequest(ContractModel):
     look_id: str | None = None
     look: Look | None = None  # an unsaved draft
-    transition: Transition | None = None  # accepted; M1 plays every transition as a cut
+    transition: Transition | None = None  # None: the look's own


 class StartResponse(RunningZone):
@@ -326,6 +341,14 @@ def _running_fields(info: RunningZoneInfo, index: LightIndex) -> dict[str, Any]:
     error = None
     if info.error is not None:
         error = {"layer": info.error.layer, "message": info.error.message, "at": info.error.at}
+    transition = None
+    if info.transition is not None:
+        transition = {
+            "from": info.transition.from_name,
+            "kind": info.transition.kind,
+            "progress": round(info.transition.progress, 3),
+            "duration_s": info.transition.duration_s,
+        }
     return {
         "zone_id": info.zone_id,
         "look_id": info.look_id,
@@ -335,6 +358,7 @@ def _running_fields(info: RunningZoneInfo, index: LightIndex) -> dict[str, Any]:
         "lights": list(index.collapse(info.lights)),
         "covers": list(info.covers),
         "state": info.state,
+        "transition": transition,
         "fps": fps,
         "error": error,
         "waiting_for": list(info.waiting_for) or None,
```

`src/dj_ledfx/web/router_zones.py`:

```diff
--- a/src/dj_ledfx/web/router_zones.py
+++ b/src/dj_ledfx/web/router_zones.py
@@ -69,10 +69,11 @@ async def list_recent(request: Request) -> list[api.RecentLook]:

 @router.post("/zones/{zone_id}/start")
 async def start_zone(request: Request, zone_id: str, body: api.StartRequest) -> api.StartResponse:
-    """Put a look on a zone: a saved look by id, or an unsaved draft."""
+    """Put a look on a zone: a saved look by id, or an unsaved draft, with the transition
+    given, or else the look's own."""
     with answers():
         look = requested_look(request, body.look_id, body.look)
-        result = await get_zones(request).start(zone_id, look)
+        result = await get_zones(request).start(zone_id, look, api.transition_in(body.transition))
     return api.start_out(result, light_index(request.app))


```

- [ ] **Step 4: Regenerate the API types**

```bash
(cd web && npm run api:types)
git status --short web
(cd web && npx tsc -b 2>&1 | grep "error TS")
```

Expected: only the two files under `web/src/api/generated/` changed, and `tsc -b` reports one error, `src/api/mocks/scenarios.ts(355,7): error TS2741: Property 'durationS' is missing ...` (the line may differ if F3 has merged): the `transition` scenario's running zone has no length. Step 6 gives it one. If F3 has merged and `tsc -b` names F3's code too, give each running zone's transition it builds (in tests and fixtures) a `durationS` of 3, as the scenario has; F3's components only read it.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/web/test_zones_api.py tests/web/test_ws_channels.py tests/web/test_backup_api.py tests/web/test_openapi_types.py -q`
Expected: PASS (40 tests).

- [ ] **Step 6: Name what M4 serves, and make the mock play transitions**

In `web/src/api/contract.ts`, a section for what engine M4 serves, after engine M3's:

```diff
--- a/web/src/api/contract.ts
+++ b/web/src/api/contract.ts
@@ -107,6 +107,18 @@ export type TapRequest = Schemas['TapRequest']
 /** POST /inputs/tempo/nudge: a phase shift in beats, -1 to 1; positive brings the beat sooner. */
 export type NudgeRequest = Schemas['NudgeRequest']

+// ── Served since engine M4 (modifiers and transitions) ───────────────────────────────────
+/** A layer modifier: where the layer shows (§12.2's mask), and how its field is moved. */
+export type HeightMask = Schemas['HeightMask']
+export type RoomMask = Schemas['RoomMask']
+export type SubZoneMask = Schemas['SubZoneMask']
+export type AnchorMask = Schemas['AnchorMask']
+export type Mask = NonNullable<Layer['mask']>
+export type Mirror = Schemas['Mirror']
+export type Transform = Schemas['Transform']
+/** A running zone's transition: `durationS` lets the bar move on between the running channel's pushes. */
+export type RunningZoneTransition = Schemas['RunningZoneTransition']
+
 // ── Pending: engine M6/M7 (Music Assistant, Home Assistant, the sun, signals) ─────────────
 // Shaped from §12.3–12.4, §9.3 and the Inputs renders; the milestone that serves them owns the
 // final shape (decision 6).
```

In `web/src/api/contract.test.ts`:

```diff
--- a/web/src/api/contract.test.ts
+++ b/web/src/api/contract.test.ts
@@ -1,8 +1,8 @@
 import { describe, expectTypeOf, it } from 'vitest'
 import type { components, paths } from './generated/schema'
 import type {
-  ApiPath, Deck, Furniture, Home, InputKind, InputState, Light, LightShape, LightStatus, Location, PendingPath,
-  PendingSchema, Room, RunningZone, TempoLock, TempoSource,
+  ApiPath, Deck, Furniture, Home, InputKind, InputState, Light, LightShape, LightStatus, Location, Mask, PendingPath,
+  PendingSchema, Room, RunningZone, RunningZoneTransition, TempoLock, TempoSource,
 } from './contract'

 describe('the contract', () => {
@@ -56,6 +56,16 @@ describe('the contract', () => {
     expectTypeOf<InputState>().toEqualTypeOf<'connected' | 'stale' | 'disconnected' | 'idle'>()
   })

+  // Engine M4 serves the layer modifiers, and a running zone's transition with its length.
+  it("serves engine M4's modifiers and transitions", () => {
+    expectTypeOf<
+      'HeightMask' | 'RoomMask' | 'SubZoneMask' | 'AnchorMask' | 'Mirror' | 'Transform' | 'RunningZoneTransition'
+    >().toExtend<keyof components['schemas']>()
+    expectTypeOf<Mask['kind']>().toEqualTypeOf<'height' | 'room' | 'sub-zone' | 'anchor'>()
+    expectTypeOf<NonNullable<RunningZone['transition']>>().toEqualTypeOf<RunningZoneTransition>()
+    expectTypeOf<RunningZoneTransition['durationS']>().toEqualTypeOf<number>()
+  })
+
   // I1: engine M2 serves the home's size and which rooms hold lights.
   it("carries the home's size and each room's hasLights", () => {
     expectTypeOf<Home['size']>().toEqualTypeOf<{ eastWest: number; northSouth: number }>()
```

The mock plays a start's transition as engine M4 does: the one the start asks for, or else the look's own. `from` is the zone's own look before, or the first look it took lights from: engine M4 names the look that drove most of the lights, and the mock has no LEDs to count. In `web/src/api/mocks/mock-server.ts`:

```diff
--- a/web/src/api/mocks/mock-server.ts
+++ b/web/src/api/mocks/mock-server.ts
@@ -7,8 +7,8 @@ import {
   STREAMED,
   type AnchorIn, type ApiPath, type CreateGroup, type FrameStream, type HomeSettings, type Id, type Inputs, type Light,
   type LightShape, type LightUpdate, type Look, type PendingPath, type Placement, type PlacementIn, type PreviewRequest,
-  type PreviewUpdate, type RecentLook, type RunningZone, type StartRequest, type SubZoneIn, type TakeOver, type UpdateGroup,
-  type Zone,
+  type PreviewUpdate, type RecentLook, type RunningZone, type StartRequest, type SubZoneIn, type TakeOver, type Transition,
+  type UpdateGroup, type Zone,
 } from '../contract'
 import { encodeFrame, type FrameVersion } from '../frames'
 import { PATH_PARAM } from '../rest'
@@ -250,6 +250,8 @@ export class MockServer {
   private readonly seqs: Record<FrameStream, Map<Id, number>> = { live: new Map(), preview: new Map() }
   /** When each light's placement was confirmed; the seed's confirmed lights have no time. */
   private readonly confirmedAt = new Map<Id, string>()
+  /** The zones a start's transition plays on, and when each one's ends (clock ms), as engine M4 plays them. */
+  private readonly transitionsEnd = new Map<Id, number>()
   private frameCount = 0
   private nextFrameAt: number
   private nextStatsAt: number
@@ -419,6 +421,7 @@ export class MockServer {
       this.nextLightsAt += LIGHTS_MS
       this.readLightsBack(now)
     }
+    this.endTransitions(now)
     if (now >= this.nextStatusAt) {
       this.nextStatusAt += STATUS_MS
       this.broadcast({
@@ -431,6 +434,18 @@ export class MockServer {
     }
   }

+  /** A transition that has run its time ends: the zone runs its look, and the running channel says so. */
+  private endTransitions(now: number): void {
+    for (const [zoneId, endsAt] of this.transitionsEnd) {
+      if (now < endsAt) continue
+      this.transitionsEnd.delete(zoneId)
+      const zone = this.state.running.find((candidate) => candidate.zoneId === zoneId)
+      if (zone?.state !== 'transition') continue
+      Object.assign(zone, { state: 'running', transition: null } satisfies Partial<RunningZone>)
+      this.changed('running')
+    }
+  }
+
   private signals(now: number, names: string[]): ServerMessage {
     const at = position(this.state, this.beatElapsedS(now))
     const live: Record<string, number> = { 'beat.phase': at % 1, 'bar.phase': (at % 4) / 4, bpm: this.state.beat.bpm }
@@ -764,10 +779,12 @@ export class MockServer {

   /** §11.3: the zone takes its lights from any running zone; a zone left with none stops. */
   private startLook(zoneId: Id, body: StartRequest): MockReply {
-    return this.withZone(zoneId, (zone) => this.withLookFor(body, (look) => this.takeOver(zone, look)))
+    return this.withZone(zoneId, (zone) =>
+      this.withLookFor(body, (look) => this.takeOver(zone, look, body.transition ?? look.transition)),
+    )
   }

-  private takeOver(zone: Zone, look: Look): MockReply {
+  private takeOver(zone: Zone, look: Look, transition: Transition | undefined): MockReply {
     const taking = new Set(zone.lights)
     const takeOvers: TakeOver[] = []
     const stopped: RunningZone[] = []
@@ -793,6 +810,18 @@ export class MockServer {
       brightness: previous?.brightness ?? 1,
       lights: zone.lights,
     })
+    this.transitionsEnd.delete(zone.id)
+    const kind = transition?.kind ?? 'cut'
+    const durationS = transition?.durationS ?? 0
+    if (kind !== 'cut' && durationS > 0) {
+      // Engine M4 names the look that drove most of the lights; the mock, the zone's own or the first it took from.
+      const from = previous?.lookName ?? takeOvers[0]?.lookName ?? ''
+      Object.assign(running, {
+        state: 'transition',
+        transition: { from, kind, progress: 0, durationS },
+      } satisfies Partial<RunningZone>)
+      this.transitionsEnd.set(zone.id, this.clock() + durationS * 1000)
+    }
     this.state.running.push(running)
     this.changed('running', 'lights')
     return ok({ ...running, takeOvers })
```

In `web/src/api/mocks/mock-server.test.ts`:

```diff
--- a/web/src/api/mocks/mock-server.test.ts
+++ b/web/src/api/mocks/mock-server.test.ts
@@ -214,6 +214,26 @@ describe('the REST API', () => {
     expect(socket.json().map((message) => message.channel)).toEqual(['running', 'lights'])
   })

+  it('plays the transition a start asks for, then runs the look, as engine M4 does', () => {
+    const server = startMockServer()
+    const socket = connect(server)
+    const transition = { kind: 'fade', durationS: 2 } as const
+    const reply = server.handle('POST', '/api/zones/bedroom/start', { lookId: 'sunset', transition })
+    expect(reply.body).toMatchObject({ state: 'transition', transition: { kind: 'fade', progress: 0, durationS: 2 } })
+    socket.clear()
+    vi.advanceTimersByTime(2100)
+    expect(server.state.running.find((zone) => zone.zoneId === 'bedroom')).toMatchObject({ state: 'running', transition: null })
+    expect(socket.json().map((message) => message.channel)).toContain('running')
+  })
+
+  it("plays the look's own transition when a start asks for none", () => {
+    const server = startMockServer()
+    const sunset = server.handle('GET', '/api/looks/sunset').body as Look
+    const look = { ...sunset, transition: { kind: 'wipe', durationS: 1 } } satisfies Look
+    const reply = server.handle('POST', '/api/zones/bedroom/start', { look })
+    expect(reply.body).toMatchObject({ state: 'transition', transition: { kind: 'wipe', durationS: 1 } })
+  })
+
   it('turns a zone off again and again, and says 404 for a zone it does not know', () => {
     const server = startMockServer()
     expect(server.handle('POST', '/api/zones/living/off').status).toBe(204)
```

The `transition` scenario's running zone gets its length. In `web/src/api/mocks/scenarios.ts`:

```diff
--- a/web/src/api/mocks/scenarios.ts
+++ b/web/src/api/mocks/scenarios.ts
@@ -352,7 +352,7 @@ const BUILD: Record<ScenarioName, (state: ScenarioState, now: Date) => void> = {
       lookId: 'embers',
       lookName: lookName('embers'),
       state: 'transition',
-      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62 },
+      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62, durationS: 3 },
     } satisfies Partial<RunningZone>)
   },
   problems(state, now) {
```

In `web/src/api/mocks/scenarios.test.ts`:

```diff
--- a/web/src/api/mocks/scenarios.test.ts
+++ b/web/src/api/mocks/scenarios.test.ts
@@ -120,7 +120,7 @@ describe('the other scenarios', () => {
     expect(living).toMatchObject({
       lookId: 'embers',
       state: 'transition',
-      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62 },
+      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62, durationS: 3 },
     })
   })

```

- [ ] **Step 7: Run the web gate**

```bash
(cd web && npm run api:check && npm test && npx tsc -b && npm run lint && npm run build)
ss -ltn | grep -cE ':(4174|4175) '
```

If the `ss` count isn't `0`, another worktree is running e2e: wait until both ports are free (Global Constraints), then:

```bash
(cd web && npx playwright install chromium && npm run e2e)
```

Expected: every step passes; the web tests are Before Task 1's count plus 3 (537 on `98ecbee`), and e2e has 60 passed and 20 skipped on `98ecbee`. The screenshots don't change: the scenario's zone shows the same progress.

- [ ] **Step 8: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/web/contract.py src/dj_ledfx/web/router_zones.py tests/web/test_zones_api.py tests/web/test_ws_channels.py tests/web/test_backup_api.py
uv run ruff check --fix src/dj_ledfx/web/contract.py src/dj_ledfx/web/router_zones.py tests/web/test_zones_api.py tests/web/test_ws_channels.py tests/web/test_backup_api.py
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/web/contract.py src/dj_ledfx/web/router_zones.py web/src/api tests/web/test_zones_api.py tests/web/test_ws_channels.py tests/web/test_backup_api.py
git commit -m "feat(web): a start's transition, the running zone's with its length, and the mock playing them"
```

---


### Task 10: Check it on this home

Two checks, in order, as M3's Task 15 ran them (spec §9: "a short checklist run on the real lights; preview-only mode allows a dry run first"). The dry run starts the branch on a snapshot of the deployed app's `state.db`, with discovery off, so the home's real lights are offline ghosts and nothing reaches one. Pro DJ Link listens on a loopback port, so the deployed app keeps UDP 50001. The dry run rehearses the deploy (the first start on real data: the running zones resume, with no transition), reads the home's location and the evening there, previews the layer and look modifiers on the room with the most lights, and plays every kind of transition on that room with preview-only on. The second check puts them on the real lights with the owner watching. Each step that touches the deployed container or the lights asks the owner first and goes on only with a yes.

Report only counts and yes/no results, in the PR and anywhere else: no light ids (they hold MACs), no addresses, no model names, and never the home's location. The probe prints whether the stored location is still the handoff's, never the coordinates.

The branch serves on a port of its own, since the deployed app holds 8080 and 8081 belongs to another service. Each shell this task opens starts from the same two values, set once in a file:

```bash
printf 'PORT=8098\nW=/home/anirudhlath/code/.worktrees/dj-ledfx/m4-modifiers\n' > /tmp/m4-live.env
. /tmp/m4-live.env && ss -ltn | grep -c ":$PORT "
```

Expected: `0`, the port is free. Every block below starts with `. /tmp/m4-live.env`.

If the branch stops answering, or is still running 15 s after a Ctrl-C (`kill -INT`), run `kill -USR1 "$(pgrep -n -f /tmp/m4-dry/run.py)"` first (the dry-run driver then writes every thread's stack into its log), then `kill -9` the same process, and tell the owner.

**Files:**
- Create (outside the repo): `/tmp/m4-live.env`, `/tmp/m4-dry/run.py`, `/tmp/m4-wait.py`, `/tmp/m4-probe.py`, `/tmp/m4-show.py`

- [ ] **Step 1: Snapshot the deployed state (read-only), with the owner's yes**

Ask the owner first: this runs one read-only process in the deployed container, which changes nothing there and touches no light. Go on only with a yes.

```bash
. /tmp/m4-live.env && cd "$W"
mkdir -p /tmp/m4-dry && rm -f /tmp/m4-dry/state.db
docker exec dj-ledfx-app-1 python -c "import sqlite3, sys; db = sqlite3.connect('file:/app/state/state.db?mode=ro', uri=True); sys.stdout.write('\n'.join(db.iterdump()))" > /tmp/m4-dry/dump.sql
uv run python -c "import sqlite3; db = sqlite3.connect('/tmp/m4-dry/state.db'); db.executescript(open('/tmp/m4-dry/dump.sql').read()); db.close()"
uv run python -c "import sqlite3; db = sqlite3.connect('/tmp/m4-dry/state.db'); print(db.execute('select count(*) from devices').fetchone(), db.execute('select count(*) from zone_assignments').fetchone())"
```

Expected: the device count the deployed app knows, and the number of zones it has running (`curl -s http://127.0.0.1:8080/api/running | uv run python -c "import json, sys; print(len(json.load(sys.stdin)['zones']))"`).

- [ ] **Step 2: Write the scripts**

`/tmp/m4-dry/run.py`, the real entry point with discovery off:

```python
import faulthandler
import signal
import sys

import dj_ledfx.main
from dj_ledfx.devices.backend import DeviceBackend

faulthandler.register(signal.SIGUSR1, all_threads=True)  # kill -USR1: every thread's stack
DeviceBackend._registry.clear()  # no discovery: every light stays an offline ghost
sys.argv = ["dj_ledfx", *sys.argv[1:]]
dj_ledfx.main.main()
```

`/tmp/m4-wait.py`, which waits for an app to answer or for a process to end, so no shell loop has to sleep:

```python
"""Wait for an app: `m4-wait.py URL SECONDS` until the URL answers, `m4-wait.py --gone PID
SECONDS` until the process has ended. Exits 1 if the time runs out."""

import os
import sys
import time
import urllib.request


def answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:  # another user's process: still there
        return False
    return False


if sys.argv[1] == "--gone":
    ready, what = (lambda: gone(int(sys.argv[2]))), "ended"
else:
    ready, what = (lambda: answers(sys.argv[1])), "answering"
end = time.monotonic() + float(sys.argv[-1])
while not ready():
    if time.monotonic() > end:
        print(f"not {what} after {sys.argv[-1]} s")
        sys.exit(1)
    time.sleep(0.5)
print(what)
```

`/tmp/m4-probe.py`, which reads, previews (a preview never reaches a light) and plays transitions with preview-only on. It imports the branch's `evening_amount` and the seed's location to compare, so it runs from `$W`:

```python
"""M4 probe: the home's location and the evening; layer and look modifiers on previews; and
transitions on the room with the most lights, with preview-only on. Nothing reaches a
light. It prints counts and yes or no: no ids, names, addresses or coordinates."""

import asyncio
import copy
import json
import struct
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

from dj_ledfx.home.seed import handoff_home_json
from dj_ledfx.home.sun import evening_amount

BASE = sys.argv[1]  # the branch: http://127.0.0.1:$PORT
LIT = 8  # a byte above this is a lit channel
Frames = dict[str, list[bytes]]  # each light's preview frames, oldest first


def call(method: str, path: str, body: object = None) -> tuple[int, Any]:
    """The status and the body: an error status is an answer too."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{BASE}/api{path}", data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status, text = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read()
    try:
        return status, json.loads(text) if text else None
    except ValueError:
        return status, text.decode(errors="replace")


def ok(method: str, path: str, body: object = None) -> Any:
    status, answer = call(method, path, body)
    if status >= 300:
        sys.exit(f"{method} {path} answered {status}: {answer}")
    return answer


def running(zone_id: str) -> dict[str, Any] | None:
    return next((z for z in ok("GET", "/running")["zones"] if z["zoneId"] == zone_id), None)


def start(zone_id: str, look_id: str, transition: dict[str, Any] | None = None) -> tuple[int, Any]:
    body: dict[str, Any] = {"lookId": look_id}
    if transition is not None:
        body["transition"] = transition
    return call("POST", f"/zones/{zone_id}/start", body)


async def listen(ws: ClientConnection, seconds: float) -> tuple[Frames, list[dict[str, Any]]]:
    """Every message on the socket for a while: the preview frames, and the JSON ones."""
    frames: Frames = {}
    messages: list[dict[str, Any]] = []
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        try:
            message = await asyncio.wait_for(ws.recv(), left)
        except TimeoutError:
            break
        if isinstance(message, bytes):
            if message[0] == 0x02:  # protocol 2's preview stream
                (id_len,) = struct.unpack_from("<H", message, 1)
                light_id = message[3 : 3 + id_len].decode()
                frames.setdefault(light_id, []).append(message[3 + id_len + 4 :])
        else:
            messages.append(json.loads(message))
    return frames, messages


async def answer(ws: ClientConnection, command_id: str) -> dict[str, Any]:
    async with asyncio.timeout(5):
        while True:
            message = await ws.recv()
            if isinstance(message, str) and json.loads(message).get("id") == command_id:
                return json.loads(message)


async def preview(ws: ClientConnection, zone_id: str, draft: dict[str, Any]) -> Frames:
    started = ok("POST", "/preview", {"zoneId": zone_id, "look": draft})
    await listen(ws, 0.3)  # the last preview's frames still on their way
    frames, _ = await listen(ws, 2.0)
    ok("DELETE", f"/preview/{started['previewId']}")
    return frames


def lit_leds(payload: bytes) -> int:
    return sum(max(payload[k : k + 3]) > LIT for k in range(0, len(payload), 3))


def lit_lights(frames: Frames) -> int:
    return sum(any(lit_leds(payload) for payload in payloads) for payloads in frames.values())


def most_lit_leds(frames: Frames) -> int:
    return sum(max(map(lit_leds, payloads), default=0) for payloads in frames.values())


def brightest(frames: Frames) -> int:
    return max((max(payload, default=0) for p in frames.values() for payload in p), default=0)


def moving(frames: Frames) -> int:
    return sum(len(set(payloads)) > 10 for payloads in frames.values())


def drafted(look: dict[str, Any], modifiers: dict[str, Any] | None = None, **layer: Any) -> dict[str, Any]:
    """The look as an unsaved draft: the layer modifiers on each streamed layer (a firmware
    layer takes none), and the look modifiers given."""
    draft = copy.deepcopy(look)
    for each in draft["layers"]:
        if each["type"] != "firmware":
            each.update(layer)
    if modifiers is not None:
        draft["modifiers"] = {**draft["modifiers"], **modifiers}
    return draft


def pushes(messages: list[dict[str, Any]], zone_id: str) -> list[tuple[str, float | None]]:
    """The running channel's pushes of one zone: its state, and its transition's progress."""
    seen = []
    for message in messages:
        if message.get("channel") != "running":
            continue
        for zone in message["zones"]:
            if zone["zoneId"] == zone_id:
                moved = zone["transition"]["progress"] if zone["transition"] else None
                seen.append((zone["state"], moved))
    return seen


async def main() -> None:
    resumed = ok("GET", "/running")["zones"]
    print(f"zones resumed at start: {len(resumed)}, none in a transition: {all(z['state'] != 'transition' for z in resumed)}")
    home = ok("GET", "/home")
    place, seed = home.get("location"), handoff_home_json()["location"]
    print("the home has a location:", place is not None)
    if place is not None:
        print("still the handoff's assumed location:", (place["lat"], place["lon"]) == (seed["lat"], seed["lon"]))
        print("confirmed by the owner:", place["confirmed"])
        print(f"the evening there now: {evening_amount(place['lat'], place['lon'], datetime.now(UTC)):.2f}")

    zones = ok("GET", "/zones")
    room = max((z for z in zones if z["kind"] == "room"), key=lambda z: len(z["lights"]))
    other = next(r for r in home["rooms"] if r["id"] != room["id"])
    print(f"the room with the most lights: {len(room['lights'])} lights")
    rainbow, aurora = ok("GET", "/looks/classic-rainbow-wave"), ok("GET", "/looks/aurora")

    # One socket for the whole run, closed once at the end, as M3's probe kept it.
    async with connect(BASE.replace("http", "ws", 1) + "/ws", max_size=None, max_queue=None) as ws:
        await ws.send(json.dumps(
            {"action": "subscribe_frames", "id": "frames", "fps": 60, "protocol": 2, "streams": ["preview"]}
        ))
        await answer(ws, "frames")

        plain = await preview(ws, room["id"], drafted(rainbow))
        print(f"rainbow wave: {lit_lights(plain)} lights lit, {most_lit_leds(plain)} LEDs, brightest {brightest(plain)}")
        own = await preview(ws, room["id"], drafted(rainbow, mask={"kind": "room", "room": room["id"]}))
        print(f"masked to its own room: {lit_lights(own)} lights lit")
        elsewhere = await preview(ws, room["id"], drafted(rainbow, mask={"kind": "room", "room": other["id"]}))
        print(f"masked to another room: {most_lit_leds(elsewhere)} LEDs lit")
        low = await preview(ws, room["id"], drafted(rainbow, mask={"kind": "height", "range": [0.0, 1.0]}))
        print(f"masked to the first metre: {most_lit_leds(low)} LEDs lit")
        capped = await preview(ws, room["id"], drafted(rainbow, {"brightnessCap": 0.2}))
        print(f"capped at 0.2: brightest {brightest(capped)}")
        every = drafted(
            aurora,
            {"trailsS": 1.0, "downbeatFlash": True, "brightnessCap": 0.8, "evening": True},
            mask={"kind": "height", "range": [0.3, 2.0]},
            mirror={"axis": "x", "at": None},
            transform={"offset": [0.5, 0.0, 0.0], "rotateDeg": 30.0, "scale": 1.5},
        )
        busy = await preview(ws, room["id"], every)
        print(f"aurora with every modifier: {moving(busy)} of {len(busy)} lights moving")

        was_preview_only = ok("GET", "/config")["engine"].get("preview_only") is True
        ok("PUT", "/config", {"engine": {"preview_only": True}})
        names = {look_id: ok("GET", f"/looks/{look_id}")["name"] for look_id in ("classic-breathe", "lava")}
        ok("POST", f"/zones/{room['id']}/start", {"lookId": "classic-breathe"})
        await listen(ws, 1.0)
        status, started = start(room["id"], "classic-strobe", {"kind": "fade", "durationS": 4})
        moving_on = started["transition"] or {}
        print(
            "a 4 s fade starts:", status == 200 and started["state"] == "transition",
            "| from the look before:", moving_on.get("from") == names["classic-breathe"],
            "| progress 0:", moving_on.get("progress") == 0,
            "| durationS 4:", moving_on.get("durationS") == 4,
        )
        _, first = await listen(ws, 2.0)
        halfway = running(room["id"])["transition"] or {}
        print(f"2 s in: progress {halfway.get('progress', -1):.2f}")
        _, second = await listen(ws, 2.5)
        after = running(room["id"])
        print("4.5 s in, running with no transition:", after["state"] == "running" and after["transition"] is None)
        print("the running channel's pushes of the zone:", pushes(first + second, room["id"]))

        for kind, look_id in (("wipe", "lava"), ("spread", "aurora"), ("dissolve", "lava")):
            status, started = start(room["id"], look_id, {"kind": kind, "durationS": 2})
            await listen(ws, 2.5)
            after = running(room["id"])
            print(f"a 2 s {kind}: plays {status == 200 and started['state'] == 'transition'}, then runs {after['state'] == 'running'}")

        status, _ = start(room["id"], "aurora", {"kind": "fade", "durationS": 11})
        print(f"an 11 s fade: {status}, the zone unchanged: {running(room['id'])['lookId'] == 'lava'}")

        start(room["id"], "aurora", {"kind": "fade", "durationS": 4})
        await listen(ws, 1.0)
        status, started = start(room["id"], "lava", {"kind": "fade", "durationS": 4})
        print("a start mid-transition plays from the look it interrupted:", (started["transition"] or {}).get("from") == ok("GET", "/looks/aurora")["name"])
        await listen(ws, 4.5)

        start(room["id"], "aurora", {"kind": "fade", "durationS": 4})
        await listen(ws, 1.0)
        status, _ = call("POST", f"/zones/{room['id']}/off")
        print(f"Off mid-transition: {status}, off at once: {running(room['id']) is None}")
        await listen(ws, 3.0)
        print("still off after the midpoint:", running(room["id"]) is None)

        start(room["id"], "lava", {"kind": "dissolve", "durationS": 4})
        await listen(ws, 1.0)
        status, _ = call("POST", "/running/stop-all")
        await listen(ws, 3.0)
        print(f"Stop all mid-transition: {status}, nothing running after the midpoint: {ok('GET', '/running')['zones'] == []}")

        ok("PUT", "/config", {"engine": {"preview_only": was_preview_only}})


asyncio.run(main())
```

`/tmp/m4-show.py`, for Step 5, one step on the real lights at a time:

```python
"""M4 on the real lights, one step at a time: `m4-show.py BASE STEP`. Each step starts a
look on the room with the most lights (or the whole home), says what to look for, and
leaves it running. It prints counts and yes or no only."""

import copy
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from dj_ledfx.home.sun import evening_amount

BASE, STEP = sys.argv[1], sys.argv[2]  # the branch: http://127.0.0.1:$PORT


def call(method: str, path: str, body: object = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{BASE}/api{path}", data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status, text = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read()
    return status, json.loads(text) if text else None


def ok(method: str, path: str, body: object = None) -> Any:
    status, answer = call(method, path, body)
    if status >= 300:
        sys.exit(f"{method} {path} answered {status}: {answer}")
    return answer


def drafted(look_id: str, modifiers: dict[str, Any] | None = None, **layer: Any) -> dict[str, Any]:
    """A built-in look as an unsaved draft, with layer modifiers on its streamed layers."""
    draft = copy.deepcopy(ok("GET", f"/looks/{look_id}"))
    for each in draft["layers"]:
        if each["type"] != "firmware":
            each.update(layer)
    if modifiers is not None:
        draft["modifiers"] = {**draft["modifiers"], **modifiers}
    return draft


def start(zone_id: str, look: str | dict[str, Any], transition: dict[str, Any] | None = None) -> Any:
    body: dict[str, Any] = {"lookId": look} if isinstance(look, str) else {"look": look}
    if transition is not None:
        body["transition"] = transition
    return ok("POST", f"/zones/{zone_id}/start", body)


def say(what: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {what}")


zones = ok("GET", "/zones")
ROOM = max((z for z in zones if z["kind"] == "room"), key=lambda z: len(z["lights"]))["id"]
HOME = next(z for z in zones if z["kind"] == "home")["id"]

if STEP == "lights":  # wait for the lights to come online, up to a minute
    for _ in range(60):
        lights = ok("GET", "/lights")
        online = sum(light["status"] == "online" for light in lights)
        if online == len(lights):
            break
        time.sleep(1)
    say(f"{online} of {len(lights)} lights online")
elif STEP == "height":
    start(ROOM, drafted("classic-rainbow-wave", mask={"kind": "height", "range": [0.0, 1.0]}))
    say("the rainbow wave in the first metre above the floor only, fading out over 10 cm above it")
elif STEP == "room-mask":
    start(HOME, drafted("classic-rainbow-wave", mask={"kind": "room", "room": ROOM}))
    say("the whole home runs it, but only the room's lights show it; the rest are dark")
    time.sleep(15)
    status, _ = call("POST", f"/zones/{HOME}/off")
    say(f"the whole home off again ({status}): every light back as it was")
elif STEP == "mirror":
    start(ROOM, drafted("classic-rainbow-wave", mirror={"axis": "x", "at": None}))
    say("the wave mirrored east-west about the room's middle: both halves alike")
elif STEP == "turn":
    start(ROOM, drafted("classic-rainbow-wave", transform={"offset": [0.0, 0.0, 0.0], "rotateDeg": 90.0, "scale": 1.0}))
    say("the wave runs a quarter turn round from the plain look's direction (clockwise, seen from above)")
elif STEP == "trails":
    start(ROOM, drafted("classic-strobe", {"trailsS": 1.5}))
    say("each flash leaves a trail that fades over 1.5 s")
elif STEP == "flash":
    start(ROOM, drafted("classic-rainbow-wave", {"downbeatFlash": True}))
    say("a flash towards white on the first beat of every bar, fading over half a beat")
elif STEP == "cap":
    start(ROOM, drafted("classic-rainbow-wave", {"brightnessCap": 0.3}))
    say("the wave at most 30% bright")
elif STEP == "cap-firmware":
    start(ROOM, drafted("firmware", {"brightnessCap": 0.3}))
    say("the lights running their own effects at most 30% bright too")
elif STEP == "evening":
    place = ok("GET", "/home")["location"]
    amount = 0.0 if place is None else evening_amount(place["lat"], place["lon"], datetime.now(UTC))
    start(ROOM, drafted("classic-rainbow-wave", {"evening": True}))
    say(f"the evening's amount now: {amount:.2f}; at 0 the wave is as it was, above 0 warmer and dimmer")
elif STEP in ("fade", "wipe", "spread", "dissolve"):
    start(ROOM, "lava")
    time.sleep(3)
    say(f"a 6 s {STEP} from lava to aurora starts now")
    start(ROOM, "aurora", {"kind": STEP, "durationS": 6})
    time.sleep(7)
    say("done: aurora alone")
elif STEP == "midpoint":
    start(ROOM, "firmware")
    time.sleep(5)
    say("a 10 s fade to sunset starts now: the lights running their own effect switch whole at 5 s")
    start(ROOM, "sunset", {"kind": "fade", "durationS": 10})
    time.sleep(11)
    say("done: sunset alone")
elif STEP == "interrupt":
    start(ROOM, "lava", {"kind": "fade", "durationS": 6})
    time.sleep(2)
    say("a second 6 s fade, to aurora, starts mid-transition: no jump")
    start(ROOM, "aurora", {"kind": "fade", "durationS": 6})
    time.sleep(7)
    say("done: aurora alone")
elif STEP == "off":
    start(ROOM, "lava", {"kind": "fade", "durationS": 6})
    time.sleep(2)
    status, _ = call("POST", f"/zones/{ROOM}/off")
    say(f"Off mid-transition ({status}): the room's lights go back as they were, and stay so")
    time.sleep(5)
    say(f"still off after the midpoint: {all(z['zoneId'] != ROOM for z in ok('GET', '/running')['zones'])}")
elif STEP == "stop":
    status, _ = call("POST", "/running/stop-all")
    say(f"Stop all ({status}): every light back as it was")
else:
    sys.exit(f"unknown step {STEP}")
```

- [ ] **Step 3: The dry run**

```bash
. /tmp/m4-live.env && cd "$W"
(uv run python /tmp/m4-dry/run.py --dj-listen 127.0.0.1:0 --web --web-host 127.0.0.1 --web-port "$PORT" --config /tmp/m4-dry/config.toml --db /tmp/m4-dry/state.db > /tmp/m4-dry/app.log 2>&1 & echo $! > /tmp/m4-dry/pid)
uv run python /tmp/m4-wait.py "http://127.0.0.1:$PORT/api/running" 60
timeout 300 uv run --with websockets python /tmp/m4-probe.py "http://127.0.0.1:$PORT"
curl -sf -m 5 "http://127.0.0.1:$PORT/api/running" > /dev/null && echo "still answering"
kill -INT "$(cat /tmp/m4-dry/pid)"; uv run python /tmp/m4-wait.py --gone "$(cat /tmp/m4-dry/pid)" 15
grep -c Traceback /tmp/m4-dry/app.log; grep -c "cutting to" /tmp/m4-dry/app.log
```

`--web-port` wins over the port in the snapshot's config, so the deployed app keeps 8080. Expected (the probe was tried on a made-up home of eight lights while this plan was written, and printed these lines there):
- `zones resumed at start`: the count Step 1 found, and `none in a transition: True` (ruling 16).
- `the home has a location: True`. Whether it is `still the handoff's assumed location` and `confirmed by the owner` is the owner's news, not a failure (ruling 19). `the evening there now`: from 0.00 (day) to 1.00 (night).
- `rainbow wave`: every light in the room lit, the brightest byte near 255. `masked to its own room`: as many lights lit. `masked to another room`: 0 LEDs. `masked to the first metre`: fewer LEDs than the plain wave, or as many if every LED in the room is below 1 m. `capped at 0.2`: brightest at most 51 (0.2 × 255).
- `aurora with every modifier`: most of the room's lights moving.
- `a 4 s fade starts: True | from the look before: True | progress 0: True | durationS 4: True`; `2 s in: progress` from 0.40 to 0.60; `4.5 s in, running with no transition: True`; and the running channel pushed the zone three times, `[('transition', 0.0), ('transition', <about 0.5>), ('running', None)]`: as the fade started, passed its midpoint and ended (ruling 15).
- Each 2 s wipe, spread and dissolve `plays True, then runs True`. `an 11 s fade: 422, the zone unchanged: True`. The start mid-transition plays from the look it interrupted. `Off mid-transition: 204, off at once: True`, `still off after the midpoint: True`, and Stop all the same.
- `still answering`, `ended`, 0 tracebacks and 0 `cutting to` lines.

Anything else is a bug. Fix it in the task that owns the code, with a test, before going on.

- [ ] **Step 4: Ask the owner before touching the deployed app**

Tell the owner the dry run's results. If the stored location is still the handoff's, say so: until they set the home's own (`PUT /api/home` with a `location`, on the deployed app, whenever they like), looks with the evening follow the handoff's assumed place. Don't ask for the location, and never write it anywhere. Then ask to stop the deployed container for about fifteen minutes, run the branch on the real lights while they watch, and give the lights back. Go on only with a yes.

- [ ] **Step 5: Run the branch on the real lights**

With the owner's yes. Home Assistant takes UDP 4002 at about :x8 past each hour if dj-ledfx is down then (CLAUDE.md's Gotchas), so stop the container and start the branch together, well clear of it: if `date +%M` ends in 6, 7, 8 or 9, wait until it ends in 0.

```bash
. /tmp/m4-live.env && cd "$W"
date +%M
(cd /home/anirudhlath/code/private/dj-ledfx && docker compose stop app)
mkdir -p /tmp/m4-real/state
docker cp dj-ledfx-app-1:/app/state/. /tmp/m4-real/state/   # stopped: a consistent copy
cp /home/anirudhlath/code/private/dj-ledfx/config.toml /tmp/m4-real/config.toml
(uv run -m dj_ledfx --web --web-host 127.0.0.1 --web-port "$PORT" --config /tmp/m4-real/config.toml --db /tmp/m4-real/state/state.db > /tmp/m4-real/app.log 2>&1 & echo $! > /tmp/m4-real/pid)
uv run python /tmp/m4-wait.py "http://127.0.0.1:$PORT/api/running" 60
ss -ulne 'sport = :4002'
```

The branch works on a copy, so the deployed `state.db` is never written, and with the container stopped it binds UDP 50001 and 4002 as the deployed app does. Expected: `answering`, and `ss` lists one socket on 4002, the branch's (not `uid:10001`, the container's user). If `ss` lists none, the Govee lamps can't answer the branch: tell the owner before going on.

Then, one step at a time, with the owner watching, run `uv run python /tmp/m4-show.py "http://127.0.0.1:$PORT" STEP` from `$W` for each STEP below, in order. Each prints what to look for; the owner judges. Run `stop` at once if a light misbehaves at any step.

1. `lights`: waits up to a minute for the lights to come online, and prints how many are.
2. `height`, `room-mask` (it turns the whole home off again after 15 s), `mirror` and `turn`: the layer modifiers (rulings 2 and 3).
3. `trails`, `flash`, `cap` and `cap-firmware`: the look modifiers; the cap holds the lights that run their own effect too (ruling 9). `evening`: only telling while the evening's amount is above 0; at 0 the owner sees the look as it is.
4. `fade`, `wipe`, `spread` and `dissolve`: 6 s each, lava to aurora. A wipe runs along the room's longer side, west to east or north to south; a spread grows outward from the anchor nearest the room's middle (ruling 10).
5. `midpoint`: the firmware showcase, then a 10 s fade to sunset. The lights that run their own effect switch whole 5 s in; the rest fade (ruling 12).
6. `interrupt`: a fade, and a second one 2 s into it, with no jump (ruling 13).
7. `off`: Off 2 s into a fade. The room's lights go back as they were and stay so past the midpoint.
8. `stop`: Stop all.

The tunables are the owner's to judge here: the evening's tint and level, the flash's level and length, the trails' fall, the transitions' edges and the masks' soft edge (`EVENING_TINT`, `EVENING_LEVEL`, `FLASH_LEVEL`, `FLASH_BEATS`, `TRAILS_FALL`, `EDGES`, `MASK_EDGE_M`). A change they ask for goes into the task that owns the constant (Task 3, 4 or 6), with its tests, as a fix commit on this branch.

- [ ] **Step 6: Give the lights back to the deployed app**

Again well clear of :x8 past the hour.

```bash
. /tmp/m4-live.env && cd "$W"
date +%M
kill -INT "$(cat /tmp/m4-real/pid)"; uv run python /tmp/m4-wait.py --gone "$(cat /tmp/m4-real/pid)" 15
grep -c Traceback /tmp/m4-real/app.log; grep -c "cutting to" /tmp/m4-real/app.log
(cd /home/anirudhlath/code/private/dj-ledfx && docker compose start app)
uv run python /tmp/m4-wait.py http://127.0.0.1:8080/api/running 120
curl -s http://127.0.0.1:8080/api/running | uv run python -c "import json, sys; print(len(json.load(sys.stdin)['zones']), 'zones running')"
ss -ulne 'sport = :4002'
```

If the wait says `not ended`, the branch is stuck: `kill -USR1` its Python process (`pgrep -n -f 'dj_ledfx --web'`), then `kill -9` it, and tell the owner. Expected:
- `ended`, no tracebacks and no `cutting to` lines.
- The deployed app is back, running as many zones as Step 1 found: it resumes from its own `state.db`.
- `ss` shows `uid:10001` on 4002. If it shows another user, Home Assistant took the port: tell the owner (CLAUDE.md's Gotchas).

Tell the owner it's done. There's nothing to commit here: a fix found in this task goes into the task that owns the code, with a test.

---


### Task 11: CLAUDE.md and the README

CLAUDE.md asks for the claude-md skill to revise Claude's context after each plan. M4 adds four modules, a dependency, the zone runtime's transitions and a manager task, and changes what a start, a running zone and a look's layers carry, so CLAUDE.md's architecture, design decisions, testing and gotchas all need lines. The README's feature list gains one.

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Run the skills**

Run the `claude-md-management:claude-md-improver` skill (audit and targeted updates), then `/claude-md-management:revise-claude-md` for what this branch taught. Both show their changes before writing. Get the owner's yes.

- [ ] **Step 2: Check the facts M4 changed are in CLAUDE.md**

Whatever the skills propose, CLAUDE.md must end up saying these, and nothing that contradicts them. Keep design values out of it: name the files that hold them (CLAUDE.md, "Web App Design"). Never write the home's location, or the handoff's.

- **Architecture:**
  - The `effects/ledset.py` line: a zone's `Space` also carries its rooms' and sub-zones' floor outlines (`room_outlines`, `sub_zone_outlines`), so an edited outline is a new space; `moved(pos)` gives the same LEDs at other positions, keeping the zone's bounds and normalisation (`frame`), for a mirror or a transform.
  - The `effects/blend.py` entry: `blend_into()` takes one opacity, or one per LED (shape (N, 1)) for a mask. The `effects/strip_adapter.py` entry: a linear projection runs along the set's bounds.
  - The `looks/` line: the model reads, checks and writes back the layer modifiers (`Mask`: height, room, sub-zone or anchor; `Mirror`; `Transform`) and the look modifiers; a saved transition's length is clamped, never refused (not finite or not above 0: a cut; over 10 s: 10 s).
  - Add `zones/layer_view.py` (a layer's view of its zone's LEDs: the mask's weights and the moved positions, `LayerView`), `zones/look_modifiers.py` (`Trails`, `flashed()`, `warmed()`, `capped()`) and `zones/transition.py` (`switch_order()` and `new_share()`: where each LED switches, and its share of the new look).
  - The `zones/` line: the runtime runs the look modifiers after the layers, and plays transitions (`begin_transition()`, twins, `holder()`, `take_switch()`); the manager's `start()` takes a transition (None: the look's own), and its `run()` applies the lights at each transition's midpoint.
  - Add `home/sun.py`: `evening_amount(lat, lon, at)` from astral's sun times, and `Evening`, the amount now at the home's location, worked out at most once a second; `main.py` hands one to the zone manager.
  - The `web/contract.py` line: the modifiers' models, `Transition`'s limits, `transition_in()`, and `RunningZone.transition` with `durationS`.
- **Key design decisions:**
  - Layer modifiers change where a field is drawn, never the effect: a mask weighs each LED (a soft 0.1 m edge for a height band or an anchor's reach; a room or sub-zone by its outline), and a mirror, then a transform, move the positions the effect sees. A firmware layer takes none.
  - The look modifiers run on each new frame in a fixed order: trails, the downbeat flash, the evening, the copy of what the firmware lights show, then the brightness cap. Only the cap reaches a light that runs its own effect: it starts at the zone's brightness times the cap (`firmware_brightness`), and a new cap starts the effects again.
  - The evening (the owner's decision): up from an hour before sunset to civil dusk, full through the night, down from civil dawn to sunrise, eased, at the home's location; 0 with no location, logged once.
  - A transition renders every look it replaces (the zone's own last runtime, and a twin of each zone it takes lights from) and mixes them in LED by LED. A light that runs a firmware effect in either look follows the old one until the midpoint, then switches whole. A start mid-transition takes the mix on, and at most three looks render; a change to the zone's lights or a restart cuts; Off and Stop all put the lights back, and the midpoint after changes nothing. A resumed zone plays none.
  - A transition lasts at most 10 s. A request outside the limits gets 422; saved data is clamped.
- **Testing:**
  - Shared fakes: `tests/runtime_fakes.py` (the zone runtime's: `LIGHTS`, `FlatField`, `PlaceField`, `register_fields()`, `field_layer()`, `place_layer()`, `glow_layer()`, `look_of()`, `placed_light()`, `runtime_of()`, `latest()`, `sent()`), `leds_at(space=...)` in `tests/map_home.py`, and `evening=` on `build_home()`, `assemble()` and `make_home`.
  - The perf run covers every built-in look with every modifier, each transition kind mid-way, and three looks at once (`with_every_modifier()`, `home_runtime()`, `tick_times()` in `tests/zones/test_runtime_perf.py`).
- **Gotchas:**
  - The seeded map's location is the one the handoff assumed, not this home's, until the owner sets the real one with `PUT /api/home`; the evening follows whichever is stored. Never write either in the repo.
  - Mid-transition, a light's applied key, its firmware effect and its brightness come from `runtime.holder(device_id)`, not from the runtime: reading `claim_for()` on the new runtime would send the new effect before the midpoint.
  - A twin is never ticked, added to the engine or routed: only the zone that replaced it renders it, and it goes when the transition ends.
  - The `running` channel pushes a zone in transition only as it starts, passes the midpoint and ends; a client moves the bar on from `progress` and `durationS`.
  - astral raises `ValueError` for a day the sun never reaches an event (polar day and night, midsummer nights with no civil dusk); `evening_amount` gathers each event over the dates around and never raises.

- [ ] **Step 3: Add the README's feature**

In `README.md`, after the "Always-running tempo clock" bullet, add:

```markdown
- **Modifiers and transitions** — a look's layers can be masked (to a height band, a room, a sub-zone or the reach of an anchor), mirrored and moved; a look can leave trails, flash on every downbeat, stay under a brightness cap (lights running their own effects included) and turn warmer and dimmer in the evening, from an hour before sunset at the home's location. A look comes in with a cut, fade, wipe, spread or dissolve from whatever the lights showed, and lights running their own effects switch at the transition's midpoint.
```

- [ ] **Step 4: Check that nothing still promises M4**

```bash
git grep -n -e "arrive in M4" -e "M1 plays every transition" -e "transitions arrive" -- . ':!docs'
```

Expected: no lines, as on the dry run. The plan and the specs under `docs/` keep their history. A line under `web/` can only be F3's, if this branch was cut after F3 merged: Task 12's Step 3 settles it.

- [ ] **Step 5: Offer a memory**

The owner's auto-memory index (`/home/anirudhlath/.claude/projects/-home-anirudhlath/memory/MEMORY.md`) has a `dj-ledfx redesign` entry. Offer to add one line to its file (`project_dj_ledfx_redesign.md`): M4 landed as a PR; astral is a dependency now; looks with the evening follow the stored home location, which is the handoff's until the owner sets theirs. Write it only with a yes.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: CLAUDE.md and the README for modifiers and transitions"
```

---


### Task 12: Catch up with master, and the PR

CLAUDE.md ends every plan with a pull request. F3, the web app's Live page, may have merged meanwhile, and may have changed the same web files as Task 9 (`contract.ts` and the mock) or read what Task 9 changed (a running zone's transition). This task rebases, makes F3's code follow what M4 serves, runs every gate again and opens the PR. It never merges.

**Files:**
- Modify: whatever the rebase leaves in conflict under `web/src/api/`; `web/src/api/generated/*` if the rebase changed the backend's API; any F3 code that `tsc -b` names in Step 3
- Create: `/tmp/m4-pr-body.md` (not committed)

- [ ] **Step 1: Rebase onto `master`**

```bash
git fetch origin
git rebase origin/master
git log --oneline -8 origin/master
```

The branch hasn't been pushed, so rebasing is safe. Under `web/`, the branch changes the generated API types (Tasks 3, 4 and 9), `contract.ts`, `contract.test.ts` and the mock (Task 9). A conflict in the generated types means master's API changed too: if `web/package-lock.json` changed on master, run `(cd web && npm ci)` first; then regenerate from the code the rebase has merged, `(cd web && npm run api:types)`, and `git add web/src/api/generated && git rebase --continue`. A conflict in `contract.ts`, `contract.test.ts` or `web/src/api/mocks/` means F3 changed them too: keep both sides (F3's change and Task 9's), and Step 3 checks the result. A conflict anywhere else under `web/` means something unexpected changed: stop and tell the owner. If a conflict touches `CLAUDE.md`, `README.md`, `src/dj_ledfx/main.py`, `src/dj_ledfx/zones/manager.py` or `src/dj_ledfx/web/contract.py`, keep both sides. In `pyproject.toml`, keep both sides' dependency lines, then run `uv lock` (never hand-edit `uv.lock`) and `git add pyproject.toml uv.lock`.

- [ ] **Step 2: Check the generated types**

```bash
uv sync --extra web
(cd web && npm ci && npm run api:types && git status --short src/api/generated)
uv run pytest tests/web/test_openapi_types.py -q
```

Expected: `git status` lists nothing and the pytest passes. If it lists files, commit them:

```bash
git add web/src/api/generated
git commit -m "chore(web): regenerate the API types after the rebase"
```

- [ ] **Step 3: Make F3's code follow what M4 serves**

Skip this step if F3 hasn't merged.

1. Run `(cd web && npx tsc -b 2>&1 | grep "error TS")`. Where it names F3's tests or fixtures building a running zone's transition without `durationS`, give it a `durationS` of 3, as the mock's `transition` scenario has. F3's components only read it. Two of F3's tests pin a transition sent with no length, built as `{ from: 'Fireflies', kind: 'fade', progress: 0.25 }`: `zone-view.test.ts`, "shows a transition's kind, its duration when the server sends one, and its progress", and `zone-card.test.tsx`, "moves a transition on by itself at its duration, and holds one with no duration". Give those two `durationS: 0` instead, and keep their expectations ("Fade", held at 25%): F3's `transitionView()` reads a length of 0 or less as unsaid (F3's plan, Task 23 Step 3 and its "Hand-off").
2. If F3 wrote a pending type in `contract.ts` for anything this branch serves (a running zone's transition with its length, a mask, a mirror or a transform), delete it and use Task 9's alias, as F1's decision 6 asks, and make F3's code follow the generated type, never the other way round. If a pending type has a field the generated one doesn't, stop and tell the owner: the contract needs a ruling.
3. If F3's mock plays starts differently from Task 9's (its own `takeOver`, say), keep F3's behaviour and add Task 9's: a start's transition, or the look's own, as a `transition` state that ends after `durationS`. Task 9's tests in `mock-server.test.ts` say what it must do.
4. Run `(cd web && npm test && npx tsc -b && npm run lint)` and `uv run pytest tests/web -q`. If anything changed, commit it:

```bash
git add web/src
git commit -m "fix(web): F3's Live page follows engine M4's transitions"
```

- [ ] **Step 4: Run every gate**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
uv run pytest -m perf -q
(cd web && npm run api:check && npm test && npx tsc -b && npm run lint && npm run build)
ss -ltn | grep -cE ':(4174|4175) '
```

e2e serves on 4174 and 4175, so only one worktree can run it at a time (CLAUDE.md's Gotchas). If the `ss` count isn't `0`, another worktree is running it: wait until both ports are free, with a Monitor on `until ! ss -ltn | grep -qE ':(4174|4175) '; do sleep 10; done`, then:

```bash
(cd web && npx playwright install chromium && npm run e2e)
```

Expected:
- ruff is clean and every test passes: 1706 passed and 1 skipped on `98ecbee`, plus whatever master added.
- No format findings, and mypy no worse than Before Task 1's baseline.
- The perf run has 40 tests on `98ecbee` (Before Task 1's 18, Task 4's 17 and Task 7's 5), each under 5 ms per zone frame and none dropping to a lower frame rate.
- Every web step passes. The web tests are Before Task 1's count plus 3, plus whatever F3 added. e2e: 60 passed and 20 skipped on `98ecbee`, plus F3's.

- [ ] **Step 5: Check that nothing private is in the branch**

```bash
git diff origin/master -- . ':!docs/design' ':!src/dj_ledfx/home/data' > /tmp/m4-diff.txt
grep -nE '^\+.*\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|^\+.*\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/m4-diff.txt | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
uv run python -c "import json; print('\n'.join(sorted({l['model'] for l in json.load(open('docs/design/web-app/home.json'))['lights'] if l.get('model')})))" > /tmp/m4-models.txt
grep '^+' /tmp/m4-diff.txt | grep -ciFf /tmp/m4-models.txt || echo "no model names"
uv run python -c "import json; home = json.load(open('docs/design/web-app/home.json')); place = home['location']; print('\n'.join(sorted({l['name'] for l in home['lights'] if ' ' in l['name']}) + [place['name'].split(',')[0], str(place['lat']), str(place['lon'])]))" > /tmp/m4-private.txt
grep '^+' /tmp/m4-diff.txt | grep -ciwFf /tmp/m4-private.txt || echo "no light names or place"
```

Expected: `no addresses`, `no model names` and `no light names or place` (each held on the dry run's final diff). Loopback and `0.0.0.0` are allowed. The lists come from `home.json` at run time, so they're never typed here, and the greps print only counts. The handoff's own files and the vendored `home.json` are excluded. Anything found goes: replace it with `localhost`, a made-up name or made-up coordinates. If a count comes from a line this branch only moved, tell the owner instead.

- [ ] **Step 6: Write the PR description**

Write `/tmp/m4-pr-body.md` with these sections, in this order.

**Summary.** Engine milestone M4 of `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: the layer modifiers (mask, mirror, transform) and the look modifiers (trails, downbeat flash, brightness cap, evening) on every look, and transitions (cut, fade, wipe, spread, dissolve) on every start, the lights that run their own effects switching at the midpoint. Plan: `docs/superpowers/plans/2026-10-03-m4-modifiers-transitions.md`.

**What changed**, one bullet per area:

- Looks: the model reads, checks and writes back the modifiers, and clamps a saved transition's length instead of refusing it.
- Effects: `LedSet.moved()`, a per-LED opacity in `blend_into`, and the rooms' and sub-zones' outlines in each zone's `Space`.
- Zones: `layer_view.py` (masks, mirrors, transforms), `look_modifiers.py`, `transition.py` (where each LED switches), transitions in the runtime (twins of the zones a start takes lights from, `holder()` for the firmware lights), and the manager's `run()`, which applies the midpoint.
- Home: `home/sun.py`, the evening at the home's location, with astral 3.2, the one new dependency.
- API: a start plays its transition, or the look's own; `RunningZone.transition` with `durationS`; the modifiers' and transitions' limits (422).
- The web app: `contract.ts` names what M4 serves, and the mock plays a start's transition (Task 9); F3's code follows (Step 3), if it merged first.
- Docs: CLAUDE.md and the README.

**API** (web spec §12.3–12.4 names): `POST /api/zones/{id}/start` plays `transition`, or else the look's own. `RunningZone.state` is `transition` while one plays, with `transition: {from, kind, progress, durationS}`; `durationS` is this branch's addition (ruling 15). `Layer.mask`, `mirror` and `transform` are typed (ruling 1). `LookModifiers` and `Transition` refuse what's out of range with 422, in looks, previews and starts alike. WebSocket: `running` pushes a zone as its transition starts, passes the midpoint and ends.

**Migration.** None. The modifiers and transitions live inside the looks and zone assignments `state.db` already holds, and a saved transition outside the limits loads clamped.

**Deployment.** After the merge, from the main checkout: `git pull && docker compose up -d --build`, well clear of :x8 past the hour, then check `ss -ulne 'sport = :4002'` shows `uid:10001` (CLAUDE.md's Gotchas). astral installs with the image. The ports stay as they are. The running zones resume with no transition. Looks with the evening follow the stored home location: say whether Task 10 found it still the handoff's, never what it is.

**Spec rulings.** Rulings 1–21 from the plan, one line each.

**Review Focus.** The plan's five items, each with its tests.

**Real lights.** Task 10's results as counts and yes or no: the dry run's lines, and the owner's check of each step on the real lights, with any tunable they changed. No ids, addresses, model names or places.

**Test plan.** Step 4's gates with their counts, the perf run, the web gate, and Task 10.

End the description with:

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Then check the description as Step 5 checked the diff:

```bash
grep -nE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/m4-pr-body.md | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
grep -ciFf /tmp/m4-models.txt /tmp/m4-pr-body.md || echo "no model names"
grep -ciwFf /tmp/m4-private.txt /tmp/m4-pr-body.md || echo "no light names or place"
```

Expected: `no addresses`, `no model names` and `no light names or place`.

- [ ] **Step 7: Push and open the PR**

```bash
git push -u origin feature/m4-modifiers-transitions
gh pr create --base master --head feature/m4-modifiers-transitions \
  --title "M4 modifiers and transitions: masks, mirrors, transforms, trails, flash, cap and evening; cut, fade, wipe, spread and dissolve" \
  --body-file /tmp/m4-pr-body.md
gh pr view --json url --jq .url
```

Give the owner the URL. Don't merge: the owner does, after review. CLAUDE.md's code-architect review and `/simplify` run on the open PR, outside this plan.
