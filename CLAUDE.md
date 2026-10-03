# dj-ledfx

Beat-synced LED effect engine driven by Pro DJ Link network data with per-device latency compensation.

## Superpowers Skill Guidelines

- Use opus with max effort from brainstorming and planning.
- Use /executing-plans skill for executing the plan.
- Use sonnet or opus for implementing the plan.
- Use opus for reviewing and simplification stages.
- Use haiku for committing.
- Prefer latest internet grounded knowledge over training knowledge.
- Use context7 to check latest docs and for external dependencies.
- Add claude md skill as a task to improve and revise claude context, memories etc.
- Finally create a PR with the changes.
- Don't put code-architect reviews or /simplify in plans as tasks. Run them once, on the plan's PR after it opens: a @feature-dev:code-architect review and /simplify. Fix every issue they raise and push the fixes to the PR.

## Redesign in Progress

- Engine: `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`, milestones M1–M8, one plan each.
- Web app: `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md` (the Claude Design handoff), milestones F0–F11, built in `web/` beside `frontend/` and served at `/next` until the F11 cut-over. The engine spec's §10 says how the two tracks meet.

## Web App Design

The Claude Design handoff is the only source of design truth. Don't work from memory, a summary or an earlier conversation.

- Behaviour, structure, data contract and copy: the web app spec. Look and layout: the reference renders in `docs/design/web-app/reference/`.
- The renders are not in git. They live in the main checkout, `/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/`; read them there from a worktree. If they're missing, extract them from `.superpowers/design-handoff/2026-09-23-dj-ledfx-web-handoff.zip` in the main checkout.
- `docs/design/web-app/HANDOFF.sha256` pins every design file, renders included. Check with `sha256sum -c --ignore-missing HANDOFF.sha256` in that directory.
- Each render's HTML sits beside its PNG (`Main.html` beside `Main.png`). Where the app and a render differ, its markup settles what the picture can't: a font run, a colour, what a state leaves out.
- Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are: import them, or copy them byte for byte with a test that fails when the copy differs. Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file.
- Before each web app task, re-read the spec sections and look at the renders that the task names.
- A new handoff replaces `docs/design/web-app/` and the web app spec wholesale. Don't hand-edit the design files.


## Commands

```bash
uv sync                          # Install dependencies
uv sync --extra web              # Install with web UI extras
uv run -m dj_ledfx              # Run the app
uv run -m dj_ledfx --demo       # Run with no Pro DJ Link listener: the internal clock keeps the tempo (no DJ hardware)
uv run -m dj_ledfx --demo --bpm 124  # Set the internal clock's BPM at start; it's saved like a BPM set in the app
uv run -m dj_ledfx --demo --web # Run with web UI (requires: uv sync --extra web)
uv run -m dj_ledfx --demo --web dev  # Run with hot-reload dev server (frontend + backend)
uv run -m dj_ledfx --dj-listen 127.0.0.1:0 --web --web-port 8099  # Hear Pro DJ Link on any free loopback port (GET /api/inputs names it) beside the deployed app
uv run pytest                    # Run tests
uv run pytest -x -v              # Run tests, stop on first failure
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check
cd frontend && npm run build     # Build frontend static assets
cd frontend && npx tsc --noEmit -p tsconfig.app.json  # TypeScript type check (plain `npx tsc --noEmit` checks nothing: the root tsconfig only holds references)
cd frontend && npm run dev       # Frontend dev server (proxies to :8080)
uv run python scripts/lifx_record_fixtures.py  # Record the LAN's LIFX replies into tests/fixtures/lifx/recorded/ (read-only; runs beside the container)
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments N --pattern whole --restore-colour RRGGBB --restore-power on  # Play a razer pattern (whole, ends, stripes, chase, gaps or status) on one Govee lamp to judge by eye, then put the lamp back as the two --restore- options say; only status binds UDP 4002, so it runs only while the deployed app is stopped
docker compose up -d --build     # Deploy: from the main checkout ~/code/private/dj-ledfx, after a merge (see Deployment)
docker compose logs app          # The deployed app's log
cd web && npm install            # New web app (F0–F11): install dependencies
cd web && npm run dev            # Dev server at http://localhost:5174/next/ (proxies /api and /ws to :8080); add ?scenario=<name> to run on the mocks (?still holds the beat and the frames, ?protocol=1 speaks as engine M1)
cd web && npm run build          # Type-check and build web/dist; fails if MSW got in or the JS, three.js's chunk aside, passes §14's budget; FastAPI serves it at /next
cd web && npm run build:mock     # Build web/dist-mock: the app on its mocks (the hero unless ?scenario=), which e2e serves
cd web && npm run api:types      # Regenerate web/src/api/generated/ from the backend's code, after any API change
cd web && npm run api:check      # Fail if the generated types aren't the backend's; `-- --url http://127.0.0.1:8080` also compares a running server (GET only)
cd web && npm run design:numbers # Regenerate src/stage/design-numbers.ts and src/pages/live-numbers.ts from the spec and the pinned renders (read from the main checkout); their node test fails while either is stale
cd web && npm test               # Vitest: unit and component tests
cd web && npm run lint           # ESLint (npx tsc -b type-checks)
cd web && npx playwright install chromium  # Once per machine
cd web && npm run e2e            # Playwright: screenshots, axe on every route, keyboard, reflow
cd web && npm run e2e:perf       # Playwright on this machine's GPU: the stage's frame rate and idle main thread against §14 (e2e's ports: never beside npm run e2e)
```

## Deployment

- The app runs on this host as `dj-ledfx-app-1` (compose project `dj-ledfx`, from the committed `Dockerfile` and `docker-compose.yml`), with host networking: it serves 8080 and binds Pro DJ Link's 50001/udp itself. No `--demo`.
- After merging a deploy change: `docker compose up -d --build` in the main checkout `~/code/private/dj-ledfx`. The container mounts that checkout's `config.toml`; `state.db` stays in the `dj-ledfx_state` volume and zones resume.
- The app runs as uid 10001 (`dj-ledfx`). `docker/entrypoint.sh` starts as root only to hand `/app/state` to that user (a volume from before it existed is root-owned), then drops to it with `setpriv`. The image's HEALTHCHECK polls `/api/running` on 8080.
- UFW governs 8080: the LAN is allowed, and `tailscale0` has its own 8080 rule. Ask the owner before changing UFW.
- Check it: `docker compose ps`, `curl -s http://127.0.0.1:8080/api/running`, `/api/lights`, `/api/attention`.

## Architecture

