# Home Effects Engine Design

Turn dj-ledfx from a Pro-DJ-Link-driven LED strip engine into an always-on effects engine for the whole home, where effects live in 3D space. Pro DJ Link becomes one input among several.

**Status:** design approved in brainstorming (2026-09-23), then reconciled with the web app's Claude Design handoff the same day. This is the umbrella spec for eight engine milestones; each gets its own implementation plan, M1 first. The web app has its own spec, [`2026-09-23-web-app-rebuild-design.md`](2026-09-23-web-app-rebuild-design.md), and is built as a parallel track (§10).

## 1. Goals and Scope

**Goals**

- Set a look on a room, or the whole home, and it keeps running: no input needed, and it survives restarts.
- Use each light's own firmware effects (LIFX Flame, Morph, Move, waveforms; OpenRGB hardware modes) side by side with our own effects.
- Compute effects at each LED's real position in the home, so light moves through rooms the way it would through space.
- Let inputs drive looks without requiring them: tempo (Pro DJ Link or an internal clock), music (Music Assistant via Sendspin), Home Assistant.
- Ship all 29 looks from the brainstorm mockups, sliced from easy to hard.
- Serve the rebuilt web app's data contract (§10), where the home is the interface.

**Target:** this home and its current lights (§6.6).

**Out of scope for now:** a node-based editor (parameter bindings in M7 are the first step toward it), DMX and pixel-dense installs, other homes, GPU rendering, logging in to the Roborock cloud.

## 2. Milestones

Easy to hard. M2 is the foundation for everything after it. Each milestone also extends backup and restore to the data it adds.

| # | Milestone | Delivers | Looks |
|---|---|---|---|
| M1 | Set-and-forget | Firmware effects; looks as data (built-in and saved); zones with take-over, brightness, Off, Restart and Stop all, persisting and resuming; sharing policy; light status and the attention feed; LIFX capabilities from `products.json`; host-network deploy; minimal look picker | Firmware showcase |
| M2 | 3D fields | Home map (rooms, walls, windows, furniture, anchors, sub-zones, placements) seeded from this home, with placement guessing and confirmation; field-effect API; layer stack; zones as rooms, sub-zones, home and groups; zone frames with per-device slices; per-zone render horizon; preview runtimes and frame protocol v2; today's effects through a strip adapter; the PC as one light with parts | Sunset, Aurora, Lava, Color carousel, Ripples, Focus |
| M3 | Tempo | Always-running tempo clock (internal with tap and nudge, Pro DJ Link takeover, source lock); beat and bar index in the render context; deck info | Shockwave + beam, Scanner, 3D checker, Speaker waves (beat-driven) |
| M4 | Modifiers and transitions | Layer and look modifiers; cut, fade, wipe, spread, dissolve | — |
| M5 | Particles | Particle API; emitters, paths and targets that know where the lamps are | Fireflies, Embers, Rain storm, Snow, Spotlights, Beat bursts, Fountain, Vortex, Twin comets, Bouncing ball, Flock |
| M6 | Whole home | Whole-home zone; overlays; sun position; bedtime flow | Home sunset, Wisp, Goodnight |
| M7 | Live inputs | Sendspin visualizer; Home Assistant signals, triggers and control API; signal catalogue; parameter bindings | Room spectrum, Tide, Drop moment, Doorbell ripple; Speaker waves moves to real audio |
| M8 | Effects in space | The `fx` stream: particles, rings, planes and sun shafts drawn on the web app's stage | — |

That is 29 looks: 1 + 6 + 4 + 11 + 3 + 4.

**Web app:** built from the Claude Design handoff as a parallel track, F0–F11, on mocks first (§10). M1 still adds a minimal look picker to today's UI, so set-and-forget works before the new app is wired to the engine.

## 3. What Exists Today and What Changes

