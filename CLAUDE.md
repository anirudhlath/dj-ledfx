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
- Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are: import them, or copy them byte for byte with a test that fails when the copy differs. Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file.
- Before each web app task, re-read the spec sections and look at the renders that the task names.
- A new handoff replaces `docs/design/web-app/` and the web app spec wholesale. Don't hand-edit the design files.


## Commands

```bash
uv sync                          # Install dependencies
uv sync --extra web              # Install with web UI extras
uv run -m dj_ledfx              # Run the app
uv run -m dj_ledfx --demo       # Run with simulated beats (no DJ hardware)
uv run -m dj_ledfx --demo --web # Run with web UI (requires: uv sync --extra web)
uv run -m dj_ledfx --demo --web dev  # Run with hot-reload dev server (frontend + backend)
uv run pytest                    # Run tests
uv run pytest -x -v              # Run tests, stop on first failure
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check
cd frontend && npm run build     # Build frontend static assets
cd frontend && npx tsc --noEmit -p tsconfig.app.json  # TypeScript type check (plain `npx tsc --noEmit` checks nothing: the root tsconfig only holds references)
cd frontend && npm run dev       # Frontend dev server (proxies to :8080)
uv run python scripts/lifx_record_fixtures.py  # Record the LAN's LIFX replies into tests/fixtures/lifx/recorded/ (read-only; runs beside the container)
docker compose up -d --build     # Deploy: from the main checkout ~/code/private/dj-ledfx, after a merge (see Deployment)
docker compose logs app          # The deployed app's log
cd web && npm install            # New web app (F0–F11): install dependencies
cd web && npm run dev            # Dev server at http://localhost:5174/next/ (proxies /api and /ws to :8080)
cd web && npm run build          # Type-check and build web/dist; FastAPI serves it at /next
cd web && npm test               # Vitest: unit and component tests
cd web && npm run lint           # ESLint (npx tsc -b type-checks)
cd web && npx playwright install chromium  # Once per machine
cd web && npm run e2e            # Playwright: screenshots, axe on every route, keyboard, reflow
```

## Deployment

- The app runs on this host as `dj-ledfx-app-1` (compose project `dj-ledfx`, from the committed `Dockerfile` and `docker-compose.yml`), with host networking: it serves 8080 and binds Pro DJ Link's 50001/udp itself. No `--demo`.
- After merging a deploy change: `docker compose up -d --build` in the main checkout `~/code/private/dj-ledfx`. The container mounts that checkout's `config.toml`; `state.db` stays in the `dj-ledfx_state` volume and zones resume.
- UFW governs 8080: the LAN is allowed, and `tailscale0` has its own 8080 rule. Ask the owner before changing UFW.
- Check it: `docker compose ps`, `curl -s http://127.0.0.1:8080/api/running`, `/api/lights`, `/api/attention`.

## Architecture

