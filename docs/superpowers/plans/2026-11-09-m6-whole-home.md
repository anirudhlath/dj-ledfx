# M6 Whole Home (engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Home looks run on the whole home. The engine works out the sun from the home's location and the map's north offset, sends it to the web app on `GET /inputs` and the `inputs` channel, and hands it to every frame. The three Home looks the handoff gives without Home Assistant, Home sunset, Wisp and Goodnight, are built in and listed by `GET /api/looks` with looks.json's metadata. An overlay plays a Home look over every running zone for a set time while the zones underneath keep running (`POST`/`DELETE /api/running/overlay`, and `Running.overlays`, on the `running` channel). Bedtime is Goodnight started on Whole home, by hand now and by M7's trigger later: the rooms go dark one by one, farthest first, and each room's lights are switched off once it's dark, the night room left on a night light (the owner's answer, 2026-11-11). The owner can put each of them on the real lights, after merging and at their word, and watch them on the stage.

**Architecture:** Five small pieces on what exists. (1) `validate_look` stops refusing `scope: "whole-home"`, and the zone manager refuses one on any zone but Whole home (`ZoneManager.check_scope`). (2) `home/sun.py` gains `sun_position()`, `daylight()`, `sun_path()` and `Sun`, a once-a-second reading at `Home.location` built the way `Evening` is. `RuntimeEnv.sun` hands it to each runtime, which puts `sun.elevation` and `sun.azimuth` in the frame's signals (`render_context`); a look that needs the sun waits until there is one. `Space.north_offset_deg` carries the map's north, so an effect can turn the true azimuth onto the plan. (3) Three effects: `HomeSunset(SunsetGradient)`, whose sun is the real one; `Wisp(ParamParticles)`, which tours rooms; and `Goodnight(ParamField)`, which walks the rooms off from the look's elapsed time (`RenderContext.elapsed_s`, from the zone's `since`). A field effect can say when each LED is dark for good (`FieldEffect.lights_out()`, Goodnight's only), the runtime turns that into a time for each light (`ZoneRuntime.out_after()`), and the zone manager switches each such light off when its time comes, if the light can switch power (`DeviceAdapter.switches_power`). (4) Overlays: `zones/overlay.py`'s `OverlayRun` is a runtime of its own over the whole home's lights, with an amount that eases in and out. An `OverlaySlot` that the manager shares with every streaming `DeviceRoute` (`DeviceRoute.over`) and with `FrameFeed` mixes the overlay over a zone's colours by screen, at each light's own moment, after the zone's brightness. (5) The web contract: `SunInput` on `Inputs`, and `OverlayRequest`, `Overlay` and `Running.overlays`, with `npm run api:types` and `contract.ts`'s hand-written sun swapped for the generated one.

**Tech Stack:** Python 3.14, numpy, astral 3.2 (already a dependency: `sun.elevation`, `sun.azimuth`), FastAPI, pytest with pytest-asyncio. No new dependency. Under `web/`, only the regenerated `src/api/generated/`, `src/api/contract.ts`, `src/api/contract.test.ts` and one type in `src/api/mocks/scenarios.ts` change.

**Spec:** `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md` §2 (the M6 row), §4.3 (zones; the overlay), §5.2 (looks: `needs`, `scope`, the built-ins), §7.3 (the sun), §7.4 (triggers, M7's, which call M6's overlay) and §8; `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md` §8.2, §8.3, §12.2's `Overlay`, §12.3 (`/running`, `/running/overlay`, "**Overlays**") and §12.4 (the `running` and `inputs` rows, "**The `sun` input**"). The docs PR that carries this plan wrote §12.3's overlay routes and paragraph and §12.4's `sun` input. Read them before starting.

**What exists.** M6 starts from master at `d5e4931`, after M8 #60 and F10 #61:

- **The whole-home zone.** `HOME_ZONE_ID = "home"` and `HOME_ZONE_NAME = "Whole home"` (`zones/model.py`); `MapZones` (`zones/home_view.py`) derives it from the map, and it follows the map like a room. But `validate_look` (`looks/model.py`) refuses every look whose scope isn't `"any-zone"`, with "Home looks (whole-home scope) arrive in M6", and six tests pin that refusal (Task 1).
- **The location.** `Home.location` comes from home.json's demo location until the owner sets the real one with `PUT /api/home`, and lives only in the deployed `state.db`. `home/sun.py` turns it into the evening (`Evening`, `_times()` caching astral's events per place and UTC date); `main.py` hands one to the zone manager. Nothing works out the sun's position, and the frames carry no sun signal.
- **Inputs.** `looks/model.py`'s `InputKind` includes `"sun"`. `zones/runtime.py`'s `ALWAYS_AVAILABLE` is `{"tempo"}`, so a look that needs the sun waits forever, dark. `GET /api/inputs` (`web/router_inputs.py`, `contract.inputs_out`) has the tempo and Pro DJ Link only. The web app hand-writes `SunInput` (with `path`) in `web/src/api/contract.ts`, and its stage (`web/src/stage/sun.ts`) already draws the sun from the true azimuth turned by `home.northOffsetDeg`.
- **Overlays.** `contract.Overlay` and `Running.overlays` exist, the list always empty ("overlays arrive in M6"). The web app has its `OverlayCard`; the web side of overlays is not this plan's.
- **The three looks** are in looks.json (`homesunset`, `wisp`, `goodnight`; category `home`, scope `whole-home`; inputs `["sun"]`, `[]` and `["home-assistant"]`) and not among the built-ins. `builtin_looks()` lists a handoff look only if `_handoff_layers()` gives it layers.

**Execution:** in a new worktree, `~/code/.worktrees/dj-ledfx/m6-whole-home` on branch `feature/m6-whole-home`, by the method the owner picks. Branch it from `origin/master` after the docs PR with this plan has merged; Before Task 1 sets it up. F5, the web app's Looks library, is planned beside this one (`docs/superpowers/plans/2026-11-09-f5-looks-library.md`) and may merge first. They meet at `GET /api/looks` (F5 lists the three new looks with no code of its own) and at `contract.ts`, where Task 13 rebases over whatever has merged.

**How to read the tasks.** Each step gives the signatures, the constants, the test names with what each asserts, and the exact values. The code those determine is the implementer's. A test comes first and is seen to fail.

---

## Global Constraints

Every task's requirements include these. Quotes are verbatim from the specs.

- The M6 row (engine §2): "| M6 | Whole home | Whole-home zone; overlays; sun position; bedtime flow | Home sunset, Wisp, Goodnight |".
- §4.3: "An **overlay** (M6) is a Home look that plays over every zone for a set time and then gets out of the way. The zones underneath keep running." The web spec §11.3: "Overlays (Doorbell ripple) render on top of all zones for their duration and then get out of the way."
- §5.2: "`needs` lists the inputs a look can't run without (music, home-assistant, sun); a zone whose look needs a missing input waits dark and starts when the input arrives. `uses` lists inputs a look follows when they're present and does without otherwise. Tempo is always available, from the internal clock at worst. `scope: whole-home` pins Home looks to the whole-home zone." "The built-ins keep the ids, names, descriptions and thumbnail ids of the handoff's `docs/design/web-app/looks.json`." The web spec §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
- §7.3: "**Sun (M6):** azimuth and elevation are computed locally from the location (Home Assistant's config once connected, otherwise `config.toml`) and the home map's north offset." The next sentence says where Home sunset starts, at one room's west windows (ruling 6). The catalogue names "`sun.elevation`" and "`time.evening`", and the web spec's Signals list adds "`sun.azimuth`".
- §7.4 (M7, which this plan's overlay must serve): "Home looks start from them as overlays (the doorbell plays Doorbell ripple over everything for 8 s; bedtime starts Goodnight). Anything more involved stays in Home Assistant automations, which call REST actions through `rest_command`: set a look on a zone, turn a zone off, set brightness, and play a timed overlay."
- The web contract: §12.2 `interface Overlay { lookId: Id; name: string; trigger: string; endsAt: string; progress: number }`; §12.3 `GET /running` "RunningZone[] + Overlay[]", `POST /running/overlay` and `DELETE /running/overlay` with the "**Overlays**" paragraph; §12.4's `running` row "on change | `RunningZone[]`, `Overlay[]`", and "**The `sun` input**" (`SunInput`, `Inputs.sun: SunInput | null`, every number to 1 decimal, the path at the clock's 10-minute marks). Binding.
- §4.1: "Everything stays on the single asyncio event loop. Budget: under 5 ms per zone frame on one core." §8: "**A look raises or produces NaN:** that zone holds its last good frame, the look is marked crashed, and the error is logged once (rate-limited). Other zones keep running." An overlay that fails costs its own frames, never a zone's.
- §9: "**Performance:** a benchmark test on this home's 412-LED map asserts each zone renders in under 5 ms." Perf tests are marked `perf` and deselected by default (`-m perf` runs them).
- **The cut** (Spec Rulings 8, 11 and 15, and the report): this slice is Home looks on Whole home, the sun, the three looks, and overlays started over REST. **Deferred**, and said so wherever it would otherwise be expected: sun shafts (ruling 15); an overlay's `fx` on the stage (with M7's doorbell ring); an overlay reaching idle lights or lights running their own effect (ruling 11); an overlay kept across a restart; a resume finishing a walk that a restart interrupted (ruling 19); the location from Home Assistant's config, bedtime's trigger, signals and bindings (M7); an overlay's own brightness or blend; the web app's overlay card wiring (a web milestone). Particle tuning (#48–#58, tracking #62) is parked: Wisp's numbers are first values.
- The repo is public: no LAN addresses, MACs, SSIDs, light names, light model names, room names from this home or the design's home, the home's location or AI model names in code, tests, commits, the PR or this plan. Fixtures use made-up ids (`test-lamp`, lamps a–d, `light-0`) and 127.0.0.1. A room or light name the code needs is read at run time from the seed (`seed_home().rooms`, `seed_lights()`), never typed. The sun's tests use made-up places (the equator at 0° E, 45° N 0° E, 89.9° N), never a home's. The real location is never read, printed or written by anything in this plan.
- Design values are never retyped: looks.json's ids, names, descriptions, categories, scopes, inputs and thumbnails come from the vendored byte copy (`looks/data/looks.json`) through `handoff_looks()`. `web/src/stage/design-numbers.ts` is generated and not touched.
- Code style (CLAUDE.md): `uv` for everything (`uv run …`, never pip, conda or an activated venv), npm in `web/`; `loguru` (never INFO in the render loop); `mypy --strict`; render paths synchronous, lock-free and numpy on whole arrays (no Python loop over LEDs or particles); a frame in a ring never changed after it's written (`ring.colors_at` may hand out a frame's own array: copy before mixing in place); new effects imported in `effects/__init__.py`; a field or particle effect a pure function of its moment, its seed and the LEDs.
- Gates, per task before commit: `uv run ruff check .` clean and `uv run pytest -q` green; `uv run ruff format --check .` with no findings and `uv run mypy src/` no worse than Before Task 1's baseline. During a task run only its test files, and run the full gate once, before the commit. Run `uv run ruff format` and `uv run ruff check --fix` on the files the task touched, never the whole tree. `uv run pytest -m perf -q` in Tasks 3, 5, 6, 7 and 9. A task that changes a route, a contract model or a route's docstring runs `(cd web && npm run api:types)` in the same commit (tests/web/test_openapi_types.py fails otherwise), then `(cd web && npx tsc -b && npm test && npm run lint)`.
- Live system: no task touches a light, the deployed `dj-ledfx-app-1`, docker's state, UFW, port 8080, UDP 4002 or 50001. Task 11's dry run runs the branch on simulated lights in a loopback-only network namespace (`unshare -rn`), with a fresh database, so it needs no owner go. `--demo` is not lamp-safe (it only skips Pro DJ Link), and the `run-demo` skill uses it: never use either here. Every step on real lights is in the PR's checklist, after the owner merges and deploys at their word, with the owner's "go" before each step. Home Assistant holds UDP 4002, so the deployed app sends to the Govee lamps but can't hear them: it can't capture one, and Off leaves a Govee lamp as the look left it. master changes only through the PR, which the owner merges. There are no stacked branches, and never a bare `git stash`.

## Spec Rulings

The specs leave some things open. These are the rulings this plan builds on, each with why and what it costs if it's wrong. Task 13 lists them in the PR. Three were the owner's to answer, and the owner answered them on 2026-11-11: rulings 8, 11 and 15, each marked so. Ruling 19 works out the owner's answer to 8. The rest are this plan's rulings, for the owner to check in the PR, ruling 10 first.

