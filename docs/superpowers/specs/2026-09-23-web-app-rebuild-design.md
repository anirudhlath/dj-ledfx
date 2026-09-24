# dj-ledfx Web App Rebuild: Design Handoff

**Status:** approved design, ready to plan · **Direction:** A, "Dollhouse" · **Date:** 2026-09-23
**Replaces:** the whole of `frontend/` (built from the ground up, not refactored)
**Design canvas (owner only):** https://claude.ai/artifact/TRmujo6qFt3PskpnS8y33z
**Reference renders in this repo:** `docs/design/web-app/reference/*.png` and `*.html` (open the HTML in a browser; artboard links work)
**Design assets:** `docs/design/web-app/tokens.css`, `icons.ts`, `home.json`, `looks.json`

---

## 0. How to use this document

This spec is written for Claude Code. It is the source of truth for **behaviour, structure and data**. The reference renders are the source of truth for **look and layout**. When they disagree on behaviour or copy, this document wins. When they disagree on pixels, the renders win, except for the 3D stage (section 7): the renders draw it as SVG approximations, and the real one is a three.js scene built to the numbers in 7.

Follow the repo workflow in `CLAUDE.md`: turn this into implementation plans under `docs/superpowers/plans/` (one per milestone in section 13), run the code-architect and simplify review steps on each, and open one PR per milestone.

Everything the owner has not confirmed is listed in section 15. Don't invent answers for those; build them behind the typed data layer so they're cheap to change.

---

## 1. What we're building

dj-ledfx is a self-hosted lighting engine that runs **looks** across every smart light in one apartment, 24/7, from a home server. Effects are computed in 3D: every LED has a real position in the home, so light moves through rooms the way it would through space. It started as a DJ tool synced to Pioneer Pro DJ Link. Now DJing is just one input.

The web app is an **instrument for playing light through a real home, not a settings panel.** One person uses it: the owner, mostly at a desktop browser, and on a phone for quick changes from the sofa.

### 1.1 Jobs, in priority order

1. Put a look on a room, or the whole home, and walk away. It keeps running, even after restarts.
2. See at a glance what's running where, and every light's live colour.
3. Browse and preview looks, tweak one and save it as a new look.
4. Place lights in the 3D home and fix their positions.
5. Check on devices and inputs: health, latency, tempo, music, Home Assistant.

Layout, navigation weight and performance budgets follow this order. Job 1 must take seconds on both desktop and phone.

### 1.2 Moments the design is built around

These are the acceptance tests for "does it feel right". Each has a reference render.

| Moment | Where to see it |
|---|---|
| A sunset starts at the bedroom's west windows and follows the real sun across the apartment | `Main.png` (sun shafts through the three west windows) |
| Tapping a tempo and watching every lamp land on the beat | `Phone-Tempo.png`, tempo module everywhere |
| The doorbell sends a golden ring from the front door through every room | `Live-Doorbell.png` |
| Fireflies drift through the living room; each lamp glows only as one passes | `Main.png`, `Look-Editor.png`, `Phone-Zone.png` |

### 1.3 Non-goals

