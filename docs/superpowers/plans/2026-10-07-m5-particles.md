# M5 Particles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Particle effects join field and firmware effects: particles that move through the home, sent from, led along and drawn to its anchors and lamps, lighting the LEDs near them. The eleven particle looks of the handoff's `looks.json` run as built-ins on any zone, in previews and transitions and with every modifier, inside the 5 ms frame budget.

**Architecture:** `effects/particle_tools.py` holds what every particle effect shares, in pure numpy: `Particles` (positions, colours and radii at one moment); `draws()`, a counter-based random generator keyed by event, so the same moment always gives the same particles; the zone's lamps as stops (`Lamps`, one per light, each with its LEDs); `Ground` (the LEDs, their lamps, the floor and the ceiling, worked out once for each LED set); the moves the looks share (`wander`, `arc`, `tour`, `spread_over`, `around`); and `lit()`, which lights each LED by a Gaussian falloff with its distance from each particle, densely below 2000 LEDs and through a spatial grid above. `effects/particles.py` adds `ParticleEffect` (`place`, `step`, `sample` and `particles`) and `ParamParticles`, which keeps its settings as `ParamField` does (the two now share `ParamSettings` in `effects/base.py`) and works its particles out in closed form, `positions(ctx, ground)`. The look model takes particle layers, and the zone runtime draws them through each layer's view, as M4 draws a field layer: masks, mirrors, transforms, blends, look modifiers, transitions and twins all apply. Eleven effect modules, one for each look, and the built-ins' layers for the eleven looks complete it. The API's shapes don't change: the contract's `Layer.type` already names `particles`.

**Tech Stack:** Python 3.11+ (3.14 in the venv and the container), numpy (2.4 in `uv.lock`), FastAPI and Pydantic v2, loguru, pytest. No new dependency and no external API, so there was nothing to check against outside docs. The web app is untouched: M5 changes no API shape, so the generated types stay as they are (`npm run api:check` in Tasks 3 and 8; the whole web gate in Task 11).