| Today | After |
|---|---|
| Effects render a 1D strip: `render(ctx: BeatContext, led_count)` | Effects render every LED of a zone at its 3D position; 1D effects keep working through a strip adapter |
| `SpatialCompositor` maps the strip onto devices with `LinearMapping` / `RadialMapping` | Removed, except inside the strip adapter |
| `EffectEngine.tick()` renders each `ScenePipeline` at `now + max_lookahead_s` (1 s) | Renders each zone at `now + horizon`; the horizon is the zone's slowest device latency plus one frame (~100–150 ms) |
| `BeatContext`: `beat_phase`, `bar_phase`, `bpm`, `dt` | `RenderContext` adds absolute time, beat and bar index, and signals, all sampled at the frame's target time |
| Global transport: STOPPED / PLAYING / SIMULATING; devices only receive frames while PLAYING | No global play. Assigning a look starts it; Off stops it. A global preview-only toggle replaces SIMULATING |
| Scenes with placements; activating a scene is refused while one of its devices is in another active scene | Zones on one home map; a device is in at most one active zone, and the newest assignment takes it over |
| LIFX types from hard-coded `MATRIX_PRODUCTS` / `MULTIZONE_PRODUCTS`; `led_count = tile_count * 64` | Capabilities from LIFX's `products.json`; matrix size from `StateDeviceChain` |
| OpenRGB devices forced into Direct mode | Direct mode for streamed looks; the device's own modes for firmware looks |
| Web UI: Live, Devices, Config and Scene pages; binary LED frames keyed by device name | A new web app built from the Claude Design handoff (§10); frame protocol v2 keyed by stable id, with a live/preview stream byte, up to 60 fps |
| Container on a bridge network, `--demo`, only `config.toml` mounted; Dockerfile and compose file untracked | Host networking, `state.db` on a volume, no `--demo`; files committed |

**Kept:** the Pro DJ Link listener and `BeatClock` drift correction, the ring buffer, per-device send loops and latency strategies, ghost/promote discovery, SQLite `state.db` as the runtime source of truth with TOML import/export, the event bus, and today's web pages until the new web app replaces them.

## 4. Architecture

### 4.1 Runtime

```
Inputs ──► TempoClock ─┐
           SignalBus ──┤
                       ▼
ZoneRuntime (one per active zone; preview runtimes render for the web app only)
  Look: layers + modifiers ── render(ctx at target time) ──► ring buffer
                                  (float RGB, every LED in the zone)
                                               │
LookaheadScheduler: per-device send loop ── frame at now + latency ──► device slice ──► adapter
Firmware layers ──► effect start/stop on the device (that device skips streaming)
```

- A **zone runtime** owns the look instance, the zone's `LedSet` (every LED of every device in the zone, in a fixed order), the zone's ring buffer, and each device's slice `[offset, offset + led_count)`.
- The engine renders each zone's frame for `now + horizon`. The horizon is the zone's largest device latency plus one frame, so reactive looks stay responsive while slow devices still get their frames in time. The ring buffer only needs to cover the horizon.
- Each device's send loop reads the frame nearest `now + its latency`, takes its slice, converts float RGB to the device format and sends it. Devices claimed by a firmware layer skip streaming.
- A **preview runtime** is a zone runtime whose frames go only to the web app's preview stream. The web app uses one to show a look before it starts and while it is being edited. It never sends to devices and never touches captured state.
- Colour stays float RGB through the whole layer stack and is clamped and converted once, at send.
- Everything stays on the single asyncio event loop. Budget: under 5 ms per zone frame on one core. No GPU: the planned Proxmox LXC has none, and the benchmark shows none is needed.
- From M8, effects can also describe what they draw in space (particle positions, rings, planes, sun shafts) for the web app's stage.

Benchmark (numpy on one 5800X3D core):

| LEDs | Sunset | Aurora | 500 particles | Worst frame |
|---|---|---|---|---|
| 412 (this home) | 0.36 ms | 0.71 ms | 1.28 ms | 2.47 ms |
| 2k | 0.49 ms | 0.94 ms | 7.0 ms | 9.26 ms |
| 10k | 1.09 ms | 1.91 ms | 32.7 ms | 36.9 ms |