1. **Home looks play on Whole home, and only there.** `validate_look` drops its refusal, so a whole-home look saves, validates and previews like any other. `ZoneManager.check_scope(zone_id, look)` raises `ZoneError(f"{look.name} plays on {HOME_ZONE_NAME} only")` (400 through `answers()`) for a whole-home look on any zone but `HOME_ZONE_ID`. It runs in `start`, `start_preview` and `PreviewManager.update`. *Why:* §5.2 "pins Home looks to the whole-home zone"; the composer already locks the zone (`locksToHome` in `web/src/compose/model.ts`). *If wrong:* one check in three callers.
2. **The sun's numbers.** `sun_position(lat, lon, at)` is astral's `sun.elevation(..., with_refraction=True)`, the apparent height that the stage's "above the horizon" means, and `sun.azimuth`, in degrees clockwise from **true** north. The north offset is applied where the plan is drawn: the stage turns the azimuth itself (`sunPoint` in `web/src/stage/sun.ts`), and an effect turns it through `Space.north_offset_deg` (ruling 5). So `/inputs` sends the true azimuth, and sending it turned would turn it twice. The location is `Home.location`, set by `PUT /api/home`, not `config.toml` as §7.3 says: M2 moved it onto the map. Home Assistant's config is M7's. *If wrong:* one conversion in `sun_out`.
3. **Sunrise, sunset and the path.** `daylight(lat, lon, at)` gives the latest sunrise at or before `at` and the first sunset after that sunrise, from `_times()`'s events around the date. Either is None where none falls in that window (polar day or night). `sun_path(lat, lon, at)` gives the sun at the clock's 10-minute marks (UTC :00, :10, …) `m` with `at − PATH_SPAN < m ≤ at`, where `PATH_SPAN` is 2 h and `PATH_STEP` 10 min. That is always 12 points, oldest first. *Why:* the web's `sameSun` compares paths, and the heartbeat sends a copy every second: marks on the clock keep the path equal between marks, so the stage doesn't redraw every second. The mock's path is the same shape. *If wrong:* the stage's arc starts up to 10 minutes later than "two hours ago"; two constants.
4. **No location, no sun, and a look that needs it waits.** `Sun()` and `Sun.reading()` are None with no location, logged once at WARNING as `Evening` does, and `/inputs` sends `sun: null`. `ZoneRuntime.waiting_for` lists `"sun"` while `env.sun()` is None, so Home sunset waits dark (§5.2) and starts within a second of a location being set (`Sun` caches for `CACHE_S`). The runtime calls `on_state_change` when its waiting set changes, so the `running` channel says so. An overlay of a look that needs a missing input is refused (ruling 13). At a pole astral still gives a position, and sunrise and sunset are null. The sun follows whatever location is stored, the seed's demo one included, as the evening does.
5. **The sun in each frame.** While there is a sun, every frame's `SignalView` carries `sun.elevation` and `sun.azimuth` (`SUN_ELEVATION`, `SUN_AZIMUTH` in `effects/context.py`; true north's degrees, unrounded). With none it carries neither, so `ctx.signals.get(SUN_ELEVATION, d)` gives `d`. `Space.north_offset_deg` (from `space_of`, the map's `north_offset_deg`) is part of the space's equality, so turning north redraws a running zone's LEDs and its effects see the new north. `plan_bearing(azimuth_deg, north_offset_deg) = (azimuth_deg + north_offset_deg) % 360`, clockwise from the plan's up (north at offset 0), the sum the stage passes to `bearingVector`. *Why:* §7.3's catalogue names `sun.elevation`, and the web's Signals list names `sun.azimuth`. *If wrong:* a signal name; one constant each.
6. **Home sunset.** Sunset's gradient, with the real sun as its sun. `HomeSunset(SunsetGradient)` drops the `anchor` setting and keeps the rest: palette, level, warmth, drift, and the candles' Flame layer that Sunset has. Its sun is `sun_point(leds, elevation_deg, azimuth_deg)` (`effects/field_tools.py`), where the stage draws the sun, but on the zone's frame (`LedSet.bounds`) and with no margin. It sits on a line from the frame's middle along `plan_bearing`, at the point where the line leaves the frame's box (`exit`), `across = exit·cos e` out and `exit·sin e` above the frame's top. The gradient is warmest nearest it: `ANCHOR_SHARE` of it is each LED's `reach()` from that point, as Sunset's anchor is. So at sunset, with the sun in the west, the warmth sits at the home's west side, where §7.3's west windows are. It follows the sun at any height, below the horizon included; the reach is worked out every frame (one `reach()` over the LEDs), the height part once for each set of LEDs. With no sun signal (a preview with no location) it plays as Sunset with no anchor. *If wrong:* anchoring the warmth to the windows of the room the spec names needs window heights on the map (ruling 15); one more setting then.
7. **Wisp.** `Wisp(ParamParticles)`: `count` wisps (default 2, as its description says; 1 to 4). Each rests on an LED of a lamp for `hold_s` (default 4 s, 0.5 to 30), then glides over `move_s` (default 3 s, 0.5 to 20) to a lamp in another room. Its rooms come from a tour (`tour()`) over the rooms that have lamps (`lamp_rooms()`), and `draws()` picks its lamp in a room and the LED on each visit. With one room, or none on the map, it tours the lamps. Its light is the particle's falloff at `size` (default 0.5 m, 0.2 to 1.5), so "each lamp glows only while one passes". Its colour is `palette` (default one warm white) times `level` (default 0.8). It runs on seconds, not beats (needs nothing), and starts each wisp a share of a step apart, as Spotlights does. *Why:* Spotlights' proven tour, keyed by room. *If wrong:* constants, tuned on the stage later (#62 is parked).
8. **Bedtime is Goodnight started on Whole home, and the rooms it walks off are switched off (the owner's answer, 2026-11-11).** The renders show it as a start: State-Nothing-Running's "Start again" has Goodnight on Whole home from where Home sunset stopped, and the mock's last night says Goodnight replaced Home sunset on the whole home. The specs word it otherwise (engine §7.4 lists "bedtime starts Goodnight" among overlays; web §8.3 says "Other Home-category triggers (Goodnight on bedtime) use the same overlay pattern"), but an overlay ends and gives the lights back to the zones underneath, so it can't leave rooms off. So Goodnight is a start: its walk takes every light (newest wins), each room goes dark in turn, and each room's lights are switched off once it's dark (ruling 19). The night room stays on a night light until something else starts or Off restores. M7's bedtime trigger will call `start(HOME_ZONE_ID, goodnight)`.
9. **Goodnight's walk.** `Goodnight(ParamField)` with `walk_s` (default 60 s, 10 to 600), `night_room` (a room's id, type `zone`), `night_level` (default 0.12, 0 to 1), `palette` (default warm, two stops, the brighter for the front) and `level` (default 0.7). At the start every room glows at `level`. The other rooms switch off one by one, farthest first from the night room, by the distance between room centres (`polygon_centre`), over the rooms the zone's LEDs are in (a take-over that shrinks the zone can move the moments; ruling 19's mark keeps a light already switched off out); room `i` of `n` switches off at `walk_s·(i + 1)/(n + 1)`. Each brightens by `FRONT_BOOST` (1.4×, clipped to 1) over the `FRONT_S` (3 s) before its switch, then fades to black over `FADE_S` (2 s). LEDs in no room (`NO_ROOM`) go with the first room. After the last room the night room eases from `level` to `night_level` over one room's share of the walk and stays there. A night room not on the map leaves every room to switch off. `lights_out(leds)` gives each LED the elapsed time from which it's dark for good: its room's switch plus `FADE_S` plus `OFF_AFTER_S` (1 s, so the power-off lands on a light already black), and infinity for the night room's LEDs; ruling 19 turns that into power. The walk's clock is the look's elapsed time, `RenderContext.elapsed_s`, counted from the zone's start (`since`). A resume after a restart picks the walk up where it was; a Restart keeps `since`; a new start walks again from the top. The default night room is the one Goodnight's description names (`room_named_in(description, seed_home().rooms)`), as an anchored look's anchor comes from its description. *If wrong:* constants and one setting.
10. **An overlay mixes by screen (a decision for the owner to check in the PR).** Each LED shows `z + o − z·o`, where `z` is the zone's colour after its brightness and `o` is the overlay's colour times its amount. It's mixed in float, then converted once (`to_device_colors(…, scale=1.0)`), in `scheduling/route.py`'s `overlaid()`, which the routes and the frame feed share. It never darkens what's under it: the Live-Doorbell render has the lamps near the ring glowing gold and the rest keeping their look. The amount eases in and out over `OVERLAY_EDGE_S` (0.25 s, smoothstep) at the overlay's ends, read at each light's own moment (`now + latency`), as its frames are. An overlay plays at brightness 1. *If wrong:* `normal` (the overlay covers the zones, black included) or `add`; one function.
11. **What an overlay reaches (the owner's answer, 2026-11-11).** The lights that stream a running zone's frames, among the whole home's. That leaves out idle lights (no zone has captured them), a light running its own effect (its route doesn't stream), a light its look has switched off (ruling 19: it has no route), and every light while preview-only is on (no route streams). The web preview's live frames show the mix for the lights it reaches, and for none its look has switched off (`OverlaySlot.reaches`). *Why:* an idle light would have to be captured, switched on and restored for an overlay of a few seconds; that is the doorbell's question, M7's.
12. **One overlay at a time, not kept.** A new overlay replaces the one playing: the old one stops at once and the new one eases in. Stop all ends it, even with no zone running; `DELETE` ends it; and it ends by itself at its end, by a task that sleeps until then (`ZoneManager(sleep=, monotonic=)` for tests). It isn't saved in `state.db`, so a restart drops it. Its runtime is the zone manager's own (`OverlayRun.runtime`). It covers every light of the whole home at brightness 1, with every light `emulated`, so a firmware layer streams its copy and claims nothing. It follows the map in `_redraw`, has no state callbacks, and isn't a zone: `running()` doesn't list it and `live_runtimes` leaves it out. The engine hosts it, so it renders ahead into its own ring.
13. **Overlay rules.** A Home look only: any other scope gets `ZoneError("Only a Home look plays over everything")`. Whole home needs lights (`ZoneError(f"{HOME_ZONE_NAME} has no lights")`), and the look needs its inputs: a missing one gets `ZoneError(f"{look.name} waits for {inputs}")`. `durationS` must be more than 0 and at most `MAX_OVERLAY_S` (3600 s), and a finite number (422). `trigger` is 1 to 200 characters (422 otherwise), `"api"` by default. `start_overlay(look, duration_s, trigger="api")` is what M7's triggers will call.
14. **No overlay fx.** `FrameFeed.fx()` leaves the overlay out: what it draws in space is M7's doorbell ring, a new optional key by §12.4's extension rule. *If wrong:* the stage shows an overlay's particles (Wisp's) only in its lamps' light.
15. **Sun shafts are deferred (the owner's answer, 2026-11-11).** M8 said they follow M6's sun, and §12.4 reserves `shafts`. But home.json's windows have no sill or head heights, so a shaft through a window has no top or bottom, and slice simple first puts them after the sun is seen working. §12.4's fx bullet now says so. They need sill and head heights on windows (the map, the API, the web's Home map) and the shaft geometry: a slice of their own.
16. **The REST shape.** `POST /api/running/overlay` takes `OverlayRequest {lookId | look (draft), durationS, trigger?}` and answers 201 with an `Overlay`. `DELETE /api/running/overlay` answers 204 whether or not one plays. `GET /api/running` and the `running` channel carry `overlays` (none or one). `progress` is `(now − started)/(ends − started)` clipped to 0..1 at the message, and `endsAt` is UTC. The manager emits `ZonesChanged` as an overlay starts and ends, so the `running` channel pushes then.
17. **The dry run and the real lights.** Task 11 runs the branch's real entry point on simulated lights (a `DeviceBackend` of `FakeLight`s named and sized from `seed_lights()`) inside `unshare -rn` (loopback only), with a fresh `state.db`, so the seed's demo location gives it a sun. It needs no go. The PR's checklist holds the real-light steps, one go each, after the owner merges and deploys.
18. **Goodnight starts by hand.** looks.json gives Goodnight `inputs: ["home-assistant"]`, but State-Inputs-Down says "Goodnight on bedtime won't trigger · still starts by hand". So it needs nothing and uses Home Assistant: `STARTS_BY_HAND = frozenset({"goodnight"})` in `looks/builtin.py` sets `needs=()` and `uses=` the handoff's inputs. *If wrong:* one set.
19. **Lights out (works out the owner's answer of 2026-11-11 to ruling 8).** How a look switches lights off; Goodnight is the only one that does.
    - *What and when.* `ZoneRuntime.out_after(device_id)` is the elapsed time from which a light is dark for good in its zone's look: the latest of its LEDs' `lights_out()` times, so a light reaching into the night room never goes. It's None (never) unless every visible streamed layer gives `lights_out()`, no layer has a mask, the look's `downbeat_flash` is off, and no firmware layer claims the light. A light is *out* (`ZoneManager._is_out`) once its zone's `started_t + out_after` has passed, the light can switch power (`DeviceAdapter.switches_power`: LIFX and Govee yes, OpenRGB and the default no), and its zone isn't mid-transition. The zone manager's lights-out timer (one task) wakes at the next such moment and switches off each light that has just gone out and is still being sent the look (readied, connected, not read off, preview-only off). Its route is taken away first, then `set_power(False)` goes under its `send_lock`, so no frame lands after (a Govee frame could switch a lamp on), and the run marks it (`_Running.switched_off`). The mark keeps it out if a take-over shrinks the zone and its moment moves; it goes with the run. A failure is logged and leaves the light dark but on. A Govee lamp gets the command though the app can't hear it (Home Assistant holds UDP 4002). A light that can't switch power keeps streaming its black.
    - *While out.* An out light gets no route, so no overlay reaches it. It isn't readied, captured, switched on or off, or asked about a firmware effect, whatever its power reads, so a light switched back on elsewhere (Home Assistant, a wall switch) is left as it's set.
    - *A later start.* A start on any zone that takes the light (a new run, so no mark and no moment passed) switches it on (`_switch_on`, as for any light that reads off) and applies its look. That includes Goodnight again, whose walk starts afresh. Its capture from before dj-ledfx first took it stays as it was: an out light is never released or captured again.
    - *Off and Stop all.* They restore an out light's capture with its power (`restore_state(state, power=True)`), so a light that was on when captured comes back on as it was, though it reads off. Off's rule never to switch a light on (§6.4) is for a light switched off elsewhere; this one dj-ledfx switched off. `_end_run` notes which of a run's lights are out before the run goes (`_restore_on`); a light a take-over moves to another zone isn't one, so a backup's restore and a deleted zone do the same. A light with nothing captured (`b""`, as a Govee lamp is while the app can't hear it) is left alone by Off, so it stays off until a look switches it on.
    - *Resume and Restart.* A Restart keeps `since`, so out lights stay out and the walk goes on. A resume picks the walk up from the saved `since`: lights whose moment is still to come are switched off at it, and lights whose moment passed while the app was down count as out and are left as they are, since one that reads on may have been switched back on by someone. A light offline at its moment is left as it comes back.
    - *Preview only* sends nothing, power included: the timer switches nothing while it's on, and a light that went out meanwhile is left as it is when it's turned off.

    *If wrong:* a light that a restart interrupted mid-walk stays lit at its last frame; a mark of the lights switched off, kept in `state.db`, would let a resume finish the walk. And if Off after Goodnight shouldn't light the home again (it does, for every light captured on), `_restore_on` goes and Off leaves those lights off.

## Review Focus

These are the five things a user is most likely to hit, the most likely first. Each has tests in the task that owns the code.

1. **Goodnight's lights out.** A light switched off at its moment and only then; one switched back on elsewhere left alone; a later start switching it on with its capture kept; Off and Stop all restoring it, power included; preview only sending nothing; a resume or a Restart mid-walk and after it; a transition; the walk's clock across a restart. Tests: Task 8, `test_a_light_is_switched_off_once_its_look_has_it_dark_for_good`, `test_an_out_light_switched_on_elsewhere_is_left_alone`, `test_a_later_start_switches_it_back_on_and_keeps_its_capture`, `test_off_and_stop_all_restore_an_out_light_power_included`, `test_preview_only_sends_nothing_power_included`, `test_a_resume_mid_walk_switches_off_only_the_lights_still_to_come` and `test_no_light_is_switched_off_mid_transition`; Task 7, `test_a_resumed_zone_counts_its_looks_time_from_its_saved_start`, `test_a_restart_keeps_the_zones_start` and `test_a_twin_and_a_transitions_old_look_keep_their_own_elapsed_time`.
2. **Zones changing under an overlay.** A zone that starts, stops or takes lights while an overlay plays; the map changing; Stop all; a light running its own effect; preview only. Tests: Task 9, `test_an_overlay_plays_over_every_running_zone_and_they_keep_running`, `test_a_zone_started_under_an_overlay_is_overlaid_from_its_first_send`, `test_stop_all_ends_the_overlay_even_with_nothing_running`, `test_the_overlay_follows_the_whole_homes_lights_when_the_map_changes` and `test_an_overlay_reaches_no_idle_light_and_no_light_running_its_own_effect` and `test_an_overlay_never_reaches_a_light_its_look_switched_off`.
3. **Moments at the overlay's edges.** Its first and last quarter-second at a slow light's moment and a fast one's, a newer overlay, its own end, and a route read after the end. Tests: Task 9, `test_an_overlays_amount_eases_in_and_out_over_its_edges`, `test_a_route_reads_the_overlay_at_its_own_moment`, `test_a_newer_overlay_replaces_the_one_playing` and `test_an_overlay_ends_by_itself_and_says_so`; Task 10, `test_the_running_channel_pushes_the_overlay_as_it_starts_and_ends`.
4. **The sun at the edges.** A pole, no location, a location set while a zone waits, a north offset turned, a heartbeat between path marks. Tests: Task 2, `test_the_sun_at_a_pole_has_a_place_but_no_sunrise_or_sunset`, `test_the_path_is_the_ten_minute_marks_of_the_two_hours_before_now_oldest_first` and `test_no_location_no_sun_logged_once`; Task 3, `test_a_look_that_needs_the_sun_waits_dark_without_one` and `test_a_sun_arriving_starts_a_waiting_zone_and_says_so`; Task 5, `test_turning_north_turns_its_warmth`.
5. **The budget.** Every built-in look with every modifier (the three new ones join `test_a_zone_frame_renders_in_under_5_ms`, which now asserts that no look waits), a route mixing an overlay, and an overlay rendering on every seeded LED. Tests: Task 3's change to `test_a_zone_frame_renders_in_under_5_ms`; Task 9, `test_a_route_mixing_an_overlay_stays_cheap` and `test_an_overlay_renders_in_budget` (perf).

---

## File Structure

New backend modules (paths under `src/dj_ledfx/`):

| File | Responsibility |
|---|---|
| `effects/home_sunset.py` | `HomeSunset`: Sunset's gradient with the real sun as its sun |
| `effects/wisp.py` | `Wisp`: wisps that tour the rooms' lamps |
| `effects/goodnight.py` | `Goodnight`: the rooms walked off from the look's elapsed time, the night room left on; `FRONT_BOOST`, `FRONT_S`, `FADE_S` |
| `zones/overlay.py` | `OverlayRun` (the look, trigger, runtime, start and end on both clocks, `amount(t)`), `OverlaySlot` (the playing overlay, which routes and the feed read), `MAX_OVERLAY_S`, `OVERLAY_EDGE_S` |

Modified, task by task:

- Task 1: `looks/model.py` (`validate_look`), `zones/manager.py` (`check_scope`), `zones/preview.py` (`update`).
- Task 2: `home/sun.py` (`SunPoint`, `SunReading`, `sun_position`, `daylight`, `sun_path`, `plan_bearing`, `PATH_SPAN`, `PATH_STEP`, `Sun`).
- Task 3: `effects/context.py` (`SUN_ELEVATION`, `SUN_AZIMUTH`, `render_context(..., sun=)`), `effects/ledset.py` (`Space.north_offset_deg`), `home/map.py` (`space_of`), `zones/runtime.py` (`RuntimeEnv.sun`, `waiting_for`, `tick`), `zones/manager.py` (`sun=`), `main.py`.
- Task 4: `web/contract.py` (`SunPathPoint`, `SunInput`, `Inputs.sun`, `sun_out`, `inputs_out`), `web/app.py` (`create_app(sun=)`), `web/state.py` (`get_sun`), `web/router_inputs.py`, `web/ws.py` (`_inputs_message`), `main.py`; `web/src/api/{generated/,contract.ts,contract.test.ts}`, `web/src/api/mocks/scenarios.ts`.
- Task 5: `effects/field_tools.py` (`sun_point`), `effects/__init__.py`, `looks/builtin.py`.
- Task 6: `effects/particle_tools.py` (`lamp_rooms`), `effects/__init__.py`, `looks/builtin.py`.
- Task 7: `home/geometry.py` (`polygon_centre`), `effects/context.py` (`RenderContext.elapsed_s`), `zones/runtime.py` (`started_t`), `zones/manager.py` (`monotonic=`, `_started_t`), `effects/__init__.py`, `looks/builtin.py` (`room_named_in`, `STARTS_BY_HAND`).
- Task 8: `devices/adapter.py` (`switches_power`), `devices/lifx/base.py`, `devices/govee/adapter_base.py`, `effects/field.py` (`FieldEffect.lights_out`), `effects/goodnight.py` (`lights_out`, `OFF_AFTER_S`), `zones/runtime.py` (`out_after`), `zones/manager.py` (`_Running.switched_off`, `_is_out`, the lights-out timer, `_restore_on`, `sleep=`, `close`), `main.py`.
- Task 9: `scheduling/route.py` (`OverSource`, `DeviceRoute.over`, `overlaid`), `zones/model.py` (`OverlayInfo`), `zones/manager.py` (`start_overlay`, `stop_overlay`, `overlays`, `overlay_slot`), `zones/frames.py` (`FrameFeed(overlay=)`), `main.py`.
- Task 10: `web/contract.py` (`OverlayRequest`, `overlay_out`, `running_out`), `web/router_zones.py`, `web/ws.py` (`_running_message`); `web/src/api/{generated/,contract.ts,contract.test.ts}`.
- Task 12: `CLAUDE.md`, `README.md`.

New test files: `tests/sun_fakes.py` (shared: `FixedSun`, `AT_DUSK`; Task 3), `tests/zones/test_runtime_sun.py` (Task 3), `tests/effects/test_home_sunset.py` (Task 5), `tests/effects/test_wisp.py` (Task 6), `tests/effects/test_goodnight.py` (Task 7), `tests/zones/test_manager_lights_out.py` (Task 8), `tests/zones/test_overlay.py` and `tests/zones/test_manager_overlay.py` (Task 9), `tests/web/test_overlay_api.py` (Task 10). Tests are added to: `tests/looks/test_model.py`, `tests/zones/test_preview.py`, `tests/web/test_preview_api.py`, `tests/web/test_looks_api.py`, `tests/web/test_zones_api.py` and `tests/zones/test_manager.py` (Task 1); `tests/home/test_sun.py` (Task 2); `tests/effects/test_context.py`, `tests/home/test_map.py`, `tests/zone_home.py`, `tests/zones/conftest.py` and `tests/zones/test_runtime_perf.py` (Task 3); `tests/api_home.py`, `tests/web/test_inputs_api.py` and `tests/web/test_ws_channels.py` (Task 4); `tests/looks/test_builtin.py` (Tasks 5–7); `tests/effects/test_particle_tools.py` (Task 6); `tests/home/test_geometry.py`, `tests/zones/test_runtime.py` and `tests/zones/test_manager.py` (Task 7); `tests/conftest.py`, `tests/runtime_fakes.py`, `tests/devices/test_adapter_state.py`, `tests/effects/test_goodnight.py`, `tests/zones/test_runtime.py`, `tests/zone_home.py` and `tests/zones/conftest.py` (Task 8); `tests/scheduling/test_route.py`, `tests/zones/test_frames.py` and `tests/zones/test_runtime_perf.py` (Task 9); `tests/web/test_ws_channels.py` (Task 10).

---

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/m6-whole-home /home/anirudhlath/code/.worktrees/dj-ledfx/m6-whole-home origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/m6-whole-home
cd "$W"
test -f docs/superpowers/plans/2026-11-09-m6-whole-home.md && grep -q 'The `sun` input' docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md && grep -q 'DELETE /running/overlay' docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md && echo "plan and contract present"
test -f src/dj_ledfx/effects/fx.py && grep -q 'def frame_at' src/dj_ledfx/effects/ring_buffer.py && echo "M8 present"
grep -q 'arrive in M6' src/dj_ledfx/looks/model.py && test ! -f src/dj_ledfx/zones/overlay.py && ! grep -q 'def sun_position' src/dj_ledfx/home/sun.py && echo "no M6 yet"
git log --oneline -5 origin/master
```

Expected: `plan and contract present`, `M8 present` and `no M6 yet`. If one is missing, stop and tell the owner. The log shows whether F5 has merged; either is fine, since Task 13 rebases over it. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
(cd web && npm ci)
```

Without the `web` extra the web tests skip silently and mypy reports dozens of extra errors. The web packages are for `npm run api:types` (Tasks 4 and 10) and Task 13's web gate.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1 | tee /tmp/m6-baseline-tests.txt
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ 2>&1 | tee /tmp/m6-baseline-mypy.txt | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm run api:check)
```

Expected: the suite green (its pass count and warnings in `/tmp/m6-baseline-tests.txt`), ruff clean, mypy's count in the last line, perf green, `api:check` clean. Each task's gate compares with these.

---

### Task 1: Home looks play on Whole home

**Files:**
- Modify: `src/dj_ledfx/looks/model.py` (`validate_look`), `src/dj_ledfx/zones/manager.py` (`check_scope`, `start`, `start_preview`), `src/dj_ledfx/zones/preview.py` (`PreviewManager.update`)
- Test: `tests/looks/test_model.py`, `tests/zones/test_manager.py`, `tests/zones/test_preview.py`, `tests/web/test_zones_api.py`, `tests/web/test_preview_api.py`, `tests/web/test_looks_api.py`

**Interfaces:**
- Consumes: `HOME_ZONE_ID`, `HOME_ZONE_NAME`, `ZoneError` (`zones/model.py`); `FakeHome` (`tests/zone_home.py`), whose zones include Whole home.
- Produces: `ZoneManager.check_scope(zone_id: str, look: Look) -> None`, raising `ZoneError(f"{look.name} plays on {HOME_ZONE_NAME} only")` for `look.scope == "whole-home"` on a zone other than `HOME_ZONE_ID`; `validate_look` accepts either scope.

- [ ] **Step 1: Write the failing tests.** Six existing tests pin the refusal; change each, and add the new behaviour:
  - `tests/looks/test_model.py`: drop the `({"scope": "whole-home"}, "M6")` row from the refusal parametrization; add `test_a_home_look_validates` (`validate_look` of a look with `scope="whole-home"` raises nothing).
  - `tests/zones/test_manager.py`: rename `test_a_zone_with_no_lights_or_a_look_m1_cannot_run_is_refused` to `test_a_zone_with_no_lights_or_a_home_look_off_whole_home_is_refused`; its home look on `"z"` now raises `ZoneError, match="plays on Whole home only"`. Add `test_a_home_look_starts_on_whole_home` (`make_home` with `view=FakeHome(rooms={"west": ["lamp"]})`; `start(HOME_ZONE_ID, home_look)` gives a running zone whose look id is `"x"` and whose lights are `("lamp",)`).
  - `tests/zones/test_preview.py`: the `previews.update(second, replace(…, scope="whole-home"))` case raises `ZoneError, match="plays on Whole home only"` (the preview is on a room), and the preview keeps running. Add `test_a_home_look_previews_on_whole_home`.
  - `tests/web/test_zones_api.py` `test_bad_starts_are_refused_with_the_reason`: `too_big` is still a 400, and its detail is `f"{breathe['name']} plays on Whole home only"`.
  - `tests/web/test_preview_api.py` `test_a_bad_preview_request_says_why`: the last row is `(400, f"{home_look['name']} plays on Whole home only")`.
  - `tests/web/test_looks_api.py`: rename `test_a_look_m1_cannot_run_is_refused_with_the_reason` to `test_a_home_look_saves_and_a_look_with_no_layers_is_refused`. The whole-home draft saves with the status `POST /api/looks` answers any new look; the same draft with `layers: []` is a 400 with "A look needs at least one layer".
- [ ] **Step 2: Run them to see them fail:** `uv run pytest tests/looks/test_model.py tests/zones/test_manager.py tests/zones/test_preview.py tests/web/test_zones_api.py tests/web/test_preview_api.py tests/web/test_looks_api.py -q`. Expected: the changed and new tests fail, either on "arrive in M6" or because a home look is refused.
- [ ] **Step 3: Implement.** Remove the scope refusal from `validate_look`. Add `check_scope` to `ZoneManager`. Call it in `start` after `validate_look`, before the lock; in `start_preview` before the runtime is made; and in `PreviewManager.update` with the preview runtime's `zone_id`, after `validate_look`. The web app's tests that quote "arrive in M6" (`web/src/api/preview.test.ts`, `web/src/compose/consequence.test.ts`, `web/src/compose/composer.test.tsx`) build that error themselves as a sample refusal: leave them.
- [ ] **Step 4: Run the Step 2 command.** Expected: all pass.
- [ ] **Step 5: Gate and commit:** run the gate, then `git add -A src/dj_ledfx/looks/model.py src/dj_ledfx/zones/manager.py src/dj_ledfx/zones/preview.py tests/ && git commit -m "M6: Home looks play on Whole home only"`.

### Task 2: The sun's position

**Files:**
- Modify: `src/dj_ledfx/home/sun.py`
- Test: `tests/home/test_sun.py`

**Interfaces:**
- Consumes: astral 3.2's `sun.elevation(observer, dateandtime, with_refraction=True)` and `sun.azimuth(observer, dateandtime)`; `_times(lat, lon, around)`, `CACHE_S`; `Location` (`Home.location`, `.lat`, `.lon`).
- Produces:
  - `SunPoint(at: datetime, elevation_deg: float, azimuth_deg: float)`, frozen, slots, hashable (it keys Task 3's signal cache).
  - `SunReading(now: SunPoint, sunrise: datetime | None, sunset: datetime | None, path: tuple[SunPoint, ...])`, frozen.
  - `sun_position(lat: float, lon: float, at: datetime) -> SunPoint`, with the azimuth in `[0, 360)`.
  - `daylight(lat: float, lon: float, at: datetime) -> tuple[datetime | None, datetime | None]`, with ruling 3's semantics.
  - `sun_path(lat: float, lon: float, at: datetime) -> tuple[SunPoint, ...]`, using `PATH_SPAN = timedelta(hours=2)` and `PATH_STEP = timedelta(minutes=10)`.
  - `plan_bearing(azimuth_deg: float, north_offset_deg: float) -> float`.
  - `class Sun(location: Callable[[], Location | None], *, now=utcnow, clock=time.monotonic)`, with `__call__() -> SunPoint | None` and `reading() -> SunReading | None`. Each is worked out at most once a `CACHE_S` on `clock`, and the location is read each time. With no location both give None, and it logs one WARNING, "The home has no location: looks that need the sun wait", until a location comes back.

- [ ] **Step 1: Write the failing tests** in `tests/home/test_sun.py`, at made-up places only (`EQUATOR = (0.0, 0.0)`, `MID = (45.0, 0.0)`, `POLE = (89.9, 0.0)`) and fixed UTC times:
  - `test_sun_position_is_astrals_apparent_elevation_and_true_azimuth`: at `MID`, 2026-06-21 12:00 UTC, the point's `elevation_deg` and `azimuth_deg` equal astral's (refraction included) within 1e-9, `at` is the time asked, and the azimuth is within `[0, 360)`.
  - `test_daylight_is_the_latest_sunrise_and_the_sunset_after_it`: at `MID` on 2026-06-21, at 12:00 the sunrise is that morning's and the sunset that evening's (sunrise < at < sunset); at 23:00 both are that day's (sunset < at); at 01:00 both are the day before's.
  - `test_the_sun_at_a_pole_has_a_place_but_no_sunrise_or_sunset`: at `POLE` on 2026-06-21 the elevation is finite and above 0, and `daylight` is `(None, None)`; on 2026-12-21 the elevation is below 0 and `daylight` is `(None, None)`.
  - `test_the_path_is_the_ten_minute_marks_of_the_two_hours_before_now_oldest_first`: at 12:34:56 UTC, the 12 points are at 10:40, 10:50, … 12:30; each equals `sun_position` at its mark. At exactly 12:30:00 the last point is 12:30 and the first 10:40. Two calls 30 s apart within one mark give equal paths.
  - `test_plan_bearing_turns_the_azimuth_by_the_north_offset`: `(270, 90) → 0`, `(10, 355) → 5`, `(90, 0) → 90`.
  - `test_sun_works_its_reading_out_at_most_once_a_second_and_follows_the_location`: on a fake clock and a fake `now`, a location callable counts its calls. Two calls within `CACHE_S` read the location once; after `CACHE_S` a changed location gives the new place's point; `reading()` carries `now`, `sunrise`, `sunset` and `path` for the same moment.
  - `test_no_location_no_sun_logged_once`: `Sun(lambda: None)` gives None from both, and the WARNING is logged once over three seconds of calls (capture loguru as this file's `Evening` tests do).
- [ ] **Step 2: Run:** `uv run pytest tests/home/test_sun.py -q`. Expected: the new tests fail with ImportError.
- [ ] **Step 3: Implement** the names above. `daylight` picks from `_times(lat, lon, at.date())["sunrise"]` and `["sunset"]`. `sun_path`'s first mark is the clock's 10-minute mark at or before `at`, stepped back 11 times. `Sun` keeps one cached `SunReading` and its stamp: `__call__` is `reading().now` without building the path when `reading()` hasn't run that second, so the render loop pays for one astral call a second, not 13. The pole tests hold because `_times` never raises.
- [ ] **Step 4: Run the Step 2 command.** Expected: all pass.
- [ ] **Step 5: Gate and commit:** `git add src/dj_ledfx/home/sun.py tests/home/test_sun.py && git commit -m "M6: the sun's position, day and recent path at the home"`.

### Task 3: The sun in every frame, and looks that wait for it

**Files:**
- Create: `tests/sun_fakes.py`, `tests/zones/test_runtime_sun.py`
- Modify: `src/dj_ledfx/effects/context.py`, `src/dj_ledfx/effects/ledset.py` (`Space`), `src/dj_ledfx/home/map.py` (`space_of`), `src/dj_ledfx/zones/runtime.py` (`RuntimeEnv`, `waiting_for`, `tick`), `src/dj_ledfx/zones/manager.py` (`__init__`), `src/dj_ledfx/main.py`
- Test: `tests/effects/test_context.py`, `tests/home/test_map.py`, `tests/zone_home.py`, `tests/zones/conftest.py`, `tests/zones/test_manager.py`, `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: Task 2's `SunPoint` and `Sun`.
- Produces:
  - `SUN_ELEVATION = "sun.elevation"` and `SUN_AZIMUTH = "sun.azimuth"`.
  - `render_context(clock, t, dt, evening=0.0, *, sun: SunPoint | None = None)`. The signals are cached per `(dj, evening, sun)` as `_evening_signals` is now, and the cache's `maxsize` stays small: `Sun` hands out the same object for a second.
  - `Space.north_offset_deg: float = 0.0`, compared in `__eq__` and hashed.
  - `RuntimeEnv.sun: Callable[[], SunPoint | None] = lambda: None`.
  - `ZoneRuntime.waiting_for` leaves out `"sun"` while `env.sun()` isn't None. `tick` calls `on_state_change(self)` when `waiting_for` differs from the last tick's.
  - `ZoneManager(..., sun: Callable[[], SunPoint | None] = lambda: None)`, given to its `RuntimeEnv`; previews and twins inherit it through `replace`.
  - Test helpers: `tests/sun_fakes.py`'s `AT_DUSK = SunPoint(datetime(2026, 3, 20, 18, 0, tzinfo=UTC), 2.0, 270.0)` (made up) and `FixedSun(point: SunPoint | None, reading: SunReading | None = None)`, callable with `.reading()`. `build_home`, `assemble` and `make_home` gain `sun=` (None: `lambda: None`), and the perf file's `home_runtime` defaults `sun` to `lambda: AT_DUSK`.

- [ ] **Step 1: Write the failing tests:**
  - `tests/effects/test_context.py` `test_a_frame_carries_the_suns_signals_while_there_is_one`: `render_context(clock, t, dt, sun=AT_DUSK).signals.get(SUN_ELEVATION)` is 2.0 and `.get(SUN_AZIMUTH)` is 270.0; with `sun=None`, `.get(SUN_ELEVATION, -99.0)` is -99.0; `EVENING` and `DJ_BEAT` are as before either way.
  - `tests/home/test_map.py` `test_the_space_carries_the_north_offset`: `space_of(replace(plan, north_offset_deg=30.0)).north_offset_deg` is 30.0, and that space differs from the one at 0.
  - `tests/zones/test_runtime_sun.py`, with `runtime_of`, `look_of` and a registered test field that keeps the last `ctx` it rendered (defined with `register=False` in the file):
    - `test_a_look_that_needs_the_sun_waits_dark_without_one`: `look_of(layer, needs=("sun",))`, `sun=lambda: None`. After ticks, `waiting_for == ("sun",)`, `state == "waiting"`, and the newest frame is black.
    - `test_a_sun_arriving_starts_a_waiting_zone_and_says_so`: a `FixedSun` whose point the test sets after the first tick; the next tick gives `waiting_for == ()` and `state == "running"`, `on_state_change` is called once for the change, and once more when the sun goes again.
    - `test_every_frame_carries_the_sun_the_env_gives`: the kept ctx's signals hold `AT_DUSK`'s numbers.
    - `test_a_look_that_needs_nothing_never_waits_for_the_sun`.
  - `tests/sun_fakes.py` is imported as `from sun_fakes import AT_DUSK, FixedSun` (`pythonpath = ["tests"]`), as `zone_home` is.
  - `tests/zones/test_manager.py` `test_the_zone_manager_hands_its_runtimes_and_previews_the_sun`: `make_home(..., sun=FixedSun(AT_DUSK))`; a started zone's runtime and a preview's both read `AT_DUSK` from `env.sun()`.
  - `tests/zones/test_runtime_perf.py` `test_a_zone_frame_renders_in_under_5_ms`: also assert `runtime.waiting_for == ()` after its ticks (every built-in, with `home_runtime`'s default sun).
- [ ] **Step 2: Run:** `uv run pytest tests/effects/test_context.py tests/home/test_map.py tests/zones/test_runtime_sun.py tests/zones/test_manager.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** In `tick`, pass `sun=self._env.sun()` to `render_context`. In `main.py`, beside `evening=Evening(...)`, make one `sun = Sun(lambda: home_map.home.location)` before the `ZoneManager` and pass `sun=sun` (Task 4 gives the same object to `create_app`). `space_of` sets `north_offset_deg=home.north_offset_deg`.
- [ ] **Step 4: Run the Step 2 command, then** `uv run pytest -m perf -q tests/zones/test_runtime_perf.py`. Expected: all pass, under budget.
- [ ] **Step 5: Gate and commit:** `git add -A src tests && git commit -m "M6: every frame carries the sun; looks that need it wait for it"`.

### Task 4: The sun on `GET /inputs` and the `inputs` channel

**Files:**
- Modify: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/app.py`, `src/dj_ledfx/web/state.py`, `src/dj_ledfx/web/router_inputs.py`, `src/dj_ledfx/web/ws.py`, `src/dj_ledfx/main.py`; `web/src/api/generated/` (regenerated), `web/src/api/contract.ts`, `web/src/api/contract.test.ts`, `web/src/api/mocks/scenarios.ts`
- Test: `tests/api_home.py`, `tests/web/test_inputs_api.py`, `tests/web/test_ws_channels.py`

**Interfaces:**
- Consumes: Task 2's `Sun.reading()` and `SunReading`; `tests/sun_fakes.py`'s `FixedSun`.
- Produces:
  - `contract.SunPathPoint(at: datetime, elevation: float, azimuth: float)`.
  - `contract.SunInput(elevation: float, azimuth: float, sunrise: datetime | None, sunset: datetime | None, path: list[SunPathPoint] = Field(default_factory=list))`. `sunrise` and `sunset` have no default, so the generated TypeScript has `sunrise: string | null`; `path` has one, so it's `path?: SunPathPoint[]`, matching §12.4.
  - `Inputs.sun: SunInput | None`, with no default (required, nullable). The docstring becomes "GET /inputs: the tempo, Pro DJ Link and the sun; music and Home Assistant join in M7".
  - `sun_out(reading: SunReading | None) -> SunInput | None`, every number rounded to 1 decimal, and `inputs_out(tempo, listening, sun: SunReading | None)`.
  - `create_app(..., sun: Sun | None = None)`, which sets `app.state.sun`, and `state.get_sun(app) -> SunReading | None` (None with no `Sun`).
  - `api_home(..., sun=None)`.

- [ ] **Step 1: Write the failing tests:**
  - `tests/web/test_inputs_api.py` `test_inputs_carry_the_sun_with_its_day_and_path`: `api_home(..., sun=FixedSun(...))` with a reading at made-up numbers (elevation 2.14, azimuth 268.06, two path points). `GET /api/inputs`'s `sun` is `{"elevation": 2.1, "azimuth": 268.1, "sunrise": <UTC text>, "sunset": <UTC text>, "path": [{"at": …, "elevation": …, "azimuth": …}, …]}`, each number to 1 decimal and the times in the contract's UTC form.
  - `test_inputs_say_no_sun_as_null`: with no sun, and with `FixedSun(None)`, `sun` is `null` and the key is present.
  - `test_a_polar_sun_has_null_sunrise_and_sunset`: a reading with both None is sent as `null` and `null`.
  - `tests/web/test_ws_channels.py` `test_the_inputs_channel_carries_the_sun`: the first `inputs` message (`until(ws, "inputs")`) has the same `sun` as `GET /api/inputs`.
- [ ] **Step 2: Run:** `uv run pytest tests/web/test_inputs_api.py tests/web/test_ws_channels.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement** the models and converters; pass `get_sun(request.app)` in `router_inputs.get_inputs` and `get_sun(app)` in `ws._inputs_message`; in `main.py`, pass the Task 3 `sun` to `create_app`.
- [ ] **Step 4: Run the Step 2 command.** Expected: all pass.
- [ ] **Step 5: Regenerate the web app's types and swap in the generated sun:**
  - `(cd web && npm run api:types)`.
  - `web/src/api/contract.ts`: add a section "Served since engine M6 (the sun, overlays)" with `export type SunInput = Schemas['SunInput']` and `export type SunPathPoint = Schemas['SunPathPoint']`. Delete the hand-written two, drop `sun` from `PendingInputs` and update its comment to "What M7 adds to GET /inputs". `Inputs` stays `Schemas['Inputs'] & Partial<PendingInputs>`.
  - `web/src/api/mocks/scenarios.ts`: `ScenarioInputs` becomes `Omit<Required<Inputs>, 'prodjlink' | 'sun'> & { prodjlink: Omit<ProDjLinkInput, 'decks'>; sun: SunInput }`, since every scenario has a location. That keeps the stage tests reading the hero's sun as a `SunInput`.
  - `web/src/api/contract.test.ts`: add `it("serves engine M6's sun", …)`. It checks that `'SunInput' | 'SunPathPoint'` extends `keyof components['schemas']`, that `NonNullable<Inputs['sun']>` equals `SunInput`, and that `SunInput['sunrise']` equals `string | null`.
  - Run `(cd web && npx tsc -b && npm test && npm run lint)`. Expected: clean. If `tsc -b` flags a test reading a sun from `Inputs` rather than a scenario, add a non-null assertion there, and nothing else.
- [ ] **Step 6: Gate and commit:** run the gate, `uv run pytest tests/web/test_openapi_types.py -q`, then `git add -A src tests web/src/api && git commit -m "M6: the sun on GET /inputs and the inputs channel"`.

### Task 5: Home sunset

**Files:**
- Create: `src/dj_ledfx/effects/home_sunset.py`, `tests/effects/test_home_sunset.py`
- Modify: `src/dj_ledfx/effects/field_tools.py` (`sun_point`), `src/dj_ledfx/effects/__init__.py`, `src/dj_ledfx/looks/builtin.py`
- Test: `tests/looks/test_builtin.py`

**Interfaces:**
- Consumes: `SunsetGradient`, `ANCHOR_SHARE`, `HORIZON_SWAY` (`effects/sunset_gradient.py`); `reach`, `height01`; `SUN_ELEVATION`, `SUN_AZIMUTH`; `Space.north_offset_deg`; `plan_bearing`; `leds_at(..., space=)` (`tests/map_home.py`).
- Produces:
  - `sun_point(leds: LedSet, elevation_deg: float, azimuth_deg: float) -> F32`, the point of ruling 6. With `b = radians(plan_bearing(azimuth, leds.space.north_offset_deg))`, the plan direction is `(sin b, −cos b)` (x east, y south, the stage's `bearingVector`). `exit` is the distance from the box's middle to its edge that way; the point is `(cx + exit·cos e·dx, cy + exit·cos e·dy, top + exit·sin e)`.
  - `class HomeSunset(SunsetGradient)`, kind `home_sunset`. `parameters()` is Sunset's without `anchor`. `render` puts the per-LEDs height part (cached through `_per_leds`) and a per-frame `reach(leds, sun_point(...))` together at `ANCHOR_SHARE`. With no sun signal it gives what `SunsetGradient(anchor="")` gives.
  - In `looks/builtin.py`'s `_handoff_layers()`: `"homesunset": (_field("sky", "Gradient", "home_sunset"), <Sunset's candle Flame layer>)`.

- [ ] **Step 1: Write the failing tests** in `tests/effects/test_home_sunset.py`, on a row of LEDs east to west at one height, in a box from (0, 0, 0) to (4, 2, 2) (`leds_at`), with a `RenderContext` whose signals carry the sun:
  - `test_the_sun_point_is_where_the_stage_draws_it_on_the_zones_frame`: north 0. Elevation 0 at azimuth 90 gives (4, 1, 2), the east edge's middle at the top. Azimuth 180 gives (2, 2, 2), the south edge. Elevation 90 gives (2, 1, 2 + exit). A north offset of 90 turns azimuth 0 to the east edge.
  - `test_home_sunset_is_warmest_where_the_sun_stands`: azimuth 270, elevation 2. The westmost LED's red is above the eastmost's, and its blue below.
  - `test_turning_north_turns_its_warmth`: the same sun with `north_offset_deg` 180 in the LEDs' space makes the eastmost LED the warmest.
  - `test_without_a_sun_it_plays_as_sunset_with_no_anchor`: with no sun signals, its frames equal `SunsetGradient`'s with the same settings and `anchor=""`, at three moments.
  - `test_home_sunset_has_sunsets_settings_but_no_anchor`.
  - `test_home_sunset_is_finite_in_range_and_moves_with_the_sun`: elevations −20, 0 and 45 give finite frames in 0..1, and two azimuths 10° apart give different frames.
- [ ] **Add to `tests/looks/test_builtin.py`:**
  - an `M6` tuple of the Home looks built so far, `("homesunset",)` here; Tasks 6 and 7 append `"wisp"` and `"goodnight"`. It joins `SHOWCASE`'s set, and the length check adds `len(M6)`.
  - In `test_each_showcase_look_has_its_fields_and_firmware`: `layers["homesunset"] == [("field", "home_sunset"), ("firmware", "lifx_flame")]`, its Flame's lights and settings equal Sunset's, and the look's `needs == ("sun",)`.
- [ ] **Step 2: Run:** `uv run pytest tests/effects/test_home_sunset.py tests/looks/test_builtin.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement**, and import the effect in `effects/__init__.py` (alphabetical: `from dj_ledfx.effects import home_sunset as _home_sunset  # noqa: F401`).
- [ ] **Step 4: Run the Step 2 command, then** `uv run pytest -m perf -q tests/zones/test_runtime_perf.py`. Expected: all pass; Home sunset joins the perf sweep with a sun and doesn't wait.
- [ ] **Step 5: Gate and commit:** `git add -A src tests && git commit -m "M6: Home sunset, the sunset with the real sun"`.

### Task 6: Wisp

**Files:**
- Create: `src/dj_ledfx/effects/wisp.py`, `tests/effects/test_wisp.py`
- Modify: `src/dj_ledfx/effects/particle_tools.py` (`lamp_rooms`), `src/dj_ledfx/effects/__init__.py`, `src/dj_ledfx/looks/builtin.py`
- Test: `tests/effects/test_particle_tools.py`, `tests/looks/test_builtin.py`

**Interfaces:**
- Consumes: `ParamParticles.positions(ctx, ground)` and `drawn()` (`effects/particles.py`), `Ground` (`lamps`, `on(stop, u)`), `Lamps`, `tour`, `draws`, `arc`, `swarm`, `ease_in_out` (`effects/easing.py`), `REACH`, `NO_ROOM`, Spotlights' tour pattern (`effects/spotlights.py`); `seeded_ledset()`, `leds_at`, `tiny_home()` (`tests/map_home.py`).
- Produces:
  - `lamp_rooms(ground: Ground) -> NDArray[np.intp]`: each lamp's room, the `LedSet.room` of its first member LED (`NO_ROOM` for an unplaced one).
  - `class Wisp(ParamParticles)`, kind `wisp`, with ruling 7's settings: `count` (int, 2, 1–4), `hold_s` (float, 4.0, 0.5–30), `move_s` (float, 3.0, 0.5–20), `size` (float, 0.5, 0.2–1.5), `palette` (color_list, one warm white), `level` (`level_param(0.8)`).
  - `"wisp": (_particles("wisp", "wisp"),)` in `_handoff_layers()`.

- [ ] **Step 1: Write the failing tests:**
  - `tests/effects/test_particle_tools.py` `test_lamp_rooms_gives_each_lamp_its_room`: on `leds_at` with two rooms and an unplaced light, `lamp_rooms(Ground.of(leds))` lists each lamp's room index and `NO_ROOM` for the unplaced one.
  - `tests/effects/test_wisp.py`:
    - `test_wisp_makes_count_wisps_at_every_moment`: `count` 1 to 4 gives that many particles at 20 moments on `seeded_ledset()`.
    - `test_a_wisp_rests_on_a_lamps_led_then_moves_to_another_room`: at each rest's middle, every wisp sits on one LED's position. On a two-room `leds_at`, consecutive rests of one wisp are in different rooms.
    - `test_with_one_room_a_wisp_tours_its_lamps`: three lamps in one room are each visited within one round, never the same lamp twice running.
    - `test_each_lamp_glows_only_while_a_wisp_is_near`: `drawn(effect, ctx, leds)`. An LED farther than `REACH` radii of `size` from every wisp is black, and an LED a wisp rests on is lit.
    - `test_wisps_set_off_apart`: two wisps never start a glide in the same frame.
    - `test_wisp_is_the_same_moment_however_the_frames_fall`: the frame at t equals itself after a run of other moments.
  - `tests/looks/test_builtin.py`: append `"wisp"` to `M6` and add `"wisp": "wisp"` to `PARTICLE_KINDS`. In `test_each_particle_look_has_its_particle_layer_named_after_it`, a look in `M6` asserts `look.category == "home"` and `look.needs == ()` rather than the tempo branch.
- [ ] **Step 2: Run:** `uv run pytest tests/effects/test_particle_tools.py tests/effects/test_wisp.py tests/looks/test_builtin.py -q`. Expected: the new tests fail. `tests/effects/test_particle_effects.py`'s sweep takes Wisp in by its registry once it registers.
- [ ] **Step 3: Implement.** A wisp `k`'s step is `floor((t + k·(hold_s + move_s)/count) / (hold_s + move_s))`. Its room at a step is `rooms[tour(seed, k, step, len(rooms))]`. Its lamp in that room and the LED on that lamp come from `draws(seed, key=(k, step), 2, stream=WISP_VISITS)`, a stream constant of its own. Its position is the rest's LED, then `arc(from, to, ease_in_out(share), rise=0.0)` while it glides. Import the effect in `effects/__init__.py`.
- [ ] **Step 4: Run the Step 2 command, then** `uv run pytest tests/effects/test_particle_effects.py -q` and `uv run pytest -m perf -q tests/effects/test_particle_effects.py tests/zones/test_runtime_perf.py`. Expected: all pass, including the sweep's largest settings and the cap.
- [ ] **Step 5: Gate and commit:** `git add -A src tests && git commit -m "M6: Wisp, wisps that roam room to room"`.

### Task 7: Goodnight, and a look's elapsed time

**Files:**
- Create: `src/dj_ledfx/effects/goodnight.py`, `tests/effects/test_goodnight.py`
- Modify: `src/dj_ledfx/home/geometry.py` (`polygon_centre`), `src/dj_ledfx/effects/context.py` (`RenderContext.elapsed_s`), `src/dj_ledfx/zones/runtime.py` (`started_t`), `src/dj_ledfx/zones/manager.py` (`monotonic=`, `_started_t`), `src/dj_ledfx/effects/__init__.py`, `src/dj_ledfx/looks/builtin.py`
- Test: `tests/home/test_geometry.py`, `tests/effects/test_context.py`, `tests/zones/test_runtime.py`, `tests/zones/test_manager.py`, `tests/looks/test_builtin.py`; `tests/zone_home.py` and `tests/zones/conftest.py` (`monotonic=`)

**Interfaces:**
- Consumes: `Space.room_outlines`, `Space.rooms`, `LedSet.room`, `NO_ROOM`; `normalise_name`; `_Running.since`; `RuntimeEnv`, `ZoneRuntime.twin()`, `render(ctx, *, in_space=True)`, `restart()`, `update_look()`.
- Produces:
  - `polygon_centre(polygon: Polygon) -> tuple[float, float]`, the area centroid (the vertex mean for a polygon of no area).
  - `RenderContext.elapsed_s: float = 0.0`, and `render_context(..., elapsed_s: float = 0.0)`: seconds since the zone started this look.
  - `ZoneRuntime(..., started_t: float | None = None)`, read back as the property `started_t`, on the engine's monotonic clock; None means `time.monotonic()` at construction. `tick` gives each frame `elapsed_s = target − started_t`. In a transition, each replaced look renders with its own runtime's elapsed time (`dataclasses.replace(ctx, elapsed_s=…)`). `twin()` keeps `started_t`, `restart()` and `update_look()` keep it, and a preview has its own.
  - `ZoneManager(..., monotonic: Callable[[], float] = time.monotonic)` and `_started_t(since: datetime) -> float`, which is `monotonic() − max(0, (now() − since).total_seconds())`. It's passed from `_new_runtime(..., started_t=)` for a start, a resume and a rebuild, so a resumed look counts from its saved `since`.
  - `class Goodnight(ParamField)`, kind `goodnight`, with ruling 9's settings and constants `FRONT_BOOST = 1.4`, `FRONT_S = 3.0` and `FADE_S = 2.0`. Its per-LEDs work (each room's order and switch time) is cached through `_per_leds`.
  - `room_named_in(text: str, rooms: Sequence[Room]) -> str`, the twin of `anchor_named_in`.
  - `STARTS_BY_HAND: frozenset[str] = frozenset({"goodnight"})`; `_from_handoff` gives such a look `needs=()` and `uses=tuple(entry["inputs"])`.
  - `"goodnight": (_field("walk", "Goodnight", "goodnight", night_room=room_named_in(entry's description, home.rooms)),)` in `_handoff_layers()`, which reads `seed_home()` once for anchors and rooms alike (`test_the_handoff_layers_seed_the_map_once` holds).

- [ ] **Step 1: Write the failing tests:**
  - `tests/home/test_geometry.py` `test_polygon_centre_is_the_area_centroid`: a 4×2 rectangle gives (2, 1); an L shape gives its known centroid; three points on a line give their mean.
  - `tests/effects/test_context.py` `test_a_frame_carries_the_looks_elapsed_time`.
  - `tests/zones/test_runtime.py`:
    - `test_a_runtime_counts_its_looks_time_from_its_start`: `runtime_of(look, started_t=100.0)`, then `tick(110.0)`; the kept ctx's `elapsed_s` is `110 + horizon_s − 100`.
    - `test_a_twin_and_a_transitions_old_look_keep_their_own_elapsed_time`: during a fade from a look started at 100 to one started at 150, the old look renders with its own elapsed time and the new one with its own, and a twin's elapsed time equals its zone's.
    - `test_a_restart_and_a_look_update_keep_the_start`.
  - `tests/zones/test_manager.py`:
    - `test_a_resumed_zone_counts_its_looks_time_from_its_saved_start`: an assignment saved 30 s before `now`, with a fake `monotonic` at 1000. After `resume()`, the runtime's `started_t` is 970.
    - `test_a_restart_keeps_the_zones_start`.
    - `test_a_new_start_counts_from_zero`.
  - `tests/effects/test_goodnight.py`, on `leds_at` with three rooms in a row (west, middle, east, made-up ids) and `night_room` the west room:
    - `test_every_room_glows_warm_at_the_start`: at elapsed 0 every LED is lit at about `level`.
    - `test_rooms_switch_off_farthest_from_the_night_room_first`: the east room is black from `walk_s/3 + FADE_S/2`, while the middle room is still lit.
    - `test_each_room_brightens_as_the_front_reaches_it_then_goes_black`: a room's brightest moment falls within `FRONT_S` before its switch, above its start level, and it's black `FADE_S` after.
    - `test_the_night_room_settles_on_its_night_light_and_stays`: after `walk_s`, the night room's LEDs are at `night_level` times its colour, still so at `walk_s·10`, and every other LED is black.
    - `test_leds_in_no_room_go_dark_with_the_first_room`.
    - `test_a_night_room_not_on_the_map_walks_every_room_off`.
    - `test_goodnight_is_a_function_of_its_elapsed_time`: the same `elapsed_s` gives the same frame at different `t`.
  - `tests/looks/test_builtin.py`:
    - `test_a_room_is_found_by_the_name_a_text_mentions`: the twin of the anchor test on `tiny_home().rooms`, its text built from a room's name read at run time.
    - `test_goodnights_night_room_is_the_room_its_description_names`: the setting is a room of `seed_home()` whose name, lower-cased, is in the look's description.
    - The metadata test expects `needs == ()` and `uses == tuple(entry["inputs"])` for a look in `STARTS_BY_HAND`, and `NEEDS_UNTIL_M7`'s value or the handoff's inputs otherwise.
    - Append `"goodnight"` to `M6`; `layers["goodnight"] == [("field", "goodnight")]`.
- [ ] **Step 2: Run:** `uv run pytest tests/home/test_geometry.py tests/effects/test_context.py tests/zones/test_runtime.py tests/zones/test_manager.py tests/effects/test_goodnight.py tests/looks/test_builtin.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Import the effect in `effects/__init__.py`.
- [ ] **Step 4: Run the Step 2 command, then** `uv run pytest -m perf -q tests/zones/test_runtime_perf.py`. Expected: all pass.
- [ ] **Step 5: Gate and commit:** `git add -A src tests && git commit -m "M6: Goodnight walks the rooms off and leaves one on a night light"`.

### Task 8: Lights out, Goodnight's rooms switched off

**Files:**
- Create: `tests/zones/test_manager_lights_out.py`
- Modify: `src/dj_ledfx/devices/adapter.py` (`switches_power`), `src/dj_ledfx/devices/lifx/base.py`, `src/dj_ledfx/devices/govee/adapter_base.py`, `src/dj_ledfx/effects/field.py` (`FieldEffect.lights_out`), `src/dj_ledfx/effects/goodnight.py`, `src/dj_ledfx/zones/runtime.py`, `src/dj_ledfx/zones/manager.py`, `src/dj_ledfx/main.py`
- Test: `tests/conftest.py` (`FakeLight(switches_power=)`), `tests/runtime_fakes.py` (`OutField`), `tests/devices/test_adapter_state.py`, `tests/effects/test_goodnight.py`, `tests/zones/test_runtime.py`, `tests/zone_home.py` and `tests/zones/conftest.py` (`sleep=`)

**Interfaces:**
- Consumes: Task 7's `Goodnight`, `ZoneRuntime.started_t` and `_started_t`; `_Running`, `_take_over`, `_redraw`; the zone manager's `_sync`, `_sync_device`, `_look_at`, `_release`, `_end_run`, `_switch_on`, `_set_power`, `_ready`, `verify_firmware` and `on_power_reading`; `adapter.send_lock`; the runtime's layer views and `transitioning`; `FakeLight`'s `calls` and `power`; `lifx_bulb()` (`tests/lifx_fakes.py`), `lamp_transport()` (`tests/govee_fakes.py`), `adapter_of()` (`tests/openrgb_fakes.py`).
- Produces (ruling 19):
  - `DeviceAdapter.switches_power -> bool` (a property), False by default, True for the LIFX adapters (`devices/lifx/base.py`) and the Govee ones (`devices/govee/adapter_base.py`); OpenRGB keeps False. `FakeLight(..., switches_power: bool = True)`.
  - `FieldEffect.lights_out(leds: LedSet) -> F32 | None`: each LED's elapsed time from which the effect has it black for good (`inf`: never); None by default.
  - `Goodnight.lights_out(leds)`, ruling 9's, from the same `_per_leds` builder as its render (one builder, so its slot never hands back another's array), and `OFF_AFTER_S = 1.0`.
  - `ZoneRuntime.out_after(device_id: str) -> float | None`, kept until the look or the LEDs change.
  - `_Running.switched_off: set[str]`, the lights the timer switched off in that run. `ZoneManager._is_out(device_id: str) -> bool`: in its owning run's `switched_off`, or past its moment as ruling 19 says; the lights-out timer: `_schedule_lights_out()`, called at the end of every `_sync` and after each wake, one task, a due light whose zone is mid-transition tried again after `LIGHTS_OUT_RETRY_S` (1 s); `_restore_on: set[str]`, filled by `_end_run`, read by `_release`, and emptied as each light is released or switched on; the kwarg `sleep: Callable[[float], Awaitable[None]] = asyncio.sleep`; `close() -> None`, which cancels the timer.
  - `tests/runtime_fakes.py`'s `OutField`, registered with the other test fields: black everywhere, its `lights_out` giving the LEDs of the light ids in its `out` setting (light id to seconds) those times and every other LED `inf`.
  - `main.py`: `zone_manager.close()` before `previews.close()`.

- [ ] **Step 1: Write the failing tests:**
  - `tests/devices/test_adapter_state.py` `test_which_lights_switch_power`: a LIFX bulb (`lifx_bulb(transport)`) and `GoveeRazerAdapter(lamp_transport(can_receive=False), lamp_record(), 15)` say True, and that Govee adapter's `set_power(False)` sends `build_turn_message(on=False)` on its transport though it can't hear the lamp; an OpenRGB adapter (`adapter_of()`) and a bare `DeviceAdapter` subclass say False.
  - `tests/effects/test_goodnight.py` `test_lights_out_is_each_rooms_switch_its_fade_and_a_second`: on Task 7's three-room row, the east room's LEDs give `walk_s/3 + FADE_S + OFF_AFTER_S`, the middle room's `2·walk_s/3 + FADE_S + OFF_AFTER_S`, the night room's `inf`, and LEDs in no room the east room's. Every frame at or after an LED's time has it black.
  - `tests/zones/test_runtime.py`:
    - `test_a_light_is_out_after_its_latest_leds_time`: `OutField` giving one light's LEDs 5 and 7 s gives `out_after` 7.0; a light with one LED at `inf` gives None.
    - `test_nothing_is_out_unless_every_layer_says_so_unmasked_and_unflashed`: each of these gives None: a second visible layer with no `lights_out`, a mask on the layer, `downbeat_flash` on, and a light a firmware layer claims. A hidden second layer changes nothing.
  - `tests/zones/test_manager_lights_out.py`, on `make_home` over `FakeHome` (rooms `west: [a]` and `east: [b]`) with fake `sleep` and `monotonic` and `OutField(out={"a": 5.0})` started on `HOME_ZONE_ID`:
    - `test_a_light_is_switched_off_once_its_look_has_it_dark_for_good`: before 5 s `a` streams. At 5 s its route is gone and `("power", False)` is its last call, and `power_of("a")` is False. `b` still streams and gets no power call.
    - `test_a_light_that_cant_switch_power_keeps_streaming_black`: `FakeLight(switches_power=False)` gets no power call and keeps its streaming route.
    - `test_an_out_light_switched_on_elsewhere_is_left_alone`: after 5 s, `on_power_reading("a", True)` then `verify_firmware("a")` give no prepare, no frame, no power call and no route.
    - `test_a_later_start_switches_it_back_on_and_keeps_its_capture`: a flat look started on `west` gives `("power", True)`, a prepare and a streaming route, and no second `capture`; Off on `west` then restores `b"before"` with power.
    - `test_off_and_stop_all_restore_an_out_light_power_included`, parametrized over `off(HOME_ZONE_ID)` and `stop_all()`: `a` gets `("restore", b"before")`, not `restore_off`, and reads on again; `b` is restored as before.
    - `test_an_out_light_with_nothing_captured_stays_off_at_off`: `FakeLight(captured=None)` gets no restore and stays off.
    - `test_preview_only_sends_nothing_power_included`: with preview only on before 5 s, no `("power", …)` call comes at 5 s or after. Turning it off after 5 s sends `a` nothing (no prepare, no power), while `b` is prepared and streams.
    - `test_a_resume_after_the_walk_leaves_out_lights_alone`: with an assignment saved 60 s before `now`, after `resume()` `a` is neither captured, prepared nor switched, and `b` streams.
    - `test_a_resume_mid_walk_switches_off_only_the_lights_still_to_come`: `OutField(out={"a": 5.0, "b": 20.0})` with the assignment saved 10 s before `now`: `a` is left alone, and `b` is switched off at 20 s of the look's time.
    - `test_a_restart_keeps_the_walk`: `restart(HOME_ZONE_ID)` after 5 s doesn't switch `a` on.
    - `test_a_take_over_of_another_light_leaves_an_out_light_out`: after 5 s a flat look started on `east` takes `b`; Whole home is rebuilt with `a` alone, and `a` gets no call and no route; Off on `home` then restores it with power. It holds too when the rebuilt runtime's `out_after("a")` is later than now (monkeypatch it to answer 50.0 after the rebuild): the run's `switched_off` mark keeps `a` out.
    - `test_no_light_is_switched_off_mid_transition`: started with a 10 s fade, `a` is switched off only once the fade has ended, within `LIGHTS_OUT_RETRY_S`.
    - `test_a_light_offline_at_its_moment_is_left_as_it_comes_back`.
    - `test_close_ends_the_lights_out_timer`.
    - `test_goodnight_switches_the_far_room_off_and_leaves_the_night_room_on`: `build_home(plan=tiny_home())`, one light in each room, Goodnight's night room the first light's room. After `walk_s + FADE_S + OFF_AFTER_S` the other light got `("power", False)`, and the night room's light still streams.
- [ ] **Step 2: Run:** `uv run pytest tests/devices/test_adapter_state.py tests/effects/test_goodnight.py tests/zones/test_runtime.py tests/zones/test_manager_lights_out.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** `_sync_device` leaves an out light alone right after it finds the owning runtime: the route set to None and `_applied` popped, before any switch-on. `_look_at` neither reads nor captures an out light, and `verify_firmware` returns early for one. The timer's switch-off takes the route away first, then sends `set_power(False)` under the adapter's `send_lock`, then calls `_set_power(device_id, False)` and adds the light to its run's `switched_off`. A failure is logged at WARNING and the light is left dark but on. `_release` passes `power=True` for a light in `_restore_on`. The existing power tests in `tests/zones/test_manager.py` and `tests/zones/test_manager_lifecycle.py` pass unchanged: a light switched off elsewhere still drops out and rejoins, and Off still never switches on a light dj-ledfx didn't switch off.
- [ ] **Step 4: Run the Step 2 command, then** `uv run pytest tests/zones tests/devices -q`. Expected: all pass.
- [ ] **Step 5: Gate and commit:** `git add -A src tests && git commit -m "M6: Goodnight switches off the lights of the rooms it walks off"`.

### Task 9: Overlays in the engine

**Files:**
- Create: `src/dj_ledfx/zones/overlay.py`, `tests/zones/test_overlay.py`, `tests/zones/test_manager_overlay.py`
- Modify: `src/dj_ledfx/scheduling/route.py`, `src/dj_ledfx/zones/model.py` (`OverlayInfo`), `src/dj_ledfx/zones/manager.py`, `src/dj_ledfx/zones/frames.py`, `src/dj_ledfx/main.py`
- Test: `tests/scheduling/test_route.py`, `tests/zones/test_frames.py`, `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: Task 8's `_is_out`, `sleep=` and `close()`; `ZoneRuntime(..., emulated=, started_t=)`, `ring`, `leds.slice_for`, `streams()`; `_new_runtime`, `_members`, `_zones[HOME_ZONE_ID]`, `_follow`, `_publish`, `_host.add_runtime`/`remove_runtime`, `ZonesChanged`; `smoothstep`; `FakeRoutes.routes` (`tests/zone_home.py`).
- Produces:
  - In `scheduling/route.py`:
    - `class OverSource(Protocol)`, with `def over_at(self, device_id: str, t: float, count: int) -> tuple[FloatRGB, float] | None`: the overlay's colours for that light at `t`, and its amount, or None when nothing plays, the overlay doesn't cover the light, its slice isn't `count` LEDs, its ring is empty, or the amount is 0.
    - `overlaid(base: FloatRGB, scale: float, top: FloatRGB, amount: float) -> FloatRGB`, ruling 10's screen, which never writes `base` or `top`.
    - `DeviceRoute.over: OverSource | None = None`. `colors_at` asks it at the route's own `target_time` and converts the mix at scale 1.0, or does exactly what it does now when there is nothing to mix.
  - In `zones/overlay.py`:
    - `MAX_OVERLAY_S = 3600.0` and `OVERLAY_EDGE_S = 0.25`.
    - `OverlayRun(look, trigger, runtime, started_t, ends_t, started_at, ends_at)`, frozen, with `amount(t) -> float`: `smoothstep` up over the first `OVERLAY_EDGE_S` and down over the last, 0 outside, peaking below 1 when shorter than two edges.
    - `class OverlaySlot(reaches: Callable[[str], bool])`, an `OverSource`, with `run: OverlayRun | None`. The manager makes it with `reaches=lambda d: not self._is_out(d)`, so `over_at` gives None for a light its look has switched off, for the frame feed as for the routes (ruling 11).
  - In `zones/model.py`: `OverlayInfo(look_id, look_name, trigger, started_at: datetime, ends_at: datetime)`.
  - In `ZoneManager`:
    - `async start_overlay(look: Look, duration_s: float, trigger: str = "api") -> OverlayInfo`, with ruling 13's refusals. A duration outside (0, `MAX_OVERLAY_S`] or not finite raises `ZoneError`; the API's 422 comes first.
    - `async stop_overlay() -> None`, idempotent.
    - `overlays() -> list[OverlayInfo]` and `overlay_slot -> OverlaySlot` (property).
    - `close()` (Task 8's) cancels the end task too; the end task sleeps through Task 8's `sleep=`.
    - `_publish` gives every streaming route `over=self._overlay_slot`, whether or not an overlay plays, so starting and ending one changes no route. `stop_all` ends the overlay first, even with no zone running. `_redraw` makes the overlay runtime follow Whole home's members.
    - An overlay's start and end each emit `ZonesChanged`.
  - `FrameFeed(live, previews=list, *, clock=time.monotonic, overlay: OverSource | None = None)`: `frames("live", …)` mixes the overlay into a live runtime's device slice where `runtime.streams(device_id)` and `over_at` gives colours; `fx()` is unchanged (ruling 14).
  - `main.py`: `FrameFeed(..., overlay=zone_manager.overlay_slot)`.

- [ ] **Step 1: Write the failing tests:**
  - `tests/scheduling/test_route.py`:
    - `test_overlaid_screens_the_overlay_onto_the_zone_after_its_brightness`: base 0.5 at scale 0.5 and top 0.4 at amount 1 give 0.25 + 0.4 − 0.1 = 0.55; at amount 0.5 they give 0.25 + 0.2 − 0.05; base and top are unchanged.
    - `test_a_route_with_nothing_to_mix_sends_what_it_sent_before`: `over` None, and an `OverSource` answering None, both give bytes equal to `to_device_colors(colours, n, brightness)`.
    - `test_a_route_reads_the_overlay_at_its_own_moment`: a fake `OverSource` records the `t` it's asked at; it's the route's `target_time`.
  - `tests/zones/test_overlay.py`:
    - `test_an_overlays_amount_eases_in_and_out_over_its_edges`: 0 at `started_t` and before, 1 from `started_t + OVERLAY_EDGE_S` to `ends_t − OVERLAY_EDGE_S`, 0 at `ends_t` and after, rising and falling monotonically between.
    - `test_an_overlay_shorter_than_its_edges_peaks_below_full`.
    - `test_the_slot_gives_nothing_for_a_light_it_doesnt_cover_or_of_another_led_count`.
    - `test_the_slot_gives_the_overlays_colours_and_amount_at_a_moment`.
  - `tests/zones/test_manager_overlay.py`, with `make_home` over `FakeHome` (rooms `west: [a, b]`, `east: [c]`), registered test fields (`_fields`), and a home look made of a flat field. Fake `sleep` and `monotonic` come in through `make_home`'s `sleep=` and `monotonic=` (Tasks 8 and 7):
    - `test_an_overlay_plays_over_every_running_zone_and_they_keep_running`: west and east each run a look. After `start_overlay(home_flat, 8)`, each streaming route's colours at a moment mid-overlay are `overlaid` of its zone's and the overlay's. `running()` is unchanged, `overlays()` has one with the trigger `"api"`, `ends_at = started_at + 8 s`, and `ZonesChanged` was emitted.
    - `test_only_a_home_look_plays_over_everything`.
    - `test_an_overlay_needs_lights_and_its_inputs`: a look needing the sun with `sun=lambda: None` is refused with "waits for"; Whole home with no lights is refused with "has no lights".
    - `test_a_newer_overlay_replaces_the_one_playing`: the first overlay's runtime is removed from the host, and `overlays()` holds the second only.
    - `test_an_overlay_ends_by_itself_and_says_so`: release the fake sleep. `overlays()` is empty, the runtime is gone from the host, `ZonesChanged` was emitted, and the routes send their zones' colours as before.
    - `test_stop_all_ends_the_overlay_even_with_nothing_running`.
    - `test_stop_overlay_is_idempotent`.
    - `test_a_zone_started_under_an_overlay_is_overlaid_from_its_first_send`: its routes carry the slot.
    - `test_an_overlay_reaches_no_idle_light_and_no_light_running_its_own_effect`: an idle light has no route. A light running a firmware layer (`GlowFirmware`, `tests/conftest.py`) has a route with `streaming=False`, which the scheduler never sends. With preview only on, no route streams.
    - `test_the_overlay_follows_the_whole_homes_lights_when_the_map_changes`: `FakeHome` gains a light and `home_changed()` runs; the overlay runtime's lights include it.
    - `test_close_ends_the_overlays_timer`: no task is left pending after `close()`.
    - `test_an_overlay_never_reaches_a_light_its_look_switched_off`: `west` runs `OutField(out={"a": 5.0})`. After 5 s an overlay leaves `a` with no route, and `overlay_slot.over_at("a", …)` is None, while `b` and `c` are overlaid.
  - `tests/zones/test_frames.py`:
    - `test_the_live_feed_shows_the_overlay_on_the_lights_it_reaches`: a light that streams shows the mix in 8 bits, and one running its own effect (drawn as a copy) shows its copy alone.
    - `test_the_feed_leaves_the_overlay_out_of_fx`.
  - `tests/zones/test_runtime_perf.py` (perf):
    - `test_a_route_mixing_an_overlay_stays_cheap`: `colors_at` over a seeded light's slice with an overlay playing averages under 0.25 ms a call over 1000 calls.
    - `test_an_overlay_renders_in_budget`: Wisp's and Home sunset's overlay runtimes on every seeded LED, with `emulated` all, render each frame in under 5 ms.
- [ ] **Step 2: Run:** `uv run pytest tests/scheduling/test_route.py tests/zones/test_overlay.py tests/zones/test_manager_overlay.py tests/zones/test_frames.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.**
  - The overlay runtime is `self._new_runtime(HOME_ZONE_ID, look, members, 1.0, env=replace(self._env, on_state_change=None, on_switch=None), emulated=members, started_t=self._monotonic())`. `_new_runtime` gains `emulated=`. `ends_t = started_t + duration_s`; `started_at = self._now()`; `ends_at = started_at + duration`.
  - The end task sleeps `duration_s`, then ends that run if it's still the slot's. The start and the end run under `self._lock`.
  - `over_at` copies nothing: `overlaid` makes the new array.
- [ ] **Step 4: Run the Step 2 command, then** `uv run pytest -m perf -q tests/zones/test_runtime_perf.py`. Expected: all pass, under budget.
- [ ] **Step 5: Gate and commit:** `git add -A src tests && git commit -m "M6: overlays, a Home look played over every running zone"`.

### Task 10: Overlays over REST and the `running` channel

**Files:**
- Create: `tests/web/test_overlay_api.py`
- Modify: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_zones.py`, `src/dj_ledfx/web/ws.py`; `web/src/api/generated/`, `web/src/api/contract.ts`, `web/src/api/contract.test.ts`
- Test: `tests/web/test_ws_channels.py`

**Interfaces:**
- Consumes: Task 9's `start_overlay`, `stop_overlay`, `overlays()` and `OverlayInfo`; `requested_look` (`router_zones.py`); `answers()`; `raw_json` and `until` (`tests/web/conftest.py`).
- Produces:
  - `OverlayRequest(look_id: str | None = None, look: Look | None = None, duration_s: float = Field(gt=0, le=MAX_OVERLAY_S, allow_inf_nan=False), trigger: str = Field(default="api", min_length=1, max_length=200))`.
  - `overlay_out(info: OverlayInfo, now: datetime) -> Overlay`, with ruling 16's `progress`.
  - `running_out(infos, index, overlays: Iterable[OverlayInfo] = (), now: datetime | None = None)`.
  - `POST /running/overlay` (status 201, answers `Overlay`; docstring "Play a Home look over every running zone for durationS seconds; it replaces any overlay playing") and `DELETE /running/overlay` (status 204; docstring "End the overlay playing, if one is").
  - `list_running` and `ws._running_message` pass `zones.overlays()`.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_overlay_api.py`, on `api_home` with a `FakeHome` that has Whole home and a running room zone:
  - `test_post_overlay_plays_a_home_look_over_everything`: `POST /api/running/overlay {"lookId": "wisp", "durationS": 8}` is a 201. The body's `lookId` is `"wisp"`, `name` is looks.json's (read through `handoff_looks()`), `trigger` is `"api"`, `endsAt` is 8 s after the start in UTC, and `progress` is 0.0. `GET /api/running`'s `overlays` holds the same.
  - `test_an_overlay_takes_a_draft_and_names_its_trigger`: a draft `look` and `"trigger": "test"`.
  - `test_bad_overlays_are_refused_with_the_reason`:
    - both or neither of `lookId` and `look`: 400, "Send either lookId or look";
    - an unknown look: 404;
    - an any-zone look: 400, "Only a Home look plays over everything";
    - `durationS` 0, 3601, a string, or NaN sent with `raw_json`: 422;
    - a 201-character `trigger`: 422.
  - `test_delete_overlay_ends_it_and_answers_204_either_way`.
  - `test_progress_is_the_share_of_the_overlay_played`: `overlay_out(info, now)` gives 0.5 halfway, and 0.0 and 1.0 before and after.
  - `tests/web/test_ws_channels.py` `test_the_running_channel_pushes_the_overlay_as_it_starts_and_ends`: after the POST, `until(ws, "running")` has one overlay; after the DELETE, none.
- [ ] **Step 2: Run:** `uv run pytest tests/web/test_overlay_api.py tests/web/test_ws_channels.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the Step 2 command.** Expected: all pass.
- [ ] **Step 5: Regenerate the types.** `(cd web && npm run api:types)`. In `contract.ts`'s M6 section add `export type OverlayRequest = Schemas['OverlayRequest']` (`Overlay` is already the generated alias). Extend the M6 test in `contract.test.ts`: `'OverlayRequest'` extends `keyof components['schemas']`, `'/api/running/overlay'` extends `ApiPath`, and `Overlay['progress']` is `number`. Run `(cd web && npx tsc -b && npm test && npm run lint)`. Expected: clean.
- [ ] **Step 6: Gate and commit:** the gate and `uv run pytest tests/web/test_openapi_types.py -q`, then `git add -A src tests web/src/api && git commit -m "M6: POST and DELETE /api/running/overlay, and overlays on the running channel"`.

### Task 11: A lamp-safe dry run

No files change; the scripts go to a temporary directory. This run reaches no light: the device backends are cleared and replaced by simulated ones, and the namespace has only loopback. So it needs no owner go (ruling 17). The simulated lights take Goodnight's power commands, so the run checks lights out end to end.

- [ ] **Step 1: Write the driver and the probe:**

```bash
D=$(mktemp -d /tmp/m6-dry.XXXXXX)
cat > "$D/driver.py" <<'EOF'
import sys

sys.path.insert(0, "tests")  # FakeLight
from conftest import FakeLight  # noqa: E402

import dj_ledfx.main  # noqa: E402
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice  # noqa: E402
from dj_ledfx.home.seed import seed_lights  # noqa: E402
from dj_ledfx.latency.tracker import tracker_for  # noqa: E402

DeviceBackend._registry.clear()  # no real backend: nothing reaches a light


class SimBackend(DeviceBackend):  # registers itself
    def is_enabled(self, config):
        return True

    async def discover(self, config, on_found=None, skip_ids=None, known=()):
        found = []
        for n, seed in enumerate(seed_lights()):  # the seed's names, read here, never typed
            if skip_ids and f"sim-{n}" in skip_ids:
                continue
            light = FakeLight(f"sim-{n}", name=seed.name, led_count=seed.leds)
            device = DiscoveredDevice(light, tracker_for(config.devices.lifx, name=seed.name), None)
            if on_found is not None:
                on_found(device)
            found.append(device)
        return found


sys.argv = ["dj_ledfx", *sys.argv[1:]]
dj_ledfx.main.main()
EOF
```

`$D/probe.py` uses `httpx` against `http://127.0.0.1:8098` and prints only counts and statuses, never a name or a number from the map. In order, it:
  - waits up to 60 s for `GET /api/lights` to list every simulated light;
  - `POST /api/lights/placement/guess` (seeds match by name);
  - prints whether `GET /api/inputs`'s `sun` is present (the seed's demo location), and its key set;
  - prints the ids of `GET /api/looks` among `homesunset`, `wisp` and `goodnight`, with each one's `category`, `scope`, `needs` and `thumbnail`;
  - `POST /api/zones/home/start {"lookId": "homesunset"}` and prints the status and the zone's `state`, `waitingFor` and light count;
  - `POST /api/zones/<the first room's id from GET /api/zones>/start {"lookId": "wisp"}` and prints the status (400 expected);
  - starts `sunset` on that room, then `POST /api/running/overlay {"lookId": "wisp", "durationS": 5}` and prints the status and `len(GET /api/running .overlays)`; it sleeps 6 s and prints the length again;
  - starts Goodnight on `home` as a draft (`GET /api/looks`'s `goodnight` with its layer's `walk_s` set to 10, sent as `{"look": …}`) and prints the status and `state`. It then polls `GET /api/lights` for up to 30 s and, once the count stops changing, prints how many lights read `power: false`, how many `true`, and how many have `status: switched-off`;
  - `POST /api/zones/home/off`, and prints the status and, after up to 40 s of polling (idle lights are read every 30 s), how many lights read `power: false`;
  - `POST /api/running/stop-all` and prints the status.

- [ ] **Step 2: Run it in a loopback-only namespace**, with a fresh database:

```bash
unshare -rn sh -c '
  ip link set lo up
  uv run --offline python "$0/driver.py" --dj-listen 127.0.0.1:0 --web --web-host 127.0.0.1 --web-port 8098 --config "$0/config.toml" --db "$0/state.db" > "$0/app.log" 2>&1 &
  app=$!
  uv run --offline python "$0/probe.py"
  kill -TERM $app; wait $app
' "$D"
grep -c Traceback "$D/app.log"
```

Expected:
  - every light listed and placed;
  - `sun` present with keys `elevation, azimuth, sunrise, sunset, path`;
  - the three looks listed with looks.json's category, scope and thumbnail; Goodnight's `needs` is `[]`;
  - Home sunset 200 and `running`, with `waitingFor` empty;
  - Wisp on a room 400;
  - the overlay 201 with 1 overlay, then 0;
  - Goodnight 200 and `running`. After its walk most lights read off and have `status: switched-off`, and the night room's read on (both counts above 0). After Off none reads off: the simulated lights were captured on, and Off restores their power (Off's status 204);
  - Stop all 204;
  - `Traceback` count 0.