**Spec:** `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: the amendments at its top, the M5 row in §2, §4.1, §5.1 (the `ParticleEffect` API and its "Particles:" paragraph), §5.2, §5.3 (M4's modifiers and transitions, which particle layers take like any other), §8, §9 and §10. The contract is `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md` §12.2 (`Layer`). The looks' names, descriptions, categories and inputs are `docs/design/web-app/looks.json`'s: read them there, never from this plan. Read the specs before starting.

**What exists.** What M5 starts from, on master at `d6f959e`:

- `looks/model.py` refuses a particle layer ("Particle layers arrive in M5"), though the contract's `Layer.type` already includes `particles`; `make_effect()` makes field and firmware effects only.
- `ParamField` (`effects/field.py`) keeps a field effect's settings in one dict, with `_prepare()`, `_per_leds()`, `reseed()` and `_rng(k)`.
- The zone runtime (`zones/runtime.py`) blends its visible field layers bottom to top, each through its layer's view (M4's mask, mirror and transform); crashes a zone whose layer gives NaN (`_finite`); and renders twins of replaced looks for transitions.
- The built-ins are M2's and M3's looks and the `firmware` look, in `looks.json`'s order, then the six classics. `looks.json`'s other looks, the eleven particle looks among them, have no layers yet, so they aren't served.
- Spec §4.1's benchmark put 500 particles on this home's 412 LEDs at 1.28 ms a frame.

**Execution:** `/executing-plans` in a new worktree, `~/code/.worktrees/dj-ledfx/m5-particles` on branch `feature/m5-particles`. Branch it from `origin/master` after the docs PR with this plan has merged; Before Task 1 sets it up.

F4, the web app's Put a look on, is planned at the same time and may merge first. This plan changes nothing under `web/`, but F4 may change `web/src/api/generated/*`, `web/src/api/contract.ts` and the mocks, and the backend tests that list the built-in looks. Task 11 rebases over whatever has merged, settles any conflict and runs every gate again.

**How to read the code.** A new file is given whole, in a `python` block after "Create". A change to an existing file is a unified diff, in a `diff` block, against the file as master at `d6f959e` and the earlier tasks leave it; apply the blocks in the order given. Save a block to a file and run `git apply --recount` on it (`git apply --recount /tmp/m5-step.diff`), or make the same edit by hand. If master has moved past `d6f959e` and a block no longer applies, make the edit by hand: its hunks say where. Every block was applied in this order to a worktree of `d6f959e` while this plan was written, and each task's gate passed there with the counts given. A newer master may add to them.

---


## Global Constraints

Every task's requirements include these. Quotes are verbatim from the specs.

- M5 scope (engine spec §2): "Particle API; emitters, paths and targets that know where the lamps are", and the eleven looks the row lists. Their ids are `fireflies`, `embers`, `rain`, `snow`, `spotlights`, `bursts`, `fountain`, `vortex`, `comets`, `ball` and `flock`; their names, descriptions and thumbnail ids come from `looks.json`.
- §5.1, the particle kind:

  ```python
  class ParticleEffect(Effect):
      def step(self, ctx: RenderContext) -> None: ...                       # advance state with a seeded RNG
      def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB: ...
  ```

  "**Particles:** capped at about 500, with a seeded RNG so runs repeat. Emitters, paths and targets can be anchors or lamps: comets follow a path through lamps, spotlights visit lamps, embers rise from lamp bases. Particles light LEDs by distance falloff; past about 2k LEDs a spatial grid keeps the lookup cheap."
- §4.1: "Colour stays float RGB through the whole layer stack and is clamped and converted once, at send." "Everything stays on the single asyncio event loop. Budget: under 5 ms per zone frame on one core. No GPU: the planned Proxmox LXC has none, and the benchmark shows none is needed." "Past about 2k LEDs, particles switch to a spatial grid." "From M8, effects can also describe what they draw in space (particle positions, rings, planes, sun shafts) for the web app's stage."
- The light-sync amendment: "A zone renders up to 500 ms ahead, up from 120 ms."
- §5.2: "Layers composite bottom to top in float RGB. Blend modes: normal, add, screen, multiply, max. A firmware layer claims its devices; streamed layers skip them." "The built-ins keep the ids, names, descriptions and thumbnail ids of the handoff's `docs/design/web-app/looks.json`."
- §5.3: "During a transition the zone renders both looks, so both count against the frame budget."
- §8: "**A look raises or produces NaN:** that zone holds its last good frame, the look is marked crashed, and the error is logged once (rate-limited). Other zones keep running." "A zone that keeps exceeding its 5 ms budget drops to a lower frame rate, so it cannot stall the shared event loop." "**Data:** a bad or missing home map, or a bad look, never crashes the app. It starts with what it has and reports the problem."
- §9: "**Looks:** a sweep over all 29 presets checks that every look stays finite and in range, outputs the right shape, and repeats exactly with a fixed seed. Each effect also gets a few behaviour checks". "No pixel-exact reference images; they would break on every tuning change." "**Performance:** a benchmark test on this home's 412-LED map asserts each zone renders in under 5 ms. It is marked as a performance test and run locally." "**Each milestone** ends with a short checklist run on the real lights; preview-only mode allows a dry run first."
- §2: "Each milestone also extends backup and restore to the data it adds."
- §10: "Where this spec and the contract name the same thing differently, the contract's name wins." The contract's `Layer` (web spec §12.2): "`type: 'field' | 'particles' | 'firmware'; kind: string`".
- Build nothing from M6 or later: no whole-home scope, overlays, sun input, signals or bindings, and no `fx` stream (M8). `validate_look` keeps refusing whole-home looks and bound settings with the milestones that bring them. Particle state stays readable (`ParticleEffect.particles`, ruling 1) so M8 can draw positions, but nothing reads it for that yet.
- Design files (CLAUDE.md, "Web App Design"): never retype a look's name, description or thumbnail id, an anchor, or any other design value, in code, tests, docs or this plan. Code and tests read them from the vendored `looks.json` (`handoff_looks()`) and the seeded map.
- The repo is public: no LAN addresses, MACs, SSIDs, light names, light model names, room names, the home's location or AI model names in code, tests, commits, the PR or this plan. Fixtures use made-up ids (`test-lamp`, lamps a–d, `light-0`, `light-1`, …) and 127.0.0.1. Loopback, `0.0.0.0` and port numbers are fine.
- Code style (CLAUDE.md): `uv` for everything, `loguru` for logging, `mypy --strict`, render paths synchronous and lock-free, numpy on whole arrays in the render path (no loop over LEDs or particles), a frame in a ring never changed after it's written, and every new effect imported in `effects/__init__.py`.
- Gates, per task before commit: `uv run ruff check .` clean and `uv run pytest -q` green; `uv run ruff format --check .` no findings and `uv run mypy src/` no worse than the baseline from Before Task 1 (16 errors when this plan was written). An error in a file the task touched is the task's to fix unless the baseline had it. During a task, run only its test files; run the full gate once, before the commit. The plan's code was formatter-exact when it was written, but run `uv run ruff format` and `uv run ruff check --fix` on the files the task touched before the gate, never on the whole tree. `uv run pytest -m perf -q` keeps every zone frame under the 5 ms budget: Tasks 1, 4, 5, 6, 7, 8 and 11 run it.
- M5 changes no API shape, so no task regenerates the web app's types: Tasks 3 and 8 check that with `npm run api:check`, and Task 11 runs the whole web gate. e2e serves on :4174 and :4175, so only one worktree can run it at a time: check `ss -ltn | grep -cE ':(4174|4175) '` first, and while it isn't `0`, wait (a Monitor on `until ! ss -ltn | grep -qE ':(4174|4175) '; do sleep 10; done`), never a foreground sleep.
- Live system: the deployed `dj-ledfx-app-1`, docker and the lights are touched only in Task 9, each such step with the owner's go. The deployed app holds TCP 8080 and UDP 4002 and 50001 on this host, and 8081 belongs to another service: a branch run serves on `PORT=8098`, set once in Task 9. A branch run beside the deployed app never opens UDP 4002, since two apps there would split the Govee lamps' replies between them: the dry run has no light backend at all, and the run on the real lights starts only once the container has stopped. UFW and master are never touched; master changes only through the PR, which the owner merges.

## Spec Rulings

The specs disagree, or say nothing, in a few places. These are the rulings this plan builds on. Task 11 lists them in the PR; the ones marked **owner** change what the owner sees, and Task 9 shows them on the real lights.

1. **The particle API.** §5.1 gives `ParticleEffect` `step(ctx)` and `sample(ctx, leds)`. This plan adds `place(leds)`: the LEDs the layer's view shows (its mask's LEDs, at the places its mirror and transform move them to), which say where the particles move. Each frame the runtime calls `place`, `step` and `sample` (`drawn()`), and `place` is cheap for a set it has seen. The `particles` property is the last step's `Particles`: positions in metres on the map's axes, colours with their brightness in them, and radii, oldest first. M8's `fx` stream can read it; nothing does yet.
2. **Particles in closed form.** §5.1's sketch has particles "advance state with a seeded RNG". Every M5 effect instead works its particles out from the frame's moment, its seed and the LEDs alone (`ParamParticles.positions(ctx, ground)`), drawing its random numbers for each event (a firefly, a drop, a beat's burst) from a counter-based generator, `draws(seed, keys, count, stream)` on SplitMix64's mixer. That keeps the spec's promise that "runs repeat", whatever the frames' timing, and more besides: a twin draws what its zone draws, as M4's transitions need; a zone renders up to 500 ms ahead, and its horizon can grow or shrink without the particles jumping; and a particle that lands on a beat lands on it at any frame rate. `step()` is still where the particles move. **Owner:** a settings change applies from the next frame, so the particles jump to where the new settings put them, as M2's and M3's field effects already do; easing a bound setting is M7's.
3. **Lamps.** "Emitters, paths and targets can be anchors or lamps." A lamp is a stop: each light in the zone, and lights whose middles are within 0.3 m of one another make one (`SAME_STOP_M`; the parts of a light with parts share one placement). **Owner:** each visit, landing, drop, flake or ember picks its own LED of its lamp at random (`Lamps.led`, `Ground.on`), so particles reach the whole length of a long light (a strip, a tube) as they reach a short one. A lamp's base, §5.1's "lamp bases", is under one of its LEDs at the height of its lowest LED (`Ground.foot`). A zone of one lamp keeps going round that lamp, and a zone with no LEDs draws nothing.
4. **The falloff.** "Particles light LEDs by distance falloff": each particle adds its colour times exp(−(d/r)²) to each LED, d its distance from the LED and r its radius (at least 0.01 m, `MIN_RADIUS_M`), out to 2.5 radii (`REACH`; past it a particle adds under half an 8-bit step), and each LED's sum is clipped to 1, channel by channel. **Owner:** a particle layer is black between its particles, so under the `normal` blend it covers the layers below it with black there; to lay particles over a field, give the particle layer `add`, `screen` or `max`. Each built-in particle look has one particle layer and no field under it.
5. **The grid.** "past about 2k LEDs a spatial grid keeps the lookup cheap": from 2000 LEDs (`GRID_FROM_LEDS`), `lit()` measures only the LEDs in the 27 grid cells round each particle's cell, each cell at least REACH times the largest radius wide (in steps of √2, so a `Ground` keeps a few grids, at most 8). A few particles far larger than the rest (over twice the median radius, such as a lightning strike) are lit densely, so they don't make every cell huge. The grid gives the dense sum's colours (Task 1's tests). This home's 412 LEDs never use it; 500 particles on 10,000 LEDs stay within the budget (Task 1's perf test).
6. **Floor and ceiling.** Particles move inside the zone's frame (its bounds, which a layer's view keeps), between the map's floor (height 0) and the ceiling the zone's space carries. A zone whose space has no ceiling (LEDs placed with no map) floors at its lowest LED and ceilings 0.5 m over its highest (`CEILING_OVER_M`).
7. **Layer modifiers on a particle layer.** A particle layer takes M4's layer modifiers as a field layer does: its mask weighs the LEDs it lights, and its mirror, then its transform, move the positions the effect sees (M4's ruling 3), so the particles are worked out among the moved LEDs and light them there. **Owner:** what's placed by the zone's frame or by an anchor moves with the field (an offset moves the fountain's spray off its anchor by that much), while what goes to a lamp still goes to one of its LEDs, which lights where it really is. Under a mirror, a lamp on the high side is found at its reflection, so a particle that lands on it lights whatever stands at that reflection as well. The look modifiers and transitions take a particle layer's frames like any layer's. A particle layer that picks lights is refused, as a field layer is ("give a streamed layer a mask instead").
8. **Layers of the wrong kind.** A particle layer whose kind isn't a particle effect, or a field or firmware layer whose kind is one, is refused with the reason ("… isn't a particle effect", "… isn't a field effect", "… isn't a firmware effect"; 400), as a field layer of a firmware kind is now. A saved look with such a layer crashes its zone with the reason, as an unknown kind does.
9. **The cap.** "capped at about 500": each step keeps at most 500 particles (`MAX_PARTICLES`), the newest (the last `positions()` gives), and every effect's largest settings stay within it (Task 4's sweep).
10. **What each look does with the lamps** (**owner**; each look's description is `looks.json`'s, read there):
    - `fireflies`: each firefly wanders slowly round an LED of a lamp of its own, every lamp taken before any gets two, glowing low and flaring now and then; given an anchor in its Drift toward setting, they wander round that anchor instead. The Look-Editor render also shows a Wander in setting with a room in it: here that is the layer's room mask (M4), not a setting of the effect.
    - `embers`: from the base of each lamp, each under an LED of its own, embers climb to just over the lamp's top, dimming and reddening as they go. The engine spec says "embers rise from lamp bases", and the look's description starts them somewhere else (read it there); this plan follows the engine spec, so on an upright lamp they start near the floor and on a light up high at its lowest LED. The look's firmware layer, `flame`, runs LIFX Flame on the lights its description names, picked as Aurora's Morph layer picks them (`type:candle`, `type:tube`; Sunset's Flame picks only `type:candle`), and the embers climb the rest: a firmware layer claims its lights.
    - `rain`: drops run down each lamp past an LED of it, and about four times a minute a bolt of lightning lands at a random point over the floor, at half the ceiling's height: one wide particle, which lights each lamp the more the nearer it is, with a flash, a dip and a second flicker.
    - `snow`: flakes fall from the ceiling to the floor, a few for each lamp at once, each within 0.3 m of an LED of a lamp, swaying as they go.
    - `spotlights`: each spotlight (two by default) rests on an LED of a lamp, then glides to another lamp, on a shuffled tour of every lamp that never stays on one lamp twice running.
    - `bursts`: on every beat a burst leaves the anchor the description names (read from it, as Focus's is), each particle landing on an LED of a random lamp and fading there; the downbeat's burst is bigger.
    - `fountain`: a steady spray rises and falls round the anchor the description names, and on every beat a burst is thrown to land on lamps' LEDs on the next beat.
    - `vortex`: particles circle the zone's middle on rings through the lamps' LEDs, rising from the floor to the ceiling over four bars, each beat's share of the turn coming in a rush at the beat.
    - `comets`: two comets go round the lamps in a loop, in their order round the zone's middle, from opposite sides of it, each landing on an LED of the next lamp on every beat, with a tail.
    - `ball`: the ball lands on the base of a lamp, under an LED of it, on every beat, bouncing up between, on a shuffled tour of the lamps, a new colour each bounce.
    - `flock`: the flock gathers on one lamp after another, two bars each, swirls about its middle and bursts apart on the downbeat of every other bar.
11. **Palettes and settings are this plan's.** `looks.json` gives each look a description and a thumbnail, no colours or numbers, so each effect's palette, settings, limits and defaults are this plan's own. The Look-Editor render shows an edited Fireflies, not the built-in's defaults. **Owner:** they are the owner's to tune in Task 9.
12. **The built-ins.** Each particle look has one particle layer, id `particles`, named as `looks.json` names the look (read at run time); the embers' firmware layer is `flame`, named "Flame". `bursts` and `fountain` take the anchor their descriptions name, read with `anchor_named_in()` as Focus's and Shockwave's are. Like every built-in, they come in with a cut (M4's ruling 17).
13. **Tempo.** The tempo looks move with the beat count and phase (`ctx.beats`), never the BPM, so a tempo change carries them on from where they are, and a landing or a burst falls on the beat at any tempo from 30 to 300 BPM. The ambient looks move in seconds (`ctx.t`).
14. **Backups.** Particle layers live inside the looks and zone assignments backups already carry, so M5 adds no table and no migration.
15. **No Level setting.** The particle effects have no `level` setting (M2's `level_param()`): a particle's brightness is in its colour, and the zone's brightness and the look's brightness cap dim it.

## Review Focus

These are the five inputs the specs imply that are most likely to bite someone using this, most likely first. Each has tests in the task that owns the code.

1. **The smallest zones.** A room with one lamp, a room with one bulb (one LED), a zone of LEDs with no map (no ceiling, no anchors), and a zone whose lights are all offline (no LEDs). Every look stays finite and in range, a lone bulb still lights, and a zone with no LEDs draws nothing; nothing raises. Tests: Task 4's sweep, which every later task's effects join, `test_a_zone_of_one_lamp_with_no_map_draws_in_range`, `test_a_zone_of_one_bulb_draws_in_range_and_lights_it` and `test_a_zone_with_no_leds_draws_nothing`; Task 2, `test_no_leds_or_no_place_give_no_particles`; Task 1, `test_a_zone_with_no_leds_has_no_lamps`; Task 5, `test_with_one_lamp_a_spotlight_moves_up_and_down_it`.
2. **Tempo changes and extremes.** A DJ's tempo from 30 to 300 BPM, or a jump from one to the other mid-look. Every frame stays in range, and comets, the ball, the flock and the bursts still land on the beat. Tests: Task 4's sweep, `test_a_tempo_from_30_to_300_bpm_keeps_every_frame_in_range`; Task 6, `test_a_burst_keeps_its_shape_at_any_tempo`; Task 7, `test_each_comet_lands_on_an_led_on_every_beat_at_any_tempo` and `test_the_ball_lands_on_a_lamps_foot_on_every_beat_at_any_tempo` (30, 120 and 300 BPM) and `test_the_flock_moves_on_the_beat_at_any_tempo`.
3. **Frames that fall unevenly.** A zone over its budget renders every few ticks, a transition renders a replaced look on its twin, and the horizon moves with the lights' latencies: the same moment must give the same frame. Tests: Task 4's sweep, `test_every_particle_effect_is_finite_in_range_and_repeats_with_a_fixed_seed` and `test_the_same_moment_gives_the_same_frame_however_the_frames_fall`; Task 8, `test_a_twin_of_a_particle_look_draws_what_its_runtime_draws` and `test_a_particle_look_mid_transition_from_another_renders_in_under_5_ms` (perf).
4. **The largest settings.** The look editor's sliders at their ends, on a home with many lamps: at most 500 particles, and a frame within the budget. Tests: Task 4's sweep, `test_the_largest_settings_keep_to_the_particle_cap` and `test_every_particle_effect_at_its_largest_settings_draws_in_the_budget` (perf); Task 4, `test_each_lamp_has_per_lamp_flakes_falling_past_it_up_to_the_cap`; Task 2, `test_a_step_keeps_the_newest_500`; Task 1, `test_500_particles_light_10k_leds_in_the_frame_budget` (perf).
5. **Hand-made looks that mix kinds.** A look from a client or the editor with a particle layer of a field kind, a field layer of a particle kind, a particle layer that picks lights, or a particle layer with modifiers over a field. Each mismatch is refused with the reason; modifiers and blends work; a particle layer that gives NaN crashes only its zone. Tests: Task 3, `test_a_layer_of_another_kind_of_effect_is_refused_with_the_reason`, `test_particle_layers_take_modifiers_and_round_trip_but_pick_no_lights`, `test_a_layers_transform_and_mirror_move_its_particles_as_they_move_a_field`, `test_particle_and_field_layers_blend_bottom_to_top` and `test_a_particle_layer_that_gives_nan_crashes_its_zone`.

---

## File Structure

New backend modules (paths under `src/dj_ledfx/`):

| File | Responsibility |
|---|---|
| `effects/particle_tools.py` | What particle effects share: `Particles` (`swarm`, `joined`, `NO_PARTICLES`), `draws()` and `recent()`, the moves (`wander`, `arc`, `tour`, `shuffled`, `spread_over`, `around`), the lamps (`Lamps`, `lamps_of`, `NO_LAMPS`), `Ground`, and `lit()` with its grid |
| `effects/particles.py` | `ParticleEffect`, `ParamParticles`, `MAX_PARTICLES` and `drawn()` |
| `effects/{fireflies,snowfall}.py` | Task 4's two looks' particles |
| `effects/{embers,rain_storm,spotlights}.py` | Task 5's three |
| `effects/{beat_bursts,fountain,vortex}.py` | Task 6's three |
| `effects/{twin_comets,bouncing_ball,flock}.py` | Task 7's three |

Modified: `effects/base.py` (`ParamSettings`) and `effects/field.py` (`ParamField` on it) in Task 2; `looks/model.py` and `zones/runtime.py` in Task 3; `effects/__init__.py` in Tasks 4–7; `looks/builtin.py` in Task 8; `CLAUDE.md` and `README.md` in Task 10. Nothing under `web/`.

Shared test helpers:

- `tests/map_home.py`: `lights_at(*lights, ceiling=3.0)`, one light for each list of points (Task 1), with `anchors=` from Task 6; `upright(x, y, low=0.1, high=1.4)`, an upright lamp's 14 LEDs (Task 4).
- `tests/runtime_fakes.py`: `DotParticles`, a particle effect of one dot that `register_fields()` registers as `dot_particles`, and `dot_layer()` (Task 3).
- `tests/effects/test_particle_effects.py` (Task 4): the sweep over every registered particle effect (`PARTICLE_KINDS`), which each later task's effects join by registering.

New test files: `tests/effects/test_particle_tools.py` (Task 1), `tests/effects/test_particles.py` (Task 2), `tests/zones/test_runtime_particles.py` (Task 3), `tests/effects/test_{fireflies,snowfall,particle_effects}.py` (Task 4), `tests/effects/test_{embers,rain_storm,spotlights}.py` (Task 5), `tests/effects/test_{beat_bursts,fountain,vortex}.py` (Task 6) and `tests/effects/test_{twin_comets,bouncing_ball,flock}.py` (Task 7).

---

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/m5-particles /home/anirudhlath/code/.worktrees/dj-ledfx/m5-particles origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/m5-particles
cd "$W"
test -f docs/superpowers/plans/2026-10-07-m5-particles.md && test -f docs/design/web-app/looks.json && echo "plan and design present"
test -f src/dj_ledfx/zones/layer_view.py && test -f src/dj_ledfx/zones/transition.py && echo "M4 present"
grep -q 'Particle layers arrive in M5' src/dj_ledfx/looks/model.py && echo "M5's refusal still here"
git log --oneline -5 origin/master
```

Expected: `plan and design present`, `M4 present` and `M5's refusal still here`. If one is missing, stop and tell the owner. The log shows whether F4 has merged; either is fine, since Task 11 rebases over it. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
(cd web && npm ci)
```

Without the `web` extra, the web tests skip silently and mypy reports dozens of extra errors. The web app's packages are for `npm run api:check` (Tasks 3 and 8) and Task 11's web gate.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tee /tmp/m5-baseline-mypy.txt | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm test 2>&1 | grep -E "^ +Tests " && npx tsc -b && npm run lint && npm run api:check)
ss -ltn | grep -cE ':(4174|4175) '
```

If the `ss` count isn't `0`, another worktree is running e2e: wait until both ports are free (Global Constraints), then:

```bash
(cd web && npx playwright install chromium && npm run e2e 2>&1 | tail -4)
```

Write the results down: the test count (`2029 passed, 1 skipped, 42 deselected` on `d6f959e`), the format findings (none: `339 files already formatted`), mypy's error count (16), the perf run (`42 passed`), the web tests' count (716), `api types match`, and e2e's (`90 passed`, `48 skipped`). Every gate compares with these. `ruff check` should be clean, and the web gate and e2e green. If any isn't, tell the owner before starting.

- [ ] **Step 4: Check the design files**

```bash
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256 | grep -E 'looks.json|home.json')
```

Expected: `looks.json: OK` and `home.json: OK`. A mismatch means someone hand-edited a design file: stop and tell the owner.

---

### Task 1: The particle toolkit

What every particle effect shares, in pure numpy, before any effect uses it: the particles of a moment, random numbers keyed by event (ruling 2), the zone's lamps as stops with their LEDs (ruling 3), the ground the particles move on (ruling 6), the moves the looks share, and the light (rulings 4 and 5). Nothing imports it until Task 2.

**Files:**
- Create: `src/dj_ledfx/effects/particle_tools.py`, `tests/effects/test_particle_tools.py`
- Modify: `tests/map_home.py` (`lights_at()`)

**Interfaces:**
- Consumes: `LedSet` (`effects/ledset.py`: `pos`, `count`, `bounds`, `centre`, `slices`, `space.ceiling`, `anchors`), `FloatRGB` (`types.py`).
- Produces, in `effects.particle_tools`:
  - `F32 = NDArray[np.float32]`, `F64 = NDArray[np.float64]`; `REACH = 2.5`, `GRID_FROM_LEDS = 2000`, `SAME_STOP_M = 0.3`, `CEILING_OVER_M = 0.5`, `MIN_RADIUS_M = 0.01`.
  - `Particles(pos: F32, colour: F32, radius: F32)`, frozen, shapes (P, 3), (P, 3) and (P,), oldest first, with `count`, `newest(count) -> Particles` and `pick(which: NDArray[np.bool_]) -> Particles`; `swarm(pos, colour, radius) -> Particles` (one colour or one radius for all, radii at least `MIN_RADIUS_M`); `NO_PARTICLES`; `joined(*parts: Particles) -> Particles`.
  - `draws(seed: int, keys: ArrayLike, count: int, stream: int = 0) -> F64`, shape (keys, count), each from 0 to 1 (1 left out), the same for the same seed, stream and key.
  - `recent(now: float, every: float, life: float) -> NDArray[np.int64]`: the events, one every `every` at a random moment within it, that may be alive at `now`.
  - `WANDER_DRAWS = 12`; `wander(u: F64, t: float, speed: float, low: ArrayLike, high: ArrayLike) -> F64`, shape (wanderers, 3), inside its box (one box, or one each).
  - `arc(start: ArrayLike, end: ArrayLike, share: ArrayLike, rise: ArrayLike) -> F64`: points on a parabola from start to end, `rise` metres over the line half-way.
  - `TOURS = 1000`; `tour(seed: int, key: int, step: int, stops: int) -> int`; `shuffled(seed: int, key: int, round_: int, stops: int) -> NDArray[np.intp]`; `spread_over(seed: int, count: int, stops: int) -> NDArray[np.intp]`.
  - `Lamps(centre: F32, low: F32, high: F32, members: NDArray[np.intp], starts: NDArray[np.intp])` with `count`, `pick(u: ArrayLike) -> NDArray[np.intp]` (a stop for each u) and `led(stop: ArrayLike, u: ArrayLike) -> NDArray[np.intp]` (an LED of each stop, its index in the zone); `NO_LAMPS`; `lamps_of(leds: LedSet) -> Lamps`.
  - `around(points: F32, middle: NDArray[np.floating[Any]]) -> NDArray[np.intp]`: the points' order round the middle, seen from above.
  - `Ground(leds: LedSet, lamps: Lamps, floor: float, ceiling: float)`, made by `Ground.of(leds)`, with `low`, `high` and `centre` (the zone's frame), `on(stop, u) -> F64` (an LED of each stop), `foot(stop, u) -> F64` (that LED at its stop's lowest LED's height), `box(margin=0.0, around=None) -> tuple[F64, F64]` and `grid(size) -> _Grid`.
  - `lit(ground: Ground, particles: Particles) -> FloatRGB`: each LED's light, a new float32 array.
  - In `tests/map_home.py`: `lights_at(*lights: Sequence[Sequence[float]], ceiling: float | None = 3.0) -> LedSet`, one light (`light-0`, `light-1`, …) for each list of points, in a zone with that ceiling.

- [ ] **Step 1: Write the failing tests**

In `tests/map_home.py`, a zone of several lights, which most of M5's tests stand their lamps in:

```diff
--- a/tests/map_home.py
+++ b/tests/map_home.py
@@ -165,6 +165,20 @@ def leds_at(
     return build_ledset([LedSource("light", len(points), placed=placed)], space)


+def lights_at(*lights: Sequence[Sequence[float]], ceiling: float | None = 3.0) -> LedSet:
+    """Lights' LEDs at these map positions, one light for each list of points, in this
+    order, in a zone with this ceiling and no anchors."""
+    sources = [
+        LedSource(
+            f"light-{index}",
+            len(points),
+            placed=PlacedLeds.from_positions(np.asarray(points, dtype=np.float64).reshape(-1, 3)),
+        )
+        for index, points in enumerate(lights)
+    ]
+    return build_ledset(sources, Space(ceiling=ceiling))
+
+
 ROW = [[x, 0.0, 1.0] for x in np.linspace(0.0, 4.0, 9)]  # 0.5 m apart, west to east


```

Create `tests/effects/test_particle_tools.py`:

```python
from __future__ import annotations

import math
import statistics
import time

import numpy as np
import pytest
from map_home import ROW, leds_at, lights_at

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import (
    CEILING_OVER_M,
    GRID_FROM_LEDS,
    MIN_RADIUS_M,
    NO_PARTICLES,
    REACH,
    SAME_STOP_M,
    WANDER_DRAWS,
    Ground,
    _densely,
    arc,
    around,
    draws,
    joined,
    lamps_of,
    lit,
    recent,
    spread_over,
    swarm,
    tour,
    wander,
)
from dj_ledfx.zones.runtime import FRAME_BUDGET_S


def _scattered(count: int, seed: int) -> LedSet:
    """`count` LEDs scattered through a 15 x 15 x 3 m home, as one light."""
    points = np.random.default_rng(seed).uniform((0.0, 0.0, 0.0), (15.0, 15.0, 3.0), (count, 3))
    return lights_at([tuple(point) for point in points])


def test_a_particle_lights_each_led_by_a_gaussian_falloff_out_to_its_reach() -> None:
    ground = Ground.of(leds_at(ROW))  # 0.5 m apart along x
    one = swarm([[0.0, 0.0, 1.0]], [1.0, 0.0, 0.0], 0.5)

    reds = lit(ground, one)[:, 0]

    expected = [
        math.exp(-((d / 0.5) ** 2)) if d <= REACH * 0.5 else 0.0 for d in np.arange(9) * 0.5
    ]
    np.testing.assert_allclose(reds, expected, atol=1e-6)
    assert reds[2] > 0.0 and reds[3] == 0.0  # 1 m is two radii; 1.5 m is past REACH


def test_light_adds_up_and_stays_at_most_1() -> None:
    ground = Ground.of(leds_at(ROW))
    two = swarm([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]], [0.6, 0.6, 0.6], 0.5)

    frame = lit(ground, two)

    assert frame.dtype == np.float32
    np.testing.assert_allclose(frame[0], 1.0)  # 1.2, held at 1
    np.testing.assert_allclose(frame[1], 1.2 * math.exp(-1.0), rtol=1e-5)


def test_no_particles_or_no_leds_light_nothing() -> None:
    ground = Ground.of(leds_at(ROW))
    assert not lit(ground, NO_PARTICLES).any()
    empty = Ground.of(lights_at())
    assert lit(empty, swarm([[0.0, 0.0, 0.0]], [1.0, 1.0, 1.0], 1.0)).shape == (0, 3)


def test_a_radius_is_never_below_the_floor() -> None:
    particles = swarm([[0.0, 0.0, 0.0]], [1.0, 1.0, 1.0], 0.0)
    assert particles.radius[0] == pytest.approx(MIN_RADIUS_M)
    assert np.isfinite(lit(Ground.of(leds_at(ROW)), particles)).all()


# Spec §4.1: past about 2k LEDs, particles switch to a spatial grid. It must light the
# LEDs as the dense sum would, particles outside the frame and of every size included.
def test_the_grid_lights_the_leds_as_every_led_against_every_particle_does() -> None:
    ground = Ground.of(_scattered(GRID_FROM_LEDS + 500, seed=1))
    rng = np.random.default_rng(2)
    particles = swarm(
        rng.uniform((-2.0, -2.0, -1.0), (17.0, 17.0, 4.0), (300, 3)),
        rng.uniform(0.0, 1.0, (300, 3)),
        rng.uniform(0.05, 0.6, 300),
    )

    by_grid = lit(ground, particles)
    dense = np.zeros_like(by_grid)
    _densely(ground, particles, dense)

    assert by_grid.any()
    np.testing.assert_allclose(by_grid, np.minimum(dense, 1.0), atol=1e-4)


def test_the_grid_lights_a_few_far_larger_particles_as_the_dense_sum_does() -> None:
    ground = Ground.of(_scattered(GRID_FROM_LEDS, seed=4))
    rng = np.random.default_rng(5)
    small = swarm(rng.uniform(0.0, 15.0, (200, 3)), rng.uniform(0.0, 1.0, (200, 3)), 0.2)
    large = swarm(rng.uniform(0.0, 15.0, (3, 3)), rng.uniform(0.0, 1.0, (3, 3)), [2.0, 2.5, 3.0])
    particles = joined(small, large)

    dense = np.zeros((ground.leds.count, 3), dtype=np.float32)
    _densely(ground, particles, dense)

    np.testing.assert_allclose(lit(ground, particles), np.minimum(dense, 1.0), atol=1e-4)


def test_a_ground_keeps_a_few_grids_and_reuses_one_for_close_sizes() -> None:
    ground = Ground.of(_scattered(100, seed=3))

    assert ground.grid(0.9) is ground.grid(0.95)  # one size in √2 steps: 2^(1/2) m
    for size in np.linspace(0.05, 20.0, 40):
        ground.grid(float(size))
    assert len(ground._grids) <= 8


def test_draws_repeat_for_a_seed_and_key_and_differ_for_another() -> None:
    first = draws(7, [1, 2, 3], 4)
    assert first.shape == (3, 4)
    np.testing.assert_array_equal(first, draws(7, [1, 2, 3], 4))
    np.testing.assert_array_equal(first[1:2], draws(7, [2], 4))  # each key on its own
    assert not np.array_equal(first, draws(8, [1, 2, 3], 4))
    assert not np.array_equal(first[0], first[1])
    many = draws(7, np.arange(-5000, 5000), 2)  # negative keys too
    assert many.min() >= 0.0 and many.max() < 1.0
    assert abs(float(many.mean()) - 0.5) < 0.01


def test_each_stream_draws_its_own_numbers() -> None:
    assert not np.array_equal(draws(7, [1, 2], 3), draws(7, [1, 2], 3, stream=1))
    np.testing.assert_array_equal(draws(7, [1, 2], 3, stream=1), draws(7, [1, 2], 3, stream=1))


def test_recent_events_hold_every_event_alive_now() -> None:
    every, life = 0.5, 1.2
    for now in (0.0, 3.1, 10.3, 1e6 + 0.25):
        events = set(recent(now, every, life).tolist())
        for n in range(math.floor(now / every) - 10, math.floor(now / every) + 10):
            for u in (0.0, 0.5, 0.999):  # event n comes at (n + u) * every
                if (n + u) * every <= now < (n + u) * every + life:
                    assert n in events
        assert len(events) <= life / every + 3


def test_wanderers_stay_in_their_box_and_move_smoothly() -> None:
    u = draws(3, np.arange(20), WANDER_DRAWS)
    low, high = np.array([0.0, 1.0, 0.5]), np.array([4.0, 3.0, 2.5])
    speed = 0.5
    times = 1000.0 + np.arange(600) / 60  # ten seconds at 60 frames a second
    path = np.array([wander(u, float(t), speed, low, high) for t in times])  # (T, 20, 3)

    assert (path >= low - 1e-9).all() and (path <= high + 1e-9).all()
    steps = np.linalg.norm(np.diff(path, axis=0), axis=2)
    assert steps.max() <= 1.4 * speed * math.sqrt(3.0) / 60  # never a jump
    assert np.ptp(path[:, :, 0], axis=0).min() > 0.1  # each of them moves
    assert len({tuple(p) for p in np.round(path[0], 3)}) == 20  # each where it alone is


def test_each_wanderer_keeps_to_a_box_of_its_own() -> None:
    u = draws(5, np.arange(3), WANDER_DRAWS)
    low = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0]])
    for t in np.arange(0.0, 60.0, 0.5):
        where = wander(u, float(t), 1.0, low, low + 1.0)
        assert (where >= low - 1e-9).all() and (where <= low + 1.0 + 1e-9).all()


def test_a_wanderer_in_a_flat_box_keeps_to_it() -> None:
    u = draws(4, np.arange(5), WANDER_DRAWS)
    where = wander(u, 50.0, 0.3, [1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    np.testing.assert_allclose(where, 1.0, atol=0.05 + 1e-9)


def test_an_arc_goes_from_start_to_end_rising_half_way() -> None:
    start, end = np.array([[0.0, 0.0, 1.0]]), np.array([[2.0, 0.0, 1.0]])
    np.testing.assert_allclose(arc(start, end, [0.0], 0.5), start)
    np.testing.assert_allclose(arc(start, end, [1.0], 0.5), end)
    np.testing.assert_allclose(arc(start, end, [0.5], 0.5), [[1.0, 0.0, 1.5]])
    many = arc(start, end, np.linspace(0.0, 1.0, 5), 0.5)
    assert many.shape == (5, 3) and many[:, 2].max() == 1.5


def test_a_tour_visits_every_stop_each_round_and_never_stays() -> None:
    for stops in (3, 5, 11):
        visits = [tour(1, 0, step, stops) for step in range(-stops, 12 * stops)]
        assert all(a != b for a, b in zip(visits, visits[1:], strict=False))
        for start in range(0, len(visits), stops):
            assert sorted(visits[start : start + stops]) == list(range(stops))
    assert [tour(1, 0, step, 2) for step in range(4)] == [0, 1, 0, 1]
    assert {tour(1, 0, step, 1) for step in range(4)} == {0}
    tours = [[tour(1, key, step, 5) for step in range(10)] for key in range(3)]
    assert tours[0] != tours[1] != tours[2]  # each tour its own


def test_things_spread_over_every_stop_before_any_takes_two() -> None:
    taken = spread_over(1, 12, 5)
    assert sorted(taken[:5].tolist()) == list(range(5))
    assert np.bincount(taken, minlength=5).tolist().count(3) == 2  # 12 over 5: 3, 3, 2, 2, 2
    assert spread_over(1, 3, 1).tolist() == [0, 0, 0]
    assert not np.array_equal(spread_over(1, 5, 5), spread_over(2, 5, 5))


def test_each_light_is_a_stop_at_its_middle_with_its_lowest_and_highest_led() -> None:
    lamps = lamps_of(lights_at([(1.0, 1.0, 0.1), (1.0, 1.0, 1.5)], [(4.0, 2.0, 1.0)]))

    assert lamps.count == 2
    np.testing.assert_allclose(lamps.centre, [[1.0, 1.0, 0.8], [4.0, 2.0, 1.0]], atol=1e-6)
    np.testing.assert_allclose(lamps.low, [0.1, 1.0])
    np.testing.assert_allclose(lamps.high, [1.5, 1.0])
    assert lamps.members.tolist() == [0, 1, 2] and lamps.starts.tolist() == [0, 2, 3]


def test_a_stop_and_an_led_of_it_are_picked_alike() -> None:
    ground = Ground.of(lights_at([(0.0, 0.0, 1.0), (1.0, 0.0, 1.0)], [(5.0, 0.0, 1.0)]))
    lamps = ground.lamps

    assert lamps.pick([0.0, 0.49, 0.5, 0.999]).tolist() == [0, 0, 1, 1]
    assert lamps.led([0, 0, 1], [0.2, 0.7, 0.9]).tolist() == [0, 1, 2]
    np.testing.assert_allclose(ground.on([0, 1], [0.7, 0.0]), [[1.0, 0.0, 1.0], [5.0, 0.0, 1.0]])


def test_a_foot_is_under_an_led_at_its_lamps_lowest() -> None:
    ground = Ground.of(lights_at([(1.0, 1.0, 0.1), (1.0, 1.0, 1.5)], [(3.0, 0.0, 2.0)]))
    np.testing.assert_allclose(
        ground.foot([0, 0, 1], [0.9, 0.1, 0.5]), [[1.0, 1.0, 0.1]] * 2 + [[3.0, 0.0, 2.0]]
    )
    np.testing.assert_allclose(ground.foot(0, 0.9), [1.0, 1.0, 0.1])


def test_lights_at_one_spot_make_one_stop() -> None:
    near = SAME_STOP_M * 0.5
    parts = [[(2.0, 2.0, 0.8)], [(2.0 + near, 2.0, 0.9)], [(2.0, 2.0, 1.1)], [(6.0, 2.0, 1.0)]]

    lamps = lamps_of(lights_at(*parts))

    assert lamps.count == 2  # a device's parts share its placement: one stop
    np.testing.assert_allclose(lamps.low, [0.8, 1.0])
    np.testing.assert_allclose(lamps.high, [1.1, 1.0])
    assert lamps.members.tolist() == [0, 1, 2, 3] and lamps.starts.tolist() == [0, 3, 4]


def test_a_zone_with_no_leds_has_no_lamps() -> None:
    assert lamps_of(lights_at()).count == 0
    assert Ground.of(lights_at()).lamps.count == 0


def test_around_goes_round_the_middle() -> None:
    points = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]])
    assert list(around(points.astype(np.float32), np.zeros(3))) == [2, 1, 0, 3]


def test_the_floor_and_ceiling_are_the_maps_or_else_the_leds() -> None:
    lights = ([(1.0, 1.0, 0.5), (1.0, 1.0, 1.5)],)
    mapped = Ground.of(lights_at(*lights, ceiling=3.0))
    unmapped = Ground.of(lights_at(*lights, ceiling=None))

    assert (mapped.floor, mapped.ceiling) == (0.0, 3.0)
    assert (unmapped.floor, unmapped.ceiling) == pytest.approx((0.5, 1.5 + CEILING_OVER_M))


def test_a_box_is_the_frame_widened_and_kept_between_the_floor_and_ceiling() -> None:
    ground = Ground.of(lights_at([(1.0, 2.0, 0.2), (3.0, 4.0, 2.8)], ceiling=3.0))

    low, high = ground.box(0.5)

    np.testing.assert_allclose(low, [0.5, 1.5, 0.0])  # not below the floor
    np.testing.assert_allclose(high, [3.5, 4.5, 3.0])  # nor over the ceiling
    np.testing.assert_allclose(ground.box()[0], [1.0, 2.0, 0.2], atol=1e-6)
    low, high = ground.box(1.5, around=[2.0, 2.0, 2.0])
    np.testing.assert_allclose(low, [0.5, 0.5, 0.5])
    np.testing.assert_allclose(high, [3.5, 3.5, 3.0])
    low, high = ground.box(1.0, around=[[2.0, 2.0, 0.5], [5.0, 5.0, 2.5]])
    np.testing.assert_allclose(low, [[1.0, 1.0, 0.0], [4.0, 4.0, 1.5]])
    np.testing.assert_allclose(high, [[3.0, 3.0, 1.5], [6.0, 6.0, 3.0]])


def test_newest_keeps_the_last_particles() -> None:
    particles = swarm(np.arange(15.0).reshape(5, 3), [1.0, 1.0, 1.0], 0.2)
    newest = particles.newest(2)
    np.testing.assert_array_equal(newest.pos, particles.pos[3:])
    assert particles.newest(9) is particles


def test_joined_keeps_each_swarm_in_order_and_pick_keeps_the_marked() -> None:
    first = swarm([[0.0, 0.0, 0.0]], [1.0, 0.0, 0.0], 0.1)
    second = swarm([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], [0.0, 1.0, 0.0], [0.2, 0.3])
    both = joined(first, second)

    np.testing.assert_array_equal(both.pos[:, 0], [0.0, 1.0, 2.0])
    np.testing.assert_allclose(both.radius, [0.1, 0.2, 0.3])
    picked = both.pick(np.array([True, False, True]))
    np.testing.assert_array_equal(picked.pos[:, 0], [0.0, 2.0])
    np.testing.assert_array_equal(picked.colour, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


# Spec §4.1's budget past 2k LEDs: 500 particles of a usual size on 10k LEDs, by the grid.
@pytest.mark.perf
def test_500_particles_light_10k_leds_in_the_frame_budget() -> None:
    ground = Ground.of(_scattered(10_000, seed=6))
    rng = np.random.default_rng(7)
    particles = swarm(rng.uniform(0.0, 15.0, (500, 3)), rng.uniform(0.0, 1.0, (500, 3)), 0.2)
    lit(ground, particles)  # the grid is made once for each size
    durations = []
    for _ in range(60):
        started = time.perf_counter()
        lit(ground, particles)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < FRAME_BUDGET_S
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects/test_particle_tools.py -q 2>&1 | tail -3`
Expected: FAIL: a collection error, `ModuleNotFoundError: No module named 'dj_ledfx.effects.particle_tools'`.

- [ ] **Step 3: Write the toolkit**

Create `src/dj_ledfx/effects/particle_tools.py`:

```python
"""What particle effects share (spec §5.1): the particles of a moment, the random numbers
they're drawn from, the zone's lamps, and how particles light LEDs. Pure numpy.

A particle lights each LED by a Gaussian falloff with its distance, out to REACH radii,
and the LEDs add up what reaches them. Below GRID_FROM_LEDS LEDs every LED is measured
against every particle; from it on (spec §4.1: "Past about 2k LEDs, particles switch to a
spatial grid") only the LEDs in the grid cells around each particle are, with the same
colours.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

if TYPE_CHECKING:
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

F32 = NDArray[np.float32]
F64 = NDArray[np.float64]

REACH = 2.5  # a particle lights nothing past this many radii: under half an 8-bit step
GRID_FROM_LEDS = 2000  # from this many LEDs on, lit() looks only near each particle
SAME_STOP_M = 0.3  # lights whose middles are this close make one stop
CEILING_OVER_M = 0.5  # with no map, the ceiling is this far over the highest LED
MIN_RADIUS_M = 0.01  # a particle's light falls off over at least this
_GRID_SIZES = 8  # the grids a Ground keeps, one per cell size

_GOLDEN = np.uint64(0x9E3779B97F4A7C15)
_STREAMS = 0xD1B54A32D192ED03  # each stream starts this far on from the last
_MIX = (np.uint64(0xBF58476D1CE4E5B9), np.uint64(0x94D049BB133111EB))
_SHIFTS = (np.uint64(30), np.uint64(27), np.uint64(31))


@dataclass(frozen=True, eq=False, slots=True)
class Particles:
    """Where a particle effect's particles are at one moment: each one's position in
    metres on the map's axes, as the layer sees them (a layer's mirror or transform moves
    them with the LEDs), its colour 0..1 with its brightness in it, and its radius in
    metres, which sets how far its light falls (lit()). Oldest first."""

    pos: F32  # (P, 3)
    colour: F32  # (P, 3)
    radius: F32  # (P,)

    @property
    def count(self) -> int:
        return int(self.pos.shape[0])

    def newest(self, count: int) -> Particles:
        """The `count` newest: the last ones."""
        if self.count <= count:
            return self
        return Particles(self.pos[-count:], self.colour[-count:], self.radius[-count:])

    def pick(self, which: NDArray[np.bool_]) -> Particles:
        """The particles `which` marks, in order."""
        return Particles(self.pos[which], self.colour[which], self.radius[which])


def swarm(pos: ArrayLike, colour: ArrayLike, radius: ArrayLike) -> Particles:
    """Particles from positions (P, 3), colours (P, 3) or one colour (3,), and radii (P,)
    or one radius (at least MIN_RADIUS_M), as float32 arrays of their own."""
    where = np.array(pos, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    colours = np.broadcast_to(np.asarray(colour, dtype=np.float32), (count, 3)).copy()
    radii = np.maximum(
        np.broadcast_to(np.asarray(radius, dtype=np.float32), (count,)), MIN_RADIUS_M
    )
    return Particles(where, colours, radii.astype(np.float32))


NO_PARTICLES = swarm(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0))


def joined(*parts: Particles) -> Particles:
    """Several swarms as one, in order: the first's particles are the oldest."""
    return Particles(
        np.concatenate([part.pos for part in parts]),
        np.concatenate([part.colour for part in parts]),
        np.concatenate([part.radius for part in parts]),
    )


def _mix(x: NDArray[np.uint64]) -> NDArray[np.uint64]:
    """SplitMix64's finaliser: every bit of x stirred into every bit of the result."""
    x = (x ^ (x >> _SHIFTS[0])) * _MIX[0]
    x = (x ^ (x >> _SHIFTS[1])) * _MIX[1]
    mixed: NDArray[np.uint64] = x ^ (x >> _SHIFTS[2])
    return mixed


def draws(seed: int, keys: ArrayLike, count: int, stream: int = 0) -> F64:
    """`count` random numbers from 0 to 1 (1 left out) for each key, shape (keys, count),
    from the seed, the stream and the key alone: a key is an event (a particle, a beat's
    burst), so the same seed and key give the same numbers however the frames fall, and an
    effect gives each kind of event its own stream. ParamSettings._rng's counter-based
    twin, for many particles at once."""
    k = np.asarray(keys, dtype=np.int64).astype(np.uint64).reshape(-1, 1)
    j = np.arange(1, count + 1, dtype=np.uint64).reshape(1, -1)
    base = np.uint64((seed + stream * _STREAMS) % 2**64)
    first = _mix(k * _GOLDEN + base)
    bits = _mix(first + j * _GOLDEN)
    values: F64 = (bits >> np.uint64(11)).astype(np.float64) * 2.0**-53
    return values


def recent(now: float, every: float, life: float) -> NDArray[np.int64]:
    """The events that may be alive at `now`: event n comes at (n + u) * every, u from 0 to
    1, and lives `life`. In seconds or in beats alike."""
    first = math.floor((now - life) / every) - 1
    return np.arange(first, math.floor(now / every) + 1, dtype=np.int64)


WANDER_DRAWS = 12  # the random numbers a wanderer takes


def wander(u: F64, t: float, speed: float, low: ArrayLike, high: ArrayLike) -> F64:
    """Where each wanderer is at time t, inside the box from low to high (one box, (3,), or
    one each, (wanderers, 3)): two slow waves on each axis, of periods and phases from its
    WANDER_DRAWS random numbers (a row of u), so it moves smoothly and never repeats for
    long, at about `speed` metres a second. Shape (wanderers, 3)."""
    low64, high64 = np.asarray(low, dtype=np.float64), np.asarray(high, dtype=np.float64)
    half = np.maximum((high64 - low64) / 2.0, 0.05)
    rate = (0.6 + 0.8 * u[:, :6]).reshape(-1, 2, 3) * (speed / half)[..., None, :]  # rad/s
    phase = 2.0 * math.pi * u[:, 6:].reshape(-1, 2, 3)
    waves = np.sin(rate * t + phase)
    where: F64 = (low64 + high64) / 2.0 + half * (0.6 * waves[:, 0] + 0.4 * waves[:, 1])
    return where


def arc(start: ArrayLike, end: ArrayLike, share: ArrayLike, rise: ArrayLike) -> F64:
    """Points `share` (0..1) of the way from start to end, each on a parabola that rises
    `rise` metres over the straight line half-way: a hop, a bounce or a throw. With share in
    proportion to the time, it's a thrown thing's path. Shape (points, 3)."""
    a, b = np.asarray(start, dtype=np.float64), np.asarray(end, dtype=np.float64)
    part = np.asarray(share, dtype=np.float64)
    where: F64 = np.array(a + (b - a) * part[..., None], dtype=np.float64, ndmin=2)
    where[:, 2] += (4.0 * np.asarray(rise) * part * (1.0 - part)).ravel()
    return where


TOURS = 1000  # tour k draws from stream TOURS + k


def tour(seed: int, key: int, step: int, stops: int) -> int:
    """The stop tour `key` is at on its step `step`, of `stops` stops (at least one): each
    round of `stops` steps visits every stop once, in an order of its own, and a tour never
    stays on one stop two steps running (with two stops it goes to and fro, with one it
    stays)."""
    if stops < 3:
        return step % stops
    round_, place = divmod(step, stops)
    order = shuffled(seed, key, round_, stops)
    if place < 2 and order[0] == shuffled(seed, key, round_ - 1, stops)[-1]:
        order[[0, 1]] = order[[1, 0]]
    return int(order[place])


def shuffled(seed: int, key: int, round_: int, stops: int) -> NDArray[np.intp]:
    """Round `round_` of tour `key`: the stops in the order its random numbers put them."""
    order: NDArray[np.intp] = np.argsort(
        draws(seed, [round_], stops, stream=TOURS + key)[0], kind="stable"
    )
    return order


def spread_over(seed: int, count: int, stops: int) -> NDArray[np.intp]:
    """The stop each of `count` things takes, of `stops` (at least one): every stop once
    before any twice, in an order the seed picks."""
    taken: NDArray[np.intp] = shuffled(seed, 0, 0, stops)[np.arange(count) % stops]
    return taken


@dataclass(frozen=True, eq=False, slots=True)
class Lamps:
    """The zone's lamps, where particles find them (spec §5.1: emitters, paths and targets
    can be lamps). One stop for each light, and one for lights whose middles are within
    SAME_STOP_M of one another (a device's parts share its placement): each stop's middle,
    the heights of its lowest and highest LED, and its LEDs."""

    centre: F32  # (S, 3)
    low: F32  # (S,)
    high: F32  # (S,)
    members: NDArray[np.intp]  # the zone's LEDs, stop by stop, each stop's in zone order
    starts: NDArray[np.intp]  # (S + 1,): stop s's LEDs are members[starts[s]:starts[s + 1]]

    @property
    def count(self) -> int:
        return int(self.centre.shape[0])

    def pick(self, u: ArrayLike) -> NDArray[np.intp]:
        """The stop each u (0..1) picks, each stop alike."""
        picked: NDArray[np.intp] = np.minimum(
            (np.asarray(u, dtype=np.float64) * self.count).astype(np.intp), self.count - 1
        )
        return picked

    def led(self, stop: ArrayLike, u: ArrayLike) -> NDArray[np.intp]:
        """An LED of each stop, the one u (0..1) picks of its LEDs: its index in the zone."""
        stops = np.asarray(stop, dtype=np.intp)
        first, many = self.starts[stops], self.starts[stops + 1] - self.starts[stops]
        place = np.minimum((np.asarray(u, dtype=np.float64) * many).astype(np.intp), many - 1)
        led: NDArray[np.intp] = self.members[first + place]
        return led


NO_LAMPS = Lamps(
    np.zeros((0, 3), np.float32),
    np.zeros(0, np.float32),
    np.zeros(0, np.float32),
    np.zeros(0, np.intp),
    np.zeros(1, np.intp),
)


def lamps_of(leds: LedSet) -> Lamps:
    """The stops the LEDs make, in the zone's order: each light's LEDs, joined with the
    stop before whose first light's middle is within SAME_STOP_M."""
    groups: list[list[NDArray[np.intp]]] = []
    firsts: list[NDArray[np.float32]] = []
    for piece in leds.slices:
        if piece.count == 0:
            continue
        middle = leds.pos[piece.start : piece.stop].mean(axis=0)
        near = next(
            (i for i, first in enumerate(firsts) if np.linalg.norm(first - middle) <= SAME_STOP_M),
            None,
        )
        which = np.arange(piece.start, piece.stop, dtype=np.intp)
        if near is None:
            firsts.append(middle)
            groups.append([which])
        else:
            groups[near].append(which)
    if not groups:
        return NO_LAMPS
    members = [np.concatenate(group) for group in groups]
    heights = [leds.pos[which, 2] for which in members]
    return Lamps(
        centre=np.array(
            [np.mean([leds.pos[w].mean(axis=0) for w in group], axis=0) for group in groups],
            dtype=np.float32,
        ),
        low=np.array([z.min() for z in heights], dtype=np.float32),
        high=np.array([z.max() for z in heights], dtype=np.float32),
        members=np.concatenate(members),
        starts=np.cumsum([0, *(len(which) for which in members)]).astype(np.intp),
    )


def around(points: F32, middle: NDArray[np.floating[Any]]) -> NDArray[np.intp]:
    """The points' order round the middle, seen from above: a loop round the room."""
    offset = points[:, :2].astype(np.float64) - np.asarray(middle, dtype=np.float64)[:2]
    order: NDArray[np.intp] = np.argsort(np.arctan2(offset[:, 1], offset[:, 0]), kind="stable")
    return order


@dataclass(frozen=True, slots=True)
class _Grid:
    """The LEDs sorted by grid cell: the cells' keys in order, the LEDs in that order, and
    how keys are made (the origin, the cell size and the cell counts along each axis)."""

    keys: NDArray[np.int64]
    order: NDArray[np.intp]
    origin: F32
    size: float
    dims: NDArray[np.int64]

    def key(self, cells: NDArray[np.int64]) -> NDArray[np.int64]:
        """Each cell's key; a cell outside the grid is one of its edge cells, which hold no
        LEDs."""
        cells = np.clip(cells, 0, self.dims - 1)
        keys: NDArray[np.int64] = (cells[..., 0] * self.dims[1] + cells[..., 1]) * self.dims[
            2
        ] + cells[..., 2]
        return keys

    def cells(self, points: F32) -> NDArray[np.int64]:
        cells: NDArray[np.int64] = np.floor((points - self.origin) / np.float32(self.size)).astype(
            np.int64
        )
        return cells


_NEIGHBOURS = np.array(
    [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)], dtype=np.int64
)


@dataclass(frozen=True, eq=False)
class Ground:
    """Where a particle effect's particles move, worked out once for each LED set: the
    LEDs, their lamps, the zone's frame (the set's bounds, which a layer's view keeps), its
    floor and its ceiling. The floor is the map's (height 0) and the ceiling the map's
    under a map; with none, the lowest LED and CEILING_OVER_M over the highest."""

    leds: LedSet
    lamps: Lamps
    floor: float
    ceiling: float
    _grids: dict[float, _Grid] = field(default_factory=dict)

    @classmethod
    def of(cls, leds: LedSet) -> Ground:
        low, high = leds.bounds
        ceiling = leds.space.ceiling
        if ceiling is not None and ceiling > 0.0:
            return cls(leds, lamps_of(leds), 0.0, float(ceiling))
        return cls(leds, lamps_of(leds), float(low[2]), float(high[2]) + CEILING_OVER_M)

    @property
    def low(self) -> F32:
        return self.leds.bounds[0]

    @property
    def high(self) -> F32:
        return self.leds.bounds[1]

    @property
    def centre(self) -> F32:
        return self.leds.centre

    def on(self, stop: ArrayLike, u: ArrayLike) -> F64:
        """Where an LED of each stop is: the one u (0..1) picks (Lamps.led), so particles
        spread along a long light as they do round a short one."""
        on: F64 = self.leds.pos[self.lamps.led(stop, u)].astype(np.float64)
        return on

    def foot(self, stop: ArrayLike, u: ArrayLike) -> F64:
        """An LED of each stop seen from above (the one u picks, as on() picks it), down at
        the height of the stop's lowest LED: where a thing rising up the lamp starts, or
        one landing on it lands."""
        foot = self.on(stop, u)
        foot[..., 2] = self.lamps.low[np.asarray(stop, dtype=np.intp)]
        return foot

    def box(self, margin: float = 0.0, around: ArrayLike | None = None) -> tuple[F64, F64]:
        """Where particles that roam stay: the zone's frame `margin` metres wider each way,
        or `margin` each way round each point (shape (3,) or (P, 3)), between the floor and
        the ceiling."""
        if around is None:
            low, high = self.low.astype(np.float64), self.high.astype(np.float64)
        else:
            low = high = np.asarray(around, dtype=np.float64)
        low, high = low - margin, high + margin
        low[..., 2] = np.maximum(low[..., 2], self.floor)
        high[..., 2] = np.minimum(high[..., 2], self.ceiling)
        return low, high

    @cached_property
    def _from_centre(self) -> tuple[F32, F32]:
        """Each LED's place from the frame's centre, and its square length."""
        pos: F32 = (self.leds.pos - self.centre).astype(np.float32)
        return pos, np.einsum("ij,ij->i", pos, pos)

    def grid(self, size: float) -> _Grid:
        """The LEDs in cells at least `size` wide (a power of √2 metres, so only a few
        sizes are ever kept), each LED at least one cell in from the grid's edge."""
        width = 2.0 ** (math.ceil(2.0 * math.log2(max(size, 0.01))) / 2.0)
        grid = self._grids.get(width)
        if grid is None:
            if len(self._grids) >= _GRID_SIZES:
                self._grids.clear()
            origin = (self.low - np.float32(width)).astype(np.float32)
            cells = np.floor((self.leds.pos - origin) / np.float32(width)).astype(np.int64)
            np.maximum(cells, 1, out=cells)  # rounding never puts an LED in an edge cell
            dims = cells.max(axis=0) + 2 if len(cells) else np.full(3, 2, dtype=np.int64)
            unsorted = _Grid(np.zeros(0, np.int64), np.zeros(0, np.intp), origin, width, dims)
            keys = unsorted.key(cells)
            order = np.argsort(keys, kind="stable")
            grid = self._grids[width] = _Grid(keys[order], order, origin, width, dims)
        return grid


def lit(ground: Ground, particles: Particles) -> FloatRGB:
    """Each LED's light from the particles (spec §5.1: "Particles light LEDs by distance
    falloff"): the sum of each particle's colour times exp(-(d / r)²), d its distance from
    the LED and r its radius, out to REACH radii, and at most 1. A new float32 array."""
    count = ground.leds.count
    out = np.zeros((count, 3), dtype=np.float32)
    if count == 0 or particles.count == 0:
        return out
    if count < GRID_FROM_LEDS:
        _densely(ground, particles, out)
    else:  # the grid's cells fit the usual sizes; the few far larger light every LED anyway
        large = particles.radius > np.float32(2.0) * np.median(particles.radius)
        if large.any():
            _densely(ground, particles.pick(large), out)
            particles = particles.pick(~large)
        _by_grid(ground, particles, out)
    np.minimum(out, np.float32(1.0), out=out)
    return out


def _densely(ground: Ground, particles: Particles, out: FloatRGB) -> None:
    """Every LED against every particle, as one matrix product."""
    pos, square = ground._from_centre
    at = (particles.pos - ground.centre).astype(np.float32)
    gap = square[:, None] + np.einsum("ij,ij->i", at, at)[None, :] - 2.0 * (pos @ at.T)
    np.maximum(gap, np.float32(0.0), out=gap)  # (N, P) square distances
    reach = particles.radius * particles.radius
    weight = np.exp(-gap / reach)
    weight[gap > np.float32(REACH * REACH) * reach] = 0.0
    out += (weight @ particles.colour).astype(np.float32)


def _by_grid(ground: Ground, particles: Particles, out: FloatRGB) -> None:
    """Only the LEDs in the 27 cells round each particle's, the cells REACH radii of the
    largest particle wide: each pair of a particle and an LED near it, gathered at once."""
    if particles.count == 0:
        return
    grid = ground.grid(REACH * float(particles.radius.max()))
    near = grid.key(grid.cells(particles.pos)[:, None, :] + _NEIGHBOURS[None, :, :])  # (P, 27)
    first = np.searchsorted(grid.keys, near, side="left").ravel()
    many = np.searchsorted(grid.keys, near, side="right").ravel() - first
    pairs = int(many.sum())
    if pairs == 0:
        return
    whose = np.repeat(np.repeat(np.arange(particles.count), len(_NEIGHBOURS)), many)
    step = np.arange(pairs) - np.repeat(np.cumsum(many) - many, many)
    led = grid.order[np.repeat(first, many) + step]
    gap = ground.leds.pos[led] - particles.pos[whose]
    square = np.einsum("ij,ij->i", gap, gap)
    reach = particles.radius[whose] * particles.radius[whose]
    weight = np.exp(-square / reach)
    weight[square > np.float32(REACH * REACH) * reach] = 0.0
    for channel in range(3):
        out[:, channel] += np.bincount(
            led, weights=weight * particles.colour[whose, channel], minlength=len(out)
        ).astype(np.float32)
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/effects/test_particle_tools.py -q 2>&1 | tail -1 && uv run pytest tests/effects/test_particle_tools.py -m perf -q 2>&1 | tail -1`
Expected: PASS (26 tests), then the perf test: `1 passed`, 500 particles lighting 10,000 LEDs within the budget.

- [ ] **Step 5: Run the gate**

```bash
uv run ruff format src/dj_ledfx/effects/particle_tools.py tests/effects/test_particle_tools.py tests/map_home.py
uv run ruff check --fix src/dj_ledfx/effects/particle_tools.py tests/effects/test_particle_tools.py tests/map_home.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `All checks passed!`, `341 files already formatted`, mypy's 16 errors (`checked 154 source files`), `2055 passed, 1 skipped, 43 deselected` (Before Task 1's 2029 and this task's 26) and `43 passed` in the perf run (this task's one more).

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/particle_tools.py tests/effects/test_particle_tools.py tests/map_home.py
git commit -m "feat(effects): the particle toolkit: particles, draws by event, lamps, ground and light"
```

---


### Task 2: The particle effect kind

`ParticleEffect` joins `FieldEffect` and `FirmwareEffect` (spec §5.1), with the `place` and `particles` this plan adds (ruling 1). `ParamParticles` keeps its settings as `ParamField` does, so the settings machinery moves out of `ParamField` into `ParamSettings` in `effects/base.py`, which both build on. `ParamField` behaves as before: every field effect's tests still pass, unchanged. `ParamParticles` works its particles out in closed form (ruling 2), keeps the newest 500 (ruling 9), and never asks an effect for particles on a zone with no LEDs.

**Files:**
- Create: `src/dj_ledfx/effects/particles.py`, `tests/effects/test_particles.py`
- Modify: `src/dj_ledfx/effects/base.py`, `src/dj_ledfx/effects/field.py`

**Interfaces:**
- Consumes: Task 1's `Ground` (`Ground.of`), `Particles`, `NO_PARTICLES`, `swarm` and `lit`.
- Produces:
  - `effects.base.ParamSettings(Effect, register=False)`: `__init__(**settings)` (unknown settings raise `TypeError`; defaults filled in), `get_params()`, `reseed(seed)` (sets `_seed`), `_rng(k)`, `_apply_params(**kwargs)`, `_prepare()` (a `palette` setting's float palette in `_palette`) and `_per_leds(leds, build)`, all moved unchanged from `ParamField`. `ParamField(ParamSettings, FieldEffect)` keeps its name and behaviour.
  - `effects.particles`: `MAX_PARTICLES = 500`; `ParticleEffect(Effect)`, abstract: `place(leds: LedSet) -> None`, `step(ctx: RenderContext) -> None`, `sample(ctx: RenderContext, leds: LedSet) -> FloatRGB` and the property `particles -> Particles`; `ParamParticles(ParamSettings, ParticleEffect)`, whose subclasses write one method, `positions(ctx: RenderContext, ground: Ground) -> Particles` (called only for a ground with at least one LED), with `place()` keeping the `Ground` of the set until another set comes, `step()` keeping the newest `MAX_PARTICLES`, and `sample()` lighting the LEDs with `lit()`; `drawn(effect: ParticleEffect, ctx: RenderContext, leds: LedSet) -> FloatRGB`, the three calls a frame makes.

- [ ] **Step 1: Write the failing tests**

Create `tests/effects/test_particles.py`:

```python
from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest
from conftest import render_ctx
from map_home import ROW, leds_at

from dj_ledfx.effects.base import ParamSettings
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import Ground, Particles, swarm
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles, ParticleEffect, drawn


class _Dots(ParamParticles, register=False):
    """`count` dots in a row along x from the zone's west end, 0.5 m apart, at `t` metres
    east: each the palette's first colour. `grounds` keeps every Ground it moved on."""

    grounds: ClassVar[list[Ground]] = []

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "count": EffectParam(type="int", default=1, min=0, max=2000),
            "palette": EffectParam(type="color_list", default=["#ff0000"]),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        assert ground.leds.count > 0
        _Dots.grounds.append(ground)
        count = int(self._values["count"])
        x = ground.low[0] + ctx.t + 0.5 * np.arange(count)
        pos = np.stack([x, np.zeros(count), np.full(count, 1.0)], axis=1)
        return swarm(pos, self._palette[0], 0.25)


@pytest.fixture(autouse=True)
def _grounds() -> None:
    _Dots.grounds = []


def test_particle_and_field_effects_keep_their_settings_alike() -> None:
    assert issubclass(ParamParticles, ParamSettings) and issubclass(ParamField, ParamSettings)
    dots = _Dots(count=3)
    assert dots.get_params() == {"count": 3, "palette": ["#ff0000"]}
    np.testing.assert_allclose(dots._palette, [[1.0, 0.0, 0.0]])
    with pytest.raises(TypeError, match="no setting speed"):
        _Dots(speed=1.0)


def test_a_step_moves_the_particles_to_the_moment_and_sample_lights_the_leds() -> None:
    leds = leds_at(ROW)  # 0.5 m apart from x = 0
    dots = _Dots()
    dots.place(leds)

    dots.step(render_ctx(t=1.0))

    assert isinstance(dots, ParticleEffect)
    np.testing.assert_allclose(dots.particles.pos, [[1.0, 0.0, 1.0]])
    frame = dots.sample(render_ctx(t=1.0), leds)
    assert frame.shape == (9, 3) and frame.dtype == np.float32
    assert int(np.argmax(frame[:, 0])) == 2  # the LED at 1 m
    assert not frame[:, 1:].any()


def test_drawn_places_steps_and_samples() -> None:
    leds = leds_at(ROW)
    dots = _Dots()
    first = drawn(dots, render_ctx(t=0.5), leds)
    later = drawn(dots, render_ctx(t=2.0), leds)
    assert int(np.argmax(first[:, 0])) == 1 and int(np.argmax(later[:, 0])) == 4


def test_the_ground_is_made_once_for_each_led_set() -> None:
    leds, other = leds_at(ROW), leds_at(ROW[:4])
    dots = _Dots()
    for t in (0.0, 0.1, 0.2):
        drawn(dots, render_ctx(t=t), leds)
    assert len({id(ground) for ground in _Dots.grounds}) == 1
    drawn(dots, render_ctx(t=0.3), other)
    assert _Dots.grounds[-1].leds is other


def test_a_step_keeps_the_newest_500() -> None:
    dots = _Dots(count=MAX_PARTICLES + 300)
    dots.place(leds_at(ROW))
    dots.step(render_ctx(t=0.0))
    assert dots.particles.count == MAX_PARTICLES
    np.testing.assert_allclose(dots.particles.pos[0, 0], 0.5 * 300)  # the oldest 300 dropped


def test_no_leds_or_no_place_give_no_particles() -> None:
    dots = _Dots(count=4)
    dots.step(render_ctx(t=1.0))  # never placed
    assert dots.particles.count == 0
    empty = leds_at([])
    frame = drawn(dots, render_ctx(t=1.0), empty)
    assert frame.shape == (0, 3)
    assert dots.particles.count == 0
    assert not _Dots.grounds  # positions() never ran: every effect has an LED to go by


def test_a_settings_change_applies_at_the_next_step() -> None:
    leds = leds_at(ROW)
    dots = _Dots(count=1)
    drawn(dots, render_ctx(t=0.0), leds)
    dots.set_params(count=3, palette=["#00ff00"])
    frame = drawn(dots, render_ctx(t=0.0), leds)
    assert dots.particles.count == 3
    assert frame[:, 1].max() > 0.9 and not frame[:, 0].any()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects/test_particles.py -q 2>&1 | tail -3`
Expected: FAIL: a collection error, `ImportError: cannot import name 'ParamSettings' from 'dj_ledfx.effects.base'`.

- [ ] **Step 3: Move the settings into `ParamSettings`, and add the particle kind**

In `src/dj_ledfx/effects/base.py`:

```diff
--- a/src/dj_ledfx/effects/base.py
+++ b/src/dj_ledfx/effects/base.py
@@ -5,14 +5,22 @@ from __future__ import annotations
 import inspect
 import re
 from abc import ABC, abstractmethod
-from typing import Any, ClassVar
+from collections.abc import Callable
+from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast

 import numpy as np
 from numpy.typing import NDArray

+from dj_ledfx.effects.color import palette_float
 from dj_ledfx.effects.params import EffectParam, check_setting
 from dj_ledfx.types import BeatContext

+if TYPE_CHECKING:
+    from dj_ledfx.effects.ledset import LedSet
+    from dj_ledfx.types import FloatRGB
+
+T = TypeVar("T")
+

 def _to_snake_case(name: str) -> str:
     s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
@@ -69,6 +77,67 @@ class Effect(ABC):  # noqa: B024
         """Make the effect's randomness repeatable. Default: it has none."""


+class ParamSettings(Effect, register=False):
+    """An effect that keeps its settings in one dict: the field effects (ParamField) and
+    the particle effects (ParamParticles).
+
+    parameters() states each setting and its default once: __init__ takes settings by
+    name and fills in the defaults (None, or an empty list for a list setting, is the
+    default). The effect reads self._values. _prepare() rebuilds what's derived from the
+    settings (here, a "palette" setting's float palette in self._palette), and
+    _per_leds() keeps what depends only on the LEDs and the settings until either
+    changes. Randomness goes through reseed(), which sets self._seed.
+    """
+
+    _values: dict[str, Any]
+    _palette: FloatRGB
+    _seed: int = 0
+
+    def __init__(self, **settings: Any) -> None:
+        schema = self.parameters()
+        unknown = sorted(set(settings) - set(schema))
+        if unknown:
+            raise TypeError(f"{type(self).__name__} has no setting {', '.join(unknown)}")
+        values: dict[str, Any] = {}
+        for name, param in schema.items():
+            value = settings.get(name)
+            if isinstance(param.default, list):
+                values[name] = list(value or param.default)
+            else:
+                values[name] = param.default if value is None else value
+        self._apply_params(**values)
+
+    def get_params(self) -> dict[str, Any]:
+        return dict(self._values)
+
+    def reseed(self, seed: int) -> None:
+        self._seed = seed
+
+    def _rng(self, k: int) -> np.random.Generator:
+        """The random numbers of draw k (a drop, a beat): the same seed and k always give
+        the same ones, however the frames fall."""
+        return np.random.default_rng([self._seed % 2**32, k % 2**63])
+
+    def _apply_params(self, **kwargs: Any) -> None:
+        self._values = {**getattr(self, "_values", {}), **kwargs}
+        self._kept_for: LedSet | None = None
+        self._prepare()
+
+    def _prepare(self) -> None:
+        """Rebuild anything derived from the settings. A subclass that adds to this calls
+        super()._prepare()."""
+        if "palette" in self._values:
+            self._palette = palette_float(self._values["palette"])
+
+    def _per_leds(self, leds: LedSet, build: Callable[[LedSet], T]) -> T:
+        """What build makes of these LEDs with the current settings, kept until the LED
+        set or a setting changes."""
+        if self._kept_for is not leds:
+            self._kept: Any = build(leds)
+            self._kept_for = leds
+        return cast(T, self._kept)
+
+
 class StripEffect(Effect):
     """Today's 1D effects: a strip of `led_count` LEDs in 8-bit RGB."""

```

In `src/dj_ledfx/effects/field.py`, `ParamField` keeps only its name and its kind:

```diff
--- a/src/dj_ledfx/effects/field.py
+++ b/src/dj_ledfx/effects/field.py
@@ -3,21 +3,15 @@
 from __future__ import annotations

 from abc import abstractmethod
-from collections.abc import Callable
-from typing import TYPE_CHECKING, Any, TypeVar, cast
+from typing import TYPE_CHECKING

-import numpy as np
-
-from dj_ledfx.effects.base import Effect
-from dj_ledfx.effects.color import palette_float
+from dj_ledfx.effects.base import Effect, ParamSettings

 if TYPE_CHECKING:
     from dj_ledfx.effects.context import RenderContext
     from dj_ledfx.effects.ledset import LedSet
     from dj_ledfx.types import FloatRGB

-T = TypeVar("T")
-

 class FieldEffect(Effect):
     @abstractmethod
@@ -25,61 +19,6 @@ class FieldEffect(Effect):
         """Return shape (leds.count, 3) float32, 0..1 per channel, vectorised numpy."""


-class ParamField(FieldEffect):
-    """A field effect that keeps its settings in one dict.
-
-    parameters() states each setting and its default once: __init__ takes settings by
-    name and fills in the defaults (None, or an empty list for a list setting, is the
-    default). render reads self._values. _prepare() rebuilds what's derived from the
-    settings (here, a "palette" setting's float palette in self._palette), and
-    _per_leds() keeps what depends only on the LEDs and the settings until either
-    changes. Randomness goes through reseed(), which sets self._seed.
-    """
-
-    _values: dict[str, Any]
-    _palette: FloatRGB
-    _seed: int = 0
-
-    def __init__(self, **settings: Any) -> None:
-        schema = self.parameters()
-        unknown = sorted(set(settings) - set(schema))
-        if unknown:
-            raise TypeError(f"{type(self).__name__} has no setting {', '.join(unknown)}")
-        values: dict[str, Any] = {}
-        for name, param in schema.items():
-            value = settings.get(name)
-            if isinstance(param.default, list):
-                values[name] = list(value or param.default)
-            else:
-                values[name] = param.default if value is None else value
-        self._apply_params(**values)
-
-    def get_params(self) -> dict[str, Any]:
-        return dict(self._values)
-
-    def reseed(self, seed: int) -> None:
-        self._seed = seed
-
-    def _rng(self, k: int) -> np.random.Generator:
-        """The random numbers of draw k (a drop, a beat): the same seed and k always give
-        the same ones, however the frames fall."""
-        return np.random.default_rng([self._seed % 2**32, k % 2**63])
-
-    def _apply_params(self, **kwargs: Any) -> None:
-        self._values = {**getattr(self, "_values", {}), **kwargs}
-        self._kept_for: LedSet | None = None
-        self._prepare()
-
-    def _prepare(self) -> None:
-        """Rebuild anything derived from the settings. A subclass that adds to this calls
-        super()._prepare()."""
-        if "palette" in self._values:
-            self._palette = palette_float(self._values["palette"])
-
-    def _per_leds(self, leds: LedSet, build: Callable[[LedSet], T]) -> T:
-        """What build makes of these LEDs with the current settings, kept until the LED
-        set or a setting changes."""
-        if self._kept_for is not leds:
-            self._kept: Any = build(leds)
-            self._kept_for = leds
-        return cast(T, self._kept)
+class ParamField(ParamSettings, FieldEffect):
+    """A field effect that keeps its settings in one dict (ParamSettings): render reads
+    self._values."""
```

Create `src/dj_ledfx/effects/particles.py`:

```python
"""Particle effects (spec §5.1): particles that move through the home, emitted from, led
along and drawn to its anchors and lamps, lighting the LEDs near them.

A particle effect is placed among a layer's LEDs (place()), moves its particles to a
moment (step()) and lights the LEDs from them (sample()). ParamParticles keeps its
settings as a field effect does and works its particles out from the moment, the seed and
the LEDs alone (positions()), so the same moment always gives the same particles: frames
repeat, a twin draws what its zone draws, and a particle that lands on a beat lands on it
however the frames fall.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from dj_ledfx.effects.base import Effect, ParamSettings
from dj_ledfx.effects.particle_tools import NO_PARTICLES, Ground, Particles, lit

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

MAX_PARTICLES = 500  # spec §5.1: "capped at about 500"; step() keeps the newest


class ParticleEffect(Effect):
    @abstractmethod
    def place(self, leds: LedSet) -> None:
        """Where the particles move: the layer's view of its zone's LEDs. Cheap to call
        again with the same set."""

    @abstractmethod
    def step(self, ctx: RenderContext) -> None:
        """Move the particles to ctx's moment."""

    @abstractmethod
    def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Each LED's light from the particles: shape (leds.count, 3) float32, 0..1."""

    @property
    @abstractmethod
    def particles(self) -> Particles:
        """The particles of the last step, oldest first."""


class ParamParticles(ParamSettings, ParticleEffect):
    """A particle effect that keeps its settings in one dict (ParamSettings) and its
    particles in closed form: positions() gives the particles at any moment from the
    moment, the seed and the Ground alone."""

    _ground: Ground | None = None
    _particles: Particles = NO_PARTICLES

    def place(self, leds: LedSet) -> None:
        self._placed(leds)

    def step(self, ctx: RenderContext) -> None:
        ground = self._ground
        if ground is None or ground.leds.count == 0:
            self._particles = NO_PARTICLES
            return
        self._particles = self.positions(ctx, ground).newest(MAX_PARTICLES)

    def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return lit(self._placed(leds), self._particles)

    @property
    def particles(self) -> Particles:
        return self._particles

    @abstractmethod
    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        """The particles at ctx's moment, among the ground's LEDs (at least one)."""

    def _placed(self, leds: LedSet) -> Ground:
        """The ground of these LEDs, worked out again only for another set."""
        ground = self._ground
        if ground is None or ground.leds is not leds:
            ground = self._ground = Ground.of(leds)
        return ground


def drawn(effect: ParticleEffect, ctx: RenderContext, leds: LedSet) -> FloatRGB:
    """A particle effect's frame on these LEDs at ctx's moment: placed, stepped, sampled."""
    effect.place(leds)
    effect.step(ctx)
    return effect.sample(ctx, leds)
```

- [ ] **Step 4: Run them to see them pass, and every effect's tests with them**

Run: `uv run pytest tests/effects/test_particles.py -q 2>&1 | tail -1 && uv run pytest tests/effects tests/looks -q 2>&1 | tail -1`
Expected: PASS (7 tests), then `430 passed, 2 deselected`: every effect's and look's tests pass unchanged on the moved settings.

- [ ] **Step 5: Run the gate**

```bash
uv run ruff format src/dj_ledfx/effects/base.py src/dj_ledfx/effects/field.py src/dj_ledfx/effects/particles.py tests/effects/test_particles.py
uv run ruff check --fix src/dj_ledfx/effects/base.py src/dj_ledfx/effects/field.py src/dj_ledfx/effects/particles.py tests/effects/test_particles.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: `All checks passed!`, `343 files already formatted`, mypy's 16 errors (`checked 155 source files`) and `2062 passed, 1 skipped, 43 deselected`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/base.py src/dj_ledfx/effects/field.py src/dj_ledfx/effects/particles.py tests/effects/test_particles.py
git commit -m "feat(effects): the particle effect kind, sharing ParamField's settings through ParamSettings"
```

---


### Task 3: Particle layers in looks and the zone runtime

The look model stops refusing particle layers and refuses a layer of the wrong kind with the reason (ruling 8). The runtime draws particle layers bottom to top with the field layers, each through its layer's view (ruling 7): placed among the LEDs the view shows, stepped to the frame's moment and sampled, then blended, masked and checked for NaN as a field layer is. `streamed_layers()` gives the runtime its layers; `visible_field_layers()` keeps its meaning for the classic effect endpoints, which a particle look never answers. A test particle effect, `DotParticles`, joins the runtime fakes.

**Files:**
- Create: `tests/zones/test_runtime_particles.py`
- Modify: `src/dj_ledfx/looks/model.py`, `src/dj_ledfx/zones/runtime.py`, `tests/runtime_fakes.py`, `tests/looks/test_model.py`

**Interfaces:**
- Consumes: Task 2's `ParticleEffect`, `ParamParticles` and `drawn`; Task 1's `Ground`, `Particles` and `swarm` (in the fakes).
- Produces:
  - `looks.model.make_effect(layer: Layer) -> FieldEffect | ParticleEffect | FirmwareEffect`: a particle layer's kind must be a particle effect ("Layer '…': '…' isn't a particle effect"); a field layer's must be a field or strip effect, and a firmware layer's a firmware effect, as before.
  - `looks.model.streamed_layers(look: Look) -> list[Layer]`: the visible field and particle layers, bottom to top.
  - `ZoneRuntime._streamed: list[tuple[Layer, FieldEffect | ParticleEffect]]`, bottom to top, where `_fields` was; `ZoneRuntime.field_effect` is the bottom streamed layer's effect only when that is a field effect.
  - In `tests/runtime_fakes.py`: `DotParticles(ParamParticles, register=False)`, one dot of `level` grey at `x` metres east on the map's axes (y 0, 1 m up), 0.3 m across, NaN while `FlatField.mode` is `"nan"`, registered as `dot_particles` by `register_fields()`; `dot_layer(x: float = 0.0, level: float = 1.0, **changes) -> Layer` (id `dots`, name `Dots`).

- [ ] **Step 1: Write the failing tests**

In `tests/runtime_fakes.py`, a particle effect a test can read at a glance:

```diff
--- a/tests/runtime_fakes.py
+++ b/tests/runtime_fakes.py
@@ -1,6 +1,6 @@
-"""Fakes for zone runtime tests: three lights, field effects that are easy to read, and
-looks and runtimes made of them. A test file registers the fields with an autouse fixture
-that calls register_fields() (conftest drops them after each test)."""
+"""Fakes for zone runtime tests: three lights, field and particle effects that are easy to
+read, and looks and runtimes made of them. A test file registers the effects with an
+autouse fixture that calls register_fields() (conftest drops them after each test)."""

 from __future__ import annotations

@@ -17,6 +17,8 @@ from dj_ledfx.effects.context import RenderContext
 from dj_ledfx.effects.field import FieldEffect
 from dj_ledfx.effects.ledset import NO_ROOM, LedSet, PlacedLeds
 from dj_ledfx.effects.params import EffectParam
+from dj_ledfx.effects.particle_tools import Ground, Particles, swarm
+from dj_ledfx.effects.particles import ParamParticles
 from dj_ledfx.looks.model import Layer, Look, Transition
 from dj_ledfx.tempo.clock import TempoClock
 from dj_ledfx.types import FloatRGB
@@ -76,9 +78,27 @@ class PlaceField(FieldEffect, register=False):
         return np.array(leds.pos, dtype=np.float32)


+class DotParticles(ParamParticles, register=False):
+    """One dot of `level` grey at `x` metres east on the map's axes (y 0, 1 m up), 0.3 m
+    across, as the layer sees it: a layer's transform moves it with the field. Its colour
+    is NaN while FlatField.mode is "nan"."""
+
+    @classmethod
+    def parameters(cls) -> dict[str, EffectParam]:
+        return {
+            "x": EffectParam(type="float", default=0.0, min=-10.0, max=10.0),
+            "level": EffectParam(type="float", default=1.0, min=0.0, max=1.0),
+        }
+
+    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
+        level = np.nan if FlatField.mode == "nan" else float(self._values["level"])
+        return swarm([[float(self._values["x"]), 0.0, 1.0]], [level, level, level], 0.3)
+
+
 def register_fields() -> None:
     Effect._registry["flat_field"] = FlatField
     Effect._registry["place_field"] = PlaceField
+    Effect._registry["dot_particles"] = DotParticles
     FlatField.mode = "ok"
     PlaceField.seen = []

@@ -96,6 +116,18 @@ def field_layer(level: float = 0.5, opacity: float = 1.0, **changes: Any) -> Lay
     )


+def dot_layer(x: float = 0.0, level: float = 1.0, **changes: Any) -> Layer:
+    """A particle layer of one dot; changes set any other field of the Layer."""
+    return Layer(
+        id=changes.pop("id", "dots"),
+        name=changes.pop("name", "Dots"),
+        type="particles",
+        kind="dot_particles",
+        settings={"x": x, "level": level},
+        **changes,
+    )
+
+
 def place_layer(**changes: Any) -> Layer:
     return Layer(id="place", name="Place", type="field", kind="place_field", **changes)

```

In `tests/looks/test_model.py`, the M5 refusal goes, and layers of the wrong kind are refused with the reason:

```diff
--- a/tests/looks/test_model.py
+++ b/tests/looks/test_model.py
@@ -4,6 +4,7 @@ from typing import Any, ClassVar

 import numpy as np
 import pytest
+from runtime_fakes import register_fields

 from dj_ledfx.effects.base import Effect
 from dj_ledfx.effects.context import RenderContext
@@ -11,6 +12,7 @@ from dj_ledfx.effects.field import FieldEffect
 from dj_ledfx.effects.firmware_lifx import LifxFlame
 from dj_ledfx.effects.ledset import LedSet
 from dj_ledfx.effects.params import EffectParam
+from dj_ledfx.effects.particles import ParticleEffect
 from dj_ledfx.effects.strip_adapter import StripAdapter
 from dj_ledfx.looks.model import (
     LIGHTS_SETTING,
@@ -31,6 +33,7 @@ from dj_ledfx.looks.model import (
     look_to_dict,
     make_effect,
     setting_schema,
+    streamed_layers,
     validate_look,
     visible_field_layer,
     visible_field_layers,
@@ -143,7 +146,6 @@ def test_setting_schema_types() -> None:
         ({"category": "party"}, "category"),
         ({"scope": "whole-home"}, "M6"),
         ({"needs": ["weather"]}, "input"),
-        ({"layers": [_layer(type="particles", kind="fireflies")]}, "M5"),
         ({"layers": [_layer(settings={"beats_per_cycle": {"value": 2.0, "binding": {}}})]}, "M7"),
         ({"layers": [_layer(settings={"beats_per_cycle": 2.0})]}, "value"),
         ({"transition": {"kind": "melt", "durationS": 1.0}}, "transition"),
@@ -187,6 +189,42 @@ def test_layer_problems_are_refused(layers: list[dict[str, Any]], reason: str) -
         validate_look(look_from_dict(_look(layers=layers)))


+def test_a_layer_of_another_kind_of_effect_is_refused_with_the_reason() -> None:
+    register_fields()  # flat_field and dot_particles
+    for layer_type, kind, reason in [
+        ("particles", "flat_field", "isn't a particle effect"),
+        ("particles", "lifx_flame", "isn't a particle effect"),
+        ("field", "dot_particles", "isn't a field effect"),
+        ("firmware", "dot_particles", "isn't a firmware effect"),
+    ]:
+        look = look_from_dict(_look(layers=[_layer(type=layer_type, kind=kind, settings={})]))
+        with pytest.raises(LookError, match=reason):
+            validate_look(look)
+
+
+def test_particle_layers_take_modifiers_and_round_trip_but_pick_no_lights() -> None:
+    register_fields()
+    layer = _layer(
+        type="particles",
+        kind="dot_particles",
+        settings={"x": {"value": 1.5}},
+        mask={"kind": "height", "range": [0.5, 1.5]},
+        mirror={"axis": "y", "at": 2.5},
+        transform={"offset": [1.0, 0.0, 0.0], "rotateDeg": 0.0, "scale": 1.0},
+    )
+    look = look_from_dict(_look(layers=[_layer(id="under"), {**layer, "id": "dots"}]))
+
+    validate_look(look)
+    assert [layer.id for layer in streamed_layers(look)] == ["under", "dots"]
+    assert [layer.id for layer in visible_field_layers(look)] == ["under"]
+    effect = make_effect(look.layers[1])
+    assert isinstance(effect, ParticleEffect) and effect.get_params()["x"] == 1.5
+    assert look_from_dict(look_to_dict(look, for_storage=True)) == look
+    picking = _layer(type="particles", kind="dot_particles", settings={"lights": {"value": ["a"]}})
+    with pytest.raises(LookError, match="give a streamed layer a mask"):
+        validate_look(look_from_dict(_look(layers=[picking])))
+
+
 def test_hidden_field_layers_and_firmware_layers_are_fine() -> None:
     look = look_from_dict(
         _look(
```

Create `tests/zones/test_runtime_particles.py`:

```python
from __future__ import annotations

import numpy as np
import pytest
from runtime_fakes import (
    FlatField,
    dot_layer,
    field_layer,
    glow_layer,
    latest,
    look_of,
    placed_light,
    runtime_of,
)

from dj_ledfx.looks.model import Mirror, Transform
from dj_ledfx.zones.runtime import ZoneRuntime

pytestmark = pytest.mark.usefixtures("_fields")

# One light of 9 LEDs, 0.5 m apart along x from 0 to 4 m, 1 m up.
ROW_LIGHT = placed_light("row", *[(0.5 * i, 0.0, 1.0) for i in range(9)])


def _lit(runtime: ZoneRuntime) -> list[int]:
    """The LEDs the newest frame lights at least half."""
    return [int(i) for i in np.flatnonzero(latest(runtime)[:, 0] >= 0.5)]


def test_a_particle_layer_lights_the_leds_near_its_particles() -> None:
    runtime = runtime_of(look_of(dot_layer(x=2.0)), [ROW_LIGHT])
    runtime.tick(100.0)
    frame = latest(runtime)
    np.testing.assert_allclose(frame[4], 1.0)  # the LED at 2 m
    assert _lit(runtime) == [4]
    assert not frame[[0, 8]].any()  # 2 m off: past its reach


def test_particle_and_field_layers_blend_bottom_to_top() -> None:
    look = look_of(field_layer(level=0.2), dot_layer(x=2.0, level=0.5, blend="add"))
    runtime = runtime_of(look, [ROW_LIGHT])
    runtime.tick(100.0)
    frame = latest(runtime)
    np.testing.assert_allclose(frame[4], 0.7)
    np.testing.assert_allclose(frame[0], 0.2)


def test_a_layers_transform_and_mirror_move_its_particles_as_they_move_a_field() -> None:
    shifted = runtime_of(
        look_of(dot_layer(x=2.0, transform=Transform(offset=(1.0, 0.0, 0.0)))), [ROW_LIGHT]
    )
    mirrored = runtime_of(look_of(dot_layer(x=1.0, mirror=Mirror(axis="x"))), [ROW_LIGHT])
    shifted.tick(100.0)
    mirrored.tick(100.0)
    assert _lit(shifted) == [6]  # 1 m further east
    assert _lit(mirrored) == [2, 6]  # at 1 m, and across the middle at 3 m


def test_update_look_tunes_a_particle_layer_in_place() -> None:
    runtime = runtime_of(look_of(dot_layer(x=1.0), glow_layer()), [ROW_LIGHT])
    generation = runtime.generation
    runtime.update_look(look_of(dot_layer(x=3.0), glow_layer()))
    runtime.tick(100.0)
    assert runtime.generation == generation
    assert _lit(runtime) == [6]


def test_a_particle_layer_that_gives_nan_crashes_its_zone() -> None:
    runtime = runtime_of(look_of(dot_layer()), [ROW_LIGHT])
    FlatField.mode = "nan"
    runtime.tick(100.0)
    assert runtime.crash is not None and runtime.crash.layer == "Dots"
    assert "NaN" in runtime.crash.message
    assert runtime.ring.count == 0


def test_a_light_a_firmware_layer_cannot_run_shows_the_particle_layer() -> None:
    runtime = runtime_of(look_of(dot_layer(x=2.0), glow_layer()), [ROW_LIGHT])
    assert runtime.mode_of("row") == "streaming"  # a lamp can't run Glow: the dots play
    assert runtime.field_effect is None  # no classic effect to tune
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/looks/test_model.py tests/zones/test_runtime_particles.py -q 2>&1 | tail -3`
Expected: FAIL: a collection error, `ImportError: cannot import name 'streamed_layers' from 'dj_ledfx.looks.model'`, which stops the run.

- [ ] **Step 3: Take particle layers in the model and draw them in the runtime**

In `src/dj_ledfx/looks/model.py`:

```diff
--- a/src/dj_ledfx/looks/model.py
+++ b/src/dj_ledfx/looks/model.py
@@ -1,7 +1,8 @@
 """The look model, shaped like the web app contract (web spec §12.2; engine spec §5.2).

-M2 blends any number of visible field layers under the firmware layers. Everything else
-the contract can describe is refused with the milestone that brings it.
+The runtime blends any number of visible streamed layers, field and particle layers alike,
+under the firmware layers. Everything else the contract can describe is refused with the
+milestone that brings it.
 """

 from __future__ import annotations
@@ -15,6 +16,7 @@ from dj_ledfx.effects.base import StripEffect
 from dj_ledfx.effects.field import FieldEffect
 from dj_ledfx.effects.firmware import FirmwareEffect
 from dj_ledfx.effects.params import EffectParam, check_setting
+from dj_ledfx.effects.particles import ParticleEffect
 from dj_ledfx.effects.registry import get_effect_class
 from dj_ledfx.effects.strip_adapter import PROJECTION_PARAMS, StripAdapter
 from dj_ledfx.looks.selectors import Selector, parse_selector
@@ -285,8 +287,6 @@ def _inputs(values: Any, what: str) -> tuple[Any, ...]:
 def _layer_from_dict(layer: Any, index: int) -> Layer:
     data = _READ.mapping(layer, f"Layer {index + 1}")
     layer_type = _choice(data.get("type"), get_args(LayerType), "layer type")
-    if layer_type == "particles":
-        raise LookError("Particle layers arrive in M5")
     raw_settings = _READ.mapping(data.get("settings") or {}, "Layer settings")
     settings: dict[str, Any] = {}
     for key, setting in raw_settings.items():
@@ -488,7 +488,7 @@ def look_to_dict(
     return data


-def make_effect(layer: Layer) -> FieldEffect | FirmwareEffect:
+def make_effect(layer: Layer) -> FieldEffect | ParticleEffect | FirmwareEffect:
     """A fresh effect for the layer with its settings applied. Strip effects come wrapped,
     so the adapter takes its projection settings and passes the rest on."""
     try:
@@ -496,11 +496,15 @@ def make_effect(layer: Layer) -> FieldEffect | FirmwareEffect:
     except KeyError:
         raise LookError(f"Layer '{layer.name}' uses an unknown effect '{layer.kind}'") from None
     raw = cls()
-    effect: FieldEffect | FirmwareEffect
+    effect: FieldEffect | ParticleEffect | FirmwareEffect
     if layer.type == "firmware":
         if not isinstance(raw, FirmwareEffect):
             raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a firmware effect")
         effect = raw
+    elif layer.type == "particles":
+        if not isinstance(raw, ParticleEffect):
+            raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a particle effect")
+        effect = raw
     elif isinstance(raw, StripEffect):
         effect = StripAdapter(raw)
     elif isinstance(raw, FieldEffect):
@@ -514,8 +518,13 @@ def make_effect(layer: Layer) -> FieldEffect | FirmwareEffect:
     return effect


+def streamed_layers(look: Look) -> list[Layer]:
+    """The layers the runtime blends, field and particle layers alike, bottom to top."""
+    return [layer for layer in look.layers if layer.type != "firmware" and layer.visible]
+
+
 def visible_field_layers(look: Look) -> list[Layer]:
-    """The streamed layers the runtime blends, bottom to top."""
+    """The visible field layers, bottom to top."""
     return [layer for layer in look.layers if layer.type == "field" and layer.visible]


```

In `src/dj_ledfx/zones/runtime.py`:

```diff
--- a/src/dj_ledfx/zones/runtime.py
+++ b/src/dj_ledfx/zones/runtime.py
@@ -26,6 +26,7 @@ from dj_ledfx.effects.ledset import (
     Space,
     build_ledset,
 )
+from dj_ledfx.effects.particles import ParticleEffect, drawn
 from dj_ledfx.effects.ring_buffer import RingBuffer
 from dj_ledfx.looks.model import (
     Layer,
@@ -35,7 +36,7 @@ from dj_ledfx.looks.model import (
     TransitionKind,
     firmware_layers,
     make_effect,
-    visible_field_layers,
+    streamed_layers,
 )
 from dj_ledfx.looks.selectors import selects
 from dj_ledfx.scheduling.route import DeviceRoute
@@ -96,7 +97,7 @@ def _finite(colors: FloatRGB) -> FloatRGB:


 def _opacity(layer: Layer, view: LayerView) -> float | NDArray[np.float32]:
-    """How much of a field layer shows: its opacity, by each LED's weight in its mask."""
+    """How much of a streamed layer shows: its opacity, by each LED's weight in its mask."""
     if view.weight is None:
         return layer.opacity
     return view.weight if layer.opacity == 1.0 else view.weight * np.float32(layer.opacity)
@@ -231,7 +232,7 @@ class ZoneRuntime:
         self._trails = Trails()
         self._transition: _Transition | None = None
         self._handover: set[str] = set()  # see handing_over
-        self._fields: list[tuple[Layer, FieldEffect]] = []  # bottom to top
+        self._streamed: list[tuple[Layer, FieldEffect | ParticleEffect]] = []  # bottom to top
         self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
         self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
         self._copies: dict[str, int] = {}  # light -> firmware layer streamed as a copy
@@ -242,7 +243,7 @@ class ZoneRuntime:
         self._copy_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
         self._claim_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
         self._lights: tuple[ZoneLight, ...] = ()
-        # Each field layer's view of the LEDs (its mask, mirror and transform), with the
+        # Each streamed layer's view of the LEDs (its mask, mirror and transform), with the
         # modifiers it was made for; a new LED set clears them (_place).
         self._views: dict[int, tuple[object, LayerView]] = {}  # by the layer's place
         self._rendering = ""
@@ -271,8 +272,10 @@ class ZoneRuntime:

     @property
     def field_effect(self) -> FieldEffect | None:
-        """The bottom field layer's effect: a classic look's only one."""
-        return self._fields[0][1] if self._fields else None
+        """The bottom streamed layer's effect when it's a field effect: a classic look's
+        only one."""
+        effect = self._streamed[0][1] if self._streamed else None
+        return None if isinstance(effect, ParticleEffect) else effect

     @property
     def waiting_for(self) -> tuple[str, ...]:
@@ -461,11 +464,11 @@ class ZoneRuntime:
         if self.crash is not None or _layout(old) != _layout(look) or old.needs != look.needs:
             self._compile()
             return
-        for index, layer in enumerate(visible_field_layers(look)):
-            old_layer, field_effect = self._fields[index]
+        for index, layer in enumerate(streamed_layers(look)):
+            old_layer, effect = self._streamed[index]
             if old_layer.settings != layer.settings:
-                field_effect.set_params(**layer.settings)
-            self._fields[index] = (layer, field_effect)
+                effect.set_params(**layer.settings)
+            self._streamed[index] = (layer, effect)
         resend = False
         for index, layer in enumerate(reversed(firmware_layers(look))):
             old_layer, firmware = self._firmware[index]
@@ -722,14 +725,18 @@ class ZoneRuntime:
         return frame

     def _render_layers(self, ctx: RenderContext) -> FloatRGB:
-        """The field layers blended bottom to top, then each firmware layer's copy drawn on
-        the lights that stream it."""
+        """The streamed layers blended bottom to top, then each firmware layer's copy drawn
+        on the lights that stream it. A particle layer's particles move to the frame's
+        moment among the LEDs its view shows, then light them."""
         count = self.leds.count
         frame: FloatRGB | None = None
-        for index, (layer, field_effect) in enumerate(self._fields):
+        for index, (layer, effect) in enumerate(self._streamed):
             self._rendering = layer.name
             view = self._view(index, layer)
-            colors = _finite(field_effect.render(ctx, view.leds))
+            if isinstance(effect, ParticleEffect):
+                colors = _finite(drawn(effect, ctx, view.leds))
+            else:
+                colors = _finite(effect.render(ctx, view.leds))
             opacity = _opacity(layer, view)
             if frame is None and layer.blend == "normal":  # over black: its colours, weighed
                 frame = np.multiply(colors, opacity, dtype=np.float32)
@@ -755,9 +762,9 @@ class ZoneRuntime:
             frame[where] = _finite(firmware.emulate(ctx, leds)) * np.float32(layer.opacity)

     def _view(self, index: int, layer: Layer) -> LayerView:
-        """The view of the zone's LEDs for the field layer at `index`, made again only when
-        its modifiers or the LED set change, so the effect's per-LED work is kept between
-        frames. Kept by place, not id: a saved look may give two layers one id."""
+        """The view of the zone's LEDs for the streamed layer at `index`, made again only
+        when its modifiers or the LED set change, so the effect's per-LED work is kept
+        between frames. Kept by place, not id: a saved look may give two layers one id."""
         modifiers = layer.modifiers
         kept = self._views.get(index)
         if kept is not None and kept[0] == modifiers:
@@ -770,21 +777,21 @@ class ZoneRuntime:
         self.generation = next(_GENERATIONS)
         self.crash = None
         self._trails.reset()
-        self._fields = []
+        self._streamed = []
         self._firmware = []
-        layers = visible_field_layers(self.look) + list(reversed(firmware_layers(self.look)))
+        layers = streamed_layers(self.look) + list(reversed(firmware_layers(self.look)))
         for position, layer in enumerate(layers):
             try:
                 effect = make_effect(layer)
             except LookError as exc:
-                self._fields, self._firmware = [], []
+                self._streamed, self._firmware = [], []
                 self._fail(layer.name, str(exc))
                 break
             effect.reseed(self._seed + position)
             if isinstance(effect, FirmwareEffect):
                 self._firmware.append((layer, effect))
             else:
-                self._fields.append((layer, effect))
+                self._streamed.append((layer, effect))
         self._plan_claims()

     def _place(self, lights: Sequence[ZoneLight], leds: LedSet | None = None) -> None:
@@ -830,7 +837,7 @@ class ZoneRuntime:
             picked = [i for i in range(len(self._firmware)) if self._picks(i, light)]
             index = next((i for i in picked if self._firmware[i][1].supports(light.caps)), None)
             if index is None:
-                if not self._fields and picked:
+                if not self._streamed and picked:
                     self._copies[light.device_id] = picked[0]
             elif light.device_id in self._emulated:
                 self._copies[light.device_id] = index
```

- [ ] **Step 4: Run them to see them pass, and the looks' and zones' tests with them**

Run: `uv run pytest tests/looks/test_model.py tests/zones/test_runtime_particles.py -q 2>&1 | tail -1 && uv run pytest tests/looks tests/zones tests/web -q 2>&1 | tail -1`
Expected: PASS (88 tests), then `612 passed, 41 deselected` for the looks', zones' and web tests. The warnings are FastAPI's `on_event` deprecation, as on master.

- [ ] **Step 5: Run the gate, and check the API didn't change**

```bash
uv run ruff format src/dj_ledfx/looks/model.py src/dj_ledfx/zones/runtime.py tests/runtime_fakes.py tests/looks/test_model.py tests/zones/test_runtime_particles.py
uv run ruff check --fix src/dj_ledfx/looks/model.py src/dj_ledfx/zones/runtime.py tests/runtime_fakes.py tests/looks/test_model.py tests/zones/test_runtime_particles.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
(cd web && npm run api:check 2>&1 | tail -1)
```

Expected: `All checks passed!`, `344 files already formatted`, mypy's 16 errors, `2069 passed, 1 skipped, 43 deselected` and `api types match`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/looks/model.py src/dj_ledfx/zones/runtime.py tests/runtime_fakes.py tests/looks/test_model.py tests/zones/test_runtime_particles.py
git commit -m "feat(zones): particle layers in looks and the zone runtime, through each layer's view"
```

---


### Task 4: The particles of `fireflies` and `snow`, and the sweep

The particles of `fireflies` and `snow`, the two ambient looks that wander and fall (ruling 10), and the sweep every particle effect joins (spec §9: "every look stays finite and in range, outputs the right shape, and repeats exactly with a fixed seed"). The sweep takes every registered particle effect, so Tasks 5, 6 and 7 add nothing to it: their effects join it as they register. It runs each effect on this home's seeded LEDs and on the smallest zones a home can have (Review Focus 1), at tempos from 30 to 300 BPM (Review Focus 2), with its frames falling unevenly (Review Focus 3) and at its largest settings (Review Focus 4).

**Files:**
- Create: `src/dj_ledfx/effects/fireflies.py`, `src/dj_ledfx/effects/snowfall.py`, `tests/effects/test_fireflies.py`, `tests/effects/test_snowfall.py`, `tests/effects/test_particle_effects.py`
- Modify: `src/dj_ledfx/effects/__init__.py`, `tests/map_home.py` (`upright()`)

**Interfaces:**
- Consumes: Task 1's `draws`, `swarm`, `wander`, `WANDER_DRAWS`, `spread_over`, `Ground.on`, `Ground.box` and `Lamps.pick`; Task 2's `ParamParticles`, `MAX_PARTICLES` and `drawn`; `palette_at` (`effects/color.py`); `EffectParam` and `anchor_param` (`effects/params.py`); `seeded_ledset()`, `leds_at()` and `ROW` (`tests/map_home.py`); `render_ctx()` and `tempo_ctx()` (`tests/conftest.py`); `FRAME_BUDGET_S` (`zones/runtime.py`).
- Produces:
  - `effects.fireflies.Fireflies`, kind `fireflies`: settings `palette`, `count` (1–60, 12), `speed` (0.05–2 m/s, 0.3, bindable), `glow_size` (0.1–2 m, 0.5) and `drift_toward` (an anchor, none by default); `FIREFLY_PALETTE`, `RANGE_M = 1.0`, `DRIFT_REACH_M = 1.5`, `GLOW_LOW = 0.35`, `FLARE_S = (2.0, 5.0)`.
  - `effects.snowfall.Snowfall`, kind `snowfall`: settings `palette`, `per_lamp` (1–20, 4, bindable), `fall_s` (3–40 s, 12), `drift` (0–1.5 m, 0.3) and `size` (0.05–0.6 m, 0.2); `SNOW_PALETTE`, `COLUMN_M = 0.3`, `SWAYS = 2.0`, `EDGE = 0.05`, `FALLS = 4096`.
  - In `tests/map_home.py`: `upright(x: float, y: float, low: float = 0.1, high: float = 1.4) -> list[list[float]]`, an upright lamp's 14 LEDs.
  - `tests/effects/test_particle_effects.py`: `PARTICLE_KINDS` (every registered particle effect's kind, sorted), and the sweep's tests, each parametrized over it.

- [ ] **Step 1: Write the failing tests**

In `tests/map_home.py`, an upright lamp, which most of the looks' tests stand in their rooms:

```diff
--- a/tests/map_home.py
+++ b/tests/map_home.py
@@ -179,6 +179,11 @@ def lights_at(*lights: Sequence[Sequence[float]], ceiling: float | None = 3.0) -
     return build_ledset(sources, Space(ceiling=ceiling))


+def upright(x: float, y: float, low: float = 0.1, high: float = 1.4) -> list[list[float]]:
+    """An upright lamp's 14 LEDs at (x, y), from `low` to `high` metres up."""
+    return [[x, y, z] for z in np.linspace(low, high, 14)]
+
+
 ROW = [[x, 0.0, 1.0] for x in np.linspace(0.0, 4.0, 9)]  # 0.5 m apart, west to east


```

Create `tests/effects/test_particle_effects.py`, the sweep:

```python
"""Every particle effect, swept (spec §9: every look stays finite and in range, outputs the
right shape, and repeats exactly with a fixed seed), on this home's LEDs and on the
smallest zones a home can have."""

from __future__ import annotations

import statistics
import time
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import leds_at, seeded_ledset

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import MAX_PARTICLES, ParticleEffect, drawn
from dj_ledfx.effects.registry import get_effect_class, get_effect_classes
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import FRAME_BUDGET_S

PARTICLE_KINDS = sorted(
    name for name, cls in get_effect_classes().items() if issubclass(cls, ParticleEffect)
)
START = 2000.0  # beats: 1000 s into a steady 120 BPM


def _effect(kind: str, seed: int = 1, **settings: Any) -> ParticleEffect:
    effect = get_effect_class(kind)(**settings)
    assert isinstance(effect, ParticleEffect)
    effect.reseed(seed)
    return effect


def _largest(kind: str) -> dict[str, Any]:
    """Every number the effect takes at its largest."""
    return {
        name: int(param.max) if param.type == "int" else param.max
        for name, param in get_effect_class(kind).parameters().items()
        if param.type in ("int", "float") and param.max is not None
    }


def _frames(effect: ParticleEffect, leds: LedSet, count: int = 120) -> list[FloatRGB]:
    """Two seconds at 60 frames a second, checking the particles as they go."""
    frames = []
    for step in range(count):
        frames.append(drawn(effect, tempo_ctx(START + step / 30), leds))
        particles = effect.particles
        assert particles.count <= MAX_PARTICLES
        assert np.isfinite(particles.pos).all() and np.isfinite(particles.radius).all()
    return frames


def _good(frames: list[FloatRGB], leds: LedSet) -> None:
    for frame in frames:
        assert frame.shape == (leds.count, 3) and frame.dtype == np.float32
        assert np.isfinite(frame).all()
        assert frame.min() >= 0.0 and frame.max() <= 1.0


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_every_particle_effect_is_finite_in_range_and_repeats_with_a_fixed_seed(
    kind: str,
) -> None:
    leds = seeded_ledset()
    frames = _frames(_effect(kind), leds)
    _good(frames, leds)
    assert any(frame.any() for frame in frames)  # it lights something
    again = _frames(_effect(kind), leds)
    for frame, repeat in zip(frames, again, strict=True):
        np.testing.assert_array_equal(frame, repeat)
    other = _frames(_effect(kind, seed=2), leds)
    assert any(not np.array_equal(a, b) for a, b in zip(frames, other, strict=True))


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_the_same_moment_gives_the_same_frame_however_the_frames_fall(kind: str) -> None:
    leds = seeded_ledset()
    stepped, jumped = _effect(kind), _effect(kind)
    for beats in (START, START + 0.4, START + 3.7):
        drawn(stepped, tempo_ctx(beats), leds)
    moment = tempo_ctx(START + 9.25)
    np.testing.assert_array_equal(drawn(stepped, moment, leds), drawn(jumped, moment, leds))


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_tempo_from_30_to_300_bpm_keeps_every_frame_in_range(kind: str) -> None:
    leds = seeded_ledset()
    effect, t, beats, frames = _effect(kind), 1000.0, START, []
    for bpm in (30.0, 300.0, 120.0):  # each for two seconds, the clock running on
        for _ in range(60):
            t, beats = t + 1 / 30, beats + bpm / 60.0 / 30
            frames.append(drawn(effect, replace(tempo_ctx(beats, bpm=bpm), t=t), leds))
            assert effect.particles.count <= MAX_PARTICLES
    _good(frames, leds)


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_zone_of_one_lamp_with_no_map_draws_in_range(kind: str) -> None:
    leds = leds_at([[1.0, 1.0, 0.1 + 0.1 * i] for i in range(14)], ceiling=None)
    _good(_frames(_effect(kind), leds, count=60), leds)


@pytest.mark.parametrize("ceiling", [None, 3.0], ids=["no map", "a 3 m ceiling"])
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_zone_of_one_bulb_draws_in_range_and_lights_it(kind: str, ceiling: float | None) -> None:
    leds = leds_at([[1.0, 1.0, 1.0]], ceiling=ceiling)  # one LED: its lamp's top and foot
    frames = _frames(_effect(kind), leds, count=600)
    _good(frames, leds)
    assert max(float(frame.max()) for frame in frames) > 0.1  # it lights at some moment


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_zone_with_no_leds_draws_nothing(kind: str) -> None:
    effect = _effect(kind)
    frame = drawn(effect, tempo_ctx(START), leds_at([]))
    assert frame.shape == (0, 3) and effect.particles.count == 0


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_the_largest_settings_keep_to_the_particle_cap(kind: str) -> None:
    leds = seeded_ledset()
    _good(_frames(_effect(kind, **_largest(kind)), leds, count=30), leds)


# Spec §9's benchmark: every particle effect at its largest settings, on this home's LEDs.
@pytest.mark.perf
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_every_particle_effect_at_its_largest_settings_draws_in_the_budget(kind: str) -> None:
    leds = seeded_ledset()
    effect = _effect(kind, **_largest(kind))
    durations = []
    for step in range(240):
        started = time.perf_counter()
        drawn(effect, tempo_ctx(START + step / 30), leds)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < FRAME_BUDGET_S
```

Create `tests/effects/test_fireflies.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.fireflies import DRIFT_REACH_M, GLOW_LOW, RANGE_M, Fireflies
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import REACH
from dj_ledfx.effects.particles import drawn

# Three upright lamps round a room under a 3 m ceiling, and a 12 m row of LEDs 0.25 m
# apart, 1 m up, with a sofa near its west end.
THREE = lights_at(upright(0.5, 0.5), upright(4.5, 0.5), upright(2.5, 4.0))
ROW_12 = [[x, 0.0, 1.0] for x in np.linspace(0.0, 12.0, 49)]
SOFA = (2.0, 0.5, 0.5)


def _flies(**settings: object) -> Fireflies:
    flies = Fireflies(**settings)
    flies.reseed(1)
    return flies


def _moments(seconds: float = 30.0) -> list[float]:
    return [500.0 + t for t in np.arange(0.0, seconds, 0.1)]


def _paths(flies: Fireflies, leds: LedSet, seconds: float = 30.0) -> np.ndarray:
    """Each firefly's places over some seconds: shape (moments, fireflies, 3)."""
    seen = []
    for t in _moments(seconds):
        drawn(flies, render_ctx(t=t), leds)
        seen.append(flies.particles.pos)
    return np.stack(seen)


def test_each_firefly_wanders_round_a_lamp_of_its_own_every_lamp_taken_alike() -> None:
    paths = _paths(_flies(count=6, speed=1.0), THREE)
    lamps = np.array([[0.5, 0.5], [4.5, 0.5], [2.5, 4.0]])
    away = np.abs(paths[:, :, None, :2] - lamps[None, None, :, :]).max(axis=3)  # (m, f, lamp)
    home = (away <= RANGE_M + 1e-5).all(axis=0)  # the lamps each keeps within RANGE_M of
    assert home.any(axis=1).all()
    assert np.bincount(home.argmax(axis=1), minlength=3).tolist() == [2, 2, 2]
    assert paths[..., 2].min() >= 0.0 and paths[..., 2].max() <= 3.0  # floor to ceiling


def test_fireflies_spread_along_a_long_light() -> None:
    paths = _paths(_flies(count=10, speed=1.0), leds_at(ROW_12), seconds=5.0)
    assert np.ptp(paths[0, :, 0]) > 6.0  # round LEDs all along it, not round its middle


def test_fireflies_that_drift_toward_an_anchor_keep_near_it() -> None:
    leds = leds_at(ROW_12, anchors={"sofa": SOFA})
    flies = _flies(count=20, speed=1.0, drift_toward="sofa")
    for t in _moments():
        drawn(flies, render_ctx(t=t), leds)
        away = np.abs(flies.particles.pos - np.array(SOFA, dtype=np.float32))
        assert (away[:, :2] <= DRIFT_REACH_M + 1e-5).all()
        assert (flies.particles.pos[:, 2] >= 0.0).all()  # never under the floor


def test_each_firefly_glows_softly_and_flares_now_and_then() -> None:
    leds = leds_at(ROW)
    flies = _flies(count=5, palette=["#ffffff"])
    glow = []
    for t in _moments(10.0):
        drawn(flies, render_ctx(t=t), leds)
        glow.append(flies.particles.colour[:, 0])
    levels = np.array(glow)  # (moments, fireflies)
    assert levels.min() >= GLOW_LOW - 1e-6
    assert (levels.max(axis=0) > 0.95).all()  # each flares at least once in 10 s


def test_a_lamp_glows_only_while_a_firefly_drifts_through_it() -> None:
    leds = leds_at(ROW_12)
    flies = _flies(count=2, glow_size=0.3)
    for t in _moments(5.0):
        frame = drawn(flies, render_ctx(t=t), leds)
        gaps = np.linalg.norm(leds.pos[:, None, :] - flies.particles.pos[None, :, :], axis=2)
        far = gaps.min(axis=1) > REACH * 0.3
        assert not frame[far].any()  # black between them
        assert far.sum() >= len(far) - 14  # two fireflies light a few LEDs at most
```

Create `tests/effects/test_snowfall.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at

from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.snowfall import COLUMN_M, EDGE, Snowfall

# Four bulbs round a 6 x 4 m room, under a 3 m ceiling.
CORNERS = lights_at([(0.0, 0.0, 0.5)], [(6.0, 0.0, 1.0)], [(6.0, 4.0, 1.5)], [(0.0, 4.0, 2.0)])


def _snow(**settings: object) -> Snowfall:
    snow = Snowfall(**settings)
    snow.reseed(1)
    return snow


def test_snow_falls_from_the_ceiling_to_the_floor() -> None:
    snow = _snow(fall_s=12.0)
    drawn(snow, render_ctx(t=500.0), CORNERS)
    before = snow.particles.pos[:, 2].copy()
    drawn(snow, render_ctx(t=500.5), CORNERS)
    after = snow.particles.pos[:, 2]

    fell = before - after  # half a second, at 3 m in 10 to 14 s: 0.1 to 0.15 m
    started_again = fell < 0.0  # back at the ceiling
    assert (fell[~started_again] > 0.09).all() and (fell[~started_again] < 0.16).all()
    assert started_again.sum() <= 2
    assert (after >= 0.0).all() and (after <= 3.0).all()


def test_each_lamp_has_per_lamp_flakes_falling_past_it_up_to_the_cap() -> None:
    snow = _snow(per_lamp=3.0)
    drawn(snow, render_ctx(t=500.0), CORNERS)
    assert snow.particles.count == 12
    drawn(snow, render_ctx(t=500.0), leds_at([[1.0, 1.0, 1.0]]))
    assert snow.particles.count == 3
    many = lights_at(*[[(float(x), 0.0, 1.0)] for x in range(40)])
    snow = _snow(per_lamp=20.0)
    drawn(snow, render_ctx(t=500.0), many)  # 800 flakes asked for
    assert snow.particles.count == MAX_PARTICLES


def test_each_flake_falls_past_an_led_and_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long
    snow = _snow(per_lamp=12.0, drift=0.0)
    drawn(snow, render_ctx(t=500.0), leds)
    pos = snow.particles.pos
    gaps = np.linalg.norm(pos[:, None, :2] - leds.pos[None, :, :2], axis=2).min(axis=1)
    assert (gaps <= COLUMN_M + 1e-5).all()
    assert np.ptp(pos[:, 0]) > 2.5  # past LEDs all along it, not past its middle


def test_a_flake_fades_in_at_the_ceiling_and_out_at_the_floor() -> None:
    snow = _snow(palette=["#ffffff"])
    for t in np.arange(500.0, 520.0, 0.25):
        drawn(snow, render_ctx(t=float(t)), CORNERS)
        share = (3.0 - snow.particles.pos[:, 2]) / 3.0  # how far down each flake is
        glow = snow.particles.colour[:, 0]
        assert (glow <= np.minimum(share, 1.0 - share) / EDGE + 1e-4).all()


def test_flakes_sway_as_they_fall() -> None:
    still, swaying = _snow(drift=0.0), _snow(drift=0.5)
    sideways = []
    for snow in (still, swaying):
        drawn(snow, render_ctx(t=500.0), CORNERS)
        first = snow.particles.pos[:, :2].copy()
        drawn(snow, render_ctx(t=501.0), CORNERS)
        sideways.append(np.linalg.norm(snow.particles.pos[:, :2] - first, axis=1))
    steady = sideways[0] < 1e-6
    assert steady.mean() > 0.9  # without drift a flake falls straight down
    assert np.median(sideways[1]) > 0.1
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects/test_fireflies.py tests/effects/test_snowfall.py tests/effects/test_particle_effects.py -q 2>&1 | tail -4`
Expected: FAIL: two collection errors, `ModuleNotFoundError: No module named 'dj_ledfx.effects.fireflies'` and the same for `snowfall`. The sweep collects, over no effects yet.

- [ ] **Step 3: Write the two effects, and register them**

Create `src/dj_ledfx/effects/fireflies.py`:

```python
"""Fireflies' particles (looks.json "fireflies").

Each firefly wanders on slow waves of its own (particle_tools.wander) round an LED of a lamp
of its own (any of its LEDs), within RANGE_M of it, every lamp taken before any gets two, or
round the anchor they drift toward, within DRIFT_REACH_M; between the floor and the ceiling
either way. It glows at GLOW_LOW of its brightest between flares and flares once in a period
of its own from FLARE_S, so a lamp is lit only while a firefly is near it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam, anchor_param
from dj_ledfx.effects.particle_tools import WANDER_DRAWS, draws, spread_over, swarm, wander
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import F64, Ground, Particles

FIREFLY_PALETTE = ("#b4ff3c", "#ffe650", "#78ff8c")
RANGE_M = 1.0  # a firefly wanders this far round its LED
DRIFT_REACH_M = 1.5  # drawn to an anchor, they wander within this of it
GLOW_LOW = 0.35  # a firefly's glow between flares, of its brightest
FLARE_S = (2.0, 5.0)  # each flares once a period from this range, its own


class Fireflies(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(FIREFLY_PALETTE), label="Palette"
            ),
            "count": EffectParam(type="int", default=12, min=1, max=60, step=1, label="Count"),
            "speed": EffectParam(
                type="float",
                default=0.3,
                min=0.05,
                max=2.0,
                step=0.05,
                label="Speed",
                description="Metres a second",
                bindable=True,
            ),
            "glow_size": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=2.0,
                step=0.05,
                label="Glow size",
                description="Metres",
            ),
            "drift_toward": anchor_param("Drift toward", "None: they wander round the lamps"),
        }

    def _boxes(self, ground: Ground, spots: F64) -> tuple[F64, F64]:
        """Where each wanders: round the anchor they drift toward, else round the LED its
        spot (0..1) picks of its lamp."""
        name = str(self._values["drift_toward"])
        anchor = ground.leds.anchors.get(name) if name else None
        if anchor is not None:
            return ground.box(DRIFT_REACH_M, around=anchor)
        lamps = spread_over(self._seed, len(spots), ground.lamps.count)
        return ground.box(RANGE_M, around=ground.on(lamps, spots))

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        count = int(values["count"])
        u = draws(self._seed, np.arange(count), WANDER_DRAWS + 4)
        shade, period, phase, spot = u[:, WANDER_DRAWS:].T
        low, high = self._boxes(ground, spot)
        where = wander(u[:, :WANDER_DRAWS], ctx.t, float(values["speed"]), low, high)
        period = FLARE_S[0] + (FLARE_S[1] - FLARE_S[0]) * period
        flare = (0.5 - 0.5 * np.cos(2.0 * math.pi * (ctx.t / period + phase))) ** 4
        glow = GLOW_LOW + (1.0 - GLOW_LOW) * flare
        colour = palette_at(self._palette, shade) * glow[:, None].astype(np.float32)
        return swarm(where, colour, float(values["glow_size"]))
```

Create `src/dj_ledfx/effects/snowfall.py`:

```python
"""Snow's particles (looks.json "snow").

Flakes fall past the lamps, per_lamp of them at once for each: each falls from the ceiling
to the floor over its own fall, swaying as it goes, within COLUMN_M of an LED of a lamp
(Ground.on), then starts again at the ceiling over another. Flake i's fall c is where
draws() of that fall says. A flake fades in at the ceiling and out at the floor, and lights
a lamp as it passes.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

SNOW_PALETTE = ("#ffffff", "#d2e6ff", "#a0c8ff")
COLUMN_M = 0.3  # a flake falls within this of its LED, seen from above
SWAYS = 2.0  # a flake sways from side to side this many times on its way down
EDGE = 0.05  # it fades in over this share of its fall, and out over the last
FALLS = 4096  # flake i's fall c draws from key c * FALLS + i


class Snowfall(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(SNOW_PALETTE), label="Palette"),
            "per_lamp": EffectParam(
                type="float",
                default=4.0,
                min=1.0,
                max=20.0,
                step=1.0,
                label="Snow",
                description="Flakes falling past each lamp at once",
                bindable=True,
            ),
            "fall_s": EffectParam(
                type="float",
                default=12.0,
                min=3.0,
                max=40.0,
                step=1.0,
                label="Fall",
                description="Seconds from the ceiling to the floor",
            ),
            "drift": EffectParam(
                type="float",
                default=0.3,
                min=0.0,
                max=1.5,
                step=0.05,
                label="Drift",
                description="Metres a flake sways to each side",
            ),
            "size": EffectParam(
                type="float",
                default=0.2,
                min=0.05,
                max=0.6,
                step=0.05,
                label="Flake size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        count = min(MAX_PARTICLES, max(1, round(float(values["per_lamp"]) * lamps.count)))
        flakes = np.arange(count)
        own = draws(self._seed, flakes, 3)  # each flake's pace, start and colour
        fall = float(values["fall_s"]) * (0.85 + 0.3 * own[:, 0])
        progress = ctx.t / fall + own[:, 1]
        falls = np.floor(progress).astype(np.int64)
        share = progress - falls  # 0 at the ceiling, 1 at the floor
        where = draws(self._seed, falls * FALLS + flakes, 5, stream=1)  # this fall's place
        past = ground.on(lamps.pick(where[:, 0]), where[:, 4])
        out, side = COLUMN_M * np.sqrt(where[:, 1]), 2.0 * math.pi * where[:, 2]
        turn = 2.0 * math.pi * (SWAYS * share + where[:, 3])
        drift = float(values["drift"])
        pos = np.stack(
            [
                past[:, 0] + out * np.cos(side) + drift * np.sin(turn),
                past[:, 1] + out * np.sin(side) + drift * np.cos(turn),
                ground.ceiling - share * (ground.ceiling - ground.floor),
            ],
            axis=1,
        )
        fade = np.minimum(1.0, np.minimum(share, 1.0 - share) / EDGE)
        colour = palette_at(self._palette, own[:, 2]) * fade[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
```

In `src/dj_ledfx/effects/__init__.py`:

```diff
--- a/src/dj_ledfx/effects/__init__.py
+++ b/src/dj_ledfx/effects/__init__.py
@@ -5,6 +5,7 @@ from dj_ledfx.effects import checker_cubes as _checker_cubes  # noqa: F401
 from dj_ledfx.effects import color_carousel as _color_carousel  # noqa: F401
 from dj_ledfx.effects import color_chase as _color_chase  # noqa: F401
 from dj_ledfx.effects import fire_storm as _fire_storm  # noqa: F401
+from dj_ledfx.effects import fireflies as _fireflies  # noqa: F401
 from dj_ledfx.effects import firmware_lifx as _firmware_lifx  # noqa: F401
 from dj_ledfx.effects import firmware_openrgb as _firmware_openrgb  # noqa: F401
 from dj_ledfx.effects import focus_field as _focus_field  # noqa: F401
@@ -14,6 +15,7 @@ from dj_ledfx.effects import rainbow_wave as _rainbow_wave  # noqa: F401
 from dj_ledfx.effects import ripples as _ripples  # noqa: F401
 from dj_ledfx.effects import scanner_plane as _scanner_plane  # noqa: F401
 from dj_ledfx.effects import shockwave_shell as _shockwave_shell  # noqa: F401
+from dj_ledfx.effects import snowfall as _snowfall  # noqa: F401
 from dj_ledfx.effects import speaker_waves as _speaker_waves  # noqa: F401
 from dj_ledfx.effects import strobe as _strobe  # noqa: F401
 from dj_ledfx.effects import sunset_gradient as _sunset_gradient  # noqa: F401
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/effects/test_fireflies.py tests/effects/test_snowfall.py tests/effects/test_particle_effects.py -q 2>&1 | tail -1 && uv run pytest tests/effects/test_particle_effects.py -m perf -q 2>&1 | tail -1`
Expected: PASS (`26 passed, 2 deselected`: the two effects' tests and the sweep over them), then `2 passed, 16 deselected`: each effect at its largest settings within the budget.

- [ ] **Step 5: Run the gate**

```bash
uv run ruff format src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/fireflies.py src/dj_ledfx/effects/snowfall.py tests/effects/test_fireflies.py tests/effects/test_snowfall.py tests/effects/test_particle_effects.py tests/map_home.py
uv run ruff check --fix src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/fireflies.py src/dj_ledfx/effects/snowfall.py tests/effects/test_fireflies.py tests/effects/test_snowfall.py tests/effects/test_particle_effects.py tests/map_home.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `All checks passed!`, `349 files already formatted`, mypy's 16 errors (`checked 157 source files`), `2095 passed, 1 skipped, 45 deselected` and `45 passed` in the perf run.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/fireflies.py src/dj_ledfx/effects/snowfall.py tests/effects/test_fireflies.py tests/effects/test_snowfall.py tests/effects/test_particle_effects.py tests/map_home.py
git commit -m "feat(effects): the fireflies and snowfall particle effects, and the sweep every particle effect joins"
```

---


### Task 5: The particles of `embers`, `rain` and `spotlights`

The particles of `embers`, `rain` and `spotlights` (ruling 10): embers rising from the lamps' bases (ruling 3's "lamp bases"), rain on the lamps under lightning strikes that light the nearest lamps most, and spotlights touring the lamps. Each effect joins Task 4's sweep by registering.

**Files:**
- Create: `src/dj_ledfx/effects/embers.py`, `src/dj_ledfx/effects/rain_storm.py`, `src/dj_ledfx/effects/spotlights.py`, `tests/effects/test_embers.py`, `tests/effects/test_rain_storm.py`, `tests/effects/test_spotlights.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

**Interfaces:**
- Consumes: Task 1's `draws`, `recent`, `swarm`, `joined`, `NO_PARTICLES`, `tour`, `Ground.on`, `Ground.foot`, `Ground.floor` and `Ground.ceiling`; Task 2's `ParamParticles`; `palette_at` and `palette_float` (`effects/color.py`), `ease_in_out` (`effects/easing.py`); Task 4's `upright()` and Task 1's `lights_at()` in the tests.
- Produces:
  - `effects.embers.Embers`, kind `embers`: settings `palette`, `per_lamp` (0.5–10, 3, bindable), `rise_s` (1–15 s, 4) and `size` (0.03–0.5 m, 0.12); `EMBER_PALETTE` (catching to dying), `CLIMB_OVER_M = 0.3`, `WOBBLE_M = 0.06`, `WOBBLE_S = 2.0`, `LIFE_SPREAD = 0.5`, `FLICKER_HZ = 7.0`, `CATCH_S = 0.15`, `LAMP_KEYS = 65536`.
  - `effects.rain_storm.RainStorm`, kind `rain_storm`: settings `palette`, `lightning` (a colour), `drops_per_lamp` (0.5–8, 2, bindable), `fall_s` (0.3–4 s, 1), `size` (0.03–0.4 m, 0.1), `strikes_per_min` (0–30, 4, bindable) and `strike_reach` (1–10 m, 3); `flash(age: NDArray[np.float64]) -> NDArray[np.float64]`, a strike's brightness by its age in seconds; `RAIN_PALETTE`, `LIGHTNING`, `OVER_M = 0.25`, `UNDER_M = 0.15`, `JITTER_M = 0.05`, `EDGE = 0.1`, `FLASH_S = 0.6`, `LAMP_KEYS = 65536`.
  - `effects.spotlights.Spotlights`, kind `spotlights`: settings `palette`, `count` (1–6, 2), `hold_s` (0.5–30 s, 4, bindable), `move_s` (0.5–30 s, 3, bindable) and `size` (0.2–3 m, 0.8); `SPOT_PALETTE`.

- [ ] **Step 1: Write the failing tests**

Create `tests/effects/test_embers.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.embers import CLIMB_OVER_M, WOBBLE_M, Embers
from dj_ledfx.effects.particle_tools import lamps_of
from dj_ledfx.effects.particles import drawn

# Two upright lamps from 0.1 to 1.4 m and a short one on a table from 0.8 to 1.2 m.
LAMPS = lights_at(upright(1.0, 1.0), upright(5.0, 1.0), upright(3.0, 4.0, 0.8, 1.2))


def _embers(**settings: object) -> Embers:
    embers = Embers(**settings)
    embers.reseed(1)
    return embers


def _moments(seconds: float = 10.0) -> list[float]:
    return [500.0 + t for t in np.arange(0.0, seconds, 0.1)]


def test_embers_rise_from_each_lamps_foot_to_just_over_its_top() -> None:
    lamps = lamps_of(LAMPS)
    embers = _embers(per_lamp=3.0)
    seen = []
    for t in _moments():
        drawn(embers, render_ctx(t=t), LAMPS)
        seen.append(embers.particles.pos)
    where = np.concatenate(seen)
    gaps = np.linalg.norm(where[:, None, :2] - lamps.centre[None, :, :2], axis=2)
    lamp = gaps.argmin(axis=1)
    assert (gaps.min(axis=1) <= WOBBLE_M + 1e-5).all()  # each on its lamp
    assert (where[:, 2] >= lamps.low[lamp] - 1e-5).all()  # from its foot
    assert (where[:, 2] <= lamps.high[lamp] + CLIMB_OVER_M + 1e-5).all()
    assert set(lamp.tolist()) == {0, 1, 2}
    for which in range(3):  # some just leaving each lamp's foot
        assert where[lamp == which, 2].min() < lamps.low[which] + 0.05


def test_an_ember_dims_and_reddens_as_it_climbs() -> None:
    lamps = lamps_of(LAMPS)
    embers = _embers(palette=["#ffffff", "#ff0000"])  # white as it catches, red dying
    for t in _moments(3.0):
        drawn(embers, render_ctx(t=t), LAMPS)
        pos, colour = embers.particles.pos, embers.particles.colour
        lamp = np.linalg.norm(pos[:, None, :2] - lamps.centre[None, :, :2], axis=2).argmin(axis=1)
        foot, top = lamps.low[lamp], lamps.high[lamp] + CLIMB_OVER_M
        share = ((pos[:, 2] - foot) / (top - foot)) ** (1 / 0.8)  # how far up its climb
        lit = colour[:, 0] > 1e-3
        np.testing.assert_allclose(colour[lit, 1] / colour[lit, 0], 1.0 - share[lit], atol=1e-3)
        assert (colour[:, 0] <= 1.0 - share + 1e-4).all()


def test_embers_smoulder_all_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long, 1 m up
    embers = _embers(per_lamp=10.0)
    xs = []
    for t in _moments(5.0):
        drawn(embers, render_ctx(t=t), leds)
        xs.extend(embers.particles.pos[:, 0].tolist())
    assert np.ptp(xs) > 3.0  # from LEDs all along it, not from its middle


def test_embers_stop_at_the_ceiling() -> None:
    low_ceiling = lights_at(upright(1.0, 1.0), ceiling=1.5)
    embers = _embers()
    for t in _moments(5.0):
        drawn(embers, render_ctx(t=t), low_ceiling)
        assert (embers.particles.pos[:, 2] <= 1.5 + 1e-5).all()


def test_each_lamp_has_about_per_lamp_embers_climbing_it() -> None:
    embers = _embers(per_lamp=4.0)
    counts = []
    for t in _moments(30.0):
        drawn(embers, render_ctx(t=t), LAMPS)
        counts.append(embers.particles.count)
    assert 3.0 * 4.0 * 0.8 < np.mean(counts) < 3.0 * 4.0 * 1.2
```

Create `tests/effects/test_rain_storm.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.particle_tools import lamps_of
from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.rain_storm import FLASH_S, JITTER_M, OVER_M, UNDER_M, RainStorm, flash

# Three upright lamps along a 6 m room.
LAMPS = lights_at(upright(0.5, 1.0), upright(3.0, 1.0), upright(5.5, 1.0))


def _storm(**settings: object) -> RainStorm:
    storm = RainStorm(**settings)
    storm.reseed(1)
    return storm


def test_rain_runs_down_each_lamp() -> None:
    lamps = lamps_of(LAMPS)
    storm = _storm(strikes_per_min=0.0, fall_s=1.0)
    drawn(storm, render_ctx(t=500.0), LAMPS)
    before = storm.particles.pos.copy()
    drawn(storm, render_ctx(t=500.05), LAMPS)
    after = storm.particles.pos

    for where in (before, after):
        gaps = np.linalg.norm(where[:, None, :2] - lamps.centre[None, :, :2], axis=2)
        assert (gaps.min(axis=1) <= JITTER_M + 1e-5).all()
        assert (where[:, 2] <= 1.4 + OVER_M + 1e-5).all()
        assert (where[:, 2] >= 0.1 - UNDER_M - 1e-5).all()
    # A drop runs 1.3 + 0.4 m in a second: 0.085 m in 0.05 s. Match each drop by its place.
    for drop in after:
        same = np.linalg.norm(before[:, :2] - drop[:2], axis=1) < 1e-4
        if same.any():  # not one that started since
            np.testing.assert_allclose(before[same, 2][0] - drop[2], 0.085, atol=1e-4)


def test_rain_runs_down_past_leds_all_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long
    storm = _storm(strikes_per_min=0.0, drops_per_lamp=8.0)
    xs = []
    for t in np.arange(500.0, 502.0, 0.1):
        drawn(storm, render_ctx(t=float(t)), leds)
        pos = storm.particles.pos
        gaps = np.linalg.norm(pos[:, None, :2] - leds.pos[None, :, :2], axis=2).min(axis=1)
        assert (gaps <= JITTER_M + 1e-5).all()
        xs.extend(pos[:, 0].tolist())
    assert np.ptp(xs) > 3.0  # past LEDs all along it, not past its middle


def test_lightning_lights_each_lamp_by_its_distance_from_the_strike() -> None:
    storm = _storm(palette=["#000000"], strikes_per_min=30.0, strike_reach=3.0)
    for t in np.arange(500.0, 510.0, 0.01):
        frame = drawn(storm, render_ctx(t=float(t)), LAMPS)
        strikes = storm.particles.radius > 2.0
        if strikes.any() and frame.max() > 0.2:
            break
    else:
        raise AssertionError("no strike in 10 s at 30 a minute")
    spot = storm.particles.pos[strikes][0]
    lamps = lamps_of(LAMPS)
    nearest_first = np.argsort(np.linalg.norm(lamps.centre[:, :2] - spot[:2], axis=1))
    glow = [frame[14 * lamp : 14 * lamp + 14, 0].mean() for lamp in nearest_first]
    assert glow[0] >= glow[1] >= glow[2]
    assert glow[0] > glow[2]


def test_no_lightning_at_no_strikes_a_minute() -> None:
    storm = _storm(strikes_per_min=0.0)
    for t in np.arange(500.0, 560.0, 0.25):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        assert (storm.particles.radius < 1.0).all()


def test_a_strike_flashes_dims_and_flickers_once_more() -> None:
    ages = np.array([0.0, 0.15, 0.25, FLASH_S])
    first, dim, flicker, over = flash(ages)
    assert first == 1.0
    assert dim < 0.25 < 0.5 < flicker
    assert over < 0.01
```

Create `tests/effects/test_spotlights.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.spotlights import Spotlights

# Five upright lamps round a room.
FIVE = lights_at(
    upright(0.5, 0.5), upright(4.5, 0.5), upright(4.5, 3.5), upright(0.5, 3.5), upright(2.5, 2.0)
)


def _spots(**settings: object) -> Spotlights:
    spots = Spotlights(**settings)
    spots.reseed(1)
    return spots


def _off_the_leds(pos: np.ndarray) -> np.ndarray:
    """How far each spotlight is from the nearest LED."""
    return np.linalg.norm(pos[:, None, :] - FIVE.pos[None, :, :], axis=2).min(axis=1)


def test_a_spotlight_rests_on_an_led_then_glides_to_the_next_lamp() -> None:
    spots = _spots(count=1, hold_s=4.0, move_s=3.0)
    resting, gliding, lamps = [], [], []
    for t in np.arange(700.0, 728.0, 0.25):  # four steps of 7 s
        drawn(spots, render_ctx(t=float(t)), FIVE)
        pos = spots.particles.pos
        if (t / 7.0) % 1.0 < 4.0 / 7.0:
            resting.append(_off_the_leds(pos)[0])
            lamps.append(int(np.argmin(np.linalg.norm(pos[0, :2] - FIVE.pos[::14, :2], axis=1))))
        else:
            gliding.append(_off_the_leds(pos)[0])
    assert max(resting) < 1e-4  # on an LED while it rests
    assert max(gliding) > 0.5  # between lamps as it glides
    visits = [lamp for lamp, before in zip(lamps, [-1, *lamps], strict=False) if lamp != before]
    assert len(visits) == 4  # a lamp a step, never one twice running


def test_with_one_lamp_a_spotlight_moves_up_and_down_it() -> None:
    one = lights_at(upright(2.0, 2.0))
    spots = _spots(count=3)
    heights = []
    for t in np.arange(700.0, 760.0, 0.5):
        drawn(spots, render_ctx(t=float(t)), one)
        np.testing.assert_allclose(spots.particles.pos[:, :2], [[2.0, 2.0]] * 3, atol=1e-5)
        heights.append(spots.particles.pos[:, 2])
    assert 0.1 - 1e-5 <= np.min(heights) and np.max(heights) <= 1.4 + 1e-5
    assert np.ptp(heights) > 0.5  # from one of its LEDs to another


def test_spotlights_set_off_at_even_shares_of_a_step_apart() -> None:
    spots = _spots(count=2, hold_s=4.0, move_s=3.0)
    for t in np.arange(700.0, 728.0, 0.25):
        drawn(spots, render_ctx(t=float(t)), FIVE)
        assert _off_the_leds(spots.particles.pos).min() < 1e-4  # one of the two rests
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects/test_embers.py tests/effects/test_rain_storm.py tests/effects/test_spotlights.py -q 2>&1 | tail -4`
Expected: FAIL: three collection errors, `ModuleNotFoundError: No module named 'dj_ledfx.effects.embers'` and the same for `rain_storm` and `spotlights`.

- [ ] **Step 3: Write the three effects, and register them**

Create `src/dj_ledfx/effects/embers.py`:

```python
"""Embers' particles (looks.json "embers"); the look's firmware layer runs LIFX Flame beside
them.

Each lamp sends embers up from its foot (spec §5.1: "embers rise from lamp bases"), a few at
a time, each under an LED of its own (Ground.foot), so a long light smoulders along its
length; each climbs to just over the lamp's top as it dies: hot and bright as it catches,
dimmer and redder as it climbs, flickering all the way. Ember n of lamp s comes from draws()
of its key alone, so an ember is where it is whenever it's drawn.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, recent, swarm
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

EMBER_PALETTE = ("#fff0a0", "#ffa020", "#ff4808", "#901000")  # catching to dying
CLIMB_OVER_M = 0.3  # an ember dies this far over its lamp's top (or at the ceiling)
WOBBLE_M = 0.06  # how far it wanders from its LED as it climbs
WOBBLE_S = 2.0  # once round in this long
LIFE_SPREAD = 0.5  # an ember lives its rise time, give or take a quarter
FLICKER_HZ = 7.0
CATCH_S = 0.15  # it brightens over this as it catches
LAMP_KEYS = 65536  # ember n of lamp s draws from key n * LAMP_KEYS + s


class Embers(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(EMBER_PALETTE), label="Palette"
            ),
            "per_lamp": EffectParam(
                type="float",
                default=3.0,
                min=0.5,
                max=10.0,
                step=0.5,
                label="Embers",
                description="Embers climbing each lamp at once",
                bindable=True,
            ),
            "rise_s": EffectParam(
                type="float",
                default=4.0,
                min=1.0,
                max=15.0,
                step=0.5,
                label="Rise",
                description="Seconds an ember takes to climb",
            ),
            "size": EffectParam(
                type="float",
                default=0.12,
                min=0.03,
                max=0.5,
                step=0.01,
                label="Ember size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        rise = float(values["rise_s"])
        every = rise / float(values["per_lamp"])  # one ember leaves each lamp this often
        n = recent(ctx.t, every, rise * (1.0 + LIFE_SPREAD / 2.0))
        lamp = np.tile(np.arange(lamps.count), len(n))
        u = draws(self._seed, np.repeat(n, lamps.count) * LAMP_KEYS + lamp, 5)
        born = (np.repeat(n, lamps.count) + u[:, 0]) * every
        age = ctx.t - born
        share = age / (rise * (1.0 - LIFE_SPREAD / 2.0 + LIFE_SPREAD * u[:, 1]))
        alive = np.flatnonzero((age >= 0.0) & (share < 1.0))
        alive = alive[np.argsort(born[alive], kind="stable")]  # oldest first
        lamp, u, age, share = lamp[alive], u[alive], age[alive], share[alive]
        wobble = 2.0 * math.pi * (u[:, 2] + age / WOBBLE_S)
        foot = ground.foot(lamp, u[:, 4])
        top = np.maximum(np.minimum(lamps.high[lamp] + CLIMB_OVER_M, ground.ceiling), foot[:, 2])
        pos = np.stack(
            [
                foot[:, 0] + WOBBLE_M * np.sin(wobble),
                foot[:, 1] + WOBBLE_M * np.cos(wobble),
                foot[:, 2] + (top - foot[:, 2]) * share**0.8,
            ],
            axis=1,
        )
        flicker = 0.75 + 0.25 * np.sin(2.0 * math.pi * (FLICKER_HZ * age + u[:, 3]))
        glow = flicker * (1.0 - share) * np.minimum(1.0, age / CATCH_S)
        colour = palette_at(self._palette, share) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
```

Create `src/dj_ledfx/effects/rain_storm.py`:

```python
"""Rain storm's particles (looks.json "rain"): drops and lightning.

Drops run down each lamp from just over its top to just under its bottom, a few at a time,
each past an LED of its own (Ground.on), so rain runs along a long light's length. A strike
comes once in each stretch of 60 / strikes_per_min seconds, at a random moment and a random
spot over the zone's floor at half the ceiling's height: one particle as wide as
strike_reach, so each lamp lights by its distance from the strike. It flashes, dims, and
flickers once more.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at, palette_float
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import NO_PARTICLES, draws, joined, recent, swarm
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

RAIN_PALETTE = ("#2850ff", "#78b4ff", "#c8e6ff")
LIGHTNING = "#e6eeff"
OVER_M = 0.25  # a drop starts this far over its lamp's top
UNDER_M = 0.15  # and runs out this far under its bottom
JITTER_M = 0.05  # how far from its LED a drop runs
EDGE = 0.1  # a drop fades in over this share of its run, and out over the last
FLASH_S = 0.6  # a strike is over in this long
LAMP_KEYS = 65536  # drop n of lamp s draws from key n * LAMP_KEYS + s


def flash(age: NDArray[np.float64]) -> NDArray[np.float64]:
    """A strike's brightness `age` seconds after it: a flash, and a flicker after it."""
    envelope: NDArray[np.float64] = np.exp(-age / 0.08) + 0.6 * np.exp(
        -(((age - 0.25) / 0.06) ** 2)
    )
    return np.minimum(envelope, 1.0)


class RainStorm(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(RAIN_PALETTE), label="Palette"),
            "lightning": EffectParam(type="color", default=LIGHTNING, label="Lightning"),
            "drops_per_lamp": EffectParam(
                type="float",
                default=2.0,
                min=0.5,
                max=8.0,
                step=0.5,
                label="Drops",
                description="Drops running down each lamp at once",
                bindable=True,
            ),
            "fall_s": EffectParam(
                type="float",
                default=1.0,
                min=0.3,
                max=4.0,
                step=0.1,
                label="Fall",
                description="Seconds a drop takes to run down a lamp",
            ),
            "size": EffectParam(
                type="float",
                default=0.1,
                min=0.03,
                max=0.4,
                step=0.01,
                label="Drop size",
                description="Metres",
            ),
            "strikes_per_min": EffectParam(
                type="float",
                default=4.0,
                min=0.0,
                max=30.0,
                step=1.0,
                label="Lightning",
                description="Strikes a minute; none at 0",
                bindable=True,
            ),
            "strike_reach": EffectParam(
                type="float",
                default=3.0,
                min=1.0,
                max=10.0,
                step=0.5,
                label="Strike reach",
                description="Metres",
            ),
        }

    def _prepare(self) -> None:
        super()._prepare()
        self._lightning = palette_float([self._values["lightning"]])[0]

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        return joined(self._drops(ctx, ground), self._strikes(ctx, ground))

    def _drops(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        fall = float(values["fall_s"])
        every = fall / float(values["drops_per_lamp"])  # a drop starts down each lamp this often
        n = recent(ctx.t, every, fall)
        lamp = np.tile(np.arange(lamps.count), len(n))
        u = draws(self._seed, np.repeat(n, lamps.count) * LAMP_KEYS + lamp, 4)
        born = (np.repeat(n, lamps.count) + u[:, 0]) * every
        share = (ctx.t - born) / fall  # 0 over the lamp's top, 1 under its bottom
        alive = np.flatnonzero((share >= 0.0) & (share < 1.0))
        alive = alive[np.argsort(born[alive], kind="stable")]  # oldest first
        lamp, u, share = lamp[alive], u[alive], share[alive]
        top, bottom = lamps.high[lamp] + OVER_M, lamps.low[lamp] - UNDER_M
        side = 2.0 * math.pi * u[:, 1]
        past = ground.on(lamp, u[:, 3])
        pos = np.stack(
            [
                past[:, 0] + JITTER_M * np.cos(side),
                past[:, 1] + JITTER_M * np.sin(side),
                top - (top - bottom) * share,
            ],
            axis=1,
        )
        fade = np.minimum(1.0, np.minimum(share, 1.0 - share) / EDGE)
        colour = palette_at(self._palette, u[:, 2]) * fade[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))

    def _strikes(self, ctx: RenderContext, ground: Ground) -> Particles:
        per_min = float(self._values["strikes_per_min"])
        if per_min <= 0.0:
            return NO_PARTICLES
        every = 60.0 / per_min
        n = recent(ctx.t, every, FLASH_S)
        u = draws(self._seed, n, 3, stream=1)
        age = ctx.t - (n + u[:, 0]) * every
        alive = (age >= 0.0) & (age < FLASH_S)
        low, high = ground.low.astype(np.float64), ground.high.astype(np.float64)
        spot = low[:2] + u[alive, 1:] * (high[:2] - low[:2])
        pos = np.column_stack([spot, np.full(len(spot), (ground.floor + ground.ceiling) / 2.0)])
        colour = self._lightning[None, :] * flash(age[alive])[:, None].astype(np.float32)
        return swarm(pos, colour, float(self._values["strike_reach"]))
```

Create `src/dj_ledfx/effects/spotlights.py`:

```python
"""Spotlights' particles (looks.json "spotlights").

Each spotlight rests on a lamp for hold_s, on an LED of it (any of its LEDs, its own each
visit), then glides to the next over move_s, on a tour of its own (particle_tools.tour):
every lamp once a round in a shuffled order, never the same lamp twice in a row. The
spotlights set off at even shares of a step apart, so they're never all on the move at once.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm, tour
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

SPOT_PALETTE = ("#ffd28c", "#8cc8ff")


class Spotlights(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(SPOT_PALETTE), label="Palette"),
            "count": EffectParam(type="int", default=2, min=1, max=6, step=1, label="Spotlights"),
            "hold_s": EffectParam(
                type="float",
                default=4.0,
                min=0.5,
                max=30.0,
                step=0.5,
                label="Rest",
                description="Seconds on each lamp",
                bindable=True,
            ),
            "move_s": EffectParam(
                type="float",
                default=3.0,
                min=0.5,
                max=30.0,
                step=0.5,
                label="Glide",
                description="Seconds from one lamp to the next",
                bindable=True,
            ),
            "size": EffectParam(
                type="float",
                default=0.8,
                min=0.2,
                max=3.0,
                step=0.1,
                label="Spot size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        count = int(values["count"])
        hold, move = float(values["hold_s"]), float(values["move_s"])
        rest = hold / (hold + move)  # the share of each step spent resting
        pos = np.zeros((count, 3))
        for spot in range(count):
            clock = ctx.t / (hold + move) + spot / count
            step = math.floor(clock)
            part = clock - step
            stops = [tour(self._seed, spot, visit, lamps.count) for visit in (step, step + 1)]
            spots = draws(self._seed, [step, step + 1], 1, stream=1 + spot)[:, 0]
            here, there = ground.on(stops, spots)
            glide = ease_in_out(max(0.0, (part - rest) / (1.0 - rest)))
            pos[spot] = here + (there - here) * glide
        colour = self._palette[np.arange(count) % len(self._palette)]
        return swarm(pos, colour, float(values["size"]))
```

In `src/dj_ledfx/effects/__init__.py`:

```diff
--- a/src/dj_ledfx/effects/__init__.py
+++ b/src/dj_ledfx/effects/__init__.py
@@ -4,6 +4,7 @@ from dj_ledfx.effects import breathe as _breathe  # noqa: F401
 from dj_ledfx.effects import checker_cubes as _checker_cubes  # noqa: F401
 from dj_ledfx.effects import color_carousel as _color_carousel  # noqa: F401
 from dj_ledfx.effects import color_chase as _color_chase  # noqa: F401
+from dj_ledfx.effects import embers as _embers  # noqa: F401
 from dj_ledfx.effects import fire_storm as _fire_storm  # noqa: F401
 from dj_ledfx.effects import fireflies as _fireflies  # noqa: F401
 from dj_ledfx.effects import firmware_lifx as _firmware_lifx  # noqa: F401
@@ -11,11 +12,13 @@ from dj_ledfx.effects import firmware_openrgb as _firmware_openrgb  # noqa: F401
 from dj_ledfx.effects import focus_field as _focus_field  # noqa: F401
 from dj_ledfx.effects import lava_plasma as _lava_plasma  # noqa: F401
 from dj_ledfx.effects import lighthouse_beam as _lighthouse_beam  # noqa: F401
+from dj_ledfx.effects import rain_storm as _rain_storm  # noqa: F401
 from dj_ledfx.effects import rainbow_wave as _rainbow_wave  # noqa: F401
 from dj_ledfx.effects import ripples as _ripples  # noqa: F401
 from dj_ledfx.effects import scanner_plane as _scanner_plane  # noqa: F401
 from dj_ledfx.effects import shockwave_shell as _shockwave_shell  # noqa: F401
 from dj_ledfx.effects import snowfall as _snowfall  # noqa: F401
 from dj_ledfx.effects import speaker_waves as _speaker_waves  # noqa: F401
+from dj_ledfx.effects import spotlights as _spotlights  # noqa: F401
 from dj_ledfx.effects import strobe as _strobe  # noqa: F401
 from dj_ledfx.effects import sunset_gradient as _sunset_gradient  # noqa: F401
```

- [ ] **Step 4: Run them to see them pass, and the sweep with them**

Run: `uv run pytest tests/effects/test_embers.py tests/effects/test_rain_storm.py tests/effects/test_spotlights.py tests/effects/test_particle_effects.py -q 2>&1 | tail -1 && uv run pytest tests/effects/test_particle_effects.py -m perf -q 2>&1 | tail -1`
Expected: PASS (`53 passed, 5 deselected`: the three effects' tests and the sweep, now over five effects), then `5 passed, 40 deselected`.

- [ ] **Step 5: Run the gate**

```bash
uv run ruff format src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/embers.py src/dj_ledfx/effects/rain_storm.py src/dj_ledfx/effects/spotlights.py tests/effects/test_embers.py tests/effects/test_rain_storm.py tests/effects/test_spotlights.py
uv run ruff check --fix src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/embers.py src/dj_ledfx/effects/rain_storm.py src/dj_ledfx/effects/spotlights.py tests/effects/test_embers.py tests/effects/test_rain_storm.py tests/effects/test_spotlights.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `All checks passed!`, `355 files already formatted`, mypy's 16 errors (`checked 160 source files`), `2132 passed, 1 skipped, 48 deselected` and `48 passed` in the perf run.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/embers.py src/dj_ledfx/effects/rain_storm.py src/dj_ledfx/effects/spotlights.py tests/effects/test_embers.py tests/effects/test_rain_storm.py tests/effects/test_spotlights.py
git commit -m "feat(effects): the embers, rain_storm and spotlights particle effects"
```

---


### Task 6: The particles of `bursts`, `fountain` and `vortex`

The particles of `bursts`, `fountain` and `vortex` (ruling 10), the first three tempo looks: each moves with the beat count and phase, never the BPM (ruling 13). Bursts and the fountain start from an anchor (Task 8 gives each the one its description names), or the zone's middle on a map without it, and send particles to the lamps' LEDs; the vortex turns through the lamps. `lights_at()` gains anchors for their tests.

**Files:**
- Create: `src/dj_ledfx/effects/beat_bursts.py`, `src/dj_ledfx/effects/fountain.py`, `src/dj_ledfx/effects/vortex.py`, `tests/effects/test_beat_bursts.py`, `tests/effects/test_fountain.py`, `tests/effects/test_vortex.py`
- Modify: `src/dj_ledfx/effects/__init__.py`, `tests/map_home.py` (`lights_at()`)

**Interfaces:**
- Consumes: Task 1's `draws`, `recent`, `swarm`, `joined`, `arc`, `Lamps.pick`, `Ground.on`, `Ground.floor`, `Ground.ceiling`, `Ground.low` and `Ground.high`; Task 2's `ParamParticles`; `anchor_or_centre` (`effects/field_tools.py`), `anchor_param` (`effects/params.py`), `palette_at` (`effects/color.py`) and `BEATS_PER_BAR` (`tempo/model.py`).
- Produces:
  - `effects.beat_bursts.BeatBursts`, kind `beat_bursts`: settings `anchor` (none by default: the zone's middle), `palette`, `per_beat` (1–30, 12, bindable), `downbeat` (1–4 times, 2.5), `fade_beats` (0.25–4, 1.5) and `size` (0.05–1 m, 0.25); `burst_size(beat: int) -> int`, the particles in beat `beat`'s burst; `BURST_PALETTE`, `ARRIVE = 0.4`, `SCATTER_M = 0.15`, `BEAT_KEYS = 1024`.
  - `effects.fountain.Fountain`, kind `fountain`: settings `anchor`, `palette`, `rate` (5–120 drops a second, 30, bindable), `height_m` (0.3–3 m, 1.2, bindable), `spread_m` (0.2–5 m, 2), `burst` (0–60, 16) and `size` (0.05–0.5 m, 0.2); `FOUNTAIN_PALETTE`, `GRAVITY = 9.81`, `BURST_UP = 1.2`, `FLIGHT_BEATS = 1.0`, `REST_BEATS = 0.5`, `BEAT_KEYS = 256`.
  - `effects.vortex.Vortex`, kind `vortex`: settings `palette`, `count` (10–300, 60), `turns_per_bar` (0.1–2, 0.5, bindable), `kick` (0–1, 0.7), `rise_bars` (1–16, 4) and `size` (0.1–1 m, 0.3); `kicked(beats: float, kick: float) -> float`, the turn's progress in beats with `kick` of each beat's share coming in a rush at the beat; `VORTEX_PALETTE` (low to high), `LEAST_RADIUS_M = 0.5`, `JITTER_M = 0.2`.
  - In `tests/map_home.py`: `lights_at(*lights, ceiling=3.0, anchors: Mapping[str, Sequence[float]] | None = None)`.

- [ ] **Step 1: Write the failing tests**

In `tests/map_home.py`, anchors for a zone of lights:

```diff
--- a/tests/map_home.py
+++ b/tests/map_home.py
@@ -165,9 +165,13 @@ def leds_at(
     return build_ledset([LedSource("light", len(points), placed=placed)], space)


-def lights_at(*lights: Sequence[Sequence[float]], ceiling: float | None = 3.0) -> LedSet:
+def lights_at(
+    *lights: Sequence[Sequence[float]],
+    ceiling: float | None = 3.0,
+    anchors: Mapping[str, Sequence[float]] | None = None,
+) -> LedSet:
     """Lights' LEDs at these map positions, one light for each list of points, in this
-    order, in a zone with this ceiling and no anchors."""
+    order, in a zone with this ceiling and these anchors."""
     sources = [
         LedSource(
             f"light-{index}",
@@ -176,7 +180,8 @@ def lights_at(*lights: Sequence[Sequence[float]], ceiling: float | None = 3.0) -
         )
         for index, points in enumerate(lights)
     ]
-    return build_ledset(sources, Space(ceiling=ceiling))
+    points = {name: np.asarray(p, dtype=np.float32) for name, p in (anchors or {}).items()}
+    return build_ledset(sources, Space(anchors=MappingProxyType(points), ceiling=ceiling))


 def upright(x: float, y: float, low: float = 0.1, high: float = 1.4) -> list[list[float]]:
```

Create `tests/effects/test_beat_bursts.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.beat_bursts import SCATTER_M, BeatBursts
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import drawn

TV = np.array([2.0, 0.2, 1.0], dtype=np.float32)


def _room() -> LedSet:
    """Four upright lamps round a 4 x 4 m room, with a TV anchor on its north wall."""
    corners = (upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))
    return lights_at(*corners, anchors={"tv": TV})


def _bursts(**settings: object) -> BeatBursts:
    bursts = BeatBursts(anchor="tv", **settings)
    bursts.reseed(1)
    return bursts


def _at_the_tv(bursts: BeatBursts) -> int:
    return int((np.linalg.norm(bursts.particles.pos - TV, axis=1) < 1e-5).sum())


def test_every_beat_fires_a_burst_from_the_anchor_and_the_downbeat_a_bigger_one() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, downbeat=2.5)
    drawn(bursts, tempo_ctx(2001.0), room)  # beat 2001: the bar's second
    assert _at_the_tv(bursts) == 12
    drawn(bursts, tempo_ctx(2004.0), room)  # beat 2004: a downbeat
    assert _at_the_tv(bursts) == 30
    assert [bursts.burst_size(beat) for beat in range(2000, 2005)] == [30, 12, 12, 12, 30]


def test_each_particle_lands_on_an_led_of_a_lamp_and_every_lamp_gets_some() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, fade_beats=1.5)
    lamps = set()
    for beat in range(2001, 2009):
        drawn(bursts, tempo_ctx(beat + 0.7), room)  # landed: its burst is 0.7 beats old
        landed = bursts.particles.pos[bursts.particles.count - bursts.burst_size(beat) :]
        gaps = np.linalg.norm(landed[:, None, :] - room.pos[None, :, :], axis=2)
        assert (gaps.min(axis=1) <= SCATTER_M + 1e-5).all()
        lamps |= set((gaps.argmin(axis=1) // 14).tolist())
    assert lamps == {0, 1, 2, 3}


def test_a_burst_fades_by_fade_beats() -> None:
    room = _room()
    bursts = _bursts(per_beat=12, fade_beats=1.5, palette=["#ffffff"])
    drawn(bursts, tempo_ctx(2001.49), room)
    assert bursts.particles.count == 30 + 12  # the downbeat's burst, and beat 2001's
    assert (bursts.particles.colour[:30, 0] < 0.01).all()  # the downbeat's has all but faded
    drawn(bursts, tempo_ctx(2001.5), room)
    assert bursts.particles.count == 12  # and now it's gone


def test_a_burst_keeps_its_shape_at_any_tempo() -> None:
    room = _room()
    slow, fast = _bursts(), _bursts()
    drawn(slow, tempo_ctx(2001.3, bpm=60.0), room)
    drawn(fast, tempo_ctx(2001.3, bpm=240.0), room)
    np.testing.assert_array_equal(slow.particles.pos, fast.particles.pos)
```

Create `tests/effects/test_fountain.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.fountain import Fountain
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import drawn

TABLE = np.array([2.0, 2.0, 0.45], dtype=np.float32)


def _room() -> LedSet:
    """Four upright lamps round a 4 x 4 m room, with a coffee table in its middle."""
    corners = (upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))
    return lights_at(*corners, anchors={"coffee": TABLE})


def _fountain(**settings: object) -> Fountain:
    fountain = Fountain(anchor="coffee", **settings)
    fountain.reseed(1)
    return fountain


def _spray(fountain: Fountain, seconds: float = 4.0) -> np.ndarray:
    """Every drop's place over some seconds at 120 BPM, 30 times a second."""
    room = _room()
    seen = []
    for step in range(int(seconds * 30)):
        drawn(fountain, tempo_ctx(2000.0 + step / 15), room)
        seen.append(fountain.particles.pos)
    return np.concatenate(seen)


def test_the_spray_rises_to_its_height_and_never_falls_under_the_floor() -> None:
    where = _spray(_fountain(burst=0, height_m=1.2))
    assert where[:, 2].min() >= 0.0
    assert 0.85**2 * 1.2 < where[:, 2].max() - TABLE[2] <= 1.2 + 1e-4


def test_the_spray_comes_down_within_its_spread() -> None:
    where = _spray(_fountain(burst=0, spread_m=1.5))
    above = where[where[:, 2] >= TABLE[2]]  # before a drop falls past the table
    away = np.linalg.norm(above[:, :2] - TABLE[:2], axis=1)
    assert away.max() <= 1.5 + 1e-4
    assert away.max() > 1.0
    np.testing.assert_allclose(where[:, :2].mean(axis=0), TABLE[:2], atol=0.3)


def test_every_beat_fires_a_burst_of_drops() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=40)
    drawn(fountain, tempo_ctx(2000.999), room)
    before = fountain.particles.count
    drawn(fountain, tempo_ctx(2001.001), room)
    assert fountain.particles.count - before in (39, 40, 41)  # a spray drop may come or go


def test_a_burst_goes_higher_than_the_spray() -> None:
    sprayed = _spray(_fountain(burst=0))[:, 2].max()
    burst = _spray(_fountain(rate=5.0, burst=60))[:, 2].max()
    assert burst > sprayed + 0.3


def test_a_bursts_drops_land_on_leds_on_the_next_beat() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=8)
    drawn(fountain, tempo_ctx(2001.0), room)
    landed, leaving = fountain.particles.pos[-16:-8], fountain.particles.pos[-8:]
    gaps = np.linalg.norm(landed[:, None, :] - room.pos[None, :, :], axis=2).min(axis=1)
    assert (gaps < 1e-4).all()  # beat 2000's burst, on its LEDs
    np.testing.assert_allclose(leaving, np.repeat([TABLE], 8, axis=0), atol=1e-5)  # 2001's
```

Create `tests/effects/test_vortex.py`:

```python
from __future__ import annotations

import math

import numpy as np
from conftest import tempo_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.vortex import JITTER_M, Vortex, kicked


def _room() -> LedSet:
    """Four upright lamps round a 4 x 4 m room under a 3 m ceiling: its middle is (2, 2)."""
    return lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _vortex(**settings: object) -> Vortex:
    vortex = Vortex(**settings)
    vortex.reseed(1)
    return vortex


def _turn(pos: np.ndarray) -> np.ndarray:
    return np.arctan2(pos[:, 1] - 2.0, pos[:, 0] - 2.0)


def test_the_kick_puts_most_of_each_beats_turn_at_the_beat() -> None:
    assert kicked(7.0, 0.7) == 7.0 and kicked(8.0, 0.7) == 8.0  # whole beats stay whole
    assert kicked(7.5, 0.0) == 7.5  # no kick: even through the beat
    assert kicked(7.25, 0.7) - 7.0 > 0.45  # kicked: nearly half of it in the first quarter
    steps = [kicked(7.0 + i / 10, 0.7) for i in range(11)]
    assert all(b > a for a, b in zip(steps, steps[1:], strict=False))  # never back


def test_particles_spiral_up_round_the_middle_and_the_nearer_ones_turn_faster() -> None:
    room = _room()
    vortex = _vortex(kick=0.0, turns_per_bar=0.5)
    drawn(vortex, tempo_ctx(2000.0), room)
    first = vortex.particles.pos.copy()
    drawn(vortex, tempo_ctx(2000.4), room)
    then = vortex.particles.pos

    turned = np.mod(_turn(then) - _turn(first), 2.0 * math.pi)
    assert (turned > 0.0).all() and (turned < 0.5).all()  # all one way, a little
    out = np.linalg.norm(first[:, :2] - 2.0, axis=1)
    np.testing.assert_allclose(out, np.linalg.norm(then[:, :2] - 2.0, axis=1), atol=1e-5)
    assert np.corrcoef(out, turned)[0, 1] < -0.9  # the nearer, the faster
    rose = then[:, 2] - first[:, 2]
    assert ((rose > 0.0) | (rose < -2.5)).all()  # up, or back at the floor


def test_particles_glow_most_half_way_up() -> None:
    room = _room()
    vortex = _vortex(palette=["#ffffff"])
    drawn(vortex, tempo_ctx(2000.0), room)
    height = vortex.particles.pos[:, 2] / 3.0
    np.testing.assert_allclose(vortex.particles.colour[:, 0], np.sin(math.pi * height), atol=1e-5)


def test_the_rings_pass_through_leds_all_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long: the middle is its middle, (2, 0)
    vortex = _vortex()
    drawn(vortex, tempo_ctx(2000.0), leds)
    out = np.linalg.norm(vortex.particles.pos[:, :2] - np.array([2.0, 0.0]), axis=1)
    rings = np.abs(leds.pos[:, 0] - 2.0)  # each LED's distance from the middle
    assert (np.abs(out[:, None] - rings[None, :]).min(axis=1) <= JITTER_M + 1e-5).all()
    assert np.ptp(out) > 1.5  # rings through its ends as well as its middle
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects/test_beat_bursts.py tests/effects/test_fountain.py tests/effects/test_vortex.py -q 2>&1 | tail -4`
Expected: FAIL: three collection errors, `ModuleNotFoundError: No module named 'dj_ledfx.effects.beat_bursts'` and the same for `fountain` and `vortex`.

- [ ] **Step 3: Write the three effects, and register them**

Create `src/dj_ledfx/effects/beat_bursts.py`:

```python
"""Beat bursts' particles (looks.json "bursts").

Beat j's burst leaves the anchor on the beat, a bigger one on the downbeat, each particle
flying out to an LED of a lamp of its own (any lamp and any of its LEDs, at random) and
slowing as it lands there, ARRIVE of the way through its fade, then fading on the lamp; all
of it is gone fade_beats after the beat. Its colour is the palette's colour j, round and
round. Ages are in beats, so a burst keeps its shape at any tempo.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, anchor_param
from dj_ledfx.effects.particle_tools import draws, recent, swarm
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

BURST_PALETTE = ("#ff3cc8", "#3cc8ff", "#ffe63c", "#ffffff")
ARRIVE = 0.4  # a particle lands on its lamp this share of the way through its fade
SCATTER_M = 0.15  # it lands within this of its LED
BEAT_KEYS = 1024  # particle k of beat j's burst draws from key j * BEAT_KEYS + k


class BeatBursts(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": anchor_param("Fires from"),
            "palette": EffectParam(
                type="color_list", default=list(BURST_PALETTE), label="Palette"
            ),
            "per_beat": EffectParam(
                type="int",
                default=12,
                min=1,
                max=30,
                step=1,
                label="Particles",
                description="Particles in each beat's burst",
                bindable=True,
            ),
            "downbeat": EffectParam(
                type="float",
                default=2.5,
                min=1.0,
                max=4.0,
                step=0.5,
                label="Downbeat",
                description="Times as many on the downbeat",
            ),
            "fade_beats": EffectParam(
                type="float",
                default=1.5,
                min=0.25,
                max=4.0,
                step=0.25,
                label="Fade",
                description="Beats a burst takes to fade",
            ),
            "size": EffectParam(
                type="float",
                default=0.25,
                min=0.05,
                max=1.0,
                step=0.05,
                label="Particle size",
                description="Metres",
            ),
        }

    def burst_size(self, beat: int) -> int:
        """How many particles beat `beat`'s burst fires."""
        size = int(self._values["per_beat"])
        if beat % BEATS_PER_BAR == 0:
            return round(size * float(self._values["downbeat"]))
        return size

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        fade = float(values["fade_beats"])
        beats = ctx.beats
        alive = [int(j) for j in recent(beats, 1.0, fade) if 0.0 <= beats - j < fade]
        sizes = [self.burst_size(j) for j in alive]
        beat = np.repeat(np.array(alive, dtype=np.int64), sizes)
        k = np.array([i for size in sizes for i in range(size)], dtype=np.int64)
        u = draws(self._seed, beat * BEAT_KEYS + k, 5)
        lamp = ground.lamps.pick(u[:, 0])
        up = 2.0 * u[:, 1] - 1.0  # where round its LED it lands
        side = 2.0 * math.pi * u[:, 2]
        flat = np.sqrt(1.0 - up * up)
        near = SCATTER_M * np.cbrt(u[:, 3])[:, None]
        landing = ground.on(lamp, u[:, 4]) + near * np.stack(
            [flat * np.cos(side), flat * np.sin(side), up], axis=1
        )
        age = (beats - beat) / fade  # 0 on the beat, 1 faded
        way = 1.0 - (1.0 - np.minimum(age / ARRIVE, 1.0)) ** 2  # fast out, slowing to land
        origin = anchor_or_centre(ground.leds, str(values["anchor"])).astype(np.float64)
        pos = origin + (landing - origin) * way[:, None]
        palette = self._palette
        colour = palette[beat % len(palette)] * (1.0 - age)[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
```

Create `src/dj_ledfx/effects/fountain.py`:

```python
"""Fountain's particles (looks.json "fountain").

A steady spray leaves the anchor `rate` times a second, each drop thrown up to about
height_m and out on its own heading, landing back at the anchor's height up to spread_m
away, then falling on to the floor. On every beat a burst of `burst` drops is thrown higher,
each to an LED of a lamp of its own (any lamp and any of its LEDs, at random): it lands
there on the next beat and fades over half a beat. The spray is timed in seconds and the
bursts in beats.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.field_tools import anchor_or_centre
from dj_ledfx.effects.params import EffectParam, anchor_param
from dj_ledfx.effects.particle_tools import arc, draws, joined, recent, swarm
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

FOUNTAIN_PALETTE = ("#2878ff", "#64c8ff", "#e6faff")
GRAVITY = 9.81  # m/s²
BURST_UP = 1.2  # a burst's drops rise this much higher than the spray, give or take a fifth
FLIGHT_BEATS = 1.0  # they land on their lamps on the next beat
REST_BEATS = 0.5  # and fade there over this
BEAT_KEYS = 256  # drop k of beat j's burst draws from key j * BEAT_KEYS + k


class Fountain(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "anchor": anchor_param("Sprays from"),
            "palette": EffectParam(
                type="color_list", default=list(FOUNTAIN_PALETTE), label="Palette"
            ),
            "rate": EffectParam(
                type="float",
                default=30.0,
                min=5.0,
                max=120.0,
                step=5.0,
                label="Spray",
                description="Drops a second",
                bindable=True,
            ),
            "height_m": EffectParam(
                type="float",
                default=1.2,
                min=0.3,
                max=3.0,
                step=0.1,
                label="Height",
                description="Metres the spray goes up",
                bindable=True,
            ),
            "spread_m": EffectParam(
                type="float",
                default=2.0,
                min=0.2,
                max=5.0,
                step=0.1,
                label="Spread",
                description="Metres from the fountain the spray lands, at most",
            ),
            "burst": EffectParam(
                type="int",
                default=16,
                min=0,
                max=60,
                step=1,
                label="Burst",
                description="Drops in each beat's burst",
            ),
            "size": EffectParam(
                type="float",
                default=0.2,
                min=0.05,
                max=0.5,
                step=0.05,
                label="Drop size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        origin = anchor_or_centre(ground.leds, str(self._values["anchor"])).astype(np.float64)
        return joined(self._spray(ctx, ground, origin), self._bursts(ctx, ground, origin))

    def _spray(self, ctx: RenderContext, ground: Ground, origin: NDArray[np.float64]) -> Particles:
        """The steady spray: drops thrown up and out under gravity, until the floor."""
        values = self._values
        up = math.sqrt(2.0 * GRAVITY * float(values["height_m"]))  # m/s to the height
        fall = max(float(origin[2]) - ground.floor, 0.0)
        longest = (up + math.sqrt(up * up + 2.0 * GRAVITY * fall)) / GRAVITY  # to the floor
        every = 1.0 / float(values["rate"])
        n = recent(ctx.t, every, longest)
        u = draws(self._seed, n, 4)
        age = ctx.t - (n + u[:, 0]) * every
        speed = up * (0.85 + 0.15 * u[:, 1])  # up, m/s
        flight = 2.0 * speed / GRAVITY  # up and back down to the anchor's height
        out = float(values["spread_m"]) * np.sqrt(u[:, 3]) / flight  # m/s
        z = origin[2] + speed * age - 0.5 * GRAVITY * age * age
        kept = np.flatnonzero((age >= 0.0) & (z >= ground.floor))
        kept = kept[np.argsort(-age[kept], kind="stable")]  # oldest first
        away, heading = out[kept] * age[kept], 2.0 * math.pi * u[kept, 2]
        pos = np.stack(
            [origin[0] + away * np.cos(heading), origin[1] + away * np.sin(heading), z[kept]],
            axis=1,
        )
        glow = np.clip(1.5 - age[kept] / flight[kept], 0.0, 1.0)  # fades as it falls past
        colour = palette_at(self._palette, u[kept, 1]) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))

    def _bursts(
        self, ctx: RenderContext, ground: Ground, origin: NDArray[np.float64]
    ) -> Particles:
        """Each beat's burst: drops thrown from the anchor to the lamps."""
        values = self._values
        size, beats = int(values["burst"]), ctx.beats
        fired = recent(beats, 1.0, FLIGHT_BEATS + REST_BEATS)
        fired = fired[(fired <= beats) & (beats - fired < FLIGHT_BEATS + REST_BEATS)]
        beat = np.repeat(fired, size)
        u = draws(self._seed, beat * BEAT_KEYS + np.tile(np.arange(size), len(fired)), 3, stream=1)
        landing = ground.on(ground.lamps.pick(u[:, 0]), u[:, 2])
        share = (beats - beat.astype(np.float64)) / FLIGHT_BEATS  # 1: landed
        rise = float(values["height_m"]) * BURST_UP * (0.8 + 0.4 * u[:, 1])
        pos = arc(origin, landing, np.minimum(share, 1.0), rise)
        glow = np.clip(1.0 - (share - 1.0) * FLIGHT_BEATS / REST_BEATS, 0.0, 1.0)
        colour = palette_at(self._palette, u[:, 1]) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
```

Create `src/dj_ledfx/effects/vortex.py`:

```python
"""Vortex's particles (looks.json "vortex").

Each particle circles the zone's middle on the ring through an LED of one of its lamps (any
of its LEDs, at random; seen from above), the lamps taken in turn, so the particles sweep
through the lamps as they go round, the nearer rings faster. Each rises from the floor to
the ceiling over rise_bars bars, then starts again at the floor. The turn follows the music,
not the clock: `kick` of each beat's share of the turn comes in a rush at the beat.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

VORTEX_PALETTE = ("#7828ff", "#2878ff", "#28e6c8")  # low to high
LEAST_RADIUS_M = 0.5  # the vortex is at least this wide each way
JITTER_M = 0.2  # a particle circles this close to its lamp's ring, either side


def kicked(beats: float, kick: float) -> float:
    """The beats counted with `kick` of each beat in a rush at its start: whole beats stay
    whole, and the share of a beat gone is eased out (fast, then slow) as much as kick says."""
    whole = math.floor(beats)
    part = beats - whole
    return whole + (1.0 - kick) * part + kick * (1.0 - (1.0 - part) ** 3)


class Vortex(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(VORTEX_PALETTE), label="Palette"
            ),
            "count": EffectParam(
                type="int", default=60, min=10, max=300, step=10, label="Particles"
            ),
            "turns_per_bar": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=2.0,
                step=0.1,
                label="Spin",
                description="Turns round the room each bar",
                bindable=True,
            ),
            "kick": EffectParam(
                type="float",
                default=0.7,
                min=0.0,
                max=1.0,
                step=0.05,
                label="Kick",
                description="How much of each beat's turn comes at the beat",
            ),
            "rise_bars": EffectParam(
                type="float",
                default=4.0,
                min=1.0,
                max=16.0,
                step=1.0,
                label="Rise",
                description="Bars from the floor to the ceiling",
            ),
            "size": EffectParam(
                type="float",
                default=0.3,
                min=0.1,
                max=1.0,
                step=0.05,
                label="Particle size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        count = int(values["count"])
        u = draws(self._seed, np.arange(count), 4)
        bars = kicked(ctx.beats, float(values["kick"])) / BEATS_PER_BAR
        lamps = ground.lamps
        middle = ((ground.low + ground.high) / 2.0).astype(np.float64)
        past = ground.on(np.arange(count) % lamps.count, u[:, 3])
        ring = np.linalg.norm(past[:, :2] - middle[:2], axis=1)
        out = np.maximum(ring + JITTER_M * (2.0 * u[:, 0] - 1.0), 0.0)
        widest = max(float(out.max()), LEAST_RADIUS_M)
        speed = float(values["turns_per_bar"]) * (1.4 - 0.6 * out / widest)  # nearer: faster
        turn = 2.0 * math.pi * (u[:, 1] + bars * speed)
        height = np.mod(u[:, 2] + bars / float(values["rise_bars"]), 1.0)
        pos = np.stack(
            [
                middle[0] + out * np.cos(turn),
                middle[1] + out * np.sin(turn),
                ground.floor + height * (ground.ceiling - ground.floor),
            ],
            axis=1,
        )
        glow = np.sin(math.pi * height)  # dark at the floor and at the ceiling
        colour = palette_at(self._palette, height) * glow[:, None].astype(np.float32)
        return swarm(pos, colour, float(values["size"]))
```

In `src/dj_ledfx/effects/__init__.py`:

```diff
--- a/src/dj_ledfx/effects/__init__.py
+++ b/src/dj_ledfx/effects/__init__.py
@@ -1,4 +1,5 @@
 from dj_ledfx.effects import aurora_curtains as _aurora_curtains  # noqa: F401
+from dj_ledfx.effects import beat_bursts as _beat_bursts  # noqa: F401
 from dj_ledfx.effects import beat_pulse as _beat_pulse  # noqa: F401
 from dj_ledfx.effects import breathe as _breathe  # noqa: F401
 from dj_ledfx.effects import checker_cubes as _checker_cubes  # noqa: F401
@@ -10,6 +11,7 @@ from dj_ledfx.effects import fireflies as _fireflies  # noqa: F401
 from dj_ledfx.effects import firmware_lifx as _firmware_lifx  # noqa: F401
 from dj_ledfx.effects import firmware_openrgb as _firmware_openrgb  # noqa: F401
 from dj_ledfx.effects import focus_field as _focus_field  # noqa: F401
+from dj_ledfx.effects import fountain as _fountain  # noqa: F401
 from dj_ledfx.effects import lava_plasma as _lava_plasma  # noqa: F401
 from dj_ledfx.effects import lighthouse_beam as _lighthouse_beam  # noqa: F401
 from dj_ledfx.effects import rain_storm as _rain_storm  # noqa: F401
@@ -22,3 +24,4 @@ from dj_ledfx.effects import speaker_waves as _speaker_waves  # noqa: F401
 from dj_ledfx.effects import spotlights as _spotlights  # noqa: F401
 from dj_ledfx.effects import strobe as _strobe  # noqa: F401
 from dj_ledfx.effects import sunset_gradient as _sunset_gradient  # noqa: F401
+from dj_ledfx.effects import vortex as _vortex  # noqa: F401
```

- [ ] **Step 4: Run them to see them pass, and the sweep with them**

Run: `uv run pytest tests/effects/test_beat_bursts.py tests/effects/test_fountain.py tests/effects/test_vortex.py tests/effects/test_particle_effects.py -q 2>&1 | tail -1 && uv run pytest tests/effects/test_particle_effects.py -m perf -q 2>&1 | tail -1`
Expected: PASS (`77 passed, 8 deselected`: the sweep now over eight effects), then `8 passed, 64 deselected`.

- [ ] **Step 5: Run the gate**

```bash
uv run ruff format src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/beat_bursts.py src/dj_ledfx/effects/fountain.py src/dj_ledfx/effects/vortex.py tests/effects/test_beat_bursts.py tests/effects/test_fountain.py tests/effects/test_vortex.py tests/map_home.py
uv run ruff check --fix src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/beat_bursts.py src/dj_ledfx/effects/fountain.py src/dj_ledfx/effects/vortex.py tests/effects/test_beat_bursts.py tests/effects/test_fountain.py tests/effects/test_vortex.py tests/map_home.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `All checks passed!`, `361 files already formatted`, mypy's 16 errors (`checked 163 source files`), `2169 passed, 1 skipped, 51 deselected` and `51 passed` in the perf run.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/beat_bursts.py src/dj_ledfx/effects/fountain.py src/dj_ledfx/effects/vortex.py tests/effects/test_beat_bursts.py tests/effects/test_fountain.py tests/effects/test_vortex.py tests/map_home.py
git commit -m "feat(effects): the beat_bursts, fountain and vortex particle effects, on the beat"
```

---


### Task 7: The particles of `comets`, `ball` and `flock`

The particles of `comets`, `ball` and `flock` (ruling 10), the tempo looks that travel the lamps: §5.1's "comets follow a path through lamps". Each lands or gathers on the beat at any tempo (ruling 13; Review Focus 2).

**Files:**
- Create: `src/dj_ledfx/effects/twin_comets.py`, `src/dj_ledfx/effects/bouncing_ball.py`, `src/dj_ledfx/effects/flock.py`, `tests/effects/test_twin_comets.py`, `tests/effects/test_bouncing_ball.py`, `tests/effects/test_flock.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

**Interfaces:**
- Consumes: Task 1's `draws`, `swarm`, `arc`, `around`, `tour`, `Lamps.count`, `Lamps.centre`, `Ground.on`, `Ground.foot`, `Ground.centre` and `Ground.ceiling`; Task 2's `ParamParticles`; `palette_at` (`effects/color.py`), `ease_in_out` (`effects/easing.py`) and `BEATS_PER_BAR` (`tempo/model.py`).
- Produces:
  - `effects.twin_comets.TwinComets`, kind `twin_comets`: settings `palette`, `tail` (0–30 particles, 8), `tail_beats` (0.1–2, 0.5) and `size` (0.1–1 m, 0.35); `at(beats: NDArray[np.float64], comet: int, ground: Ground) -> NDArray[np.float64]`, where a comet is at those beats; `COMET_PALETTE`, `COMETS = 2`, `HOP = 0.25`.
  - `effects.bouncing_ball.BouncingBall`, kind `bouncing_ball`: settings `palette`, `height_m` (0.3–3 m, 1.5, bindable) and `size` (0.1–1.5 m, 0.5); `BALL_PALETTE`.
  - `effects.flock.Flock`, kind `flock`: settings `palette`, `count` (5–200, 40), `spread_m` (0.2–3 m, 0.8), `scatter` (1–8 times, 3) and `size` (0.05–0.6 m, 0.2); `scattered(since: float, scatter: float) -> float`, how far out the birds are `since` beats after a scattering downbeat; `FLOCK_PALETTE`, `MOVE_BARS = 2`, `SWIRL_BARS = 2.0`, `SCATTER_BEATS = 0.75`, `FLAT = 0.5`.

- [ ] **Step 1: Write the failing tests**

Create `tests/effects/test_twin_comets.py`:

```python
from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.twin_comets import TwinComets

# Four upright lamps at the corners of a 4 x 4 m room: round its middle, (2, 2), they go
# south-west, south-east, north-east, north-west.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _comets(**settings: object) -> TwinComets:
    comets = TwinComets(**settings)
    comets.reseed(1)
    return comets


def _off_the_leds(pos: np.ndarray) -> np.ndarray:
    return np.linalg.norm(pos[:, None, :] - ROOM.pos[None, :, :], axis=2).min(axis=1)


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_each_comet_lands_on_an_led_on_every_beat_at_any_tempo(bpm: float) -> None:
    comets = _comets(tail=0)
    for beat in range(2000, 2008):
        drawn(comets, tempo_ctx(float(beat), bpm=bpm), ROOM)
        assert (_off_the_leds(comets.particles.pos) < 1e-4).all()
        drawn(comets, tempo_ctx(beat + 0.5, bpm=bpm), ROOM)
        assert (_off_the_leds(comets.particles.pos) > 0.5).all()  # in the air between


def test_the_comets_go_round_the_loop_a_lamp_a_beat_on_opposite_sides() -> None:
    comets = _comets(tail=0)
    turns = []
    for beat in range(2000, 2009):
        drawn(comets, tempo_ctx(float(beat)), ROOM)
        first, second = comets.particles.pos[:, :2].astype(np.float64)
        assert np.linalg.norm(first - second) > 4.0  # at opposite corners
        turns.append(math.atan2(first[1] - 2.0, first[0] - 2.0))
    steps = np.mod(np.diff(turns), 2.0 * math.pi)
    np.testing.assert_allclose(steps, math.pi / 2.0, atol=1e-5)  # the next lamp round


def test_a_tail_trails_where_its_comet_was_fading_and_shrinking() -> None:
    comets = _comets(tail=4, tail_beats=0.5, palette=["#ffffff"])
    drawn(comets, tempo_ctx(2003.3), ROOM)
    tail = comets.particles  # the first comet's five first, its tail's end first
    for place, back in enumerate((4, 3, 2, 1, 0)):
        head = _comets(tail=0)
        drawn(head, tempo_ctx(2003.3 - 0.5 * back / 5), ROOM)
        np.testing.assert_allclose(tail.pos[place], head.particles.pos[0], atol=1e-5)
    assert (np.diff(tail.colour[:5, 0]) > 0.0).all() and (np.diff(tail.radius[:5]) > 0.0).all()
```

Create `tests/effects/test_bouncing_ball.py`:

```python
from __future__ import annotations

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.bouncing_ball import BouncingBall
from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.particles import drawn

# Three upright lamps and a bulb at the corners of a 4 x 4 m room, and where each one's
# foot is.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), [(0.5, 3.5, 1.2)])
FEET = np.array([[0.5, 0.5, 0.1], [3.5, 0.5, 0.1], [3.5, 3.5, 0.1], [0.5, 3.5, 1.2]])


def _ball(**settings: object) -> BouncingBall:
    ball = BouncingBall(**settings)
    ball.reseed(1)
    return ball


def _landings(ball: BouncingBall, beats: range, bpm: float = 120.0) -> list[int]:
    """The foot the ball is on at each whole beat; it must be on one."""
    feet = []
    for beat in beats:
        drawn(ball, tempo_ctx(float(beat), bpm=bpm), ROOM)
        gaps = np.linalg.norm(FEET - ball.particles.pos[0], axis=1)
        assert gaps.min() < 1e-4
        feet.append(int(gaps.argmin()))
    return feet


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_the_ball_lands_on_a_lamps_foot_on_every_beat_at_any_tempo(bpm: float) -> None:
    feet = _landings(_ball(), range(2000, 2012), bpm)
    assert all(a != b for a, b in zip(feet, feet[1:], strict=False))  # never twice running
    for start in range(0, 12, 4):  # every lamp once a round
        assert sorted(feet[start : start + 4]) == [0, 1, 2, 3]


def test_the_ball_bounces_height_m_up_between_beats() -> None:
    ball = _ball(height_m=1.5)
    feet = _landings(ball, range(2000, 2009))
    for beat, (here, there) in enumerate(zip(feet, feet[1:], strict=False), start=2000):
        drawn(ball, tempo_ctx(beat + 0.5), ROOM)
        half_way = (FEET[here, 2] + FEET[there, 2]) / 2.0
        np.testing.assert_allclose(ball.particles.pos[0, 2], half_way + 1.5, atol=1e-5)


def test_the_ball_bounces_no_higher_than_the_ceiling() -> None:
    low = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), [(0.5, 3.5, 1.2)], ceiling=1.5)
    ball = _ball(height_m=3.0)
    for beats in np.arange(2000.0, 2012.0, 0.05):
        drawn(ball, tempo_ctx(float(beats)), low)
        assert ball.particles.pos[0, 2] <= 1.5 + 1e-5


def test_the_ball_takes_the_next_colour_at_each_bounce() -> None:
    palette = ["#ff0000", "#00ff00", "#0000ff"]
    ball = _ball(palette=palette)
    for beat in range(2000, 2006):
        drawn(ball, tempo_ctx(beat + 0.25), ROOM)
        np.testing.assert_allclose(ball.particles.colour[0], palette_float(palette)[beat % 3])
```

Create `tests/effects/test_flock.py`:

```python
from __future__ import annotations

import numpy as np
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.flock import Flock
from dj_ledfx.effects.particles import drawn

# Four upright lamps at the corners of a 4 x 4 m room.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _flock(**settings: object) -> Flock:
    flock = Flock(**settings)
    flock.reseed(1)
    return flock


def _spread(flock: Flock, beats: float) -> float:
    """How far the birds are from their middle, on average, at this moment."""
    drawn(flock, tempo_ctx(beats), ROOM)
    pos = flock.particles.pos
    return float(np.linalg.norm(pos - pos.mean(axis=0), axis=1).mean())


def test_the_flock_gathers_round_an_led_of_each_lamp_in_turn() -> None:
    flock = _flock(spread_m=0.2)
    lamps = []
    for bar in range(500, 512, 2):  # it comes to a lamp on every other downbeat
        drawn(flock, tempo_ctx(4.0 * bar), ROOM)
        gaps = np.linalg.norm(flock.particles.pos[:, None, :] - ROOM.pos[None, :, :], axis=2)
        led = int(gaps.max(axis=0).argmin())  # the LED every bird is nearest together
        assert gaps[:, led].max() <= 0.2 + 1e-5
        lamps.append(led // 14)
    assert all(a != b for a, b in zip(lamps, lamps[1:], strict=False))
    assert set(lamps) == {0, 1, 2, 3}


def test_the_flock_scatters_on_every_other_downbeat_and_gathers_again() -> None:
    flock = _flock(scatter=3.0)
    gathered = _spread(flock, 2000.0)  # beat 2000: it has just come to a lamp
    np.testing.assert_allclose(_spread(flock, 2000.75), 3.0 * gathered, rtol=1e-4)
    assert _spread(flock, 2003.0) < 1.5 * gathered  # gathering again by the bar's end
    assert _spread(flock, 2004.75) < 1.2 * gathered  # the bar between: no scatter


def test_the_flock_moves_on_the_beat_at_any_tempo() -> None:
    slow, fast = _flock(), _flock()
    for beats in (2000.0, 2001.3, 2006.9):
        drawn(slow, tempo_ctx(beats, bpm=30.0), ROOM)
        drawn(fast, tempo_ctx(beats, bpm=300.0), ROOM)
        np.testing.assert_array_equal(slow.particles.pos, fast.particles.pos)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/effects/test_twin_comets.py tests/effects/test_bouncing_ball.py tests/effects/test_flock.py -q 2>&1 | tail -4`
Expected: FAIL: three collection errors, `ModuleNotFoundError: No module named 'dj_ledfx.effects.twin_comets'` and the same for `bouncing_ball` and `flock`.

- [ ] **Step 3: Write the three effects, and register them**

Create `src/dj_ledfx/effects/twin_comets.py`:

```python
"""Twin comets' particles (looks.json "comets").

The comets go round the zone's lamps in a loop (their order round its middle, seen from
above), one lamp a beat: each leaves a lamp on the beat, hops through the air to the next
and lands on it, on an LED of it (any of its LEDs, its own each visit), on the next beat.
They start on opposite sides of the loop, so they chase each other round it. Each trails a
tail of fading, shrinking particles where it was over the last tail_beats.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import arc, around, draws, swarm
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

COMET_PALETTE = ("#ff6428", "#28c8ff")
COMETS = 2
HOP = 0.25  # a hop rises this share of the way it goes


class TwinComets(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(COMET_PALETTE), label="Palette"
            ),
            "tail": EffectParam(
                type="int",
                default=8,
                min=0,
                max=30,
                step=1,
                label="Tail",
                description="Particles in each comet's tail",
            ),
            "tail_beats": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=2.0,
                step=0.1,
                label="Tail length",
                description="Beats each tail reaches back",
            ),
            "size": EffectParam(
                type="float",
                default=0.35,
                min=0.1,
                max=1.0,
                step=0.05,
                label="Comet size",
                description="Metres",
            ),
        }

    def at(self, beats: NDArray[np.float64], comet: int, ground: Ground) -> NDArray[np.float64]:
        """Where comet `comet` is at each of these beats."""
        loop = around(ground.lamps.centre, ground.centre)
        start = math.floor(draws(self._seed, [0], 1)[0, 0] * len(loop))
        start += comet * (len(loop) // COMETS)
        beat = np.floor(beats)
        visit = beat.astype(np.int64) + start
        here, there = (
            self._landing(ground, loop, visit, comet),
            self._landing(ground, loop, visit + 1, comet),
        )
        hop = HOP * np.linalg.norm(there - here, axis=1)
        return arc(here, there, ease_in_out(beats - beat), hop)

    def _landing(
        self, ground: Ground, loop: NDArray[np.intp], visit: NDArray[np.int64], comet: int
    ) -> NDArray[np.float64]:
        """Where comet `comet` lands on each visit: on that visit's stop of the loop, on an
        LED of it of the visit's own."""
        spot = draws(self._seed, visit, 1, stream=1 + comet)[:, 0]
        return ground.on(loop[visit % len(loop)], spot)

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        tail = int(values["tail"])
        back = np.arange(tail, -1, -1) / (tail + 1)  # the tail's end first, the head last
        beats = ctx.beats - float(values["tail_beats"]) * back
        glow = ((1.0 - back) ** 2)[:, None].astype(np.float32)
        size = float(values["size"]) * (1.0 - 0.6 * back)
        palette = self._palette
        pos = np.concatenate([self.at(beats, comet, ground) for comet in range(COMETS)])
        colour = np.concatenate([palette[comet % len(palette)] * glow for comet in range(COMETS)])
        return swarm(pos, colour, np.tile(size, COMETS))
```

Create `src/dj_ledfx/effects/bouncing_ball.py`:

```python
"""Bouncing ball's particles (looks.json "ball").

The ball lands on a lamp on every beat, at its foot under one of its LEDs (Ground.foot, any
of its LEDs, its own each beat), and bounces from there to the next lamp of its tour
(particle_tools.tour: every lamp once a round in a shuffled order, never the same lamp twice
in a row), height_m up over the beat, landing on it on the next beat. It takes the palette's
next colour at each bounce.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import arc, draws, swarm, tour
from dj_ledfx.effects.particles import ParamParticles

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

BALL_PALETTE = ("#ff3c50", "#ffd23c", "#3cff8c", "#3c8cff")


class BouncingBall(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(BALL_PALETTE), label="Palette"),
            "height_m": EffectParam(
                type="float",
                default=1.5,
                min=0.3,
                max=3.0,
                step=0.1,
                label="Bounce",
                description="Metres the ball bounces",
                bindable=True,
            ),
            "size": EffectParam(
                type="float",
                default=0.5,
                min=0.1,
                max=1.5,
                step=0.05,
                label="Ball size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        beat = math.floor(ctx.beats)
        stops = [tour(self._seed, 0, bounce, ground.lamps.count) for bounce in (beat, beat + 1)]
        here, there = ground.foot(stops, draws(self._seed, [beat, beat + 1], 1, stream=1)[:, 0])
        room = ground.ceiling - max(float(here[2]), float(there[2]))  # under the ceiling
        height = max(min(float(values["height_m"]), room), 0.0)
        where = arc(here, there, [ctx.beats - beat], height)
        palette = self._palette
        return swarm(where, palette[beat % len(palette)], float(values["size"]))
```

Create `src/dj_ledfx/effects/flock.py`:

```python
"""Flock's particles (looks.json "flock").

The flock flies from lamp to lamp on a tour (particle_tools.tour), MOVE_BARS bars from one
to the next, easing in and out, so it gathers on each lamp in turn, round an LED of it (any
of its LEDs, its own each visit). Each bird keeps its own place in the flock, within
spread_m of its middle, and the whole flock turns about its middle once every SWIRL_BARS
bars. On the downbeat of every other bar, as the flock comes to a lamp, the birds burst out
to `scatter` times their places and gather again over the next few beats.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import draws, swarm, tour
from dj_ledfx.effects.particles import ParamParticles
from dj_ledfx.tempo.model import BEATS_PER_BAR

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.particle_tools import Ground, Particles

FLOCK_PALETTE = ("#fff0c8", "#ffb464", "#ff6482")
MOVE_BARS = 2  # the flock takes this many bars from one lamp to the next
SWIRL_BARS = 2.0  # it turns once in this many bars
SCATTER_BEATS = 0.75  # a scatter is widest this many beats after its downbeat
FLAT = 0.5  # a flock is this much flatter than it is wide


def scattered(since: float, scatter: float) -> float:
    """How far out the birds are, as a share of their places, `since` beats after the
    downbeat that scatters them: out to `scatter` at SCATTER_BEATS, then back."""
    rise = since / SCATTER_BEATS
    return 1.0 + (scatter - 1.0) * rise * math.exp(1.0 - rise)


class Flock(ParamParticles):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(
                type="color_list", default=list(FLOCK_PALETTE), label="Palette"
            ),
            "count": EffectParam(type="int", default=40, min=5, max=200, step=5, label="Birds"),
            "spread_m": EffectParam(
                type="float",
                default=0.8,
                min=0.2,
                max=3.0,
                step=0.1,
                label="Spread",
                description="Metres from the flock's middle",
            ),
            "scatter": EffectParam(
                type="float",
                default=3.0,
                min=1.0,
                max=8.0,
                step=0.5,
                label="Scatter",
                description="How far the flock scatters, times its spread",
            ),
            "size": EffectParam(
                type="float",
                default=0.2,
                min=0.05,
                max=0.6,
                step=0.05,
                label="Bird size",
                description="Metres",
            ),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        values = self._values
        lamps = ground.lamps
        trips = ctx.beats / (BEATS_PER_BAR * MOVE_BARS)
        trip = math.floor(trips)
        stops = [tour(self._seed, 0, visit, lamps.count) for visit in (trip, trip + 1)]
        here, there = ground.on(stops, draws(self._seed, [trip, trip + 1], 1, stream=1)[:, 0])
        middle = here + (there - here) * ease_in_out(trips - trip)
        u = draws(self._seed, np.arange(int(values["count"])), 4)
        up = 2.0 * u[:, 0] - 1.0
        flat = np.sqrt(1.0 - up * up)
        heading = 2.0 * math.pi * u[:, 1] + 2.0 * math.pi * ctx.beats / (
            BEATS_PER_BAR * SWIRL_BARS
        )
        reach = float(values["spread_m"]) * np.cbrt(u[:, 2])  # spread evenly through a ball
        since = (trips - trip) * BEATS_PER_BAR * MOVE_BARS  # beats since it came to a lamp
        out = reach * scattered(since, float(values["scatter"]))
        pos = middle + np.stack(
            [out * flat * np.cos(heading), out * flat * np.sin(heading), FLAT * out * up], axis=1
        )
        return swarm(pos, palette_at(self._palette, u[:, 3]), float(values["size"]))
```

In `src/dj_ledfx/effects/__init__.py`:

```diff
--- a/src/dj_ledfx/effects/__init__.py
+++ b/src/dj_ledfx/effects/__init__.py
@@ -1,6 +1,7 @@
 from dj_ledfx.effects import aurora_curtains as _aurora_curtains  # noqa: F401
 from dj_ledfx.effects import beat_bursts as _beat_bursts  # noqa: F401
 from dj_ledfx.effects import beat_pulse as _beat_pulse  # noqa: F401
+from dj_ledfx.effects import bouncing_ball as _bouncing_ball  # noqa: F401
 from dj_ledfx.effects import breathe as _breathe  # noqa: F401
 from dj_ledfx.effects import checker_cubes as _checker_cubes  # noqa: F401
 from dj_ledfx.effects import color_carousel as _color_carousel  # noqa: F401
@@ -10,6 +11,7 @@ from dj_ledfx.effects import fire_storm as _fire_storm  # noqa: F401
 from dj_ledfx.effects import fireflies as _fireflies  # noqa: F401
 from dj_ledfx.effects import firmware_lifx as _firmware_lifx  # noqa: F401
 from dj_ledfx.effects import firmware_openrgb as _firmware_openrgb  # noqa: F401
+from dj_ledfx.effects import flock as _flock  # noqa: F401
 from dj_ledfx.effects import focus_field as _focus_field  # noqa: F401
 from dj_ledfx.effects import fountain as _fountain  # noqa: F401
 from dj_ledfx.effects import lava_plasma as _lava_plasma  # noqa: F401
@@ -24,4 +26,5 @@ from dj_ledfx.effects import speaker_waves as _speaker_waves  # noqa: F401
 from dj_ledfx.effects import spotlights as _spotlights  # noqa: F401
 from dj_ledfx.effects import strobe as _strobe  # noqa: F401
 from dj_ledfx.effects import sunset_gradient as _sunset_gradient  # noqa: F401
+from dj_ledfx.effects import twin_comets as _twin_comets  # noqa: F401
 from dj_ledfx.effects import vortex as _vortex  # noqa: F401
```

- [ ] **Step 4: Run them to see them pass, and the sweep with them**

Run: `uv run pytest tests/effects/test_twin_comets.py tests/effects/test_bouncing_ball.py tests/effects/test_flock.py tests/effects/test_particle_effects.py -q 2>&1 | tail -1 && uv run pytest tests/effects/test_particle_effects.py -m perf -q 2>&1 | tail -1`
Expected: PASS (`102 passed, 11 deselected`: the sweep over all eleven), then `11 passed, 88 deselected`.

- [ ] **Step 5: Run the gate**

```bash
uv run ruff format src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/twin_comets.py src/dj_ledfx/effects/bouncing_ball.py src/dj_ledfx/effects/flock.py tests/effects/test_twin_comets.py tests/effects/test_bouncing_ball.py tests/effects/test_flock.py
uv run ruff check --fix src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/twin_comets.py src/dj_ledfx/effects/bouncing_ball.py src/dj_ledfx/effects/flock.py tests/effects/test_twin_comets.py tests/effects/test_bouncing_ball.py tests/effects/test_flock.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `All checks passed!`, `367 files already formatted`, mypy's 16 errors (`checked 166 source files`), `2207 passed, 1 skipped, 54 deselected` and `54 passed` in the perf run.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/__init__.py src/dj_ledfx/effects/twin_comets.py src/dj_ledfx/effects/bouncing_ball.py src/dj_ledfx/effects/flock.py tests/effects/test_twin_comets.py tests/effects/test_bouncing_ball.py tests/effects/test_flock.py
git commit -m "feat(effects): the twin_comets, bouncing_ball and flock particle effects, which travel the lamps on the beat"
```

---


### Task 8: The eleven particle looks as built-ins

The built-ins gain the eleven particle looks (ruling 12), in `looks.json`'s order among the others, so the API serves them, every zone can start one, and the built-ins' sweep (spec §9's "every look stays finite and in range … and repeats exactly with a fixed seed") takes them. Each has one particle layer, id `particles`, named as `looks.json` names the look; the embers also have a firmware layer, Flame, on the lights Aurora's Morph layer picks (`type:candle` and `type:tube`), which the embers' description names; and `bursts` and `fountain` take the anchors their descriptions name. A twin of each draws what its zone draws (Review Focus 3), and a particle look mid-transition from another stays within the budget.

**Files:**
- Modify: `src/dj_ledfx/looks/builtin.py`, `tests/looks/test_builtin.py`, `tests/web/test_looks_api.py`, `tests/web/test_zones_api.py`, `tests/zones/test_runtime_particles.py`, `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: the eleven effect kinds of Tasks 4–7; Task 3's `streamed_layers()` and `make_effect()`; Task 2's `ParticleEffect` and `drawn()`; `handoff_looks()`, `_firmware()`, `_anchor_of()` and `seed_home()` (`looks/builtin.py`, as they are); Task 4's `upright()`; Task 3's `placed_light()`, `runtime_of()` and `latest()` from `tests/runtime_fakes.py`; `builtin_look()` (`tests/conftest.py`); `_heavy()` and `tick_times()` (`tests/zones/test_runtime_perf.py`).
- Produces:
  - `looks.builtin._particles(look_id: str, kind: str, **settings: Any) -> Layer`: a particle look's one particle layer, id `particles`, named from `handoff_looks()[look_id]["name"]`.
  - The built-ins `fireflies` (kind `fireflies`), `embers` (`embers`, and the firmware layer `flame`, `lifx_flame` on `type:candle` and `type:tube`), `rain` (`rain_storm`), `snow` (`snowfall`), `spotlights` (`spotlights`), `bursts` (`beat_bursts`, with the anchor its description names), `vortex` (`vortex`), `comets` (`twin_comets`), `fountain` (`fountain`, with the anchor its description names), `flock` (`flock`) and `ball` (`bouncing_ball`), in `looks.json`'s order among the handoff's other built-ins.

- [ ] **Step 1: Write the failing tests**

In `tests/looks/test_builtin.py`, the handoff's built-ins now include the particle looks, each with its particle layer, and the built-ins' sweep draws particle layers:

```diff
--- a/tests/looks/test_builtin.py
+++ b/tests/looks/test_builtin.py
@@ -10,6 +10,7 @@ from map_home import DESIGN, handoff_pins, seeded_ledset, tiny_home

 from dj_ledfx.effects.aurora_curtains import AURORA_PALETTE
 from dj_ledfx.effects.firmware import FirmwareEffect
+from dj_ledfx.effects.particles import ParticleEffect, drawn
 from dj_ledfx.effects.registry import get_strip_effect_classes
 from dj_ledfx.home.model import Home
 from dj_ledfx.home.seed import seed_home
@@ -27,6 +28,7 @@ from dj_ledfx.looks.model import (
     Look,
     firmware_layers,
     make_effect,
+    streamed_layers,
     validate_look,
     visible_field_layers,
 )
@@ -34,11 +36,28 @@ from dj_ledfx.looks.selectors import Selector
 from dj_ledfx.types import FloatRGB

 VENDORED = files("dj_ledfx.looks") / "data" / "looks.json"
-SHOWCASE = [
-    *("sunset", "aurora", "lava", "carousel", "ripples", "focus"),  # M2
-    *("shockwave", "scanner", "checker", "speakers"),  # M3
-    FIRMWARE_LOOK_ID,
+M2 = ("sunset", "aurora", "lava", "carousel", "ripples", "focus")
+M3 = ("shockwave", "scanner", "checker", "speakers")
+M5 = ("fireflies", "embers", "rain", "snow", "spotlights")  # ambient
+M5_TEMPO = ("bursts", "vortex", "comets", "fountain", "flock", "ball")
+SHOWCASE = [  # in looks.json's order
+    look_id
+    for look_id in handoff_looks()
+    if look_id in {*M2, *M3, *M5, *M5_TEMPO, FIRMWARE_LOOK_ID}
 ]
+PARTICLE_KINDS = {
+    "fireflies": "fireflies",
+    "embers": "embers",
+    "rain": "rain_storm",
+    "snow": "snowfall",
+    "spotlights": "spotlights",
+    "bursts": "beat_bursts",
+    "vortex": "vortex",
+    "comets": "twin_comets",
+    "fountain": "fountain",
+    "flock": "flock",
+    "ball": "bouncing_ball",
+}


 def test_vendored_looks_json_is_a_byte_copy_of_the_handoff() -> None:
@@ -53,7 +72,7 @@ def test_the_handoff_looks_come_first_in_its_order_with_its_metadata() -> None:
     looks = builtin_looks()[: len(SHOWCASE)]

     assert [look.id for look in looks] == SHOWCASE
-    assert SHOWCASE == [look_id for look_id in handoff if look_id in SHOWCASE]  # looks.json order
+    assert len(SHOWCASE) == len(M2) + len(M3) + len(M5) + len(M5_TEMPO) + 1
     for look in looks:
         entry = handoff[look.id]
         assert (look.name, look.category, look.description) == (
@@ -91,11 +110,28 @@ def test_each_showcase_look_has_its_fields_and_firmware() -> None:
     assert aurora_morph.settings == {"palette": list(AURORA_PALETTE)}  # the curtains' palette


-@pytest.mark.parametrize("look_id", ["focus", "shockwave", "speakers"])
+def test_each_particle_look_has_its_particle_layer_named_after_it() -> None:
+    for look_id, kind in PARTICLE_KINDS.items():
+        look = builtin_look(look_id)
+        particles = look.layers[0]
+        assert (particles.type, particles.kind) == ("particles", kind)
+        assert particles.name == handoff_looks()[look_id]["name"]
+        assert isinstance(make_effect(particles), ParticleEffect)
+        assert [layer.type for layer in look.layers[1:]] == (
+            ["firmware"] if look_id == "embers" else []
+        )
+    flame = builtin_look("embers").layers[1]
+    assert flame.kind == "lifx_flame"
+    assert flame.lights == (Selector("type", "candle"), Selector("type", "tube"))
+    assert {look.category for look in map(builtin_look, M5)} == {"ambient"}
+    assert {look.needs for look in map(builtin_look, M5_TEMPO)} == {("tempo",)}
+
+
+@pytest.mark.parametrize("look_id", ["focus", "shockwave", "speakers", "bursts", "fountain"])
 def test_anchored_looks_start_from_the_anchor_their_description_names(look_id: str) -> None:
     look = builtin_look(look_id)

-    [anchor_id] = {layer.settings["anchor"] for layer in visible_field_layers(look)}
+    [anchor_id] = {layer.settings["anchor"] for layer in streamed_layers(look)}
     anchor = seed_home().anchor(anchor_id)

     assert anchor is not None
@@ -168,9 +204,7 @@ def test_ids_are_unique_and_every_builtin_validates() -> None:
 def _frames(look: Look, seed: int) -> list[FloatRGB]:
     """Render every streamed layer, and every firmware layer's copy, for 3 s on this home."""
     leds = seeded_ledset()
-    effects = [
-        make_effect(layer) for layer in [*visible_field_layers(look), *firmware_layers(look)]
-    ]
+    effects = [make_effect(layer) for layer in [*streamed_layers(look), *firmware_layers(look)]]
     for effect in effects:
         effect.reseed(seed)
     frames: list[FloatRGB] = []
@@ -179,6 +213,8 @@ def _frames(look: Look, seed: int) -> list[FloatRGB]:
         for effect in effects:
             if isinstance(effect, FirmwareEffect):
                 frames.append(effect.emulate(ctx, leds))
+            elif isinstance(effect, ParticleEffect):
+                frames.append(drawn(effect, ctx, leds))
             else:
                 frames.append(effect.render(ctx, leds))
     return frames
```

In `tests/web/test_looks_api.py`, the API serves them in `looks.json`'s order, each with its settings:

```diff
--- a/tests/web/test_looks_api.py
+++ b/tests/web/test_looks_api.py
@@ -15,12 +15,23 @@ from tests.web.conftest import raw_json

 BUILT_INS = [
     "sunset",
+    "fireflies",
+    "embers",
+    "rain",
+    "snow",
     "aurora",
     "lava",
     "carousel",
     "ripples",
     "focus",
+    "spotlights",
+    "bursts",
     "shockwave",
+    "vortex",
+    "comets",
+    "fountain",
+    "flock",
+    "ball",
     "scanner",
     "checker",
     "speakers",
@@ -90,6 +101,19 @@ async def test_looks_come_built_in_first_in_the_contract_shape(api: Api) -> None
     }


+async def test_a_particle_look_comes_with_its_layer_and_its_settings(api: Api) -> None:
+    looks = (await api.client.get("/api/looks")).json()
+
+    ball = looks[BUILT_INS.index("ball")]
+    [layer] = ball["layers"]
+    assert (layer["type"], layer["kind"], layer["name"]) == (
+        "particles",
+        "bouncing_ball",
+        ball["name"],
+    )
+    assert [entry["key"] for entry in layer["schema"]] == ["palette", "height_m", "size"]
+
+
 async def test_a_look_is_saved_as_new_changed_and_deleted(api: Api) -> None:
     draft = (await api.client.get("/api/looks/classic-breathe")).json()
     draft["name"] = "Dim breathe"
```

In `tests/web/test_zones_api.py`, one starts on a zone as any look does:

```diff
--- a/tests/web/test_zones_api.py
+++ b/tests/web/test_zones_api.py
@@ -12,6 +12,7 @@ from api_home import Api, api_home
 from conftest import FakeLight

 from dj_ledfx.devices.lights import LightIndex
+from dj_ledfx.looks.builtin import handoff_looks
 from dj_ledfx.web.contract import running_zone_out
 from dj_ledfx.zones.model import RunningZoneInfo, ZoneRecord
 from tests.web.conftest import raw_json
@@ -79,6 +80,15 @@ async def test_a_start_answers_the_running_zone_and_its_take_overs(api: Api) ->
     assert running["overlays"] == []


+async def test_a_particle_look_starts_on_a_zone_like_any_other(api: Api) -> None:
+    resp = await api.client.post("/api/zones/desk/start", json={"lookId": "ball"})
+
+    assert resp.status_code == 200
+    started = resp.json()
+    assert started["lookName"] == handoff_looks()["ball"]["name"]
+    assert (started["state"], started["lights"], started["error"]) == ("running", ["a", "b"], None)
+
+
 async def test_a_draft_look_runs_without_being_saved(api: Api) -> None:
     draft = (await api.client.get("/api/looks/classic-breathe")).json()
     draft["id"] = ""
```

In `tests/zones/test_runtime_particles.py`, a twin of each draws what its zone draws, on four lamps at a room's corners:

```diff
--- a/tests/zones/test_runtime_particles.py
+++ b/tests/zones/test_runtime_particles.py
@@ -2,6 +2,8 @@ from __future__ import annotations

 import numpy as np
 import pytest
+from conftest import builtin_look
+from map_home import upright
 from runtime_fakes import (
     FlatField,
     dot_layer,
@@ -20,6 +22,24 @@ pytestmark = pytest.mark.usefixtures("_fields")

 # One light of 9 LEDs, 0.5 m apart along x from 0 to 4 m, 1 m up.
 ROW_LIGHT = placed_light("row", *[(0.5 * i, 0.0, 1.0) for i in range(9)])
+# Lamps a-d: four upright lamps at the corners of a 4 x 4 m room.
+CORNERS = [
+    placed_light(f"lamp-{name}", *[(x, y, z) for x, y, z in upright(x, y)])
+    for name, (x, y) in zip("abcd", [(0.5, 0.5), (3.5, 0.5), (3.5, 3.5), (0.5, 3.5)], strict=True)
+]
+PARTICLE_LOOKS = [
+    "fireflies",
+    "embers",
+    "rain",
+    "snow",
+    "spotlights",
+    "bursts",
+    "vortex",
+    "comets",
+    "fountain",
+    "flock",
+    "ball",
+]


 def _lit(runtime: ZoneRuntime) -> list[int]:
@@ -78,3 +98,23 @@ def test_a_light_a_firmware_layer_cannot_run_shows_the_particle_layer() -> None:
     runtime = runtime_of(look_of(dot_layer(x=2.0), glow_layer()), [ROW_LIGHT])
     assert runtime.mode_of("row") == "streaming"  # a lamp can't run Glow: the dots play
     assert runtime.field_effect is None  # no classic effect to tune
+
+
+# Two beats at the internal clock's 120 BPM, a twelfth of a beat apart, then a jump ahead:
+# whatever phase the clock is at, some frame falls near a landing (a lone ball is dark while
+# it flies between two lamps).
+MOMENTS = [1000.0 + k / 24 for k in range(24)] + [1003.25]
+
+
+@pytest.mark.parametrize("look_id", PARTICLE_LOOKS)
+def test_a_twin_of_a_particle_look_draws_what_its_runtime_draws(look_id: str) -> None:
+    original = runtime_of(builtin_look(look_id), CORNERS)
+    twin = original.twin()
+
+    lit = False
+    for moment in MOMENTS:
+        original.tick(moment)
+        twin.tick(moment)
+        np.testing.assert_array_equal(latest(twin), latest(original))
+        lit = lit or bool(latest(original).any())
+    assert lit  # on the lamps
```

In `tests/zones/test_runtime_perf.py`, two of the heaviest particle looks mid-transition, with every modifier on:

```diff
--- a/tests/zones/test_runtime_perf.py
+++ b/tests/zones/test_runtime_perf.py
@@ -132,6 +132,19 @@ def test_a_zone_frame_mid_transition_renders_in_under_5_ms(kind: TransitionKind)
     assert new.fps_actual >= 59  # it never dropped to a lower frame rate


+# M5: particle looks count against the same budget mid-transition: two of the heaviest,
+# every modifier on, 4 s into the longest transition.
+def test_a_particle_look_mid_transition_from_another_renders_in_under_5_ms() -> None:
+    old, new = _heavy("rain"), _heavy("fountain")
+    new.begin_transition(Transition(kind="dissolve", duration_s=MAX_TRANSITION_S), [old])
+
+    durations = tick_times(new)
+
+    assert new.state == "transition"
+    assert statistics.median(durations) < FRAME_BUDGET_S
+    assert new.fps_actual >= 59
+
+
 # The most a zone renders at once: a start while its transition plays mixes three looks.
 def test_three_looks_mid_transition_render_in_under_5_ms() -> None:
     first, second, third = _heavy("aurora"), _heavy("lava"), _heavy("focus")
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/looks/test_builtin.py tests/web/test_looks_api.py tests/web/test_zones_api.py tests/zones/test_runtime_particles.py -q 2>&1 | tail -1 && uv run pytest tests/zones/test_runtime_perf.py -m perf -q -k particle 2>&1 | tail -1`
Expected: FAIL: `41 failed, 55 passed`, then `1 failed`. The particle looks aren't built-ins yet: `builtin_look()` raises `StopIteration` for each, the built-ins and the API's looks come without them, and starting `ball` answers 404.

- [ ] **Step 3: Add the particle looks to the built-ins**

In `src/dj_ledfx/looks/builtin.py`:

```diff
--- a/src/dj_ledfx/looks/builtin.py
+++ b/src/dj_ledfx/looks/builtin.py
@@ -1,8 +1,9 @@
 """Built-in looks (spec §5.2).

 The handoff's looks take their metadata from its looks.json (vendored in data/looks.json,
-byte for byte), in its order: M2's six showcase looks, M3's four tempo looks and the
-Firmware showcase. The handoff has no layers, so they live here. The six classic looks
+byte for byte), in its order: M2's six showcase looks, M3's four tempo looks, M5's eleven
+particle looks and the Firmware showcase. The handoff has no layers, so they live here; a
+particle look's one particle layer takes the look's own name. The six classic looks
 are today's effects; the handoff has no entry for them, so their names and descriptions
 live here too.
 """
@@ -69,6 +70,12 @@ def _field(
     return Layer(id=layer_id, name=name, type="field", kind=kind, blend=blend, settings=settings)


+def _particles(look_id: str, kind: str, **settings: Any) -> Layer:
+    """The particle layer of a particle look, named as looks.json names the look."""
+    name = str(handoff_looks()[look_id]["name"])
+    return Layer(id="particles", name=name, type="particles", kind=kind, settings=settings)
+
+
 def _anchor_of(look_id: str, anchors: Sequence[Anchor]) -> str:
     """The anchor the look's looks.json description names, among the seeded map's."""
     return anchor_named_in(handoff_looks()[look_id]["description"], anchors)
@@ -92,6 +99,7 @@ def _handoff_layers() -> Mapping[str, tuple[Layer, ...]]:
     anchors = seed_home().anchors
     tv, speakers = _anchor_of("shockwave", anchors), _anchor_of("speakers", anchors)
     focus = _anchor_of("focus", anchors)
+    bursts, fountain = _anchor_of("bursts", anchors), _anchor_of("fountain", anchors)
     return {
         "sunset": (
             _field("sky", "Gradient", "sunset_gradient"),
@@ -107,14 +115,28 @@ def _handoff_layers() -> Mapping[str, tuple[Layer, ...]]:
                 palette=list(AURORA_PALETTE),
             ),
         ),
+        "fireflies": (_particles("fireflies", "fireflies"),),
+        "embers": (
+            _particles("embers", "embers"),
+            _firmware("flame", "Flame", "lifx_flame", lights=["type:candle", "type:tube"]),
+        ),
+        "rain": (_particles("rain", "rain_storm"),),
+        "snow": (_particles("snow", "snowfall"),),
         "lava": (_field("plasma", "Plasma", "lava_plasma"),),
         "carousel": (_field("carousel", "Carousel", "color_carousel"),),
         "ripples": (_field("ripples", "Ripples", "ripples"),),
         "focus": (_field("focus", "Focus", "focus_field", anchor=focus),),
+        "spotlights": (_particles("spotlights", "spotlights"),),
+        "bursts": (_particles("bursts", "beat_bursts", anchor=bursts),),
         "shockwave": (
             _field("shell", "Shockwave", "shockwave_shell", anchor=tv),
             _field("beam", "Beam", "lighthouse_beam", blend="add", anchor=tv),
         ),
+        "vortex": (_particles("vortex", "vortex"),),
+        "comets": (_particles("comets", "twin_comets"),),
+        "fountain": (_particles("fountain", "fountain", anchor=fountain),),
+        "flock": (_particles("flock", "flock"),),
+        "ball": (_particles("ball", "bouncing_ball"),),
         "scanner": (_field("plane", "Plane", "scanner_plane"),),
         "checker": (_field("cubes", "Cubes", "checker_cubes"),),
         "speakers": (_field("waves", "Waves", "speaker_waves", anchor=speakers),),
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/looks/test_builtin.py tests/web/test_looks_api.py tests/web/test_zones_api.py tests/zones/test_runtime_particles.py -q 2>&1 | tail -1 && uv run pytest tests/zones/test_runtime_perf.py -m perf -q -k particle 2>&1 | tail -1`
Expected: PASS (`107 passed`), then `1 passed, 63 deselected`. The warnings are FastAPI's `on_event` deprecation.

- [ ] **Step 5: Run the gate, and check the API didn't change**

```bash
uv run ruff format src/dj_ledfx/looks/builtin.py tests/looks/test_builtin.py tests/web/test_looks_api.py tests/web/test_zones_api.py tests/zones/test_runtime_particles.py tests/zones/test_runtime_perf.py
uv run ruff check --fix src/dj_ledfx/looks/builtin.py tests/looks/test_builtin.py tests/web/test_looks_api.py tests/web/test_zones_api.py tests/zones/test_runtime_particles.py tests/zones/test_runtime_perf.py
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm run api:check 2>&1 | tail -1)
```

Expected: `All checks passed!`, `367 files already formatted`, mypy's 16 errors, `2234 passed, 1 skipped, 77 deselected` (8 more warnings: the two new web tests', 4 each), `77 passed` in the perf run and `api types match`. The perf run grows by 23: the new mid-transition test, and the eleven particle looks plain and with every modifier, which the perf tests that cover every built-in now take in.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/looks/builtin.py tests/looks/test_builtin.py tests/web/test_looks_api.py tests/web/test_zones_api.py tests/zones/test_runtime_particles.py tests/zones/test_runtime_perf.py
git commit -m "feat(looks): the eleven particle looks as built-ins, in looks.json's order"
```

---


### Task 9: Check it on this home

Two checks, in order, as M4's Task 10 ran them (spec §9: "a short checklist run on the real lights; preview-only mode allows a dry run first"). The dry run starts the branch on a snapshot of the deployed app's `state.db` with no light backend (no Govee, LIFX or OpenRGB), so the home's real lights are offline ghosts and nothing reaches one, and the branch opens no Govee transport: the deployed app keeps UDP 4002 to itself, as it must, since two apps there would split the Govee lamps' replies between them. Pro DJ Link listens on a loopback port, so the deployed app keeps UDP 50001 too. The dry run rehearses the deploy (the first start on real data: the running zones resume), previews every particle look on the room with the most lights and on the whole home, previews one with every modifier, and plays particle looks in and out of transitions with preview-only on. The second check puts the looks on the real lights with the owner watching. Every step that touches the deployed container or the lights waits for the owner's go, one step at a time.

Report only counts and yes/no results, in the PR and anywhere else: no light ids (they hold MACs), no addresses, no model names, no room names and never the home's location. The scripts print counts, yes or no, and what the API says of a built-in look; they never print a light's or a room's name.

The branch serves on a port of its own, since the deployed app holds 8080 and 8081 belongs to another service. Each shell this task opens starts from the same two values, set once in a file:

```bash
printf 'PORT=8098\nW=/home/anirudhlath/code/.worktrees/dj-ledfx/m5-particles\n' > /tmp/m5-live.env
. /tmp/m5-live.env && ss -ltn | grep -c ":$PORT "
```

Expected: `0`, the port is free. Every block below starts with `. /tmp/m5-live.env`.

If the dry run stops answering, or is still running 15 s after a Ctrl-C (`kill -INT`), run `kill -USR1 "$(pgrep -P "$(cat /tmp/m5-dry/pid)")"` first (the Python process `uv run` started: its driver then writes every thread's stack into its log), then `kill -9` the same process, and tell the owner. Don't look it up with `pgrep -f /tmp/m5-dry/run.py`: that also matches the shell running the command, whose command line holds the same text.

**Files:**
- Create (outside the repo): `/tmp/m5-live.env`, `/tmp/m5-dry/run.py`, `/tmp/m5-wait.py`, `/tmp/m5-probe.py`, `/tmp/m5-show.py`

- [ ] **Step 1: Snapshot the deployed state (read-only), with the owner's go**

Ask the owner first: this runs one read-only process in the deployed container, which changes nothing there and touches no light. Go on only with a go.

```bash
. /tmp/m5-live.env && cd "$W"
mkdir -p /tmp/m5-dry && rm -f /tmp/m5-dry/state.db
docker exec dj-ledfx-app-1 python -c "import sqlite3, sys; db = sqlite3.connect('file:/app/state/state.db?mode=ro', uri=True); sys.stdout.write('\n'.join(db.iterdump()))" > /tmp/m5-dry/dump.sql
uv run python -c "import sqlite3; db = sqlite3.connect('/tmp/m5-dry/state.db'); db.executescript(open('/tmp/m5-dry/dump.sql').read()); db.close()"
uv run python -c "import sqlite3; db = sqlite3.connect('/tmp/m5-dry/state.db'); print(db.execute('select count(*) from devices').fetchone(), db.execute('select count(*) from zone_assignments').fetchone())"
curl -s http://127.0.0.1:8080/api/running | uv run python -c "import json, sys; print(len(json.load(sys.stdin)['zones']), 'zones running')"
```

Expected: the device count the deployed app knows, and as many zone assignments as it has zones running.

- [ ] **Step 2: Write the scripts**

`/tmp/m5-dry/run.py`, the real entry point with no light backend. Each backend opens its own transport (the Govee one binds UDP 4002), and the app makes them only from this registry, so with it empty nothing is discovered or reached:

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

`/tmp/m5-wait.py`, which waits for an app to answer or for a process to end, so no shell loop has to sleep:

```python
"""Wait for an app: `m5-wait.py URL SECONDS` until the URL answers, `m5-wait.py --gone PID
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

`/tmp/m5-probe.py`, which previews (a preview never reaches a light) and plays transitions with preview-only on:

```python
"""M5 probe: every particle look on previews of the room with the most lights and of the
whole home, one with every modifier, and particle looks in and out of transitions with
preview-only on. Nothing reaches a light. It prints counts and yes or no: no ids of lights,
names or addresses."""

import asyncio
import copy
import json
import struct
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

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


async def listen(ws: ClientConnection, seconds: float) -> Frames:
    """The preview frames on the socket for a while."""
    frames: Frames = {}
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        try:
            message = await asyncio.wait_for(ws.recv(), left)
        except TimeoutError:
            break
        if isinstance(message, bytes) and message[0] == 0x02:  # protocol 2's preview stream
            (id_len,) = struct.unpack_from("<H", message, 1)
            light_id = message[3 : 3 + id_len].decode()
            frames.setdefault(light_id, []).append(message[3 + id_len + 4 :])
    return frames


async def answer(ws: ClientConnection, command_id: str) -> dict[str, Any]:
    async with asyncio.timeout(5):
        while True:
            message = await ws.recv()
            if isinstance(message, str) and json.loads(message).get("id") == command_id:
                return json.loads(message)


async def preview(ws: ClientConnection, zone_id: str, look: str | dict[str, Any]) -> Frames:
    """A look's preview frames over 2 s: a look by its id, or a draft."""
    body = {"zoneId": zone_id, **({"lookId": look} if isinstance(look, str) else {"look": look})}
    started = ok("POST", "/preview", body)
    await listen(ws, 0.3)  # the last preview's frames still on their way
    frames = await listen(ws, 2.0)
    ok("DELETE", f"/preview/{started['previewId']}")
    return frames


def lit_leds(payload: bytes) -> int:
    return sum(max(payload[k : k + 3]) > LIT for k in range(0, len(payload), 3))


def lit_lights(frames: Frames) -> int:
    return sum(any(lit_leds(payload) for payload in payloads) for payloads in frames.values())


def brightest(frames: Frames) -> int:
    return max((max(payload, default=0) for p in frames.values() for payload in p), default=0)


def moving(frames: Frames) -> int:
    return sum(len(set(payloads)) > 10 for payloads in frames.values())


def drafted(look: dict[str, Any], modifiers: dict[str, Any], **layer: Any) -> dict[str, Any]:
    """The look as an unsaved draft: the layer modifiers on each streamed layer (a firmware
    layer takes none), and the look modifiers given."""
    draft = copy.deepcopy(look)
    for each in draft["layers"]:
        if each["type"] != "firmware":
            each.update(layer)
    draft["modifiers"] = {**draft["modifiers"], **modifiers}
    return draft


async def main() -> None:
    resumed = ok("GET", "/running")["zones"]
    print(f"zones resumed at start: {len(resumed)}")
    zones = ok("GET", "/zones")
    room = max((z for z in zones if z["kind"] == "room"), key=lambda z: len(z["lights"]))
    home = next(z for z in zones if z["kind"] == "home")
    print(f"the room with the most lights: {len(room['lights'])}; the whole home: {len(home['lights'])}")
    looks = [
        look
        for look in ok("GET", "/looks")
        if look["builtIn"] and any(layer["type"] == "particles" for layer in look["layers"])
    ]
    print(f"particle looks: {len(looks)}")

    # One socket for the whole run, closed once at the end, as M3's and M4's probes kept it.
    async with connect(BASE.replace("http", "ws", 1) + "/ws", max_size=None, max_queue=None) as ws:
        await ws.send(json.dumps(
            {"action": "subscribe_frames", "id": "frames", "fps": 60, "protocol": 2, "streams": ["preview"]}
        ))
        await answer(ws, "frames")

        for look in looks:
            here = await preview(ws, room["id"], look["id"])
            everywhere = await preview(ws, home["id"], look["id"])
            print(
                f"{look['id']}: the room {lit_lights(here)} of {len(room['lights'])} lights lit,"
                f" {moving(here)} moving, brightest {brightest(here)}"
                f" | the whole home {lit_lights(everywhere)} of {len(home['lights'])} lit"
            )

        comets = next(look for look in looks if look["id"] == "comets")
        every = drafted(
            comets,
            {"trailsS": 1.0, "downbeatFlash": True, "brightnessCap": 0.8, "evening": True},
            mask={"kind": "height", "range": [0.3, 2.0]},
            mirror={"axis": "x", "at": None},
            transform={"offset": [0.5, 0.0, 0.0], "rotateDeg": 30.0, "scale": 1.5},
        )
        busy = await preview(ws, room["id"], every)
        print(f"comets with every modifier: {lit_lights(busy)} lights lit, brightest {brightest(busy)}")

        was_preview_only = ok("GET", "/config")["engine"].get("preview_only") is True
        ok("PUT", "/config", {"engine": {"preview_only": True}})
        ok("POST", f"/zones/{room['id']}/start", {"lookId": "lava"})
        await listen(ws, 1.0)
        for kind, look_id in (("dissolve", "fireflies"), ("fade", "ball"), ("wipe", "rain"), ("spread", "lava")):
            status, started = start(room["id"], look_id, {"kind": kind, "durationS": 2})
            await listen(ws, 2.5)
            after = running(room["id"]) or {}
            print(
                f"a 2 s {kind} to {look_id}: plays {status == 200 and started['state'] == 'transition'},"
                f" then runs {after.get('state') == 'running' and after.get('lookId') == look_id},"
                f" no error {after.get('error') is None}"
            )
        status, _ = call("POST", "/running/stop-all")
        print(f"Stop all: {status}, nothing running: {ok('GET', '/running')['zones'] == []}")
        ok("PUT", "/config", {"engine": {"preview_only": was_preview_only}})


asyncio.run(main())
```

`/tmp/m5-show.py`, for Step 5, one step on the real lights at a time. A look's step prints its name and its `looks.json` description as the API serves them, so the owner can judge the lights against the description:

```python
"""M5 on the real lights, one step at a time: `m5-show.py BASE STEP`. Each step starts a
look on the room with the most lights (or the whole home), says what it is, and leaves it
running. It prints counts and yes or no only: no ids of lights, names or addresses."""

import copy
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

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


def drafted(look_id: str, **layer: Any) -> dict[str, Any]:
    """A built-in look as an unsaved draft, with layer modifiers on its streamed layers."""
    draft = copy.deepcopy(ok("GET", f"/looks/{look_id}"))
    for each in draft["layers"]:
        if each["type"] != "firmware":
            each.update(layer)
    return draft


def start(zone_id: str, look: str | dict[str, Any], transition: dict[str, Any] | None = None) -> Any:
    body: dict[str, Any] = {"lookId": look} if isinstance(look, str) else {"look": look}
    if transition is not None:
        body["transition"] = transition
    return ok("POST", f"/zones/{zone_id}/start", body)


def say(what: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {what}")


def name(look_id: str) -> str:
    """A built-in look's name, as the API serves it."""
    return str(ok("GET", f"/looks/{look_id}")["name"])


def shown(look_id: str, zone_id: str, where: str) -> None:
    """Start a built-in look and say what looks.json says it is (read, never retyped)."""
    look = ok("GET", f"/looks/{look_id}")
    started = start(zone_id, look_id)
    say(f"{look['name']} on {where}, {started['state']}: {look['description']}")


zones = ok("GET", "/zones")
ROOM = max((z for z in zones if z["kind"] == "room"), key=lambda z: len(z["lights"]))["id"]
HOME = next(z for z in zones if z["kind"] == "home")["id"]
PARTICLE_LOOKS = [
    look["id"]
    for look in ok("GET", "/looks")
    if look["builtIn"] and any(layer["type"] == "particles" for layer in look["layers"])
]

if STEP == "lights":  # wait for the lights to come online, up to a minute
    for _ in range(60):
        lights = ok("GET", "/lights")
        online = sum(light["status"] not in ("offline", "reconnecting") for light in lights)
        if online == len(lights):
            break
        time.sleep(1)
    say(f"{online} of {len(lights)} lights online")
elif STEP in PARTICLE_LOOKS:
    shown(STEP, ROOM, "the room")
elif STEP.endswith("-home") and STEP.removesuffix("-home") in PARTICLE_LOOKS:
    shown(STEP.removesuffix("-home"), HOME, "the whole home")
elif STEP == "mirror":
    start(ROOM, drafted("comets", mirror={"axis": "x", "at": None}))
    say(
        f"{name('comets')} folded across the room's middle, the east half mirroring the west:"
        " each landing lights its lamp and whatever stands at the lamp's reflection"
    )
elif STEP == "move":
    start(ROOM, drafted("fountain", transform={"offset": [1.0, 0.0, 0.0], "rotateDeg": 0.0, "scale": 1.0}))
    say(f"{name('fountain')} moved 1 m east: its spray rises 1 m east of its anchor; its bursts still land on lamps")
elif STEP == "into":
    start(ROOM, "aurora")
    time.sleep(3)
    say(f"a 6 s dissolve from {name('aurora')} to {name('fireflies')} starts now")
    start(ROOM, "fireflies", {"kind": "dissolve", "durationS": 6})
    time.sleep(7)
    say(f"done: {name('fireflies')} alone")
elif STEP == "between":
    say(f"a 6 s fade from what runs now to {name('ball')} starts now")
    start(ROOM, "ball", {"kind": "fade", "durationS": 6})
    time.sleep(7)
    say(f"done: {name('ball')} alone")
elif STEP == "tempo":
    start(ROOM, "ball")
    for bpm in (60.0, 180.0):
        ok("PUT", "/inputs/tempo", {"lock": "internal", "bpm": bpm})
        say(f"{name('ball')} at {bpm:.0f} BPM for 10 s: it lands on a lamp on every beat")
        time.sleep(10)
    ok("PUT", "/inputs/tempo", {"lock": "auto"})
    say("the tempo back to Auto")
elif STEP == "stop":
    status, _ = call("POST", "/running/stop-all")
    say(f"Stop all ({status}): every light back as it was")
else:
    sys.exit(f"unknown step {STEP}")
```

- [ ] **Step 3: The dry run**

```bash
. /tmp/m5-live.env && cd "$W"
(uv run python /tmp/m5-dry/run.py --dj-listen 127.0.0.1:0 --web --web-host 127.0.0.1 --web-port "$PORT" --config /tmp/m5-dry/config.toml --db /tmp/m5-dry/state.db > /tmp/m5-dry/app.log 2>&1 & echo $! > /tmp/m5-dry/pid)
uv run python /tmp/m5-wait.py "http://127.0.0.1:$PORT/api/running" 60
ss -Hulnp | grep "pid=$(pgrep -P "$(cat /tmp/m5-dry/pid)")," | awk '{print $4}'
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
timeout 300 uv run --with websockets python /tmp/m5-probe.py "http://127.0.0.1:$PORT"
curl -sf -m 5 "http://127.0.0.1:$PORT/api/running" > /dev/null && echo "still answering"
kill -INT "$(cat /tmp/m5-dry/pid)"; uv run python /tmp/m5-wait.py --gone "$(cat /tmp/m5-dry/pid)" 15
grep -c Traceback /tmp/m5-dry/app.log; grep -c "cutting to" /tmp/m5-dry/app.log
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
```

`--web-port` wins over the port in the snapshot's config, so the deployed app keeps 8080. The first `ss` lists the UDP sockets the dry run holds, and the other two who holds 4002, while it runs and once it has stopped. When this plan was written, this block ran beside the deployed app on a made-up home of eight lights with no zones running, and printed:

```text
answering
127.0.0.1:41453
0.0.0.0:4002 uid:10001
zones resumed at start: 0
the room with the most lights: 8; the whole home: 8
particle looks: 11
fireflies: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
embers: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
rain: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
snow: the room 7 of 8 lights lit, 7 moving, brightest 255 | the whole home 8 of 8 lit
spotlights: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
bursts: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
vortex: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
comets: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
fountain: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
flock: the room 8 of 8 lights lit, 8 moving, brightest 255 | the whole home 8 of 8 lit
ball: the room 8 of 8 lights lit, 8 moving, brightest 254 | the whole home 8 of 8 lit
comets with every modifier: 8 lights lit, brightest 204
a 2 s dissolve to fireflies: plays True, then runs True, no error True
a 2 s fade to ball: plays True, then runs True, no error True
a 2 s wipe to rain: plays True, then runs True, no error True
a 2 s spread to lava: plays True, then runs True, no error True
Stop all: 204, nothing running: True
still answering
ended
0
0
0.0.0.0:4002 uid:10001
```

Expected on this home:
- `answering`, then one address, `127.0.0.1:` and a port: the dry run's only UDP socket is its Pro DJ Link listener on loopback, and it holds neither 4002 nor 50001. Then one line, `0.0.0.0:4002 uid:10001`: the deployed app alone holds 4002 (a socket of root's shows no `uid:`). If the dry run lists any other socket, or 4002 shows a second line or another user, stop the dry run at once (`kill -INT "$(cat /tmp/m5-dry/pid)"`) and tell the owner.
- `zones resumed at start`: the count Step 1 found.
- `particle looks: 11`.
- For each look, at least one light lit and at least one moving in the room and in the whole home, and the brightest byte above 100. How many light up in the 2 s each preview lasts depends on the look and the home: the swarms (fireflies, embers, rain, snow, bursts, vortex, fountain) reach most lights, and the looks that travel the lamps (spotlights, comets, flock, ball) light the lamps they reach, a few in 2 s on a large zone. No look lights 0 lights.
- `comets with every modifier`: at least one light lit, the brightest at most 204 (the 0.8 cap times 255).
- Each 2 s dissolve, fade, wipe and spread `plays True, then runs True, no error True`, and `Stop all: 204, nothing running: True`.
- `still answering`, `ended`, 0 tracebacks and 0 `cutting to` lines, then `0.0.0.0:4002 uid:10001` alone once more.

Anything else is a bug. Fix it in the task that owns the code, with a test, before going on.

- [ ] **Step 4: Ask the owner before touching the deployed app**

Tell the owner the dry run's results. Then ask to stop the deployed container for about twenty minutes, run the branch on the real lights while they watch, and give the lights back. Go on only with their go.

- [ ] **Step 5: Run the branch on the real lights**

With the owner's go. Stop the container and start the branch at once, without waiting for a time of the hour, then check who holds UDP 4002 (CLAUDE.md's Gotchas: Home Assistant takes it if dj-ledfx is down when it retries).

```bash
. /tmp/m5-live.env && cd "$W"
(cd /home/anirudhlath/code/private/dj-ledfx && docker compose stop app)
mkdir -p /tmp/m5-real/state
docker cp dj-ledfx-app-1:/app/state/. /tmp/m5-real/state/   # stopped: a consistent copy
cp /home/anirudhlath/code/private/dj-ledfx/config.toml /tmp/m5-real/config.toml
(uv run -m dj_ledfx --web --web-host 127.0.0.1 --web-port "$PORT" --config /tmp/m5-real/config.toml --db /tmp/m5-real/state/state.db > /tmp/m5-real/app.log 2>&1 & echo $! > /tmp/m5-real/pid)
uv run python /tmp/m5-wait.py "http://127.0.0.1:$PORT/api/running" 60
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
```

The branch works on a copy, so the deployed `state.db` is never written, and with the container stopped it binds UDP 50001 and 4002 as the deployed app does. Expected: `answering`, then one line, `0.0.0.0:4002` and your own user (`uid:` and what `id -u` prints), the branch's socket, not `uid:10001`, the container's. If `ss` lists none, or another user's, the Govee lamps can't answer the branch: tell the owner before going on.

Then, one step at a time, each with the owner's go, run `uv run python /tmp/m5-show.py "http://127.0.0.1:$PORT" STEP` from `$W` for each STEP below, in order. Each prints what it started; the owner judges. Run `stop` at once if a light misbehaves at any step.

1. `lights`: waits up to a minute for the lights to come online, and prints how many are.
2. Each particle look on the room with the most lights, by its id: `fireflies`, `embers`, `rain`, `snow`, `spotlights`, `bursts`, `vortex`, `comets`, `fountain`, `flock` and `ball`. Each prints the look's name and description; ruling 10 says what the plan made of each. The embers' Flame layer runs on the room's candles and tubes, if it has any, and the embers climb the rest. The tempo looks follow whatever tempo the clock has: a DJ's, or the internal clock's.
3. `fireflies-home`, `spotlights-home` and `comets-home` (any look's id with `-home` works): a look on the whole home, whose lamps are every lamp in it. Off is `stop`.
4. `mirror`: `comets` folded across the room's middle (ruling 7). `move`: the fountain moved 1 m east; its spray rises off its anchor by that much, and its bursts still land on lamps (ruling 7).
5. `into`: a 6 s dissolve from aurora to fireflies. `between`: a 6 s fade from fireflies to the ball (two particle looks).
6. `tempo`: the ball at 60 BPM, then at 180, 10 s each, landing on a lamp on every beat (ruling 13; Review Focus 2), then the tempo back to Auto. While a DJ plays, the internal lock overrides them for those 20 s.
7. `stop`: Stop all.

The tunables are the owner's to judge here (ruling 11): each look's palette (`FIREFLY_PALETTE`, `EMBER_PALETTE`, `RAIN_PALETTE` and `LIGHTNING`, `SNOW_PALETTE`, `SPOT_PALETTE`, `BURST_PALETTE`, `VORTEX_PALETTE`, `COMET_PALETTE`, `FOUNTAIN_PALETTE`, `FLOCK_PALETTE`, `BALL_PALETTE`) and its settings' defaults (each `EffectParam`'s `default`), such as how many fireflies, how big the spotlights, how fast the vortex. A change they ask for goes into the task that owns the effect (Task 4, 5, 6 or 7), with its tests, as a fix commit on this branch.

- [ ] **Step 6: Give the lights back to the deployed app**

With the owner's go, at once, without waiting for a time of the hour. Stop the branch first, and start the container only once the branch has ended: while it runs it holds UDP 4002 and 50001, and a container started beside it would find both taken.

```bash
. /tmp/m5-live.env && cd "$W"
kill -INT "$(cat /tmp/m5-real/pid)"; uv run python /tmp/m5-wait.py --gone "$(cat /tmp/m5-real/pid)" 15
grep -c Traceback /tmp/m5-real/app.log; grep -c "cutting to" /tmp/m5-real/app.log
ss -Hulne 'sport = :4002' | grep -c .
```

Expected: `ended`, 0 tracebacks, 0 `cutting to` lines, and `0`: nothing holds 4002 now. If the wait says `not ended`, the branch is stuck: run `kill -9 "$(pgrep -P "$(cat /tmp/m5-real/pid)")"` (the Python process `uv run` started; this run has no stack-dump driver, and the lights come first), then the wait again, and tell the owner. If `ss` counts a socket, another program took 4002 the moment it was free (CLAUDE.md's Gotchas): go on, and tell the owner.

```bash
. /tmp/m5-live.env && cd "$W"
(cd /home/anirudhlath/code/private/dj-ledfx && docker compose start app)
uv run python /tmp/m5-wait.py http://127.0.0.1:8080/api/running 120
curl -s http://127.0.0.1:8080/api/running | uv run python -c "import json, sys; print(len(json.load(sys.stdin)['zones']), 'zones running')"
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
```

Expected:
- `answering`, and the deployed app runs as many zones as Step 1 found: it resumes from its own `state.db`.
- One line, `0.0.0.0:4002 uid:10001`. Anything else means the deployed app can't hear the Govee lamps (a line with no `uid:` is root's: Home Assistant took the port): tell the owner (CLAUDE.md's Gotchas).

Tell the owner it's done. There's nothing to commit here: a fix found in this task goes into the task that owns the code, with a test.

---


### Task 10: CLAUDE.md and the README

CLAUDE.md asks for the claude-md skill to revise Claude's context after each plan. M5 adds a kind of effect, its toolkit, eleven effect modules and their built-in looks, and the runtime now draws particle layers, so CLAUDE.md's architecture, design decisions, testing and gotchas all need lines. The README's feature list gains one.

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Run the skills**

Run the `claude-md-management:claude-md-improver` skill (audit and targeted updates), then `/claude-md-management:revise-claude-md` for what this branch taught. Both show their changes before writing. Get the owner's go.

- [ ] **Step 2: Check the facts M5 changed are in CLAUDE.md**

Whatever the skills propose, CLAUDE.md must end up saying these, and nothing that contradicts them. Keep design values out of it: name the files that hold them (CLAUDE.md, "Web App Design"), and never a look's name or description.

- **Architecture:**
  - Add `effects/particle_tools.py`: what particle effects share, in pure numpy. `Particles` (positions in metres on the map's axes, colours with their brightness in them, radii; `swarm()`, `joined()`, `NO_PARTICLES`); `draws(seed, keys, count, stream)`, a counter-based generator on SplitMix64's mixer, and `recent()`, the events that may be alive at a moment; the moves (`wander`, `arc`, `tour`, `shuffled`, `spread_over`, `around`); the zone's lamps as stops (`Lamps`, `lamps_of()`, `NO_LAMPS`; lights within `SAME_STOP_M` of one another are one stop); `Ground`, worked out once for each LED set (its lamps, floor and ceiling; `on()`, the LED of a lamp that a draw picks; `foot()`, under one at its lowest LED's height; `box()`); and `lit()`, the Gaussian falloff out to `REACH` radii, dense below `GRID_FROM_LEDS` LEDs and through a spatial grid from there.
  - Add `effects/particles.py`: `ParticleEffect` (`place(leds)`, `step(ctx)`, `sample(ctx, leds)` and `particles`, the last step's, which M8's `fx` stream can read), `ParamParticles` (a particle effect's settings kept as `ParamField` keeps a field's, and its particles worked out in closed form by `positions(ctx, ground)`), `MAX_PARTICLES` (500, the newest kept) and `drawn(effect, ctx, leds)`, the three calls in order.
  - The `effects/field.py` line: `ParamField` stands on `ParamSettings` (`effects/base.py`), which `ParamParticles` shares (the settings, `_prepare()`, `reseed()`).
  - Add `effects/{fireflies,snowfall,embers,rain_storm,spotlights,beat_bursts,fountain,vortex,twin_comets,bouncing_ball,flock}.py`: the eleven particle looks' effects.
  - The `looks/` line: the built-ins are the handoff's M2, M3 and M5 looks and the `firmware` look, in `looks.json`'s order, then the six classics; the model takes particle layers, and `make_effect()` refuses a layer whose kind is another kind's effect, with the reason; `streamed_layers()` is the visible field and particle layers, bottom to top.
  - The `zones/` line: the runtime draws its streamed layers, field and particle alike (`_streamed`), bottom to top through each layer's view; a particle layer is placed among the LEDs its view shows, stepped and sampled (`drawn()`).
- **Key design decisions:**
  - A particle effect works its particles out from the frame's moment, its seed and the LEDs alone, drawing each event's random numbers from `draws()`: the same moment gives the same frame however the frames fall, a twin draws what its zone draws, and a landing falls on the beat at any frame rate. A settings change applies from the next frame, so the particles jump.
  - Emitters, paths and targets are anchors or lamps. Each visit, landing, drop, flake or ember picks its own LED of its lamp, so particles reach the whole length of a long light; a lamp's base is under one of its LEDs at its lowest LED's height. Particles move inside the zone's frame, from the map's floor to the ceiling its space carries (with no ceiling, from its lowest LED to `CEILING_OVER_M` over its highest).
  - A particle lights each LED by exp(−(d/r)²), clipped to 1; a particle layer is black between its particles, so under `normal` it covers the layers below it there: to lay particles over a field, give the particle layer `add`, `screen` or `max`.
  - The tempo looks move with the beat count and phase (`ctx.beats`), never the BPM; the ambient ones in seconds (`ctx.t`).
  - A particle layer takes the layer modifiers as a field layer does: what an anchor or the zone's frame places moves with the field, and what goes to a lamp still goes to one of its LEDs.
- **Testing:**
  - `tests/effects/test_particle_effects.py`: the sweep every registered particle effect joins (`PARTICLE_KINDS`): finite, in range and repeating; the same moment however the frames fall; 30 to 300 BPM; the smallest zones (one lamp with no map, one bulb, no LEDs); the cap at the largest settings; and, marked perf, each effect at its largest settings within the budget.
  - Shared helpers: `lights_at(*lights, ceiling=3.0, anchors=None)` and `upright(x, y)` in `tests/map_home.py`; `DotParticles` (`dot_particles`) and `dot_layer()` in `tests/runtime_fakes.py`.
  - The perf run adds 500 particles on 10,000 LEDs, each particle effect at its largest settings, and a particle look mid-transition from another.
- **Gotchas:**
  - A particle effect's randomness goes through `draws()` keyed by event, never a generator stepped from frame to frame: a frame skipped or rendered twice would change every frame after it.
  - A particle layer can't pick lights (`lights`), as a field layer can't: give it a mask.
  - Nothing reads `ParticleEffect.particles` before M8.

- [ ] **Step 3: Add the README's feature**

In `README.md`, after the "Modifiers and transitions" bullet, add:

```markdown
- **Particles** — particle effects move through the home, sent from, led along and drawn to its anchors and lamps, and light the LEDs near them by a distance falloff, through a spatial grid on large homes. The handoff's eleven particle looks run as built-ins on any zone, with every modifier and transition, and repeat exactly whatever the frames' timing; the tempo ones land on the beat at any tempo.
```

- [ ] **Step 4: Check that nothing still promises M5**

```bash
git grep -n -e "arrive in M5" -e "Particle layers arrive" -- . ':!docs'
```

Expected: no lines (git grep exits 1), as when this plan was tried. The plan and the specs under `docs/` keep their history. A line under `web/` can only be F4's, if this branch was cut after F4 merged: Task 11's Step 3 settles it.

- [ ] **Step 5: Offer a memory**

The owner's auto-memory index (`/home/anirudhlath/.claude/projects/-home-anirudhlath/memory/MEMORY.md`) has a `dj-ledfx redesign` entry. Offer to add one line to its file (`project_dj_ledfx_redesign.md`): M5 landed as a PR; particle looks are worked out in closed form from the moment, so they repeat and twins match; the palettes and defaults are the plan's own until the owner tunes them. Write it only with a go.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: CLAUDE.md and the README for particles"
```

---


### Task 11: Catch up with master, and the PR

CLAUDE.md ends every plan with a pull request. F4, the web app's Put a look on, may have merged meanwhile. This branch changes nothing under `web/`, but F4 may have changed the backend's tests of the built-in looks, or written web code for looks the engine didn't serve yet. This task rebases, makes F4's code follow what M5 serves, runs every gate again and opens the PR. It never merges.

**Files:**
- Modify: whatever the rebase leaves in conflict; `web/src/api/generated/*` if the rebase changed the backend's API; any F4 code that Step 3 names
- Create: `/tmp/m5-pr-body.md` (not committed)

- [ ] **Step 1: Rebase onto `master`**

```bash
git fetch origin
git rebase origin/master
git log --oneline -8 origin/master
```

The branch hasn't been pushed, so rebasing is safe. It changes no file under `web/`, so a conflict there means something unexpected changed: stop and tell the owner. A conflict in `tests/web/test_looks_api.py`, `tests/looks/test_builtin.py` or `tests/web/test_zones_api.py` means F4 changed the built-ins' tests too: keep both sides (F4's change and Task 8's: the built-ins in `looks.json`'s order, the particle looks among them), and Step 4 checks the result. If a conflict touches `CLAUDE.md`, `README.md`, `src/dj_ledfx/looks/builtin.py`, `src/dj_ledfx/looks/model.py` or `src/dj_ledfx/zones/runtime.py`, keep both sides. If `pyproject.toml` or `uv.lock` changed on master, run `uv sync --extra web` before Step 4 (never hand-edit `uv.lock`).

- [ ] **Step 2: Check the generated types**

```bash
uv sync --extra web
(cd web && npm ci && npm run api:types && git status --short src/api/generated)
uv run pytest tests/web/test_openapi_types.py -q
```

Expected: `git status` lists nothing and the pytest passes: M5 changes no API shape, so the types are master's. If it lists files, master's own types were behind its API: commit them, and say so in the PR.

```bash
git add web/src/api/generated
git commit -m "chore(web): regenerate the API types after the rebase"
```

- [ ] **Step 3: Make F4's code follow what M5 serves**

Skip this step if F4 hasn't merged.

1. Run `git grep -n -i -e "M5" -e "particle" -- web/src ':!web/src/api/generated' ':!web/src/design/icons.ts'`. A line that says the particle looks aren't served yet, hides them, greys them out or skips them for having no layers is F4's placeholder for M5: make it follow what M5 serves. `GET /api/looks` now answers the eleven particle looks with their layers (`type: 'particles'`, which the contract's `Layer.type` always had), and every zone starts and previews them like any look. Never change the backend to fit F4's code; if F4's code needs something the API doesn't serve, stop and tell the owner: the contract needs a ruling.
2. Run `(cd web && npm test && npx tsc -b && npm run lint)` and `uv run pytest tests/web -q`. If anything changed, commit it:

```bash
git add web/src
git commit -m "fix(web): F4's Put a look on follows engine M5's particle looks"
```

- [ ] **Step 4: Run every gate**

```bash
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm run api:check && npm test 2>&1 | grep -E "^ +Tests " && npx tsc -b && npm run lint && npm run build 2>&1 | tail -1)
ss -ltn | grep -cE ':(4174|4175) '
```

e2e serves on 4174 and 4175, so only one worktree can run it at a time (CLAUDE.md's Gotchas). If the `ss` count isn't `0`, another worktree is running it: wait until both ports are free, with a Monitor on `until ! ss -ltn | grep -qE ':(4174|4175) '; do sleep 10; done`, then:

```bash
(cd web && npx playwright install chromium && npm run e2e 2>&1 | tail -4)
```

Expected:
- ruff is clean and every test passes: `2234 passed, 1 skipped, 77 deselected` when this plan was tried on `d6f959e` (Before Task 1's 2029 and this branch's 205), plus whatever master has added since.
- `367 files already formatted`, and mypy's 16 errors: no worse than Before Task 1's baseline.
- The perf run: `77 passed` when this plan was tried (Before Task 1's 42, Task 1's one, the sweep's eleven, and Task 8's 23), each under 5 ms per zone frame.
- Every web step passes: `api types match`, Before Task 1's 716 web tests plus whatever F4 added, `tsc -b`, lint and the build. e2e: `90 passed` and `48 skipped` on `d6f959e`, plus F4's.

- [ ] **Step 5: Check that nothing private is in the branch**

```bash
git diff origin/master -- . ':!docs/design' ':!src/dj_ledfx/home/data' > /tmp/m5-diff.txt
grep -nE '^\+.*\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|^\+.*\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/m5-diff.txt | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
uv run python -c "import json; print('\n'.join(sorted({l['model'] for l in json.load(open('docs/design/web-app/home.json'))['lights'] if l.get('model')})))" > /tmp/m5-models.txt
grep '^+' /tmp/m5-diff.txt | grep -ciFf /tmp/m5-models.txt || echo "no model names"
uv run python -c "import json; from dj_ledfx.home.seed import OWNER_ROOM_NAMES; home = json.load(open('docs/design/web-app/home.json')); place = home['location']; print('\n'.join(sorted({l['name'] for l in home['lights'] if ' ' in l['name']} | {r['name'] for r in home['rooms']} | set(OWNER_ROOM_NAMES.values())) + [place['name'].split(',')[0], str(place['lat']), str(place['lon'])]))" > /tmp/m5-private.txt
grep '^+' /tmp/m5-diff.txt | grep -ciwFf /tmp/m5-private.txt || echo "no light names, room names or place"
```

Expected: `no addresses`, then `0` and `no model names`, then `0` and `no light names, room names or place` (`grep -c` prints the 0), as on this plan's final diff when it was tried. Loopback and `0.0.0.0` are allowed. The lists come from `home.json` and the seed at run time, so they're never typed here, and the greps print only counts. The handoff's own files and the vendored `home.json` are excluded. Anything found goes: replace it with `localhost`, a made-up name or made-up coordinates. If a count comes from a line this branch only moved, or from F4's lines after the rebase, tell the owner instead.

- [ ] **Step 6: Write the PR description**

Write `/tmp/m5-pr-body.md` with these sections, in this order.

**Summary.** Engine milestone M5 of `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: particle effects, which move through the home sent from, led along and drawn to its anchors and lamps, and the handoff's eleven particle looks as built-ins, on any zone, with every modifier and transition, inside the 5 ms budget. Plan: `docs/superpowers/plans/2026-10-07-m5-particles.md`.

**What changed**, one bullet per area:

- Effects: `particle_tools.py` (`Particles`, `draws()`, the moves, the lamps, `Ground`, and `lit()` with its grid), `particles.py` (`ParticleEffect`, `ParamParticles`, `drawn()`), `ParamSettings` shared with `ParamField`, and the eleven effect modules.
- Looks: the model takes particle layers and refuses a layer of the wrong kind with the reason; the eleven particle looks join the built-ins in `looks.json`'s order.
- Zones: the runtime draws particle layers with the field layers, bottom to top, through each layer's view.
- The web app: unchanged, the API's shapes being the same; F4's code follows (Step 3), if it merged first.
- Docs: CLAUDE.md and the README.

**API.** No shape changes: `Layer.type` already named `particles` (web spec §12.2). `GET /api/looks` serves the eleven particle looks, each with its layer and that layer's settings schema; `POST /api/looks` and the previews refuse a layer of the wrong kind with the reason (400), and a particle layer that picks lights, as a field layer is refused.

**Migration.** None. Particle layers live inside the looks and zone assignments `state.db` already holds (ruling 14).

**Deployment.** After the merge, from the main checkout: `git pull && docker compose up -d --build`, at once, then check that `ss -ulne 'sport = :4002'` shows `uid:10001`; if it shows another user, Home Assistant took the port (CLAUDE.md's Gotchas). The ports stay as they are, and the running zones resume.

**Spec rulings.** Rulings 1–15 from the plan, one line each, the owner's marked.

**Review Focus.** The plan's five items, each with its tests.

**Real lights.** Task 9's results as counts and yes or no: the dry run's lines, and the owner's check of each step on the real lights, with any palette or default they changed. No ids, addresses, model names, room names or places.

**Test plan.** Step 4's gates with their counts, the perf run, the web gate, and Task 9.

End the description with:

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Then check the description as Step 5 checked the diff:

```bash
grep -nE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/m5-pr-body.md | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
grep -ciFf /tmp/m5-models.txt /tmp/m5-pr-body.md || echo "no model names"
grep -ciwFf /tmp/m5-private.txt /tmp/m5-pr-body.md || echo "no light names, room names or place"
```

Expected: `no addresses`, then `0` and `no model names`, then `0` and `no light names, room names or place`.

- [ ] **Step 7: Push and open the PR**

```bash
git push -u origin feature/m5-particles
gh pr create --base master --head feature/m5-particles \
  --title "M5 particles: particle effects that know where the lamps are, and the eleven particle looks" \
  --body-file /tmp/m5-pr-body.md
gh pr view --json url --jq .url
```

Give the owner the URL. Don't merge: the owner does, after review. /executing-plans' own final review of the whole branch closes the run; a code-architect review or `/simplify` runs only if the owner asks for one.