src/dj_ledfx/ layout:
- `prodjlink/` — Pro DJ Link UDP protocol (passive listener on port 50001 of the config's `network.interface`, `auto` being every interface, or on `--dj-listen HOST:PORT`). `hear_pro_dj_link()` returns the listener and its `Listening` (where it listens, for `GET /inputs`); a port it can't bind logs a WARNING and leaves the tempo to the internal clock, and `prodjlink.state` reads `disconnected`
- `tempo/` — the tempo clock, always running (engine spec §7.2): `model` (sources, locks, the limits and `check_bpm`, `TempoSample`, `DeckView`, `TempoSettings`, the events `TempoChanged` and `DecksChanged`), `timeline` (`Timeline`, a straight line of beats, `beat_and_bar` splitting a position into beat and bar, and `nearest_beat`), `tap` (`TapTempo`: runs of taps on client or arrival times), `decks` (`DeckTracker`: the players the beat packets tell of), `clock` (`TempoClock`: the sources, the lock and the controls, Pro DJ Link, `run()`, saving and reloading) and `store` (`TempoStore`: section `tempo` of `state.db`'s config table)
- `effects/` — Effect ABC (`base.py`, with today's 1D `StripEffect`) + the 60fps engine, which hosts each running zone's runtime (and the preview's) and renders it ahead into that runtime's ring buffer
- `effects/context.py` — `RenderContext` (beat, time, signals) that field effects render from; `render_context(clock, t, dt)` reads the tempo clock's position at the frame's target time (`position_at`, no whole `TempoSample`), so `beat_index` and `bar_index` are real counts; its one signal before M6, `beat.dj` (`DJ_BEAT`), is 1 while a DJ's deck drives the clock, and `to_beat_context` hands it to 1D effects as `dj`, with the beat count (`beat_index`); both contexts' `beats` is the count and the phase, where the music is
- `effects/ledset.py` — `LedSet`: a zone's LEDs where their placements put them on the home map, in order, carrying the zone's `Space` (rooms, anchors, ceiling; equal by value), with its `bounds` and `centre` cached; `subset()` gives some devices' LEDs with the zone's positions and device indices (a firmware layer's copy is drawn on its own lights)
- `effects/ring_buffer.py` — `RingBuffer`: a running zone's frames, rendered ahead. `colors_at(t, start, stop)` is the one read, the send loops' and the web app's feed's alike: LEDs start..stop at a moment, blended (easing's `lerp`) from the two frames `find_around` gives, found by their times; on a frame or outside the frames it hands out that frame's own colours
- `effects/field.py`, `effects/strip_adapter.py` — `FieldEffect`, and `ParamField` (each setting and its default stated once in `parameters()`, filled in by `__init__(**settings)`; the settings in one dict; `_prepare()` rebuilds what's derived from them, the float palette included, and `_per_leds()` keeps per-LED work until the LEDs or a setting change; `_rng(k)`, draw k's seeded generator, beside `reseed()`; `level_param()` and `anchor_param()` in `params.py`); `StripAdapter` plays a 1D `StripEffect` by projecting each LED's position onto an axis, linear or radial (`spatial/mapping.py`), or along the LEDs in zone order
- `effects/blend.py` (`blend_into()`: the five blend modes), `effects/field_tools.py` (anchors, distances, `bearing()` in turns, height, `band()`, the one Gaussian falloff, and smoothstep on easing's cubic), `effects/noise.py` (seeded 3D value noise, each axis hashed once; `fbm3`)
- `effects/{sunset_gradient,aurora_curtains,lava_plasma,color_carousel,ripples,focus_field}.py` — the six showcase looks' field effects
- `effects/{shockwave_shell,lighthouse_beam,scanner_plane,checker_cubes,speaker_waves}.py` — the field effects of engine M3's four tempo looks
- `effects/firmware.py`, `firmware_lifx.py`, `firmware_openrgb.py` — effects the light runs itself: LIFX Flame and Morph (matrix), Move (multizone), waveforms (bulbs), OpenRGB hardware modes; lights that can't run one get its streamed `emulate()`; `require_adapter()` turns the wrong kind of light into `FirmwareRejected`
- `effects/color.py` — Color math: hex/RGB conversion, and one HSV formula and one palette interpolation, in floats (`hsv_float`, `palette_float`, `palette_at`); `hsv_to_rgb_array` and `palette_lerp` are their 8-bit forms, and `palette_loop` is `palette_lerp` round a loop, the last colour blending back into the first
- `effects/easing.py` — Easing functions: lerp (of floats, or of float32 colours for the ring's blend), ease_in/out, sine_ease, raised_cosine
- `effects/energy.py` — BPM→energy mapping (0-1 linear between 100-150 BPM), for amounts, never speeds
- `scheduling/` — LookaheadScheduler: per-device send loops with FrameSlot depth-1 slots, written from the distributor's tick before the device is due (`due_at`), each device at its own rate (its `max_fps`: its adapter's `stream_fps`, or the engine's rate when that's None), a frame equal to the last one sent (`LastSend`: its adapter, bytes and time) skipped for up to `KEEPALIVE_S` (a route set, a new adapter or a drop-out sends the next frame whatever it is), and `note_send` after each send; it makes no frame snapshots for the web app and never reads a route that doesn't stream
- `scheduling/route.py` — `DeviceRoute`: a light's slice of its zone's frames. It holds the runtime and reads the runtime's ring and LED set at each send, so a zone that rebuilds its LEDs needs no re-route; `colors_at()` reads its slice from the ring at the light's moment (`RingBuffer.colors_at`) and converts it to 8 bits once, at send, through `to_device_colors(colors, count, scale)`, whose one multiply carries the zone's brightness
- `metrics.py` — Contextmanager-based timing metrics for performance measurement
- `devices/lights.py` — `LightIndex`: the PC's OpenRGB devices as one light with parts (`light_id_of`, `expand`/`collapse` between light ids and device ids). Every `LightEntry` has parts: a plain light is one part, itself; `part_slices()` says where each part's LEDs sit
- `devices/` — DeviceAdapter ABC (read/set power and colour, capture/restore, `last_heard`: when the light last answered anything, None by default; `stream_fps`: the rate it was built with under its kind's `stream_fps_cap`, None for the engine's; `display_ms`: how long after a frame lands it shows it, 0 by default) + OpenRGB adapter (asyncio.to_thread wrapped) + device-type heuristics
- `devices/capabilities.py` — `DeviceCapabilities`: what a light can do (colour, matrix, multizone, effects); `LightReading` (`UNKNOWN`: it answered but can't say) and `try_read()` (None: no answer)
- `devices/backend.py` — DeviceBackend ABC for protocol-level adapters: `discover()` gets the known devices' rows (`known`), and `rebuild()` sets an online light up again from its row with no network; `DiscoveredDevice.on_accepted` hands the tracker the light's round trips once the orchestrator takes the device in, and its `max_fps` is the adapter's `stream_fps`; `configured_fps(config, max_fps)`, the engine's rate or a kind's `max_fps` if lower, is the rate each backend builds its adapters with
- `devices/govee/` — Govee WiFi LED protocol: `GoveeRazerAdapter` (`razer.py`: razer frames, one colour per segment, to UDP 4003, no replies, and razer's arming) or `GoveeColourAdapter` (`colour.py`: one `colorwc` colour, the frame's average, on any number of segments, capped at `GOVEE_COLOUR_FPS` by its own `stream_fps_cap`), chosen on the plan's `razer`; `adapter_base.py` holds what both share (reads, capture, a restore that sends razer-off first, where the segments sit, and the stored device types `govee_segment` and `govee_solid`); `output.py` (`GoveeOutput`, a lamp's own output in its device row's `extra`; `LampPlan`, `lamp_plan()`, `planned()` from a row; `LampOutputReport` and `lamp_report()`, how a lamp plays: as its live adapter does while it's online); the SKU table with each model's `razer`, `form` and `segments_from_top`; the transport, which times each status query to its reply and hands the round trip to the lamp's tracker (there's no probe loop). A status read asks twice (`STATUS_TRIES`), as LIFX reads do; a lamp silent to both raises `NoAnswer`
- `devices/lifx/` — LIFX LAN protocol (bulb/strip/tile discovery, packet encoding, transport); `base.py` shared adapter, `transport.py` `ask` (retries), `answer` (the reply's type checked and parsed by `parsed()`: None when the light can't say, `NoAnswer` when it's silent; GetVersion and the setup queries use it) and `query` (None either way, for the adapters' reads), and the echo probes, sent only to a light that streams (`register_device(..., streaming=)`), `products.py` `lifx_capabilities()` from the vendored `data/products.json`, and `matrix_form()`: a candle's or a tube's matrix wraps round a cylinder (the tile-chain adapter's `MatrixGeometry.form`), the rest are flat. Streamed frames fade over the gap to the next at the rate the adapter streams at (`stream_fade_ms` of its `stream_fps`), and it shows a frame half-way through (`display_ms`); strips and matrices take at most `LIFX_STRIP_FPS` and `LIFX_MATRIX_FPS` (20), and a matrix's `display_ms` adds `MATRIX_DISPLAY_MS`. Discovery skips a known online light before `GetVersion`, and a light silent to `GetVersion` or a setup query gives no record that scan
- `looks/` — the look model, the built-ins (the handoff's M2 and M3 looks and the Firmware showcase, in looks.json's order from the vendored `data/looks.json`, then the six classics; the `speakers` look runs on the beat until M7, `NEEDS_UNTIL_M7`), and the store (saved looks, stars)
- `looks/selectors.py` — which lights a layer picks: light ids, or `type:<word>`. The look model parses a layer's `lights` setting into `Layer.lights` and writes it back as a list
- `zones/` — `model` (every light, rooms, groups), `store`, `runtime` (a running look's layer stack and ring buffer, rendered at most `HORIZON_CAP_S` ahead and before brightness), `manager` (take-over, capture/restore, brightness, Stop all, resume, preview-only, the sharing policy, "Start again"), `lights` (LightMonitor: status and the 5 s/30 s polls), `attention` (the feed)
- `zones/home_view.py` (`HomeView`, what the zone manager asks of the map; `MapZones`: the whole home, rooms and sub-zones as zones), `zones/preview.py` (`PreviewManager`: one preview at a time), `zones/frames.py` (`Watchers.watching(stream)`: who watches which stream; `FrameFeed(live, previews)`: the web app's frames, read from the rings at now as the lights' are (`RingBuffer.colors_at`), each runtime's colours converted once, scaled by its zone's brightness, and only for the devices asked for)
- `home/` — the home map: `model` (`Home`, rooms, sub-zones, anchors, walls; home.json's shape), `geometry`, `shapes` (the five light shapes, `Placement`, `led_positions()`), `seed` (the vendored `data/home.json`, a byte copy with a test, and the owner's room names over it), `store` (`state.db`; a stored map it can't read is set aside in `home_map_unreadable`, which backups carry, and the seed is used), `guess` (placement guessing, each light in its form, which one classifier `_form()` decides for both `placed_in_form()` and `in_form()`; the old scene placements moved on), `map` (`HomeMap`: queries, each target's spot and LEDs kept until they change; edits through `_edit()`; `Space`; change listeners; `refit(device_id)` fits the placement of the light that came online to its form, a seed's or a guess's but never the owner's, and `main.py` spawns it for each light that comes online; `guess()` and `refit()` save through `_put()`, one transaction)
- `latency/` — ProbeStrategy protocol + StaticLatency, EMA (three outliers in a row are a new level), WindowedMean and WindowedMedian (the default) strategies, the windowed two on one `WindowedLatency` base that works its statistic out as a sample lands, over a window of `LATENCY_WINDOW`; `STRATEGIES` maps each name a config can use to its factory, which `make_strategy()` looks up. `LatencyTracker` counts a round trip (a LIFX echo probe's, a Govee status read's), halved, only within `STREAMING_WINDOW_S` of a frame sent (`note_send`, `update_rtt`; `streaming` says it's within that window), and adds the device's `display_ms`; `measured` says one has landed since the last reset (never for a static strategy), and the API's `estimated` is its opposite; `tracker_for(cfg, seed_ms=, display_ms=)` builds one from a kind of device's config, for the OpenRGB, LIFX and Govee backends alike
- `config.py` — Nested dataclass config (EngineConfig, EffectConfig, NetworkConfig, WebConfig, DevicesConfig) with load/save via tomllib/tomli_w; the rate constants (`LIFX_STRIP_FPS`, `LIFX_MATRIX_FPS`, `GOVEE_RAZER_FPS`, `GOVEE_COLOUR_FPS`), and `LATENCY_WINDOW`, re-exported from `latency/strategies.py`
- `effects/params.py` — EffectParam descriptor for runtime introspection
- `effects/registry.py` — Effect auto-registry via __init_subclass__, get_effect_classes/schemas
- `effects/presets.py` — PresetStore with TOML persistence
- `devices/manager.py` — DeviceManager: the managed devices (online and ghosts), indexed by stable id (`get_by_stable_id` is a dict lookup, rebuilt on every change) and by light (`lights`, the `LightIndex`, rebuilt beside it), promote/demote (`replace_adapter()` swaps in a set-up device; a live adapter replaced is disconnected), groups
- `web/` — FastAPI app factory, REST routers (effects, devices, config, scene, looks, zones, lights, attention, home, preview, inputs), WebSocket hub, Pydantic schemas
- `web/router_inputs.py` — `GET /inputs` (the tempo, and Pro DJ Link with its decks) and the three tempo controls: `PUT /inputs/tempo`, `POST /inputs/tempo/tap`, `POST /inputs/tempo/nudge`
- `web/router_lights.py` — the lights, and `GET` and `PUT /lights/{id}/output`, a Govee lamp's own output, asked of the discovery orchestrator (outside the web spec's contract until a handoff adds it)
- `web/frames.py` — frame encoders v1 and v2; `light_frames()` assembles each light's bytes (the PC's parts in part order, black where a part has nothing)
- `web/contract.py` — the web spec's API models (camelCase) and the converters from engine types; `web/errors.py` — `answers()` maps engine errors to HTTP, and `unprocessable` is the 422 handler, which answers a NaN as text
- `web/ws.py` — WebSocket hub: binary LED frames from `FrameFeed`, v1 by default and v2 after `subscribe_frames` with `"protocol": 2` (streams `live`/`preview`, optional `lights`); the beat at the client's rate, web spec §12.4's fields plus the old UI's (`is_playing`, `beat_pos`, `deck_number`, `deck_name`) until F11; stats and status channels; pushed `running`, `lights`, `attention` and `decks` snapshots on change, and `inputs` on change and once a second (one heartbeat in `event_broadcast` serves every tab, and none follows a push within the second); the `tap` command takes `client_time`; a command it can't use (not a JSON object, a non-finite `fps`) gets an error reply and the session goes on; `transport` carries preview-only (`simulating` while on, `playing` otherwise); `close_all()` ends sessions with 1001 at shutdown
- `web/state.py` — WS subscription state and the `app.state` getters (`get_zones`, `get_looks`, `get_discovery`, ...); the discovery orchestrator is in `app.state`, so `POST /devices/scan` runs a real scan, and so does the old UI's `POST /devices/discover`, which names the devices it brought online
- `web/router_scene.py` — Scene REST endpoints for the old scene page until F11 (placement CRUD, mapping config)
- `spatial/mapping.py` — mapping_from_config() shared factory for LinearMapping/RadialMapping
- `spatial/compositor.py` — Spatial compositor for multi-device LED frame distribution (the old scene page's, until F11)
- `spatial/geometry.py` — 3D geometry utilities for spatial calculations
- `spatial/scene.py` — SceneModel: device placements, spatial configuration
- `types.py` — Canonical location for all shared types (RGB, DeviceInfo, RenderedFrame, DeviceStats), and `clamp01`
- `timing.py` — `utcnow()`, `as_utc()`, `utc_text()` and `parse_utc()` (a saved time as UTC text and back, for the zone and tempo stores), the one-second rate window (`RATE_WINDOW_S`, `trim_window`) and `paced()`, the fixed-period loop the engine and the scheduler run
- `events.py` — Typed callback event bus (sync, non-blocking callbacks only) + device events; the zones' events (`ZonesChanged`, `PreviewOnlyChanged`, `LightsChanged`, `AttentionChanged`) live in `zones/model.py`, the tempo's (`TempoChanged`, `DecksChanged`) in `tempo/model.py`
- `persistence/` — SQLite-backed state persistence (state_db.py, toml_io.py, debounced_writer.py, migrations/); `StateDB.write_many` runs statements as one transaction, and `has_mark`/`mark_statement` mark run-once steps
- `devices/discovery.py` — DiscoveryOrchestrator: multi-wave scanning, fast reconnect, ghost promote/demote (one `_promote()`); a Govee lamp's output: `set_output()` keeps it in the row and plays it at once, `output_of()` says how the lamp plays, `apply_outputs()` plays what restored rows hold; scans and output changes take turns (`_scan_lock`: a Govee scan has one reply handler)
- `devices/ghost.py` — GhostAdapter: placeholder for offline devices (is_connected=False, send_frame no-op)
- `status.py` — SystemStatus health tracking
- `main.py` — Application coordinator (startup/shutdown orchestration; serves the web app with granian's embedded server, on the app's own event loop, and stops it through `_WebServer.stop()`: close the websockets, then granian's `Server.stop()`; `_spawn()` runs the event handlers' work as background tasks and logs one that fails)

frontend/ (Vite + React 19 + TypeScript + shadcn/ui + Tailwind CSS v4):
- `src/lib/ws-client.ts` — Multiplexed WS client with reconnection
- `src/lib/api-client.ts` — Typed REST client
- `src/hooks/` — React hooks for beat, effects, devices, scene and zones state
- `src/pages/` — Views: Live Performance, Devices, Config, Scene (3D editor)
- `src/components/` — look-picker (zone, look, Start, Off, Preview only), tempo-section, effect-deck, device-monitor (Live page); scene/ (3D editor)
- `src/components/scene/` — R3F scene editor: viewport, device meshes, mapping helpers, bounds box, panels

web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4 + Base UI; served at /next until F11):
- `src/styles/tokens.css`, `src/design/icons.ts` — byte copies of `docs/design/web-app/`, changed only by `cp` (keep search-and-replace away from them); `src/design/payload.node.test.ts` fails if either drifts
- `src/design/` — the spec's §6.1 primitives and `Icon`, and the page's one status region (`Announcer`, `useAnnounce()`)
- `src/chrome/` — the §6.2 always-within-reach cluster; `live.tsx` puts each part on its own slice of the live store (`hooks.ts`) and draws nothing before its data; `state.ts` holds the chrome's data types and `HERO_CHROME`, which the specimen draws and which supplies the server name and the sunset until F6; preview only is the server's `transport`, read from the live store
- `src/api/` — the data layer (§12); components never call `fetch` or touch the socket. `generated/` (the backend's OpenAPI schema and openapi-typescript's types, committed), `contract.ts` (generated aliases, and the pending types later engine milestones serve), `rest.ts` (`api.*`), `live-client.ts` (the one socket: backoff, silence watchdog, resync, frame protocol handshake), `live-store.ts` (zustand; `useLive(selector)`), `frames.ts` (`FrameStore`: reused typed arrays React never watches; `onNextFrame()` wakes whoever waits for the next frame), `beat.ts` (`BeatClock`), `queries.ts` (TanStack Query), `live.ts` (the app's singletons; `startDataLayer()`, and `resetDataLayer()` for tests)
- `src/api/mocks/` — `MockServer` plays a §12.5 scenario (REST, channels, animated frames) from byte copies of `home.json` and `looks.json`; MSW puts it behind fetch and WebSocket in dev (`?scenario=`) and in `dist-mock`; tests reach it through `inMemorySockets()`
- `scripts/dump_openapi.py` prints the backend's OpenAPI schema from the code, with no server
- `scripts/design-numbers.ts` (with `design-extract.ts`, whose `readHandoff()` reads the handoff and checks the renders' pins) writes `src/stage/design-numbers.ts`: `SPEC` read from the spec's own sentences, `RENDER` from the pinned `Main.html` and `State-Firmware.html`, `TOKENS` (the colours) from tokens.css; and `src/pages/live-numbers.ts`: `LIVE_LAYOUT`, the two layout numbers Live's first load needs, so it doesn't carry the stage's
- `scripts/chunks.ts` names the bundle's chunks (`THREE_CHUNK`) for vite.config.ts, which makes them, and `scripts/check-dist.ts`, which leaves three.js's out of §14's budget
- `src/stage/` — the stage (§7), `live` and `frozen` modes. Pure modules turn the API's data into what is drawn (`plan`, `bodies`, `show`, `camera`, `view-memory`, `home-geometry`, `room-mask`, `labels`, `picking`, `marks`, `sun`, `tooltip`), every number from `design-numbers.ts` and every colour from its `TOKENS` (tokens.css's) through `palette.ts`. `behaviour.ts`'s `stageBehaviour()` is §7.6's modes table: `StageView` asks it once (mode, variant, reduced motion, the Labels switch) and hands down what each part does (interactive, overlays, labels, the sun's label, greyed, `cadenceMs`); nothing else checks the mode or the variant. `FrameWriter` writes the frame store's arrays into the instances in place, and says whether anything changed; `cadence.ts`'s `useCadence` is the stage's one draw tick (the canvas draws on it, and the light tooltip follows it through `onStageDraw()`); `stage-canvas.tsx` mounts React Three Fiber's `createRoot` on its own canvas; `scene/` is three.js under it (`HomeScene`, `LightMeshes`); `overlays/` the SVG layer and the HTML overlays; `StageView` puts them together, and `stage.tsx` is Live's lazy chunk
- `src/shell/` — rail, top bar, tab bar, phone header; `AppShell` swaps desktop and phone chrome at the phone breakpoint without remounting the page
- `src/app/` — `boot.tsx` (starts the mocks when asked, then the data layer and the router; `main.tsx` only calls it), routes (§4.3), each with a `PageMeta` handle for its titles and context lines; pages sit in a pathless route whose `errorElement` keeps the chrome, and the root route's catches `AppShell` itself
- `src/pages/` — `live.tsx` (the stage, loaded lazily, with its REST data prefetched while its chunk loads, and the Running panel's place until F3), placeholders, not-found and error pages (all drawn by `EmptyState`), and the unlinked `/system` specimen
- `src/lib/` — formatters and the viewport, size, motion and clock hooks (`useIsPhone`, `useElementSize`, `useReducedMotion`, `useNow`)
- `e2e/` — Playwright specs, `helpers.ts` (`open()`, `openStage()` and the stage's canvas locator) and the committed screenshot baselines; `stage.perf.ts` runs only under `npm run e2e:perf` (`playwright.perf.config.ts`)
- `src/dj_ledfx/web/app.py` serves `web/dist` at `/next` (SPA fallback), registered before the old UI's catch-all

## Code Style

- Use `uv` for everything (never pip, never poetry)
- Use `loguru` for all logging (never stdlib logging)
- Use `ruff` for linting and formatting
- Use `mypy` strict mode for type checking
- All device I/O must be async. Synchronous libs (openrgb-python) wrapped in `asyncio.to_thread()`
- Field effects render `render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB`; today's six 1D effects keep `StripEffect.render(self, ctx: BeatContext, led_count: int)` and run through `StripAdapter`
- Firmware effects implement `supports(caps)`, `start(adapter, params)`, `stop(adapter)`, `is_running(adapter)` (None: the light can't say) and `emulate(ctx, leds)` for lights that can't run them
- New effects must: import in `effects/__init__.py` to trigger auto-registry via `__init_subclass__`
- Use shared utilities from `effects/color.py` (hex_to_rgb, rgb_to_hex, hsv_float, palette_float, palette_at, hsv_to_rgb_array, palette_lerp, palette_loop, to_float_rgb) and `effects/easing.py`
- Effect render methods are synchronous (pure numpy math, no I/O)
- `TempoClock`'s reads (`position_at(t)`, `sample_at(t)`, `sample()`, its properties) are synchronous and lock-free, called from the render loop
- `TempoClock`'s writes are `on_beat(event)` (the bus's `BeatEvent`), `set_tempo(lock, bpm)`, `tap(client_time)` and `nudge(delta)`; `settle()` lets the sources change hands (`run()` calls it every 0.25 s). A bad value raises `TempoError` (a `ValueError`, 400), a BPM sent with the Pro DJ Link or Music lock is one too, and a control while such a lock is on raises `TempoLockedError` (409)
- DeviceAdapter is ABC (abstract base class). ProbeStrategy remains Protocol. Always code to the interface.
- All components run on a single asyncio event loop — no cross-thread state access
- AppConfig uses nested dataclasses: `config.engine.fps`, `config.devices.openrgb.host` (not flat)
- EffectEngine hosts the zones' runtimes and the preview's, by identity (`add_runtime(runtime)`/`remove_runtime(runtime)`, called by the zone manager); there is no effect deck
- `frontend/` uses shadcn/ui components (based on @base-ui/react, NOT Radix — different APIs); `web/` uses @base-ui/react directly behind its own primitives in `src/design/`
- `frontend/` hooks in `src/hooks/`, one per domain (use-beat, use-devices, use-effects, use-scene, use-zones, use-ws-connection)
- WebSocket binary frame protocol v1: 2-byte name length, UTF-8 name, 4-byte sequence, then RGB bytes. v2: 1-byte stream (0x01 live, 0x02 preview), 2-byte id length LE, UTF-8 light id, 4-byte sequence LE, then RGB bytes. v1 stays until F11
- A field effect keeps its settings in one dict through `ParamField`; it's a pure function of the frame's time and the LEDs' positions, and any randomness goes through `reseed()` and `_rng(k)`

## Key Design Decisions

- Ring buffer stores FUTURE frames. High-latency devices read newer (further-future) frames.
- Each zone runtime renders at `now + horizon` into its own ring buffer: its lights' largest latency plus a rendered frame (a zone over its budget renders every few ticks), at most 120 ms (`HORIZON_CAP_S`) and within the lookahead; a light slower than that gets the newest frame and runs late by the difference. A LIFX matrix sits just past the cap (about 123 ms with its display delay, so about 3 ms late, against a measured p95 lateness of 42 ms); the cap stays, since raising it delays every look change in its zone (the light-output plan's ruling 1).
- A send loop reads its light's moment, `now + device_latency`, blended from the two frames either side of it, and the web app's feed reads now the same way. A moment that shifts by less than a frame (a latency measured again; the distributor's and the engine's ticks, each stamped with the time it ran) shifts the colours as little. Read from the nearest frame, near half-way between two frames it showed as one frame sent twice and the next skipped, which made the LIFX bulbs judder. A zone over its budget still sends each light at the light's own rate, the blend filling in between the frames it renders, so its unchanged-frame skip sheds no sends. A light past the horizon cap still gets the newest frame alone, and a flash shorter than a frame reaches a light spread over two sends at lower levels.
- A frame in a ring buffer is never changed after it's written: the runtime renders a new array every tick, the ring hands out frames and a frame's own colours, and `lerp` and `to_device_colors` make the new arrays each send uses.
- Passive Pro DJ Link mode for MVP (no virtual CDJ handshake needed for beat packets).
- One `TempoClock`, always running (spec §7.2): Pro DJ Link while a DJ plays, the music's beat from M7, then the internal clock (a BPM, taps, nudges). A takeover snaps the phase once onto the nearest beat and keeps the beat and bar counts; after that, drift is corrected softly under 5 ms and snapped at 5 ms or more. A source quiet for 2 s hands back at the last BPM and phase.
- BPM must always be pitch-adjusted: `track_bpm * (1 + pitch/100)`. A deck's `bpm` is its track's, with `pitch_percent` beside it.
- A deck plays while its beats arrive (one in the last 2 s), is cued after, and is forgotten after 30 min: passive mode has no play/pause signal. The clock follows one deck at a time, the first heard, and `master` marks it, since passive mode can't hear the DJ's master. The old UI's `is_playing` is "the clock isn't stale".
- A set BPM, a tap or a nudge holds Internal under Auto until a DJ starts again; `PUT /inputs/tempo` with `lock: "auto"` and no BPM releases the hold.
- A tap's `client_time` is a hint, not a setting: missing, not finite, or more than a day from the server's clock, the tap is timed by its arrival (`tempo/tap.py`'s `usable_client_time`), over REST and the socket alike (both parse `TapRequest`). A BPM or a nudge that isn't a finite number is refused (422), and so is a `client_time` that isn't a number. `types.is_finite_number` is the one finite-number check.
- The tempo settings (the lock, the internal BPM with how and when it was set, the last DJ set) live in `state.db`'s config table under section `tempo`. They join backup and restore, and a restore applies them at once.
- Event bus callbacks must be non-blocking (<1ms). Async work uses `create_task()`.
- Per-device send loops, each device at its own rate: every adapter is built at the configured rate, the engine's or its kind's `max_fps` if lower, and states what it streams at (`stream_fps`): OpenRGB devices, LIFX bulbs and a Govee lamp by razer (30 by default) at the configured rate, LIFX strips and matrices at most 20 a second, and a Govee lamp by `colorwc` at most 10 whatever the config says; a frame equal to the last one sent is skipped for up to a second, unless the route was set, the adapter changed or the light dropped out since. Distributor writes target_time floats to depth-1 FrameSlots — no numpy copies until actual send — from the tick before a device is due, so a light slower than the engine isn't written frames it never takes; `frames_dropped` counts only frames still untaken a period after the device was due.
- Latency is one way: a windowed median seeded at the config's `latency_ms` (LIFX 10 ms, Govee 100 ms), plus the device's display delay (half a LIFX fade; a matrix's `MATRIX_DISPLAY_MS` more). Idle round trips are ignored: Wi-Fi power save makes them long. So LIFX's echo probes go only to a light that streams. OpenRGB devices keep the device-type heuristics (USB 5 ms) permanently: nothing probes them, and the scheduler never times a send. A light's latency is `estimated` in the API until a round trip measured while it streams lands.
- Brightness applies at send: rings hold frames before brightness; routes and the frame feed scale them.
- A Govee lamp's output: its own (`PUT /api/lights/{id}/output`, JSON in its device row's `extra` under `output`), else the config's `segment_override` (one outside `MIN_SEGMENTS` to `MAX_SEGMENTS` is ignored with a warning), else the SKU table. One set plays at once, with no network (the lamp's adapter is built again from its row), and so do a restored backup's; `GET` says how the lamp plays now, from its live adapter, and the config's `segment_override` is the one the lamps were set up with (a change applies at the next start).
- Razer is switched on before a lamp's first frame and after `RAZER_IDLE_S` without one, and again after a prepare, restore or power switch; a restore of a lamp that's on sends razer-off first, and a lamp playing one colour is sent razer-off when it's prepared.
- DeviceAdapter is ABC (not Protocol). discover() excluded from base — adapters own their own discovery.
- SQLite `state.db` is single source of truth at runtime; TOML is import/export format only
- Device identity: MAC-based `stable_id` for cross-session matching via `DeviceInfo.effective_id` (falls back to name)
- Web layer resolves display names → stable_ids before any DB write (placements, deletions)
- A new stable_id is a new light even beside an online light of the same name (the PC's four RAM sticks share one); a device is matched by name only when exactly one managed device has that name and it's offline (`DiscoveryOrchestrator._merge`)
- Ghost/promote/demote lifecycle: offline devices stay registered as GhostAdapters, get promoted when rediscovered
- Discovery `skip_ids` must exclude offline devices — otherwise ghosts can never be re-promoted
- Zones replace the transport, scenes and pipelines (spec §4.3): starting a look on a zone takes its lights from other zones (newest wins); what's running persists and resumes on start; there is nothing to press play on
- Capture/restore: a light is captured before dj-ledfx first changes it; the capture survives hand-overs between zones and restarts (in state.db) and is released on Off or Stop all. `capture_state()` returns None by default (can't capture: Off leaves it alone)
- Sharing policy (spec §6.4): dj-ledfx switches a light on only when a look is applied. A zone light switched off elsewhere drops out and rejoins when it's back on; a stopped firmware effect is re-sent at the next 5 s poll while the light is on; idle lights are read every 30 s and never changed
- Light status: a light whose read fails three 5 s polls in a row (no answer, or any error) is `offline` (a wall switch), whatever its protocol; `switched-off` is a power reading, not an attention item. A failed read isn't a miss when the light was heard from since its last read ended (`last_heard`: a Govee lamp's status replies, every LIFX reply, echoes included, though only a streaming light is probed), and a light set up again (`DeviceOnlineEvent`, `DeviceDiscoveredEvent`) starts counting afresh
- A Govee lamp that misses three reads goes offline and gets no frames until a scan finds it.
- Preview-only (`engine.preview_only`, `PUT /api/config`) applies at once: looks run and stream to the web preview, the lights are left alone. It's kept across restarts in state.db's config table
- Scenes became device-group zones once (migration 004), not running; the old UI's effect endpoints take `?zone=`
- Rooms, sub-zones and the whole home are zones derived from the map, and they follow it: a light moved into a running room joins it unless a newer zone holds it, and so does a device discovered there (switched on only by the next look applied); a light moved out is put back; a running sub-zone that's deleted turns off
- A preview's runtime lives in the zone manager beside the zones' (`start_preview`/`end_preview`) and follows the map in the same redraw; it never gets a route, ends when its zone is gone, and ends after 10 s unwatched
- A light that runs its own effect is drawn only while the live stream is watched
- The PC is one light in the API; each part stays its own device underneath, with its own adapter, latency and LED order
- Placements are confirmed only explicitly: guessing and moving never confirm a placement (a confirmed one stays confirmed when the owner moves it), and seeds are always unconfirmed
- Placement guessing puts each light in its form (an upright lamp stands from 0.1 m, a strip lies along its length, a matrix stands as a grid with its first row at the top, as an old scene's matrix now does too, and a candle's or a tube's stands as a cylinder), and when a light comes online its unconfirmed placement, if it hides the light's form, is fitted again, unless it's the owner's. On the lights a candle's and a tube's first row is at the top, so a cylinder whose rows run bottom to top, as home.json's seeds do, hides the form: the fit turns its rows and keeps its spot and size (`fitted()` in `home/guess.py`). A placement's `source` says whose it is: `seed` (home.json's), `guess` (a spread spot or a refit) or `owner` (`PUT /api/lights/{id}/placement`, or an old scene's placement moved on at the first start); `state.db` (migration 009) and backups keep it.
- A look that stops is remembered for "Start again" (`GET /api/running/recent`, M2 plan ruling 19): one entry per zone and look, the 10 newest stops in `state.db`. Gone zones, deleted looks and what runs now are left out when the list is read. Deleting a zone and restoring a backup remember nothing
- The seed gives the room `corridor` the owner's name over home.json's (`OWNER_ROOM_NAMES` in `home/seed.py`, ruling 18); home.json is left as it is
- The map, the placements and the recent looks join backup and restore

## Logging Discipline

- Default production level: INFO
- TRACE: per-frame data (only with `--log-level TRACE`)
- DEBUG: per-beat data, device sends
- INFO: state changes, periodic status (every 10s), startup/shutdown
- WARNING: device disconnect, network issues, drift > threshold
- ERROR: unrecoverable failures
- Never log at INFO in the render loop hot path

## Testing

- Tests mirror src structure: `tests/prodjlink/`, `tests/tempo/`, etc.
- Use `pytest-asyncio` for async tests
- Packet parsing tests use hex dump fixtures from `tests/fixtures/`; `tests/fixtures/lifx/recorded/` holds replies recorded from this home's lights (a product with no recording skips)
- Mock `openrgb-python` for device tests
- Integration tests drive a `TempoClock` with a DJ's beat (`beat_event()`) → full pipeline → mock DeviceAdapter
- Shared fakes: `tests/conftest.py` (`FakeLight`, a controllable light, whose `heard` is its `last_heard`; `GlowFirmware`, a firmware effect; `device_stats()`, `render_ctx()`, `tempo_ctx()` (a moment some beats into a steady tempo) and `beat_ctx()` (that moment as a 1D effect sees it); `events()`, every event of one type a bus emits; `builtin_look()`, a built-in look by id; `Hold`, a call held part-way; the `db` fixture, an open state.db; `as_schema()`, a state.db made to look as an older schema left it, for an upgrade test (it drops `placements.source`, the one column a migration can't add twice); the PC's `SERVER`, `OPENRGB`, `pc_lights()`, `pc_part_info()`, and `lamp_info()`, `colours()`; `RingSource` and `ring_route()`, a route over a ring's frames at a `brightness`; `nearest_frame()`, the frame in a ring nearest a moment), `tests/zone_home.py` (a zone manager over fake lights, and `Home.tempo`, a real `TempoClock` over its state.db; `zone_record()`), `tests/api_home.py` (the same behind the web app; `discovery=` stands in for the discovery orchestrator, and `backends=` gives it a real one over those backends), `tests/lifx_fakes.py` (`FakeLifxTransport`, a LifxTransport with a faked socket, whose `quiet` lists the message types a light never answers; `lifx_bulb/strip/candle()`; `read_hex()` for hex fixtures), `tests/govee_fakes.py` (the test lamp: `lamp_record()`, its device row `lamp_row()`, and `govee_lamp()`, a `FakeLight` with Govee's caps; the SKU table's kinds `UPRIGHT` and `NO_RAZER`, registered under `TEST_MODEL`; `lamp_transport()`, a transport that hears the lamp, and `sent()`, what went through it), `tests/tempo_fakes.py` (`FakeTime`, `tempo_clock()`, `beat_event()`, `beat_packet()` (raw `next_beat_ms` and `capability` too), `play()`, `PLAYER`, `START`, `START_WALL`); `pythonpath = ["tests"]` makes them importable
- The repo is public: new code, tests, commits and PRs carry no LAN address, MAC, light name or model number. A test address is `127.0.0.1`, a Govee device id `test-lamp`, and a test that needs a Govee model reads one from `SKU_REGISTRY` or adds its own key (`test-model`)
- Every test starts from the app's effect registry (an autouse fixture in conftest); a test effect defined with `register=False` never leaks
- `tests/map_home.py`: `tiny_home()` (a two-room plan) and points on it (`DESK_CORNER`, `IN_THE_DESK_CORNER`, `IN_THE_EAST_ROOM`), `open_map()` (a real `HomeMap` over state.db and some lights), `leds_at()` (`anchor_points=` gives an anchor more than one point), `handoff_pins()` and `design_home_json()` (the design files), and `seeded_zone_lights()`/`seeded_space()`/`seeded_ledset()` (this home's seeded LEDs, for perf); `build_home(plan=...)` and `api_home(plan=...)` wire a real `HomeMap`; `FakeHome` stands in for the map's zones (a test edits it, then calls `manager.home_changed()`)
- Web tests use `httpx.AsyncClient` with FastAPI's `TestClient` pattern; `tests/web/conftest.py` shares `mock_deps(**overrides)` (create_app's arguments, mocked, any of them replaced), `write_dist()`, `static_client()`, and `until(ws, channel)`, the next message on one /ws channel
- `tests/web/` covers all REST routers and WebSocket hub; `tests/test_main.py` runs the app in a subprocess and checks a SIGTERM shutdown logs no traceback, and that browser tabs closing their sockets never freeze it; every app there hears Pro DJ Link on `--dj-listen 127.0.0.1:0` and a test reads the port back from `GET /api/inputs`'s `prodjlink.interface`; `_app()` starts one and kills it on the way out, and `_stop()` sends SIGTERM and waits
- Gates compare with a baseline: no new mypy errors (compare `uv run mypy src/` output with the branch's starting point) and no format findings; perf benchmarks are deselected (`-m perf` runs them)
- `tests/web/test_openapi_types.py` fails when `web/src/api/generated/openapi.json` isn't the backend's schema; `cd web && npm run api:types` regenerates it

## Gotchas

- `openrgb-python` is synchronous TCP — MUST wrap in `asyncio.to_thread()` or it blocks the event loop
- XDJ-AZ is an all-in-one 4-deck unit — may send multi-deck beat data from a single device ID
- Beat packets on port 50001 are broadcast (free), but status packets on port 50002 require virtual CDJ registration
- Phase wraps from ~1.0 to ~0.0 at each beat — effects must handle this discontinuity: one that moves across beats reads `beats`, and a BPM energy never sets a speed (it would jump wherever the phase it scales wraps)
- Pro DJ Link requires binding to the correct network interface (not localhost)
- A zone's ring has frames from its first tick, `horizon` ahead (at most `HORIZON_CAP_S`), and a light whose moment comes before the first frame is sent that frame, so a look reaches every light within a frame or two of its start
- Only CDJ-3000 generation packets (0x1F) supported in MVP; older hardware silently ignored
- R3F: `<threeLine>` is the correct intrinsic for THREE.Line (not `<line_>`) — crashes if wrong
- R3F: `useFrame` for live-updating geometry; drei `Line` component only updates on prop change via React state
- R3F: TransformControls `onChange` prop for live drag callbacks (not useEffect + ref — refs don't trigger effects)
- R3F: optimistic state updates needed when dragging 3D objects to avoid position jumps during API round-trips
- Config persistence: `dataclasses.asdict()` serializes field names as-is; `load_config` must match (e.g. `scene_config` not `scene`)
- Device adapter: use `managed.adapter.device_info.name` (not `managed.adapter.name`) to get device name
- SQLite: never use `INSERT OR REPLACE` on tables with FK cascades — it's `DELETE + INSERT`, silently wiping child rows. Use `INSERT ... ON CONFLICT DO UPDATE SET` instead
- SQLite: `executescript()` issues implicit COMMIT before running — breaks transactional migrations. Use manual `BEGIN`/`COMMIT` with individual `execute()` calls
- SQLite: single `asyncio.Lock` on StateDB protects the `sqlite3.Connection` object (not thread-safe despite `check_same_thread=False`), not DB-level locking
- Scheduler hot path: don't `list()` wrap `dict.values()` iteration — unnecessary allocation at 60fps on single event loop
- TOML serialization: use `json.dumps(v)` not `str(v)` for config values — `str(True)` produces `"True"` which fails `json.loads()` round-trip; a hand-edited backup's unquoted date or time is a TOML datetime, which `import_toml` stores as ISO text (`_iso_text`); TOML has no null, so the export leaves an unset config value out (one saved as null made every export of the deployed database fail)
- StateDB: every call on the connection, `close()` included, goes through `_locked()`, which holds the lock until the worker thread is done with the connection, even when the caller is cancelled (a shutdown mid-write): a thread can't be stopped, so a cancelled caller waits for it
- numpy `np.clip(...).astype()` returns `Any` per mypy — bind it to an annotated `NDArray` local before returning (M2's way), or `# type: ignore[no-any-return]` (not `[return-value]`)
- Migration SQL is split on `;` (`state_db.py`), so a migration's comments must not contain one
- Migration 009 gives each placement from before it a `source`. The first start's rows, written in one transaction with the `home_placements_seeded` mark, are those within a second of the earliest: they become `seed`, or `owner` where an old scene placed the device (a spread spot among them is called a seed too, which changes nothing: a refit treats seeds and guesses alike). Any other row is a `guess`, so an owner's placement made through the API before 009 reads as a guess
- `HomeMap.load()` calls no listeners, so restore can run it under the zone manager's lock
- `type:<word>` selectors match whole words of a light's name and model
- Focus's anchor comes from its looks.json description, not from typed text
- The deployed app's first M2 start runs migrations 005 and 006 and places every known light, unconfirmed; a light discovered later gets no placement until `POST /api/lights/placement/guess` or the next start
- From the deployed app's first M3 start the tempo clock always runs: with no DJ, the classic looks move at the internal clock's 120 BPM (until a BPM is set) where before they stood still. Strobe flashes once a beat, under 3 a second, until a DJ's beat drives it (`beat.dj`); with a DJ it keeps its subdivisions
- The classics move on the beat count, not the BPM. In Colour chase each light glides one palette colour along every `beats_per_step` beats (1 by default), from the last colour back to the first, and the colours travel forward along the axis (`reverse`: back); Rainbow wave turns once a bar; Breathe breathes once every `beats_per_cycle` beats (up to 8, across bar lines) and takes its next colour at its dimmest
- `recent_looks` compares its times as text, so they're written in UTC (`timing.utc_text`)
- MockDeviceAdapter: never patch `type(adapter).device_info` (class-level property) — leaks to all instances across tests. Use a subclass instead.
- Web tests: `uv sync --extra web` required in worktrees — web tests skip silently without it
- Granian's embedded `Server.stop()` abandons open websockets, and a close sent from another task hangs while a receive is pending: each `/ws` session cancels its own receive, then closes (`ws.close_all`)
- Granian before 2.7.8 can freeze the whole app when a `/ws` client leaves. Its `future_watcher` tears the socket down by blocking on the socket's locks while holding the GIL, and a send still in flight holds one of them and needs the GIL to log its error, so the two wait forever. uv.lock pins 2.8.4, which also has the fix for CVE-2026-42544 (since 2.7.4), and pyproject.toml's floor keeps it there; 2.7.8 and 2.7.9 don't freeze, but often never finish the close handshake
- Try another version of a locked package in a separate venv: `uv run` re-syncs `.venv` to uv.lock, so `uv pip install granian==X` followed by `uv run` runs the locked version
- Awaiting cancelled tasks in a `finally`: use `asyncio.wait(tasks)`, not `gather` — gather re-raises a child's CancelledError, which anyio's cancel scope doesn't swallow (a flaky test, not a crash)
- LIFX: a colour (SetColor) doesn't stop a tile effect on a Candle C; the LIFX app also sends SetTileEffect OFF. `is_running` reads GetTileEffect; bulb waveforms can't say (None)
- LIFX: a bulb keeps animating its waveform's colour while switched off, so colour reads can't show a re-send
- LIFX scripts can run beside the deployed app: `LifxTransport.open()` binds an ephemeral port
- A LIFX matrix queues `SetTileState64` above about 30 a second; matrices are capped at 20
- OpenRGB: parts in an `Off` mode keep a stale colour buffer, so `/api/lights` shows a colour for a dark part; read the mode to know. The Corsair Commander Core reports 0 LEDs
- UDP 4002 (Govee replies) belongs to whichever program binds it first. The deployed app holds it; Home Assistant's `govee_light_local` retries every 10 minutes, at about :x8 past the hour, and takes it if dj-ledfx is down then, which leaves dj-ledfx deaf to Govee replies (the log warns `could not bind port 4002`): it can't read a lamp or tell one stopped answering, and keeps sending. Stop the app well clear of :x8, and after a restart check that `ss -ulne 'sport = :4002'` shows `uid:10001` (`ss -p` needs root)
- Govee `colorwc` at 40 a second ran 9 commands behind, and two lamps flooded that way were unreachable for about ten minutes; `GOVEE_COLOUR_FPS` caps it at 10 whatever the config says
- A Govee lamp can show nothing for a razer frame with more colours than it has segments: given 15, two of three upright lamps of 14 stayed dark and the third dropped the extra. The SKU table's count, or a lamp's own output, is the count the lamp shows. Check a new model's count by eye with `scripts/govee_razer_check.py`
- A Govee lamp streaming razer still answers status queries (an upright lamp answered 9 of 10 while streaming, 5 of 5 before), so one that stops answering mid-look is still taken offline; a read asks twice, so one lost reply isn't a miss
- A run beside the deployed app can't bind UDP 50001: it warns and runs on its internal clock, with `prodjlink.state` "disconnected". To hear Pro DJ Link there, pass `--dj-listen 127.0.0.1:0` (any free loopback port; `GET /api/inputs` names it), and serve on a free `--web-port` (the deployed app holds 8080)
- A run beside the deployed app can't hear Govee replies, so it can't capture a lamp, and Off can't restore one: keep Govee lamps out of such a run (delete their rows from its copy of the database)
- The container mounts `config.toml` read-only (a file bind mount: saving logs `Device or resource busy`); `state.db` lives in the `dj-ledfx_state` volume. At start the app reads its config from state.db, and config.toml only while state.db holds none of `AppConfig`'s sections, so settings saved from the web app, preview-only included, survive a restart
- `migrate_from_toml()` runs once per database: the first start that finds config.toml or presets.toml migrates them and writes the run-once mark `toml_migrated`, and a setting saved before then (preview-only, the tempo) doesn't stop it. Migration 008 gave the mark to every database that already held the app's config (any section but `tempo`), the deployed one included, so its read-only config.toml isn't migrated again
- `Path.resolve()` raises `ValueError` on a NUL byte (a request for `/%00`); path guards must catch it, as `_file_within` in `web/app.py` does
- FastAPI's own 422 echoes the request's input, and JSON can't carry a NaN, so a NaN in a body gave a 500; `unprocessable` in `web/errors.py` answers it as text
- Web app: tokens.css names both a colour and a font size `control`; `text-control` is the colour, `text-size-control` the size
- Web app: where tokens.css has a token, use its utility (`text-data`, `h-(--touch-min)`), never an arbitrary value equal to it
- Web app: `@import "./tokens.css" theme(static)` keeps every token as a CSS variable, even ones no class uses
- Web app: Vite's dev and preview servers only answer below `/next/` — a bare `/next` is a 404 there and a missing asset gets index.html; FastAPI handles both (tests/web/test_next_static.py)
- Web app: React Router won't match a bare `/next` against a `/next/` basename, so `app/boot.tsx` passes `routerBasename(import.meta.env.BASE_URL)`; Vitest reports `BASE_URL` as `/` whatever `base` says, so tests pass `routerBasename('/next/')`
- Web app: Base UI tooltips are visual only (their popups are `aria-hidden`); icon-only triggers still need `aria-label`
- Web app: Base UI clones a `trigger` element and adds props and a ref, so a component used as one spreads the rest of `ComponentProps<'button'>` onto its button (React 19 passes `ref` as a prop; see `AttentionButton`)
- Web app: axe's region rule flags a popup portaled loose into `<body>` unless it's a dialog; the Select list portals into the dialog or `<main>` around its trigger, and a new overlay joins `OVERLAYS` in `e2e/shell.spec.ts`
- Web app: Base UI's `Portal` renders nothing for `container={null}`; `undefined`, or a ref still holding null, means `<body>`
- Web app: a live region must exist before its text changes, so the page keeps one: `Announcer` wraps `AppShell`, outside the chrome that swaps at the phone breakpoint, and says the connection's news; anything else speaks through `useAnnounce()`, as `Toast` does. Don't add another `role="status"`
- Web app: where a render draws a control smaller than `--touch-min`, keep the drawn face and add the `touch-target` utility from app.css (`max-md:touch-target` on a phone-only control, like TempoModule's TAP); it grows the hit area and never shrinks one
- Web app: `AppShell`'s root alone pads by all four `env(safe-area-inset-*)` (index.html sets `viewport-fit=cover`), in both layouts; a phone turned sideways is wider than the phone breakpoint and gets the desktop chrome. Keep insets off the rail, the bars and `<main>`. e2e fakes a notch with CDP `Emulation.setSafeAreaInsetsOverride` and checks landmark edges
- Web app: jsdom has no `matchMedia`; component tests resize with `setViewportWidth()` from `src/test/viewport.ts`
- Web app: `npm run e2e` builds the mock bundle (`dist-mock`) and serves it on :4174, and the production bundle on :4175 for e2e/production.spec.ts (no backend, so it says Reconnecting), both with `strictPort` and no server reuse, so only one worktree can run it at a time; `vite preview` proxies nothing, so e2e never reaches a real server
- Web app: Playwright baselines are per OS (`*-linux.png`); re-record with `npm run e2e -- --update-snapshots` only after comparing with the reference renders by eye
- Web app: a backend API change (a route, a contract model) needs `cd web && npm run api:types` in the same commit, or tests/web/test_openapi_types.py fails; when the backend starts serving a type `contract.ts` wrote by hand, `contract.test.ts` fails `tsc -b` until the hand-written type becomes the generated alias
- A route's docstring is its OpenAPI description: changing one changes the generated types (`cd web && npm run api:types`)
- Web app: MSW's worker comes from the msw package (`msw/mockServiceWorker.js`), served by the `mswWorker()` plugin in vite.config.ts in dev and emitted into `dist-mock`, never into a production build; `scripts/check-dist.ts` fails `npm run build` if MSW, the mock fixtures or home.json gets in. ESLint keeps `@/api/mocks/*`, `fetch` and `WebSocket` inside src/api/
- Web app: if MSW's worker fails to register (plain http off localhost), app/boot.tsx draws "The mocks didn't start" with the browser's reason instead of a blank page
- Web app: the chrome and the pages read the live store a slice at a time (`useLive(selector)`); a selector that builds an object needs `useLiveShallow`, or its component redraws on every message, and a slice a message replaces with an equal copy (the inputs heartbeat's sun, once a second) needs `useLiveBy(selector, same)`. Frames never go into React state
- Web app: the beat clock and the link's watchdog run on `performance.now()` (`clientNow()`), which Playwright's `page.clock.setFixedTime` leaves running; the mock's times come from `Date`, so a fixed clock still shows the renders' times
- Web app: e2e runs on the mock, which renders only once MSW's worker is up, so a Playwright test waits for the data (`open()` in e2e/helpers.ts waits for the attention button, whatever it says) before `document.fonts.ready`; a test of the stage opens with `openStage()` (e2e/helpers.ts), which waits for the canvas to show; a test that measures the tempo waits for it with `tempo()`, and a screenshot opens with `openStill()` (both in e2e/shell.spec.ts; `?still` holds the beat and the frames)
- Web app: a test running a `MockServer` through `inMemorySockets()` advances fake timers with `await vi.advanceTimersByTimeAsync()`, because the socket delivers in microtasks; `startMockServer()` and `startMockDataLayer()` in src/test/live.ts start one on `Date.now()` and stop it after the test; `startDataLayer()` stops the client it started before, so there is one socket at a time
- Web app: the shared test setup calls `resetDataLayer()` after each test (the client stopped; the live store, frames, beat clock and REST cache empty); a component test that needs the server's data seeds it with `seedLive()` from src/test/live.ts
- Web app: the owner renamed room `corridor` for display through `OWNER_ROOM_NAMES` in src/api/mocks/fixtures.ts, as engine M2's seed does; the byte copy of home.json stays as it is, and a room name is read through `roomName()` or the fixtures, never from the JSON
- Web app: "Start again" is `api.recentLooks()` (`GET /api/running/recent`), newest stop first; one tap is `api.start(zoneId, { lookId })`, and the mock remembers stops as engine M2 does
- Web app: Vitest strips types without checking them, so `npx tsc -b` is the type gate: a class with two members of one name runs in Vitest with the later one silently winning
- Web app: MSW's Node server makes Node 26 print `ExperimentalWarning: localStorage is not available` in node-environment tests; it's harmless
- Web app: the stage's numbers and colours are `SPEC`, `RENDER` and `TOKENS` in `src/stage/design-numbers.ts`, and Live's layout numbers `LIVE_LAYOUT` in `src/pages/live-numbers.ts`; `npm run design:numbers` generates both. Never edit them by hand, and never read tokens.css at runtime. After a new handoff, regenerate them: `src/stage/design-numbers.node.test.ts` fails until then, and skips its render half where the renders are missing (CI)
- Web app: the stage's canvas is R3F's `createRoot` on `StageCanvas`'s own `<canvas>`, not `<Canvas>`, whose event manager and `extend(THREE)` would bundle all of three.js; it has no event manager (the pointer is picked in `picking.ts`), and the scene goes in as `<primitive>`s. Its frameloop is `never` until `gl.compileAsync()` has compiled the scene's shaders, with the canvas hidden till then (an opaque context is black before its first draw), then `demand`
- Web app: the light layer draws in `useCadence`'s tick: `FrameWriter.write()`, and only if that changed something, `LightMeshes.update()` and `advance(now)`, which renders in that animation frame; `invalidate()` would wait for the next one and halve the rate. After an animation frame with nothing new the cadence sleeps, asking for no animation frames, until `FrameStore.onNextFrame()` wakes it
- Web app: the stage's canvas is `linear` and `flat`: colours are made with `Color.setRGB()` from `palette.ts`, never from a hex string, which three.js would convert from sRGB
- Web app: jsdom has no WebGL, ResizeObserver or reduced-motion query. Stage tests take their scaffolding from src/test/stage.ts: `MAIN_STAGE` (Main.png's stage size), `heroPose()`, `stageWriter()`, `sceneProps()`, `seedStage()` (REST and live data), `loadedStage()` (the lazy chunk's wait) and the factories that mock `webgl.ts` and `stage-canvas.tsx`. A vi.mock factory runs before the file's imports, so it reaches them by a dynamic import (`vi.mock('./stage-canvas', (original) => import('@/test/stage').then((stage) => stage.canvasMock(original)))`), and src/test/stage.ts imports none of the modules it stands in for. Tests push frames with `pushFrame()` (src/test/live.ts), size the stage with `resizeObserved()` (src/test/resize.ts) and switch reduced motion with `setReducedMotion()` (src/test/viewport.ts); Node's `THREE_CJS_DEPRECATED` warning in those tests comes from React Three Fiber's CommonJS build, which Vitest loads, and is harmless
- Web app: three.js is a chunk of its own (`codeSplitting` in vite.config.ts, named by `THREE_CHUNK` in scripts/chunks.ts), which `scripts/check-dist.ts` leaves out of §14's budget; Vite's warning that the chunk is large is expected
- Web app: `npm run e2e:perf` draws on the machine's GPU (ANGLE over Vulkan) and fails on a software renderer; it serves on e2e's ports, so it can't run beside `npm run e2e`
- Web app: the mock streams the lights running their own effect, as the engine does while the live stream is watched, so the firmware scenario streams every LED in the home; that is what `e2e:perf` measures
- Web app: Playwright's web servers run `tsc -b` before they build, so a type error anywhere stops `npm run e2e` and `e2e:perf` at start with `Process from config.webServer was not able to start. Exit code: 2`; `npx tsc -b` shows it