If a step differs, fix it in the task that owns it and run again. Delete `$D` afterwards (`rm -r "$D"`).

### Task 12: CLAUDE.md and README

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1:** Run the `claude-md-management:claude-md-improver` skill on the repo's `CLAUDE.md`, then `/claude-md-management:revise-claude-md` with this branch's learnings. Check that the file now says these, and change what it says otherwise:
  - The Architecture entries for `home/sun.py`, the new effects, `zones/overlay.py` and `scheduling/route.py`.
  - `effects/context.py`: the signals, `sun.elevation` and `sun.azimuth` beside `beat.dj` and `time.evening`, and `elapsed_s`.
  - `effects/ledset.py`: `Space.north_offset_deg`.
  - `zones/`: overlays, `check_scope`, the sun in `RuntimeEnv`, and lights out (`out_after`, `_is_out`, the lights-out timer, `_restore_on`); `devices/adapter.py`: `switches_power`; `effects/field.py`: `lights_out()`.
  - `web/`: `POST`/`DELETE /running/overlay` and `GET /inputs`'s sun.
  - Key Design Decisions: Home looks on Whole home only; an overlay screens over streaming lights only; one at a time, not kept; bedtime is a start of Goodnight, which switches off each room it walks off (ruling 19).
  - Testing: `tests/sun_fakes.py`; `sun=`, `sleep=` and `monotonic=` on the zone fixtures; `FakeLight(switches_power=)`; `OutField` in `tests/runtime_fakes.py`.
  - Gotchas: replace the F4 ruling 3 line ("the engine refuses a preview or a start of a whole-home look until M6") with the engine allowing them on Whole home only. Add: the sun follows whatever location is stored; Goodnight switches off the lights of the rooms it walks off, and Off restores them as captured, power included, except a Govee lamp that HA keeps deaf, which has no capture and stays off until a look switches it on; a restart mid-walk leaves the lights the walk hadn't reached as they were; an overlay isn't kept across a restart.