Past about 2k LEDs, particles switch to a spatial grid.

### 4.2 Render Context

```python
@dataclass(frozen=True, slots=True)
class RenderContext:
    t: float                # absolute time (s) the frame will be shown
    dt: float
    beat_phase: float       # 0..1
    bar_phase: float        # 0..1
    bpm: float
    beat_index: int
    bar_index: int
    signals: SignalView     # values sampled at t (§7.3)
```

### 4.3 Zones and Assignment

- Zone kinds: room, sub-zone (inside a room, e.g. the Office desk), whole home, device group.
- A device belongs to at most one active zone. Assigning a look to a zone that overlaps active zones takes their shared devices over: the newest assignment wins. The other zones keep running on their remaining devices, or stop if none remain. The start response lists the take-overs, and the web app shows them before Start.
- Assigning a look starts it at once (with the look's transition) and saves a `ZoneAssignment` in `state.db`: the look, its settings, the zone's brightness and the start time. Off stops the look and restores each device's captured state. Stop all does that for every zone.
- Each running zone has a brightness (0–1) that scales its streamed frames and its firmware effects.
- A running zone is in one of five states: running, transition, slow, crashed, or waiting (its look needs an input that isn't there; §5.2). Restart re-creates a crashed zone's look.
- An **overlay** (M6) is a Home look that plays over every zone for a set time and then gets out of the way. The zones underneath keep running.
- Captured state is per device. It is taken when dj-ledfx first takes control of a device, kept through hand-overs between zones and across restarts, and released on Off.
- Preview-only is global: everything renders and streams to the web preview, and nothing is sent to devices. Turning it off sends the current state to the lights.

## 5. Effect Model

### 5.1 Three Effect Kinds

```python
class FieldEffect(Effect):
    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB: ...   # (N, 3) float32, vectorised numpy

class ParticleEffect(Effect):
    def step(self, ctx: RenderContext) -> None: ...                       # advance state with a seeded RNG
    def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB: ...

class FirmwareEffect(Effect):
    def supports(self, caps: DeviceCapabilities) -> bool: ...
    async def start(self, adapter: DeviceAdapter, params: Params) -> None: ...
    async def stop(self, adapter: DeviceAdapter) -> None: ...
    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB: ... # preview and fallback
```

`LedSet` is built once per zone and rebuilt when placements change:

- `pos` (N, 3): position in metres on the home map's axes (x east, y south, z up; §6.1)
- `npos` (N, 3): position normalised to the zone's bounds (0..1)
- `room`, `device` (N,): integer ids
- `anchors`: name → (3,) position (e.g. TV, sofa, speakers, coffee table)
- the per-device slices

**Particles:** capped at about 500, with a seeded RNG so runs repeat. Emitters, paths and targets can be anchors or lamps: comets follow a path through lamps, spotlights visit lamps, embers rise from lamp bases. Particles light LEDs by distance falloff; past about 2k LEDs a spatial grid keeps the lookup cheap.

**Firmware:** LIFX Flame and Morph (tile effect), Move (multizone effect) and waveforms (single bulbs); OpenRGB hardware modes. Govee is streamed only. If a device doesn't support the requested firmware effect, or rejects it, the layer streams `emulate()` to that device instead. `emulate()` is also what the preview shows. In M1, before the home map exists, a zone's `LedSet` comes from each device's own geometry (its matrix or strip layout).

**Today's 1D effects** (beat pulse, breathe, color chase, fire storm, rainbow wave, strobe) become fields through a strip adapter: each LED's position is projected onto an axis, linear or radial like today's mappings, and samples the 1D render.

### 5.2 Looks

A look is data in `state.db`; effects are code in the registry. The 29 mockup looks ship as built-ins.

```json
{
  "id": "sunset",
  "name": "Sunset",
  "category": "ambient",
  "scope": "any-zone",
  "needs": [],
  "uses": [],
  "builtin": true,
  "derived_from": null,
  "starred": false,
  "description": "Warm at the floor to deep blue at the ceiling; the Candles run Flame.",
  "thumbnail": "sunset",
  "default_zone": "living_room",
  "layers": [
    {"kind": "field", "effect": "sunset_gradient", "params": {"level": 0.85}, "blend": "normal", "opacity": 1.0},
    {"kind": "firmware", "effect": "lifx_flame", "devices": ["candle-1", "candle-2", "candle-3"], "params": {}}
  ],
  "modifiers": [],
  "transition": {"kind": "fade", "seconds": 2.0}
}
```

- Layers composite bottom to top in float RGB. Blend modes: normal, add, screen, multiply, max. A firmware layer claims its devices; streamed layers skip them.
- Categories: ambient, tempo, audio, home, firmware. `needs` lists the inputs a look can't run without (music, home-assistant, sun); a zone whose look needs a missing input waits dark and starts when the input arrives. `uses` lists inputs a look follows when they're present and does without otherwise. Tempo is always available, from the internal clock at worst. `scope: whole-home` pins Home looks to the whole-home zone.
- The built-ins keep the ids, names, descriptions and thumbnail ids of the handoff's `docs/design/web-app/looks.json`. They are never overwritten: saving an edit creates a new look ("Mine") with `derived_from` set. Any look can be starred.
- The settings schema (`EffectParam`) gains `anchor` (a named home-map point), `point` (any xyz position), `zone`, `device_set` (device ids or a selector such as `type:candle`) and `range` (a low–high pair, e.g. a height band), alongside today's float, int, color, color_list (palettes), bool and choice. Each setting says whether it can be bound to a signal (§7.5).

### 5.3 Modifiers and Transitions (M4)

- **Layer modifiers:** mask (height band, room, sub-zone, or distance from an anchor), mirror (across a plane), transform (translate, rotate or scale the field's space).
- **Look modifiers:** trails (per-LED decay), downbeat flash, brightness cap (also caps firmware devices), evening (warmer and dimmer from an hour before sunset to the end of civil twilight, off again at sunrise).
- **Transitions:** cut; fade; wipe (a plane sweeps across the zone); spread (outward from an anchor); dissolve (per-LED random threshold). Firmware devices switch at the transition's midpoint. During a transition the zone renders both looks, so both count against the frame budget.

## 6. Home Map and Devices

### 6.1 Home Map

One map in metres on the plan's axes, matching the web app's data contract: x is east, y is south, z is up, with the origin at the north-west corner of the home's bounds. The web app's three.js stage maps (x, y, z) to (x, z, y). A stored north offset says where true north is; 0 means straight up the plan.

- **Rooms:** id, name, Home Assistant area, outline (an x/y polygon), floor and ceiling height, label position.
- **Walls:** segments with thickness, marked exterior or interior, with openings (door or window, the extent along the wall, sill and head height). The bedroom's west windows are flagged west-facing, for the sun.
- **Structure:** columns and ceiling beams (with the beams' bottom height).
- **Furniture:** named boxes with a height (sofa, coffee table, TV console, TV, speakers, bed, desk, counter, table), so rooms are recognisable on the stage. The owner can edit them.
- **Sub-zones:** named polygons inside a room with an optional Home Assistant area (the Office desk, the kitchen counter).
- **Anchors:** named 3D points that looks reference (TV, sofa, speakers, coffee table, …). An anchor can hold more than one point, like the speaker pair.
- **Placements:** device → shape (point, line, bent line, cylinder or grid; OpenRGB key maps become grids), position, rotation (turn, tilt, roll), size, LED order, and whether the owner has confirmed it.

Placement guessing spreads unplaced devices around their rooms, unconfirmed. Moving a light doesn't confirm it; confirming is explicit. The map lives in `state.db` and joins backup and restore.

### 6.2 Seeding This Home (M2)

A one-off script, `scripts/import_home.py`, builds this home's map; rerun it if the vacuum remaps. Its inputs stay out of git because they describe the home:

1. The Roborock map from Home Assistant's cached copy (`/config/.storage/roborock/<entry_id>`). Home Assistant only writes that cache when the integration unloads, so press Reload on the Roborock integration first. The script checks the cache's age. No cloud login.
2. The owner's partial 3D model (`apartment.abc`), converted once to JSON with Blender's Python module, for exterior walls, windows, columns, beams and heights.
3. Two lines the owner drew: the bedroom/bathroom wall, and the kitchen counter front (the kitchen wall stands 25″ behind it).

The method was prototyped during brainstorming; the prototype lives in `.superpowers/brainstorm/1505004-1790196208/home-import/` (gitignored). The prototype's plan runs y north from a south-west origin; the script converts it to the map's axes (§6.1).

- **Registration:** try 8 orientations of the vacuum map with FFT cross-correlation, then polish to sub-pixel accuracy by maximising "floor inside the walls" and "lidar on the walls". Result: a 180° rotation, so the top of the vacuum map is north.
- **Exterior walls:** a model wall moves out only where the robot's floor goes past it. Straight lidar lines inside a room are furniture, not walls; the owner confirmed this for the corridor and the living room. Corrections applied to the model: the courtyard is 0.5 m deeper (the north wing moved north); the diagonal wall is 12.5° (the model had 9.4°); the sunroom's west end moved 36 cm out; the east wall moved 10–15 cm out.
- **Interior walls:** the owner's lines, refined by lidar (the bedroom wall sits 6 cm east of the drawn line). Bathroom | wardrobe and wardrobe | corridor come from lidar. Doors go where the robot drives through: bedroom → kitchen, bedroom → bathroom, bathroom → wardrobe. Open-plan boundaries follow the Roborock room split.
- **Furniture, anchors and first placements:** taken from the handoff's `docs/design/web-app/home.json`, which estimated them from the floor plan, and registered onto the imported outline. All start unconfirmed.
- **Result:** Living room 30.2 m², Bedroom 24.7, Kitchen 17.8, Corridor/Entrance 11.0, Wardrobe 9.4, Bathroom 8.2, Study 8.2, Sunroom 6.1. Sub-zones: the Office desk (along the Bedroom's south wall) and the kitchen counter. Heights: ceiling 3.35 m, beams down to 3.10 m. Windows: 11, plus the balcony door, all from the model.
- The model's compass labels are 180° off (it calls the bedroom's west windows "east"); the map ignores them.

### 6.3 Devices and Capabilities

- **LIFX:** capabilities come from a vendored copy of LIFX's `products.json` (colour, temperature range, multizone, extended multizone, matrix, chain) instead of hard-coded product sets. Matrix size comes from `StateDeviceChain` instead of 64 LEDs per tile.
- **OpenRGB:** Direct mode for streamed looks; the device's own modes for firmware looks. The PC's OpenRGB devices (keyboard, RAM, GPU, motherboard, mouse) appear in the web app as one light with parts, from M2 (in M1 each is its own light). Each part keeps its own adapter, latency and LED order, and can be placed on its own; by default the parts share the PC's placement.
- **Govee:** streamed only.
- **Status**, for the web app: streaming, running its own effect, streamed copy, offline, switched off elsewhere, or idle (not in a running zone, with its current power and colour). Switched off elsewhere means reachable but powered off. A light cut at the wall switch is unreachable, so it shows as offline.
- **Detail**, for the Devices page: model, address, MAC, firmware version, LED count and parts; measured, estimated and overridden latency with a 60 s history; send rate; dropped frames; the last scan time.

### 6.4 Sharing Policy

- dj-ledfx turns lights on only when a look is applied, never on restart.
- A light switched off elsewhere drops out of its zone (power is polled every 5 s) and rejoins when it is switched back on.
- While a look runs, colours set elsewhere are overwritten. Firmware looks are sent again if something else stopped them, but only while the light is on.
- Lights that aren't in a running zone are idle. dj-ledfx reads their power and colour every 30 s, so the web app can show them as they are, and never changes them.
- An offline light needs attention only after 2 minutes offline, and only while it belongs to a running zone.

### 6.5 Migration

Existing scenes migrate once, in two steps:

- **M1:** each scene becomes a device-group zone, so looks can be assigned before the home map exists.
- **M2:** each placement moves onto the home map. It keeps its geometry and rotation; its position is offset from its room's centre by its scene-relative position and left unconfirmed until it is confirmed in the editor.

### 6.6 This Home's Lights

Home Assistant devices (19) by room:

- **Living room:** Right Corner Lamp, Left Corner Lamp (no Home Assistant area yet), Rope, Ikea Lamp 1–3, Candle 1–3 (LIFX Candle Color), Right Lamp (LIFX Mini Color), TV Lamp (LIFX Tube)
- **Kitchen:** Corner Lamp (Govee H6076), Floor Lamp (LIFX Mini Color)
- **Bedroom:** Bed Left, Bed Right (LIFX A19)
- **Office (desk sub-zone in the Bedroom):** Desk Left, Desk Right (LIFX A19); PC via OpenRGB: Vengeance RGB Pro DDR4 ×4 (10 LEDs each), Vengeance RGB ×2 (1 each), SteelSeries Apex Pro TKL (112), MSI RTX 4090 Suprim Liquid X (1), Razer Basilisk V3 Pro (13), ASUS ROG Crosshair VIII Hero (8)
- **Corridor (Home Assistant: Entrance):** Neon Indoor (LIFX Neon)
- **No lights:** Study, Sunroom, Bathroom, Wardrobe

### 6.7 Deployment (M1)

- Commit the Dockerfile, compose file and `.dockerignore`.
- `network_mode: host` (LIFX broadcast discovery and Pro DJ Link need it), `restart: unless-stopped`, `state.db` on a volume, `config.toml` mounted, no `--demo`.
- With host networking, the web port is governed by the host firewall (UFW) rather than Docker's published-port rules. Check LAN reachability before switching, and ask before changing UFW.

## 7. Inputs and Always-On

### 7.1 Always-On (M1)

- Each zone's look is saved in `state.db`, with its settings, brightness and start time, and resumes on start. Lights that are off stay off (§6.4).
- Firmware looks are sent again after a restart, or if something else stopped them, but only while the light is on.
- Off puts each light back how it was before the look started. That captured state is saved, so Off still works after a restart.
- Offline devices keep their place in their zone as ghosts and rejoin when rediscovered, as today.

### 7.2 Tempo Clock (M3)

- One `TempoClock`, always running. Sources, highest priority first: Pro DJ Link, beats from the music when beat detection is confident (M7), then the internal clock (a BPM field, tap tempo and nudge). A source lock, Auto by default, can pin one source.
- Tapping sets the internal clock and holds it until a higher source starts again.
- When a source takes over, the phase snaps once; after that, drift uses today's soft (under 5 ms) and hard correction. A source that goes quiet for about 2 s hands back, and the clock carries on at the last BPM and phase without a jump.
- Effects read beat and bar phase and index from the render context, sampled at the frame's target time.
- For the web app: each Pro DJ Link deck's player number and name, BPM and pitch, and the tempo master where the packets allow (§11).

### 7.3 Signals (M6–M7)

- A `SignalBus` collects named, timestamped values (scalars or small arrays) from inputs. `ctx.signals` samples them at the frame's target time, interpolating between samples. Stale signals ease to neutral (loudness fades to 0 over about 1 s) so reactive looks settle instead of freezing. An input is stale when it stops updating while it should (music: 10 s while playing).
- A catalogue lists every signal with its live value, where it comes from and which looks or bindings use it (e.g. `beat.phase`, `bpm`, `loudness`, `spectrum.bass`, `onset.kick`, `doorbell`, `bedtime`, `sun.elevation`, `time.evening`).
- **Sun (M6):** azimuth and elevation are computed locally from the location (Home Assistant's config once connected, otherwise `config.toml`) and the home map's north offset. Home sunset starts at the bedroom's west windows.
- **Music (M7):** a Sendspin client in the `visualizer@v1` role joins Music Assistant and receives loudness, beat, peak frequency, spectrum and peaks. The data is timestamped in server time and sent ahead of playback, which suits rendering ahead. Kick, snare and hi-hat onsets are derived from the spectrum; now playing and the player group come from Music Assistant. A spike comes first: confirm the Music Assistant server's Sendspin version supports the role (an earlier LedFx attempt hit an aiosendspin version mismatch).
- **Home Assistant (M7):** entity states the owner chooses (music playing, a bedtime boolean, the doorbell), read over Home Assistant's WebSocket API with a dedicated long-lived token.

### 7.4 Triggers and Control from Home Assistant (M7)

Simple triggers live in dj-ledfx: the owner picks the entities, and Home looks start from them as overlays (the doorbell plays Doorbell ripple over everything for 8 s; bedtime starts Goodnight). Anything more involved stays in Home Assistant automations, which call REST actions through `rest_command`: set a look on a zone, turn a zone off, set brightness, and play a timed overlay.

### 7.5 Parameter Bindings (M7)

Any bindable look parameter can follow a signal: `{signal, in: [lo, hi], out: [lo, hi], smoothing_s, curve}`, where the curve is linear or ease. Examples: Aurora's speed follows loudness; Sunset's warmth follows the sun's elevation. Every look becomes reactive without new effects, and this is the first step toward the deferred node editor.

## 8. Error Handling

- **A look raises or produces NaN:** that zone holds its last good frame, the look is marked crashed, and the error is logged once (rate-limited). Other zones keep running. Restart re-creates the look; Off restores the lights.
- **A zone runs slow:** render time is measured per zone. A zone that keeps exceeding its 5 ms budget drops to a lower frame rate, so it cannot stall the shared event loop. It shows as slow while it stays below 80% of the target frame rate for 30 s.
- **Devices:** offline devices become ghosts and rejoin on rediscovery, as today. A rejected firmware command falls back to streamed emulation. If a device's state could not be captured, Off leaves that light alone rather than guessing.
- **Inputs:** if Pro DJ Link drops, the clock carries on at the last tempo. Sendspin and Home Assistant reconnect with backoff, and their signals ease to neutral meanwhile.
- **Data:** a bad or missing home map, or a bad look, never crashes the app. It starts with what it has and reports the problem.
- **Attention feed:** the server derives one list, so every screen agrees. Items: a light offline (§6.4), a zone crashed, a zone slow, an input disconnected, an input stale while something depends on it, a device dropping more than 5% of its frames for a minute. Switched off elsewhere, no DJ and nothing playing are never attention items.

## 9. Testing

- **Looks:** a sweep over all 29 presets checks that every look stays finite and in range, outputs the right shape, and repeats exactly with a fixed seed. Each effect also gets a few behaviour checks, e.g. "Sunset is warmest at its anchor" and "a ripple reaches LEDs in order of distance". No pixel-exact reference images; they would break on every tuning change.
- **Performance:** a benchmark test on this home's 412-LED map asserts each zone renders in under 5 ms. It is marked as a performance test and run locally.
- **Clock:** source takeover and source loss, driven by fake time.
- **Pipeline:** today's end-to-end test (simulated beats → pipeline → mock devices) extends to zones on the home map: each device must receive its own slice at its target time, allowing for its latency.
- **Preview:** preview runtimes never send to devices and never change captured state.
- **Sharing and resume:** fake lights report their power state; the app "restarts" on the same database. Assert that looks resume, that lights drop out and rejoin, and that no power-on command is ever sent on restart.
- **LIFX effect commands:** checked against recorded packet bytes, like the existing protocol tests in `tests/fixtures/`.
- **API contract:** the web app generates its types from FastAPI's OpenAPI schema, so the schema is the contract. Frame protocol v2 has encoder tests here and decoder tests in the web app.
- **Sendspin, Home Assistant and the REST API:** fake Sendspin and Home Assistant servers; REST tests with `httpx`.
- **Each milestone** ends with a short checklist run on the real lights; preview-only mode allows a dry run first.
- **Gates stay as today:** `ruff check`, `ruff format --check`, `mypy` strict and `pytest` for the backend; `tsc --noEmit` and the build for the frontend. The web app's own tests are in its spec (§14 there).

## 10. Web App

- **Source of truth:** the Claude Design handoff. [`2026-09-23-web-app-rebuild-design.md`](2026-09-23-web-app-rebuild-design.md) covers behaviour, structure and the data contract; `docs/design/web-app/` holds the tokens, icons, `looks.json`, `home.json` and the reference renders. The renders stay out of git; `HANDOFF.sha256` pins every design file, renders included. The web app and the engine use these files as they are, with tests that fail if a copy drifts (CLAUDE.md, "Web app design").
- **The engine serves the handoff's data contract** (its §12: domain types, REST under `/api`, WebSocket v2 and frame protocol v2), plus an `idle` light status (§6.3) that the handoff's `LightStatus` lacks. Where this spec and the contract name the same thing differently, the contract's name wins.
- **Two tracks.** The handoff's frontend milestones run alongside the engine as **F0–F11** (its M0–M11, renamed so they don't collide with M1–M8). They start on mocks and switch to the real API as the engine delivers it:

| Web app | Needs from the engine |
|---|---|
| F3 Live; F6 Devices | M1: zones, take-over, brightness, Off, Stop all, light status, attention; M2: the PC as one light with parts (F6) |
| F4 Put a look on | M1 zones; M2 preview runtimes and frame protocol v2 |
| F7 Home map | M2 home map |
| F8 Look editor | M2 layers; M4 modifiers and transitions; M7 bindings |
| F6 Inputs | M3 tempo; M6 sun; M7 Music Assistant, Home Assistant and signals |
| F10 Effects in space | M8 |

- **Beside, not instead:** the new app lives in `web/` and is served at `/next` until it reaches parity. Today's UI keeps working, including M1's look picker, and every F milestone merges to `master` on its own, with no stacked branches. The cut-over (F11) deletes `frontend/` and the old endpoints. This replaces the handoff's "delete `frontend/src`" in F0.
- **The handoff's open questions** (its §15):
  1. LED counts, models and positions in `home.json` are estimates. Discovery and the home map supply the real ones.
  2. The location comes from Home Assistant's configuration; the handoff assumed Dallas.
  3. Its proposed behaviours are adopted: tapping holds Internal until a higher source returns; a crashed look holds its last frame; stale music hands the clock back down the chain; "Place them roughly for me"; a tempo source lock; latency override as Auto or Set; slow means below 80% of the target frame rate for 30 s.
  4. Switched off elsewhere versus offline: §6.3 and §6.4.
  5. Evening timing: §5.3.

## 11. Risks and Open Questions

1. **Sendspin compatibility:** the Music Assistant server may not offer `visualizer@v1` in a version aiosendspin can talk to. A spike opens M7.
2. **Firmware effects per device:** Flame and Morph on the Candles and Tube, and Move on the Neon, need checking on the real lights in M1.
3. **Host networking and UFW** (§6.7).
4. **Home Assistant's recorder:** its LIFX integration will record colour changes while looks run. Exclude those entities from the recorder if the database grows.
5. **Stale Roborock cache:** it is only refreshed when the integration is reloaded; the import script checks its age.
6. **Particle cost past 2k LEDs:** not an issue at this home's 412 LEDs.
7. **Pro DJ Link deck state:** passive mode hears beat packets only. Deck state (cued, playing) and the tempo master come from status packets, which need a virtual CDJ, so until then the decks show what beat packets carry.
8. **Two tracks drifting apart:** the OpenAPI-generated types turn contract drift into a build error in the web app, and the mocks must change with every contract change.
