# M1 Set-and-forget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a look on a zone and have it keep running (through restarts, shared lights, switched-off lights and firmware effects) without a transport to press play on.

**Architecture:** Each running zone owns a `ZoneRuntime`: a compiled look, a `LedSet` built from its devices' own geometry, and a ring buffer of float-RGB frames rendered at `now + horizon`. The `LookaheadScheduler` sends each device its slice of its zone's frame through a `DeviceRoute`, converting to 8-bit once, at send. A `ZoneManager` owns the zone lifecycle (take-over, capture and restore, brightness, Off, Restart, Stop all, resume, preview-only, the sharing policy) and runs firmware layers on the lights that support them. A `LightMonitor` and an `AttentionFeed` derive light status and the attention list for the API. Looks are data (`looks/`), zones and assignments live in `state.db`, and new REST and WebSocket endpoints use the web app contract's names.

**Tech Stack:** Python 3.11+ (3.14 per `.python-version`, and in the container), asyncio, numpy, SQLite (`sqlite3` via `asyncio.to_thread`), FastAPI and Pydantic v2, loguru, pytest with pytest-asyncio, LIFX LAN protocol, openrgb-python 0.3.6, React 19 with TypeScript and shadcn/ui (base-ui), Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md` (M1 row in §2 and every section tagged M1). API names and shapes come from `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md` §9, §11 and §12. Read both before starting.

**Execution:** `/executing-plans` in a new worktree branched from `master` after the docs PR merges (`~/code/.worktrees/dj-ledfx/m1-set-and-forget`, branch `feature/m1-set-and-forget`); Before Task 1 sets it up. PR #10 (the old SPA fallback's path traversal fix, `_file_within` in `web/app.py`) merges first, and M1 leaves that code alone. F0 (the new app in `web/`, served at `/next`) may merge before or during M1. Where both touch the same code (`create_app`'s parameters, the tests that call it, the static-file block), keep F0's side; Tasks 21, 24 and 32 say how.

---

## Global Constraints

Every task's requirements include these. Quotes are verbatim from the spec.

- M1 scope: "Firmware effects; looks as data (built-in and saved); zones with take-over, brightness, Off, Restart and Stop all, persisting and resuming; sharing policy; light status and the attention feed; LIFX capabilities from `products.json`; host-network deploy; minimal look picker". Build nothing from M2 or later: no home map, no layer blending beyond one streamed layer plus firmware layers, no modifiers, no transitions other than cut, no particles, no new inputs.
- No user-visible regression: today's six effects keep running as built-in looks through the strip adapter (LED order along the zone's devices), and the old UI keeps working until F11.
- "Budget: under 5 ms per zone frame on one core."
- "The horizon is the zone's largest device latency plus one frame, so reactive looks stay responsive while slow devices still get their frames in time."
- "Colour stays float RGB through the whole layer stack and is clamped and converted once, at send."
- "Everything stays on the single asyncio event loop."
- "A device belongs to at most one active zone. Assigning a look to a zone that overlaps active zones takes their shared devices over: the newest assignment wins. The other zones keep running on their remaining devices, or stop if none remain."
- "Captured state is per device. It is taken when dj-ledfx first takes control of a device, kept through hand-overs between zones and across restarts, and released on Off."
- "If a device's state could not be captured, Off leaves that light alone rather than guessing."
- "Preview-only is global: everything renders and streams to the web preview, and nothing is sent to devices. Turning it off sends the current state to the lights."
- "dj-ledfx turns lights on only when a look is applied, never on restart."
- "A light switched off elsewhere drops out of its zone (power is polled every 5 s) and rejoins when it is switched back on."
- "Firmware looks are sent again if something else stopped them, but only while the light is on."
- "Lights that aren't in a running zone are idle. dj-ledfx reads their power and colour every 30 s, so the web app can show them as they are, and never changes them."
- "An offline light needs attention only after 2 minutes offline, and only while it belongs to a running zone."
- "A look raises or produces NaN: that zone holds its last good frame, the look is marked crashed, and the error is logged once (rate-limited). Other zones keep running."
- "A zone that keeps exceeding its 5 ms budget drops to a lower frame rate, so it cannot stall the shared event loop. It shows as slow while it stays below 80% of the target frame rate for 30 s."
- "A rejected firmware command falls back to streamed emulation."
- Attention items in M1: light offline, zone crashed, zone slow, frames dropping ("a device dropping more than 5% of its frames for a minute"). "Switched off elsewhere, no DJ and nothing playing are never attention items."
- Built-in looks "keep the ids, names, descriptions and thumbnail ids of the handoff's `docs/design/web-app/looks.json`. They are never overwritten: saving an edit creates a new look ("Mine") with `derived_from` set."
- "Where this spec and the contract name the same thing differently, the contract's name wins." New endpoints and channels use the contract's names: looks, zones, running, light status (plus `idle`), attention, preview-only.
- Old endpoints that the old UI still uses stay until F11.
- Design files: use `looks.json` as it is or copy it byte for byte with a test that fails when the copy drifts (CLAUDE.md, "Web App Design"). Never retype a look's name or description.
- Code style (CLAUDE.md): `uv` for everything, `loguru` for logging, `mypy --strict`, all device I/O async, `asyncio.to_thread()` around openrgb-python, event bus callbacks non-blocking (spawn tasks for async work), never `INSERT OR REPLACE` on tables with FK cascades.
- Gates, per task before commit: `uv run ruff check .` clean and `uv run pytest -q` green; `uv run ruff format --check .` and `uv run mypy src/` no worse than the baseline from Before Task 1. The counts may fall (Task 24 deletes the one file the formatter flags), never rise, and an error in a file the task touched is the task's to fix unless the baseline had it. For frontend changes also `cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run build` (plain `npx tsc --noEmit` checks nothing: the root `tsconfig.json` only lists references). During a task, run only the task's test files; run the full gate once, before the commit. The plan's code isn't guaranteed to be formatter-exact: run `uv run ruff format` and `uv run ruff check --fix` on the files the task touched before the gate, never on the whole tree.
- Deployment: "With host networking, the web port is governed by the host firewall (UFW) rather than Docker's published-port rules. Check LAN reachability before switching, and ask before changing UFW."

## Review Focus

The five inputs the spec implies that are most likely to bite someone using this, most likely first. Each has a test in the task that owns the code.

1. **Two overlapping zones started one after the other.** The newer zone takes the shared lights; the older zone keeps its other lights, or stops if it has none left; the shared lights keep the state captured before the first look, so Off on the newer zone puts them back the way they were before either look. Test: Task 16, `test_takeover_keeps_first_capture_and_off_restores_it`.
2. **A restart while some zone lights are switched off elsewhere.** The zone resumes, no power-on command is ever sent, the switched-off lights stay dark and rejoin when they are switched back on. Test: Task 17, `test_resume_never_powers_on_and_switched_off_lights_rejoin`.
3. **Preview-only toggled around a start and an Off.** A look started during preview-only reaches the lights (and powers them on) only when preview-only is turned off; an Off during preview-only restores the lights only then, exactly once. Test: Task 17, `test_preview_only_defers_power_on_and_restore_until_turned_off`.
4. **A light that comes back with a different LED count while its zone runs** (a ghost registered with 60 LEDs rediscovered as a 5-LED Candle, or a Neon reporting a new zone count). The zone rebuilds its LED set and routes, and no route ever slices past the end of the zone's frame. Test: Task 17, `test_rejoin_with_new_led_count_rebuilds_routes`.
5. **A saved look or assignment in `state.db` that no longer loads** (a removed effect kind, bad settings, corrupt JSON). The app starts, the other zones resume, that zone shows as crashed with the reason and doesn't touch its lights, and Off still restores them; a bad saved look is skipped with a warning. Tests: Task 17, `test_resume_with_broken_look_shows_crashed_and_off_restores`; Task 13, `test_load_skips_corrupt_saved_look`.

---

## File Structure

New backend modules:

| File | Responsibility |
|---|---|
| `src/dj_ledfx/effects/context.py` | `RenderContext`, `SignalView`, `render_context()` (sampled at the frame's target time), `to_beat_context()` for 1D effects |
| `src/dj_ledfx/effects/ledset.py` | `LedSet` (positions, normalised positions, device ids, per-device slices and local coordinates) and `build_ledset()` from each device's own geometry |
| `src/dj_ledfx/effects/field.py` | `FieldEffect`: `render(ctx, leds) -> FloatRGB` |
| `src/dj_ledfx/effects/firmware.py` | `FirmwareEffect`: `supports`, `start`, `stop`, `is_running`, `emulate` |
| `src/dj_ledfx/effects/strip_adapter.py` | `StripAdapter`: plays a 1D `StripEffect` along a zone's LEDs in order |
| `src/dj_ledfx/effects/firmware_lifx.py` | `LifxFlame`, `LifxMorph`, `LifxMove`, `LifxWaveform` |
| `src/dj_ledfx/effects/firmware_openrgb.py` | `OpenrgbMode` (hardware modes) |
| `src/dj_ledfx/devices/capabilities.py` | `DeviceCapabilities`, `LightReading`, `FirmwareRejected`, `protocol_of()` |
| `src/dj_ledfx/devices/lifx/products.py` + `devices/lifx/data/products.json` | Vendored LIFX product registry and the capability resolver |
| `src/dj_ledfx/devices/lifx/base.py` | `LifxAdapterBase`: packets, requests, power, colour reads, capture/restore, firmware commands shared by bulb, strip and matrix |
| `src/dj_ledfx/looks/model.py` | `Look`, `Layer`, `Transition`, `LookModifiers`; contract-shaped (de)serialisation; M1 validation; settings schema |
| `src/dj_ledfx/looks/builtin.py` + `looks/data/looks.json` | Byte copy of the handoff's `looks.json`; the Firmware showcase and the six classic looks |
| `src/dj_ledfx/looks/store.py` | `LookStore`: built-ins, saved looks ("Mine"), stars |
| `src/dj_ledfx/zones/model.py` | `ZoneRecord`, `Assignment`, `TakeOver`, `RunningZoneInfo`, `CrashInfo`, `StartResult`, errors, events |
| `src/dj_ledfx/zones/store.py` | `ZoneStore`: zones, members, assignments; one-off scene migration |
| `src/dj_ledfx/zones/runtime.py` | `ZoneRuntime`: compiled look, claims, render at the horizon, crash hold, frame-rate drop, slow and waiting states |
| `src/dj_ledfx/zones/manager.py` | `ZoneManager`: start, take-over, Off, brightness, Restart, Stop all, resume, preview-only, sharing policy, groups, classic-effect control |
| `src/dj_ledfx/zones/lights.py` | `LightMonitor`: light status, power and colour polling (5 s / 30 s), firmware checks |
| `src/dj_ledfx/zones/attention.py` | `AttentionFeed`: the server-derived attention list |
| `src/dj_ledfx/scheduling/route.py` | `DeviceRoute` and `to_device_colors()` (the one float-to-8-bit conversion) |
| `src/dj_ledfx/persistence/migrations/004_zones_and_looks.sql` | zones, zone_members, looks, look_stars, zone_assignments |
| `src/dj_ledfx/web/contract.py` | Pydantic models for the contract (camelCase aliases) and converters |
| `src/dj_ledfx/web/router_looks.py`, `router_zones.py`, `router_lights.py`, `router_attention.py` | New REST endpoints |
| `src/dj_ledfx/web/errors.py` | `answers()`: zone and look errors become 404, 409 or 400 with the reason |
| `scripts/lifx_record_fixtures.py` | Records real LIFX reply bytes for fixture tests (read-only) |

Modified (paths under `src/dj_ledfx/`): `types.py`, `events.py`, `config.py`, `main.py`, `effects/{base,registry,engine,__init__,beat_pulse,breathe,color_chase,fire_storm,rainbow_wave,strobe}.py`, `scheduling/scheduler.py`, `devices/{adapter,ghost,manager,openrgb}.py`, `devices/lifx/{packet,transport,bulb,strip,tile_chain,discovery}.py`, `devices/govee/{adapter_base,transport}.py`, `persistence/{state_db,toml_io}.py`, `web/{app,state,ws,schemas,router_effects,router_config,router_scene}.py`. Also `pyproject.toml` (the `perf` marker) and `config.toml`.

Frontend (Task 26): modified `frontend/src/{lib/types.ts,lib/api-client.ts,hooks/use-effects.ts,pages/live.tsx,pages/config.tsx}`; new `hooks/use-zones.ts` and `components/look-picker.tsx`; `components/transport-section.tsx` renamed to `components/tempo-section.tsx`; `hooks/use-transport.ts` deleted.

Deleted in the cut-over (Task 24): `transport.py`, `effects/deck.py`, `spatial/pipeline.py`, `spatial/pipeline_manager.py`, `web/router_transport.py`, and their tests.

Written in Task 27: `Dockerfile`, `docker-compose.yml`, `.dockerignore`. They replace the untracked drafts in the main checkout.

Shared test helpers: `tests/conftest.py` gains `FakeLight` (Task 2) and `GlowFirmware` (Task 15); `tests/lifx_fakes.py` answers like a LIFX light (Task 7); `tests/zone_home.py` builds a zone manager over fake lights (Task 16); `tests/api_home.py` builds the app around it (Task 21). `tests/fixtures/lifx/` holds packet bytes checked against LIFX's docs (Task 4) and replies recorded from the real lights (Task 28).

---

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/m1-set-and-forget /home/anirudhlath/code/.worktrees/dj-ledfx/m1-set-and-forget origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/m1-set-and-forget
cd "$W"
test -f docs/superpowers/plans/2026-09-23-m1-set-and-forget.md && test -f docs/design/web-app/looks.json && echo "specs present"
grep -q '^def _file_within' src/dj_ledfx/web/app.py && echo "traversal fix present"
test -f web/package.json && echo "F0 merged" || echo "F0 not merged yet"
```

Expected: `specs present` and `traversal fix present`. If either is missing, the docs PR or PR #10 hasn't merged: stop and tell the owner. Either F0 line is fine. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
```

Without the `web` extra the web tests skip silently and mypy reports dozens of extra errors.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tee /tmp/m1-baseline-mypy.txt | tail -1
```

Expected on 2026-09-24's `master`:

- `680 passed`, in about 20 s.
- `ruff check` is clean.
- `ruff format --check` flags one file, `src/dj_ledfx/spatial/pipeline_manager.py`, which Task 24 deletes.
- mypy reports `Found 26 errors in 8 files`: `web/router_scene.py` 15, `web/router_config.py` 3, `web/app.py` 2, `web/state.py` 2, and one each in `web/ws.py`, `persistence/state_db.py`, `spatial/mapping.py` and `effects/presets.py`.

If `master` has moved (PR #10, F0), record what it says now. These are the numbers every gate compares with.

---

### Task 1: Render context and LED sets

The two types every later effect renders with. `RenderContext` is sampled at the frame's target time; `LedSet` is a zone's LEDs in one fixed order with positions built from each device's own geometry (spec §4.2, §5.1).

**Files:**
- Modify: `src/dj_ledfx/types.py` (add `FloatRGB`)
- Create: `src/dj_ledfx/effects/context.py`
- Create: `src/dj_ledfx/effects/ledset.py`
- Test: `tests/effects/test_context.py`, `tests/effects/test_ledset.py`

**Interfaces:**
- Consumes: `BeatClock.get_state_at(t: float) -> BeatState`; `spatial.geometry.{DeviceGeometry, MatrixGeometry, StripGeometry, TileLayout, expand_positions}`.
- Produces:
  - `dj_ledfx.types.FloatRGB = NDArray[np.float32]` (shape `(n, 3)`, 0..1 per channel)
  - `effects.context.SignalView(values: Mapping[str, float] | None = None)` with `.get(name: str, default: float = 0.0) -> float`; `NO_SIGNALS: SignalView`
  - `effects.context.RenderContext(t, dt, beat_phase, bar_phase, bpm, beat_index, bar_index, signals)` (frozen, slots)
  - `effects.context.render_context(clock: BeatClock, t: float, dt: float) -> RenderContext`
  - `effects.context.to_beat_context(ctx: RenderContext) -> BeatContext`
  - `effects.ledset.DeviceSlice(device_id: str, start: int, stop: int)` with `.count -> int`
  - `effects.ledset.LedSource(device_id: str, led_count: int, geometry: DeviceGeometry | None = None)`
  - `effects.ledset.LedSet` with `pos`, `npos`, `local` (`(N, 3)` float32), `local_u` (`(N,)` float32), `room`, `device` (`(N,)` int32), `anchors: Mapping[str, NDArray[np.float32]]`, `slices: tuple[DeviceSlice, ...]`, `.count -> int`, `.slice_for(device_id: str) -> DeviceSlice | None`
  - `effects.ledset.build_ledset(sources: Sequence[LedSource], gap_m: float = DEVICE_GAP_M) -> LedSet`; constants `LED_PITCH_M = 0.03`, `DEVICE_GAP_M = 0.5`

- [ ] **Step 1: Write the failing tests**

`tests/effects/test_context.py`:

```python
from __future__ import annotations

import time

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.context import (
    NO_SIGNALS,
    RenderContext,
    SignalView,
    render_context,
    to_beat_context,
)


def test_signal_view_returns_default_for_missing_signal() -> None:
    view = SignalView({"loudness": 0.4})
    assert view.get("loudness") == 0.4
    assert view.get("bass") == 0.0
    assert view.get("bass", 0.5) == 0.5


def test_signal_view_is_a_snapshot() -> None:
    values = {"loudness": 0.4}
    view = SignalView(values)
    values["loudness"] = 0.9
    assert view.get("loudness") == 0.4


def test_render_context_samples_the_clock_at_the_target_time() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    target = now + 0.25

    ctx = render_context(clock, target, 1 / 60)

    expected = clock.get_state_at(target)
    assert ctx.t == target
    assert ctx.dt == 1 / 60
    assert ctx.beat_phase == expected.beat_phase
    assert ctx.bar_phase == expected.bar_phase
    assert ctx.bpm == 120.0
    assert (ctx.beat_index, ctx.bar_index) == (0, 0)
    assert ctx.signals is NO_SIGNALS


def test_to_beat_context_keeps_phases_bpm_and_dt() -> None:
    ctx = RenderContext(
        t=1.0,
        dt=0.02,
        beat_phase=0.3,
        bar_phase=0.7,
        bpm=128.0,
        beat_index=0,
        bar_index=0,
        signals=NO_SIGNALS,
    )
    beat = to_beat_context(ctx)
    assert (beat.beat_phase, beat.bar_phase, beat.bpm, beat.dt) == (0.3, 0.7, 128.0, 0.02)
```

`tests/effects/test_ledset.py`:

```python
from __future__ import annotations

import numpy as np

from dj_ledfx.effects.ledset import DEVICE_GAP_M, LedSource, build_ledset
from dj_ledfx.spatial.geometry import MatrixGeometry, PointGeometry, StripGeometry, TileLayout


def test_slices_follow_source_order() -> None:
    leds = build_ledset([LedSource("a", 3), LedSource("b", 5), LedSource("c", 1)])
    assert leds.count == 9
    assert [(s.device_id, s.start, s.stop) for s in leds.slices] == [
        ("a", 0, 3),
        ("b", 3, 8),
        ("c", 8, 9),
    ]
    assert leds.device.tolist() == [0, 0, 0, 1, 1, 1, 1, 1, 2]
    assert leds.slice_for("b") is not None and leds.slice_for("b").count == 5
    assert leds.slice_for("missing") is None


def test_arrays_have_the_documented_shapes_and_types() -> None:
    leds = build_ledset([LedSource("a", 4), LedSource("b", 2)])
    for name in ("pos", "npos", "local"):
        array = getattr(leds, name)
        assert array.shape == (6, 3), name
        assert array.dtype == np.float32, name
    assert leds.local_u.shape == (6,) and leds.local_u.dtype == np.float32
    assert leds.room.dtype == np.int32 and leds.room.tolist() == [0] * 6
    assert leds.device.dtype == np.int32
    assert dict(leds.anchors) == {}


def test_device_without_geometry_is_a_vertical_strip() -> None:
    leds = build_ledset([LedSource("a", 5)])
    assert np.allclose(leds.local_u, [0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.allclose(leds.local[:, 2], [0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.allclose(leds.local[:, 0], 0.5)  # degenerate axis
    assert np.allclose(np.diff(leds.pos[:, 2]), 0.03)


def test_matrix_rows_run_down_from_the_top() -> None:
    matrix = MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 2, 2),))
    leds = build_ledset([LedSource("tile", 4, matrix)])
    # LED order is row-major with row 0 at the top.
    assert np.allclose(leds.local[:, 0], [0.0, 1.0, 0.0, 1.0])
    assert np.allclose(leds.local[:, 2], [1.0, 1.0, 0.0, 0.0])


def test_matrix_with_the_wrong_pixel_count_falls_back_to_a_strip() -> None:
    matrix = MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 8, 8),))
    leds = build_ledset([LedSource("tile", 5, matrix)])
    assert np.allclose(leds.local[:, 2], [0.0, 0.25, 0.5, 0.75, 1.0])


def test_strip_geometry_is_followed() -> None:
    strip = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
    leds = build_ledset([LedSource("strip", 4, strip)])
    assert np.all(np.diff(leds.pos[:, 0]) > 0)
    assert np.allclose(leds.pos[:, 2], 0.0)


def test_point_with_several_leds_falls_back_to_a_strip() -> None:
    leds = build_ledset([LedSource("lamp", 3, PointGeometry())])
    assert np.allclose(leds.local[:, 2], [0.0, 0.5, 1.0])


def test_devices_sit_side_by_side_with_a_gap() -> None:
    strip = StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)
    leds = build_ledset([LedSource("a", 4, strip), LedSource("b", 4, strip)])
    a = leds.pos[leds.device == 0]
    b = leds.pos[leds.device == 1]
    assert b[:, 0].min() - a[:, 0].max() == np.float32(DEVICE_GAP_M)


def test_normalised_positions_span_the_zone() -> None:
    leds = build_ledset([LedSource("a", 3), LedSource("b", 3)])
    assert leds.npos.min() >= 0.0 and leds.npos.max() <= 1.0
    assert np.isclose(leds.npos[:, 0].min(), 0.0) and np.isclose(leds.npos[:, 0].max(), 1.0)
    assert np.allclose(leds.npos[:, 1], 0.5)  # every LED at y = 0


def test_single_led_device() -> None:
    leds = build_ledset([LedSource("bulb", 1)])
    assert leds.count == 1
    assert leds.local_u.tolist() == [0.0]
    assert np.allclose(leds.local, 0.5)


def test_empty_zone_has_no_leds() -> None:
    leds = build_ledset([])
    assert leds.count == 0
    assert leds.pos.shape == (0, 3)
    assert leds.slices == ()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/effects/test_context.py tests/effects/test_ledset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.effects.context'`.

- [ ] **Step 3: Add `FloatRGB` to `src/dj_ledfx/types.py`**

Below `RGB = tuple[int, int, int]`:

```python
FloatRGB = NDArray[np.float32]  # shape (n_leds, 3), linear 0..1 per channel
```

- [ ] **Step 4: Write `src/dj_ledfx/effects/context.py`**

```python
"""What an effect knows about the moment it draws (spec §4.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from dj_ledfx.types import BeatContext

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock


class SignalView:
    """Named input signals sampled at the frame's target time. Empty until M6-M7."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, float] | None = None) -> None:
        self._values: Mapping[str, float] = MappingProxyType(dict(values or {}))

    def get(self, name: str, default: float = 0.0) -> float:
        return self._values.get(name, default)


NO_SIGNALS = SignalView()


@dataclass(frozen=True, slots=True)
class RenderContext:
    t: float  # time (s, time.monotonic() clock) the frame will be shown
    dt: float
    beat_phase: float  # 0..1
    bar_phase: float  # 0..1
    bpm: float
    beat_index: int  # 0 until M3 adds the tempo clock's beat counter
    bar_index: int  # 0 until M3
    signals: SignalView


def render_context(clock: BeatClock, t: float, dt: float) -> RenderContext:
    """Sample the beat clock at the frame's target time `t`."""
    state = clock.get_state_at(t)
    return RenderContext(
        t=t,
        dt=dt,
        beat_phase=state.beat_phase,
        bar_phase=state.bar_phase,
        bpm=state.bpm,
        beat_index=0,
        bar_index=0,
        signals=NO_SIGNALS,
    )


def to_beat_context(ctx: RenderContext) -> BeatContext:
    """The narrow context today's 1D effects render with."""
    return BeatContext(
        beat_phase=ctx.beat_phase, bar_phase=ctx.bar_phase, bpm=ctx.bpm, dt=ctx.dt
    )
```

- [ ] **Step 5: Write `src/dj_ledfx/effects/ledset.py`**

```python
"""A zone's LEDs in one fixed order, with positions (spec §5.1).

M1 has no home map, so build_ledset() lays the zone's devices side by side along x,
each in its own geometry: matrices hang with row 0 at the top, strips follow their
direction, and anything else is a vertical strip with its first LED at the bottom.
M2 replaces the layout with home-map placements; the arrays stay the same.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.spatial.geometry import (
    DeviceGeometry,
    MatrixGeometry,
    StripGeometry,
    expand_positions,
)

LED_PITCH_M = 0.03
DEVICE_GAP_M = 0.5


@dataclass(frozen=True, slots=True)
class DeviceSlice:
    device_id: str
    start: int
    stop: int

    @property
    def count(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True, slots=True)
class LedSource:
    """One device's share of a zone: its id, LED count and own geometry."""

    device_id: str
    led_count: int
    geometry: DeviceGeometry | None = None


@dataclass(frozen=True, eq=False)
class LedSet:
    pos: NDArray[np.float32]  # (N, 3) metres, x east, y south, z up
    npos: NDArray[np.float32]  # (N, 3) normalised to the zone's bounds
    local: NDArray[np.float32]  # (N, 3) normalised to each device's own bounds
    local_u: NDArray[np.float32]  # (N,) position along the device's LED order
    room: NDArray[np.int32]  # (N,) room ids, all 0 until M2
    device: NDArray[np.int32]  # (N,) index into `slices`
    anchors: Mapping[str, NDArray[np.float32]]
    slices: tuple[DeviceSlice, ...]

    @property
    def count(self) -> int:
        return int(self.pos.shape[0])

    def slice_for(self, device_id: str) -> DeviceSlice | None:
        for device_slice in self.slices:
            if device_slice.device_id == device_id:
                return device_slice
        return None


def build_ledset(sources: Sequence[LedSource], gap_m: float = DEVICE_GAP_M) -> LedSet:
    positions: list[NDArray[np.float64]] = []
    locals_: list[NDArray[np.float64]] = []
    along: list[NDArray[np.float64]] = []
    owners: list[NDArray[np.int32]] = []
    slices: list[DeviceSlice] = []
    cursor_x = 0.0
    start = 0
    for index, source in enumerate(sources):
        count = max(0, source.led_count)
        if count:
            local = _local_positions(source.geometry, count)
            low = local.min(axis=0)
            high = local.max(axis=0)
            placed = local - low
            placed[:, 0] += cursor_x
            cursor_x += float(high[0] - low[0]) + gap_m
            positions.append(placed)
            locals_.append(_normalise(local, low, high))
            along.append(np.arange(count) / (count - 1) if count > 1 else np.zeros(1))
            owners.append(np.full(count, index, dtype=np.int32))
        slices.append(DeviceSlice(source.device_id, start, start + count))
        start += count

    pos = np.concatenate(positions) if positions else np.zeros((0, 3))
    npos = _normalise(pos, pos.min(axis=0), pos.max(axis=0)) if len(pos) else pos
    return LedSet(
        pos=pos.astype(np.float32),
        npos=npos.astype(np.float32),
        local=(np.concatenate(locals_) if locals_ else np.zeros((0, 3))).astype(np.float32),
        local_u=(np.concatenate(along) if along else np.zeros(0)).astype(np.float32),
        room=np.zeros(len(pos), dtype=np.int32),
        device=np.concatenate(owners) if owners else np.zeros(0, dtype=np.int32),
        anchors=MappingProxyType({}),
        slices=tuple(slices),
    )


def _normalise(
    values: NDArray[np.float64], low: NDArray[np.float64], high: NDArray[np.float64]
) -> NDArray[np.float64]:
    span = high - low
    out = np.full(values.shape, 0.5)
    spread = span > 1e-9
    out[:, spread] = (values[:, spread] - low[spread]) / span[spread]
    return out


def _local_positions(geometry: DeviceGeometry | None, count: int) -> NDArray[np.float64]:
    if isinstance(geometry, MatrixGeometry) and (
        sum(tile.width * tile.height for tile in geometry.tiles) == count
    ):
        grid = expand_positions(geometry, (0.0, 0.0, 0.0), count)
        return np.column_stack([grid[:, 0], np.zeros(count), grid[:, 1].max() - grid[:, 1]])
    if isinstance(geometry, StripGeometry):
        return expand_positions(geometry, (0.0, 0.0, 0.0), count)
    if count == 1:
        return np.zeros((1, 3))
    # No usable geometry: a point with several LEDs, a matrix whose size disagrees
    # with the LED count, or nothing at all.
    return np.column_stack([np.zeros(count), np.zeros(count), np.arange(count) * LED_PITCH_M])
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/effects/test_context.py tests/effects/test_ledset.py -v`
Expected: PASS (16 tests).

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/types.py src/dj_ledfx/effects/context.py src/dj_ledfx/effects/ledset.py tests/effects/test_context.py tests/effects/test_ledset.py
git commit -m "feat(effects): add RenderContext and LedSet built from device geometry"
```

---

### Task 2: Device capabilities and the light control API

What a light can do (`DeviceCapabilities`), what the app can read back (`LightReading`), and the four control hooks every adapter gains: `capabilities`, `read_light()`, `set_power()`, `prepare_stream()`. `capture_state()` now returns `None` when a light can't be captured, instead of guessing 50% white (spec §8). Adds the `FakeLight` test double that later tasks use.

**Files:**
- Create: `src/dj_ledfx/devices/capabilities.py`
- Modify: `src/dj_ledfx/devices/adapter.py`
- Modify: `src/dj_ledfx/devices/manager.py` (`_capture_device_state` tolerates `None`)
- Modify: `src/dj_ledfx/devices/lifx/bulb.py`, `src/dj_ledfx/devices/lifx/strip.py`, `src/dj_ledfx/devices/govee/adapter_base.py` (`capture_state` return type)
- Modify: `tests/conftest.py` (add `FakeLight`)
- Test: `tests/devices/test_capabilities.py`, `tests/devices/test_adapter_state.py` (rewrite)

**Interfaces:**
- Consumes: `DeviceInfo.backend`, `DeviceInfo.device_type`.
- Produces:
  - `devices.capabilities.LightProtocol = Literal["LIFX", "Govee", "OpenRGB"]`
  - `devices.capabilities.DeviceCapabilities(protocol, model="", colour=True, multizone=False, extended_multizone=False, matrix=False, chain=False, temperature_range=None, firmware_version=None, openrgb_modes=())` (frozen, slots)
  - `devices.capabilities.LightReading(power: bool | None, colour: tuple[int, int, int] | None)` (frozen, slots)
  - `devices.capabilities.FirmwareRejected(Exception)`
  - `devices.capabilities.protocol_of(backend_or_type: str) -> LightProtocol`
  - `DeviceAdapter.capabilities -> DeviceCapabilities` (property), `async read_light() -> LightReading`, `async set_power(on: bool) -> None`, `async prepare_stream() -> None`, `async capture_state() -> bytes | None`
  - `tests/conftest.py`: `FakeLight(stable_id, *, name=None, led_count=4, caps=None, power=True, colour=(255, 200, 150), captured=b"before", connected=True, geometry=None)` with `.calls: list[tuple[str, object]]`, `.frames`, `.power`, `.firmware_running`, `.reject_firmware`, `.names() -> list[str]`

- [ ] **Step 1: Write the failing tests**

`tests/devices/test_capabilities.py`:

```python
from __future__ import annotations

import pytest

from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading, protocol_of


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("lifx", "LIFX"),
        ("lifx_tile", "LIFX"),
        ("govee", "Govee"),
        ("govee_segment", "Govee"),
        ("openrgb", "OpenRGB"),
        ("", "OpenRGB"),
    ],
)
def test_protocol_of(value: str, expected: str) -> None:
    assert protocol_of(value) == expected


def test_capabilities_default_to_a_plain_colour_light() -> None:
    caps = DeviceCapabilities(protocol="Govee")
    assert caps.colour is True
    assert not (caps.multizone or caps.extended_multizone or caps.matrix or caps.chain)
    assert caps.openrgb_modes == ()


def test_light_reading_allows_unknown_values() -> None:
    reading = LightReading(power=None, colour=None)
    assert reading.power is None and reading.colour is None
```

Replace `tests/devices/test_adapter_state.py` with:

```python
"""Default DeviceAdapter state and control hooks."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.types import DeviceInfo


class FakeAdapter(DeviceAdapter):
    """Minimal concrete DeviceAdapter for testing the default hooks."""

    def __init__(self, led_count: int = 10, device_type: str = "fake") -> None:
        self._led_count = led_count
        self._device_type = device_type
        self._connected = True
        self.sent_frames: list[NDArray[np.uint8]] = []

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name="FakeDevice",
            device_type=self._device_type,
            led_count=self._led_count,
            address="fake",
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.sent_frames.append(colors.copy())


@pytest.mark.asyncio
async def test_capture_state_default_is_none() -> None:
    """A light that can't be captured says so, so Off leaves it alone."""
    assert await FakeAdapter().capture_state() is None


@pytest.mark.asyncio
async def test_restore_state_default_sends_the_bytes_as_a_frame() -> None:
    adapter = FakeAdapter(led_count=3)
    state = np.array([[255, 0, 0]] * 3, dtype=np.uint8).tobytes()

    await adapter.restore_state(state)

    assert len(adapter.sent_frames) == 1
    sent = adapter.sent_frames[0]
    assert sent.shape == (3, 3)
    assert np.all(sent[:, 0] == 255) and np.all(sent[:, 1:] == 0)


def test_default_capabilities_follow_the_device_type() -> None:
    assert FakeAdapter(device_type="govee_segment").capabilities.protocol == "Govee"
    assert FakeAdapter(device_type="lifx").capabilities.protocol == "LIFX"
    assert FakeAdapter().capabilities.protocol == "OpenRGB"


@pytest.mark.asyncio
async def test_default_read_light_is_unknown() -> None:
    assert await FakeAdapter().read_light() == LightReading(power=None, colour=None)


@pytest.mark.asyncio
async def test_default_power_and_stream_hooks_do_nothing() -> None:
    adapter = FakeAdapter()
    await adapter.set_power(True)
    await adapter.prepare_stream()
    assert adapter.sent_frames == []
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/devices/test_capabilities.py tests/devices/test_adapter_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.devices.capabilities'`.

- [ ] **Step 3: Write `src/dj_ledfx/devices/capabilities.py`**

```python
"""What a light can do, and what the app can read back from it (spec §6.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LightProtocol = Literal["LIFX", "Govee", "OpenRGB"]


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    protocol: LightProtocol
    model: str = ""
    colour: bool = True
    multizone: bool = False
    extended_multizone: bool = False
    matrix: bool = False
    chain: bool = False
    temperature_range: tuple[int, int] | None = None
    firmware_version: str | None = None
    openrgb_modes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LightReading:
    power: bool | None  # None: the light can't tell us
    colour: tuple[int, int, int] | None  # 8-bit sRGB, None when unknown


class FirmwareRejected(Exception):
    """The light refused a firmware command, or never acknowledged it."""


def protocol_of(backend_or_type: str) -> LightProtocol:
    """Map a DeviceInfo backend (or a ghost's device_type) to the contract's protocol."""
    key = backend_or_type.lower()
    if key.startswith("lifx"):
        return "LIFX"
    if key.startswith("govee"):
        return "Govee"
    return "OpenRGB"
```

- [ ] **Step 4: Add the hooks to `src/dj_ledfx/devices/adapter.py`**

Add the import below the existing imports:

```python
from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading, protocol_of
```

Replace the existing `capture_state` method (the 50% white default) with the block below, and add the three new hooks after `geometry`:

```python
    @property
    def capabilities(self) -> DeviceCapabilities:
        """What the light can do. Default: a streamed-only colour light."""
        info = self.device_info
        return DeviceCapabilities(protocol=protocol_of(info.backend or info.device_type))

    async def read_light(self) -> LightReading:
        """Read power and colour without changing anything. Default: unknown."""
        return LightReading(power=None, colour=None)

    async def set_power(self, on: bool) -> None:  # noqa: B027
        """Switch the light on or off. Default: the protocol can't, so do nothing."""

    async def prepare_stream(self) -> None:  # noqa: B027
        """Get the light ready for streamed frames (stop its own effects, pick direct mode)."""

    async def capture_state(self) -> bytes | None:
        """Capture how the light looks now, to put it back on Off. None: can't capture."""
        return None
```

Keep `restore_state` as it is.

- [ ] **Step 5: Let `DeviceManager._capture_device_state` skip lights that can't be captured**

In `src/dj_ledfx/devices/manager.py`, inside `_capture_device_state`, right after `state_bytes = await adapter.capture_state()`:

```python
            if state_bytes is None:
                return
```

(The whole method goes away in Task 24; this keeps mypy green until then.)

The three adapters that override `capture_state` fall back to `super().capture_state()`, which can now return `None`. Widen their return annotation so mypy accepts it. In `src/dj_ledfx/devices/lifx/bulb.py`, `src/dj_ledfx/devices/lifx/strip.py` and `src/dj_ledfx/devices/govee/adapter_base.py`:

```python
    async def capture_state(self) -> bytes | None:
```

- [ ] **Step 6: Add `FakeLight` to `tests/conftest.py`**

Append (and add the imports to the top of the file):

```python
from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading


class FakeLight(DeviceAdapter):
    """A light that records what the app asks of it. Power and colour are readable."""

    supports_latency_probing = False

    def __init__(
        self,
        stable_id: str,
        *,
        name: str | None = None,
        led_count: int = 4,
        caps: DeviceCapabilities | None = None,
        power: bool | None = True,
        colour: tuple[int, int, int] | None = (255, 200, 150),
        captured: bytes | None = b"before",
        connected: bool = True,
        geometry: DeviceGeometry | None = None,
    ) -> None:
        self.stable_id = stable_id
        self.name = name or stable_id
        self._led_count = led_count
        self._caps = caps or DeviceCapabilities(protocol="LIFX")
        self.power = power
        self.colour = colour
        self.captured = captured
        self.connected = connected
        self._geometry = geometry
        self.firmware_running = False
        self.reject_firmware = False
        self.calls: list[tuple[str, object]] = []
        self.frames: list[NDArray[np.uint8]] = []

    @property
    def device_info(self) -> DeviceInfo:
        backend = self._caps.protocol.lower()
        return DeviceInfo(
            name=self.name,
            device_type=backend,
            led_count=self._led_count,
            address=f"fake://{self.stable_id}",
            stable_id=self.stable_id,
            backend=backend,
        )

    @property
    def is_connected(self) -> bool:
        return self.connected

    @property
    def led_count(self) -> int:
        return self._led_count

    @property
    def geometry(self) -> DeviceGeometry | None:
        return self._geometry

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._caps

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.frames.append(colors.copy())

    async def capture_state(self) -> bytes | None:
        self.calls.append(("capture", None))
        return self.captured

    async def restore_state(self, state: bytes) -> None:
        self.calls.append(("restore", state))

    async def read_light(self) -> LightReading:
        return LightReading(power=self.power, colour=self.colour)

    async def set_power(self, on: bool) -> None:
        self.calls.append(("power", on))
        self.power = on

    async def prepare_stream(self) -> None:
        self.calls.append(("prepare_stream", None))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `uv run pytest tests/devices/test_capabilities.py tests/devices/test_adapter_state.py tests/devices -q`
Expected: PASS. (The Govee tests of `capture_state` still pass: they connect first, so the captured status is returned.)

- [ ] **Step 8: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/capabilities.py src/dj_ledfx/devices/adapter.py src/dj_ledfx/devices/manager.py src/dj_ledfx/devices/lifx/bulb.py src/dj_ledfx/devices/lifx/strip.py src/dj_ledfx/devices/govee/adapter_base.py tests/conftest.py tests/devices/test_capabilities.py tests/devices/test_adapter_state.py
git commit -m "feat(devices): add capabilities, light readings and control hooks to adapters"
```

---

### Task 3: Effect kinds and the strip adapter

Split today's `Effect` into the registry-and-parameters base plus three kinds (spec §5.1): `StripEffect` (today's 1D effects, unchanged render), `FieldEffect` (renders a zone's `LedSet` in float RGB) and `FirmwareEffect` (runs on the light). `StripAdapter` plays any `StripEffect` along a zone's LEDs in order. Adds a `reseed()` hook so looks repeat exactly with a fixed seed (spec §9).

**Files:**
- Modify: `src/dj_ledfx/effects/base.py`
- Create: `src/dj_ledfx/effects/field.py`, `src/dj_ledfx/effects/firmware.py`, `src/dj_ledfx/effects/strip_adapter.py`
- Modify: `src/dj_ledfx/effects/{beat_pulse,breathe,color_chase,fire_storm,rainbow_wave,strobe}.py` (base class), `fire_storm.py` (`reseed`)
- Modify: `src/dj_ledfx/effects/registry.py`, `src/dj_ledfx/effects/deck.py`, `src/dj_ledfx/web/router_effects.py`
- Test: `tests/effects/test_effect_kinds.py`; modify `tests/effects/test_registry.py`

**Interfaces:**
- Consumes: `RenderContext`, `to_beat_context`, `LedSet`, `FloatRGB` (Task 1); `DeviceCapabilities`, `DeviceAdapter` (Task 2).
- Produces:
  - `effects.base.Effect`: `_registry`, `__init_subclass__(register: bool = True)`, `parameters()`, `get_params()`, `set_params(**kw)`, `_apply_params(**kw)`, `reseed(seed: int) -> None`
  - `effects.base.StripEffect(Effect)`: abstract `render(ctx: BeatContext, led_count: int) -> NDArray[np.uint8]`
  - `effects.field.FieldEffect(Effect)`: abstract `render(ctx: RenderContext, leds: LedSet) -> FloatRGB`
  - `effects.firmware.Params = Mapping[str, Any]`; `effects.firmware.FirmwareEffect(Effect)`: `display_name: ClassVar[str]`, abstract `supports(caps) -> bool`, `async start(adapter, params: Params) -> None`, `async stop(adapter) -> None`, `async is_running(adapter) -> bool | None`, `emulate(ctx, leds) -> FloatRGB`; concrete `start_params(brightness: float) -> dict[str, Any]`
  - `effects.strip_adapter.StripAdapter(inner: StripEffect)` (a `FieldEffect`, not registered) with `.inner`
  - `effects.registry`: `get_effect_classes() -> dict[str, type[Effect]]`, `get_effect_class(name) -> type[Effect]` (KeyError if unknown), `get_strip_effect_classes() -> dict[str, type[StripEffect]]`, `get_effect_schemas()` (strip effects only), `create_effect(name, **params) -> Effect`, `create_strip_effect(name, **params) -> StripEffect` (KeyError if unknown or not a strip effect)

- [ ] **Step 1: Write the failing tests**

`tests/effects/test_effect_kinds.py`:

```python
from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.base import Effect, StripEffect
from dj_ledfx.effects.context import NO_SIGNALS, RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.fire_storm import FireStorm
from dj_ledfx.effects.ledset import LedSet, LedSource, build_ledset
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.registry import (
    create_strip_effect,
    get_effect_class,
    get_effect_schemas,
    get_strip_effect_classes,
)
from dj_ledfx.effects.strip_adapter import StripAdapter
from dj_ledfx.types import BeatContext, FloatRGB

CLASSIC = {"beat_pulse", "breathe", "color_chase", "fire_storm", "rainbow_wave", "strobe"}


def _ctx(t: float = 1.0) -> RenderContext:
    return RenderContext(
        t=t, dt=1 / 60, beat_phase=0.25, bar_phase=0.5, bpm=128.0,
        beat_index=0, bar_index=0, signals=NO_SIGNALS,
    )


class _Ramp(StripEffect, register=False):
    """Red ramps 0..255 along the strip."""

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"level": EffectParam(type="float", default=1.0, min=0.0, max=1.0)}

    def __init__(self, level: float = 1.0) -> None:
        self.level = level

    def get_params(self) -> dict[str, Any]:
        return {"level": self.level}

    def _apply_params(self, **kwargs: Any) -> None:
        self.level = float(kwargs.get("level", self.level))

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        out = np.zeros((led_count, 3), dtype=np.uint8)
        out[:, 0] = np.linspace(0, 255 * self.level, led_count).astype(np.uint8)
        return out


class _Probe(FirmwareEffect, register=False):
    display_name = "Probe"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"period": EffectParam(type="float", default=4.0, min=1.0, max=10.0)}

    def __init__(self, period: float = 4.0) -> None:
        self.period = period

    def get_params(self) -> dict[str, Any]:
        return {"period": self.period}

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.matrix

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        return None

    async def stop(self, adapter: DeviceAdapter) -> None:
        return None

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        return None

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return np.zeros((leds.count, 3), dtype=np.float32)


def test_classic_effects_are_registered_strip_effects() -> None:
    strips = get_strip_effect_classes()
    assert CLASSIC <= set(strips)
    for name in CLASSIC:
        assert issubclass(strips[name], StripEffect)


def test_abstract_kinds_and_opt_outs_are_not_registered() -> None:
    for name in ("strip_effect", "field_effect", "firmware_effect", "strip_adapter", "_ramp"):
        assert name not in Effect._registry


def test_schemas_cover_strip_effects_only() -> None:
    class ProbeField(FieldEffect):
        def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
            return np.zeros((leds.count, 3), dtype=np.float32)

    assert get_effect_class("probe_field") is ProbeField
    assert "probe_field" not in get_effect_schemas()
    assert CLASSIC <= set(get_effect_schemas())
    del Effect._registry["probe_field"]


def test_unknown_kinds_raise_key_error() -> None:
    with pytest.raises(KeyError):
        get_effect_class("no_such_effect")
    with pytest.raises(KeyError):
        create_strip_effect("no_such_effect")


def test_create_strip_effect_refuses_other_kinds() -> None:
    class ProbeField2(FieldEffect):
        def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
            return np.zeros((leds.count, 3), dtype=np.float32)

    with pytest.raises(KeyError, match="strip"):
        create_strip_effect("probe_field2")
    del Effect._registry["probe_field2"]


def test_strip_adapter_plays_the_strip_along_the_leds_in_order() -> None:
    leds = build_ledset([LedSource("a", 3), LedSource("b", 2)])
    colors = StripAdapter(_Ramp()).render(_ctx(), leds)
    assert colors.shape == (5, 3)
    assert colors.dtype == np.float32
    assert np.allclose(colors[:, 0], np.linspace(0, 255, 5).astype(np.uint8) / 255.0)
    assert np.all(colors[:, 1:] == 0.0)


def test_strip_adapter_forwards_parameters() -> None:
    inner = _Ramp()
    adapter = StripAdapter(inner)
    adapter.set_params(level=0.5)
    assert inner.level == 0.5
    assert adapter.get_params() == {"level": 0.5}
    with pytest.raises(ValueError):
        adapter.set_params(level=2.0)


def test_fire_storm_repeats_after_reseed() -> None:
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=1 / 60)
    a, b = FireStorm(), FireStorm()
    a.reseed(7)
    b.reseed(7)
    for _ in range(3):
        assert np.array_equal(a.render(ctx, 12), b.render(ctx, 12))


def test_start_params_add_brightness_to_the_settings() -> None:
    assert _Probe(period=6.0).start_params(0.4) == {"period": 6.0, "brightness": 0.4}
```

In `tests/effects/test_registry.py`:
- change `from dj_ledfx.effects.base import Effect` to `from dj_ledfx.effects.base import Effect, StripEffect`, and `class DummyEffect(Effect):` to `class DummyEffect(StripEffect):` (`_BadEffect(Effect)` stays: a concrete `Effect` with a bad parameter list must still raise);
- add `get_strip_effect_classes` to the `from dj_ledfx.effects.registry import (...)` block;
- in the three smoke tests (`test_all_registered_effects_render_with_defaults`, `..._with_zero_bpm`, `..._with_zero_leds`) replace `get_effect_classes().items()` with `get_strip_effect_classes().items()`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/effects/test_effect_kinds.py tests/effects/test_registry.py -v`
Expected: FAIL with `ImportError: cannot import name 'StripEffect' from 'dj_ledfx.effects.base'`.

- [ ] **Step 3: Rewrite `src/dj_ledfx/effects/base.py`**

```python
"""Effect base classes with parameter introspection and auto-registry."""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext


def _to_snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class Effect(ABC):  # noqa: B024
    """Registry and parameters shared by every effect kind (strip, field, firmware).

    The kinds below declare the abstract methods, so this class has none of its own.
    Concrete subclasses register under their snake_case class name unless the name
    starts with "_" or the class is declared with `register=False`.
    """

    _registry: ClassVar[dict[str, type[Effect]]] = {}

    def __init_subclass__(cls, register: bool = True, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        params = cls.parameters()
        if params:
            sig = inspect.signature(cls.__init__)
            init_params = {p for p in sig.parameters if p != "self"}
            missing = set(params.keys()) - init_params
            if missing:
                raise TypeError(
                    f"{cls.__name__} parameters() declares {missing} "
                    f"but __init__ does not accept them"
                )
        if register and not cls.__name__.startswith("_"):
            Effect._registry[_to_snake_case(cls.__name__)] = cls

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def set_params(self, **kwargs: Any) -> None:
        schema = self.parameters()
        for key, value in kwargs.items():
            if key not in schema:
                raise ValueError(f"Unknown parameter: {key}")
            param = schema[key]
            if param.type in ("float", "int"):
                if param.min is not None and value < param.min:
                    raise ValueError(f"{key}={value} below min {param.min}")
                if param.max is not None and value > param.max:
                    raise ValueError(f"{key}={value} above max {param.max}")
            if param.type == "choice" and value not in (param.choices or []):
                raise ValueError(f"{key}={value} not in {param.choices}")
        self._apply_params(**kwargs)

    def _apply_params(self, **kwargs: Any) -> None:  # noqa: B027
        pass

    def reseed(self, seed: int) -> None:  # noqa: B027
        """Make the effect's randomness repeatable. Default: it has none."""


class StripEffect(Effect):
    """Today's 1D effects: a strip of `led_count` LEDs in 8-bit RGB."""

    @abstractmethod
    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        """Return shape (led_count, 3) uint8 RGB array."""
```

- [ ] **Step 4: Write `src/dj_ledfx/effects/field.py`**

```python
"""Field effects render every LED of a zone at its position (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from dj_ledfx.effects.base import Effect

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class FieldEffect(Effect):
    @abstractmethod
    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Return shape (leds.count, 3) float32, 0..1 per channel, vectorised numpy."""
```

- [ ] **Step 5: Write `src/dj_ledfx/effects/firmware.py`**

```python
"""Firmware effects ask a light to run one of its own built-in effects (spec §5.1)."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from dj_ledfx.effects.base import Effect

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.capabilities import DeviceCapabilities
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

Params = Mapping[str, Any]


class FirmwareEffect(Effect):
    display_name: ClassVar[str] = ""  # the light's "own effect" name, e.g. "LIFX Flame"

    @abstractmethod
    def supports(self, caps: DeviceCapabilities) -> bool: ...

    @abstractmethod
    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        """Start (or restart) the effect. Raise FirmwareRejected if the light refuses."""

    @abstractmethod
    async def stop(self, adapter: DeviceAdapter) -> None: ...

    @abstractmethod
    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        """Whether the light still runs it; None when the protocol can't say."""

    @abstractmethod
    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """A streamed copy for lights that can't run it, and what the preview shows."""

    def start_params(self, brightness: float) -> dict[str, Any]:
        """What start() receives: this layer's settings plus the zone brightness (0-1)."""
        return {**self.get_params(), "brightness": brightness}
```

- [ ] **Step 6: Write `src/dj_ledfx/effects/strip_adapter.py`**

```python
"""Plays a 1D strip effect along a zone's LEDs (spec §5.1).

M1 uses the LED order along the zone's devices; M2 adds projecting each LED's
position onto an axis, linear or radial like today's mappings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from dj_ledfx.effects.context import to_beat_context
from dj_ledfx.effects.field import FieldEffect

if TYPE_CHECKING:
    from dj_ledfx.effects.base import StripEffect
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB


class StripAdapter(FieldEffect, register=False):
    def __init__(self, inner: StripEffect) -> None:
        self.inner = inner

    def get_params(self) -> dict[str, Any]:
        return self.inner.get_params()

    def set_params(self, **kwargs: Any) -> None:
        self.inner.set_params(**kwargs)

    def reseed(self, seed: int) -> None:
        self.inner.reseed(seed)

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        colors = self.inner.render(to_beat_context(ctx), leds.count)
        out = colors.astype(np.float32)
        out *= np.float32(1.0 / 255.0)
        return out
```

- [ ] **Step 7: Re-base the six effects and seed Fire storm**

In each of `beat_pulse.py`, `breathe.py`, `color_chase.py`, `fire_storm.py`, `rainbow_wave.py`, `strobe.py`: change `from dj_ledfx.effects.base import Effect` to `from dj_ledfx.effects.base import StripEffect` and the class line from `(Effect)` to `(StripEffect)`. Nothing else changes.

In `fire_storm.py`, add to `FireStorm`:

```python
    def reseed(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)
        self._prev_frame = None
```

- [ ] **Step 8: Update `src/dj_ledfx/effects/registry.py`**

```python
"""Effect class registry and schema discovery."""

from __future__ import annotations

from typing import Any

from dj_ledfx.effects.base import Effect, StripEffect
from dj_ledfx.effects.params import EffectParam


def get_effect_classes() -> dict[str, type[Effect]]:
    return dict(Effect._registry)


def get_effect_class(name: str) -> type[Effect]:
    """The registered class for an effect kind. Raises KeyError if unknown."""
    return Effect._registry[name]


def get_strip_effect_classes() -> dict[str, type[StripEffect]]:
    return {
        name: cls for name, cls in Effect._registry.items() if issubclass(cls, StripEffect)
    }


def get_effect_schemas() -> dict[str, dict[str, EffectParam]]:
    """Parameter schemas of the 1D strip effects, for the old UI's effect deck."""
    return {name: cls.parameters() for name, cls in get_strip_effect_classes().items()}


def create_effect(name: str, **params: Any) -> Effect:
    return Effect._registry[name](**params)


def create_strip_effect(name: str, **params: Any) -> StripEffect:
    cls = Effect._registry[name]
    if not issubclass(cls, StripEffect):
        raise KeyError(f"{name} is not a strip effect")
    return cls(**params)
```

- [ ] **Step 9: Keep the deck and the effects router on strip effects**

In `src/dj_ledfx/effects/deck.py`: import `StripEffect` instead of `Effect` (`from dj_ledfx.effects.base import StripEffect, _to_snake_case`); type `__init__(self, effect: StripEffect, ...)`, the `effect` property's return type and `swap_effect(self, new_effect: StripEffect)` as `StripEffect`; in `apply_update` import and call `create_strip_effect` instead of `create_effect`.

In `src/dj_ledfx/web/router_effects.py`: import `create_strip_effect` instead of `create_effect`, and in `load_preset` call `new_effect = create_strip_effect(preset.effect_class, **preset.params)`.

- [ ] **Step 10: Run the tests to see them pass**

Run: `uv run pytest tests/effects tests/web/test_router_effects.py -q`
Expected: PASS.

- [ ] **Step 11: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/effects tests/effects src/dj_ledfx/web/router_effects.py
git commit -m "feat(effects): split effect kinds into strip, field and firmware with a strip adapter"
```

---

### Task 4: LIFX message codec

Encoders and decoders for every LIFX message M1 adds (firmware effects, power, host firmware, unhandled replies), and a fix for `StateDeviceChain`, which today reads a tile count from byte 1 when the protocol puts it at byte 881. Byte layouts come from the LIFX LAN protocol docs (lan.developer.lifx.com, "Tile messages", "Multizone messages", "Light messages", "Field types"); the fixtures below were packed independently from those layouts. Task 28 adds fixtures recorded from the real lights.

| Message | Type | Payload layout (little-endian) | Size |
|---|---|---|---|
| GetHostFirmware / StateHostFirmware | 14 / 15 | build u64, reserved 8, version_minor u16, version_major u16 | 0 / 20 |
| GetVersion / StateVersion | 32 / 33 | vendor u32, product u32, reserved 4 | 0 / 12 |
| SetWaveform | 103 | reserved u8, transient u8, HSBK, period u32 ms, cycles f32, skew_ratio i16, waveform u8 | 21 |
| SetLightPower | 117 | level u16 (0 or 65535), duration u32 ms | 6 |
| StateUnhandled | 223 | unhandled_type u16 | 2 |
| GetMultiZoneEffect / SetMultiZoneEffect / StateMultiZoneEffect | 507 / 508 / 509 | instanceid u32, type u8, reserved 2, speed u32 ms, duration u64 ns, reserved 8, parameters 32 (Move: direction u32 at parameter offset 4; 0 reversed, 1 forward) | 0 / 59 / 59 |
| GetDeviceChain / StateDeviceChain | 701 / 702 | start_index u8, 16 tile slots of 55 bytes (width u8 at 16, height u8 at 17), tile_devices_count u8 | 0 / 882 |
| GetTileEffect | 718 | reserved 2 | 2 |
| SetTileEffect | 719 | reserved 2, instanceid u32, type u8, speed u32 ms, duration u64 ns, reserved 8, parameters 32, palette_count u8, palette 16 × HSBK | 188 |
| StateTileEffect | 720 | reserved 1, then as SetTileEffect from instanceid | 187 |

Enums: TileEffectType OFF 0, MORPH 2, FLAME 3, SKY 5; MultiZoneEffectType OFF 0, MOVE 1; Waveform SAW 0, SINE 1, HALF_SINE 2, TRIANGLE 3, PULSE 4.

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/packet.py`
- Create: `tests/fixtures/lifx/*.hex` (8 files, below)
- Create: `tests/devices/lifx/test_effect_packets.py`
- Modify: `tests/devices/lifx/test_packet.py` (replace `test_parse_state_device_chain`)

**Interfaces:**
- Consumes: `lifx.types.TileInfo`.
- Produces (all in `devices.lifx.packet`):
  - constants `GET_HOST_FIRMWARE`, `STATE_HOST_FIRMWARE`, `GET_VERSION`, `STATE_VERSION`, `GET_COLOR`, `SET_COLOR`, `SET_WAVEFORM`, `LIGHT_STATE`, `SET_LIGHT_POWER`, `STATE_UNHANDLED`, `GET_MULTIZONE_EFFECT`, `SET_MULTIZONE_EFFECT`, `STATE_MULTIZONE_EFFECT`, `SET_EXTENDED_COLOR_ZONES`, `GET_DEVICE_CHAIN`, `STATE_DEVICE_CHAIN`, `GET_TILE_EFFECT`, `SET_TILE_EFFECT`, `STATE_TILE_EFFECT`
  - `HSBK = tuple[int, int, int, int]`; `TileEffectType`, `MultiZoneEffectType`, `Waveform` (IntEnum)
  - `TileEffectState(instance_id, effect, speed_ms, palette: tuple[HSBK, ...])`, `MultiZoneEffectState(instance_id, effect, speed_ms, reverse: bool)`
  - `build_set_tile_effect(effect, speed_ms, palette=(), *, instance_id=0, duration_ns=0) -> bytes`, `build_get_tile_effect() -> bytes`, `parse_state_tile_effect(payload) -> TileEffectState`
  - `build_set_multizone_effect(effect, speed_ms, *, reverse=False, instance_id=0, duration_ns=0) -> bytes`, `parse_state_multizone_effect(payload) -> MultiZoneEffectState`
  - `build_set_waveform(hsbk, period_ms, cycles, waveform, *, transient=True, skew_ratio=0.5) -> bytes`
  - `build_set_light_power(on: bool, duration_ms: int = 0) -> bytes`
  - `parse_state_host_firmware(payload) -> tuple[int, int]` (major, minor), `parse_state_unhandled(payload) -> int`
  - `parse_state_device_chain(payload) -> list[TileInfo]` (fixed layout; raises `ValueError` when short)

- [ ] **Step 1: Add the fixtures**

Each file is a comment line and one line of hex (the payload only, no header).

`tests/fixtures/lifx/set_tile_effect_flame.hex`:
```
# SetTileEffect(719) FLAME, speed 4000 ms, no palette. Packed from the LAN protocol docs.
00000000000003a00f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
```

`tests/fixtures/lifx/set_tile_effect_morph.hex`:
```
# SetTileEffect(719) MORPH, speed 6000 ms, palette hue 0, 21845, 43690 at full saturation and brightness, 3500 K.
0000000000000270170000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000030000ffffffffac0d5555ffffffffac0daaaaffffffffac0d0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
```

`tests/fixtures/lifx/set_multizone_effect_move.hex`:
```
# SetMultiZoneEffect(508) MOVE, speed 8000 ms, direction forward (1).
00000000010000401f0000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000
```

`tests/fixtures/lifx/set_waveform_sine.hex`:
```
# SetWaveform(103) transient SINE to HSBK (0, 65535, 32768, 3500), period 4000 ms, 1e6 cycles, skew 0.5.
00010000ffff0080ac0da00f000000247449000001
```

`tests/fixtures/lifx/set_light_power_on.hex`:
```
# SetLightPower(117) on, duration 0.
ffff00000000
```

`tests/fixtures/lifx/state_tile_effect_flame.hex`:
```
# StateTileEffect(720) instance 7, FLAME, speed 4000 ms, no palette.
000700000003a00f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
```

`tests/fixtures/lifx/state_multizone_effect_move.hex`:
```
# StateMultiZoneEffect(509) instance 9, MOVE, speed 8000 ms, direction reversed (0).
09000000010000401f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
```

`tests/fixtures/lifx/state_host_firmware.hex`:
```
# StateHostFirmware(15) build 1650000000000000000, version 3.90.
0000650742fae51600000000000000005a000300
```

- [ ] **Step 2: Write the failing tests**

`tests/devices/lifx/test_effect_packets.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from dj_ledfx.devices.lifx.packet import (
    MultiZoneEffectType,
    TileEffectType,
    Waveform,
    build_get_tile_effect,
    build_set_light_power,
    build_set_multizone_effect,
    build_set_tile_effect,
    build_set_waveform,
    parse_state_host_firmware,
    parse_state_multizone_effect,
    parse_state_tile_effect,
    parse_state_unhandled,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "lifx"


def load_hex(name: str) -> bytes:
    lines = (FIXTURES / name).read_text().splitlines()
    return bytes.fromhex("".join(line for line in lines if not line.startswith("#")))


def test_set_tile_effect_flame_matches_fixture() -> None:
    payload = build_set_tile_effect(TileEffectType.FLAME, 4000)
    assert len(payload) == 188
    assert payload == load_hex("set_tile_effect_flame.hex")


def test_set_tile_effect_morph_matches_fixture() -> None:
    palette = [(0, 65535, 65535, 3500), (21845, 65535, 65535, 3500), (43690, 65535, 65535, 3500)]
    payload = build_set_tile_effect(TileEffectType.MORPH, 6000, palette)
    assert payload == load_hex("set_tile_effect_morph.hex")


def test_set_tile_effect_keeps_at_most_16_palette_colours() -> None:
    payload = build_set_tile_effect(TileEffectType.MORPH, 1000, [(i, 0, 0, 3500) for i in range(20)])
    assert len(payload) == 188
    assert payload[59] == 16


def test_get_tile_effect_is_two_reserved_bytes() -> None:
    assert build_get_tile_effect() == b"\x00\x00"


def test_set_multizone_effect_move_matches_fixture() -> None:
    payload = build_set_multizone_effect(MultiZoneEffectType.MOVE, 8000)
    assert len(payload) == 59
    assert payload == load_hex("set_multizone_effect_move.hex")


def test_set_multizone_effect_reverse_sets_direction_zero() -> None:
    payload = build_set_multizone_effect(MultiZoneEffectType.MOVE, 8000, reverse=True)
    assert payload[31:35] == b"\x00\x00\x00\x00"


def test_set_waveform_matches_fixture() -> None:
    payload = build_set_waveform((0, 65535, 32768, 3500), 4000, 1e6, Waveform.SINE)
    assert len(payload) == 21
    assert payload == load_hex("set_waveform_sine.hex")


def test_set_light_power_matches_fixture() -> None:
    assert build_set_light_power(True) == load_hex("set_light_power_on.hex")
    assert build_set_light_power(False) == b"\x00\x00\x00\x00\x00\x00"


def test_parse_state_tile_effect() -> None:
    state = parse_state_tile_effect(load_hex("state_tile_effect_flame.hex"))
    assert state.instance_id == 7
    assert state.effect == TileEffectType.FLAME
    assert state.speed_ms == 4000
    assert state.palette == ()


def test_parse_state_tile_effect_reads_the_palette() -> None:
    palette = [(100, 200, 300, 3500), (400, 500, 600, 4000)]
    set_payload = build_set_tile_effect(TileEffectType.MORPH, 5000, palette, instance_id=3)
    # StateTileEffect is SetTileEffect with one reserved byte fewer at the front.
    state = parse_state_tile_effect(set_payload[1:])
    assert state.effect == TileEffectType.MORPH
    assert state.instance_id == 3
    assert state.palette == tuple(palette)


def test_parse_state_tile_effect_rejects_short_payloads() -> None:
    with pytest.raises(ValueError):
        parse_state_tile_effect(b"\x00" * 20)


def test_parse_state_multizone_effect() -> None:
    state = parse_state_multizone_effect(load_hex("state_multizone_effect_move.hex"))
    assert state.instance_id == 9
    assert state.effect == MultiZoneEffectType.MOVE
    assert state.speed_ms == 8000
    assert state.reverse is True


def test_parse_state_host_firmware() -> None:
    assert parse_state_host_firmware(load_hex("state_host_firmware.hex")) == (3, 90)


def test_parse_state_unhandled() -> None:
    assert parse_state_unhandled(b"\xcf\x02") == 719
```

In `tests/devices/lifx/test_packet.py`, replace `test_parse_state_device_chain` with:

```python
    @staticmethod
    def _chain_payload(tiles: list[tuple[int, int, float, float]]) -> bytes:
        """StateDeviceChain as documented: start_index, 16 slots of 55 bytes, count."""
        slots = b""
        for width, height, user_x, user_y in tiles:
            slots += struct.pack(
                "<hhh2sffBBBII4sQ8sHH4s",
                10, -20, 980, b"\x00\x00", user_x, user_y, width, height, 0,
                1, 57, b"\x00" * 4, 0, b"\x00" * 8, 90, 3, b"\x00" * 4,
            )
        slots = slots.ljust(16 * 55, b"\x00")
        return struct.pack("<B", 0) + slots + struct.pack("<B", len(tiles))

    def test_parse_state_device_chain_single_candle(self) -> None:
        payload = self._chain_payload([(5, 6, 0.0, 0.0)])
        assert len(payload) == 882
        tiles = parse_state_device_chain(payload)
        assert len(tiles) == 1
        assert (tiles[0].width, tiles[0].height) == (5, 6)
        assert (tiles[0].accel_x, tiles[0].accel_y, tiles[0].accel_z) == (10, -20, 980)

    def test_parse_state_device_chain_two_tiles(self) -> None:
        tiles = parse_state_device_chain(
            self._chain_payload([(8, 8, 0.0, 0.0), (8, 8, 1.0, 0.5)])
        )
        assert [(t.width, t.height, t.user_x, t.user_y) for t in tiles] == [
            (8, 8, 0.0, 0.0),
            (8, 8, 1.0, 0.5),
        ]

    def test_parse_state_device_chain_rejects_short_payloads(self) -> None:
        with pytest.raises(ValueError):
            parse_state_device_chain(b"\x00\x01" + b"\x00" * 55)
```

(Add `import pytest` to the file's imports if it isn't there.)

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/devices/lifx/test_effect_packets.py tests/devices/lifx/test_packet.py -v`
Expected: FAIL with `ImportError: cannot import name 'MultiZoneEffectType'`.

- [ ] **Step 4: Add the codec to `src/dj_ledfx/devices/lifx/packet.py`**

Add `from collections.abc import Sequence` and `from enum import IntEnum` to the imports, then add below `PROTOCOL = 1024`:

```python
# --- Message types (LIFX LAN protocol) ---
GET_HOST_FIRMWARE = 14
STATE_HOST_FIRMWARE = 15
GET_VERSION = 32
STATE_VERSION = 33
GET_COLOR = 101
SET_COLOR = 102
SET_WAVEFORM = 103
LIGHT_STATE = 107
SET_LIGHT_POWER = 117
STATE_UNHANDLED = 223
GET_MULTIZONE_EFFECT = 507
SET_MULTIZONE_EFFECT = 508
STATE_MULTIZONE_EFFECT = 509
SET_EXTENDED_COLOR_ZONES = 510
GET_DEVICE_CHAIN = 701
STATE_DEVICE_CHAIN = 702
GET_TILE_EFFECT = 718
SET_TILE_EFFECT = 719
STATE_TILE_EFFECT = 720

HSBK = tuple[int, int, int, int]
TILE_EFFECT_PALETTE_MAX = 16
DEVICE_CHAIN_SLOTS = 16
TILE_ENTRY_SIZE = 55


class TileEffectType(IntEnum):
    OFF = 0
    MORPH = 2
    FLAME = 3
    SKY = 5


class MultiZoneEffectType(IntEnum):
    OFF = 0
    MOVE = 1


class Waveform(IntEnum):
    SAW = 0
    SINE = 1
    HALF_SINE = 2
    TRIANGLE = 3
    PULSE = 4


@dataclass(frozen=True, slots=True)
class TileEffectState:
    instance_id: int
    effect: int  # a TileEffectType value; unknown values are kept as they are
    speed_ms: int
    palette: tuple[HSBK, ...]


@dataclass(frozen=True, slots=True)
class MultiZoneEffectState:
    instance_id: int
    effect: int  # a MultiZoneEffectType value
    speed_ms: int
    reverse: bool
```

Add these builders after `build_set_extended_color_zones`:

```python
def build_set_tile_effect(
    effect: TileEffectType,
    speed_ms: int,
    palette: Sequence[HSBK] = (),
    *,
    instance_id: int = 0,
    duration_ns: int = 0,
) -> bytes:
    """SetTileEffect(719) payload, 188 bytes. Flame ignores the palette; Morph uses it."""
    colors = list(palette)[:TILE_EFFECT_PALETTE_MAX]
    head = struct.pack(
        "<BBIBIQII", 0, 0, instance_id, int(effect), speed_ms, duration_ns, 0, 0
    )
    body = b"".join(struct.pack("<4H", *c) for c in colors)
    return (
        head
        + bytes(32)
        + struct.pack("<B", len(colors))
        + body.ljust(TILE_EFFECT_PALETTE_MAX * 8, b"\x00")
    )


def build_get_tile_effect() -> bytes:
    """GetTileEffect(718) payload: two reserved bytes."""
    return b"\x00\x00"


def build_set_multizone_effect(
    effect: MultiZoneEffectType,
    speed_ms: int,
    *,
    reverse: bool = False,
    instance_id: int = 0,
    duration_ns: int = 0,
) -> bytes:
    """SetMultiZoneEffect(508) payload, 59 bytes. Move's direction: 0 reversed, 1 forward."""
    parameters = struct.pack("<II", 0, 0 if reverse else 1) + bytes(24)
    head = struct.pack(
        "<IBHIQII", instance_id, int(effect), 0, speed_ms, duration_ns, 0, 0
    )
    return head + parameters


def build_set_waveform(
    hsbk: HSBK,
    period_ms: int,
    cycles: float,
    waveform: Waveform,
    *,
    transient: bool = True,
    skew_ratio: float = 0.5,
) -> bytes:
    """SetWaveform(103) payload, 21 bytes. skew_ratio 0..1 is PULSE's duty cycle."""
    skew = max(-32768, min(32767, round(skew_ratio * 65535) - 32768))
    return struct.pack(
        "<BB4HIfhB", 0, int(transient), *hsbk, period_ms, cycles, skew, int(waveform)
    )


def build_set_light_power(on: bool, duration_ms: int = 0) -> bytes:
    """SetLightPower(117) payload, 6 bytes."""
    return struct.pack("<HI", 65535 if on else 0, duration_ms)
```

Replace `parse_state_device_chain` with the fixed version, and add the new parsers after it:

```python
def parse_state_device_chain(payload: bytes) -> list[TileInfo]:
    """StateDeviceChain(702): start_index, 16 tile slots of 55 bytes, then the tile count."""
    from dj_ledfx.devices.lifx.types import TileInfo as TileInfoCls

    expected = 1 + DEVICE_CHAIN_SLOTS * TILE_ENTRY_SIZE + 1
    if len(payload) < expected:
        raise ValueError(f"StateDeviceChain payload too short: {len(payload)} < {expected}")
    count = min(payload[expected - 1], DEVICE_CHAIN_SLOTS)
    tiles: list[TileInfoCls] = []
    for index in range(count):
        start = 1 + index * TILE_ENTRY_SIZE
        entry = payload[start : start + TILE_ENTRY_SIZE]
        accel_x, accel_y, accel_z = struct.unpack("<hhh", entry[0:6])
        user_x, user_y = struct.unpack("<ff", entry[8:16])
        tiles.append(
            TileInfoCls(
                user_x=user_x,
                user_y=user_y,
                width=entry[16],
                height=entry[17],
                accel_x=accel_x,
                accel_y=accel_y,
                accel_z=accel_z,
            )
        )
    return tiles


def parse_state_tile_effect(payload: bytes) -> TileEffectState:
    """StateTileEffect(720), 187 bytes."""
    if len(payload) < 187:
        raise ValueError(f"StateTileEffect payload too short: {len(payload)} < 187")
    _reserved, instance_id, effect, speed_ms, _duration, _r1, _r2 = struct.unpack(
        "<BIBIQII", payload[:26]
    )
    count = min(payload[58], TILE_EFFECT_PALETTE_MAX)
    palette: list[HSBK] = []
    for index in range(count):
        start = 59 + index * 8
        hue, sat, bri, kelvin = struct.unpack("<4H", payload[start : start + 8])
        palette.append((hue, sat, bri, kelvin))
    return TileEffectState(int(instance_id), int(effect), int(speed_ms), tuple(palette))


def parse_state_multizone_effect(payload: bytes) -> MultiZoneEffectState:
    """StateMultiZoneEffect(509), 59 bytes."""
    if len(payload) < 59:
        raise ValueError(f"StateMultiZoneEffect payload too short: {len(payload)} < 59")
    instance_id, effect, _r, speed_ms, _duration, _r1, _r2 = struct.unpack(
        "<IBHIQII", payload[:27]
    )
    (direction,) = struct.unpack("<I", payload[31:35])
    return MultiZoneEffectState(
        int(instance_id), int(effect), int(speed_ms), reverse=direction == 0
    )


def parse_state_host_firmware(payload: bytes) -> tuple[int, int]:
    """StateHostFirmware(15) -> (major, minor)."""
    _build, _reserved, minor, major = struct.unpack("<QQHH", payload[:20])
    return int(major), int(minor)


def parse_state_unhandled(payload: bytes) -> int:
    """StateUnhandled(223) -> the message type the light didn't handle."""
    (unhandled,) = struct.unpack("<H", payload[:2])
    return int(unhandled)
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/devices/lifx -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/lifx/packet.py tests/fixtures/lifx tests/devices/lifx/test_effect_packets.py tests/devices/lifx/test_packet.py
git commit -m "feat(lifx): encode firmware effect, power and firmware messages; fix StateDeviceChain layout"
```

---

### Task 5: LIFX transport: matched request and reply

Today `request_response()`, discovery and `_query_version()` each swap the transport's single packet handler while they wait, so two requests in flight steal each other's replies and echo probes are dropped meanwhile. The light monitor (Task 19) polls every zone light every 5 s, concurrently, so replies must be matched to their request. This task matches replies by `(device IP, sequence number)`, accepts `StateUnhandled` (223) as a reply so callers can tell "refused" from "no answer", and gives discovery persistent listeners.

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/transport.py` (rewrite below)
- Modify: `src/dj_ledfx/devices/lifx/bulb.py`, `src/dj_ledfx/devices/lifx/strip.py`, `src/dj_ledfx/devices/lifx/discovery.py` (check the reply type)
- Test: `tests/devices/lifx/test_transport.py` (add tests)

**Interfaces:**
- Consumes: `LifxPacket`, message constants and parsers from Task 4.
- Produces:
  - `LifxTransport.request_response(packet: LifxPacket, addr: tuple[str, int], response_type: int | Collection[int], timeout: float = 1.0) -> LifxPacket | None`: assigns the packet a fresh sequence number; returns the reply (which may be `STATE_UNHANDLED`), or `None` on timeout
  - `LifxTransport.add_listener(listener: PacketListener) -> None`, `remove_listener(listener) -> None`; `PacketListener = Callable[[LifxPacket, tuple[str, int]], None]`
  - `LifxTransport.make_request(mac: bytes, msg_type: int, payload: bytes = b"") -> LifxPacket`
  - `LifxTransport.query_host_firmware(mac: bytes, ip: str, port: int) -> tuple[int, int] | None` (major, minor)
  - `LifxTransport.query_version(mac: bytes, ip: str, port: int) -> tuple[int, int] | None` (vendor, product; two tries)
  - `LifxTransport._query_version(mac, ip, port) -> tuple[int, int]` keeps its contract ((1, 0) when the light doesn't answer)

- [ ] **Step 1: Write the failing tests**

Append to `tests/devices/lifx/test_transport.py` (add `import asyncio` and `import struct` to the imports, and `from dj_ledfx.devices.lifx.packet import STATE_UNHANDLED`):

```python
class _Sent:
    """Stands in for the UDP socket and keeps what was sent."""

    def __init__(self) -> None:
        self.packets: list[tuple[LifxPacket, tuple[str, int]]] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.packets.append((LifxPacket.unpack(data), addr))

    def close(self) -> None:
        pass


def _transport() -> tuple[LifxTransport, _Sent]:
    transport = LifxTransport()
    sent = _Sent()
    transport._socket = sent  # type: ignore[assignment]
    transport._is_open = True
    return transport, sent


def _request(msg_type: int = 101) -> LifxPacket:
    return LifxPacket(
        tagged=False,
        source=0,
        target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
        ack_required=False,
        res_required=True,
        sequence=0,
        msg_type=msg_type,
        payload=b"",
    )


def _reply(transport: LifxTransport, request: LifxPacket, msg_type: int, payload: bytes) -> bytes:
    return LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=request.target,
        ack_required=False,
        res_required=False,
        sequence=request.sequence,
        msg_type=msg_type,
        payload=payload,
    ).pack()


@pytest.mark.asyncio
async def test_concurrent_requests_get_their_own_replies() -> None:
    transport, sent = _transport()
    first = asyncio.create_task(transport.request_response(_request(), ("10.0.0.1", 56700), 107))
    second = asyncio.create_task(transport.request_response(_request(), ("10.0.0.2", 56700), 107))
    await asyncio.sleep(0)
    (req_a, _), (req_b, _) = sent.packets
    assert req_a.sequence != req_b.sequence

    # Replies arrive in the opposite order.
    transport._on_packet_received(_reply(transport, req_b, 107, b"B"), ("10.0.0.2", 56700))
    transport._on_packet_received(_reply(transport, req_a, 107, b"A"), ("10.0.0.1", 56700))

    reply_a, reply_b = await asyncio.gather(first, second)
    assert reply_a is not None and reply_a.payload == b"A"
    assert reply_b is not None and reply_b.payload == b"B"


@pytest.mark.asyncio
async def test_reply_with_another_sequence_is_ignored() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    stray = LifxPacket(
        tagged=False, source=transport.source_id, target=request.target,
        ack_required=False, res_required=False, sequence=(request.sequence + 1) % 256,
        msg_type=107, payload=b"x",
    )
    transport._on_packet_received(stray.pack(), ("10.0.0.1", 56700))
    assert await task is None


@pytest.mark.asyncio
async def test_reply_from_another_light_is_ignored() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    transport._on_packet_received(_reply(transport, request, 107, b"x"), ("10.0.0.9", 56700))
    assert await task is None


@pytest.mark.asyncio
async def test_state_unhandled_answers_the_request() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(transport.request_response(_request(719), ("10.0.0.1", 56700), 720))
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    transport._on_packet_received(
        _reply(transport, request, STATE_UNHANDLED, struct.pack("<H", 719)), ("10.0.0.1", 56700)
    )
    reply = await task
    assert reply is not None and reply.msg_type == STATE_UNHANDLED


@pytest.mark.asyncio
async def test_timeout_returns_none_and_forgets_the_request() -> None:
    transport, _ = _transport()
    reply = await transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.02)
    assert reply is None
    assert transport._waiters == {}


@pytest.mark.asyncio
async def test_echo_replies_are_handled_while_a_request_waits() -> None:
    transport, sent = _transport()
    rtts: list[float] = []
    record = LifxDeviceRecord(mac=b"\xaa" * 6, ip="10.0.0.1", port=56700, vendor=1, product=1)
    transport.register_device(record, rtt_callback=rtts.append)
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)

    seq = transport.next_sequence()
    transport._pending_probes[seq] = ("10.0.0.1", time.monotonic())
    echo = LifxPacket(
        tagged=False, source=transport.source_id, target=b"\xaa" * 6 + b"\x00\x00",
        ack_required=False, res_required=False, sequence=seq % 256, msg_type=59,
        payload=seq.to_bytes(8, "little") + b"\x00" * 56,
    )
    transport._on_packet_received(echo.pack(), ("10.0.0.1", 56700))

    assert len(rtts) == 1
    await task


@pytest.mark.asyncio
async def test_listeners_see_packets_while_a_request_waits() -> None:
    transport, sent = _transport()
    seen: list[int] = []
    transport.add_listener(lambda pkt, addr: seen.append(pkt.msg_type))
    task = asyncio.create_task(
        transport.request_response(_request(), ("10.0.0.1", 56700), 107, timeout=0.05)
    )
    await asyncio.sleep(0)
    service = LifxPacket(
        tagged=False, source=transport.source_id, target=b"\xbb" * 6 + b"\x00\x00",
        ack_required=False, res_required=False, sequence=0, msg_type=3,
        payload=struct.pack("<BI", 1, 56700),
    )
    transport._on_packet_received(service.pack(), ("10.0.0.7", 56700))
    assert seen == [3]
    await task


@pytest.mark.asyncio
async def test_query_host_firmware() -> None:
    transport, sent = _transport()
    task = asyncio.create_task(transport.query_host_firmware(b"\xaa" * 6, "10.0.0.1", 56700))
    await asyncio.sleep(0)
    request, _ = sent.packets[0]
    assert request.msg_type == 14
    transport._on_packet_received(
        _reply(transport, request, 15, struct.pack("<QQHH", 0, 0, 77, 2)), ("10.0.0.1", 56700)
    )
    assert await task == (2, 77)


@pytest.mark.asyncio
async def test_query_version_retries_once_then_defaults_to_a_bulb() -> None:
    transport, sent = _transport()
    assert await transport._query_version(b"\xaa" * 6, "10.0.0.1", 56700) == (1, 0)
    assert [p.msg_type for p, _ in sent.packets] == [32, 32]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/devices/lifx/test_transport.py -v`
Expected: FAIL (`AttributeError: 'LifxTransport' object has no attribute '_waiters'`, `add_listener`, `query_host_firmware`).

- [ ] **Step 3: Rewrite `src/dj_ledfx/devices/lifx/transport.py`**

```python
from __future__ import annotations

import asyncio
import dataclasses
import random
import time
from collections.abc import Callable, Collection

from loguru import logger

from dj_ledfx.devices.lifx.packet import (
    GET_HOST_FIRMWARE,
    GET_VERSION,
    STATE_HOST_FIRMWARE,
    STATE_UNHANDLED,
    STATE_VERSION,
    LifxPacket,
    build_echo_request,
    parse_state_host_firmware,
    parse_state_service,
    parse_state_version,
)
from dj_ledfx.devices.lifx.types import LifxDeviceRecord

PacketListener = Callable[[LifxPacket, tuple[str, int]], None]
_Waiter = tuple[frozenset[int], "asyncio.Future[LifxPacket]"]


class LifxTransport:
    """Shared UDP transport for all LIFX devices on the network.

    Replies are matched to their request by (device IP, sequence number), so any
    number of requests can be in flight at once. Discovery listens through
    add_listener() instead of replacing the packet handler.
    """

    def __init__(self) -> None:
        self._source_id = random.randint(2, 0xFFFFFFFF)
        self._sequence_counter = 0
        self._socket: asyncio.DatagramTransport | None = None
        self._protocol: _LifxUDPProtocol | None = None
        self._probe_task: asyncio.Task[None] | None = None
        self._is_open = False

        # Device registry: (ip, port) -> device record
        self._devices: dict[tuple[str, int], LifxDeviceRecord] = {}
        # RTT callbacks: ip -> callback(rtt_ms)
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}
        # Pending echo probes: sequence_counter -> (device_ip, send_time)
        self._pending_probes: dict[int, tuple[str, float]] = {}
        # Requests waiting for a reply: (ip, wire sequence) -> (accepted types, future)
        self._waiters: dict[tuple[str, int], _Waiter] = {}
        self._listeners: list[PacketListener] = []

    @property
    def source_id(self) -> int:
        return self._source_id

    @property
    def is_open(self) -> bool:
        return self._is_open

    def next_sequence(self) -> int:
        self._sequence_counter += 1
        return self._sequence_counter

    async def open(self) -> None:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _LifxUDPProtocol(self),
            local_addr=("0.0.0.0", 0),
            allow_broadcast=True,
        )
        self._socket = transport
        self._protocol = protocol
        self._is_open = True
        logger.debug("LIFX transport opened on port {}", self._socket.get_extra_info("sockname"))

    async def close(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        if self._socket:
            self._socket.close()
        self._is_open = False
        self._devices.clear()
        self._rtt_callbacks.clear()
        self._pending_probes.clear()
        for _types, future in self._waiters.values():
            future.cancel()
        self._waiters.clear()
        self._listeners.clear()
        logger.debug("LIFX transport closed")

    def send_packet(self, packet: LifxPacket, addr: tuple[str, int]) -> None:
        if self._socket:
            self._socket.sendto(packet.pack(), addr)

    def make_request(self, mac: bytes, msg_type: int, payload: bytes = b"") -> LifxPacket:
        """A unicast packet that asks for a reply. request_response() sets the sequence."""
        return LifxPacket(
            tagged=False,
            source=self._source_id,
            target=mac + b"\x00\x00",
            ack_required=False,
            res_required=True,
            sequence=0,
            msg_type=msg_type,
            payload=payload,
        )

    def register_device(
        self,
        record: LifxDeviceRecord,
        rtt_callback: Callable[[float], None] | None = None,
    ) -> None:
        key = (record.ip, record.port)
        self._devices[key] = record
        if rtt_callback:
            self._rtt_callbacks[record.ip] = rtt_callback

    def add_listener(self, listener: PacketListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: PacketListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def request_response(
        self,
        packet: LifxPacket,
        addr: tuple[str, int],
        response_type: int | Collection[int],
        timeout: float = 1.0,
    ) -> LifxPacket | None:
        """Send `packet` and wait for its reply.

        The reply is one of `response_type`, or StateUnhandled (223) when the light
        doesn't support the message. Returns None on timeout.
        """
        accepted = {response_type} if isinstance(response_type, int) else set(response_type)
        seq = self.next_sequence() % 256
        key = (addr[0], seq)
        future: asyncio.Future[LifxPacket] = asyncio.get_running_loop().create_future()
        self._waiters[key] = (frozenset(accepted | {STATE_UNHANDLED}), future)
        try:
            self.send_packet(dataclasses.replace(packet, sequence=seq), addr)
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return None
        finally:
            self._waiters.pop(key, None)

    def start_probing(self, interval_s: float = 2.0) -> None:
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))

    async def _probe_loop(self, interval_s: float) -> None:
        while self._is_open:
            now = time.monotonic()
            stale = [k for k, (_, t) in self._pending_probes.items() if now - t > interval_s]
            for k in stale:
                del self._pending_probes[k]

            for (ip, port), record in self._devices.items():
                seq = self.next_sequence()
                self._pending_probes[seq] = (record.ip, now)
                pkt = LifxPacket(
                    tagged=False,
                    source=self._source_id,
                    target=record.mac + b"\x00\x00",
                    ack_required=False,
                    res_required=False,
                    sequence=seq % 256,
                    msg_type=58,
                    payload=build_echo_request(seq.to_bytes(8, "little")),
                )
                self.send_packet(pkt, (ip, port))

            await asyncio.sleep(interval_s)

    def _broadcast_get_service(self, addr: tuple[str, int]) -> None:
        self.send_packet(
            LifxPacket(
                tagged=True,
                source=self._source_id,
                target=b"\x00" * 8,
                ack_required=False,
                res_required=False,
                sequence=self.next_sequence() % 256,
                msg_type=2,
                payload=b"",
            ),
            addr,
        )

    async def discover(
        self,
        timeout_s: float = 1.0,
        on_record: Callable[[LifxDeviceRecord], None] | None = None,
    ) -> list[LifxDeviceRecord]:
        """Broadcast GetService, collect responses, query versions.

        If *on_record* is provided it is called as soon as each device's
        version query completes, rather than waiting for all devices.
        """
        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex -> (mac, ip, port)
        version_tasks: list[asyncio.Task[LifxDeviceRecord | None]] = []
        results: list[LifxDeviceRecord] = []

        async def _query_version_and_record(
            mac: bytes, ip: str, port: int
        ) -> LifxDeviceRecord | None:
            vendor, product = await self._query_version(mac, ip, port)
            record = LifxDeviceRecord(mac=mac, ip=ip, port=port, vendor=vendor, product=product)
            results.append(record)
            if on_record is not None:
                on_record(record)
            return record

        def _on_state_service(pkt: LifxPacket, addr: tuple[str, int]) -> None:
            if pkt.msg_type != 3:
                return
            service, port = parse_state_service(pkt.payload)
            if service != 1:  # UDP
                return
            mac = pkt.target[:6]
            if mac.hex() not in discovered:
                discovered[mac.hex()] = (mac, addr[0], port)
                version_tasks.append(
                    asyncio.create_task(_query_version_and_record(mac, addr[0], port))
                )

        self.add_listener(_on_state_service)
        try:
            # Broadcast GetService 3 times, 1 second apart; dedup by MAC
            for i in range(3):
                self._broadcast_get_service(("255.255.255.255", 56700))
                if i < 2:
                    await asyncio.sleep(1.0)
            remaining = timeout_s - 2.0
            if remaining > 0:
                await asyncio.sleep(remaining)
        finally:
            self.remove_listener(_on_state_service)

        if version_tasks:
            await asyncio.gather(*version_tasks, return_exceptions=True)

        logger.info("LIFX discovery found {} devices", len(results))
        return results

    async def unicast_sweep(
        self,
        subnet_hosts: list[str],
        concurrency: int = 50,
        timeout_s: float = 0.5,
    ) -> list[LifxDeviceRecord]:
        """Send GetService to every IP in the list. Rate-limited."""
        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex -> (mac, ip, port)

        def _on_state_service(pkt: LifxPacket, addr: tuple[str, int]) -> None:
            if pkt.msg_type != 3:
                return
            service, port = parse_state_service(pkt.payload)
            if service == 1:  # UDP
                mac = pkt.target[:6]
                discovered[mac.hex()] = (mac, addr[0], port)

        self.add_listener(_on_state_service)
        try:
            sem = asyncio.Semaphore(concurrency)

            async def _probe_host(ip: str) -> None:
                async with sem:
                    self._broadcast_get_service((ip, 56700))

            await asyncio.gather(*[_probe_host(ip) for ip in subnet_hosts])
            await asyncio.sleep(timeout_s)
        finally:
            self.remove_listener(_on_state_service)

        results: list[LifxDeviceRecord] = []
        for mac, ip, port in discovered.values():
            vendor, product = await self._query_version(mac, ip, port)
            results.append(
                LifxDeviceRecord(mac=mac, ip=ip, port=port, vendor=vendor, product=product)
            )

        logger.info("LIFX unicast sweep found {} devices", len(results))
        return results

    async def query_version(self, mac: bytes, ip: str, port: int) -> tuple[int, int] | None:
        """(vendor, product), or None if the light doesn't answer two tries."""
        request = self.make_request(mac, GET_VERSION)
        for _attempt in range(2):
            reply = await self.request_response(request, (ip, port), STATE_VERSION, timeout=0.5)
            if reply is not None and reply.msg_type == STATE_VERSION:
                vendor, product, _version = parse_state_version(reply.payload)
                return int(vendor), int(product)
        return None

    async def _query_version(self, mac: bytes, ip: str, port: int) -> tuple[int, int]:
        """Query a device's vendor and product. Returns (1, 0) if it never answers."""
        version = await self.query_version(mac, ip, port)
        if version is None:
            logger.warning("LIFX device {} did not respond to GetVersion, defaulting to bulb", ip)
            return 1, 0
        return version

    async def query_host_firmware(self, mac: bytes, ip: str, port: int) -> tuple[int, int] | None:
        """(major, minor) of the light's firmware, or None if it doesn't answer."""
        reply = await self.request_response(
            self.make_request(mac, GET_HOST_FIRMWARE), (ip, port), STATE_HOST_FIRMWARE, 0.5
        )
        if reply is None or reply.msg_type != STATE_HOST_FIRMWARE:
            return None
        return parse_state_host_firmware(reply.payload)

    def _on_packet_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            pkt = LifxPacket.unpack(data)
        except Exception:
            return

        if pkt.msg_type == 59:  # EchoResponse
            self._handle_echo_response(pkt, addr)
            return

        waiter = self._waiters.get((addr[0], pkt.sequence))
        if waiter is not None:
            accepted, future = waiter
            if pkt.msg_type in accepted and not future.done():
                future.set_result(pkt)

        for listener in tuple(self._listeners):
            listener(pkt, addr)

    def _handle_echo_response(self, pkt: LifxPacket, addr: tuple[str, int]) -> None:
        if len(pkt.payload) >= 8:
            seq = int.from_bytes(pkt.payload[:8], "little")
        else:
            return

        probe = self._pending_probes.pop(seq, None)
        if probe is None:
            return

        device_ip, send_time = probe
        rtt_ms = (time.monotonic() - send_time) * 1000.0
        callback = self._rtt_callbacks.get(device_ip)
        if callback:
            callback(rtt_ms)
            logger.trace("RTT for {}: {:.1f}ms", device_ip, rtt_ms)


class _LifxUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, transport_owner: LifxTransport) -> None:
        self._owner = transport_owner

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._owner._on_packet_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("LIFX UDP error: {}", exc)
```

- [ ] **Step 4: Check the reply type at the existing call sites**

A reply can now be `StateUnhandled`, so each existing caller must check the type before parsing:
- `bulb.py` `capture_state`: `if response is not None:` becomes `if response is not None and response.msg_type == 107:`
- `strip.py` `capture_state`: `if response is not None:` becomes `if response is not None and response.msg_type == 512:`
- `discovery.py` (matrix branch): `if resp:` becomes `if resp is not None and resp.msg_type == 702:`
- `discovery.py` (multizone branch): `if resp:` becomes `if resp is not None and resp.msg_type == 512:`

(Tasks 7 and 8 rewrite these files; this keeps them correct in between.)

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/devices/lifx -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/lifx tests/devices/lifx/test_transport.py
git commit -m "fix(lifx): match replies to requests so concurrent requests and probes don't collide"
```

---

### Task 6: LIFX capabilities from products.json

Replace the hard-coded `MATRIX_PRODUCTS` and `MULTIZONE_PRODUCTS` sets with LIFX's own product registry (spec §6.3). Today's sets are wrong: pid 70 is the LIFX Switch (listed as matrix and multizone), pid 90 is a Clean A19 bulb (listed as multizone), and the Candles past pid 68, the Tube, Spot, Path, Ceiling and Neon are missing.

**Files:**
- Create: `src/dj_ledfx/devices/lifx/data/products.json` (vendored, pinned)
- Create: `src/dj_ledfx/devices/lifx/products.py`
- Test: `tests/devices/lifx/test_products.py`

**Interfaces:**
- Consumes: `DeviceCapabilities` (Task 2).
- Produces:
  - `devices.lifx.products.PRODUCTS_SHA256: str`, `PRODUCTS_URL: str`
  - `devices.lifx.products.LifxProduct(pid, name, colour, multizone, extended_multizone, matrix, chain, relays, temperature_range)` (frozen, slots)
  - `devices.lifx.products.lifx_product(pid: int, firmware: tuple[int, int] | None, vid: int = 1) -> LifxProduct | None`: features from the vendor defaults, then the product, then every upgrade the firmware has reached; `None` for an unknown product
  - `devices.lifx.products.lifx_capabilities(pid: int, firmware: tuple[int, int] | None, vid: int = 1) -> DeviceCapabilities`: an unknown product is a colour bulb named `"LIFX product {pid}"`; `firmware_version` is `"{major}.{minor}"` when known

- [ ] **Step 1: Vendor the registry**

```bash
mkdir -p src/dj_ledfx/devices/lifx/data
curl -fsSL -o src/dj_ledfx/devices/lifx/data/products.json \
  https://raw.githubusercontent.com/LIFX/products/8adbe485db11621639f693f3a1510603f029c902/products.json
echo "09f6b87367ea3a974cd4be9e7a562db73e1776d012854fb487b00ac9be520360  src/dj_ledfx/devices/lifx/data/products.json" | sha256sum -c
```

Expected: `src/dj_ledfx/devices/lifx/data/products.json: OK`. Hatchling packages everything under `src/dj_ledfx`, so the file ships in the wheel and the Docker image without build changes.

- [ ] **Step 2: Write the failing tests**

`tests/devices/lifx/test_products.py`:

```python
from __future__ import annotations

import hashlib
from importlib.resources import files

import pytest

from dj_ledfx.devices.lifx.products import PRODUCTS_SHA256, lifx_capabilities, lifx_product


def test_vendored_registry_matches_the_pin() -> None:
    data = (files("dj_ledfx.devices.lifx") / "data" / "products.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == PRODUCTS_SHA256


@pytest.mark.parametrize("pid", [57, 68, 137, 138, 185, 186, 215, 216])
def test_candles_are_matrix_lights(pid: int) -> None:
    product = lifx_product(pid, (3, 90))
    assert product is not None
    assert product.matrix and not product.chain and not product.multizone


def test_tile_is_a_matrix_chain() -> None:
    product = lifx_product(55, (3, 70))
    assert product is not None and product.matrix and product.chain


@pytest.mark.parametrize("pid", [171, 173, 176, 177, 217, 218])
def test_spot_path_ceiling_and_tube_are_matrix_lights(pid: int) -> None:
    product = lifx_product(pid, (4, 10))
    assert product is not None and product.matrix


@pytest.mark.parametrize("pid", [141, 142, 205, 206])
def test_neon_is_extended_multizone(pid: int) -> None:
    product = lifx_product(pid, (4, 10))
    assert product is not None and product.multizone and product.extended_multizone


def test_first_lifx_z_has_no_extended_multizone() -> None:
    product = lifx_product(31, (1, 22))
    assert product is not None and product.multizone and not product.extended_multizone


def test_upgrades_apply_from_their_firmware_version() -> None:
    before = lifx_product(32, (2, 76))
    after = lifx_product(32, (2, 77))
    unknown = lifx_product(32, None)
    assert before is not None and not before.extended_multizone
    assert after is not None and after.extended_multizone
    assert unknown is not None and not unknown.extended_multizone


def test_temperature_range_upgrade() -> None:
    old = lifx_product(27, (2, 70))
    new = lifx_product(27, (2, 80))
    assert old is not None and old.temperature_range == (2500, 9000)
    assert new is not None and new.temperature_range == (1500, 9000)


def test_switch_and_clean_bulb_are_no_longer_misclassified() -> None:
    switch = lifx_product(70, None)
    clean = lifx_product(90, None)
    assert switch is not None and switch.relays and not switch.matrix and not switch.multizone
    assert clean is not None and not clean.multizone and not clean.matrix


def test_unknown_product() -> None:
    assert lifx_product(9999, (3, 0)) is None
    caps = lifx_capabilities(9999, (3, 0))
    assert caps.protocol == "LIFX"
    assert caps.model == "LIFX product 9999"
    assert caps.colour and not caps.matrix and not caps.multizone


def test_capabilities_carry_model_firmware_and_features() -> None:
    caps = lifx_capabilities(217, (4, 10))
    assert caps.model == "LIFX Tube"
    assert caps.firmware_version == "4.10"
    assert caps.matrix and caps.colour
    assert caps.temperature_range == (1500, 9000)
    assert lifx_capabilities(217, None).firmware_version is None
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/devices/lifx/test_products.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.devices.lifx.products'`.

- [ ] **Step 4: Write `src/dj_ledfx/devices/lifx/products.py`**

```python
"""LIFX product capabilities from LIFX's own registry (spec §6.3).

`data/products.json` is a pinned copy of https://github.com/LIFX/products. To update it,
download products.json from a newer commit, update PRODUCTS_URL and PRODUCTS_SHA256,
and run tests/devices/lifx/test_products.py.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from dj_ledfx.devices.capabilities import DeviceCapabilities

PRODUCTS_URL = (
    "https://raw.githubusercontent.com/LIFX/products/"
    "8adbe485db11621639f693f3a1510603f029c902/products.json"
)
PRODUCTS_SHA256 = "09f6b87367ea3a974cd4be9e7a562db73e1776d012854fb487b00ac9be520360"


@dataclass(frozen=True, slots=True)
class LifxProduct:
    pid: int
    name: str
    colour: bool
    multizone: bool
    extended_multizone: bool
    matrix: bool
    chain: bool
    relays: bool  # a switch, not a light
    temperature_range: tuple[int, int] | None


@functools.cache
def _registry() -> dict[int, tuple[dict[str, Any], dict[int, dict[str, Any]]]]:
    """vid -> (vendor defaults, pid -> product entry)."""
    raw = (files("dj_ledfx.devices.lifx") / "data" / "products.json").read_bytes()
    vendors: list[dict[str, Any]] = json.loads(raw)
    return {
        int(vendor["vid"]): (
            dict(vendor.get("defaults", {})),
            {int(product["pid"]): product for product in vendor["products"]},
        )
        for vendor in vendors
    }


def lifx_product(pid: int, firmware: tuple[int, int] | None, vid: int = 1) -> LifxProduct | None:
    vendor = _registry().get(vid)
    if vendor is None:
        return None
    defaults, products = vendor
    entry = products.get(pid)
    if entry is None:
        return None
    features: dict[str, Any] = {**defaults, **entry.get("features", {})}
    if firmware is not None:
        for upgrade in entry.get("upgrades", []):
            if firmware >= (int(upgrade["major"]), int(upgrade["minor"])):
                features.update(upgrade.get("features", {}))
    temperature = features.get("temperature_range")
    return LifxProduct(
        pid=pid,
        name=str(entry["name"]),
        colour=bool(features.get("color", False)),
        multizone=bool(features.get("multizone", False)),
        extended_multizone=bool(features.get("extended_multizone", False)),
        matrix=bool(features.get("matrix", False)),
        chain=bool(features.get("chain", False)),
        relays=bool(features.get("relays", False)),
        temperature_range=(int(temperature[0]), int(temperature[1])) if temperature else None,
    )


def lifx_capabilities(
    pid: int, firmware: tuple[int, int] | None, vid: int = 1
) -> DeviceCapabilities:
    version = f"{firmware[0]}.{firmware[1]}" if firmware is not None else None
    product = lifx_product(pid, firmware, vid)
    if product is None:
        return DeviceCapabilities(
            protocol="LIFX", model=f"LIFX product {pid}", firmware_version=version
        )
    return DeviceCapabilities(
        protocol="LIFX",
        model=product.name,
        colour=product.colour,
        multizone=product.multizone,
        extended_multizone=product.extended_multizone,
        matrix=product.matrix,
        chain=product.chain,
        temperature_range=product.temperature_range,
        firmware_version=version,
    )
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/devices/lifx/test_products.py -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/lifx/data/products.json src/dj_ledfx/devices/lifx/products.py tests/devices/lifx/test_products.py
git commit -m "feat(lifx): read product capabilities from LIFX's vendored products.json"
```

---

### Task 7: LIFX adapters: shared base, control, capture and matrix size

The three LIFX adapters share one base that gives them the light control API from Task 2 (power, colour reads, getting ready to stream), confirmed firmware commands for Task 10, and a capture that includes power and any running firmware effect, so Off can put a Candle's Flame back (spec §6.3, §7.1, §8). The matrix adapter takes its size from `StateDeviceChain` instead of 64 LEDs per tile, so a Candle is its real 5 × 6 matrix.

This task also fixes `parse_state_extended_color_zones`: it read colours from byte 4, but `StateExtendedColorZones` has a `colors_count` byte there and the colours start at byte 5 (LIFX LAN docs, "Information messages", packet 512).

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/packet.py` (constants, `hsbk_to_rgb`, the zones parser)
- Create: `src/dj_ledfx/devices/lifx/base.py`
- Modify (rewrite): `src/dj_ledfx/devices/lifx/bulb.py`, `src/dj_ledfx/devices/lifx/strip.py`, `src/dj_ledfx/devices/lifx/tile_chain.py`
- Create: `tests/lifx_fakes.py` (`FakeLifxTransport`, a transport that answers like a LIFX light)
- Test: `tests/devices/lifx/test_lifx_control.py`; modify `tests/devices/lifx/test_packet.py` (`test_parse_state_extended_color_zones`)

**Interfaces:**
- Consumes: Task 2 (`DeviceCapabilities`, `LightReading`, `FirmwareRejected`); Task 4 codec; Task 5 `LifxTransport.make_request`, `request_response`.
- Produces:
  - `packet.STATE_LIGHT_POWER = 118`, `packet.GET_EXTENDED_COLOR_ZONES = 511`, `packet.STATE_EXTENDED_COLOR_ZONES = 512`, `packet.SET_TILE_STATE_64 = 715`, `packet.hsbk_to_rgb(hsbk: HSBK) -> tuple[int, int, int]`
  - `lifx.base.LifxAdapterBase(transport, device_info, target_mac, *, kelvin: int, caps: DeviceCapabilities)`: `capabilities`, `read_light()`, `set_power(on)`, `prepare_stream()`, `capture_state() -> bytes | None`, `restore_state(state)`, `async set_colour(hsbk: HSBK, duration_ms: int = 0) -> None`, `async set_waveform(hsbk, period_ms: int, cycles: float, waveform: Waveform, *, transient: bool = True, skew_ratio: float = 0.5) -> None` (both raise `FirmwareRejected`)
  - `lifx.base.hsbk_from_json(values: object) -> HSBK`
  - `LifxBulbAdapter(transport, device_info, target_mac, kelvin=3500, *, caps=None)`
  - `LifxStripAdapter(transport, device_info, target_mac, zone_count=1, kelvin=3500, *, caps=None)` plus `async set_zone_colours(colours: Sequence[HSBK], duration_ms: int = 0)`, `async start_multizone_effect(effect: MultiZoneEffectType, speed_ms: int, *, reverse: bool = False)` (raise `FirmwareRejected`), `async multizone_effect() -> MultiZoneEffectState | None`
  - `LifxTileChainAdapter(transport, device_info, target_mac, tile_count=5, kelvin=3500, *, tiles: Sequence[TileInfo] = (), caps=None)` plus `tiles`, `geometry -> MatrixGeometry`, `async start_tile_effect(effect: TileEffectType, speed_ms: int, palette: Sequence[HSBK] = ())` (raises `FirmwareRejected`), `async tile_effect() -> TileEffectState | None`
  - Captured state is JSON: `{"v": 1, "power": bool, "hsbk": [h, s, b, k]}` plus `"zones"` and `"multizone_effect"` (strips) or `"tile_effect"` (matrices) when present
  - `tests/lifx_fakes.FakeLifxTransport(*, power=True, hsbk=(0, 0, 65535, 3500), label="Lamp", zones=(), product=1, firmware=(3, 70), chain=(), unhandled=(), silent=False)` with `.sent`, `.types()`, `.last(msg_type)`, `.tile_effect: tuple[int, int, tuple[HSBK, ...]]`, `.multizone_effect: tuple[int, int, bool]`, `query_version()`, `query_host_firmware()`; `chain` is a list of `(width, height)` tiles

- [ ] **Step 1: Write the fake transport**

`tests/lifx_fakes.py`:

```python
"""A stand-in for LifxTransport that answers requests the way a LIFX light does."""

from __future__ import annotations

import struct
from collections.abc import Collection, Sequence

from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    GET_DEVICE_CHAIN,
    GET_EXTENDED_COLOR_ZONES,
    GET_HOST_FIRMWARE,
    GET_MULTIZONE_EFFECT,
    GET_TILE_EFFECT,
    GET_VERSION,
    HSBK,
    LIGHT_STATE,
    SET_COLOR,
    SET_EXTENDED_COLOR_ZONES,
    SET_LIGHT_POWER,
    SET_MULTIZONE_EFFECT,
    SET_TILE_EFFECT,
    SET_WAVEFORM,
    STATE_DEVICE_CHAIN,
    STATE_EXTENDED_COLOR_ZONES,
    STATE_HOST_FIRMWARE,
    STATE_LIGHT_POWER,
    STATE_MULTIZONE_EFFECT,
    STATE_TILE_EFFECT,
    STATE_UNHANDLED,
    STATE_VERSION,
    LifxPacket,
)


class FakeLifxTransport:
    """Records every packet. Requests get the reply a light would send, or None when silent."""

    def __init__(
        self,
        *,
        power: bool = True,
        hsbk: HSBK = (0, 0, 65535, 3500),
        label: str = "Lamp",
        zones: Sequence[HSBK] = (),
        product: int = 1,
        firmware: tuple[int, int] = (3, 70),
        chain: Sequence[tuple[int, int]] = (),
        unhandled: Collection[int] = (),
        silent: bool = False,
    ) -> None:
        self.source_id = 4242
        self.power = power
        self.hsbk = hsbk
        self.label = label
        self.zones: list[HSBK] = list(zones)
        self.product = product
        self.firmware = firmware
        self.chain = list(chain)  # (width, height) per tile
        self.tile_effect: tuple[int, int, tuple[HSBK, ...]] = (0, 0, ())
        self.multizone_effect: tuple[int, int, bool] = (0, 0, False)
        self.unhandled = set(unhandled)
        self.silent = silent
        self.is_open = True
        self.sent: list[LifxPacket] = []
        self._sequence = 0

    def next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def make_request(self, mac: bytes, msg_type: int, payload: bytes = b"") -> LifxPacket:
        return LifxPacket(
            tagged=False,
            source=self.source_id,
            target=mac + b"\x00\x00",
            ack_required=False,
            res_required=True,
            sequence=0,
            msg_type=msg_type,
            payload=payload,
        )

    def send_packet(self, packet: LifxPacket, addr: tuple[str, int]) -> None:
        self.sent.append(packet)
        self._apply(packet)

    async def request_response(
        self,
        packet: LifxPacket,
        addr: tuple[str, int],
        response_type: int | Collection[int],
        timeout: float = 1.0,
    ) -> LifxPacket | None:
        self.sent.append(packet)
        if self.silent:
            return None
        if packet.msg_type in self.unhandled:
            return self._reply(STATE_UNHANDLED, struct.pack("<H", packet.msg_type))
        self._apply(packet)
        return self._state_for(packet.msg_type)

    async def query_version(self, mac: bytes, ip: str, port: int) -> tuple[int, int] | None:
        reply = await self.request_response(self.make_request(mac, GET_VERSION), (ip, port), STATE_VERSION)
        return (1, self.product) if reply is not None and reply.msg_type == STATE_VERSION else None

    async def query_host_firmware(self, mac: bytes, ip: str, port: int) -> tuple[int, int] | None:
        request = self.make_request(mac, GET_HOST_FIRMWARE)
        reply = await self.request_response(request, (ip, port), STATE_HOST_FIRMWARE)
        return self.firmware if reply is not None and reply.msg_type == STATE_HOST_FIRMWARE else None

    def register_device(self, *args: object, **kwargs: object) -> None:
        pass

    def start_probing(self, interval_s: float = 2.0) -> None:
        pass

    def types(self) -> list[int]:
        return [packet.msg_type for packet in self.sent]

    def last(self, msg_type: int) -> LifxPacket:
        return [packet for packet in self.sent if packet.msg_type == msg_type][-1]

    def _apply(self, packet: LifxPacket) -> None:
        payload = packet.payload
        if packet.msg_type == SET_COLOR:
            hue, sat, bri, kelvin = struct.unpack("<4H", payload[1:9])
            self.hsbk = (hue, sat, bri, kelvin)
        elif packet.msg_type == SET_LIGHT_POWER:
            (level,) = struct.unpack("<H", payload[:2])
            self.power = level != 0
        elif packet.msg_type == SET_TILE_EFFECT:
            (speed,) = struct.unpack("<I", payload[7:11])
            palette: list[HSBK] = []
            for index in range(payload[59]):
                hue, sat, bri, kelvin = struct.unpack("<4H", payload[60 + index * 8 : 68 + index * 8])
                palette.append((hue, sat, bri, kelvin))
            self.tile_effect = (payload[6], speed, tuple(palette))
        elif packet.msg_type == SET_MULTIZONE_EFFECT:
            (speed,) = struct.unpack("<I", payload[7:11])
            (direction,) = struct.unpack("<I", payload[31:35])
            self.multizone_effect = (payload[4], speed, direction == 0)
        elif packet.msg_type == SET_EXTENDED_COLOR_ZONES:
            _duration, _mode, index, count = struct.unpack("<IBHB", payload[:8])
            while len(self.zones) < index + count:
                self.zones.append((0, 0, 0, 3500))
            for offset in range(count):
                start = 8 + offset * 8
                hue, sat, bri, kelvin = struct.unpack("<4H", payload[start : start + 8])
                self.zones[index + offset] = (hue, sat, bri, kelvin)

    def _state_for(self, msg_type: int) -> LifxPacket | None:
        if msg_type in (GET_COLOR, SET_COLOR, SET_WAVEFORM):
            label = self.label.encode()[:32]
            power = 65535 if self.power else 0
            state = struct.pack("<4H2sH32s8s", *self.hsbk, b"", power, label, b"")
            return self._reply(LIGHT_STATE, state)
        if msg_type == SET_LIGHT_POWER:
            return self._reply(STATE_LIGHT_POWER, struct.pack("<H", 65535 if self.power else 0))
        if msg_type in (GET_TILE_EFFECT, SET_TILE_EFFECT):
            effect, speed, palette = self.tile_effect
            colours = b"".join(struct.pack("<4H", *c) for c in palette)
            state = (
                struct.pack("<BIBIQII", 0, 1, effect, speed, 0, 0, 0)
                + bytes(32)
                + bytes([len(palette)])
                + colours.ljust(128, b"\x00")
            )
            return self._reply(STATE_TILE_EFFECT, state)
        if msg_type in (GET_MULTIZONE_EFFECT, SET_MULTIZONE_EFFECT):
            effect, speed, reverse = self.multizone_effect
            state = (
                struct.pack("<IBHIQII", 1, effect, 0, speed, 0, 0, 0)
                + struct.pack("<II", 0, 0 if reverse else 1)
                + bytes(24)
            )
            return self._reply(STATE_MULTIZONE_EFFECT, state)
        if msg_type in (GET_EXTENDED_COLOR_ZONES, SET_EXTENDED_COLOR_ZONES):
            shown = self.zones[:82]
            colours = b"".join(struct.pack("<4H", *c) for c in shown)
            state = struct.pack("<HHB", len(self.zones), 0, len(shown)) + colours.ljust(656, b"\x00")
            return self._reply(STATE_EXTENDED_COLOR_ZONES, state)
        if msg_type == GET_DEVICE_CHAIN:
            entries = b"".join(
                struct.pack(
                    "<hhh2sffBBBII4sQ8sHH4s",
                    0, 0, 0, b"", float(index), 0.0, width, height, 0,
                    1, self.product, b"", 0, b"", 0, 0, b"",
                )
                for index, (width, height) in enumerate(self.chain)
            )
            state = b"\x00" + entries.ljust(16 * 55, b"\x00") + bytes([len(self.chain)])
            return self._reply(STATE_DEVICE_CHAIN, state)
        if msg_type == GET_HOST_FIRMWARE:
            major, minor = self.firmware
            return self._reply(STATE_HOST_FIRMWARE, struct.pack("<QQHH", 0, 0, minor, major))
        if msg_type == GET_VERSION:
            return self._reply(STATE_VERSION, struct.pack("<III", 1, self.product, 0))
        return None

    def _reply(self, msg_type: int, payload: bytes) -> LifxPacket:
        return LifxPacket(
            tagged=False,
            source=self.source_id,
            target=b"\x00" * 8,
            ack_required=False,
            res_required=False,
            sequence=0,
            msg_type=msg_type,
            payload=payload,
        )
```

- [ ] **Step 2: Write the failing tests**

`tests/devices/lifx/test_lifx_control.py`:

```python
from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from lifx_fakes import FakeLifxTransport

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected, LightReading
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    HSBK,
    SET_COLOR,
    SET_EXTENDED_COLOR_ZONES,
    SET_LIGHT_POWER,
    SET_MULTIZONE_EFFECT,
    SET_TILE_EFFECT,
    SET_TILE_STATE_64,
    MultiZoneEffectType,
    TileEffectType,
    hsbk_to_rgb,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.spatial.geometry import MatrixGeometry
from dj_ledfx.types import DeviceInfo

MAC = b"\xd0\x73\xd5\x00\x00\x01"
RED: HSBK = (0, 65535, 65535, 3500)
WHITE: HSBK = (0, 0, 65535, 3500)


def _info(kind: str, leds: int) -> DeviceInfo:
    return DeviceInfo(
        f"LIFX {kind}",
        f"lifx_{kind}",
        leds,
        "10.0.0.5:56700",
        mac=MAC.hex(),
        stable_id=f"lifx:{MAC.hex()}",
        backend="lifx",
    )


def _bulb(transport: FakeLifxTransport) -> LifxBulbAdapter:
    return LifxBulbAdapter(transport, _info("bulb", 1), MAC)  # type: ignore[arg-type]


def _strip(transport: FakeLifxTransport, zones: int = 8) -> LifxStripAdapter:
    return LifxStripAdapter(transport, _info("strip", zones), MAC, zone_count=zones)  # type: ignore[arg-type]


def _candle(transport: FakeLifxTransport, caps: DeviceCapabilities | None = None) -> LifxTileChainAdapter:
    tile = TileInfo(user_x=0.0, user_y=0.0, width=5, height=6, accel_x=0, accel_y=0, accel_z=0)
    return LifxTileChainAdapter(
        transport, _info("tile", 30), MAC, tiles=[tile], caps=caps  # type: ignore[arg-type]
    )


def test_hsbk_to_rgb() -> None:
    assert hsbk_to_rgb(RED) == (255, 0, 0)
    assert hsbk_to_rgb(WHITE) == (255, 255, 255)
    assert hsbk_to_rgb((21845, 65535, 32768, 3500)) == (0, 128, 0)


async def test_read_light_reports_power_and_colour() -> None:
    transport = FakeLifxTransport(power=False, hsbk=RED)
    assert await _bulb(transport).read_light() == LightReading(power=False, colour=(255, 0, 0))
    assert transport.types() == [GET_COLOR]


async def test_read_light_is_unknown_when_the_light_is_silent() -> None:
    transport = FakeLifxTransport(silent=True)
    assert await _bulb(transport).read_light() == LightReading(power=None, colour=None)


async def test_set_power_sends_set_light_power() -> None:
    transport = FakeLifxTransport(power=False)
    await _bulb(transport).set_power(True)
    assert transport.power is True
    assert struct.unpack("<HI", transport.last(SET_LIGHT_POWER).payload) == (65535, 0)


async def test_bulb_capture_and_restore_round_trip() -> None:
    transport = FakeLifxTransport(power=False, hsbk=RED)
    bulb = _bulb(transport)
    captured = await bulb.capture_state()
    assert captured is not None
    assert json.loads(captured) == {"v": 1, "power": False, "hsbk": list(RED)}

    transport.power, transport.hsbk = True, WHITE  # the look ran
    transport.sent.clear()
    await bulb.restore_state(captured)

    assert transport.types() == [SET_COLOR, SET_LIGHT_POWER]
    assert transport.hsbk == RED
    assert transport.power is False


async def test_capture_is_none_when_the_light_is_silent() -> None:
    assert await _bulb(FakeLifxTransport(silent=True)).capture_state() is None


async def test_unreadable_capture_leaves_the_light_alone() -> None:
    transport = FakeLifxTransport()
    await _bulb(transport).restore_state(b"\x80\x80\x80")
    assert transport.sent == []


async def test_strip_captures_zones_and_its_move_effect() -> None:
    zones: list[HSBK] = [(i * 1000, 65535, 65535, 3500) for i in range(8)]
    transport = FakeLifxTransport(zones=zones)
    transport.multizone_effect = (int(MultiZoneEffectType.MOVE), 4000, True)
    strip = _strip(transport)

    captured = await strip.capture_state()
    assert captured is not None
    snapshot = json.loads(captured)
    assert snapshot["zones"] == [list(z) for z in zones]
    assert snapshot["multizone_effect"] == {"effect": 1, "speed_ms": 4000, "reverse": True}

    await strip.prepare_stream()
    assert transport.multizone_effect[0] == MultiZoneEffectType.OFF

    transport.zones = [(0, 0, 0, 3500)] * 8
    transport.sent.clear()
    await strip.restore_state(captured)

    assert transport.types() == [SET_EXTENDED_COLOR_ZONES, SET_MULTIZONE_EFFECT, SET_LIGHT_POWER]
    assert transport.zones == zones
    assert transport.multizone_effect == (1, 4000, True)


async def test_candle_size_geometry_and_frames_follow_its_device_chain() -> None:
    transport = FakeLifxTransport()
    candle = _candle(transport)
    assert candle.led_count == 30
    geometry = candle.geometry
    assert isinstance(geometry, MatrixGeometry)
    assert [(t.width, t.height) for t in geometry.tiles] == [(5, 6)]

    await candle.send_frame(np.zeros((30, 3), dtype=np.uint8))
    (frame,) = transport.sent
    assert frame.msg_type == SET_TILE_STATE_64
    tile_index, length, _reserved, x, y, width = struct.unpack("<6B", frame.payload[:6])
    assert (tile_index, length, x, y, width) == (0, 1, 0, 0, 5)


async def test_tiles_wider_than_64_pixels_are_sent_in_row_bands() -> None:
    transport = FakeLifxTransport()
    wide = TileInfo(user_x=0.0, user_y=0.0, width=16, height=8, accel_x=0, accel_y=0, accel_z=0)
    adapter = LifxTileChainAdapter(transport, _info("tile", 128), MAC, tiles=[wide])  # type: ignore[arg-type]
    await adapter.send_frame(np.zeros((128, 3), dtype=np.uint8))
    rows = [struct.unpack("<6B", p.payload[:6])[4] for p in transport.sent]
    assert rows == [0, 4]


async def test_candle_captures_and_restores_its_flame() -> None:
    transport = FakeLifxTransport()
    candle = _candle(transport)
    await candle.start_tile_effect(TileEffectType.FLAME, 5000)
    captured = await candle.capture_state()
    assert captured is not None
    assert json.loads(captured)["tile_effect"] == {"effect": 3, "speed_ms": 5000, "palette": []}

    await candle.prepare_stream()
    assert transport.tile_effect[0] == TileEffectType.OFF

    transport.sent.clear()
    await candle.restore_state(captured)
    assert transport.types() == [SET_COLOR, SET_TILE_EFFECT, SET_LIGHT_POWER]
    assert transport.tile_effect[:2] == (3, 5000)


async def test_firmware_command_rejected_by_the_light() -> None:
    transport = FakeLifxTransport(unhandled={SET_TILE_EFFECT})
    with pytest.raises(FirmwareRejected):
        await _candle(transport).start_tile_effect(TileEffectType.FLAME, 5000)


async def test_firmware_command_without_an_answer_is_rejected_after_a_retry() -> None:
    transport = FakeLifxTransport(silent=True)
    with pytest.raises(FirmwareRejected):
        await _candle(transport).start_tile_effect(TileEffectType.FLAME, 5000)
    assert transport.types() == [SET_TILE_EFFECT, SET_TILE_EFFECT]


async def test_prepare_stream_tolerates_lights_without_effects() -> None:
    transport = FakeLifxTransport(unhandled={SET_TILE_EFFECT})
    await _candle(transport).prepare_stream()
    assert transport.types() == [SET_TILE_EFFECT]


def test_adapters_report_their_capabilities() -> None:
    transport = FakeLifxTransport()
    caps = DeviceCapabilities(protocol="LIFX", model="LIFX Tube", matrix=True)
    assert _candle(transport, caps).capabilities is caps
    assert _strip(transport).capabilities.extended_multizone
    assert _bulb(transport).capabilities == DeviceCapabilities(protocol="LIFX")
```

In `tests/devices/lifx/test_packet.py`, replace `test_parse_state_extended_color_zones`:

```python
    def test_parse_state_extended_color_zones(self) -> None:
        header = struct.pack("<HHB", 10, 0, 10)
        hsbk_data = struct.pack("<4H", 100, 200, 300, 3500) * 10
        payload = header + hsbk_data.ljust(82 * 8, b"\x00")
        zone_count, zone_index, colors = parse_state_extended_color_zones(payload)
        assert zone_count == 10
        assert zone_index == 0
        assert len(colors) == 10
        assert colors[0] == (100, 200, 300, 3500)

    def test_parse_state_extended_color_zones_rejects_short_payloads(self) -> None:
        with pytest.raises(ValueError):
            parse_state_extended_color_zones(b"\x01\x00")
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/devices/lifx/test_lifx_control.py tests/devices/lifx/test_packet.py -v`
Expected: FAIL (`ImportError: cannot import name 'SET_TILE_STATE_64'`).

- [ ] **Step 4: Extend `src/dj_ledfx/devices/lifx/packet.py`**

Add `import colorsys` to the imports and these constants beside Task 4's:

```python
STATE_LIGHT_POWER = 118
GET_EXTENDED_COLOR_ZONES = 511
STATE_EXTENDED_COLOR_ZONES = 512
SET_TILE_STATE_64 = 715
```

Replace `parse_state_extended_color_zones`:

```python
def parse_state_extended_color_zones(payload: bytes) -> tuple[int, int, list[HSBK]]:
    """StateExtendedColorZones(512): zones_count, zone_index, colors_count, then 82 colours."""
    if len(payload) < 5:
        raise ValueError(f"StateExtendedColorZones payload too short: {len(payload)} < 5")
    zone_count, zone_index, colors_count = struct.unpack("<HHB", payload[:5])
    colors: list[HSBK] = []
    for index in range(min(colors_count, 82)):
        start = 5 + index * 8
        if start + 8 > len(payload):
            break
        hue, sat, bri, kelvin = struct.unpack("<4H", payload[start : start + 8])
        colors.append((hue, sat, bri, kelvin))
    return int(zone_count), int(zone_index), colors
```

Add after `rgb_to_hsbk`:

```python
def hsbk_to_rgb(hsbk: HSBK) -> tuple[int, int, int]:
    """LIFX HSBK to 8-bit RGB. Kelvin is ignored, so a white shows as plain white."""
    hue, sat, bri, _kelvin = hsbk
    red, green, blue = colorsys.hsv_to_rgb(hue / 65535, sat / 65535, bri / 65535)
    return round(red * 255), round(green * 255), round(blue * 255)
```

- [ ] **Step 5: Write `src/dj_ledfx/devices/lifx/base.py`**

```python
"""What every LIFX adapter shares: packets, confirmed commands, power, colour reads,
capture and restore (spec §6.3, §7.1, §8)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected, LightReading
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    HSBK,
    LIGHT_STATE,
    SET_COLOR,
    SET_LIGHT_POWER,
    SET_WAVEFORM,
    STATE_LIGHT_POWER,
    STATE_UNHANDLED,
    LifxPacket,
    Waveform,
    build_set_color,
    build_set_light_power,
    build_set_waveform,
    hsbk_to_rgb,
    parse_light_state,
)
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

CAPTURE_VERSION = 1
RESTORE_FADE_MS = 500


def hsbk_from_json(values: object) -> HSBK:
    """An HSBK saved as a JSON list. Raises ValueError when it isn't one."""
    if not isinstance(values, list) or len(values) != 4:
        raise ValueError(f"not an HSBK: {values!r}")
    hue, sat, bri, kelvin = (int(v) for v in values)
    return hue, sat, bri, kelvin


class LifxAdapterBase(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        *,
        kelvin: int,
        caps: DeviceCapabilities,
    ) -> None:
        self._transport = transport
        self._device_info = device_info
        self._target_mac = target_mac
        self._kelvin = kelvin
        self._caps = caps
        self._is_connected = False
        host, port = device_info.address.rsplit(":", 1)
        self._addr = (host, int(port))

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._caps

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    # --- packets ---

    def _send(self, msg_type: int, payload: bytes = b"") -> None:
        """Fire and forget: streamed frames."""
        packet = LifxPacket(
            tagged=False,
            source=self._transport.source_id,
            target=self._target_mac + b"\x00\x00",
            ack_required=False,
            res_required=False,
            sequence=self._transport.next_sequence() % 256,
            msg_type=msg_type,
            payload=payload,
        )
        self._transport.send_packet(packet, self._addr)

    async def _ask(
        self, msg_type: int, payload: bytes, reply_type: int, *, timeout: float = 0.5
    ) -> LifxPacket | None:
        """Send a request and wait for its reply, retrying once. The reply may be 223."""
        request = self._transport.make_request(self._target_mac, msg_type, payload)
        for _attempt in range(2):
            reply = await self._transport.request_response(request, self._addr, reply_type, timeout)
            if reply is not None:
                return reply
        return None

    async def _command(self, msg_type: int, payload: bytes, reply_type: int) -> LifxPacket:
        """A command the light must confirm. Raises FirmwareRejected when it doesn't."""
        reply = await self._ask(msg_type, payload, reply_type)
        if reply is None:
            raise FirmwareRejected(f"{self._device_info.name} didn't answer message {msg_type}")
        if reply.msg_type == STATE_UNHANDLED:
            raise FirmwareRejected(f"{self._device_info.name} doesn't support message {msg_type}")
        return reply

    # --- reading ---

    async def _light_state(self) -> tuple[HSBK, bool, str] | None:
        reply = await self._ask(GET_COLOR, b"", LIGHT_STATE)
        if reply is None or reply.msg_type != LIGHT_STATE:
            return None
        try:
            hue, sat, bri, kelvin, power, label = parse_light_state(reply.payload)
        except ValueError:
            return None
        return (hue, sat, bri, kelvin), power != 0, label

    async def read_light(self) -> LightReading:
        state = await self._light_state()
        if state is None:
            return LightReading(power=None, colour=None)
        hsbk, power, _label = state
        return LightReading(power=power, colour=hsbk_to_rgb(hsbk))

    # --- control ---

    async def set_power(self, on: bool) -> None:
        await self._set_power(on, 0)

    async def _set_power(self, on: bool, duration_ms: int) -> None:
        reply = await self._ask(
            SET_LIGHT_POWER, build_set_light_power(on, duration_ms), STATE_LIGHT_POWER
        )
        if reply is None or reply.msg_type != STATE_LIGHT_POWER:
            logger.warning(
                "LIFX '{}' didn't confirm power {}", self._device_info.name, "on" if on else "off"
            )

    async def set_colour(self, hsbk: HSBK, duration_ms: int = 0) -> None:
        await self._command(SET_COLOR, build_set_color(hsbk, duration_ms), LIGHT_STATE)

    async def set_waveform(
        self,
        hsbk: HSBK,
        period_ms: int,
        cycles: float,
        waveform: Waveform,
        *,
        transient: bool = True,
        skew_ratio: float = 0.5,
    ) -> None:
        payload = build_set_waveform(
            hsbk, period_ms, cycles, waveform, transient=transient, skew_ratio=skew_ratio
        )
        await self._command(SET_WAVEFORM, payload, LIGHT_STATE)

    # --- capture and restore ---

    async def capture_state(self) -> bytes | None:
        state = await self._light_state()
        if state is None:
            logger.warning("LIFX '{}' didn't answer; its state isn't captured", self._device_info.name)
            return None
        hsbk, power, _label = state
        snapshot: dict[str, Any] = {"v": CAPTURE_VERSION, "power": power, "hsbk": list(hsbk)}
        snapshot.update(await self._capture_extra())
        return json.dumps(snapshot).encode()

    async def restore_state(self, state: bytes) -> None:
        try:
            snapshot = json.loads(state)
            hsbk = hsbk_from_json(snapshot["hsbk"])
            power = bool(snapshot["power"])
        except (ValueError, KeyError, TypeError):
            logger.warning(
                "LIFX '{}': captured state is unreadable, leaving the light alone",
                self._device_info.name,
            )
            return
        await self._restore_colours(snapshot, hsbk)
        await self._restore_effect(snapshot)
        await self._set_power(power, RESTORE_FADE_MS)

    async def _capture_extra(self) -> dict[str, Any]:
        """Anything beyond power and colour. Strips add zones, matrices their effect."""
        return {}

    async def _restore_colours(self, snapshot: dict[str, Any], hsbk: HSBK) -> None:
        await self._ask(SET_COLOR, build_set_color(hsbk, RESTORE_FADE_MS), LIGHT_STATE)

    async def _restore_effect(self, snapshot: dict[str, Any]) -> None:
        """Restart the firmware effect that ran before. Bulbs have none."""
```

- [ ] **Step 6: Rewrite `src/dj_ledfx/devices/lifx/bulb.py`**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.lifx.base import LifxAdapterBase
from dj_ledfx.devices.lifx.packet import SET_COLOR, build_set_color, rgb_to_hsbk
from dj_ledfx.spatial.geometry import DeviceGeometry, PointGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport


class LifxBulbAdapter(LifxAdapterBase):
    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        kelvin: int = 3500,
        *,
        caps: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(
            transport,
            device_info,
            target_mac,
            kelvin=kelvin,
            caps=caps or DeviceCapabilities(protocol="LIFX"),
        )

    @property
    def led_count(self) -> int:
        return 1

    @property
    def geometry(self) -> DeviceGeometry:
        return PointGeometry()

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        self._send(SET_COLOR, build_set_color(rgb_to_hsbk(r, g, b, kelvin=self._kelvin)))
```

- [ ] **Step 7: Rewrite `src/dj_ledfx/devices/lifx/strip.py`**

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.lifx.base import RESTORE_FADE_MS, LifxAdapterBase, hsbk_from_json
from dj_ledfx.devices.lifx.packet import (
    GET_EXTENDED_COLOR_ZONES,
    GET_MULTIZONE_EFFECT,
    HSBK,
    SET_EXTENDED_COLOR_ZONES,
    SET_MULTIZONE_EFFECT,
    STATE_EXTENDED_COLOR_ZONES,
    STATE_MULTIZONE_EFFECT,
    MultiZoneEffectState,
    MultiZoneEffectType,
    build_set_extended_color_zones,
    build_set_multizone_effect,
    parse_state_extended_color_zones,
    parse_state_multizone_effect,
    rgb_array_to_hsbk,
)
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

MAX_ZONES_PER_PACKET = 82


class LifxStripAdapter(LifxAdapterBase):
    """Extended-multizone lights: Z, Beam, Neon, String."""

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        zone_count: int = 1,
        kelvin: int = 3500,
        *,
        caps: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(
            transport,
            device_info,
            target_mac,
            kelvin=kelvin,
            caps=caps
            or DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True),
        )
        self._zone_count = zone_count

    @property
    def led_count(self) -> int:
        return self._zone_count

    @property
    def geometry(self) -> DeviceGeometry:
        return StripGeometry(direction=(1, 0, 0), length=1.0)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        for start in range(0, len(hsbk), MAX_ZONES_PER_PACKET):
            chunk = hsbk[start : start + MAX_ZONES_PER_PACKET]
            values: list[HSBK] = [(int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in chunk]
            self._send(
                SET_EXTENDED_COLOR_ZONES,
                build_set_extended_color_zones(0, 1, start, len(values), values),
            )

    async def set_zone_colours(self, colours: Sequence[HSBK], duration_ms: int = 0) -> None:
        for start in range(0, len(colours), MAX_ZONES_PER_PACKET):
            chunk = list(colours[start : start + MAX_ZONES_PER_PACKET])
            await self._command(
                SET_EXTENDED_COLOR_ZONES,
                build_set_extended_color_zones(duration_ms, 1, start, len(chunk), chunk),
                STATE_EXTENDED_COLOR_ZONES,
            )

    async def start_multizone_effect(
        self, effect: MultiZoneEffectType, speed_ms: int, *, reverse: bool = False
    ) -> None:
        await self._command(
            SET_MULTIZONE_EFFECT,
            build_set_multizone_effect(effect, speed_ms, reverse=reverse),
            STATE_MULTIZONE_EFFECT,
        )

    async def multizone_effect(self) -> MultiZoneEffectState | None:
        reply = await self._ask(GET_MULTIZONE_EFFECT, b"", STATE_MULTIZONE_EFFECT)
        if reply is None or reply.msg_type != STATE_MULTIZONE_EFFECT:
            return None
        try:
            return parse_state_multizone_effect(reply.payload)
        except ValueError:
            return None

    async def prepare_stream(self) -> None:
        try:
            await self.start_multizone_effect(MultiZoneEffectType.OFF, 0)
        except FirmwareRejected:
            logger.debug("LIFX '{}' has no multizone effects to stop", self._device_info.name)

    async def _zone_colours(self) -> list[HSBK] | None:
        reply = await self._ask(GET_EXTENDED_COLOR_ZONES, b"", STATE_EXTENDED_COLOR_ZONES)
        if reply is None or reply.msg_type != STATE_EXTENDED_COLOR_ZONES:
            return None
        try:
            _count, _index, colours = parse_state_extended_color_zones(reply.payload)
        except ValueError:
            return None
        return colours

    async def _capture_extra(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        zones = await self._zone_colours()
        if zones:
            extra["zones"] = [list(zone) for zone in zones]
        effect = await self.multizone_effect()
        if effect is not None and effect.effect != MultiZoneEffectType.OFF:
            extra["multizone_effect"] = {
                "effect": effect.effect,
                "speed_ms": effect.speed_ms,
                "reverse": effect.reverse,
            }
        return extra

    async def _restore_colours(self, snapshot: dict[str, Any], hsbk: HSBK) -> None:
        zones = snapshot.get("zones")
        if isinstance(zones, list) and zones:
            try:
                await self.set_zone_colours([hsbk_from_json(z) for z in zones], RESTORE_FADE_MS)
                return
            except (FirmwareRejected, ValueError):
                logger.warning("LIFX '{}': couldn't restore its zones", self._device_info.name)
        await super()._restore_colours(snapshot, hsbk)

    async def _restore_effect(self, snapshot: dict[str, Any]) -> None:
        effect = snapshot.get("multizone_effect")
        if not isinstance(effect, dict):
            return
        try:
            await self.start_multizone_effect(
                MultiZoneEffectType(int(effect["effect"])),
                int(effect["speed_ms"]),
                reverse=bool(effect["reverse"]),
            )
        except (FirmwareRejected, ValueError, KeyError, TypeError):
            logger.warning("LIFX '{}': couldn't restart its effect", self._device_info.name)
```

- [ ] **Step 8: Rewrite `src/dj_ledfx/devices/lifx/tile_chain.py`**

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.lifx.base import LifxAdapterBase, hsbk_from_json
from dj_ledfx.devices.lifx.packet import (
    GET_TILE_EFFECT,
    HSBK,
    SET_TILE_EFFECT,
    SET_TILE_STATE_64,
    STATE_TILE_EFFECT,
    TileEffectState,
    TileEffectType,
    build_get_tile_effect,
    build_set_tile_effect,
    build_set_tile_state64,
    parse_state_tile_effect,
    rgb_array_to_hsbk,
)
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.spatial.geometry import MatrixGeometry, TileLayout
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport

PIXELS_PER_PACKET = 64
DEFAULT_TILE_SIZE = (8, 8)
PIXEL_PITCH_M = 0.03


class LifxTileChainAdapter(LifxAdapterBase):
    """Matrix lights: Tile, Candle, Tube, Spot, Path, Ceiling. Sized from StateDeviceChain."""

    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        tile_count: int = 5,
        kelvin: int = 3500,
        *,
        tiles: Sequence[TileInfo] = (),
        caps: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(
            transport,
            device_info,
            target_mac,
            kelvin=kelvin,
            caps=caps or DeviceCapabilities(protocol="LIFX", matrix=True),
        )
        self._tiles: list[TileInfo] = list(tiles)
        self._tile_count = len(self._tiles) or tile_count

    @property
    def tiles(self) -> list[TileInfo]:
        return self._tiles

    def _tile_sizes(self) -> list[tuple[int, int]]:
        if self._tiles:
            return [(tile.width, tile.height) for tile in self._tiles]
        return [DEFAULT_TILE_SIZE] * self._tile_count

    @property
    def led_count(self) -> int:
        return sum(width * height for width, height in self._tile_sizes())

    @property
    def geometry(self) -> MatrixGeometry:
        layouts: list[TileLayout] = []
        for index, (width, height) in enumerate(self._tile_sizes()):
            if index < len(self._tiles):
                tile = self._tiles[index]
                offset = (tile.user_x * width * PIXEL_PITCH_M, tile.user_y * height * PIXEL_PITCH_M)
            else:
                offset = (index * (width + 1) * PIXEL_PITCH_M, 0.0)
            layouts.append(TileLayout(offset[0], offset[1], width, height))
        return MatrixGeometry(tiles=tuple(layouts), pixel_pitch=PIXEL_PITCH_M)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        hsbk = rgb_array_to_hsbk(colors, kelvin=self._kelvin)
        start = 0
        for tile_index, (width, height) in enumerate(self._tile_sizes()):
            rows_per_packet = max(1, PIXELS_PER_PACKET // width)
            for row in range(0, height, rows_per_packet):
                rows = min(rows_per_packet, height - row)
                chunk = hsbk[start + row * width : start + (row + rows) * width]
                values: list[HSBK] = [(int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in chunk]
                self._send(
                    SET_TILE_STATE_64,
                    build_set_tile_state64(tile_index, 1, 0, row, width, 0, values),
                )
            start += width * height

    async def start_tile_effect(
        self, effect: TileEffectType, speed_ms: int, palette: Sequence[HSBK] = ()
    ) -> None:
        await self._command(
            SET_TILE_EFFECT, build_set_tile_effect(effect, speed_ms, palette), STATE_TILE_EFFECT
        )

    async def tile_effect(self) -> TileEffectState | None:
        reply = await self._ask(GET_TILE_EFFECT, build_get_tile_effect(), STATE_TILE_EFFECT)
        if reply is None or reply.msg_type != STATE_TILE_EFFECT:
            return None
        try:
            return parse_state_tile_effect(reply.payload)
        except ValueError:
            return None

    async def prepare_stream(self) -> None:
        try:
            await self.start_tile_effect(TileEffectType.OFF, 0)
        except FirmwareRejected:
            logger.debug("LIFX '{}' has no tile effects to stop", self._device_info.name)

    async def _capture_extra(self) -> dict[str, Any]:
        effect = await self.tile_effect()
        if effect is None or effect.effect == TileEffectType.OFF:
            return {}
        return {
            "tile_effect": {
                "effect": effect.effect,
                "speed_ms": effect.speed_ms,
                "palette": [list(colour) for colour in effect.palette],
            }
        }

    async def _restore_effect(self, snapshot: dict[str, Any]) -> None:
        effect = snapshot.get("tile_effect")
        if not isinstance(effect, dict):
            return
        try:
            await self.start_tile_effect(
                TileEffectType(int(effect["effect"])),
                int(effect["speed_ms"]),
                [hsbk_from_json(colour) for colour in effect["palette"]],
            )
        except (FirmwareRejected, ValueError, KeyError, TypeError):
            logger.warning("LIFX '{}': couldn't restart its effect", self._device_info.name)
```

- [ ] **Step 9: Run the tests to see them pass**

Run: `uv run pytest tests/devices/lifx -v`
Expected: PASS, including the existing bulb, strip and tile tests (their constructors are unchanged).

- [ ] **Step 10: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/lifx tests/lifx_fakes.py tests/devices/lifx/test_lifx_control.py tests/devices/lifx/test_packet.py
git commit -m "feat(lifx): shared adapter base with power, colour reads, firmware commands and full capture"
```

---

### Task 8: LIFX discovery by product

Discovery classifies each light by its product and firmware (Task 6) instead of the hard-coded sets, sizes matrices from `StateDeviceChain` and strips from their zone count, and names each light after its LIFX label, the name the owner gave it in the LIFX app (the names in spec §6.6: "Candle 1", "TV Lamp"). Switches are skipped. `connect_known` asks each known light the same questions instead of trusting the database row, so a Candle saved as 64 LEDs comes back as its real 30; a light that doesn't answer stays a ghost until discovery finds it.

**Files:**
- Modify (rewrite): `src/dj_ledfx/devices/lifx/discovery.py`
- Test: `tests/devices/lifx/test_discovery.py` (rewrite)

**Interfaces:**
- Consumes: `lifx_product`, `lifx_capabilities` (Task 6); the adapters (Task 7); `LifxTransport.query_version`, `query_host_firmware`, `make_request`, `request_response` (Task 5); `FakeLifxTransport` (Task 7).
- Produces:
  - `LifxBackend._create_adapter(record: LifxDeviceRecord, config: AppConfig) -> LifxAdapterBase | None` (None for switches)
  - `LifxBackend.connect_known(device_rows, config)` re-queries every row and skips lights that don't answer
  - Device names: the LIFX label; `"{model} ({ip})"` when the label is empty; `"{label} ({last 4 hex of the MAC})"` when another LIFX light already has that label

- [ ] **Step 1: Write the failing tests**

Replace `tests/devices/lifx/test_discovery.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from lifx_fakes import FakeLifxTransport

from dj_ledfx.config import AppConfig, DevicesConfig, LIFXConfig
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.discovery import LifxBackend
from dj_ledfx.devices.lifx.packet import GET_DEVICE_CHAIN
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import LifxDeviceRecord

MAC = b"\xd0\x73\xd5\x00\x00\x01"


def _record(product: int, mac: bytes = MAC) -> LifxDeviceRecord:
    return LifxDeviceRecord(mac=mac, ip="10.0.0.5", port=56700, vendor=1, product=product)


def _backend(transport: FakeLifxTransport) -> LifxBackend:
    backend = LifxBackend()
    backend._transport = transport  # type: ignore[assignment]
    return backend


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"lifx:{MAC.hex()}",
        "name": "LIFX Tile (10.0.0.5)",
        "backend": "lifx",
        "device_type": "lifx_tile",
        "led_count": 64,
        "ip": "10.0.0.5",
        "mac": MAC.hex(),
    }
    row.update(overrides)
    return row


def test_is_enabled_checks_config() -> None:
    backend = LifxBackend()
    assert backend.is_enabled(AppConfig(devices=DevicesConfig(lifx=LIFXConfig(enabled=True))))
    assert not backend.is_enabled(AppConfig(devices=DevicesConfig(lifx=LIFXConfig(enabled=False))))


async def test_candle_is_a_matrix_sized_from_its_device_chain() -> None:
    transport = FakeLifxTransport(product=57, label="Candle 1", chain=[(5, 6)], firmware=(3, 90))
    adapter = await _backend(transport)._create_adapter(_record(57), AppConfig())
    assert isinstance(adapter, LifxTileChainAdapter)
    assert adapter.led_count == 30
    assert adapter.device_info.led_count == 30
    assert adapter.device_info.name == "Candle 1"
    assert adapter.device_info.device_type == "lifx_tile"
    assert adapter.capabilities.model == "LIFX Candle C"
    assert adapter.capabilities.firmware_version == "3.90"


async def test_tile_without_a_chain_reply_falls_back_to_five_8x8_tiles() -> None:
    transport = FakeLifxTransport(product=55, unhandled={GET_DEVICE_CHAIN})
    adapter = await _backend(transport)._create_adapter(_record(55), AppConfig())
    assert isinstance(adapter, LifxTileChainAdapter)
    assert adapter.led_count == 5 * 64


async def test_neon_is_a_strip_sized_from_its_zones() -> None:
    zones = [(0, 0, 65535, 3500)] * 36
    transport = FakeLifxTransport(product=141, label="Neon Indoor", zones=zones, firmware=(4, 10))
    adapter = await _backend(transport)._create_adapter(_record(141), AppConfig())
    assert isinstance(adapter, LifxStripAdapter)
    assert adapter.led_count == 36
    assert adapter.device_info.led_count == 36


@pytest.mark.parametrize(("firmware", "kind"), [((2, 76), LifxBulbAdapter), ((2, 77), LifxStripAdapter)])
async def test_lifx_z_is_a_strip_from_firmware_2_77(firmware: tuple[int, int], kind: type) -> None:
    transport = FakeLifxTransport(product=32, zones=[(0, 0, 65535, 3500)] * 16, firmware=firmware)
    adapter = await _backend(transport)._create_adapter(_record(32), AppConfig())
    assert type(adapter) is kind


@pytest.mark.parametrize("product", [1, 90, 9999])
async def test_bulbs_and_unknown_products_are_bulbs(product: int) -> None:
    transport = FakeLifxTransport(product=product)
    adapter = await _backend(transport)._create_adapter(_record(product), AppConfig())
    assert type(adapter) is LifxBulbAdapter


async def test_switches_are_skipped() -> None:
    transport = FakeLifxTransport(product=70)
    assert await _backend(transport)._create_adapter(_record(70), AppConfig()) is None


async def test_unlabelled_light_is_named_after_its_model() -> None:
    transport = FakeLifxTransport(product=27, label="")
    adapter = await _backend(transport)._create_adapter(_record(27), AppConfig())
    assert adapter is not None
    assert adapter.device_info.name == "LIFX (A19) (10.0.0.5)"


async def test_duplicate_labels_get_a_suffix() -> None:
    backend = _backend(FakeLifxTransport(product=1, label="Lamp"))
    first = await backend._create_adapter(_record(1, b"\xd0\x73\xd5\x00\x00\x01"), AppConfig())
    second = await backend._create_adapter(_record(1, b"\xd0\x73\xd5\x00\x00\x02"), AppConfig())
    again = await backend._create_adapter(_record(1, b"\xd0\x73\xd5\x00\x00\x01"), AppConfig())
    assert first is not None and first.device_info.name == "Lamp"
    assert second is not None and second.device_info.name == "Lamp (0002)"
    assert again is not None and again.device_info.name == "Lamp"


async def test_discover_returns_discovered_devices() -> None:
    transport = FakeLifxTransport(product=1, label="Right Lamp")
    record = _record(1)

    async def _fake_discover(
        timeout_s: float = 1.0, on_record: Callable[[LifxDeviceRecord], None] | None = None
    ) -> list[LifxDeviceRecord]:
        if on_record is not None:
            on_record(record)
        return [record]

    transport.discover = _fake_discover  # type: ignore[attr-defined]
    config = AppConfig()
    devices = await _backend(transport).discover(config)

    (device,) = devices
    assert isinstance(device.adapter, LifxBulbAdapter)
    assert device.adapter.device_info.name == "Right Lamp"
    assert device.adapter.is_connected
    assert device.max_fps == config.devices.lifx.max_fps


async def test_connect_known_asks_the_light_instead_of_trusting_the_row() -> None:
    transport = FakeLifxTransport(product=57, label="Candle 2", chain=[(5, 6)])
    (device,) = await _backend(transport).connect_known([_row()], AppConfig())
    assert isinstance(device.adapter, LifxTileChainAdapter)
    assert device.adapter.led_count == 30
    assert device.adapter.device_info.name == "Candle 2"
    assert device.adapter.device_info.stable_id == f"lifx:{MAC.hex()}"


async def test_connect_known_leaves_silent_lights_offline() -> None:
    transport = FakeLifxTransport(silent=True)
    assert await _backend(transport).connect_known([_row()], AppConfig()) == []


async def test_connect_known_skips_rows_without_an_address() -> None:
    transport = FakeLifxTransport()
    assert await _backend(transport).connect_known([_row(ip=None)], AppConfig()) == []
    assert transport.sent == []
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/devices/lifx/test_discovery.py -v`
Expected: FAIL (the Candle is classified by the old sets as 64 LEDs and named `LIFX Tile (10.0.0.5)`; switches aren't skipped; names don't use labels).

- [ ] **Step 3: Rewrite `src/dj_ledfx/devices/lifx/discovery.py`**

```python
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.lifx.base import LifxAdapterBase
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    GET_DEVICE_CHAIN,
    GET_EXTENDED_COLOR_ZONES,
    LIGHT_STATE,
    STATE_DEVICE_CHAIN,
    STATE_EXTENDED_COLOR_ZONES,
    parse_light_state,
    parse_state_device_chain,
    parse_state_extended_color_zones,
)
from dj_ledfx.devices.lifx.products import lifx_capabilities, lifx_product
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import DEFAULT_TILE_SIZE, LifxTileChainAdapter
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord, TileInfo
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo

LIFX_PORT = 56700


class LifxBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: LifxTransport | None = None
        self._names: dict[str, str] = {}  # name -> stable_id, so two lights never share one

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.lifx.enabled

    async def _open_transport(self) -> LifxTransport:
        if self._transport is None or not self._transport.is_open:
            self._transport = LifxTransport()
            await self._transport.open()
        return self._transport

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
    ) -> list[DiscoveredDevice]:
        lifx = config.devices.lifx
        transport = await self._open_transport()
        results: list[DiscoveredDevice] = []
        setup_tasks: list[asyncio.Task[None]] = []

        async def _setup_device(record: LifxDeviceRecord) -> None:
            if skip_ids and f"lifx:{record.mac.hex()}" in skip_ids:
                return
            try:
                device = await self._setup(record, config)
            except Exception:
                logger.exception(
                    "Failed to set up LIFX device {} (product={})", record.ip, record.product
                )
                return
            if device is None:
                return
            results.append(device)
            if on_found is not None:
                on_found(device)

        def _on_record(record: LifxDeviceRecord) -> None:
            setup_tasks.append(asyncio.create_task(_setup_device(record)))

        await transport.discover(timeout_s=lifx.discovery_timeout_s, on_record=_on_record)
        if setup_tasks:
            await asyncio.gather(*setup_tasks, return_exceptions=True)

        logger.info("LIFX discovery found {} devices", len(results))
        if results:
            transport.start_probing(interval_s=lifx.echo_probe_interval_s)
        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Reconnect known LIFX lights by asking each one what it is.

        A light that doesn't answer stays a ghost until discovery finds it.
        """
        rows = [row for row in device_rows if row.get("backend") == "lifx"]
        if not rows:
            return []
        transport = await self._open_transport()

        async def _reconnect(row: dict[str, Any]) -> DiscoveredDevice | None:
            ip = row.get("ip") or ""
            mac_hex = (row.get("mac") or "").replace(":", "")
            if not ip or not mac_hex:
                logger.warning("Skipping known LIFX device '{}': missing ip or mac", row.get("name"))
                return None
            mac = bytes.fromhex(mac_hex)
            version = await transport.query_version(mac, ip, LIFX_PORT)
            if version is None:
                logger.info("Known LIFX device '{}' didn't answer; it stays offline", row.get("name"))
                return None
            vendor, product = version
            record = LifxDeviceRecord(mac=mac, ip=ip, port=LIFX_PORT, vendor=vendor, product=product)
            return await self._setup(record, config)

        outcomes = await asyncio.gather(*(_reconnect(row) for row in rows), return_exceptions=True)
        results: list[DiscoveredDevice] = []
        for row, outcome in zip(rows, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.opt(exception=outcome).error(
                    "Failed to reconnect known LIFX device '{}'", row.get("name", "?")
                )
            elif outcome is not None:
                logger.info("Reconnected known LIFX device '{}'", outcome.adapter.device_info.name)
                results.append(outcome)
        if results:
            transport.start_probing(interval_s=config.devices.lifx.echo_probe_interval_s)
        return results

    async def shutdown(self) -> None:
        if self._transport:
            await self._transport.close()
            self._transport = None

    async def _setup(self, record: LifxDeviceRecord, config: AppConfig) -> DiscoveredDevice | None:
        assert self._transport is not None
        adapter = await self._create_adapter(record, config)
        if adapter is None:
            return None
        tracker = self._create_tracker(config)
        await adapter.connect()
        self._transport.register_device(
            record,
            rtt_callback=lambda rtt, t=tracker: t.update(rtt),  # type: ignore[misc]
        )
        return DiscoveredDevice(adapter=adapter, tracker=tracker, max_fps=config.devices.lifx.max_fps)

    async def _create_adapter(
        self, record: LifxDeviceRecord, config: AppConfig
    ) -> LifxAdapterBase | None:
        assert self._transport is not None
        transport = self._transport
        firmware = await transport.query_host_firmware(record.mac, record.ip, record.port)
        product = lifx_product(record.product, firmware, record.vendor)
        if product is not None and product.relays:
            logger.debug("Skipping LIFX switch {} ({})", record.ip, product.name)
            return None
        caps = lifx_capabilities(record.product, firmware, record.vendor)
        stable_id = f"lifx:{record.mac.hex()}"
        label = await self._query_label(record)
        name = self._unique_name(label or f"{caps.model} ({record.ip})", stable_id)
        kelvin = config.devices.lifx.default_kelvin

        def _info(device_type: str, led_count: int) -> DeviceInfo:
            return DeviceInfo(
                name,
                device_type,
                led_count,
                f"{record.ip}:{record.port}",
                mac=record.mac.hex(),
                stable_id=stable_id,
                backend="lifx",
            )

        if caps.matrix:
            tiles = await self._query_chain(record)
            if not tiles:
                logger.warning("LIFX '{}' didn't report its matrix size; assuming 8x8 tiles", name)
            tile_count = len(tiles) or (5 if caps.chain else 1)
            width, height = DEFAULT_TILE_SIZE
            led_count = sum(t.width * t.height for t in tiles) or tile_count * width * height
            return LifxTileChainAdapter(
                transport,
                _info("lifx_tile", led_count),
                record.mac,
                tile_count=tile_count,
                kelvin=kelvin,
                tiles=tiles,
                caps=caps,
            )
        if caps.multizone and caps.extended_multizone:
            zones = await self._query_zone_count(record)
            return LifxStripAdapter(
                transport, _info("lifx_strip", zones), record.mac, zone_count=zones, kelvin=kelvin, caps=caps
            )
        if caps.multizone:
            logger.info("LIFX '{}' has no extended multizone; it plays as one colour", name)
        return LifxBulbAdapter(transport, _info("lifx_bulb", 1), record.mac, kelvin=kelvin, caps=caps)

    def _unique_name(self, wanted: str, stable_id: str) -> str:
        owner = self._names.setdefault(wanted, stable_id)
        if owner == stable_id:
            return wanted
        name = f"{wanted} ({stable_id[-4:]})"
        self._names[name] = stable_id
        return name

    async def _query_label(self, record: LifxDeviceRecord) -> str | None:
        assert self._transport is not None
        request = self._transport.make_request(record.mac, GET_COLOR)
        reply = await self._transport.request_response(
            request, (record.ip, record.port), LIGHT_STATE, 0.5
        )
        if reply is None or reply.msg_type != LIGHT_STATE:
            return None
        try:
            *_colour, label = parse_light_state(reply.payload)
        except ValueError:
            return None
        return label.strip() or None

    async def _query_chain(self, record: LifxDeviceRecord) -> list[TileInfo]:
        assert self._transport is not None
        request = self._transport.make_request(record.mac, GET_DEVICE_CHAIN)
        reply = await self._transport.request_response(
            request, (record.ip, record.port), STATE_DEVICE_CHAIN
        )
        if reply is None or reply.msg_type != STATE_DEVICE_CHAIN:
            return []
        try:
            return parse_state_device_chain(reply.payload)
        except ValueError:
            return []

    async def _query_zone_count(self, record: LifxDeviceRecord) -> int:
        assert self._transport is not None
        request = self._transport.make_request(record.mac, GET_EXTENDED_COLOR_ZONES)
        reply = await self._transport.request_response(
            request, (record.ip, record.port), STATE_EXTENDED_COLOR_ZONES
        )
        if reply is None or reply.msg_type != STATE_EXTENDED_COLOR_ZONES:
            logger.warning("LIFX {} didn't report its zone count; assuming 1", record.ip)
            return 1
        try:
            zone_count, _index, _colours = parse_state_extended_color_zones(reply.payload)
        except ValueError:
            return 1
        return max(1, zone_count)

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        lifx = config.devices.lifx
        strategy: StaticLatency | EMALatency | WindowedMeanLatency
        if lifx.latency_strategy == "static":
            strategy = StaticLatency(lifx.latency_ms)
        elif lifx.latency_strategy == "ema":
            strategy = EMALatency(initial_value_ms=lifx.latency_ms)
        else:
            strategy = WindowedMeanLatency(
                window_size=lifx.latency_window_size,
                initial_value_ms=lifx.latency_ms,
            )
        return LatencyTracker(strategy=strategy, manual_offset_ms=lifx.manual_offset_ms)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/devices/lifx tests/devices/test_discovery.py -v`
Expected: PASS.

- [ ] **Step 5: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/lifx/discovery.py tests/devices/lifx/test_discovery.py
git commit -m "feat(lifx): classify lights by product, size matrices from the chain, name them by label"
```

---

### Task 9: Govee and OpenRGB control

Govee and OpenRGB adapters gain the light control API (spec §6.3, §6.4). Connecting no longer changes the light: today Govee's `connect()` powers the lamp on and sets brightness 100, and OpenRGB's switches the device to Direct mode, both at startup, which breaks "dj-ledfx turns lights on only when a look is applied, never on restart". Power-on moves to `set_power` (called by the zone manager only when a look is applied), the brightness and Direct mode to `prepare_stream`. OpenRGB also gets hardware modes for Task 10.

Govee replies arrive on UDP 4002. On the deployed host Home Assistant's Govee integration holds that port (Task 27), so replies may never reach dj-ledfx: the adapter then connects blind, reads nothing (`LightReading(None, None)`) and captures nothing, so Off leaves the lamp alone (spec §8).

**Files:**
- Modify: `src/dj_ledfx/devices/govee/transport.py` (`can_receive`)
- Modify: `src/dj_ledfx/devices/govee/adapter_base.py`
- Modify: `src/dj_ledfx/devices/openrgb.py`
- Test: `tests/devices/govee/test_control.py`, `tests/devices/test_openrgb_control.py`; modify `tests/devices/govee/test_solid.py`, `tests/devices/govee/test_segment.py` (delete the three tests of connect's old side effects)

**Interfaces:**
- Consumes: `DeviceCapabilities`, `LightReading`, `FirmwareRejected` (Task 2).
- Produces:
  - `GoveeTransport.can_receive -> bool`
  - `GoveeAdapterBase`: `connect()` (reachability check only), `read_light()`, `set_power(on)`, `prepare_stream()` (brightness 100), `capture_state() -> bytes | None` (reads the lamp now)
  - `devices.openrgb.HAS_BRIGHTNESS = 1 << 4`, `HAS_PER_LED_COLOR = 1 << 5`
  - `OpenRGBAdapter`: `capabilities` (model = device name, `openrgb_modes` = mode names), `prepare_stream()` (Direct mode; `send_frame` also switches to Direct on its first frame after a hardware mode), `async set_mode(name: str, brightness: float) -> None` (raises `FirmwareRejected`), `async active_mode_name() -> str | None`, `read_light()` (power unknown, first LED's colour), `capture_state()` / `restore_state()` (JSON `{"mode": name, "colors": [[r, g, b], ...]}`)

- [ ] **Step 1: Write the failing tests**

`tests/devices/govee/test_control.py`:

```python
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

STATUS: dict[str, Any] = {"onOff": 0, "brightness": 50, "color": {"r": 10, "g": 20, "b": 30}}


@pytest.fixture
def record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="10.0.0.9", device_id="AA:BB", sku="H6076", wifi_version="1", ble_version="1"
    )


def _transport(*, can_receive: bool = True, status: dict[str, Any] | None = STATUS) -> MagicMock:
    transport = MagicMock()
    transport.can_receive = can_receive
    transport.query_status = AsyncMock(return_value=status)
    transport.send_command = AsyncMock()
    return transport


async def test_connect_changes_nothing_on_the_lamp(record: GoveeDeviceRecord) -> None:
    transport = _transport()
    adapter = GoveeSolidAdapter(transport, record)
    await adapter.connect()
    assert adapter.is_connected
    transport.send_command.assert_not_awaited()


async def test_connect_without_the_reply_port_connects_blind(record: GoveeDeviceRecord) -> None:
    transport = _transport(can_receive=False)
    adapter = GoveeSolidAdapter(transport, record)
    await adapter.connect()
    assert adapter.is_connected
    transport.query_status.assert_not_awaited()


async def test_read_light_reports_power_and_colour(record: GoveeDeviceRecord) -> None:
    adapter = GoveeSolidAdapter(_transport(), record)
    assert await adapter.read_light() == LightReading(power=False, colour=(10, 20, 30))


@pytest.mark.parametrize(("can_receive", "status"), [(False, STATUS), (True, None)])
async def test_read_light_is_unknown_when_nothing_comes_back(
    record: GoveeDeviceRecord, can_receive: bool, status: dict[str, Any] | None
) -> None:
    adapter = GoveeSolidAdapter(_transport(can_receive=can_receive, status=status), record)
    assert await adapter.read_light() == LightReading(power=None, colour=None)


async def test_capture_reads_the_lamp_now(record: GoveeDeviceRecord) -> None:
    adapter = GoveeSolidAdapter(_transport(), record)
    captured = await adapter.capture_state()
    assert captured is not None
    assert GoveeDeviceState.from_bytes(captured) == GoveeDeviceState(
        on_off=0, brightness=50, r=10, g=20, b=30
    )


async def test_capture_is_none_without_the_reply_port(record: GoveeDeviceRecord) -> None:
    assert await GoveeSolidAdapter(_transport(can_receive=False), record).capture_state() is None


async def test_set_power_and_prepare_stream(record: GoveeDeviceRecord) -> None:
    transport = _transport()
    adapter = GoveeSolidAdapter(transport, record)
    await adapter.set_power(True)
    await adapter.prepare_stream()
    sent = [call.args[1] for call in transport.send_command.call_args_list]
    assert sent == [
        {"msg": {"cmd": "turn", "data": {"value": 1}}},
        {"msg": {"cmd": "brightness", "data": {"value": 100}}},
    ]


def test_transport_knows_whether_it_can_receive() -> None:
    transport = GoveeTransport()
    assert transport.can_receive is False
    transport._recv_transport = MagicMock()
    assert transport.can_receive is True
```

`tests/devices/test_openrgb_control.py`:

```python
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dj_ledfx.devices.capabilities import FirmwareRejected, LightReading
from dj_ledfx.devices.openrgb import HAS_BRIGHTNESS, HAS_PER_LED_COLOR, OpenRGBAdapter


def _mode(name: str, *, brightness: bool = False, per_led: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        flags=(HAS_BRIGHTNESS if brightness else 0) | (HAS_PER_LED_COLOR if per_led else 0),
        brightness=100 if brightness else None,
        brightness_min=0 if brightness else None,
        brightness_max=100 if brightness else None,
    )


def _device() -> MagicMock:
    device = MagicMock()
    device.name = "SteelSeries Apex Pro TKL"
    device.modes = [
        _mode("Direct", per_led=True),
        _mode("Static", per_led=True),
        _mode("Rainbow Wave", brightness=True),
    ]
    device.active_mode = 1
    device.colors = [
        SimpleNamespace(red=10, green=20, blue=30),
        SimpleNamespace(red=0, green=0, blue=0),
    ]
    return device


async def _connected(device: MagicMock) -> OpenRGBAdapter:
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as client_cls:
        client_cls.return_value = MagicMock(devices=[device])
        adapter = OpenRGBAdapter(device_index=0)
        await adapter.connect()
    return adapter


async def test_connect_leaves_the_mode_alone() -> None:
    device = _device()
    await _connected(device)
    device.set_mode.assert_not_called()


async def test_prepare_stream_picks_direct_and_frames_do_it_once() -> None:
    device = _device()
    adapter = await _connected(device)
    await adapter.send_frame(np.zeros((2, 3), dtype=np.uint8))
    await adapter.send_frame(np.zeros((2, 3), dtype=np.uint8))
    device.set_mode.assert_called_once_with("Direct")
    assert device.set_colors.call_count == 2


async def test_capabilities_list_the_modes() -> None:
    caps = (await _connected(_device())).capabilities
    assert caps.protocol == "OpenRGB"
    assert caps.model == "SteelSeries Apex Pro TKL"
    assert caps.openrgb_modes == ("Direct", "Static", "Rainbow Wave")


async def test_set_mode_scales_brightness_on_a_copy() -> None:
    device = _device()
    adapter = await _connected(device)
    await adapter.set_mode("rainbow wave", brightness=0.5)
    (sent,) = device.set_mode.call_args.args
    assert sent.name == "Rainbow Wave"
    assert sent.brightness == 50
    assert device.modes[2].brightness == 100


async def test_a_hardware_mode_makes_the_next_frame_switch_back_to_direct() -> None:
    device = _device()
    adapter = await _connected(device)
    await adapter.prepare_stream()
    await adapter.set_mode("Rainbow Wave", brightness=1.0)
    device.set_mode.reset_mock()
    await adapter.send_frame(np.zeros((2, 3), dtype=np.uint8))
    device.set_mode.assert_called_once_with("Direct")


async def test_unknown_mode_is_rejected() -> None:
    adapter = await _connected(_device())
    with pytest.raises(FirmwareRejected):
        await adapter.set_mode("Plasma", brightness=1.0)


async def test_active_mode_name_reads_the_device() -> None:
    device = _device()
    adapter = await _connected(device)
    assert await adapter.active_mode_name() == "Static"
    device.update.assert_called()


async def test_capture_and_restore_mode_and_colours() -> None:
    device = _device()
    adapter = await _connected(device)
    captured = await adapter.capture_state()
    assert captured is not None
    assert json.loads(captured) == {"mode": "Static", "colors": [[10, 20, 30], [0, 0, 0]]}

    await adapter.restore_state(captured)
    device.set_mode.assert_called_once_with("Static")
    (colours,) = device.set_colors.call_args.args
    assert [(c.red, c.green, c.blue) for c in colours] == [(10, 20, 30), (0, 0, 0)]


async def test_read_light_reports_the_first_colour() -> None:
    adapter = await _connected(_device())
    assert await adapter.read_light() == LightReading(power=None, colour=(10, 20, 30))
```

In `tests/devices/govee/test_solid.py` delete `test_connect_turns_on_if_off` and `test_connect_captures_original_state`; in `tests/devices/govee/test_segment.py` delete `test_connect_captures_original_state`. They test the side effects this task removes; `test_control.py` covers the new behaviour.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/devices/govee/test_control.py tests/devices/test_openrgb_control.py -v`
Expected: FAIL (`ImportError: cannot import name 'HAS_BRIGHTNESS'`; Govee connect sends `turn` and `brightness`).

- [ ] **Step 3: Add `can_receive` to `src/dj_ledfx/devices/govee/transport.py`**

After `is_open`:

```python
    @property
    def can_receive(self) -> bool:
        """False when another program holds UDP 4002, so the lamps' replies never reach us."""
        return self._recv_transport is not None
```

- [ ] **Step 4: Rewrite `src/dj_ledfx/devices/govee/adapter_base.py`**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_solid_color_message,
    build_turn_message,
)
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport

STATUS_TIMEOUT_S = 1.0


class GoveeAdapterBase(DeviceAdapter):
    """Shared base for Govee adapters: connect, power, reads, capture and restore."""

    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord) -> None:
        self._transport = transport
        self._record = record
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        """Check the lamp answers, when its replies can reach us. Changes nothing on it."""
        if self._transport.can_receive:
            status = await self._transport.query_status(self._record.ip)
            if status is None:
                msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
                raise ConnectionError(msg)
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def _status(self) -> GoveeDeviceState | None:
        if not self._transport.can_receive:
            return None
        status = await self._transport.query_status(self._record.ip, timeout_s=STATUS_TIMEOUT_S)
        return GoveeDeviceState.from_status(status) if status is not None else None

    async def read_light(self) -> LightReading:
        state = await self._status()
        if state is None:
            return LightReading(power=None, colour=None)
        return LightReading(power=bool(state.on_off), colour=(state.r, state.g, state.b))

    async def set_power(self, on: bool) -> None:
        await self._transport.send_command(self._record.ip, build_turn_message(on=on))

    async def prepare_stream(self) -> None:
        await self._transport.send_command(self._record.ip, build_brightness_message(100))

    async def capture_state(self) -> bytes | None:
        state = await self._status()
        return state.to_bytes() if state is not None else None

    async def restore_state(self, state: bytes) -> None:
        saved = GoveeDeviceState.from_bytes(state)
        ip = self._record.ip
        await self._transport.send_command(
            ip, build_solid_color_message(saved.r, saved.g, saved.b)
        )
        await self._transport.send_command(ip, build_brightness_message(saved.brightness))
        # Turn off last so colour and brightness are set while the lamp is still on
        if not saved.on_off:
            await self._transport.send_command(ip, build_turn_message(on=False))
```

- [ ] **Step 5: Update `src/dj_ledfx/devices/openrgb.py`**

Add `import copy` and `import json` to the imports and `from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected, LightReading`. Add module constants after the `try/except ImportError` block:

```python
HAS_BRIGHTNESS = 1 << 4  # openrgb.utils.ModeFlags.HAS_BRIGHTNESS
HAS_PER_LED_COLOR = 1 << 5  # openrgb.utils.ModeFlags.HAS_PER_LED_COLOR
```

In `__init__` add:

```python
        self._modes: tuple[str, ...] = ()
        self._streaming = False  # True once the device is in Direct mode for streamed frames
```

In `connect()`'s inner `_connect`, delete the "Switch to Direct mode" loop and add, after `self._device = device`:

```python
            self._modes = tuple(str(mode.name) for mode in device.modes)
            self._streaming = False
```

In `send_frame`, after the `if not self._is_connected or self._device is None: return` guard:

```python
        if not self._streaming:
            await self.prepare_stream()
```

Add these methods after `send_frame`:

```python
    @property
    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            protocol="OpenRGB", model=self._device_name, openrgb_modes=self._modes
        )

    def _find_mode(self, name: str) -> Any:
        device = self._device
        if device is None:
            return None
        return next((m for m in device.modes if str(m.name).lower() == name.lower()), None)

    async def prepare_stream(self) -> None:
        device = self._device
        direct = self._find_mode("direct")
        if device is not None and direct is not None:
            await asyncio.to_thread(device.set_mode, str(direct.name))
        self._streaming = True

    async def set_mode(self, name: str, brightness: float) -> None:
        """Start one of the device's own modes, scaled to the zone's brightness."""
        device = self._device
        mode = self._find_mode(name)
        if device is None or mode is None:
            raise FirmwareRejected(f"{self._device_name} has no mode '{name}'")
        chosen = copy.copy(mode)
        if int(chosen.flags) & HAS_BRIGHTNESS and chosen.brightness_max is not None:
            low = int(chosen.brightness_min or 0)
            high = int(chosen.brightness_max)
            chosen.brightness = round(low + (high - low) * max(0.0, min(1.0, brightness)))
        try:
            await asyncio.to_thread(device.set_mode, chosen)
        except (ValueError, ConnectionError, OSError) as exc:
            raise FirmwareRejected(f"{self._device_name} refused mode '{name}': {exc}") from exc
        self._streaming = False

    async def _read(self) -> tuple[str, list[tuple[int, int, int]]] | None:
        """The active mode's name and the LED colours, fresh from the server."""
        device = self._device
        if device is None:
            return None

        def _update() -> tuple[str, list[tuple[int, int, int]]]:
            device.update()
            colours = [(int(c.red), int(c.green), int(c.blue)) for c in device.colors]
            return str(device.modes[device.active_mode].name), colours

        try:
            return await asyncio.to_thread(_update)
        except (IndexError, ConnectionError, OSError):
            return None

    async def active_mode_name(self) -> str | None:
        read = await self._read()
        return read[0] if read is not None else None

    async def read_light(self) -> LightReading:
        read = await self._read()
        colour = read[1][0] if read is not None and read[1] else None
        return LightReading(power=None, colour=colour)

    async def capture_state(self) -> bytes | None:
        read = await self._read()
        if read is None:
            return None
        mode, colours = read
        return json.dumps({"mode": mode, "colors": [list(c) for c in colours]}).encode()

    async def restore_state(self, state: bytes) -> None:
        device = self._device
        try:
            snapshot = json.loads(state)
            mode = self._find_mode(str(snapshot["mode"]))
            colours = [RGBColor(int(r), int(g), int(b)) for r, g, b in snapshot["colors"]]
        except (ValueError, KeyError, TypeError):
            logger.warning("OpenRGB '{}': captured state is unreadable", self._device_name)
            return
        if device is None or mode is None:
            return

        def _restore() -> None:
            device.set_mode(str(mode.name))
            if colours and int(mode.flags) & HAS_PER_LED_COLOR:
                device.set_colors(colours)

        try:
            await asyncio.to_thread(_restore)
        except (ValueError, ConnectionError, OSError):
            logger.warning("OpenRGB '{}': couldn't restore its mode", self._device_name)
        self._streaming = False
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/devices -v`
Expected: PASS.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/devices/govee src/dj_ledfx/devices/openrgb.py tests/devices/govee tests/devices/test_openrgb_control.py
git commit -m "feat(devices): Govee and OpenRGB power, reads and hardware modes; connecting changes nothing"
```

Until Task 24 the old transport never calls `set_power`, so a Govee lamp that is off stays off when it plays; that is the intended M1 behaviour once zones apply looks.

---

### Task 10: Firmware effects

The firmware layer kinds M1 ships (spec §6.3; web spec §11.2): LIFX Flame and Morph (tile effects), LIFX Move (multizone effect), LIFX waveforms, and OpenRGB hardware modes. Each one says which lights support it, starts, stops and checks itself on a light, and renders a streamed copy (`emulate`) for lights that can't run it and for the preview. Govee has no firmware effects; it always gets a streamed copy.

**Files:**
- Create: `src/dj_ledfx/effects/firmware_lifx.py` (`LifxFlame`, `LifxMorph`, `LifxMove`, `LifxWaveform`)
- Create: `src/dj_ledfx/effects/firmware_openrgb.py` (`OpenrgbMode`)
- Modify: `src/dj_ledfx/effects/__init__.py` (import both)
- Test: `tests/effects/test_firmware_effects.py`

**Interfaces:**
- Consumes: `FirmwareEffect`, `Params` (Task 3); `RenderContext`, `LedSet` (Task 1); `DeviceCapabilities`, `FirmwareRejected` (Task 2); the LIFX adapters' `set_colour`, `set_waveform`, `start_tile_effect`, `tile_effect`, `set_zone_colours`, `start_multizone_effect`, `multizone_effect` (Task 7); `OpenRGBAdapter.set_mode`, `active_mode_name`, `prepare_stream` (Task 9); `FakeLifxTransport` (Task 7).
- Produces (registry names in brackets):
  - `LifxFlame` [`lifx_flame`], `display_name = "LIFX Flame"`, params `period` (float 1–20, default 5): matrix LIFX lights
  - `LifxMorph` [`lifx_morph`], `"LIFX Morph"`, params `period` (float 1–20, default 6), `palette` (color_list): matrix LIFX lights
  - `LifxMove` [`lifx_move`], `"LIFX Move"`, params `period` (float 1–30, default 8), `reverse` (bool), `palette` (color_list): multizone LIFX lights
  - `LifxWaveform` [`lifx_waveform`], `"LIFX waveform"`, params `period` (float 0.5–20, default 4), `colour` (color, `#ff6a00`), `base` (color, `#1a0033`), `waveform` (choice `sine`/`triangle`/`saw`/`half_sine`/`pulse`): any LIFX colour light; `is_running` is `None` (a waveform can't be read back)
  - `OpenrgbMode` [`openrgb_mode`], `"OpenRGB mode"`, params `mode` (choice `auto`/`Rainbow Wave`/`Spectrum Cycle`/`Rainbow`/`Breathing`): OpenRGB devices that have the mode (`auto` = the first of those four the device has); `stop` returns the device to Direct mode
  - `start(adapter, params)` reads its settings and `brightness` (0–1) from `params` (what `FirmwareEffect.start_params(brightness)` builds), scales every colour by the brightness, and raises `FirmwareRejected` when the adapter isn't the right kind or the light refuses

- [ ] **Step 1: Write the failing tests**

`tests/effects/test_firmware_effects.py`:

```python
from __future__ import annotations

import struct
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from lifx_fakes import FakeLifxTransport

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import (
    SET_COLOR,
    SET_EXTENDED_COLOR_ZONES,
    SET_MULTIZONE_EFFECT,
    SET_TILE_EFFECT,
    SET_WAVEFORM,
    MultiZoneEffectType,
    TileEffectType,
    Waveform,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.devices.openrgb import HAS_BRIGHTNESS, OpenRGBAdapter
from dj_ledfx.effects.context import NO_SIGNALS, RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.firmware_lifx import LifxFlame, LifxMorph, LifxMove, LifxWaveform
from dj_ledfx.effects.firmware_openrgb import OpenrgbMode
from dj_ledfx.effects.ledset import LedSource, build_ledset
from dj_ledfx.effects.registry import get_effect_class, get_effect_schemas
from dj_ledfx.spatial.geometry import MatrixGeometry, TileLayout
from dj_ledfx.types import DeviceInfo

MAC = b"\xd0\x73\xd5\x00\x00\x01"
CANDLE = DeviceCapabilities(protocol="LIFX", model="LIFX Candle C", matrix=True)
NEON = DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True)
BULB = DeviceCapabilities(protocol="LIFX")
WHITE_BULB = DeviceCapabilities(protocol="LIFX", colour=False)
GOVEE = DeviceCapabilities(protocol="Govee")
PC = DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("Direct", "Static", "Rainbow Wave"))
PC_PLAIN = DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("Direct", "Static"))
KINDS = ["lifx_flame", "lifx_morph", "lifx_move", "lifx_waveform", "openrgb_mode"]


def _info(kind: str, leds: int) -> DeviceInfo:
    return DeviceInfo(
        "Light", f"lifx_{kind}", leds, "10.0.0.5:56700", stable_id="lifx:1", backend="lifx"
    )


def _candle(transport: FakeLifxTransport) -> LifxTileChainAdapter:
    tile = TileInfo(user_x=0.0, user_y=0.0, width=5, height=6, accel_x=0, accel_y=0, accel_z=0)
    return LifxTileChainAdapter(transport, _info("tile", 30), MAC, tiles=[tile])  # type: ignore[arg-type]


def _strip(transport: FakeLifxTransport) -> LifxStripAdapter:
    return LifxStripAdapter(transport, _info("strip", 12), MAC, zone_count=12)  # type: ignore[arg-type]


def _bulb(transport: FakeLifxTransport) -> LifxBulbAdapter:
    return LifxBulbAdapter(transport, _info("bulb", 1), MAC)  # type: ignore[arg-type]


def _ctx(t: float) -> RenderContext:
    return RenderContext(
        t=t, dt=1 / 60, beat_phase=0.0, bar_phase=0.0, bpm=120.0,
        beat_index=0, bar_index=0, signals=NO_SIGNALS,
    )


def test_firmware_kinds_are_registered_but_not_offered_as_strip_effects() -> None:
    for kind in KINDS:
        assert issubclass(get_effect_class(kind), FirmwareEffect)
    assert not set(KINDS) & set(get_effect_schemas())


@pytest.mark.parametrize(
    ("effect", "supported", "unsupported"),
    [
        (LifxFlame(), [CANDLE], [NEON, BULB, GOVEE, PC]),
        (LifxMorph(), [CANDLE], [NEON, BULB, GOVEE, PC]),
        (LifxMove(), [NEON], [CANDLE, BULB, GOVEE, PC]),
        (LifxWaveform(), [CANDLE, NEON, BULB], [WHITE_BULB, GOVEE, PC]),
        (OpenrgbMode(), [PC], [PC_PLAIN, CANDLE, GOVEE]),
    ],
)
def test_supports(
    effect: FirmwareEffect,
    supported: list[DeviceCapabilities],
    unsupported: list[DeviceCapabilities],
) -> None:
    assert all(effect.supports(caps) for caps in supported)
    assert not any(effect.supports(caps) for caps in unsupported)


def test_openrgb_mode_can_ask_for_one_mode() -> None:
    effect = OpenrgbMode(mode="Breathing")
    assert not effect.supports(PC)
    assert effect.supports(DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("breathing",)))


async def test_flame_sets_a_warm_colour_at_the_zone_brightness_then_starts() -> None:
    transport = FakeLifxTransport()
    candle = _candle(transport)
    flame = LifxFlame(period=5.0)

    await flame.start(candle, flame.start_params(0.5))

    assert transport.types() == [SET_COLOR, SET_TILE_EFFECT]
    _reserved, *_hs, brightness, _kelvin, _duration = struct.unpack(
        "<B4HI", transport.last(SET_COLOR).payload
    )
    assert brightness == pytest.approx(65535 * 0.5, abs=2)
    assert transport.tile_effect[:2] == (TileEffectType.FLAME, 5000)
    assert await flame.is_running(candle) is True

    await flame.stop(candle)
    assert await flame.is_running(candle) is False


async def test_flame_is_rejected_by_a_bulb_and_by_a_refusing_light() -> None:
    flame = LifxFlame()
    with pytest.raises(FirmwareRejected):
        await flame.start(_bulb(FakeLifxTransport()), flame.start_params(1.0))
    with pytest.raises(FirmwareRejected):
        await flame.start(
            _candle(FakeLifxTransport(unhandled={SET_TILE_EFFECT})), flame.start_params(1.0)
        )


async def test_morph_sends_its_palette_scaled_by_brightness() -> None:
    transport = FakeLifxTransport()
    morph = LifxMorph(period=6.0, palette=["#ff0000", "#0000ff"])
    await morph.start(_candle(transport), morph.start_params(0.25))
    effect, speed, palette = transport.tile_effect
    assert (effect, speed) == (TileEffectType.MORPH, 6000)
    assert [colour[2] for colour in palette] == [pytest.approx(65535 * 0.25, abs=2)] * 2


async def test_move_paints_a_gradient_then_starts_moving() -> None:
    transport = FakeLifxTransport(zones=[(0, 0, 0, 3500)] * 12)
    move = LifxMove(period=8.0, reverse=True)
    strip = _strip(transport)
    await move.start(strip, move.start_params(1.0))
    assert transport.types() == [SET_EXTENDED_COLOR_ZONES, SET_MULTIZONE_EFFECT]
    assert transport.multizone_effect == (MultiZoneEffectType.MOVE, 8000, True)
    assert len(set(transport.zones)) > 1
    assert await move.is_running(strip) is True
    await move.stop(strip)
    assert await move.is_running(strip) is False


async def test_waveform_sets_the_base_then_runs_a_transient_waveform() -> None:
    transport = FakeLifxTransport()
    wave = LifxWaveform(period=4.0, waveform="triangle")
    bulb = _bulb(transport)
    await wave.start(bulb, wave.start_params(1.0))
    assert transport.types() == [SET_COLOR, SET_WAVEFORM]
    payload = transport.last(SET_WAVEFORM).payload
    _r, transient, _h, _s, _b, _k, period, cycles, _skew, waveform = struct.unpack(
        "<BB4HIfhB", payload
    )
    assert (transient, period, waveform) == (1, 4000, Waveform.TRIANGLE)
    assert cycles >= 1e6
    assert await wave.is_running(bulb) is None


def _pc_device() -> MagicMock:
    device = MagicMock()
    device.name = "PC"
    device.modes = [
        SimpleNamespace(name="Direct", flags=0, brightness=None, brightness_min=None, brightness_max=None),
        SimpleNamespace(name="Static", flags=0, brightness=None, brightness_min=None, brightness_max=None),
        SimpleNamespace(
            name="Rainbow Wave", flags=HAS_BRIGHTNESS, brightness=100, brightness_min=0, brightness_max=100
        ),
    ]
    device.active_mode = 1
    device.colors = [SimpleNamespace(red=0, green=0, blue=0)]
    return device


async def test_openrgb_mode_starts_checks_and_stops() -> None:
    device = _pc_device()
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as client_cls:
        client_cls.return_value = MagicMock(devices=[device])
        pc = OpenRGBAdapter(device_index=0)
        await pc.connect()
    effect = OpenrgbMode()

    await effect.start(pc, effect.start_params(0.4))
    (sent,) = device.set_mode.call_args.args
    assert (sent.name, sent.brightness) == ("Rainbow Wave", 40)

    assert await effect.is_running(pc) is False
    device.active_mode = 2
    assert await effect.is_running(pc) is True

    await effect.stop(pc)
    device.set_mode.assert_called_with("Direct")


@pytest.mark.parametrize("kind", KINDS)
def test_emulations_are_finite_in_range_and_repeatable(kind: str) -> None:
    effect = get_effect_class(kind)()
    leds = build_ledset(
        [
            LedSource("candle", 30, MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 5, 6),))),
            LedSource("bulb", 1),
            LedSource("neon", 12),
        ]
    )
    first = effect.emulate(_ctx(10.0), leds)  # type: ignore[attr-defined]
    again = effect.emulate(_ctx(10.0), leds)  # type: ignore[attr-defined]
    later = effect.emulate(_ctx(11.3), leds)  # type: ignore[attr-defined]
    assert first.shape == (leds.count, 3)
    assert first.dtype == np.float32
    assert np.isfinite(first).all()
    assert first.min() >= 0.0 and first.max() <= 1.0
    assert np.array_equal(first, again)
    assert not np.array_equal(first, later)


def test_flame_copy_is_hotter_at_the_bottom() -> None:
    leds = build_ledset([LedSource("lamp", 20)])  # a vertical strip, first LED at the bottom
    flame = LifxFlame()
    frames = [flame.emulate(_ctx(t / 7), leds) for t in range(30)]
    heat = np.mean([frame.sum(axis=1) for frame in frames], axis=0)
    assert heat[:5].mean() > heat[-5:].mean()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/effects/test_firmware_effects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.effects.firmware_lifx'`.

- [ ] **Step 3: Write `src/dj_ledfx/effects/firmware_lifx.py`**

```python
"""LIFX firmware effects: Flame and Morph (tile effects), Move (multizone effect) and
waveforms (spec §6.3). Each also renders a streamed copy for lights that can't run it."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.lifx.base import LifxAdapterBase
from dj_ledfx.devices.lifx.packet import (
    HSBK,
    MultiZoneEffectType,
    TileEffectType,
    Waveform,
    rgb_to_hsbk,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.effects.color import hex_to_rgb, palette_lerp, rgb_to_hex
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

RGB = tuple[int, int, int]

FLAME_BASE = "#ff8a2a"
FLAME_COPY: list[RGB] = [(40, 4, 0), (190, 40, 0), (255, 120, 10), (255, 205, 110)]
MORPH_PALETTE = ["#ff3d6e", "#7b2cff", "#00b7ff", "#00e39a"]
MOVE_PALETTE = ["#ff0055", "#ffb300", "#00e5ff", "#8a2bff"]
WAVEFORMS = {
    "sine": Waveform.SINE,
    "triangle": Waveform.TRIANGLE,
    "saw": Waveform.SAW,
    "half_sine": Waveform.HALF_SINE,
    "pulse": Waveform.PULSE,
}
WAVEFORM_CYCLES = 1_000_000.0  # runs for weeks; a new look or Off interrupts it


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _period_ms(params: Params, default: float) -> int:
    return max(1, round(float(params.get("period", default)) * 1000))


def _hsbk(colour: str | RGB, brightness: float, kelvin: int = 3500) -> HSBK:
    r, g, b = hex_to_rgb(colour) if isinstance(colour, str) else colour
    hue, sat, bri, k = rgb_to_hsbk(r, g, b, kelvin=kelvin)
    return hue, sat, round(bri * _clamp01(brightness)), k


def _to_float(colours: NDArray[np.uint8]) -> FloatRGB:
    out = colours.astype(np.float32)
    out *= np.float32(1.0 / 255.0)
    return out


def _cyclic(palette: list[RGB], positions: NDArray[np.float64]) -> FloatRGB:
    """Palette colours around a loop: position 0 and 1 are the same colour."""
    return _to_float(palette_lerp([*palette, palette[0]], np.mod(positions, 1.0)))


def _lifx(adapter: DeviceAdapter) -> LifxAdapterBase:
    if not isinstance(adapter, LifxAdapterBase):
        raise FirmwareRejected(f"{adapter.device_info.name} isn't a LIFX light")
    return adapter


def _matrix(adapter: DeviceAdapter) -> LifxTileChainAdapter:
    if not isinstance(adapter, LifxTileChainAdapter):
        raise FirmwareRejected(f"{adapter.device_info.name} isn't a LIFX matrix light")
    return adapter


def _multizone(adapter: DeviceAdapter) -> LifxStripAdapter:
    if not isinstance(adapter, LifxStripAdapter):
        raise FirmwareRejected(f"{adapter.device_info.name} isn't a LIFX multizone light")
    return adapter


def _palette_param(default: list[str]) -> EffectParam:
    return EffectParam(type="color_list", default=list(default), label="Palette")


class LifxFlame(FirmwareEffect):
    display_name = "LIFX Flame"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=5.0, min=1.0, max=20.0, step=0.5, label="Speed"
            )
        }

    def __init__(self, period: float = 5.0) -> None:
        self._period = period

    def get_params(self) -> dict[str, Any]:
        return {"period": self._period}

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.matrix

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        matrix = _matrix(adapter)
        # The flame's intensity follows the light's own brightness.
        await matrix.set_colour(_hsbk(FLAME_BASE, float(params.get("brightness", 1.0))))
        await matrix.start_tile_effect(TileEffectType.FLAME, _period_ms(params, self._period))

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _matrix(adapter).start_tile_effect(TileEffectType.OFF, 0)

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        state = await _matrix(adapter).tile_effect()
        return None if state is None else state.effect == TileEffectType.FLAME

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        phase = 2.0 * math.pi * ctx.t / self._period
        u = leds.local_u.astype(np.float64)
        height = leds.local[:, 2].astype(np.float64)
        wobble = 0.5 + 0.25 * np.sin(phase * 3.1 + u * 11.0) + 0.25 * np.sin(
            phase * 5.3 + u * 23.0 + leds.device * 1.7
        )
        heat = np.clip((1.0 - height) * 0.7 + wobble * 0.4 - 0.05, 0.0, 1.0)
        return _to_float(palette_lerp(FLAME_COPY, heat))


class LifxMorph(FirmwareEffect):
    display_name = "LIFX Morph"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=6.0, min=1.0, max=20.0, step=0.5, label="Speed"
            ),
            "palette": _palette_param(MORPH_PALETTE),
        }

    def __init__(self, period: float = 6.0, palette: list[str] | None = None) -> None:
        self._period = period
        self._palette = [hex_to_rgb(c) for c in (palette or MORPH_PALETTE)]

    def get_params(self) -> dict[str, Any]:
        return {"period": self._period, "palette": [rgb_to_hex(*c) for c in self._palette]}

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])
        if "palette" in kwargs and kwargs["palette"]:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.matrix

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        brightness = float(params.get("brightness", 1.0))
        palette = [_hsbk(c, brightness) for c in params.get("palette", MORPH_PALETTE)]
        await _matrix(adapter).start_tile_effect(
            TileEffectType.MORPH, _period_ms(params, self._period), palette
        )

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _matrix(adapter).start_tile_effect(TileEffectType.OFF, 0)

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        state = await _matrix(adapter).tile_effect()
        return None if state is None else state.effect == TileEffectType.MORPH

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        drift = ctx.t / (self._period * 4.0)
        swirl = 0.15 * np.sin(2.0 * math.pi * (ctx.t / self._period) + leds.local_u * 6.0)
        position = leds.npos[:, 0] * 0.6 + leds.npos[:, 2] * 0.4 + drift + swirl
        return _cyclic(self._palette, position.astype(np.float64))


class LifxMove(FirmwareEffect):
    display_name = "LIFX Move"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=8.0, min=1.0, max=30.0, step=0.5, label="Speed"
            ),
            "reverse": EffectParam(type="bool", default=False, label="Reverse"),
            "palette": _palette_param(MOVE_PALETTE),
        }

    def __init__(
        self, period: float = 8.0, reverse: bool = False, palette: list[str] | None = None
    ) -> None:
        self._period = period
        self._reverse = reverse
        self._palette = [hex_to_rgb(c) for c in (palette or MOVE_PALETTE)]

    def get_params(self) -> dict[str, Any]:
        return {
            "period": self._period,
            "reverse": self._reverse,
            "palette": [rgb_to_hex(*c) for c in self._palette],
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])
        if "reverse" in kwargs:
            self._reverse = bool(kwargs["reverse"])
        if "palette" in kwargs and kwargs["palette"]:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.multizone

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        strip = _multizone(adapter)
        brightness = float(params.get("brightness", 1.0))
        palette = [hex_to_rgb(c) for c in params.get("palette", MOVE_PALETTE)]
        count = strip.led_count
        positions = np.arange(count, dtype=np.float64) / max(1, count)
        gradient = palette_lerp([*palette, palette[0]], positions)
        await strip.set_zone_colours(
            [_hsbk((int(r), int(g), int(b)), brightness) for r, g, b in gradient]
        )
        await strip.start_multizone_effect(
            MultiZoneEffectType.MOVE,
            _period_ms(params, self._period),
            reverse=bool(params.get("reverse", self._reverse)),
        )

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _multizone(adapter).start_multizone_effect(MultiZoneEffectType.OFF, 0)

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        state = await _multizone(adapter).multizone_effect()
        return None if state is None else state.effect == MultiZoneEffectType.MOVE

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        direction = -1.0 if self._reverse else 1.0
        position = leds.local_u.astype(np.float64) - direction * ctx.t / self._period
        return _cyclic(self._palette, position)


class LifxWaveform(FirmwareEffect):
    display_name = "LIFX waveform"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "period": EffectParam(
                type="float", default=4.0, min=0.5, max=20.0, step=0.5, label="Speed"
            ),
            "colour": EffectParam(type="color", default="#ff6a00", label="Colour"),
            "base": EffectParam(type="color", default="#1a0033", label="Base"),
            "waveform": EffectParam(
                type="choice", default="sine", choices=list(WAVEFORMS), label="Shape"
            ),
        }

    def __init__(
        self,
        period: float = 4.0,
        colour: str = "#ff6a00",
        base: str = "#1a0033",
        waveform: str = "sine",
    ) -> None:
        self._period = period
        self._colour = colour
        self._base = base
        self._waveform = waveform

    def get_params(self) -> dict[str, Any]:
        return {
            "period": self._period,
            "colour": self._colour,
            "base": self._base,
            "waveform": self._waveform,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "period" in kwargs:
            self._period = float(kwargs["period"])
        if "colour" in kwargs:
            self._colour = str(kwargs["colour"])
        if "base" in kwargs:
            self._base = str(kwargs["base"])
        if "waveform" in kwargs:
            self._waveform = str(kwargs["waveform"])

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "LIFX" and caps.colour

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        light = _lifx(adapter)
        brightness = float(params.get("brightness", 1.0))
        await light.set_colour(_hsbk(str(params.get("base", self._base)), brightness))
        await light.set_waveform(
            _hsbk(str(params.get("colour", self._colour)), brightness),
            _period_ms(params, self._period),
            WAVEFORM_CYCLES,
            WAVEFORMS[str(params.get("waveform", self._waveform))],
            transient=True,
        )

    async def stop(self, adapter: DeviceAdapter) -> None:
        # Any SetColor interrupts a waveform.
        await _lifx(adapter).set_colour(_hsbk(self._base, 1.0))

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        return None  # LIFX can't report a running waveform

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        p = (ctx.t / self._period) % 1.0
        shape = self._waveform
        if shape == "triangle":
            v = 1.0 - abs(2.0 * p - 1.0)
        elif shape == "saw":
            v = p
        elif shape == "half_sine":
            v = math.sin(math.pi * p)
        elif shape == "pulse":
            v = 1.0 if p < 0.5 else 0.0
        else:
            v = 0.5 - 0.5 * math.cos(2.0 * math.pi * p)
        base = np.array(hex_to_rgb(self._base), dtype=np.float32)
        target = np.array(hex_to_rgb(self._colour), dtype=np.float32)
        out = np.empty((leds.count, 3), dtype=np.float32)
        out[:] = (base + (target - base) * np.float32(v)) / np.float32(255.0)
        return out
```

- [ ] **Step 4: Write `src/dj_ledfx/effects/firmware_openrgb.py`**

```python
"""OpenRGB hardware modes as a firmware effect (spec §6.3)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.openrgb import OpenRGBAdapter
from dj_ledfx.effects.color import hsv_to_rgb_array
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.params import EffectParam

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

PREFERRED_MODES = ("Rainbow Wave", "Spectrum Cycle", "Rainbow", "Breathing")
COPY_PERIOD_S = 8.0


def _openrgb(adapter: DeviceAdapter) -> OpenRGBAdapter:
    if not isinstance(adapter, OpenRGBAdapter):
        raise FirmwareRejected(f"{adapter.device_info.name} isn't an OpenRGB device")
    return adapter


class OpenrgbMode(FirmwareEffect):
    display_name = "OpenRGB mode"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "mode": EffectParam(
                type="choice", default="auto", choices=["auto", *PREFERRED_MODES], label="Mode"
            )
        }

    def __init__(self, mode: str = "auto") -> None:
        self._mode = mode

    def get_params(self) -> dict[str, Any]:
        return {"mode": self._mode}

    def _apply_params(self, **kwargs: Any) -> None:
        if "mode" in kwargs:
            self._mode = str(kwargs["mode"])

    def chosen_mode(self, caps: DeviceCapabilities, wanted: str | None = None) -> str | None:
        """The device's own name for the mode to run, or None if it has none of them."""
        available = {name.lower(): name for name in caps.openrgb_modes}
        mode = wanted or self._mode
        for name in PREFERRED_MODES if mode == "auto" else (mode,):
            if name.lower() in available:
                return available[name.lower()]
        return None

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.protocol == "OpenRGB" and self.chosen_mode(caps) is not None

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        device = _openrgb(adapter)
        mode = self.chosen_mode(device.capabilities, str(params.get("mode", self._mode)))
        if mode is None:
            raise FirmwareRejected(f"{device.device_info.name} has none of {PREFERRED_MODES}")
        await device.set_mode(mode, float(params.get("brightness", 1.0)))

    async def stop(self, adapter: DeviceAdapter) -> None:
        await _openrgb(adapter).prepare_stream()

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        device = _openrgb(adapter)
        mode = self.chosen_mode(device.capabilities)
        active = await device.active_mode_name()
        if mode is None or active is None:
            return None
        return active.lower() == mode.lower()

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        if self._mode == "Breathing":
            level = 0.5 - 0.5 * math.cos(2.0 * math.pi * ctx.t / COPY_PERIOD_S)
            out = np.zeros((leds.count, 3), dtype=np.float32)
            out[:, 0] = np.float32(level)
            return out
        hues = np.mod(leds.local_u.astype(np.float64) - ctx.t / COPY_PERIOD_S, 1.0)
        out = hsv_to_rgb_array(hues, 1.0, 1.0).astype(np.float32)
        out *= np.float32(1.0 / 255.0)
        return out
```

- [ ] **Step 5: Register them in `src/dj_ledfx/effects/__init__.py`**

Add, keeping the list alphabetical:

```python
from dj_ledfx.effects import firmware_lifx as _firmware_lifx  # noqa: F401
from dj_ledfx.effects import firmware_openrgb as _firmware_openrgb  # noqa: F401
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/effects -v`
Expected: PASS.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/effects/firmware_lifx.py src/dj_ledfx/effects/firmware_openrgb.py src/dj_ledfx/effects/__init__.py tests/effects/test_firmware_effects.py
git commit -m "feat(effects): LIFX Flame, Morph, Move and waveform, and OpenRGB hardware modes as firmware effects"
```

---

### Task 11: Look model and validation

Looks become data (spec §5.2): a look is layers plus modifiers, a transition and metadata, shaped exactly like the contract's `Look` and `Layer` (web spec §12.2), so the API can return it as it is. M1 validates what it can run and says which milestone brings the rest: one visible streamed layer plus any number of firmware layers, no particles (M5), no modifiers (M4), no bindings (M7), no whole-home scope (M6). Transitions are stored but play as a cut until M4.

**Files:**
- Create: `src/dj_ledfx/looks/__init__.py`, `src/dj_ledfx/looks/model.py`
- Test: `tests/looks/__init__.py`, `tests/looks/test_model.py`

**Interfaces:**
- Consumes: `get_effect_class` (Task 3); `StripEffect`, `FieldEffect`, `FirmwareEffect`, `StripAdapter` (Task 3); `EffectParam`.
- Produces (all in `looks.model`):
  - Literals `LayerType`, `Blend`, `TransitionKind`, `Category`, `Scope`, `InputKind`
  - `Transition(kind: TransitionKind = "cut", duration_s: float = 0.0)`, `LookModifiers(trails_s=None, downbeat_flash=False, brightness_cap=None, evening=False)`
  - `Layer(id, name, type, kind, visible=True, blend="normal", opacity=1.0, settings: Mapping[str, Any] = {})`
  - `Look(id, name, category, description="", thumbnail="", scope="any-zone", needs=(), uses=(), layers=(), modifiers=LookModifiers(), transition=Transition(), built_in=False, derived_from=None)`
  - `LookError(ValueError)`, `LookNotFoundError(KeyError)`, `BuiltInLookError(Exception)`
  - `look_from_dict(data: Mapping[str, Any]) -> Look` (contract camelCase in; raises `LookError`), `look_to_dict(look: Look, *, starred: bool = False) -> dict[str, Any]` (contract camelCase out, with each layer's `schema`)
  - `setting_schema(kind: str) -> list[dict[str, Any]]` (contract `SettingSchema`; `bindable` is always False in M1)
  - `make_effect(layer: Layer) -> FieldEffect | FirmwareEffect` (strip effects come wrapped in `StripAdapter`; raises `LookError`)
  - `validate_look(look: Look) -> None` (raises `LookError`)
  - `visible_field_layer(look: Look) -> Layer | None`, `firmware_layers(look: Look) -> list[Layer]` (bottom to top)

- [ ] **Step 1: Write the failing tests**

`tests/looks/__init__.py` is empty. `tests/looks/test_model.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from dj_ledfx.effects.firmware_lifx import LifxFlame
from dj_ledfx.effects.strip_adapter import StripAdapter
from dj_ledfx.looks.model import (
    Layer,
    Look,
    LookError,
    LookModifiers,
    Transition,
    firmware_layers,
    look_from_dict,
    look_to_dict,
    make_effect,
    setting_schema,
    validate_look,
    visible_field_layer,
)


def _layer(**overrides: Any) -> dict[str, Any]:
    layer: dict[str, Any] = {
        "id": "l1",
        "name": "Breathe",
        "type": "field",
        "kind": "breathe",
        "visible": True,
        "blend": "normal",
        "opacity": 1.0,
        "settings": {"beats_per_cycle": {"value": 2.0}},
    }
    layer.update(overrides)
    return layer


def _look(**overrides: Any) -> dict[str, Any]:
    look: dict[str, Any] = {
        "id": "mine-1",
        "name": "My breathe",
        "category": "tempo",
        "builtIn": False,
        "derivedFrom": "classic-breathe",
        "description": "Slow",
        "thumbnail": "classic-breathe",
        "scope": "any-zone",
        "needs": [],
        "uses": ["tempo"],
        "starred": False,
        "layers": [_layer()],
        "modifiers": {"trailsS": None, "downbeatFlash": False, "brightnessCap": None, "evening": False},
        "transition": {"kind": "fade", "durationS": 2.0},
    }
    look.update(overrides)
    return look


def test_contract_round_trip() -> None:
    look = look_from_dict(_look())
    assert look.id == "mine-1"
    assert look.derived_from == "classic-breathe"
    assert look.uses == ("tempo",)
    assert look.layers[0].settings == {"beats_per_cycle": 2.0}
    assert look.transition == Transition(kind="fade", duration_s=2.0)

    out = look_to_dict(look, starred=True)
    assert out["builtIn"] is False
    assert out["derivedFrom"] == "classic-breathe"
    assert out["starred"] is True
    assert out["layers"][0]["settings"] == {"beats_per_cycle": {"value": 2.0}}
    assert out["modifiers"] == {
        "trailsS": None,
        "downbeatFlash": False,
        "brightnessCap": None,
        "evening": False,
    }
    assert out["transition"] == {"kind": "fade", "durationS": 2.0}
    assert look_from_dict(out) == look


def test_layer_schema_follows_the_effect_parameters() -> None:
    schema = {entry["key"]: entry for entry in look_to_dict(look_from_dict(_look()))["layers"][0]["schema"]}
    assert schema["palette"]["type"] == "palette"
    assert schema["beats_per_cycle"] == {
        "key": "beats_per_cycle",
        "label": "Beats per Cycle",
        "bindable": False,
        "type": "number",
        "min": 1.0,
        "max": 4.0,
        "step": 0.5,
    }


def test_setting_schema_types() -> None:
    schema = {entry["key"]: entry for entry in setting_schema("lifx_waveform")}
    assert schema["colour"]["type"] == "colour"
    assert schema["waveform"] == {
        "key": "waveform",
        "label": "Shape",
        "bindable": False,
        "type": "choice",
        "options": ["sine", "triangle", "saw", "half_sine", "pulse"],
    }
    assert {entry["key"]: entry for entry in setting_schema("lifx_move")}["reverse"]["type"] == "boolean"
    assert setting_schema("no_such_effect") == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"name": ""}, "name"),
        ({"category": "party"}, "category"),
        ({"scope": "whole-home"}, "M6"),
        ({"needs": ["weather"]}, "input"),
        ({"layers": [_layer(type="particles", kind="fireflies")]}, "M5"),
        ({"layers": [_layer(settings={"beats_per_cycle": {"value": 2.0, "binding": {}}})]}, "M7"),
        ({"layers": [_layer(mask={"kind": "height"})]}, "M4"),
        ({"layers": [_layer(settings={"beats_per_cycle": 2.0})]}, "value"),
        ({"modifiers": {"trailsS": 0.5, "downbeatFlash": False, "brightnessCap": None, "evening": False}}, "M4"),
        ({"transition": {"kind": "melt", "durationS": 1.0}}, "transition"),
    ],
)
def test_looks_m1_cannot_run_are_refused_with_the_reason(change: dict[str, Any], reason: str) -> None:
    with pytest.raises(LookError, match=reason):
        validate_look(look_from_dict(_look(**change)))


@pytest.mark.parametrize(
    ("layers", "reason"),
    [
        ([], "at least one layer"),
        ([_layer(kind="no_such_effect")], "unknown effect"),
        ([_layer(type="firmware", kind="breathe")], "firmware"),
        ([_layer(kind="lifx_flame", settings={})], "field"),
        ([_layer(settings={"beats_per_cycle": {"value": 99.0}})], "above max"),
        ([_layer(id="a"), _layer(id="b")], "one streamed layer"),
    ],
)
def test_layer_problems_are_refused(layers: list[dict[str, Any]], reason: str) -> None:
    with pytest.raises(LookError, match=reason):
        validate_look(look_from_dict(_look(layers=layers)))


def test_hidden_field_layers_and_firmware_layers_are_fine() -> None:
    look = look_from_dict(
        _look(
            layers=[
                _layer(id="a", visible=False),
                _layer(id="b"),
                _layer(id="c", type="firmware", kind="lifx_flame", settings={}),
                _layer(id="d", type="firmware", kind="openrgb_mode", settings={}),
            ]
        )
    )
    validate_look(look)
    field_layer = visible_field_layer(look)
    assert field_layer is not None and field_layer.id == "b"
    assert [layer.id for layer in firmware_layers(look)] == ["c", "d"]


def test_a_firmware_only_look_has_no_field_layer() -> None:
    look = look_from_dict(_look(layers=[_layer(type="firmware", kind="lifx_flame", settings={})]))
    validate_look(look)
    assert visible_field_layer(look) is None


def test_make_effect_wraps_strip_effects_and_applies_settings() -> None:
    effect = make_effect(Layer(id="l", name="Breathe", type="field", kind="breathe", settings={"beats_per_cycle": 2.0}))
    assert isinstance(effect, StripAdapter)
    assert effect.get_params()["beats_per_cycle"] == 2.0
    flame = make_effect(Layer(id="f", name="Flame", type="firmware", kind="lifx_flame", settings={"period": 3.0}))
    assert isinstance(flame, LifxFlame)
    assert flame.get_params() == {"period": 3.0}


def test_defaults() -> None:
    look = Look(id="x", name="X", category="ambient")
    assert look.modifiers == LookModifiers()
    assert look.transition == Transition()
    assert look.scope == "any-zone"
    assert not look.built_in
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/looks/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.looks'`.

- [ ] **Step 3: Write `src/dj_ledfx/looks/__init__.py`**

```python
"""Looks as data: built-ins, saved looks and the M1 validator (spec §5.2)."""
```

- [ ] **Step 4: Write `src/dj_ledfx/looks/model.py`**

```python
"""The look model, shaped like the web app contract (web spec §12.2; engine spec §5.2).

M1 runs one visible streamed layer plus any number of firmware layers. Everything else
the contract can describe is refused with the milestone that brings it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from dj_ledfx.effects.base import StripEffect
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.registry import get_effect_class
from dj_ledfx.effects.strip_adapter import StripAdapter

LayerType = Literal["field", "particles", "firmware"]
Blend = Literal["add", "screen", "normal", "multiply", "max"]
TransitionKind = Literal["cut", "fade", "wipe", "spread", "dissolve"]
Category = Literal["ambient", "tempo", "audio", "home", "firmware"]
Scope = Literal["any-zone", "whole-home"]
InputKind = Literal["tempo", "music", "home-assistant", "sun"]


class LookError(ValueError):
    """A look that can't be read or can't run in this version, with the reason."""


class LookNotFoundError(KeyError):
    pass


class BuiltInLookError(Exception):
    """Built-in looks are never changed; save an edit as a new look instead."""


@dataclass(frozen=True, slots=True)
class Transition:
    kind: TransitionKind = "cut"
    duration_s: float = 0.0


@dataclass(frozen=True, slots=True)
class LookModifiers:
    trails_s: float | None = None
    downbeat_flash: bool = False
    brightness_cap: float | None = None
    evening: bool = False


@dataclass(frozen=True, slots=True)
class Layer:
    id: str
    name: str
    type: LayerType
    kind: str
    visible: bool = True
    blend: Blend = "normal"
    opacity: float = 1.0
    settings: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Look:
    id: str
    name: str
    category: Category
    description: str = ""
    thumbnail: str = ""
    scope: Scope = "any-zone"
    needs: tuple[InputKind, ...] = ()
    uses: tuple[InputKind, ...] = ()
    layers: tuple[Layer, ...] = ()
    modifiers: LookModifiers = LookModifiers()
    transition: Transition = Transition()
    built_in: bool = False
    derived_from: str | None = None


def _choice(value: Any, allowed: tuple[str, ...], what: str) -> Any:
    if value not in allowed:
        raise LookError(f"Unknown {what} {value!r}; expected one of {', '.join(allowed)}")
    return value


def _float(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LookError(f"{what} must be a number")
    return float(value)


def _inputs(values: Any, what: str) -> tuple[Any, ...]:
    if not isinstance(values, list):
        raise LookError(f"'{what}' must be a list of inputs")
    return tuple(_choice(v, get_args(InputKind), "input") for v in values)


def _layer_from_dict(data: Mapping[str, Any], index: int) -> Layer:
    if not isinstance(data, Mapping):
        raise LookError(f"Layer {index + 1} must be an object")
    layer_type = _choice(data.get("type"), get_args(LayerType), "layer type")
    if layer_type == "particles":
        raise LookError("Particle layers arrive in M5")
    for modifier in ("mask", "mirror", "transform"):
        if data.get(modifier) is not None:
            raise LookError(f"Layer modifiers ({modifier}) arrive in M4")
    raw_settings = data.get("settings") or {}
    if not isinstance(raw_settings, Mapping):
        raise LookError("Layer settings must be an object")
    settings: dict[str, Any] = {}
    for key, setting in raw_settings.items():
        if not isinstance(setting, Mapping) or "value" not in setting:
            raise LookError(f"Setting '{key}' must be an object with a value")
        if setting.get("binding") is not None:
            raise LookError(f"Setting '{key}' is bound to a signal; bindings arrive in M7")
        settings[str(key)] = setting["value"]
    opacity = _float(data.get("opacity", 1.0), "Layer opacity")
    if not 0.0 <= opacity <= 1.0:
        raise LookError("Layer opacity must be between 0 and 1")
    kind = str(data.get("kind") or "")
    return Layer(
        id=str(data.get("id") or f"layer-{index + 1}"),
        name=str(data.get("name") or kind),
        type=layer_type,
        kind=kind,
        visible=bool(data.get("visible", True)),
        blend=_choice(data.get("blend", "normal"), get_args(Blend), "blend mode"),
        opacity=opacity,
        settings=settings,
    )


def look_from_dict(data: Mapping[str, Any]) -> Look:
    """Read a contract-shaped look. `builtIn` and `starred` in the input are ignored."""
    if not isinstance(data, Mapping):
        raise LookError("A look must be an object")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LookError("A look needs a name")
    layers = data.get("layers") or []
    if not isinstance(layers, list):
        raise LookError("'layers' must be a list")
    modifiers = data.get("modifiers") or {}
    transition = data.get("transition") or {}
    if not isinstance(modifiers, Mapping) or not isinstance(transition, Mapping):
        raise LookError("'modifiers' and 'transition' must be objects")
    return Look(
        id=str(data.get("id") or ""),
        name=name.strip(),
        category=_choice(data.get("category"), get_args(Category), "category"),
        description=str(data.get("description") or ""),
        thumbnail=str(data.get("thumbnail") or ""),
        scope=_choice(data.get("scope", "any-zone"), get_args(Scope), "scope"),
        needs=_inputs(data.get("needs", []), "needs"),
        uses=_inputs(data.get("uses", []), "uses"),
        layers=tuple(_layer_from_dict(layer, i) for i, layer in enumerate(layers)),
        modifiers=LookModifiers(
            trails_s=modifiers.get("trailsS"),
            downbeat_flash=bool(modifiers.get("downbeatFlash", False)),
            brightness_cap=modifiers.get("brightnessCap"),
            evening=bool(modifiers.get("evening", False)),
        ),
        transition=Transition(
            kind=_choice(transition.get("kind", "cut"), get_args(TransitionKind), "transition"),
            duration_s=_float(transition.get("durationS", 0.0), "Transition duration"),
        ),
        derived_from=str(data["derivedFrom"]) if data.get("derivedFrom") else None,
    )


def _schema_entry(key: str, param: EffectParam) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "key": key,
        "label": param.label or key.replace("_", " ").capitalize(),
        "bindable": False,  # bindings arrive in M7
    }
    if param.type in ("float", "int"):
        entry.update(
            type="number",
            min=param.min if param.min is not None else 0.0,
            max=param.max if param.max is not None else 1.0,
            step=param.step if param.step is not None else (1 if param.type == "int" else 0.01),
        )
    elif param.type == "color":
        entry["type"] = "colour"
    elif param.type == "color_list":
        entry["type"] = "palette"
    elif param.type == "bool":
        entry["type"] = "boolean"
    else:
        entry.update(type="choice", options=list(param.choices or []))
    return entry


def setting_schema(kind: str) -> list[dict[str, Any]]:
    try:
        params = get_effect_class(kind).parameters()
    except KeyError:
        return []
    return [_schema_entry(key, param) for key, param in params.items()]


def _layer_to_dict(layer: Layer) -> dict[str, Any]:
    return {
        "id": layer.id,
        "name": layer.name,
        "type": layer.type,
        "kind": layer.kind,
        "visible": layer.visible,
        "blend": layer.blend,
        "opacity": layer.opacity,
        "settings": {key: {"value": value} for key, value in layer.settings.items()},
        "schema": setting_schema(layer.kind),
        "mask": None,
        "mirror": None,
        "transform": None,
    }


def look_to_dict(look: Look, *, starred: bool = False) -> dict[str, Any]:
    return {
        "id": look.id,
        "name": look.name,
        "category": look.category,
        "builtIn": look.built_in,
        "derivedFrom": look.derived_from,
        "description": look.description,
        "thumbnail": look.thumbnail,
        "scope": look.scope,
        "needs": list(look.needs),
        "uses": list(look.uses),
        "starred": starred,
        "layers": [_layer_to_dict(layer) for layer in look.layers],
        "modifiers": {
            "trailsS": look.modifiers.trails_s,
            "downbeatFlash": look.modifiers.downbeat_flash,
            "brightnessCap": look.modifiers.brightness_cap,
            "evening": look.modifiers.evening,
        },
        "transition": {"kind": look.transition.kind, "durationS": look.transition.duration_s},
    }


def make_effect(layer: Layer) -> FieldEffect | FirmwareEffect:
    """A fresh effect for the layer with its settings applied. Strip effects come wrapped."""
    try:
        cls = get_effect_class(layer.kind)
    except KeyError:
        raise LookError(f"Layer '{layer.name}' uses an unknown effect '{layer.kind}'") from None
    effect = cls()
    try:
        effect.set_params(**layer.settings)
    except (TypeError, ValueError) as exc:
        raise LookError(f"Layer '{layer.name}': {exc}") from exc
    if layer.type == "firmware":
        if not isinstance(effect, FirmwareEffect):
            raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a firmware effect")
        return effect
    if isinstance(effect, StripEffect):
        return StripAdapter(effect)
    if isinstance(effect, FieldEffect):
        return effect
    raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a field effect")


def visible_field_layer(look: Look) -> Layer | None:
    return next((layer for layer in look.layers if layer.type == "field" and layer.visible), None)


def firmware_layers(look: Look) -> list[Layer]:
    return [layer for layer in look.layers if layer.type == "firmware"]


def validate_look(look: Look) -> None:
    """Raise LookError if M1 can't run the look."""
    if not look.layers:
        raise LookError("A look needs at least one layer")
    if look.scope != "any-zone":
        raise LookError("Home looks (whole-home scope) arrive in M6")
    if look.modifiers != LookModifiers():
        raise LookError("Look modifiers arrive in M4")
    for layer in look.layers:
        make_effect(layer)
    if sum(1 for layer in look.layers if layer.type == "field" and layer.visible) > 1:
        raise LookError("M1 plays one streamed layer; layer blending arrives in M2")
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/looks/test_model.py -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/looks tests/looks
git commit -m "feat(looks): contract-shaped look model with M1 validation"
```

---

### Task 12: Built-in looks

M1's built-ins: the handoff's Firmware showcase (its M1 look, spec §2) and today's six effects as classic looks, so nothing the owner uses today goes away. The showcase keeps the id, name, category, description, thumbnail and scope of its entry in the handoff's `looks.json`, read from a byte-for-byte copy with a test that fails when the copy drifts (CLAUDE.md, "Web App Design"). The classic looks aren't in the handoff, so their names and descriptions are ours. The other 28 handoff looks arrive with the milestones that can render them.

**Files:**
- Create: `src/dj_ledfx/looks/data/looks.json` (byte copy of `docs/design/web-app/looks.json`)
- Create: `src/dj_ledfx/looks/builtin.py`
- Test: `tests/looks/test_builtin.py`

**Interfaces:**
- Consumes: `Look`, `Layer`, `make_effect`, `validate_look`, `visible_field_layer`, `firmware_layers` (Task 11); `get_strip_effect_classes` (Task 3); `build_ledset`, `LedSource` (Task 1).
- Produces:
  - `looks.builtin.FIRMWARE_LOOK_ID = "firmware"`
  - `looks.builtin.CLASSIC_NAMES: dict[str, str]` (effect kind → look name) and `classic_look_id(kind: str) -> str` (`"classic-" + kind.replace("_", "-")`)
  - `looks.builtin.handoff_looks() -> dict[str, dict[str, Any]]` (the vendored `looks.json`, by id)
  - `looks.builtin.builtin_looks() -> tuple[Look, ...]`: the showcase first, then the six classics in `CLASSIC_NAMES` order
  - Showcase layers, bottom to top: `openrgb_mode`, `lifx_waveform`, `lifx_move`, `lifx_flame`, all `type="firmware"` with default settings. Claims go top down (Task 15), so a Candle runs Flame, the Neon Move, bulbs a waveform, the PC a hardware mode, and the Govee lamp gets Flame's streamed copy, as the look's description says.
  - Classic looks: `category="tempo"`, `uses=("tempo",)`, `thumbnail` = the look id, one visible field layer of the effect with its defaults

- [ ] **Step 1: Vendor `looks.json`**

```bash
mkdir -p src/dj_ledfx/looks/data
cp docs/design/web-app/looks.json src/dj_ledfx/looks/data/looks.json
cmp docs/design/web-app/looks.json src/dj_ledfx/looks/data/looks.json && echo same
```

Expected: `same`.

- [ ] **Step 2: Write the failing tests**

`tests/looks/test_builtin.py`:

```python
from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path

import numpy as np
import pytest

from dj_ledfx.effects.context import NO_SIGNALS, RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.ledset import LedSet, LedSource, build_ledset
from dj_ledfx.effects.registry import get_strip_effect_classes
from dj_ledfx.looks.builtin import (
    CLASSIC_NAMES,
    FIRMWARE_LOOK_ID,
    builtin_looks,
    classic_look_id,
    handoff_looks,
)
from dj_ledfx.looks.model import (
    Look,
    firmware_layers,
    make_effect,
    validate_look,
    visible_field_layer,
)
from dj_ledfx.spatial.geometry import MatrixGeometry, StripGeometry, TileLayout
from dj_ledfx.types import FloatRGB

DESIGN = Path(__file__).parents[2] / "docs" / "design" / "web-app"
VENDORED = files("dj_ledfx.looks") / "data" / "looks.json"


def test_vendored_looks_json_is_a_byte_copy_of_the_handoff() -> None:
    vendored = VENDORED.read_bytes()
    assert vendored == (DESIGN / "looks.json").read_bytes()
    pinned = {
        name: digest
        for digest, name in (
            line.split() for line in (DESIGN / "HANDOFF.sha256").read_text().splitlines() if line
        )
    }
    assert hashlib.sha256(vendored).hexdigest() == pinned["looks.json"]


def test_showcase_keeps_the_handoff_metadata() -> None:
    entry = handoff_looks()[FIRMWARE_LOOK_ID]
    showcase = builtin_looks()[0]
    assert showcase.id == entry["id"]
    assert showcase.name == entry["name"]
    assert showcase.category == entry["category"]
    assert showcase.description == entry["description"]
    assert showcase.thumbnail == entry["thumbnail"]
    assert showcase.scope == entry["scope"]
    assert list(showcase.needs) == entry["inputs"]
    assert showcase.built_in


def test_showcase_layers_bottom_to_top() -> None:
    showcase = builtin_looks()[0]
    assert [layer.kind for layer in showcase.layers] == [
        "openrgb_mode",
        "lifx_waveform",
        "lifx_move",
        "lifx_flame",
    ]
    assert all(layer.type == "firmware" for layer in showcase.layers)
    assert visible_field_layer(showcase) is None


def test_classics_cover_the_six_strip_effects() -> None:
    classics = builtin_looks()[1:]
    assert set(CLASSIC_NAMES) == set(get_strip_effect_classes())
    assert [look.id for look in classics] == [classic_look_id(kind) for kind in CLASSIC_NAMES]
    assert classic_look_id("beat_pulse") == "classic-beat-pulse"
    for look in classics:
        layer = visible_field_layer(look)
        assert layer is not None
        assert look.name == CLASSIC_NAMES[layer.kind]
        assert look.category == "tempo"
        assert look.uses == ("tempo",)
        assert look.needs == ()
        assert look.thumbnail == look.id
        assert look.built_in


def test_ids_are_unique_and_every_builtin_validates() -> None:
    looks = builtin_looks()
    assert len({look.id for look in looks}) == len(looks) == 7
    for look in looks:
        validate_look(look)


def _ledset() -> LedSet:
    return build_ledset(
        [
            LedSource("candle", 30, MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 5, 6),))),
            LedSource("bulb", 1),
            LedSource("neon", 12, StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)),
            LedSource("lamp", 20),
        ]
    )


def _frames(look: Look, seed: int) -> list[FloatRGB]:
    """Render the look's streamed layer, or every firmware layer's copy, for 3 s."""
    leds = _ledset()
    field_layer = visible_field_layer(look)
    layers = [field_layer] if field_layer is not None else firmware_layers(look)
    effects = [make_effect(layer) for layer in layers]
    for effect in effects:
        effect.reseed(seed)
    frames: list[FloatRGB] = []
    for step in range(180):
        t = 1000.0 + step / 60
        ctx = RenderContext(
            t=t,
            dt=1 / 60,
            beat_phase=(t * 2.0) % 1.0,
            bar_phase=(t / 2.0) % 1.0,
            bpm=120.0,
            beat_index=0,
            bar_index=0,
            signals=NO_SIGNALS,
        )
        for effect in effects:
            if isinstance(effect, FirmwareEffect):
                frames.append(effect.emulate(ctx, leds))
            else:
                frames.append(effect.render(ctx, leds))
    return frames


@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_every_builtin_is_finite_in_range_and_repeats_with_a_fixed_seed(look: Look) -> None:
    count = _ledset().count
    first = _frames(look, seed=7)
    again = _frames(look, seed=7)
    for frame, repeat in zip(first, again, strict=True):
        assert frame.shape == (count, 3)
        assert frame.dtype == np.float32
        assert np.isfinite(frame).all()
        assert frame.min() >= 0.0 and frame.max() <= 1.0
        assert np.array_equal(frame, repeat)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/looks/test_builtin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.looks.builtin'`.

- [ ] **Step 4: Write `src/dj_ledfx/looks/builtin.py`**

```python
"""Built-in looks (spec §5.2).

The Firmware showcase takes its metadata from the handoff's looks.json (vendored in
data/looks.json, byte for byte). The six classic looks are today's effects; the handoff
has no entry for them, so their names and descriptions live here.
"""

from __future__ import annotations

import functools
import json
from importlib.resources import files
from typing import Any

from dj_ledfx.looks.model import Layer, Look

FIRMWARE_LOOK_ID = "firmware"

# Bottom to top. Claims go top down, so the most specific effect wins each light.
SHOWCASE_LAYERS: tuple[tuple[str, str, str], ...] = (
    ("openrgb", "OpenRGB mode", "openrgb_mode"),
    ("waveform", "LIFX waveform", "lifx_waveform"),
    ("move", "LIFX Move", "lifx_move"),
    ("flame", "LIFX Flame", "lifx_flame"),
)

CLASSIC_NAMES: dict[str, str] = {
    "beat_pulse": "Beat pulse",
    "breathe": "Breathe",
    "color_chase": "Colour chase",
    "fire_storm": "Fire storm",
    "rainbow_wave": "Rainbow wave",
    "strobe": "Strobe",
}


def classic_look_id(kind: str) -> str:
    return "classic-" + kind.replace("_", "-")


@functools.cache
def handoff_looks() -> dict[str, dict[str, Any]]:
    raw = (files("dj_ledfx.looks") / "data" / "looks.json").read_bytes()
    return {str(entry["id"]): entry for entry in json.loads(raw)["looks"]}


def _showcase() -> Look:
    entry = handoff_looks()[FIRMWARE_LOOK_ID]
    return Look(
        id=entry["id"],
        name=entry["name"],
        category=entry["category"],
        description=entry["description"],
        thumbnail=entry["thumbnail"],
        scope=entry["scope"],
        needs=tuple(entry["inputs"]),
        layers=tuple(
            Layer(id=layer_id, name=name, type="firmware", kind=kind)
            for layer_id, name, kind in SHOWCASE_LAYERS
        ),
        built_in=True,
    )


def _classic(kind: str, name: str) -> Look:
    look_id = classic_look_id(kind)
    return Look(
        id=look_id,
        name=name,
        category="tempo",
        description=f"The classic {name.lower()} effect, played along the zone's lights in order.",
        thumbnail=look_id,
        uses=("tempo",),
        layers=(Layer(id="strip", name=name, type="field", kind=kind),),
        built_in=True,
    )


@functools.cache
def builtin_looks() -> tuple[Look, ...]:
    return (_showcase(), *(_classic(kind, name) for kind, name in CLASSIC_NAMES.items()))
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/looks -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/looks/data/looks.json src/dj_ledfx/looks/builtin.py tests/looks/test_builtin.py
git commit -m "feat(looks): Firmware showcase and the six classic looks as built-ins"
```

---

### Task 13: Zones-and-looks schema, StateDB helpers and the look store

Migration 004 adds the tables M1 persists: zones and their members, saved looks, stars, and what each zone runs (spec §7.1: "Each zone's look is saved in `state.db`, with its settings, brightness and start time"). It also clears `device_saved_state`: those rows were taken by the old transport, and after the migration nothing is running, so nothing would ever release them. And it drops the saved `engine.unassigned_device_mode`, which the cut-over (Task 24) removes: lights in no running zone are idle and never changed. `LookStore` serves built-ins and saved looks ("Mine"): built-ins are never changed, saving an edit creates a new look, any look can be starred, and a saved look that no longer loads is skipped with a warning (spec §8: "a bad look, never crashes the app").

**Files:**
- Create: `src/dj_ledfx/persistence/migrations/004_zones_and_looks.sql`
- Modify: `src/dj_ledfx/persistence/state_db.py` (`fetch_all`, `write`, `write_many`, `delete_device_state`)
- Create: `src/dj_ledfx/looks/store.py`
- Test: `tests/persistence/test_zones_and_looks_schema.py`, `tests/looks/test_store.py`
- Modify: `tests/persistence/test_state_db.py`, `tests/persistence/test_device_saved_state.py`, `tests/test_integration.py` (schema version 4)

**Interfaces:**
- Consumes: `Look`, `look_from_dict`, `look_to_dict`, `validate_look`, `LookError`, `LookNotFoundError`, `BuiltInLookError` (Task 11); `builtin_looks` (Task 12).
- Produces:
  - Tables `zones(id, name, kind, all_lights)`, `zone_members(zone_id, device_id, position)`, `looks(id, body, created_at, updated_at)`, `look_stars(look_id)`, `zone_assignments(zone_id, look_id, look, brightness, lights, started_at)`
  - `StateDB.fetch_all(sql, params=()) -> list[tuple[Any, ...]]`, `StateDB.write(sql, params=()) -> None`, `StateDB.write_many(statements: Sequence[tuple[str, tuple[Any, ...]]]) -> None` (one transaction), `StateDB.delete_device_state(stable_id) -> None`
  - `looks.store.look_body(look) -> str` (the JSON saved for a look: its contract shape without `schema` or `starred`)
  - `looks.store.LookStore(db)`: `async load()`, `looks() -> list[Look]` (built-ins first, then saved looks oldest first), `get(look_id) -> Look` (`LookNotFoundError`), `is_starred(look_id) -> bool`, `async create(look) -> Look` (new `mine-<8 hex>` id, `built_in=False`, keeps `derived_from`), `async update(look_id, look) -> Look`, `async delete(look_id)`, `async set_starred(look_id, starred)`; built-ins raise `BuiltInLookError` on update and delete; create and update raise `LookError` for looks M1 can't run

- [ ] **Step 1: Write the failing tests**

`tests/persistence/test_zones_and_looks_schema.py`:

```python
from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


async def test_schema_version_is_4(db: StateDB) -> None:
    assert await db.get_schema_version() == 4


async def test_new_tables_exist(db: StateDB) -> None:
    rows = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    assert {"zones", "zone_members", "looks", "look_stars", "zone_assignments"} <= {
        row[0] for row in rows
    }


async def test_deleting_a_zone_removes_its_members_and_assignment(db: StateDB) -> None:
    await db.write_many(
        [
            ("INSERT INTO zones (id, name) VALUES (?, ?)", ("z1", "Desk")),
            (
                "INSERT INTO zone_members (zone_id, device_id, position) VALUES (?, ?, ?)",
                ("z1", "lifx:aa", 0),
            ),
            (
                "INSERT INTO zone_assignments "
                "(zone_id, look_id, look, brightness, lights, started_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("z1", "firmware", "{}", 1.0, "[]", "2026-09-24T00:00:00+00:00"),
            ),
        ]
    )
    await db.write("DELETE FROM zones WHERE id=?", ("z1",))
    assert await db.fetch_all("SELECT * FROM zone_members") == []
    assert await db.fetch_all("SELECT * FROM zone_assignments") == []


async def test_write_many_is_one_transaction(db: StateDB) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        await db.write_many(
            [
                ("INSERT INTO zones (id, name) VALUES (?, ?)", ("z1", "Desk")),
                ("INSERT INTO zones (id, name) VALUES (?, ?)", ("z1", "Again")),
            ]
        )
    assert await db.fetch_all("SELECT id FROM zones") == []


async def test_delete_device_state(db: StateDB) -> None:
    await db.save_device_state("lifx:aa", b"x")
    await db.delete_device_state("lifx:aa")
    assert await db.load_device_state("lifx:aa") is None


async def test_upgrade_clears_what_the_old_transport_left(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    db = StateDB(path)
    await db.open()
    await db.save_device_state("lifx:aa", b"old")
    await db.save_config_key("engine", "unassigned_device_mode", '"idle"')
    await db.save_config_key("engine", "fps", "60")
    await db.write("UPDATE config SET value='3' WHERE section='_meta' AND key='schema_version'")
    await db.close()

    db = StateDB(path)
    await db.open()
    try:
        assert await db.get_schema_version() == 4
        assert await db.load_all_device_states() == {}
        assert await db.load_config("engine") == {"fps": "60"}
    finally:
        await db.close()
```

`tests/looks/test_store.py`:

```python
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import (
    BuiltInLookError,
    Layer,
    Look,
    LookError,
    LookNotFoundError,
    look_to_dict,
)
from dj_ledfx.looks.store import LookStore
from dj_ledfx.persistence.state_db import StateDB

BUILT_INS = len(builtin_looks())
INSERT_LOOK = "INSERT INTO looks (id, body, created_at, updated_at) VALUES (?, ?, ?, ?)"


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


def _mine(name: str = "My breathe", **settings: Any) -> Look:
    return Look(
        id="",
        name=name,
        category="tempo",
        uses=("tempo",),
        layers=(Layer(id="l1", name="Breathe", type="field", kind="breathe", settings=settings),),
        derived_from="classic-breathe",
    )


async def _loaded(db: StateDB) -> LookStore:
    store = LookStore(db)
    await store.load()
    return store


async def test_builtins_come_first(db: StateDB) -> None:
    store = await _loaded(db)
    await store.create(_mine())
    looks = store.looks()
    assert [look.id for look in looks[:BUILT_INS]] == [look.id for look in builtin_looks()]
    assert looks[BUILT_INS].id.startswith("mine-")


async def test_create_saves_a_new_look_that_survives_a_reload(db: StateDB) -> None:
    store = await _loaded(db)
    saved = await store.create(_mine(beats_per_cycle=2.0))
    assert saved.id.startswith("mine-") and len(saved.id) == len("mine-") + 8
    assert not saved.built_in
    assert saved.derived_from == "classic-breathe"
    assert (await _loaded(db)).get(saved.id) == saved


async def test_create_refuses_a_look_m1_cannot_run(db: StateDB) -> None:
    store = await _loaded(db)
    with pytest.raises(LookError, match="above max"):
        await store.create(_mine(beats_per_cycle=99.0))
    assert len(store.looks()) == BUILT_INS


async def test_update_changes_saved_looks_only(db: StateDB) -> None:
    store = await _loaded(db)
    saved = await store.create(_mine())
    updated = await store.update(saved.id, _mine(name="Slower", beats_per_cycle=4.0))
    assert updated.id == saved.id and updated.name == "Slower"
    assert (await _loaded(db)).get(saved.id).name == "Slower"
    with pytest.raises(BuiltInLookError):
        await store.update("firmware", _mine())
    with pytest.raises(LookNotFoundError):
        await store.update("mine-missing", _mine())


async def test_delete_removes_the_look_and_its_star(db: StateDB) -> None:
    store = await _loaded(db)
    saved = await store.create(_mine())
    await store.set_starred(saved.id, True)
    await store.delete(saved.id)
    with pytest.raises(LookNotFoundError):
        store.get(saved.id)
    assert await db.fetch_all("SELECT look_id FROM look_stars") == []
    with pytest.raises(BuiltInLookError):
        await store.delete("firmware")


async def test_any_look_can_be_starred(db: StateDB) -> None:
    store = await _loaded(db)
    await store.set_starred("firmware", True)
    assert store.is_starred("firmware")
    assert (await _loaded(db)).is_starred("firmware")
    await store.set_starred("firmware", False)
    assert not (await _loaded(db)).is_starred("firmware")
    with pytest.raises(LookNotFoundError):
        await store.set_starred("nope", True)


async def test_load_skips_corrupt_saved_look(db: StateDB) -> None:
    removed_kind = look_to_dict(_mine())
    removed_kind["layers"][0]["kind"] = "retired_effect"
    now = "2026-09-24T00:00:00+00:00"
    await db.write_many(
        [
            (INSERT_LOOK, ("mine-good", json.dumps(look_to_dict(_mine())), now, now)),
            (INSERT_LOOK, ("mine-json", "{not json", now, now)),
            (INSERT_LOOK, ("mine-kind", json.dumps(removed_kind), now, now)),
        ]
    )
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        store = await _loaded(db)
    finally:
        logger.remove(sink)
    assert [look.id for look in store.looks()[BUILT_INS:]] == ["mine-good"]
    assert any("mine-json" in warning for warning in warnings)
    assert any("mine-kind" in w and "retired_effect" in w for w in warnings)
```

In `tests/persistence/test_state_db.py`, rename `test_schema_version_is_3` to `test_schema_version_is_4` and assert `4`; in `test_tables_created` the expected list becomes:

```python
    expected = [
        "config",
        "device_groups",
        "device_saved_state",
        "devices",
        "groups",
        "look_stars",
        "looks",
        "presets",
        "scene_effect_state",
        "scene_placements",
        "scenes",
        "zone_assignments",
        "zone_members",
        "zones",
    ]
```

In `tests/persistence/test_device_saved_state.py`, rename `test_schema_version_is_3_after_migration` to `test_schema_version_is_4_after_migration` and assert `4`. In `tests/test_integration.py` (`test_startup_with_fresh_db`), change `assert version == 3` to `assert version == 4`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/persistence tests/looks/test_store.py -v`
Expected: FAIL: `AttributeError: 'StateDB' object has no attribute 'fetch_all'`, `ModuleNotFoundError: No module named 'dj_ledfx.looks.store'`, and schema version 3 != 4.

- [ ] **Step 3: Write `src/dj_ledfx/persistence/migrations/004_zones_and_looks.sql`**

The migration runner splits on semicolons, so no comment may contain one.

```sql
-- M1: zones, saved looks and what each zone runs

CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'group',
    all_lights INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS zone_members (
    zone_id TEXT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (zone_id, device_id)
);

CREATE TABLE IF NOT EXISTS looks (
    id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS look_stars (
    look_id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS zone_assignments (
    zone_id TEXT PRIMARY KEY REFERENCES zones(id) ON DELETE CASCADE,
    look_id TEXT NOT NULL,
    look TEXT NOT NULL,
    brightness REAL NOT NULL DEFAULT 1.0,
    lights TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL
);

-- Captures taken by the old transport. Nothing runs after this migration, so none would be released.
DELETE FROM device_saved_state;

-- M1 removes this setting: lights in no running zone are never changed.
DELETE FROM config WHERE section = 'engine' AND key = 'unassigned_device_mode'
```

- [ ] **Step 4: Add the helpers to `src/dj_ledfx/persistence/state_db.py`**

Add `from collections.abc import Sequence` to the imports. Add after `_executemany_write`:

```python
    async def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """Run a read query and return every row."""
        return await self._execute_read(sql, params)

    async def write(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Run one write statement and commit it."""
        await self._execute_write(sql, params)

    async def write_many(self, statements: Sequence[tuple[str, tuple[Any, ...]]]) -> None:
        """Run several write statements as one transaction: all of them or none."""

        def _run() -> None:
            assert self._conn is not None
            self._conn.execute("BEGIN")
            try:
                for sql, params in statements:
                    self._conn.execute(sql, params)
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

        async with self._lock:
            await asyncio.to_thread(_run)
```

and after `load_all_device_states`:

```python
    async def delete_device_state(self, stable_id: str) -> None:
        """Forget a device's captured state (it has been restored or released)."""
        await self._execute_write(
            "DELETE FROM device_saved_state WHERE stable_id=?", (stable_id,)
        )
```

- [ ] **Step 5: Write `src/dj_ledfx/looks/store.py`**

```python
"""Built-in and saved looks, and which ones are starred (spec §5.2)."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import (
    BuiltInLookError,
    Look,
    LookNotFoundError,
    look_from_dict,
    look_to_dict,
    validate_look,
)

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB


def _now() -> str:
    return datetime.now(UTC).isoformat()


def look_body(look: Look) -> str:
    """A look as saved in state.db: its contract shape, without schema or star."""
    data = look_to_dict(look)
    data.pop("starred")
    for layer in data["layers"]:
        layer.pop("schema")
    return json.dumps(data)


class LookStore:
    def __init__(self, db: StateDB) -> None:
        self._db = db
        self._builtins: dict[str, Look] = {look.id: look for look in builtin_looks()}
        self._saved: dict[str, Look] = {}
        self._stars: set[str] = set()

    async def load(self) -> None:
        self._saved = {}
        rows = await self._db.fetch_all("SELECT id, body FROM looks ORDER BY created_at, id")
        for look_id, body in rows:
            try:
                look = replace(look_from_dict(json.loads(body)), id=look_id, built_in=False)
                validate_look(look)
            except Exception as exc:  # a bad saved look never stops the app (spec §8)
                logger.warning("Skipping saved look {}: {}", look_id, exc)
                continue
            self._saved[look_id] = look
        stars = await self._db.fetch_all("SELECT look_id FROM look_stars")
        self._stars = {row[0] for row in stars}
        logger.info("Looks: {} built in, {} saved", len(self._builtins), len(self._saved))

    def looks(self) -> list[Look]:
        return [*self._builtins.values(), *self._saved.values()]

    def get(self, look_id: str) -> Look:
        look = self._builtins.get(look_id) or self._saved.get(look_id)
        if look is None:
            raise LookNotFoundError(look_id)
        return look

    def is_starred(self, look_id: str) -> bool:
        return look_id in self._stars

    async def create(self, look: Look) -> Look:
        """Save a look as a new one ("Mine"). Built-ins are never overwritten."""
        saved = replace(look, id=f"mine-{uuid.uuid4().hex[:8]}", built_in=False)
        validate_look(saved)
        now = _now()
        await self._db.write(
            "INSERT INTO looks (id, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (saved.id, look_body(saved), now, now),
        )
        self._saved[saved.id] = saved
        return saved

    async def update(self, look_id: str, look: Look) -> Look:
        self._check_saved(look_id)
        updated = replace(look, id=look_id, built_in=False)
        validate_look(updated)
        await self._db.write(
            "UPDATE looks SET body=?, updated_at=? WHERE id=?",
            (look_body(updated), _now(), look_id),
        )
        self._saved[look_id] = updated
        return updated

    async def delete(self, look_id: str) -> None:
        self._check_saved(look_id)
        await self._db.write_many(
            [
                ("DELETE FROM looks WHERE id=?", (look_id,)),
                ("DELETE FROM look_stars WHERE look_id=?", (look_id,)),
            ]
        )
        del self._saved[look_id]
        self._stars.discard(look_id)

    async def set_starred(self, look_id: str, starred: bool) -> None:
        self.get(look_id)
        if starred:
            await self._db.write(
                "INSERT INTO look_stars (look_id) VALUES (?) ON CONFLICT(look_id) DO NOTHING",
                (look_id,),
            )
            self._stars.add(look_id)
        else:
            await self._db.write("DELETE FROM look_stars WHERE look_id=?", (look_id,))
            self._stars.discard(look_id)

    def _check_saved(self, look_id: str) -> None:
        if look_id in self._builtins:
            raise BuiltInLookError(f"'{look_id}' is built in; save your changes as a new look")
        if look_id not in self._saved:
            raise LookNotFoundError(look_id)
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/persistence tests/looks -v`
Expected: PASS.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/persistence src/dj_ledfx/looks/store.py tests/persistence tests/looks/test_store.py tests/test_integration.py
git commit -m "feat(looks): persist zones, saved looks and stars; add the look store"
```

---

### Task 14: Zone store and the scene migration

Zones and assignments in `state.db`, and the one-off migration of today's scenes (spec §6.5: "each scene becomes a device-group zone, so looks can be assigned before the home map exists"). Nothing is running after the migration: the global transport is gone, so there is nothing to carry over. An assignment also saves the lights the zone owns after take-overs, so a restart gives each zone back exactly the lights it had rather than replaying take-overs from scratch.

Migration rules: a scene with placements becomes a group whose lights are ordered by placement position (x, then y, then z); a scene with no placements becomes a group that follows every light (today's default pipeline caught every unassigned device); with no scenes at all, one "All lights" zone is created. The migration runs once, recorded in `config` as `_meta.scenes_migrated`, so zones deleted later don't come back.

**Files:**
- Create: `src/dj_ledfx/zones/__init__.py`, `src/dj_ledfx/zones/model.py`, `src/dj_ledfx/zones/store.py`
- Test: `tests/zones/__init__.py`, `tests/zones/test_store.py`

**Interfaces:**
- Consumes: `StateDB.fetch_all`, `write`, `write_many`, `upsert_device`, `save_scene`, `save_placement` (Task 13 and existing).
- Produces:
  - `zones.model.ZoneKind = Literal["home", "room", "sub-zone", "group"]`, `ALL_LIGHTS_ZONE_ID = "all-lights"`
  - `zones.model.ZoneRecord(id, name, kind="group", lights: tuple[str, ...] = (), all_lights=False)` (frozen)
  - `zones.model.Assignment(zone_id, look_id, look_json: str, brightness: float, lights: tuple[str, ...], started_at: datetime)` (frozen)
  - `zones.store.new_group_id() -> str` (`group-<8 hex>`)
  - `zones.store.ZoneStore(db)`: `async load_zones() -> list[ZoneRecord]`, `async save_zone(zone)`, `async delete_zone(zone_id)`, `async load_assignments() -> list[Assignment]` (oldest first), `async save_assignment(assignment)`, `async delete_assignment(zone_id)`, `async migrate_scenes_once() -> None`

- [ ] **Step 1: Write the failing tests**

`tests/zones/__init__.py` is empty. `tests/zones/test_store.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.model import ALL_LIGHTS_ZONE_ID, Assignment, ZoneRecord
from dj_ledfx.zones.store import ZoneStore, new_group_id


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


async def test_zones_keep_their_light_order(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="desk", name="Office desk", lights=("c", "a", "b")))
    await store.save_zone(ZoneRecord(id="all", name="Everything", all_lights=True))
    assert await store.load_zones() == [
        ZoneRecord(id="desk", name="Office desk", lights=("c", "a", "b")),
        ZoneRecord(id="all", name="Everything", all_lights=True),
    ]


async def test_saving_a_zone_replaces_its_lights(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="desk", name="Desk", lights=("a", "b")))
    await store.save_zone(ZoneRecord(id="desk", name="Desk 2", lights=("b",)))
    assert await store.load_zones() == [ZoneRecord(id="desk", name="Desk 2", lights=("b",))]


async def test_assignments_round_trip_oldest_first(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="a", name="A", lights=("x",)))
    await store.save_zone(ZoneRecord(id="b", name="B", lights=("y",)))
    newer = Assignment("a", "firmware", "{}", 0.5, ("x",), datetime(2026, 9, 24, 20, tzinfo=UTC))
    older = Assignment("b", "classic-breathe", "{}", 1.0, ("y",), datetime(2026, 9, 24, 19, tzinfo=UTC))
    await store.save_assignment(newer)
    await store.save_assignment(older)
    assert await store.load_assignments() == [older, newer]

    await store.save_assignment(Assignment("a", "firmware", "{}", 0.25, (), newer.started_at))
    await store.delete_assignment("b")
    assert [(a.zone_id, a.brightness) for a in await store.load_assignments()] == [("a", 0.25)]

    await store.delete_zone("a")
    assert await store.load_assignments() == []
    assert [zone.id for zone in await store.load_zones()] == ["b"]


async def test_scenes_become_device_group_zones_once(db: StateDB) -> None:
    for device_id in ("lifx:a", "lifx:b", "lifx:c"):
        await db.upsert_device({"id": device_id, "name": device_id, "backend": "lifx"})
    await db.save_scene({"id": "s1", "name": "Desk", "is_active": 1})
    await db.save_scene({"id": "s2", "name": "Default"})
    await db.save_placement({"scene_id": "s1", "device_id": "lifx:b", "position_x": 2.0})
    await db.save_placement({"scene_id": "s1", "device_id": "lifx:a", "position_x": 1.0})
    await db.save_placement(
        {"scene_id": "s1", "device_id": "lifx:c", "position_x": 1.0, "position_y": 1.0}
    )
    store = ZoneStore(db)

    await store.migrate_scenes_once()

    zones = await store.load_zones()
    assert [(z.name, z.kind, z.lights, z.all_lights) for z in zones] == [
        ("Desk", "group", ("lifx:a", "lifx:c", "lifx:b"), False),
        ("Default", "group", (), True),
    ]
    assert all(zone.id.startswith("group-") for zone in zones)
    assert await store.load_assignments() == []  # nothing runs after the migration

    await store.delete_zone(zones[0].id)
    await store.migrate_scenes_once()
    assert [z.name for z in await store.load_zones()] == ["Default"]


async def test_no_scenes_gives_one_all_lights_zone(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.migrate_scenes_once()
    assert await store.load_zones() == [
        ZoneRecord(id=ALL_LIGHTS_ZONE_ID, name="All lights", all_lights=True)
    ]


def test_group_ids() -> None:
    first, second = new_group_id(), new_group_id()
    assert first.startswith("group-") and len(first) == len("group-") + 8
    assert first != second
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/zones/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.zones'`.

- [ ] **Step 3: Write `src/dj_ledfx/zones/__init__.py` and `src/dj_ledfx/zones/model.py`**

`src/dj_ledfx/zones/__init__.py`:

```python
"""Zones: which lights a look runs on, and the runtime that renders it (spec §4.3)."""
```

`src/dj_ledfx/zones/model.py`:

```python
"""Zones and what runs on them (engine spec §4.3; web spec §12.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ZoneKind = Literal["home", "room", "sub-zone", "group"]

ALL_LIGHTS_ZONE_ID = "all-lights"


@dataclass(frozen=True, slots=True)
class ZoneRecord:
    id: str
    name: str
    kind: ZoneKind = "group"
    lights: tuple[str, ...] = ()  # stable ids, in LED order
    all_lights: bool = False  # follows every known light, in discovery order


@dataclass(frozen=True, slots=True)
class Assignment:
    """What a running zone runs, as saved in state.db (spec §7.1)."""

    zone_id: str
    look_id: str
    look_json: str  # the contract-shaped look as it was started
    brightness: float
    lights: tuple[str, ...]  # the lights the zone owns after take-overs
    started_at: datetime
```

- [ ] **Step 4: Write `src/dj_ledfx/zones/store.py`**

```python
"""Zones and assignments in state.db, and the one-off scene migration (spec §6.5, §7.1)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from dj_ledfx.zones.model import ALL_LIGHTS_ZONE_ID, Assignment, ZoneKind, ZoneRecord

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB

Statement = tuple[str, tuple[Any, ...]]

_MIGRATED_KEY = "scenes_migrated"


def new_group_id() -> str:
    return f"group-{uuid.uuid4().hex[:8]}"


def _lights(text: str, zone_id: str) -> tuple[str, ...]:
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        logger.warning("Zone {}: saved lights are unreadable; using the zone's lights", zone_id)
        return ()
    return tuple(value)


def _time(text: str, zone_id: str) -> datetime:
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        logger.warning("Zone {}: unreadable start time {!r}; using now", zone_id, text)
        return datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class ZoneStore:
    def __init__(self, db: StateDB) -> None:
        self._db = db

    async def load_zones(self) -> list[ZoneRecord]:
        zones = await self._db.fetch_all(
            "SELECT id, name, kind, all_lights FROM zones ORDER BY rowid"
        )
        members = await self._db.fetch_all(
            "SELECT zone_id, device_id FROM zone_members ORDER BY zone_id, position"
        )
        lights: dict[str, list[str]] = {}
        for zone_id, device_id in members:
            lights.setdefault(zone_id, []).append(device_id)
        return [
            ZoneRecord(
                id=zone_id,
                name=name,
                kind=cast(ZoneKind, kind),
                lights=tuple(lights.get(zone_id, ())),
                all_lights=bool(all_lights),
            )
            for zone_id, name, kind, all_lights in zones
        ]

    async def save_zone(self, zone: ZoneRecord) -> None:
        await self._db.write_many(self._zone_statements(zone))

    async def delete_zone(self, zone_id: str) -> None:
        """Delete a zone; its members and assignment go with it (FK cascade)."""
        await self._db.write("DELETE FROM zones WHERE id=?", (zone_id,))

    async def load_assignments(self) -> list[Assignment]:
        """Every saved assignment, oldest first, so resuming replays take-overs in order."""
        rows = await self._db.fetch_all(
            "SELECT zone_id, look_id, look, brightness, lights, started_at FROM zone_assignments"
        )
        assignments = [
            Assignment(
                zone_id=zone_id,
                look_id=look_id,
                look_json=look_json,
                brightness=float(brightness),
                lights=_lights(lights_json, zone_id),
                started_at=_time(started_at, zone_id),
            )
            for zone_id, look_id, look_json, brightness, lights_json, started_at in rows
        ]
        return sorted(assignments, key=lambda a: (a.started_at, a.zone_id))

    async def save_assignment(self, assignment: Assignment) -> None:
        await self._db.write(
            "INSERT INTO zone_assignments "
            "(zone_id, look_id, look, brightness, lights, started_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(zone_id) DO UPDATE SET look_id=excluded.look_id, look=excluded.look, "
            "brightness=excluded.brightness, lights=excluded.lights, "
            "started_at=excluded.started_at",
            (
                assignment.zone_id,
                assignment.look_id,
                assignment.look_json,
                assignment.brightness,
                json.dumps(list(assignment.lights)),
                assignment.started_at.isoformat(),
            ),
        )

    async def delete_assignment(self, zone_id: str) -> None:
        await self._db.write("DELETE FROM zone_assignments WHERE zone_id=?", (zone_id,))

    async def migrate_scenes_once(self) -> None:
        """Turn each scene into a device-group zone, once (spec §6.5). Nothing runs after."""
        done = await self._db.fetch_all(
            "SELECT 1 FROM config WHERE section='_meta' AND key=?", (_MIGRATED_KEY,)
        )
        if done:
            return
        scenes = await self._db.fetch_all("SELECT id, name FROM scenes ORDER BY rowid")
        placements = await self._db.fetch_all(
            "SELECT scene_id, device_id, position_x, position_y, position_z FROM scene_placements"
        )
        by_scene: dict[str, list[tuple[float, float, float, str]]] = {}
        for scene_id, device_id, x, y, z in placements:
            by_scene.setdefault(scene_id, []).append((x, y, z, device_id))
        zones = [
            ZoneRecord(
                id=new_group_id(),
                name=name,
                lights=tuple(device for *_, device in sorted(by_scene.get(scene_id, []))),
                all_lights=not by_scene.get(scene_id),
            )
            for scene_id, name in scenes
        ]
        if not zones:
            zones = [ZoneRecord(id=ALL_LIGHTS_ZONE_ID, name="All lights", all_lights=True)]
        statements = [statement for zone in zones for statement in self._zone_statements(zone)]
        statements.append(
            (
                "INSERT INTO config (section, key, value) VALUES ('_meta', ?, '1') "
                "ON CONFLICT(section, key) DO UPDATE SET value=excluded.value",
                (_MIGRATED_KEY,),
            )
        )
        await self._db.write_many(statements)
        logger.info("Migrated {} scene(s) to {} zone(s)", len(scenes), len(zones))

    @staticmethod
    def _zone_statements(zone: ZoneRecord) -> list[Statement]:
        statements: list[Statement] = [
            (
                "INSERT INTO zones (id, name, kind, all_lights) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                "all_lights=excluded.all_lights",
                (zone.id, zone.name, zone.kind, int(zone.all_lights)),
            ),
            ("DELETE FROM zone_members WHERE zone_id=?", (zone.id,)),
        ]
        statements += [
            (
                "INSERT INTO zone_members (zone_id, device_id, position) VALUES (?, ?, ?)",
                (zone.id, device_id, position),
            )
            for position, device_id in enumerate(zone.lights)
        ]
        return statements
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/zones/test_store.py -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones tests/zones
git commit -m "feat(zones): zone store, assignments and the one-off scene migration"
```

---

### Task 15: Zone runtime and device routes

A `ZoneRuntime` is one running zone (spec §4.1): its compiled look, its `LedSet`, and its own ring buffer of float-RGB frames rendered for `now + horizon`. It decides which lights run a firmware layer themselves (claims) and which get a streamed copy, holds the last good frame when the look raises or produces NaN, drops its frame rate when it keeps exceeding the 5 ms budget, and reports running, slow, crashed or waiting (spec §8). A `DeviceRoute` tells the scheduler where one device's frames come from: its zone's ring and its slice, converted from float to 8-bit once, at send.

Claim rules (M1 has no `device_set` settings, so a firmware layer targets every light in the zone): going down from the top layer, the first firmware layer that supports a light claims it and the light runs the effect itself. A light no firmware layer supports shows the look's streamed layer, or, in a look with no streamed layer, the top firmware layer's streamed copy. A light that rejects its effect gets that layer's streamed copy. A waiting look claims nothing and renders dark.

**Files:**
- Modify: `src/dj_ledfx/types.py` (`RenderedFrame.colors` holds float frames too)
- Modify: `src/dj_ledfx/zones/model.py` (`CrashInfo`)
- Create: `src/dj_ledfx/scheduling/route.py`
- Create: `src/dj_ledfx/zones/runtime.py`
- Modify: `tests/conftest.py` (`GlowFirmware`)
- Modify: `pyproject.toml` (the `perf` marker)
- Test: `tests/scheduling/test_route.py`, `tests/zones/test_runtime.py`, `tests/zones/test_runtime_perf.py`

**Interfaces:**
- Consumes: `RenderContext`, `render_context`, `LedSet`, `LedSource`, `DeviceSlice`, `build_ledset` (Task 1); `DeviceCapabilities` (Task 2); `FieldEffect`, `FirmwareEffect` (Task 3); `Look`, `Layer`, `LookError`, `make_effect`, `visible_field_layer`, `firmware_layers` (Task 11); `builtin_looks` (Task 12); `RingBuffer`, `RenderedFrame`; `BeatClock`.
- Produces:
  - `zones.model.CrashInfo(layer: str, message: str, at: datetime)` (frozen)
  - `scheduling.route.to_device_colors(colors: FloatRGB, led_count: int) -> NDArray[np.uint8]`
  - `scheduling.route.DeviceRoute(zone_id, ring, start, stop, streaming)` (frozen) with `.colors_at(target_time, led_count) -> NDArray[np.uint8] | None`
  - `zones.runtime.ZoneLight(device_id, led_count, caps, geometry=None)` (frozen)
  - `zones.runtime.ZoneState = Literal["running", "slow", "crashed", "waiting"]`, `LightMode = Literal["streaming", "own-effect", "streamed-copy"]`
  - `zones.runtime.ZoneRuntime(zone_id, look, lights, *, clock, latency_s: Callable[[str], float], fps=60, max_lookahead_s=1.0, brightness=1.0, seed=0, timer=time.perf_counter, now=<utc now>)` with attributes `zone_id`, `look`, `brightness`, `generation` (moves on whenever firmware lights need their effect sent again), `crash: CrashInfo | None`, `slow_since: datetime | None`, `ring`, `leds`; properties `lights`, `field_effect`, `waiting_for`, `state`, `fps_actual`, `fps_target`, `horizon_s`; methods `tick(now)`, `set_lights(lights)`, `set_brightness(value)`, `update_look(look)`, `restart()`, `mark_emulated(device_id)`, `claim_for(device_id) -> tuple[Layer, FirmwareEffect] | None`, `mode_of(device_id) -> LightMode`, `effect_name(device_id) -> str | None`, `route_for(device_id) -> DeviceRoute | None`
  - `tests/conftest.py`: `GlowFirmware` (registered as `glow_firmware`, `display_name = "Glow"`, one `level` setting): runs on `FakeLight`s whose capabilities have `matrix=True`, records `("firmware", params)`, raises `FirmwareRejected` when `reject_firmware` is set, and emulates as flat grey at `level`

- [ ] **Step 1: Add the `perf` marker to `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["tests"]
markers = ["perf: frame-budget benchmarks, run locally with `uv run pytest -m perf`"]
addopts = "-m 'not perf'"
```

(A later `-m` on the command line replaces the one in `addopts`, so `uv run pytest -m perf` runs only the benchmarks.)

- [ ] **Step 2: Add `GlowFirmware` to `tests/conftest.py`**

Add `FirmwareRejected` to the existing `dj_ledfx.devices.capabilities` import, and these imports at the top:

```python
from typing import Any, cast

from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import FloatRGB
```

and append after `FakeLight`:

```python
class GlowFirmware(FirmwareEffect):
    """A firmware effect for FakeLights whose capabilities have matrix=True."""

    display_name = "Glow"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"level": EffectParam(type="float", default=0.5, min=0.0, max=1.0)}

    def __init__(self, level: float = 0.5) -> None:
        self.level = level

    def get_params(self) -> dict[str, Any]:
        return {"level": self.level}

    def _apply_params(self, **kwargs: Any) -> None:
        self.level = float(kwargs.get("level", self.level))

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.matrix

    # cast, not isinstance: pytest imports this file twice (as tests.conftest and as
    # conftest), so a FakeLight may come from either copy.
    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        light = cast(FakeLight, adapter)
        if light.reject_firmware:
            raise FirmwareRejected(f"{light.name} refused Glow")
        light.calls.append(("firmware", dict(params)))
        light.firmware_running = True

    async def stop(self, adapter: DeviceAdapter) -> None:
        light = cast(FakeLight, adapter)
        light.calls.append(("firmware_stop", None))
        light.firmware_running = False

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        return cast(FakeLight, adapter).firmware_running

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return np.full((leds.count, 3), self.level, dtype=np.float32)
```

- [ ] **Step 3: Write the failing tests**

`tests/scheduling/test_route.py`:

```python
from __future__ import annotations

import numpy as np

from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.scheduling.route import DeviceRoute, to_device_colors
from dj_ledfx.types import RenderedFrame


def _frame(colors: np.ndarray, t: float) -> RenderedFrame:
    return RenderedFrame(colors=colors, target_time=t, beat_phase=0.0, bar_phase=0.0)


def test_to_device_colors_clamps_rounds_and_fits_the_device() -> None:
    colors = np.array([[-0.5, 0.5, 1.5], [0.2, 0.2, 0.2]], dtype=np.float32)
    out = to_device_colors(colors, 3)
    assert out.dtype == np.uint8
    assert out.tolist() == [[0, 128, 255], [51, 51, 51], [0, 0, 0]]
    assert to_device_colors(colors, 1).tolist() == [[0, 128, 255]]


def test_a_route_reads_its_slice_of_the_nearest_frame() -> None:
    ring = RingBuffer(capacity=4, led_count=5)
    colors = np.linspace(0.0, 1.0, 15, dtype=np.float32).reshape(5, 3)
    ring.write(_frame(colors, 10.0))
    ring.write(_frame(np.zeros((5, 3), dtype=np.float32), 11.0))
    route = DeviceRoute(zone_id="z", ring=ring, start=1, stop=3, streaming=True)
    out = route.colors_at(10.1, 2)
    assert out is not None
    assert out.tolist() == to_device_colors(colors[1:3], 2).tolist()


def test_a_route_never_reads_past_the_end_of_a_frame() -> None:
    ring = RingBuffer(capacity=4, led_count=2)
    ring.write(_frame(np.zeros((2, 3), dtype=np.float32), 1.0))
    too_long = DeviceRoute(zone_id="z", ring=ring, start=1, stop=3, streaming=True)
    assert too_long.colors_at(1.0, 2) is None
    empty = DeviceRoute(zone_id="z", ring=RingBuffer(4, 2), start=0, stop=2, streaming=True)
    assert empty.colors_at(1.0, 2) is None
```

`tests/zones/test_runtime.py`:

```python
from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import Any, ClassVar

import numpy as np
import pytest
from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime

TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
BULB = DeviceCapabilities(protocol="LIFX")
LAMP = DeviceCapabilities(protocol="Govee")
LIGHTS = (ZoneLight("tile", 4, TILE), ZoneLight("bulb", 1, BULB), ZoneLight("lamp", 3, LAMP))


class FlatField(FieldEffect):
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


@pytest.fixture(autouse=True)
def _reset_flat_field() -> Iterator[None]:
    FlatField.mode = "ok"
    yield
    FlatField.mode = "ok"


def _field(level: float = 0.5, opacity: float = 1.0) -> Layer:
    return Layer(
        id="field",
        name="Flat",
        type="field",
        kind="flat_field",
        opacity=opacity,
        settings={"level": level},
    )


def _glow(level: float = 0.5) -> Layer:
    return Layer(id="glow", name="Glow", type="firmware", kind="glow_firmware", settings={"level": level})


def _look(*layers: Layer, needs: tuple[Any, ...] = ()) -> Look:
    return Look(id="test", name="Test", category="ambient", layers=layers, needs=needs)


def _runtime(
    look: Look,
    lights: Sequence[ZoneLight] = LIGHTS,
    latencies: dict[str, float] | None = None,
    **kwargs: Any,
) -> ZoneRuntime:
    known = latencies or {}
    return ZoneRuntime(
        "zone",
        look,
        lights,
        clock=BeatClock(),
        latency_s=lambda device_id: known.get(device_id, 0.02),
        **kwargs,
    )


def _latest(runtime: ZoneRuntime) -> np.ndarray:
    frame = runtime.ring.find_nearest(1e9)
    assert frame is not None
    return frame.colors


def test_firmware_runs_where_supported_and_the_field_plays_elsewhere() -> None:
    runtime = _runtime(_look(_field(), _glow()))
    claim = runtime.claim_for("tile")
    assert claim is not None and claim[1].display_name == "Glow"
    assert runtime.mode_of("tile") == "own-effect"
    assert runtime.mode_of("bulb") == runtime.mode_of("lamp") == "streaming"
    tile, bulb = runtime.route_for("tile"), runtime.route_for("bulb")
    assert tile is not None and not tile.streaming
    assert bulb is not None and bulb.streaming and (bulb.start, bulb.stop) == (4, 5)


def test_a_firmware_only_look_streams_its_copy_to_lights_that_cannot_run_it() -> None:
    runtime = _runtime(_look(_glow(level=0.4)), brightness=0.5)
    assert runtime.mode_of("lamp") == "streamed-copy"
    assert runtime.effect_name("lamp") == "Glow"
    runtime.tick(100.0)
    assert np.allclose(_latest(runtime), 0.2)  # the copy everywhere, at half brightness


def test_the_top_firmware_layer_claims_first() -> None:
    flame = Layer(id="flame", name="Flame", type="firmware", kind="lifx_flame")
    runtime = _runtime(_look(_glow(), flame))
    claim = runtime.claim_for("tile")
    assert claim is not None and claim[1].display_name == "LIFX Flame"
    assert runtime.effect_name("lamp") == "LIFX Flame"  # the copy comes from the top layer


def test_a_rejected_firmware_effect_falls_back_to_its_streamed_copy() -> None:
    runtime = _runtime(_look(_field(), _glow()))
    runtime.mark_emulated("tile")
    assert runtime.claim_for("tile") is None
    assert runtime.mode_of("tile") == "streamed-copy"
    route = runtime.route_for("tile")
    assert route is not None and route.streaming


def test_frames_are_rendered_for_now_plus_the_horizon() -> None:
    runtime = _runtime(_look(_field()), latencies={"lamp": 0.1})
    runtime.tick(100.0)
    frame = runtime.ring.find_nearest(100.0)
    assert frame is not None
    assert frame.target_time == pytest.approx(100.0 + 0.1 + 1 / 60)
    assert frame.colors.dtype == np.float32 and frame.colors.shape == (8, 3)


def test_the_horizon_is_capped_by_the_lookahead() -> None:
    runtime = _runtime(_look(_field()), latencies={"lamp": 5.0}, max_lookahead_s=1.0)
    assert runtime.horizon_s == 1.0


def test_brightness_and_opacity_scale_the_frame() -> None:
    runtime = _runtime(_look(_field(level=0.8, opacity=0.5)), brightness=0.5)
    runtime.tick(100.0)
    assert np.allclose(_latest(runtime), 0.2)


def test_a_crash_holds_the_last_good_frame_and_is_logged_once() -> None:
    runtime = _runtime(_look(_field()))
    runtime.tick(100.0)
    errors: list[str] = []
    sink = logger.add(lambda message: errors.append(str(message)), level="ERROR")
    try:
        FlatField.mode = "raise"
        runtime.tick(100.1)
        runtime.tick(100.2)
        assert runtime.state == "crashed"
        assert runtime.crash is not None
        assert (runtime.crash.layer, runtime.crash.message) == ("Flat", "RuntimeError: boom")
        assert runtime.ring.count == 1  # the last good frame is still there
        runtime.restart()
        assert runtime.state == "running"
        runtime.tick(100.3)  # still raising: crashes again, without logging again
        assert runtime.state == "crashed"
    finally:
        logger.remove(sink)
    assert len(errors) == 1

    FlatField.mode = "ok"
    runtime.restart()
    runtime.tick(100.4)
    assert runtime.state == "running" and runtime.ring.count == 2


def test_nan_is_a_crash() -> None:
    runtime = _runtime(_look(_field()))
    FlatField.mode = "nan"
    runtime.tick(100.0)
    assert runtime.crash is not None and "NaN" in runtime.crash.message
    assert runtime.ring.count == 0


def test_a_look_that_cannot_be_built_is_crashed_from_the_start() -> None:
    runtime = _runtime(_look(Layer(id="x", name="Retired", type="field", kind="retired_effect")))
    assert runtime.state == "crashed"
    assert runtime.crash is not None and runtime.crash.layer == "Retired"
    runtime.tick(100.0)
    assert runtime.ring.count == 0


def test_a_slow_zone_drops_its_frame_rate_and_shows_slow_after_30_s() -> None:
    timer = itertools.count(0.0, 0.006).__next__  # every render "takes" 6 ms
    runtime = _runtime(_look(_field()), timer=timer)
    now = 100.0
    for _ in range(29 * 60):
        runtime.tick(now)
        now += 1 / 60
    assert runtime.fps_actual == pytest.approx(30, abs=1)
    assert runtime.state == "running"
    for _ in range(2 * 60):
        runtime.tick(now)
        now += 1 / 60
    assert runtime.state == "slow"
    assert runtime.slow_since is not None


def test_a_waiting_look_renders_dark_and_claims_nothing() -> None:
    runtime = _runtime(_look(_field(), _glow(), needs=("music",)))
    assert runtime.state == "waiting"
    assert runtime.waiting_for == ("music",)
    assert runtime.claim_for("tile") is None
    runtime.tick(100.0)
    assert not _latest(runtime).any()


def test_new_lights_rebuild_the_led_set_and_start_a_fresh_ring() -> None:
    runtime = _runtime(_look(_field()))
    runtime.tick(100.0)
    old_ring = runtime.ring
    runtime.set_lights([ZoneLight("tile", 64, TILE), ZoneLight("lamp", 3, LAMP)])
    assert runtime.ring is not old_ring and runtime.ring.count == 0
    assert runtime.leds.count == 67
    assert runtime.route_for("bulb") is None
    route = runtime.route_for("lamp")
    assert route is not None and (route.start, route.stop) == (64, 67)


def test_update_look_keeps_the_effect_when_the_layers_match() -> None:
    runtime = _runtime(_look(_field(0.5), _glow(level=0.5)))
    effect = runtime.field_effect
    generation = runtime.generation
    runtime.update_look(_look(_field(0.7), _glow(level=0.5)))
    assert runtime.field_effect is effect
    assert effect is not None and effect.get_params() == {"level": 0.7}
    assert runtime.generation == generation  # the firmware layer didn't change
    runtime.update_look(_look(_field(0.7), _glow(level=0.9)))
    assert runtime.generation == generation + 1  # firmware lights get the new settings
    runtime.update_look(_look(_glow(level=0.9)))
    assert runtime.field_effect is None and runtime.generation == generation + 2


def test_brightness_resends_firmware_only_when_lights_run_it() -> None:
    streamed = _runtime(_look(_field()))
    generation = streamed.generation
    streamed.set_brightness(0.3)
    assert streamed.brightness == 0.3 and streamed.generation == generation
    firmware = _runtime(_look(_field(), _glow()))
    generation = firmware.generation
    firmware.set_brightness(0.3)
    assert firmware.generation == generation + 1
```

`tests/zones/test_runtime_perf.py`:

```python
"""Spec §9: each zone renders in under 5 ms on this home's 412 LEDs. Run with -m perf."""

from __future__ import annotations

import statistics
import time

import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.looks.model import Look
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime

pytestmark = pytest.mark.perf

CANDLE = DeviceCapabilities(protocol="LIFX", matrix=True, chain=True)
NEON = DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True)
BULB = DeviceCapabilities(protocol="LIFX")
LAMP = DeviceCapabilities(protocol="Govee")
PC = DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("Direct", "Rainbow Wave"))

HOME = [
    *[(30, CANDLE)] * 3,
    (52, CANDLE),
    *[(1, BULB)] * 9,
    (65, NEON),
    (20, LAMP),
    *[(10, PC)] * 4,
    (1, PC),
    (1, PC),
    (112, PC),
    (1, PC),
    (13, PC),
    (8, PC),
]


@pytest.mark.parametrize("look", builtin_looks(), ids=lambda look: look.id)
def test_a_zone_frame_renders_in_under_5_ms(look: Look) -> None:
    lights = [ZoneLight(f"light-{i}", count, caps) for i, (count, caps) in enumerate(HOME)]
    assert sum(light.led_count for light in lights) == 412
    runtime = ZoneRuntime("home", look, lights, clock=BeatClock(), latency_s=lambda _: 0.05)
    durations = []
    for step in range(240):
        started = time.perf_counter()
        runtime.tick(1000.0 + step / 60)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < 0.005
```

- [ ] **Step 4: Run the tests to see them fail**

Run: `uv run pytest tests/scheduling/test_route.py tests/zones/test_runtime.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.scheduling.route'`.

- [ ] **Step 5: Let `RenderedFrame` carry float frames**

In `src/dj_ledfx/types.py`, add `Any` to the imports (`from typing import Any`) and change the field:

```python
@dataclass(slots=True)
class RenderedFrame:
    # uint8 from the legacy scene pipelines, float32 (FloatRGB) from zone runtimes, until
    # the cut-over (Task 24) makes every frame FloatRGB.
    colors: NDArray[Any]  # shape (n_leds, 3)
    target_time: float  # monotonic time when this should be displayed
    beat_phase: float
    bar_phase: float
```

- [ ] **Step 6: Add `CrashInfo` to `src/dj_ledfx/zones/model.py`**

```python
@dataclass(frozen=True, slots=True)
class CrashInfo:
    """Why a zone's look stopped rendering (spec §8)."""

    layer: str  # the failing layer's name
    message: str
    at: datetime
```

- [ ] **Step 7: Write `src/dj_ledfx/scheduling/route.py`**

```python
"""Where a device's frames come from: its zone's ring buffer and its slice (spec §4.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.types import FloatRGB


def to_device_colors(colors: FloatRGB, led_count: int) -> NDArray[np.uint8]:
    """Clamp float RGB and convert it to 8 bits: the one conversion, at send."""
    out = np.zeros((led_count, 3), dtype=np.uint8)
    count = min(led_count, colors.shape[0])
    scaled = np.clip(colors[:count], 0.0, 1.0) * np.float32(255.0) + np.float32(0.5)
    out[:count] = scaled.astype(np.uint8)
    return out


@dataclass(frozen=True, slots=True)
class DeviceRoute:
    zone_id: str
    ring: RingBuffer
    start: int
    stop: int
    streaming: bool  # False while the light runs a firmware layer itself

    def colors_at(self, target_time: float, led_count: int) -> NDArray[np.uint8] | None:
        """This device's slice of the zone frame nearest target_time, or None."""
        frame = self.ring.find_nearest(target_time)
        if frame is None or frame.colors.shape[0] < self.stop:
            return None
        return to_device_colors(frame.colors[self.start : self.stop], led_count)
```

- [ ] **Step 8: Write `src/dj_ledfx/zones/runtime.py`**

```python
"""One running zone: its look, its LEDs and the frames it renders ahead (spec §4.1, §8)."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import numpy as np
from loguru import logger

from dj_ledfx.effects.context import render_context
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.ledset import DeviceSlice, LedSource, build_ledset
from dj_ledfx.looks.model import (
    Layer,
    Look,
    LookError,
    firmware_layers,
    make_effect,
    visible_field_layer,
)
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.model import CrashInfo

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.devices.capabilities import DeviceCapabilities
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.field import FieldEffect
    from dj_ledfx.spatial.geometry import DeviceGeometry
    from dj_ledfx.types import FloatRGB

FRAME_BUDGET_S = 0.005
SLOW_RATIO = 0.8
SLOW_AFTER_S = 30.0
CRASH_LOG_INTERVAL_S = 60.0
ALWAYS_AVAILABLE = frozenset({"tempo"})  # the internal clock at worst (spec §5.2)

ZoneState = Literal["running", "slow", "crashed", "waiting"]
LightMode = Literal["streaming", "own-effect", "streamed-copy"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _finite(colors: FloatRGB) -> FloatRGB:
    if not np.isfinite(colors).all():
        raise FloatingPointError("the layer produced NaN or infinite colours")
    return colors


def _layout(look: Look) -> list[tuple[str, str, str, bool]]:
    return [(layer.id, layer.type, layer.kind, layer.visible) for layer in look.layers]


@dataclass(frozen=True, slots=True)
class ZoneLight:
    """One light as its zone sees it."""

    device_id: str
    led_count: int
    caps: DeviceCapabilities
    geometry: DeviceGeometry | None = None


class ZoneRuntime:
    """Renders one running zone's look ahead of time into its own ring buffer."""

    def __init__(
        self,
        zone_id: str,
        look: Look,
        lights: Sequence[ZoneLight],
        *,
        clock: BeatClock,
        latency_s: Callable[[str], float],
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        brightness: float = 1.0,
        seed: int = 0,
        timer: Callable[[], float] = time.perf_counter,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.zone_id = zone_id
        self.look = look
        self.brightness = brightness
        self.generation = 0
        self.crash: CrashInfo | None = None
        self.slow_since: datetime | None = None
        self._clock = clock
        self._latency_s = latency_s
        self._fps = fps
        self._max_lookahead_s = max_lookahead_s
        self._seed = seed
        self._timer = timer
        self._now = now
        self._field: tuple[Layer, FieldEffect] | None = None
        self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
        self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
        self._copies: dict[str, int] = {}  # light -> firmware layer streamed as a copy
        self._emulated: set[str] = set()  # lights that rejected their firmware effect
        self._lights: tuple[ZoneLight, ...] = ()
        self._slices: dict[str, DeviceSlice] = {}
        self._rendering = ""
        self._last_crash_log = float("-inf")
        self._render_s = 0.0  # moving average of the render time
        self._stride = 1
        self._ticks = 0
        self._rendered: deque[float] = deque()
        self._below_since: float | None = None
        self.ring = RingBuffer(capacity=int(max_lookahead_s * fps) + 2, led_count=0)
        self.leds = build_ledset([])
        self.set_lights(lights)
        self._compile()

    # --- what the zone looks like from outside -------------------------------------

    @property
    def lights(self) -> tuple[ZoneLight, ...]:
        return self._lights

    @property
    def field_effect(self) -> FieldEffect | None:
        return self._field[1] if self._field is not None else None

    @property
    def waiting_for(self) -> tuple[str, ...]:
        return tuple(need for need in self.look.needs if need not in ALWAYS_AVAILABLE)

    @property
    def state(self) -> ZoneState:
        if self.crash is not None:
            return "crashed"
        if self.waiting_for:
            return "waiting"
        return "slow" if self.slow_since is not None else "running"

    @property
    def fps_actual(self) -> float:
        return float(len(self._rendered))

    @property
    def fps_target(self) -> int:
        return self._fps

    @property
    def horizon_s(self) -> float:
        """The zone's largest device latency plus one frame, within the lookahead."""
        latency = max((self._latency_s(light.device_id) for light in self._lights), default=0.0)
        return min(latency + 1.0 / self._fps, self._max_lookahead_s)

    def claim_for(self, device_id: str) -> tuple[Layer, FirmwareEffect] | None:
        index = self._claims.get(device_id)
        return None if index is None else self._firmware[index]

    def mode_of(self, device_id: str) -> LightMode:
        if device_id in self._claims:
            return "own-effect"
        if device_id in self._copies:
            return "streamed-copy"
        return "streaming"

    def effect_name(self, device_id: str) -> str | None:
        index = self._claims.get(device_id, self._copies.get(device_id))
        return None if index is None else self._firmware[index][1].display_name

    def route_for(self, device_id: str) -> DeviceRoute | None:
        piece = self._slices.get(device_id)
        if piece is None or piece.count == 0:
            return None
        return DeviceRoute(
            zone_id=self.zone_id,
            ring=self.ring,
            start=piece.start,
            stop=piece.stop,
            streaming=device_id not in self._claims,
        )

    # --- changes --------------------------------------------------------------------

    def set_lights(self, lights: Sequence[ZoneLight]) -> None:
        """Rebuild the LED set and start a fresh ring, so no route outlives its frames."""
        self._lights = tuple(lights)
        self.leds = build_ledset(
            [LedSource(light.device_id, light.led_count, light.geometry) for light in self._lights]
        )
        self._slices = {piece.device_id: piece for piece in self.leds.slices}
        self.ring = RingBuffer(capacity=self.ring.capacity, led_count=self.leds.count)
        self._emulated &= set(self._slices)
        self._plan_claims()

    def set_brightness(self, value: float) -> None:
        self.brightness = value
        if self._claims:
            self.generation += 1  # firmware effects take the brightness when they start

    def update_look(self, look: Look) -> None:
        """Take new settings in place when the layers are the same, else rebuild the look.

        In place keeps each effect's state, so a chase keeps its position while a slider
        moves. The generation moves on only when firmware lights need their effect again.
        """
        old, self.look = self.look, look
        if self.crash is not None or _layout(old) != _layout(look) or old.needs != look.needs:
            self._compile()
            return
        field_layer = visible_field_layer(look)
        if self._field is not None and field_layer is not None:
            self._field[1].set_params(**field_layer.settings)
            self._field = (field_layer, self._field[1])
        resend = False
        for index, layer in enumerate(reversed(firmware_layers(look))):
            old_layer, effect = self._firmware[index]
            if old_layer.settings != layer.settings:
                effect.set_params(**layer.settings)
                resend = True
            self._firmware[index] = (layer, effect)
        if resend:
            self.generation += 1

    def restart(self) -> None:
        """Re-create the look (spec §8), and give rejected firmware effects another try."""
        self._emulated.clear()
        self._compile()

    def mark_emulated(self, device_id: str) -> None:
        """The light refused its firmware effect: stream that layer's copy to it instead."""
        index = self._claims.pop(device_id, None)
        if index is not None:
            self._emulated.add(device_id)
            self._copies[device_id] = index

    # --- rendering ------------------------------------------------------------------

    def tick(self, now: float) -> None:
        """Render the frame shown at now + horizon, unless crashed or skipping for budget."""
        if self.crash is not None:
            return
        self._ticks += 1
        if self._ticks % self._stride:
            return
        target = now + self.horizon_s
        ctx = render_context(self._clock, target, self._stride / self._fps)
        started = self._timer()
        try:
            colors = self._render(ctx)
        except Exception as exc:  # a look never takes the engine down (spec §8)
            self._fail(self._rendering, f"{type(exc).__name__}: {exc}")
            return
        elapsed = self._timer() - started
        self.ring.write(
            RenderedFrame(
                colors=colors,
                target_time=target,
                beat_phase=ctx.beat_phase,
                bar_phase=ctx.bar_phase,
            )
        )
        self._track_speed(now, elapsed)

    def _render(self, ctx: RenderContext) -> FloatRGB:
        frame = np.zeros((self.leds.count, 3), dtype=np.float32)
        if self.waiting_for or self.leds.count == 0:
            return frame
        if self._field is not None:
            layer, effect = self._field
            self._rendering = layer.name
            frame[:] = _finite(effect.render(ctx, self.leds)) * np.float32(layer.opacity)
        assigned = [*self._claims.items(), *self._copies.items()]
        for index in sorted({owner for _, owner in assigned}):
            layer, firmware = self._firmware[index]
            self._rendering = layer.name
            copy = _finite(firmware.emulate(ctx, self.leds)) * np.float32(layer.opacity)
            for device_id, owner in assigned:
                if owner == index:
                    piece = self._slices[device_id]
                    frame[piece.start : piece.stop] = copy[piece.start : piece.stop]
        frame *= np.float32(self.brightness)
        return frame

    def _compile(self) -> None:
        self.generation += 1
        self.crash = None
        self._field = None
        self._firmware = []
        field_layer = visible_field_layer(self.look)
        layers = [field_layer] if field_layer is not None else []
        layers += list(reversed(firmware_layers(self.look)))
        for layer in layers:
            try:
                effect = make_effect(layer)
            except LookError as exc:
                self._field = None
                self._firmware = []
                self._fail(layer.name, str(exc))
                break
            effect.reseed(self._seed)
            if isinstance(effect, FirmwareEffect):
                self._firmware.append((layer, effect))
            else:
                self._field = (layer, effect)
        self._plan_claims()

    def _plan_claims(self) -> None:
        self._claims = {}
        self._copies = {}
        if self.crash is not None or self.waiting_for or not self._firmware:
            return
        for light in self._lights:
            index = next(
                (i for i, (_, fw) in enumerate(self._firmware) if fw.supports(light.caps)),
                None,
            )
            if index is None:
                if self._field is None:
                    self._copies[light.device_id] = 0  # the top layer's streamed copy
            elif light.device_id in self._emulated:
                self._copies[light.device_id] = index
            else:
                self._claims[light.device_id] = index

    def _fail(self, layer: str, message: str) -> None:
        self.crash = CrashInfo(layer=layer, message=message, at=self._now())
        stamp = time.monotonic()
        if stamp - self._last_crash_log >= CRASH_LOG_INTERVAL_S:
            self._last_crash_log = stamp
            logger.error(
                "Zone {}: layer '{}' crashed, holding the last frame: {}",
                self.zone_id,
                layer,
                message,
            )

    def _track_speed(self, now: float, elapsed: float) -> None:
        self._render_s = elapsed if self._render_s == 0.0 else 0.9 * self._render_s + 0.1 * elapsed
        self._stride = max(1, min(self._fps, math.ceil(self._render_s / FRAME_BUDGET_S)))
        self._rendered.append(now)
        while now - self._rendered[0] > 1.0:
            self._rendered.popleft()
        if len(self._rendered) < SLOW_RATIO * self._fps:
            if self._below_since is None:
                self._below_since = now
            if self.slow_since is None and now - self._below_since >= SLOW_AFTER_S:
                self.slow_since = self._now()
        else:
            self._below_since = None
            self.slow_since = None
```

- [ ] **Step 9: Run the tests to see them pass**

Run: `uv run pytest tests/scheduling/test_route.py tests/zones -v`
Expected: PASS. Then run the benchmark once: `uv run pytest -m perf -v`. Expected: PASS on this machine (7 looks, median under 5 ms). If a look fails, profile it before continuing; the budget is a spec requirement, not a tuning target.

- [ ] **Step 10: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add pyproject.toml src/dj_ledfx/types.py src/dj_ledfx/zones src/dj_ledfx/scheduling/route.py tests/conftest.py tests/scheduling/test_route.py tests/zones
git commit -m "feat(zones): zone runtime with claims, horizon, crash hold and frame-rate drop"
```

---

### Task 16: Zone manager: start, take-over, Off, brightness, Restart, Stop all

The `ZoneManager` owns which running zone each light belongs to and everything dj-ledfx asks of the lights (spec §4.3, §6.4, §8): a light's state is captured the first time dj-ledfx takes control of it and kept through hand-overs; applying a look turns the zone's lights on; firmware layers start on the lights that claim them and fall back to a streamed copy when a light refuses; Off restores each light once, and leaves alone a light that couldn't be captured. Captures are saved in `state.db` (`device_saved_state`), so Off still works after a restart. A capture that failed is saved as empty bytes: it records that dj-ledfx has control, so a restart doesn't capture the look itself as "before".

The manager talks to the engine and the scheduler through two small protocols, `RuntimeHost` and `RouteTable`; the engine and scheduler implement them in the cut-over (Task 24), and tests use fakes. Every command holds one lock, so take-overs never interleave.

**Files:**
- Modify: `src/dj_ledfx/zones/model.py` (`TakeOver`, `RunningZoneInfo`, `StartResult`, errors, `ZonesChanged`)
- Create: `src/dj_ledfx/zones/manager.py`
- Create: `tests/zone_home.py`, `tests/zones/conftest.py`
- Test: `tests/zones/test_manager.py`

**Interfaces:**
- Consumes: `ZoneRuntime`, `ZoneLight`, `LightMode`, `ZoneState`, `CrashInfo` (Task 15); `ZoneStore`, `ZoneRecord`, `Assignment` (Task 14); `LookStore`, `look_body` (Task 13); `Look`, `validate_look`, `LookNotFoundError` (Task 11); `LightReading` (Task 2); `DeviceManager.get_by_stable_id`, `DeviceManager.devices`, `LatencyTracker.effective_latency_s`; `StateDB.load_all_device_states`, `save_device_state`, `delete_device_state`; `EventBus`; `FakeLight`, `GlowFirmware` (Tasks 2 and 15).
- Produces:
  - `zones.model.TakeOver(zone_id, zone_name, look_name, lights: tuple[str, ...], stopped: bool)`
  - `zones.model.RunningZoneInfo(zone_id, look_id, look_name, since: datetime, brightness, lights: tuple[str, ...], state: ZoneState, fps_actual: float | None = None, fps_target: int | None = None, error: CrashInfo | None = None, waiting_for: tuple[str, ...] = (), slow_since: datetime | None = None)`
  - `zones.model.StartResult(running: RunningZoneInfo, take_overs: tuple[TakeOver, ...])`
  - `zones.model.ZoneNotFoundError(KeyError)`, `ZoneError(ValueError)`, `ZoneNotRunningError(ZoneError)`; event `ZonesChanged()`
  - `zones.manager.RuntimeHost` (`add_runtime(runtime)`, `remove_runtime(zone_id)`), `zones.manager.RouteTable` (`set_route(device_id, route | None)`, `set_preview_only(on)`)
  - `zones.manager.ZoneManager(*, store, looks, devices, db, host, routes, event_bus, clock, fps=60, max_lookahead_s=1.0, preview_only=False, now=<utc now>)`: `async load()`, `preview_only`, `zones() -> list[ZoneRecord]` (an all-lights zone lists every known light), `get_zone(zone_id)`, `running() -> list[RunningZoneInfo]` (oldest first), `running_info(zone_id)`, `owner_of(device_id)`, `light_mode(device_id) -> LightMode | None`, `effect_name(device_id)`, `power_of(device_id)`, `async start(zone_id, look) -> StartResult`, `async off(zone_id)`, `async stop_all()`, `async set_brightness(zone_id, value) -> RunningZoneInfo`, `async restart(zone_id) -> RunningZoneInfo`
  - `tests/zone_home.py`: `Home` (`db`, `lights`, `devices`, `store`, `looks`, `host`, `routes`, `bus`, `manager`, `clock`, `changes`, `look(look_id)`), `FakeHost`, `FakeRoutes`, `GLOW` and `BREATHE_AND_GLOW` looks, `TILE` capabilities, `build_home(tmp_path, lights, zones, *, preview_only=False)`, `HomeFactory`; `tests/zones/conftest.py`: the `make_home` fixture (closes the database afterwards)

- [ ] **Step 1: Add the model types to `src/dj_ledfx/zones/model.py`**

Add `TYPE_CHECKING` to the `typing` import, and below the imports:

```python
if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneState
```

Append:

```python
@dataclass(frozen=True, slots=True)
class TakeOver:
    """A running zone that lost lights to a newer start (spec §4.3)."""

    zone_id: str
    zone_name: str
    look_name: str
    lights: tuple[str, ...]  # the lights it lost
    stopped: bool  # it had none left, so it stopped


@dataclass(frozen=True, slots=True)
class RunningZoneInfo:
    """A running zone as the web app sees it (web spec §12.2 RunningZone)."""

    zone_id: str
    look_id: str
    look_name: str
    since: datetime
    brightness: float
    lights: tuple[str, ...]  # the lights it owns after take-overs
    state: ZoneState
    fps_actual: float | None = None
    fps_target: int | None = None
    error: CrashInfo | None = None
    waiting_for: tuple[str, ...] = ()
    slow_since: datetime | None = None  # for the attention feed; not in the contract


@dataclass(frozen=True, slots=True)
class StartResult:
    running: RunningZoneInfo
    take_overs: tuple[TakeOver, ...]


class ZoneNotFoundError(KeyError):
    """No zone has that id."""


class ZoneError(ValueError):
    """A zone request that can't be carried out, with the reason."""


class ZoneNotRunningError(ZoneError):
    pass


@dataclass(frozen=True, slots=True)
class ZonesChanged:
    """Running zones changed: started, stopped, taken over, brightness or state."""
```

- [ ] **Step 2: Write the test home**

`tests/zone_home.py`:

```python
"""A home for ZoneManager tests: real stores on a temporary state.db, FakeLights, and
fakes for the engine (it hosts runtimes) and the scheduler (it holds routes)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from conftest import FakeLight

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.looks.store import LookStore
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.zones.manager import ZoneManager
from dj_ledfx.zones.model import ZoneRecord, ZonesChanged
from dj_ledfx.zones.runtime import ZoneRuntime
from dj_ledfx.zones.store import ZoneStore

TILE = DeviceCapabilities(protocol="LIFX", matrix=True)
GLOW_LAYER = Layer(id="glow", name="Glow", type="firmware", kind="glow_firmware")
GLOW = Look(id="glow", name="Glow look", category="firmware", layers=(GLOW_LAYER,))
BREATHE_AND_GLOW = Look(
    id="breathe-glow",
    name="Breathe and glow",
    category="ambient",
    layers=(Layer(id="field", name="Breathe", type="field", kind="breathe"), GLOW_LAYER),
)
START = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)


class FakeHost:
    """Stands in for the engine: it only keeps the runtimes it is given."""

    def __init__(self) -> None:
        self.runtimes: dict[str, ZoneRuntime] = {}

    def add_runtime(self, runtime: ZoneRuntime) -> None:
        self.runtimes[runtime.zone_id] = runtime

    def remove_runtime(self, zone_id: str) -> None:
        self.runtimes.pop(zone_id, None)


class FakeRoutes:
    """Stands in for the scheduler: it only keeps each light's route."""

    def __init__(self) -> None:
        self.routes: dict[str, DeviceRoute] = {}
        self.preview_only = False

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None:
        if route is None:
            self.routes.pop(device_id, None)
        else:
            self.routes[device_id] = route

    def set_preview_only(self, on: bool) -> None:
        self.preview_only = on


@dataclass
class Home:
    db: StateDB
    lights: dict[str, FakeLight]
    devices: DeviceManager
    store: ZoneStore
    looks: LookStore
    host: FakeHost
    routes: FakeRoutes
    bus: EventBus
    manager: ZoneManager
    clock: list[datetime]  # the manager's "now"; tests move it
    changes: list[ZonesChanged] = field(default_factory=list)

    def look(self, look_id: str) -> Look:
        return self.looks.get(look_id)


HomeFactory = Callable[..., Awaitable[Home]]


async def build_home(
    tmp_path: Path,
    lights: Sequence[FakeLight],
    zones: Sequence[ZoneRecord],
    *,
    preview_only: bool = False,
) -> Home:
    db = StateDB(tmp_path / "state.db")
    await db.open()
    store = ZoneStore(db)
    for zone in zones:
        await store.save_zone(zone)
    return await assemble(db, lights, [START], preview_only)


async def assemble(
    db: StateDB, lights: Sequence[FakeLight], clock: list[datetime], preview_only: bool
) -> Home:
    """The app's objects around an open state.db and a set of lights."""
    bus = EventBus()
    devices = DeviceManager(event_bus=bus)
    for light in lights:
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(20.0)))
    looks = LookStore(db)
    await looks.load()
    store = ZoneStore(db)
    host, routes = FakeHost(), FakeRoutes()
    manager = ZoneManager(
        store=store,
        looks=looks,
        devices=devices,
        db=db,
        host=host,
        routes=routes,
        event_bus=bus,
        clock=BeatClock(),
        preview_only=preview_only,
        now=lambda: clock[0],
    )
    home = Home(
        db=db,
        lights={light.stable_id: light for light in lights},
        devices=devices,
        store=store,
        looks=looks,
        host=host,
        routes=routes,
        bus=bus,
        manager=manager,
        clock=clock,
    )
    bus.subscribe(ZonesChanged, home.changes.append)
    await manager.load()
    return home
```

`tests/zones/conftest.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest_asyncio
from conftest import FakeLight
from zone_home import Home, HomeFactory, build_home

from dj_ledfx.zones.model import ZoneRecord


@pytest_asyncio.fixture
async def make_home(tmp_path: Path) -> AsyncIterator[HomeFactory]:
    homes: list[Home] = []

    async def factory(
        lights: Sequence[FakeLight], zones: Sequence[ZoneRecord], *, preview_only: bool = False
    ) -> Home:
        home = await build_home(tmp_path, lights, zones, preview_only=preview_only)
        homes.append(home)
        return home

    yield factory
    for home in homes:
        await home.db.close()
```

- [ ] **Step 3: Write the failing tests**

`tests/zones/test_manager.py`:

```python
from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import FakeLight
from zone_home import GLOW, TILE, HomeFactory

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.looks.model import Look, LookError
from dj_ledfx.zones.model import (
    TakeOver,
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
)

LAMP = DeviceCapabilities(protocol="Govee")


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


async def test_start_captures_switches_on_and_streams(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", power=False)
    bulb = FakeLight("bulb")
    home = await make_home([lamp, bulb], [_zone("desk", "lamp", "bulb")])

    result = await home.manager.start("desk", home.look("classic-breathe"))

    assert lamp.names() == ["capture", "power", "prepare_stream"]
    assert bulb.names() == ["capture", "prepare_stream"]
    assert result.take_overs == ()
    info = result.running
    assert (info.zone_id, info.look_id, info.look_name) == ("desk", "classic-breathe", "Breathe")
    assert (info.lights, info.brightness, info.state) == (("lamp", "bulb"), 1.0, "running")
    runtime = home.host.runtimes["desk"]
    assert home.routes.routes["lamp"].ring is runtime.ring
    assert home.routes.routes["bulb"].streaming
    [saved] = await home.store.load_assignments()
    assert (saved.zone_id, saved.look_id, saved.lights) == ("desk", "classic-breathe", ("lamp", "bulb"))
    assert await home.db.load_device_state("lamp") == b"before"
    assert len(home.changes) == 1


async def test_a_light_that_cannot_report_its_power_is_switched_on(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", caps=LAMP, power=None)
    home = await make_home([lamp], [_zone("z", "lamp")])

    await home.manager.start("z", home.look("classic-breathe"))

    assert lamp.names() == ["capture", "power", "prepare_stream"]


# Review focus 1: overlapping zones started one after the other.
async def test_takeover_keeps_first_capture_and_off_restores_it(make_home: HomeFactory) -> None:
    a = FakeLight("a", captured=b"a-before")
    b = FakeLight("b", captured=b"b-before")
    c = FakeLight("c", captured=b"c-before")
    home = await make_home([a, b, c], [_zone("left", "a", "b"), _zone("right", "b", "c")])
    await home.manager.start("left", home.look("classic-breathe"))
    b.captured = b"b-showing-breathe"  # what capturing b again would get now

    result = await home.manager.start("right", home.look("classic-strobe"))

    assert result.take_overs == (TakeOver("left", "Left", "Breathe", ("b",), stopped=False),)
    left = home.manager.running_info("left")
    assert left is not None and left.lights == ("a",)
    assert home.host.runtimes["left"].leds.count == a.led_count
    assert home.routes.routes["a"].zone_id == "left"
    assert home.routes.routes["b"].zone_id == "right"
    assert b.names().count("capture") == 1
    saved = {x.zone_id: x.lights for x in await home.store.load_assignments()}
    assert saved == {"left": ("a",), "right": ("b", "c")}

    await home.manager.off("right")

    assert ("restore", b"b-before") in b.calls
    assert ("restore", b"c-before") in c.calls
    assert "restore" not in a.names()
    assert set(home.routes.routes) == {"a"}
    assert [x.zone_id for x in await home.store.load_assignments()] == ["left"]

    await home.manager.off("left")
    assert ("restore", b"a-before") in a.calls
    assert await home.db.load_all_device_states() == {}


async def test_a_zone_left_with_no_lights_stops(make_home: HomeFactory) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    everything = ZoneRecord(id="all", name="Everything", all_lights=True)
    home = await make_home([a, b], [_zone("desk", "a"), everything])
    await home.manager.start("desk", home.look("classic-breathe"))

    result = await home.manager.start("all", home.look("classic-strobe"))

    assert result.take_overs == (TakeOver("desk", "Desk", "Breathe", ("a",), stopped=True),)
    assert result.running.lights == ("a", "b")
    assert home.manager.running_info("desk") is None
    assert set(home.host.runtimes) == {"all"}
    assert [x.zone_id for x in await home.store.load_assignments()] == ["all"]
    assert "restore" not in a.names()  # it went straight to the newer zone


async def test_firmware_runs_on_the_lights_that_support_it(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    lamp = FakeLight("lamp", caps=LAMP)
    home = await make_home([tile, lamp], [_zone("z", "tile", "lamp")])

    await home.manager.start("z", GLOW)

    assert tile.calls == [("capture", None), ("firmware", {"level": 0.5, "brightness": 1.0})]
    assert not home.routes.routes["tile"].streaming
    assert lamp.names() == ["capture", "prepare_stream"]
    assert home.routes.routes["lamp"].streaming
    assert home.manager.light_mode("tile") == "own-effect"
    assert home.manager.light_mode("lamp") == "streamed-copy"
    assert home.manager.effect_name("lamp") == "Glow"
    assert home.manager.light_mode("nobody") is None


async def test_a_rejected_firmware_effect_streams_its_copy(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    tile.reject_firmware = True
    home = await make_home([tile], [_zone("z", "tile")])

    await home.manager.start("z", GLOW)

    assert tile.names() == ["capture", "prepare_stream"]
    assert home.routes.routes["tile"].streaming
    assert home.manager.light_mode("tile") == "streamed-copy"


async def test_off_leaves_an_uncapturable_light_alone(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", captured=None)
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    assert await home.db.load_device_state("lamp") == b""  # control taken, nothing captured

    await home.manager.off("z")

    assert "restore" not in lamp.names()
    assert await home.db.load_device_state("lamp") is None


async def test_off_is_idempotent_and_unknown_zones_raise(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.off("z")
    assert lamp.calls == []

    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.off("z")
    await home.manager.off("z")

    assert lamp.names().count("restore") == 1
    with pytest.raises(ZoneNotFoundError):
        await home.manager.off("nope")
    with pytest.raises(ZoneNotFoundError):
        await home.manager.start("nope", home.look("classic-breathe"))


async def test_brightness_is_saved_and_resends_firmware(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)

    info = await home.manager.set_brightness("z", 0.4)

    assert info.brightness == 0.4
    assert tile.calls[-1] == ("firmware", {"level": 0.5, "brightness": 0.4})
    assert home.host.runtimes["z"].brightness == 0.4
    [saved] = await home.store.load_assignments()
    assert saved.brightness == 0.4
    with pytest.raises(ZoneError, match="between 0 and 1"):
        await home.manager.set_brightness("z", 1.5)
    await home.manager.off("z")
    with pytest.raises(ZoneNotRunningError):
        await home.manager.set_brightness("z", 0.5)


async def test_stop_all_restores_every_light(make_home: HomeFactory) -> None:
    a, b = FakeLight("a", captured=b"a0"), FakeLight("b", captured=b"b0")
    home = await make_home([a, b], [_zone("one", "a"), _zone("two", "b")])
    await home.manager.start("one", home.look("classic-breathe"))
    await home.manager.start("two", home.look("classic-strobe"))

    await home.manager.stop_all()

    assert ("restore", b"a0") in a.calls and ("restore", b"b0") in b.calls
    assert home.manager.running() == []
    assert home.host.runtimes == {} and home.routes.routes == {}
    assert await home.store.load_assignments() == []


async def test_restart_gives_a_rejected_firmware_effect_another_try(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    tile.reject_firmware = True
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    tile.reject_firmware = False

    info = await home.manager.restart("z")

    assert tile.names()[-1] == "firmware"
    assert home.manager.light_mode("tile") == "own-effect"
    assert not home.routes.routes["tile"].streaming
    assert info.state == "running"


async def test_starting_a_running_zone_again_replaces_its_look(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp", captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.manager.set_brightness("z", 0.3)

    result = await home.manager.start("z", home.look("classic-strobe"))

    assert (result.running.look_id, result.running.brightness) == ("classic-strobe", 0.3)
    assert lamp.names().count("capture") == 1 and "restore" not in lamp.names()
    assert list(home.host.runtimes) == ["z"]
    assert home.routes.routes["lamp"].ring is home.host.runtimes["z"].ring


async def test_a_look_starts_its_firmware_even_when_layer_ids_repeat(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    brighter = Look(
        id="glow-2",
        name="Brighter glow",
        category="firmware",
        layers=(replace(GLOW.layers[0], settings={"level": 0.9}),),  # same layer id
    )

    await home.manager.start("z", brighter)

    assert tile.names().count("firmware") == 2  # a new look always sends its effect
    assert tile.calls[-1] == ("firmware", {"level": 0.9, "brightness": 1.0})


async def test_a_zone_with_no_lights_or_a_look_m1_cannot_run_is_refused(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("empty"), _zone("z", "lamp")])
    with pytest.raises(ZoneError, match="no lights"):
        await home.manager.start("empty", home.look("classic-breathe"))
    home_look = Look(id="x", name="X", category="home", scope="whole-home", layers=GLOW.layers)
    with pytest.raises(LookError, match="M6"):
        await home.manager.start("z", home_look)
    assert lamp.calls == []
```

- [ ] **Step 4: Run the tests to see them fail**

Run: `uv run pytest tests/zones/test_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.zones.manager'`.

- [ ] **Step 5: Write `src/dj_ledfx/zones/manager.py`**

```python
"""Zones at run time: start, take-over, Off, brightness, Restart and Stop all (spec §4.3).

The manager owns which running zone each light belongs to, and everything dj-ledfx asks
of the lights (spec §6.4): it captures a light the first time dj-ledfx takes control of
it, switches it on when a look is applied, runs firmware layers on the lights that claim
them, and puts the light back how it was when it leaves every running zone. Captures are
saved in state.db, so Off still works after a restart. A light that couldn't be captured
is saved as an empty capture: Off leaves it alone rather than guessing (spec §8).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.looks.model import LookNotFoundError, validate_look
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import (
    Assignment,
    CrashInfo,
    RunningZoneInfo,
    StartResult,
    TakeOver,
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
    ZonesChanged,
)
from dj_ledfx.zones.runtime import LightMode, ZoneLight, ZoneRuntime

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.devices.adapter import DeviceAdapter
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.events import EventBus
    from dj_ledfx.looks.model import Look
    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.scheduling.route import DeviceRoute
    from dj_ledfx.zones.store import ZoneStore

# What a light was last given: the runtime it belongs to, that runtime's generation, and
# the firmware layer it runs (None: it streams).
AppliedKey = tuple[int, int, str | None]


class RuntimeHost(Protocol):
    """Renders the running zones: the effect engine."""

    def add_runtime(self, runtime: ZoneRuntime) -> None: ...

    def remove_runtime(self, zone_id: str) -> None: ...


class RouteTable(Protocol):
    """Sends each light its slice of its zone's frames: the scheduler."""

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None: ...

    def set_preview_only(self, on: bool) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _Running:
    look_id: str
    look_name: str
    look_json: str  # the look as it was started, as saved in state.db
    brightness: float
    since: datetime
    lights: list[str]  # the lights the zone owns after take-overs, in zone order
    runtime: ZoneRuntime | None  # None when the saved look can't be read (Task 17)
    epoch: int  # tells runtimes apart, so a new look always reaches the lights
    broken: CrashInfo | None = None


class ZoneManager:
    def __init__(
        self,
        *,
        store: ZoneStore,
        looks: LookStore,
        devices: DeviceManager,
        db: StateDB,
        host: RuntimeHost,
        routes: RouteTable,
        event_bus: EventBus,
        clock: BeatClock,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        preview_only: bool = False,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._store = store
        self._looks = looks
        self._devices = devices
        self._db = db
        self._host = host
        self._routes = routes
        self._event_bus = event_bus
        self._clock = clock
        self._fps = fps
        self._max_lookahead_s = max_lookahead_s
        self._preview_only = preview_only
        self._now = now
        self._zones: dict[str, ZoneRecord] = {}
        self._running: dict[str, _Running] = {}
        self._captured: dict[str, bytes] = {}  # b"": control taken, nothing captured
        self._applied: dict[str, AppliedKey] = {}
        self._power: dict[str, bool | None] = {}
        self._deferred_power_on: set[str] = set()
        self._epochs = 0
        self._lock = asyncio.Lock()
        routes.set_preview_only(preview_only)

    async def load(self) -> None:
        self._zones = {zone.id: zone for zone in await self._store.load_zones()}
        self._captured = await self._db.load_all_device_states()

    # --- queries ----------------------------------------------------------------------

    @property
    def preview_only(self) -> bool:
        return self._preview_only

    def zones(self) -> list[ZoneRecord]:
        return [replace(zone, lights=self._lights_of(zone)) for zone in self._zones.values()]

    def get_zone(self, zone_id: str) -> ZoneRecord:
        zone = self._zones.get(zone_id)
        if zone is None:
            raise ZoneNotFoundError(zone_id)
        return replace(zone, lights=self._lights_of(zone))

    def running(self) -> list[RunningZoneInfo]:
        infos = [self._info(zone_id, running) for zone_id, running in self._running.items()]
        return sorted(infos, key=lambda info: info.since)

    def running_info(self, zone_id: str) -> RunningZoneInfo | None:
        running = self._running.get(zone_id)
        return None if running is None else self._info(zone_id, running)

    def owner_of(self, device_id: str) -> str | None:
        for zone_id, running in self._running.items():
            if device_id in running.lights:
                return zone_id
        return None

    def light_mode(self, device_id: str) -> LightMode | None:
        """How a light shows its zone's look; None when no running zone owns it."""
        zone_id = self.owner_of(device_id)
        if zone_id is None:
            return None
        runtime = self._running[zone_id].runtime
        return "streaming" if runtime is None else runtime.mode_of(device_id)

    def effect_name(self, device_id: str) -> str | None:
        """The firmware effect a light runs, or streams a copy of."""
        zone_id = self.owner_of(device_id)
        runtime = self._running[zone_id].runtime if zone_id is not None else None
        return None if runtime is None else runtime.effect_name(device_id)

    def power_of(self, device_id: str) -> bool | None:
        return self._power.get(device_id)

    # --- commands ---------------------------------------------------------------------

    async def start(self, zone_id: str, look: Look) -> StartResult:
        """Put a look on a zone. It takes its lights over from running zones (spec §4.3)."""
        validate_look(look)
        async with self._lock:
            zone = self.get_zone(zone_id)
            lights = [light for light in zone.lights if self._adapter(light) is not None]
            if not lights:
                raise ZoneError(f"{zone.name} has no lights")
            take_overs, touched = await self._take_over(zone_id, lights)
            previous = self._running.pop(zone_id, None)
            if previous is not None:
                self._host.remove_runtime(zone_id)
            brightness = previous.brightness if previous is not None else 1.0
            runtime = self._new_runtime(zone_id, look, lights, brightness)
            running = _Running(
                look_id=look.id,
                look_name=look.name,
                look_json=look_body(look),
                brightness=brightness,
                since=self._now(),
                lights=lights,
                runtime=runtime,
                epoch=self._next_epoch(),
            )
            self._running[zone_id] = running
            self._host.add_runtime(runtime)
            await self._persist(zone_id)
            released = [x for x in previous.lights if x not in lights] if previous else []
            await self._sync([*lights, *touched, *released], power_on=lights)
            result = StartResult(self._info(zone_id, running), tuple(take_overs))
        self._event_bus.emit(ZonesChanged())
        return result

    async def off(self, zone_id: str) -> None:
        """Stop the zone's look and put its lights back how they were. Idempotent."""
        async with self._lock:
            self.get_zone(zone_id)
            released = await self._stop(zone_id)
            if not released:
                return
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    async def stop_all(self) -> None:
        async with self._lock:
            if not self._running:
                return
            released: list[str] = []
            for zone_id in list(self._running):
                released += await self._stop(zone_id)
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    async def set_brightness(self, zone_id: str, value: float) -> RunningZoneInfo:
        """Scale the zone's streamed frames and its firmware effects (spec §4.3)."""
        if not 0.0 <= value <= 1.0:
            raise ZoneError("Brightness must be between 0 and 1")
        async with self._lock:
            running = self._require_running(zone_id)
            running.brightness = value
            if running.runtime is not None:
                running.runtime.set_brightness(value)
            await self._persist(zone_id)
            await self._sync(running.lights)
            info = self._info(zone_id, running)
        self._event_bus.emit(ZonesChanged())
        return info

    async def restart(self, zone_id: str) -> RunningZoneInfo:
        """Re-create the zone's look (spec §8); rejected firmware effects get another try."""
        async with self._lock:
            running = self._require_running(zone_id)
            if running.runtime is not None:
                running.runtime.restart()
            elif self._rebuild_broken(zone_id, running):
                await self._persist(zone_id)
            await self._sync(running.lights)
            info = self._info(zone_id, running)
        self._event_bus.emit(ZonesChanged())
        return info

    # --- running zones ----------------------------------------------------------------

    def _require_running(self, zone_id: str) -> _Running:
        zone = self.get_zone(zone_id)
        running = self._running.get(zone_id)
        if running is None:
            raise ZoneNotRunningError(f"{zone.name} isn't running")
        return running

    def _next_epoch(self) -> int:
        self._epochs += 1
        return self._epochs

    def _new_runtime(
        self, zone_id: str, look: Look, lights: Iterable[str], brightness: float
    ) -> ZoneRuntime:
        return ZoneRuntime(
            zone_id,
            look,
            self._zone_lights(lights),
            clock=self._clock,
            latency_s=self._latency_s,
            fps=self._fps,
            max_lookahead_s=self._max_lookahead_s,
            brightness=brightness,
            now=self._now,
        )

    def _rebuild_broken(self, zone_id: str, running: _Running) -> bool:
        """A zone whose saved look can't be read tries the look saved under its id."""
        try:
            look = self._looks.get(running.look_id)
        except LookNotFoundError:
            return False
        running.runtime = self._new_runtime(zone_id, look, running.lights, running.brightness)
        running.epoch = self._next_epoch()
        running.broken = None
        running.look_name = look.name
        running.look_json = look_body(look)
        self._host.add_runtime(running.runtime)
        return True

    async def _take_over(
        self, zone_id: str, wanted: Iterable[str]
    ) -> tuple[list[TakeOver], list[str]]:
        """Take lights from other running zones: the newest assignment wins (spec §4.3).

        Returns the take-overs and the lights left in zones that lost some: their zone
        rebuilt its LED set, so they need new routes.
        """
        wanted_set = set(wanted)
        take_overs: list[TakeOver] = []
        touched: list[str] = []
        for other_id, other in list(self._running.items()):
            lost = [x for x in other.lights if x in wanted_set] if other_id != zone_id else []
            if not lost:
                continue
            other.lights = [x for x in other.lights if x not in wanted_set]
            stopped = not other.lights
            zone_name = self._zones[other_id].name
            take_overs.append(TakeOver(other_id, zone_name, other.look_name, tuple(lost), stopped))
            if stopped:
                await self._stop(other_id)
                continue
            if other.runtime is not None:
                other.runtime.set_lights(self._zone_lights(other.lights))
            await self._persist(other_id)
            touched += other.lights
        return take_overs, touched

    async def _stop(self, zone_id: str) -> list[str]:
        """Forget a running zone. Returns its lights, which the caller syncs (releases)."""
        running = self._running.pop(zone_id, None)
        if running is None:
            return []
        self._host.remove_runtime(zone_id)
        await self._store.delete_assignment(zone_id)
        return running.lights

    async def _persist(self, zone_id: str) -> None:
        running = self._running[zone_id]
        await self._store.save_assignment(
            Assignment(
                zone_id=zone_id,
                look_id=running.look_id,
                look_json=running.look_json,
                brightness=running.brightness,
                lights=tuple(running.lights),
                started_at=running.since,
            )
        )

    def _info(self, zone_id: str, running: _Running) -> RunningZoneInfo:
        runtime = running.runtime
        if runtime is None:
            return RunningZoneInfo(
                zone_id=zone_id,
                look_id=running.look_id,
                look_name=running.look_name,
                since=running.since,
                brightness=running.brightness,
                lights=tuple(running.lights),
                state="crashed",
                error=running.broken,
            )
        return RunningZoneInfo(
            zone_id=zone_id,
            look_id=running.look_id,
            look_name=running.look_name,
            since=running.since,
            brightness=running.brightness,
            lights=tuple(running.lights),
            state=runtime.state,
            fps_actual=runtime.fps_actual,
            fps_target=runtime.fps_target,
            error=runtime.crash,
            waiting_for=runtime.waiting_for,
            slow_since=runtime.slow_since,
        )

    # --- lights -----------------------------------------------------------------------

    def _adapter(self, device_id: str) -> DeviceAdapter | None:
        managed = self._devices.get_by_stable_id(device_id)
        return None if managed is None else managed.adapter

    def _zone_light(self, device_id: str) -> ZoneLight | None:
        adapter = self._adapter(device_id)
        if adapter is None:
            return None
        return ZoneLight(device_id, adapter.led_count, adapter.capabilities, adapter.geometry)

    def _zone_lights(self, device_ids: Iterable[str]) -> list[ZoneLight]:
        return [light for d in device_ids if (light := self._zone_light(d)) is not None]

    def _latency_s(self, device_id: str) -> float:
        managed = self._devices.get_by_stable_id(device_id)
        return 0.0 if managed is None else managed.tracker.effective_latency_s

    def _lights_of(self, zone: ZoneRecord) -> tuple[str, ...]:
        if not zone.all_lights:
            return zone.lights
        infos = (managed.adapter.device_info for managed in self._devices.devices)
        return tuple(info.stable_id for info in infos if info.stable_id)

    async def _sync(self, device_ids: Iterable[str], power_on: Iterable[str] = ()) -> None:
        """Bring each light in line with the zone that owns it, or release it."""
        wanted = set(power_on)
        if self._preview_only:
            self._deferred_power_on |= wanted  # applied when preview-only is turned off
        ids = list(dict.fromkeys(device_ids))
        results = await asyncio.gather(
            *(self._sync_device(d, d in wanted) for d in ids), return_exceptions=True
        )
        for device_id, result in zip(ids, results, strict=True):
            if isinstance(result, Exception):
                logger.opt(exception=result).warning("Couldn't update light {}", device_id)

    async def _sync_device(self, device_id: str, power_on: bool) -> None:
        zone_id = self.owner_of(device_id)
        adapter = self._adapter(device_id)
        if zone_id is None:
            self._routes.set_route(device_id, None)
            self._applied.pop(device_id, None)
            if adapter is not None and not self._preview_only:
                await self._release(device_id, adapter)
            return
        running = self._running[zone_id]
        runtime = running.runtime
        if runtime is None:  # the saved look can't be read: leave the light alone
            self._routes.set_route(device_id, None)
            return
        if (
            self._preview_only  # frames reach the web preview only
            or runtime.crash is not None  # the light holds the last frame
            or adapter is None
            or not adapter.is_connected  # offline: it rejoins when it's back
        ):
            self._routes.set_route(device_id, runtime.route_for(device_id))
            return
        if device_id not in self._power:
            self._power[device_id] = (await self._read(adapter)).power
        if device_id not in self._captured:
            await self._capture(device_id, adapter)
        if power_on and self._power[device_id] is not True:  # off, or it can't say
            await self._switch_on(device_id, adapter)
        if self._power[device_id] is False:  # switched off elsewhere: out until it's back on
            self._routes.set_route(device_id, None)
            self._applied.pop(device_id, None)
            return
        await self._apply(device_id, adapter, running, runtime)
        self._routes.set_route(device_id, runtime.route_for(device_id))

    async def _apply(
        self, device_id: str, adapter: DeviceAdapter, running: _Running, runtime: ZoneRuntime
    ) -> None:
        """Start the light's firmware layer, or get it ready to stream, once per change."""
        claim = runtime.claim_for(device_id)
        key: AppliedKey = (running.epoch, runtime.generation, claim[0].id if claim else None)
        if self._applied.get(device_id) == key:
            return
        if claim is not None:
            layer, effect = claim
            self._routes.set_route(device_id, runtime.route_for(device_id))  # stop frames first
            try:
                await effect.start(adapter, effect.start_params(runtime.brightness))
            except Exception as exc:  # rejected or no answer: stream a copy (spec §8)
                logger.warning(
                    "{} didn't start {} ({}); streaming a copy instead",
                    adapter.device_info.name,
                    effect.display_name,
                    exc,
                )
                runtime.mark_emulated(device_id)
                claim = None
                key = (running.epoch, runtime.generation, None)
        if claim is None:
            try:
                await adapter.prepare_stream()
            except Exception as exc:
                logger.warning("Couldn't prepare {}: {}", adapter.device_info.name, exc)
        self._applied[device_id] = key

    async def _read(self, adapter: DeviceAdapter) -> LightReading:
        try:
            return await adapter.read_light()
        except Exception as exc:
            logger.warning("Couldn't read {}: {}", adapter.device_info.name, exc)
            return LightReading(power=None, colour=None)

    async def _capture(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Capture a light before dj-ledfx first changes it (spec §4.3)."""
        try:
            state = await adapter.capture_state()
        except Exception as exc:
            logger.warning("Couldn't capture {}: {}", adapter.device_info.name, exc)
            state = None
        if state is None:
            logger.info("{} can't be captured; Off will leave it alone", adapter.device_info.name)
        self._captured[device_id] = state or b""
        await self._db.save_device_state(device_id, state or b"")

    async def _switch_on(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Only ever called for a look being applied (spec §6.4)."""
        try:
            await adapter.set_power(True)
        except Exception as exc:
            logger.warning("Couldn't switch on {}: {}", adapter.device_info.name, exc)
            return
        self._power[device_id] = True

    async def _release(self, device_id: str, adapter: DeviceAdapter) -> None:
        """Put a light back how it was before dj-ledfx took control, once (spec §4.3)."""
        state = self._captured.get(device_id)
        if state is None or not adapter.is_connected:
            return  # nothing to release, or offline: released when it's back
        if state and self._power.get(device_id) is not False:  # never switch a light on
            try:
                await adapter.restore_state(state)
            except Exception as exc:
                logger.warning("Couldn't restore {}: {}", adapter.device_info.name, exc)
                return
            self._power.pop(device_id, None)  # the restore may have switched it off
        del self._captured[device_id]
        await self._db.delete_device_state(device_id)
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/zones -v`
Expected: PASS.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones tests/zone_home.py tests/zones
git commit -m "feat(zones): zone manager with take-over, capture and restore, brightness and restart"
```

---

### Task 17: Zone manager: resume, preview-only, and lights that come and go

The rest of the lifecycle (spec §4.3, §6.4, §8). On start-up the manager replays the saved assignments oldest first, so take-overs come out as they were, and never switches a light on. Preview-only keeps every light as it is and lets the preview carry on; turning it off applies what changed meanwhile, once. The light monitor (Task 19) reports power readings: a light switched off elsewhere drops out of its zone's stream and rejoins when it's back on, and a firmware effect the light stopped is sent again while the light is on. A light that drops out keeps its place in its zone; when it comes back with a different LED count or other capabilities, the zone rebuilds its LED set, and every light in the zone gets its new slice of the new ring. A light seen for the first time joins the newest running all-lights zone.

A saved look that can't be read shows its zone as crashed with the reason, and leaves the zone's lights alone until Restart (which tries the look saved under the same id) or Off (which restores them). A saved look that can be read but not built (a removed effect kind, bad settings) gives a runtime that is crashed from the start, with the layer and the reason.

GhostAdapter keeps the capabilities and geometry the light had when it went offline, so its zone doesn't re-plan firmware claims while it's away and the lights API still shows what it can do.

**Files:**
- Modify: `src/dj_ledfx/zones/model.py` (`PreviewOnlyChanged`)
- Modify: `src/dj_ledfx/zones/manager.py`
- Modify: `src/dj_ledfx/devices/ghost.py`, `src/dj_ledfx/devices/manager.py` (`demote_device`)
- Modify: `tests/zone_home.py` (`Home.restart`)
- Test: `tests/zones/test_manager_lifecycle.py`; modify `tests/devices/test_manager.py`

**Interfaces:**
- Consumes: everything Task 16 produces; `look_from_dict` (Task 11); `ZoneStore.load_assignments`, `delete_assignment` (Task 14); `ZoneRuntime.set_lights`, `lights`, `claim_for`, `crash` (Task 15); `FirmwareEffect.is_running` (Task 3); `DeviceManager.promote_device`, `demote_device`, `add_device`.
- Produces:
  - `zones.model.PreviewOnlyChanged(on: bool)` event
  - `ZoneManager.resume()`, `set_preview_only(on)`, `on_power_reading(device_id, power: bool | None)`, `verify_firmware(device_id)`, `on_device_offline(device_id)`, `on_device_online(device_id)`, `on_device_discovered(device_id)` (all async)
  - `GhostAdapter(device_info, led_count, *, caps: DeviceCapabilities | None = None, geometry: DeviceGeometry | None = None)` with `capabilities` and `geometry`; `DeviceManager.demote_device` passes the old adapter's
  - `tests/zone_home.py`: `Home.restart(*, preview_only=False) -> Home` (clears each light's `calls`, builds the app again on the same `state.db` and lights, awaits `resume()`)

- [ ] **Step 1: Add the event to `src/dj_ledfx/zones/model.py`**

```python
@dataclass(frozen=True, slots=True)
class PreviewOnlyChanged:
    on: bool
```

- [ ] **Step 2: Add `Home.restart` to `tests/zone_home.py`**

Inside `class Home`, after `look()`:

```python
    async def restart(self, *, preview_only: bool = False) -> Home:
        """The app starting again on the same state.db and lights, then resuming."""
        for light in self.lights.values():
            light.calls.clear()
        home = await assemble(self.db, list(self.lights.values()), self.clock, preview_only)
        await home.manager.resume()
        return home
```

- [ ] **Step 3: Write the failing tests**

`tests/zones/test_manager_lifecycle.py`:

```python
from __future__ import annotations

import asyncio
import json

from conftest import FakeLight
from zone_home import BREATHE_AND_GLOW, GLOW, TILE, HomeFactory

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import PreviewOnlyChanged, ZoneRecord

LAMP = DeviceCapabilities(protocol="Govee")
CANDLE = DeviceCapabilities(protocol="LIFX", matrix=True, chain=True)


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


# Review focus 2: a restart while a zone light is switched off elsewhere.
async def test_resume_never_powers_on_and_switched_off_lights_rejoin(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    home = await make_home([a, b], [_zone("z", "a", "b")])
    await home.manager.start("z", home.look("classic-breathe"))
    a.power = False  # switched off at the wall while the app was down

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.lights == ("a", "b") and info.state == "running"
    assert a.calls == []  # not captured again, not switched on
    assert b.names() == ["prepare_stream"]
    assert "a" not in home.routes.routes and home.routes.routes["b"].zone_id == "z"
    assert home.manager.power_of("a") is False

    a.power = True
    await home.manager.on_power_reading("a", True)  # the light monitor sees it back on

    assert a.names() == ["prepare_stream"]
    assert home.routes.routes["a"].zone_id == "z"
    assert home.host.runtimes["z"].leds.count == 8  # it kept its LEDs while it was off


async def test_resume_replays_take_overs_oldest_first(make_home: HomeFactory) -> None:
    a, b, c = FakeLight("a"), FakeLight("b"), FakeLight("c")
    home = await make_home([a, b, c], [_zone("left", "a", "b"), _zone("right", "b", "c")])
    await home.manager.start("left", home.look("classic-breathe"))
    home.clock[0] = home.clock[0].replace(minute=5)
    await home.manager.start("right", home.look("classic-strobe"))

    home = await home.restart()

    assert [(x.zone_id, x.lights) for x in home.manager.running()] == [
        ("left", ("a",)),
        ("right", ("b", "c")),
    ]
    assert home.routes.routes["b"].zone_id == "right"
    assert all("capture" not in light.names() for light in (a, b, c))


# Review focus 3: preview-only toggled around a start and an Off.
async def test_preview_only_defers_power_on_and_restore_until_turned_off(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", power=False, captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")], preview_only=True)
    seen: list[bool] = []
    home.bus.subscribe(PreviewOnlyChanged, lambda event: seen.append(event.on))
    assert home.routes.preview_only

    await home.manager.start("z", home.look("classic-breathe"))

    assert lamp.calls == []
    assert home.routes.routes["lamp"].zone_id == "z"  # the preview still gets frames

    await home.manager.set_preview_only(False)

    assert lamp.names() == ["capture", "power", "prepare_stream"]
    assert not home.routes.preview_only

    await home.manager.set_preview_only(True)
    await home.manager.off("z")
    assert "restore" not in lamp.names()

    await home.manager.set_preview_only(False)
    await home.manager.set_preview_only(True)
    await home.manager.set_preview_only(False)

    assert lamp.calls.count(("restore", b"l0")) == 1
    assert await home.db.load_device_state("lamp") is None
    assert seen == [False, True, False, True, False]


# Review focus 4: a light comes back with a different LED count while its zone runs.
async def test_rejoin_with_new_led_count_rebuilds_routes(make_home: HomeFactory) -> None:
    ghost = FakeLight("candle", led_count=60, connected=False)  # known, not found yet
    lamp = FakeLight("lamp", led_count=3, caps=LAMP)
    home = await make_home([ghost, lamp], [_zone("z", "candle", "lamp")])
    await home.manager.start("z", BREATHE_AND_GLOW)
    runtime = home.host.runtimes["z"]
    assert runtime.leds.count == 63
    assert ghost.calls == []

    candle = FakeLight("candle", led_count=5, caps=CANDLE)
    home.devices.promote_device("candle", candle)
    await home.manager.on_device_online("candle")

    assert home.host.runtimes["z"] is runtime
    assert runtime.leds.count == 8
    candle_route, lamp_route = home.routes.routes["candle"], home.routes.routes["lamp"]
    assert (candle_route.start, candle_route.stop) == (0, 5)
    assert (lamp_route.start, lamp_route.stop) == (5, 8)
    assert candle_route.ring is runtime.ring and lamp_route.ring is runtime.ring
    assert not candle_route.streaming  # the Candle runs Glow itself now
    assert candle.names() == ["capture", "firmware"]  # captured, never switched on
    assert lamp.names() == ["capture", "prepare_stream"]  # from the start; now just a new slice
    runtime.tick(100.0)
    colours = lamp_route.colors_at(100.0, 3)
    assert colours is not None and colours.shape == (3, 3)


# Review focus 5: a saved assignment whose look no longer loads.
async def test_resume_with_broken_look_shows_crashed_and_off_restores(
    make_home: HomeFactory,
) -> None:
    a = FakeLight("a", captured=b"a-before")
    b = FakeLight("b", captured=b"b-before")
    home = await make_home([a, b], [_zone("good", "a"), _zone("bad", "b")])
    await home.manager.start("good", home.look("classic-breathe"))
    await home.manager.start("bad", home.look("classic-strobe"))
    retired = json.loads(look_body(home.look("classic-strobe")))
    retired["layers"][0]["kind"] = "retired_effect"  # an effect this version doesn't have
    await home.db.write(
        "UPDATE zone_assignments SET look=? WHERE zone_id='bad'", (json.dumps(retired),)
    )

    home = await home.restart()

    bad = home.manager.running_info("bad")
    assert bad is not None and bad.state == "crashed"
    assert bad.error is not None and "retired_effect" in bad.error.message
    assert b.calls == []  # a crashed zone leaves its lights alone
    good = home.manager.running_info("good")
    assert good is not None and good.state == "running"
    assert a.names() == ["prepare_stream"]

    await home.manager.off("bad")

    assert b.calls == [("restore", b"b-before")]


async def test_an_unreadable_saved_look_restarts_from_the_look_store(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.db.write("UPDATE zone_assignments SET look='{not json' WHERE zone_id='z'")

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "crashed" and info.look_name == "Breathe"
    assert info.error is not None and "can't be read" in info.error.message
    assert lamp.calls == [] and "lamp" not in home.routes.routes
    assert "z" not in home.host.runtimes

    info = await home.manager.restart("z")

    assert info.state == "running" and info.error is None
    assert lamp.names() == ["prepare_stream"]
    [saved] = await home.store.load_assignments()
    assert json.loads(saved.look_json)["name"] == "Breathe"


async def test_a_light_switched_off_during_a_look_drops_out_and_rejoins(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)

    tile.power = False
    await home.manager.on_power_reading("tile", False)
    assert "tile" not in home.routes.routes
    tile.firmware_running = False
    await home.manager.verify_firmware("tile")  # off: nothing is sent
    assert tile.names() == ["capture", "firmware"]

    tile.power = True
    await home.manager.on_power_reading("tile", True)

    assert tile.names() == ["capture", "firmware", "firmware"]
    assert "power" not in tile.names()
    assert not home.routes.routes["tile"].streaming


async def test_a_stopped_firmware_effect_is_sent_again(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)

    await home.manager.verify_firmware("tile")  # still running: nothing to do
    assert tile.names().count("firmware") == 1

    tile.firmware_running = False  # the LIFX app changed it
    await home.manager.verify_firmware("tile")

    assert tile.names().count("firmware") == 2
    assert tile.firmware_running


async def test_a_light_that_drops_out_rejoins_with_its_effect(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    ring = home.host.runtimes["z"].ring

    home.devices.demote_device("tile")
    await asyncio.sleep(0)  # let the demoted adapter's disconnect run
    await home.manager.on_device_offline("tile")
    await tile.connect()
    home.devices.promote_device("tile", tile)
    await home.manager.on_device_online("tile")

    assert tile.names() == ["capture", "firmware", "firmware"]
    assert home.host.runtimes["z"].ring is ring  # same LEDs: no rebuild


async def test_off_while_a_light_is_offline_restores_it_when_it_is_back(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    home.devices.demote_device("lamp")
    await asyncio.sleep(0)
    await home.manager.on_device_offline("lamp")

    await home.manager.off("z")

    assert "restore" not in lamp.names()
    assert await home.db.load_device_state("lamp") == b"l0"  # kept until it's back

    await lamp.connect()
    home.devices.promote_device("lamp", lamp)
    await home.manager.on_device_online("lamp")

    assert lamp.calls[-1] == ("restore", b"l0")
    assert await home.db.load_device_state("lamp") is None


async def test_a_new_light_joins_the_newest_all_lights_zone(make_home: HomeFactory) -> None:
    a = FakeLight("a")
    everything = ZoneRecord(id="all", name="Everything", all_lights=True)
    home = await make_home([a], [everything, _zone("desk", "a")])
    await home.manager.start("all", home.look("classic-breathe"))

    new = FakeLight("new", power=False)
    home.devices.add_device(new, LatencyTracker(strategy=StaticLatency(20.0)))
    await home.manager.on_device_discovered("new")

    info = home.manager.running_info("all")
    assert info is not None and info.lights == ("a", "new")
    assert new.names() == ["capture"]  # ready for Off, but left switched off
    assert "new" not in home.routes.routes
    assert home.host.runtimes["all"].leds.count == 8
    [saved] = await home.store.load_assignments()
    assert saved.lights == ("a", "new")


async def test_a_new_light_is_left_alone_when_no_all_lights_zone_runs(
    make_home: HomeFactory,
) -> None:
    a = FakeLight("a")
    home = await make_home([a], [_zone("desk", "a")])
    await home.manager.start("desk", home.look("classic-breathe"))

    new = FakeLight("new")
    home.devices.add_device(new, LatencyTracker(strategy=StaticLatency(20.0)))
    await home.manager.on_device_discovered("new")

    assert new.calls == [] and home.manager.owner_of("new") is None
```

In `tests/devices/test_manager.py`, add `from conftest import FakeLight`, `from dj_ledfx.devices.capabilities import DeviceCapabilities` and `from dj_ledfx.spatial.geometry import StripGeometry` to the imports at the top (`GhostAdapter` is already imported further down), and append:

```python
def test_a_demoted_light_keeps_its_capabilities_and_geometry() -> None:
    mgr = DeviceManager(event_bus=EventBus())
    caps = DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True)
    geometry = StripGeometry(direction=(1.0, 0.0, 0.0), length=2.0)
    mgr.add_device(FakeLight("lifx:n1", led_count=40, caps=caps, geometry=geometry), _make_tracker())

    mgr.demote_device("lifx:n1")

    device = mgr.get_by_stable_id("lifx:n1")
    assert device is not None and isinstance(device.adapter, GhostAdapter)
    assert device.adapter.capabilities == caps
    assert device.adapter.geometry == geometry
    assert device.adapter.led_count == 40


def test_a_ghost_without_capabilities_guesses_from_its_type() -> None:
    info = _make_info()
    ghost = GhostAdapter(info, led_count=60)
    assert ghost.capabilities == DeviceCapabilities(protocol="LIFX")
    assert ghost.geometry is None
```

(`demote_device` runs outside an event loop here, so it skips the async disconnect, as `test_demote_device` does; `_make_info()` is a LIFX strip.)

- [ ] **Step 4: Run the tests to see them fail**

Run: `uv run pytest tests/zones/test_manager_lifecycle.py tests/devices/test_manager.py -v`
Expected: FAIL. The lifecycle tests fail with `AttributeError: 'ZoneManager' object has no attribute 'resume'` (or `set_preview_only`, `on_power_reading`, `verify_firmware`, `on_device_offline`, `on_device_discovered`), and `test_a_demoted_light_keeps_its_capabilities_and_geometry` fails its capabilities assertion. `test_a_ghost_without_capabilities_guesses_from_its_type` already passes: it guards the default.

- [ ] **Step 5: Let GhostAdapter keep what the light could do**

In `src/dj_ledfx/devices/ghost.py`, add the imports:

```python
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.spatial.geometry import DeviceGeometry
```

and replace `__init__` and add two properties:

```python
    def __init__(
        self,
        device_info: DeviceInfo,
        led_count: int,
        *,
        caps: DeviceCapabilities | None = None,
        geometry: DeviceGeometry | None = None,
    ) -> None:
        self._device_info = device_info
        self._led_count = led_count
        self._caps = caps
        self._geometry = geometry

    @property
    def capabilities(self) -> DeviceCapabilities:
        """What the light could do when it was last seen, else a guess from its type."""
        return self._caps if self._caps is not None else super().capabilities

    @property
    def geometry(self) -> DeviceGeometry | None:
        return self._geometry
```

In `src/dj_ledfx/devices/manager.py`, `demote_device`, replace `managed.adapter = GhostAdapter(info, led_count=led_count)` with:

```python
        managed.adapter = GhostAdapter(
            info,
            led_count=led_count,
            caps=old_adapter.capabilities,
            geometry=old_adapter.geometry,
        )
```

- [ ] **Step 6: Add the lifecycle to `src/dj_ledfx/zones/manager.py`**

Add `import json` to the imports, `look_from_dict` to the `dj_ledfx.looks.model` import, and `PreviewOnlyChanged` to the `dj_ledfx.zones.model` import. Add these methods to `ZoneManager`, after `restart()`:

```python
    async def resume(self) -> None:
        """Bring back the zones that were running when the app stopped (spec §4.3, §6.4).

        Assignments replay oldest first, so take-overs come out as they were. Lights are
        captured when first reached and never switched on. A captured light that no zone
        owns any more is restored when it's reachable.
        """
        async with self._lock:
            for saved in await self._store.load_assignments():
                zone = self._zones.get(saved.zone_id)
                members = self._lights_of(zone) if zone is not None else ()
                lights = [
                    light
                    for light in saved.lights or members
                    if light in members and self._adapter(light) is not None
                ]
                if not lights:
                    logger.info("Zone {} has none of its lights left; not resuming it", saved.zone_id)
                    await self._store.delete_assignment(saved.zone_id)
                    continue
                await self._take_over(saved.zone_id, lights)
                running = self._resumed(saved, lights)
                self._running[saved.zone_id] = running
                if running.runtime is not None:
                    self._host.add_runtime(running.runtime)
                await self._persist(saved.zone_id)
            await self._sync(self._known_lights())
        self._event_bus.emit(ZonesChanged())

    async def set_preview_only(self, on: bool) -> None:
        """Preview-only: looks run and stream to the web preview; the lights are left alone.

        Turning it off sends the current state to the lights (spec §6.4): lights of zones
        started meanwhile are captured and switched on, lights of zones turned off are
        restored, once.
        """
        async with self._lock:
            if on == self._preview_only:
                return
            self._preview_only = on
            self._routes.set_preview_only(on)
            if not on:
                deferred, self._deferred_power_on = self._deferred_power_on, set()
                await self._sync(self._known_lights(), power_on=deferred)
        self._event_bus.emit(PreviewOnlyChanged(on))

    async def on_power_reading(self, device_id: str, power: bool | None) -> None:
        """The light monitor read a light's power (every 5 s for zone lights).

        A light switched off elsewhere drops out of its zone's stream and rejoins when it's
        switched back on (spec §6.4). This never switches a light on.
        """
        if power is None:
            return
        async with self._lock:
            before = self._power.get(device_id)
            self._power[device_id] = power
            if power != before and self.owner_of(device_id) is not None:
                await self._sync([device_id])

    async def verify_firmware(self, device_id: str) -> None:
        """Send a light's firmware effect again if something stopped it, while it's on."""
        async with self._lock:
            zone_id = self.owner_of(device_id)
            runtime = self._running[zone_id].runtime if zone_id is not None else None
            claim = runtime.claim_for(device_id) if runtime is not None else None
            adapter = self._adapter(device_id)
            if (
                runtime is None
                or claim is None
                or runtime.crash is not None
                or device_id not in self._applied
                or adapter is None
                or not adapter.is_connected
                or self._preview_only
                or self._power.get(device_id) is False
            ):
                return
            effect = claim[1]
            try:
                running = await effect.is_running(adapter)
            except Exception as exc:
                logger.debug("Couldn't ask {} about {}: {}", device_id, effect.display_name, exc)
                return
            if running is False:  # None: the light can't say, so trust it
                logger.info(
                    "{} stopped {}; sending it again", adapter.device_info.name, effect.display_name
                )
                del self._applied[device_id]
                await self._sync([device_id])

    async def on_device_offline(self, device_id: str) -> None:
        """A light dropped out. It keeps its place in its zone until it's back."""
        async with self._lock:
            self._applied.pop(device_id, None)
            self._power.pop(device_id, None)

    async def on_device_online(self, device_id: str) -> None:
        """A known light came back, or was found at start-up. It isn't switched on.

        If it came back with another LED count or other capabilities, its zone rebuilds
        its LED set and every light in the zone gets its slice of the new ring. A captured
        light that no zone owns any more is restored now.
        """
        async with self._lock:
            self._applied.pop(device_id, None)
            self._power.pop(device_id, None)
            zone_id = self.owner_of(device_id)
            running = self._running[zone_id] if zone_id is not None else None
            if running is not None and running.runtime is not None:
                lights = self._zone_lights(running.lights)
                if list(running.runtime.lights) != lights:
                    running.runtime.set_lights(lights)
                    await self._sync(running.lights)
                    return
            await self._sync([device_id])

    async def on_device_discovered(self, device_id: str) -> None:
        """A light seen for the first time joins the newest running all-lights zone."""
        async with self._lock:
            zone_id = self._newest_all_lights_zone()
            if zone_id is None or self.owner_of(device_id) is not None:
                return
            running = self._running[zone_id]
            running.lights.append(device_id)
            if running.runtime is not None:
                running.runtime.set_lights(self._zone_lights(running.lights))
            await self._persist(zone_id)
            await self._sync(running.lights)
        self._event_bus.emit(ZonesChanged())
```

and these helpers, after `_rebuild_broken()`:

```python
    def _resumed(self, saved: Assignment, lights: list[str]) -> _Running:
        """A running zone rebuilt from its saved assignment (spec §8 for bad looks)."""
        running = _Running(
            look_id=saved.look_id,
            look_name=self._look_name(saved.look_id),
            look_json=saved.look_json,
            brightness=saved.brightness,
            since=saved.started_at,
            lights=lights,
            runtime=None,
            epoch=self._next_epoch(),
        )
        try:
            look = replace(look_from_dict(json.loads(saved.look_json)), id=saved.look_id)
        except Exception as exc:  # a bad saved look never stops the app
            logger.error("Zone {}: the saved look can't be read: {}", saved.zone_id, exc)
            running.broken = CrashInfo(
                layer="", message=f"The saved look can't be read: {exc}", at=self._now()
            )
            return running
        running.look_name = look.name
        running.runtime = self._new_runtime(saved.zone_id, look, lights, saved.brightness)
        return running

    def _look_name(self, look_id: str) -> str:
        try:
            return self._looks.get(look_id).name
        except LookNotFoundError:
            return look_id

    def _newest_all_lights_zone(self) -> str | None:
        running = [
            (state.since, zone_id)
            for zone_id, state in self._running.items()
            if self._zones[zone_id].all_lights
        ]
        return max(running)[1] if running else None
```

and, after `_lights_of()`:

```python
    def _known_lights(self) -> list[str]:
        """Every light the app knows, then captured lights no device stands for yet."""
        ids = (managed.adapter.device_info.stable_id for managed in self._devices.devices)
        return list(dict.fromkeys([*(x for x in ids if x), *self._captured]))
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `uv run pytest tests/zones tests/devices/test_manager.py tests/devices/test_ghost.py -v`
Expected: PASS.

- [ ] **Step 8: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones src/dj_ledfx/devices/ghost.py src/dj_ledfx/devices/manager.py tests/zone_home.py tests/zones tests/devices/test_manager.py
git commit -m "feat(zones): resume, preview-only, power readings and lights that come and go"
```

---

### Task 18: Zone manager: groups and the classic effect deck

Custom groups of lights (web spec §11.3, `POST /zones/groups`, `PUT/DELETE /zones/groups/{id}`), and the old UI's effect deck aimed at a zone, so the old UI keeps its effect and parameter controls until F11 (spec §6.5).

Changing a running group's lights works like a start: the group takes the added lights over from other running zones and switches them on, and the lights it lost are restored; it keeps its look, brightness and start time. Deleting a running group turns it off first. Only `kind == "group"` zones can be edited: rooms, sub-zones and the home come from the home map in M2.

The effect deck reads and changes the classic effect a zone plays. New settings for the effect it already plays apply in place (`ZoneRuntime.update_look`), so the effect keeps its phase while a slider moves; another effect starts that effect's classic look on the zone.

**Files:**
- Modify: `src/dj_ledfx/zones/manager.py`
- Test: `tests/zones/test_manager_groups.py`

**Interfaces:**
- Consumes: Task 16 and 17's `ZoneManager`; `new_group_id` (Task 14); `ZoneRuntime.update_look`, `field_effect`, `look` (Task 15); `visible_field_layer`, `validate_look`, `LookNotFoundError`, `LookError` (Task 11); `classic_look_id` (Task 12); `get_strip_effect_classes` (Task 3).
- Produces (all on `ZoneManager`):
  - `async create_group(name: str, lights: Sequence[str]) -> ZoneRecord` (raises `ZoneError`: empty name, no lights, unknown light)
  - `async update_group(zone_id, *, name: str | None = None, lights: Sequence[str] | None = None) -> ZoneRecord` (raises `ZoneNotFoundError`, `ZoneError`)
  - `async delete_group(zone_id) -> None` (raises `ZoneNotFoundError`, `ZoneError`)
  - `classic_layer(zone_id) -> tuple[str, dict[str, Any]] | None`: the classic effect kind a running zone plays and its current settings
  - `async set_classic_effect(zone_id, effect: str | None, params: Mapping[str, Any]) -> tuple[str, dict[str, Any]]` (raises `ZoneNotFoundError`; `ZoneNotRunningError` when `effect` is None and the zone plays no classic effect; `LookNotFoundError` for an unknown effect; `LookError` for bad settings)

- [ ] **Step 1: Write the failing tests**

`tests/zones/test_manager_groups.py`:

```python
from __future__ import annotations

import json

import pytest
from conftest import FakeLight
from zone_home import GLOW, HomeFactory

from dj_ledfx.looks.model import LookError, LookNotFoundError
from dj_ledfx.zones.model import (
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
)


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


async def test_groups_are_created_renamed_and_deleted(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("a"), FakeLight("b")], [])

    group = await home.manager.create_group(" Desk ", ["b", "a", "b"])

    assert group.id.startswith("group-")
    assert (group.name, group.kind, group.lights) == ("Desk", "group", ("b", "a"))
    assert home.manager.get_zone(group.id) == group
    assert await home.store.load_zones() == [group]

    renamed = await home.manager.update_group(group.id, name="Desk lamps")
    assert (renamed.name, renamed.lights) == ("Desk lamps", ("b", "a"))

    await home.manager.delete_group(group.id)
    assert home.manager.zones() == [] and await home.store.load_zones() == []
    assert len(home.changes) == 3


async def test_bad_groups_are_refused(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("a")], [])
    with pytest.raises(ZoneError, match="needs a name"):
        await home.manager.create_group("  ", ["a"])
    with pytest.raises(ZoneError, match="at least one light"):
        await home.manager.create_group("Desk", [])
    with pytest.raises(ZoneError, match="Unknown light 'nope'"):
        await home.manager.create_group("Desk", ["a", "nope"])
    with pytest.raises(ZoneNotFoundError):
        await home.manager.update_group("nope", name="X")
    with pytest.raises(ZoneNotFoundError):
        await home.manager.delete_group("nope")
    assert home.manager.zones() == []


async def test_changing_a_running_group_takes_over_and_releases_lights(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a", captured=b"a0"), FakeLight("b")
    c = FakeLight("c", power=False)
    home = await make_home([a, b, c], [_zone("other", "c")])
    group = await home.manager.create_group("Desk", ["a", "b"])
    await home.manager.start("other", home.look("classic-strobe"))
    await home.manager.start(group.id, home.look("classic-breathe"))
    await home.manager.set_brightness(group.id, 0.5)
    home.clock[0] = home.clock[0].replace(minute=30)

    await home.manager.update_group(group.id, lights=["b", "c"])

    info = home.manager.running_info(group.id)
    assert info is not None and info.lights == ("b", "c")
    assert (info.brightness, info.since.minute) == (0.5, 0)  # same look, same start
    assert home.manager.running_info("other") is None  # it had nothing left
    assert ("restore", b"a0") in a.calls and "a" not in home.routes.routes
    assert c.names().count("capture") == 1  # captured once, by the first zone
    assert home.routes.routes["c"].zone_id == group.id
    [saved] = await home.store.load_assignments()
    assert saved.lights == ("b", "c")


async def test_deleting_a_running_group_turns_it_off_first(make_home: HomeFactory) -> None:
    a = FakeLight("a", captured=b"a0")
    home = await make_home([a], [])
    group = await home.manager.create_group("Desk", ["a"])
    await home.manager.start(group.id, home.look("classic-breathe"))

    await home.manager.delete_group(group.id)

    assert a.calls[-1] == ("restore", b"a0")
    assert home.manager.running() == [] and home.host.runtimes == {}
    assert await home.store.load_assignments() == []


async def test_the_effect_deck_starts_and_tunes_a_zones_classic_effect(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("a")], [_zone("z", "a")])
    assert home.manager.classic_layer("z") is None

    kind, params = await home.manager.set_classic_effect("z", "breathe", {"min_brightness": 0.1})

    assert kind == "breathe" and params["min_brightness"] == 0.1
    info = home.manager.running_info("z")
    assert info is not None and info.look_id == "classic-breathe"
    runtime = home.host.runtimes["z"]
    effect = runtime.field_effect

    kind, params = await home.manager.set_classic_effect("z", None, {"min_brightness": 0.2})

    assert (kind, params["min_brightness"]) == ("breathe", 0.2)
    assert home.host.runtimes["z"] is runtime and runtime.field_effect is effect  # in place
    [saved] = await home.store.load_assignments()
    settings = json.loads(saved.look_json)["layers"][0]["settings"]
    assert settings["min_brightness"] == {"value": 0.2}

    kind, _ = await home.manager.set_classic_effect("z", "strobe", {})

    assert kind == "strobe" and home.host.runtimes["z"] is not runtime
    strobe = home.host.runtimes["z"].field_effect
    assert strobe is not None
    assert home.manager.classic_layer("z") == ("strobe", strobe.get_params())


async def test_the_effect_deck_refuses_what_it_cannot_play(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("a")], [_zone("z", "a")])
    with pytest.raises(ZoneNotRunningError):
        await home.manager.set_classic_effect("z", None, {"min_brightness": 0.2})
    with pytest.raises(LookNotFoundError):
        await home.manager.set_classic_effect("z", "nope", {})
    with pytest.raises(LookError, match="min_brightness"):
        await home.manager.set_classic_effect("z", "breathe", {"min_brightness": 0.9})
    with pytest.raises(ZoneNotFoundError):
        await home.manager.set_classic_effect("nope", "breathe", {})
    assert home.manager.running() == []

    await home.manager.start("z", GLOW)
    assert home.manager.classic_layer("z") is None  # a firmware look has no classic effect
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/zones/test_manager_groups.py -v`
Expected: FAIL with `AttributeError: 'ZoneManager' object has no attribute 'create_group'` (and `set_classic_effect`, `classic_layer`).

- [ ] **Step 3: Add groups and the effect deck to `src/dj_ledfx/zones/manager.py`**

Add to the imports: `Mapping` and `Sequence` to the `collections.abc` import, `Any` to the `typing` import, `from dj_ledfx.effects.registry import get_strip_effect_classes`, `from dj_ledfx.looks.builtin import classic_look_id`, `visible_field_layer` to the `dj_ledfx.looks.model` import, and `from dj_ledfx.zones.store import new_group_id`.

Add this module-level helper above `class ZoneManager`:

```python
def _with_settings(look: Look, changes: Mapping[str, Any]) -> Look:
    """The look with new settings on its visible field layer."""
    field = visible_field_layer(look)
    return replace(
        look,
        layers=tuple(
            replace(layer, settings={**layer.settings, **changes}) if layer is field else layer
            for layer in look.layers
        ),
    )
```

Add these methods to `ZoneManager`, after `on_device_discovered()`:

```python
    # --- groups (web spec §11.3) --------------------------------------------------------

    async def create_group(self, name: str, lights: Sequence[str]) -> ZoneRecord:
        async with self._lock:
            zone = ZoneRecord(
                id=new_group_id(), name=self._group_name(name), lights=self._group_lights(lights)
            )
            await self._store.save_zone(zone)
            self._zones[zone.id] = zone
        self._event_bus.emit(ZonesChanged())
        return zone

    async def update_group(
        self, zone_id: str, *, name: str | None = None, lights: Sequence[str] | None = None
    ) -> ZoneRecord:
        """Rename a group or change its lights. A running group applies the change at once."""
        async with self._lock:
            zone = self._group(zone_id)
            if name is not None:
                zone = replace(zone, name=self._group_name(name))
            if lights is not None:
                zone = replace(zone, lights=self._group_lights(lights), all_lights=False)
            await self._store.save_zone(zone)
            self._zones[zone_id] = zone
            if lights is not None and zone_id in self._running:
                await self._regroup(zone_id, list(zone.lights))
        self._event_bus.emit(ZonesChanged())
        return self.get_zone(zone_id)

    async def delete_group(self, zone_id: str) -> None:
        """Delete a group. A running group is turned off first."""
        async with self._lock:
            self._group(zone_id)
            released = await self._stop(zone_id)
            await self._store.delete_zone(zone_id)
            del self._zones[zone_id]
            await self._sync(released)
        self._event_bus.emit(ZonesChanged())

    def _group(self, zone_id: str) -> ZoneRecord:
        zone = self._zones.get(zone_id)
        if zone is None:
            raise ZoneNotFoundError(zone_id)
        if zone.kind != "group":
            raise ZoneError(f"{zone.name} isn't a group; rooms come from the home map")
        return zone

    @staticmethod
    def _group_name(name: str) -> str:
        if not name.strip():
            raise ZoneError("A group needs a name")
        return name.strip()

    def _group_lights(self, lights: Sequence[str]) -> tuple[str, ...]:
        unique = tuple(dict.fromkeys(lights))
        if not unique:
            raise ZoneError("A group needs at least one light")
        for light in unique:
            if self._adapter(light) is None:
                raise ZoneError(f"Unknown light '{light}'")
        return unique

    async def _regroup(self, zone_id: str, members: list[str]) -> None:
        """A running group's lights changed: take over, apply and release as a start would."""
        running = self._running[zone_id]
        added = [light for light in members if light not in running.lights]
        removed = [light for light in running.lights if light not in members]
        _, touched = await self._take_over(zone_id, added)
        running.lights = members
        if running.runtime is not None:
            running.runtime.set_lights(self._zone_lights(members))
        await self._persist(zone_id)
        await self._sync([*members, *touched, *removed], power_on=added)

    # --- the old UI's effect deck, until F11 ---------------------------------------------

    def classic_layer(self, zone_id: str) -> tuple[str, dict[str, Any]] | None:
        """The classic effect a running zone plays, and its current settings."""
        running = self._running.get(zone_id)
        runtime = running.runtime if running is not None else None
        if runtime is None or runtime.field_effect is None:
            return None
        layer = visible_field_layer(runtime.look)
        if layer is None or layer.kind not in get_strip_effect_classes():
            return None
        return layer.kind, runtime.field_effect.get_params()

    async def set_classic_effect(
        self, zone_id: str, effect: str | None, params: Mapping[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """Tune the classic effect a zone plays in place, or start another one's look."""
        async with self._lock:
            zone = self.get_zone(zone_id)
            current = self.classic_layer(zone_id)
            kind = effect or (current[0] if current is not None else None)
            if kind is None:
                raise ZoneNotRunningError(f"{zone.name} isn't playing a classic effect")
            running = self._running.get(zone_id)
            runtime = running.runtime if running is not None else None
            in_place = current is not None and current[0] == kind
            if in_place and running is not None and runtime is not None:
                look = _with_settings(runtime.look, params)
                validate_look(look)
                runtime.update_look(look)
                running.look_json = look_body(look)
                await self._persist(zone_id)
                await self._sync(running.lights)
        if in_place:
            self._event_bus.emit(ZonesChanged())
        else:
            look = _with_settings(self._looks.get(classic_look_id(kind)), params)
            await self.start(zone_id, look)
        result = self.classic_layer(zone_id)
        if result is None:  # only if the zone was changed meanwhile
            raise ZoneNotRunningError(f"{zone.name} isn't playing a classic effect")
        return result
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/zones -v`
Expected: PASS.

- [ ] **Step 5: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones/manager.py tests/zones/test_manager_groups.py
git commit -m "feat(zones): custom groups and the classic effect deck per zone"
```

---

### Task 19: Light monitor: status, power and colour polling

Light status for the web app (spec §6.3; web spec §9.1, `LightStatus` plus `idle`), and the polling behind the sharing policy (spec §6.4). Zone lights are read every 5 s: their power goes to the zone manager, so a light switched off elsewhere drops out and rejoins when it's back on, and their firmware effects are checked and sent again if something stopped them. Idle lights (in no running zone) are read every 30 s so the web app can show them as they are, and are never changed. A LIFX light that misses three reads in a row is reported offline with a `DeviceOfflineEvent`: a light cut at the wall switch is unreachable, and UDP sends never fail, so nothing else would notice.

Statuses, first match wins: `reconnecting` (the device manager is reconnecting it), `offline` (a ghost, or not connected), `idle` (no running zone owns it), `switched-off` (its zone owns it and its last power reading was off), then the zone manager's mode: `own-effect`, `streamed-copy` or `streaming`. `ownEffect` names the firmware effect a light runs or streams a copy of. `statusSince` moves only when the status changes.

The monitor works its statuses out again after each poll and whenever zones change (`ZonesChanged`); `main` also calls `refresh()` after it promotes or demotes a device (Task 24). It emits `LightsChanged` when anything it reports changed.

**Files:**
- Modify: `src/dj_ledfx/zones/model.py` (`LightsChanged`)
- Create: `src/dj_ledfx/zones/lights.py`
- Test: `tests/zones/test_lights.py`

**Interfaces:**
- Consumes: `ZoneManager.owner_of`, `light_mode`, `effect_name`, `power_of`, `on_power_reading`, `verify_firmware` (Tasks 16 and 17); `DeviceManager.devices`, `ManagedDevice.status`; `DeviceAdapter.read_light`, `capabilities` (Task 2); `DeviceOfflineEvent`, `EventBus`.
- Produces:
  - `zones.model.LightsChanged()` event
  - `zones.lights.LightStatus = Literal["streaming", "own-effect", "streamed-copy", "offline", "switched-off", "reconnecting", "idle"]`
  - `zones.lights.LightState(device_id, status, since: datetime, own_effect: str | None = None, power: bool | None = None, colour: tuple[int, int, int] | None = None)` (frozen)
  - `zones.lights.LightMonitor(*, devices, zones, event_bus, zone_poll_s=5.0, idle_poll_s=30.0, now=<utc now>)`: `states() -> list[LightState]` (device manager order), `state(device_id) -> LightState | None`, `refresh()`, `async poll_zone_lights()`, `async poll_idle_lights()`, `async run()`, `stop()`

- [ ] **Step 1: Add the event to `src/dj_ledfx/zones/model.py`**

```python
@dataclass(frozen=True, slots=True)
class LightsChanged:
    """A light's status, power or colour changed."""
```

- [ ] **Step 2: Write the failing tests**

`tests/zones/test_lights.py`:

```python
from __future__ import annotations

import asyncio
from datetime import timedelta

from conftest import FakeLight
from zone_home import BREATHE_AND_GLOW, GLOW, TILE, Home, HomeFactory

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.events import DeviceOfflineEvent
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.model import LightsChanged, ZoneRecord

LAMP = DeviceCapabilities(protocol="Govee")


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


def _monitor(home: Home, **kwargs: float) -> LightMonitor:
    return LightMonitor(
        devices=home.devices,
        zones=home.manager,
        event_bus=home.bus,
        now=lambda: home.clock[0],
        **kwargs,
    )


def _status(monitor: LightMonitor) -> dict[str, tuple[str, str | None]]:
    return {s.device_id: (s.status, s.own_effect) for s in monitor.states()}


async def test_statuses_follow_zones_power_and_connection(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    lamp = FakeLight("lamp", caps=LAMP)
    bulb = FakeLight("bulb")
    spare = FakeLight("spare", colour=(10, 20, 30))
    gone = FakeLight("gone", connected=False)
    wobbly = FakeLight("wobbly")
    home = await make_home(
        [tile, lamp, bulb, spare, gone, wobbly], [_zone("z", "tile", "lamp", "bulb")]
    )
    monitor = _monitor(home)
    await home.manager.start("z", BREATHE_AND_GLOW)
    managed = home.devices.get_by_stable_id("wobbly")
    assert managed is not None
    managed.status = "reconnecting"
    bulb.power = False

    await monitor.poll_zone_lights()
    await monitor.poll_idle_lights()

    assert _status(monitor) == {
        "tile": ("own-effect", "Glow"),
        "lamp": ("streaming", None),
        "bulb": ("switched-off", None),
        "spare": ("idle", None),
        "gone": ("offline", None),
        "wobbly": ("reconnecting", None),
    }
    idle = monitor.state("spare")
    assert idle is not None and (idle.power, idle.colour) == (True, (10, 20, 30))
    assert spare.calls == []  # idle lights are only read


async def test_a_light_that_cannot_run_the_firmware_look_shows_its_copy(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("lamp", caps=LAMP)], [_zone("z", "lamp")])
    monitor = _monitor(home)

    await home.manager.start("z", GLOW)  # ZonesChanged makes the monitor refresh

    assert _status(monitor) == {"lamp": ("streamed-copy", "Glow")}


async def test_zone_polls_drop_switched_off_lights_and_resend_stopped_effects(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    monitor = _monitor(home)
    await home.manager.start("z", GLOW)

    tile.firmware_running = False  # something else changed the light
    await monitor.poll_zone_lights()
    assert tile.names().count("firmware") == 2

    tile.power = False
    await monitor.poll_zone_lights()
    assert "tile" not in home.routes.routes
    assert _status(monitor) == {"tile": ("switched-off", None)}

    tile.power = True
    await monitor.poll_zone_lights()
    assert _status(monitor) == {"tile": ("own-effect", "Glow")}
    assert "power" not in tile.names()


async def test_status_since_moves_only_when_the_status_changes(make_home: HomeFactory) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    monitor = _monitor(home)
    monitor.refresh()
    first = monitor.state("lamp")
    assert first is not None and first.status == "idle"

    home.clock[0] += timedelta(minutes=1)
    monitor.refresh()
    assert monitor.state("lamp") == first

    home.clock[0] += timedelta(minutes=1)
    await home.manager.start("z", home.look("classic-breathe"))
    started = monitor.state("lamp")
    assert started is not None and started.status == "streaming"
    assert started.since == home.clock[0]


async def test_lights_changed_is_emitted_only_on_change(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [_zone("z", "lamp")])
    monitor = _monitor(home)
    events: list[LightsChanged] = []
    home.bus.subscribe(LightsChanged, events.append)

    monitor.refresh()
    monitor.refresh()
    assert len(events) == 1

    await home.manager.start("z", home.look("classic-breathe"))
    assert len(events) == 2


async def test_a_lifx_light_that_misses_three_polls_is_reported_offline(
    make_home: HomeFactory,
) -> None:
    bulb = FakeLight("bulb")
    lamp = FakeLight("lamp", caps=LAMP, power=None, colour=None)  # Govee that can't say
    home = await make_home([bulb, lamp], [])
    monitor = _monitor(home)
    offline: list[DeviceOfflineEvent] = []
    home.bus.subscribe(DeviceOfflineEvent, offline.append)
    bulb.power, bulb.colour = None, None  # a LIFX light that no longer answers

    for _ in range(2):
        await monitor.poll_idle_lights()
    assert offline == []
    await monitor.poll_idle_lights()

    assert offline == [DeviceOfflineEvent(stable_id="bulb", name="bulb")]


async def test_run_polls_zone_lights_often_and_idle_lights_rarely(
    make_home: HomeFactory,
) -> None:
    a = FakeLight("a")
    spare = FakeLight("spare", colour=(1, 1, 1))
    home = await make_home([a, spare], [_zone("z", "a")])
    await home.manager.start("z", home.look("classic-breathe"))
    monitor = _monitor(home, zone_poll_s=0.01, idle_poll_s=60.0)
    task = asyncio.create_task(monitor.run())
    await asyncio.sleep(0.05)

    a.power = False
    spare.colour = (2, 2, 2)
    await asyncio.sleep(0.05)
    monitor.stop()
    await task

    assert home.manager.power_of("a") is False  # read again within 50 ms
    idle = monitor.state("spare")
    assert idle is not None and idle.colour == (1, 1, 1)  # not read again for 60 s
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/zones/test_lights.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.zones.lights'`.

- [ ] **Step 4: Write `src/dj_ledfx/zones/lights.py`**

```python
"""Light status for the web app, and the polling behind the sharing policy (spec §6.3, §6.4).

Zone lights are read every 5 s: their power goes to the zone manager (a light switched off
elsewhere drops out and rejoins when it's back on) and their firmware effects are checked.
Idle lights are read every 30 s so the web app can show them as they are; they are never
changed. A LIFX light that misses three reads in a row is reported offline: a light cut at
the wall switch is unreachable, and UDP sends never fail.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from loguru import logger

from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.events import DeviceOfflineEvent
from dj_ledfx.zones.model import LightsChanged, ZonesChanged

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
    from dj_ledfx.events import EventBus
    from dj_ledfx.zones.manager import ZoneManager

LightStatus = Literal[
    "streaming", "own-effect", "streamed-copy", "offline", "switched-off", "reconnecting", "idle"
]

ZONE_POLL_S = 5.0
IDLE_POLL_S = 30.0
MISSED_POLLS_OFFLINE = 3
_UNKNOWN = LightReading(power=None, colour=None)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class LightState:
    device_id: str
    status: LightStatus
    since: datetime  # when the light got this status
    own_effect: str | None = None  # the firmware effect it runs, or streams a copy of
    power: bool | None = None  # as last read
    colour: tuple[int, int, int] | None = None  # as last read


class LightMonitor:
    def __init__(
        self,
        *,
        devices: DeviceManager,
        zones: ZoneManager,
        event_bus: EventBus,
        zone_poll_s: float = ZONE_POLL_S,
        idle_poll_s: float = IDLE_POLL_S,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._devices = devices
        self._zones = zones
        self._event_bus = event_bus
        self._zone_poll_s = zone_poll_s
        self._idle_poll_s = idle_poll_s
        self._now = now
        self._states: dict[str, LightState] = {}
        self._readings: dict[str, LightReading] = {}
        self._missed: dict[str, int] = {}
        self._running = False
        event_bus.subscribe(ZonesChanged, lambda _event: self.refresh())

    def states(self) -> list[LightState]:
        return list(self._states.values())

    def state(self, device_id: str) -> LightState | None:
        return self._states.get(device_id)

    def refresh(self) -> None:
        """Work every light's status out again. Emits LightsChanged if anything changed."""
        states: dict[str, LightState] = {}
        for managed in self._devices.devices:
            device_id = managed.adapter.device_info.stable_id
            if not device_id:
                continue
            status, effect = self._status_of(device_id, managed)
            old = self._states.get(device_id)
            reading = self._readings.get(device_id, _UNKNOWN)
            states[device_id] = LightState(
                device_id=device_id,
                status=status,
                since=old.since if old is not None and old.status == status else self._now(),
                own_effect=effect,
                power=reading.power,
                colour=reading.colour,
            )
        changed = states != self._states
        self._states = states
        if changed:
            self._event_bus.emit(LightsChanged())

    async def poll_zone_lights(self) -> None:
        """Read each reachable zone light; its power and firmware go to the zone manager."""
        await asyncio.gather(*(self._poll_zone_light(m) for m in self._reachable(owned=True)))
        self.refresh()

    async def poll_idle_lights(self) -> None:
        """Read each reachable idle light, so the web app shows it as it is."""
        await asyncio.gather(*(self._read(m) for m in self._reachable(owned=False)))
        self.refresh()

    async def run(self) -> None:
        """Poll until stopped: zone lights every 5 s, idle lights every 30 s."""
        self._running = True
        next_idle = 0.0
        while self._running:
            started = time.monotonic()
            try:
                await self.poll_zone_lights()
                if started >= next_idle:
                    next_idle = started + self._idle_poll_s
                    await self.poll_idle_lights()
            except Exception:
                logger.exception("Light poll failed")
            await asyncio.sleep(max(0.0, self._zone_poll_s - (time.monotonic() - started)))

    def stop(self) -> None:
        self._running = False

    def _status_of(
        self, device_id: str, managed: ManagedDevice
    ) -> tuple[LightStatus, str | None]:
        if managed.status == "reconnecting":
            return "reconnecting", None
        if managed.status == "offline" or not managed.adapter.is_connected:
            return "offline", None
        mode = self._zones.light_mode(device_id)
        if mode is None:
            return "idle", None
        if self._zones.power_of(device_id) is False:
            return "switched-off", None
        return mode, self._zones.effect_name(device_id)

    def _reachable(self, *, owned: bool) -> list[ManagedDevice]:
        return [
            managed
            for managed in self._devices.devices
            if managed.status == "online"
            and managed.adapter.is_connected
            and managed.adapter.device_info.stable_id
            and (self._zones.owner_of(managed.adapter.device_info.stable_id) is not None) == owned
        ]

    async def _poll_zone_light(self, managed: ManagedDevice) -> None:
        reading = await self._read(managed)
        device_id = managed.adapter.device_info.effective_id
        await self._zones.on_power_reading(device_id, reading.power)
        await self._zones.verify_firmware(device_id)

    async def _read(self, managed: ManagedDevice) -> LightReading:
        adapter = managed.adapter
        info = adapter.device_info
        try:
            reading = await adapter.read_light()
        except Exception as exc:
            logger.debug("Couldn't read {}: {}", info.name, exc)
            reading = _UNKNOWN
        if reading.power is None and adapter.capabilities.protocol == "LIFX":
            missed = self._missed.get(info.effective_id, 0) + 1
            self._missed[info.effective_id] = missed
            if missed >= MISSED_POLLS_OFFLINE:
                del self._missed[info.effective_id]
                logger.warning("{} stopped answering; it's offline until it's found again", info.name)
                self._event_bus.emit(DeviceOfflineEvent(stable_id=info.effective_id, name=info.name))
            return reading
        self._missed.pop(info.effective_id, None)
        if reading != _UNKNOWN:
            self._readings[info.effective_id] = reading
        return reading
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/zones/test_lights.py -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/zones/model.py src/dj_ledfx/zones/lights.py tests/zones/test_lights.py
git commit -m "feat(zones): light monitor with status, power and colour polling"
```

---

### Task 20: Attention feed

The server-derived attention list (spec §8; web spec §9.5, `AttentionItem`), so every screen agrees. M1's items: a light offline for 2 minutes while it belongs to a running zone (spec §6.4), a zone crashed, a zone slow, and a light dropping more than 5% of its frames for a minute. Inputs arrive in M3 and M7, so there are no input items yet. Switched off elsewhere is never an item. Items are ordered by severity, then newest first. Their text doesn't change while the problem lasts (no live numbers), so the list only changes when a problem starts or ends.

A zone crashes or turns slow inside its runtime, with no command to announce it. `ZoneManager.watch_states()`, called by the feed's 1 Hz update, emits `ZonesChanged` when a running zone's state changed by itself, so the web app's `running` channel shows it too.

`DeviceStats` gains the light's id and its dropped-frame percentage; the scheduler fills both in the cut-over (Task 24).

**Files:**
- Modify: `src/dj_ledfx/zones/model.py` (`AttentionChanged`), `src/dj_ledfx/zones/manager.py` (`watch_states`), `src/dj_ledfx/types.py` (`DeviceStats`)
- Create: `src/dj_ledfx/zones/attention.py`
- Test: `tests/zones/test_attention.py`

**Interfaces:**
- Consumes: `ZoneManager.running`, `get_zone`, `owner_of` (Task 16); `RunningZoneInfo.state`, `error`, `slow_since`, `fps_target` (Task 16); `LightMonitor.states`, `LightState` (Task 19); `DeviceManager.get_by_stable_id`; `ZoneRuntime.tick`, `slow_since` (Task 15).
- Produces:
  - `zones.model.AttentionChanged()` event
  - `ZoneManager.watch_states() -> None`
  - `types.DeviceStats` gains `device_id: str = ""` and `dropped_pct: float = 0.0`
  - `zones.attention.AttentionItem(id, severity: Literal["high", "normal"], kind: Literal["light-offline", "zone-crashed", "zone-slow", "input-disconnected", "input-stale", "frames-dropping"], subject_type: Literal["light", "zone", "input"], subject_id, title, detail, since: datetime, actions: tuple[Literal["restart", "details", "retry", "open"], ...])` (frozen)
  - `zones.attention.AttentionFeed(*, zones, lights, devices, stats: Callable[[], Sequence[DeviceStats]], event_bus, interval_s=1.0, now=<utc now>, tz: tzinfo | None = None)`: `items() -> list[AttentionItem]`, `update()`, `async run()`, `stop()`. `tz=None` formats times in the host's local time zone.

- [ ] **Step 1: Add the event, the stats fields and `watch_states`**

`src/dj_ledfx/zones/model.py`, append:

```python
@dataclass(frozen=True, slots=True)
class AttentionChanged:
    """The attention list changed."""
```

`src/dj_ledfx/types.py`, `DeviceStats`, after `connected`:

```python
    device_id: str = ""  # the light's stable id
    dropped_pct: float = 0.0  # share of frames dropped over the last second, while streaming
```

`src/dj_ledfx/zones/manager.py`: add `ZoneState` to the `dj_ledfx.zones.runtime` import; in `__init__`, after `self._epochs = 0`:

```python
        self._seen_states: dict[str, ZoneState] = {}
```

and add after `restart()`:

```python
    def watch_states(self) -> None:
        """Emit ZonesChanged when a running zone changed state by itself (crashed, slow).

        A zone not seen yet counts as running: every zone starts that way, or its start
        already announced it.
        """
        states = {
            zone_id: self._info(zone_id, running).state
            for zone_id, running in self._running.items()
        }
        changed = any(self._seen_states.get(z, "running") != state for z, state in states.items())
        self._seen_states = states
        if changed:
            self._event_bus.emit(ZonesChanged())
```

- [ ] **Step 2: Write the failing tests**

`tests/zones/test_attention.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, timedelta

from conftest import FakeLight
from zone_home import START, Home, HomeFactory

from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.looks.model import Layer, Look
from dj_ledfx.types import DeviceStats, FloatRGB
from dj_ledfx.zones.attention import AttentionFeed, AttentionItem
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.model import AttentionChanged, ZoneRecord


class Exploding(FieldEffect):
    """A field effect whose every frame raises."""

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        raise RuntimeError("boom")


SPARKS = Look(
    id="sparks",
    name="Sparks",
    category="ambient",
    layers=(Layer(id="f", name="Spark field", type="field", kind="exploding"),),
)


def _zone(zone_id: str, name: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=name, lights=lights)


def _stats(device_id: str, dropped_pct: float) -> DeviceStats:
    return DeviceStats(
        device_name=device_id,
        effective_latency_ms=20.0,
        send_fps=55.0,
        frames_dropped=0,
        device_id=device_id,
        dropped_pct=dropped_pct,
    )


def _feed(
    home: Home, stats: Callable[[], Sequence[DeviceStats]] = list, interval_s: float = 1.0
) -> tuple[LightMonitor, AttentionFeed]:
    monitor = LightMonitor(
        devices=home.devices, zones=home.manager, event_bus=home.bus, now=lambda: home.clock[0]
    )
    feed = AttentionFeed(
        zones=home.manager,
        lights=monitor,
        devices=home.devices,
        stats=stats,
        event_bus=home.bus,
        interval_s=interval_s,
        now=lambda: home.clock[0],
        tz=UTC,
    )
    return monitor, feed


async def test_an_offline_zone_light_needs_attention_after_two_minutes(
    make_home: HomeFactory,
) -> None:
    rope, spare = FakeLight("rope", name="Rope"), FakeLight("spare", name="Spare")
    home = await make_home([rope, spare], [_zone("z", "Living room", "rope")])
    await home.manager.start("z", home.look("classic-breathe"))
    monitor, feed = _feed(home)
    home.devices.demote_device("rope")
    home.devices.demote_device("spare")  # offline too, but in no running zone
    monitor.refresh()

    home.clock[0] += timedelta(minutes=1, seconds=59)
    feed.update()
    assert feed.items() == []

    home.clock[0] += timedelta(seconds=1)
    feed.update()

    assert feed.items() == [
        AttentionItem(
            id="light-offline:rope",
            severity="normal",
            kind="light-offline",
            subject_type="light",
            subject_id="rope",
            title="Rope offline",
            detail="Rope offline since 19:00. It rejoins by itself when it's back.",
            since=START,
            actions=("details",),
        )
    ]


async def test_crashed_zones_come_first_and_slow_zones_after(make_home: HomeFactory) -> None:
    home = await make_home(
        [FakeLight("a"), FakeLight("b"), FakeLight("c")],
        [
            _zone("desk", "Desk", "a"),
            _zone("porch", "Porch lights", "b"),
            _zone("kitchen", "Kitchen", "c"),
        ],
    )
    _, feed = _feed(home)
    for zone_id in ("desk", "porch"):
        await home.manager.start(zone_id, SPARKS)
    await home.manager.start("kitchen", home.look("classic-breathe"))
    home.clock[0] += timedelta(minutes=1)
    home.host.runtimes["desk"].tick(100.0)  # raises: the zone crashes now
    home.clock[0] += timedelta(minutes=1)
    home.host.runtimes["porch"].tick(100.0)
    home.host.runtimes["kitchen"].slow_since = home.clock[0]
    zone_events = len(home.changes)

    feed.update()
    feed.update()

    assert len(home.changes) == zone_events + 1  # the running channel hears about it once
    porch, desk, kitchen = feed.items()
    assert (porch.kind, desk.kind, kitchen.kind) == ("zone-crashed", "zone-crashed", "zone-slow")
    assert (desk.severity, desk.title, desk.actions) == ("high", "Sparks crashed", ("restart", "details"))
    assert desk.detail == "The Desk lights are holding the last frame. Spark field: RuntimeError: boom"
    assert desk.since == START + timedelta(minutes=1)
    assert porch.detail.startswith("Porch lights are holding the last frame.")
    assert (kitchen.severity, kitchen.title, kitchen.subject_id) == (
        "normal",
        "Kitchen is running slow",
        "kitchen",
    )


async def test_a_light_dropping_frames_for_a_minute_needs_attention(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("lamp", name="Lamp")], [])
    stats = [_stats("lamp", 8.0)]
    _, feed = _feed(home, stats=lambda: stats)

    feed.update()
    home.clock[0] += timedelta(seconds=59)
    feed.update()
    assert feed.items() == []

    home.clock[0] += timedelta(seconds=1)
    feed.update()
    [item] = feed.items()
    assert (item.kind, item.title, item.since) == ("frames-dropping", "Lamp is dropping frames", START)

    stats[0] = _stats("lamp", 2.0)
    feed.update()
    assert feed.items() == []


async def test_attention_changed_is_emitted_only_when_the_list_changes(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("lamp")], [])
    stats: list[DeviceStats] = []
    _, feed = _feed(home, stats=lambda: stats)
    events: list[AttentionChanged] = []
    home.bus.subscribe(AttentionChanged, events.append)

    feed.update()
    stats.append(_stats("lamp", 9.0))
    feed.update()  # dropping, but not for a minute yet
    assert events == []

    home.clock[0] += timedelta(minutes=1)
    feed.update()
    feed.update()
    assert len(events) == 1


async def test_run_updates_until_stopped(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [])
    stats = [_stats("lamp", 9.0)]
    _, feed = _feed(home, stats=lambda: stats, interval_s=0.01)
    task = asyncio.create_task(feed.run())
    await asyncio.sleep(0.03)
    home.clock[0] += timedelta(minutes=2)
    await asyncio.sleep(0.03)
    feed.stop()
    await task

    assert [item.kind for item in feed.items()] == ["frames-dropping"]
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/zones/test_attention.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dj_ledfx.zones.attention'`.

- [ ] **Step 4: Write `src/dj_ledfx/zones/attention.py`**

```python
"""The attention list, derived on the server so every screen agrees (spec §8; web §9.5).

M1's items: a zone light offline for 2 minutes, a zone crashed, a zone slow, and a light
dropping more than 5% of its frames for a minute. Input items arrive with the inputs (M3,
M7). Switched off elsewhere is never an item.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from typing import TYPE_CHECKING, Literal

from loguru import logger

from dj_ledfx.zones.model import AttentionChanged

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.events import EventBus
    from dj_ledfx.types import DeviceStats
    from dj_ledfx.zones.lights import LightMonitor
    from dj_ledfx.zones.manager import ZoneManager
    from dj_ledfx.zones.model import RunningZoneInfo

Severity = Literal["high", "normal"]
AttentionKind = Literal[
    "light-offline", "zone-crashed", "zone-slow", "input-disconnected", "input-stale",
    "frames-dropping",
]
SubjectType = Literal["light", "zone", "input"]
AttentionAction = Literal["restart", "details", "retry", "open"]

OFFLINE_AFTER = timedelta(minutes=2)
DROPPING_AFTER = timedelta(minutes=1)
DROPPING_PCT = 5.0


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AttentionItem:
    id: str
    severity: Severity
    kind: AttentionKind
    subject_type: SubjectType
    subject_id: str
    title: str
    detail: str
    since: datetime
    actions: tuple[AttentionAction, ...]


class AttentionFeed:
    def __init__(
        self,
        *,
        zones: ZoneManager,
        lights: LightMonitor,
        devices: DeviceManager,
        stats: Callable[[], Sequence[DeviceStats]],
        event_bus: EventBus,
        interval_s: float = 1.0,
        now: Callable[[], datetime] = _utcnow,
        tz: tzinfo | None = None,
    ) -> None:
        self._zones = zones
        self._lights = lights
        self._devices = devices
        self._stats = stats
        self._event_bus = event_bus
        self._interval_s = interval_s
        self._now = now
        self._tz = tz
        self._items: list[AttentionItem] = []
        self._dropping_since: dict[str, datetime] = {}
        self._running = False

    def items(self) -> list[AttentionItem]:
        return list(self._items)

    def update(self) -> None:
        """Derive the list again. Emits AttentionChanged when it changed."""
        self._zones.watch_states()
        now = self._now()
        items = [*self._offline_lights(now), *self._zone_items(), *self._dropping(now)]
        items.sort(key=lambda item: (item.severity != "high", -item.since.timestamp()))
        if items != self._items:
            self._items = items
            self._event_bus.emit(AttentionChanged())

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                self.update()
            except Exception:
                logger.exception("Attention update failed")
            await asyncio.sleep(self._interval_s)

    def stop(self) -> None:
        self._running = False

    def _name(self, device_id: str) -> str:
        managed = self._devices.get_by_stable_id(device_id)
        return managed.adapter.device_info.name if managed is not None else device_id

    def _offline_lights(self, now: datetime) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for state in self._lights.states():
            if state.status != "offline" or now - state.since < OFFLINE_AFTER:
                continue
            if self._zones.owner_of(state.device_id) is None:
                continue
            name = self._name(state.device_id)
            at = state.since.astimezone(self._tz).strftime("%H:%M")
            items.append(
                AttentionItem(
                    id=f"light-offline:{state.device_id}",
                    severity="normal",
                    kind="light-offline",
                    subject_type="light",
                    subject_id=state.device_id,
                    title=f"{name} offline",
                    detail=f"{name} offline since {at}. It rejoins by itself when it's back.",
                    since=state.since,
                    actions=("details",),
                )
            )
        return items

    def _zone_items(self) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        for info in self._zones.running():
            name = self._zones.get_zone(info.zone_id).name
            if info.state == "crashed":
                items.append(self._crashed(info, name))
            elif info.state == "slow" and info.slow_since is not None:
                items.append(
                    AttentionItem(
                        id=f"zone-slow:{info.zone_id}",
                        severity="normal",
                        kind="zone-slow",
                        subject_type="zone",
                        subject_id=info.zone_id,
                        title=f"{name} is running slow",
                        detail=(
                            f"{info.look_name} can't keep up with {info.fps_target} fps, "
                            "so it runs at a lower frame rate."
                        ),
                        since=info.slow_since,
                        actions=("details",),
                    )
                )
        return items

    @staticmethod
    def _crashed(info: RunningZoneInfo, name: str) -> AttentionItem:
        lights = f"{name} are" if name.lower().endswith("lights") else f"The {name} lights are"
        error = info.error
        reason = ""
        if error is not None:
            reason = f" {error.layer}: {error.message}" if error.layer else f" {error.message}"
        return AttentionItem(
            id=f"zone-crashed:{info.zone_id}",
            severity="high",
            kind="zone-crashed",
            subject_type="zone",
            subject_id=info.zone_id,
            title=f"{info.look_name} crashed",
            detail=f"{lights} holding the last frame.{reason}",
            since=error.at if error is not None else info.since,
            actions=("restart", "details"),
        )

    def _dropping(self, now: datetime) -> list[AttentionItem]:
        items: list[AttentionItem] = []
        dropping: dict[str, datetime] = {}
        for stat in self._stats():
            if not stat.device_id or stat.dropped_pct <= DROPPING_PCT:
                continue
            since = self._dropping_since.get(stat.device_id, now)
            dropping[stat.device_id] = since
            if now - since < DROPPING_AFTER:
                continue
            name = self._name(stat.device_id)
            items.append(
                AttentionItem(
                    id=f"frames-dropping:{stat.device_id}",
                    severity="normal",
                    kind="frames-dropping",
                    subject_type="light",
                    subject_id=stat.device_id,
                    title=f"{name} is dropping frames",
                    detail=f"{name} has dropped more than 5% of its frames for a minute.",
                    since=since,
                    actions=("details",),
                )
            )
        self._dropping_since = dropping
        return items
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/zones -v`
Expected: PASS.

- [ ] **Step 6: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/types.py src/dj_ledfx/zones tests/zones/test_attention.py
git commit -m "feat(zones): attention feed for offline lights, crashed and slow zones, dropped frames"
```

---

### Task 21: Contract models and the looks API

The web app generates its types from FastAPI's OpenAPI schema, so the schema is the contract (spec §9, §10). `web/contract.py` holds Pydantic models named exactly as the contract's types (web spec §12.2): snake_case fields here, camelCase on the wire. This task adds the look types and `/api/looks` (web spec §12.3): list and read looks, save as new ("Mine"), change or delete saved looks (built-ins answer 409), and star any look. The app is created with `separate_input_output_schemas=False`, so each type appears once in the schema under its contract name (`Look`, not `Look-Input` and `Look-Output`).

`create_app` gains four optional parameters now (`look_store`, `zone_manager`, `light_monitor`, `attention_feed`), so the tests' app builder doesn't change again in Tasks 22 and 23. Routers answer 503 while their object is missing. `tests/api_home.py` serves the app over a test home through `httpx.ASGITransport`, so the app, the stores and the test share one event loop.

**Files:**
- Create: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_looks.py`
- Modify: `src/dj_ledfx/web/app.py`, `src/dj_ledfx/web/state.py`
- Create: `tests/api_home.py`
- Test: `tests/web/test_looks_api.py`

**Interfaces:**
- Consumes: `LookStore` (Task 13); `look_to_dict`, `look_from_dict`, `LookError`, `LookNotFoundError`, `BuiltInLookError` (Task 11); `build_home`, `Home` (Task 16); `LightMonitor` (Task 19); `AttentionFeed` (Task 20).
- Produces:
  - `web.contract.ContractModel` (camelCase aliases, `populate_by_name`); `SettingValue`, `SettingSchema`, `Layer` (field `setting_schema`, alias `schema`), `LookModifiers`, `Transition`, `Look`, `Starred`; `look_out(look, starred) -> contract.Look`, `look_in(body: contract.Look) -> looks.model.Look` (raises `LookError`)
  - `web.state.get_looks(request) -> LookStore`, `get_zones(request) -> ZoneManager`, `get_light_monitor(request) -> LightMonitor`, `get_attention(request) -> AttentionFeed` (each raises 503 while missing)
  - `create_app(..., look_store=None, zone_manager=None, light_monitor=None, attention_feed=None)`
  - REST: `GET /api/looks`, `GET /api/looks/{id}`, `POST /api/looks` (201), `PUT /api/looks/{id}` (409 for built-ins), `DELETE /api/looks/{id}` (204; 409 for built-ins), `PUT /api/looks/{id}/starred` `{starred}`
  - `tests/api_home.py`: `Api(home, app, client, monitor, feed, stats)` and `api_home(tmp_path, lights, zones)` (async context manager; closes the database)

- [ ] **Step 1: Write the test app builder**

`tests/api_home.py`:

```python
"""The web app over a test home (zone_home.py), served through httpx's ASGI transport so
the app, the stores and the test share one event loop. Import it from tests/web only:
tests/web/conftest.py skips those tests when the web extra isn't installed."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import httpx
from conftest import FakeLight
from fastapi import FastAPI
from zone_home import Home, build_home

from dj_ledfx.config import AppConfig
from dj_ledfx.types import DeviceStats
from dj_ledfx.web.app import create_app
from dj_ledfx.zones.attention import AttentionFeed
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.model import ZoneRecord


@dataclass
class Api:
    home: Home
    app: FastAPI
    client: httpx.AsyncClient
    monitor: LightMonitor
    feed: AttentionFeed
    stats: list[DeviceStats]  # what the scheduler reports; tests append to it


@asynccontextmanager
async def api_home(
    tmp_path: Path, lights: Sequence[FakeLight], zones: Sequence[ZoneRecord]
) -> AsyncIterator[Api]:
    home = await build_home(tmp_path, lights, zones)
    stats: list[DeviceStats] = []
    monitor = LightMonitor(
        devices=home.devices, zones=home.manager, event_bus=home.bus, now=lambda: home.clock[0]
    )
    feed = AttentionFeed(
        zones=home.manager,
        lights=monitor,
        devices=home.devices,
        stats=lambda: stats,
        event_bus=home.bus,
        now=lambda: home.clock[0],
        tz=UTC,
    )
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=home.devices,
        scheduler=MagicMock(get_device_stats=lambda: stats),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=AppConfig(),
        config_path=None,
        state_db=home.db,
        event_bus=home.bus,
        look_store=home.looks,
        zone_manager=home.manager,
        light_monitor=monitor,
        attention_feed=feed,
    )
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Api(home, app, client, monitor, feed, stats)
    finally:
        await home.db.close()
```

- [ ] **Step 2: Write the failing tests**

`tests/web/test_looks_api.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

BUILT_INS = [
    "firmware",
    "classic-beat-pulse",
    "classic-breathe",
    "classic-color-chase",
    "classic-fire-storm",
    "classic-rainbow-wave",
    "classic-strobe",
]


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a")], []) as api:
        yield api


async def test_looks_come_built_in_first_in_the_contract_shape(api: Api) -> None:
    resp = await api.client.get("/api/looks")

    assert resp.status_code == 200
    looks = resp.json()
    assert [look["id"] for look in looks] == BUILT_INS
    breathe = looks[2]
    assert {key: breathe[key] for key in ("name", "category", "builtIn", "derivedFrom")} == {
        "name": "Breathe",
        "category": "tempo",
        "builtIn": True,
        "derivedFrom": None,
    }
    assert (breathe["scope"], breathe["needs"], breathe["uses"]) == ("any-zone", [], ["tempo"])
    assert breathe["starred"] is False
    assert breathe["modifiers"] == {
        "trailsS": None,
        "downbeatFlash": False,
        "brightnessCap": None,
        "evening": False,
    }
    assert breathe["transition"] == {"kind": "cut", "durationS": 0.0}
    [layer] = breathe["layers"]
    assert (layer["id"], layer["type"], layer["kind"], layer["settings"]) == (
        "strip",
        "field",
        "breathe",
        {},
    )
    assert [entry["key"] for entry in layer["schema"]] == [
        "palette",
        "beats_per_cycle",
        "min_brightness",
    ]
    assert layer["schema"][1] == {
        "key": "beats_per_cycle",
        "label": "Beats per Cycle",
        "unit": None,
        "bindable": False,
        "type": "number",
        "min": 1.0,
        "max": 4.0,
        "step": 0.5,
        "options": None,
    }


async def test_a_look_is_saved_as_new_changed_and_deleted(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["name"] = "Dim breathe"
    draft["derivedFrom"] = "classic-breathe"
    draft["layers"][0]["settings"] = {"min_brightness": {"value": 0.2}}

    created = await api.client.post("/api/looks", json=draft)

    assert created.status_code == 201
    mine = created.json()
    assert mine["id"].startswith("mine-") and mine["builtIn"] is False
    assert (mine["name"], mine["derivedFrom"]) == ("Dim breathe", "classic-breathe")
    assert mine["layers"][0]["settings"] == {"min_brightness": {"value": 0.2, "binding": None}}

    mine["name"] = "Dimmer breathe"
    updated = await api.client.put(f"/api/looks/{mine['id']}", json=mine)
    assert updated.status_code == 200 and updated.json()["name"] == "Dimmer breathe"
    listed = [look["id"] for look in (await api.client.get("/api/looks")).json()]
    assert listed == [*BUILT_INS, mine["id"]]

    assert (await api.client.delete(f"/api/looks/{mine['id']}")).status_code == 204
    assert (await api.client.get(f"/api/looks/{mine['id']}")).status_code == 404


async def test_built_in_looks_are_never_changed(api: Api) -> None:
    breathe = (await api.client.get("/api/looks/classic-breathe")).json()

    resp = await api.client.put("/api/looks/classic-breathe", json=breathe)

    assert resp.status_code == 409
    assert "save your changes as a new look" in resp.json()["detail"]
    assert (await api.client.delete("/api/looks/classic-breathe")).status_code == 409
    assert (await api.client.put("/api/looks/nope", json=breathe)).status_code == 404
    assert (await api.client.delete("/api/looks/nope")).status_code == 404
    assert (await api.client.get("/api/looks/nope")).status_code == 404


async def test_a_look_m1_cannot_run_is_refused_with_the_reason(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["scope"] = "whole-home"

    resp = await api.client.post("/api/looks", json=draft)

    assert resp.status_code == 400 and "M6" in resp.json()["detail"]


async def test_any_look_can_be_starred(api: Api) -> None:
    resp = await api.client.put("/api/looks/classic-strobe/starred", json={"starred": True})

    assert resp.status_code == 200 and resp.json()["starred"] is True
    listed = {look["id"]: look["starred"] for look in (await api.client.get("/api/looks")).json()}
    assert listed["classic-strobe"] is True and listed["classic-breathe"] is False
    resp = await api.client.put("/api/looks/nope/starred", json={"starred": True})
    assert resp.status_code == 404


async def test_the_openapi_schema_uses_the_contract_names(api: Api) -> None:
    schema = (await api.client.get("/openapi.json")).json()["components"]["schemas"]

    names = {"Look", "Layer", "SettingSchema", "SettingValue", "LookModifiers", "Transition"}
    assert names <= set(schema)
    assert {"schema", "settings"} <= set(schema["Layer"]["properties"])
    assert {"builtIn", "derivedFrom", "starred"} <= set(schema["Look"]["properties"])
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv sync --extra web && uv run pytest tests/web/test_looks_api.py -v`
Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'look_store'`.

- [ ] **Step 4: Write `src/dj_ledfx/web/contract.py`**

```python
"""The web app's data contract (web spec §12.2) as Pydantic models.

Fields are snake_case here and camelCase on the wire. Class names are the contract's:
the web app generates its types from the OpenAPI schema (spec §9).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from dj_ledfx.looks import model as looks

InputKind = Literal["tempo", "music", "home-assistant", "sun"]
TransitionKind = Literal["cut", "fade", "wipe", "spread", "dissolve"]


class ContractModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# --- looks -------------------------------------------------------------------------


class SettingValue(ContractModel):
    value: Any
    binding: dict[str, Any] | None = None  # bindings arrive in M7


class SettingSchema(ContractModel):
    key: str
    label: str
    unit: str | None = None
    bindable: bool = False
    type: Literal[
        "number", "colour", "palette", "anchor", "point", "zone", "lights", "range",
        "boolean", "choice",
    ]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None


class Layer(ContractModel):
    id: str
    name: str
    type: Literal["field", "particles", "firmware"]
    kind: str
    visible: bool = True
    blend: Literal["add", "screen", "normal", "multiply", "max"] = "normal"
    opacity: float = 1.0
    settings: dict[str, SettingValue] = Field(default_factory=dict)
    setting_schema: list[SettingSchema] = Field(default_factory=list, alias="schema")
    mask: dict[str, Any] | None = None
    mirror: dict[str, Any] | None = None
    transform: dict[str, Any] | None = None


class LookModifiers(ContractModel):
    trails_s: float | None = None
    downbeat_flash: bool = False
    brightness_cap: float | None = None
    evening: bool = False


class Transition(ContractModel):
    kind: TransitionKind = "cut"
    duration_s: float = 0.0


class Look(ContractModel):
    id: str = ""
    name: str
    category: Literal["ambient", "tempo", "audio", "home", "firmware"]
    built_in: bool = False
    derived_from: str | None = None
    description: str = ""
    thumbnail: str = ""
    scope: Literal["any-zone", "whole-home"] = "any-zone"
    needs: list[InputKind] = Field(default_factory=list)
    uses: list[InputKind] = Field(default_factory=list)
    starred: bool = False
    layers: list[Layer] = Field(default_factory=list)
    modifiers: LookModifiers = Field(default_factory=LookModifiers)
    transition: Transition = Field(default_factory=Transition)


class Starred(ContractModel):
    starred: bool


def look_out(look: looks.Look, starred: bool) -> Look:
    return Look.model_validate(looks.look_to_dict(look, starred=starred))


def look_in(body: Look) -> looks.Look:
    """The look a request describes. Raises LookError when M1 can't read it."""
    return looks.look_from_dict(body.model_dump(by_alias=True))
```

- [ ] **Step 5: Add the state helpers to `src/dj_ledfx/web/state.py`**

Change the `typing` import to `from typing import TYPE_CHECKING, Any, cast`, add to the `TYPE_CHECKING` block:

```python
    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.zones.attention import AttentionFeed
    from dj_ledfx.zones.lights import LightMonitor
    from dj_ledfx.zones.manager import ZoneManager
```

and append:

```python
def _required(request: Request, name: str, what: str) -> Any:
    from fastapi import HTTPException

    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(503, f"{what} aren't available")
    return value


def get_looks(request: Request) -> LookStore:
    return cast("LookStore", _required(request, "look_store", "Looks"))


def get_zones(request: Request) -> ZoneManager:
    return cast("ZoneManager", _required(request, "zone_manager", "Zones"))


def get_light_monitor(request: Request) -> LightMonitor:
    return cast("LightMonitor", _required(request, "light_monitor", "Light statuses"))


def get_attention(request: Request) -> AttentionFeed:
    return cast("AttentionFeed", _required(request, "attention_feed", "Attention items"))
```

- [ ] **Step 6: Write `src/dj_ledfx/web/router_looks.py`**

```python
"""Looks: built-in and saved ("Mine"), with stars (web spec §12.3)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from dj_ledfx.looks.model import BuiltInLookError, LookError, LookNotFoundError
from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_looks

router = APIRouter()


def _not_found(look_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"No look '{look_id}'")


@router.get("/looks")
async def list_looks(request: Request) -> list[api.Look]:
    store = get_looks(request)
    return [api.look_out(look, store.is_starred(look.id)) for look in store.looks()]


@router.get("/looks/{look_id}")
async def get_look(request: Request, look_id: str) -> api.Look:
    store = get_looks(request)
    try:
        look = store.get(look_id)
    except LookNotFoundError:
        raise _not_found(look_id) from None
    return api.look_out(look, store.is_starred(look_id))


@router.post("/looks", status_code=201)
async def create_look(request: Request, body: api.Look) -> api.Look:
    """Save a look as a new one ("Mine"). Built-ins are never overwritten."""
    store = get_looks(request)
    try:
        look = await store.create(api.look_in(body))
    except LookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api.look_out(look, starred=False)


@router.put("/looks/{look_id}")
async def update_look(request: Request, look_id: str, body: api.Look) -> api.Look:
    store = get_looks(request)
    try:
        look = await store.update(look_id, api.look_in(body))
    except LookNotFoundError:
        raise _not_found(look_id) from None
    except BuiltInLookError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api.look_out(look, store.is_starred(look_id))


@router.delete("/looks/{look_id}", status_code=204)
async def delete_look(request: Request, look_id: str) -> Response:
    store = get_looks(request)
    try:
        await store.delete(look_id)
    except LookNotFoundError:
        raise _not_found(look_id) from None
    except BuiltInLookError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.put("/looks/{look_id}/starred")
async def set_starred(request: Request, look_id: str, body: api.Starred) -> api.Look:
    store = get_looks(request)
    try:
        await store.set_starred(look_id, body.starred)
    except LookNotFoundError:
        raise _not_found(look_id) from None
    return api.look_out(store.get(look_id), body.starred)
```

- [ ] **Step 7: Wire the router and the new parameters into `src/dj_ledfx/web/app.py`**

Add to the `TYPE_CHECKING` block:

```python
    from dj_ledfx.looks.store import LookStore
    from dj_ledfx.zones.attention import AttentionFeed
    from dj_ledfx.zones.lights import LightMonitor
    from dj_ledfx.zones.manager import ZoneManager
```

Add these keyword parameters at the end of `create_app`'s signature (after `pipeline_manager`, or after whatever parameter is last):

```python
    look_store: LookStore | None = None,
    zone_manager: ZoneManager | None = None,
    light_monitor: LightMonitor | None = None,
    attention_feed: AttentionFeed | None = None,
```

Replace `app = FastAPI(title="dj-ledfx")` with:

```python
    # One schema per type, under the contract's name (not Look-Input / Look-Output).
    app = FastAPI(title="dj-ledfx", separate_input_output_schemas=False)
```

After `app.state.pipeline_manager = pipeline_manager`:

```python
    app.state.look_store = look_store
    app.state.zone_manager = zone_manager
    app.state.light_monitor = light_monitor
    app.state.attention_feed = attention_feed
```

and with the other router imports and `include_router` calls:

```python
    from dj_ledfx.web.router_looks import router as looks_router

    app.include_router(looks_router, prefix="/api")
```

Keep the new `include_router` calls before the static-file block, so the SPA fallback (and the `/next` routes, if F0 has landed) stay last.

- [ ] **Step 8: Run the tests to see them pass**

Run: `uv run pytest tests/web -v`
Expected: PASS, including the existing web tests.

- [ ] **Step 9: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/web tests/api_home.py tests/web/test_looks_api.py
git commit -m "feat(web): contract models and the looks API"
```

---

### Task 22: Zones and running API, the `running` channel, and the preview-only switch

The zone endpoints of web spec §12.3: list zones, edit groups, list running zones, start a look (a saved look by id, or an unsaved draft), brightness, Off, Restart and Stop all. A start answers the running zone plus the take-overs it caused, so the UI can say what it took over (web spec §11.3). Rooms, overlays and transitions arrive later (M2, M6, M4), so `covers` and `overlays` are empty and `transition` is null; the contract keeps their shapes so the web app's generated types don't change.

The WebSocket gets its first pushed channel, `running` (web spec §12.4). One broadcaster task per app turns events into channel pushes: an event marks its channel stale, and changes that arrive while a push goes out coalesce into one push. A client that connects gets every pushed channel's current state first. Tasks 23 and 24 add the `lights`, `attention` and `transport` channels to the same two tables.

Preview only becomes a config value, `engine.preview_only` (web spec §12.1 "Config: + preview only"), applied at once through `PUT /config`. That endpoint also stops dropping the `[discovery]` section: `_merge_config` rebuilt `AppConfig` without it, so every config save reset discovery to its defaults and wrote them to `state.db`. The old UI's preview-only switch (Task 26) goes through this endpoint, so the bug would now bite on every toggle.

**Files:**
- Modify: `src/dj_ledfx/config.py` (`EngineConfig.preview_only`)
- Modify: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_config.py`, `src/dj_ledfx/web/ws.py`, `src/dj_ledfx/web/app.py`
- Create: `src/dj_ledfx/web/errors.py`, `src/dj_ledfx/web/router_zones.py`
- Test: `tests/web/test_zones_api.py`, `tests/web/test_ws_channels.py`, `tests/web/test_preview_only_config.py`

**Interfaces:**
- Consumes: `ZoneManager` queries and commands (Tasks 16–18), `ZoneManager.set_preview_only` (Task 17); `RunningZoneInfo`, `StartResult`, `TakeOver`, `ZonesChanged`, `ZoneRecord` and the zone errors (Tasks 14 and 16); `LookStore.get`, `LookError`, `LookNotFoundError` (Tasks 11 and 13); `contract.ContractModel`, `Look`, `Transition`, `InputKind`, `TransitionKind`, `look_in`, `get_looks`, `get_zones`, `api_home` (Task 21).
- Produces:
  - `config.EngineConfig.preview_only: bool = False`
  - `web.contract`: `Zone`, `RunningZoneTransition`, `RunningZoneFps`, `RunningZoneError`, `RunningZone`, `Overlay`, `Running`, `TakeOver`, `StartRequest`, `StartResponse`, `Brightness`, `CreateGroup`, `UpdateGroup`; `zone_out(zone)`, `running_zone_out(info)`, `running_out(infos)`, `start_out(result)`
  - `web.errors.answers()`: a context manager that turns `ZoneNotFoundError` and `LookNotFoundError` into 404, `ZoneNotRunningError` into 409, and any other `ZoneError` or `LookError` into 400, with the reason as `detail` (the effects router reuses it in Task 24)
  - REST: `GET /api/zones`, `POST /api/zones/groups` (201), `PUT /api/zones/groups/{id}`, `DELETE /api/zones/groups/{id}` (204), `GET /api/running`, `POST /api/zones/{id}/start`, `PUT /api/zones/{id}/brightness`, `POST /api/zones/{id}/off` (204), `POST /api/zones/{id}/restart`, `POST /api/running/stop-all` (204). Errors: unknown zone or look 404, zone not running 409, anything else the zone or look refuses 400, with the reason in `detail`.
  - `web.ws`: `_SNAPSHOTS` (channel → snapshot function) and `_STALE_ON` (event type → channel), `initial_messages(app) -> list[dict]`, `async event_broadcast(app)`; WS message `{"channel": "running", "zones": RunningZone[], "overlays": Overlay[]}`
  - `PUT /api/config`: `engine.preview_only` must be a boolean (400 otherwise), applies at once, and `X-Requires-Restart` is `"false"` when nothing else changed; `POST /api/config/import` applies it the same way

- [ ] **Step 1: Write the failing tests**

`tests/web/test_zones_api.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.zones.model import ZoneRecord

ZONES = [
    ZoneRecord(id="desk", name="Desk", lights=("a", "b")),
    ZoneRecord(id="left", name="Left", lights=("a",)),
    ZoneRecord(id="all", name="All lights", all_lights=True),
]


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a"), FakeLight("b")], ZONES) as api:
        yield api


async def test_zones_list_every_zone_with_its_lights(api: Api) -> None:
    resp = await api.client.get("/api/zones")

    assert resp.status_code == 200
    assert resp.json() == [
        {"id": "desk", "name": "Desk", "kind": "group", "lights": ["a", "b"]},
        {"id": "left", "name": "Left", "kind": "group", "lights": ["a"]},
        {"id": "all", "name": "All lights", "kind": "group", "lights": ["a", "b"]},
    ]


async def test_a_start_answers_the_running_zone_and_its_take_overs(api: Api) -> None:
    first = await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    assert first.status_code == 200
    assert first.json() == {
        "zoneId": "desk",
        "lookId": "classic-breathe",
        "lookName": "Breathe",
        "since": "2026-09-24T19:00:00Z",
        "brightness": 1.0,
        "lights": ["a", "b"],
        "covers": [],
        "state": "running",
        "transition": None,
        "fps": {"actual": 0.0, "target": 60},
        "error": None,
        "waitingFor": None,
        "takeOvers": [],
    }

    second = await api.client.post("/api/zones/left/start", json={"lookId": "classic-strobe"})

    assert second.json()["takeOvers"] == [
        {
            "zoneId": "desk",
            "zoneName": "Desk",
            "lookName": "Breathe",
            "lights": ["a"],
            "stopped": False,
        }
    ]
    running = (await api.client.get("/api/running")).json()
    assert [(zone["zoneId"], zone["lights"]) for zone in running["zones"]] == [
        ("desk", ["b"]),
        ("left", ["a"]),
    ]
    assert running["overlays"] == []


async def test_a_draft_look_runs_without_being_saved(api: Api) -> None:
    draft = (await api.client.get("/api/looks/classic-breathe")).json()
    draft["id"] = ""
    draft["name"] = "Slow breathe"

    resp = await api.client.post("/api/zones/desk/start", json={"look": draft})

    assert resp.status_code == 200
    assert (resp.json()["lookId"], resp.json()["lookName"]) == ("draft", "Slow breathe")
    saved = [look["id"] for look in (await api.client.get("/api/looks")).json()]
    assert "draft" not in saved


async def test_bad_starts_are_refused_with_the_reason(api: Api) -> None:
    breathe = (await api.client.get("/api/looks/classic-breathe")).json()
    start = "/api/zones/desk/start"

    both = await api.client.post(start, json={"lookId": "classic-breathe", "look": breathe})
    neither = await api.client.post(start, json={})
    no_zone = await api.client.post("/api/zones/nope/start", json={"lookId": "classic-breathe"})
    no_look = await api.client.post(start, json={"lookId": "nope"})
    too_big = await api.client.post(start, json={"look": {**breathe, "scope": "whole-home"}})

    codes = [resp.status_code for resp in (both, neither, no_zone, no_look, too_big)]
    assert codes == [400, 400, 404, 404, 400]
    assert both.json()["detail"] == "Send either lookId or look"
    assert no_zone.json()["detail"] == "No zone 'nope'"
    assert no_look.json()["detail"] == "No look 'nope'"
    assert "M6" in too_big.json()["detail"]


async def test_brightness_restart_off_and_stop_all(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    dim = await api.client.put("/api/zones/desk/brightness", json={"value": 0.5})
    too_bright = await api.client.put("/api/zones/desk/brightness", json={"value": 2})
    restarted = await api.client.post("/api/zones/desk/restart")

    assert (dim.status_code, dim.json()["brightness"]) == (200, 0.5)
    assert too_bright.status_code == 400
    assert (restarted.status_code, restarted.json()["state"]) == (200, "running")

    assert (await api.client.post("/api/zones/desk/off")).status_code == 204
    assert (await api.client.post("/api/zones/desk/off")).status_code == 204  # idempotent
    assert (await api.client.post("/api/zones/nope/off")).status_code == 404
    not_running = await api.client.post("/api/zones/desk/restart")
    assert (not_running.status_code, not_running.json()["detail"]) == (409, "Desk isn't running")

    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    assert (await api.client.post("/api/running/stop-all")).status_code == 204
    assert (await api.client.get("/api/running")).json() == {"zones": [], "overlays": []}
    assert api.home.lights["b"].names()[-1] == "restore"


async def test_groups_are_created_changed_and_deleted(api: Api) -> None:
    created = await api.client.post("/api/zones/groups", json={"name": "Shelf", "lights": ["b", "a"]})

    assert created.status_code == 201
    group = created.json()
    assert group["id"].startswith("group-")
    assert (group["name"], group["kind"], group["lights"]) == ("Shelf", "group", ["b", "a"])

    url = f"/api/zones/groups/{group['id']}"
    renamed = await api.client.put(url, json={"name": "Shelves"})
    unknown = await api.client.put(url, json={"lights": ["zzz"]})

    assert (renamed.status_code, renamed.json()["name"]) == (200, "Shelves")
    assert (unknown.status_code, unknown.json()["detail"]) == (400, "Unknown light 'zzz'")
    assert (await api.client.delete(url)).status_code == 204
    assert (await api.client.delete(url)).status_code == 404
    zone_ids = [zone["id"] for zone in (await api.client.get("/api/zones")).json()]
    assert group["id"] not in zone_ids


async def test_the_openapi_schema_uses_the_contract_names(api: Api) -> None:
    schema = (await api.client.get("/openapi.json")).json()["components"]["schemas"]

    assert {"Zone", "RunningZone", "Running", "Overlay", "TakeOver", "StartRequest"} <= set(schema)
    assert {"zoneId", "lookName", "covers", "waitingFor"} <= set(
        schema["RunningZone"]["properties"]
    )
```

`tests/web/test_ws_channels.py`:

```python
"""Pushed WebSocket channels (web spec §12.4): the current state on connect, then changes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.web.ws import event_broadcast, initial_messages
from dj_ledfx.zones.model import ZoneRecord, ZonesChanged


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))

    def on(self, channel: str) -> list[dict[str, Any]]:
        return [message for message in self.messages if message["channel"] == channel]


async def until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(1.0):
        while not condition():
            await asyncio.sleep(0.01)


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("a",))]
    async with api_home(tmp_path, [FakeLight("a")], zones) as api:
        yield api


@pytest_asyncio.fixture
async def socket(api: Api) -> AsyncIterator[FakeSocket]:
    """A connected client, with the app's event broadcaster running."""
    fake = FakeSocket()
    api.app.state.connected_websockets.add(fake)
    task = asyncio.create_task(event_broadcast(api.app))
    await asyncio.sleep(0)  # let it subscribe
    yield fake
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_running_zones_are_pushed_when_they_change(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    await until(lambda: bool(socket.on("running")))

    [message] = socket.on("running")
    assert [zone["zoneId"] for zone in message["zones"]] == ["desk"]
    assert message["zones"][0]["lookName"] == "Breathe"
    assert message["overlays"] == []


async def test_changes_that_arrive_together_are_pushed_once(api: Api, socket: FakeSocket) -> None:
    api.home.bus.emit(ZonesChanged())
    api.home.bus.emit(ZonesChanged())
    await until(lambda: bool(socket.on("running")))
    await asyncio.sleep(0.05)

    assert len(socket.on("running")) == 1


async def test_a_client_that_connects_gets_the_current_state(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    messages = {message["channel"]: message for message in initial_messages(api.app)}

    assert [zone["zoneId"] for zone in messages["running"]["zones"]] == ["desk"]
```

`tests/web/test_preview_only_config.py`:

```python
"""Preview only is a config value the zone manager applies at once (spec §6.4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.config import AppConfig, DiscoveryConfig


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a")], []) as api:
        yield api


async def test_preview_only_applies_without_a_restart(api: Api) -> None:
    resp = await api.client.put("/api/config", json={"engine": {"preview_only": True}})

    assert resp.status_code == 200
    assert resp.headers["X-Requires-Restart"] == "false"
    assert api.home.manager.preview_only and api.home.routes.preview_only
    assert (await api.client.get("/api/config")).json()["engine"]["preview_only"] is True
    assert (await api.home.db.load_config("engine"))["preview_only"] == "true"


async def test_preview_only_must_be_true_or_false(api: Api) -> None:
    resp = await api.client.put("/api/config", json={"engine": {"preview_only": "yes"}})

    assert resp.status_code == 400
    assert api.home.manager.preview_only is False


async def test_other_changes_need_a_restart_and_keep_every_section(api: Api) -> None:
    api.app.state.config = AppConfig(discovery=DiscoveryConfig(subnet_mask=16))

    resp = await api.client.put("/api/config", json={"engine": {"fps": 30}})

    assert resp.headers["X-Requires-Restart"] == "true"
    assert resp.json()["discovery"]["subnet_mask"] == 16
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/web/test_zones_api.py tests/web/test_ws_channels.py tests/web/test_preview_only_config.py -v`
Expected: FAIL: `ImportError: cannot import name 'event_broadcast'`, 404 for the zone routes, and `KeyError: 'preview_only'`.

- [ ] **Step 3: Add the config value**

In `src/dj_ledfx/config.py`, add to `EngineConfig`:

```python
    # Looks run and show in the web app; the lights are left alone (spec §6.4).
    preview_only: bool = False
```

- [ ] **Step 4: Add the zone types to `src/dj_ledfx/web/contract.py`**

Add `from collections.abc import Iterable` and `from datetime import datetime` to the imports (at runtime, not under `TYPE_CHECKING`: Pydantic resolves the annotations), and:

```python
from dj_ledfx.zones.model import RunningZoneInfo, StartResult, ZoneRecord
```

Append:

```python
# --- zones -------------------------------------------------------------------------


class Zone(ContractModel):
    id: str
    name: str
    kind: Literal["home", "room", "sub-zone", "group"]
    lights: list[str]


class RunningZoneTransition(ContractModel):
    from_: str = Field(alias="from")
    kind: TransitionKind
    progress: float


class RunningZoneFps(ContractModel):
    actual: float
    target: int


class RunningZoneError(ContractModel):
    layer: str
    message: str
    at: datetime


class RunningZone(ContractModel):
    zone_id: str
    look_id: str
    look_name: str
    since: datetime
    brightness: float
    lights: list[str]  # the lights it owns after take-overs
    covers: list[str] = Field(default_factory=list)  # rooms come with the home map (M2)
    state: Literal["running", "transition", "slow", "crashed", "waiting"]
    transition: RunningZoneTransition | None = None  # transitions arrive in M4
    fps: RunningZoneFps | None = None
    error: RunningZoneError | None = None
    waiting_for: list[InputKind] | None = None


class Overlay(ContractModel):
    look_id: str
    name: str
    trigger: str
    ends_at: datetime
    progress: float


class Running(ContractModel):
    zones: list[RunningZone]
    overlays: list[Overlay] = Field(default_factory=list)  # overlays arrive in M6


class TakeOver(ContractModel):
    zone_id: str
    zone_name: str
    look_name: str
    lights: list[str]  # the lights it lost
    stopped: bool  # it had none left, so it stopped


class StartRequest(ContractModel):
    look_id: str | None = None
    look: Look | None = None  # an unsaved draft
    transition: Transition | None = None  # accepted; M1 plays every transition as a cut


class StartResponse(RunningZone):
    take_overs: list[TakeOver] = Field(default_factory=list)


class Brightness(ContractModel):
    value: float


class CreateGroup(ContractModel):
    name: str
    lights: list[str]


class UpdateGroup(ContractModel):
    name: str | None = None
    lights: list[str] | None = None


def zone_out(zone: ZoneRecord) -> Zone:
    return Zone(id=zone.id, name=zone.name, kind=zone.kind, lights=list(zone.lights))


def _running_fields(info: RunningZoneInfo) -> dict[str, Any]:
    fps = None
    if info.fps_actual is not None and info.fps_target is not None:
        fps = {"actual": round(info.fps_actual, 1), "target": info.fps_target}
    error = None
    if info.error is not None:
        error = {"layer": info.error.layer, "message": info.error.message, "at": info.error.at}
    return {
        "zone_id": info.zone_id,
        "look_id": info.look_id,
        "look_name": info.look_name,
        "since": info.since,
        "brightness": info.brightness,
        "lights": list(info.lights),
        "state": info.state,
        "fps": fps,
        "error": error,
        "waiting_for": list(info.waiting_for) or None,
    }


def running_zone_out(info: RunningZoneInfo) -> RunningZone:
    return RunningZone.model_validate(_running_fields(info))


def running_out(infos: Iterable[RunningZoneInfo]) -> Running:
    return Running(zones=[running_zone_out(info) for info in infos])


def start_out(result: StartResult) -> StartResponse:
    take_overs = [
        {
            "zone_id": take_over.zone_id,
            "zone_name": take_over.zone_name,
            "look_name": take_over.look_name,
            "lights": list(take_over.lights),
            "stopped": take_over.stopped,
        }
        for take_over in result.take_overs
    ]
    fields = {**_running_fields(result.running), "take_overs": take_overs}
    return StartResponse.model_validate(fields)
```

- [ ] **Step 5: Write `src/dj_ledfx/web/errors.py` and `src/dj_ledfx/web/router_zones.py`**

`src/dj_ledfx/web/errors.py`:

```python
"""Zone and look errors as HTTP answers, with the reason for the web app to show."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from dj_ledfx.looks.model import LookError, LookNotFoundError
from dj_ledfx.zones.model import ZoneError, ZoneNotFoundError, ZoneNotRunningError


@contextmanager
def answers() -> Iterator[None]:
    try:
        yield
    except ZoneNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No zone '{exc.args[0]}'") from exc
    except LookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No look '{exc.args[0]}'") from exc
    except ZoneNotRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ZoneError, LookError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

`src/dj_ledfx/web/router_zones.py`:

```python
"""Zones, running zones and groups (web spec §11.3, §12.3)."""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, HTTPException, Request, Response

from dj_ledfx.web import contract as api
from dj_ledfx.web.errors import answers
from dj_ledfx.web.state import get_looks, get_zones

router = APIRouter()


@router.get("/zones")
async def list_zones(request: Request) -> list[api.Zone]:
    return [api.zone_out(zone) for zone in get_zones(request).zones()]


@router.post("/zones/groups", status_code=201)
async def create_group(request: Request, body: api.CreateGroup) -> api.Zone:
    with answers():
        zone = await get_zones(request).create_group(body.name, body.lights)
    return api.zone_out(zone)


@router.put("/zones/groups/{zone_id}")
async def update_group(request: Request, zone_id: str, body: api.UpdateGroup) -> api.Zone:
    with answers():
        zone = await get_zones(request).update_group(zone_id, name=body.name, lights=body.lights)
    return api.zone_out(zone)


@router.delete("/zones/groups/{zone_id}", status_code=204)
async def delete_group(request: Request, zone_id: str) -> Response:
    """Delete a group. A running group is turned off first."""
    with answers():
        await get_zones(request).delete_group(zone_id)
    return Response(status_code=204)


@router.get("/running")
async def list_running(request: Request) -> api.Running:
    return api.running_out(get_zones(request).running())


@router.post("/zones/{zone_id}/start")
async def start_zone(request: Request, zone_id: str, body: api.StartRequest) -> api.StartResponse:
    """Put a look on a zone: a saved look by id, or an unsaved draft."""
    with answers():
        if body.look_id is not None and body.look is None:
            look = get_looks(request).get(body.look_id)
        elif body.look is not None and body.look_id is None:
            look = api.look_in(body.look)
            if not look.id:
                look = replace(look, id="draft")
        else:
            raise HTTPException(status_code=400, detail="Send either lookId or look")
        result = await get_zones(request).start(zone_id, look)
    return api.start_out(result)


@router.put("/zones/{zone_id}/brightness")
async def set_brightness(request: Request, zone_id: str, body: api.Brightness) -> api.RunningZone:
    with answers():
        info = await get_zones(request).set_brightness(zone_id, body.value)
    return api.running_zone_out(info)


@router.post("/zones/{zone_id}/off", status_code=204)
async def turn_off(request: Request, zone_id: str) -> Response:
    """Stop the zone's look and put its lights back how they were. Idempotent."""
    with answers():
        await get_zones(request).off(zone_id)
    return Response(status_code=204)


@router.post("/zones/{zone_id}/restart")
async def restart_zone(request: Request, zone_id: str) -> api.RunningZone:
    with answers():
        info = await get_zones(request).restart(zone_id)
    return api.running_zone_out(info)


@router.post("/running/stop-all", status_code=204)
async def stop_all(request: Request) -> Response:
    await get_zones(request).stop_all()
    return Response(status_code=204)
```

- [ ] **Step 6: Apply preview only through `src/dj_ledfx/web/router_config.py`**

Add `DiscoveryConfig` to the `dj_ledfx.config` import. In `_merge_config`, add `"discovery": (DiscoveryConfig, existing.discovery),` to `section_map`, and `discovery=kwargs.get("discovery", existing.discovery),` to the `AppConfig(...)` it returns, after `devices=`.

Add below `_merge_config`:

```python
def _check_preview_only(body: dict[str, Any]) -> None:
    engine = body.get("engine")
    value = engine.get("preview_only") if isinstance(engine, dict) else None
    if value is not None and not isinstance(value, bool):
        raise HTTPException(status_code=400, detail="engine.preview_only must be true or false")


def _requires_restart(old: AppConfig, new: AppConfig) -> str:
    """Preview only applies at once; every other change at the next start."""

    def rest(config: AppConfig) -> AppConfig:
        return dataclasses.replace(
            config, engine=dataclasses.replace(config.engine, preview_only=False)
        )

    return "true" if rest(old) != rest(new) else "false"


async def _apply_live(request: Request, config: AppConfig) -> None:
    zones = getattr(request.app.state, "zone_manager", None)
    if zones is not None:
        await zones.set_preview_only(config.engine.preview_only)
```

In `update_config`, call `_check_preview_only(body)` first; after the StateDB block, `await _apply_live(request, new_config)`; and return `headers={"X-Requires-Restart": _requires_restart(config, new_config)}`. In `import_config`, call `_check_preview_only(data)` after parsing the TOML, `await _apply_live(request, new_config)` after saving, and return the same header.

- [ ] **Step 7: Push the `running` channel from `src/dj_ledfx/web/ws.py`**

Add `from collections.abc import Callable` to the imports, and:

```python
from dj_ledfx.web import contract
from dj_ledfx.zones.model import ZonesChanged
```

Add after `_broadcast_json`:

```python
def _running_message(app: Any) -> dict[str, Any] | None:
    zones = getattr(app.state, "zone_manager", None)
    if zones is None:
        return None
    running = contract.running_out(zones.running())
    return {"channel": "running", **running.model_dump(mode="json", by_alias=True)}


# Each pushed channel's snapshot, and the events that make a channel stale.
_SNAPSHOTS: dict[str, Callable[[Any], dict[str, Any] | None]] = {"running": _running_message}
_STALE_ON: dict[type[Any], str] = {ZonesChanged: "running"}


def initial_messages(app: Any) -> list[dict[str, Any]]:
    """Every pushed channel's current state, for a client that has just connected."""
    messages = (snapshot(app) for snapshot in _SNAPSHOTS.values())
    return [message for message in messages if message is not None]


async def event_broadcast(app: Any) -> None:
    """Push a channel's snapshot to every client when an event makes it stale.

    Changes that arrive while a push goes out coalesce into the next push.
    """
    event_bus = app.state.event_bus
    stale: dict[str, None] = {}  # an ordered set of channels
    wake = asyncio.Event()

    def mark(event: object) -> None:
        stale[_STALE_ON[type(event)]] = None
        wake.set()

    for event_type in _STALE_ON:
        event_bus.subscribe(event_type, mark)
    try:
        while True:
            await wake.wait()
            wake.clear()
            channels = list(stale)
            stale.clear()
            for channel in channels:
                message = _SNAPSHOTS[channel](app)
                if message is not None:
                    await _broadcast_json(app, message)
    finally:
        for event_type in _STALE_ON:
            event_bus.unsubscribe(event_type, mark)
```

In `ws_endpoint`, send the current state before the polling tasks start, as the first lines inside the `try:`:

```python
        for message in initial_messages(app):
            await _send_json(websocket, message)
```

- [ ] **Step 8: Wire the router and the broadcaster into `src/dj_ledfx/web/app.py`**

Replace the startup and shutdown hooks with:

```python
    @app.on_event("startup")
    async def _start_broadcasts() -> None:
        if app.state.event_bus is not None:
            from dj_ledfx.web.ws import event_broadcast, transport_broadcast

            app.state.broadcast_tasks = [
                asyncio.create_task(transport_broadcast(app)),
                asyncio.create_task(event_broadcast(app)),
            ]

    @app.on_event("shutdown")
    async def _stop_broadcasts() -> None:
        tasks = getattr(app.state, "broadcast_tasks", [])
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
```

and next to the looks router:

```python
    from dj_ledfx.web.router_zones import router as zones_router

    app.include_router(zones_router, prefix="/api")
```

- [ ] **Step 9: Run the tests to see them pass**

Run: `uv run pytest tests/web -v`
Expected: PASS, including the existing config and WebSocket tests (their apps have no zone manager, so nothing new is pushed to them).

- [ ] **Step 10: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/config.py src/dj_ledfx/web tests/web
git commit -m "feat(web): zones and running API, running channel, live preview-only switch"
```

---

### Task 23: Lights and attention API, and the `lights` and `attention` channels

`GET /lights` (web spec §12.2 `Light`, §12.3) and `GET /attention` (§9.5), and their pushed channels (§12.4). A light's status comes from the light monitor (Task 19): the contract's `LightStatus` plus `idle` for lights in no running zone. Two extra fields, `power` and `colour` (`#RRGGBB`), carry what the monitor last read, so the web app can show idle lights as they are ("Your lights are as they were", web spec §9.4). Placement fields (`room`, `subZone`, `shape`, `ledOrder`, `confirmed`) arrive with the home map in M2 and are empty until then; `parts` stays null until M2 makes the PC one light with parts (spec §6.3). `builtInEffects` lists the firmware effects a light can run itself, and the `effects` capability is set when there is at least one.

Latency: `measuredMs` is the latency strategy's value (without the owner's offset), `estimated` is true for lights that can't be probed (they use the type's heuristic), and `overrideMs` stays null: overrides move to `PUT /lights/{id}/latency` with the rest of the device actions in F6's backend work, and the old `/api/devices` endpoints keep serving them until then.

The old `stats` channel gains each light's `id` and `dropped_pct` (web spec §12.4); the scheduler fills them from Task 24 on.

**Files:**
- Modify: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/ws.py`, `src/dj_ledfx/web/app.py`
- Create: `src/dj_ledfx/web/router_lights.py`, `src/dj_ledfx/web/router_attention.py`
- Test: `tests/web/test_lights_api.py`; modify `tests/web/test_ws_channels.py`

**Interfaces:**
- Consumes: `LightMonitor.refresh`, `states`, `state`, `LightState`, `LightStatus`, `LightsChanged` (Task 19); `AttentionFeed.items`, `AttentionItem` (domain), `AttentionChanged` (Task 20); `DeviceStats.device_id`, `dropped_pct` (Task 20); `DeviceCapabilities` (Task 2); `FirmwareEffect`, `get_effect_classes` (Task 3); `ManagedDevice`; `get_light_monitor`, `get_attention`, `api_home` (Task 21); `_SNAPSHOTS`, `_STALE_ON` (Task 22).
- Produces:
  - `web.contract`: `LightLatency`, `LightPart`, `Light`, `LightUpdate`, `AttentionSubject`, `AttentionItem`; `built_in_effects(caps) -> list[str]`, `light_out(managed, state, stats) -> Light`, `light_update_out(state) -> LightUpdate`, `attention_out(item) -> AttentionItem`
  - REST: `GET /api/lights` (device manager order), `GET /api/attention`
  - WS messages `{"channel": "lights", "lights": LightUpdate[]}` (`id`, `status`, `statusSince`, `ownEffect`, `power`, `colour`) and `{"channel": "attention", "items": AttentionItem[]}`; `stats` entries gain `id` and `dropped_pct`

- [ ] **Step 1: Write the failing tests**

`tests/web/test_lights_api.py`:

```python
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from api_home import api_home
from conftest import FakeLight
from zone_home import GLOW

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.types import DeviceStats
from dj_ledfx.zones.model import ZoneRecord

TILE = DeviceCapabilities(protocol="LIFX", model="LIFX Tile", matrix=True, firmware_version="3.70")
LAMP = DeviceCapabilities(protocol="Govee", model="H6076")


def _stats(device_id: str, send_fps: float, dropped_pct: float) -> DeviceStats:
    return DeviceStats(
        device_name=device_id,
        effective_latency_ms=20.0,
        send_fps=send_fps,
        frames_dropped=0,
        device_id=device_id,
        dropped_pct=dropped_pct,
    )


async def test_lights_come_with_their_status_and_numbers(tmp_path: Path) -> None:
    tile = FakeLight("tile", name="Tile", led_count=64, caps=TILE)
    lamp = FakeLight("lamp", name="Lamp", caps=LAMP)
    zones = [ZoneRecord(id="desk", name="Desk", lights=("tile",))]
    async with api_home(tmp_path, [tile, lamp], zones) as api:
        await api.home.manager.start("desk", GLOW)
        await api.monitor.poll_idle_lights()
        api.stats.extend([_stats("tile", 0.0, 0.0), _stats("lamp", 39.46, 1.25)])

        resp = await api.client.get("/api/lights")

    assert resp.status_code == 200
    tile_out, lamp_out = resp.json()
    assert {"LIFX Flame", "LIFX Morph", "LIFX waveform", "Glow"} <= set(
        tile_out.pop("builtInEffects")
    )
    assert tile_out == {
        "id": "tile",
        "name": "Tile",
        "room": None,
        "subZone": None,
        "model": "LIFX Tile",
        "protocol": "LIFX",
        "leds": 64,
        "capabilities": ["colour", "matrix", "effects"],
        "parts": None,
        "shape": None,
        "ledOrder": "",
        "confirmed": False,
        "status": "own-effect",
        "statusSince": "2026-09-24T19:00:00Z",
        "ownEffect": "Glow",
        "latency": {"measuredMs": 20.0, "overrideMs": None, "estimated": True},
        "sendFps": 0.0,
        "droppedPct": 0.0,
        "address": "fake://tile",
        "mac": None,
        "firmware": "3.70",
        "power": None,
        "colour": None,
    }
    assert {key: lamp_out[key] for key in ("status", "ownEffect", "power", "colour")} == {
        "status": "idle",
        "ownEffect": None,
        "power": True,
        "colour": "#FFC896",
    }
    assert (lamp_out["capabilities"], lamp_out["builtInEffects"]) == (["colour"], [])
    assert (lamp_out["protocol"], lamp_out["sendFps"], lamp_out["droppedPct"]) == (
        "Govee",
        39.5,
        1.25,
    )


async def test_attention_lists_what_needs_the_owner(tmp_path: Path) -> None:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("rope",))]
    async with api_home(tmp_path, [FakeLight("rope", name="Rope")], zones) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))
        api.home.devices.demote_device("rope")
        api.monitor.refresh()
        api.home.clock[0] += timedelta(minutes=2)
        api.feed.update()

        resp = await api.client.get("/api/attention")

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "id": "light-offline:rope",
            "severity": "normal",
            "kind": "light-offline",
            "subject": {"type": "light", "id": "rope"},
            "title": "Rope offline",
            "detail": "Rope offline since 19:00. It rejoins by itself when it's back.",
            "since": "2026-09-24T19:00:00Z",
            "actions": ["details"],
        }
    ]
```

In `tests/web/test_ws_channels.py`, add `from datetime import timedelta` to the imports, and append:

```python
async def test_light_statuses_are_pushed_when_they_change(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    await until(lambda: bool(socket.on("lights")))

    assert socket.on("lights")[-1]["lights"] == [
        {
            "id": "a",
            "status": "streaming",
            "statusSince": "2026-09-24T19:00:00Z",
            "ownEffect": None,
            "power": None,
            "colour": None,
        }
    ]


async def test_attention_is_pushed_when_the_list_changes(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    api.home.devices.demote_device("a")
    api.monitor.refresh()
    api.home.clock[0] += timedelta(minutes=2)
    api.feed.update()
    await until(lambda: bool(socket.on("attention")))

    [message] = socket.on("attention")
    assert [item["kind"] for item in message["items"]] == ["light-offline"]


async def test_a_client_that_connects_gets_every_pushed_channel(api: Api) -> None:
    api.monitor.refresh()

    channels = [message["channel"] for message in initial_messages(api.app)]

    assert channels == ["running", "lights", "attention"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/web/test_lights_api.py tests/web/test_ws_channels.py -v`
Expected: FAIL: 404 for `/api/lights` and `/api/attention`, and no `lights` or `attention` messages.

- [ ] **Step 3: Add the light and attention types to `src/dj_ledfx/web/contract.py`**

Add to the imports:

```python
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.registry import get_effect_classes
from dj_ledfx.types import DeviceStats
from dj_ledfx.zones import attention
from dj_ledfx.zones.lights import LightState, LightStatus
```

Append:

```python
# --- lights and attention ----------------------------------------------------------


class LightLatency(ContractModel):
    measured_ms: float | None
    override_ms: float | None = None  # overrides move to PUT /lights/{id}/latency (F6)
    estimated: bool  # the light can't be probed: the type's heuristic


class LightPart(ContractModel):
    name: str
    leds: int


class Light(ContractModel):
    id: str
    name: str
    room: str | None = None  # placement fields arrive with the home map (M2)
    sub_zone: str | None = None
    model: str
    protocol: Literal["LIFX", "Govee", "OpenRGB"]
    leds: int
    capabilities: list[Literal["colour", "multizone", "matrix", "effects"]]
    built_in_effects: list[str]
    parts: list[LightPart] | None = None
    shape: dict[str, Any] | None = None
    led_order: str = ""
    confirmed: bool = False
    status: LightStatus  # the contract's LightStatus plus "idle"
    status_since: datetime
    own_effect: str | None = None
    latency: LightLatency
    send_fps: float
    dropped_pct: float
    address: str
    mac: str | None = None
    firmware: str | None = None
    power: bool | None = None  # as last read; not in the contract
    colour: str | None = None  # "#RRGGBB" as last read; not in the contract


class LightUpdate(ContractModel):
    """A light's entry on the `lights` channel."""

    id: str
    status: LightStatus
    status_since: datetime
    own_effect: str | None = None
    power: bool | None = None
    colour: str | None = None


class AttentionSubject(ContractModel):
    type: Literal["light", "zone", "input"]
    id: str


class AttentionItem(ContractModel):
    id: str
    severity: Literal["high", "normal"]
    kind: Literal[
        "light-offline",
        "zone-crashed",
        "zone-slow",
        "input-disconnected",
        "input-stale",
        "frames-dropping",
    ]
    subject: AttentionSubject
    title: str
    detail: str
    since: datetime
    actions: list[Literal["restart", "details", "retry", "open"]]


def _hex(colour: tuple[int, int, int] | None) -> str | None:
    if colour is None:
        return None
    red, green, blue = colour
    return f"#{red:02X}{green:02X}{blue:02X}"


def built_in_effects(caps: DeviceCapabilities) -> list[str]:
    """The firmware effects a light can run itself (web spec §11.2)."""
    return [
        cls.display_name
        for cls in get_effect_classes().values()
        if issubclass(cls, FirmwareEffect) and cls().supports(caps)
    ]


def light_out(managed: ManagedDevice, state: LightState, stats: DeviceStats | None) -> Light:
    adapter, tracker = managed.adapter, managed.tracker
    info, caps = adapter.device_info, adapter.capabilities
    effects = built_in_effects(caps)
    flags = {
        "colour": caps.colour,
        "multizone": caps.multizone,
        "matrix": caps.matrix,
        "effects": bool(effects),
    }
    return Light.model_validate(
        {
            "id": state.device_id,
            "name": info.name,
            "model": caps.model or info.device_type,
            "protocol": caps.protocol,
            "leds": adapter.led_count,
            "capabilities": [name for name, on in flags.items() if on],
            "built_in_effects": effects,
            "status": state.status,
            "status_since": state.since,
            "own_effect": state.own_effect,
            "latency": {
                "measured_ms": round(tracker.effective_latency_ms - tracker.manual_offset_ms, 1),
                "estimated": not adapter.supports_latency_probing,
            },
            "send_fps": round(stats.send_fps, 1) if stats else 0.0,
            "dropped_pct": round(stats.dropped_pct, 2) if stats else 0.0,
            "address": info.address,
            "mac": info.mac,
            "firmware": caps.firmware_version,
            "power": state.power,
            "colour": _hex(state.colour),
        }
    )


def light_update_out(state: LightState) -> LightUpdate:
    return LightUpdate(
        id=state.device_id,
        status=state.status,
        status_since=state.since,
        own_effect=state.own_effect,
        power=state.power,
        colour=_hex(state.colour),
    )


def attention_out(item: attention.AttentionItem) -> AttentionItem:
    return AttentionItem.model_validate(
        {
            "id": item.id,
            "severity": item.severity,
            "kind": item.kind,
            "subject": {"type": item.subject_type, "id": item.subject_id},
            "title": item.title,
            "detail": item.detail,
            "since": item.since,
            "actions": list(item.actions),
        }
    )
```

- [ ] **Step 4: Write the routers**

`src/dj_ledfx/web/router_lights.py`:

```python
"""Lights with their status (web spec §9.1, §12.2). Device actions stay on /api/devices."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_light_monitor

router = APIRouter()


@router.get("/lights")
async def list_lights(request: Request) -> list[api.Light]:
    monitor = get_light_monitor(request)
    monitor.refresh()  # picks up lights found since the last poll
    scheduler = request.app.state.scheduler
    stats = {entry.device_id: entry for entry in scheduler.get_device_stats()}
    lights = []
    for managed in request.app.state.device_manager.devices:
        state = monitor.state(managed.adapter.device_info.stable_id or "")
        if state is not None:
            lights.append(api.light_out(managed, state, stats.get(state.device_id)))
    return lights
```

`src/dj_ledfx/web/router_attention.py`:

```python
"""What needs the owner's attention, derived on the server (web spec §9.5)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_attention

router = APIRouter()


@router.get("/attention")
async def list_attention(request: Request) -> list[api.AttentionItem]:
    return [api.attention_out(item) for item in get_attention(request).items()]
```

In `src/dj_ledfx/web/app.py`, next to the zones router:

```python
    from dj_ledfx.web.router_attention import router as attention_router
    from dj_ledfx.web.router_lights import router as lights_router

    app.include_router(lights_router, prefix="/api")
    app.include_router(attention_router, prefix="/api")
```

- [ ] **Step 5: Push the `lights` and `attention` channels from `src/dj_ledfx/web/ws.py`**

Change the zones import to `from dj_ledfx.zones.model import AttentionChanged, LightsChanged, ZonesChanged`. Add after `_running_message`:

```python
def _lights_message(app: Any) -> dict[str, Any] | None:
    monitor = getattr(app.state, "light_monitor", None)
    if monitor is None:
        return None
    lights = [contract.light_update_out(state) for state in monitor.states()]
    return {
        "channel": "lights",
        "lights": [light.model_dump(mode="json", by_alias=True) for light in lights],
    }


def _attention_message(app: Any) -> dict[str, Any] | None:
    feed = getattr(app.state, "attention_feed", None)
    if feed is None:
        return None
    items = [contract.attention_out(item) for item in feed.items()]
    return {
        "channel": "attention",
        "items": [item.model_dump(mode="json", by_alias=True) for item in items],
    }
```

and extend the two tables:

```python
_SNAPSHOTS: dict[str, Callable[[Any], dict[str, Any] | None]] = {
    "running": _running_message,
    "lights": _lights_message,
    "attention": _attention_message,
}
_STALE_ON: dict[type[Any], str] = {
    ZonesChanged: "running",
    LightsChanged: "lights",
    AttentionChanged: "attention",
}
```

In `_stats_poll`, add to each device entry:

```python
                        "id": s.device_id,
                        "dropped_pct": s.dropped_pct,
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/web -v`
Expected: PASS.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/web tests/web
git commit -m "feat(web): lights and attention API with their pushed channels"
```

---

### Task 24: Cut-over: the engine renders zones, the scheduler follows routes

The switch from the global transport to zones (spec §2, §4.1, §6.5). The effect engine renders every running zone's runtime; the scheduler sends each device its slice of its zone's frames through the device's route, converting to 8 bits once, at send; lights running their own effect get no frames, and preview-only sends nothing while the web preview carries on. `main` builds the zone manager, the light monitor and the attention feed, resumes the zones that were running before any light connects, and hands device events to the zone manager.

Everything the transport and the scene pipelines needed goes: `transport.py`, the effect deck, `ScenePipeline`, `PipelineManager`, `/api/transport`, `/api/scenes/*`, the WebSocket `set_effect` and `set_transport` commands, and the device manager's capture-on-connect (the zone manager captures lights now). The old UI keeps its effect controls and presets through a `?zone=` parameter on the same endpoints (spec §6.5), and the WebSocket `transport` channel now carries preview-only in the contract's terms: `simulating` while it's on, `playing` otherwise (web spec §12.4). The old UI's transport buttons stop working here; Task 26 replaces them with the look picker.

The legacy single-scene endpoints (`/api/scene`) stay: the old UI's scene page uses them until F11. They no longer reach the scheduler.

**Files:**
- Modify: `src/dj_ledfx/effects/engine.py`, `src/dj_ledfx/scheduling/scheduler.py`, `src/dj_ledfx/main.py`
- Modify: `src/dj_ledfx/types.py`, `src/dj_ledfx/events.py`, `src/dj_ledfx/config.py`, `src/dj_ledfx/devices/manager.py`
- Modify: `src/dj_ledfx/web/app.py`, `src/dj_ledfx/web/ws.py`, `src/dj_ledfx/web/router_effects.py`, `src/dj_ledfx/web/router_scene.py`, `src/dj_ledfx/web/schemas.py`
- Delete: `src/dj_ledfx/transport.py`, `src/dj_ledfx/effects/deck.py`, `src/dj_ledfx/spatial/pipeline.py`, `src/dj_ledfx/spatial/pipeline_manager.py`, `src/dj_ledfx/web/router_transport.py`
- Delete tests: `tests/test_transport.py`, `tests/test_transport_integration.py`, `tests/effects/test_engine_transport.py`, `tests/effects/test_deck.py`, `tests/scheduling/test_scheduler_transport.py`, `tests/spatial/test_pipeline_manager.py`, `tests/spatial/test_pipeline.py`, `tests/spatial/test_spatial_pipeline.py`, `tests/web/test_router_transport.py`, `tests/web/test_ws_transport.py`
- Test: `tests/scheduling/test_scheduler.py`, `tests/effects/test_engine.py`, `tests/test_integration.py`, `tests/web/test_router_effects.py`, `tests/web/test_ws.py`, `tests/web/test_ws_channels.py`
- Modify tests: `tests/api_home.py`, `tests/web/test_app.py`, `tests/web/test_router_config.py`, `tests/web/test_router_devices.py`, `tests/web/test_router_scene.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `ZoneRuntime` (`zone_id`, `ring`, `lights`, `leds`, `horizon_s`, `tick`, `route_for`), `ZoneLight`, `DeviceRoute`, `to_device_colors` (Task 15); `ZoneManager` with `load`, `resume`, `set_preview_only`, `on_device_offline`, `on_device_online`, `on_device_discovered`, `classic_layer`, `set_classic_effect`, `get_zone`, `preview_only` (Tasks 16–18); `PreviewOnlyChanged` (Task 17); `LightMonitor` (Task 19); `AttentionFeed`, `DeviceStats.device_id`, `DeviceStats.dropped_pct` (Task 20); `get_zones`, `api_home` (Task 21); `answers()`, `_SNAPSHOTS`, `_STALE_ON`, `initial_messages`, `event_broadcast`, `EngineConfig.preview_only` (Task 22); `LookStore` (Task 13); `ZoneStore.migrate_scenes_once` (Task 14); `builtin_looks` (Task 12); `DeviceCapabilities` (Task 2).
- Produces:
  - `EffectEngine(fps=60)`: `add_runtime(runtime)`, `remove_runtime(zone_id)`, `tick(now)`, `async run()`, `stop()`, `avg_render_time_ms`, `fill_level` (the emptiest zone ring, `1.0` when nothing runs). It is the zone manager's `RuntimeHost`.
  - `LookaheadScheduler(devices=(), fps=60, disconnect_backoff_s=1.0, event_bus=None)`: `set_route(device_id, route | None)`, `set_preview_only(on)`, `preview_only`, `add_device(managed)`, `remove_device(stable_id)`, `has_device(stable_id)`, `frame_snapshots`, `get_device_stats()` (`send_fps` over the last second, `device_id`, `dropped_pct` while streaming), `async run()`, `stop()`. It is the zone manager's `RouteTable`.
  - `RenderedFrame.colors: FloatRGB`
  - Old UI endpoints: `GET /api/effects/active?zone=`, `PUT /api/effects/active?zone=`, `POST /api/presets?zone=`, `POST /api/presets/{name}/load?zone=`
  - WebSocket `transport` channel: `{"channel": "transport", "state": "playing" | "simulating"}`, on connect and when preview-only changes
  - `create_app(...)` without `effect_deck` and `pipeline_manager`

- [ ] **Step 1: Rewrite the scheduler tests**

In `tests/scheduling/test_scheduler.py`:

1. Delete `from dj_ledfx.transport import TransportState`, the `_set_playing` helper and every `_set_playing(scheduler)` line:

```bash
sed -i '/from dj_ledfx.transport import TransportState/d; /^    _set_playing(scheduler)$/d' tests/scheduling/test_scheduler.py
```

then delete the `_set_playing` function itself (its `def` line, docstring and two body lines).

2. Point every scheduler the tests build at the new helper (run this before adding the helper, whose own line must stay as it is):

```bash
sed -i 's/scheduler = LookaheadScheduler(/scheduler = _scheduler(/' tests/scheduling/test_scheduler.py
```

3. Add `from typing import Any` to the imports and `from dj_ledfx.scheduling.route import DeviceRoute` after the scheduler import. Give `_make_device` a `led_count: int = 10` parameter, passed on as `MockDeviceAdapter(name=name, led_count=led_count, connected=connected)`. Replace `_fill_buffer` with the float version and add the helpers below it:

```python
def _fill_buffer(buf: RingBuffer, base_time: float, count: int = 60) -> None:
    for i in range(count):
        frame = RenderedFrame(
            colors=np.full((10, 3), (i % 256) / 255.0, dtype=np.float32),
            target_time=base_time + i * (1.0 / 60.0),
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)


def _route(
    ring: RingBuffer, *, start: int = 0, stop: int = 10, streaming: bool = True
) -> DeviceRoute:
    return DeviceRoute(zone_id="zone", ring=ring, start=start, stop=stop, streaming=streaming)


def _scheduler(
    ring_buffer: RingBuffer, devices: list[ManagedDevice], **kwargs: Any
) -> LookaheadScheduler:
    """A scheduler that sends every device the first ten LEDs of ring_buffer's frames."""
    made = LookaheadScheduler(devices=devices, **kwargs)
    for device in devices:
        made.set_route(device.adapter.device_info.effective_id, _route(ring_buffer))
    return made


async def _run_for(scheduler: LookaheadScheduler, seconds: float) -> None:
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(seconds)
    scheduler.stop()
    await task
```

4. Delete `test_compositor_property_setter`, `test_remove_pipeline_refs` and `test_remove_pipeline_refs_only_affects_target_scene`. In `test_device_send_state_creation`, delete the `pipeline=None,` argument. In `test_get_device_stats`, add `assert stats[0].device_id == "StatsDevice"` after the `device_name` assertion. In `test_distributor_handles_concurrent_add_device`, route the late device before adding it:

```python
    late_device = _make_device("LateJoiner", latency_ms=10.0)
    scheduler.set_route("LateJoiner", _route(buf))
    scheduler.add_device(late_device)
```

5. Append the route tests:

```python
# --- Routes ---


def _two_frame_ring() -> RingBuffer:
    """Frame 0 for now and frame 1 for a second later; LEDs 0-4 and 5-9 differ in each."""
    buf = RingBuffer(capacity=10, led_count=10)
    now = time.monotonic()
    for index, (first, second) in enumerate([(0.25, 0.5), (0.75, 1.0)]):
        colors = np.empty((10, 3), dtype=np.float32)
        colors[:5], colors[5:] = first, second
        buf.write(
            RenderedFrame(colors=colors, target_time=now + index, beat_phase=0.0, bar_phase=0.0)
        )
    return buf


async def test_each_device_gets_its_slice_of_the_frame_for_its_own_latency() -> None:
    near = _make_device("near", latency_ms=10.0, led_count=5)
    far = _make_device("far", latency_ms=600.0, led_count=5)
    buf = _two_frame_ring()
    scheduler = LookaheadScheduler(devices=[near, far], fps=60)
    scheduler.set_route("near", _route(buf, start=0, stop=5))
    scheduler.set_route("far", _route(buf, start=5, stop=10))

    await _run_for(scheduler, 0.2)

    # near reads frame 0 (now + 10 ms), far reads frame 1 (now + 600 ms)
    near_sent = {frame.tobytes() for frame in near.adapter.send_frame_calls}
    far_sent = {frame.tobytes() for frame in far.adapter.send_frame_calls}
    assert near_sent == {bytes([64] * 15)}  # 0.25 in 8 bits
    assert far_sent == {bytes([255] * 15)}


async def test_preview_only_sends_nothing_but_keeps_the_preview() -> None:
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(buf, [device], fps=60)
    scheduler.set_preview_only(True)

    await _run_for(scheduler, 0.15)

    assert scheduler.preview_only
    assert device.adapter.send_frame_calls == []
    assert "TestDevice" in scheduler.frame_snapshots
    assert scheduler.get_device_stats()[0].dropped_pct == 0.0


async def test_a_light_running_its_own_effect_gets_no_frames() -> None:
    device = _make_device()
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = LookaheadScheduler(devices=[device], fps=60)
    scheduler.set_route("TestDevice", _route(buf, streaming=False))

    await _run_for(scheduler, 0.15)

    assert device.adapter.send_frame_calls == []
    assert "TestDevice" in scheduler.frame_snapshots  # the preview shows its streamed copy


async def test_a_device_without_a_route_gets_nothing() -> None:
    routed, idle = _make_device("routed"), _make_device("idle")
    buf = RingBuffer(capacity=60, led_count=10)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = LookaheadScheduler(devices=[routed, idle], fps=60)
    scheduler.set_route("routed", _route(buf))

    await _run_for(scheduler, 0.15)

    assert routed.adapter.send_frame_calls
    assert idle.adapter.send_frame_calls == []
    assert "idle" not in scheduler.frame_snapshots


async def test_stats_report_the_share_of_frames_a_streaming_light_misses() -> None:
    starved, idle = _make_device("starved"), _make_device("idle")
    scheduler = LookaheadScheduler(devices=[starved, idle], fps=60)
    scheduler.set_route("starved", _route(RingBuffer(capacity=60, led_count=10)))  # no frames

    await _run_for(scheduler, 0.15)

    stats = {entry.device_id: entry for entry in scheduler.get_device_stats()}
    assert (stats["starved"].send_fps, stats["starved"].dropped_pct) == (0.0, 100.0)
    assert stats["idle"].dropped_pct == 0.0  # not streaming, so nothing is missed
```

- [ ] **Step 2: Rewrite the engine tests**

In `tests/effects/test_engine.py`, keep the `clock` fixture and the four `test_ring_buffer_*` tests. Replace the imports with:

```python
import asyncio
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

import dj_ledfx.metrics as metrics_mod
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.engine import EffectEngine, RingBuffer
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime
```

and everything after `test_ring_buffer_empty_returns_none` with:

```python
def _runtime(zone_id: str, clock: BeatClock) -> ZoneRuntime:
    look = next(look for look in builtin_looks() if look.id == "classic-breathe")
    light = ZoneLight(f"{zone_id}-light", 4, DeviceCapabilities(protocol="LIFX"))
    return ZoneRuntime(zone_id, look, [light], clock=clock, latency_s=lambda _: 0.05)


def test_the_engine_renders_each_zone_it_hosts(clock: BeatClock) -> None:
    engine = EffectEngine(fps=60)
    desk, shelf = _runtime("desk", clock), _runtime("shelf", clock)
    engine.add_runtime(desk)
    engine.add_runtime(shelf)
    now = time.monotonic()

    engine.tick(now)
    engine.remove_runtime("shelf")
    engine.tick(now + 1 / 60)

    assert (desk.ring.count, shelf.ring.count) == (2, 1)
    frame = desk.ring.find_nearest(now + 0.05 + 1 / 60)
    assert frame is not None
    assert (frame.colors.shape, frame.colors.dtype) == ((4, 3), np.float32)
    assert engine.fill_level == desk.ring.fill_level
    assert EffectEngine().fill_level == 1.0


def test_a_tick_observes_the_render_duration(
    clock: BeatClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    duration, rendered = MagicMock(), MagicMock()
    monkeypatch.setattr(metrics_mod, "RENDER_DURATION", duration)
    monkeypatch.setattr(metrics_mod, "FRAMES_RENDERED", rendered)
    engine = EffectEngine(fps=60)
    engine.add_runtime(_runtime("desk", clock))

    engine.tick(time.monotonic())

    duration.observe.assert_called_once()
    rendered.inc.assert_called_once()
    assert engine.avg_render_time_ms > 0.0


async def test_the_engine_renders_until_stopped(clock: BeatClock) -> None:
    engine = EffectEngine(fps=60)
    desk = _runtime("desk", clock)
    engine.add_runtime(desk)

    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.1)
    engine.stop()
    await asyncio.wait_for(task, timeout=1.0)

    assert desk.ring.count >= 3
```

- [ ] **Step 3: Rewrite the end-to-end tests**

In `tests/test_integration.py`, replace everything from the top of the file down to (not including) `async def test_rtt_callback_updates_tracker` with the block below, and delete `test_multi_pipeline_renders_to_separate_devices` at the end of the file. The two latency tests and the two start-up tests stay.

```python
import asyncio
import time
from pathlib import Path

import numpy as np
import pytest
from conftest import MockDeviceAdapter

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.zones.runtime import ZoneLight, ZoneRuntime


def _device(name: str, latency_ms: float, led_count: int) -> ManagedDevice:
    adapter = MockDeviceAdapter(name=name, led_count=led_count)
    tracker = LatencyTracker(strategy=StaticLatency(latency_ms))
    return ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)


def _clock() -> BeatClock:
    clock = BeatClock()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=time.monotonic())
    return clock


def _zone(
    zone_id: str, look_id: str, devices: list[ManagedDevice], clock: BeatClock
) -> ZoneRuntime:
    """A running zone as the zone manager builds one (lights are keyed by name here)."""
    look = next(look for look in builtin_looks() if look.id == look_id)
    caps = DeviceCapabilities(protocol="LIFX")
    lights = [ZoneLight(d.adapter.device_info.name, d.adapter.led_count, caps) for d in devices]
    latency = {d.adapter.device_info.name: d.tracker.effective_latency_s for d in devices}
    return ZoneRuntime(zone_id, look, lights, clock=clock, latency_s=latency.__getitem__)


async def _play(zones: list[ZoneRuntime], devices: list[ManagedDevice], seconds: float) -> None:
    """The engine and the scheduler, wired the way main wires them, for a while."""
    engine = EffectEngine(fps=60)
    scheduler = LookaheadScheduler(devices=devices, fps=60)
    for zone in zones:
        engine.add_runtime(zone)
        for light in zone.lights:
            scheduler.set_route(light.device_id, zone.route_for(light.device_id))
    tasks = [asyncio.create_task(engine.run()), asyncio.create_task(scheduler.run())]
    await asyncio.sleep(seconds)
    engine.stop()
    scheduler.stop()
    await asyncio.gather(*tasks)


async def test_one_zone_streams_each_light_its_own_slice() -> None:
    near, far = _device("near", 10.0, 10), _device("far", 100.0, 5)
    zone = _zone("desk", "classic-rainbow-wave", [near, far], _clock())

    await _play([zone], [near, far], 0.5)

    assert zone.horizon_s == pytest.approx(0.1 + 1 / 60)
    assert zone.leds.count == 15
    assert near.adapter.send_frame_calls and far.adapter.send_frame_calls
    near_frame, far_frame = near.adapter.send_frame_calls[-1], far.adapter.send_frame_calls[-1]
    assert (near_frame.shape, far_frame.shape) == ((10, 3), (5, 3))
    assert near_frame.dtype == far_frame.dtype == np.uint8


async def test_two_zones_play_their_own_looks() -> None:
    left, right = _device("left", 10.0, 10), _device("right", 10.0, 10)
    clock = _clock()
    zones = [
        _zone("a", "classic-beat-pulse", [left], clock),
        _zone("b", "classic-rainbow-wave", [right], clock),
    ]

    await _play(zones, [left, right], 0.5)

    assert left.adapter.send_frame_calls and right.adapter.send_frame_calls
    left_frame, right_frame = left.adapter.send_frame_calls[-1], right.adapter.send_frame_calls[-1]
    assert not np.array_equal(left_frame, right_frame), "each zone plays its own look"
```

- [ ] **Step 4: Rewrite the effect endpoint tests on a zone**

Replace `tests/web/test_router_effects.py` with:

```python
"""The old UI's effect controls, aimed at a zone's classic effect (spec §6.5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.effects.presets import PresetStore
from dj_ledfx.zones.model import ZoneRecord

DESK = {"zone": "desk"}


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("a",))]
    async with api_home(tmp_path, [FakeLight("a")], zones) as api:
        api.app.state.preset_store = PresetStore(state_db=api.home.db)
        yield api


async def test_list_effects(api: Api) -> None:
    resp = await api.client.get("/api/effects")

    assert resp.status_code == 200
    assert "beat_pulse" in resp.json()


async def test_choosing_an_effect_starts_its_classic_look_on_the_zone(api: Api) -> None:
    resp = await api.client.get("/api/effects/active", params=DESK)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Desk isn't playing a classic effect"

    resp = await api.client.put("/api/effects/active", params=DESK, json={"effect": "beat_pulse"})

    assert resp.status_code == 200
    assert resp.json()["effect"] == "beat_pulse"
    running = (await api.client.get("/api/running")).json()["zones"]
    assert [(zone["zoneId"], zone["lookId"]) for zone in running] == [
        ("desk", "classic-beat-pulse")
    ]


async def test_settings_change_in_place(api: Api) -> None:
    await api.client.put("/api/effects/active", params=DESK, json={"effect": "beat_pulse"})

    resp = await api.client.put(
        "/api/effects/active", params=DESK, json={"params": {"gamma": 3.0}}
    )

    assert resp.status_code == 200
    active = (await api.client.get("/api/effects/active", params=DESK)).json()
    assert (active["effect"], active["params"]["gamma"]) == ("beat_pulse", 3.0)


async def test_unknown_effects_unknown_zones_and_no_zone(api: Api) -> None:
    resp = await api.client.put("/api/effects/active", params=DESK, json={"effect": "nope"})
    assert (resp.status_code, resp.json()["detail"]) == (404, "Unknown effect: nope")

    resp = await api.client.get("/api/effects/active", params={"zone": "zzz"})
    assert (resp.status_code, resp.json()["detail"]) == (404, "No zone 'zzz'")

    resp = await api.client.get("/api/effects/active")
    assert resp.status_code == 422


async def test_presets_save_and_load_on_a_zone(api: Api) -> None:
    body = {"effect": "beat_pulse", "params": {"gamma": 3.0}}
    await api.client.put("/api/effects/active", params=DESK, json=body)

    resp = await api.client.post("/api/presets", params=DESK, json={"name": "Test"})
    assert resp.status_code == 200
    assert (resp.json()["effect_class"], resp.json()["params"]["gamma"]) == ("beat_pulse", 3.0)

    await api.client.put("/api/effects/active", params=DESK, json={"effect": "rainbow_wave"})
    resp = await api.client.post("/api/presets/Test/load", params=DESK)
    assert resp.status_code == 200
    assert (resp.json()["effect"], resp.json()["params"]["gamma"]) == ("beat_pulse", 3.0)

    resp = await api.client.put("/api/presets/Test", json={"params": {"gamma": 4.0}})
    assert (resp.status_code, resp.json()["params"]["gamma"]) == (200, 4.0)
    assert [p["name"] for p in (await api.client.get("/api/presets")).json()] == ["Test"]
    assert (await api.client.delete("/api/presets/Test")).status_code == 200
    assert (await api.client.get("/api/presets")).json() == []
    assert (await api.client.post("/api/presets/Test/load", params=DESK)).status_code == 404
```

- [ ] **Step 5: Update the WebSocket tests**

In `tests/web/test_ws.py`, delete the `BeatPulse` and `EffectDeck` imports, the `deck = EffectDeck(BeatPulse())` line and the `effect_deck=deck,` argument, and replace `test_ws_set_effect_with_scene_id` and `test_ws_set_effect_without_scene_id` with:

```python
def test_ws_the_old_deck_and_transport_commands_are_gone(client):
    """set_effect and set_transport went with the global deck and transport (M1)."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "set_transport", "id": "t1", "state": "playing"})
        for _ in range(10):
            msg = json.loads(ws.receive_text())
            if msg.get("channel") == "error" and msg.get("id") == "t1":
                assert msg["detail"] == "Unknown action: set_transport"
                break
        else:
            pytest.fail("no error for set_transport")
```

In `tests/web/test_ws_channels.py`, add `PreviewOnly` coverage: change the last assertion of `test_a_client_that_connects_gets_every_pushed_channel` to

```python
    assert channels == ["running", "lights", "attention", "transport"]
```

and append:

```python
async def test_preview_only_is_pushed_as_the_transport_state(
    api: Api, socket: FakeSocket
) -> None:
    await api.home.manager.set_preview_only(True)
    await until(lambda: bool(socket.on("transport")))

    assert socket.on("transport") == [{"channel": "transport", "state": "simulating"}]
```

- [ ] **Step 6: Run the tests to see them fail**

Run: `uv run pytest tests/scheduling/test_scheduler.py tests/effects/test_engine.py tests/test_integration.py tests/web/test_router_effects.py tests/web/test_ws.py tests/web/test_ws_channels.py -q`
Expected: FAIL: `TypeError`s from the old `LookaheadScheduler` and `EffectEngine` signatures (`missing ... 'ring_buffer'`, `missing ... 'clock'`), the effect endpoints still reading the global deck, and no `transport` channel.

- [ ] **Step 7: Delete the transport, the deck and the scene pipelines**

```bash
git rm src/dj_ledfx/transport.py src/dj_ledfx/effects/deck.py \
  src/dj_ledfx/spatial/pipeline.py src/dj_ledfx/spatial/pipeline_manager.py \
  src/dj_ledfx/web/router_transport.py \
  tests/test_transport.py tests/test_transport_integration.py \
  tests/effects/test_engine_transport.py tests/effects/test_deck.py \
  tests/scheduling/test_scheduler_transport.py tests/spatial/test_pipeline_manager.py \
  tests/spatial/test_pipeline.py tests/spatial/test_spatial_pipeline.py \
  tests/web/test_router_transport.py tests/web/test_ws_transport.py
```

`tests/spatial/test_compositor.py` stays: the legacy `/api/scene` endpoints still use the compositor.

- [ ] **Step 8: Rewrite `EffectEngine` in `src/dj_ledfx/effects/engine.py`**

`RingBuffer` doesn't change. Replace the imports with:

```python
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.types import RenderedFrame

if TYPE_CHECKING:
    from dj_ledfx.zones.runtime import ZoneRuntime  # imports RingBuffer from this module
```

and the whole `EffectEngine` class with:

```python
class EffectEngine:
    """Renders every running zone once a frame (spec §4.1).

    The zone manager adds and removes the zones' runtimes: this is its RuntimeHost. Each
    runtime renders for now plus its own horizon into its own ring buffer.
    """

    def __init__(self, fps: int = 60) -> None:
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._runtimes: dict[str, ZoneRuntime] = {}
        self._running = False
        self._render_times: deque[float] = deque(maxlen=fps * 10)

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0.0
        return sum(self._render_times) / len(self._render_times) * 1000.0

    @property
    def fill_level(self) -> float:
        """The emptiest running zone's ring buffer fill; 1.0 when nothing runs."""
        return min((runtime.ring.fill_level for runtime in self._runtimes.values()), default=1.0)

    def add_runtime(self, runtime: ZoneRuntime) -> None:
        self._runtimes[runtime.zone_id] = runtime

    def remove_runtime(self, zone_id: str) -> None:
        self._runtimes.pop(zone_id, None)

    def tick(self, now: float) -> None:
        started = time.monotonic()
        for runtime in self._runtimes.values():
            runtime.tick(now)
        elapsed = time.monotonic() - started
        metrics.RENDER_DURATION.observe(elapsed)
        metrics.FRAMES_RENDERED.inc()
        self._render_times.append(elapsed)

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        metrics.RENDER_FPS.set(self._fps)
        logger.info("EffectEngine started: {} fps", self._fps)
        next_tick = time.monotonic()
        while self._running:
            self.tick(time.monotonic())
            next_tick += self._frame_period
            delay = next_tick - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            else:  # fell behind: count from now rather than burst to catch up
                next_tick = time.monotonic()
                await asyncio.sleep(0)
        logger.info("EffectEngine stopped")
```

- [ ] **Step 9: Rewrite `src/dj_ledfx/scheduling/scheduler.py`**

`FrameSlot` doesn't change. Replace the rest of the file (keep `FrameSlot` where it is):

```python
"""Sends each light its slice of its zone's frames, ahead by the light's latency (spec §4.1)."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx import metrics
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.events import DeviceOfflineEvent, EventBus
from dj_ledfx.types import DeviceStats

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dj_ledfx.scheduling.route import DeviceRoute

RATE_WINDOW_S = 1.0  # send_fps and dropped_pct cover the last second


# class FrameSlot: unchanged


def _trim(sent_at: deque[float], now: float) -> None:
    while sent_at and now - sent_at[0] > RATE_WINDOW_S:
        sent_at.popleft()


@dataclass
class DeviceSendState:
    """Per-device send state, keyed by stable_id."""

    managed: ManagedDevice
    slot: FrameSlot
    send_count: int = 0
    send_task: asyncio.Task[None] | None = None
    sent_at: deque[float] = field(default_factory=deque)  # send times in the last second


class LookaheadScheduler:
    """Sends each device the slice its route points at, for now plus the device's latency.

    The zone manager sets the routes: this is its RouteTable. A device with no route gets
    nothing. A light running its own effect, and every light while preview-only is on,
    gets no frames either, but its slice still reaches the web preview.
    """

    def __init__(
        self,
        devices: Sequence[ManagedDevice] = (),
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
        event_bus: EventBus | None = None,
    ) -> None:
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._disconnect_backoff_s = disconnect_backoff_s
        self._running = False
        self._event_bus = event_bus
        self._routes: dict[str, DeviceRoute] = {}
        self._preview_only = False
        self._frame_snapshots: dict[str, tuple[NDArray[np.uint8], int]] = {}
        self._frame_seq: dict[str, int] = {}
        self._device_state: dict[str, DeviceSendState] = {}
        for device in devices:
            key = self._device_key(device)
            self._device_state[key] = DeviceSendState(managed=device, slot=FrameSlot())

    @staticmethod
    def _device_key(managed: ManagedDevice) -> str:
        return managed.adapter.device_info.effective_id

    @property
    def frame_snapshots(self) -> dict[str, tuple[NDArray[np.uint8], int]]:
        return self._frame_snapshots

    @property
    def preview_only(self) -> bool:
        return self._preview_only

    def set_route(self, device_id: str, route: DeviceRoute | None) -> None:
        """Where a device's frames come from; None stops them."""
        if route is None:
            self._routes.pop(device_id, None)
        else:
            self._routes[device_id] = route

    def set_preview_only(self, on: bool) -> None:
        """Frames reach the web preview only and nothing is sent (spec §6.4)."""
        self._preview_only = on

    def add_device(self, managed: ManagedDevice) -> None:
        """Add a device dynamically. Spawns a send task if the scheduler is running."""
        key = self._device_key(managed)
        if key in self._device_state:
            logger.warning("Device '{}' already in scheduler, skipping add", key)
            return
        state = DeviceSendState(managed=managed, slot=FrameSlot())
        self._device_state[key] = state
        if self._running:
            state.send_task = asyncio.create_task(self._send_loop(state, key))
        logger.info("Scheduler: added device '{}'", key)

    def remove_device(self, stable_id: str) -> None:
        """Remove a device by stable_id (or name). Cancels its send task."""
        state = self._device_state.pop(stable_id, None)
        if state is None:
            logger.warning("Scheduler: remove_device called for unknown key '{}'", stable_id)
            return
        if state.send_task is not None and not state.send_task.done():
            state.send_task.cancel()
        logger.info("Scheduler: removed device '{}'", stable_id)

    def has_device(self, stable_id: str) -> bool:
        return stable_id in self._device_state

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("LookaheadScheduler started with {} devices", len(self._device_state))
        for key, state in list(self._device_state.items()):
            state.send_task = asyncio.create_task(self._send_loop(state, key))
        try:
            last_tick = time.monotonic()
            while self._running:
                self._distribute(time.monotonic())
                last_tick += self._frame_period
                sleep_time = last_tick - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    last_tick = time.monotonic()
                    await asyncio.sleep(0)
        finally:
            # Runs on normal exit and on cancellation. Snapshot: devices may come and go.
            all_states = list(self._device_state.values())
            all_tasks = [s.send_task for s in all_states if s.send_task is not None]
            for task in all_tasks:
                task.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)
            for state in all_states:
                state.send_task = None
        logger.info("LookaheadScheduler stopped")

    def _distribute(self, now: float) -> None:
        """Tell each routed device which moment its next frame is for: now + its latency."""
        for key, state in self._device_state.items():
            if key not in self._routes:
                continue
            name = state.managed.adapter.device_info.name
            if state.slot.has_pending:
                logger.trace("Frame overwritten for '{}': it drains slower than the engine", name)
                metrics.FRAMES_DROPPED.labels(device=name).inc()
            state.slot.put(now + state.managed.tracker.effective_latency_s)

    async def _send_loop(self, state: DeviceSendState, key: str) -> None:
        device = state.managed
        slot = state.slot
        was_connected = device.adapter.is_connected
        last_send_time = time.monotonic()

        while self._running and key in self._device_state:
            if not device.adapter.is_connected:
                if was_connected:
                    logger.warning("Device '{}' disconnected", device.adapter.device_info.name)
                    if self._event_bus is not None:
                        self._event_bus.emit(
                            DeviceOfflineEvent(
                                stable_id=device.adapter.device_info.stable_id or key,
                                name=device.adapter.device_info.name,
                            )
                        )
                was_connected = False
                await asyncio.sleep(self._disconnect_backoff_s)
                continue

            if not was_connected:
                logger.info("Device '{}' reconnected", device.adapter.device_info.name)
                device.tracker.reset()
                was_connected = True

            try:
                target_time = await slot.take(timeout=1.0)
            except TimeoutError:
                continue

            route = self._routes.get(key)
            if route is None:
                continue
            colors = route.colors_at(target_time, device.adapter.led_count)
            device_name = device.adapter.device_info.name
            if colors is None:
                logger.trace("No frame yet for '{}' (target {:.3f})", device_name, target_time)
                continue

            if route.streaming and not self._preview_only:
                send_start = time.monotonic()
                try:
                    await device.adapter.send_frame(colors)
                except Exception:
                    logger.warning("Send failed for '{}'", device_name)
                    continue
                sent = time.monotonic()
                metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(sent - send_start)
                if device.adapter.supports_latency_probing:
                    device.tracker.update((sent - send_start) * 1000.0)
                state.send_count += 1
                state.sent_at.append(sent)
                _trim(state.sent_at, sent)
                metrics.DEVICE_LATENCY.labels(device=device_name).set(
                    device.tracker.effective_latency_s
                )
                metrics.DEVICE_FPS.labels(device=device_name).set(device.max_fps)

            # The web preview shows every routed device's slice, sent or not.
            seq = self._frame_seq.get(device_name, 0) + 1
            self._frame_seq[device_name] = seq
            self._frame_snapshots[device_name] = (colors, seq)

            last_send_time += 1.0 / device.max_fps
            remaining = last_send_time - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            else:  # fell behind: snap to now rather than burst to catch up
                last_send_time = time.monotonic()

    def get_device_stats(self) -> list[DeviceStats]:
        """Per-device send statistics; rates cover the last second."""
        now = time.monotonic()
        stats: list[DeviceStats] = []
        for key, state in self._device_state.items():
            device = state.managed
            _trim(state.sent_at, now)
            send_fps = float(len(state.sent_at))
            stats.append(
                DeviceStats(
                    device_name=device.adapter.device_info.name,
                    effective_latency_ms=device.tracker.effective_latency_ms,
                    send_fps=send_fps,
                    frames_dropped=max(0, state.slot.put_count - state.send_count),
                    connected=device.adapter.is_connected,
                    device_id=key,
                    dropped_pct=self._dropped_pct(key, state, send_fps),
                )
            )
        return stats

    def _dropped_pct(self, key: str, state: DeviceSendState, send_fps: float) -> float:
        """How far a streaming light falls short of the frames it should get, in percent."""
        route = self._routes.get(key)
        if (
            route is None
            or not route.streaming
            or self._preview_only
            or not state.managed.adapter.is_connected
        ):
            return 0.0
        expected = min(self._fps, state.managed.max_fps)
        return max(0.0, 1.0 - send_fps / expected) * 100.0
```

(The `# class FrameSlot: unchanged` line marks where the existing `FrameSlot` class stays; don't add the comment.)

- [ ] **Step 10: Drop what the transport left in the core modules**

- `src/dj_ledfx/types.py`: `RenderedFrame.colors` becomes `colors: FloatRGB  # shape (n_leds, 3), linear 0..1`; delete the comment Task 15 added above it, and the `Any` import if nothing else uses it.
- `src/dj_ledfx/events.py`: delete `from dj_ledfx.transport import TransportState` and the `TransportStateChangedEvent` class.
- `src/dj_ledfx/config.py`: delete `unassigned_device_mode` from `EngineConfig` (migration 004 already dropped the saved value).
- `src/dj_ledfx/devices/manager.py`: the zone manager captures lights now (Task 16). Delete the `TransportStateChangedEvent` and `TransportState` imports, the `TYPE_CHECKING` import of `StateDB`, `self._transport_state`, `self._state_db`, the `event_bus.subscribe(TransportStateChangedEvent, ...)` line, `set_state_db`, `_on_transport_changed` and `_capture_device_state`; in `connect_all`, delete the `elif self._transport_state == ...` branch (the loop keeps only the failure log); in `promote_device`, delete the last three lines (the capture comment, the `if` and its `create_task`).
- `tests/test_config.py`: delete `test_engine_config_unassigned_device_mode_default` and `test_engine_config_unassigned_device_mode_idle`.

- [ ] **Step 11: Rewrite `src/dj_ledfx/web/router_effects.py`**

```python
"""The old UI's effect controls and presets, aimed at a zone's classic effect (spec §6.5).

Deleted with the old UI in F11.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request

from dj_ledfx.effects.presets import Preset
from dj_ledfx.effects.registry import get_effect_schemas
from dj_ledfx.web.errors import answers
from dj_ledfx.web.schemas import (
    ActiveEffectResponse,
    CreatePresetRequest,
    PresetResponse,
    SetEffectRequest,
)
from dj_ledfx.web.state import get_zones

router = APIRouter()

ZoneQuery = Annotated[str, Query(description="The zone whose classic effect this is")]


def _known_effect(effect: str | None) -> None:
    if effect is not None and effect not in get_effect_schemas():
        raise HTTPException(status_code=404, detail=f"Unknown effect: {effect}")


def _classic(request: Request, zone: str) -> tuple[str, dict[str, Any]]:
    """The classic effect a zone plays, with its settings; 404 when it plays none."""
    zones = get_zones(request)
    with answers():
        name = zones.get_zone(zone).name
    current = zones.classic_layer(zone)
    if current is None:
        raise HTTPException(status_code=404, detail=f"{name} isn't playing a classic effect")
    return current


@router.get("/effects")
async def list_effects() -> dict[str, Any]:
    schemas = get_effect_schemas()
    result = {}
    for name, params in schemas.items():
        result[name] = {
            k: {
                "type": p.type,
                "default": p.default,
                "min": p.min,
                "max": p.max,
                "step": p.step,
                "choices": p.choices,
                "label": p.label,
                "description": p.description,
            }
            for k, p in params.items()
        }
    return result


@router.get("/effects/active")
async def get_active_effect(request: Request, zone: ZoneQuery) -> ActiveEffectResponse:
    effect, params = _classic(request, zone)
    return ActiveEffectResponse(effect=effect, params=params)


@router.put("/effects/active")
async def set_active_effect(
    request: Request, zone: ZoneQuery, body: SetEffectRequest
) -> ActiveEffectResponse:
    """New settings apply in place; another effect starts its classic look on the zone."""
    _known_effect(body.effect)
    with answers():
        effect, params = await get_zones(request).set_classic_effect(
            zone, body.effect, body.params or {}
        )
    return ActiveEffectResponse(effect=effect, params=params)


@router.get("/presets")
async def list_presets(request: Request) -> list[PresetResponse]:
    store = request.app.state.preset_store
    return [
        PresetResponse(name=p.name, effect_class=p.effect_class, params=p.params)
        for p in store.list()
    ]


@router.post("/presets")
async def save_preset(
    request: Request, zone: ZoneQuery, body: CreatePresetRequest
) -> PresetResponse:
    """Save the classic effect the zone plays, with its settings."""
    effect, params = _classic(request, zone)
    preset = Preset(name=body.name, effect_class=effect, params=params)
    await request.app.state.preset_store.save_async(preset)
    return PresetResponse(name=preset.name, effect_class=preset.effect_class, params=preset.params)


@router.put("/presets/{name}")
async def update_preset(request: Request, name: str, body: SetEffectRequest) -> PresetResponse:
    store = request.app.state.preset_store
    try:
        existing = store.load(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    params = dict(existing.params)
    if body.params:
        params.update(body.params)
    updated = Preset(name=name, effect_class=body.effect or existing.effect_class, params=params)
    await store.save_async(updated)
    return PresetResponse(
        name=updated.name, effect_class=updated.effect_class, params=updated.params
    )


@router.post("/presets/{name}/load")
async def load_preset(request: Request, name: str, zone: ZoneQuery) -> ActiveEffectResponse:
    """Play the preset's effect, with its settings, on the zone."""
    try:
        preset = request.app.state.preset_store.load(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    _known_effect(preset.effect_class)
    with answers():
        effect, params = await get_zones(request).set_classic_effect(
            zone, preset.effect_class, preset.params
        )
    return ActiveEffectResponse(effect=effect, params=params)


@router.delete("/presets/{name}")
async def delete_preset(request: Request, name: str) -> dict[str, str]:
    store = request.app.state.preset_store
    try:
        await store.delete_async(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    return {"status": "deleted"}
```

- [ ] **Step 12: Drop the multi-scene endpoints and the transport schemas**

- `src/dj_ledfx/web/router_scene.py`: delete everything from the `# Multi-scene CRUD endpoints` comment block (including the `# ---` line above it) to the end of the file: `_get_scene_row`, `router_scenes` and its endpoints went with the scene pipelines. Replace `_rebuild_compositor` (the scheduler has no compositor any more; `GET /api/scene` still reads strip indices from it):

```python
def _rebuild_compositor(request: Request, scene: SceneModel) -> None:
    """Rebuild the spatial compositor after a scene mutation."""
    if not scene.placements:
        request.app.state.compositor = None
        return
    mapping = mapping_from_config(request.app.state.config.scene_config or {})
    request.app.state.compositor = SpatialCompositor(scene, mapping)
```

- `src/dj_ledfx/web/schemas.py`: delete `from dj_ledfx.transport import TransportState`, `SceneListItem`, `CreateSceneRequest`, `UpdateSceneRequest`, `TransportBody` and `TransportResponse`.

Then drop the imports those deletions left unused:

```bash
uv run ruff check --fix src/dj_ledfx/web/router_scene.py src/dj_ledfx/web/schemas.py src/dj_ledfx/devices/manager.py src/dj_ledfx/types.py
```

- [ ] **Step 13: Update `src/dj_ledfx/web/ws.py`**

Delete the `TransportStateChangedEvent` and `TransportState` imports, `transport_broadcast`, and the `set_effect` and `set_transport` branches of `_handle_command`. Change the zones import to also bring `PreviewOnlyChanged`:

```python
from dj_ledfx.zones.model import AttentionChanged, LightsChanged, PreviewOnlyChanged, ZonesChanged
```

Add after `_attention_message`:

```python
def _transport_state(zones: Any) -> str:
    """Preview-only in the contract's transport terms (web spec §12.4)."""
    return "simulating" if zones.preview_only else "playing"


def _transport_message(app: Any) -> dict[str, Any] | None:
    zones = getattr(app.state, "zone_manager", None)
    if zones is None:
        return None
    return {"channel": "transport", "state": _transport_state(zones)}
```

Extend the tables:

```python
_SNAPSHOTS: dict[str, Callable[[Any], dict[str, Any] | None]] = {
    "running": _running_message,
    "lights": _lights_message,
    "attention": _attention_message,
    "transport": _transport_message,
}
_STALE_ON: dict[type[Any], str] = {
    ZonesChanged: "running",
    LightsChanged: "lights",
    AttentionChanged: "attention",
    PreviewOnlyChanged: "transport",
}
```

In `_status_poll`, replace `engine.transport_state.value` with:

```python
            "transport": _transport_state(zones) if zones is not None else "playing",
```

and add `zones = getattr(app.state, "zone_manager", None)` next to `engine = app.state.effect_engine`.

- [ ] **Step 14: Update `src/dj_ledfx/web/app.py`**

- Delete `effect_deck: EffectDeck,` and `pipeline_manager: PipelineManager | None = None,` from `create_app`'s signature, their `TYPE_CHECKING` imports, and `app.state.effect_deck = effect_deck` and `app.state.pipeline_manager = pipeline_manager`.
- Delete the `router_scenes` and `transport_router` imports and their `include_router` calls.
- The startup hook starts only the event broadcaster:

```python
    @app.on_event("startup")
    async def _start_broadcasts() -> None:
        if app.state.event_bus is not None:
            from dj_ledfx.web.ws import event_broadcast

            app.state.broadcast_tasks = [asyncio.create_task(event_broadcast(app))]
```

Leave the static-file block (`_file_within`, the SPA fallback and the `/next` routes, if F0 has landed) as it is.

Every test that builds the app loses the two arguments, including PR #10's `tests/web/test_static_fallback.py` and, if F0 has landed, F0's `tests/web/test_next_static.py`:

```bash
sed -i '/effect_deck=MagicMock(),/d' tests/api_home.py tests/web/test_router_config.py tests/web/test_router_devices.py tests/web/test_router_scene.py tests/web/test_static_fallback.py
if [ -f tests/web/test_next_static.py ]; then sed -i '/effect_deck=MagicMock(),/d' tests/web/test_next_static.py; fi
sed -i '/"effect_deck": MagicMock(),/d' tests/web/test_app.py
grep -rn 'effect_deck\b\|pipeline_manager' tests
```

The grep (its `\b` skips Task 18's `test_the_effect_deck_*` names) then finds only `tests/web/test_router_scene.py`. In `tests/web/test_router_scene.py`:
- delete `class TestMultiSceneEndpoints` (to the end of the file);
- in `_make_test_app`, delete the `pipeline_manager` parameter and the `pipeline_manager=pipeline_manager,` argument;
- in `test_compositor_rebuilt_after_mutation`, build the app with `compositor=None,` and replace `assert mock_scheduler.compositor is not None` with `assert isinstance(app.state.compositor, SpatialCompositor)`.

- [ ] **Step 15: Wire zones into `src/dj_ledfx/main.py`**

Imports: delete `BeatPulse`, `EffectDeck` and `PipelineManager`; add

```python
from collections.abc import Coroutine
from typing import Any

from dj_ledfx.looks.store import LookStore
from dj_ledfx.zones.attention import AttentionFeed
from dj_ledfx.zones.lights import LightMonitor
from dj_ledfx.zones.manager import ZoneManager
from dj_ledfx.zones.store import ZoneStore
```

(sorted into the existing blocks). Delete `device_manager.set_state_db(state_db)`.

Replace everything from

```python
    if registered_devices:
        await discovery_orchestrator.connect_known_devices(registered_devices)
```

down to and including `event_bus.subscribe(DeviceOnlineEvent, _on_device_online)` with:

```python
    # Scenes become groups once; zones that were running come back (spec §4.3, §6.5).
    zone_store = ZoneStore(state_db)
    await zone_store.migrate_scenes_once()
    look_store = LookStore(state_db)
    await look_store.load()

    engine = EffectEngine(fps=config.engine.fps)
    scheduler = LookaheadScheduler(
        devices=device_manager.devices, fps=config.engine.fps, event_bus=event_bus
    )
    zone_manager = ZoneManager(
        store=zone_store,
        looks=look_store,
        devices=device_manager,
        db=state_db,
        host=engine,
        routes=scheduler,
        event_bus=event_bus,
        clock=clock,
        fps=config.engine.fps,
        max_lookahead_s=config.engine.max_lookahead_ms / 1000.0,
        preview_only=config.engine.preview_only is True,
    )
    await zone_manager.load()
    # Before any light connects, so no light is restored and then taken over again.
    await zone_manager.resume()

    light_monitor = LightMonitor(devices=device_manager, zones=zone_manager, event_bus=event_bus)
    attention_feed = AttentionFeed(
        zones=zone_manager,
        lights=light_monitor,
        devices=device_manager,
        stats=scheduler.get_device_stats,
        event_bus=event_bus,
    )

    background: set[asyncio.Task[None]] = set()

    def _spawn(work: Coroutine[Any, Any, None]) -> None:
        """Run a zone manager handler off the event bus, keeping a reference to it."""
        task = asyncio.create_task(work)
        background.add(task)
        task.add_done_callback(background.discard)

    def _on_device_offline(event: DeviceOfflineEvent) -> None:
        managed = device_manager.get_by_stable_id(event.stable_id)
        if managed is None or managed.status == "offline":
            return  # the scheduler and the light monitor can both report the same light
        device_manager.demote_device(event.stable_id)
        _spawn(zone_manager.on_device_offline(event.stable_id))
        light_monitor.refresh()

    def _on_device_back(event: DeviceOnlineEvent | DeviceDiscoveredEvent) -> None:
        managed = device_manager.get_by_stable_id(event.stable_id)
        if managed is None:
            return
        if not scheduler.has_device(event.stable_id):
            scheduler.add_device(managed)
        if isinstance(event, DeviceDiscoveredEvent):
            _spawn(zone_manager.on_device_discovered(event.stable_id))
        else:
            _spawn(zone_manager.on_device_online(event.stable_id))
        light_monitor.refresh()

    event_bus.subscribe(DeviceOfflineEvent, _on_device_offline)
    event_bus.subscribe(DeviceOnlineEvent, _on_device_back)
    event_bus.subscribe(DeviceDiscoveredEvent, _on_device_back)

    if registered_devices:
        await discovery_orchestrator.connect_known_devices(registered_devices)
```

In the `create_app(` call, delete `effect_deck=default_deck,` and `pipeline_manager=pipeline_manager,`, change `compositor=default_compositor,` to `compositor=None,`, keep any argument F0 added, and add after `event_bus=event_bus,`:

```python
            look_store=look_store,
            zone_manager=zone_manager,
            light_monitor=light_monitor,
            attention_feed=attention_feed,
```

After `tasks.append(asyncio.create_task(scheduler.run()))`:

```python
    tasks.append(asyncio.create_task(light_monitor.run()))
    tasks.append(asyncio.create_task(attention_feed.run()))
```

In `_status_loop`, replace both `default_ring_buffer.fill_level` with `engine.fill_level`. In the shutdown sequence, after `engine.stop()`:

```python
    light_monitor.stop()
    attention_feed.stop()
```

and replace the task cancellation with:

```python
    for task in [*tasks, *background]:
        task.cancel()
    await asyncio.gather(*tasks, *background, return_exceptions=True)
```

Shutdown leaves the lights as they are: running zones resume at the next start (spec §4.3).

- [ ] **Step 16: Run the tests to see them pass**

Run: `uv run pytest -q`
Expected: PASS (the whole suite: nothing may still import the deleted modules).

Then check nothing refers to what was deleted:

```bash
grep -rn 'TransportState\|EffectDeck\|PipelineManager\|ScenePipeline\|set_state_db' src tests
grep -rln 'unassigned_device_mode' src tests
```

Expected: no output from the first; the second lists only `src/dj_ledfx/persistence/migrations/004_zones_and_looks.sql` and the migration test that saves the old value.

- [ ] **Step 17: Smoke-run the app**

A fresh config directory has no scenes and no running zones, so no light is changed; idle lights are only read.

```bash
tmp=$(mktemp -d)
timeout -s INT 25 uv run python -m dj_ledfx --demo --web --web-port 18099 --config "$tmp/config.toml" > "$tmp/log.txt" 2>&1 &
curl -s --retry 20 --retry-connrefused --retry-delay 1 http://127.0.0.1:18099/api/running; echo
curl -s http://127.0.0.1:18099/api/looks | head -c 120; echo
wait
grep -c Traceback "$tmp/log.txt"; tail -n 3 "$tmp/log.txt"
```

Expected: `{"zones":[],"overlays":[]}`, looks starting with `[{"id":"firmware"`, `0` tracebacks, and the log ending with `dj-ledfx stopped`.

- [ ] **Step 18: Run the gates and commit**

```bash
uv run ruff format src/dj_ledfx/effects/engine.py src/dj_ledfx/scheduling/scheduler.py src/dj_ledfx/main.py src/dj_ledfx/web tests/scheduling/test_scheduler.py tests/effects/test_engine.py tests/test_integration.py tests/web
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add -A src tests
git commit -m "feat: cut over to zones: engine renders zone runtimes, scheduler follows routes"
```

`src/dj_ledfx/spatial/pipeline_manager.py` was the file `ruff format --check` flagged on master, and mypy's baseline errors in the deleted modules go with them: both counts may drop here. Record the new mypy count as the baseline for the remaining tasks.

---

### Task 25: Backup and restore cover zones and looks

Each milestone extends backup and restore to the data it adds (spec §2). M1 adds zones, saved looks, stars and what each zone runs, so `GET /api/state/export` writes them and `POST /api/state/import` reads them back. Restore follows the web spec's wording (§9, Settings → Backup): running looks stop first, then come back from the file. Everything else keeps the endpoint's merge behaviour; "restoring replaces everything" and the `/backup` names are B8's (M6). Captured light states are not backed up: stopping restores every light, and resuming captures afresh.

Look bodies and running looks are JSON strings inside the TOML, because TOML has no null and the contract shape uses it.

**Files:**
- Modify: `src/dj_ledfx/persistence/toml_io.py`
- Modify: `src/dj_ledfx/web/router_config.py`
- Modify: `tests/persistence/test_toml_io.py`
- Modify: `tests/web/test_router_config.py` (remove `test_state_import_with_db`)
- Create: `tests/web/test_backup_api.py`

**Interfaces:**
- Consumes: `ZoneStore.load_zones`, `save_zone`, `load_assignments`, `save_assignment`, `ZoneRecord`, `Assignment`, `ZoneKind` (Task 14); `StateDB.fetch_all`, `write`, `write_many` (Task 13); `builtin_looks` (Task 12); `LookStore.load`, `create`, `set_starred`, `get`, `is_starred` (Task 13); `ZoneManager.stop_all`, `load`, `resume`, `start`, `set_brightness`, `running`, `zones` (Tasks 16 and 17); `get_looks`, `get_zones`, `api_home` (Task 21).
- Produces:
  - Export sections `[zones."<id>"]` (`name`, `kind`, `all_lights`, `lights`), `[looks."<id>"]` (`body`, `created_at`, `updated_at`), `[stars]` (`looks`), `[running."<zone id>"]` (`look_id`, `look`, `brightness`, `lights`, `started_at` as a TOML datetime)
  - `POST /api/state/import`: 400 `Invalid TOML: …` for a file that isn't TOML (nothing changes); otherwise stops every zone, imports, reloads looks and zones, and resumes what the file ran; 503 without a database, look store or zone manager

- [ ] **Step 1: Write the failing persistence test**

Append to `tests/persistence/test_toml_io.py` (add `from datetime import UTC, datetime` to its imports, and the two `dj_ledfx.zones` imports):

```python
from dj_ledfx.zones.model import Assignment, ZoneRecord
from dj_ledfx.zones.store import ZoneStore

STARTED = datetime(2026, 9, 24, 19, 30, 15, 250000, tzinfo=UTC)
INSERT_LOOK = "INSERT INTO looks (id, body, created_at, updated_at) VALUES (?, ?, ?, ?)"
LOOK_ROW = ("mine-0badc0de", '{"name": "Mine", "derivedFrom": null}', "2026-09-24T18:00", "t2")


async def _zones_looks_and_running(db: StateDB) -> None:
    store = ZoneStore(db)
    await store.save_zone(ZoneRecord(id="desk", name="Office desk", lights=("lifx:b", "lifx:a")))
    await store.save_zone(ZoneRecord(id="all-lights", name="All lights", all_lights=True))
    await db.write(INSERT_LOOK, LOOK_ROW)
    await db.write("INSERT INTO look_stars (look_id) VALUES (?)", ("classic-breathe",))
    await store.save_assignment(
        Assignment("desk", "mine-0badc0de", LOOK_ROW[1], 0.5, ("lifx:b",), STARTED)
    )


@pytest.mark.asyncio
async def test_zones_looks_stars_and_running_round_trip(db, tmp_path: Path) -> None:
    await _zones_looks_and_running(db)
    text = await export_toml(db)

    fresh = StateDB(tmp_path / "fresh.db")
    await fresh.open()
    try:
        await import_toml(fresh, text)

        assert await ZoneStore(fresh).load_zones() == await ZoneStore(db).load_zones()
        assert await ZoneStore(fresh).load_assignments() == await ZoneStore(db).load_assignments()
        looks = await fresh.fetch_all("SELECT id, body, created_at, updated_at FROM looks")
        assert looks == [LOOK_ROW]
        assert await fresh.fetch_all("SELECT look_id FROM look_stars") == [("classic-breathe",)]
    finally:
        await fresh.close()


@pytest.mark.asyncio
async def test_import_skips_what_it_cannot_use(db) -> None:
    text = """
[zones.desk]
name = "Desk"
kind = "castle"
lights = ["lifx:a"]

[looks.firmware]
body = "{}"

[looks.mine-nobody]
created_at = "2026-09-24T18:00"

[running.desk]
look_id = "classic-breathe"
look = "{}"
brightness = 0.5
lights = ["lifx:a"]
started_at = "not a time"

[running.nowhere]
look_id = "classic-breathe"
look = "{}"
brightness = 1.0
lights = []
started_at = 2026-09-24T19:00:00Z
"""
    await import_toml(db, text)

    assert await ZoneStore(db).load_zones() == [
        ZoneRecord(id="desk", name="Desk", kind="group", lights=("lifx:a",))
    ]
    assert await db.fetch_all("SELECT id FROM looks") == []
    assert await ZoneStore(db).load_assignments() == []
```

- [ ] **Step 2: Write the failing API tests**

`tests/web/test_backup_api.py`:

```python
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.looks.model import Look
from dj_ledfx.zones.model import ZoneRecord

DESK = ZoneRecord(id="desk", name="Desk", lights=("a",))


def _mine(api: Api) -> Look:
    breathe = api.home.look("classic-breathe")
    return replace(breathe, name="My breathe", built_in=False, derived_from=breathe.id)


async def test_restore_brings_back_zones_looks_stars_and_what_ran(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    (tmp_path / "new").mkdir()
    async with api_home(tmp_path / "old", [FakeLight("a")], [DESK]) as old:
        mine = await old.home.looks.create(_mine(old))
        await old.home.looks.set_starred(mine.id, True)
        await old.home.manager.start("desk", mine)
        await old.home.manager.set_brightness("desk", 0.5)
        await old.home.db.save_preset("Slow", "breathe", json.dumps({"beats_per_cycle": 8}))
        backup = (await old.client.get("/api/state/export")).text

    async with api_home(tmp_path / "new", [FakeLight("a")], []) as new:
        resp = await new.client.post("/api/state/import", content=backup)

        assert resp.status_code == 200
        assert [zone.id for zone in new.home.manager.zones()] == ["desk"]
        assert new.home.looks.get(mine.id).name == "My breathe"
        assert new.home.looks.is_starred(mine.id)
        running = [(r.zone_id, r.look_id, r.brightness) for r in new.home.manager.running()]
        assert running == [("desk", mine.id, 0.5)]
        assert "desk" in new.home.host.runtimes
        assert [p["name"] for p in await new.home.db.load_presets()] == ["Slow"]


async def test_restoring_stops_what_runs_here_first(tmp_path: Path) -> None:
    kitchen = ZoneRecord(id="kitchen", name="Kitchen", lights=("b",))
    lights = [FakeLight("a"), FakeLight("b")]
    async with api_home(tmp_path, lights, [DESK, kitchen]) as api:
        await api.home.manager.start("kitchen", api.home.look("classic-breathe"))

        resp = await api.client.post("/api/state/import", content="")

        assert resp.status_code == 200
        assert api.home.manager.running() == []
        assert ("restore", b"before") in api.home.lights["b"].calls
        assert [zone.id for zone in api.home.manager.zones()] == ["desk", "kitchen"]


async def test_a_file_that_is_not_toml_changes_nothing(tmp_path: Path) -> None:
    async with api_home(tmp_path, [FakeLight("a")], [DESK]) as api:
        await api.home.manager.start("desk", api.home.look("classic-breathe"))

        resp = await api.client.post("/api/state/import", content="this is = = not toml")

        assert resp.status_code == 400
        assert resp.json()["detail"].startswith("Invalid TOML: ")
        assert [r.zone_id for r in api.home.manager.running()] == ["desk"]
```

In `tests/web/test_router_config.py`, delete `test_state_import_with_db`: its app has no zone manager, so the import now answers 503. The round trip above imports a preset instead.

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/persistence/test_toml_io.py tests/web/test_backup_api.py -v`
Expected: FAIL: the fresh database has no zones, looks, stars or assignments; the restore test finds no zones; `this is = = not toml` raises `TOMLDecodeError` instead of answering 400.

- [ ] **Step 4: Export and import the new sections in `src/dj_ledfx/persistence/toml_io.py`**

Replace the module docstring's format list with:

```python
"""TOML import/export marshaling for StateDB.

Export format:
  [config.<section>]          — config key-value pairs
  [devices."<name>"]          — device records keyed by display name
  [scenes."<id>"]             — scene records
  [scenes."<id>".effect]      — scene effect state
  [scenes."<id>".placements."<device_name>"]  — device placements
  [groups."<name>"]           — group metadata + members
  [presets."<name>"]          — preset records
  [zones."<id>"]              — zones: name, kind, all_lights, lights (stable ids, LED order)
  [looks."<id>"]              — saved looks: body (contract JSON), created_at, updated_at
  [stars]                     — looks = ids of starred looks, built in or saved
  [running."<zone id>"]       — what a zone runs: look_id, look (JSON), brightness,
                                lights, started_at

Import merges into what is there. Zones and looks in the file replace those with the
same id, and each running entry becomes that zone's assignment.
"""
```

Change the imports to:

```python
import dataclasses
import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, get_args

import tomli_w
from loguru import logger

from dj_ledfx.looks.builtin import builtin_looks
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.model import Assignment, ZoneKind, ZoneRecord
from dj_ledfx.zones.store import ZoneStore
```

In `export_toml`, before `return tomli_w.dumps(doc)`:

```python
    doc.update(await _export_zones_and_looks(db))
```

At the end of `import_toml`, after the presets loop:

```python
    await _import_zones_and_looks(db, data)
```

Add below `import_toml`:

```python
_UPSERT_LOOK = (
    "INSERT INTO looks (id, body, created_at, updated_at) VALUES (?, ?, ?, ?) "
    "ON CONFLICT(id) DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at"
)
_STAR = "INSERT INTO look_stars (look_id) VALUES (?) ON CONFLICT(look_id) DO NOTHING"


async def _export_zones_and_looks(db: StateDB) -> dict[str, Any]:
    """Zones, saved looks, stars and what each zone runs (M1)."""
    store = ZoneStore(db)
    doc: dict[str, Any] = {}
    zones = await store.load_zones()
    if zones:
        doc["zones"] = {
            zone.id: {
                "name": zone.name,
                "kind": zone.kind,
                "all_lights": zone.all_lights,
                "lights": list(zone.lights),
            }
            for zone in zones
        }
    looks = await db.fetch_all(
        "SELECT id, body, created_at, updated_at FROM looks ORDER BY created_at, id"
    )
    if looks:
        doc["looks"] = {
            look_id: {"body": body, "created_at": created_at, "updated_at": updated_at}
            for look_id, body, created_at, updated_at in looks
        }
    stars = await db.fetch_all("SELECT look_id FROM look_stars ORDER BY look_id")
    if stars:
        doc["stars"] = {"looks": [look_id for (look_id,) in stars]}
    assignments = await store.load_assignments()
    if assignments:
        doc["running"] = {
            a.zone_id: {
                "look_id": a.look_id,
                "look": a.look_json,
                "brightness": a.brightness,
                "lights": list(a.lights),
                "started_at": a.started_at,
            }
            for a in assignments
        }
    return doc


def _tables(data: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    """The sub-tables of a top-level table; anything else there is ignored."""
    table = data.get(key, {})
    if not isinstance(table, dict):
        return {}
    return {name: value for name, value in table.items() if isinstance(value, dict)}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _zone(zone_id: str, info: dict[str, Any]) -> ZoneRecord:
    kind = info.get("kind", "group")
    if kind not in get_args(ZoneKind):
        logger.warning("import_toml: zone '{}' has unknown kind {!r}; using group", zone_id, kind)
        kind = "group"
    return ZoneRecord(
        id=zone_id,
        name=str(info.get("name", zone_id)),
        kind=cast(ZoneKind, kind),
        lights=_strings(info.get("lights")),
        all_lights=bool(info.get("all_lights", False)),
    )


def _assignment(zone_id: str, info: dict[str, Any]) -> Assignment | None:
    look_id, look = info.get("look_id"), info.get("look")
    brightness, started_at = info.get("brightness", 1.0), info.get("started_at")
    if (
        not isinstance(look_id, str)
        or not isinstance(look, str)
        or not isinstance(brightness, int | float)
        or isinstance(brightness, bool)
        or not isinstance(started_at, datetime)
    ):
        return None
    return Assignment(
        zone_id=zone_id,
        look_id=look_id,
        look_json=look,
        brightness=min(max(float(brightness), 0.0), 1.0),
        lights=_strings(info.get("lights")),
        started_at=started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC),
    )


async def _import_zones_and_looks(db: StateDB, data: dict[str, Any]) -> None:
    store = ZoneStore(db)
    for zone_id, info in _tables(data, "zones").items():
        await store.save_zone(_zone(zone_id, info))

    built_in = {look.id for look in builtin_looks()}
    now = datetime.now(UTC).isoformat()
    for look_id, info in _tables(data, "looks").items():
        body = info.get("body")
        if look_id in built_in or not isinstance(body, str):
            logger.warning("import_toml: skipped look '{}' (built in, or no body)", look_id)
            continue
        created_at = str(info.get("created_at", now))
        await db.write(_UPSERT_LOOK, (look_id, body, created_at, str(info.get("updated_at", now))))

    stars = data.get("stars", {})
    starred = _strings(stars.get("looks") if isinstance(stars, dict) else None)
    await db.write_many([(_STAR, (look_id,)) for look_id in starred])

    known = {zone.id for zone in await store.load_zones()}
    for zone_id, info in _tables(data, "running").items():
        assignment = _assignment(zone_id, info) if zone_id in known else None
        if assignment is None:
            logger.warning("import_toml: skipped what zone '{}' was running", zone_id)
            continue
        await store.save_assignment(assignment)
```

The saved look bodies are not validated here: `LookStore.load` already skips a body it can't use, with a warning (spec §8).

- [ ] **Step 5: Stop, import and resume in `src/dj_ledfx/web/router_config.py`**

Change the state import to `from dj_ledfx.web.state import get_db, get_looks, get_zones`, and replace `import_state` with:

```python
@router.post("/state/import")
async def import_state(request: Request) -> dict[str, str]:
    """Restore a backup: running looks stop first, then come back from the file."""
    from dj_ledfx.persistence.toml_io import import_toml

    db = get_db(request)
    try:
        text = (await request.body()).decode()
        tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid TOML: {exc}") from exc
    zones, looks = get_zones(request), get_looks(request)
    await zones.stop_all()
    try:
        await import_toml(db, text)
    finally:
        await looks.load()
        await zones.load()
        await zones.resume()
    return {"status": "ok"}
```

The `finally` keeps the zone manager in step with `state.db` even if the import fails part-way.

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/persistence/test_toml_io.py tests/web/test_backup_api.py tests/web/test_router_config.py -v`
Expected: PASS.

- [ ] **Step 7: Run the gates and commit**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/persistence/toml_io.py src/dj_ledfx/web/router_config.py tests/persistence/test_toml_io.py tests/web/test_backup_api.py tests/web/test_router_config.py
git commit -m "feat(backup): export and restore zones, looks, stars and running zones"
```

---

### Task 26: The old UI gets a minimal look picker

Today's Live page loses its Play / Sim / Stop buttons (the transport is gone) and gains a look picker: pick a zone and a look, **Start** or **Off**, and the **Preview only** switch (spec §2 M1; web spec §11.3, §12). The effect deck works on the chosen zone's classic effect through the `?zone=` endpoints from Task 24, so the six effects stay one click away. The picker names what a start would take over, as the web spec asks ("Takes over the Living room from *Fireflies*"). The new web app replaces all of this in F3/F4.

The old UI has no unit tests and is deleted in F11. Its checks are the type checker, ESLint on the files this task touches (master has 10 ESLint errors elsewhere, none in these files), the build, and a browser check against the real app.

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api-client.ts`, `frontend/src/hooks/use-effects.ts`, `frontend/src/pages/live.tsx`, `frontend/src/pages/config.tsx`
- Rename: `frontend/src/components/transport-section.tsx` → `frontend/src/components/tempo-section.tsx`
- Create: `frontend/src/hooks/use-zones.ts`, `frontend/src/components/look-picker.tsx`
- Delete: `frontend/src/hooks/use-transport.ts`

**Interfaces:**
- Consumes: `GET /api/zones`, `GET /api/looks`, `GET /api/running`, `POST /api/zones/{id}/start`, `POST /api/zones/{id}/off` (Tasks 21 and 22); `PUT /api/config` with `engine.preview_only` (Task 22); WS `running` and `transport` channels (Tasks 22 and 24); the effect and preset endpoints with `?zone=` (Task 24).
- Produces: `useZones()`, `useEffects(zoneId, lookId)`, `<LookPicker>`, `<TempoSection beat>`; API client `getZones`, `getLooks`, `getRunning`, `startLook`, `turnOff`, `setPreviewOnly`, and zone-aware `getActiveEffect`, `setActiveEffect`, `savePreset`, `loadPreset`.

- [ ] **Step 1: Install and record the frontend baseline**

```bash
cd frontend && npm ci && npx tsc --noEmit -p tsconfig.app.json && npx eslint src 2>&1 | grep problems
```

Expected: `tsc` prints nothing; ESLint reports `✖ 10 problems (10 errors, 0 warnings)`. (`npx tsc --noEmit` without `-p` checks nothing: the root `tsconfig.json` only holds references.)

- [ ] **Step 2: Types**

In `frontend/src/lib/types.ts`, give `AppConfig.engine` the new setting:

```ts
  engine: { fps: number; max_lookahead_ms: number; preview_only?: boolean }
```

and replace the last line (`export type TransportState = ...`) with:

```ts
// Zones, looks and what runs: web spec §12.2 names, only the fields the look picker reads

export interface Zone {
  id: string
  name: string
  kind: "home" | "room" | "sub-zone" | "group"
  lights: string[]
}

export interface LookSummary {
  id: string
  name: string
  category: string
  builtIn: boolean
}

export interface RunningZone {
  zoneId: string
  lookId: string
  lookName: string
  since: string
  brightness: number
  lights: string[]
  state: "running" | "transition" | "slow" | "crashed" | "waiting"
  error: { layer: string; message: string; at: string } | null
  waitingFor: string[] | null
}

export interface Running {
  zones: RunningZone[]
}
```

- [ ] **Step 3: API client**

In `frontend/src/lib/api-client.ts`, replace everything from the top of the file through `loadPreset` (the imports, `fetchJson`, the effect functions and the first presets functions) with:

```ts
import type {
  ActiveEffect,
  AppConfig,
  Device,
  DeviceGroup,
  EffectParamSchema,
  LookSummary,
  Preset,
  Running,
  RunningZone,
  SceneData,
  Zone,
} from "./types"

const BASE = "/api"

async function request(path: string, init?: RequestInit): Promise<Response> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`)
  }
  return resp
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  return (await request(path, init)).json() as Promise<T>
}

// The effect deck works on one zone's classic effect
function zone(zoneId: string): string {
  return `zone=${encodeURIComponent(zoneId)}`
}

// Effects
export async function getEffects(): Promise<
  Record<string, Record<string, EffectParamSchema>>
> {
  return fetchJson("/effects")
}

export async function getActiveEffect(zoneId: string): Promise<ActiveEffect | null> {
  const resp = await fetch(`${BASE}/effects/active?${zone(zoneId)}`)
  if (resp.status === 404) return null // the zone isn't playing a classic effect
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json() as Promise<ActiveEffect>
}

export async function setActiveEffect(
  zoneId: string,
  req: { effect?: string; params?: Record<string, unknown> }
): Promise<ActiveEffect> {
  return fetchJson(`/effects/active?${zone(zoneId)}`, {
    method: "PUT",
    body: JSON.stringify(req),
  })
}

// Presets
export async function getPresets(): Promise<Preset[]> {
  return fetchJson("/presets")
}

export async function savePreset(zoneId: string, name: string): Promise<Preset> {
  return fetchJson(`/presets?${zone(zoneId)}`, {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export async function loadPreset(zoneId: string, name: string): Promise<ActiveEffect> {
  return fetchJson(`/presets/${encodeURIComponent(name)}/load?${zone(zoneId)}`, {
    method: "POST",
  })
}
```

and replace the `// Transport` section at the end with:

```ts
// Zones and looks (web spec §12.3)
export async function getZones(): Promise<Zone[]> {
  return fetchJson("/zones")
}

export async function getLooks(): Promise<LookSummary[]> {
  return fetchJson("/looks")
}

export async function getRunning(): Promise<Running> {
  return fetchJson("/running")
}

export async function startLook(zoneId: string, lookId: string): Promise<RunningZone> {
  return fetchJson(`/zones/${encodeURIComponent(zoneId)}/start`, {
    method: "POST",
    body: JSON.stringify({ lookId }),
  })
}

export async function turnOff(zoneId: string): Promise<void> {
  await request(`/zones/${encodeURIComponent(zoneId)}/off`, { method: "POST" })
}

export async function setPreviewOnly(on: boolean): Promise<AppConfig> {
  return fetchJson("/config", {
    method: "PUT",
    body: JSON.stringify({ engine: { preview_only: on } }),
  })
}
```

- [ ] **Step 4: Write `frontend/src/hooks/use-zones.ts`**

```ts
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import * as api from "@/lib/api-client"
import type { LookSummary, RunningZone, Zone } from "@/lib/types"
import { wsClient } from "@/lib/ws-client"

function report(e: unknown) {
  toast.error(e instanceof Error ? e.message : String(e))
}

/** Zones, looks and what runs; the `running` and `transport` channels keep them current. */
export function useZones() {
  const [zones, setZones] = useState<Zone[]>([])
  const [looks, setLooks] = useState<LookSummary[]>([])
  const [running, setRunning] = useState<RunningZone[]>([])
  const [previewOnly, setPreviewOnlyState] = useState(false)

  useEffect(() => {
    Promise.all([api.getZones(), api.getLooks(), api.getRunning(), api.getConfig()])
      .then(([zoneList, lookList, now, config]) => {
        setZones(zoneList)
        setLooks(lookList)
        setRunning(now.zones)
        setPreviewOnlyState(config.engine.preview_only ?? false)
      })
      .catch(report)
    const offRunning = wsClient.on("running", (msg) => {
      setRunning(msg.zones as RunningZone[])
    })
    const offTransport = wsClient.on("transport", (msg) => {
      setPreviewOnlyState(msg.state === "simulating")
    })
    return () => {
      offRunning()
      offTransport()
    }
  }, [])

  const start = useCallback(async (zoneId: string, lookId: string) => {
    try {
      await api.startLook(zoneId, lookId)
      setRunning((await api.getRunning()).zones)
    } catch (e) {
      report(e)
    }
  }, [])

  const off = useCallback(async (zoneId: string) => {
    try {
      await api.turnOff(zoneId)
      setRunning((await api.getRunning()).zones)
    } catch (e) {
      report(e)
    }
  }, [])

  const setPreviewOnly = useCallback(async (on: boolean) => {
    try {
      const config = await api.setPreviewOnly(on)
      setPreviewOnlyState(config.engine.preview_only ?? on)
    } catch (e) {
      report(e)
    }
  }, [])

  return { zones, looks, running, previewOnly, start, off, setPreviewOnly }
}
```

- [ ] **Step 5: Aim the effect deck at a zone in `frontend/src/hooks/use-effects.ts`**

Replace the file with:

```ts
import { useCallback, useEffect, useState } from "react"
import * as api from "@/lib/api-client"
import type { ActiveEffect, EffectParamSchema, Preset } from "@/lib/types"

type ZoneEffect = ActiveEffect & { zoneId: string }

/**
 * The effect deck works on one zone's classic effect. `lookId` is the look the zone
 * runs (null when it's off), so the deck reloads whenever that changes.
 */
export function useEffects(zoneId: string | null, lookId: string | null) {
  const [schemas, setSchemas] = useState<
    Record<string, Record<string, EffectParamSchema>>
  >({})
  const [active, setActive] = useState<ZoneEffect | null>(null)
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getEffects(), api.getPresets()])
      .then(([effects, presetList]) => {
        setSchemas(effects)
        setPresets(presetList)
      })
      .catch((e) => console.error("Failed to init effects:", e))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (zoneId === null || lookId === null) return
    let current = true
    api
      .getActiveEffect(zoneId)
      .then((effect) => {
        if (current) setActive({ zoneId, effect: effect?.effect ?? "", params: effect?.params ?? {} })
      })
      .catch((e) => console.error("Failed to load the zone's effect:", e))
    return () => {
      current = false
    }
  }, [zoneId, lookId])

  const shown = lookId !== null && active?.zoneId === zoneId ? active : null

  const switchEffect = useCallback(
    async (name: string) => {
      if (zoneId === null) return
      setActive({ zoneId, ...(await api.setActiveEffect(zoneId, { effect: name })) })
    },
    [zoneId]
  )

  const updateParam = useCallback(
    async (key: string, value: unknown) => {
      if (zoneId === null) return
      const result = await api.setActiveEffect(zoneId, { params: { [key]: value } })
      setActive({ zoneId, ...result })
    },
    [zoneId]
  )

  const loadPreset = useCallback(
    async (name: string) => {
      if (zoneId === null) return
      setActive({ zoneId, ...(await api.loadPreset(zoneId, name)) })
    },
    [zoneId]
  )

  const savePreset = useCallback(
    async (name: string) => {
      if (zoneId === null) return
      await api.savePreset(zoneId, name)
      setPresets(await api.getPresets())
    },
    [zoneId]
  )

  const removePreset = useCallback(async (name: string) => {
    await api.deletePreset(name)
    setPresets(await api.getPresets())
  }, [])

  return {
    schemas,
    activeEffect: shown?.effect ?? "",
    activeParams: shown?.params ?? {},
    presets,
    loading,
    switchEffect,
    updateParam,
    loadPreset,
    savePreset,
    removePreset,
  }
}
```

- [ ] **Step 6: Write `frontend/src/components/look-picker.tsx`**

```tsx
import { useState } from "react"
import type { LookSummary, RunningZone, Zone } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface LookPickerProps {
  zones: Zone[]
  looks: LookSummary[]
  running: RunningZone[]
  previewOnly: boolean
  zoneId: string | null
  onZoneChange: (zoneId: string) => void
  onStart: (zoneId: string, lookId: string) => Promise<void>
  onOff: (zoneId: string) => Promise<void>
  onPreviewOnlyChange: (on: boolean) => Promise<void>
}

function describe(zone: RunningZone): string {
  const since = new Date(zone.since).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  switch (zone.state) {
    case "crashed":
      return `${zone.lookName} crashed: ${zone.error?.message ?? "no details"}`
    case "waiting":
      return `${zone.lookName} is waiting for ${(zone.waitingFor ?? []).join(", ")}`
    case "slow":
      return `${zone.lookName} since ${since}, running slow`
    default:
      return `${zone.lookName} since ${since}`
  }
}

/** What starting a look here would take from other running zones (web spec §11.3). */
function consequence(zone: Zone, zones: Zone[], running: RunningZone[]): string | null {
  const parts: string[] = []
  for (const other of running) {
    if (other.zoneId === zone.id) continue
    const shared = other.lights.filter((light) => zone.lights.includes(light)).length
    if (shared === 0) continue
    const name = zones.find((z) => z.id === other.zoneId)?.name ?? other.zoneId
    const what = shared === other.lights.length ? name : `${shared} of ${name}'s lights`
    parts.push(`${what} from ${other.lookName}`)
  }
  return parts.length > 0 ? `Takes over ${parts.join(" and ")}` : null
}

export function LookPicker({
  zones,
  looks,
  running,
  previewOnly,
  zoneId,
  onZoneChange,
  onStart,
  onOff,
  onPreviewOnlyChange,
}: LookPickerProps) {
  const [lookChoice, setLookChoice] = useState<string | null>(null)
  const zone = zones.find((z) => z.id === zoneId) ?? null
  const playing = running.find((r) => r.zoneId === zoneId) ?? null
  const lookId = lookChoice ?? playing?.lookId ?? looks[0]?.id ?? null
  const note = zone ? consequence(zone, zones, running) : null

  return (
    <div className="flex items-center gap-3 p-3 bg-card ring-1 ring-foreground/10 rounded-xl">
      <Select
        items={Object.fromEntries(zones.map((z) => [z.id, z.name]))}
        value={zoneId}
        onValueChange={(v: string | null) => {
          if (v === null) return
          setLookChoice(null)
          onZoneChange(v)
        }}
      >
        <SelectTrigger className="h-8 w-44 text-sm">
          <SelectValue placeholder="Zone" />
        </SelectTrigger>
        <SelectContent>
          {zones.map((z) => (
            <SelectItem key={z.id} value={z.id} className="text-sm">
              {z.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        items={Object.fromEntries(looks.map((look) => [look.id, look.name]))}
        value={lookId}
        onValueChange={(v: string | null) => {
          if (v !== null) setLookChoice(v)
        }}
      >
        <SelectTrigger className="h-8 w-52 text-sm">
          <SelectValue placeholder="Look" />
        </SelectTrigger>
        <SelectContent>
          {looks.map((look) => (
            <SelectItem key={look.id} value={look.id} className="text-sm">
              {look.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        size="sm"
        disabled={zone === null || lookId === null}
        onClick={() => {
          if (zone !== null && lookId !== null) void onStart(zone.id, lookId)
        }}
      >
        Start
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={playing === null}
        onClick={() => {
          if (playing !== null) void onOff(playing.zoneId)
        }}
      >
        Off
      </Button>

      <div className="flex flex-col gap-0.5 min-w-0 flex-1 text-xs">
        <span className="truncate">{playing ? describe(playing) : "No look on"}</span>
        {note && <span className="truncate text-muted-foreground">{note}</span>}
      </div>

      <Label className="text-xs shrink-0">
        <Switch
          checked={previewOnly}
          onCheckedChange={(on: boolean) => {
            void onPreviewOnlyChange(on)
          }}
        />
        Preview only
      </Label>
    </div>
  )
}
```

- [ ] **Step 7: Keep the tempo display, drop the transport**

```bash
git mv frontend/src/components/transport-section.tsx frontend/src/components/tempo-section.tsx
git rm -q frontend/src/hooks/use-transport.ts
```

In `tempo-section.tsx`: change the first two imports to

```tsx
import { useLayoutEffect, useRef, useState } from "react"
import type { BeatState } from "@/lib/types"
```

delete the `Button` and `lucide-react` imports; replace everything from `interface TransportSectionProps` down to (not including) `{/* BPM — most prominent */}` with

```tsx
/** Tempo from the beat clock. Looks start and stop from the look picker now. */
export function TempoSection({ beat }: { beat: BeatState }) {
  const { bpm, beatPhase, barPhase, isPlaying, beatPos, pitchPercent, deckName } = beat

  const bpmDisplay = bpm > 0 ? bpm.toFixed(1) : "---.-"

  return (
    <div className="flex items-stretch gap-4 p-3 bg-card ring-1 ring-foreground/10 rounded-xl">
```

This removes the Play / Sim / Stop buttons, their Space and S shortcuts, and the divider after them. `BeatGrid`, the BPM, the LIVE badge and the deck info stay as they are.

- [ ] **Step 8: Wire the Live page**

Replace `frontend/src/pages/live.tsx` with:

```tsx
import { useState } from "react"
import { useBeat } from "@/hooks/use-beat"
import { useEffects } from "@/hooks/use-effects"
import { useDevices } from "@/hooks/use-devices"
import { useScene } from "@/hooks/use-scene"
import { useZones } from "@/hooks/use-zones"
import { LookPicker } from "@/components/look-picker"
import { TempoSection } from "@/components/tempo-section"
import { EffectDeck } from "@/components/effect-deck"
import { DeviceMonitor } from "@/components/device-monitor"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"

export default function LivePage() {
  const beat = useBeat()
  const home = useZones()
  const [chosenZone, setChosenZone] = useState<string | null>(null)
  const zoneId = chosenZone ?? home.running[0]?.zoneId ?? home.zones[0]?.id ?? null
  const lookId = home.running.find((r) => r.zoneId === zoneId)?.lookId ?? null
  const effects = useEffects(zoneId, lookId)
  const { devices, frameData } = useDevices()
  const { scene } = useScene()

  const placements = scene?.placements ?? []

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Put a look on a zone */}
      <LookPicker
        zones={home.zones}
        looks={home.looks}
        running={home.running}
        previewOnly={home.previewOnly}
        zoneId={zoneId}
        onZoneChange={setChosenZone}
        onStart={home.start}
        onOff={home.off}
        onPreviewOnlyChange={home.setPreviewOnly}
      />

      {/* Tempo */}
      <TempoSection beat={beat} />

      {/* Middle: Scene preview + Effect deck */}
      <div className="flex gap-3 flex-1 min-h-0">
        {/* Live 3D scene preview */}
        <div className="flex-1 min-w-0 min-h-0 rounded-lg border border-border overflow-hidden">
          <SceneViewport>
            {placements.map((p) => (
              <DeviceMesh
                key={p.device_id}
                position={p.position}
                geometry={p.geometry}
                ledCount={p.led_count}
                frameData={frameData.get(p.device_id) ?? null}
              />
            ))}
          </SceneViewport>
        </div>

        {/* Effect deck: the chosen zone's classic effect */}
        <div className="w-80 shrink-0 min-h-0">
          <EffectDeck
            schemas={effects.schemas}
            activeEffect={effects.activeEffect}
            activeParams={effects.activeParams}
            presets={effects.presets}
            loading={effects.loading}
            switchEffect={effects.switchEffect}
            updateParam={effects.updateParam}
            loadPreset={effects.loadPreset}
            savePreset={effects.savePreset}
          />
        </div>
      </div>

      {/* Device monitor strip */}
      <DeviceMonitor devices={devices} frameData={frameData} />
    </div>
  )
}
```

- [ ] **Step 9: Stop the Config page sending preview-only back**

The Config page sends its whole draft on Apply, which would put back the preview-only value it loaded. In `frontend/src/pages/config.tsx`, `handleApply`, replace `const updated = await updateConfig(draft)` with:

```tsx
      // Preview only is switched on the Live page: don't send back the value loaded here
      const engine = { fps: draft.engine.fps, max_lookahead_ms: draft.engine.max_lookahead_ms }
      const updated = await updateConfig({ ...draft, engine })
```

- [ ] **Step 10: Type-check, lint and build**

```bash
cd frontend
npx tsc --noEmit -p tsconfig.app.json
npx eslint src/lib/types.ts src/lib/api-client.ts src/hooks/use-zones.ts src/hooks/use-effects.ts src/components/look-picker.tsx src/components/tempo-section.tsx src/pages/live.tsx src/pages/config.tsx
npm run build
grep -rn 'TransportState\|use-transport\|transport-section\|getTransport\|setTransport' src
```

Expected: no output from `tsc`, ESLint or the grep; the build ends with Vite's `✓ built in …`.

- [ ] **Step 11: Check it in a browser**

Run the app from a scratch config directory, so the repo's `state.db` isn't touched, and switch preview-only on before anything starts. The lights on the LAN are discovered, but preview-only sends them nothing (Task 17's Review Focus test).

```bash
tmp=$(mktemp -d)
uv run python -m dj_ledfx --demo --web --web-port 18099 --config "$tmp/config.toml" > "$tmp/log.txt" 2>&1 &
app=$!
curl -s --retry 20 --retry-connrefused --retry-delay 1 -X PUT http://127.0.0.1:18099/api/config \
  -H 'Content-Type: application/json' -d '{"engine": {"preview_only": true}}' | head -c 80; echo
```

Expected: the reply starts `{"engine":{"fps":60,"max_lookahead_ms":1000,"preview_only":true`.

With the Playwright browser tools, open `http://127.0.0.1:18099/` and check, in order:

1. The look picker shows the zone **All lights** and the look **Firmware showcase**; **Preview only** is on; the state line reads "No look on".
2. Pick **Breathe**, press **Start**: the state line reads "Breathe since HH:MM" and the effect deck shows Breathe's parameters.
3. Move one deck slider: no error toast.
4. Press **Off**: the state line reads "No look on".
5. Switch **Preview only** off. Nothing runs, so nothing is sent.
6. On the Config page, change the frame rate and **Apply**: "Configuration saved".

Take one screenshot of the Live page after step 2 (`m1-look-picker.png`), then stop the app and confirm preview-only stayed off through the Apply:

```bash
curl -s http://127.0.0.1:18099/api/config | python3 -c 'import json, sys; print(json.load(sys.stdin)["engine"]["preview_only"])'
kill -INT $app; wait $app
grep -c Traceback "$tmp/log.txt"
```

Expected: `False`, then `0`.

- [ ] **Step 12: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): minimal look picker on the Live page; transport controls removed"
```

---

### Task 27: Deploy on the host network

Spec §6.7: commit the Dockerfile, compose file and `.dockerignore`; host networking, `restart: unless-stopped`, `state.db` on a volume, `config.toml` mounted, no `--demo`. Drafts of the three files sit untracked in the main checkout (`/home/anirudhlath/code/private/dj-ledfx/`); this task replaces them. The running container shows why each change is needed:

- It serves nothing. The web server binds `web.host` = `127.0.0.1` inside the container, so the published port reaches nothing. And `uv pip install --system .` puts the package in site-packages, where the app never finds `frontend/dist`. The new image passes `--web-host 0.0.0.0` and installs the project editable with `uv sync`, so `frontend/dist` and `web/dist` (the new app at `/next`, once F0 lands) sit where `web/app.py` looks.
- It finds no lights. Bridge networking hides LIFX broadcast discovery, Pro DJ Link and the OpenRGB server on the host's `127.0.0.1:6742`.
- Its `state.db` lives in the container layer, so every rebuild loses it.
- `config.toml` is a single-file bind mount, which can't be renamed or replaced: the first-start migration's rename to `.bak`, and every `PUT /api/config` (`atomic_toml_write`'s `os.replace`), would fail on it. It's now mounted read-only and only seeds a fresh `state.db`, which is the source of truth (CLAUDE.md). Both writers tolerate that.
- The migration stores values with `str()`, so `false` becomes `"False"` (a true string) and lists become their Python repr: the gotcha CLAUDE.md already records. The tracked `config.toml` carries those strings from an earlier save.

Without `--demo` the beat clock moves only with Pro DJ Link, so classic tempo looks hold still until a DJ plays (M3 brings the internal clock). Firmware looks run by themselves.

**Files:**
- Modify: `src/dj_ledfx/config.py` (`atomic_toml_write`, `save_config`)
- Modify: `src/dj_ledfx/persistence/toml_io.py` (`migrate_from_toml`, `_migrate_config_toml`)
- Modify: `config.toml`
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Test: `tests/test_config.py`, `tests/persistence/test_toml_io.py`; modify `tests/persistence/test_state_db.py` (`test_migrate_from_config_toml` reads a stored value as JSON)

**Interfaces:**
- Consumes: the CLI flags `--web`, `--web-host`, `--config`, `--db`; F0's `web/dist` serving (if merged).
- Produces: `save_config` logs instead of raising when the file can't be written; `migrate_from_toml` leaves a file it can't rename in place; migrated config values are stored as JSON. The `dj-ledfx` compose project: container `dj-ledfx-app-1`, volume `dj-ledfx_state`, web UI on the host's port 8080.

- [ ] **Step 1: Write the failing tests**

In `tests/test_config.py`, add `import errno` to the imports and append:

```python
def test_save_config_leaves_a_file_it_cannot_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The container mounts config.toml read-only; state.db is the source of truth."""
    path = tmp_path / "config.toml"
    path.write_text("[engine]\nfps = 30\n")

    def busy(src: object, dst: object) -> None:
        raise OSError(errno.EBUSY, "Device or resource busy")

    monkeypatch.setattr("dj_ledfx.config.os.replace", busy)

    save_config(AppConfig(), path)

    assert path.read_text() == "[engine]\nfps = 30\n"
    assert not (tmp_path / "config.tmp").exists()
```

In `tests/persistence/test_toml_io.py`, add `import errno` and `migrate_from_toml` to the imports and append:

```python
@pytest.mark.asyncio
async def test_migration_keeps_value_types(tmp_path: Path) -> None:
    config_toml = tmp_path / "config.toml"
    config_toml.write_text(
        '[network]\ninterface = "auto"\npassive_mode = false\n\n'
        '[web]\ncors_origins = ["http://localhost:5173"]\n'
    )
    db = StateDB(tmp_path / "state.db")
    await db.open()
    try:
        await migrate_from_toml(db, config_path=config_toml)
        config = await db.load_all_config()
    finally:
        await db.close()

    assert config[("network", "interface")] == "auto"
    assert config[("network", "passive_mode")] is False
    assert config[("web", "cors_origins")] == ["http://localhost:5173"]


@pytest.mark.asyncio
async def test_migration_leaves_a_file_it_cannot_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bind-mounted config.toml can't be renamed; the migration still counts."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("[engine]\nfps = 90\n")

    def busy(self: Path, target: object) -> Path:
        raise OSError(errno.EBUSY, "Device or resource busy")

    monkeypatch.setattr(Path, "rename", busy)
    db = StateDB(tmp_path / "state.db")
    await db.open()
    try:
        await migrate_from_toml(db, config_path=config_toml)
        config = await db.load_all_config()
    finally:
        await db.close()

    assert config[("engine", "fps")] == 90
    assert config_toml.exists()
```

In `tests/persistence/test_state_db.py`, `test_migrate_from_config_toml`, the stored value is JSON now. Replace

```python
    assert network_cfg.get("interface") == "192.168.1.100"
```

with

```python
    assert json.loads(network_cfg["interface"]) == "192.168.1.100"
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_config.py tests/persistence/test_toml_io.py tests/persistence/test_state_db.py -v`
Expected: FAIL: `save_config` raises `OSError: [Errno 16] Device or resource busy`; the migration stores `"False"` and `"['http://localhost:5173']"` as strings; the rename raises; `json.loads` fails on the unquoted `192.168.1.100`.

- [ ] **Step 3: Tolerate an unwritable config file in `src/dj_ledfx/config.py`**

Replace `atomic_toml_write` and `save_config` with:

```python
def atomic_toml_write(data: dict[str, Any], path: Path) -> None:
    """Atomically write a dict as TOML via tmp + os.replace."""
    import tomli_w

    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(tomli_w.dumps(data).encode())
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def save_config(config: AppConfig, path: Path) -> None:
    """Mirror the config to TOML. state.db is the source of truth, so a file that can't be
    written (the container mounts config.toml read-only) only logs a warning."""
    import dataclasses

    data = dataclasses.asdict(config)
    strip_none(data)
    try:
        atomic_toml_write(data, path)
    except OSError as exc:
        logger.warning("Config not written to {}: {}", path, exc)
```

- [ ] **Step 4: Fix the migration in `src/dj_ledfx/persistence/toml_io.py`**

In `migrate_from_toml`, change the docstring's second bullet to `- If the file exists, parse it, import data into DB, rename to .bak (or leave it, with a warning, when it can't be renamed).` and replace the two blocks that rename with:

```python
    if config_path is not None and config_path.exists():
        await _migrate_config_toml(db, config_path)
        _set_aside(config_path)

    if presets_path is not None and presets_path.exists():
        await _migrate_presets_toml(db, presets_path)
        _set_aside(presets_path)
```

Add below `migrate_from_toml`:

```python
def _set_aside(path: Path) -> None:
    """Rename a migrated file to .bak. A file that can't be renamed (config.toml is mounted
    read-only in the container) stays where it is: the database is the source of truth."""
    bak = path.with_suffix(".toml.bak")
    try:
        path.rename(bak)
    except OSError as exc:
        logger.warning("migrate_from_toml: left {} in place ({})", path, exc)
        return
    logger.info("migrate_from_toml: migrated {}, backed up to {}", path, bak)
```

In `_migrate_config_toml`, store JSON like every other config write (the gotcha in CLAUDE.md): replace `str(v)` with `json.dumps(v)` in both `str_kv` and `nested_kv`, and change the comment above `str_kv` to `# Top-level keys (non-dict values), as JSON like every other config write`.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/test_config.py tests/persistence tests/test_integration.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the fixes**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add src/dj_ledfx/config.py src/dj_ledfx/persistence/toml_io.py tests/test_config.py tests/persistence/test_toml_io.py tests/persistence/test_state_db.py
git commit -m "fix(config): keep value types when migrating config.toml; tolerate a read-only config file"
```

- [ ] **Step 7: Give `config.toml` real types**

In the tracked `config.toml`, the `[network]` and `[web]` sections become:

```toml
[network]
interface = "auto"
passive_mode = true

[web]
enabled = false
host = "127.0.0.1"
port = 8080
cors_origins = ["http://localhost:5173", "http://localhost:4173", "http://localhost:8080"]
```

These are the values the strings meant. (`"False"` was a true string, so the web UI started without `--web` on a fresh database; CLAUDE.md's commands all pass `--web`.) Check nothing else is a quoted boolean or list:

```bash
grep -nE '= "(True|False|\[.*\])"' config.toml
```

Expected: no output.

- [ ] **Step 8: Write the deployment files**

`Dockerfile`:

```dockerfile
# dj-ledfx: the home lighting engine and its web UIs (engine spec §6.7).
# Deploy with docker compose: see docker-compose.yml.

# Stage 1: the web UIs. frontend/ is today's UI; web/ is the new app, served at /next
# once F0 has landed (until then web/dist stays empty).
FROM node:24-slim AS ui
WORKDIR /build
COPY . .
RUN cd frontend && npm ci && npm run build
RUN if [ -f web/package.json ]; then cd web && npm ci && npm run build; else mkdir -p web/dist; fi

# Stage 2: the engine, installed editable so it finds frontend/dist and web/dist.
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --extra web --extra metrics --no-install-project
COPY src/ src/
RUN uv sync --frozen --no-dev --extra web --extra metrics
COPY --from=ui /build/frontend/dist frontend/dist
COPY --from=ui /build/web/dist web/dist
ENV PATH="/app/.venv/bin:$PATH"

# config.toml is mounted read-only and only seeds a fresh state.db, which lives on a
# volume. No --demo: the beat comes from Pro DJ Link.
CMD ["python", "-m", "dj_ledfx", "--web", "--web-host", "0.0.0.0", \
     "--config", "/app/config/config.toml", "--db", "/app/state/state.db"]
```

The image's Python matches `.python-version` (3.14), which the tests run on. Node 24 meets F0's floor (^22.22.2, ^24.15 or 26+).

`docker-compose.yml`:

```yaml
# dj-ledfx on this host (engine spec §6.7): docker compose up -d --build
#
# Host networking: LIFX broadcast discovery and Pro DJ Link need it. The web UI listens on
# the host's port 8080, so the host firewall (UFW) decides who reaches it, not Docker.
name: dj-ledfx  # the same stack from whichever checkout this runs

services:
  app:
    build: .
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./config.toml:/app/config/config.toml:ro  # seeds a fresh state.db; never written
      - state:/app/state                           # state.db, the source of truth

volumes:
  state:
```

`.dockerignore`:

```
.git
.venv
**/__pycache__
**/*.pyc
.mypy_cache
.ruff_cache
.pytest_cache
.env
.superpowers
.worktrees
.playwright-mcp
docs/
tests/
monitoring/
scripts/
profiles/
frontend/node_modules
frontend/dist
web/node_modules
web/dist
*.db
*.db-wal
*.db-shm
*.bak
```

- [ ] **Step 9: Build the image**

```bash
docker compose build
docker run --rm --entrypoint sh dj-ledfx-app -c 'ls /app/frontend/dist/index.html /app/web/dist; python --version; python -c "import dj_ledfx.web.app"'
```

Expected: the build succeeds; `/app/frontend/dist/index.html` exists, `web/dist` lists F0's build (or nothing before F0), Python 3.14, and the import succeeds.

- [ ] **Step 10: Check LAN reachability before switching**

With host networking the host firewall governs port 8080 (spec §6.7). Serve a throwaway page on a free port and fetch it from another machine on the LAN, the satellite Pi `pi1` (`192.168.50.224`, key and user from `/home/anirudhlath/code/alfred-deploy/satellites.yaml`):

```bash
python3 -m http.server 18080 --bind 0.0.0.0 --directory "$(mktemp -d)" > /dev/null 2>&1 &
probe=$!
ssh -i /home/anirudhlath/code/alfred-deploy/id_ed25519_satellites -o BatchMode=yes anirudhlath@192.168.50.224 \
  'curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://192.168.50.158:18080/'
kill $probe
sudo -n ufw status verbose | grep -E 'Default|192.168.50|tailscale0|8080'
```

Expected: `200`, and UFW allows `192.168.50.0/24` in. If the Pi doesn't get `200`, stop and ask the owner; don't change UFW. If `sudo -n` needs a password, ask the owner to run `sudo ufw status verbose` and paste the result.

- [ ] **Step 11: Back up the old database and switch**

The old container keeps `state.db` in its layer, and recreating it deletes that. Its database holds one scene with no placements, no devices and no presets, so the new stack starts fresh; keep a copy anyway (`*.bak` is gitignored):

```bash
docker exec dj-ledfx-app-1 python -c "import sqlite3; dst = sqlite3.connect('/tmp/state-backup.db'); sqlite3.connect('/app/state.db').backup(dst); dst.close()"
docker cp dj-ledfx-app-1:/tmp/state-backup.db /home/anirudhlath/code/private/dj-ledfx/state.db.pre-m1.bak
docker compose -f /home/anirudhlath/code/private/dj-ledfx/docker-compose.yml -p dj-ledfx down
docker compose up -d
```

The last command runs in this worktree. To roll back: `docker compose down` here, then `docker compose up -d --build` in the main checkout, whose untracked files are the old stack (`--build`, because Step 9 gave the new image the old one's tag).

- [ ] **Step 12: Verify from the LAN**

```bash
docker compose ps --format '{{.Name}} {{.Status}}'
docker compose logs app 2>&1 | grep -E 'ERROR|Traceback|could not bind' | head -5
curl -s http://127.0.0.1:8080/api/running; echo
curl -s http://127.0.0.1:8080/api/lights | python3 -c 'import json, sys; print(len(json.load(sys.stdin)), "lights")'
ssh -i /home/anirudhlath/code/alfred-deploy/id_ed25519_satellites -o BatchMode=yes anirudhlath@192.168.50.224 \
  'curl -s -o /dev/null -w "%{http_code} /\n" http://192.168.50.158:8080/; curl -s http://192.168.50.158:8080/next | grep -c /next/assets/'
```

Expected:

- `dj-ledfx-app-1 Up …`.
- No errors. While Home Assistant's Govee integration holds UDP 4002 (`ss -ulpn | grep 4002` shows `192.168.50.158:4002`), the log warns `Govee: could not bind port 4002 …`; note it for Task 28.
- `{"zones":[],"overlays":[]}`: nothing runs after the migration.
- A light count close to the home's (spec §6.6); LIFX discovery takes about 10 s, so run it again if it's low.
- `200 /` from the Pi. With F0 merged, `/next` serves the new app (a count of 1 or more); without it, the count is 0.

Then open `http://192.168.50.158:8080/` in a browser (the Playwright tools) and check the Live page's look picker lists the migrated zone. It is **Default**, following every light: `config.toml`'s `[effect]` section makes the old default scene on a fresh database, and Task 14's migration turns that scene into a zone.

- [ ] **Step 13: Ask about Tailscale**

The old compose file advertised `http://admin.anirudhlath.com:8080` over Tailscale, which only worked because Docker's published ports bypass UFW. On `tailscale0`, UFW allows only ports 22 and 8888. Ask the owner whether to allow 8080 there (`sudo ufw allow in on tailscale0 to any port 8080 proto tcp`). Don't change UFW without a yes.

- [ ] **Step 14: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore config.toml
git commit -m "feat(deploy): host-network container with state.db on a volume and a read-only config"
```

Until this branch merges, the container's `config.toml` mount points into this worktree. After the merge, redeploy from the main checkout (Task 32 lists the commands in the PR).

---

### Task 28: Check it on the real lights

M1's demo is the Firmware showcase (spec §2), and spec §11 risk 2 asks for Flame and Morph on the Candles and Tube, and Move on the Neon, to be checked on the real lights. This task records real LIFX replies as fixtures next to Task 4's packed ones, then walks the deployed app through the sharing policy (spec §6.4) and always-on behaviour (§7.1) with the owner watching the lights.

The checks run against the container from Task 27 on `http://127.0.0.1:8080`. Ask the owner before each step that changes lights, and ask them to say what each light shows; you can't see the lights. Record every result (pass, or what happened instead) for the PR description (Task 32). A failure that is a bug gets a failing test and a fix before the checklist carries on; anything else goes in the PR as a finding.

**Files:**
- Create: `scripts/lifx_record_fixtures.py`
- Create: `tests/devices/lifx/test_recorded_packets.py`
- Create: `tests/fixtures/lifx/recorded/*.hex` (written by the script)

**Interfaces:**
- Consumes: `LifxTransport.open`, `discover`, `make_request`, `request_response`, `query_host_firmware`, `close` (Task 5); `lifx_product` (Task 6); the Task 4 codec; the REST API (Tasks 21–23).
- Produces: `scripts/lifx_record_fixtures.py` (read-only: it sends Get messages only); fixtures named `<pid>-<product slug>-<message>.hex`, each a comment line and one line of hex payload, without MACs or addresses.

- [ ] **Step 1: Write the recorder**

`scripts/lifx_record_fixtures.py`:

```python
"""Record replies from the LIFX lights on this LAN as test fixtures (M1 plan, Task 28).

Read-only: it sends Get messages and writes each reply's payload to
tests/fixtures/lifx/recorded/<pid>-<product>-<message>.hex. Run from the repo root:

    uv run python scripts/lifx_record_fixtures.py
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path

from dj_ledfx.devices.lifx.packet import (
    GET_DEVICE_CHAIN,
    GET_HOST_FIRMWARE,
    GET_MULTIZONE_EFFECT,
    GET_TILE_EFFECT,
    GET_VERSION,
    STATE_DEVICE_CHAIN,
    STATE_HOST_FIRMWARE,
    STATE_MULTIZONE_EFFECT,
    STATE_TILE_EFFECT,
    STATE_VERSION,
    build_get_tile_effect,
)
from dj_ledfx.devices.lifx.products import LifxProduct, lifx_product
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "lifx" / "recorded"
NAMES = {
    STATE_HOST_FIRMWARE: "state_host_firmware",
    STATE_VERSION: "state_version",
    STATE_DEVICE_CHAIN: "state_device_chain",
    STATE_TILE_EFFECT: "state_tile_effect",
    STATE_MULTIZONE_EFFECT: "state_multizone_effect",
}


def _queries(product: LifxProduct) -> list[tuple[int, bytes, int]]:
    queries = [(GET_HOST_FIRMWARE, b"", STATE_HOST_FIRMWARE), (GET_VERSION, b"", STATE_VERSION)]
    if product.matrix:
        queries.append((GET_DEVICE_CHAIN, b"", STATE_DEVICE_CHAIN))
        queries.append((GET_TILE_EFFECT, build_get_tile_effect(), STATE_TILE_EFFECT))
    if product.multizone:
        queries.append((GET_MULTIZONE_EFFECT, b"", STATE_MULTIZONE_EFFECT))
    return queries


async def _record(transport: LifxTransport, record: LifxDeviceRecord) -> None:
    firmware = await transport.query_host_firmware(record.mac, record.ip, record.port)
    product = lifx_product(record.product, firmware, record.vendor)
    if product is None:
        print(f"skipped unknown product {record.product}")
        return
    slug = re.sub(r"[^a-z0-9]+", "-", product.name.lower()).strip("-")
    version = f"{firmware[0]}.{firmware[1]}" if firmware else "unknown"
    for get, payload, state in _queries(product):
        request = transport.make_request(record.mac, get, payload)
        reply = await transport.request_response(request, (record.ip, record.port), state)
        if reply is None or reply.msg_type != state:
            got = "nothing" if reply is None else f"type {reply.msg_type}"
            print(f"{product.name}: no {NAMES[state]} ({got})")
            continue
        path = OUT / f"{product.pid}-{slug}-{NAMES[state]}.hex"
        path.write_text(
            f"# {NAMES[state]} ({state}) from {product.name} (pid {product.pid}), "
            f"firmware {version}, recorded {date.today()}.\n{reply.payload.hex()}\n"
        )
        print(f"wrote {path.relative_to(ROOT)}")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    transport = LifxTransport()
    await transport.open()
    try:
        for record in await transport.discover(timeout_s=3.0):
            await _record(transport, record)
    finally:
        await transport.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Write the tests over whatever was recorded**

`tests/devices/lifx/test_recorded_packets.py`:

```python
"""Replies recorded from this home's lights (scripts/lifx_record_fixtures.py) parse."""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_ledfx.devices.lifx.packet import (
    MultiZoneEffectType,
    TileEffectType,
    parse_state_device_chain,
    parse_state_host_firmware,
    parse_state_multizone_effect,
    parse_state_tile_effect,
    parse_state_version,
)

RECORDED = Path(__file__).parents[2] / "fixtures" / "lifx" / "recorded"


def _payload(path: Path) -> bytes:
    lines = path.read_text().splitlines()
    return bytes.fromhex("".join(line for line in lines if not line.startswith("#")))


def _recorded(message: str) -> list[Path]:
    return sorted(RECORDED.glob(f"*-{message}.hex"))


def _pid(path: Path) -> int:
    return int(path.name.split("-", 1)[0])


@pytest.mark.parametrize("path", _recorded("state_host_firmware"), ids=lambda p: p.stem)
def test_host_firmware(path: Path) -> None:
    major, _minor = parse_state_host_firmware(_payload(path))
    assert major >= 2


@pytest.mark.parametrize("path", _recorded("state_version"), ids=lambda p: p.stem)
def test_version_names_the_product(path: Path) -> None:
    vendor, product, _version = parse_state_version(_payload(path))
    assert (vendor, product) == (1, _pid(path))


@pytest.mark.parametrize("path", _recorded("state_device_chain"), ids=lambda p: p.stem)
def test_device_chain(path: Path) -> None:
    tiles = parse_state_device_chain(_payload(path))
    assert 1 <= len(tiles) <= 16
    assert all(1 <= tile.width <= 16 and 1 <= tile.height <= 16 for tile in tiles)


@pytest.mark.parametrize("path", _recorded("state_tile_effect"), ids=lambda p: p.stem)
def test_tile_effect(path: Path) -> None:
    state = parse_state_tile_effect(_payload(path))
    assert state.effect in {kind.value for kind in TileEffectType}
    assert state.effect == TileEffectType.OFF or state.speed_ms > 0


@pytest.mark.parametrize("path", _recorded("state_multizone_effect"), ids=lambda p: p.stem)
def test_multizone_effect(path: Path) -> None:
    state = parse_state_multizone_effect(_payload(path))
    assert state.effect in {kind.value for kind in MultiZoneEffectType}
    assert state.effect == MultiZoneEffectType.OFF or state.speed_ms > 0
```

Run: `uv run pytest tests/devices/lifx/test_recorded_packets.py -v`
Expected: every test SKIPPED ("got empty parameter set"): nothing is recorded yet.

- [ ] **Step 3: Note what the engine found**

```bash
curl -s http://127.0.0.1:8080/api/lights | python3 -c '
import json, sys
for light in json.load(sys.stdin):
    print(light["name"], light["status"], light["model"], light["capabilities"], light["builtInEffects"], sep=" | ")'
zone=$(curl -s http://127.0.0.1:8080/api/zones | python3 -c 'import json, sys; print(json.load(sys.stdin)[0]["id"])')
echo "$zone"; ss -ulpn | grep 4002
```

Compare with spec §6.6: three Candles (LIFX Candle Colour) and the TV Lamp (LIFX Tube) offer Flame and Morph; the Neon offers Move; the A19s and Mini Colours offer waveforms; the PC's OpenRGB parts offer hardware modes; the Govee Corner Lamp offers none. Every light is `idle`. `$zone` is the migrated **Default** zone that follows every light (Task 27). If the Govee lamp is missing and UDP 4002 belongs to Home Assistant, dj-ledfx can't hear it: record that for the PR, with the owner's options (move Home Assistant's Govee integration off LAN control, or leave the lamp to Home Assistant).

- [ ] **Step 4: Run the Firmware showcase and record the replies**

Ask the owner first, then:

```bash
curl -s -X POST "http://127.0.0.1:8080/api/zones/$zone/start" -H 'Content-Type: application/json' -d '{"lookId": "firmware"}' | python3 -m json.tool | head -20
uv run python scripts/lifx_record_fixtures.py
uv run pytest tests/devices/lifx/test_recorded_packets.py -v
```

Expected: the start answers with `"state": "running"`. The owner sees Flame on the Candles and the Tube, Move on the Neon, a slow waveform on the bulbs, a hardware mode on the PC, and the Govee lamp (if reachable) streaming Flame's copy. The recorder writes a firmware, version and chain fixture per product, a tile effect fixture showing Flame (type 3) for the Candle and the Tube, and a multizone fixture showing Move (type 1) for the Neon. The recorded tests PASS. In `/api/lights` the firmware lights are `own-effect` with their effect's name, and the Govee lamp is `streamed-copy`.

A recorded test that fails means Task 4's layout disagrees with the light: fix the parser against the recorded bytes, with the recorded fixture as the failing test.

- [ ] **Step 5: Morph**

```bash
candles=$(curl -s http://127.0.0.1:8080/api/lights | python3 -c 'import json, sys; print(json.dumps([l["id"] for l in json.load(sys.stdin) if "LIFX Morph" in l["builtInEffects"]]))')
group=$(curl -s -X POST http://127.0.0.1:8080/api/zones/groups -H 'Content-Type: application/json' -d "{\"name\": \"Morph check\", \"lights\": $candles}" | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])')
curl -s -X POST "http://127.0.0.1:8080/api/zones/$group/start" -H 'Content-Type: application/json' \
  -d '{"look": {"name": "Morph check", "category": "firmware", "layers": [{"id": "morph", "name": "Morph", "type": "firmware", "kind": "lifx_morph"}]}}' \
  | python3 -c 'import json, sys; r = json.load(sys.stdin); print(r["state"], [t["zoneName"] for t in r["takeOvers"]])'
```

Expected: `running ['Default']`: the group took the Candles and the Tube over from the showcase, which keeps the rest. The owner sees Morph's palette on those lights.

- [ ] **Step 6: Brightness, restart and resume**

```bash
curl -s -X PUT "http://127.0.0.1:8080/api/zones/$zone/brightness" -H 'Content-Type: application/json' -d '{"value": 0.4}' > /dev/null
curl -s http://127.0.0.1:8080/api/running | python3 -c 'import json, sys; print([(z["zoneId"], z["brightness"], z["since"]) for z in json.load(sys.stdin)["zones"]])'
docker compose restart app
curl -s --retry 20 --retry-connrefused --retry-delay 1 http://127.0.0.1:8080/api/running | python3 -c 'import json, sys; print([(z["zoneId"], z["brightness"], z["since"]) for z in json.load(sys.stdin)["zones"]])'
```

Expected: the owner sees the showcase dim to 40%. After the restart both zones are back with the same brightness and `since`, and the firmware effects are sent again to the lights that are on. Lights that were off stay off (spec §6.4).

- [ ] **Step 7: Sharing policy**

With the owner:

1. Switch a showcase bulb off in the LIFX app or Home Assistant. Within about 5 s `/api/lights` shows it `switched-off`, and dj-ledfx doesn't switch it back on. Switch it on: it rejoins and runs its waveform again.
2. Set a colour on one Candle from the LIFX app, stopping its Morph. Within the monitor's poll (about 5 s) dj-ledfx sends Morph again, because the light is on.
3. Leave an idle light alone: `/api/lights` shows its real power and colour (read every 30 s) and nothing changes it.

- [ ] **Step 8: Offline and attention**

Ask the owner to cut one light in a running zone at the wall. Straight away `/api/lights` shows it `offline` (or `reconnecting`); after 2 minutes `curl -s http://127.0.0.1:8080/api/attention` lists a `light-offline` item for it. Power it back: it rejoins its zone and the item clears.

- [ ] **Step 9: Preview only, then Off and Stop all**

1. On the Live page switch **Preview only** on and start **Breathe** on the Morph group: the lights keep Morph and the preview shows Breathe. Switch preview-only off: the group's lights change to Breathe (holding still without a DJ, Task 27).
2. Press **Off** for the group: each light returns to the state captured before its first look (the owner confirms).
3. `curl -s -X POST http://127.0.0.1:8080/api/running/stop-all`: every light is back how it was before M1 touched it.
4. Delete the check group: `curl -s -X DELETE "http://127.0.0.1:8080/api/zones/groups/$group"`.

- [ ] **Step 10: Commit the recordings**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
git add scripts/lifx_record_fixtures.py tests/devices/lifx/test_recorded_packets.py tests/fixtures/lifx/recorded
git commit -m "test(lifx): fixtures recorded from the real lights"
```

Keep the results of Steps 3–9 for the PR description.

---

### Task 29: Architecture review

CLAUDE.md asks for a `@feature-dev:code-architect` review of every plan's work, with every issue it raises fixed. Fix Minor findings too.

**Files:**
- Modify: whatever the findings touch
- Create: `/tmp/m1-review/changed.txt` (the reviewer's file list; not committed)

- [ ] **Step 1: List what changed**

The reviewer can read files but can't run git, so give it the list:

```bash
mkdir -p /tmp/m1-review
git diff --name-status master...HEAD > /tmp/m1-review/changed.txt
git log --oneline master..HEAD >> /tmp/m1-review/changed.txt
wc -l /tmp/m1-review/changed.txt
```

- [ ] **Step 2: Dispatch the reviewer**

Use the Agent tool with `subagent_type: "feature-dev:code-architect"` and `model: "opus"`, and this prompt:

```text
Review the M1 branch of dj-ledfx in /home/anirudhlath/code/.worktrees/dj-ledfx/m1-set-and-forget.
/tmp/m1-review/changed.txt lists every file changed against master, then the commits.

Spec: docs/superpowers/specs/2026-09-23-home-effects-engine-design.md, the M1 row of §2
and every section tagged M1. API names and shapes: docs/superpowers/specs/
2026-09-23-web-app-rebuild-design.md §9, §11, §12. Plan: docs/superpowers/plans/
2026-09-23-m1-set-and-forget.md, especially Global Constraints and Review Focus.

Report every finding with file:line, severity (Critical, Important, Minor) and the fix.
Look hardest at: dependency direction (web -> zones -> looks -> effects -> devices, never
back); ZoneManager locking, what it does to lights under preview-only, and the events it
emits; the scheduler's per-frame path; SQLite transactions and FK cascades; drift from
the web spec's contract; anything M2 would have to undo in RenderContext, LedSet,
FieldEffect, FirmwareEffect or ZoneRuntime; code the cut-over left dead.
```

- [ ] **Step 3: Fix every finding**

For each finding: a failing test first when behaviour changes, the fix, the task's tests, then the gates:

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
```

Commit each fix on its own (`fix(<area>): <what>`), or group Minor findings in one area into one commit.

If a finding contradicts the spec or this plan's Global Constraints, don't implement it: reply to the reviewer with the quote, and list it for the PR (Task 32).

- [ ] **Step 4: Confirm with the reviewer**

Send the same reviewer (SendMessage to its agent id) each finding with the commit that fixes it, and ask it to check the fixes and report anything still open. Repeat Steps 3 and 4 until it reports nothing open.

---

### Task 30: Simplify pass

CLAUDE.md asks for a `/simplify` pass over every plan's work, with every issue it raises fixed.

**Files:**
- Modify: whatever the findings touch

- [ ] **Step 1: Run `/simplify` on the branch**

Invoke the `simplify` skill on the changes since `master` (`git diff master...HEAD`). It reviews the changed code for reuse, quality and efficiency.

- [ ] **Step 2: Fix every finding**

Fix all of them, Minor included. A change that alters behaviour gets a failing test first; a pure refactor keeps the tests as they are. After each group of fixes:

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
```

For frontend fixes also run `cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run build`.

A finding that would break a Global Constraint (for example, merging the one float-to-8-bit conversion back into the effects, or dropping the preview-only checks) is answered with the quote and listed for the PR instead.

- [ ] **Step 3: Commit**

```bash
git add -A src tests frontend/src
git commit -m "refactor: simplify pass over M1"
```

---

### Task 31: Revise CLAUDE.md

CLAUDE.md asks for the claude-md skill to revise Claude's context after each plan. M1 makes a good part of CLAUDE.md wrong: the transport, the effect deck and the pipelines are gone.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Run the skills**

Run the `claude-md-management:claude-md-improver` skill (audit and targeted updates), then `/claude-md-management:revise-claude-md` for what this branch taught. Both show their changes before writing; get the owner's yes.

- [ ] **Step 2: Check the facts M1 changed are in**

Whatever the skills propose, CLAUDE.md must end up saying these, and nothing that contradicts them:

- **Commands:** `cd frontend && npx tsc --noEmit -p tsconfig.app.json` (plain `npx tsc --noEmit` checks nothing: the root tsconfig only holds references); deploy with `docker compose up -d --build` from the main checkout; `uv run python scripts/lifx_record_fixtures.py` records LIFX replies (read-only).
- **Architecture:** drop `transport.py`, `effects/deck.py`, `spatial/pipeline.py`, `spatial/pipeline_manager.py`, `web/router_transport.py`. Add `effects/{context,ledset,field,firmware,strip_adapter,firmware_lifx,firmware_openrgb}.py`, `devices/capabilities.py`, `devices/lifx/{base,products}.py` with the vendored `data/products.json`, `looks/` (model, built-ins with the vendored `looks.json`, store), `zones/` (model, store, runtime, manager, lights, attention), `scheduling/route.py`, `web/{contract,errors}.py`, the looks, zones, lights and attention routers, and the WebSocket channels `running`, `lights`, `attention` and `transport` (which now carries preview-only).
- **Code style:** field effects render `(ctx: RenderContext, leds: LedSet) -> FloatRGB`; firmware effects have `supports`, `start`, `stop`, `is_running` and `emulate`; today's 1D effects run through `StripAdapter`; the engine hosts zone runtimes (no deck); frontend hooks include `use-zones` and no `use-transport`.
- **Key design decisions:** replace the transport, multi-scene and multi-pipeline bullets with zones: take-over (newest wins), captured state kept across hand-overs and restarts and released on Off, Stop all, resume on start, preview-only (`engine.preview_only`, applied at once), the sharing policy (spec §6.4), scenes migrated to zones once, and the old UI's effect endpoints taking `?zone=`.
- **Testing:** `tests/conftest.py` (`FakeLight`, `GlowFirmware`), `tests/zone_home.py`, `tests/api_home.py` and `pythonpath = ["tests"]`; the gates' baseline rule (no new mypy errors or format findings). Remove the `_resume_event` advice.
- **Gotchas:** remove the STOPPED-by-default, `_resume_event` and PipelineManager entries. Add: Home Assistant's Govee integration holds UDP 4002, so dj-ledfx can't hear Govee replies on this host; without `--demo` (as deployed) classic tempo looks hold still until a DJ plays (M3 adds the internal clock); the container mounts `config.toml` read-only and `state.db` lives in the `dj-ledfx_state` volume.
- **Deployment:** host networking, so UFW governs port 8080 (LAN allowed; ask before changing UFW); after merging a deploy change, `docker compose up -d --build` in the main checkout.

- [ ] **Step 3: Offer the host's notes and a memory**

The server's own `/home/anirudhlath/CLAUDE.md` lists `dj-ledfx-app-1` with published ports 8080, 9091 and 50001/udp. Tell the owner the row is now host-networked on 8080 (the app binds 50001/udp itself; metrics stay off), and edit that file only if they say yes. It isn't in this repo.

The owner's auto-memory (`/home/anirudhlath/.claude/projects/-home-anirudhlath/memory/`) has no dj-ledfx entry. Offer one, `project_dj_ledfx.md`, with a line in its `MEMORY.md` index: where the container runs, that it redeploys from the main checkout, the Govee port clash with Home Assistant, and that tempo looks hold still without a DJ until M3. Write it only if they say yes.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md for zones, looks, firmware effects and the host-network deploy"
```

---

### Task 32: Open the PR, then redeploy from the main checkout

CLAUDE.md ends every plan with a pull request. This task stands in for the "push and create a PR" option of superpowers:finishing-a-development-branch. Keep the worktree until Step 6: the running container mounts its `config.toml`.

**Files:**
- Create: `/tmp/m1-pr-body.md` (not committed)

- [ ] **Step 1: Catch up with `master`**

```bash
git fetch origin
git rebase origin/master
```

The branch hasn't been pushed yet, so rebasing is safe. If F0 landed meanwhile, its `tests/web/test_next_static.py` calls `create_app(effect_deck=...)`: delete that argument, as Task 24 did for the other tests. When a conflict touches `web/app.py`, keep both sides: F0's `/next` routes and PR #10's `_file_within` stay after M1's routers.

- [ ] **Step 2: Run every gate**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
(cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run build)
```

Expected: ruff clean, every test passes, no format findings or mypy errors beyond the baseline, and the frontend builds. If the rebase brought F0's `web/` in after Task 27 ran, also run `docker compose build` and expect it to build `web/dist` too. That builds the image and leaves the running container alone.

- [ ] **Step 3: Write the PR description**

Write `/tmp/m1-pr-body.md` with these sections, in this order.

**Summary.** Engine milestone M1 of `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: put a look on a zone and it keeps running (through restarts, shared lights, switched-off lights and firmware effects) without a transport to press play on. Plan: `docs/superpowers/plans/2026-09-23-m1-set-and-forget.md`.

**What changed**, one bullet per area:

- Effects: `RenderContext`, `LedSet` from each device's own geometry, `FieldEffect`, `FirmwareEffect`, and the strip adapter that runs today's six effects in LED order along a zone's lights. Firmware effects: LIFX Flame and Morph (tiles), Move (multizone), waveforms (bulbs), OpenRGB hardware modes. Govee and anything that can't run an effect get its streamed `emulate()`.
- Devices: capabilities and a read and set control API for power and colour; LIFX codec, transport, discovery and adapters, with capabilities from a vendored `products.json`.
- Looks: the look model, seven built-ins (the handoff's Firmware showcase and today's six effects as classic looks), saved looks and stars.
- Zones: every light, rooms and groups; take-over (newest wins), captured state restored on Off, brightness, Restart, Stop all, resume after a restart, preview-only, the sharing policy, light status and the attention feed. Scenes become device-group zones once, not running.
- Scheduler: each light gets its slice of its zone's frames through a route, converted to 8 bits once, at send. The transport, the effect deck and the scene pipelines are gone.
- Old UI: the Live page's transport controls became a look picker (zone, look, Start, Off, Preview only). The effect controls and presets work on the chosen zone.
- Backup and restore: `/api/state/export` and `/api/state/import` carry zones, saved looks, stars and what was running.
- Deploy: a committed Dockerfile, compose file and `.dockerignore`: host networking, `state.db` on the `dj-ledfx_state` volume, `config.toml` mounted read-only, no `--demo`.

**API** (web spec §9, §11 and §12 names):

- New: `GET /api/looks`, `GET /api/looks/{id}`, `POST /api/looks`, `PUT /api/looks/{id}`, `DELETE /api/looks/{id}`, `PUT /api/looks/{id}/starred`; `GET /api/zones`, `POST /api/zones/groups`, `PUT /api/zones/groups/{id}`, `DELETE /api/zones/groups/{id}`; `GET /api/running`, `POST /api/zones/{id}/start`, `PUT /api/zones/{id}/brightness`, `POST /api/zones/{id}/off`, `POST /api/zones/{id}/restart`, `POST /api/running/stop-all`; `GET /api/lights`; `GET /api/attention`.
- WebSocket: pushed channels `running`, `lights` and `attention`; `transport` now carries preview-only (`simulating` while on, `playing` otherwise); `stats` entries gain `id` and `dropped_pct`.
- Preview-only: `PUT /api/config` with `{"engine": {"preview_only": true}}`, applied at once and kept across restarts.
- Changed: `GET/PUT /api/effects/active`, `POST /api/presets` and `POST /api/presets/{name}/load` take `?zone=`.
- Removed: `/api/transport`, `/api/scenes/*`, and the WebSocket `set_effect` and `set_transport` commands. `/api/scene` stays for the old scene page until F11.

**Migration.** Migration 004 adds looks, stars, zones and assignments. Each scene becomes a device-group zone, not running; the global transport is gone; SIMULATING becomes preview-only. On the host, the new volume's database starts fresh: `config.toml`'s `[effect]` section makes the default scene, which became the zone **Default**. The old container's database is kept as `state.db.pre-m1.bak`.

**Deployment.** How the host runs it now, and the commands for after the merge (Step 6).

**Real lights.** One row per check in Task 28, in its order: the check, what the owner saw, pass or what happened instead. Then the recorded fixtures' products (`tests/fixtures/lifx/recorded/`).

**Findings and follow-ups:**

- Home Assistant's Govee integration holds UDP 4002 on this host, so dj-ledfx can't hear Govee replies: the lamp is discovered only if Task 28 says so. The options are moving the lamp's LAN control out of Home Assistant or leaving it there.
- Without `--demo`, the classic tempo looks hold still until a DJ plays; M3's internal clock fixes that. Firmware looks animate.
- Existing databases keep the legacy `"True"` and `"False"` strings the old `config.toml` migration wrote; only the tracked `config.toml` was fixed.
- Tailscale: UFW allows only 22 and 8888 on `tailscale0`, so 8080 over Tailscale needs the owner's rule (Task 27, Step 13, and what they decided).
- Every review or `/simplify` finding that was answered with a quote instead of a change (Tasks 29 and 30), with the quote.

**Test plan.** The gates from Step 2 with their counts, Task 26's browser check, Task 27's LAN check from `192.168.50.224`, and Task 28's checklist.

End the description with:

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feature/m1-set-and-forget
gh pr create --base master --head feature/m1-set-and-forget \
  --title "M1 Set-and-forget: zones, looks, firmware effects and a host-network deploy" \
  --body-file /tmp/m1-pr-body.md
gh pr view --json url --jq .url
```

Don't merge. Give the owner the URL and ask them to review it.

- [ ] **Step 5: Wait for the merge**

The owner merges it. Check with `gh pr view --json state --jq .state`; expect `MERGED` before Step 6.

- [ ] **Step 6: Redeploy from the main checkout**

The main checkout still holds the old stack's untracked Dockerfile, compose file and `.dockerignore`, and `git pull` refuses to overwrite untracked files. Keep them as gitignored `*.bak` files, pull, then rebuild. The pinned project name `dj-ledfx` means compose replaces `dj-ledfx-app-1` and keeps the `dj-ledfx_state` volume:

```bash
cd /home/anirudhlath/code/private/dj-ledfx
mv Dockerfile Dockerfile.pre-m1.bak && mv docker-compose.yml docker-compose.yml.pre-m1.bak && mv .dockerignore .dockerignore.pre-m1.bak
git pull --ff-only
docker compose up -d --build
docker inspect dj-ledfx-app-1 --format '{{range .Mounts}}{{.Source}} {{end}}'
curl -s http://127.0.0.1:8080/api/running; echo
```

These lines also work pasted into fish. Expected: the mounts show `/home/anirudhlath/code/private/dj-ledfx/config.toml` and the `dj-ledfx_state` volume, and `/api/running` lists what ran before the redeploy (resume).

Then the worktree can go, through finishing-a-development-branch's cleanup.