- [ ] **Step 2:** In `README.md`, add one feature line: Home looks on the whole home, the sun, and overlays.
- [ ] **Step 3:** Check for promises the branch has kept or broken: `git grep -n "arrive in M6\|until M6\|M6's sun\|overlays arrive" -- src tests CLAUDE.md README.md docs/superpowers/specs`. Expected: nothing, or only what the specs say of later milestones.
- [ ] **Step 4:** Offer the controller one line for the memory file `project_dj_ledfx_redesign.md` ("M6 #<PR> open: Home looks, sun, overlays, Goodnight's lights out; built on the owner's answers of 11-11"), to write only on their go.
- [ ] **Step 5: Gate and commit:** `git add CLAUDE.md README.md && git commit -m "M6: CLAUDE.md and README for Home looks, the sun and overlays"`.

### Task 13: Catch up with master, check, and open the PR

- [ ] **Step 1: Rebase:** `git fetch origin && git rebase origin/master`. Resolve conflicts in `web/src/api/contract.ts`, `contract.test.ts` and `CLAUDE.md` by keeping both sides. Then run `(cd web && npm run api:types)` and `git status --short web/src/api/generated` (expected: empty, or commit the regenerated files with "M6: regenerate the API types after the rebase").
- [ ] **Step 2: Check F5's side.**
  - If F5 has merged, its Looks library lists every built-in from `GET /api/looks`: check that its tests or mocks don't pin a list of looks that leaves out `homesunset`, `wisp` or `goodnight`.
  - Check that nothing it added hand-writes `SunInput` or `Overlay` (`git grep -n "interface SunInput\|interface Overlay" web/src`; expected: nothing).
  - F5's "Only ready now" can now judge Home sunset from `inputs.sun != null`; tell the controller if F5 assumed otherwise.
