# M8 Effects in Space (engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The engine sends what each running zone and the preview draw in space, on the `fx` WebSocket channel (web spec §12.4, "The `fx` payload"): the particles of M5's eleven looks, Shockwave's shell, Speaker waves' kick fronts and Ripples' drops as rings, and the Scanner's plane and Shockwave's beam as planes, in the home map's frame, at most 30 times a second, to the sessions that ask. The web app's F10, planned beside this one, draws them on the stage, so the owner can see how each particle look meets the lamps and tune the M5 looks (issues #48–#58).

**Architecture:** One optional hook on every effect, `Effect.in_space(ctx, leds) -> Fx | None`, None by default (`effects/fx.py` holds the shapes: `Fx` of `Particles`, `Rings` and `Planes`). A particle effect's hook hands over the particles its last step made, so no look's code changes; the five field effects the spec names say where their shell, front, ripple or plane is. The zone runtime asks each streamed layer for its fx right after its frame, maps them from the effect's space onto the map through the layer's view (`LayerView.in_home()`: the transform undone, every image of a mirror, the mask), applies the layer's opacity and the look's evening and cap, and keeps the result in the `RenderedFrame` beside the colours. `FrameFeed.fx()` reads, for every live and preview runtime, the newest frame at or before now (`RingBuffer.frame_at`), never blended; `web/fx.py` turns that into the payload (brightness, rounding, the 500-particle cap) and `web/ws.py` sends it on a per-session poll at 30 Hz, only when it changed, to protocol-2 sessions that sent `subscribe_fx {on: true}`.

**Tech Stack:** Python 3.14 in the venv and the container, numpy, FastAPI and Starlette's WebSocket, loguru, pytest with pytest-asyncio. No new dependency and no external API. Nothing under `web/` changes: the WebSocket channels' types are written by hand in `web/src/api/contract.ts`, not generated from the engine (OpenAPI covers REST only), so this plan regenerates nothing, and F10 writes the `fx` types there.

**Spec:** `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md` §12.4 (the `fx` row of the channel table, `subscribe_fx {on}`, and "The `fx` payload" with its bullets: binding), §7.4 (what the stage draws) and §13's M10 row; `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: the amendments at its top, the M8 row in §2, §4.1, §5.1, §5.3, §8 and §9. Read them before starting.

**What exists.** What M8 starts from, on master at `3ac0dac` (the docs branch adds only `57455a7`, which wrote the `fx` payload into the web spec):