- Authentication or multiple users. LAN only, one owner.
- A light theme. The app is dark only (it's used in dark rooms, and a dark ground keeps light colours true).
- Internationalisation. English copy, 24-hour clock, metric units.
- Replacing Grafana/Prometheus monitoring. The app shows health that matters to the owner; deep metrics stay in Grafana.
- Protocol work (LIFX, Govee, OpenRGB, Pro DJ Link drivers). The app consumes what the engine exposes.

---

## 2. Design principles

1. **The only colour is light.** The interface is neutral warm greys. Every chromatic pixel on screen is a light's real, current colour, so the owner can trust what they see. There is exactly one UI colour, `signal` (orange), and it only ever means "this needs you".
2. **The home is the interface.** The 3D home (the "stage") is the main surface. Rooms are clickable, lights show their live colour at their real position, and effects are drawn in the space where they happen.
3. **Always within reach.** Tempo, preview-only and "needs attention" sit in the top bar (desktop) or header (phone) on every screen.
4. **Preview before commit.** Choosing a look renders it on screen first. The lights keep running what they were running until you press Start.
5. **Honest states.** Every light, zone and input shows its real state with the same visual vocabulary everywhere (section 9). Nothing is hidden and nothing is alarming unless it needs action.
6. **The app never turns lights on by itself.** Only starting a look does. "Off" puts each light back how it was.

---

## 3. What gets replaced

### 3.1 Delete

Delete everything under `frontend/src/` (pages, components, hooks, lib) and the shadcn/ui generated components. Nothing is carried over as code. Useful knowledge from the old code is captured below.

### 3.2 Keep (stack)

| Keep | Why |
|---|---|
| Vite 8, React 19, TypeScript 5.9 (strict) | Same toolchain the repo already builds and serves |
| Tailwind CSS v4 (CSS-first `@theme`) | Tokens in `docs/design/web-app/tokens.css` are written for it |
| three, @react-three/fiber 9, @react-three/drei | The stage (section 7) |
| react-router 7 | Routing (section 4) |
| @base-ui/react | Headless, accessible primitives (popover, dialog/sheet, slider, switch, select, tooltip, tabs). We style them ourselves |
| FastAPI static serving + SPA fallback in `web/app.py`, Vite dev proxy for `/api` and `/ws` | Unchanged |

### 3.3 Drop or add

| Change | Notes |
|---|---|
| Drop shadcn component copies, `lucide-react`, `next-themes`, Geist font, `sonner` | Own primitives on base-ui; own icon set (`icons.ts`); dark only; fonts per tokens; own toast |
| Add `@fontsource/instrument-sans`, `@fontsource/instrument-serif`, `@fontsource-variable/jetbrains-mono` | Self-hosted fonts (the server may have no internet) |
| Add `zustand` | Live stores (beat, frames, zones, inputs, attention) read outside React render at 60 fps |
| Add `@tanstack/react-query` | REST cache, invalidation after mutations |
| Add `openapi-typescript` (dev) | Generate API types from FastAPI's `/openapi.json` so the UI can't drift from the backend |
| Add `msw` (dev) | Mock REST + a mock WebSocket so UI work isn't blocked by backend work (section 12.5) |
| Add Playwright (dev) and `@axe-core/playwright` | Visual and accessibility checks (section 14) |

### 3.4 Old concepts to new concepts

| Old UI / engine concept | New UI concept | Notes |
|---|---|---|
| Transport PLAYING / STOPPED | Zones running / "Stop all" | The owner never sees "transport". Running looks are the state |
| Transport SIMULATING ("renders to web UI only, skips send_frame") | **Preview only** (global) | Same semantics. Build the switch on this |
| Effect + params, EffectDeck | **Look** (layers + modifiers + transition) | 29 built-in looks (`looks.json`) |
| Presets | **Mine**: saved variations of a look | "Save as new look" |
| Scenes / pipelines (activate, deactivate, per-scene effect) | **Zones** (room, sub-zone, whole home, custom group) | Overlap rule changes: see 11.3 |
| Device groups (with colour) | Rooms and custom zones | Group colours are gone (colour belongs to light) |
| Scene editor, linear/radial mapping | **Home map** (3D placement, anchors, sub-zones) | Mappings are retired; looks are 3D fields |
| Config page | **Settings** | |
| Device monitor | **Devices** + the live stage | |
| `/api/state/export`, `/api/state/import` | **Backup / Restore** | Must include looks, zones, map, devices, inputs, settings |

### 3.5 Parity checklist (must not be lost)

- Identify (blink) a light · latency override per light · remove a light · discover / scan for new lights
- Export and import of everything (backup/restore)
- Live per-LED colour from the binary frame stream
- Beat position, BPM, pitch-adjusted tempo from Pro DJ Link, deck number
- Per-device send rate, effective latency, dropped frames, connection status

---

## 4. Information architecture and routes

### 4.1 Desktop navigation

A 72 px **rail** on the left (logo, then Live, Looks, Map, Devices, Inputs, Settings; a signal dot on Devices or Inputs when something there needs attention). A 60 px **top bar** on every screen: page title and context on the left; on the right, the always-within-reach cluster: **tempo module**, **Preview only** switch, **Needs attention** button, **connection** indicator.

### 4.2 Phone navigation

A header (page title in serif, context line; right side: preview-only eye button, needs-attention button, and a reconnect indicator when disconnected), a **tempo strip** under it on Live, and a bottom **tab bar**: Live, Looks, Devices, Tempo, Settings. The home map is reached from Devices (its phone job is confirming guessed positions). Leave the top 47 px to the OS (use `env(safe-area-inset-top)`); never draw a fake status bar.

### 4.3 Routes

| Route | Desktop | Phone | Reference |
|---|---|---|---|
| `/` | redirect to `/live` | same | |
| `/live` | Stage + Running panel | Header, tempo, stage, zone cards, sticky "Put a look on" | `Main`, `Phone-Live` |
| `/live/put` `?zone=&look=` | Right panel becomes the composer; stage previews | Bottom sheet over a focused stage | `Live-PutLookOn`, `Phone-PutLookOn` |
| `/live/zones/:zoneId` | (desktop uses the card in the panel) | Zone detail | `Phone-Zone` |
| `/looks` `?cat=&q=` | Library, all 29 by category | Starred first, 2-column grid | `Looks`, `Phone-Looks` |
| `/looks/:lookId` | Look editor | Tweak (key settings only) | `Look-Editor`, `Phone-LookTweak` |
| `/map` `/map/:thingId` | Outliner, stage in edit mode, inspector | Confirm a guessed light | `Home-Map`, `Phone-Map` |
| `/devices` `/devices/:deviceId` | Table grouped by room, inline expanded row | List grouped by attention then room | `Devices`, `Phone-Devices` |
| `/inputs` | Tempo, Pro DJ Link, Music Assistant, Home Assistant, Signals | "Tempo" tab: BPM, TAP, decks | `Inputs`, `Phone-Tempo` |
| `/settings` `#output|home|inputs|lights|backup` | Section nav + form + backup card | Grouped list | `Settings`, `Phone-Settings` |

URL state: the composer's zone and look, the looks filter and search, the selected map object and the expanded device row live in the URL so reload and back work.

### 4.4 Breakpoints

| Width | Layout |
|---|---|
| < 768 px | Phone layouts (designed at 390 × 844) |
| 768–1199 px | Desktop structure, collapsible right panel (overlays the stage), rail stays |
| ≥ 1200 px | Desktop (designed at 1440 × 900). The stage is fluid; side panels are fixed widths |

---

## 5. Visual system

All values are in `tokens.css`. The System artboard (`reference/System.png`) shows them assembled.

### 5.1 Colour

| Token | Hex | Use |
|---|---|---|
| `bg` | `#0d0c0b` | Page, stage |
| `panel` | `#131210` | Side panels, sheets |
| `raised` | `#1a1916` | Cards, popovers, tooltips |
| `control` | `#24221f` | Inputs, secondary buttons, active nav item |
| `control-hover` | `#2e2c28` | Hover, slider track, tempo pips at rest |
| `line` / `line-soft` / `line-strong` | `#2a2824` / `#1f1d1a` / `#3a3732` | Borders / dividers / popover and outline-button borders |
| `text` | `#f2eee6` | Primary text; the primary button's fill |
| `text-2` | `#b3ada2` | Secondary text (about 9:1) |
| `text-3` | `#8a857b` | Tertiary text (about 5:1), never below 11 px |
| `signal` | `#ff6b3d` | Needs attention: offline lights, crashed looks, slow zones, stale or disconnected inputs. Nothing else |
| `tape` | stripes of `text` and `bg`, 135°, 9 px | Preview only. Nothing else |

Rules:
- Never tint UI chrome with a hue. Selection is a white outline; the primary button is off-white on dark.
- A light's colour in the UI is always its live colour, lifted for legibility only as specified in 7.4 and 6.6.
- The doorbell overlay card (`Live-Doorbell`) uses the ring's gold because it is showing the look's colour, not a UI accent.

### 5.2 Type

Three families, all self-hosted.

| Role | Family | Sizes |
|---|---|---|
| Display: look names, page heads, empty states, room names in detail views | Instrument Serif 400 | 64, 56, 40, 30 (zone card), 26 (compact/phone), 20 (grid) |
| UI | Instrument Sans 400–700 | 17/600 page title, 15/600 section, 13.5 body, 13 controls, 12 meta, 11/600 caps labels (tracking 0.09em) |
| Numbers: BPM, latency, fps, times, coordinates, hex | JetBrains Mono, tabular | 80 (phone BPM), 64 (inputs BPM), 20 (tempo module), 12.5 (data) |

Look names are always serif. Room and zone names in lists are sans 12.5/600. On the stage, room labels are 9.5 px sans caps with the running look beneath in 15 px serif italic.

### 5.3 Space, radii, elevation

4 px spacing base. Radii: chip 6, control 8, tile 10, card 12, panel 14, sheet 20, pills fully round. Only floating things have shadows (`shadow-pop` for popovers and dialogs, `shadow-tip` for tooltips, `shadow-sheet` for phone sheets). Everything else is separated by borders and surface steps.

### 5.4 Motion

- **Beat-synced motion must follow the real beat clock**, never a CSS timer. The mocks use CSS keyframes at 121.8 BPM only as a stand-in. Extrapolate beat phase on the client from the last `beat` message (`bpm`, `beat_phase`, server timestamp) every animation frame and write it to a CSS variable or a ref.
- Tempo pips: the current beat's pip lights to `text` with a soft glow at the beat and fades back to `control-hover` by the end of that beat. The downbeat pip is wider (14 px vs 10 px).
- UI transitions: 120 ms (hover, press), 200 ms (panels, chips), 320 ms (sheets). Ease-out for entering, ease-in-out for moving.
- Look thumbnails animate continuously (they are how you "see them move before choosing"). Pause thumbnails that are off screen.
- `prefers-reduced-motion`: stop particles, beat pulses, thumbnail loops and live-dot pulses. The stage still updates light colours, at most once per second.

### 5.5 Icons

`icons.ts` holds 65 icons drawn for this app: 24 px grid, 1.6 stroke, round caps and joins, `currentColor`. Build one `<Icon name size />` component. Icon-only buttons always get an `aria-label`. Use the names as given; don't mix in another icon library.

### 5.6 Tape (preview only)

When preview only is on, the whole app window gets a 6 px (phone 5 px) tape frame on all four edges, the top-bar switch track turns to tape, the Running panel header gets a 6 px tape bar, and the stage shows a label: **PREVIEW ONLY · Everything renders here. Nothing is sent to the lights.** with a "Send to lights again" button. It must be impossible to miss. See `State-Preview-Only.png`, `Phone-State-Preview-Only.png`.

---

## 6. Components

Build these as the design system (`src/design/`). Props below are the minimum; types come from section 12. Every interactive element is a real `<button>`, `<a>`, `<input>` or base-ui primitive. Touch targets are at least 44 px on phone.

### 6.1 Primitives

| Component | Spec |
|---|---|
| `Button` | Variants: `primary` (text fill, on-text label), `secondary` (control fill, line border), `outline` (transparent, line-strong border), `ghost` (transparent, text-2), `danger` (transparent, signal text, signal-line border). Sizes: sm 30 px, md 36 px, lg 48 px (phone CTA 52 px). Radius 8. Label 12.5/13.5/15, weight 600. Optional leading icon (16/18 px) and trailing icon. Renders as `<a>` when it navigates |
| `IconButton` | 32 px desktop, 44 px phone, radius 8, control fill; `active` inverts to text fill |
| `Switch` | 34 × 20 track; knob 14 px. Off: control-hover track, text-2 knob. On: text track, on-text knob. `tape` variant: tape track when on. `role="switch"` |
| `Slider` | 4 px track, filled part `text`, rest `control-hover`; 14 px `text` thumb with 3 px bg ring; value in mono 12 text-2 on the right. Real range input |
| `Segmented` | Container raised + line border, radius 8, 2 px padding; active item control-hover fill, text; others text-3 |
| `SelectTrigger` | 32 px, control fill, line border, radius 8, value + chevron. Opens a base-ui select or popover list |
| `Field` | Label 11.5 text-3 above; 32 px box; mono value; optional unit suffix text-3 |
| `Chip` | 22 px, radius 11, 11.5/600, optional 13 px icon. Variants: `input` (control fill, text-2), `mod` (outline, text-2), `quiet` (outline, text-3), `signal` (signal-bg, signal text, signal-line), `solid` (text fill) |
| `Label` | 11/600 caps, tracking 0.09em, text-3 |
| `Tag` | On-stage pill, 26 px, 11.5/700. `plain` (bg 88%, line), `signal`, `solid` |
| `Tooltip` | raised 94%, line-strong border, radius 10, shadow-tip |
| `Popover` / `Dialog` / `Sheet` | raised surface, line-strong border, radius 12, shadow-pop. Phone `Sheet`: panel surface, radius 20 top, 40 × 5 grabber, shadow-sheet |
| `Toast` | 44 px pill, raised 95%, border tinted by context (doorbell uses the ring gold); used for moments, not errors |

### 6.2 Always-within-reach cluster

**`TempoModule`** (380 × 40 desktop; phone strip 358 × 48). Left to right: source button (icon + "Music", "Pro DJ Link", "Internal"; opens a popover with the source chain from `/inputs`), BPM in mono 20/600 with a "BPM" caps suffix, four beat pips, "bar 42" in mono 11.5 text-3 (desktop only), **TAP** button (28 px desktop, 40 px phone). States: normal; `stale` (source label in signal, pips stop). Tapping sends taps with client timestamps (12.4); the BPM updates within one tap after the third.

**`PreviewOnlySwitch`**: "Preview only" label + tape switch (desktop); 44 px eye button that becomes a tape disc when on (phone).

**`AttentionButton`**: when items exist, signal-bg, signal-line border, alert icon, "Needs attention" and a count badge (signal fill, mono). With none: quiet outline "All good" with a check (desktop; phone hides it). Opens `AttentionPopover` (desktop, 430 px, anchored under the button) or `AttentionSheet` (phone). Each item: icon, title, one-line explanation, up to two actions (Restart, Details, Retry now, Open…). See `State-Problems.png`, `Phone-State-Problems.png`.

**`ConnectionIndicator`**: "● Live 60 fps" (pulsing dot) or "⟳ Reconnecting · try 3" in signal.

### 6.3 Zone components

**`ZoneCard`** (panel width 372; padding 14/16/16; radius 12; raised; line border). Anatomy, top to bottom:
1. Header: zone name (12.5/600 text-2) + context (12 text-3), and a "More" icon button (Edit look, Change look, Restart, Show lights on the map).
2. Look name, serif 30 (compact 26).
3. Meta row: input chips for what the look uses (`Sun`, `Tempo`, `Music`, `Home Assistant`) or a quiet "No inputs" chip; modifier chips (`Evening`); "since 18:04 · 1 h 10 m".
4. Live swatches: one `LightSwatch` per light in the zone (6.6).
5. Optional note (12 px): what's wrong or special, e.g. "**Rope offline** since 17:02 · Candle 2 was switched off elsewhere and rejoins when it's back on".
6. Controls: brightness slider + "Off" outline button.

States (all in `State-Sheet.png`): **running**; **transition** (old name struck through → new name, progress bar with kind and %); **slow** (note in signal: "38 of 60 fps for 2 min"); **crashed** (signal border; note explains and says the lights hold the last frame; controls become Restart · Details · Off); **waiting for an input** (the missing input chip in signal; swatches dark; note: "Nothing playing on Music Assistant. The look waits dark and starts with the music."); **overlay** (a Home look playing over everything, e.g. Doorbell ripple: gold-tinted card, time left, progress bar).

Context line rules: for Whole home when other zones have taken lights, list the rooms it still covers ("Kitchen · Bedroom · Entrance"); for a room, the light count ("11 lights"); for a tempo look, the source ("on the music's beat").

**`ZoneRow`**: collapsed one-line zone (serif 20 look name, zone name, small swatches). Used when the panel runs out of room and on the state sheet.

**`ZonePicker`**: chips for Whole home, each room with lights, each sub-zone (Office desk, Kitchen counter), "Entrance", saved custom groups, and a dashed "Pick lights…" chip. Each chip shows what's running there in small text; the selected chip is inverted. Clicking a room on the stage selects the same zone.

### 6.4 Look components

**`LookThumb`**: the animated motion portrait for each look (a small 16:10 scene with a faint perspective floor grid and the look's motif). All 29 motifs are in `reference/Looks.html`; port them as small canvas or SVG components keyed by `looks.json` `thumbnail` ids. Tempo and audio motifs must follow the live beat clock, not CSS timers. Later, when the engine can render a look for a zone offscreen, a thumbnail may switch to the real preview; keep the component interface `(lookId, size, live?: boolean)`.

**`LookCard`** (grid, 201 px at 6 columns): thumb (radius 10, line border), serif 20 name + star toggle, two-line description (12 text-3), input list (icons + names, or "No input"; a missing input shows in signal). Overlays: "● Living room" when running somewhere; "From Fireflies" for a saved variation. Hover (and focus): white border, bottom gradient scrim with **Put on…** and **Edit** buttons.

**`LookTile`** (composer, 176 px): thumb, serif 19 name, input icons; "PREVIEWING" solid tag when selected; "RUNNING HERE" tag when it's the zone's current look.

### 6.5 Editor components

`LayerRow` (drag handle, visibility toggle, type icon tile for field / particles / firmware, name, one-line summary, blend and opacity in mono), `ModifierRow` (name, sub, value, switch), `SettingRow` (96 px label, control, 28 px **bind** button; bound state inverts the bind button and shows "follows Loudness"), `BindingEditor` (signal select, "At silence" / "At loudest" fields with units, live input and output readouts, a meter, smoothing), `SignalTile` (name, live value, meter, where it comes from and what uses it).

Setting controls by type: number (slider + value), colour (swatch + picker), palette (swatch row + name + edit), anchor (select with anchor icon + "Pick any point in the home" crosshair button), point (xyz fields + pick), zone (select), set of lights (chips / multi-select), range (dual slider, e.g. height band 0.3–2.2 m), boolean (switch), choice (segmented or select).

### 6.6 `LightSwatch`

The one way a light's live colour appears outside the stage. 14 px circle (12 phone, 16 devices table).
- Live: fill = the light's colour mixed from `#1e1c19` toward the colour by `0.15 + intensity` (clamped), with a glow `0 0 10px` of the colour scaled by intensity; intensity ≤ 0.04 shows `#26241f` (dark).
- Multizone or matrix: a 1.9× wide pill with a left-to-right gradient of its zones.
- Running its own effect: 1.5 px dotted `text-2` outline, 2 px offset.
- Streamed copy: 1.5 px dashed `text-3` outline, 2 px offset.
- Offline: hollow, 1.5 px dashed signal border.
- Switched off elsewhere: hollow, 1.5 px `text-3` border with a diagonal slash.
Always carries an accessible name: "Candle 2, switched off elsewhere".

### 6.7 Devices and inputs components

`DeviceRow` (table row, 48 px) and `DeviceDetail` (expanded row: horizontal LED strip of every zone in live colour, what it can do, latency sparkline for 60 s with now / avg / p95, latency override Auto | Set + ms field, Show in map, Identify, Remove, MAC and firmware). `StatusCell` (section 9.1). `InputCard` (icon, title, status on the right: "● Connected", "○ No DJ", "⚠ Stale · 42 s" in signal). `SourceChain` (Pro DJ Link → Music → Internal; the active one inverted). `DeckSlot` (empty dashed, cued, playing, MASTER badge). `Spectrum` (32 bars, bass left). `EntityTable` (Home Assistant entities with friendly name, entity id in mono, value and sub-value, what uses it).

---

## 7. The stage (3D home)

The stage is the heart of the app. It is one R3F component used in five modes, fed by `home.json`-shaped geometry from the API and the live frame stream.

### 7.1 Geometry

Source: `GET /api/home` (12.3), seeded from `docs/design/web-app/home.json`. Plan coordinates are metres with x east, y south, z up, origin at the plan's north-west corner. In three.js map plan `(x, y, z)` to world `(x, z, y)` (y up, +z south).

Draw:
- **Floors:** each room polygon, `stage-floor` with a 0.8 px `stage-floor-edge` outline.
- **Courtyard** (opens to the west): `stage-courtyard` with a faint 7 px dot pattern. **Balcony** (off the sunroom): 45° hatch.
- **Walls:** cut at **0.85 m** (dollhouse). Exterior walls 0.24 m thick, interior 0.12 m, door gaps left open. Top faces `stage-wall-top`, sides `stage-wall-side` (facing camera) and `stage-wall-side-2` (other).
- **Windows:** wall below 0.45 m, then a glass pane (text at 10%) to the cut height with a 1.1 px top edge (text at 45%). The three **west bedroom windows** are flagged `westFacing`; looks that model the sun light their glass.
- **Glass door** sunroom → balcony: same as a window with a 0.02 m sill.
- **Columns:** 8 structural columns at cut height + 0.02, lighter top (`stage-column-top`).
- **Furniture blocks** (sofa, coffee table, TV console, TV, speakers, bed, desk, counter, table) as dark boxes so rooms are recognisable. They are map data the owner can edit.
- **Ghost volume:** the outline at ceiling height (3.35 m) as a faint line (text at 7.5%), plus faint vertical lines from the cut height to the ceiling at outline corners. Beams (3.10 m) appear only in map mode.

### 7.2 Camera and views

- Orthographic. **Turned 14° clockwise from north-up, tilted 55° above the horizon** (camera to the south-south-east, looking north-north-west). North stays roughly up so it reads like the floor plan. Fit the whole outline plus 2.3 m of height with 56 px side padding, 70 px top and 64 px bottom on desktop Live.
- Focus framing (zone detail, editor preview, composer on phone): fit the zone's polygon, tilt 50°, show neighbours dimmed at the edges.
- View controls: `3D | Plan` segmented (Plan is the same scene from straight above), rotate (orbit ±45° around the vertical in 15° steps; snap back with Fit), zoom, Fit. Remember the view per route in local storage.

### 7.3 Lights

For each light, sample points along its shape: point (1), cylinder (6 up the height when taller than 0.3 m, else 2), line (6), bent line (10 along the path), grid (7 across). Each sample's colour and intensity come from the frame stream (7.5).

Per sample:
- **Core:** 3.4 px dot (screen space, `sizeAttenuation: false`), colour lifted toward white by `0.35 + 0.3·intensity`. A dark light shows a 3 px `stage-light-off` dot.
- **Halo:** additive sprite, radius `14 px · (0.5 + 0.7·intensity)` for single-point lights, `9 px · (…)` for strip samples; radial falloff: 90%·i at the centre, 28%·i at 22% radius, 0 at the edge.
- **Floor pool:** additive disc on the floor under each sample, radius in metres `(1.15 + 0.6·z) · (0.55 + 0.6·intensity)` (×0.72 for multi-sample lights). Falloff 95%·i centre, 35%·i at 25%, 0 at the edge. **Clip each pool to its own room's floor** (stencil or a room-id mask texture) so light doesn't bleed through walls.
- **Strips** (line, bent line, cylinder, grid): draw each segment between samples as a 3–4 px line in the segment's colour; the strip is visible even when dark.
- **Height cue:** a dashed drop line (2/2, text at 18%) from every raised light to a small floor tick.
- **States on the stage:** offline = hollow dashed ring, no glow; switched off elsewhere = hollow ring with a slash; running its own effect = dotted ring around the light (glow continues, colour is the firmware's approximate colour); streamed copy = two small wave marks beside the light; guessed position (map mode) = dashed 10 px ring; selected = solid 13 px white ring.

### 7.4 Effects in space

Where the engine can describe what a look is doing in 3D (particles, fields, rings, the sun), the stage draws it faintly in the room, not only on lamps: firefly and ember particles (tiny glowing points), sun shafts through the west windows onto the bedroom floor, the doorbell's gold ring clipped to the apartment outline, the Scanner plane, Shockwave spheres. This is the "Effects in space" toggle (default on). It needs the `fx` stream (12.4); until that exists the toggle is hidden and the stage shows lamps and pools only.

**The sun:** a sun disc outside the apartment at its real azimuth and elevation, with a dashed arc of its recent path and a mono label "SUN 2° · W". Drawn whenever it's above the horizon, in all modes except map.

### 7.5 Live data path (performance)

- The frame stream is binary (12.4). Decode into one preallocated `Uint8Array` per light keyed by stable light id; never create objects per frame.
- One `InstancedMesh` for cores, one for halos, one for pools; write `instanceColor` in `useFrame` from the latest buffers. **No React state per frame.** React re-renders only when geometry or selection changes.
- Target 60 fps with all 412 LEDs and 60 pools on a 2020-era laptop GPU; cap DPR at 2; pause rendering when the tab is hidden; drop to 30 fps on phone.
- Labels are HTML overlays positioned from projected points (drei `Html` with `occlude=false`, or a manual projection pass once per frame).

### 7.6 Modes

| Mode | Used by | Behaviour |
|---|---|---|
| `live` | Live, Doorbell | Live colours, particles, sun, labels (room caps + running look in serif italic), hover tooltip on a light (name, hex + intensity, look · zone, model · latency), click a room → composer with that zone |
| `compose` | Put a look on | Rooms outside the chosen zone dimmed to 34%; chosen zone outlined in 1.6 px `text`; the chosen zone renders the **preview stream** instead of live; a "PREVIEW ON SCREEN" tag says the lights are still running the old look |
| `focus` | Zone detail, editor preview, phone tweak | Framed on one zone, other zones' lights hidden, soft vignette |
| `map` | Home map | 1 m floor grid, anchors (diamonds + caps labels), sub-zones (dashed outlines), guessed rings, selection, transform gizmo (7.7), beams |
| `frozen` | Reconnecting | Last frame, grayscale 85%, brightness 55%, no animation |

### 7.7 Map editing

- Tools: Select, Move, Rotate (segmented); Add light (from the unplaced list), Anchor, Sub-zone (draw a polygon on the floor); views 3D / Top / Front; snap (5 cm default; 1, 5, 10 cm, off).
- Gizmo labels use the home's real directions: **N, W, UP** arrows (not X/Y/Z), and a dashed rotate ring on the floor with a handle.
- A readout next to the selection: "14.30 E · 12.75 S · 0.00 up · 0.62 m tall".
- Positions update optimistically while dragging (the repo already learned this: see the R3F gotchas in `CLAUDE.md`) and are saved on release.
- Moving a guessed light doesn't confirm it. Confirming is explicit ("Confirm position").

---

## 8. Screens

Each screen lists what it shows, what it does, its states and the data it needs. File names refer to `docs/design/web-app/reference/`.

### 8.1 Live (desktop) · `Main`

- **Stage** fills the space between the rail and the 404 px panel. Overlays: top-left `3D | Plan`, "Effects in space" and "Labels" switches; top-right the sun readout ("Sun 2° · W · sets 19:26"); bottom-left the light-state legend (Live colour, Own effect, Offline, Switched off elsewhere); bottom-right rotate, zoom, fit.
- **Running panel:** header "Running · 3 zones · all 19 lights" + "Stop all" (ghost). Zone cards in start order, newest on top. Footer: primary lg **Put a look on** and "or click a room in the home".
- **Hover** a card → its zone outlines on the stage. **Hover** a light → tooltip. **Click** a room → `/live/put?zone=<room>`.
- If more zones run than fit, older ones collapse to `ZoneRow`s.
- States: nothing running (`State-Nothing-Running`), transition (`State-Transition`), problems (`State-Problems`), own effects and streamed copies (`State-Firmware`), preview only (`State-Preview-Only`), reconnecting (`State-Reconnecting`).
- Data: home geometry, frames, running zones, beat, inputs (sun), attention, connection.

### 8.2 Put a look on (desktop) · `Live-PutLookOn`

The composer replaces the Running panel; the stage goes into `compose` mode.
1. **Where:** zone chips across the top of the stage (6.3), preselected from the room clicked or the last zone used.
2. **What:** search ("Search 29 looks"), category chips (Starred, Ambient, Tempo, Audio, Home, Firmware), 2-column `LookTile` grid. Selecting a tile starts **preview on screen** for that zone immediately.
3. **How:** transition select (Cut, Fade, Wipe, Spread, Dissolve + duration; default the look's own), an explanation of consequences ("Takes over the Living room from *Fireflies*. The Candles and the TV Lamp will run LIFX Flame."), **Cancel** and primary **Start <Look>**.
- Home looks (whole-home scope) lock the zone to Whole home.
- A look whose input is missing stays selectable; its tile says "Waits for music" / "Needs Home Assistant" in signal, and the consequence line says what will happen.
- Keyboard: `L` opens the composer from Live; arrows move through tiles; Enter starts; Esc cancels.
- Data: zones, looks, `POST /api/preview` (start/replace/stop), preview frame stream, start look.

### 8.3 Doorbell ripple over everything · `Live-Doorbell`

When Home Assistant reports the doorbell, the engine plays Doorbell ripple over whatever is running. The stage shows the gold ring spreading from the front door (clipped to the apartment), lamps near the ring glowing gold; a toast top-left: bell icon, "Doorbell", "Front door · 19:16 · ripple playing over everything", time left in mono gold, "Stop ripple". The panel shows an overlay card on top of the zone cards. Other Home-category triggers (Goodnight on bedtime) use the same overlay pattern.

### 8.4 Looks · `Looks`

- Filter bar: search (looks, layers, inputs), category tabs with counts (All 29, Starred, Ambient 11, Tempo 9, Audio 4, Home 4, Firmware 1, Mine), "Only ready now" switch (hides looks waiting for an unavailable input), "New look".
- Sections per category: serif 32 name, count, one-line blurb (`looks.json` `categories`). 6-column grid of `LookCard`s, 28/16 px gaps. Firmware and Mine share the last row.
- Clicking a card opens the editor; hover shows Put on… / Edit.
- Data: looks (with starred, running zones, missing inputs), inputs availability.

### 8.5 Look editor · `Look-Editor`

- Header strip (68 px): back to Looks, serif 32 look name, a dashed "Edited · not saved" chip while there are changes, context ("Ambient · running on Living room"), actions **Reset to original**, **Save as new look…**, primary **Put on…**. Built-in looks are never overwritten; saving always creates a new look in Mine. Editing a look in Mine offers "Save" and "Save as new".
- **Left column (330 px):** Layers (top draws over the ones below; drag to reorder; add layer), Look modifiers (Trails with time, Downbeat flash, Brightness cap with %, Evening), Transition (segmented kind + duration slider), Needs (derived: which inputs the look needs vs. only uses; e.g. "Runs without any input. Speed follows Loudness when music plays and rests at 0.15 m/s otherwise.").
- **Centre:** preview on screen in `focus` mode for a chosen zone (select), pause, "Compare with original" (split or toggle), anchors used by the look drawn on the stage ("Drift toward: Sofa"). Below: live signals the look uses (`SignalTile`s).
- **Right column (370 px):** the selected layer: type, name, Blend (Add, Screen, Normal, Multiply, Max), Opacity; Settings (6.5) each with a bind button; Layer modifiers: Mask (height band, room, sub-zone, distance from an anchor), Mirror, Transform (offset, rotate, scale).
- Every change updates the preview within one frame; nothing reaches the lights until Put on…
- Data: look definition + setting schema, anchors, zones, signals, preview.

### 8.6 Home map · `Home-Map`

- **Outliner (280 px):** search; Lights · 19 grouped by room (shape icon, name, LED count, GUESSED badge); Anchors · 5; Sub-zones · 2.
- **Stage** in `map` mode with the toolbar (7.7), a banner when any positions are guessed ("2 lights are placed at guessed positions: Rope and Ikea Lamp 3. Confirm them so looks land where you expect." · Review), footer facts (Grid 1 m · Ceiling 3.35 m · beams 3.10 m · North is up).
- **Inspector (340 px)** for the selection: name, model, LEDs, room (derived from position); confirmation state ("Position confirmed on 12 Sep" or "Guessed" + **Confirm position**); Shape (Point, Line, Bent line, Cylinder, Grid); Position in metres (East, South, Up); Rotation (Turn, Tilt, Roll); Size (per shape: height and radius for a cylinder, width and depth for a grid, path points for a line); LED order (e.g. Bottom → top, with "LED 1 is at the bottom. Blink it to check."); Identify (blink); Remove from the map (danger).
- Anchors: name, position, optional pair (Speakers). Sub-zones: name, parent room, polygon points.
- Empty state: `State-No-Lights-Placed` (all lights unplaced; "Place your 19 lights" card with **Place them roughly for me** and **Blink one**; auto-placed lights are marked guessed).
- Data: home, placements, anchors, sub-zones, identify.

### 8.7 Devices · `Devices`

- Head: serif 40 "19 lights, 412 LEDs"; facts (17 streaming · **1 offline** in signal · 1 switched off elsewhere · Last scan 19:02); filter segmented (All, Needs attention, LIFX, Govee, OpenRGB); **Find new lights**.
- Table grouped by room (group header: room · count · running *Look*): Light (swatch, name, model · IP), LEDs, Can do (Colour, Multizone, Matrix, Effects), Status (9.1), Latency (mono ms; "est." for heuristic values; "SET" badge for overrides), Send rate, Dropped (signal above 1.5%), Actions (Identify, More).
- One row expands inline (`DeviceDetail`). The PC shows its parts as chips ("5 parts, one device": Keyboard 104, RAM sticks 16, GPU 16, Motherboard 12, Mouse 2).
- Data: devices + stats (1 Hz), frames for the expanded row's LED strip, latency history (60 s).

### 8.8 Inputs · `Inputs`

- **Tempo** (2/3 width): BPM in mono 64 and its source line ("from the music · bar 42 · beat 2 of 4"), big beat pips, nudge − / +, a 112 × 72 TAP pad, and the **source chain** Pro DJ Link → Music → Internal with the active source inverted and each one's status ("No DJ on the network", "Beat of 'Rain' · 99% sure", "118.0 · tapped 19:10"). Copy: "The first source that's available drives the clock. Tapping sets Internal and takes over until music or a DJ starts again."
- **Pro DJ Link** (1/3): four deck slots; the interface ("Listening on eth0 · 192.168.1.10"); last DJ set. With a DJ: see `Phone-Tempo` (decks with player name, state, BPM, pitch, MASTER).
- **Music Assistant:** connection, now playing (serif title, artist, player group select), loudness meter (0–1 and LUFS), 32-bar spectrum, beat, kick, snare, hi-hat, "Updated 40 ms ago".
- **Home Assistant:** host and token state, chosen entities (doorbell, bedtime, what's playing, sun) with live value and what uses them, **Choose entities**.
- **Signals:** every signal (name in mono, live value, meter, source, what uses it: `beat.phase`, `bar.phase`, `bpm`, `loudness`, `spectrum.bass`, `onset.kick`, `doorbell`, `bedtime`, `sun.elevation`, `sun.azimuth`, `time.evening`, …).
- States: `State-Inputs-Down` (music stale 42 s with last-known values dimmed and tempo fallen back to Internal; Home Assistant disconnected with "What stops working"; no DJ empty card).
- Data: inputs snapshot + `inputs` stream, `signals` stream (10 Hz), beat.

### 8.9 Settings · `Settings`

Section nav (Output, Home, Inputs, Light integrations, Backup) + a 700 px form + a Backup card on the right.
- **Output:** Preview only (tape switch; copy: "Render everything on screen and send nothing to the lights. The whole app is taped off while it's on."); Brightness cap (global slider); Engine frame rate (30 / 45 / 60 / 90 fps).
- **Home:** Location (place + lat/lon; used for the sun and Evening); North (compass + degrees); Ceiling (3.35 m) and Beams (3.10 m).
- **Inputs:** Pro DJ Link network interface (select from the server's interfaces with IPs); Music Assistant (host + on/off); Home Assistant (host, Token…, on/off).
- **Light integrations:** LIFX (broadcast address), Govee (multicast address), OpenRGB (host:port), each with on/off and a count of lights.
- **Backup:** "Download backup" (one file with looks, zones, the home map, devices, inputs and settings; show the last download) and "Restore from a file…" (confirm dialog: "Restoring replaces everything here. Running looks stop first, then come back from the file.").
- Changes save on blur/toggle with an inline "Saved" tick; invalid values show inline errors, never toasts.

### 8.10 Phone

| Screen | Reference | Notes |
|---|---|---|
| Live | `Phone-Live` | Header "Home" + "Wed 19:14 · sun sets 19:26"; tempo strip; stage 390 × 268 (no labels); "Running" list of compact zone cards (tap → zone detail); sticky primary **Put a look on** (52 px) above the tab bar |
| Put a look on | `Phone-PutLookOn` | Focused stage on top with "PREVIEW ON SCREEN · LIGHTS UNCHANGED"; sheet: Where (52 px zone buttons, horizontal scroll), What (category chips, look rows with 84 × 54 thumbs), consequence + transition, primary **Start Embers on Living room** |
| Zone detail | `Phone-Zone` | Focused stage; serif 40 look name; meta; big brightness slider; Change / Tweak / Off (48 px); lights list with live swatches and states |
| Looks | `Phone-Looks` | Search, category chips, Starred first, 2-column cards |
| Tweak | `Phone-LookTweak` | Preview; layer chips (the selected one solid); the look's key settings with Follow / bound pills; modifiers; bottom bar Reset + **Save as new look**; "Layers, masks and transitions are on the desktop editor." |
| Devices | `Phone-Devices` | Find new lights + Map; "Needs attention" group first, then rooms |
| Confirm a guessed light | `Phone-Map` | No tab bar (a focused task). Map stage; sheet with Blink, a 10 cm nudge pad (N/S/E/W) and height ±, coordinates, primary **Confirm position** |
| Tempo | `Phone-Tempo` | Source line, mono 80 BPM (e.g. 125.5 = 124.00 +1.2%), pips, 72 px TAP, decks with MASTER; "Music Assistant: nothing playing. Audio looks wait for music." |
| Settings | `Phone-Settings` | Grouped rows; the home map points to desktop |
| States | `Phone-State-*` | Preview only (tape frame + banner), Needs attention (sheet), Reconnecting (frozen stage + card), Nothing running (start again list) |

---

## 9. States catalogue

The visual vocabulary is fixed; use it everywhere. `State-Sheet.png` shows the set.

### 9.1 Lights

| State | Stage | Swatch | Devices status | Copy | Attention? |
|---|---|---|---|---|---|
| Streaming | glow + pool | filled | "● Streaming" | – | no |
| Running its own effect | glow + dotted ring | dotted outline | "Own effect" + effect name ("LIFX Flame") | "Own effect · LIFX Flame" | no |
| Streamed copy | glow + wave marks | dashed outline | "Streamed copy" | "Streamed copy · Govee has no Flame" | no |
| Offline | hollow dashed ring | dashed signal | "Offline since 17:02" (signal) | "Rope offline since 17:02. It rejoins by itself when it's back." | **yes** |
| Switched off elsewhere | hollow ring + slash | ring + slash | "Switched off elsewhere · rejoins" | "Candle 2 was switched off elsewhere and rejoins when it's back on." | no |
| Guessed position | dashed ring (map) | – | GUESSED badge (map lists) | "Placed by the app, not by you." | banner on the map only |

Offline and switched-off lights keep their zone membership and rejoin by themselves. The app never turns a switched-off light on.

### 9.2 Zones

Running · Transition · Slow · Crashed · Waiting for an input · Overlay, as in 6.3. Slow means below 80% of the target frame rate for more than 30 s. A crashed look holds the last frame until the owner restarts it or turns it off.

### 9.3 Inputs

| State | Chip | Meaning |
|---|---|---|
| Connected | input chip | Live values |
| Stale | signal chip with age ("Music · 42 s") | Connected but no updates for longer than expected (music: 10 s while playing). Looks hold the last value; tempo falls back down the chain |
| Disconnected | signal chip | Can't reach it; retrying. Triggers pause ("Doorbell ripple and Goodnight can't trigger") |
| Idle | quiet chip ("No DJ") | Nothing to report, nothing wrong |
| Needed by a look | signal chip on the look | That look waits for the input |

### 9.4 App

| State | Reference | Behaviour |
|---|---|---|
| Preview only | `State-Preview-Only` | 5.6. Starting or changing looks still works; everything stays on screen until preview only is turned off, then the current state goes to the lights |
| Reconnecting | `State-Reconnecting` | Stage frozen (7.6), cards at 45% opacity and inert, a centred card: "Lost the live link to homeserver. Your looks keep running on the server. This is the last frame, from 19:14:32. Controls come back when the link does." + Try now. Exponential backoff 1, 2, 4, 8 s, max 10 s. Resync everything on reconnect |
| Nothing running | `State-Nothing-Running` | Stage shows each light as it is ("Your lights are as they were: 9 on, 10 off"), "Start again" list of recent looks with one-tap play, primary Put a look on |
| No lights placed | `State-No-Lights-Placed` | 8.6 |
| First run, no lights found | (same pattern) | "No lights yet" + Find new lights + which integrations are on |

### 9.5 Needs attention

Server-derived so desktop and phone agree (12.4 `attention`). Items: light offline, zone crashed, zone slow, input disconnected, input stale (while something depends on it), device dropping more than 5% of frames for a minute. Ordered by severity then time. The rail shows a signal dot on Devices (lights) and Inputs (inputs). "Switched off elsewhere", "No DJ" and "nothing playing" are never attention items.

---

## 10. Copy

- Plain, calm, specific. Say what happened and what will happen next ("The kitchen lights are holding the last frame").
- Words: **look** (never "effect" or "preset" in the UI), **zone**, **light** (use "device" only on the Devices page header and for the PC), **Off** (stops a look and restores lights), **Stop all**, **Put a look on**, **Preview only**, **Needs attention**.
- Names from the backend verbatim (light names, entity ids, track titles).
- Time: 24 h ("19:14"); durations "1 h 10 m", "9 m", "42 s"; "since 18:04 · 1 h 10 m".
- Units: m (two decimals for positions), ms, fps, %, °, BPM (one decimal; Pro DJ Link shows pitch-adjusted BPM and the raw "124.00 +1.2%").
- Numbers are mono and tabular. Hex colours are uppercase in tooltips (#C8F25A).
- Sentence case everywhere except caps labels.

---

## 11. Behaviour rules

### 11.1 Looks

A look is a named preset of **layers** (field, particles, firmware), **look modifiers** (trails, downbeat flash, brightness cap, evening), a default **transition** and a **category**. Each layer has settings, **layer modifiers** (mask, mirror, transform), a blend mode and opacity. Any setting can be **bound** to a signal. A look declares which inputs it **needs** (it waits without them) and which it only **uses** (degrades gracefully).

### 11.2 Firmware layers

A firmware layer asks lights to run a built-in effect (LIFX Flame, Morph, Move, waveforms; OpenRGB hardware modes). Lights that can't run it get a **streamed copy** rendered by the engine. The UI shows both states (9.1).

### 11.3 Zones and take-over

- Zones: Whole home, each room with lights, sub-zones (Office desk, Kitchen counter), custom groups of lights.
- **A light is in at most one running zone.** Starting a look on a zone takes over its lights from any running zone that overlaps. The overlapped zone keeps running on the lights it still has, and its context line lists what it still covers. A zone left with no lights stops.
- This replaces today's rule in `PipelineManager` (activation is refused when a device is in another active scene). The UI must show the consequence before Start ("Takes over the Living room from *Fireflies*").
- **Off** stops the zone's look and restores each light to how it was before the look started (captured state). **Stop all** does this for every zone after a confirm.
- Overlays (Doorbell ripple) render on top of all zones for their duration and then get out of the way.

### 11.4 Persistence

Running zones survive restarts: after the server starts, every zone that was running resumes (same look, settings, brightness, start time). The old "starts STOPPED, user must press play" behaviour goes away for the UI.

### 11.5 Tempo

The clock always runs. Source priority: Pro DJ Link (when a DJ plays) → the music's beat (when Music Assistant plays and beat confidence is high) → Internal (tapped or nudged). Tap sets Internal and holds it until a higher source starts again. The source popover can lock a source ("Auto" by default).

---

## 12. Data contract

Build the UI against a typed, isolated data layer (`src/api/`): generated OpenAPI types, a REST client, a WebSocket client and a frame decoder, plus MSW mocks that serve the 19:14 scenario. Components never call `fetch` or touch the socket directly.

### 12.1 Today vs needed

Backend on `master` at `f420013` (13 Jul 2026). If the looks/zones/inputs engine already exists in unpushed work, map it onto these shapes in `src/api/` and delete the rows that are done.

| Capability | Today | Needed by the UI |
|---|---|---|
| Devices list, discover, scan, identify, latency override, remove | `/api/devices/*` | Extend `DeviceResponse`: `id` (stable_id), `room`, `model`, `protocol`, `capabilities`, `builtInEffects`, `parts`, `status` (9.1), `latency: {measured, override, estimated}` |
| Live LED frames | WS binary, keyed by device **name**, max 30 fps | Key by stable id, up to 60 fps, stream type byte (live / preview), 12.4 |
| Beat | WS `beat` (bpm, phases, beat_pos, pitch, deck) | + `source`, `bar`, `server_time`, `stale`, `decks[]`, tap endpoint |
| Device stats | WS `stats` 1 Hz | + stable id, status enum per 9.1, latency history on request |
| Transport | `/api/transport`, WS `transport` | Preview only = SIMULATING; running zones resume on boot (11.4) |
| Effects, presets | 6 effects, param schema, presets | **Looks** (29 built-ins + Mine) with layers, modifiers, bindings, inputs, starred |
| Scenes / pipelines | activate/deactivate, per-scene effect, placements per scene | **Zones** with take-over (11.3), brightness, off/restore, restart, transitions |
| Scene placements | point / strip / matrix, one mapping | **Home**: rooms, walls, windows, furniture, anchors, sub-zones; placements with shapes point / line / bent line / cylinder / grid, `confirmed`, LED order |
| Preview | – | Render a look (built-in, saved or unsaved draft) for a zone to the UI only |
| Inputs | Pro DJ Link only | Music Assistant, Home Assistant, sun, signals catalogue with usedBy |
| Attention | – | Server-derived list (9.5) |
| Config | `/api/config` (engine, network, devices…) | + preview only, brightness cap, location, north, ceiling/beams, MA and HA settings |
| Backup | `/api/state/export`, `/api/state/import` | Must cover everything in 3.4 |

Each "Needed" row is its own backend plan (13.2). The UI milestones can proceed on mocks in parallel.

### 12.2 Domain types (UI side)

```ts
type Id = string

interface Home {
  outline: Vec2[]; rooms: Room[]; subZones: SubZone[]; walls: Wall[]; columns: Box2[]
  furniture: Furniture[]; anchors: Anchor[]; ceiling: number; beams: number
  northOffsetDeg: number; location: { name: string; lat: number; lon: number }
}
interface Room { id: Id; name: string; polygon: Vec2[]; labelAt: Vec2 }
interface SubZone { id: Id; name: string; room: Id; polygon: Vec2[] }
interface Anchor { id: Id; name: string; position: Vec3; points?: Vec3[]; confirmed: boolean }

type LightShape =
  | { kind: 'point'; position: Vec3 }
  | { kind: 'line'; path: [Vec3, Vec3] }
  | { kind: 'bent-line'; path: Vec3[] }
  | { kind: 'cylinder'; base: Vec3; height: number; radius: number }
  | { kind: 'grid'; center: Vec3; width: number; depth: number; rotation: Vec3 }
type LightStatus = 'streaming' | 'own-effect' | 'streamed-copy' | 'offline' | 'switched-off' | 'reconnecting'
interface Light {
  id: Id; name: string; room: Id | null; subZone: Id | null; model: string
  protocol: 'LIFX' | 'Govee' | 'OpenRGB'; leds: number; capabilities: ('colour' | 'multizone' | 'matrix' | 'effects')[]
  builtInEffects: string[]; parts?: { name: string; leds: number }[]
  shape: LightShape | null; ledOrder: string; confirmed: boolean
  status: LightStatus; statusSince: string; ownEffect?: string
  latency: { measuredMs: number | null; overrideMs: number | null; estimated: boolean }
  sendFps: number; droppedPct: number; address: string; mac?: string; firmware?: string
}

type InputKind = 'tempo' | 'music' | 'home-assistant' | 'sun'
interface Look {
  id: Id; name: string; category: 'ambient' | 'tempo' | 'audio' | 'home' | 'firmware'
  builtIn: boolean; derivedFrom?: Id; description: string; thumbnail: string
  scope: 'any-zone' | 'whole-home'; needs: InputKind[]; uses: InputKind[]; starred: boolean
  layers: Layer[]; modifiers: LookModifiers; transition: Transition
}
interface Layer {
  id: Id; name: string; type: 'field' | 'particles' | 'firmware'; kind: string
  visible: boolean; blend: 'add' | 'screen' | 'normal' | 'multiply' | 'max'; opacity: number
  settings: Record<string, SettingValue>; schema: SettingSchema[]
  mask?: Mask; mirror?: Mirror; transform?: Transform
}
type SettingSchema = { key: string; label: string; unit?: string; bindable: boolean } & (
  | { type: 'number'; min: number; max: number; step: number }
  | { type: 'colour' } | { type: 'palette' } | { type: 'anchor' } | { type: 'point' }
  | { type: 'zone' } | { type: 'lights' } | { type: 'range'; min: number; max: number }
  | { type: 'boolean' } | { type: 'choice'; options: string[] })
interface Binding { signal: string; inMin: number; inMax: number; outMin: number; outMax: number; smoothingMs: number; curve: 'linear' | 'ease' }
type SettingValue = { value: unknown; binding?: Binding }
interface LookModifiers { trailsS: number | null; downbeatFlash: boolean; brightnessCap: number | null; evening: boolean }
interface Transition { kind: 'cut' | 'fade' | 'wipe' | 'spread' | 'dissolve'; durationS: number }

interface Zone { id: Id; name: string; kind: 'home' | 'room' | 'sub-zone' | 'group'; lights: Id[] }
interface RunningZone {
  zoneId: Id; lookId: Id; lookName: string; since: string; brightness: number
  lights: Id[]            // lights it currently owns after take-overs
  covers: string[]        // rooms it still covers, for the context line
  state: 'running' | 'transition' | 'slow' | 'crashed' | 'waiting'
  transition?: { from: string; kind: Transition['kind']; progress: number }
  fps?: { actual: number; target: number }; error?: { layer: string; message: string; at: string }
  waitingFor?: InputKind[]
}
interface Overlay { lookId: Id; name: string; trigger: string; endsAt: string; progress: number }

interface AttentionItem {
  id: Id; severity: 'high' | 'normal'; kind: 'light-offline' | 'zone-crashed' | 'zone-slow' | 'input-disconnected' | 'input-stale' | 'frames-dropping'
  subject: { type: 'light' | 'zone' | 'input'; id: Id }; title: string; detail: string; since: string
  actions: ('restart' | 'details' | 'retry' | 'open')[]
}
```

### 12.3 REST (proposed; `/api` prefix)

```
GET    /home                         home geometry + anchors + sub-zones
PUT    /home                         north, ceiling, beams, location
POST   /home/anchors · PUT/DELETE /home/anchors/{id}
POST   /home/subzones · PUT/DELETE /home/subzones/{id}
PUT    /lights/{id}/placement        shape, position, rotation, size, ledOrder
POST   /lights/{id}/placement/confirm
POST   /lights/placement/guess       spread unplaced lights around their rooms (all unconfirmed)
GET    /lights                       (today: /devices) · POST /lights/{id}/identify · PUT /lights/{id}/latency · DELETE /lights/{id}
POST   /lights/discover · POST /lights/scan

GET    /looks · GET /looks/{id}
POST   /looks                        save as new (body: full look, derivedFrom)
PUT    /looks/{id}                   saved looks only · DELETE /looks/{id}
PUT    /looks/{id}/starred

GET    /zones                        all zones (home, rooms, sub-zones, groups)
POST   /zones/groups · PUT/DELETE /zones/groups/{id}
GET    /running                      RunningZone[] + Overlay[]
POST   /zones/{id}/start             { lookId | look (draft), transition? } → RunningZone, with takeOvers[]
PUT    /zones/{id}/brightness        { value }
POST   /zones/{id}/off · POST /zones/{id}/restart · POST /running/stop-all

POST   /preview                      { zoneId, lookId | look } → { previewId }; replaces any previous preview
PUT    /preview/{previewId}          { look }   live edits from the editor
DELETE /preview/{previewId}

GET    /inputs                       tempo, prodjlink, music, homeAssistant, sun
PUT    /inputs/tempo                 { lock: 'auto' | 'prodjlink' | 'music' | 'internal', bpm? }
POST   /inputs/tempo/tap             { clientTime }  (or WS action, 12.4)
POST   /inputs/tempo/nudge           { delta }
PUT    /inputs/home-assistant/entities
GET    /signals                      catalogue with usedBy

GET    /attention
GET    /config · PUT /config
GET    /backup (file download) · POST /backup/restore (multipart)
```

### 12.4 WebSocket `/ws` v2

JSON envelope `{ "channel": string, ... }` as today, plus:

| Channel | Rate | Payload |
|---|---|---|
| `beat` | client-chosen, ≤ 30 Hz | `bpm, beat_phase, bar_phase, bar, beat_in_bar, pitch_percent, source, stale, server_time` |
| `decks` | on change | `[{ number, player, state: 'empty'|'cued'|'playing', bpm, pitch_percent, master }]` |
| `running` | on change | `RunningZone[]`, `Overlay[]` |
| `lights` | on change | `[{ id, status, statusSince, ownEffect }]` |
| `stats` | 1 Hz | `[{ id, send_fps, latency_ms, dropped_pct }]` |
| `inputs` | on change + 1 Hz heartbeat | music (state, track, group, loudness, lufs, spectrum[32], onsets, updated_at), home assistant (state, entities), sun (elevation, azimuth, sunset, sunrise) |
| `signals` | when subscribed, 10 Hz | `{ name: value }` |
| `attention` | on change | `AttentionItem[]` |
| `fx` | when subscribed, ≤ 30 Hz | optional: particles `[x,y,z,r,g,b,size]`, rings, planes, sun shafts per zone, for "Effects in space" |
| `transport` | on change | `state` (stopped / playing / simulating) → preview only |

Commands (client → server): `subscribe_beat {fps}`, `subscribe_frames {fps ≤ 60, lights?: Id[], streams?: ['live'|'preview']}`, `subscribe_signals {names?}`, `subscribe_fx {on}`, `tap {client_time}`.

**Binary frame v2:** `[1B stream: 0x01 live | 0x02 preview][2B id_len LE][id UTF-8 (stable id)][4B seq LE][RGB × leds]`. Keep v1 behind a version handshake until the old UI is deleted.

Beat extrapolation: client computes `phase(t) = beat_phase + (t − server_time − offset) · bpm / 60`, with `offset` estimated from ping round-trips; snap softly (< 5 ms) or hard (≥ 5 ms), mirroring `BeatClock` drift correction.

### 12.5 Mocks

MSW handlers and a mock WS in `src/api/mocks/` serve fixtures built from `home.json`, `looks.json` and the scenarios in the reference renders: **hero** (Wed 19:14: Home sunset on Whole home covering Kitchen, Bedroom, Entrance; Fireflies on Living room; Twin comets on Office desk; tempo from Music at 121.8; Rope offline; Candle 2 switched off elsewhere), **doorbell**, **transition**, **problems**, **firmware**, **inputs-down**, **nothing-running**, **no-lights**, **reconnecting**, **dj-playing**. A `?scenario=` query switches fixtures in dev. The mock frame generator animates simple versions of the looks so the stage is alive without the engine.

---

## 13. Build plan

> **Reconciled with the engine spec** (`2026-09-23-home-effects-engine-design.md` §2 and §10). The milestones below are called F0–F11 there. The backend track B1–B8 is folded into engine milestones M1–M8. The new app is built beside the old one and served at `/next` until parity, and the old `frontend/` is deleted at the F11 cut-over rather than in F0. Where this section and the engine spec disagree on order, the engine spec wins.

### 13.1 Frontend milestones (branch `feature/web-app-rebuild`)

| # | Milestone | Done when |
|---|---|---|
| M0 | Scaffold: delete `frontend/src`, fresh Vite app, tokens, fonts, `Icon`, primitives (6.1), app shell (rail, top bar, tab bar, phone header), routes with placeholders | Shell matches `Main.png` chrome at 1440 × 900 and `Phone-Live.png` chrome at 390 × 844; axe passes |
| M1 | Data layer: OpenAPI types, REST client, WS client with reconnect/backoff and resync, frame decoder v1+v2, zustand stores, MSW + mock WS with all scenarios | Stores update from the mock at 60 fps without React re-renders (React profiler) |
| M2 | Stage: geometry from `home.json`, camera, walls, windows, furniture, lights (cores, halos, pools clipped per room, strips, drop lines), labels, tooltip, room click, `live` + `frozen` modes, 3D/Plan, sun | Visual side-by-side with `Main.png` reads the same; 60 fps with 412 LEDs |
| M3 | Live: Running panel, `ZoneCard` (all states), `LightSwatch`, tempo module on the real beat, preview only (tape), attention popover, connection | All Live states from 9 reproduce from mock scenarios |
| M4 | Put a look on: composer, `ZonePicker`, `LookTile`, preview stream in `compose` mode, consequence line, transitions, Start / Cancel | Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts) |
| M5 | Looks library + all 29 `LookThumb` motifs, stars, filters, "Only ready now" | Matches `Looks.png`; thumbs follow the beat clock |
| M6 | Devices, Inputs, Settings (incl. backup/restore) | Match references; all parity items in 3.5 work against the real backend |
| M7 | Home map: outliner, inspector, gizmo (N/W/UP), shapes, anchors, sub-zones, guessed/confirm, auto-place | Place, move and confirm a light; add an anchor and a sub-zone |
| M8 | Look editor: layers, settings by type, bindings, modifiers, transition, preview with live edits, save as new, reset | Edit Fireflies, bind Speed to Loudness, save as "Fireflies, slow" |
| M9 | Phone layouts for every screen in 8.10, sheets, touch targets | Match `Phone-*.png`; usable one-handed |
| M10 | Doorbell/overlay, effects in space (`fx`), reduced motion, performance and accessibility pass | All moments in 1.2 reproduce; axe clean; reduced motion honoured |
| M11 | Cut-over: remove v1 frame protocol and any old endpoints the UI no longer uses; update `CLAUDE.md` frontend section and README screenshots | Old UI gone; docs current |

### 13.2 Backend track (separate plans, can run in parallel)

B1 zones with take-over, off/restore and resume on boot (replaces the activation-conflict rule) · B2 looks model (layers, modifiers, bindings, needs/uses) and the 29 built-ins · B3 preview pipeline + binary frame v2 (stable ids, 60 fps, stream byte) · B4 inputs: Music Assistant, Home Assistant, sun, signals, tempo source chain + tap · B5 home model (rooms, anchors, sub-zones, furniture, shapes, confirmed) and placement guessing · B6 light status enrichment (own effect, streamed copy, switched off elsewhere) and the attention feed · B7 `fx` stream for effects in space · B8 backup covering everything.

Order: B1 and B3 unblock M3–M4 against the real engine; B5 unblocks M7; B2 unblocks M8; B4 unblocks M6's Inputs; B7 is last.

---

## 14. Quality bar and tests

- **Unit (Vitest):** formatters (durations, BPM, units), frame decoder v1/v2, beat extrapolation, take-over consequence text, attention ordering, swatch colour maths (6.6).
- **Components (Testing Library):** every `ZoneCard` state, `LightSwatch` states, `TempoModule` stale, composer flow.
- **Visual (Playwright):** each route × each mock scenario at 1440 × 900 and 390 × 844. Compare against the reference PNGs by eye in review, then commit the app's own screenshots as baselines (the references are guides, not pixel oracles).
- **Accessibility:** `@axe-core/playwright` on every route; full keyboard path through Live → composer → Start; the stage has an accessible alternative (the Running panel and a zone list with room buttons); icon buttons labelled; contrast from 5.1 holds.
- **Performance:** stage ≥ 55 fps p95 with 412 LEDs streaming at 60 fps on desktop, ≥ 30 fps on a recent phone; main thread idle ≥ 50% on Live; first load < 400 KB gzipped JS excluding three.js.
- **Resilience:** kill the server during a session → Reconnecting state within 2 s, full resync on return, no duplicate subscriptions.

---

## 15. Assumptions and open questions (confirm with the owner)

1. **Light models and LED counts** are estimates that sum to 412: Rope as a LIFX Lightstrip (60), Candles 26 each, TV Lamp (Tube) 52, Neon 48, Govee floor lamp 13, PC 150 (keyboard 104, RAM 16, GPU 16, motherboard 12, mouse 2), bulbs 1. Replace with discovery data.
2. **Every position** in `home.json` (lights, anchors, furniture) is estimated from the floor plan and starts unconfirmed. The reference renders flag only Rope and Ikea Lamp 3 as guessed, to show the state.
3. **Location** is Dallas, TX (32.78, −96.80) for the sun. Confirm the building's coordinates and north offset (the plan is drawn north-up).
4. **Behaviours proposed by the design** (not in the original brief): tapping takes over as Internal until a higher source returns; a crashed look holds its last frame; stale music makes tempo fall back to Internal; "Place them roughly for me" auto-places lights as guessed; a tempo source lock (Auto by default); latency override as Auto | Set; slow = below 80% of target for 30 s.
5. **Switched off elsewhere** vs **offline**: the UI needs the engine to tell "reachable but powered off by another app" apart from "unreachable". If a wall switch cuts power, the light is unreachable and will show as offline. Decide whether that should count as attention.
6. **Evening modifier** timing (warmer and dimmer "later in the day"): tie to sunset + civil twilight, or to fixed times?
7. **Sample content** in the renders (the track "Rain" by Kerri Chandler, IP addresses, MAC, firmware, dates) is placeholder data for fixtures only.

---

## Appendix A. Artboard index

| Reference file | Screen | Route |
|---|---|---|
| `Direction-A-Dollhouse` · `-B-Mixer` · `-C-Almanac` | The three explored directions (A chosen) | – |
| `Main` | Live, home at sunset | `/live` |
| `Live-PutLookOn` | Put a look on, preview first | `/live/put?zone=living&look=embers` |
| `Live-Doorbell` | Doorbell ripple over everything | `/live` (overlay) |
| `Looks` | Looks library | `/looks` |
| `Look-Editor` | Shape a look | `/looks/fireflies` |
| `Home-Map` | Home map | `/map/tube` |
| `Devices` | Devices | `/devices/tube` |
| `Inputs` | Inputs | `/inputs` |
| `Settings` | Settings | `/settings` |
| `State-Preview-Only` · `State-Transition` · `State-Problems` · `State-Firmware` | Live states | `/live?scenario=…` |
| `State-Inputs-Down` | Inputs states | `/inputs?scenario=inputs-down` |
| `State-Nothing-Running` · `State-No-Lights-Placed` · `State-Reconnecting` | Empty and offline | `/live`, `/map` |
| `State-Sheet` | Lights, zones, inputs state vocabulary | – |
| `System` | Tokens, components, icons, stage spec | – |
| `Phone-Live` · `-PutLookOn` · `-Zone` · `-Looks` · `-LookTweak` · `-Devices` · `-Map` · `-Tempo` · `-Settings` | Phone screens | 4.3 |
| `Phone-State-Preview-Only` · `-Problems` · `-Reconnecting` · `-Nothing-Running` | Phone states | – |

## Appendix B. The 29 looks

`docs/design/web-app/looks.json` has ids, names, categories, inputs, descriptions and thumbnail motifs. Categories: Ambient 11 (no input), Tempo 9 (beat), Audio 4 (Music Assistant; Drop moment also uses tempo), Home 4 (whole apartment; Home sunset uses the sun, Goodnight and Doorbell ripple use Home Assistant), Firmware 1.