- [ ] **Step 3: Every gate:**

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ 2>&1 | tail -1      # no worse than /tmp/m6-baseline-mypy.txt
uv run pytest -q 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm run api:check && npx tsc -b && npm test && npm run lint && npm run build)
```

Expected: all clean and green, perf under budget.

- [ ] **Step 4: The privacy grep** over the branch's diff. It prints counts only; expected 0 each:

```bash
git diff origin/master...HEAD > /tmp/m6-diff.txt
uv run python - <<'EOF'
import json, re
from pathlib import Path
from dj_ledfx.home.seed import OWNER_ROOM_NAMES, seed_lights
diff = Path("/tmp/m6-diff.txt").read_text().lower()
added = "\n".join(l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
home = json.loads(Path("docs/design/web-app/home.json").read_text())
rooms = {r["name"].lower() for r in home.get("rooms", [])} | {n.lower() for n in OWNER_ROOM_NAMES.values()}
lights = {s.name.lower() for s in seed_lights()}
words = lambda names: sum(len(re.findall(rf"\b{re.escape(n)}\b", added)) for n in names if n)
print("room names:", words(rooms))
print("light names:", words(lights))
print("lat/lon literals:", len(re.findall(r"\b(lat|lon|latitude|longitude)\b\s*[=:]\s*-?\d", added)))
print("ip addresses:", len([m for m in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", added) if m not in ("127.0.0.1", "0.0.0.0")]))
EOF
rm /tmp/m6-diff.txt
```

A hit means a name or a number got into the diff: remove it and run the grep again. The sun's made-up test places are passed as `(0.0, 0.0)`-style tuples, not `lat=` literals. If one is written as a keyword, check it's one of the three made-up places and say so in the PR.

- [ ] **Step 5: Push and open the PR:** `git push -u origin feature/m6-whole-home`, then `gh pr create --base master --title "M6: Whole home — Home looks, the sun, overlays" --body-file <file>`. The body has these sections:
  - **Summary:** what M6 does, in four bullets.
  - **For the owner:** the answers of 2026-11-11 (rulings 8, 11 and 15) as built; ruling 19 (lights out) in full, since it decides what Off, a resume and preview only do with lights Goodnight switched off; ruling 10 (the screen mix) as a decision to check; then the other rulings in one line each.
  - **Deferred:** the cut from Global Constraints.
  - **Test plan:** the gates and the dry run's results, counts only.
  - **After you merge and deploy (each step only on your "go")**, against the deployed app's REST API on 127.0.0.1:8080:
    0. A caveat: Home Assistant holds UDP 4002, so the app can't capture a Govee lamp. Off leaves one as the look left it, and after Goodnight that's off, until a look switches it on (step 5) or Home Assistant does.
    1. Start Home sunset on Whole home, and check `waitingFor` is empty and the warmth sits on the sun's side.
    2. Start Wisp on Whole home.
    3. Start Sunset on one room, then play Wisp over everything for 30 s (`POST /api/running/overlay`), and watch it ease in, play and ease out.
    4. Start Goodnight on Whole home and watch the walk (60 s). The rooms go dark farthest first from the night room, and each room's lights switch off about 3 s after it's dark: each such light's `status` in `GET /api/lights` turns `switched-off`, a LIFX one's `power` reads `false` within 5 s, and a Govee one's `power` stays unknown (step 0), so look at the lamp. The night room stays on its night light.
    5. Start Home sunset on Whole home: every light Goodnight switched off comes back on, the Govee lamps included, and plays it.
    6. Start Goodnight again, and when its walk is done, Off on Whole home: the LIFX lights come back as they were captured, power included, and the Govee lamps stay off (step 0).

    The location is the one already stored. Nothing in these steps reads or prints it.

  The body ends with the line "🤖 Generated with [Claude Code](https://claude.com/claude-code)".
- [ ] **Step 6:** Run the final review the owner's method calls for, fix every finding (Minor ones included), push, and tell the controller the PR's number. Never merge: the owner merges, and deploys at their word.

---

## Hand-off

- **To the owner:** the PR, built on their answers of 2026-11-11, with ruling 19 and decision 10 to check, and the real-light checklist, each step only on their go after they merge and deploy.
- **To M7:**
  - `ZoneManager.start_overlay(look, duration_s, trigger)` is what the doorbell trigger and Home Assistant's "play a timed overlay" call. Doorbell ripple's ring is an `fx` key of its own, and it needs ruling 11 settled.
  - Bedtime calls `start(HOME_ZONE_ID, goodnight)`, which switches off the rooms it walks off (rulings 8 and 19).
  - `sun.elevation` and `sun.azimuth` join the signals catalogue.
  - The location from Home Assistant's config would feed `Sun` and `Evening`'s callable.
  - Goodnight already lists Home Assistant in `uses`.
- **To the web app:** `GET /inputs`'s `sun` and the generated `SunInput`; `Running.overlays` and the `running` channel for Live's overlay card (§8.3); `POST`/`DELETE /running/overlay` for its "Stop ripple".
- **Deferred:** sun shafts (window heights first), overlay fx, overlays reaching idle lights, overlays kept across restarts, an overlay's own brightness or blend, a mark of the lights a walk switched off kept across a restart.

## Coverage

| Spec item | Task |
|---|---|
| §2 M6: whole-home zone | 1 (Home looks on it), 11 |
| §2 M6: overlays; §4.3's overlay; §7.4's timed overlay | 9, 10 |
| §2 M6: sun position; §7.3 Sun | 2, 3, 4 |
| §2 M6: bedtime flow (the owner's answer, 2026-11-11: the walked-off lights switched off) | 7, 8, 11 (rulings 8, 9, 19) |
| §2 M6: Home sunset, Wisp, Goodnight; §5.2 built-ins keep looks.json's metadata | 5, 6, 7 |
| §5.2 `needs` waits dark; `scope: whole-home` pins Home looks | 3, 1 |
| §6.4 sharing policy: capture, restore, power | 8 (ruling 19) |
| §4.1 budget; §9 performance | 3, 5, 6, 7, 9 (perf) |
| §8 a look that fails | 9 (the overlay is its own runtime) |
| Web §12.2 `Overlay`; §12.3 `/running`, `/running/overlay`; §12.4 `running` | 10 |
| Web §12.3 `/inputs` sun; §12.4 `inputs`, "The `sun` input" | 4 |
| Web §12.4 sun shafts; M8's hand-off: sun shafts after M6's sun | deferred (ruling 15, the owner's answer, 2026-11-11) |