src/dj_ledfx/ layout:
- `prodjlink/` — Pro DJ Link UDP protocol (passive listener on port 50001)
- `beat/` — BeatClock phase interpolation + BeatSimulator for demo mode
- `effects/` — Effect ABC (`base.py`, with today's 1D `StripEffect`) + the 60fps engine, which hosts each running zone's runtime and renders it ahead into that zone's ring buffer
- `effects/context.py` — `RenderContext` (beat, time, signals) that field effects render from
- `effects/ledset.py` — `LedSet`: a zone's LEDs from each device's own geometry, in order
- `effects/field.py`, `effects/strip_adapter.py` — `FieldEffect`; `StripAdapter` runs a 1D `StripEffect` in LED order along a zone's lights
- `effects/firmware.py`, `firmware_lifx.py`, `firmware_openrgb.py` — effects the light runs itself: LIFX Flame and Morph (matrix), Move (multizone), waveforms (bulbs), OpenRGB hardware modes; lights that can't run one get its streamed `emulate()`
- `effects/color.py` — Color math: hex/RGB conversion, HSV→RGB vectorized, palette interpolation
- `effects/easing.py` — Easing functions: lerp, ease_in/out, sine_ease
- `effects/energy.py` — BPM→energy mapping (0-1 linear between 100-150 BPM)
- `scheduling/` — LookaheadScheduler: per-device send loops with FrameSlot depth-1 slots, FPS cap, RTT measurement
- `scheduling/route.py` — `DeviceRoute`: a light's slice of its zone's frames, converted to 8 bits once, at send
- `metrics.py` — Contextmanager-based timing metrics for performance measurement
- `devices/` — DeviceAdapter ABC (read/set power and colour, capture/restore) + OpenRGB adapter (asyncio.to_thread wrapped) + device-type heuristics
- `devices/capabilities.py` — `DeviceCapabilities`: what a light can do (colour, matrix, multizone, effects)
- `devices/backend.py` — DeviceBackend ABC for protocol-level adapters
- `devices/govee/` — Govee WiFi LED protocol (UDP segment control, SKU registry, transport)
- `devices/lifx/` — LIFX LAN protocol (bulb/strip/tile discovery, packet encoding, transport); `base.py` shared adapter, `products.py` capabilities from the vendored `data/products.json`
- `looks/` — the look model, the built-ins (the handoff's Firmware showcase and six classic looks, from the vendored `data/looks.json`), and the store (saved looks, stars)
- `zones/` — `model` (every light, rooms, groups), `store`, `runtime` (a running look's layers and ring buffer), `manager` (take-over, capture/restore, brightness, Stop all, resume, preview-only, the sharing policy), `lights` (LightMonitor: status and the 5 s/30 s polls), `attention` (the feed)
- `latency/` — ProbeStrategy protocol + StaticLatency/EMA/WindowedMean strategies
- `config.py` — Nested dataclass config (EngineConfig, EffectConfig, NetworkConfig, WebConfig, DevicesConfig) with load/save via tomllib/tomli_w
- `effects/params.py` — EffectParam descriptor for runtime introspection
- `effects/registry.py` — Effect auto-registry via __init_subclass__, get_effect_classes/schemas/create
- `effects/presets.py` — PresetStore with TOML persistence
- `devices/manager.py` — DeviceManager: discovery, lifecycle, group management
- `web/` — FastAPI app factory, REST routers (effects, devices, config, scene, looks, zones, lights, attention), WebSocket hub, Pydantic schemas
- `web/contract.py` — the web spec's API models (camelCase) and the converters from engine types; `web/errors.py` — `answers()` maps engine errors to HTTP
- `web/ws.py` — WebSocket hub: binary LED frame broadcast (2-byte name + 4-byte seq + RGB); beat, stats and status channels; pushed `running`, `lights` and `attention` snapshots; `transport` carries preview-only (`simulating` while on, `playing` otherwise); `close_all()` ends sessions with 1001 at shutdown
- `web/state.py` — WS subscription state and the `app.state` getters (`get_zones`, `get_looks`, ...)
- `web/router_scene.py` — Scene REST endpoints for the old scene page until F11 (placement CRUD, mapping config)
- `spatial/mapping.py` — mapping_from_config() shared factory for LinearMapping/RadialMapping
- `spatial/compositor.py` — Spatial compositor for multi-device LED frame distribution
- `spatial/geometry.py` — 3D geometry utilities for spatial calculations
- `spatial/scene.py` — SceneModel: device placements, spatial configuration
- `types.py` — Canonical location for all shared types (RGB, DeviceInfo, RenderedFrame, BeatState, DeviceStats)
- `events.py` — Typed callback event bus (sync, non-blocking callbacks only) + device events; the zones' events (`ZonesChanged`, `PreviewOnlyChanged`, `LightsChanged`, `AttentionChanged`) live in `zones/model.py`
- `persistence/` — SQLite-backed state persistence (state_db.py, toml_io.py, debounced_writer.py, migrations/)
- `devices/discovery.py` — DiscoveryOrchestrator: multi-wave scanning, fast reconnect, ghost promote/demote
- `devices/ghost.py` — GhostAdapter: placeholder for offline devices (is_connected=False, send_frame no-op)
- `status.py` — SystemStatus health tracking
- `main.py` — Application coordinator (startup/shutdown orchestration; stops the web server through `_WebServer.stop()`: close the websockets, then granian's `Server.stop()`)

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
- `src/chrome/` — the §6.2 always-within-reach cluster; `state.ts` holds its data types (`ChromeState`, `TempoState`, `Connection`) and `useChrome()` (a hero fixture until F1/F3)
- `src/shell/` — rail, top bar, tab bar, phone header; `AppShell` swaps desktop and phone chrome at the phone breakpoint without remounting the page
- `src/app/` — routes (§4.3), each with a `PageMeta` handle for its titles and context lines; pages sit in a pathless route whose `errorElement` keeps the chrome, and the root route's catches `AppShell` itself
- `src/pages/` — placeholders, not-found and error pages (all drawn by `EmptyState`), and the unlinked `/system` specimen
- `src/lib/` — formatters and the viewport and clock hooks (`useIsPhone`, `useNow`)
- `e2e/` — Playwright specs and the committed screenshot baselines
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
- Use shared utilities from `effects/color.py` (hex_to_rgb, rgb_to_hex, hsv_to_rgb_array, palette_lerp) and `effects/easing.py`
- Effect render methods are synchronous (pure numpy math, no I/O)
- BeatClock read methods are synchronous and lock-free (called from render loop)
- BeatClock write method is `on_beat(bpm, beat_number, next_beat_ms, timestamp, ...)` (not `update()`)
- DeviceAdapter is ABC (abstract base class). ProbeStrategy remains Protocol. Always code to the interface.
- All components run on a single asyncio event loop — no cross-thread state access
- AppConfig uses nested dataclasses: `config.engine.fps`, `config.devices.openrgb.host` (not flat)
- EffectEngine hosts the zones' runtimes (`add_runtime`/`remove_runtime`, called by the zone manager); there is no effect deck
- `frontend/` uses shadcn/ui components (based on @base-ui/react, NOT Radix — different APIs); `web/` uses @base-ui/react directly behind its own primitives in `src/design/`
- `frontend/` hooks in `src/hooks/`, one per domain (use-beat, use-devices, use-effects, use-scene, use-zones, use-ws-connection)
- WebSocket binary frame protocol: 2-byte name length, UTF-8 name, 4-byte sequence, then RGB bytes

## Key Design Decisions

- Ring buffer stores FUTURE frames. High-latency devices read newer (further-future) frames.
- Each zone runtime renders at `now + horizon` (its lights' largest latency plus a frame, within the lookahead) into its own ring buffer. Scheduler picks frame at `now + device_latency`.
- Frame data must be copied before passing to device threads (race condition prevention).
- Passive Pro DJ Link mode for MVP (no virtual CDJ handshake needed for beat packets).
- BeatClock drift correction: soft correct if <5ms, hard snap if >=5ms.
- BPM must always be pitch-adjusted: `track_bpm * (1 + pitch/100)`.
- `is_playing` inferred from packet flow in passive mode (no explicit play/pause signal).
- Event bus callbacks must be non-blocking (<1ms). Async work uses `create_task()`.
- Per-device send loops: each device runs at its natural FPS (bounded by configurable cap). Distributor writes target_time floats to depth-1 FrameSlots — no numpy copies until actual send.
- Device-type heuristic latency: Govee WiFi=100ms, LIFX WiFi=50ms, USB=5ms. Seeds the latency strategy. OpenRGB adapters use heuristics permanently (supports_latency_probing=False).
- DeviceAdapter is ABC (not Protocol). Provides supports_latency_probing class attribute. discover() excluded from base — adapters own their own discovery.
- SQLite `state.db` is single source of truth at runtime; TOML is import/export format only
- Device identity: MAC-based `stable_id` for cross-session matching via `DeviceInfo.effective_id` (falls back to name)
- Web layer resolves display names → stable_ids before any DB write (placements, deletions)
- A new stable_id is a new light even beside an online light of the same name (the PC's four RAM sticks share one); only an offline ghost is promoted by name
- Ghost/promote/demote lifecycle: offline devices stay registered as GhostAdapters, get promoted when rediscovered
- Discovery `skip_ids` must exclude offline devices — otherwise ghosts can never be re-promoted
- Zones replace the transport, scenes and pipelines (spec §4.3): starting a look on a zone takes its lights from other zones (newest wins); what's running persists and resumes on start; there is nothing to press play on
- Capture/restore: a light is captured before dj-ledfx first changes it; the capture survives hand-overs between zones and restarts (in state.db) and is released on Off or Stop all. `capture_state()` returns None by default (can't capture: Off leaves it alone)
- Sharing policy (spec §6.4): dj-ledfx switches a light on only when a look is applied. A zone light switched off elsewhere drops out and rejoins when it's back on; a stopped firmware effect is re-sent at the next 5 s poll while the light is on; idle lights are read every 30 s and never changed
- Light status: a LIFX light that misses three 5 s polls is `offline` (a wall switch); `switched-off` is a power reading, not an attention item
- Preview-only (`engine.preview_only`, `PUT /api/config`) applies at once: looks run and stream to the web preview, the lights are left alone. It's kept across restarts in state.db's config table
- Scenes became device-group zones once (migration 004), not running; the old UI's effect endpoints take `?zone=`

## Logging Discipline

- Default production level: INFO
- TRACE: per-frame data (only with `--log-level TRACE`)
- DEBUG: per-beat data, device sends
- INFO: state changes, periodic status (every 10s), startup/shutdown
- WARNING: device disconnect, network issues, drift > threshold
- ERROR: unrecoverable failures
- Never log at INFO in the render loop hot path

## Testing

- Tests mirror src structure: `tests/prodjlink/`, `tests/beat/`, etc.
- Use `pytest-asyncio` for async tests
- Packet parsing tests use hex dump fixtures from `tests/fixtures/`; `tests/fixtures/lifx/recorded/` holds replies recorded from this home's lights (a product with no recording skips)
- Mock `openrgb-python` for device tests
- Integration tests run BeatSimulator → full pipeline → mock DeviceAdapter
- Shared fakes: `tests/conftest.py` (`FakeLight`, a controllable light; `GlowFirmware`, a firmware effect), `tests/zone_home.py` (a zone manager over fake lights), `tests/api_home.py` (the same behind the web app); `pythonpath = ["tests"]` makes them importable
- Web tests use `httpx.AsyncClient` with FastAPI's `TestClient` pattern; `tests/web/conftest.py` shares `mock_deps()`, `write_dist()` and `static_client()` for `create_app`
- `tests/web/` covers all REST routers and WebSocket hub; `tests/test_main.py` runs the app in a subprocess and checks a SIGTERM shutdown logs no traceback
- Gates compare with a baseline: no new mypy errors (compare `uv run mypy src/` output with the branch's starting point) and no format findings; perf benchmarks are deselected (`-m perf` runs them)

## Gotchas

- `openrgb-python` is synchronous TCP — MUST wrap in `asyncio.to_thread()` or it blocks the event loop
- XDJ-AZ is an all-in-one 4-deck unit — may send multi-deck beat data from a single device ID
- Beat packets on port 50001 are broadcast (free), but status packets on port 50002 require virtual CDJ registration
- Phase wraps from ~1.0 to ~0.0 at each beat — effects must handle this discontinuity
- Pro DJ Link requires binding to the correct network interface (not localhost)
- Ring buffer needs ~1s to warm up — high-latency devices get no frames until buffer fills to their latency depth
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
- TOML serialization: use `json.dumps(v)` not `str(v)` for config values — `str(True)` produces `"True"` which fails `json.loads()` round-trip
- `close()` on StateDB must acquire the lock to prevent races with in-flight `to_thread` operations
- numpy `np.clip(...).astype()` returns `Any` per mypy — use `# type: ignore[no-any-return]` (not `[return-value]`)
- MockDeviceAdapter: never patch `type(adapter).device_info` (class-level property) — leaks to all instances across tests. Use a subclass instead.
- Web tests: `uv sync --extra web` required in worktrees — web tests skip silently without it
- Granian's embedded `Server.stop()` abandons open websockets, and a close sent from another task hangs while a receive is pending: each `/ws` session cancels its own receive, then closes (`ws.close_all`)
- Awaiting cancelled tasks in a `finally`: use `asyncio.wait(tasks)`, not `gather` — gather re-raises a child's CancelledError, which anyio's cancel scope doesn't swallow (a flaky test, not a crash)
- LIFX: a colour (SetColor) doesn't stop a tile effect on a Candle C; the LIFX app also sends SetTileEffect OFF. `is_running` reads GetTileEffect; bulb waveforms can't say (None)
- LIFX: a bulb keeps animating its waveform's colour while switched off, so colour reads can't show a re-send
- LIFX scripts can run beside the deployed app: `LifxTransport.open()` binds an ephemeral port
- OpenRGB: parts in an `Off` mode keep a stale colour buffer, so `/api/lights` shows a colour for a dark part; read the mode to know. The Corsair Commander Core reports 0 LEDs
- Home Assistant's Govee integration holds UDP 4002 on this host, so dj-ledfx can't hear Govee replies here (the log warns `could not bind port 4002`)
- Without `--demo` (as deployed), classic tempo looks hold still until a DJ plays (M3 adds the internal clock); firmware looks animate
- The container mounts `config.toml` read-only (a file bind mount: saving logs `Device or resource busy`); `state.db` lives in the `dj-ledfx_state` volume. At start the app reads its config from state.db, and config.toml only while state.db has none, so settings saved from the web app, preview-only included, survive a restart
- `Path.resolve()` raises `ValueError` on a NUL byte (a request for `/%00`); path guards must catch it, as `_file_within` in `web/app.py` does
- Web app: tokens.css names both a colour and a font size `control`; `text-control` is the colour, `text-size-control` the size
- Web app: where tokens.css has a token, use its utility (`text-data`, `h-(--touch-min)`), never an arbitrary value equal to it
- Web app: `@import "./tokens.css" theme(static)` keeps every token as a CSS variable, even ones no class uses
- Web app: Vite's dev and preview servers only answer below `/next/` — a bare `/next` is a 404 there and a missing asset gets index.html; FastAPI handles both (tests/web/test_next_static.py)
- Web app: React Router won't match a bare `/next` against a `/next/` basename, so `main.tsx` passes `routerBasename(import.meta.env.BASE_URL)`; Vitest reports `BASE_URL` as `/` whatever `base` says, so tests pass `routerBasename('/next/')`
- Web app: Base UI tooltips are visual only (their popups are `aria-hidden`); icon-only triggers still need `aria-label`
- Web app: Base UI clones a `trigger` element and adds props and a ref, so a component used as one spreads the rest of `ComponentProps<'button'>` onto its button (React 19 passes `ref` as a prop; see `AttentionButton`)
- Web app: axe's region rule flags a popup portaled loose into `<body>` unless it's a dialog; the Select list portals into the dialog or `<main>` around its trigger, and a new overlay joins `OVERLAYS` in `e2e/shell.spec.ts`
- Web app: Base UI's `Portal` renders nothing for `container={null}`; `undefined`, or a ref still holding null, means `<body>`
- Web app: a live region must exist before its text changes, so the page keeps one: `Announcer` wraps `AppShell`, outside the chrome that swaps at the phone breakpoint, and says the connection's news; anything else speaks through `useAnnounce()`, as `Toast` does. Don't add another `role="status"`
- Web app: where a render draws a control smaller than `--touch-min`, keep the drawn face and add the `touch-target` utility from app.css (`max-md:touch-target` on a phone-only control, like TempoModule's TAP); it grows the hit area and never shrinks one
- Web app: `AppShell`'s root alone pads by all four `env(safe-area-inset-*)` (index.html sets `viewport-fit=cover`), in both layouts; a phone turned sideways is wider than the phone breakpoint and gets the desktop chrome. Keep insets off the rail, the bars and `<main>`. e2e fakes a notch with CDP `Emulation.setSafeAreaInsetsOverride` and checks landmark edges
- Web app: jsdom has no `matchMedia`; component tests resize with `setViewportWidth()` from `src/test/viewport.ts`
- Web app: `npm run e2e` builds and serves the bundle on :4174 with `strictPort` and no server reuse, so only one worktree can run it at a time
- Web app: Playwright baselines are per OS (`*-linux.png`); re-record with `npm run e2e -- --update-snapshots` only after comparing with the reference renders by eye