- M5's particle effects keep their last step's particles readable (`ParticleEffect.particles`: positions in metres on the map's axes, colours with their brightness in them, radii, oldest first), and CLAUDE.md says "Nothing reads `ParticleEffect.particles` before M8".
- The five field effects that draw something the spec names: `shockwave_shell`, `lighthouse_beam` (the two layers of Shockwave), `scanner_plane` (Scanner), `speaker_waves` (Speaker waves) and `ripples` (Ripples), each lighting its LEDs through `band()`, the Gaussian that falls to e^-1 one width out.
- A zone runtime renders `RenderedFrame(colors, target_time, beat_phase, bar_phase)` into its ring, up to `HORIZON_CAP_S` (500 ms) ahead; each layer draws through its `LayerView` (`zones/layer_view.py`: the mask's weights, and the LEDs its mirror, then its transform, move); the look modifiers run after the layers (`flashed`, `Trails`, `warmed`, `capped`).
- `FrameFeed` (`zones/frames.py`) reads each live and preview runtime's colours at now, blended (`RingBuffer.colors_at`); `web/ws.py` sends them as binary frames, v2 after `subscribe_frames` with `"protocol": 2`. Any other action, `subscribe_fx` among them, gets `{"channel": "error", "detail": "Unknown action: …"}`.
- The web app's mock (`web/src/api/mocks/mock-server.ts`) already acks `subscribe_fx` and sends nothing; F10 makes it send fx.

**Execution:** in a new worktree, `~/code/.worktrees/dj-ledfx/m8-fx` on branch `feature/m8-fx`, by the method the owner picks. Branch it from `origin/master` after the docs PR with this plan has merged; Before Task 1 sets it up.

F10, the web app's side, is planned at the same time (`docs/superpowers/plans/2026-10-14-f10-effects-in-space.md`) and may merge first. The two meet only at the payload, which the web spec fixes. This plan changes nothing under `web/`; Task 8 rebases over whatever has merged and checks that F10's hand-written types and mock match what the engine sends.

**How to read the code.** A new file is given whole, in a `python` block after "Create". A change to an existing file is a unified diff, in a `diff` block, against the file as master at `3ac0dac` and the earlier tasks leave it; apply the blocks in the order given. Save a block to a file and run `git apply --recount` on it (`git apply --recount /tmp/m8-step.diff`), or make the same edit by hand. If master has moved past `3ac0dac` and a block no longer applies, make the edit by hand: its hunks say where. Every block was applied in this order to a copy of `57455a7` while this plan was written, and each task's gate passed there with the counts given. A newer master may add to them.

---


## Global Constraints

Every task's requirements include these. Quotes are verbatim from the specs.

- The engine spec's M8 row (§2): "The `fx` stream: particles, rings, planes and sun shafts drawn on the web app's stage (brought forward on 2026-10-14, after M5, so the particle looks can be tuned on the stage; sun shafts follow M6's sun)". §4.1: "From M8, effects can also describe what they draw in space (particle positions, rings, planes, sun shafts) for the web app's stage."
- The web spec's channel row (§12.4): "`fx` | when subscribed, ≤ 30 Hz | optional: particles `[x,y,z,r,g,b,size]`, rings, planes, sun shafts per zone, for "Effects in space"", and the command "`subscribe_fx {on}`".
- The payload (§12.4, binding):

  ```ts
  interface FxMessage { channel: 'fx'; zones: ZoneFx[] }      // the whole picture: each message replaces the last
  interface ZoneFx {
    zoneId: Id
    stream: 'live' | 'preview'                                 // which frames it belongs with, as frame v2's stream byte
    particles?: [x: number, y: number, z: number, r: number, g: number, b: number, size: number][]
    rings?: { center: Vec3; radius: number; width: number; rgb: Vec3; form: 'sphere' | 'circle' }[]
    planes?: { point: Vec3; normal: Vec3; width: number; rgb: Vec3; ray?: Vec3 }[]
  }
  type Vec3 = [number, number, number]
  ```

  - "Positions and lengths are metres in the home map's frame (z up), the frame the stage places the LEDs in: an effect's own space (a layer's transform, its mirror) is mapped back, and a mirrored layer sends each thing at every place the mirror shows it. Colours are linear 0–1, after the zone's brightness. Numbers are rounded to 3 decimals."
  - "What a zone sends is what its lights show at now: the engine keeps each rendered frame's `fx` beside its colours and sends the newest at or before now, the moment the live and preview frames are read at."
  - "A `circle` lies level (its axis is z); a `sphere` is a shell. A plane is infinite unless it has a `ray`, a direction in the plane: then it is the half on that side of `point` (a lighthouse beam). `width` is how thick the shell, ring or plane is drawn."
  - "A zone with nothing to draw is left out, and a message with no zones clears the stage. The server sends at most 30 a second and only to a session that sent `subscribe_fx {on: true}`, until `{on: false}`; it sends nothing while nothing changes."
  - "**Extending it:** a later kind (M6's sun `shafts`, the doorbell's ring) is a new optional key on `ZoneFx`, or a new optional field on an item. The client ignores keys it doesn't know, and the server never renames or removes one, so neither side bumps a version."
  - "**What draws what (M8's first slice):** every particle effect (M5's eleven looks) sends `particles`; Shockwave's shell and Speaker waves' kick fronts send `sphere` rings, Ripples' drops `circle` rings; Scanner sends a level plane and Shockwave's beam a plane with a `ray`. Firmware layers send nothing. Sun shafts wait for M6's sun."
- The cut (agreed with the owner, 2026-10-14): this slice is the `fx` stream for particles, rings and planes, live and preview. **Deferred**, and said so wherever it would otherwise be expected: sun shafts (M6's sun), the doorbell's gold ring and the overlays (M6/M7), and F10's reduced-motion, performance and accessibility pass. No speculative generality beyond the payload's own extension rule.
- §4.1: "Everything stays on the single asyncio event loop. Budget: under 5 ms per zone frame on one core." The light-sync amendment: "A zone renders up to 500 ms ahead, up from 120 ms."
- §8: "**A look raises or produces NaN:** that zone holds its last good frame, the look is marked crashed, and the error is logged once (rate-limited). Other zones keep running." What a zone draws in space never costs it its frame.
- §9: "**Performance:** a benchmark test on this home's 412-LED map asserts each zone renders in under 5 ms. It is marked as a performance test and run locally." Perf tests are marked `perf` and deselected by default (`-m perf` runs them).
- The repo is public: no LAN addresses, MACs, SSIDs, light names, light model names, room names, the home's location or AI model names in code, tests, commits, the PR or this plan; no model identifiers in commits, PRs or code. Fixtures use made-up ids (`test-lamp`, lamps a–d, `light-0`, …) and 127.0.0.1. Loopback, `0.0.0.0` and port numbers are fine.
- Code style (CLAUDE.md): `uv` for everything, `loguru` for logging (never INFO in the render loop), `mypy --strict`, render paths synchronous and lock-free, numpy on whole arrays in the render path (no loop over LEDs or particles), and a frame in a ring never changed after it's written: an `Fx` is frozen and every change makes a new one.
- Gates, per task before commit: `uv run ruff check .` clean and `uv run pytest -q` green; `uv run ruff format --check .` no findings and `uv run mypy src/` no worse than the baseline from Before Task 1 (16 errors when this plan was written). During a task, run only its test files; run the full gate once, before the commit. The plan's code was formatter-exact when it was written, but run `uv run ruff format` and `uv run ruff check --fix` on the files the task touched before the gate, never on the whole tree. `uv run pytest -m perf -q` keeps every zone frame under the 5 ms budget: Tasks 1, 4, 5 and 8 run it.
- Live system: nothing in this plan touches a light, the deployed `dj-ledfx-app-1`, docker's state, UFW, port 8080 or UDP 4002. Task 6's dry run reads a copy of the deployed `state.db` through one read-only process and runs the branch on a spare port with no light backend, so it needs no owner go (ruling 15). master changes only through the PR, which the owner merges; no stacked branches. Never a bare `git stash`. Fix every review finding, Minor ones included; reviews run only when the owner asks.

## Spec Rulings

The specs leave some things open. These are the rulings this plan builds on, each with why and what it costs if it's wrong. Rulings 1–5 carry the controller's decisions, refined where a reason is given. Task 8 lists them in the PR; the ones marked **owner** change what the owner sees on the stage.

1. **One hook, None by default.** `Effect.in_space(ctx, leds) -> Fx | None` (`effects/base.py`), called by the runtime right after the effect's frame, with the same moment and LEDs. `ParticleEffect`'s returns its last step's `Particles` (none: None), so the eleven M5 effects send theirs with no code of their own; the five field effects the spec names implement it (Task 2); every other effect, the firmware ones included, keeps the default. *Why:* one entry point, and the particles are already worked out each frame, so drawing them costs a reference. *If wrong:* a later kind (M6's sun shafts) is one more field on `Fx` and one more key in the encoder, which the payload's extension rule allows.
2. **The shapes, and what `size` and `width` mean.** `effects/fx.py`: `Fx(particles, rings, planes)`, in the effect's own space, colours linear as the effect draws them, before the layer's opacity, the look's modifiers and the zone's brightness. A particle's `size` is its radius in metres, the `r` of its exp(−(d/r)²) light (on the map: grown by a transform's scale). A ring's or a plane's `width` is its light's full thickness where it falls to e^-1: twice the `band()` width its effect lights the LEDs with. **Owner:** the beam's light is an angle, not a thickness, so its `width` is that angle in radians, the beam's full width 1 m from the anchor (`radians(width_deg)`). *Why:* the spec says only "how thick the shell, ring or plane is drawn"; the e^-1 width matches what the LEDs show, and F10 must read it the same way (Task 8 checks). *If wrong:* F10 draws everything twice or half as thick; one constant here or there.
3. **What each field effect sends (owner).** Shockwave's shell: a `sphere` round its anchor (the zone's middle with none), out to its front, `reach_m × beat_phase`, in its crest's colour, `(1 − phase)²` along the ramp. Speaker waves: a `sphere` round each of its anchor's points, out to the kick's front, in the colour the crest lights an LED; the snares and hats stay on the LEDs. Ripples: a level `circle` where each live drop landed, out to its front, in the colour its strength lights, as §12.4 says, though the effect lights LEDs by their 3D distance from the drop. Scanner: a level plane through the zone's middle at the height it lights (between the floor and the ceiling; with no ceiling, the zone's bottom and top), in the ramp's brightest colour. Shockwave's beam: the upright half-plane from its anchor towards the bar's bearing (`ray` = (cos 2πφ, sin 2πφ, 0), φ the bar phase, x east and y south as `bearing()` has them), in its colour. Each colour is times the effect's `level`. *Why:* each is the thing the LEDs light, where they light it. *If wrong:* one effect's `in_space`, with its tests.
4. **Kept beside the colours, read at now, never blended.** `RenderedFrame` gains `fx: Fx | None`, on the map, before brightness; the runtime writes it with the colours, so the ring covers the horizon for both. `FrameFeed.fx()` reads, for each live then preview runtime, `RingBuffer.frame_at(now)`: the newest frame at or before now, never a blend of two (a ring and a particle can't be blended), the first frame for a moment before it (as the colours hold it), and a crashed zone's last good frame (the ring keeps it). *Why:* §12.4's second bullet. *If wrong:* the stage leads or lags the lights by up to a frame (1/60 s).
5. **Onto the map.** `LayerView.in_home(fx)` undoes the transform (a place goes back through the turn, the scale and the offset; a direction, a normal or a ray, through the turn; a length grows by the scale), then draws each thing at every place the mirror shows it: a particle on the mirror's low side at its place and at its reflection, side by side, and **owner:** a particle on the high side, which no LED shows (the high side's LEDs see the low side's field), not at all; a ring or a plane whole at its place and at its reflection, its normal and ray reflected. *Why:* §12.4's first bullet; "every place the mirror shows it". *If wrong:* a mirrored look's particles show where its lights don't light them; `in_home` and its tests.
6. **The mask (owner; the controller asked for a ruling).** A particle is weighed by the mask at the place it lands on the map (its colour times the weight, as the LEDs there are) and left out where the mask weighs 0, so fireflies masked to a room fade out at its walls as the room's lamps do. A ring or a plane is drawn whole while the mask weighs any of the zone's LEDs above 0, and not at all otherwise. *Why:* clipping a sphere or a plane to a room's outline needs a field the payload doesn't have; a later optional key could carry one, by the extension rule. *If wrong:* a masked Shockwave draws its whole sphere past the room it lights; the cost is a clip key and F10 drawing it.
7. **Colours: which modifiers apply.** A layer's opacity multiplies its fx colours whatever its blend (a blend mixes with the layer below, which has no meaning for a particle in the air). The look's evening and brightness cap apply, as they change every LED the look lights; **owner:** the downbeat flash and trails don't: the flash brightens the whole frame for a moment and trails are the LEDs' memory of what they showed, neither of which is a thing in space. The zone's brightness applies at encode, as it does at send; colours are then clipped to 0..1 and rounded to 3 places, and an item whose colour rounds to black or holds a number JSON can't carry is left out, a kind with nothing left is left out, and so is a zone. *Why:* §12.4: "Colours are linear 0–1, after the zone's brightness." *If wrong:* a flash or a trail missing on the stage: one more `recoloured` in `_render_look`.
8. **The cap: 500 particles a zone and stream** (`MAX_FX_PARTICLES` in `web/fx.py`, the newest kept, as `MAX_PARTICLES` keeps a step's). *Why:* it is the particle effects' own cap, so a layer is never cut unless a mirror doubles it or particle layers stack; this home's eleven looks make at most 76 particles at their defaults (snow) and 380 at their largest settings (snow), measured on the seeded home while this plan was written. A full zone is about 25 KB of JSON a message, and two full zones encode in well under half a frame (Task 5's perf test). *If wrong:* a stacked or mirrored zone loses its oldest particles on the stage only.
9. **During a transition, the new look's fx alone (owner),** from its first frame. Each look's runtime keeps its own; the zone's frame carries the new one's. *Why:* mixing a dissolve or a wipe into things in space needs a share for each item, which the payload doesn't have; the new look is what the zone is becoming. *If wrong:* for a transition's length (10 s at most) the stage shows the new look's particles while some LEDs still show the old look.
10. **Always worked out.** The runtime asks every streamed layer for its fx every frame, watched or not. *Why:* measured on this home at the largest settings with every modifier, it costs at most 0.21 ms a frame (Task 4's perf test bounds it at 0.5 ms, a tenth of the budget), and a watcher gate would make the first message after a subscribe wait a horizon. *If wrong:* a `Watchers.watching("fx")`-style gate is one condition in `_render_layers`.
11. **A hook that fails costs its fx, never the frame.** An exception in `in_space` or `in_home` drops that layer's fx for that frame and logs one WARNING per zone a minute at most (`CRASH_LOG_INTERVAL_S`); the frame and the lights go on. A message that can't be made ends that session's fx channel with one ERROR log; the session's other channels go on. *Why:* §8; the lights come first. *If wrong:* a silent stage instead of a log line.
12. **The channel.** `subscribe_fx` takes `on: true | false`; anything else gets `{"channel": "error", "id", "detail": "subscribe_fx takes on: true or false"}`, and the ack is `{"channel": "ack", "id", "action": "subscribe_fx", "on"}` (the mock's ack has no `on`; a client ignores keys it doesn't know). Each session that turns it on gets its own poll, every 1/30 s: while it asks and speaks frame protocol 2 (`ZoneFx.stream` is v2's), it sends the whole picture when it differs from the last one it sent that session. So nothing goes out while nothing changes, one message with no zones goes out when the last zone stops drawing, and **owner:** a session that turns it on, or moves to protocol 2, gets the picture at once, an empty one included. A protocol-1 session is acked and sent nothing. Every zone's fx go to every subscribed session, live and preview, whatever frame streams it watches: the client picks by `stream`. The message text is cached for one engine frame and made again when a zone's frame for now, or its brightness, is another one (`app.state.fx_cache`): sessions whose polls land within the same frame share it, and a session polling on another phase encodes its own (amended by the final review: the frames change at 60 Hz and each poll runs at 30 Hz on its own phase, so this is not one encode for every tab). *Why:* §12.4's last bullets. *If wrong:* one condition in `_fx_poll`.
13. **Preview runtimes send with stream `"preview"`,** the zone being the preview's zone, read by `FrameFeed` as their frames are. A preview's fx start with its first frame and stop when it ends.
14. **The perf bound.** Every built-in look that draws in space, at its layers' largest settings and with every modifier (mirror and mask included), renders under the 5 ms budget, and its fx's share of the frame stays under 0.5 ms (`FX_SHARE_S`), against the same look with every hook returning None. *Why:* §4.1's budget, and the controller's "fx must not push a zone frame over 5 ms".
15. **The dry run needs no owner go.** Task 6 copies the deployed `state.db` with one read-only process in the container (`docker exec … sqlite3 … mode=ro`), runs the branch on a spare port with no light backend, and probes the `fx` channel over a WebSocket. It changes nothing in the deployed app, opens neither UDP 4002 nor 50001, and reaches no light, so, as the controller decided, it runs without asking. M5's Task 9 asked a go for the same read-only snapshot. There is no step on the real lights: F10's stage is where the owner sees fx.

## Review Focus

These are the five inputs the specs imply that are most likely to bite someone using this, most likely first. Each has tests in the task that owns the code.

1. **Mirrored and moved layers.** A layer with a transform (offset, turn, scale) or a mirror, or both: every particle, ring and plane lands where the zone's LEDs show it, and a mirror shows each thing at both its images and nothing the LEDs don't show. Tests: Task 3, `test_in_home_undoes_the_transform_so_what_an_led_sees_lands_on_the_led`, `test_in_home_turns_a_planes_directions_and_grows_lengths_by_the_scale`, `test_in_home_draws_a_particle_on_the_mirrors_low_side_at_both_its_images` and `test_in_home_draws_rings_and_planes_whole_at_both_images_of_a_mirror`; Task 4, `test_a_layers_transform_and_mirror_move_its_fx_onto_the_map`.
2. **Sessions that come and go.** A tab that subscribes, unsubscribes and subscribes again; a tab that never moved to protocol 2; a bad `on`; the last zone stopping; nothing changing for a while; many tabs at once. Tests: Task 5, `test_subscribe_fx_is_acked_and_sends_fx_over_the_socket`, `test_a_session_gets_the_picture_once_then_nothing_while_nothing_changes`, `test_only_a_protocol_2_session_that_asked_gets_fx_and_turning_on_resends`, `test_fx_go_out_at_most_30_times_a_second`, `test_every_session_shares_one_message_until_a_frame_changes` and `test_a_message_that_cant_be_made_ends_the_channel_once_with_a_log`; Task 6's probe on this home's data.
3. **Moments between and around frames.** Now between two frames, before a ring's first frame, in a transition, after a crash: the newest frame at or before now, never a blend. Tests: Task 4, `test_frame_at_is_the_newest_frame_at_or_before_the_moment_never_a_blend`, `test_the_feed_reads_each_zones_fx_from_the_newest_frame_at_or_before_now`, `test_mid_transition_a_zone_draws_the_new_looks_fx_from_its_first_frame` and `test_an_effect_that_cant_say_what_it_draws_loses_its_fx_not_its_frame`.
4. **Colours the stage must not overstate.** A dimmed zone, a capped or evening look, a half-opacity layer, a black or NaN particle, a mask's soft edge. Tests: Task 4, `test_a_layers_opacity_dims_its_fx_whatever_its_blend`, `test_the_evening_and_the_cap_change_the_fx_as_they_change_the_leds` and `test_a_flash_and_trails_light_the_leds_alone`; Task 3, `test_in_home_weighs_particles_by_the_mask_where_they_land_and_drops_those_it_hides` and `test_a_mask_keeps_rings_and_planes_whole_while_it_shows_any_led`; Task 5, `test_colours_carry_the_zones_brightness_clipped_and_numbers_round_to_3_places` and `test_what_rounds_to_black_or_holds_a_nan_is_left_out_and_so_is_an_empty_zone`.
5. **The largest settings.** Every look that draws in space at its sliders' ends with every modifier on this home's LEDs, and two full zones encoded for every tab. Tests: Task 4, `test_what_a_zone_draws_in_space_keeps_its_frame_under_5_ms` (perf); Task 5, `test_a_zone_sends_its_newest_particles_up_to_the_cap` and `test_two_full_zones_encode_well_inside_a_frame` (perf).

---

## File Structure

New backend modules (paths under `src/dj_ledfx/`):

| File | Responsibility |
|---|---|
| `effects/fx.py` | What an effect draws in space: `Rings` and `rings()`, `Planes` and `planes()`, `Fx` (`empty`, `recoloured()`), `NO_RINGS`, `NO_PLANES`, `NO_FX` and `fx_joined()` |
| `web/fx.py` | The `fx` channel's message: `fx_message(shown)`, `FX_FPS`, `MAX_FX_PARTICLES`, `DECIMALS` |

Modified: `effects/base.py` (`Effect.in_space`) and `effects/particles.py` (`ParticleEffect.in_space`) in Task 1; `effects/{shockwave_shell,speaker_waves,ripples,scanner_plane,lighthouse_beam}.py` in Task 2; `zones/layer_view.py` (`LayerView.in_home`, `mask_weights_at`) in Task 3; `types.py` (`RenderedFrame.fx`), `effects/ring_buffer.py` (`frame_at`), `zones/runtime.py` and `zones/frames.py` (`ZoneFx`, `FrameFeed.fx`) in Task 4; `web/ws.py`, `web/state.py` (`ClientSubscription.fx`) and `web/app.py` (`app.state.fx_cache`) in Task 5; `CLAUDE.md` and `README.md` in Task 7. Nothing under `web/`.

New test files: `tests/effects/test_fx.py` (Task 1), `tests/effects/test_ring_buffer.py` and `tests/zones/test_runtime_fx.py` (Task 4), `tests/web/test_fx_message.py` and `tests/web/test_ws_fx.py` (Task 5). Tests added to: `tests/effects/test_particle_effects.py` (Task 1, the sweep: every particle effect draws its particles in space), the five field effects' test files (Task 2), `tests/zones/test_layer_view.py` (Task 3), `tests/zones/test_frames.py` and `tests/zones/test_runtime_perf.py` (Task 4).

---

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/m8-fx /home/anirudhlath/code/.worktrees/dj-ledfx/m8-fx origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/m8-fx
cd "$W"
test -f docs/superpowers/plans/2026-10-14-m8-effects-in-space.md && grep -q 'The `fx` payload' docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md && echo "plan and payload present"
test -f src/dj_ledfx/effects/particles.py && test -f src/dj_ledfx/effects/ripples.py && echo "M5 present"
test ! -f src/dj_ledfx/effects/fx.py && ! grep -q subscribe_fx src/dj_ledfx/web/ws.py && echo "no fx yet"
git log --oneline -5 origin/master
```

Expected: `plan and payload present`, `M5 present` and `no fx yet`. If one is missing, stop and tell the owner. The log shows whether F10 has merged; either is fine, since Task 8 rebases over it. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
(cd web && npm ci)
```

Without the `web` extra, the web tests skip silently and mypy reports dozens of extra errors. The web app's packages are for `npm run api:check` (Task 5) and Task 8's web gate.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tee /tmp/m8-baseline-mypy.txt | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm run api:check)
```

Write the results down: the test count (`2749 passed, 1 skipped, 79 deselected` on `57455a7`, with `972 warnings`), the format findings (none: `370 files already formatted`), mypy's error count (`Found 16 errors in 4 files (checked 166 source files)`), the perf run (`79 passed`) and `api types match`. Every gate compares with these. `ruff check` should be clean. If any isn't, tell the owner before starting.

---

### Task 1: The fx shapes and the hook

What an effect draws in space, and the one hook every effect has (ruling 1, ruling 2). A particle effect's hook hands over its last step's particles; every other effect keeps the default, None. Nothing calls the hook until Task 4.

**Files:**
- Create: `src/dj_ledfx/effects/fx.py`, `tests/effects/test_fx.py`
- Modify: `src/dj_ledfx/effects/base.py`, `src/dj_ledfx/effects/particles.py`, `tests/effects/test_particle_effects.py`

**Interfaces:**
- Consumes: `Particles`, `NO_PARTICLES` and `joined()` (`effects/particle_tools.py`); `RenderContext`, `LedSet`.
- Produces, in `effects.fx`:
  - `F32 = NDArray[np.float32]`; `Recolour = Callable[[F32], F32]`.
  - `Rings(centre: F32 (K, 3), radius: F32 (K,), width: F32 (K,), colour: F32 (K, 3), circle: NDArray[np.bool_] (K,))`, frozen, with `count`; `rings(centre, radius, width, colour, *, circle=False) -> Rings` (one value for all, or one each).
  - `Planes(point, normal, width, colour, ray)` (a ray of zeros: the whole plane), with `count`; `planes(point, normal, width, colour, ray=(0, 0, 0)) -> Planes`.
  - `NO_RINGS`, `NO_PLANES`; `Fx(particles=NO_PARTICLES, rings=NO_RINGS, planes=NO_PLANES)`, frozen, compared by identity, with `empty` and `recoloured(change: Recolour) -> Fx`; `NO_FX`; `fx_joined(parts: list[Fx]) -> Fx | None` (None for none, the one for one, else bottom layer first).
  - `Effect.in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None` (None); `ParticleEffect.in_space` (its `particles`, or None when it has none).

- [ ] **Step 1: Write the failing tests**

Create `tests/effects/test_fx.py`:

```python
"""What effects draw in space (engine spec §4.1, web spec §12.4's `fx` payload): the shapes,
and the hook every effect has."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import ROW, leds_at
from runtime_fakes import DotParticles

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.fx import NO_FX, Fx, fx_joined, planes, rings
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.effects.particles import ParticleEffect, drawn
from dj_ledfx.effects.registry import get_effect_classes

# The field effects that draw something in space (web spec §12.4: "What draws what").
FIELDS_IN_SPACE = {
    "shockwave_shell",
    "speaker_waves",
    "ripples",
    "scanner_plane",
    "lighthouse_beam",
}


def test_rings_and_planes_take_one_value_for_all_or_one_for_each() -> None:
    two = rings([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]], [1.0, 2.0], 0.5, (1.0, 0.5, 0.0))
    assert two.count == 2 and two.radius.tolist() == [1.0, 2.0] and two.width.tolist() == [0.5] * 2
    assert two.colour.tolist() == [[1.0, 0.5, 0.0]] * 2 and not two.circle.any()
    assert rings([0.0, 0.0, 0.0], 1.0, 0.1, (1.0, 1.0, 1.0), circle=True).circle.tolist() == [True]
    level = planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 1.0))
    assert level.count == 1 and level.ray.tolist() == [[0.0, 0.0, 0.0]]  # no ray: whole
    assert all(array.dtype == np.float32 for array in (two.centre, level.normal, level.ray))


def test_fx_join_bottom_layer_first_and_recolour_every_kind() -> None:
    low = Fx(particles=swarm([[0.0, 0.0, 1.0]], (1.0, 1.0, 1.0), 0.2))
    high = Fx(
        particles=swarm([[1.0, 0.0, 1.0]], (0.5, 0.5, 0.5), 0.3),
        rings=rings([0.0, 0.0, 0.0], 1.0, 0.1, (1.0, 0.0, 0.0)),
        planes=planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 0.0)),
    )
    both = fx_joined([low, high])
    assert both is not None and both.particles.pos[:, 0].tolist() == [0.0, 1.0]
    assert (both.rings.count, both.planes.count) == (1, 1)
    assert fx_joined([low]) is low and fx_joined([]) is None

    halved = both.recoloured(lambda colours: colours * np.float32(0.5))
    assert halved.particles.colour[:, 0].tolist() == [0.5, 0.25]
    assert halved.rings.colour.tolist() == [[0.5, 0.0, 0.0]]
    assert halved.planes.colour.tolist() == [[0.0, 0.5, 0.0]]
    assert both.particles.colour[0, 0] == 1.0  # a new Fx: the old one is as it was
    assert NO_FX.empty and not both.empty


def test_a_particle_effect_draws_its_last_steps_particles_in_space() -> None:
    effect, leds, ctx = DotParticles(x=2.0), leds_at(ROW), tempo_ctx(8.0)
    assert effect.in_space(ctx, leds) is None  # no step yet: no particles

    drawn(effect, ctx, leds)
    fx = effect.in_space(ctx, leds)

    assert fx is not None and fx.particles is effect.particles
    assert fx.particles.pos.tolist() == [[2.0, 0.0, 1.0]]
    assert (fx.rings.count, fx.planes.count) == (0, 0)


@pytest.mark.parametrize(
    "kind",
    sorted(
        name
        for name, cls in get_effect_classes().items()
        if name not in FIELDS_IN_SPACE and not issubclass(cls, ParticleEffect)
    ),
)
def test_other_field_strip_and_firmware_effects_draw_nothing_in_space(kind: str) -> None:
    effect: Effect = get_effect_classes()[kind]()
    assert effect.in_space(tempo_ctx(8.0), leds_at(ROW)) is None
```

In `tests/effects/test_particle_effects.py`, the sweep's every particle effect draws its particles in space, and a zone with no LEDs draws nothing there either:

```diff
diff --git a/tests/effects/test_particle_effects.py b/tests/effects/test_particle_effects.py
index dbea47d..3a5cab8 100644
--- a/tests/effects/test_particle_effects.py
+++ b/tests/effects/test_particle_effects.py
@@ -134,6 +134,16 @@ def test_a_zone_with_no_leds_draws_nothing(kind: str) -> None:
     effect = _effect(kind)
     frame = drawn(effect, tempo_ctx(START), leds_at([]))
     assert frame.shape == (0, 3) and effect.particles.count == 0
+    assert effect.in_space(tempo_ctx(START), leds_at([])) is None  # nothing in space either
+
+
+# M8: each particle look's particles reach the stage as they are, with no code of its own.
+@pytest.mark.parametrize("kind", PARTICLE_KINDS)
+def test_every_particle_effect_draws_its_particles_in_space(kind: str) -> None:
+    effect, leds, ctx = _effect(kind), seeded_ledset(), tempo_ctx(START)
+    drawn(effect, ctx, leds)
+    fx = effect.in_space(ctx, leds)
+    assert fx is not None and fx.particles is effect.particles and fx.particles.count > 0
 
 
 # Ceilings float32 stores a little over (2.45 as 2.4500000477): a lamp with its top LED exactly
```

- [ ] **Step 2: Run them, to see them fail**

```bash
uv run pytest tests/effects/test_fx.py tests/effects/test_particle_effects.py -q 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'dj_ledfx.effects.fx'`, collecting `test_fx.py`.

- [ ] **Step 3: Write the shapes and the hook**

Create `src/dj_ledfx/effects/fx.py`:

```python
"""What an effect draws in space (engine spec §4.1: "From M8, effects can also describe what
they draw in space"), for the web app's stage (web spec §7.4, and §12.4's `fx` payload).

An effect says it through one hook, `Effect.in_space(ctx, leds)`, None by default: a
particle effect's are its particles, and the field effects that draw a shell, a front, a
ripple or a plane say where it is. Positions and lengths are metres on the map's axes as
the effect sees them (a layer's view moves them; `LayerView.in_home()` maps them back),
colours linear 0..1 as the effect draws them, before the layer's opacity, the look's
modifiers and the zone's brightness.

`width` is how thick a ring or a plane is drawn: its light's full width where it falls to
e^-1, twice the `band()` width its effect lights the LEDs with.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dj_ledfx.effects.particle_tools import NO_PARTICLES, Particles, joined

F32 = NDArray[np.float32]
Recolour = Callable[[F32], F32]  # (K, 3) colours to (K, 3) colours, in an array of its own


def _rows(values: ArrayLike, count: int, width: int) -> F32:
    """One row of `width` floats for each of `count` items: given for each, or one for all."""
    shape = (count, width) if width > 1 else (count,)
    return np.broadcast_to(np.asarray(values, dtype=np.float32), shape).astype(np.float32)


@dataclass(frozen=True, eq=False, slots=True)
class Rings:
    """Shells and level rings of light: each one's centre, radius, width and colour, and
    whether it's a level circle (its axis z) rather than a sphere's shell."""

    centre: F32  # (K, 3)
    radius: F32  # (K,)
    width: F32  # (K,)
    colour: F32  # (K, 3)
    circle: NDArray[np.bool_]  # (K,)

    @property
    def count(self) -> int:
        return int(self.centre.shape[0])


def rings(
    centre: ArrayLike,
    radius: ArrayLike,
    width: ArrayLike,
    colour: ArrayLike,
    *,
    circle: bool = False,
) -> Rings:
    """Rings from centres (K, 3) and each one's (or one for all) radius, width and colour."""
    where = np.array(centre, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    return Rings(
        where,
        _rows(radius, count, 1),
        _rows(width, count, 1),
        _rows(colour, count, 3),
        np.full(count, circle, dtype=np.bool_),
    )


@dataclass(frozen=True, eq=False, slots=True)
class Planes:
    """Planes of light: a point on each, its unit normal, width and colour, and its ray, a
    direction in the plane: the plane is the half on that side of the point (a beam). A ray
    of zeros: the whole plane."""

    point: F32  # (K, 3)
    normal: F32  # (K, 3)
    width: F32  # (K,)
    colour: F32  # (K, 3)
    ray: F32  # (K, 3)

    @property
    def count(self) -> int:
        return int(self.point.shape[0])


def planes(
    point: ArrayLike,
    normal: ArrayLike,
    width: ArrayLike,
    colour: ArrayLike,
    ray: ArrayLike = (0.0, 0.0, 0.0),
) -> Planes:
    """Planes from points (K, 3) and each one's (or one for all) normal, width, colour and
    ray."""
    where = np.array(point, dtype=np.float32).reshape(-1, 3)
    count = len(where)
    return Planes(
        where,
        _rows(normal, count, 3),
        _rows(width, count, 1),
        _rows(colour, count, 3),
        _rows(ray, count, 3),
    )


NO_RINGS = rings(np.zeros((0, 3)), 0.0, 0.0, (0.0, 0.0, 0.0))
NO_PLANES = planes(np.zeros((0, 3)), (0.0, 0.0, 1.0), 0.0, (0.0, 0.0, 0.0))


@dataclass(frozen=True, eq=False, slots=True)
class Fx:
    """What one layer, or a zone's frame, draws in space."""

    particles: Particles = NO_PARTICLES
    rings: Rings = NO_RINGS
    planes: Planes = NO_PLANES

    @property
    def empty(self) -> bool:
        return self.particles.count == 0 and self.rings.count == 0 and self.planes.count == 0

    def recoloured(self, change: Recolour) -> Fx:
        """Every colour changed by `change` (a layer's opacity, the evening, the cap)."""
        particles, ring, plane = self.particles, self.rings, self.planes
        return Fx(
            Particles(particles.pos, change(particles.colour), particles.radius),
            Rings(ring.centre, ring.radius, ring.width, change(ring.colour), ring.circle),
            Planes(plane.point, plane.normal, plane.width, change(plane.colour), plane.ray),
        )


NO_FX = Fx()


def fx_joined(parts: list[Fx]) -> Fx | None:
    """Several layers' fx as one, bottom layer first; None for none."""
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return Fx(
        joined(*(part.particles for part in parts)),
        Rings(
            *(
                np.concatenate([getattr(part.rings, name) for part in parts])
                for name in ("centre", "radius", "width", "colour", "circle")
            )
        ),
        Planes(
            *(
                np.concatenate([getattr(part.planes, name) for part in parts])
                for name in ("point", "normal", "width", "colour", "ray")
            )
        ),
    )
```

In `src/dj_ledfx/effects/base.py`, the hook:

```diff
diff --git a/src/dj_ledfx/effects/base.py b/src/dj_ledfx/effects/base.py
index df08123..0e0acc4 100644
--- a/src/dj_ledfx/effects/base.py
+++ b/src/dj_ledfx/effects/base.py
@@ -16,6 +16,8 @@ from dj_ledfx.effects.params import EffectParam, check_setting
 from dj_ledfx.types import BeatContext
 
 if TYPE_CHECKING:
+    from dj_ledfx.effects.context import RenderContext
+    from dj_ledfx.effects.fx import Fx
     from dj_ledfx.effects.ledset import LedSet
     from dj_ledfx.types import FloatRGB
 
@@ -76,6 +78,12 @@ class Effect(ABC):  # noqa: B024
     def reseed(self, seed: int) -> None:  # noqa: B027
         """Make the effect's randomness repeatable. Default: it has none."""
 
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
+        """What the effect's last frame on these LEDs, at ctx's moment, draws in space, for
+        the web app's stage (effects/fx.py); None: nothing to draw, the default. Called
+        right after the frame, with the same moment and LEDs."""
+        return None
+
 
 class ParamSettings(Effect, register=False):
     """An effect that keeps its settings in one dict: the field effects (ParamField) and
```

In `src/dj_ledfx/effects/particles.py`, a particle effect's:

```diff
diff --git a/src/dj_ledfx/effects/particles.py b/src/dj_ledfx/effects/particles.py
index c2fe486..917f95c 100644
--- a/src/dj_ledfx/effects/particles.py
+++ b/src/dj_ledfx/effects/particles.py
@@ -15,6 +15,7 @@ from abc import abstractmethod
 from typing import TYPE_CHECKING
 
 from dj_ledfx.effects.base import Effect, ParamSettings
+from dj_ledfx.effects.fx import Fx
 from dj_ledfx.effects.particle_tools import NO_PARTICLES, Among, Ground, Particles, lit
 
 if TYPE_CHECKING:
@@ -47,6 +48,11 @@ class ParticleEffect(Effect):
     def particles(self) -> Particles:
         """The particles of the last step, oldest first."""
 
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
+        """The last step's particles: where each is, its colour and its radius."""
+        particles = self.particles
+        return Fx(particles=particles) if particles.count else None
+
 
 class ParamParticles(ParamSettings, ParticleEffect):
     """A particle effect that keeps its settings in one dict (ParamSettings) and its
```

- [ ] **Step 4: Run the task's tests**

```bash
uv run pytest tests/effects/test_fx.py tests/effects/test_particle_effects.py -q 2>&1 | tail -1
```

Expected: `175 passed, 11 deselected`.

- [ ] **Step 5: The gate**

```bash
uv run ruff format src/dj_ledfx/effects tests/effects && uv run ruff check --fix src/dj_ledfx/effects tests/effects
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `2781 passed, 1 skipped, 79 deselected` (Before Task 1's 2749 and this task's 32), `372 files already formatted`, `Found 16 errors in 4 files (checked 167 source files)`, and `79 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/fx.py src/dj_ledfx/effects/base.py src/dj_ledfx/effects/particles.py tests/effects/test_fx.py tests/effects/test_particle_effects.py
git commit -m "feat(effects): what an effect draws in space, and its particles"
```

---

### Task 2: The five field effects in space

Shockwave's shell, Speaker waves' kick fronts, Ripples' drops, the Scanner's plane and Shockwave's beam, each where its LEDs light it (ruling 3), its `width` twice its `band()` width (ruling 2). Ripples' and Speaker waves' render code moves into helpers their hooks share (`_alive()`, `_points()`, `_reach()`), with no change to what they render: their existing tests pin that.

**Files:**
- Modify: `src/dj_ledfx/effects/{shockwave_shell,speaker_waves,ripples,scanner_plane,lighthouse_beam}.py`, and their tests `tests/effects/test_{shockwave_shell,speaker_waves,ripples,scanner_plane,lighthouse_beam}.py`

**Interfaces:**
- Consumes: Task 1's `Fx`, `rings()`, `planes()`; `anchor_or_centre()`, `band()` (`effects/field_tools.py`), `palette_at()`, `raised_cosine()`.
- Produces: `ShockwaveShell.in_space`, `SpeakerWaves.in_space`, `Ripples.in_space` (None while no drop is alive), `ScannerPlane.in_space`, `LighthouseBeam.in_space`; `Ripples._alive(ctx, leds)`, `SpeakerWaves._points(leds)`, `speaker_waves._reach(points, leds)`, `scanner_plane._height(ctx)`, `ShockwaveShell._crest(ctx)`.

- [ ] **Step 1: Write the failing tests**

```diff
diff --git a/tests/effects/test_shockwave_shell.py b/tests/effects/test_shockwave_shell.py
index 7f7143c..3a45d2d 100644
--- a/tests/effects/test_shockwave_shell.py
+++ b/tests/effects/test_shockwave_shell.py
@@ -1,5 +1,6 @@
 from __future__ import annotations
 
+import numpy as np
 from conftest import tempo_ctx
 from map_home import leds_at
 
@@ -27,3 +28,19 @@ def test_without_its_anchor_the_shell_starts_in_the_middle() -> None:
     frame = ShockwaveShell(anchor="gone").render(tempo_ctx(4.0), leds)
 
     assert frame.sum(axis=1).argmax() == 1
+
+
+# M8: the shell in space is where it lights the LEDs, in the colour its crest lights them.
+def test_the_shell_is_drawn_as_a_sphere_round_the_anchor_out_to_its_front() -> None:
+    effect = ShockwaveShell(anchor="tv", reach_m=6.0, shell_m=0.6)
+    leds = leds_at(FROM_THE_TV, anchors=TV)
+    ctx = tempo_ctx(8.0 + 1 / 3)
+
+    frame = effect.render(ctx, leds)
+    fx = effect.in_space(ctx, leds)
+
+    assert fx.particles.count == 0 and fx.planes.count == 0
+    [centre], [radius], [width] = fx.rings.centre, fx.rings.radius, fx.rings.width
+    assert np.allclose(centre, TV["tv"]) and not fx.rings.circle[0]  # a sphere's shell
+    assert np.isclose(radius, 2.0) and np.isclose(width, 1.2)  # 6 m a beat; twice 0.6 m
+    assert np.allclose(fx.rings.colour[0], frame[2])  # the LED 2 m out is on the crest
```

```diff
diff --git a/tests/effects/test_speaker_waves.py b/tests/effects/test_speaker_waves.py
index a22c493..aa1493c 100644
--- a/tests/effects/test_speaker_waves.py
+++ b/tests/effects/test_speaker_waves.py
@@ -104,3 +104,19 @@ def test_frame_after_frame_it_draws_what_a_new_one_draws() -> None:
         fresh.reseed(seed)
         ctx = tempo_ctx(4.0 + k / 30)
         assert np.array_equal(effect.render(ctx, leds), fresh.render(ctx, leds)), k
+
+
+# M8: each kick's front in space is a sphere round a speaker, as far out as it lights the
+# LEDs, in the colour it lights them; the snares and hats stay on the LEDs.
+def test_each_kick_front_is_drawn_as_a_sphere_round_its_speaker() -> None:
+    effect = SpeakerWaves(anchor="speakers")
+    leds = leds_at(BETWEEN, anchor_points=PAIR)
+    ctx = tempo_ctx(4.25)  # each front 1 m out, as the first test says
+
+    frame = effect.render(ctx, leds)
+    fx = effect.in_space(ctx, leds)
+
+    assert np.allclose(fx.rings.centre, PAIR["speakers"]) and not fx.rings.circle.any()
+    assert np.allclose(fx.rings.radius, 1.0) and np.allclose(fx.rings.width, 0.8)
+    assert np.allclose(fx.rings.colour, frame[0])  # the LED 1 m from a speaker: on its crest
+    assert fx.particles.count == 0 and fx.planes.count == 0
```

```diff
diff --git a/tests/effects/test_ripples.py b/tests/effects/test_ripples.py
index e4d97ca..23b19e0 100644
--- a/tests/effects/test_ripples.py
+++ b/tests/effects/test_ripples.py
@@ -8,7 +8,7 @@ import pytest
 from conftest import render_ctx
 from map_home import leds_at, seeded_ledset
 
-from dj_ledfx.effects.color import palette_float
+from dj_ledfx.effects.color import palette_at, palette_float
 from dj_ledfx.effects.ripples import LIFE_FADES, RIPPLE_PALETTE, Ripples
 
 ACROSS_THE_ROOM = [(x, 2.0, 0.5) for x in np.linspace(0.0, 6.0, 13)]
@@ -72,3 +72,24 @@ def test_ripples_at_their_densest_render_in_under_5_ms() -> None:
         effect.render(render_ctx(t=1000.0 + step / 60), leds)
         durations.append(time.perf_counter() - started)
     assert statistics.median(durations) < 0.005
+
+
+# M8: each drop still alive is drawn as a level ring where it landed, as far out as it has
+# travelled, in its crest's colour; gone drops aren't.
+def test_each_live_drop_is_drawn_as_a_level_ring_where_it_landed() -> None:
+    effect, leds = _ripples(), leds_at(ACROSS_THE_ROOM)
+    when, where = effect.drop(0, leds)
+    palette = palette_float(list(RIPPLE_PALETTE))
+
+    for age in (0.5, 2.0):
+        ctx = render_ctx(when + age)
+        effect.render(ctx, leds)
+        fx = effect.in_space(ctx, leds)
+        assert fx is not None and fx.rings.count == 1 and fx.rings.circle.all()
+        assert np.allclose(fx.rings.centre[0], where) and np.isclose(fx.rings.radius[0], age)
+        crest = palette_at(palette, np.array([np.exp(-age / 3.0)], dtype=np.float32)) * 0.9
+        assert np.allclose(fx.rings.colour, crest) and np.isclose(fx.rings.width[0], 0.7)
+
+    gone = render_ctx(when + LIFE_FADES * 3.0 + 0.1)  # past its life, before the next drop
+    assert effect.drop(1, leds)[0] > gone.t
+    assert effect.in_space(gone, leds) is None
```

```diff
diff --git a/tests/effects/test_scanner_plane.py b/tests/effects/test_scanner_plane.py
index 2ef844c..de713f1 100644
--- a/tests/effects/test_scanner_plane.py
+++ b/tests/effects/test_scanner_plane.py
@@ -1,5 +1,6 @@
 from __future__ import annotations
 
+import numpy as np
 from conftest import tempo_ctx
 from map_home import leds_at
 
@@ -18,3 +19,24 @@ def test_the_plane_sweeps_up_and_back_every_two_beats() -> None:
     ]
 
     assert lit == [0, 2, 4, 2, 0]
+
+
+# M8: the plane in space is level at the height it lights, in its colour, as thick as its
+# band; with no map, between the zone's lowest and highest LEDs.
+def test_the_plane_is_drawn_level_at_the_height_it_lights() -> None:
+    effect = ScannerPlane(width=0.12)
+    raised = [(x, y, z + 1.0) for x, y, z in FLOOR_TO_CEILING]  # 1 m to 4 m up
+    for points, ceiling, low, high in (
+        (FLOOR_TO_CEILING, 3.0, 0.0, 3.0),
+        (raised, None, 1.0, 4.0),
+    ):
+        leds = leds_at(points, ceiling=ceiling)
+        ctx = tempo_ctx(0.5)  # half-way up
+
+        frame = effect.render(ctx, leds)
+        fx = effect.in_space(ctx, leds)
+
+        [point], [normal], [width] = fx.planes.point, fx.planes.normal, fx.planes.width
+        assert np.isclose(point[2], (low + high) / 2) and normal.tolist() == [0.0, 0.0, 1.0]
+        assert np.isclose(width, 2 * 0.12 * (high - low)) and not fx.planes.ray.any()
+        assert np.allclose(fx.planes.colour[0], frame[2])  # the middle LED is lit full
```

```diff
diff --git a/tests/effects/test_lighthouse_beam.py b/tests/effects/test_lighthouse_beam.py
index 08ec5ed..7e571e4 100644
--- a/tests/effects/test_lighthouse_beam.py
+++ b/tests/effects/test_lighthouse_beam.py
@@ -22,3 +22,21 @@ def test_the_beam_turns_once_a_bar() -> None:
 
         assert frame.sum(axis=1).argmax() == beat
         assert np.allclose(frame[(beat + 2) % 4], 0.0)  # dark behind it
+
+
+# M8: the beam in space is the upright half-plane from the anchor towards the LED it lights.
+def test_the_beam_is_drawn_as_a_half_plane_from_the_anchor_towards_its_bearing() -> None:
+    effect = LighthouseBeam(anchor="tv", width_deg=20.0)
+    leds = leds_at(AROUND, anchors=TV)
+
+    for beat in range(4):
+        ctx = tempo_ctx(4.0 + beat)
+        frame = effect.render(ctx, leds)
+        fx = effect.in_space(ctx, leds)
+
+        [point], [ray], [normal] = fx.planes.point, fx.planes.ray, fx.planes.normal
+        assert np.allclose(point, TV["tv"])
+        assert np.allclose(ray, AROUND[beat] - np.array(TV["tv"]), atol=1e-6)  # towards it
+        assert np.isclose(np.dot(ray, normal), 0.0) and normal[2] == 0.0  # upright
+        assert np.isclose(fx.planes.width[0], math.radians(20.0))
+        assert np.allclose(fx.planes.colour[0], frame[beat])
```

- [ ] **Step 2: Run them, to see them fail**

```bash
uv run pytest tests/effects/test_shockwave_shell.py tests/effects/test_speaker_waves.py tests/effects/test_ripples.py tests/effects/test_scanner_plane.py tests/effects/test_lighthouse_beam.py -q 2>&1 | tail -1
```

Expected: `5 failed, 12 passed, 1 deselected`: each new test meets the default hook's None (`AttributeError: 'NoneType' object has no attribute …`, and Ripples' `assert None is not None`).

- [ ] **Step 3: Write the five hooks**

```diff
diff --git a/src/dj_ledfx/effects/shockwave_shell.py b/src/dj_ledfx/effects/shockwave_shell.py
index ed09eb2..dbf8095 100644
--- a/src/dj_ledfx/effects/shockwave_shell.py
+++ b/src/dj_ledfx/effects/shockwave_shell.py
@@ -11,6 +11,7 @@ from numpy.typing import NDArray
 from dj_ledfx.effects.color import palette_at, palette_float
 from dj_ledfx.effects.field import ParamField
 from dj_ledfx.effects.field_tools import anchor_or_centre, band, distances
+from dj_ledfx.effects.fx import Fx, rings
 from dj_ledfx.effects.params import EffectParam, anchor_param, level_param
 
 if TYPE_CHECKING:
@@ -54,10 +55,29 @@ class ShockwaveShell(ParamField):
         away = self._per_leds(leds, self._away)
         front = float(values["reach_m"]) * ctx.beat_phase
         glow = band(away, front, float(values["shell_m"]))
-        glow *= np.float32((1.0 - ctx.beat_phase) ** 2)
+        glow *= np.float32(self._crest(ctx))
         frame = palette_at(self._ramp, glow)  # an array of its own, float32
         frame *= np.float32(values["level"])
         return frame
 
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx:
+        """The shell: a sphere round the anchor, as far out as its front, in its crest's
+        colour."""
+        values = self._values
+        crest = palette_at(self._ramp, np.array([self._crest(ctx)], dtype=np.float32))
+        crest *= np.float32(values["level"])
+        shell = rings(
+            anchor_or_centre(leds, values["anchor"]),
+            float(values["reach_m"]) * ctx.beat_phase,
+            2.0 * float(values["shell_m"]),
+            crest,
+        )
+        return Fx(rings=shell)
+
+    @staticmethod
+    def _crest(ctx: RenderContext) -> float:
+        """How bright the shell's crest is: full on the beat, fading as it spreads."""
+        return (1.0 - ctx.beat_phase) ** 2
+
     def _away(self, leds: LedSet) -> NDArray[np.float32]:
         return distances(leds, anchor_or_centre(leds, self._values["anchor"]))
```

```diff
diff --git a/src/dj_ledfx/effects/speaker_waves.py b/src/dj_ledfx/effects/speaker_waves.py
index b9c5cf7..6f1616d 100644
--- a/src/dj_ledfx/effects/speaker_waves.py
+++ b/src/dj_ledfx/effects/speaker_waves.py
@@ -23,6 +23,7 @@ from dj_ledfx.effects.field_tools import (
     height01,
     smoothstep,
 )
+from dj_ledfx.effects.fx import Fx, rings
 from dj_ledfx.effects.params import EffectParam, anchor_param, level_param
 
 if TYPE_CHECKING:
@@ -94,6 +95,15 @@ class SpeakerWaves(ParamField):
         out *= np.float32(values["level"])
         return out
 
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx:
+        """Each kick's front: a sphere round each of the anchor's points, as far out as the
+        front, in the colour its crest lights an LED. The snares and hats stay on the LEDs."""
+        points = self._points(leds)
+        front = _reach(points, leds) * ctx.beat_phase / ACROSS_BY
+        crest = self._rest + (self._kick - self._rest) * np.float32(1.0 - ctx.beat_phase)
+        crest *= np.float32(self._values["level"])
+        return Fx(rings=rings(points, front, 2.0 * WAVE_M, crest))
+
     def _sparkles(self, beat_index: int, count: int, share: float) -> F32:
         """Which LEDs this beat's hi-hat lights (1) and leaves (0): drawn once a beat, from
         the seed and the beat alone, and kept for the beat's frames."""
@@ -107,16 +117,27 @@ class SpeakerWaves(ParamField):
         """Each LED's distance from each of the anchor's points (k, n), from their middle,
         how high up it is (0 low, 1 high), and the kick's reach: from the points to the
         farthest corner of the zone's bounds."""
+        points = self._points(leds)
+        each = np.stack([distances(leds, point) for point in points])
+        middle = distances(leds, points.mean(axis=0).astype(np.float32))
+        high = smoothstep(HIGH_FROM, HIGH_TO, height01(leds))
+        return each, middle, high, _reach(points, leds)
+
+    def _points(self, leds: LedSet) -> F32:
+        """Where the waves start: each of the anchor's points, or the zone's middle, (k, 3)."""
         anchor = self._values["anchor"]
         points = leds.space.anchor_points.get(anchor) if anchor else None
         if points is None or len(points) == 0:
             points = anchor_or_centre(leds, anchor)[None, :]
-        each = np.stack([distances(leds, point) for point in points])
-        middle = distances(leds, points.mean(axis=0).astype(np.float32))
-        low, top = leds.bounds
-        farthest = np.maximum(abs(points - low), abs(points - top))  # to each point's far corner
-        reach = float(np.linalg.norm(farthest, axis=1).max())
-        return each, middle, smoothstep(HIGH_FROM, HIGH_TO, height01(leds)), reach
+        return points
+
+
+def _reach(points: F32, leds: LedSet) -> float:
+    """How far a kick's front goes: from the points to the farthest corner of the zone's
+    bounds."""
+    low, top = leds.bounds
+    farthest = np.maximum(abs(points - low), abs(points - top))  # to each point's far corner
+    return float(np.linalg.norm(farthest, axis=1).max())
 
 
 def _towards(out: FloatRGB, colour: F32, amount: F32) -> None:
```

```diff
diff --git a/src/dj_ledfx/effects/ripples.py b/src/dj_ledfx/effects/ripples.py
index cd101ef..eceeef2 100644
--- a/src/dj_ledfx/effects/ripples.py
+++ b/src/dj_ledfx/effects/ripples.py
@@ -18,6 +18,7 @@ from numpy.typing import NDArray
 from dj_ledfx.effects.color import palette_at
 from dj_ledfx.effects.field import ParamField
 from dj_ledfx.effects.field_tools import band, distances
+from dj_ledfx.effects.fx import Fx, rings
 from dj_ledfx.effects.params import EffectParam, level_param
 
 if TYPE_CHECKING:
@@ -95,21 +96,48 @@ class Ripples(ParamField):
         return when, where
 
     def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
-        values = self._values
-        interval, fade = self._interval(), float(values["fade_s"])
-        speed, life = float(values["speed"]), LIFE_FADES * fade
+        wave = np.zeros(leds.count, dtype=np.float32)
+        for where, radius, strength in self._alive(ctx, leds):
+            ring = band(distances(leds, where), radius, RING_WIDTH_M)
+            ring *= np.float32(strength)
+            np.maximum(wave, ring, out=wave)
+        colours = palette_at(self._palette, wave)
+        return (colours * np.float32(self._values["level"])).astype(np.float32)
+
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
+        """Each live drop's ring: a level circle on the floor where it landed, as far out as
+        it has travelled, in the colour its crest lights an LED."""
+        alive = self._alive(ctx, leds)
+        if not alive:
+            return None
+        strength = np.array([each for _, _, each in alive], dtype=np.float32)
+        crest = palette_at(self._palette, strength) * np.float32(self._values["level"])
+        return Fx(
+            rings=rings(
+                [where for where, _, _ in alive],
+                [radius for _, radius, _ in alive],
+                2.0 * RING_WIDTH_M,
+                crest,
+                circle=True,
+            )
+        )
+
+    def _alive(
+        self, ctx: RenderContext, leds: LedSet
+    ) -> list[tuple[NDArray[np.float32], float, float]]:
+        """Each drop still alive at ctx's moment: where it landed, how far its ring has
+        travelled, and how strong it still is (1 as it lands, fading). Draws of drops gone
+        are let go."""
+        interval, fade = self._interval(), float(self._values["fade_s"])
+        speed, life = float(self._values["speed"]), LIFE_FADES * fade
         first = math.floor((ctx.t - life) / interval) - 1  # the oldest drop that may be alive
         last = math.floor(ctx.t / interval)  # no later drop has landed yet
         for gone in [k for k in self._draws if k < first]:
             del self._draws[gone]
-        wave = np.zeros(leds.count, dtype=np.float32)
+        alive = []
         for k in range(first, last + 1):
             when, where = self.drop(k, leds)
             age = ctx.t - when
-            if not 0.0 <= age <= life:
-                continue
-            ring = band(distances(leds, where), speed * age, RING_WIDTH_M)
-            ring *= np.float32(math.exp(-age / fade))
-            np.maximum(wave, ring, out=wave)
-        colours = palette_at(self._palette, wave)
-        return (colours * np.float32(values["level"])).astype(np.float32)
+            if 0.0 <= age <= life:
+                alive.append((where, speed * age, math.exp(-age / fade)))
+        return alive
```

```diff
diff --git a/src/dj_ledfx/effects/scanner_plane.py b/src/dj_ledfx/effects/scanner_plane.py
index c2b67c5..a579d8c 100644
--- a/src/dj_ledfx/effects/scanner_plane.py
+++ b/src/dj_ledfx/effects/scanner_plane.py
@@ -12,6 +12,7 @@ from dj_ledfx.effects.color import palette_at, palette_float
 from dj_ledfx.effects.easing import raised_cosine
 from dj_ledfx.effects.field import ParamField
 from dj_ledfx.effects.field_tools import band, height01
+from dj_ledfx.effects.fx import Fx, planes
 from dj_ledfx.effects.params import EffectParam, level_param
 
 if TYPE_CHECKING:
@@ -49,8 +50,28 @@ class ScannerPlane(ParamField):
     def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
         values = self._values
         heights: NDArray[np.float32] = self._per_leds(leds, height01)
-        cycle = ctx.beats % 2.0 / 2.0  # up in one beat, down in the next
-        glow = band(heights, raised_cosine(cycle), float(values["width"]))
+        glow = band(heights, _height(ctx), float(values["width"]))
         frame = palette_at(self._ramp, glow)  # an array of its own, float32
         frame *= np.float32(values["level"])
         return frame
+
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx:
+        """The plane: level, at its height between the floor and the ceiling (with no
+        ceiling, the zone's bottom and top, as height01 has them), in its own colour."""
+        ceiling = leds.space.ceiling
+        if ceiling is None or ceiling <= 0.0:
+            low, high = (float(corner[2]) for corner in leds.bounds)
+        else:
+            low, high = 0.0, ceiling
+        span = high - low
+        point = (*leds.centre[:2], low + _height(ctx) * span)
+        colour = self._ramp[-1] * np.float32(self._values["level"])
+        return Fx(
+            planes=planes(point, (0.0, 0.0, 1.0), 2.0 * self._values["width"] * span, colour)
+        )
+
+
+def _height(ctx: RenderContext) -> float:
+    """Where the plane is, 0 on the floor to 1 at the ceiling: up in one beat, down in the
+    next."""
+    return raised_cosine(ctx.beats % 2.0 / 2.0)
```

```diff
diff --git a/src/dj_ledfx/effects/lighthouse_beam.py b/src/dj_ledfx/effects/lighthouse_beam.py
index b97a4cf..880f4a3 100644
--- a/src/dj_ledfx/effects/lighthouse_beam.py
+++ b/src/dj_ledfx/effects/lighthouse_beam.py
@@ -3,6 +3,7 @@ once a bar, on the floor plane; dark elsewhere, so it adds onto the layer below.
 
 from __future__ import annotations
 
+import math
 from typing import TYPE_CHECKING
 
 import numpy as np
@@ -10,7 +11,8 @@ from numpy.typing import NDArray
 
 from dj_ledfx.effects.color import palette_float
 from dj_ledfx.effects.field import ParamField
-from dj_ledfx.effects.field_tools import band, bearing
+from dj_ledfx.effects.field_tools import anchor_or_centre, band, bearing
+from dj_ledfx.effects.fx import Fx, planes
 from dj_ledfx.effects.params import EffectParam, anchor_param, level_param
 
 if TYPE_CHECKING:
@@ -55,5 +57,16 @@ class LighthouseBeam(ParamField):
         frame: FloatRGB = self._colour * beam[:, None]  # float32 times float32
         return frame
 
+    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx:
+        """The beam: the upright half-plane from the anchor towards the bar's bearing, as
+        wide as the beam is 1 m from the anchor, in its colour."""
+        turn = 2.0 * math.pi * ctx.bar_phase
+        towards = (math.cos(turn), math.sin(turn), 0.0)
+        across = (-math.sin(turn), math.cos(turn), 0.0)
+        width = math.radians(float(self._values["width_deg"]))  # e^-1 either side: ±width/2
+        colour = self._colour * np.float32(self._values["level"])
+        point = anchor_or_centre(leds, self._values["anchor"])
+        return Fx(planes=planes(point, across, width, colour, ray=towards))
+
     def _bearing(self, leds: LedSet) -> NDArray[np.float64]:
         return bearing(leds, self._values["anchor"])
```

- [ ] **Step 4: Run the task's tests**

```bash
uv run pytest tests/effects/test_shockwave_shell.py tests/effects/test_speaker_waves.py tests/effects/test_ripples.py tests/effects/test_scanner_plane.py tests/effects/test_lighthouse_beam.py tests/effects/test_fx.py -q 2>&1 | tail -1
```

Expected: `38 passed, 1 deselected`. `test_fx.py`'s parametrised test still leaves the five out (`FIELDS_IN_SPACE`).

- [ ] **Step 5: The gate**

```bash
uv run ruff format src/dj_ledfx/effects tests/effects && uv run ruff check --fix src/dj_ledfx/effects tests/effects
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1
```

Expected: `2786 passed, 1 skipped, 79 deselected`, `372 files already formatted`, `Found 16 errors in 4 files (checked 167 source files)`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects tests/effects
git commit -m "feat(effects): shells, fronts, ripples and planes in space"
```

---

### Task 3: A layer's fx on the map

What a layer's effect draws, moved from the effect's space onto the map through the layer's view (ruling 5), and weighed by its mask (ruling 6). `mask_weights_at()` weighs any places, a particle's as well as an LED's; `mask_weights()` becomes its LEDs' case. `LayerView` keeps the zone's own LEDs and the layer's modifiers, which `in_home` needs; the runtime builds it as before.

**Files:**
- Modify: `src/dj_ledfx/zones/layer_view.py`, `tests/zones/test_layer_view.py`

**Interfaces:**
- Consumes: Task 1's `Fx`, `Rings`, `Planes`, `NO_RINGS`, `NO_PLANES`; `Particles.pick()`; `rotation_matrix()` (`home/shapes.py`).
- Produces: `LayerView(leds, weight=None, zone=None, mask=None, mirror=None, transform=None)` with `in_home(fx: Fx) -> Fx`; `mask_weights_at(mask, pos: NDArray[np.float32], leds: LedSet) -> NDArray[np.float32]`.

- [ ] **Step 1: Write the failing tests**

```diff
diff --git a/tests/zones/test_layer_view.py b/tests/zones/test_layer_view.py
index ba9da5c..e5557d7 100644
--- a/tests/zones/test_layer_view.py
+++ b/tests/zones/test_layer_view.py
@@ -7,6 +7,8 @@ import numpy as np
 import pytest
 from map_home import DESK_CORNER, leds_at, tiny_space
 
+from dj_ledfx.effects.fx import Fx, planes, rings
+from dj_ledfx.effects.particle_tools import swarm
 from dj_ledfx.looks.model import (
     AnchorMask,
     HeightMask,
@@ -16,7 +18,13 @@ from dj_ledfx.looks.model import (
     SubZoneMask,
     Transform,
 )
-from dj_ledfx.zones.layer_view import layer_view, mask_weights, mirrored, transformed
+from dj_ledfx.zones.layer_view import (
+    layer_view,
+    mask_weights,
+    mask_weights_at,
+    mirrored,
+    transformed,
+)
 
 
 def test_a_height_mask_shows_the_layer_between_its_heights_with_a_soft_edge() -> None:
@@ -94,3 +102,140 @@ def test_a_moved_view_keeps_the_zones_bounds_and_weighs_by_where_the_leds_are()
     assert np.allclose(view.leds.pos[:, 0], [1.0, 1.0])  # the east LED sees the west side
     assert all(np.allclose(a, b) for a, b in zip(view.leds.bounds, leds.bounds, strict=True))
     assert view.weight is not None and view.weight.tolist() == [[1.0], [0.0]]  # where it is
+
+
+# What a layer draws in space, on the map (M8): in_home().
+
+
+def _dots(*places: list[float]) -> Fx:
+    return Fx(particles=swarm(places, (1.0, 0.5, 0.25), 0.2))
+
+
+def test_in_home_undoes_the_transform_so_what_an_led_sees_lands_on_the_led() -> None:
+    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 3.0, 2.0], [4.0, 2.0, 0.5]], space=tiny_space())
+    layer = Layer(
+        id="a",
+        name="A",
+        type="field",
+        kind="breathe",
+        transform=Transform(offset=(0.5, -1.0, 0.25), rotate_deg=30.0, scale=1.5),
+    )
+    view = layer_view(layer, leds)
+    seen = view.leds.pos.tolist()  # where in the effect's space each LED looks
+
+    home = view.in_home(Fx(particles=swarm(seen, (1.0, 1.0, 1.0), 0.2)))
+
+    assert np.allclose(home.particles.pos, leds.pos, atol=1e-5)
+    assert np.allclose(home.particles.radius, 0.3)  # grown by the scale
+
+
+def test_in_home_turns_a_planes_directions_and_grows_lengths_by_the_scale() -> None:
+    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 3.0, 1.0]], space=tiny_space())
+    layer = Layer(
+        id="a",
+        name="A",
+        type="field",
+        kind="breathe",
+        transform=Transform(offset=(1.0, 0.0, 0.0), rotate_deg=90.0, scale=2.0),
+    )
+    view = layer_view(layer, leds)
+    at, ray, normal = [3.0, 2.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]
+    fx = Fx(
+        rings=rings(at, 1.0, 0.1, (1.0, 0.0, 0.0)),
+        planes=planes(at, normal, 0.2, (0.0, 1.0, 0.0), ray=ray),
+    )
+    # Where the map shows the effect's point, and the points a metre along its ray and
+    # its normal.
+    along = view.in_home(_dots(at, list(np.add(at, ray)), list(np.add(at, normal))))
+
+    home = view.in_home(fx)
+
+    there, ahead, up = along.particles.pos.astype(np.float64)
+    assert np.allclose(home.rings.centre, [there]) and np.allclose(home.planes.point, [there])
+    assert home.rings.radius.tolist() == [2.0]
+    assert home.rings.width.tolist() == pytest.approx([0.2])
+    assert home.planes.width.tolist() == pytest.approx([0.4])
+    assert np.allclose(home.planes.ray[0] * 2.0, ahead - there, atol=1e-5)
+    assert np.allclose(home.planes.normal[0] * 2.0, up - there, atol=1e-5)
+
+
+def test_in_home_draws_a_particle_on_the_mirrors_low_side_at_both_its_images() -> None:
+    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())
+    view = layer_view(
+        Layer(id="a", name="A", type="field", kind="breathe", mirror=Mirror("x", 4.0)), leds
+    )
+
+    home = view.in_home(_dots([1.0, 1.0, 1.0], [6.0, 2.0, 1.0], [3.0, 2.0, 1.0]))
+
+    # The particle at x 6 is on the high side, which no LED sees: left out. Each of the
+    # others is drawn where it is and at its reflection, side by side, oldest first.
+    assert home.particles.pos.tolist() == [
+        [1.0, 1.0, 1.0],
+        [7.0, 1.0, 1.0],
+        [3.0, 2.0, 1.0],
+        [5.0, 2.0, 1.0],
+    ]
+    # Every LED's own place is among the images of what it sees.
+    seen = view.in_home(Fx(particles=swarm(view.leds.pos.tolist(), (1.0, 1.0, 1.0), 0.2)))
+    for place in leds.pos:
+        assert np.isclose(seen.particles.pos, place).all(axis=1).any()
+
+
+def test_in_home_draws_rings_and_planes_whole_at_both_images_of_a_mirror() -> None:
+    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())
+    view = layer_view(
+        Layer(id="a", name="A", type="field", kind="breathe", mirror=Mirror("x", 4.0)), leds
+    )
+    fx = Fx(
+        rings=rings([2.0, 1.0, 1.0], 3.0, 0.1, (1.0, 0.0, 0.0)),
+        planes=planes(
+            [2.0, 1.0, 1.0], (0.6, 0.8, 0.0), 0.2, (0.0, 1.0, 0.0), ray=(0.8, -0.6, 0.0)
+        ),
+    )
+
+    home = view.in_home(fx)
+
+    assert home.rings.centre.tolist() == [[2.0, 1.0, 1.0], [6.0, 1.0, 1.0]]
+    assert home.rings.radius.tolist() == [3.0, 3.0]  # whole: a ring crossing the plane too
+    assert home.planes.point.tolist() == [[2.0, 1.0, 1.0], [6.0, 1.0, 1.0]]
+    assert np.allclose(home.planes.normal, [[0.6, 0.8, 0.0], [-0.6, 0.8, 0.0]])
+    assert np.allclose(home.planes.ray, [[0.8, -0.6, 0.0], [-0.8, -0.6, 0.0]])
+
+
+def test_in_home_weighs_particles_by_the_mask_where_they_land_and_drops_those_it_hides() -> None:
+    leds = leds_at([[1.0, 1.0, 1.0], [1.0, 1.0, 2.0]], space=tiny_space())
+    view = layer_view(
+        Layer(id="a", name="A", type="field", kind="breathe", mask=HeightMask(0.5, 1.5)), leds
+    )
+
+    home = view.in_home(_dots([1.0, 1.0, 1.0], [1.0, 1.0, 1.5], [1.0, 1.0, 3.0]))
+
+    # Inside in full, on the edge at half, above it gone.
+    assert home.particles.pos[:, 2].tolist() == [1.0, 1.5]
+    assert np.allclose(home.particles.colour, [[1.0, 0.5, 0.25], [0.5, 0.25, 0.125]])
+
+
+def test_a_mask_keeps_rings_and_planes_whole_while_it_shows_any_led() -> None:
+    fx = Fx(
+        rings=rings([1.0, 1.0, 1.0], 2.0, 0.1, (1.0, 0.0, 0.0)),
+        planes=planes([1.0, 1.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 0.0)),
+    )
+    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())
+
+    def masked(mask: RoomMask) -> Fx:
+        layer = Layer(id="a", name="A", type="field", kind="breathe", mask=mask)
+        return layer_view(layer, leds).in_home(fx)
+
+    shown = masked(RoomMask("west"))
+    assert (shown.rings.count, shown.planes.count) == (1, 1)
+    assert shown.rings.radius.tolist() == [2.0]  # whole, past the room's outline too
+    hidden = masked(RoomMask("no-such-room"))
+    assert (hidden.rings.count, hidden.planes.count) == (0, 0)
+
+
+def test_mask_weights_at_an_leds_place_is_the_leds_weight() -> None:
+    leds = leds_at(
+        [[1.0, 1.0, 0.2], [1.0, 1.0, 1.0], [7.0, 1.0, 0.5], [7.0, 3.0, 2.0]], space=tiny_space()
+    )
+    for mask in (HeightMask(0.5, 2.0), RoomMask("west"), AnchorMask("gone", 2.0)):
+        assert np.array_equal(mask_weights_at(mask, leds.pos, leds), mask_weights(mask, leds))
```

- [ ] **Step 2: Run them, to see them fail**

```bash
uv run pytest tests/zones/test_layer_view.py -q 2>&1 | tail -3
```

Expected: `ImportError: cannot import name 'mask_weights_at' from 'dj_ledfx.zones.layer_view'`.

- [ ] **Step 3: Map fx onto the map**

```diff
diff --git a/src/dj_ledfx/zones/layer_view.py b/src/dj_ledfx/zones/layer_view.py
index b945b22..13a5155 100644
--- a/src/dj_ledfx/zones/layer_view.py
+++ b/src/dj_ledfx/zones/layer_view.py
@@ -6,6 +6,9 @@ soft edge where the band or the reach ends. The mirror and the transform move th
 positions the effect sees: an LED shows what the field has at its mirrored and
 transformed place. A view depends only on the LEDs and the modifiers, so the runtime keeps
 one per layer until either changes.
+
+What the layer's effect draws in space (effects/fx.py) is in the effect's own space; the
+view maps it back onto the map (in_home()), where the stage draws it.
 """
 
 from __future__ import annotations
@@ -16,7 +19,9 @@ from typing import TYPE_CHECKING
 
 import numpy as np
 
-from dj_ledfx.effects.field_tools import anchor_or_centre, distances, smoothstep
+from dj_ledfx.effects.field_tools import anchor_or_centre, smoothstep
+from dj_ledfx.effects.fx import NO_PLANES, NO_RINGS, Fx, Planes, Rings
+from dj_ledfx.effects.particle_tools import Particles
 from dj_ledfx.home.geometry import points_in_polygon
 from dj_ledfx.home.shapes import rotation_matrix
 from dj_ledfx.looks.model import (
@@ -42,10 +47,15 @@ _AXIS = {"x": 0, "y": 1, "z": 2}
 @dataclass(frozen=True, eq=False)
 class LayerView:
     """What a layer draws on: the LEDs its effect renders (the zone's own, or moved) and
-    each LED's share of the layer, shape (N, 1); None: every LED in full."""
+    each LED's share of the layer, shape (N, 1); None: every LED in full. `zone` is the
+    zone's own LED set, where the mask and the moves were made (None: `leds`, unmoved)."""
 
     leds: LedSet
     weight: NDArray[np.float32] | None = None
+    zone: LedSet | None = None
+    mask: Mask | None = None
+    mirror: Mirror | None = None
+    transform: Transform | None = None
 
     @cached_property
     def among(self) -> NDArray[np.bool_] | None:
@@ -53,34 +63,64 @@ class LayerView:
         lamps are made of these, one array for as long as the view is kept."""
         return None if self.weight is None else self.weight[:, 0] > 0.0
 
+    def in_home(self, fx: Fx) -> Fx:
+        """What the layer's effect draws, moved from the effect's space onto the map: back
+        through the transform, then at every place the mirror shows it. A particle the
+        mirror doesn't show (past its plane) is left out, and one in both halves is drawn
+        in both; a ring or a plane is drawn whole at its place and at its reflection. The
+        mask weighs each particle's colour where it lands, and one it weighs 0 is left out;
+        a ring or a plane is drawn whole while the mask weighs any LED, else not at all."""
+        zone = self.zone or self.leds
+        centre = zone.centre.astype(np.float64)
+        particles, rings, planes = fx.particles, fx.rings, fx.planes
+        if self.transform is not None:
+            particles, rings, planes = _unmoved(self.transform, centre, particles, rings, planes)
+        if self.mirror is not None:
+            axis = _AXIS[self.mirror.axis]
+            at = float(centre[axis]) if self.mirror.at is None else self.mirror.at
+            particles = _particle_images(particles, axis, at)
+            rings, planes = _ring_images(rings, axis, at), _plane_images(planes, axis, at)
+        if self.mask is not None:
+            particles = _weighed(particles, mask_weights_at(self.mask, particles.pos, zone))
+            if not bool(self.among is not None and self.among.any()):
+                rings, planes = NO_RINGS, NO_PLANES
+        return Fx(particles, rings, planes)
+
 
 def layer_view(layer: Layer, leds: LedSet) -> LayerView:
     weight = None if layer.mask is None else mask_weights(layer.mask, leds)[:, None]
     if layer.mirror is None and layer.transform is None:
-        return LayerView(leds, weight)
+        return LayerView(leds, weight, mask=layer.mask)
     pos = leds.pos.astype(np.float64)
     if layer.mirror is not None:
         pos = mirrored(layer.mirror, pos, leds.centre)
     if layer.transform is not None:
         pos = transformed(layer.transform, pos, leds.centre)
-    return LayerView(leds.moved(pos), weight)
+    return LayerView(leds.moved(pos), weight, leds, layer.mask, layer.mirror, layer.transform)
 
 
 def mask_weights(mask: Mask, leds: LedSet) -> NDArray[np.float32]:
     """Each LED's share of a masked layer, 0..1, from where the LED sits. A room or a
     sub-zone the map doesn't have (any more) shows the layer nowhere; an anchor it doesn't
     have is the zone's middle, as it is for the effects."""
+    return mask_weights_at(mask, leds.pos, leds)
+
+
+def mask_weights_at(mask: Mask, pos: NDArray[np.float32], leds: LedSet) -> NDArray[np.float32]:
+    """The mask's weight, 0..1, at each of these places on the map (an LED's, or a
+    particle's), in the zone of these LEDs: its rooms', sub-zones' and anchors' places."""
     half = MASK_EDGE_M / 2.0
     match mask:
         case HeightMask(low, high):
-            z = leds.pos[:, 2]
+            z = pos[:, 2]
             inside = smoothstep(low - half, low + half, z) * (
                 1.0 - smoothstep(high - half, high + half, z)
             )
             weights: NDArray[np.float32] = inside.astype(np.float32)
             return weights
         case AnchorMask(anchor, radius):
-            reach = distances(leds, anchor_or_centre(leds, anchor))
+            point = anchor_or_centre(leds, anchor)
+            reach = np.asarray(np.linalg.norm(pos - point, axis=1), dtype=np.float32)
             near: NDArray[np.float32] = (
                 1.0 - smoothstep(radius - half, radius + half, reach)
             ).astype(np.float32)
@@ -90,8 +130,8 @@ def mask_weights(mask: Mask, leds: LedSet) -> NDArray[np.float32]:
         case SubZoneMask(sub_zone):
             outline = leds.space.sub_zone_outlines.get(sub_zone)
     if not outline:
-        return np.zeros(leds.count, dtype=np.float32)
-    inside_outline = points_in_polygon(leds.pos[:, :2].astype(np.float64), outline)
+        return np.zeros(len(pos), dtype=np.float32)
+    inside_outline = points_in_polygon(pos[:, :2].astype(np.float64), outline)
     return inside_outline.astype(np.float32)
 
 
@@ -119,3 +159,97 @@ def transformed(
     turn = rotation_matrix((transform.rotate_deg, 0.0, 0.0))  # the map's turn
     placed: NDArray[np.float64] = back @ turn + middle  # rows times it: turned back
     return placed
+
+
+def _unmoved(
+    transform: Transform,
+    centre: NDArray[np.float64],
+    particles: Particles,
+    rings: Rings,
+    planes: Planes,
+) -> tuple[Particles, Rings, Planes]:
+    """Things in the effect's space where the transform shows them on the map: transformed()
+    undone. Places go back through the turn, the scale and the offset; directions through
+    the turn alone; lengths grow by the scale."""
+    turn = rotation_matrix((transform.rotate_deg, 0.0, 0.0))
+    offset = np.asarray(transform.offset, dtype=np.float64)
+    scale = transform.scale
+
+    def place(points: NDArray[np.float32]) -> NDArray[np.float32]:
+        back = ((points.astype(np.float64) - centre) @ turn.T) * scale + centre + offset
+        return back.astype(np.float32)
+
+    def turned(directions: NDArray[np.float32]) -> NDArray[np.float32]:
+        return (directions.astype(np.float64) @ turn.T).astype(np.float32)
+
+    grown = np.float32(scale)
+    return (
+        Particles(place(particles.pos), particles.colour, particles.radius * grown),
+        Rings(
+            place(rings.centre),
+            rings.radius * grown,
+            rings.width * grown,
+            rings.colour,
+            rings.circle,
+        ),
+        Planes(
+            place(planes.point),
+            turned(planes.normal),
+            planes.width * grown,
+            planes.colour,
+            turned(planes.ray),
+        ),
+    )
+
+
+def _reflected(points: NDArray[np.float32], axis: int, at: float) -> NDArray[np.float32]:
+    across = points.copy()
+    across[:, axis] = 2.0 * at - across[:, axis]
+    return across
+
+
+def _flipped(directions: NDArray[np.float32], axis: int) -> NDArray[np.float32]:
+    across = directions.copy()
+    across[:, axis] = -across[:, axis]
+    return across
+
+
+def _particle_images(particles: Particles, axis: int, at: float) -> Particles:
+    """The particles the mirror shows, each at its place and then at its reflection, so the
+    two stay side by side, oldest first: those on its low side, since an LED on the high
+    side sees the field at its own reflection."""
+    shown = particles.pick(particles.pos[:, axis] <= at)
+
+    def twice(values: NDArray[np.float32]) -> NDArray[np.float32]:
+        return np.repeat(values, 2, axis=0)
+
+    pos = twice(shown.pos)
+    pos[1::2] = _reflected(shown.pos, axis, at)
+    return Particles(pos, twice(shown.colour), twice(shown.radius))
+
+
+def _ring_images(rings: Rings, axis: int, at: float) -> Rings:
+    return Rings(
+        np.concatenate([rings.centre, _reflected(rings.centre, axis, at)]),
+        np.concatenate([rings.radius, rings.radius]),
+        np.concatenate([rings.width, rings.width]),
+        np.concatenate([rings.colour, rings.colour]),
+        np.concatenate([rings.circle, rings.circle]),
+    )
+
+
+def _plane_images(planes: Planes, axis: int, at: float) -> Planes:
+    return Planes(
+        np.concatenate([planes.point, _reflected(planes.point, axis, at)]),
+        np.concatenate([planes.normal, _flipped(planes.normal, axis)]),
+        np.concatenate([planes.width, planes.width]),
+        np.concatenate([planes.colour, planes.colour]),
+        np.concatenate([planes.ray, _flipped(planes.ray, axis)]),
+    )
+
+
+def _weighed(particles: Particles, weights: NDArray[np.float32]) -> Particles:
+    """Each particle's colour times its weight, leaving out those weighed 0."""
+    kept = weights > 0.0
+    shown = particles.pick(kept)
+    return Particles(shown.pos, shown.colour * weights[kept][:, None], shown.radius)
```

- [ ] **Step 4: Run the task's tests, and the runtime's that build views**

```bash
uv run pytest tests/zones/test_layer_view.py tests/zones/test_runtime_modifiers.py tests/zones/test_runtime_particles.py -q 2>&1 | tail -1
```

Expected: all pass; `test_layer_view.py` alone is `16 passed`.

- [ ] **Step 5: The gate**

```bash
uv run ruff format src/dj_ledfx/zones/layer_view.py tests/zones/test_layer_view.py && uv run ruff check --fix src/dj_ledfx/zones/layer_view.py tests/zones/test_layer_view.py
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1
```

Expected: `2793 passed, 1 skipped, 79 deselected`, `372 files already formatted`, `Found 16 errors in 4 files (checked 167 source files)`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/zones/layer_view.py tests/zones/test_layer_view.py
git commit -m "feat(zones): a layer's fx on the map, through its mirror, transform and mask"
```

---

### Task 4: Each frame keeps its fx, and the feed reads them

The runtime asks each streamed layer for its fx right after its frame, maps them onto the map at the layer's opacity, runs the evening and the cap over them (ruling 7), and writes them into the frame beside its colours (ruling 4); a hook that fails costs only its fx (ruling 11). A transition's frame carries the new look's (ruling 9). `FrameFeed.fx()` reads them at now, never blended. The perf run gains every look that draws in space at its largest (ruling 14).

**Files:**
- Create: `tests/effects/test_ring_buffer.py`, `tests/zones/test_runtime_fx.py`
- Modify: `src/dj_ledfx/types.py`, `src/dj_ledfx/effects/ring_buffer.py`, `src/dj_ledfx/zones/runtime.py`, `src/dj_ledfx/zones/frames.py`, `tests/zones/test_frames.py`, `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: Tasks 1–3: `Effect.in_space`, `Fx.recoloured`, `fx_joined`, `LayerView.in_home`; `warmed()`, `capped()`.
- Produces: `RenderedFrame.fx: Fx | None = None`; `RingBuffer.frame_at(target_time) -> RenderedFrame | None`; `ZoneRuntime._in_space(layer, effect, ctx, view) -> Fx | None`; `ZoneFx(stream, zone_id, fx, brightness)` and `FrameFeed.fx() -> list[ZoneFx]` in `zones/frames.py`; `FX_SHARE_S` in `tests/zones/test_runtime_perf.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/effects/test_ring_buffer.py`:

```python
"""The ring's one unblended read: the frame at a moment, for what it draws in space."""

from __future__ import annotations

import numpy as np

from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.types import RenderedFrame


def _frame(t: float) -> RenderedFrame:
    return RenderedFrame(
        colors=np.zeros((1, 3), dtype=np.float32), target_time=t, beat_phase=0.0, bar_phase=0.0
    )


def test_frame_at_is_the_newest_frame_at_or_before_the_moment_never_a_blend() -> None:
    ring = RingBuffer(3)
    assert ring.frame_at(1.0) is None  # empty
    frames = [_frame(t) for t in (1.0, 2.0, 3.0, 4.0)]  # the ring wraps: 1.0 goes
    for frame in frames:
        ring.write(frame)

    assert ring.frame_at(2.0) is frames[1]  # on a frame: that frame
    assert ring.frame_at(2.9) is frames[1]  # between two: the one before, held
    assert ring.frame_at(9.0) is frames[3]  # past the newest: the newest
    assert ring.frame_at(0.5) is frames[1]  # before the first: the first, as colors_at holds it
```

Create `tests/zones/test_runtime_fx.py`:

```python
"""What a running zone draws in space (M8, engine spec §4.1): each frame's fx, kept in the
ring beside its colours, on the map."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import nearest_frame
from loguru import logger
from runtime_fakes import (
    FADE,
    DotParticles,
    dot_layer,
    field_layer,
    glow_layer,
    latest,
    look_of,
    placed_light,
    runtime_of,
)
from tempo_fakes import START, FakeTime, tempo_clock

from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.looks.model import Layer, LookModifiers, Mirror, Transform
from dj_ledfx.zones.runtime import ZoneRuntime

pytestmark = pytest.mark.usefixtures("_fields")

# One light of 9 LEDs, 0.5 m apart along x from 0 to 4 m, 1 m up: its centre is at 2 m.
ROW_LIGHT = placed_light("row", *[(0.5 * i, 0.0, 1.0) for i in range(9)])
UNDER_THE_DOT = 4  # the LED at 2 m


def _fx(runtime: ZoneRuntime) -> Fx | None:
    """What the newest frame draws in space."""
    return nearest_frame(runtime.ring, 1e9).fx


def _dots(runtime: ZoneRuntime) -> list[list[float]]:
    fx = _fx(runtime)
    assert fx is not None
    return fx.particles.pos.tolist()


def test_each_frame_keeps_what_its_layers_draw_in_space_beside_its_colours() -> None:
    runtime = runtime_of(look_of(field_layer(0.2), dot_layer(x=2.0, blend="add")), [ROW_LIGHT])
    runtime.tick(100.0)

    frame = nearest_frame(runtime.ring, 1e9)
    assert frame.fx is not None and frame.colors[UNDER_THE_DOT, 0] > 0.2  # the dot's light
    assert frame.fx.particles.pos.tolist() == [[2.0, 0.0, 1.0]]  # the field draws nothing
    assert frame.fx.particles.colour.tolist() == [[1.0, 1.0, 1.0]]
    assert (frame.fx.rings.count, frame.fx.planes.count) == (0, 0)


def test_a_layers_transform_and_mirror_move_its_fx_onto_the_map() -> None:
    shifted = runtime_of(
        look_of(dot_layer(x=2.0, transform=Transform(offset=(1.0, 0.0, 0.0)))), [ROW_LIGHT]
    )
    mirrored = runtime_of(look_of(dot_layer(x=1.0, mirror=Mirror(axis="x"))), [ROW_LIGHT])
    shifted.tick(100.0)
    mirrored.tick(100.0)
    assert _dots(shifted) == [[3.0, 0.0, 1.0]]  # where the lights show it: 1 m further east
    assert _dots(mirrored) == [[1.0, 0.0, 1.0], [3.0, 0.0, 1.0]]  # and across the middle


def test_a_layers_opacity_dims_its_fx_whatever_its_blend() -> None:
    for blend in ("normal", "add", "screen", "max"):
        runtime = runtime_of(look_of(dot_layer(x=2.0, opacity=0.5, blend=blend)), [ROW_LIGHT])
        runtime.tick(100.0)
        fx = _fx(runtime)
        assert fx is not None and fx.particles.colour.tolist() == [[0.5, 0.5, 0.5]]


def test_the_evening_and_the_cap_change_the_fx_as_they_change_the_leds() -> None:
    modifiers = LookModifiers(evening=True, brightness_cap=0.4)
    runtime = runtime_of(
        look_of(dot_layer(x=2.0), modifiers=modifiers), [ROW_LIGHT], evening=lambda: 1.0
    )
    runtime.tick(100.0)
    fx = _fx(runtime)
    assert fx is not None
    # The LED under the dot shows the dot's own colour, so the two match.
    np.testing.assert_allclose(fx.particles.colour[0], latest(runtime)[UNDER_THE_DOT], rtol=1e-6)
    assert float(fx.particles.colour.max()) == pytest.approx(0.4)


def test_a_flash_and_trails_light_the_leds_alone() -> None:
    clock = tempo_clock(FakeTime())  # beat 0 at START, 120 BPM: a bar every 2 s
    modifiers = LookModifiers(trails_s=10.0, downbeat_flash=True)
    runtime = runtime_of(
        look_of(dot_layer(x=2.0, level=0.5), modifiers=modifiers), [ROW_LIGHT], clock=clock
    )

    runtime.tick(START + 2.0)  # just past the downbeat: the flash
    assert latest(runtime)[UNDER_THE_DOT, 0] > 0.75
    fx = _fx(runtime)
    assert fx is not None and fx.particles.colour.tolist() == [[0.5, 0.5, 0.5]]
    runtime.tick(START + 2.3)  # the flash is over, its trail isn't
    assert latest(runtime)[UNDER_THE_DOT, 0] > 0.5
    fx = _fx(runtime)
    assert fx is not None and fx.particles.colour.tolist() == [[0.5, 0.5, 0.5]]


@pytest.mark.parametrize(
    "layers",
    [(field_layer(0.5),), (field_layer(0.5), glow_layer())],
    ids=["field", "firmware"],
)
def test_layers_that_draw_nothing_in_space_give_a_frame_no_fx(layers: tuple[Layer, ...]) -> None:
    runtime = runtime_of(look_of(*layers))
    runtime.tick(100.0)
    assert latest(runtime).any() and _fx(runtime) is None


def test_a_waiting_look_and_a_dark_dot_draw_nothing_in_space() -> None:
    waiting = runtime_of(look_of(dot_layer(x=2.0), needs=("music",)), [ROW_LIGHT])
    dark = runtime_of(look_of(dot_layer(x=2.0, level=0.0)), [ROW_LIGHT])
    waiting.tick(100.0)
    dark.tick(100.0)
    assert waiting.state == "waiting" and _fx(waiting) is None
    fx = _fx(dark)  # a black particle is still a particle: the channel leaves it out
    assert fx is not None and fx.particles.count == 1


def test_mid_transition_a_zone_draws_the_new_looks_fx_from_its_first_frame() -> None:
    old = runtime_of(look_of(dot_layer(x=1.0)), [ROW_LIGHT])
    new = runtime_of(look_of(dot_layer(x=3.0)), [ROW_LIGHT])
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    assert new.state == "transition"
    assert latest(new)[2, 0] > 0.0  # the old look's dot still lights its LED...
    assert _dots(new) == [[3.0, 0.0, 1.0]]  # ...but only the new look's is drawn in space
    new.tick(1001.0)
    assert _dots(new) == [[3.0, 0.0, 1.0]]


def test_an_effect_that_cant_say_what_it_draws_loses_its_fx_not_its_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(self: DotParticles, ctx: RenderContext, leds: LedSet) -> Fx | None:
        raise RuntimeError("no fx")

    monkeypatch.setattr(DotParticles, "in_space", broken)
    runtime = runtime_of(look_of(dot_layer(x=2.0)), [ROW_LIGHT])
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        runtime.tick(100.0)
        runtime.tick(100.1)
    finally:
        logger.remove(sink)

    assert runtime.state == "running"
    assert latest(runtime)[UNDER_THE_DOT, 0] == pytest.approx(1.0)
    assert _fx(runtime) is None
    assert len(warnings) == 1 and "RuntimeError: no fx" in warnings[0]
```

In `tests/zones/test_frames.py`, the feed's read:

```diff
diff --git a/tests/zones/test_frames.py b/tests/zones/test_frames.py
index a8203de..abab669 100644
--- a/tests/zones/test_frames.py
+++ b/tests/zones/test_frames.py
@@ -1,15 +1,19 @@
 from __future__ import annotations
 
 from functools import partial
+from types import SimpleNamespace
 
 import numpy as np
 from conftest import FakeLight, nearest_frame
 from runtime_fakes import TILE
 from zone_home import BREATHE_AND_GLOW, GLOW, HomeFactory, zone_record
 
+from dj_ledfx.effects.fx import Fx
+from dj_ledfx.effects.particle_tools import swarm
+from dj_ledfx.effects.ring_buffer import RingBuffer
 from dj_ledfx.scheduling.route import to_device_colors
 from dj_ledfx.types import RenderedFrame
-from dj_ledfx.zones.frames import FrameFeed, Watchers
+from dj_ledfx.zones.frames import FrameFeed, Watchers, ZoneFx
 from dj_ledfx.zones.preview import PreviewManager
 
 
@@ -121,3 +125,43 @@ async def test_the_web_app_sees_a_zone_at_its_brightness(make_home: HomeFactory)
     count = runtime.leds.count
     expected = to_device_colors(frame.colors[:count] * np.float32(0.5), count)
     assert np.array_equal(feed.frames("live")["lamp"], expected)
+
+
+# M8: what each zone draws in space, read from the rings at now.
+
+
+def _ring_of(*frames: tuple[float, Fx | None]) -> RingBuffer:
+    ring = RingBuffer(8)
+    for t, fx in frames:
+        ring.write(
+            RenderedFrame(
+                colors=np.zeros((1, 3), dtype=np.float32),
+                target_time=t,
+                beat_phase=0.0,
+                bar_phase=0.0,
+                fx=fx,
+            )
+        )
+    return ring
+
+
+def _drawn() -> Fx:
+    return Fx(particles=swarm([[1.0, 2.0, 1.0]], (1.0, 1.0, 1.0), 0.2))
+
+
+def test_the_feed_reads_each_zones_fx_from_the_newest_frame_at_or_before_now() -> None:
+    early, late = _drawn(), _drawn()
+    live = SimpleNamespace(
+        zone_id="z", brightness=0.5, ring=_ring_of((99.0, early), (100.5, late))
+    )
+    dark = SimpleNamespace(zone_id="dark", brightness=1.0, ring=_ring_of((99.0, None)))
+    preview = SimpleNamespace(zone_id="z", brightness=1.0, ring=_ring_of((99.0, late)))
+    now = [100.0]
+    feed = FrameFeed(lambda: [live, dark], lambda: [preview], clock=lambda: now[0])  # type: ignore[list-item, return-value]
+
+    assert feed.fx() == [ZoneFx("live", "z", early, 0.5), ZoneFx("preview", "z", late, 1.0)]
+    now[0] = 100.4  # nearer the next frame: still the one before, never a blend
+    assert feed.fx()[0].fx is early
+    now[0] = 100.5
+    assert feed.fx()[0].fx is late
+    assert FrameFeed(lambda: [], clock=lambda: 100.0).fx() == []
```

In `tests/zones/test_runtime_perf.py`, the perf run's looks that draw in space:

```diff
diff --git a/tests/zones/test_runtime_perf.py b/tests/zones/test_runtime_perf.py
index 52ad967..4f789fd 100644
--- a/tests/zones/test_runtime_perf.py
+++ b/tests/zones/test_runtime_perf.py
@@ -11,9 +11,12 @@ from datetime import UTC, datetime
 from typing import Any
 
 import pytest
-from conftest import builtin_look
+from conftest import builtin_look, nearest_frame
 from map_home import seeded_space, seeded_zone_lights
 
+from dj_ledfx.effects.base import Effect
+from dj_ledfx.effects.particles import ParticleEffect
+from dj_ledfx.effects.registry import get_effect_class
 from dj_ledfx.home.model import Location
 from dj_ledfx.home.seed import handoff_home_json
 from dj_ledfx.home.sun import Evening, evening_amount
@@ -21,6 +24,7 @@ from dj_ledfx.looks.builtin import builtin_looks
 from dj_ledfx.looks.model import (
     MAX_TRANSITION_S,
     HeightMask,
+    Layer,
     Look,
     LookModifiers,
     Mirror,
@@ -193,3 +197,55 @@ def test_a_start_taking_lights_from_two_zones_mid_transition_renders_in_under_5_
     assert all(len(source.transition_sources) == 1 for source in new.transition_sources)
     assert statistics.median(durations) < FRAME_BUDGET_S
     assert new.fps_actual >= 59
+
+
+# M8: what a zone draws in space is worked out with every frame, inside the same budget.
+# Each look that draws anything in space, at its layers' largest settings and with every
+# modifier, its mirror doubling its particles; and the hook's whole share, against the same
+# look with every effect saying nothing.
+FX_SHARE_S = 0.0005  # a tenth of the budget
+
+
+def _at_their_largest(look: Look) -> Look:
+    def largest(layer: Layer) -> Layer:
+        if layer.type == "firmware":
+            return layer
+        params = get_effect_class(layer.kind).parameters().items()
+        top = {
+            name: int(param.max) if param.type == "int" else param.max
+            for name, param in params
+            if param.type in ("int", "float") and param.max is not None
+        }
+        return replace(layer, settings={**layer.settings, **top})
+
+    return replace(look, layers=tuple(largest(layer) for layer in look.layers))
+
+
+def _draws_in_space(look: Look) -> bool:
+    return any(
+        layer.type != "firmware" and get_effect_class(layer.kind).in_space is not Effect.in_space
+        for layer in look.layers
+    )
+
+
+@pytest.mark.parametrize(
+    "look", [look for look in builtin_looks() if _draws_in_space(look)], ids=lambda look: look.id
+)
+def test_what_a_zone_draws_in_space_keeps_its_frame_under_5_ms(
+    look: Look, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    dressed = with_every_modifier(_at_their_largest(look))
+    runtime = home_runtime(dressed, evening=lambda: 0.5)
+    durations = tick_times(runtime)
+    assert statistics.median(durations) < FRAME_BUDGET_S
+    drawn = 0  # the frames that drew something in space (the mirror hides half the field)
+    for step in range(240):
+        runtime.tick(1010.0 + step / 60)
+        drawn += nearest_frame(runtime.ring, 1e9).fx is not None
+    assert drawn > 0
+
+    monkeypatch.setattr(Effect, "in_space", lambda self, ctx, leds: None)
+    monkeypatch.setattr(ParticleEffect, "in_space", lambda self, ctx, leds: None)
+    without = home_runtime(dressed, evening=lambda: 0.5)
+    share = statistics.median(durations) - statistics.median(tick_times(without))
+    assert share < FX_SHARE_S
```

- [ ] **Step 2: Run them, to see them fail**

```bash
uv run pytest tests/effects/test_ring_buffer.py tests/zones/test_runtime_fx.py tests/zones/test_frames.py -q 2>&1 | tail -3
```

Expected: `ImportError: cannot import name 'ZoneFx' from 'dj_ledfx.zones.frames'` (and `frame_at` and `RenderedFrame`'s `fx` missing behind it).

- [ ] **Step 3: Keep each frame's fx, and read them**

In `src/dj_ledfx/types.py`:

```diff
diff --git a/src/dj_ledfx/types.py b/src/dj_ledfx/types.py
index d8ad444..e888a39 100644
--- a/src/dj_ledfx/types.py
+++ b/src/dj_ledfx/types.py
@@ -2,11 +2,14 @@ from __future__ import annotations
 
 import math
 from dataclasses import dataclass
-from typing import TypeGuard
+from typing import TYPE_CHECKING, TypeGuard
 
 import numpy as np
 from numpy.typing import NDArray
 
+if TYPE_CHECKING:
+    from dj_ledfx.effects.fx import Fx
+
 RGB = tuple[int, int, int]
 FloatRGB = NDArray[np.float32]  # shape (n_leds, 3), linear 0..1 per channel
 
@@ -49,6 +52,7 @@ class RenderedFrame:
     target_time: float  # monotonic time when this should be displayed
     beat_phase: float
     bar_phase: float
+    fx: Fx | None = None  # what the frame draws in space, on the map, before brightness
 
 
 @dataclass(frozen=True, slots=True)
```

In `src/dj_ledfx/effects/ring_buffer.py`:

```diff
diff --git a/src/dj_ledfx/effects/ring_buffer.py b/src/dj_ledfx/effects/ring_buffer.py
index 4555ec6..a9675cc 100644
--- a/src/dj_ledfx/effects/ring_buffer.py
+++ b/src/dj_ledfx/effects/ring_buffer.py
@@ -57,6 +57,12 @@ class RingBuffer:
             return before, before, 0.0
         return before, after, (target_time - before_t) / (after_t - before_t)
 
+    def frame_at(self, target_time: float) -> RenderedFrame | None:
+        """The newest frame at or before target_time, never blended: the first frame for a
+        moment before it, as colors_at holds it; None while the ring is empty."""
+        found = self.find_around(target_time)
+        return None if found is None else found[0]
+
     def colors_at(self, target_time: float, start: int, stop: int) -> FloatRGB | None:
         """LEDs start..stop at target_time, blended from the frames either side of it, or
         None: the ring is empty, or a frame is shorter than stop. Between two frames it's a
```

In `src/dj_ledfx/zones/runtime.py`:

```diff
diff --git a/src/dj_ledfx/zones/runtime.py b/src/dj_ledfx/zones/runtime.py
index 8fe85be..0e2b971 100644
--- a/src/dj_ledfx/zones/runtime.py
+++ b/src/dj_ledfx/zones/runtime.py
@@ -17,6 +17,7 @@ from loguru import logger
 from dj_ledfx.effects.blend import blend_into
 from dj_ledfx.effects.context import render_context
 from dj_ledfx.effects.firmware import FirmwareEffect
+from dj_ledfx.effects.fx import Fx, fx_joined
 from dj_ledfx.effects.ledset import (
     NO_ROOM,
     NO_SPACE,
@@ -60,7 +61,7 @@ if TYPE_CHECKING:
 FRAME_BUDGET_S = 0.005
 SLOW_RATIO = 0.8
 SLOW_AFTER_S = 30.0
-CRASH_LOG_INTERVAL_S = 60.0
+CRASH_LOG_INTERVAL_S = 60.0  # a crash, or a layer's fx failing, is logged at most this often
 ALWAYS_AVAILABLE = frozenset({"tempo"})  # the internal clock at worst (spec §5.2)
 # How far ahead a zone renders at most. A light slower than this gets the newest frame and
 # runs late by the difference. A dozing Govee lamp's latency is its whole round trip, up to
@@ -248,6 +249,8 @@ class ZoneRuntime:
         self._views: dict[int, tuple[object, LayerView]] = {}  # by the layer's place
         self._rendering = ""
         self._last_crash_log = float("-inf")
+        self._last_fx_log = float("-inf")
+        self._fx: Fx | None = None  # what the look's newest frame draws in space, on the map
         self._render_s = 0.0  # moving average of the render time
         self._stride = 1
         self._ticks = 0
@@ -632,6 +635,7 @@ class ZoneRuntime:
                 target_time=target,
                 beat_phase=ctx.beat_phase,
                 bar_phase=ctx.bar_phase,
+                fx=self._fx,
             )
         )
         self._track_speed(now, elapsed)
@@ -706,7 +710,9 @@ class ZoneRuntime:
         flash leaves one) and the evening. The lights that run their own effect are drawn
         after those, as they show (for the preview, while it's watched), and the brightness
         cap goes over every LED. The trails keep their own copy of what they showed.
-        Waiting, it's dark."""
+        Waiting, it's dark. What the layers draw in space is kept in self._fx, under the
+        evening and the cap; a flash and trails are the LEDs' alone."""
+        self._fx = None
         count = self.leds.count
         if self.waiting_for or count == 0:
             return np.zeros((count, 3), dtype=np.float32)
@@ -718,19 +724,26 @@ class ZoneRuntime:
             frame = self._trails.apply(frame, ctx.t, modifiers.trails_s)
         if modifiers.evening:
             frame = warmed(frame, ctx)
+            if self._fx is not None:
+                self._fx = self._fx.recoloured(lambda colours: warmed(colours, ctx))
         if self._claim_targets and self._env.watched():
             self._draw_firmware(frame, ctx, self._claim_targets)
         if modifiers.brightness_cap is not None:
-            frame = capped(frame, modifiers.brightness_cap)
+            cap = modifiers.brightness_cap
+            frame = capped(frame, cap)
+            if self._fx is not None:
+                self._fx = self._fx.recoloured(lambda colours: capped(colours, cap))
         return frame
 
     def _render_layers(self, ctx: RenderContext) -> FloatRGB:
         """The streamed layers blended bottom to top, then each firmware layer's copy drawn
         on the lights that stream it. A particle layer's particles move to the frame's
         moment among the lamps its mask weighs above 0 (all of its view's, with no mask),
-        and light every LED of its view, which the mask then weighs."""
+        and light every LED of its view, which the mask then weighs. What each layer draws
+        in space is gathered into self._fx, on the map."""
         count = self.leds.count
         frame: FloatRGB | None = None
+        drawn_in_space: list[Fx] = []
         for index, (layer, effect) in enumerate(self._streamed):
             self._rendering = layer.name
             view = self._view(index, layer)
@@ -738,6 +751,9 @@ class ZoneRuntime:
                 colors = _finite(drawn(effect, ctx, view.leds, view.among))
             else:
                 colors = _finite(effect.render(ctx, view.leds))
+            fx = self._in_space(layer, effect, ctx, view)
+            if fx is not None:
+                drawn_in_space.append(fx)
             opacity = _opacity(layer, view)
             if frame is None and layer.blend == "normal":  # over black: its colours, weighed
                 frame = np.multiply(colors, opacity, dtype=np.float32)
@@ -748,8 +764,41 @@ class ZoneRuntime:
         if frame is None:
             frame = np.zeros((count, 3), dtype=np.float32)
         self._draw_firmware(frame, ctx, self._copy_targets)
+        self._fx = fx_joined(drawn_in_space)
         return frame
 
+    def _in_space(
+        self,
+        layer: Layer,
+        effect: FieldEffect | ParticleEffect,
+        ctx: RenderContext,
+        view: LayerView,
+    ) -> Fx | None:
+        """What the layer draws in space, on the map at its opacity (the view's in_home());
+        None: nothing. An effect that fails to say loses its fx, logged at most once a
+        minute, never its frame: the lights come first."""
+        try:
+            fx = effect.in_space(ctx, view.leds)
+            if fx is None or fx.empty:
+                return None
+            placed = view.in_home(fx)
+        except Exception as exc:
+            stamp = time.monotonic()
+            if stamp - self._last_fx_log >= CRASH_LOG_INTERVAL_S:
+                self._last_fx_log = stamp
+                logger.warning(
+                    "Zone {}: layer '{}' couldn't say what it draws in space ({}: {})",
+                    self.zone_id,
+                    layer.name,
+                    type(exc).__name__,
+                    exc,
+                )
+            return None
+        if layer.opacity != 1.0:
+            opacity = np.float32(layer.opacity)
+            placed = placed.recoloured(lambda colours: colours * opacity)
+        return None if placed.empty else placed
+
     def _draw_firmware(
         self,
         frame: FloatRGB,
```

In `src/dj_ledfx/zones/frames.py`:

```diff
diff --git a/src/dj_ledfx/zones/frames.py b/src/dj_ledfx/zones/frames.py
index 8b20f21..bd66894 100644
--- a/src/dj_ledfx/zones/frames.py
+++ b/src/dj_ledfx/zones/frames.py
@@ -6,12 +6,16 @@ now, whether it is sent to the light or not; the preview stream is the preview r
 Watchers says which streams any WebSocket session watches: a zone draws the lights that
 run their own effect only for the web app, so only while the live stream is watched
 (constraint 3), and a preview nobody watches ends (Review Focus 1).
+
+What each zone draws in space (the `fx` channel, web spec §12.4) is read from the same
+rings at the same moment: the newest frame's at or before now, never blended.
 """
 
 from __future__ import annotations
 
 import time
 from collections.abc import Callable, Collection, Iterable
+from dataclasses import dataclass
 from typing import TYPE_CHECKING, Literal
 
 import numpy as np
@@ -20,6 +24,7 @@ from numpy.typing import NDArray
 from dj_ledfx.scheduling.route import to_device_colors
 
 if TYPE_CHECKING:
+    from dj_ledfx.effects.fx import Fx
     from dj_ledfx.zones.runtime import ZoneRuntime
 
 Stream = Literal["live", "preview"]
@@ -49,6 +54,17 @@ class Watchers:
 Runtimes = Callable[[], list["ZoneRuntime"]]
 
 
+@dataclass(frozen=True, slots=True)
+class ZoneFx:
+    """What one zone's frame for now draws in space: which stream it belongs with, the
+    zone, its fx on the map before brightness, and the zone's brightness."""
+
+    stream: Stream
+    zone_id: str
+    fx: Fx
+    brightness: float
+
+
 class FrameFeed:
     def __init__(
         self,
@@ -83,3 +99,16 @@ class FrameFeed:
             for piece in pieces:
                 out[piece.device_id] = whole[piece.start : piece.stop]
         return out
+
+    def fx(self) -> list[ZoneFx]:
+        """What each zone draws in space now, live zones first, then the preview: the newest
+        frame's fx at or before now (RingBuffer.frame_at), never blended. A zone whose frame
+        draws nothing is left out."""
+        now = self._clock()
+        out: list[ZoneFx] = []
+        for stream in STREAMS:
+            for runtime in self._runtimes[stream]():
+                frame = runtime.ring.frame_at(now)
+                if frame is not None and frame.fx is not None:
+                    out.append(ZoneFx(stream, runtime.zone_id, frame.fx, runtime.brightness))
+        return out
```

- [ ] **Step 4: Run the task's tests, and the perf run's new ones**

```bash
uv run pytest tests/effects/test_ring_buffer.py tests/zones/test_runtime_fx.py tests/zones/test_frames.py -q 2>&1 | tail -1
uv run pytest -m perf tests/zones/test_runtime_perf.py -k draws_in_space -q 2>&1 | tail -1
```

Expected: `17 passed`, then `15 passed`: the eleven particle looks and the four looks with field effects in space (Shockwave's two layers in one look). When this plan was written the heaviest frame was 1.03 ms (vortex) and the largest fx share 0.21 ms (fountain); the field looks' share is under 0.01 ms.

- [ ] **Step 5: The gate**

```bash
uv run ruff format src/dj_ledfx tests/zones tests/effects && uv run ruff check --fix src/dj_ledfx tests/zones tests/effects
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `2805 passed, 1 skipped, 94 deselected`, `374 files already formatted`, `Found 16 errors in 4 files (checked 167 source files)`, and `94 passed` (Before Task 1's 79 and these 15).

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/types.py src/dj_ledfx/effects/ring_buffer.py src/dj_ledfx/zones/runtime.py src/dj_ledfx/zones/frames.py tests/effects/test_ring_buffer.py tests/zones/test_runtime_fx.py tests/zones/test_frames.py tests/zones/test_runtime_perf.py
git commit -m "feat(zones): each frame keeps what it draws in space, and the feed reads it at now"
```

---

### Task 5: The `fx` channel

The payload (§12.4) from the feed: the zone's brightness, the clip, the rounding, the cap and what's left out (rulings 7 and 8), in `web/fx.py`; the `subscribe_fx` command and a per-session poll in `web/ws.py` (ruling 12), with one message text shared by every session.

**Files:**
- Create: `src/dj_ledfx/web/fx.py`, `tests/web/test_fx_message.py`, `tests/web/test_ws_fx.py`
- Modify: `src/dj_ledfx/web/ws.py`, `src/dj_ledfx/web/state.py`, `src/dj_ledfx/web/app.py`

**Interfaces:**
- Consumes: Task 4's `ZoneFx` and `FrameFeed.fx()` (`app.state.frame_feed`); `ClientSubscription.frame_protocol`.
- Produces: `fx_message(shown: Sequence[ZoneFx]) -> dict[str, Any]`, `FX_FPS = 30.0`, `MAX_FX_PARTICLES = 500`, `DECIMALS = 3` in `web/fx.py`; `ClientSubscription.fx: bool = False`; `app.state.fx_cache`; `fx_text(app) -> str | None` and `_fx_poll(ws, app, sub)` in `web/ws.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_fx_message.py`:

```python
"""The `fx` channel's message (web spec §12.4, "The `fx` payload")."""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from dj_ledfx.effects.fx import Fx, Rings, planes, rings
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.web.fx import MAX_FX_PARTICLES, fx_message
from dj_ledfx.zones.frames import Stream, ZoneFx


def _shown(fx: Fx, brightness: float = 1.0, stream: Stream = "live") -> ZoneFx:
    return ZoneFx(stream, "z", fx, brightness)


def _both_forms() -> Rings:
    sphere = rings([0.0, 1.0, 1.0], 1.5, 0.3, (1.0, 0.0, 0.0))
    circle = rings([3.0, 3.0, 0.0], 2.0, 0.3, (1.0, 0.0, 0.0), circle=True)
    return Rings(
        *(
            np.concatenate([getattr(sphere, name), getattr(circle, name)])
            for name in ("centre", "radius", "width", "colour", "circle")
        )
    )


def test_each_kind_is_sent_as_the_payload_names_it() -> None:
    fx = Fx(
        particles=swarm([[1.0, 2.0, 0.5]], (1.0, 0.5, 0.25), 0.2),
        rings=_both_forms(),
        planes=planes(
            [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]],
            [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
            0.4,
            (0.0, 0.0, 1.0),
            ray=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        ),
    )

    message = fx_message([_shown(fx), _shown(fx, stream="preview")])

    assert message["channel"] == "fx"
    live, preview = message["zones"]
    assert (live["zoneId"], live["stream"], preview["stream"]) == ("z", "live", "preview")
    assert live["particles"] == [[1.0, 2.0, 0.5, 1.0, 0.5, 0.25, 0.2]]  # x y z r g b size
    red = [1.0, 0.0, 0.0]
    assert live["rings"] == [
        {"center": [0.0, 1.0, 1.0], "radius": 1.5, "width": 0.3, "rgb": red, "form": "sphere"},
        {"center": [3.0, 3.0, 0.0], "radius": 2.0, "width": 0.3, "rgb": red, "form": "circle"},
    ]
    # A whole plane has no ray; a beam's ray says which half of it is lit.
    blue = [0.0, 0.0, 1.0]
    assert live["planes"] == [
        {"point": [1.0, 1.0, 1.0], "normal": [0.0, 0.0, 1.0], "width": 0.4, "rgb": blue},
        {
            "point": [2.0, 2.0, 2.0],
            "normal": [0.0, 1.0, 0.0],
            "width": 0.4,
            "rgb": blue,
            "ray": [1.0, 0.0, 0.0],
        },
    ]
    json.dumps(message, allow_nan=False)  # plain JSON


def test_colours_carry_the_zones_brightness_clipped_and_numbers_round_to_3_places() -> None:
    fx = Fx(particles=swarm([[1.23456, 0.0, 1.0]], (0.8, 1.6, 0.123456), 0.15))
    [zone] = fx_message([_shown(fx, brightness=0.5)])["zones"]
    assert zone["particles"] == [[1.235, 0.0, 1.0, 0.4, 0.8, 0.062, 0.15]]
    [zone] = fx_message([_shown(fx, brightness=1.0)])["zones"]
    assert zone["particles"][0][3:6] == [0.8, 1.0, 0.123]  # 1.6 clipped to 1


def test_what_rounds_to_black_or_holds_a_nan_is_left_out_and_so_is_an_empty_zone() -> None:
    fx = Fx(
        particles=swarm(
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [np.nan, 0.0, 1.0]],
            [[1.0, 1.0, 1.0], [0.0004, 0.0, 0.0], [1.0, 1.0, 1.0]],
            0.2,
        ),
        rings=rings([0.0, 0.0, 0.0], np.inf, 0.1, (1.0, 1.0, 1.0)),
        planes=planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 0.0, 0.0)),
    )
    [zone] = fx_message([_shown(fx)])["zones"]
    assert zone["particles"] == [[0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.2]]
    assert "rings" not in zone and "planes" not in zone  # a kind with nothing is left out

    dark = _shown(fx, brightness=0.0)
    assert fx_message([dark]) == {"channel": "fx", "zones": []}
    assert fx_message([]) == {"channel": "fx", "zones": []}


def test_a_zone_sends_its_newest_particles_up_to_the_cap() -> None:
    count = MAX_FX_PARTICLES + 20
    places = [[i / 100.0, 0.0, 1.0] for i in range(count)]  # oldest first
    [zone] = fx_message([_shown(Fx(particles=swarm(places, (1.0, 1.0, 1.0), 0.1)))])["zones"]
    assert len(zone["particles"]) == MAX_FX_PARTICLES
    assert zone["particles"][0][0] == pytest.approx(0.2)  # the 20 oldest are cut
    assert zone["particles"][-1][0] == pytest.approx((count - 1) / 100.0)


@pytest.mark.perf
def test_two_full_zones_encode_well_inside_a_frame() -> None:
    rng = np.random.default_rng(1)
    full = Fx(
        particles=swarm(
            rng.uniform(0.0, 8.0, (MAX_FX_PARTICLES, 3)),
            rng.uniform(0.0, 1.0, (MAX_FX_PARTICLES, 3)),
            0.2,
        ),
        rings=rings(rng.uniform(0.0, 8.0, (8, 3)), 2.0, 0.3, (1.0, 0.5, 0.0)),
        planes=planes(rng.uniform(0.0, 8.0, (2, 3)), (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 1.0)),
    )
    shown = [_shown(full), _shown(full, stream="preview")]
    durations = []
    for _ in range(50):
        started = time.perf_counter()
        json.dumps(fx_message(shown))
        durations.append(time.perf_counter() - started)
    assert sorted(durations)[25] < 0.0025  # half a frame's budget, for every session at once
```

Create `tests/web/test_ws_fx.py`:

```python
"""The `fx` channel (web spec §12.4): what each zone draws in space, to the sessions that ask
for it and speak frame protocol 2, at most 30 times a second and only on a change."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from loguru import logger

from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.web.app import create_app
from dj_ledfx.web.fx import FX_FPS
from dj_ledfx.web.state import ClientSubscription
from dj_ledfx.web.ws import _fx_poll, fx_text
from dj_ledfx.zones.frames import Watchers, ZoneFx
from tests.web.conftest import mock_deps, until


def _dot(x: float = 1.0) -> Fx:
    return Fx(particles=swarm([[x, 0.0, 1.0]], (1.0, 1.0, 1.0), 0.2))


class FxFeed:
    """A FrameFeed whose zones draw what a test sets in `shown`."""

    def __init__(self, *shown: ZoneFx) -> None:
        self.shown = list(shown)

    def frames(self, stream: str, wanted: Any = None) -> dict[str, Any]:
        return {}

    def fx(self) -> list[ZoneFx]:
        return list(self.shown)


class Socket:
    """A session's socket: the texts sent to it."""

    def __init__(self) -> None:
        self.texts: list[dict[str, Any]] = []

    async def send_text(self, text: str) -> None:
        self.texts.append(json.loads(text))


def _app(feed: FxFeed) -> Any:
    return SimpleNamespace(state=SimpleNamespace(frame_feed=feed, fx_cache=None))


async def _polled(
    feed: FxFeed, sub: ClientSubscription, *steps: Any, each_s: float = 0.1
) -> list[list[dict[str, Any]]]:
    """Run the session's fx poll; between steps (callables), wait `each_s`. The messages
    sent during each wait, in order."""
    socket = Socket()
    task = asyncio.create_task(_fx_poll(socket, _app(feed), sub))  # type: ignore[arg-type]
    sent: list[list[dict[str, Any]]] = []
    try:
        for step in (lambda: None, *steps):
            step()
            seen = len(socket.texts)
            await asyncio.sleep(each_s)
            sent.append(socket.texts[seen:])
    finally:
        task.cancel()
        await asyncio.wait([task])
    return sent


async def test_a_session_gets_the_picture_once_then_nothing_while_nothing_changes() -> None:
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    sub = ClientSubscription(frame_protocol=2, fx=True)

    def moved() -> None:
        feed.shown = [ZoneFx("live", "z", _dot(2.0), 1.0)]

    def stopped() -> None:
        feed.shown = []

    first, *_, after_move, after_stop, quiet = await _polled(
        feed, sub, lambda: None, moved, stopped, lambda: None
    )

    assert [m["zones"][0]["particles"][0][0] for m in first] == [1.0]
    assert [m["zones"][0]["particles"][0][0] for m in after_move] == [2.0]
    assert after_stop == [{"channel": "fx", "zones": []}]  # once, as the last zone stops
    assert quiet == []


async def test_a_brightness_change_is_a_change() -> None:
    dot = _dot()
    feed = FxFeed(ZoneFx("live", "z", dot, 1.0))

    def dimmed() -> None:
        feed.shown = [ZoneFx("live", "z", dot, 0.5)]

    first, after = await _polled(feed, ClientSubscription(frame_protocol=2, fx=True), dimmed)
    assert first[0]["zones"][0]["particles"][0][3] == 1.0
    assert [m["zones"][0]["particles"][0][3] for m in after] == [0.5]


async def test_only_a_protocol_2_session_that_asked_gets_fx_and_turning_on_resends() -> None:
    feed = FxFeed(ZoneFx("preview", "z", _dot(), 1.0))
    sub = ClientSubscription(frame_protocol=1, fx=True)

    def speaks_2() -> None:
        sub.frame_protocol = 2

    def off() -> None:
        sub.fx = False

    def on() -> None:
        sub.fx = True

    v1, v2, after_off, after_on = await _polled(feed, sub, speaks_2, off, on)

    assert v1 == []
    assert [m["zones"][0]["stream"] for m in v2] == ["preview"]
    assert after_off == []
    assert len(after_on) == 1  # the whole picture again, though nothing changed


async def test_fx_go_out_at_most_30_times_a_second() -> None:
    feed = FxFeed()
    sub = ClientSubscription(frame_protocol=2, fx=True)
    socket = Socket()

    class Moving(FxFeed):
        def fx(self) -> list[ZoneFx]:  # a new frame every time it's asked
            return [ZoneFx("live", "z", _dot(), 1.0)]

    del feed
    task = asyncio.create_task(_fx_poll(socket, _app(Moving()), sub))  # type: ignore[arg-type]
    await asyncio.sleep(0.5)
    task.cancel()
    await asyncio.wait([task])
    assert 0 < len(socket.texts) <= 0.5 * FX_FPS + 1


def test_every_session_shares_one_message_until_a_frame_changes() -> None:
    dot = _dot()
    feed = FxFeed(ZoneFx("live", "z", dot, 1.0))
    app = _app(feed)
    text = fx_text(app)
    assert text is not None and fx_text(app) is text  # made once
    feed.shown = [ZoneFx("live", "z", _dot(), 1.0)]  # the same place, another frame
    assert fx_text(app) is not text
    assert fx_text(SimpleNamespace(state=SimpleNamespace(frame_feed=None, fx_cache=None))) is None


def test_subscribe_fx_is_acked_and_sends_fx_over_the_socket() -> None:
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    feed = FxFeed(ZoneFx("live", "z", _dot(), 1.0))
    app = create_app(**mock_deps(scheduler=scheduler, frame_feed=feed, frame_watchers=Watchers()))

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "subscribe_fx", "on": "yes", "id": 1})
        error = until(ws, "error")
        assert error == {
            "channel": "error",
            "id": 1,
            "detail": "subscribe_fx takes on: true or false",
        }
        ws.send_json({"action": "subscribe_frames", "protocol": 2, "id": 2})
        until(ws, "ack")
        ws.send_json({"action": "subscribe_fx", "on": True, "id": 3})
        assert until(ws, "ack") == {
            "channel": "ack",
            "id": 3,
            "action": "subscribe_fx",
            "on": True,
        }
        message = until(ws, "fx")

    assert message["zones"] == [
        {"zoneId": "z", "stream": "live", "particles": [[1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.2]]}
    ]


async def test_a_message_that_cant_be_made_ends_the_channel_once_with_a_log() -> None:
    class Broken(FxFeed):
        def fx(self) -> list[ZoneFx]:
            raise RuntimeError("no fx")

    errors: list[str] = []
    sink = logger.add(lambda message: errors.append(str(message)), level="ERROR")
    socket = Socket()
    sub = ClientSubscription(frame_protocol=2, fx=True)
    try:
        await asyncio.wait_for(_fx_poll(socket, _app(Broken()), sub), 1.0)  # type: ignore[arg-type]
    finally:
        logger.remove(sink)
    assert socket.texts == [] and len(errors) == 1 and "RuntimeError: no fx" in errors[0]
```

- [ ] **Step 2: Run them, to see them fail**

```bash
uv run pytest tests/web/test_fx_message.py tests/web/test_ws_fx.py -q 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'dj_ledfx.web.fx'`, collecting both.

- [ ] **Step 3: Write the message and the channel**

Create `src/dj_ledfx/web/fx.py`:

```python
"""The `fx` channel's message (web spec §12.4, "The `fx` payload"): what each zone draws in
space now, in the home map's frame, for the stage's "Effects in space".

Colours are the frame's times the zone's brightness, clipped to 0..1, and every number is
rounded to 3 decimals. An item whose colour rounds to black, or that holds a number JSON
can't carry, is left out, and so is a zone left with nothing. Past MAX_FX_PARTICLES a zone
keeps its newest particles, as a particle effect's step keeps its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.zones.frames import ZoneFx

FX_FPS = 30.0  # at most this many fx messages a second, to each session
# A zone's particles in one message, for each stream: the effects' own cap (MAX_PARTICLES),
# so a particle layer is never cut unless a mirror doubles it or layers add up. A full zone
# is about 25 KB of JSON and takes under a millisecond to encode; this home's particle looks
# make at most 76 at their defaults and 380 at their largest settings.
MAX_FX_PARTICLES = 500
DECIMALS = 3
_RGB = slice(3, 6)  # every table below has its colour in columns 3 to 5


def fx_message(shown: Sequence[ZoneFx]) -> dict[str, Any]:
    """The whole picture, one entry for each zone that draws anything: it replaces the last."""
    zones = [zone for zone in (_zone(each) for each in shown) if zone is not None]
    return {"channel": "fx", "zones": zones}


def _zone(shown: ZoneFx) -> dict[str, Any] | None:
    fx, scale = shown.fx, shown.brightness
    out: dict[str, Any] = {"zoneId": shown.zone_id, "stream": shown.stream}
    particles = fx.particles.newest(MAX_FX_PARTICLES)
    rows, _ = _table(particles.pos, _lit(particles.colour, scale), particles.radius)
    if len(rows):
        out["particles"] = rows.tolist()  # x, y, z, r, g, b, size
    rings = fx.rings
    rows, kept = _table(rings.centre, _lit(rings.colour, scale), rings.radius, rings.width)
    if len(rows):
        out["rings"] = [
            {
                "center": row[0:3],
                "radius": row[6],
                "width": row[7],
                "rgb": row[_RGB],
                "form": "circle" if circle else "sphere",
            }
            for row, circle in zip(rows.tolist(), rings.circle[kept].tolist(), strict=True)
        ]
    planes = fx.planes
    rows, _ = _table(
        planes.point, _lit(planes.colour, scale), planes.normal, planes.width, planes.ray
    )
    if len(rows):
        out["planes"] = [_plane(row) for row in rows.tolist()]
    return out if len(out) > 2 else None


def _plane(row: list[float]) -> dict[str, Any]:
    plane: dict[str, Any] = {
        "point": row[0:3],
        "normal": row[6:9],
        "width": row[9],
        "rgb": row[_RGB],
    }
    if any(row[10:13]):  # a ray: the half of the plane on its side of the point
        plane["ray"] = row[10:13]
    return plane


def _lit(colour: NDArray[np.float32], scale: float) -> NDArray[np.float64]:
    """Colours at the zone's brightness, 0..1."""
    return np.clip(colour.astype(np.float64) * scale, 0.0, 1.0)


def _table(*columns: NDArray[Any]) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """The columns side by side, a row for each item, rounded; the rows kept (finite, and
    not black once rounded), and which those were."""
    rows = np.round(np.concatenate([_column(c) for c in columns], 1), DECIMALS)
    kept = np.isfinite(rows).all(axis=1) & (rows[:, _RGB].max(axis=1, initial=0.0) > 0.0)
    return rows[kept], kept


def _column(values: NDArray[Any]) -> NDArray[np.float64]:
    """Values as rows of a table, (K,) as (K, 1): none at all still has its width."""
    width = int(np.prod(values.shape[1:]))
    return np.asarray(values, dtype=np.float64).reshape(len(values), width)
```

In `src/dj_ledfx/web/state.py`:

```diff
diff --git a/src/dj_ledfx/web/state.py b/src/dj_ledfx/web/state.py
index e38cd4a..d16f7c7 100644
--- a/src/dj_ledfx/web/state.py
+++ b/src/dj_ledfx/web/state.py
@@ -32,6 +32,7 @@ class ClientSubscription:
     frame_devices: list[str] = field(default_factory=list)  # v1: device ids; empty = all
     frame_lights: list[str] = field(default_factory=list)  # v2: light ids; empty = all
     frame_streams: list[str] = field(default_factory=lambda: ["live"])  # v1: live only
+    fx: bool = False  # subscribe_fx {on}: the fx channel, while it speaks frame protocol 2
 
 
 def get_db(request: Request) -> StateDB:
```

In `src/dj_ledfx/web/app.py`:

```diff
diff --git a/src/dj_ledfx/web/app.py b/src/dj_ledfx/web/app.py
index 0efa52b..54c9457 100644
--- a/src/dj_ledfx/web/app.py
+++ b/src/dj_ledfx/web/app.py
@@ -155,6 +155,7 @@ def create_app(
     app.state.discovery_orchestrator = discovery_orchestrator  # scans and lamp outputs
     app.state.ws_sessions = set()  # open /ws sessions: pushes go to them, ws.close_all ends them
     app.state.ws_closing = False
+    app.state.fx_cache = None  # the last fx message, and what it was made of (ws.fx_text)
 
     @app.on_event("startup")
     async def _start_broadcasts() -> None:
```

In `src/dj_ledfx/web/ws.py`:

```diff
diff --git a/src/dj_ledfx/web/ws.py b/src/dj_ledfx/web/ws.py
index d4b3bd9..ac49ca7 100644
--- a/src/dj_ledfx/web/ws.py
+++ b/src/dj_ledfx/web/ws.py
@@ -1,5 +1,5 @@
-"""Multiplexed WebSocket hub: beat, stats, status and frame channels, the pushed snapshots,
-and the tap command."""
+"""Multiplexed WebSocket hub: beat, stats, status, frame and fx channels, the pushed
+snapshots, and the tap command."""
 
 from __future__ import annotations
 
@@ -17,6 +17,7 @@ from dj_ledfx.tempo.model import DecksChanged, TempoChanged, TempoError
 from dj_ledfx.types import is_finite_number
 from dj_ledfx.web import contract
 from dj_ledfx.web.frames import encode_frame_v1, encode_frame_v2, light_frames
+from dj_ledfx.web.fx import FX_FPS, fx_message
 from dj_ledfx.web.state import ClientSubscription, get_tempo, light_index, listening
 from dj_ledfx.zones.frames import STREAMS
 from dj_ledfx.zones.model import AttentionChanged, LightsChanged, PreviewOnlyChanged, ZonesChanged
@@ -391,6 +392,48 @@ def frame_messages(app: Any, sub: ClientSubscription, seq: int) -> list[bytes]:
     ]
 
 
+async def _fx_poll(ws: WebSocket, app: Any, sub: ClientSubscription) -> None:
+    """The fx channel, FX_FPS a second at most, while the session asks for it and speaks
+    frame protocol 2: only a message that differs from the last one it was sent, so nothing
+    while nothing changes, and one with no zones once the last zone stops drawing. A
+    session that turns it on again gets the whole picture at once."""
+    last: str | None = None
+    while True:
+        await asyncio.sleep(1.0 / FX_FPS)
+        if not sub.fx or sub.frame_protocol != 2:
+            last = None
+            continue
+        try:
+            text = fx_text(app)
+        except Exception:  # a bug: say so once, and leave the session its other channels
+            logger.exception("The fx channel stopped for a session")
+            return
+        if text is None or text == last:
+            continue
+        try:
+            await ws.send_text(text)
+        except Exception:
+            return
+        last = text
+
+
+def fx_text(app: Any) -> str | None:
+    """The fx message for now, as JSON text: made once for every session, and again only
+    when a zone's frame for now, or its brightness, is another one. None: no frame feed."""
+    feed = getattr(app.state, "frame_feed", None)
+    if feed is None:
+        return None
+    shown = feed.fx()
+    # Fx compares by identity, so a key holds the very frames' fx it was made from.
+    key = tuple((each.stream, each.zone_id, each.fx, each.brightness) for each in shown)
+    cached: tuple[tuple[Any, ...], str] | None = app.state.fx_cache
+    if cached is not None and cached[0] == key:
+        return cached[1]
+    text = json.dumps(fx_message(shown))
+    app.state.fx_cache = (key, text)
+    return text
+
+
 def _subscribe_frames(sub: ClientSubscription, msg: dict[str, Any]) -> None:
     """subscribe_frames: v2 with "protocol": 2 (ruling 3), else v1 as the old UI sends it.
     Everything is checked before the subscription changes."""
@@ -464,6 +507,20 @@ async def _handle_command(
             {"channel": "ack", "id": cmd_id, "action": action, "protocol": sub.frame_protocol},
         )
 
+    elif action == "subscribe_fx":
+        on = msg.get("on")
+        if not isinstance(on, bool):
+            detail = "subscribe_fx takes on: true or false"
+            await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": detail})
+            return
+        sub.fx = on
+        has_fx_task = any(not t.done() and t.get_name() == "fx_poll" for t in tasks)
+        if on and not has_fx_task:
+            task = asyncio.create_task(_fx_poll(ws, app, sub))
+            task.set_name("fx_poll")
+            tasks.append(task)
+        await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action, "on": on})
+
     elif action == "tap":  # saved by the clock's run(), within 0.25 s
         try:
             get_tempo(app).tap(contract.TapRequest.model_validate(msg).client_time)
```

- [ ] **Step 4: Run the task's tests**

```bash
uv run pytest tests/web/test_fx_message.py tests/web/test_ws_fx.py tests/web/test_ws.py tests/web/test_ws_frames.py tests/web/test_ws_channels.py -q 2>&1 | tail -1
uv run pytest -m perf tests/web/test_fx_message.py -q 2>&1 | tail -1
(cd web && npm run api:check)
```

Expected: all pass (the two new files alone: `11 passed, 1 deselected`), then `1 passed`, then `api types match`: the WebSocket channels aren't in the OpenAPI schema, so no generated type changes.

- [ ] **Step 5: The gate**

```bash
uv run ruff format src/dj_ledfx/web tests/web && uv run ruff check --fix src/dj_ledfx/web tests/web
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
```

Expected: `2816 passed, 1 skipped, 95 deselected` with `976 warnings` (the one new test that builds the web app adds FastAPI's 4), `377 files already formatted`, `Found 16 errors in 4 files (checked 168 source files)`, and `95 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/web/fx.py src/dj_ledfx/web/ws.py src/dj_ledfx/web/state.py src/dj_ledfx/web/app.py tests/web/test_fx_message.py tests/web/test_ws_fx.py
git commit -m "feat(web): the fx channel, for sessions that subscribe"
```

---

### Task 6: Check it on this home

A dry run on a copy of the deployed app's `state.db`, with no light backend: the home's real lights are offline ghosts and nothing reaches one, so the branch opens no Govee transport and the deployed app keeps UDP 4002 to itself; Pro DJ Link listens on a loopback port, so it keeps UDP 50001 too. It touches no light and changes nothing in the deployed app, so it needs no owner go (ruling 15). A probe previews each of the eleven particle looks and each look with a field effect in space (Shockwave, with the shell and the beam, Speaker waves, Ripples and Scanner: the five field effects in four looks) on the room with the most lights, and checks that each sends what §12.4's "What draws what" says, well formed; then the session rules, a live zone with preview-only on, and Stop all's one empty message. There is no step on the real lights: F10's stage is where the owner looks at fx, and its plan has that check.

Report only counts and yes or no, in the PR and anywhere else: no light ids, addresses, model names, room names or the home's location. The probe prints counts, yes or no and look ids.

The branch serves on a port of its own, since the deployed app holds 8080 and 8081 belongs to another service. Each shell this task opens starts from the same two values, set once in a file:

```bash
printf 'PORT=8098\nW=/home/anirudhlath/code/.worktrees/dj-ledfx/m8-fx\n' > /tmp/m8-live.env
. /tmp/m8-live.env && ss -ltn | grep -c ":$PORT "
```

Expected: `0`, the port is free. If it isn't, pick another free port above 8090 and write it into the file. Every block below starts with `. /tmp/m8-live.env`.

If the dry run stops answering, or is still running 15 s after a Ctrl-C (`kill -INT`), run `kill -USR1 "$(pgrep -P "$(cat /tmp/m8-dry/pid)")"` first (the Python process `uv run` started: its driver then writes every thread's stack into its log), then `kill -9` the same process, and tell the owner.

**Files:**
- Create (outside the repo): `/tmp/m8-live.env`, `/tmp/m8-dry/run.py`, `/tmp/m8-wait.py`, `/tmp/m8-fx-probe.py`

- [ ] **Step 1: Snapshot the deployed state (read-only)**

One read-only process in the deployed container reads its database; nothing there changes and no light is touched.

```bash
. /tmp/m8-live.env && cd "$W"
mkdir -p /tmp/m8-dry && rm -f /tmp/m8-dry/state.db
docker exec dj-ledfx-app-1 python -c "import sqlite3, sys; db = sqlite3.connect('file:/app/state/state.db?mode=ro', uri=True); sys.stdout.write('\n'.join(db.iterdump()))" > /tmp/m8-dry/dump.sql
uv run python -c "import sqlite3; db = sqlite3.connect('/tmp/m8-dry/state.db'); db.executescript(open('/tmp/m8-dry/dump.sql').read()); db.close()"
uv run python -c "import sqlite3; db = sqlite3.connect('/tmp/m8-dry/state.db'); print(db.execute('select count(*) from devices').fetchone()[0], 'devices,', db.execute('select count(*) from zone_assignments').fetchone()[0], 'zone assignments')"
curl -s http://127.0.0.1:8080/api/running | uv run python -c "import json, sys; print(len(json.load(sys.stdin)['zones']), 'zones running')"
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
```

Expected: the device count the deployed app knows, as many zone assignments as it has zones running, and one line, `0.0.0.0:4002 uid:10001`: the deployed app holds 4002.

- [ ] **Step 2: Write the scripts**

`/tmp/m8-dry/run.py`, the real entry point with no light backend. Each backend opens its own transport (the Govee one binds UDP 4002), and the app makes them only from this registry, so with it empty nothing is discovered or reached:

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

`/tmp/m8-wait.py`, which waits for an app to answer or for a process to end, so no shell loop has to sleep:

```python
"""Wait for an app: `m8-wait.py URL SECONDS` until the URL answers, `m8-wait.py --gone PID
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

`/tmp/m8-fx-probe.py`, which previews (a preview never reaches a light), holds two sockets (one on frame protocol 2, one left on protocol 1), and starts one look live with preview-only on:

```python
"""M8 probe: the fx channel on this home's data, with no light. Previews each look that draws
in space on the room with the most lights and checks what its fx say against web spec
§12.4; then the sessions' rules, and a live zone with preview-only on. It prints counts and
yes or no: no ids of lights, names or addresses."""

import asyncio
import copy
import json
import math
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

BASE = sys.argv[1]  # the branch: http://127.0.0.1:$PORT
# The field effects that draw in space, and what each sends (§12.4, "What draws what").
FIELDS = {
    "shockwave_shell": "sphere rings",
    "speaker_waves": "sphere rings",
    "ripples": "circle rings",
    "scanner_plane": "a level plane",
    "lighthouse_beam": "a plane with a ray",
}
WINDOW_S = 2.0
Fx = list[dict[str, Any]]  # the fx messages, in order


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


async def fx_messages(ws: ClientConnection, seconds: float) -> Fx:
    """The fx messages on the socket for a while; everything else is let go."""
    found: Fx = []
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        try:
            message = await asyncio.wait_for(ws.recv(), left)
        except TimeoutError:
            break
        if isinstance(message, str) and (parsed := json.loads(message)).get("channel") == "fx":
            found.append(parsed)
    return found


async def acked(ws: ClientConnection, command: dict[str, Any]) -> dict[str, Any]:
    await ws.send(json.dumps(command))
    async with asyncio.timeout(5):
        while True:
            message = await ws.recv()
            if isinstance(message, str) and json.loads(message).get("id") == command["id"]:
                return json.loads(message)


def entries(messages: Fx, zone_id: str, stream: str) -> list[dict[str, Any]]:
    """The zone's entries on one stream, message by message."""
    return [z for m in messages for z in m["zones"] if (z["zoneId"], z["stream"]) == (zone_id, stream)]


def numbers(value: Any) -> list[float]:
    if isinstance(value, list):
        return [n for each in value for n in numbers(each)]
    if isinstance(value, dict):
        return [n for key, each in value.items() if key != "form" for n in numbers(each)]
    return [float(value)] if isinstance(value, (int, float)) else []


def well_formed(zone: dict[str, Any]) -> bool:
    """Every number finite and to 3 places, colours 0..1, and each item the payload's shape."""
    every = numbers({k: v for k, v in zone.items() if k not in ("zoneId", "stream")})
    if not all(math.isfinite(n) and abs(n * 1000 - round(n * 1000)) < 1e-6 for n in every):
        return False
    rgbs = [p[3:6] for p in zone.get("particles", [])]
    rgbs += [item["rgb"] for kind in ("rings", "planes") for item in zone.get(kind, [])]
    shapes = all(len(p) == 7 and p[6] > 0 for p in zone.get("particles", []))
    shapes &= all(
        set(r) == {"center", "radius", "width", "rgb", "form"} and r["form"] in ("sphere", "circle")
        for r in zone.get("rings", [])
    )
    shapes &= all(set(p) in ({"point", "normal", "width", "rgb"}, {"point", "normal", "width", "rgb", "ray"}) for p in zone.get("planes", []))
    return shapes and all(0.0 <= c <= 1.0 for rgb in rgbs for c in rgb) and any(max(rgb) > 0 for rgb in rgbs)


def drawn(zones: list[dict[str, Any]]) -> dict[str, int]:
    """How many entries held each thing the spec names."""
    count = dict.fromkeys(("particles", "sphere rings", "circle rings", "a level plane", "a plane with a ray"), 0)
    for zone in zones:
        count["particles"] += bool(zone.get("particles"))
        forms = {r["form"] for r in zone.get("rings", [])}
        count["sphere rings"] += "sphere" in forms
        count["circle rings"] += "circle" in forms
        planes = zone.get("planes", [])
        count["a level plane"] += any("ray" not in p and p["normal"] == [0.0, 0.0, 1.0] for p in planes)
        count["a plane with a ray"] += any("ray" in p for p in planes)
    return count


async def preview(ws: ClientConnection, zone_id: str, look: str | dict[str, Any]) -> Fx:
    """A look's fx over WINDOW_S: a look by its id, or a draft."""
    body = {"zoneId": zone_id, **({"lookId": look} if isinstance(look, str) else {"look": look})}
    started = ok("POST", "/preview", body)
    await fx_messages(ws, 0.3)  # the last preview's fx still on their way
    messages = await fx_messages(ws, WINDOW_S)
    ok("DELETE", f"/preview/{started['previewId']}")
    return messages


def drafted(look: dict[str, Any], modifiers: dict[str, Any], **layer: Any) -> dict[str, Any]:
    draft = copy.deepcopy(look)
    for each in draft["layers"]:
        if each["type"] != "firmware":
            each.update(layer)
    draft["modifiers"] = {**draft["modifiers"], **modifiers}
    return draft


async def main() -> None:
    zones = ok("GET", "/zones")
    room = max((z for z in zones if z["kind"] == "room"), key=lambda z: len(z["lights"]))
    print(f"zones running at start: {len(ok('GET', '/running')['zones'])}; the room's lights: {len(room['lights'])}")
    looks = [look for look in ok("GET", "/looks") if look["builtIn"]]
    particle_looks = [lk for lk in looks if any(layer["type"] == "particles" for layer in lk["layers"])]
    field_looks = [lk for lk in looks if any(layer["kind"] in FIELDS for layer in lk["layers"])]
    kinds = sorted({layer["kind"] for lk in field_looks for layer in lk["layers"] if layer["kind"] in FIELDS})
    print(f"particle looks: {len(particle_looks)}; looks with field effects in space: {len(field_looks)}, of {len(kinds)} effects")

    url = BASE.replace("http", "ws", 1) + "/ws"
    async with connect(url, max_size=None, max_queue=None) as ws, connect(url) as old:
        frames = {"action": "subscribe_frames", "id": "frames", "fps": 30, "protocol": 2, "streams": ["preview"]}
        await acked(ws, frames)
        ack = await acked(ws, {"action": "subscribe_fx", "id": "fx", "on": True})
        print(f"subscribe_fx acked: {ack == {'channel': 'ack', 'id': 'fx', 'action': 'subscribe_fx', 'on': True}}")
        bad = await acked(ws, {"action": "subscribe_fx", "id": "bad", "on": "yes"})
        print(f"a bad on is an error: {bad.get('channel') == 'error'}")
        await acked(old, {"action": "subscribe_fx", "id": "fx", "on": True})  # speaks protocol 1

        busiest = 0.0
        for look in particle_looks + field_looks:
            messages = await preview(ws, room["id"], look["id"])
            mine = entries(messages, room["id"], "preview")
            busiest = max(busiest, len(messages) / WINDOW_S)
            sends = drawn(mine)
            wanted = ["particles"] if look in particle_looks else [FIELDS[layer["kind"]] for layer in look["layers"] if layer["kind"] in FIELDS]
            most = max((len(z.get("particles", [])) for z in mine), default=0)
            print(
                f"{look['id']}: {len(messages)} messages, {len(mine)} for the preview,"
                f" {' and '.join(wanted)} in {min(sends[w] for w in wanted)},"
                f" well formed {all(well_formed(z) for z in mine)}"
                + (f", most particles {most}" if look in particle_looks else "")
            )
        print(f"most messages a second: {busiest:.1f} (at most 30)")
        print(f"a protocol-1 session got none: {await fx_messages(old, 0.5) == []}")

        comets = next(lk for lk in looks if lk["id"] == "comets")
        every = drafted(
            comets,
            {"trailsS": 1.0, "downbeatFlash": True, "brightnessCap": 0.8, "evening": True},
            mirror={"axis": "x", "at": None},
            transform={"offset": [0.5, 0.0, 0.0], "rotateDeg": 30.0, "scale": 1.5},
        )
        mine = entries(await preview(ws, room["id"], every), room["id"], "preview")
        brightest = max((c for z in mine for p in z.get("particles", []) for c in p[3:6]), default=0.0)
        print(f"comets with every modifier: particles in {drawn(mine)['particles']}, brightest {brightest} (at most 0.8)")

        await acked(ws, {"action": "subscribe_fx", "id": "off", "on": False})
        started = ok("POST", "/preview", {"zoneId": room["id"], "lookId": "fireflies"})
        quiet = await fx_messages(ws, 1.0)
        await acked(ws, {"action": "subscribe_fx", "id": "on", "on": True})
        again = await fx_messages(ws, 0.2)
        ok("DELETE", f"/preview/{started['previewId']}")
        print(f"off: none {quiet == []}; on again: the picture at once {len(again) >= 1}")

        was_preview_only = ok("GET", "/config")["engine"].get("preview_only") is True
        ok("PUT", "/config", {"engine": {"preview_only": True}})
        ok("POST", f"/zones/{room['id']}/start", {"lookId": "fireflies"})
        await fx_messages(ws, 0.5)
        live = entries(await fx_messages(ws, 1.0), room["id"], "live")
        print(f"live: particles in {drawn(live)['particles']} of {len(live)}, well formed {all(well_formed(z) for z in live)}")
        status, _ = call("POST", "/running/stop-all")
        after = await fx_messages(ws, 1.5)
        print(f"Stop all ({status}): {len(after)} message(s), the last empty {bool(after) and after[-1]['zones'] == []}")
        later = await fx_messages(ws, 1.0)
        print(f"then nothing while nothing changes: {later == []}")
        ok("PUT", "/config", {"engine": {"preview_only": was_preview_only}})


asyncio.run(main())
```

- [ ] **Step 3: The dry run**

```bash
. /tmp/m8-live.env && cd "$W"
(uv run python /tmp/m8-dry/run.py --dj-listen 127.0.0.1:0 --web --web-host 127.0.0.1 --web-port "$PORT" --config /tmp/m8-dry/config.toml --db /tmp/m8-dry/state.db > /tmp/m8-dry/app.log 2>&1 & echo $! > /tmp/m8-dry/pid)
uv run python /tmp/m8-wait.py "http://127.0.0.1:$PORT/api/running" 60
ss -Hulnp | grep "pid=$(pgrep -P "$(cat /tmp/m8-dry/pid)")," | awk '{print $4}'
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
timeout 300 uv run --with websockets python /tmp/m8-fx-probe.py "http://127.0.0.1:$PORT"
curl -sf -m 5 "http://127.0.0.1:$PORT/api/running" > /dev/null && echo "still answering"
kill -INT "$(cat /tmp/m8-dry/pid)"; uv run python /tmp/m8-wait.py --gone "$(cat /tmp/m8-dry/pid)" 15
grep -c Traceback /tmp/m8-dry/app.log; grep -c -e "couldn't say what it draws" -e "fx channel stopped" /tmp/m8-dry/app.log
ss -Hulne 'sport = :4002' | awk '{print $4, $6}'
```

`--web-port` wins over the port in the snapshot's config, so the deployed app keeps 8080. The first `ss` lists the UDP sockets the dry run holds, and the other two who holds 4002, while it runs and once it has stopped. When this plan was written, the probe ran on the plan-check worktree against a made-up home of eight ghost lights in one room, with no zones running, and printed:

```text
zones running at start: 0; the room's lights: 8
particle looks: 11; looks with field effects in space: 4, of 5 effects
subscribe_fx acked: True
a bad on is an error: True
fireflies: 59 messages, 59 for the preview, particles in 59, well formed True, most particles 12
embers: 59 messages, 59 for the preview, particles in 59, well formed True, most particles 24
rain: 59 messages, 59 for the preview, particles in 59, well formed True, most particles 20
snow: 58 messages, 58 for the preview, particles in 58, well formed True, most particles 32
spotlights: 42 messages, 42 for the preview, particles in 42, well formed True, most particles 2
bursts: 58 messages, 58 for the preview, particles in 58, well formed True, most particles 42
vortex: 58 messages, 58 for the preview, particles in 58, well formed True, most particles 60
comets: 59 messages, 59 for the preview, particles in 59, well formed True, most particles 18
fountain: 58 messages, 58 for the preview, particles in 58, well formed True, most particles 64
flock: 59 messages, 59 for the preview, particles in 59, well formed True, most particles 40
ball: 59 messages, 59 for the preview, particles in 59, well formed True, most particles 1
ripples: 59 messages, 59 for the preview, circle rings in 59, well formed True
shockwave: 59 messages, 59 for the preview, sphere rings and a plane with a ray in 59, well formed True
scanner: 58 messages, 58 for the preview, a level plane in 58, well formed True
speakers: 58 messages, 58 for the preview, sphere rings in 58, well formed True
most messages a second: 29.5 (at most 30)
a protocol-1 session got none: True
comets with every modifier: particles in 59, brightest 0.75 (at most 0.8)
off: none True; on again: the picture at once True
live: particles in 29 of 29, well formed True
Stop all (204): 1 message(s), the last empty True
then nothing while nothing changes: True
```

Expected on this home:
- `answering`, then one address, `127.0.0.1:` and a port: the dry run's only UDP socket is its Pro DJ Link listener on loopback. Then one line, `0.0.0.0:4002 uid:10001`: the deployed app alone holds 4002. If the dry run lists any other socket, or 4002 shows a second line or another user, stop the dry run at once (`kill -INT "$(cat /tmp/m8-dry/pid)"`) and tell the owner.
- `zones running at start`: the count Step 1 found (they resume on ghosts and send live fx, which the probe's preview lines leave aside).
- `particle looks: 11; looks with field effects in space: 4, of 5 effects`, both acks `True`.
- For each of the fifteen looks, its things in most of its messages (a ball, a spotlight and a ripple can be between frames that draw, so not every message), `well formed True`, and the particle counts at most 500. On a zone with more lamps the swarms draw more particles than on eight.
- `most messages a second` at most 30, even with resumed zones sending live fx: one message carries every zone.
- `a protocol-1 session got none: True`; comets' brightest at most `0.8` (the cap; the zone's brightness may make it lower); `off: none True; on again: the picture at once True`; `live: particles in N of N`, N above 0; `Stop all (204): 1 message(s), the last empty True`; `then nothing while nothing changes: True`.
- `still answering`, `ended`, `0` tracebacks and `0` fx failures in the log, then `0.0.0.0:4002 uid:10001` alone once more.

Anything else is a bug. Fix it in the task that owns the code, with a test, before going on. Tell the owner the results; there is nothing to commit here.

---

### Task 7: CLAUDE.md and the README

M8 adds the fx shapes, a hook on every effect, `LayerView.in_home`, the frames' fx, the feed's read and a channel, so CLAUDE.md's architecture, design decisions, testing and gotchas all need lines, and one gotcha ("Nothing reads `ParticleEffect.particles` before M8") is now wrong. The README's feature list gains one.

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Run the skills**

Run the `claude-md-management:claude-md-improver` skill (audit and targeted updates), then `/claude-md-management:revise-claude-md` for what this branch taught. Both show their changes before writing. Get the owner's go.

- [ ] **Step 2: Check the facts M8 changed are in CLAUDE.md**

Whatever the skills propose, CLAUDE.md must end up saying these, and nothing that contradicts them. Keep design values out of it (CLAUDE.md, "Web App Design").

- **Architecture:**
  - Add `effects/fx.py`: what an effect draws in space, for the stage (web spec §12.4's `fx`): `Fx` of `Particles`, `Rings` (`rings()`: centres, radii, widths, colours, `circle` or a sphere's shell) and `Planes` (`planes()`: points, normals, widths, colours, and a `ray` for a half-plane), in the effect's space, colours before the layer's opacity, the look's modifiers and the zone's brightness; `width` is the e^-1 full thickness, twice the `band()` width; `Fx.recoloured()`, `fx_joined()`, `NO_FX`.
  - The `effects/` line: every effect has `in_space(ctx, leds) -> Fx | None`, None by default, called right after its frame; a particle effect's is its last step's particles; `shockwave_shell`, `speaker_waves` and `ripples` send rings, `scanner_plane` and `lighthouse_beam` planes.
  - The `effects/particles.py` line: `particles`, the last step's, is what `in_space` sends (drop "which M8's `fx` stream can read").
  - The `effects/ring_buffer.py` line: `frame_at(t)`, the newest frame at or before a moment, never blended, the fx's read.
  - The `zones/` lines: the runtime asks each streamed layer for its fx after its frame, maps them onto the map (`LayerView.in_home()`), applies the layer's opacity and the look's evening and cap (not the flash or trails), and writes them into the frame (`RenderedFrame.fx`); a transition's frame carries the new look's; a hook that fails loses its fx, logged at most once a minute, never the frame. `zones/layer_view.py`: `in_home()` (the transform undone, both images of a mirror, the particles the mirror doesn't show left out; the mask weighs particles where they land, and keeps rings and planes whole while it weighs any LED) and `mask_weights_at()`. `zones/frames.py`: `ZoneFx` and `FrameFeed.fx()`, each live then preview runtime's newest frame's fx at or before now.
  - Add `web/fx.py` (`fx_message()`: brightness, clipped, 3 places, items that round to black or aren't finite left out, a zone with nothing left out, the newest `MAX_FX_PARTICLES` (500) a zone; `FX_FPS`), and to the `web/ws.py` line: the `fx` channel, after `subscribe_fx {on}` (an `on` that isn't a bool gets an error), to a session while it speaks frame protocol 2, from its own poll at `FX_FPS`, only when the message differs from the last it sent (the picture at once when it turns on, one with no zones when the last zone stops), one text for all sessions (`fx_text()`, `app.state.fx_cache`).
- **Key design decisions:**
  - What a zone draws in space is worked out with every frame, kept beside its colours, and read at now as the frames are, never blended; brightness applies at encode, as at send.
- **Testing:**
  - `tests/zones/test_runtime_fx.py` (the runtime's fx), `tests/web/test_ws_fx.py` (the channel's sessions, on a fake socket and a fake feed: `FxFeed`, `Socket`, `_polled()`), `tests/web/test_fx_message.py` (the encoder); the perf run adds every look that draws in space at its largest with every modifier, its fx's share under `FX_SHARE_S`, and two full zones encoded.
- **Gotchas:**
  - Remove "Nothing reads `ParticleEffect.particles` before M8".
  - Never call a `ParamField`'s `_per_leds()` with another builder from `in_space`: its cache is keyed by the LEDs alone, so it would hand the render's array back.
  - An `Fx` compares by identity (`eq=False`): the fx cache's key holds the frames' own fx, so a new frame is a new message even when it draws the same.
  - The WebSocket channels' types are written by hand in `web/src/api/contract.ts`; OpenAPI covers REST only, so a channel change regenerates nothing and the web app's types follow by hand.

- [ ] **Step 3: Add the README's feature**

In `README.md`, after the "Particles" bullet, add:

```markdown
- **Effects in space** — the engine tells the web app what each running look draws in space, not only on the lamps: every particle, Shockwave's and Speaker waves' spreading shells, Ripples' rings and the Scanner's and Shockwave's planes, in the home map's frame, live and in previews, on the `fx` WebSocket channel at up to 30 messages a second.
```

- [ ] **Step 4: Check that nothing still promises M8**

```bash
git grep -n -e "before M8" -e "M8's \`fx\` stream can read" -- . ':!docs'
```

Expected: no lines (git grep exits 1). The plans and the specs under `docs/` keep their history. A line under `web/` can only be F10's, if this branch was cut after F10 merged: Task 8's Step 3 settles it.

- [ ] **Step 5: Offer a memory**

The owner's auto-memory index (`/home/anirudhlath/.claude/projects/-home-anirudhlath/memory/MEMORY.md`) has a `dj-ledfx redesign` entry. Offer to add one line to its file (`project_dj_ledfx_redesign.md`): M8's first slice landed as a PR; the `fx` channel sends particles, rings and planes per zone from the frame at now; the mask, mirror, transition and modifier rulings are the plan's (rulings 5–9) until the owner changes them. Write it only with a go.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: CLAUDE.md and the README for effects in space"
```

---

### Task 8: Catch up with master, and the PR

CLAUDE.md ends every plan with a pull request. F10, the web app's side, may have merged meanwhile. This branch changes nothing under `web/`, but F10's hand-written `fx` types and its mock must say what the engine sends. This task rebases, checks that, runs every gate again and opens the PR. It never merges.

**Files:**
- Modify: whatever the rebase leaves in conflict; F10's code only if Step 3 finds it differs from the payload, and then only with the owner's ruling
- Create: `/tmp/m8-pr-body.md` (not committed)

- [ ] **Step 1: Rebase onto `master`**

```bash
git fetch origin
git rebase origin/master
git log --oneline -8 origin/master
```

The branch hasn't been pushed, so rebasing is safe. It changes no file under `web/`, so a conflict there means something unexpected changed: stop and tell the owner. If a conflict touches `CLAUDE.md`, `README.md`, `src/dj_ledfx/web/ws.py` or `src/dj_ledfx/zones/runtime.py`, keep both sides. If `pyproject.toml` or `uv.lock` changed on master, run `uv sync --extra web` before Step 4 (never hand-edit `uv.lock`).

- [ ] **Step 2: Check the generated types**

```bash
uv sync --extra web
(cd web && npm ci && npm run api:types && git status --short src/api/generated)
uv run pytest tests/web/test_openapi_types.py -q
```

Expected: `git status` lists nothing and the pytest passes: M8 changes no REST shape. If it lists files, master's own types were behind its API: commit them, and say so in the PR.

```bash
git add web/src/api/generated
git commit -m "chore(web): regenerate the API types after the rebase"
```

- [ ] **Step 3: Check F10's side against what the engine sends**

Skip this step if F10 hasn't merged.

1. `git grep -n -e "FxMessage" -e "ZoneFx" -e "subscribe_fx" -- web/src ':!web/src/api/generated'`. F10's types must have §12.4's keys exactly: `zoneId`, `stream`, `particles` (seven numbers, the last the radius: ruling 2), `rings` (`center`, `radius`, `width`, `rgb`, `form`), `planes` (`point`, `normal`, `width`, `rgb`, optional `ray`). Its mock's fx must be well formed by the same rules as Task 6's probe (`well_formed()`), and read `size` and `width` as rulings 2 and 3 say. Its ack handling must accept the engine's ack, which carries `on` beside the mock's keys.
2. Never change the engine to fit F10's code, and never change F10's code to fit a ruling the owner hasn't seen. If they differ, stop and tell the owner: the payload or a ruling needs their word.
3. Run `(cd web && npm test && npx tsc -b && npm run lint)` and `uv run pytest tests/web -q`.

- [ ] **Step 4: Run every gate**

```bash
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm run api:check && npm test 2>&1 | grep -E "^ +Tests " && npx tsc -b && npm run lint && npm run build 2>&1 | tail -1)
```

Expected:
- ruff is clean and every test passes: `2816 passed, 1 skipped, 95 deselected` when this plan was tried on `57455a7` (Before Task 1's 2749 and this branch's 67), plus whatever master has added since.
- `377 files already formatted`, and mypy's 16 errors: no worse than Before Task 1's baseline.
- The perf run: `95 passed` when this plan was tried (Before Task 1's 79, Task 4's 15 and Task 5's one), each under 5 ms per zone frame.
- Every web step passes: nothing under `web/` changed on this branch, so they pass as master's do.

- [ ] **Step 5: Check that nothing private is in the branch**

```bash
git diff origin/master -- . ':!docs/design' ':!src/dj_ledfx/home/data' > /tmp/m8-diff.txt
grep -nE '^\+.*\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|^\+.*\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/m8-diff.txt | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
uv run python -c "import json; print('\n'.join(sorted({l['model'] for l in json.load(open('docs/design/web-app/home.json'))['lights'] if l.get('model')})))" > /tmp/m8-models.txt
grep '^+' /tmp/m8-diff.txt | grep -ciFf /tmp/m8-models.txt || echo "no model names"
uv run python -c "import json; from dj_ledfx.home.seed import OWNER_ROOM_NAMES; home = json.load(open('docs/design/web-app/home.json')); place = home['location']; print('\n'.join(sorted({l['name'] for l in home['lights'] if ' ' in l['name']} | {r['name'] for r in home['rooms']} | set(OWNER_ROOM_NAMES.values())) + [place['name'].split(',')[0], str(place['lat']), str(place['lon'])]))" > /tmp/m8-private.txt
grep '^+' /tmp/m8-diff.txt | grep -ciwFf /tmp/m8-private.txt || echo "no light names, room names or place"
git log --format=%B origin/master..HEAD | grep -niE 'claude-[a-z]+-[0-9]|instruct|gguf|\b[0-9]+(\.[0-9]+)?b\b' || echo "no model ids in the commits"
```

Expected: `no addresses`, then `0` and `no model names`, then `0` and `no light names, room names or place` (`grep -c` prints the 0), then `no model ids in the commits`. Loopback and `0.0.0.0` are allowed. The lists come from `home.json` and the seed at run time, so they're never typed here, and the greps print only counts. Anything found goes: replace it with `localhost`, a made-up name or made-up coordinates.

- [ ] **Step 6: Push and open the PR**

Fill in the counts from Step 4 and Task 6, and whether F10 had merged, from Step 1.

```bash
git push -u origin feature/m8-fx
gh pr create --base master --title "M8 effects in space: the fx channel" --body-file - <<'EOF'
## Summary

The first slice of engine milestone M8 (docs/superpowers/specs/2026-09-23-home-effects-engine-design.md), per docs/superpowers/plans/2026-10-14-m8-effects-in-space.md: the `fx` WebSocket channel of the web spec's §12.4, which F10's stage draws.

- **Effects say what they draw in space:** one hook on every effect, `in_space()`, None by default. Every particle effect (M5's eleven looks) sends its particles with no code of its own; Shockwave's shell and Speaker waves' kick fronts send sphere rings, Ripples' drops circle rings, the Scanner a level plane and Shockwave's beam a half-plane with a ray. Firmware layers send nothing.
- **On the map:** each layer's fx go back through its transform and to every place its mirror shows them; its mask weighs its particles where they land; its opacity, and the look's evening and brightness cap, dim them as they dim the LEDs.
- **Read with the frames:** each rendered frame keeps its fx beside its colours, and the channel reads the newest frame at or before now, as the live and preview frames are read, never blended.
- **The channel:** `subscribe_fx {on}`, to sessions on frame protocol 2, at most 30 messages a second, only on a change, one empty message when the last zone stops; live and preview; one message made for all sessions.
- **The budget:** every look that draws in space, at its largest settings with every modifier, stays under 5 ms a zone frame, its fx at most <share> ms of it.
- **Deferred:** sun shafts (M6's sun), the doorbell's gold ring and the overlays (M6/M7), and F10's reduced-motion, performance and accessibility pass.
- Nothing under `web/` changes: the channels' types are hand-written in `web/src/api/contract.ts`, which F10 owns. F10: <merged before this, and its types and mock match what the engine sends | not merged yet>.
- CLAUDE.md and the README.

## For the owner

The plan's rulings fill gaps in the spec. The ones to check, on F10's stage:
- 2: a particle's `size` is its radius; a ring's or plane's `width` is its full thickness at e^-1; the beam's width is its angle in radians, its width 1 m out.
- 3: where each field effect's shell, front, ripple and plane are drawn; Ripples as level circles, as the spec says, though its LEDs light by 3D distance.
- 5: a mirrored layer's particles show only on the side its lights show them, at both images.
- 6: a mask fades particles out where it does, and draws a ring or a plane whole while it lights any LED.
- 7: the flash and trails stay on the LEDs; the evening and the cap dim fx too.
- 9: during a transition the stage shows the new look's fx only.
- 12: a tab that turns fx on gets the picture at once, an empty one included.
- 15: the dry run on this home's data ran without asking: one read-only process in the container, no light.

## Test plan

- [x] `uv run pytest`: <pytest count>; ruff clean; mypy at master's baseline (16)
- [x] `uv run pytest -m perf`: <perf count>, every zone frame under 5 ms; the heaviest look that draws in space <ms> ms, its fx <share> ms
- [x] The dry run on a copy of this home's state, no light backend: every particle look sends particles, Shockwave sphere rings and a beam, Speaker waves sphere rings, Ripples circle rings, the Scanner a level plane; all well formed; at most 30 a second; protocol 1 gets none; off and on; live with preview-only; Stop all's one empty message; 4002 still the deployed app's
- [x] `cd web && npm run api:check`, `npm test`, `npx tsc -b`, `npm run lint`, `npm run build`: unchanged
- [x] No LAN address, MAC, light name, light model or AI model name in the diff or the commits

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
gh pr view --json url --jq .url
```

Expected: `gh` prints the PR's URL. Don't merge it.

- [ ] **Step 7: The final review**

Run the final review of the whole branch now, the one the run's method ends with. Fix every finding it raises, Minor ones included: each fix goes in its own commit, after the gate of the task that owns the code. Push the fixes to the PR. Then stop: the owner merges.

---

## Hand-off

**F10 (the web app's Effects in space)**
- The payload is §12.4's; rulings 2 and 3 say what `size`, `width` and each field effect's shape mean, and ruling 12 what the ack and the empty message are. The stage draws them on the "Effects in space" switch (§7.4).

**Engine M6**
- **Sun shafts.** A new optional key on `ZoneFx` (`shafts`), from M6's sun, and a new field on `Fx`, by the payload's extension rule. `fx_joined`, `recoloured` and `in_home` each gain one line for it.
- **The doorbell's gold ring and the overlays** (M6/M7): an overlay's ring is another key, or a `rings` item on an overlay's own entry, for whichever milestone draws overlays.

**Later**
- **Clipping to a mask** (ruling 6): a ring's or a plane's clip to a room is a new optional field on the item.
- **A transition's mix** (ruling 9): a per-item share on each item, if the owner wants the old look's fx to fade out.

## Coverage

| The controller's decisions, and §12.4 | Task |
|---|---|
| One hook, None by default; particles without per-look code; the five field effects; firmware nothing (rulings 1–3) | 1, 2 |
| Effect space back to home space: the inverse transform, every image of a mirror; the mask (rulings 5, 6) | 3 |
| Each frame's fx beside its colours in the ring; the newest at or before now, never blended; modifiers and opacity; transitions; failures; the perf test (rulings 4, 7, 9–11, 14) | 4 |
| Brightness, 3 places, the cap of 500; `subscribe_fx`, protocol 2 only, ≤ 30 Hz, nothing while unchanged, one empty message; preview with stream `preview` (rulings 7, 8, 12, 13) | 5 |
| The dry run on this home's data, no light, no go (ruling 15) | 6 |
| CLAUDE.md and the README | 7 |
| Rebase, F10's side checked, every gate, the PR | 8 |
