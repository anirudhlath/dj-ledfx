# Light-Output Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every light shows a look on time and in its own shape: latency measured one way while a light streams, a horizon capped at 120 ms, each light sent at a rate it can take, Govee lamps lit per segment by razer, LIFX discovery that never rewrites a known light from a silent one, a Govee lamp that stops answering taken offline instead of flooded, placements in each light's form, and Aurora reaching the floor.

**Architecture:** Seven fixes in the layers that exist; no new subsystem. `latency/` gains a windowed median and a tracker that halves the round trips measured while a light streams and adds the light's display delay. The zone runtime caps its horizon and leaves brightness to the send, and the scheduler sends each light at its own rate and skips frames the light already shows. LIFX adapters fade between frames and LIFX discovery skips silent lights. Govee lamps stream razer frames (`colorwc`, at most 10 a second, is the fallback), report silence as a missed read, and each lamp can set its own output through a new route. The home map fits unconfirmed placements to each light's form.

**Tech Stack:** Python 3.11+ (3.14 in the venv and the container), asyncio, numpy, SQLite through `StateDB`, FastAPI and Pydantic v2, loguru, pytest with pytest-asyncio. The web app's gate (Vitest, ESLint, `tsc -b`, the build, Playwright) runs in Task 16. External facts: LIFX's LAN documentation puts the ceiling at 20 messages a second per device. The razer (DreamView) packets follow LedFx 2.1.9's Govee driver: a frame is `BB 00 FA B0 00`, the segment count, one RGB triple per segment and an XOR checksum of every byte before it, base64-encoded in `{"msg": {"cmd": "razer", "data": {"pt": ...}}}` and sent to the lamp's UDP 4003; switching razer on is `uwABsQEK` and off `uwABsQAL`; razer frames get no replies. Context7 isn't available in this environment.

**Spec:** `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`: §3's horizon row, §4.1, §4.3, §6.1, §6.3, §8 and §9. Govee's protocol choices are in `docs/superpowers/specs/2026-03-13-govee-lan-protocol-design.md`. Read both before starting. Where the owner ruled (Spec Rulings, O1–O3), this plan amends them, and Task 13 brings their text in line.

**What exists.** On the real lights the owner saw three problems: Aurora lit only about four lights, every look lagged, and the Govee lamps acted as single points. Master (83d84c1) has seven causes:

1. **The horizon follows the slowest light.** A zone renders at `now + horizon`, the horizon being its slowest streaming light's latency plus a frame, within the 1 s lookahead (`zones/runtime.py`, `horizon_s`). A Govee lamp's ~270 ms put every light in its zone that far ahead: a look starts after a freeze of about 0.3 s and reacts that late.
2. **Latencies are round trips.** The LIFX and Govee transports hand each probe's round trip to the tracker as if it were the one-way latency. Idle probes run long besides: a bulb's idle echo took 78 ms against 10–14 ms while it streamed (Wi-Fi power save).
3. **Every light gets every frame.** The scheduler sends each device at its `max_fps` (60 for LIFX, 40 for Govee) whether the frame changed or not. A matrix queues `SetTileState64` above about 30 a second (3 frames behind, p95 9, at 60 a second with five lights; 0–1 behind at 20). Govee `colorwc` at 40 a second ran 9 commands behind (p95 12), against 1 (p95 3) at 10.
4. **The EMA never learns a sustained rise.** `EMALatency` drops every sample more than 2σ from its mean, for good, so a latency that jumps and stays is never followed.
5. **LIFX discovery rewrites known lights from silent ones.** `skip_ids` is checked only after `GetVersion`. A light that misses `GetVersion` defaults to product (1, 0), a one-LED bulb (`LifxTransport._query_version`), and when it's an offline ghost the scan promotes it as that bulb and overwrites its row. A missed `GetHostFirmware`, chain or zone query does the same with a wrong LED count.
6. **Govee lamps play one colour.** `GoveeSegmentAdapter` averages the frame into one `colorwc` colour unless `ptReal` is on, and nothing turns it on. Its capabilities are the default ones, so the web app shows its model as `govee_segment`. And a lamp that stops answering reads as unknown (`GoveeAdapterBase.read_light`), so it's never taken offline and keeps getting frames.
7. **Placements never fit, and Aurora hangs high.** The seeds never matched these lights, so every light was placed as a point at 1.0 m, and a multi-LED light on a point stacks its LEDs a few centimetres apart. Aurora's band is `DEFAULT_BAND = (0.55, 1.0)` of the room's height, so only lights placed high take part.

The baseline, measured on 2026-10-01 between 21:48 and 21:57 with router acceleration on, by the investigation's `measure.py look` (the classic rainbow wave for 60 s on the whole home; five LIFX lights in it, three plain bulbs and two matrices; the script measures two of the bulbs and one matrix by default):

| measured light | median lateness | p95 lateness | median round trip |
|---|---|---|---|
| first bulb | −2.8 ms | 74.0 ms | 18.2 ms |
| second bulb | −6.2 ms | 85.3 ms | 18.0 ms |
| matrix | 93.1 ms | 290.1 ms | 42.0 ms (the app assumed 16) |

`measure.py` reads each measured light 4 times a second (`GetColor`, or `GetTileState64` for the matrix) and matches each reading's colour against the web app's live frames for that light, which it subscribes to at 60 a second. Its reads add a little traffic of their own, and Task 15 measures the same way, so the comparison is like for like.

One Govee lamp (`measure.py govee`): the idle `devStatus` round trip had a median of 109.4 ms. Streaming `colorwc` at 10 a second, the round trip's median was 148.7 ms, the lateness's 276.2 ms (p95 485), with 1 command behind (p95 3). At 40 a second the lateness's median was 320.7 ms, with 9 behind (p95 12).

A Govee outage, the same evening: from 21:51:51 to 21:53:11 two Govee lamps were streamed `colorwc` at 40 a second (a whole-home rainbow wave), then turned off by the app's Off. At 21:54:37 the app's restart couldn't reach either; by 22:06:01 both had been found again, on their own. About ten minutes, nothing in the routers' logs, and nobody switched them off. A 40-a-second `colorwc` flood hanging the lamps is the likeliest cause, but it's unproven.

The deployed app's backup export (`GET /api/state/export`) answers 500: its database holds an unset config value (`web.static_dir`, saved as null), and TOML has no null. Task 9 makes the export leave unset values out. Until that ships, Tasks 8 and 15 read the deployed database directly, read-only.

**Execution:** `/executing-plans` (CLAUDE.md) in this worktree, `/home/anirudhlath/code/.worktrees/dj-ledfx/light-output`, on branch `fix/light-output`, which holds this plan's commit. One PR carries the plan and its implementation. Tasks 8 and 15 touch real lights: the orchestrator runs them, step by step, and each step marked **Owner's go** waits for the owner's yes. Every other task runs without lights.

---

## Global Constraints

Every task's requirements include these.

- The owner's rulings O1–O3 (Spec Rulings) bind every task.
- The repo is public. Code, tests, commits, the PR and this plan carry no LAN addresses or MACs, none of the owner's light names, no light model names, no Govee model numbers and no AI model names. A new test address is `127.0.0.1`; a new Govee device id is `test-lamp`; a test that needs a Govee model reads one from `SKU_REGISTRY` or puts its own key (`test-model`) in it. Task 16 greps for all of these, reading the names, models and model numbers from `home.json`, the deployed app and the SKU table at run time, and the product and AI model words from the orchestrator's list, so none of them is typed here.
- An existing entry in the SKU table changes only by a ruling (ruling 12, and Task 8's findings). Refer to its entries as "the first entry (an upright lamp)" and "the second entry (a strip)".
- Tooling is `uv` only: `uv run pytest`, `uv run ruff`, `uv run mypy`.
- Gates (CLAUDE.md): while a task is under way, run only its own tests. Before each commit: `uv run ruff check .` clean, `uv run ruff format --check .` clean, `uv run mypy src/` no worse than Before Task 1's baseline (16 errors in 4 files, none of them touched here), and `uv run pytest -q` green.
- Migrations: none. A lamp's own output lives in the `devices` table's `extra` column, which migration 001 made; the latest migration stays 008.
- An API change regenerates the web app's types in the same commit: `(cd web && npm run api:types)` (Task 10). `tests/web/test_openapi_types.py` fails otherwise.
- Design files (CLAUDE.md, "Web App Design"): only Task 12 edits one, `docs/design/web-app/looks.json`, under ruling O1, with its two byte-for-byte copies and its line in `HANDOFF.sha256`.
- Real lights and the deployed app (`dj-ledfx-app-1`, compose service `app`, holding TCP 8080 and UDP 4002 and 50001) are touched only in Tasks 8 and 15, by the orchestrator, with the owner's go. Every such step starts from these preconditions: "dj-ledfx is idle: `GET http://127.0.0.1:8080/api/running` shows no zones and no overlays; LedFx is paused; each light's state is captured before and restored after; no state.db changes and no deploys."
- Home Assistant's `govee_light_local` retries binding UDP 4002 every 10 minutes, at about :x8 past the hour. If dj-ledfx is down during a retry, Home Assistant takes 4002 and dj-ledfx comes back deaf to Govee replies. A step that stops the app does it well clear of :x8, and after the restart checks `ss -ulne 'sport = :4002'` shows the socket with `uid:10001` (the app's user; `ss -p` needs root).
- The deploy is the owner's, after the merge (CLAUDE.md, "Deployment"); nothing here redeploys.
- Code style (CLAUDE.md): loguru, `mypy --strict`, render paths synchronous and lock-free, event-bus callbacks non-blocking, never `INSERT OR REPLACE` on tables with FK cascades.
- Reviews and `/simplify` run on the PR, not in tasks (CLAUDE.md).

## Spec Rulings

The owner's rulings first; the rest are this plan's, where the specs are silent or the measurements decide. Task 13 writes them into the specs, and the PR lists them.

- **O1. Aurora's band is 0.0–1.0** of the room's height, so the curtains reach the floor. The copy "curtains drift near the ceiling" in `looks.json` changes to match, as does `tests/effects/test_aurora_curtains.py`'s first test. No stored look pins the old band (checked: the only band in the code is `DEFAULT_BAND`).
- **O2. Govee per-segment output uses razer (DreamView), not `ptReal`.** `colorwc` at 10 a second or less is the fallback for models without razer.
- **O3. One plan and one PR** cover all seven causes.

1. **The horizon is capped at 120 ms** (`HORIZON_CAP_S`). A zone renders at most 120 ms ahead; a light slower than that gets the newest frame and runs late by the difference. Every light measured fits under it once latency is one-way (a matrix's ~21 ms plus its display delay, a bulb's ~9 ms; a Govee lamp's seed is 100 ms). The start freeze shrinks to a frame or two.
   *Note, 2026-10-02 (review):* a matrix sits just past the cap. With the 80 ms display delay Task 15 measured, its latency is about 123 ms, so it runs about 3 ms late, against a measured p95 lateness of 42 ms. The coordinator kept the cap: raising it to fit the matrix would delay every look change in its zone by up to 30 ms.
2. **Latency is one-way, measured while streaming.** A probe's round trip counts, halved, only when it arrives within 0.5 s of a frame sent to that light (`STREAMING_WINDOW_S`). Idle round trips are ignored: Wi-Fi power save makes them long.
3. **Latency adds the light's display delay.** A LIFX light shows a frame half-way through its fade, so its delay is half the fade. A matrix takes 40 ms more (`MATRIX_DISPLAY_MS`): the baseline's 93 ms lateness on an assumed 16 ms, less its queueing, which the 20-a-second cap ends. This number is provisional, and Task 15 measures and corrects it.
4. **A windowed median of 9 is the default strategy** for LIFX and Govee (`LATENCY_WINDOW`), seeded at 10 ms one way for LIFX and 100 ms for Govee. The EMA stays for a config that names it, fixed: three outliers in a row are a new level, not three outliers.
5. **LIFX rates:** plain bulbs keep the configured 60 a second (measured fine: median lateness within 7 ms); strips and matrices are capped at 20 a second (`LIFX_STRIP_FPS`, `LIFX_MATRIX_FPS`), LIFX's documented ceiling. Matrices were measured queueing above about 30; strips weren't measured. A chain of several tiles isn't divided further (none here).
6. **LIFX fades:** every streamed frame fades over the gap to the next one, less 2 ms (`stream_fade_ms`), on every kind, so a light moves between frames instead of stepping.
7. **Frames are fire and forget,** matrices too: nothing waits for an acknowledgement.
8. **Unchanged frames are skipped.** A frame equal to the last one sent on the same route isn't sent again for up to a second (`KEEPALIVE_S`), and counts as sent in the stats. A new route or a new adapter (a light back from a drop-out, or a Govee lamp whose output changed) always sends.
9. **Brightness applies at send.** The ring holds each zone's frames before brightness; the route and the web app's frame feed scale them.
10. **Govee rates:** razer at up to 30 a second (`GOVEE_RAZER_FPS`, the Govee `max_fps` default); `colorwc` is capped at 10 a second (`GOVEE_COLOUR_FPS`) whatever the config says, from the measurements and the outage above.
11. **Razer is armed lazily:** razer-on goes before a lamp's first frame and again after 2 s without one (`RAZER_IDLE_S`), and after every prepare, restore or power switch. A restore of a lamp that's on sends razer-off first. A lamp in colour mode is sent razer-off when it's prepared, in case it was left in razer mode. `ptReal` and its helpers are removed.
12. **The SKU table** (an existing entry changes): the first entry (an upright lamp) plays razer and is upright; the second (a strip) keeps razer off until Task 8 checks it: this home has one, and Task 8 plays `whole` on it. Each table entry gains `razer`, `form` and `segments_from_top`. Task 8 checks the upright lamps on the real lamps and may change these.
   *Note, 2026-10-02 (Task 8):* the owner watched every pattern. The upright lamps take razer and show 14 segments, the first at the bottom. With 15 colours, one lamp dropped the extra colour and two showed nothing, so the first entry's count is 14. The strip takes razer with 15 segments, the first at the plug end, so the second entry gets `razer=True`. The chase was smooth and every lamp held all four colours through `gaps`, so `RAZER_IDLE_S` stays at 2 s.
13. **A lamp's segment count:** its own stored output, else the config's `segment_override` (for RGBIC lamps, as now), else the table. Fewer than 2 segments plays one colour.
14. **Govee capabilities:** the model is `Govee <model number>` and multizone means more than one segment.
15. **A Govee lamp that stops answering is a missed read:** `read_light` raises `NoAnswer`, so three missed 5 s polls (about 15 s) take it offline; it gets no frames until a scan (every 30 s) finds it again. While another program holds UDP 4002 the app can't hear replies at all, can't tell, and keeps sending.
   *Note, 2026-10-02 (review):* a read now counts as missed only after three changes:
   - A status read asks twice.
   - Two reads of one lamp share its reply.
   - A light heard from since its last read hasn't missed it.

   Task 8 measured a streaming lamp answering 9 of 10 reads. With single reads, that would have made a false offline about every hour and a half.
16. **LIFX discovery:** a known online light is skipped before `GetVersion`; a light silent to `GetVersion` gives no record; a light silent to any setup query (firmware, label, chain, zones) is skipped for that scan. A `StateUnhandled` reply still falls back as before.
17. **Each Govee lamp's own output** (segments by razer, or one colour; a segment count): `GET` and `PUT /api/lights/{id}/output`, kept in the device row's `extra` (JSON, key `output`), carried by backups, applied at once by reconnecting the lamp (a restored backup's outputs apply at the next start). Backups leave out unset config values, since TOML has no null; one such value made every export of the deployed database fail. A lamp that doesn't answer the reconnect goes offline, and the next scan brings it back with the new output. The route is outside the web spec's contract until a design handoff adds it; the web app doesn't change.
   *Note, 2026-10-02 (review):* changing an output never takes a lamp offline. The new adapter is built from the lamp's row and swapped in with no network.
   - The orchestrator owns the setting (`set_output`, `output_of`).
   - `GET` reports what the live adapter plays.
   - A restored backup's changed outputs apply at once.
18. **The discovery orchestrator is in `app.state`.** `POST /api/devices/scan` then runs a real scan instead of the legacy rediscover, and scans take turns: one asked for while another runs waits for it, since a Govee scan has one reply handler and two at once would cut each other short.
19. **Placements fit forms:** when a light is online, an unconfirmed placement that hides its form (many LEDs on a point; an upright lamp lying down) is fitted again. An upright lamp stands as a vertical line from 0.1 m, 1.4 m tall (`UPRIGHT_BASE_M`, `UPRIGHT_HEIGHT_M`); a strip lies along its length; a matrix stands as a grid. One-LED lights, forms nobody knows and the PC keep their placements. A confirmed placement is never touched.
   *Note, 2026-10-02 (review):* only the light that came online is fitted, and only if its placement came from the seed or a guess. A placement the owner set (`PUT /api/lights/{id}/placement`, or an old scene) is never refitted; migration 009 records each placement's source. A matrix stands with its first row on top on every path, and candles and tubes fit as cylinders.
20. **Aurora's new copy** is "curtains hang from the ceiling to the floor": Task 12 edits the vendored design file under O1. The owner should make the same change in the Claude Design project, or the next handoff brings the old copy back.
21. **Rates are named constants** in `config.py`. A database-backed run takes `devices.*` from code defaults (its stored config sections are engine, network, web, discovery and effect), so the defaults are what the deployed app uses; `config.toml`'s `[devices.*]` lines change only to stay in step.
22. **The razer check script** sends no brightness and binds no port, except its `status` pattern, which binds UDP 4002 and so runs only while the deployed app is stopped.

## Review Focus

The inputs and failure modes most likely to bite someone using this, most likely first. Each has a test in the task that owns the code.

1. **A Govee lamp that stops answering mid-look** is backed off, not flooded: three missed reads take it offline, it gets no frames, and it rejoins when a scan finds it. Tests: Task 5, `test_a_lamp_that_stops_answering_is_missing_not_unknown`, with the existing `tests/zones/test_lights.py::test_a_light_that_misses_three_reads_is_reported_offline`.
2. **A look started right after another** reaches the lights at once, even when its first frame matches the last one sent, and a Govee lamp re-arms razer. Tests: Task 3, `test_a_new_route_sends_at_once`; Task 6, `test_a_look_started_right_after_another_re_arms`.
3. **A light whose latency jumps and stays high** is followed within half a window, while a lone spike is ignored. Test: Task 1, `test_a_latency_that_jumps_and_stays_is_followed`.
4. **A known light that's offline, or half-answers, during discovery** keeps its ghost and its stored row, LED count and kind. Test: Task 4, `test_a_known_light_offline_during_discovery_keeps_its_row`.
5. **A Govee lamp that ignores razer** can be set to one colour, which applies at once at the colour rate. Tests: Task 10, `test_a_lamp_that_ignores_razer_can_be_switched_to_one_colour`; Task 9, `test_a_lamp_set_to_one_colour_comes_back_in_colour`.
6. **A light that never acks or answers a probe** keeps its rate, at its seeded latency plus its display delay; nothing waits for a reply. Tests: Task 3, `test_a_light_that_never_acks_keeps_its_rate` and `test_a_light_that_never_answers_still_takes_every_frame`.

---

## File Structure

New files:

| File | Responsibility |
|---|---|
| `src/dj_ledfx/devices/govee/output.py` | A lamp's output: `GoveeOutput` (its own mode and segment count, stored in the device row's `extra`), `LampPlan`, `lamp_plan()` and `lamp_fps()` |
| `scripts/govee_razer_check.py` | Plays razer patterns on one lamp for the owner to judge by eye, then puts the lamp back (Task 8) |
| `tests/devices/lifx/test_stream_rates.py` | LIFX rates per kind, fades and display delays |
| `tests/devices/govee/test_output.py` | Lamp plans, rates and stored outputs |
| `tests/web/test_light_output_api.py` | `GET` and `PUT /api/lights/{id}/output` |

Modified, by area (paths under `src/dj_ledfx/`):

- Latency: `latency/strategies.py` (`WindowedMedianLatency`, `make_strategy`, `STRATEGIES`, the EMA's level shift), `latency/tracker.py` (`display_ms`, `note_send`, `update_rtt`), `config.py` (defaults and the rate constants), `devices/openrgb_backend.py`.
- Frames: `zones/runtime.py` (`HORIZON_CAP_S`, no brightness in the ring), `scheduling/route.py` (brightness at send), `zones/frames.py`, `scheduling/scheduler.py` (rates, skipping unchanged frames, `note_send`).
- LIFX: `devices/lifx/base.py` (fades, `stream_fps`), `bulb.py`, `strip.py`, `tile_chain.py`, `discovery.py`, `transport.py`.
- Govee: `devices/govee/adapter_base.py`, `segment.py`, `protocol.py`, `types.py`, `sku_registry.py`, `backend.py`.
- Storage and API: `persistence/state_db.py`, `persistence/toml_io.py`, `devices/discovery.py` (`reconnect`, scans taking turns), `web/contract.py`, `web/router_lights.py`, `web/state.py`, `web/app.py`, `main.py`, `web/src/api/generated/*`.
- Home map: `home/guess.py`, `home/map.py`.
- Aurora: `effects/aurora_curtains.py`, `docs/design/web-app/looks.json` with its copies and `HANDOFF.sha256`, and the design prompt `docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md`.
- Docs: both specs, `CLAUDE.md`, `README.md`, `config.toml`.

Shared test helpers: `tests/conftest.py`'s `RingSource` and `ring_route()` gain `brightness` (Task 2); `tests/lifx_fakes.py`'s `FakeLifxTransport` gains `quiet` (Task 4).

---

## Before Task 1

- [ ] **Step 1: Check the worktree**

```bash
W=/home/anirudhlath/code/.worktrees/dj-ledfx/light-output
cd "$W"
git status --short --branch
git log --oneline -3
test -f docs/superpowers/plans/2026-10-01-light-output-fixes.md && echo "plan present"
```

Expected: `## fix/light-output`, nothing uncommitted, the top commit `docs: plan the light-output fixes` over master (83d84c1 or later), and `plan present`. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
(cd web && npm ci)
```

Without the `web` extra, the web tests skip silently and mypy reports dozens of extra errors. Task 10 needs the web app's packages to regenerate the API types.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -m perf -q 2>&1 | tail -1
(cd web && npm test 2>&1 | tail -3 && npx tsc -b && npm run lint && echo "web gate green")
```

Write the five results down. When this plan was written: `1375 passed, 1 skipped, 18 deselected`; ruff clean and `309 files already formatted`; mypy `Found 16 errors in 4 files` (`effects/presets.py`, `spatial/mapping.py`, `web/router_config.py`, `web/router_scene.py`, none of which this plan touches). If ruff isn't clean or the web gate isn't green, tell the owner before starting.

- [ ] **Step 4: Check the design files**

```bash
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256)
```

Expected: every line `OK`. A mismatch means someone hand-edited a design file: stop and tell the owner.

---

### Task 1: Latency that follows the light

Causes 2 and 4. A probe's round trip becomes a one-way latency, counted only while the light streams; a windowed median is the default; the EMA learns a level that holds; and the tracker gains the light's display delay, which Task 3 fills in.

**Files:**
- Modify: `src/dj_ledfx/latency/strategies.py`, `src/dj_ledfx/latency/tracker.py`, `src/dj_ledfx/config.py`, `src/dj_ledfx/scheduling/scheduler.py` (one line), `src/dj_ledfx/devices/openrgb_backend.py`, `src/dj_ledfx/devices/lifx/discovery.py` (`_setup`, `_create_tracker`), `src/dj_ledfx/devices/govee/backend.py` (both `register_device` calls, `_create_tracker`), `config.toml`
- Test: `tests/latency/test_strategies.py`, `tests/latency/test_tracker.py`, `tests/test_config.py`, `tests/scheduling/test_scheduler.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `latency/strategies.py`: `OUTLIERS_TO_SHIFT = 3`; `STRATEGIES = ("static", "ema", "windowed_mean", "windowed_median")`; `WindowedMedianLatency(window_size: int = 9, initial_value_ms: float = 0.0)`; `make_strategy(name: str, latency_ms: float, window_size: int) -> ProbeStrategy`, raising `ValueError` for a name not in `STRATEGIES`.
  - `latency/tracker.py`: `STREAMING_WINDOW_S = 0.5`; `LatencyTracker(strategy, manual_offset_ms=0.0, *, display_ms: float = 0.0, clock: Callable[[], float] = time.monotonic)`, with `display_ms` (property), `note_send(at: float | None = None) -> None` and `update_rtt(rtt_ms: float) -> None`. `effective_latency_ms` is the strategy's latency plus `display_ms` plus the manual offset. `update(sample_ms)` still takes a one-way sample as it is.
  - `config.py`: `LATENCY_WINDOW = 9`. LIFX defaults to `"windowed_median"`, 10.0 ms, window `LATENCY_WINDOW`; Govee to `"windowed_median"`, 100.0 ms, window `LATENCY_WINDOW`.
  - The scheduler calls `tracker.note_send(sent)` after each frame it sends.

- [ ] **Step 1: Write the failing strategy tests**

In `tests/latency/test_strategies.py`, widen the import to:

```python
import pytest

from dj_ledfx.latency.strategies import (
    STRATEGIES,
    EMALatency,
    ProbeStrategy,
    StaticLatency,
    WindowedMeanLatency,
    WindowedMedianLatency,
    make_strategy,
)
```

and add at the end:

```python
# Review Focus 3: a light whose latency jumps and stays high is followed.
@pytest.mark.parametrize(
    "strategy",
    [
        EMALatency(initial_value_ms=10.0),
        WindowedMedianLatency(window_size=9, initial_value_ms=10.0),
    ],
    ids=["ema", "windowed_median"],
)
def test_a_latency_that_jumps_and_stays_is_followed(strategy: ProbeStrategy) -> None:
    for _ in range(20):
        strategy.update(20.0)
    for _ in range(10):
        strategy.update(80.0)
    assert strategy.get_latency() > 70.0


def test_the_ema_still_ignores_a_lone_spike() -> None:
    ema = EMALatency()
    for _ in range(10):
        ema.update(20.0)
    ema.update(300.0)
    ema.update(20.0)
    ema.update(300.0)  # never three in a row: still spikes
    assert ema.get_latency() == pytest.approx(20.0)


def test_the_median_shrugs_off_spikes_and_follows_a_level() -> None:
    median = WindowedMedianLatency(window_size=9, initial_value_ms=10.0)
    assert median.get_latency() == 10.0
    for sample in (20.0, 20.0, 300.0, 20.0, 20.0, 250.0, 20.0):
        median.update(sample)
    assert median.get_latency() == 20.0
    for _ in range(5):
        median.update(60.0)
    assert median.get_latency() == 60.0
    median.reset()
    assert median.get_latency() == 10.0


@pytest.mark.parametrize("name", STRATEGIES)
def test_every_strategy_a_config_names_can_be_made(name: str) -> None:
    assert make_strategy(name, 12.0, 9).get_latency() == 12.0  # seeded


def test_make_strategy_refuses_an_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown latency strategy 'fastest'"):
        make_strategy("fastest", 10.0, 9)
```

`StaticLatency` and `WindowedMeanLatency` stay imported for the existing tests.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/latency/test_strategies.py -q`
Expected: an import error for `STRATEGIES`.

- [ ] **Step 3: Write the strategies**

In `src/dj_ledfx/latency/strategies.py`, add `import statistics` to the imports and, under them:

```python
# Three samples in a row outside the spread are a new level, not three outliers.
OUTLIERS_TO_SHIFT = 3
STRATEGIES = ("static", "ema", "windowed_mean", "windowed_median")
```

Replace `EMALatency`'s `__init__`, `update` and `reset` with these, and add `_is_outlier` (`get_latency` stays):

```python
    def __init__(self, alpha: float = 0.3, initial_value_ms: float = 0.0) -> None:
        self._alpha = alpha
        self._initial_value_ms = initial_value_ms
        self._value: float = initial_value_ms
        self._initialized = False
        self._samples: list[float] = []
        self._outliers = 0  # in a row

    def update(self, new_sample: float) -> None:
        if self._is_outlier(new_sample):
            self._outliers += 1
            if self._outliers < OUTLIERS_TO_SHIFT:
                return
            # The latency moved and stayed there: start again from the new level.
            self._samples.clear()
            self._initialized = False
        self._outliers = 0
        self._samples.append(new_sample)
        if len(self._samples) > 100:
            self._samples.pop(0)

        if not self._initialized:
            self._value = new_sample
            self._initialized = True
        else:
            self._value = self._alpha * new_sample + (1.0 - self._alpha) * self._value

    def _is_outlier(self, sample: float) -> bool:
        if len(self._samples) < 5:
            return False
        mean = sum(self._samples) / len(self._samples)
        variance = sum((s - mean) ** 2 for s in self._samples) / len(self._samples)
        std = math.sqrt(variance) if variance > 0 else 0.0
        # When std is 0 (all samples identical), use 10% of mean as threshold
        threshold = 2.0 * std if std > 0 else mean * 0.1
        return threshold > 0 and abs(sample - mean) > threshold
```

```python
    def reset(self) -> None:
        self._value = self._initial_value_ms
        self._initialized = False
        self._samples.clear()
        self._outliers = 0
```

At the end of the file:

```python
class WindowedMedianLatency:
    """The median of the last window_size samples: a lone spike doesn't move it, and a
    level that holds for more than half the window moves it all the way."""

    def __init__(self, window_size: int = 9, initial_value_ms: float = 0.0) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._initial_value_ms = initial_value_ms

    def update(self, new_sample: float) -> None:
        self._window.append(new_sample)

    def get_latency(self) -> float:
        if not self._window:
            return self._initial_value_ms
        return float(statistics.median(self._window))

    def reset(self) -> None:
        self._window.clear()


def make_strategy(name: str, latency_ms: float, window_size: int) -> ProbeStrategy:
    """The strategy a config names, seeded at latency_ms (a static one keeps it)."""
    if name == "static":
        return StaticLatency(latency_ms)
    if name == "ema":
        return EMALatency(initial_value_ms=latency_ms)
    if name == "windowed_mean":
        return WindowedMeanLatency(window_size=window_size, initial_value_ms=latency_ms)
    if name == "windowed_median":
        return WindowedMedianLatency(window_size=window_size, initial_value_ms=latency_ms)
    raise ValueError(f"Unknown latency strategy '{name}': one of {', '.join(STRATEGIES)}")
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/latency/test_strategies.py -q`
Expected: all pass, the old ones too.

- [ ] **Step 5: Write the failing tracker tests**

In `tests/latency/test_tracker.py`, make the imports:

```python
from dj_ledfx.latency.strategies import StaticLatency, WindowedMedianLatency
from dj_ledfx.latency.tracker import STREAMING_WINDOW_S, LatencyTracker
```

and add:

```python
def test_the_display_delay_adds_to_the_latency() -> None:
    tracker = LatencyTracker(StaticLatency(10.0), manual_offset_ms=5.0, display_ms=24.0)
    assert tracker.display_ms == 24.0
    assert tracker.effective_latency_ms == 39.0


def test_a_round_trip_counts_half_and_only_while_the_light_streams() -> None:
    now = [100.0]
    strategy = WindowedMedianLatency(window_size=9, initial_value_ms=10.0)
    tracker = LatencyTracker(strategy, clock=lambda: now[0])
    tracker.update_rtt(60.0)  # nothing sent yet: an idle round trip
    assert tracker.effective_latency_ms == 10.0
    tracker.note_send()
    now[0] += 0.1
    tracker.update_rtt(60.0)
    assert tracker.effective_latency_ms == 30.0
    now[0] += STREAMING_WINDOW_S + 0.1
    tracker.update_rtt(200.0)  # idle again, its Wi-Fi dozing: ignored
    assert tracker.effective_latency_ms == 30.0


def test_reset_forgets_that_the_light_streamed() -> None:
    now = [100.0]
    strategy = WindowedMedianLatency(window_size=9, initial_value_ms=10.0)
    tracker = LatencyTracker(strategy, clock=lambda: now[0])
    tracker.note_send()
    tracker.reset()
    tracker.update_rtt(60.0)
    assert tracker.effective_latency_ms == 10.0
```

Run: `uv run pytest tests/latency/test_tracker.py -q`
Expected: an import error for `STREAMING_WINDOW_S`.

- [ ] **Step 6: Write the tracker**

Replace `src/dj_ledfx/latency/tracker.py` with:

```python
from __future__ import annotations

import time
from collections.abc import Callable

from dj_ledfx.latency.strategies import ProbeStrategy

# A round trip that arrives within this long of a send was measured while the light streamed.
STREAMING_WINDOW_S = 0.5


class LatencyTracker:
    """A light's latency: one-way network time from its strategy, plus the time the light
    takes to show a frame it has (display_ms), plus the owner's offset."""

    def __init__(
        self,
        strategy: ProbeStrategy,
        manual_offset_ms: float = 0.0,
        *,
        display_ms: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._strategy = strategy
        self._manual_offset_ms = manual_offset_ms
        self._display_ms = display_ms
        self._clock = clock
        self._last_send: float | None = None

    @property
    def manual_offset_ms(self) -> float:
        return self._manual_offset_ms

    @manual_offset_ms.setter
    def manual_offset_ms(self, value: float) -> None:
        self._manual_offset_ms = value

    @property
    def display_ms(self) -> float:
        return self._display_ms

    @property
    def effective_latency_ms(self) -> float:
        return self._strategy.get_latency() + self._display_ms + self._manual_offset_ms

    @property
    def effective_latency_s(self) -> float:
        return self.effective_latency_ms / 1000.0

    def update(self, sample_ms: float) -> None:
        """A one-way sample, taken as it is: a send that returns once the device has it."""
        self._strategy.update(sample_ms)

    def note_send(self, at: float | None = None) -> None:
        """A frame went out now, or at `at` on this tracker's clock."""
        self._last_send = self._clock() if at is None else at

    def update_rtt(self, rtt_ms: float) -> None:
        """A probe's round trip. Half of it is the one-way latency, but only while the light
        streams: an idle light's Wi-Fi dozes, and its round trips run long."""
        if self._last_send is None or self._clock() - self._last_send > STREAMING_WINDOW_S:
            return
        self._strategy.update(rtt_ms / 2.0)

    def reset(self) -> None:
        self._strategy.reset()
        self._last_send = None
```

Run: `uv run pytest tests/latency -q`
Expected: all pass.

- [ ] **Step 7: Change the defaults, with their tests**

In `tests/test_config.py`, add `LATENCY_WINDOW` to the `from dj_ledfx.config import (...)` block and import `STRATEGIES` from `dj_ledfx.latency.strategies`. In `test_lifx_config_defaults`, replace `assert config.devices.lifx.latency_strategy == "ema"` with:

```python
    assert config.devices.lifx.latency_strategy == "windowed_median"
    assert config.devices.lifx.latency_ms == 10.0  # one way, while streaming
    assert config.devices.lifx.latency_window_size == LATENCY_WINDOW
```

In `TestGoveeConfigValidation.test_govee_defaults`, replace `assert config.devices.govee.latency_strategy == "ema"` with:

```python
        assert config.devices.govee.latency_strategy == "windowed_median"
        assert config.devices.govee.latency_window_size == LATENCY_WINDOW
```

and add at the end of the file:

```python
@pytest.mark.parametrize("name", STRATEGIES)
def test_each_device_config_takes_every_strategy(name: str) -> None:
    AppConfig(
        devices=DevicesConfig(
            openrgb=OpenRGBConfig(latency_strategy=name),
            lifx=LIFXConfig(latency_strategy=name),
            govee=GoveeConfig(latency_strategy=name),
        )
    )
```

Run: `uv run pytest tests/test_config.py -q`
Expected: an import error for `LATENCY_WINDOW`: the test file imports it before it exists.

In `src/dj_ledfx/config.py`, add `from dj_ledfx.latency.strategies import STRATEGIES` to the imports and, after them:

```python
# How many recent samples a windowed latency strategy keeps: a median of nine ignores up to
# four spikes and follows a level that holds for five.
LATENCY_WINDOW = 9
```

In `LIFXConfig`, set `latency_strategy: str = "windowed_median"`, `latency_ms: float = 10.0` and `latency_window_size: int = LATENCY_WINDOW`. In `GoveeConfig`, set `latency_strategy: str = "windowed_median"` and `latency_window_size: int = LATENCY_WINDOW` (its `latency_ms` stays 100.0). `OpenRGBConfig` keeps its defaults. In `AppConfig`'s validation, replace the three lines of the strategy check (`valid = {...}`, the `if` and its `raise`) with:

```python
                if dev_cfg.latency_strategy not in STRATEGIES:
                    raise ValueError(
                        f"{name} latency_strategy must be one of {', '.join(STRATEGIES)}"
                    )
```

Run: `uv run pytest tests/test_config.py -q`
Expected: all pass.

- [ ] **Step 8: Build every tracker through `make_strategy`, and feed round trips through `update_rtt`**

`src/dj_ledfx/devices/openrgb_backend.py`: replace the `EMALatency, StaticLatency, WindowedMeanLatency` import with `from dj_ledfx.latency.strategies import make_strategy`, import `OpenRGBConfig` from `dj_ledfx.config` beside `AppConfig`, and add after the imports:

```python
def _tracker(cfg: OpenRGBConfig, name: str) -> LatencyTracker:
    """A static strategy keeps the configured latency; the others start from the heuristic
    for the device's name (OpenRGB can't be probed)."""
    seed = cfg.latency_ms if cfg.latency_strategy == "static" else estimate_device_latency_ms(name)
    strategy = make_strategy(cfg.latency_strategy, seed, cfg.latency_window_size)
    return LatencyTracker(strategy, cfg.manual_offset_ms)
```

In `discover`, replace everything from `heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)` to the end of the `tracker = LatencyTracker(...)` statement with `tracker = _tracker(orgb, adapter.device_info.name)`. In `connect_known`, replace the same span with `tracker = _tracker(orgb_cfg, adapter.device_info.name)`.

`src/dj_ledfx/devices/lifx/discovery.py`: replace the strategies import with `from dj_ledfx.latency.strategies import make_strategy`, and `_create_tracker` with:

```python
    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        lifx = config.devices.lifx
        strategy = make_strategy(lifx.latency_strategy, lifx.latency_ms, lifx.latency_window_size)
        return LatencyTracker(strategy, lifx.manual_offset_ms)
```

In `_setup`, make the registration `self._transport.register_device(record, rtt_callback=tracker.update_rtt)` (the lambda and its `type: ignore` go).

`src/dj_ledfx/devices/govee/backend.py`: the same import change; `_create_tracker` becomes:

```python
    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        govee = config.devices.govee
        strategy = make_strategy(
            govee.latency_strategy, govee.latency_ms, govee.latency_window_size
        )
        return LatencyTracker(strategy, govee.manual_offset_ms)
```

and both registrations, in `discover`'s `_setup_device` and in `connect_known`, become `register_device(record, rtt_callback=tracker.update_rtt)`.

`src/dj_ledfx/scheduling/scheduler.py`, in `_send_loop`: right after `sent = time.monotonic()`, add:

```python
            device.tracker.note_send(sent)  # its probes' round trips count from now
```

- [ ] **Step 9: Test that a probe reply counts while frames go out**

In `tests/scheduling/test_scheduler.py`, import `WindowedMedianLatency` beside `StaticLatency` and add:

```python
async def test_a_probe_reply_counts_while_frames_go_out() -> None:
    adapter = MockDeviceAdapter(name="Probed", led_count=10, supports_probing=False)
    tracker = LatencyTracker(WindowedMedianLatency(window_size=9, initial_value_ms=10.0))
    device = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=60)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    tracker.update_rtt(40.0)  # a probe's round trip while the light streams
    scheduler.stop()
    await task

    assert tracker.effective_latency_ms == 20.0
```

Run: `uv run pytest tests/scheduling tests/devices -q`
Expected: all pass.

- [ ] **Step 10: Keep `config.toml` in step**

The deployed app takes `devices.*` from code defaults (ruling 21); the example file follows them:

```bash
sed -i '/^\[devices\.lifx\]/,/^\[/{s/^latency_strategy = "ema"/latency_strategy = "windowed_median"/;s/^latency_ms = 50\.0/latency_ms = 10.0/;s/^latency_window_size = 60/latency_window_size = 9/}' config.toml
sed -i '/^\[devices\.govee\]/,/^\[/{s/^latency_strategy = "ema"/latency_strategy = "windowed_median"/;s/^latency_window_size = 60/latency_window_size = 9/}' config.toml
git diff --stat config.toml
```

Expected: `config.toml | 10 +++++-----`, five lines changed: three under `[devices.lifx]`, two under `[devices.govee]`.

- [ ] **Step 11: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/latency src/dj_ledfx/config.py src/dj_ledfx/scheduling/scheduler.py src/dj_ledfx/devices/openrgb_backend.py src/dj_ledfx/devices/lifx/discovery.py src/dj_ledfx/devices/govee/backend.py config.toml tests/latency tests/test_config.py tests/scheduling/test_scheduler.py
git commit -m "fix(latency): one-way latency measured while streaming, a windowed median, an EMA that follows a new level"
```

---

### Task 2: A capped horizon, and brightness at send

Cause 1. A zone renders at most 120 ms ahead (ruling 1), and the ring holds frames before brightness, which the route and the web app's feed apply (ruling 9).

**Files:**
- Modify: `src/dj_ledfx/zones/runtime.py` (`horizon_s`, `_render`), `src/dj_ledfx/scheduling/route.py`, `src/dj_ledfx/zones/frames.py`, `tests/conftest.py` (`RingSource`, `ring_route`)
- Test: `tests/scheduling/test_route.py`, `tests/zones/test_runtime.py`, `tests/zones/test_manager.py`, `tests/zones/test_frames.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `zones/runtime.py`: `HORIZON_CAP_S = 0.12`; `horizon_s` is `min(latency + 1 / fps, HORIZON_CAP_S, max_lookahead_s)`; `_render` no longer applies brightness.
  - `scheduling/route.py`: `slice_colors(colors, start, stop, led_count, scale: float = 1.0)`; `FrameSource` gains a read-only `brightness: float`; `DeviceRoute.colors_at` scales by `source.brightness`.
  - `tests/conftest.py`: `RingSource(ring, leds, brightness=1.0)` and `ring_route(ring, *, start=0, stop=10, streaming=True, brightness=1.0)`.

- [ ] **Step 1: Write the failing route tests**

In `tests/conftest.py`, give the frozen dataclass `RingSource` a third field, `brightness: float = 1.0`, and make `ring_route` pass a `brightness` keyword on (its signature is then one parameter per line):

```python
def ring_route(
    ring: RingBuffer,
    *,
    start: int = 0,
    stop: int = 10,
    streaming: bool = True,
    brightness: float = 1.0,
) -> DeviceRoute:
    """A route to LEDs start..stop of ring's frames, sent at this brightness."""
    leds = build_ledset([LedSource("before", start), LedSource("light", stop - start)])
    return DeviceRoute(RingSource(ring, leds, brightness), "light", streaming)
```

Add to `tests/scheduling/test_route.py`:

```python
def test_a_slice_is_scaled_before_it_is_converted() -> None:
    colors = np.full((2, 3), 1.0, dtype=np.float32)
    out = slice_colors(colors, 0, 2, 2, scale=0.5)
    assert out is not None and out.tolist() == [[128, 128, 128], [128, 128, 128]]


def test_a_route_sends_its_slice_at_the_zone_s_brightness() -> None:
    ring = RingBuffer(capacity=4)
    colors = np.full((3, 3), 0.8, dtype=np.float32)
    ring.write(_frame(colors, 10.0))
    out = ring_route(ring, start=0, stop=3, brightness=0.5).colors_at(10.0, 3)
    assert out is not None
    assert out.tolist() == to_device_colors(colors * np.float32(0.5), 3).tolist()
    kept = ring.find_nearest(10.0)
    assert kept is not None and np.allclose(kept.colors, 0.8)  # the ring keeps the full level
```

Run: `uv run pytest tests/scheduling/test_route.py -q`
Expected: the two new tests fail (`slice_colors` takes no `scale`; the route ignores brightness).

- [ ] **Step 2: Scale at send**

In `src/dj_ledfx/scheduling/route.py`, replace `slice_colors` with:

```python
def slice_colors(
    colors: FloatRGB, start: int, stop: int, led_count: int, scale: float = 1.0
) -> NDArray[np.uint8] | None:
    """LEDs start..stop of a zone frame in 8 bits, for a device of led_count LEDs, scaled by
    the zone's brightness. None when the frame is shorter: it was rendered for an LED set
    since rebuilt."""
    if colors.shape[0] < stop:
        return None
    part = colors[start:stop]
    if scale != 1.0:
        part = part * np.float32(scale)
    return to_device_colors(part, led_count)
```

Add to `FrameSource`:

```python
    @property
    def brightness(self) -> float: ...
```

and make the last line of `DeviceRoute.colors_at`:

```python
        return slice_colors(
            frame.colors, piece.start, piece.stop, led_count, self.source.brightness
        )
```

In `src/dj_ledfx/zones/frames.py`, `FrameFeed.frames` reads the runtime's brightness too: `whole = slice_colors(frame.colors, 0, count, count, runtime.brightness)`.

Run: `uv run pytest tests/scheduling/test_route.py -q`
Expected: all pass.

- [ ] **Step 3: Write the failing runtime, manager and feed tests**

In `tests/zones/test_runtime.py`, import `HORIZON_CAP_S` from `dj_ledfx.zones.runtime` beside `ZoneLight` and `ZoneRuntime`. Replace three tests:

```python
def test_a_firmware_only_look_streams_its_copy_to_lights_that_cannot_run_it() -> None:
    runtime = _runtime(_look(_glow(level=0.4)), brightness=0.5)
    assert runtime.mode_of("lamp") == "streamed-copy"
    assert runtime.effect_name("lamp") == "Glow"
    runtime.tick(100.0)
    assert np.allclose(_latest(runtime), 0.4)  # the copy everywhere; brightness waits for the send
    route = runtime.route_for("lamp")
    assert route is not None
    sent = route.colors_at(100.0, 3)
    assert sent is not None and np.all(sent == 51)  # 0.4 at half brightness, in 8 bits
```

```python
def test_the_horizon_is_capped() -> None:
    runtime = _runtime(_look(_field()), latencies={"lamp": 5.0}, max_lookahead_s=1.0)
    assert runtime.horizon_s == HORIZON_CAP_S
    shorter = _runtime(_look(_field()), latencies={"lamp": 5.0}, max_lookahead_s=0.05)
    assert shorter.horizon_s == 0.05
```

(it replaces `test_the_horizon_is_capped_by_the_lookahead`), and

```python
def test_opacity_scales_the_frame_and_brightness_the_send() -> None:
    runtime = _runtime(_look(_field(level=0.8, opacity=0.5)), brightness=0.5)
    runtime.tick(100.0)
    assert np.allclose(_latest(runtime), 0.4)
    route = runtime.route_for("bulb")
    assert route is not None
    sent = route.colors_at(100.0, 1)
    assert sent is not None and np.all(sent == 51)
```

(it replaces `test_brightness_and_opacity_scale_the_frame`). Add:

```python
def test_a_light_slower_than_the_cap_gets_the_newest_frame() -> None:
    runtime = _runtime(_look(_field(level=0.8)), latencies={"lamp": 0.5})
    assert runtime.horizon_s == HORIZON_CAP_S
    runtime.tick(100.0)
    route = runtime.route_for("lamp")
    assert route is not None
    newest = route.colors_at(100.0 + 0.5, 3)
    assert newest is not None and np.all(newest == 204)  # 0.8 in 8 bits: late, not dark
```

In `tests/zones/test_manager.py`'s `test_the_horizon_follows_connected_streaming_lights_without_a_search`, the far light's latency must sit under the cap for the test to say what it says: change `("far", 300.0)` to `("far", 100.0)` and `assert runtime.horizon_s == pytest.approx(0.3 + 1 / 60)` to `assert runtime.horizon_s == pytest.approx(0.1 + 1 / 60)`. The last assertion (`0.02 + 1 / 60`) stays.

Add to `tests/zones/test_frames.py` (it imports `GLOW` and `to_device_colors` already):

```python
async def test_the_web_app_sees_a_zone_at_its_brightness(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [zone_record("z", "lamp")])
    await home.manager.start("z", GLOW)  # this lamp can't run Glow: a streamed copy
    await home.manager.set_brightness("z", 0.5)
    feed = FrameFeed(
        home.manager.live_runtimes, home.manager.preview_runtimes, clock=lambda: 100.0
    )
    runtime = home.host.runtimes["z"]
    runtime.tick(100.0)
    frame = runtime.ring.find_nearest(100.0)
    assert frame is not None and np.allclose(frame.colors, 0.5)  # Glow's level, at full brightness
    count = runtime.leds.count
    expected = to_device_colors(frame.colors[:count] * np.float32(0.5), count)
    assert np.array_equal(feed.frames("live")["lamp"], expected)
```

Run: `uv run pytest tests/zones/test_runtime.py tests/zones/test_manager.py tests/zones/test_frames.py -q`
Expected: `test_runtime.py` fails at collection with an import error for `HORIZON_CAP_S`. Run alone, `test_manager.py` and `test_frames.py` have one failure, `test_the_web_app_sees_a_zone_at_its_brightness`: the ring holds 0.25, the zone's brightness already in it. The edited horizon test passes before and after: its far light is under the cap.

- [ ] **Step 4: Cap the horizon and take brightness out of the ring**

In `src/dj_ledfx/zones/runtime.py`, add near the module's other constants:

```python
# How far ahead a zone renders at most. A light slower than this gets the newest frame and
# runs late by the difference; a look starts and reacts within a frame or two.
HORIZON_CAP_S = 0.12
```

Replace `horizon_s`'s docstring and return:

```python
    @property
    def horizon_s(self) -> float:
        """The largest latency of the zone's lights that take its frames, plus one frame,
        capped at HORIZON_CAP_S and the lookahead. A light running its own effect, or not
        connected (latency None), takes none."""
        latency = 0.0
        for light in self._lights:
            if light.device_id not in self._claims:
                light_s = self._latency_s(light.device_id)
                if light_s is not None and light_s > latency:
                    latency = light_s
        return min(latency + 1.0 / self._fps, HORIZON_CAP_S, self._max_lookahead_s)
```

In `_render`, delete the line `frame *= np.float32(self.brightness)` (the frame goes into the ring before brightness; the route and the feed apply it).

Run: `uv run pytest tests/zones tests/scheduling -q`
Expected: all pass.

- [ ] **Step 5: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/zones/runtime.py src/dj_ledfx/zones/frames.py src/dj_ledfx/scheduling/route.py tests/conftest.py tests/scheduling/test_route.py tests/zones/test_runtime.py tests/zones/test_manager.py tests/zones/test_frames.py
git commit -m "fix(zones): render at most 120 ms ahead, and apply brightness at send"
```

---

### Task 3: Each light at its own rate: LIFX fades and caps, and no frame sent twice

Cause 3. LIFX strips and matrices stream at no more than 20 a second, every LIFX frame fades into the next, the fade's half and a matrix's own delay join the light's latency (rulings 3, 5, 6), and the scheduler skips a frame the light already shows, with a keepalive (ruling 8).

**Files:**
- Modify: `src/dj_ledfx/config.py`, `src/dj_ledfx/devices/lifx/base.py`, `src/dj_ledfx/devices/lifx/bulb.py`, `src/dj_ledfx/devices/lifx/strip.py`, `src/dj_ledfx/devices/lifx/tile_chain.py`, `src/dj_ledfx/devices/lifx/discovery.py`, `src/dj_ledfx/scheduling/scheduler.py`
- Create: `tests/devices/lifx/test_stream_rates.py`
- Test: `tests/devices/lifx/test_discovery.py`, `tests/scheduling/test_scheduler.py`

**Interfaces:**
- Consumes: Task 1's `LatencyTracker(..., display_ms=...)` and `note_send`.
- Produces:
  - `config.py`: `LIFX_STRIP_FPS = 20`, `LIFX_MATRIX_FPS = 20`.
  - `devices/lifx/base.py`: `STREAM_FADE_MARGIN_MS = 2`; `stream_fade_ms(fps: int) -> int`; `stream_fps(kind: type[LifxAdapterBase], max_fps: int) -> int`; `LifxAdapterBase.stream_fps_cap: ClassVar[int | None] = None`; every LIFX adapter takes a keyword `fade_ms: int = 0` and has `display_ms -> float` (half the fade).
  - `devices/lifx/tile_chain.py`: `MATRIX_DISPLAY_MS = 40`; a matrix's `display_ms` adds it.
  - `scheduling/scheduler.py`: `KEEPALIVE_S = 1.0`; `DeviceSendState` gains `last_route: DeviceRoute | None = None`, `last_adapter: DeviceAdapter | None = None`, `last_colors: NDArray[np.uint8] | None = None`, `last_sent_at: float = 0.0`. A frame is skipped only when the route, the adapter and the colours are the ones last sent, within `KEEPALIVE_S`.

- [ ] **Step 1: Write the failing LIFX tests**

Create `tests/devices/lifx/test_stream_rates.py`:

```python
"""LIFX rates per kind, fades between frames, and the delay a light shows a frame with."""

from __future__ import annotations

import asyncio
import struct

import numpy as np
from lifx_fakes import MAC, FakeLifxTransport, lifx_info

from dj_ledfx.config import LIFX_MATRIX_FPS, LIFX_STRIP_FPS
from dj_ledfx.devices.lifx.base import stream_fade_ms, stream_fps
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import SET_COLOR, SET_EXTENDED_COLOR_ZONES, SET_TILE_STATE_64
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import MATRIX_DISPLAY_MS, LifxTileChainAdapter


def test_each_kind_streams_within_its_cap() -> None:
    assert stream_fps(LifxBulbAdapter, 60) == 60
    assert stream_fps(LifxStripAdapter, 60) == LIFX_STRIP_FPS
    assert stream_fps(LifxTileChainAdapter, 60) == LIFX_MATRIX_FPS
    assert stream_fps(LifxTileChainAdapter, 10) == 10  # a lower configured rate wins


def test_a_fade_ends_just_before_the_next_frame() -> None:
    assert stream_fade_ms(20) == 48
    assert stream_fade_ms(60) == 15
    assert stream_fade_ms(1000) == 0


async def test_every_frame_fades_for_the_adapter_s_fade() -> None:
    transport = FakeLifxTransport()
    bulb = LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC, fade_ms=15)
    await bulb.send_frame(np.full((1, 3), 200, dtype=np.uint8))
    *_, duration = struct.unpack("<B4HI", transport.last(SET_COLOR).payload)
    assert duration == 15

    strip = LifxStripAdapter(transport, lifx_info("strip", 4), MAC, zone_count=4, fade_ms=48)
    await strip.send_frame(np.full((4, 3), 200, dtype=np.uint8))
    assert struct.unpack_from("<I", transport.last(SET_EXTENDED_COLOR_ZONES).payload)[0] == 48

    matrix = LifxTileChainAdapter(
        transport, lifx_info("matrix", 64), MAC, tile_count=1, fade_ms=48
    )
    await matrix.send_frame(np.full((64, 3), 200, dtype=np.uint8))
    assert struct.unpack_from("<6BI", transport.last(SET_TILE_STATE_64).payload)[6] == 48


def test_a_light_shows_a_frame_half_way_through_its_fade() -> None:
    transport = FakeLifxTransport()
    bulb = LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC, fade_ms=48)
    matrix = LifxTileChainAdapter(
        transport, lifx_info("matrix", 64), MAC, tile_count=1, fade_ms=48
    )
    assert bulb.display_ms == 24.0
    assert matrix.display_ms == 24.0 + MATRIX_DISPLAY_MS


# Review Focus 6: a light that never acks or answers. Frames are fire and forget.
async def test_a_light_that_never_answers_still_takes_every_frame() -> None:
    transport = FakeLifxTransport(silent=True)
    bulb = LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC, fade_ms=15)
    for level in (50, 100, 150):
        frame = np.full((1, 3), level, dtype=np.uint8)
        await asyncio.wait_for(bulb.send_frame(frame), timeout=0.05)  # waits for nothing
    assert transport.types().count(SET_COLOR) == 3
```

Add to `tests/devices/lifx/test_discovery.py` (importing `LIFX_MATRIX_FPS` from `dj_ledfx.config`, `stream_fade_ms` from `dj_ledfx.devices.lifx.base` and `MATRIX_DISPLAY_MS` from `dj_ledfx.devices.lifx.tile_chain`):

```python
async def test_a_matrix_streams_at_its_rate_and_its_latency_counts_its_display() -> None:
    transport = FakeLifxTransport(product=57, chain=[(5, 6)])
    device = await _backend(transport)._setup(_record(57), AppConfig())
    assert device is not None and isinstance(device.adapter, LifxTileChainAdapter)
    assert device.max_fps == LIFX_MATRIX_FPS
    display = stream_fade_ms(LIFX_MATRIX_FPS) / 2 + MATRIX_DISPLAY_MS
    assert device.adapter.display_ms == display
    assert device.tracker.effective_latency_ms == AppConfig().devices.lifx.latency_ms + display
```

Run: `uv run pytest tests/devices/lifx/test_stream_rates.py tests/devices/lifx/test_discovery.py -q`
Expected: both files fail at collection with an import error for `LIFX_MATRIX_FPS`.

- [ ] **Step 2: Rates, fades and display delays**

In `src/dj_ledfx/config.py`, under `LATENCY_WINDOW`:

```python
# The most frames a second a LIFX strip or matrix takes: LIFX's documented ceiling per
# device. Matrices were measured queueing frames above about 30; plain bulbs keep max_fps.
LIFX_STRIP_FPS = 20
LIFX_MATRIX_FPS = 20
```

In `src/dj_ledfx/devices/lifx/base.py`, after `RESTORE_FADE_MS = 500` (leave two blank lines between `stream_fade_ms` and `T = TypeVar("T")`, or `ruff format --check` fails):

```python
STREAM_FADE_MARGIN_MS = 2  # a streamed frame's fade ends this long before the next frame


def stream_fade_ms(fps: int) -> int:
    """The fade a streamed frame asks for at `fps` frames a second: the gap to the next
    frame, less a margin, so the light moves between frames instead of stepping."""
    return max(0, round(1000 / fps) - STREAM_FADE_MARGIN_MS)
```

In `LifxAdapterBase`, under `supports_latency_probing = False`:

```python
    # The most frames a second this kind of light takes; None: the configured max_fps.
    stream_fps_cap: ClassVar[int | None] = None
```

Give `__init__` a last keyword, `fade_ms: int = 0`, keep it as `self._fade_ms = fade_ms  # each streamed frame's fade`, and add after `capabilities`:

```python
    @property
    def display_ms(self) -> float:
        """How long after a frame lands the light shows it: half-way through its fade."""
        return self._fade_ms / 2.0
```

After the class:

```python
def stream_fps(kind: type[LifxAdapterBase], max_fps: int) -> int:
    """The rate a kind of LIFX light streams at: the configured rate, within its kind's cap."""
    cap = kind.stream_fps_cap
    return max_fps if cap is None else min(max_fps, cap)
```

`src/dj_ledfx/devices/lifx/bulb.py`: `__init__` gains `fade_ms: int = 0` after `caps` and passes `fade_ms=fade_ms` to `super().__init__`. `send_frame`'s send becomes:

```python
        hsbk = rgb_to_hsbk(r, g, b, kelvin=self._kelvin)
        self._send(SET_COLOR, build_set_color(hsbk, self._fade_ms))
```

`src/dj_ledfx/devices/lifx/strip.py`: import `LIFX_STRIP_FPS` from `dj_ledfx.config`; under `_effect_key = "multizone_effect"` add `stream_fps_cap = LIFX_STRIP_FPS`; `__init__` gains `fade_ms: int = 0` after `caps`, passed to `super().__init__`; in `send_frame`, the packet is `build_set_extended_color_zones(self._fade_ms, 1, start, len(values), values)`.

`src/dj_ledfx/devices/lifx/tile_chain.py`: import `LIFX_MATRIX_FPS` from `dj_ledfx.config`; after `PIXEL_PITCH_M`:

```python
# How much later than half its fade a matrix shows a frame: derived from the 2026-10-01
# baseline, and corrected by measuring the lights (the light-output plan's Task 15).
MATRIX_DISPLAY_MS = 40
```

Under `_effect_key = "tile_effect"` add `stream_fps_cap = LIFX_MATRIX_FPS`; `__init__` gains `fade_ms: int = 0` after `caps`, passed to `super().__init__`; in `send_frame`, the packet is `build_set_tile_state64(tile_index, 1, 0, row, width, self._fade_ms, values)`; and add:

```python
    @property
    def display_ms(self) -> float:
        """Half its fade, plus the time a matrix takes to show a frame it has."""
        return super().display_ms + MATRIX_DISPLAY_MS
```

`src/dj_ledfx/devices/lifx/discovery.py`: import `stream_fade_ms` and `stream_fps` from `dj_ledfx.devices.lifx.base` beside `LifxAdapterBase`, and add after `_zone_count_of`:

```python
def _fade_ms(kind: type[LifxAdapterBase], config: AppConfig) -> int:
    return stream_fade_ms(stream_fps(kind, config.devices.lifx.max_fps))
```

In `_create_adapter`, pass `fade_ms=_fade_ms(LifxTileChainAdapter, config)` to the matrix, `fade_ms=_fade_ms(LifxStripAdapter, config)` to the strip and `fade_ms=_fade_ms(LifxBulbAdapter, config)` to the bulb; the `LifxBulbAdapter(...)` call then goes one argument per line. `_create_tracker` takes the display delay:

```python
    def _create_tracker(self, config: AppConfig, *, display_ms: float = 0.0) -> LatencyTracker:
        lifx = config.devices.lifx
        strategy = make_strategy(lifx.latency_strategy, lifx.latency_ms, lifx.latency_window_size)
        return LatencyTracker(strategy, lifx.manual_offset_ms, display_ms=display_ms)
```

and `_setup` becomes:

```python
    async def _setup(self, record: LifxDeviceRecord, config: AppConfig) -> DiscoveredDevice | None:
        assert self._transport is not None
        adapter = await self._create_adapter(record, config)
        if adapter is None:
            return None
        tracker = self._create_tracker(config, display_ms=adapter.display_ms)
        await adapter.connect()
        self._transport.register_device(record, rtt_callback=tracker.update_rtt)
        max_fps = stream_fps(type(adapter), config.devices.lifx.max_fps)
        return DiscoveredDevice(adapter=adapter, tracker=tracker, max_fps=max_fps)
```

Run: `uv run pytest tests/devices/lifx -q`
Expected: all pass.

- [ ] **Step 3: Write the failing scheduler tests**

In `tests/scheduling/test_scheduler.py`, import `LATENCY_WINDOW` from `dj_ledfx.config`, and make the strategies and scheduler imports:

```python
from dj_ledfx.latency.strategies import (
    StaticLatency,
    WindowedMeanLatency,
    WindowedMedianLatency,
    make_strategy,
)
```

```python
from dj_ledfx.scheduling.scheduler import KEEPALIVE_S, FrameSlot, LookaheadScheduler
```

Add a helper under `_fill_buffer`:

```python
def _fill_still(buf: RingBuffer, base_time: float, count: int = 60) -> None:
    """Frames that never change: a still look."""
    for i in range(count):
        frame = RenderedFrame(
            colors=np.full((10, 3), 0.5, dtype=np.float32),
            target_time=base_time + i * (1.0 / 60.0),
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)
```

and the tests:

```python
async def test_a_still_look_is_sent_once_and_then_kept_alive() -> None:
    device = _make_device(max_fps=60)
    buf = RingBuffer(capacity=150)
    _fill_still(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.5)
    assert len(device.adapter.send_frame_calls) == 1
    (stats,) = scheduler.get_device_stats()
    assert stats.send_fps > 20  # a skipped frame counts as sent: the light is short of none
    await asyncio.sleep(KEEPALIVE_S)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 2


# Review Focus 2: a look started right after another reaches the light at once.
async def test_a_new_route_sends_at_once() -> None:
    device = _make_device(max_fps=60)
    buf = RingBuffer(capacity=150)
    _fill_still(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    assert len(device.adapter.send_frame_calls) == 1
    scheduler.set_route(device.adapter.device_info.effective_id, _route(buf))  # same frames
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert len(device.adapter.send_frame_calls) == 2


async def test_a_light_given_a_new_adapter_gets_its_frame_at_once() -> None:
    device = _make_device(max_fps=60)
    buf = RingBuffer(capacity=150)
    _fill_still(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    replacement = MockDeviceAdapter(name="TestDevice", led_count=10)
    device.adapter = replacement  # as promote_device swaps it when a lamp's output changes
    await asyncio.sleep(0.2)
    scheduler.stop()
    await task

    assert len(replacement.send_frame_calls) == 1


# Review Focus 6: a light that never acks or answers a probe keeps its rate.
async def test_a_light_that_never_acks_keeps_its_rate() -> None:
    adapter = MockDeviceAdapter(name="Quiet", led_count=10, supports_probing=False)
    strategy = make_strategy("windowed_median", 10.0, LATENCY_WINDOW)
    tracker = LatencyTracker(strategy, display_ms=24.0)
    device = ManagedDevice(adapter=adapter, tracker=tracker, max_fps=20)
    buf = RingBuffer(capacity=150)
    _fill_buffer(buf, time.monotonic(), 150)
    scheduler = _scheduler(ring_buffer=buf, devices=[device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(1.0)
    (stats,) = scheduler.get_device_stats()
    scheduler.stop()
    await task

    assert 14 <= stats.send_fps <= 26  # the tolerance of test_get_device_stats_fps_accuracy
    assert stats.effective_latency_ms == 34.0  # its seed and its display delay
```

Two existing tests assumed that repeated frames are sent. `test_fps_cap_no_accumulated_drift` runs for 2 s on 60 frames, one second of them, so its second second repeats the last frame: make its ring `RingBuffer(capacity=150)` and its fill `_fill_buffer(buf, time.monotonic(), 150)`. `test_mixed_fps_per_device` counts the adapters' frames; count the scheduler's sends instead, which include the skipped ones:

```python
async def test_mixed_fps_per_device() -> None:
    """Devices with different max_fps send at different rates."""
    fast_device = _make_device("fast", max_fps=60)
    slow_device = _make_device("slow", max_fps=30)
    buf = RingBuffer(capacity=60)
    _fill_buffer(buf, time.monotonic(), 60)
    scheduler = _scheduler(ring_buffer=buf, devices=[fast_device, slow_device], fps=60)

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.5)
    fast, slow = scheduler.get_device_stats()  # a skipped repeat counts as sent
    scheduler.stop()
    await task

    assert fast.send_fps > 0 and slow.send_fps > 0
    ratio = fast.send_fps / slow.send_fps
    assert 1.5 < ratio < 3.0, f"Expected ~2:1 ratio, got {ratio:.1f}:1"
```

Run: `uv run pytest tests/scheduling/test_scheduler.py -q`
Expected: an import error for `KEEPALIVE_S`.

- [ ] **Step 4: Skip what the light already shows**

In `src/dj_ledfx/scheduling/scheduler.py`, add `import numpy as np` and `from numpy.typing import NDArray` to the imports, `from dj_ledfx.devices.adapter import DeviceAdapter` under `TYPE_CHECKING`, and, after the imports:

```python
# A frame equal to the last one sent on the same route goes out again only this often: the
# light already shows it, and a lamp that drops a packet gets it back within a second.
KEEPALIVE_S = 1.0
```

`DeviceSendState` gains four fields after `sent_at`:

```python
    last_route: DeviceRoute | None = None  # what the last frame sent came through
    last_adapter: DeviceAdapter | None = None
    last_colors: NDArray[np.uint8] | None = None
    last_sent_at: float = 0.0
```

In `_send_loop`'s reconnect branch, under `device.tracker.reset()`, add `state.last_route = None  # a light back from a drop-out gets its frame at once`. Then replace everything from `async with device.adapter.send_lock:` down to `metrics.DEVICE_FPS.labels(device=key).set(device.max_fps)` with:

```python
            now = time.monotonic()
            if (
                route is state.last_route
                and device.adapter is state.last_adapter
                and state.last_colors is not None
                and np.array_equal(colors, state.last_colors)
                and now - state.last_sent_at < KEEPALIVE_S
            ):
                # The light shows this already: count it as sent, and send nothing.
                state.send_count += 1
                state.sent_at.append(now)
                trim_window(state.sent_at, now)
            else:
                async with device.adapter.send_lock:
                    current = self._routes.get(key)  # a restore may have run meanwhile
                    if current is None or not current.streaming:
                        continue
                    send_start = time.monotonic()
                    try:
                        await device.adapter.send_frame(colors)
                    except Exception:
                        logger.warning("Send failed for '{}'", device_name)
                        continue
                sent = time.monotonic()
                device.tracker.note_send(sent)  # its probes' round trips count from now
                state.last_route, state.last_adapter = current, device.adapter
                state.last_colors, state.last_sent_at = colors, sent
                metrics.DEVICE_SEND_DURATION.labels(device=key).observe(sent - send_start)
                if device.adapter.supports_latency_probing:
                    device.tracker.update((sent - send_start) * 1000.0)
                state.send_count += 1
                state.sent_at.append(sent)
                trim_window(state.sent_at, sent)
                metrics.DEVICE_LATENCY.labels(device=key).set(device.tracker.effective_latency_s)
                metrics.DEVICE_FPS.labels(device=key).set(device.max_fps)
```

The pacing below (`last_send_time += 1.0 / device.max_fps` and the rest) stays as it is, and runs after either branch.

Run: `uv run pytest tests/scheduling -q`
Expected: all pass.

- [ ] **Step 5: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/config.py src/dj_ledfx/devices/lifx src/dj_ledfx/scheduling/scheduler.py tests/devices/lifx tests/scheduling/test_scheduler.py
git commit -m "fix(scheduling): each light at its own rate, LIFX fades and display delays, and no frame sent twice"
```

---

### Task 4: LIFX discovery never rewrites a light from a silent one

Cause 5, ruling 16. A known light that's online is left out of a scan before it's asked anything; a light that doesn't answer `GetVersion` gives no record; a light that goes quiet during its setup is left for a later scan instead of being set up from defaults.

**Files:**
- Modify: `src/dj_ledfx/devices/lifx/transport.py` (`discover`, `unicast_sweep`; `_query_version` goes), `src/dj_ledfx/devices/lifx/discovery.py` (`discover`, `_setup`, `_create_adapter`, `_query`), `tests/lifx_fakes.py` (`quiet`)
- Test: `tests/devices/lifx/test_transport.py`, `tests/devices/lifx/test_discovery.py`

**Interfaces:**
- Consumes: Task 3's `_setup`.
- Produces:
  - `LifxTransport.discover(timeout_s: float = 1.0, on_record: Callable[[LifxDeviceRecord], None] | None = None, skip_macs: Collection[str] = ())`: a light whose MAC (lowercase hex) is in `skip_macs` is never asked its version, and a light that doesn't answer `GetVersion` twice gives no record. `LifxTransport._query_version` is gone; `query_version` (None on silence) and `query_host_firmware` stay (the fixture-recording script uses the latter).
  - `LifxBackend._query(record, msg_type, reply_type, parse, timeout) -> T | None` asks twice; it returns None for a `StateUnhandled` reply or one that doesn't parse, and raises the module's `_Silent` when the light doesn't answer. `_setup` returns None on `_Silent`.
  - `FakeLifxTransport(..., quiet: Collection[int] = ())`: message types it never answers.

- [ ] **Step 1: Write the failing transport tests**

In `tests/devices/lifx/test_transport.py`, make the packet import `from dj_ledfx.devices.lifx.packet import GET_VERSION, STATE_UNHANDLED, STATE_VERSION, LifxPacket`, and add after `_reply`:

```python
def _service(transport: LifxTransport, mac: bytes) -> bytes:
    """A light's StateService: it speaks UDP on 56700."""
    return LifxPacket(
        tagged=False,
        source=transport.source_id,
        target=mac + b"\x00\x00",
        ack_required=False,
        res_required=False,
        sequence=0,
        msg_type=3,
        payload=struct.pack("<BI", 1, 56700),
    ).pack()
```

Replace `test_query_version_retries_once_then_defaults_to_a_bulb` with:

```python
@pytest.mark.asyncio
async def test_query_version_retries_once_then_gives_up() -> None:
    transport, sent = _transport()
    assert await transport.query_version(b"\xaa" * 6, "127.0.0.1", 56700) is None
    assert [p.msg_type for p, _ in sent.packets] == [GET_VERSION, GET_VERSION]


@pytest.mark.asyncio
async def test_discovery_skips_known_lights_and_leaves_silent_ones_for_later() -> None:
    transport, sent = _transport()
    known, silent, new = (bytes.fromhex(f"d073d500000{i}") for i in (1, 2, 3))
    found: list[LifxDeviceRecord] = []
    scan = asyncio.create_task(
        transport.discover(timeout_s=0.1, on_record=found.append, skip_macs={known.hex()})
    )
    await asyncio.sleep(0.01)
    for mac in (known, silent, new):
        transport._on_packet_received(_service(transport, mac), ("127.0.0.1", 56700))
    await asyncio.sleep(0.01)  # every light that isn't skipped is asked its version
    asked = [p for p, _ in sent.packets if p.msg_type == GET_VERSION]
    assert {p.target[:6] for p in asked} == {silent, new}
    request = next(p for p in asked if p.target[:6] == new)
    transport._on_packet_received(
        _reply(transport, request, STATE_VERSION, struct.pack("<III", 1, 57, 0)),
        ("127.0.0.1", 56700),
    )

    records = await scan

    assert [(r.mac, r.product) for r in records] == [(new, 57)]
    assert found == records
    retried = [p for p, _ in sent.packets if p.msg_type == GET_VERSION and p.target[:6] == silent]
    assert len(retried) == 2  # asked twice, then left for a later scan: no made-up bulb
```

Run: `uv run pytest tests/devices/lifx/test_transport.py -q`
Expected: the discovery test fails with `TypeError` (`discover()` takes no `skip_macs`). The scan takes about 2 s: discovery broadcasts three times, a second apart.

- [ ] **Step 2: Skip known lights and drop silent ones in the transport**

In `src/dj_ledfx/devices/lifx/transport.py`, replace `discover` with:

```python
    async def discover(
        self,
        timeout_s: float = 1.0,
        on_record: Callable[[LifxDeviceRecord], None] | None = None,
        skip_macs: Collection[str] = (),
    ) -> list[LifxDeviceRecord]:
        """Broadcast GetService, collect responses, query versions.

        A light whose MAC (hex) is in `skip_macs` is known and online: it's never asked.
        A light that doesn't answer GetVersion gives no record; a later scan asks again.
        If *on_record* is provided it is called as soon as each device's version query
        completes, rather than waiting for all devices.
        """
        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex -> (mac, ip, port)
        version_tasks: list[asyncio.Task[None]] = []
        results: list[LifxDeviceRecord] = []

        async def _query_version_and_record(mac: bytes, ip: str, port: int) -> None:
            version = await self.query_version(mac, ip, port)
            if version is None:
                logger.info("LIFX {} didn't answer GetVersion; a later scan asks again", ip)
                return
            vendor, product = version
            record = LifxDeviceRecord(mac=mac, ip=ip, port=port, vendor=vendor, product=product)
            results.append(record)
            if on_record is not None:
                on_record(record)

        def _on_state_service(pkt: LifxPacket, addr: tuple[str, int]) -> None:
            if pkt.msg_type != 3:
                return
            service, port = parse_state_service(pkt.payload)
            if service != 1:  # UDP
                return
            mac = pkt.target[:6]
            if mac.hex() in skip_macs or mac.hex() in discovered:
                return
            discovered[mac.hex()] = (mac, addr[0], port)
            version_tasks.append(
                asyncio.create_task(_query_version_and_record(mac, addr[0], port))
            )
```

and keep the rest of the method (from `self.add_listener(_on_state_service)` to `return results`) as it is. In `unicast_sweep`, replace its last loop with:

```python
        results: list[LifxDeviceRecord] = []
        for mac, ip, port in discovered.values():
            version = await self.query_version(mac, ip, port)
            if version is None:
                logger.info("LIFX {} didn't answer GetVersion; a later scan asks again", ip)
                continue
            vendor, product = version
            results.append(
                LifxDeviceRecord(mac=mac, ip=ip, port=port, vendor=vendor, product=product)
            )
```

Delete `_query_version`.

Run: `uv run pytest tests/devices/lifx/test_transport.py -q`
Expected: all pass.

- [ ] **Step 3: Write the failing backend tests**

In `tests/lifx_fakes.py`, give `FakeLifxTransport.__init__` a last keyword, `quiet: Collection[int] = ()`, kept as `self.quiet = set(quiet)  # message types it never answers`, and make the start of `request_response`:

```python
        self.sent.append(packet)
        if self.silent or packet.msg_type in self.quiet:
            return None
```

In `tests/devices/lifx/test_discovery.py`, add `from collections.abc import Callable, Collection` (in place of the `Callable` import), import `GET_COLOR`, `GET_EXTENDED_COLOR_ZONES` and `GET_HOST_FIRMWARE` beside `GET_DEVICE_CHAIN`, and give `test_discover_returns_discovered_devices`'s `_fake_discover` a third parameter, `skip_macs: Collection[str] = ()` (its signature then goes one parameter per line). Add:

```python
async def test_a_known_online_light_is_left_out_before_it_is_asked() -> None:
    transport = FakeLifxTransport(product=1)
    skipped: list[Collection[str]] = []

    async def _fake_discover(
        timeout_s: float = 1.0,
        on_record: Callable[[LifxDeviceRecord], None] | None = None,
        skip_macs: Collection[str] = (),
    ) -> list[LifxDeviceRecord]:
        skipped.append(skip_macs)
        return []

    transport.discover = _fake_discover  # type: ignore[attr-defined]
    known = {f"lifx:{MAC.hex()}", "govee:test-lamp"}
    await _backend(transport).discover(AppConfig(), skip_ids=known)
    assert skipped == [{MAC.hex()}]


# Review Focus 4: a known light that's offline, or half-answers, during discovery keeps its
# ghost and its row. Set up from a silent reply, it would come back the wrong kind or size.
@pytest.mark.parametrize(
    ("product", "quiet"),
    [
        (57, GET_HOST_FIRMWARE),
        (57, GET_COLOR),
        (57, GET_DEVICE_CHAIN),
        (141, GET_EXTENDED_COLOR_ZONES),
    ],
)
async def test_a_known_light_offline_during_discovery_keeps_its_row(
    product: int, quiet: int
) -> None:
    zones = [(0, 0, 65535, 3500)] * 36
    transport = FakeLifxTransport(
        product=product, chain=[(5, 6)], zones=zones, firmware=(4, 10), quiet={quiet}
    )
    assert await _backend(transport)._setup(_record(product), AppConfig()) is None
    assert transport.types().count(quiet) == 2  # asked twice, then left for a later scan


async def test_connect_known_leaves_a_half_answering_light_offline() -> None:
    transport = FakeLifxTransport(product=57, chain=[(5, 6)], quiet={GET_DEVICE_CHAIN})
    row = _row(name="Test matrix")
    assert await _backend(transport).connect_known([row], AppConfig()) == []
```

The existing `test_tile_without_a_chain_reply_falls_back_to_five_8x8_tiles` keeps passing: a `StateUnhandled` reply still falls back.

Run: `uv run pytest tests/devices/lifx/test_discovery.py -q`
Expected: the new tests fail: the backend passes no `skip_macs`, and a quiet light is set up from defaults.

- [ ] **Step 4: Leave silent lights for a later scan in the backend**

In `src/dj_ledfx/devices/lifx/discovery.py`, import `GET_HOST_FIRMWARE`, `STATE_HOST_FIRMWARE` and `parse_state_host_firmware` beside the other packet names, and add above `class LifxBackend`:

```python
class _Silent(Exception):
    """A light stayed silent to a setup query: it's set up when a later scan finds it."""
```

In `discover`, delete the two lines at the start of `_setup_device` that check `skip_ids` (the transport skips those lights now), and replace the `await transport.discover(...)` line with:

```python
        # Known lights that are online are left out before they're asked anything.
        known = {sid.removeprefix("lifx:") for sid in skip_ids or () if sid.startswith("lifx:")}
        await transport.discover(
            timeout_s=lifx.discovery_timeout_s, on_record=_on_record, skip_macs=known
        )
```

Make `_setup`:

```python
    async def _setup(self, record: LifxDeviceRecord, config: AppConfig) -> DiscoveredDevice | None:
        assert self._transport is not None
        try:
            adapter = await self._create_adapter(record, config)
        except _Silent as silent:
            logger.info("{}; it's left as it was until a later scan", silent)
            return None
        if adapter is None:
            return None
        tracker = self._create_tracker(config, display_ms=adapter.display_ms)
        await adapter.connect()
        self._transport.register_device(record, rtt_callback=tracker.update_rtt)
        max_fps = stream_fps(type(adapter), config.devices.lifx.max_fps)
        return DiscoveredDevice(adapter=adapter, tracker=tracker, max_fps=max_fps)
```

In `_create_adapter`, replace the `firmware = await transport.query_host_firmware(...)` line with:

```python
        firmware = await self._query(
            record, GET_HOST_FIRMWARE, STATE_HOST_FIRMWARE, parse_state_host_firmware, 0.5
        )
```

and replace `_query` with:

```python
    async def _query(
        self,
        record: LifxDeviceRecord,
        msg_type: int,
        reply_type: int,
        parse: Callable[[bytes], T],
        timeout: float,
    ) -> T | None:
        """Ask the light, twice if it must, and parse its reply. None when it answers that
        it can't (StateUnhandled) or with a reply that doesn't parse: the caller falls back.
        Raises _Silent when it doesn't answer: a light set up from silence would be the
        wrong kind or size."""
        assert self._transport is not None
        reply = await self._transport.ask(
            record.mac,
            (record.ip, record.port),
            msg_type,
            b"",
            reply_type,
            tries=2,
            timeout=timeout,
        )
        if reply is None:
            raise _Silent(f"LIFX {record.ip} didn't answer message {msg_type}")
        if reply.msg_type != reply_type:
            return None
        try:
            return parse(reply.payload)
        except ValueError:
            return None
```

`_query_label`, `_query_chain` and `_query_zone_count` keep calling `_query` as they do.

Run: `uv run pytest tests/devices/lifx -q`
Expected: all pass.

- [ ] **Step 5: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/devices/lifx/transport.py src/dj_ledfx/devices/lifx/discovery.py tests/lifx_fakes.py tests/devices/lifx/test_transport.py tests/devices/lifx/test_discovery.py
git commit -m "fix(lifx): discovery skips known lights before asking and never sets a light up from silence"
```

---

### Task 5: A Govee lamp that stops answering goes offline

Cause 6's last part, ruling 15, Review Focus 1. A status query that gets no answer is a missed read, so the light monitor takes the lamp offline after three, and the scheduler stops sending to it. While another program holds UDP 4002 the app can't hear any lamp, and the reading stays unknown.

**Files:**
- Modify: `src/dj_ledfx/devices/govee/adapter_base.py` (`read_light`)
- Test: `tests/devices/govee/test_control.py`

**Interfaces:**
- Consumes: `NoAnswer` and `try_read` (`devices/capabilities.py`); `LightMonitor` counts a read that raises as a miss, and three in a row emit `DeviceOfflineEvent` (`zones/lights.py`, unchanged).
- Produces: `GoveeAdapterBase.read_light()` returns `LightReading.UNKNOWN` while `can_receive` is False, and raises `NoAnswer` when the lamp doesn't answer.

- [ ] **Step 1: Write the failing tests**

In `tests/devices/govee/test_control.py`, make the capabilities import `from dj_ledfx.devices.capabilities import LightReading, NoAnswer, try_read`, and replace `test_read_light_is_unknown_when_nothing_comes_back` (the parametrized test) with:

```python
async def test_read_light_is_unknown_while_another_program_holds_the_reply_port(
    record: GoveeDeviceRecord,
) -> None:
    transport = _transport(can_receive=False)
    adapter = GoveeSolidAdapter(transport, record)
    assert await adapter.read_light() == LightReading.UNKNOWN
    transport.query_status.assert_not_awaited()


# Review Focus 1: a lamp that stops answering mid-look is a missed read. Three in a row take
# it offline (zones/lights.py), so it gets no frames until a scan finds it again.
async def test_a_lamp_that_stops_answering_is_missing_not_unknown(
    record: GoveeDeviceRecord,
) -> None:
    adapter = GoveeSolidAdapter(_transport(status=None), record)
    with pytest.raises(NoAnswer):
        await adapter.read_light()
    assert await try_read(adapter) is None  # what the light monitor counts as a miss
```

Run: `uv run pytest tests/devices/govee/test_control.py -q`
Expected: `test_a_lamp_that_stops_answering_is_missing_not_unknown` fails: `DID NOT RAISE`.

- [ ] **Step 2: Raise on silence**

In `src/dj_ledfx/devices/govee/adapter_base.py`, import `NoAnswer` beside `LightReading` and replace `read_light` with:

```python
    async def read_light(self) -> LightReading:
        """Power and colour from a status query. Unknown while another program holds UDP
        4002, since no reply can reach us; NoAnswer when the lamp stays silent, which the
        light monitor counts as a missed read."""
        if not self._transport.can_receive:
            return LightReading.UNKNOWN
        state = await self._status()
        if state is None:
            raise NoAnswer(f"Govee {self._record.ip} didn't answer a status query")
        return LightReading(power=bool(state.on_off), colour=(state.r, state.g, state.b))
```

The zone manager's own reads go through `try_read` and treat None as unknown, as they did.

Run: `uv run pytest tests/devices/govee tests/zones/test_lights.py -q`
Expected: all pass.

- [ ] **Step 3: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/devices/govee/adapter_base.py tests/devices/govee/test_control.py
git commit -m "fix(govee): a lamp that stops answering is a missed read, so it goes offline"
```

---

### Task 6: Razer frames, one colour per segment

Cause 6, rulings O2, 11, 12 and 14. The protocol gains razer frames and the switch, `ptReal` goes, the SKU table learns which models take razer and how they stand, and `GoveeSegmentAdapter` streams razer or one colour. Govee lamps report their model and their segments.

**Files:**
- Modify: `src/dj_ledfx/devices/govee/protocol.py`, `src/dj_ledfx/devices/govee/types.py`, `src/dj_ledfx/devices/govee/sku_registry.py`, `src/dj_ledfx/devices/govee/segment.py` (rewritten), `src/dj_ledfx/devices/govee/adapter_base.py` (`capabilities`)
- Test: `tests/devices/govee/test_protocol.py`, `tests/devices/govee/test_segment.py`, `tests/devices/govee/test_sku_registry.py` (rewritten), `tests/devices/govee/test_control.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `devices/govee/protocol.py`: `RAZER_HEADER = bytes((0xBB, 0x00, 0xFA, 0xB0, 0x00))`, `RAZER_SWITCH = bytes((0xBB, 0x00, 0x01, 0xB1))`, `MAX_RAZER_SEGMENTS = 255`, `build_razer_switch(on: bool) -> dict[str, Any]`, `build_razer_frame(colors: NDArray[np.uint8]) -> dict[str, Any]` (raises `ValueError` unless it has 1 to 255 rows). `build_ble_packet`, `encode_segment_mask`, `build_segment_color_packet`, `build_pt_real_message` and `map_colors_to_segments` are gone.
  - `devices/govee/types.py`: `GoveeForm = Literal["upright", "strip"]`; `GoveeDeviceCapability(is_rgbic, segment_count, razer: bool = False, form: GoveeForm = "strip", segments_from_top: bool = False)`.
  - `devices/govee/segment.py`: `RAZER_IDLE_S = 2.0`, `UPRIGHT_HEIGHT_M = 1.4`, `STRIP_LENGTH_M = 1.0`; `GoveeSegmentAdapter(transport, record, num_segments, *, razer: bool = False, form: GoveeForm = "strip", from_top: bool = False, clock: Callable[[], float] = time.monotonic)`, with a `razer` property. An upright lamp's geometry is `StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)`, or `(0, -1, 0)` from the top; any other is `StripGeometry((1, 0, 0), STRIP_LENGTH_M)`.
  - `GoveeAdapterBase.capabilities`: `DeviceCapabilities(protocol="Govee", model="Govee <model number>", multizone=led_count > 1)`.

- [ ] **Step 1: Write the failing protocol tests**

In `tests/devices/govee/test_protocol.py`, delete every class from `TestBuildBlePacket` to the end of the file, and make the imports:

```python
from __future__ import annotations

import base64

import numpy as np
import pytest

from dj_ledfx.devices.govee.protocol import (
    MAX_RAZER_SEGMENTS,
    build_brightness_message,
    build_razer_frame,
    build_razer_switch,
    build_scan_message,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
    xor_checksum,
)
```

Add at the end:

```python
class TestRazer:
    def test_razer_switches_on_and_off(self) -> None:
        on = {"msg": {"cmd": "razer", "data": {"pt": "uwABsQEK"}}}
        off = {"msg": {"cmd": "razer", "data": {"pt": "uwABsQAL"}}}
        assert (build_razer_switch(on=True), build_razer_switch(on=False)) == (on, off)

    def test_a_frame_is_one_colour_per_segment_and_a_checksum(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        msg = build_razer_frame(colors)
        assert msg["msg"]["cmd"] == "razer"
        packet = base64.b64decode(msg["msg"]["data"]["pt"])
        assert packet[:6] == bytes((0xBB, 0x00, 0xFA, 0xB0, 0x00, 3))
        assert packet[6:15] == colors.tobytes()
        assert len(packet) == 16 and packet[15] == xor_checksum(packet[:15])

    @pytest.mark.parametrize("count", [0, MAX_RAZER_SEGMENTS + 1])
    def test_a_frame_has_1_to_255_segments(self, count: int) -> None:
        with pytest.raises(ValueError, match="1 to 255 segments"):
            build_razer_frame(np.zeros((count, 3), dtype=np.uint8))
```

Run: `uv run pytest tests/devices/govee/test_protocol.py -q`
Expected: an import error for `MAX_RAZER_SEGMENTS`.

- [ ] **Step 2: Razer in the protocol**

In `src/dj_ledfx/devices/govee/protocol.py`, add after `xor_checksum` (the `ptReal` helpers stay until Step 5: today's `segment.py` imports them, and the test suite can't load without it):

```python
# Razer (DreamView) packets, as LedFx 2.1.9's Govee driver sends them to UDP 4003: a frame
# is the header, the segment count, an RGB triple per segment and an XOR checksum; the
# switch is its four bytes, 1 or 0, and the checksum. Razer frames get no replies.
RAZER_HEADER = bytes((0xBB, 0x00, 0xFA, 0xB0, 0x00))
RAZER_SWITCH = bytes((0xBB, 0x00, 0x01, 0xB1))
MAX_RAZER_SEGMENTS = 255  # the count is one byte


def _razer(packet: bytes) -> dict[str, Any]:
    """A razer message: the packet and its XOR checksum, in base64."""
    framed = packet + bytes((xor_checksum(packet),))
    return {"msg": {"cmd": "razer", "data": {"pt": base64.b64encode(framed).decode("ascii")}}}


def build_razer_switch(on: bool) -> dict[str, Any]:
    """Switch the lamp's razer mode on (it takes razer frames) or off (its own modes)."""
    return _razer(RAZER_SWITCH + bytes((1 if on else 0,)))


def build_razer_frame(colors: NDArray[np.uint8]) -> dict[str, Any]:
    """One razer frame: a colour for each of the lamp's segments, in segment order."""
    count = len(colors)
    if not 0 < count <= MAX_RAZER_SEGMENTS:
        raise ValueError(f"A razer frame takes 1 to {MAX_RAZER_SEGMENTS} segments, not {count}")
    rgb = np.ascontiguousarray(colors, dtype=np.uint8).tobytes()
    return _razer(RAZER_HEADER + bytes((count,)) + rgb)
```

Run: `uv run pytest tests/devices/govee/test_protocol.py -q`
Expected: all pass.

- [ ] **Step 3: The SKU table learns razer and form (ruling 12)**

Replace `GoveeDeviceCapability` in `src/dj_ledfx/devices/govee/types.py` with the code below, adding `from typing import Literal` to the imports:

```python
GoveeForm = Literal["upright", "strip"]  # how a lamp's segments run: up a pole, or along


@dataclass(frozen=True, slots=True)
class GoveeDeviceCapability:
    """What the SKU table knows of a model."""

    is_rgbic: bool
    segment_count: int  # 0 for non-RGBIC
    razer: bool = False  # it takes razer (DreamView) frames: one colour per segment
    form: GoveeForm = "strip"
    segments_from_top: bool = False  # an upright lamp's segment 0 is at the top
```

Change the table's first entry only, and say where the new fields come from (the model numbers stay out of this plan, so `sed` finds the line):

```bash
sed -i '0,/GoveeDeviceCapability(is_rgbic=True, segment_count=15)/s//GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")/' src/dj_ledfx/devices/govee/sku_registry.py
sed -i '/^SKU_REGISTRY/i # razer and form: the light-output plan'"'"'s ruling 12 (an upright lamp; a strip nobody can check).' src/dj_ledfx/devices/govee/sku_registry.py
git diff --stat src/dj_ledfx/devices/govee/sku_registry.py
```

Expected: `1 file changed, 2 insertions(+), 1 deletion(-)`: the comment and the first entry; the second entry is as it was.

Replace `tests/devices/govee/test_sku_registry.py` with (it names no model: the table's keys are read from it):

```python
from __future__ import annotations

from dj_ledfx.devices.govee.sku_registry import (
    DEFAULT_CAPABILITY,
    SKU_REGISTRY,
    get_device_capability,
    get_segment_count,
)


def test_every_entry_has_segments_and_is_found_by_its_model() -> None:
    for model, capability in SKU_REGISTRY.items():
        assert capability.is_rgbic and capability.segment_count > 1, model
        assert get_device_capability(model) is capability


def test_an_unknown_model_plays_one_colour() -> None:
    capability = get_device_capability("not-a-model")
    assert capability == DEFAULT_CAPABILITY
    assert (capability.is_rgbic, capability.segment_count, capability.razer) == (False, 0, False)


def test_the_upright_lamp_takes_razer_and_the_strip_does_not() -> None:  # ruling 12
    upright, strip = SKU_REGISTRY.values()
    assert (upright.razer, upright.form, upright.segments_from_top) == (True, "upright", False)
    assert (strip.razer, strip.form) == (False, "strip")


def test_the_config_override_sets_the_segment_count() -> None:  # until Task 7
    model = next(iter(SKU_REGISTRY))
    assert get_segment_count(model) == SKU_REGISTRY[model].segment_count
    assert get_segment_count(model, config_override=10) == 10
    assert get_segment_count("not-a-model") == 0
```

Run: `uv run pytest tests/devices/govee/test_sku_registry.py -q`
Expected: all pass.

- [ ] **Step 4: Write the failing adapter tests**

In `tests/devices/govee/test_segment.py`, delete `test_send_frame_sends_pt_real` and `test_send_frame_downsamples`. In `test_send_frame_colorwc_fallback`, `test_restore_state_sends_commands` and `test_restore_state_skips_turn_off_when_on`, pass `razer=False` to `GoveeSegmentAdapter`, and give the first the docstring `"""In colour mode a frame goes out as its average colour, by colorwc."""`. Make the imports:

```python
from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.govee.protocol import build_brightness_message, build_razer_switch
from dj_ledfx.devices.govee.segment import RAZER_IDLE_S, UPRIGHT_HEIGHT_M, GoveeSegmentAdapter
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.spatial.geometry import StripGeometry

RAZER_ON, RAZER_OFF = build_razer_switch(on=True), build_razer_switch(on=False)


def _sent(transport: MagicMock) -> list[dict[str, Any]]:
    return [call.args[1] for call in transport.send_command.call_args_list]


def _razer_rgb(message: dict[str, Any]) -> bytes:
    """A razer frame's colours: after the header and the count, before the checksum."""
    assert message["msg"]["cmd"] == "razer"
    return base64.b64decode(message["msg"]["data"]["pt"])[6:-1]
```

and add at the end:

```python
class TestRazer:
    async def test_each_segment_gets_its_own_colour(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True)
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        await adapter.send_frame(colors)
        switch, frame = _sent(mock_transport)
        assert switch == RAZER_ON and _razer_rgb(frame) == colors.tobytes()

    async def test_razer_is_switched_on_again_after_a_pause(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        now = [100.0]
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True, clock=lambda: now[0])
        frame = np.zeros((3, 3), dtype=np.uint8)
        await adapter.send_frame(frame)
        now[0] += 1.0
        await adapter.send_frame(frame)
        now[0] += RAZER_IDLE_S + 0.1
        await adapter.send_frame(frame)
        assert [m == RAZER_ON for m in _sent(mock_transport)] == [True, False, False, True, False]

    # Review Focus 2: a look started right after another re-arms razer.
    async def test_a_look_started_right_after_another_re_arms(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True, clock=lambda: 100.0)
        frame = np.zeros((3, 3), dtype=np.uint8)
        await adapter.send_frame(frame)
        captured = GoveeDeviceState(on_off=1, brightness=80, r=1, g=2, b=3).to_bytes()
        await adapter.restore_state(captured)  # the first look's Off
        await adapter.prepare_stream()  # the next look, at once
        mock_transport.send_command.reset_mock()
        await adapter.send_frame(frame)
        assert _sent(mock_transport)[0] == RAZER_ON

    async def test_a_restore_takes_the_lamp_out_of_razer_first(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True)
        state = GoveeDeviceState(on_off=0, brightness=50, r=10, g=20, b=30)
        await adapter.restore_state(state.to_bytes())
        sent = _sent(mock_transport)
        assert sent[0] == RAZER_OFF
        assert [m["msg"]["cmd"] for m in sent[1:]] == ["colorwc", "brightness", "turn"]

    async def test_a_lamp_switched_off_elsewhere_is_left_alone(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True)
        state = GoveeDeviceState(on_off=1, brightness=50, r=10, g=20, b=30)
        await adapter.restore_state(state.to_bytes(), power=False)
        assert _sent(mock_transport) == []

    async def test_a_lamp_playing_one_colour_leaves_razer_when_prepared(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=False)
        await adapter.prepare_stream()
        assert _sent(mock_transport) == [RAZER_OFF, build_brightness_message(100)]

    def test_an_upright_lamp_stands(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        up = GoveeSegmentAdapter(mock_transport, record, 15, form="upright")
        down = GoveeSegmentAdapter(mock_transport, record, 15, form="upright", from_top=True)
        assert up.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
        assert down.geometry == StripGeometry((0, -1, 0), UPRIGHT_HEIGHT_M)
```

In `tests/devices/govee/test_control.py`, import `GoveeSegmentAdapter` from `dj_ledfx.devices.govee.segment` and add:

```python
def test_a_lamp_names_its_model_and_its_segments(record: GoveeDeviceRecord) -> None:
    solid = GoveeSolidAdapter(_transport(), record).capabilities
    lamp = GoveeSegmentAdapter(_transport(), record, 15, razer=True).capabilities
    assert (solid.protocol, solid.model) == ("Govee", f"Govee {record.sku}")
    assert not solid.multizone
    assert (lamp.model, lamp.multizone) == (solid.model, True)
```

Run: `uv run pytest tests/devices/govee -q`
Expected: `test_segment.py` fails at collection with an import error for `RAZER_IDLE_S`, which stops the run. Run alone, `test_control.py`'s new test fails: `GoveeSegmentAdapter` takes no `razer`.

- [ ] **Step 5: Rewrite the segment adapter, and name the model**

Replace `src/dj_ledfx/devices/govee/segment.py` with:

```python
"""A Govee lamp with segments (engine spec §6.3). In razer mode each frame lights every
segment on its own; otherwise the frame's average colour goes out by colorwc, which the
backend sends at most GOVEE_COLOUR_FPS times a second (config.py)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import (
    build_razer_frame,
    build_razer_switch,
    build_solid_color_message,
)
from dj_ledfx.devices.govee.types import GoveeDeviceRecord, GoveeForm
from dj_ledfx.spatial.geometry import DeviceGeometry, StripGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport

# A frame after a pause this long switches razer on again first: a lamp may drop out of
# razer mode when frames stop (the light-output plan's Task 8 checks how soon).
RAZER_IDLE_S = 2.0
UPRIGHT_HEIGHT_M = 1.4  # an upright lamp's segments, bottom to top
STRIP_LENGTH_M = 1.0


class GoveeSegmentAdapter(GoveeAdapterBase):
    def __init__(
        self,
        transport: GoveeTransport,
        record: GoveeDeviceRecord,
        num_segments: int,
        *,
        razer: bool = False,
        form: GoveeForm = "strip",
        from_top: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(transport, record)
        self._num_segments = num_segments
        self._razer = razer
        self._form = form
        self._from_top = from_top
        self._clock = clock
        self._last_frame_at: float | None = None  # None: razer is switched on first

    @property
    def razer(self) -> bool:
        """True: each frame lights every segment on its own. False: one colour."""
        return self._razer

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_segment",
            led_count=self._num_segments,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
            backend="govee",
        )

    @property
    def led_count(self) -> int:
        return self._num_segments

    @property
    def geometry(self) -> DeviceGeometry:
        """An upright lamp stands, segment 0 at the bottom (or the top); another lies along
        its length. Directions are the scene's: y is up."""
        if self._form == "upright":
            up = -1 if self._from_top else 1
            return StripGeometry(direction=(0, up, 0), length=UPRIGHT_HEIGHT_M)
        return StripGeometry(direction=(1, 0, 0), length=STRIP_LENGTH_M)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        try:
            if self._razer:
                await self._send_razer(colors)
            else:
                avg = colors.mean(axis=0).astype(np.uint8)
                msg = build_solid_color_message(int(avg[0]), int(avg[1]), int(avg[2]))
                await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)

    async def _send_razer(self, colors: NDArray[np.uint8]) -> None:
        now = self._clock()
        if self._last_frame_at is None or now - self._last_frame_at > RAZER_IDLE_S:
            await self._transport.send_command(self._record.ip, build_razer_switch(on=True))
        await self._transport.send_command(self._record.ip, build_razer_frame(colors))
        self._last_frame_at = now

    async def set_power(self, on: bool) -> None:
        self._last_frame_at = None  # a lamp switched may come back out of razer mode
        await super().set_power(on)

    async def prepare_stream(self) -> None:
        """Full brightness; the next frame switches razer on. A lamp playing one colour is
        taken out of razer mode, in case a look left it there."""
        self._last_frame_at = None
        if not self._razer:
            await self._transport.send_command(self._record.ip, build_razer_switch(on=False))
        await super().prepare_stream()

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """Out of razer mode first, so the lamp shows the colour it gets back. A lamp
        switched off elsewhere (power=False) is left alone, as the base class does."""
        self._last_frame_at = None
        if self._razer and power:
            await self._transport.send_command(self._record.ip, build_razer_switch(on=False))
        await super().restore_state(state, power=power)
```

In `src/dj_ledfx/devices/govee/protocol.py`, delete `build_ble_packet`, `encode_segment_mask`, `build_segment_color_packet`, `build_pt_real_message` and `map_colors_to_segments`, and the imports only they used (`Sequence`, `RGB`): nothing uses them now.

In `src/dj_ledfx/devices/govee/adapter_base.py`, import `DeviceCapabilities` beside `LightReading` and `NoAnswer`, and add after `is_connected`:

```python
    @property
    def capabilities(self) -> DeviceCapabilities:
        """The model is "Govee <model number>"; multizone when it has segments to light."""
        sku = self._record.sku
        return DeviceCapabilities(
            protocol="Govee",
            model=f"Govee {sku}" if sku else "Govee",
            multizone=self.led_count > 1,
        )
```

Run: `uv run pytest tests/devices/govee -q`
Expected: all pass. `GoveeSegmentAdapter`'s default is `razer=False`, so `devices/govee/backend.py` still builds what it built before; Task 7 hands it the plan.

- [ ] **Step 6: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/devices/govee tests/devices/govee
git commit -m "feat(govee): razer frames, one colour per segment; ptReal goes"
```

---

### Task 7: Each lamp's segments, mode and rate, and a razer check script

Rulings 10, 13 and 21. The backend builds each lamp from a plan: how many segments, razer or one colour, and the rate that goes with it (razer up to 30 a second, one colour at most 10). The script plays razer patterns on one lamp for Task 8.

**Files:**
- Create: `src/dj_ledfx/devices/govee/output.py`, `tests/devices/govee/test_output.py`, `scripts/govee_razer_check.py`
- Modify: `src/dj_ledfx/config.py`, `src/dj_ledfx/devices/govee/backend.py` (rewritten), `src/dj_ledfx/devices/govee/sku_registry.py` (`get_segment_count` goes), `config.toml`
- Test: `tests/devices/govee/test_backend.py`, `tests/devices/govee/test_sku_registry.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: Task 1's `make_strategy` and `LatencyTracker.update_rtt`; Task 6's `GoveeDeviceCapability` fields, `GoveeSegmentAdapter(..., razer=, form=, from_top=)` and `build_razer_*`.
- Produces:
  - `config.py`: `GOVEE_RAZER_FPS = 30`, `GOVEE_COLOUR_FPS = 10`; `GoveeConfig.max_fps` defaults to `GOVEE_RAZER_FPS`.
  - `devices/govee/output.py`: `GoveeMode = Literal["segments", "colour"]`; `GoveeOutput(mode: GoveeMode | None = None, segments: int | None = None)` (frozen); `LampPlan(segments: int, razer: bool)` (frozen); `lamp_plan(capability: GoveeDeviceCapability, output: GoveeOutput, segment_override: int | None) -> LampPlan`; `lamp_fps(plan: LampPlan, max_fps: int) -> int`.
  - `GoveeBackend._setup(transport, record, config) -> DiscoveredDevice` and `GoveeBackend._adapter(transport, record, config) -> tuple[GoveeAdapterBase, int]` (the adapter and its rate). `get_segment_count` is gone.
  - `scripts/govee_razer_check.py --ip ADDRESS --segments N --pattern {whole,ends,stripes,chase,gaps,status} --restore-colour RRGGBB --restore-power {on,off}`.

- [ ] **Step 1: Write the failing plan tests**

Create `tests/devices/govee/test_output.py`:

```python
"""How a Govee lamp plays: its segments, razer or one colour, and its rate."""

from __future__ import annotations

import pytest

from dj_ledfx.config import GOVEE_COLOUR_FPS, GOVEE_RAZER_FPS
from dj_ledfx.devices.govee.output import GoveeOutput, LampPlan, lamp_fps, lamp_plan
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

UPRIGHT = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")
NO_RAZER = GoveeDeviceCapability(is_rgbic=True, segment_count=15)
PLAIN = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


@pytest.mark.parametrize(
    ("capability", "output", "override", "plan"),
    [
        (UPRIGHT, GoveeOutput(), None, LampPlan(15, razer=True)),
        (NO_RAZER, GoveeOutput(), None, LampPlan(15, razer=False)),
        (UPRIGHT, GoveeOutput(), 10, LampPlan(10, razer=True)),
        (PLAIN, GoveeOutput(), 10, LampPlan(1, razer=False)),  # the override is for RGBIC
        (UPRIGHT, GoveeOutput(mode="colour"), None, LampPlan(15, razer=False)),
        (NO_RAZER, GoveeOutput(mode="segments", segments=20), 10, LampPlan(20, razer=True)),
        (PLAIN, GoveeOutput(mode="segments"), None, LampPlan(1, razer=False)),  # none to light
    ],
)
def test_a_lamp_s_own_output_then_the_config_then_the_table(
    capability: GoveeDeviceCapability, output: GoveeOutput, override: int | None, plan: LampPlan
) -> None:
    assert lamp_plan(capability, output, override) == plan


def test_razer_streams_at_the_configured_rate_and_one_colour_at_ten_at_most() -> None:
    assert lamp_fps(LampPlan(15, razer=True), GOVEE_RAZER_FPS) == GOVEE_RAZER_FPS
    assert lamp_fps(LampPlan(15, razer=False), GOVEE_RAZER_FPS) == GOVEE_COLOUR_FPS
    assert lamp_fps(LampPlan(1, razer=False), 5) == 5
```

Run: `uv run pytest tests/devices/govee/test_output.py -q`
Expected: an import error for `GOVEE_COLOUR_FPS`.

- [ ] **Step 2: The rates and the plan**

In `src/dj_ledfx/config.py`, under the LIFX rates:

```python
# Govee frames a second: razer frames (one colour per segment), and colorwc (one colour),
# capped whatever max_fps says: at 40 a second colorwc ran nine commands behind, and two
# lamps were lost for ten minutes after a minute of it.
GOVEE_RAZER_FPS = 30
GOVEE_COLOUR_FPS = 10
```

and make `GoveeConfig`'s `max_fps: int = GOVEE_RAZER_FPS  # one colour is capped at GOVEE_COLOUR_FPS`.

Create `src/dj_ledfx/devices/govee/output.py`:

```python
"""How a Govee lamp plays (the light-output plan's rulings 10 and 13): razer segments or
one colour, how many segments, and how many frames a second. A lamp's own output comes
first, then the config's segment override, then the SKU table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dj_ledfx.config import GOVEE_COLOUR_FPS
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

GoveeMode = Literal["segments", "colour"]  # razer, one colour per segment; or colorwc


@dataclass(frozen=True, slots=True)
class GoveeOutput:
    """A lamp's own output. None leaves that part to the config and the SKU table."""

    mode: GoveeMode | None = None
    segments: int | None = None


@dataclass(frozen=True, slots=True)
class LampPlan:
    segments: int  # 1: one colour, through the solid adapter
    razer: bool


def lamp_plan(
    capability: GoveeDeviceCapability, output: GoveeOutput, segment_override: int | None
) -> LampPlan:
    """The lamp's segments (its own count, else the config's override for an RGBIC lamp,
    else the table's) and whether it plays razer (its own mode, else the table's). Fewer
    than two segments plays one colour."""
    if output.segments is not None:
        segments = output.segments
    elif segment_override is not None and capability.is_rgbic:
        segments = segment_override
    else:
        segments = capability.segment_count
    if segments < 2:
        return LampPlan(1, razer=False)
    razer = capability.razer if output.mode is None else output.mode == "segments"
    return LampPlan(segments, razer)


def lamp_fps(plan: LampPlan, max_fps: int) -> int:
    """Razer at the configured rate; one colour at GOVEE_COLOUR_FPS at most."""
    return max_fps if plan.razer else min(max_fps, GOVEE_COLOUR_FPS)
```

Run: `uv run pytest tests/devices/govee/test_output.py -q`
Expected: all pass.

- [ ] **Step 3: Write the failing backend tests**

In `tests/devices/govee/test_backend.py`, make the imports:

```python
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import (
    GOVEE_COLOUR_FPS,
    GOVEE_RAZER_FPS,
    AppConfig,
    DevicesConfig,
    GoveeConfig,
)
from dj_ledfx.devices.backend import DiscoveredDevice
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.segment import UPRIGHT_HEIGHT_M, GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceCapability, GoveeDeviceRecord
from dj_ledfx.spatial.geometry import StripGeometry
```

In `test_discover_creates_segment_adapter_for_rgbic`, replace `assert results[0].max_fps == 40` with:

```python
        assert results[0].adapter.razer  # the first entry plays razer (ruling 12)
        assert results[0].max_fps == config.devices.govee.max_fps
```

and at the end of `test_discover_creates_solid_adapter_for_unknown` add `assert results[0].max_fps == GOVEE_COLOUR_FPS`. Then add at the end of the file:

```python
TEST_MODEL = "test-model"


def _lamp_row(sku: str = TEST_MODEL) -> dict[str, Any]:
    return {
        "id": "govee:test-lamp",
        "name": "Test lamp",
        "backend": "govee",
        "ip": "127.0.0.1",
        "device_id": "test-lamp",
        "sku": sku,
    }


async def _connect(config: AppConfig, sku: str = TEST_MODEL) -> DiscoveredDevice:
    transport = MagicMock()
    transport.is_open = True
    transport.can_receive = True
    transport.query_status = AsyncMock(return_value={"onOff": 1})
    transport.send_command = AsyncMock()
    backend = GoveeBackend()
    backend._transport = transport
    (device,) = await backend.connect_known([_lamp_row(sku)], config)
    return device


async def test_an_upright_razer_lamp_streams_each_segment_standing(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    upright = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, upright)
    device = await _connect(config)
    assert isinstance(device.adapter, GoveeSegmentAdapter) and device.adapter.razer
    assert device.adapter.led_count == 15
    assert device.adapter.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
    assert device.max_fps == config.devices.govee.max_fps == GOVEE_RAZER_FPS


async def test_a_lamp_without_razer_plays_one_colour_at_the_colour_rate(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    no_razer = GoveeDeviceCapability(is_rgbic=True, segment_count=15)
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, no_razer)
    device = await _connect(config)
    assert isinstance(device.adapter, GoveeSegmentAdapter) and not device.adapter.razer
    assert device.max_fps == GOVEE_COLOUR_FPS


async def test_an_unknown_model_is_one_colour_at_the_colour_rate(config: AppConfig) -> None:
    device = await _connect(config, sku="not-a-model")
    assert isinstance(device.adapter, GoveeSolidAdapter)
    assert device.max_fps == GOVEE_COLOUR_FPS


async def test_the_config_s_segment_count_applies_to_an_rgbic_lamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True)
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, capability)
    config = AppConfig(devices=DevicesConfig(govee=GoveeConfig(segment_override=10)))
    device = await _connect(config)
    assert device.adapter.led_count == 10
```

In `tests/test_config.py`, add `GOVEE_RAZER_FPS` to the `from dj_ledfx.config import (...)` block and change `test_govee_defaults`' `assert config.devices.govee.max_fps == 40` to `assert config.devices.govee.max_fps == GOVEE_RAZER_FPS`. In `tests/devices/govee/test_sku_registry.py`, delete `test_the_config_override_sets_the_segment_count` and `get_segment_count` from the import.

Run: `uv run pytest tests/devices/govee tests/test_config.py -q`
Expected: five failures: `test_discover_creates_segment_adapter_for_rgbic` and `test_an_upright_razer_lamp_streams_each_segment_standing` (no razer), and `test_discover_creates_solid_adapter_for_unknown`, `test_a_lamp_without_razer_plays_one_colour_at_the_colour_rate` and `test_an_unknown_model_is_one_colour_at_the_colour_rate` (30 a second, not 10). `test_govee_defaults` passes, since Step 2 moved the default, and so does `test_the_config_s_segment_count_applies_to_an_rgbic_lamp`, since the old backend applies the override already; it stays as a guard.

- [ ] **Step 4: Build each lamp from its plan**

Replace `src/dj_ledfx/devices/govee/backend.py` with:

```python
# src/dj_ledfx/devices/govee/backend.py
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice
from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.output import GoveeOutput, lamp_fps, lamp_plan
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import get_device_capability
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.latency.strategies import make_strategy
from dj_ledfx.latency.tracker import LatencyTracker


class GoveeBackend(DeviceBackend):
    def __init__(self) -> None:
        self._transport: GoveeTransport | None = None

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.govee.enabled

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
    ) -> list[DiscoveredDevice]:
        govee = config.devices.govee
        # Reuse existing transport if already open (e.g. multi-wave discovery)
        if self._transport is None or not self._transport.is_open:
            self._transport = GoveeTransport()
            try:
                await self._transport.open()
            except OSError:
                logger.exception("Failed to open Govee transport (port 4002 in use?)")
                self._transport = None
                return []

        results: list[DiscoveredDevice] = []
        setup_tasks: list[asyncio.Task[None]] = []

        transport = self._transport  # local ref for closure

        async def _setup_device(record: GoveeDeviceRecord) -> None:
            try:
                stable_id = f"govee:{record.device_id}"
                if skip_ids and stable_id in skip_ids:
                    return
                device = await self._setup(transport, record, config)
                results.append(device)
                if on_found is not None:
                    on_found(device)
            except Exception:
                logger.exception(
                    "Failed to set up Govee device {} (sku={})",
                    record.ip,
                    record.sku,
                )

        def _on_record(record: GoveeDeviceRecord) -> None:
            task = asyncio.create_task(_setup_device(record))
            setup_tasks.append(task)

        await transport.discover(
            timeout_s=govee.discovery_timeout_s,
            on_record=_on_record,
        )

        # Wait for any in-flight setup tasks that outlasted the scan timeout
        if setup_tasks:
            await asyncio.gather(*setup_tasks, return_exceptions=True)

        if not results:
            logger.info("No Govee devices found — ensure LAN control is enabled in Govee app")

        if results:
            transport.start_probing(interval_s=govee.probe_interval_s)

        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Directly connect to known Govee devices from DB without network scanning."""
        govee_rows = [r for r in device_rows if r.get("backend") == "govee"]
        if not govee_rows:
            return []

        govee_cfg = config.devices.govee

        # Open transport if not already open
        if self._transport is None or not self._transport.is_open:
            self._transport = GoveeTransport()
            try:
                await self._transport.open()
            except OSError:
                logger.exception("Failed to open Govee transport (port 4002 in use?)")
                self._transport = None
                return []
        transport = self._transport

        results: list[DiscoveredDevice] = []
        for row in govee_rows:
            try:
                ip = row.get("ip") or ""
                device_id = row.get("device_id") or ""
                sku = row.get("sku") or ""
                # Fallback: extract device_id from stable_id (format: "govee:{device_id}")
                if not device_id:
                    stable_id = row.get("id") or ""
                    if stable_id.startswith("govee:"):
                        device_id = stable_id[len("govee:") :]
                name = row.get("name") or f"Govee ({ip})"

                if not ip:
                    logger.warning("Skipping known Govee device '{}': missing ip", name)
                    continue

                record = GoveeDeviceRecord(
                    ip=ip,
                    device_id=device_id,
                    sku=sku,
                    wifi_version="",
                    ble_version="",
                )
                results.append(await self._setup(transport, record, config))
                logger.info("Reconnected known Govee device '{}' at {}", name, ip)
            except Exception:
                logger.exception(
                    "Failed to reconnect known Govee device '{}'", row.get("name", "?")
                )

        if results:
            transport.start_probing(interval_s=govee_cfg.probe_interval_s)

        return results

    async def shutdown(self) -> None:
        if self._transport:
            self._transport.stop_probing()
            await self._transport.close()
            self._transport = None

    async def _setup(
        self, transport: GoveeTransport, record: GoveeDeviceRecord, config: AppConfig
    ) -> DiscoveredDevice:
        """Connect a lamp as its plan says it plays, and register it for latency probes.
        Raises ConnectionError when it doesn't answer."""
        adapter, max_fps = self._adapter(transport, record, config)
        await adapter.connect()
        tracker = self._create_tracker(config)
        transport.register_device(record, rtt_callback=tracker.update_rtt)
        return DiscoveredDevice(adapter=adapter, tracker=tracker, max_fps=max_fps)

    def _adapter(
        self, transport: GoveeTransport, record: GoveeDeviceRecord, config: AppConfig
    ) -> tuple[GoveeAdapterBase, int]:
        """The adapter a lamp plays through, and its rate: razer segments, one colour across
        its segments, or one colour on a lamp with fewer than two."""
        govee = config.devices.govee
        capability = get_device_capability(record.sku)
        plan = lamp_plan(capability, GoveeOutput(), govee.segment_override)
        adapter: GoveeAdapterBase
        if plan.segments < 2:
            adapter = GoveeSolidAdapter(transport, record)
        else:
            adapter = GoveeSegmentAdapter(
                transport,
                record,
                plan.segments,
                razer=plan.razer,
                form=capability.form,
                from_top=capability.segments_from_top,
            )
        max_fps = lamp_fps(plan, govee.max_fps)
        logger.info(
            "Govee {} at {}: {} segment(s), {}, {} frames a second",
            record.sku,
            record.ip,
            plan.segments,
            "razer" if plan.razer else "one colour",
            max_fps,
        )
        return adapter, max_fps

    def _create_tracker(self, config: AppConfig) -> LatencyTracker:
        govee = config.devices.govee
        strategy = make_strategy(
            govee.latency_strategy, govee.latency_ms, govee.latency_window_size
        )
        return LatencyTracker(strategy, govee.manual_offset_ms)
```

In `src/dj_ledfx/devices/govee/sku_registry.py`, delete `get_segment_count`. Bring `config.toml` in step:

```bash
sed -i '/^\[devices\.govee\]/,/^\[/{s/^max_fps = 40/max_fps = 30/}' config.toml
git diff --stat config.toml
```

Expected: `config.toml | 2 +-`.

Run: `uv run pytest tests/devices tests/test_config.py -q`
Expected: all pass.

- [ ] **Step 5: The razer check script**

Create `scripts/govee_razer_check.py`:

```python
"""Play razer (DreamView) patterns on one Govee lamp for the owner to judge by eye, then put
the lamp back as it was (the light-output plan's Task 8).

Patterns, at GOVEE_RAZER_FPS frames a second:
  whole    the whole lamp red, green, then blue, 2 s each: does it take razer frames at all?
  ends     segment 0 red, the last segment blue, the rest dim, 5 s: which end is segment 0?
  stripes  every other segment red, on blue, 5 s: does every segment show?
  chase    one white segment running from the first to the last, 10 s: order and smoothness
  gaps     2 s each of red, green, blue and white, after pauses of 1, 2 and 3 s, with razer
           switched on only at the start: does the lamp leave razer mode in a pause?
  status   the chase, asking the lamp's status once a second: does it still answer? It binds
           UDP 4002, so it runs only while the deployed app is stopped.

It sends no brightness, and binds no port except for status. From the repo root:

    uv run python scripts/govee_razer_check.py --ip ADDRESS --segments 15 --pattern ends \\
        --restore-colour RRGGBB --restore-power on
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.config import GOVEE_RAZER_FPS
from dj_ledfx.devices.govee.protocol import (
    build_razer_frame,
    build_razer_switch,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
)
from dj_ledfx.devices.govee.transport import COMMAND_PORT, RESPONSE_PORT

PATTERNS = ("whole", "ends", "stripes", "chase", "gaps", "status")
RGB = tuple[int, int, int]
RED: RGB = (255, 0, 0)
GREEN: RGB = (0, 255, 0)
BLUE: RGB = (0, 0, 255)
WHITE: RGB = (255, 255, 255)
DIM: RGB = (40, 40, 40)
Frame = NDArray[np.uint8] | None  # None: a pause, nothing sent


def _solid(segments: int, colour: RGB) -> NDArray[np.uint8]:
    return np.tile(np.array(colour, dtype=np.uint8), (segments, 1))


def frames(pattern: str, segments: int) -> list[Frame]:
    """The pattern's frames, one every 1/GOVEE_RAZER_FPS s."""
    fps = GOVEE_RAZER_FPS
    out: list[Frame] = []
    if pattern == "whole":
        for colour in (RED, GREEN, BLUE):
            out += [_solid(segments, colour)] * (2 * fps)
    elif pattern == "ends":
        frame = _solid(segments, DIM)
        frame[0], frame[-1] = RED, BLUE
        out += [frame] * (5 * fps)
    elif pattern == "stripes":
        frame = _solid(segments, BLUE)
        frame[::2] = RED
        out += [frame] * (5 * fps)
    elif pattern in ("chase", "status"):
        steps = 10 * fps
        for step in range(steps):
            frame = np.zeros((segments, 3), dtype=np.uint8)
            frame[step * segments // steps] = WHITE
            out.append(frame)
    elif pattern == "gaps":
        for colour, pause_s in ((RED, 1), (GREEN, 2), (BLUE, 3), (WHITE, 0)):
            out += [_solid(segments, colour)] * (2 * fps)
            out += [None] * (pause_s * fps)
    else:
        raise ValueError(f"Unknown pattern {pattern!r}: one of {', '.join(PATTERNS)}")
    return out


def _send(sock: socket.socket, ip: str, message: dict[str, Any]) -> None:
    sock.sendto(json.dumps(message).encode(), (ip, COMMAND_PORT))


def _bind_replies() -> socket.socket:
    replies = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        replies.bind(("0.0.0.0", RESPONSE_PORT))
    except OSError:
        replies.close()
        sys.exit(f"UDP {RESPONSE_PORT} is held (the deployed app?): stop it first")
    replies.setblocking(False)
    return replies


def _count_replies(replies: socket.socket, ip: str) -> int:
    """The lamp's status replies waiting on the socket."""
    count = 0
    while True:
        try:
            data, (sender, _port) = replies.recvfrom(4096)
        except BlockingIOError:
            return count
        if sender == ip and b"devStatus" in data:
            count += 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ip", required=True, help="the lamp's address")
    parser.add_argument("--segments", type=int, required=True)
    parser.add_argument("--pattern", choices=PATTERNS, required=True)
    parser.add_argument("--restore-colour", required=True, help="RRGGBB: its colour before")
    parser.add_argument("--restore-power", choices=("on", "off"), required=True)
    args = parser.parse_args()
    r, g, b = bytes.fromhex(args.restore_colour)
    replies = _bind_replies() if args.pattern == "status" else None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    before = during = asked = 0
    try:
        if args.restore_power == "off":
            _send(sock, args.ip, build_turn_message(on=True))
            time.sleep(1.0)
        if replies is not None:
            for _ in range(5):
                _send(sock, args.ip, build_status_query())
                time.sleep(1.0)
            before = _count_replies(replies, args.ip)
        _send(sock, args.ip, build_razer_switch(on=True))
        start = time.monotonic()
        for index, frame in enumerate(frames(args.pattern, args.segments)):
            if frame is not None:
                _send(sock, args.ip, build_razer_frame(frame))
            if replies is not None and index % GOVEE_RAZER_FPS == 0:
                _send(sock, args.ip, build_status_query())
                asked += 1
            time.sleep(max(0.0, start + (index + 1) / GOVEE_RAZER_FPS - time.monotonic()))
        if replies is not None:
            time.sleep(1.0)
            during = _count_replies(replies, args.ip)
    finally:
        _send(sock, args.ip, build_razer_switch(on=False))
        time.sleep(0.2)
        _send(sock, args.ip, build_solid_color_message(r, g, b))
        if args.restore_power == "off":
            time.sleep(0.2)
            _send(sock, args.ip, build_turn_message(on=False))
        sock.close()
        if replies is not None:
            replies.close()
    if replies is not None:
        print(f"status replies: {before}/5 before razer, {during}/{asked} during")
    print("restored")


if __name__ == "__main__":
    main()
```

Check that it parses and builds every pattern, without a lamp:

```bash
uv run python scripts/govee_razer_check.py --help | head -3
uv run python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('check', 'scripts/govee_razer_check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
print({pattern: len(check.frames(pattern, 15)) for pattern in check.PATTERNS})
"
```

Expected: the usage line, then `{'whole': 180, 'ends': 150, 'stripes': 150, 'chase': 300, 'gaps': 420, 'status': 300}`.

- [ ] **Step 6: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/config.py src/dj_ledfx/devices/govee tests/devices/govee tests/test_config.py scripts/govee_razer_check.py config.toml
git commit -m "feat(govee): each lamp's segments, razer or one colour, and its rate; a razer check script"
```

---

### Task 8: The razer check on the real lamps (orchestrator, Owner's go)

Rulings O2, 11, 12 and 22. The orchestrator runs this task, with the owner watching the lamps; every step marked **Owner's go** waits for the owner's yes. It plays Task 7's patterns on each Govee lamp and turns what the owner sees into the SKU table's first entry and `RAZER_IDLE_S`. Nothing changes unless Step 5 or Step 6 says so. Write the findings down for the PR in words only: no lamp names, addresses or model numbers, which stay in the terminal.

**Files** (only for what Steps 5 and 6 find):
- Modify: `src/dj_ledfx/devices/govee/sku_registry.py` (the first entry), `src/dj_ledfx/devices/govee/segment.py` (`RAZER_IDLE_S`; `read_light` under the fallback ruling)
- Test: `tests/devices/govee/test_sku_registry.py`, `tests/devices/govee/test_backend.py`, `tests/devices/govee/test_segment.py`

**Interfaces:**
- Consumes: Task 7's `scripts/govee_razer_check.py`; Task 6's SKU table fields and `RAZER_IDLE_S`.
- Produces: the first entry and `RAZER_IDLE_S` as the lamps showed them. Under the fallback ruling, `GoveeSegmentAdapter.read_light()` returns `LightReading.UNKNOWN` while razer frames stream.

- [ ] **Step 1: Check the preconditions (Owner's go)**

Ask the owner: "May I check the Govee lamps now? Each pattern runs 5 to 14 seconds and puts the lamp back as it was. One last check stops the deployed app for about a minute." The preconditions, verbatim: "dj-ledfx is idle: `GET http://127.0.0.1:8080/api/running` shows no zones and no overlays; LedFx is paused; each light's state is captured before and restored after; no state.db changes and no deploys."

```bash
curl -s http://127.0.0.1:8080/api/running; echo
curl -s http://127.0.0.1:8888/api/virtuals | uv run python -c 'import json, sys; print("LedFx paused:", json.load(sys.stdin)["paused"])'
```

Expected: `{"zones":[],"overlays":[]}` and `LedFx paused: True`. If a zone runs or LedFx plays, stop and ask the owner; don't stop either yourself.

- [ ] **Step 2: List the lamps, their table entries and how they are now**

```bash
MODELS=$(docker exec -u 10001 dj-ledfx-app-1 python -c "import json, sqlite3; db = sqlite3.connect('file:/app/state/state.db?mode=ro', uri=True); print(json.dumps(dict(db.execute(\"SELECT id, sku FROM devices WHERE backend = 'govee'\").fetchall())))")
uv run python - "$MODELS" <<'EOF'
import json
import sys
import urllib.request

from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY

entry = {model: number for number, model in enumerate(SKU_REGISTRY, start=1)}
models = json.loads(sys.argv[1])
with urllib.request.urlopen("http://127.0.0.1:8080/api/lights") as answer:
    lights = json.load(answer)
for light in lights:
    if light["protocol"] == "Govee":
        print(
            light["id"], light["address"].split(":")[0], light["leds"], light["status"],
            "power", light["power"], "colour", light["colour"],
            "table entry", entry.get(models.get(light["id"]), "none"),
        )
EOF
```

The first command reads each lamp's model number from the deployed database, read-only and as the app's user, so it changes nothing; the backup export can't be used, since it answers 500 on that database (What exists). The script prints, for each lamp: its id, its address, its segment count (LEDS), its status, its power and colour as last read, and which SKU table entry it is (1, 2 or none). Keep this in the terminal: it's what Step 3 restores. A lamp whose power or colour is `None` couldn't be read: ask the owner what it showed, and restore that. A lamp that isn't `online`, skip, and tell the owner.

This home has a lamp of the second entry (a strip): play `whole` on it too in Step 3; if it shows the colours, the second entry gets `razer=True` as well (Step 5's first row, the other way round).

- [ ] **Step 3: Play the patterns, one lamp at a time (Owner's go for each lamp)**

For each lamp of the first entry, with the owner watching it, run the patterns in this order, from `$W`, putting in the lamp's address, its LEDS, its colour without the `#`, and `on` or `off` for its power:

```bash
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments LEDS --pattern whole --restore-colour RRGGBB --restore-power on
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments LEDS --pattern ends --restore-colour RRGGBB --restore-power on
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments LEDS --pattern stripes --restore-colour RRGGBB --restore-power on
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments LEDS --pattern chase --restore-colour RRGGBB --restore-power on
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments LEDS --pattern gaps --restore-colour RRGGBB --restore-power on
```

Each prints `restored` at the end. After each, ask the owner:

| pattern | ask |
|---|---|
| `whole` | Did the whole lamp turn red, then green, then blue? (If not, skip the rest for this lamp.) |
| `ends` | Which end was red, the top or the bottom? Was the other end blue? |
| `stripes` | How many bands, red and blue together? |
| `chase` | Did one white band run from the red end to the other, a band at a time, without jumping? |
| `gaps` | Which of red, green, blue and white showed? |
| after each | Is the lamp back as it was? |

If a lamp isn't back as it was, put it back by hand with `--pattern whole` stopped at once (Ctrl-C runs the restore), or ask the owner to set it in the Govee app, and stop.

- [ ] **Step 4: Does a lamp in razer mode answer status queries? (Owner's go: the deployed app stops for about a minute)**

Ruling 15 takes a lamp offline after three missed status reads. If a lamp stops answering while it streams razer, every look would drop it after 15 s, so this is checked on one lamp of the first entry. The `status` pattern binds UDP 4002, which the deployed app holds, so the app stops; Home Assistant retries binding 4002 at about :x8 past each hour, so the stop must be well clear of it:

```bash
date +%M  # go on only if the minute ends in 0 to 4; otherwise wait for the next one
(cd /home/anirudhlath/code/private/dj-ledfx && docker compose stop app)
uv run python scripts/govee_razer_check.py --ip ADDRESS --segments LEDS --pattern status --restore-colour RRGGBB --restore-power on
(cd /home/anirudhlath/code/private/dj-ledfx && docker compose start app)
until curl -sf http://127.0.0.1:8080/api/running >/dev/null; do sleep 1; done
ss -ulne 'sport = :4002'
```

Expected: the script prints `status replies: B/5 before razer, D/A during` and `restored`; after the restart, `ss` shows the socket on `:4002` with `uid:10001`, the app's user (`ss -p` needs root). If `ss` shows another uid, Home Assistant has taken the port: tell the owner at once, since the deployed app can't hear Govee replies until it holds 4002 again.

- [ ] **Step 5: Turn what the owner saw into the table's first entry**

| the owner saw | change (each is a ruling, listed in the PR) |
|---|---|
| `whole`: the lamp didn't follow red, green, blue | Razer doesn't play on that model: `sed -i 's/segment_count=15, razer=True, form="upright"/segment_count=15, form="upright"/' src/dj_ledfx/devices/govee/sku_registry.py`. Those lamps play one colour at 10 a second, and Task 10's route can still set a lamp to segments. In `tests/devices/govee/test_sku_registry.py`, rename `test_the_upright_lamp_takes_razer_and_the_strip_does_not` to `test_neither_entry_takes_razer` and make its first expected tuple `(False, "upright", False)`; in `tests/devices/govee/test_backend.py`'s `test_discover_creates_segment_adapter_for_rgbic`, make the asserts `assert not results[0].adapter.razer  # the first entry plays one colour (Task 8)` and `assert results[0].max_fps == GOVEE_COLOUR_FPS`. |
| `ends`: red at the top | `sed -i 's/razer=True, form="upright")/razer=True, form="upright", segments_from_top=True)/' src/dj_ledfx/devices/govee/sku_registry.py`, and the last value of `test_the_upright_lamp_takes_razer_and_the_strip_does_not`'s first expected tuple becomes `True`. |
| `stripes`: a band count M other than LEDS | The model has M segments: `sed -i 's/segment_count=15, razer=True/segment_count=M, razer=True/' src/dj_ledfx/devices/govee/sku_registry.py`, with the number for M. |
| `chase`: the band jumped about or skipped | Stop. Tell the owner and the coordinator: the lamp's segments aren't in order, and this plan doesn't cover that. |
| `gaps`: blue or white didn't show | The lamp leaves razer mode in a pause of 2 or 3 s: `sed -i 's/^RAZER_IDLE_S = 2.0$/RAZER_IDLE_S = 1.0/' src/dj_ledfx/devices/govee/segment.py`. The tests use the constant. |
| `gaps`: green didn't show | Stop and tell the owner and the coordinator: the lamp leaves razer within 1 s, and ruling 8's keepalive of 1 s can't hold it there. |
| all as expected (red at the bottom, LEDS bands, a smooth chase, all four colours) | Nothing. |

*Note, 2026-10-02:* the owner couldn't count `stripes` by eye. A probe that lit one segment at a time settled the count: index 13 lit the upright lamps' top segment. The strip's index 14 lit its far tip. See ruling 12's note.

- [ ] **Step 6: The fallback ruling, if Step 4 calls for it**

If the lamp answered at least 4 of 5 status queries before razer and fewer than 3 of those asked during it, a razer lamp can't be read while it streams. The ruling: `GoveeSegmentAdapter.read_light` returns `LightReading.UNKNOWN` while razer frames went out within the last `RAZER_IDLE_S`, so a streaming lamp isn't taken offline for its silence, while a lamp that's idle or plays one colour still is. Otherwise skip to Step 7.

In `tests/devices/govee/test_segment.py`, add `from dj_ledfx.devices.capabilities import LightReading, NoAnswer` to the imports and, in `class TestRazer`:

```python
    async def test_a_razer_lamp_streaming_reads_unknown_instead_of_missing(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        now = [100.0]
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True, clock=lambda: now[0])
        mock_transport.query_status = AsyncMock(return_value=None)  # razer mode: no answers
        await adapter.send_frame(np.zeros((3, 3), dtype=np.uint8))
        assert await adapter.read_light() == LightReading.UNKNOWN
        now[0] += RAZER_IDLE_S + 0.1  # the look ended, so the lamp should answer again
        with pytest.raises(NoAnswer):
            await adapter.read_light()
```

Run: `uv run pytest tests/devices/govee/test_segment.py -q`
Expected: the new test fails: `NoAnswer` raised while the lamp streams.

In `src/dj_ledfx/devices/govee/segment.py`, add `from dj_ledfx.devices.capabilities import LightReading` to the imports, and to `GoveeSegmentAdapter`, after `send_frame`:

```python
    async def read_light(self) -> LightReading:
        """As every Govee lamp's, except while razer frames stream: the lamp doesn't answer
        status queries then (the light-output plan's Task 8), so it can't say."""
        last = self._last_frame_at
        if self._razer and last is not None and self._clock() - last <= RAZER_IDLE_S:
            return LightReading.UNKNOWN
        return await super().read_light()
```

Run: `uv run pytest tests/devices/govee -q`
Expected: all pass.

- [ ] **Step 7: Gates and commit, if anything changed**

```bash
git status --short
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/devices/govee tests/devices/govee
git commit -m "fix(govee): what the razer check found on the lamps"
```

With nothing changed, there's no commit. Either way, write the findings down for Task 16's PR body: which patterns played as expected, the status counts, and every ruling Step 5 or Step 6 made.

---

### Task 9: Each lamp's own output, kept in its row and applied by reconnecting it

Ruling 17's storage half. A lamp's own output (`GoveeOutput`) lives under the key `output` in its device row's `extra` column (JSON), which nothing used until now. Backups carry it, and they work again on the deployed database: an unset config value no longer breaks the export (What exists). The Govee backend reads it when it connects known lamps, so a lamp that doesn't answer then takes it when a scan finds it, and `DiscoveryOrchestrator.reconnect()` sets a known light up again from its row at once. A restored backup's outputs apply at the next start.

**Files:**
- Modify: `src/dj_ledfx/devices/govee/output.py`, `src/dj_ledfx/persistence/state_db.py`, `src/dj_ledfx/persistence/toml_io.py`, `src/dj_ledfx/devices/govee/backend.py`, `src/dj_ledfx/devices/discovery.py`
- Test: `tests/devices/govee/test_output.py`, `tests/persistence/test_state_db.py`, `tests/persistence/test_toml_io.py`, `tests/devices/govee/test_backend.py`, `tests/devices/test_discovery.py`

**Interfaces:**
- Consumes: Task 7's `GoveeOutput`, `GoveeMode`, `lamp_plan`, `GoveeBackend._adapter` and `_setup`; Task 6's `MAX_RAZER_SEGMENTS`.
- Produces:
  - `devices/govee/output.py`: `OUTPUT_KEY = "output"`, `MODES: tuple[GoveeMode, ...]`, `MAX_SEGMENTS = MAX_RAZER_SEGMENTS`; `GoveeOutput.from_extra(extra: str | None) -> GoveeOutput` and `GoveeOutput.to_extra() -> dict[str, Any] | None`.
  - `StateDB.load_device(stable_id: str) -> dict[str, Any] | None`; `StateDB.set_device_extra(stable_id: str, key: str, value: Any) -> None` (None removes the key).
  - `DiscoveryOrchestrator.reconnect(stable_id: str) -> bool`: True when the light answered and was promoted (a `DeviceOnlineEvent`); False when it's unknown, has no row, or didn't answer (a `DeviceOfflineEvent` if it was online).
  - Backups: `[devices."<name>"]` gains `extra`, the row's JSON text; an import takes that text or a table. An unset config value is left out of the export, so a database holding one can be backed up.

- [ ] **Step 1: Write the failing output tests**

In `tests/devices/govee/test_output.py`, add at the end:

```python
@pytest.mark.parametrize(
    ("extra", "output"),
    [
        (None, GoveeOutput()),
        ('{"output": {"mode": "colour", "segments": 10}}', GoveeOutput("colour", 10)),
        ('{"output": {"segments": 20}, "other": 1}', GoveeOutput(segments=20)),
        ('{"output": {"mode": "rainbow", "segments": 1}}', GoveeOutput()),
        ('{"output": {"segments": 256}}', GoveeOutput()),
        ('{"output": {"segments": true}}', GoveeOutput()),
        ('{"output": "colour"}', GoveeOutput()),
        ("[1, 2]", GoveeOutput()),
        ("not JSON", GoveeOutput()),
    ],
)
def test_a_stored_output_is_read_as_far_as_it_can_be_used(
    extra: str | None, output: GoveeOutput
) -> None:
    assert GoveeOutput.from_extra(extra) == output


def test_an_output_is_stored_without_its_unset_parts() -> None:
    assert GoveeOutput().to_extra() is None
    assert GoveeOutput(mode="colour").to_extra() == {"mode": "colour"}
    assert GoveeOutput("segments", 10).to_extra() == {"mode": "segments", "segments": 10}
```

Run: `uv run pytest tests/devices/govee/test_output.py -q`
Expected: the new tests fail: `GoveeOutput` has no `from_extra`.

- [ ] **Step 2: Read and write a stored output**

In `src/dj_ledfx/devices/govee/output.py`, make the imports and constants (below `from __future__ import annotations`, which stays):

```python
import json
from dataclasses import dataclass
from typing import Any, Literal, get_args

from dj_ledfx.config import GOVEE_COLOUR_FPS
from dj_ledfx.devices.govee.protocol import MAX_RAZER_SEGMENTS
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

GoveeMode = Literal["segments", "colour"]  # razer, one colour per segment; or colorwc
MODES: tuple[GoveeMode, ...] = get_args(GoveeMode)
OUTPUT_KEY = "output"  # where a lamp's own output sits in its device row's extra (JSON)
MAX_SEGMENTS = MAX_RAZER_SEGMENTS  # razer's limit; one colour keeps to it too


def _segment_count(value: object) -> int | None:
    """A stored segment count a lamp can use, or None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 2 <= value <= MAX_SEGMENTS else None
```

and replace `GoveeOutput` with:

```python
@dataclass(frozen=True, slots=True)
class GoveeOutput:
    """A lamp's own output. None leaves that part to the config and the SKU table."""

    mode: GoveeMode | None = None
    segments: int | None = None

    @classmethod
    def from_extra(cls, extra: str | None) -> GoveeOutput:
        """The output kept in a device row's extra. What it can't use (JSON it can't read,
        a mode or a segment count no lamp plays) is left to the config and the table."""
        try:
            stored = json.loads(extra) if extra else None
        except ValueError:
            return cls()
        output = stored.get(OUTPUT_KEY) if isinstance(stored, dict) else None
        if not isinstance(output, dict):
            return cls()
        mode = output.get("mode")
        return cls(
            mode=mode if mode in MODES else None,
            segments=_segment_count(output.get("segments")),
        )

    def to_extra(self) -> dict[str, Any] | None:
        """What goes under extra's OUTPUT_KEY: None when the lamp has no output of its own."""
        stored = {"mode": self.mode, "segments": self.segments}
        return {key: value for key, value in stored.items() if value is not None} or None
```

Run: `uv run pytest tests/devices/govee/test_output.py -q`
Expected: all pass.

- [ ] **Step 3: Write the failing storage and backup tests**

In `tests/persistence/test_state_db.py`, add `import json` after `import asyncio`, and at the end:

```python
async def test_a_device_row_is_read_by_its_id(db) -> None:
    await db.upsert_device({"id": "govee:test-lamp", "name": "Test lamp", "backend": "govee"})
    row = await db.load_device("govee:test-lamp")
    assert row is not None and (row["name"], row["extra"]) == ("Test lamp", None)
    assert await db.load_device("govee:nobody") is None


async def test_extra_keys_are_set_and_removed_one_at_a_time(db) -> None:
    await db.upsert_device({"id": "govee:test-lamp", "name": "Test lamp", "backend": "govee"})
    await db.set_device_extra("govee:test-lamp", "output", {"mode": "colour"})
    await db.set_device_extra("govee:test-lamp", "other", [1, 2])
    await db.set_device_extra("govee:test-lamp", "output", {"segments": 10})
    row = await db.load_device("govee:test-lamp")
    assert json.loads(row["extra"]) == {"output": {"segments": 10}, "other": [1, 2]}

    await db.set_device_extra("govee:test-lamp", "output", None)

    row = await db.load_device("govee:test-lamp")
    assert json.loads(row["extra"]) == {"other": [1, 2]}


async def test_an_upsert_leaves_extra_alone(db) -> None:
    await db.upsert_device({"id": "govee:test-lamp", "name": "Test lamp", "backend": "govee"})
    await db.set_device_extra("govee:test-lamp", "output", {"mode": "colour"})
    await db.upsert_device(
        {"id": "govee:test-lamp", "name": "Renamed", "backend": "govee", "led_count": 10}
    )
    row = await db.load_device("govee:test-lamp")
    assert row["name"] == "Renamed"
    assert json.loads(row["extra"]) == {"output": {"mode": "colour"}}
```

In `tests/persistence/test_toml_io.py`, add `import tomllib` after `import json`, and at the end:

```python
LAMP_OUTPUT = json.dumps({"output": {"mode": "colour", "segments": 10}})
TABLE_FORM = """
[devices."Test lamp"]
backend = "govee"
device_id = "test-lamp"

[devices."Test lamp".extra.output]
mode = "segments"

[devices."Other lamp"]
backend = "govee"
device_id = "other-lamp"
extra = "not JSON"
"""


@pytest.mark.asyncio
async def test_a_lamp_s_own_output_travels_in_the_backup(db, tmp_path: Path) -> None:
    await db.upsert_device(
        {
            "id": "govee:test-lamp",
            "name": "Test lamp",
            "backend": "govee",
            "device_id": "test-lamp",
            "extra": LAMP_OUTPUT,
        }
    )
    text = await export_toml(db)

    fresh = StateDB(tmp_path / "fresh.db")
    await fresh.open()
    try:
        await import_toml(fresh, text)
        row = await fresh.load_device("govee:test-lamp")
        assert row is not None and json.loads(row["extra"]) == json.loads(LAMP_OUTPUT)

        await import_toml(fresh, TABLE_FORM)  # a hand-edited backup: a table, or bad text

        row = await fresh.load_device("govee:test-lamp")
        assert row is not None and json.loads(row["extra"]) == {"output": {"mode": "segments"}}
        other = await fresh.load_device("govee:other-lamp")
        assert other is not None and other["extra"] is None
    finally:
        await fresh.close()


@pytest.mark.asyncio
async def test_an_unset_config_value_is_left_out_of_the_backup(db: StateDB) -> None:
    await db.save_config_key("web", "static_dir", json.dumps(None))  # as the app saves None
    await db.save_config_key("web", "port", "8080")

    config = tomllib.loads(await export_toml(db))["config"]

    assert config["web"] == {"port": 8080}
```

Run: `uv run pytest tests/persistence -q`
Expected: the new tests fail: `StateDB` has no `load_device` (the two `extra` tests stop first at `set_device_extra`), and the unset-value test fails with `TypeError: Object of type 'NoneType' is not TOML serializable`.

- [ ] **Step 4: One row, one extra key, and the backup**

In `src/dj_ledfx/persistence/state_db.py`, add after `upsert_device`:

```python
    async def load_device(self, stable_id: str) -> dict[str, Any] | None:
        """One device row by its stable id, or None."""
        columns = ", ".join(self._DEVICE_COLUMNS)
        rows = await self._execute_read(f"SELECT {columns} FROM devices WHERE id=?", (stable_id,))
        return dict(zip(self._DEVICE_COLUMNS, rows[0], strict=True)) if rows else None

    async def set_device_extra(self, stable_id: str, key: str, value: Any) -> None:
        """Set one key of a device row's extra, a JSON object, keeping its other keys; None
        removes the key. An upsert without extra leaves it alone."""
        path = f"$.{key}"
        if value is None:
            sql = "UPDATE devices SET extra=json_remove(COALESCE(extra, '{}'), ?) WHERE id=?"
            await self._execute_write(sql, (path, stable_id))
            return
        sql = "UPDATE devices SET extra=json_set(COALESCE(extra, '{}'), ?, json(?)) WHERE id=?"
        await self._execute_write(sql, (path, json.dumps(value), stable_id))
```

In `src/dj_ledfx/persistence/toml_io.py`, in `export_toml`'s device loop, after the `last_latency_ms` lines:

```python
            if device.get("extra"):
                entry["extra"] = device["extra"]  # JSON text: a Govee lamp's own output
```

in `import_toml`'s device loop, after the `last_latency_ms` lines:

```python
        extra = _extra_text(dinfo.get("extra"))
        if extra is not None:
            device_record["extra"] = extra
```

and after `_iso_text`:

```python
def _extra_text(value: object) -> str | None:
    """A device's extra as state.db keeps it, the JSON text of an object, from a backup's
    text or table; None for anything else, which the import leaves out."""
    try:
        data = json.loads(value) if isinstance(value, str) else value
        return json.dumps(data, default=_iso_text) if isinstance(data, dict) else None
    except (TypeError, ValueError):
        return None
```

Add `; extra is JSON text` to the module docstring's `[devices."<name>"]` line, so it reads:

```text
  [devices."<name>"]          — device records keyed by display name; extra is JSON text
```

and in `export_toml`, leave unset config values out, since TOML has no null: the deployed database holds one (`web.static_dir`), and every backup of it fails without this. The loop over `all_config` becomes:

```python
    for (section, key), value in all_config.items():
        if value is None:  # unset (TOML has no null): left out, so it stays unset
            continue
        config_by_section.setdefault(section, {})[key] = value
```

Run: `uv run pytest tests/persistence -q`
Expected: all pass.

- [ ] **Step 5: Write the failing backend and reconnect tests**

In `tests/devices/govee/test_backend.py`, add `import json` to the imports, then replace `_lamp_row` and `_connect` (Task 7's) with:

```python
def _lamp_transport(status: dict[str, Any] | None) -> MagicMock:
    """A transport that hears the lamp (status: its answer, None for silence), and whose
    scans find it."""
    transport = MagicMock()
    transport.is_open = True
    transport.can_receive = True
    transport.query_status = AsyncMock(return_value=status)
    transport.send_command = AsyncMock()

    async def discover(timeout_s: float = 10.0, on_record: Any = None) -> None:
        on_record(
            GoveeDeviceRecord(
                ip="127.0.0.1",
                device_id="test-lamp",
                sku=TEST_MODEL,
                wifi_version="",
                ble_version="",
            )
        )

    transport.discover = discover
    return transport


def _lamp_row(sku: str = TEST_MODEL, output: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "govee:test-lamp",
        "name": "Test lamp",
        "backend": "govee",
        "ip": "127.0.0.1",
        "device_id": "test-lamp",
        "sku": sku,
    }
    if output is not None:
        row["extra"] = json.dumps({"output": output})
    return row


async def _connect(
    config: AppConfig, sku: str = TEST_MODEL, output: dict[str, Any] | None = None
) -> DiscoveredDevice:
    backend = GoveeBackend()
    backend._transport = _lamp_transport({"onOff": 1})
    (device,) = await backend.connect_known([_lamp_row(sku, output)], config)
    return device
```

and add at the end:

```python
UPRIGHT = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")


# Review Focus 5: a lamp whose own output is one colour comes back playing one colour.
async def test_a_lamp_set_to_one_colour_comes_back_in_colour(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    colour = await _connect(config, output={"mode": "colour"})
    assert isinstance(colour.adapter, GoveeSegmentAdapter) and not colour.adapter.razer
    assert colour.max_fps == GOVEE_COLOUR_FPS
    counted = await _connect(config, output={"segments": 10})
    assert isinstance(counted.adapter, GoveeSegmentAdapter) and counted.adapter.razer
    assert counted.adapter.led_count == 10


async def test_a_lamp_offline_at_the_reconnect_gets_its_output_when_a_scan_finds_it(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    backend = GoveeBackend()
    transport = _lamp_transport(None)  # it doesn't answer
    backend._transport = transport
    assert await backend.connect_known([_lamp_row(output={"mode": "colour"})], config) == []

    transport.query_status = AsyncMock(return_value={"onOff": 1})  # it's back
    (device,) = await backend.discover(config)

    assert isinstance(device.adapter, GoveeSegmentAdapter) and not device.adapter.razer
    assert device.max_fps == GOVEE_COLOUR_FPS
```

In `tests/devices/test_discovery.py`, add to the imports, in sorted order: the `conftest` import goes in the third-party group, after `import pytest`, and the events names join the existing `from dj_ledfx.events import EventBus`, which becomes `from dj_ledfx.events import DeviceOfflineEvent, DeviceOnlineEvent, EventBus`:

```python
from conftest import FakeLight

from dj_ledfx.devices.backend import DiscoveredDevice
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.persistence.state_db import StateDB
```

and at the end:

```python
LAMP = "govee:test-lamp"
COLOUR = '{"output": {"mode": "colour"}}'


def _lamp(led_count: int = 15) -> FakeLight:
    caps = DeviceCapabilities(protocol="Govee")
    return FakeLight(LAMP, name="Test lamp", led_count=led_count, caps=caps)


async def _known_lamp(db: StateDB, device_manager: DeviceManager) -> FakeLight:
    lamp = _lamp()
    device_manager.add_device(lamp, _make_tracker())
    await db.upsert_device({"id": LAMP, "name": "Test lamp", "backend": "govee", "extra": COLOUR})
    return lamp


# The light-output plan's ruling 17: a lamp whose output changed is set up again at once.
async def test_a_reconnect_sets_a_known_light_up_again_from_its_row(
    config, device_manager, event_bus, db
) -> None:
    online: list[DeviceOnlineEvent] = []
    event_bus.subscribe(DeviceOnlineEvent, online.append)
    await _known_lamp(db, device_manager)
    new = _lamp(led_count=10)
    backend = _backend([DiscoveredDevice(adapter=new, tracker=_make_tracker(), max_fps=10)])
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [backend]

    assert await orchestrator.reconnect(LAMP) is True

    rows, _ = backend.connect_known.await_args.args
    assert [row["extra"] for row in rows] == [COLOUR]
    managed = device_manager.get_by_stable_id(LAMP)
    assert managed is not None and managed.adapter is new
    assert (managed.max_fps, managed.status) == (10, "online")
    assert [event.stable_id for event in online] == [LAMP]
    row = await db.load_device(LAMP)
    assert row is not None and (row["led_count"], row["extra"]) == (10, COLOUR)


async def test_a_light_that_misses_its_reconnect_goes_offline(
    config, device_manager, event_bus, db
) -> None:
    offline: list[DeviceOfflineEvent] = []
    event_bus.subscribe(DeviceOfflineEvent, offline.append)
    lamp = await _known_lamp(db, device_manager)
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [_backend([])]

    assert await orchestrator.reconnect(LAMP) is False

    assert [event.stable_id for event in offline] == [LAMP]  # main demotes it
    managed = device_manager.get_by_stable_id(LAMP)
    assert managed is not None and managed.adapter is lamp


async def test_only_a_known_light_with_a_row_is_reconnected(
    config, device_manager, event_bus, db
) -> None:
    device_manager.add_device(_lamp(), _make_tracker())  # known, but with no row
    backend = _backend([])
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [backend]

    assert await orchestrator.reconnect(LAMP) is False
    assert await orchestrator.reconnect("govee:nobody") is False
    backend.connect_known.assert_not_awaited()
```

Run: `uv run pytest tests/devices/govee/test_backend.py tests/devices/test_discovery.py -q`
Expected: the new tests fail: the lamps play razer at 30 a second, and the orchestrator has no `reconnect`.

- [ ] **Step 6: The backend reads each lamp's output, and the orchestrator reconnects**

In `src/dj_ledfx/devices/govee/backend.py`:

1. In `__init__`, add `self._outputs: dict[str, GoveeOutput] = {}  # each known lamp's own, by stable id`.
2. In `connect_known`'s loop, after the lines that fall back to the stable id for `device_id`, add:

```python
                # Its own output: for now, and for the scan that finds it if it doesn't
                # answer now (the light-output plan's ruling 17)
                self._outputs[f"govee:{device_id}"] = GoveeOutput.from_extra(row.get("extra"))
```

3. In `_adapter`, replace `plan = lamp_plan(capability, GoveeOutput(), govee.segment_override)` with:

```python
        output = self._outputs.get(f"govee:{record.device_id}", GoveeOutput())
        plan = lamp_plan(capability, output, govee.segment_override)
```

In `src/dj_ledfx/devices/discovery.py`, add `DeviceOfflineEvent` to the `dj_ledfx.events` import, and after `connect_known_devices`:

```python
    async def reconnect(self, stable_id: str) -> bool:
        """Set a known light up again from its row, at once, so that a changed setting (a
        Govee lamp's own output) takes effect: the light-output plan's ruling 17. True when
        it answered. One that doesn't goes offline, and a later scan brings it back."""
        managed = self._manager.get_by_stable_id(stable_id)
        row = await self._state_db.load_device(stable_id) if self._state_db else None
        if managed is None or row is None:
            return False
        found: list[DiscoveredDevice] = []
        for backend in self._backends:
            try:
                found += await backend.connect_known([row], self._config)
            except Exception:
                logger.exception("Reconnecting {} failed in {}", stable_id, type(backend).__name__)
        device = next((d for d in found if d.adapter.device_info.effective_id == stable_id), None)
        name = managed.adapter.device_info.name
        if device is None:
            logger.warning("{} didn't answer when reconnected; it's offline until a scan", name)
            if managed.status == "online":
                self._event_bus.emit(DeviceOfflineEvent(stable_id=stable_id, name=name))
            return False
        self._manager.promote_device(
            stable_id, device.adapter, tracker=device.tracker, max_fps=device.max_fps
        )
        await self._persist_device(device.adapter)
        self._event_bus.emit(DeviceOnlineEvent(stable_id=stable_id, name=name))
        return True
```

Main's handlers do the rest: `DeviceOnlineEvent` re-applies the zone's look to the light (`zone_manager.on_device_online`), with its new LED count and rate, and `DeviceOfflineEvent` demotes it.

Run: `uv run pytest tests/devices tests/persistence -q`
Expected: all pass.

- [ ] **Step 7: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/devices src/dj_ledfx/persistence tests/devices tests/persistence
git commit -m "feat(govee): each lamp's own output, kept in its row and applied by reconnecting it"
```

---

### Task 10: `GET` and `PUT /api/lights/{id}/output`

Rulings 17 and 18, Review Focus 5. The route reads and sets a Govee lamp's own output, then reconnects the lamp so the output applies at once. The discovery orchestrator joins `app.state`, which also makes `POST /api/devices/scan` run a real scan, so scans now take turns. The route is outside the web spec's contract until a design handoff adds it; the web app doesn't change, but its generated types do.

**Files:**
- Modify: `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_lights.py`, `src/dj_ledfx/web/state.py`, `src/dj_ledfx/web/app.py`, `src/dj_ledfx/main.py`, `src/dj_ledfx/devices/discovery.py` (scans take turns), `web/src/api/generated/*` (regenerated)
- Create: `tests/web/test_light_output_api.py`
- Test: `tests/web/test_router_devices.py`, `tests/devices/test_discovery.py`

**Interfaces:**
- Consumes: Task 9's `GoveeOutput.from_extra`/`to_extra`, `OUTPUT_KEY`, `MAX_SEGMENTS`, `StateDB.load_device`, `StateDB.set_device_extra` and `DiscoveryOrchestrator.reconnect`; Task 7's `GoveeMode` and `lamp_plan`.
- Produces:
  - `web/contract.py`: `LampOutputSetting(mode: GoveeMode | None, segments: int | None)` (2 to `MAX_SEGMENTS`); `LampOutput(light_id: str, mode: GoveeMode, segments: int, own: LampOutputSetting, online: bool)`; `lamp_output_out(light_id, sku, own, segment_override, online) -> LampOutput`.
  - `GET /api/lights/{light_id}/output` and `PUT /api/lights/{light_id}/output` (body `LampOutputSetting`) answer `LampOutput`; 404 for a light that isn't a known Govee lamp; 422 for a mode or segment count no lamp plays; 503 without an orchestrator.
  - `web/state.py`: `get_discovery(request) -> DiscoveryOrchestrator`. `create_app(..., discovery_orchestrator: DiscoveryOrchestrator | None = None)`.
  - `DiscoveryOrchestrator.run_scan()` holds a lock: a scan asked for while one runs waits for it.

- [ ] **Step 1: Write the failing API tests**

Create `tests/web/test_light_output_api.py`:

```python
"""GET and PUT /api/lights/{id}/output: a Govee lamp's own output (the light-output plan's
ruling 17)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

LAMP = "govee:test-lamp"
OUTPUT = f"/api/lights/{LAMP}/output"
UPRIGHT = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")


@pytest.fixture(autouse=True)
def _test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SKU_REGISTRY, "test-model", UPRIGHT)


class FakeDiscovery:
    """Stands in for the discovery orchestrator: each reconnect gets `answer`."""

    def __init__(self, answer: bool = True) -> None:
        self.answer = answer
        self.reconnected: list[str] = []

    async def reconnect(self, stable_id: str) -> bool:
        self.reconnected.append(stable_id)
        return self.answer


@asynccontextmanager
async def _lamp_api(tmp_path: Path, discovery: FakeDiscovery) -> AsyncIterator[Api]:
    caps = DeviceCapabilities(protocol="Govee")
    lamp = FakeLight(LAMP, name="Test lamp", led_count=15, caps=caps)
    async with api_home(tmp_path, [lamp], []) as api:
        await api.home.db.upsert_device(
            {
                "id": LAMP,
                "name": "Test lamp",
                "backend": "govee",
                "ip": "127.0.0.1",
                "device_id": "test-lamp",
                "sku": "test-model",
            }
        )
        api.app.state.discovery_orchestrator = discovery
        yield api


async def _extra(api: Api, light_id: str = LAMP) -> Any:
    row = await api.home.db.load_device(light_id)
    assert row is not None
    return json.loads(row["extra"]) if row["extra"] is not None else None


async def test_a_lamp_plays_its_model_s_output_until_it_has_its_own(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery()) as api:
        answer = await api.client.get(OUTPUT)
    assert answer.status_code == 200
    assert answer.json() == {
        "lightId": LAMP,
        "mode": "segments",
        "segments": 15,
        "own": {"mode": None, "segments": None},
        "online": True,
    }


# Review Focus 5: a lamp that ignores razer can be set to one colour, which applies at once.
async def test_a_lamp_that_ignores_razer_can_be_switched_to_one_colour(tmp_path: Path) -> None:
    discovery = FakeDiscovery()
    async with _lamp_api(tmp_path, discovery) as api:
        answer = await api.client.put(OUTPUT, json={"mode": "colour"})
        stored = await _extra(api)
        again = await api.client.get(OUTPUT)
    assert answer.status_code == 200
    assert (answer.json()["mode"], answer.json()["segments"]) == ("colour", 15)
    assert answer.json()["own"] == {"mode": "colour", "segments": None}
    assert discovery.reconnected == [LAMP]  # at once
    assert stored == {"output": {"mode": "colour"}}
    assert again.json() == answer.json()


async def test_a_segment_count_is_set_then_given_back_to_the_model(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery()) as api:
        counted = await api.client.put(OUTPUT, json={"segments": 10})
        reset = await api.client.put(OUTPUT, json={})
        stored = await _extra(api)
    assert (counted.json()["mode"], counted.json()["segments"]) == ("segments", 10)
    assert counted.json()["own"] == {"mode": None, "segments": 10}
    assert reset.json()["segments"] == 15
    assert reset.json()["own"] == {"mode": None, "segments": None}
    assert stored == {}


async def test_a_lamp_that_misses_the_reconnect_says_so_and_keeps_its_output(
    tmp_path: Path,
) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery(answer=False)) as api:
        answer = await api.client.put(OUTPUT, json={"mode": "colour"})
        stored = await _extra(api)
    assert answer.status_code == 200 and answer.json()["online"] is False
    assert stored == {"output": {"mode": "colour"}}  # for the scan that finds it


async def test_only_a_known_govee_lamp_has_an_output(tmp_path: Path) -> None:
    async with _lamp_api(tmp_path, FakeDiscovery()) as api:
        await api.home.db.upsert_device(
            {"id": "lifx:test", "name": "Test bulb", "backend": "lifx"}
        )
        unknown = await api.client.get("/api/lights/govee:nobody/output")
        bulb = await api.client.put("/api/lights/lifx:test/output", json={"mode": "colour"})
    assert (unknown.status_code, bulb.status_code) == (404, 404)
    assert bulb.json()["detail"] == "No Govee lamp 'lifx:test'"


@pytest.mark.parametrize("body", [{"segments": 1}, {"segments": 256}, {"mode": "rainbow"}])
async def test_an_output_no_lamp_plays_is_refused(tmp_path: Path, body: dict[str, Any]) -> None:
    discovery = FakeDiscovery()
    async with _lamp_api(tmp_path, discovery) as api:
        answer = await api.client.put(OUTPUT, json=body)
        stored = await _extra(api)
    assert answer.status_code == 422
    assert (discovery.reconnected, stored) == ([], None)
```

In `tests/web/test_router_devices.py`'s `test_scan_endpoint_with_orchestrator`, pass the orchestrator to `create_app` instead of setting `app.state` (ruling 18):

```python
    app = create_app(
        **mock_deps(
            device_manager=manager, scheduler=scheduler, discovery_orchestrator=mock_orchestrator
        )
    )
```

and delete the line `app.state.discovery_orchestrator = mock_orchestrator`.

With the route, `POST /api/devices/scan` runs a real scan beside the 30 s loop's, and a Govee scan has one reply handler, so two at once would cut each other short: scans take turns. In `tests/devices/test_discovery.py`, add `import asyncio` before `from unittest.mock import AsyncMock, MagicMock`, and at the end:

```python
@pytest.mark.asyncio
async def test_scans_take_turns(config, device_manager, event_bus):
    """A scan asked for while one runs waits for it (POST /api/devices/scan beside the loop)."""
    orchestrator = DiscoveryOrchestrator(
        config=config, device_manager=device_manager, event_bus=event_bus
    )
    running = most = 0

    async def discover(*args: object, **kwargs: object) -> None:
        nonlocal running, most
        running += 1
        most = max(most, running)
        await asyncio.sleep(0.01)
        running -= 1

    backend = MagicMock()
    backend.discover = discover
    orchestrator._backends = [backend]

    await asyncio.gather(orchestrator.run_scan(), orchestrator.run_scan())

    assert most == 1
```

Run: `uv run pytest tests/web/test_light_output_api.py tests/web/test_router_devices.py tests/devices/test_discovery.py -q`
Expected: the output tests fail, every request answering 404 (there's no route yet), `test_only_a_known_govee_lamp_has_an_output` on its `detail` (`Not Found`); the scan test fails: `create_app` takes no `discovery_orchestrator`; and `test_scans_take_turns` fails on `assert 2 == 1`.

- [ ] **Step 2: The contract, the routes and the wiring**

In `src/dj_ledfx/web/contract.py`, add to the imports:

```python
from dj_ledfx.devices.govee.output import MAX_SEGMENTS, GoveeMode, GoveeOutput, lamp_plan
from dj_ledfx.devices.govee.sku_registry import get_device_capability
```

and after `LightUpdate`:

```python
class LampOutputSetting(ContractModel):
    """A Govee lamp's own output (the light-output plan's ruling 17; outside the web spec
    until a design handoff adds it): razer segments or one colour, and its segment count.
    Null leaves either to the config and the lamp's model."""

    mode: GoveeMode | None = None
    segments: int | None = Field(None, ge=2, le=MAX_SEGMENTS)


class LampOutput(ContractModel):
    """How a Govee lamp plays now, and its own setting."""

    light_id: str
    mode: GoveeMode
    segments: int  # 1: one colour, with no segments to light
    own: LampOutputSetting
    online: bool  # false: it didn't answer, and takes its output when a scan finds it


def lamp_output_out(
    light_id: str, sku: str, own: GoveeOutput, segment_override: int | None, online: bool
) -> LampOutput:
    plan = lamp_plan(get_device_capability(sku), own, segment_override)
    return LampOutput(
        light_id=light_id,
        mode="segments" if plan.razer else "colour",
        segments=plan.segments,
        own=LampOutputSetting(mode=own.mode, segments=own.segments),
        online=online,
    )
```

In `src/dj_ledfx/web/state.py`, add `from dj_ledfx.devices.discovery import DiscoveryOrchestrator` to the `TYPE_CHECKING` imports, and after `get_previews`:

```python
def get_discovery(request: Request) -> DiscoveryOrchestrator:
    return cast("DiscoveryOrchestrator", _required(request, "discovery_orchestrator", "Scans"))
```

In `src/dj_ledfx/web/app.py`, add `from dj_ledfx.devices.discovery import DiscoveryOrchestrator` to the `TYPE_CHECKING` imports, the parameter `discovery_orchestrator: DiscoveryOrchestrator | None = None,` after `listening`, and after `app.state.listening = listening`:

```python
    app.state.discovery_orchestrator = discovery_orchestrator  # scans and reconnects
```

Replace `src/dj_ledfx/web/router_lights.py` with:

```python
"""Lights with their status (web spec §9.1, §12.2): the PC is one light with parts (spec
§6.3). A Govee lamp's own output is here too (the light-output plan's ruling 17). Device
actions stay on /api/devices."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.devices.govee.output import OUTPUT_KEY, GoveeOutput
from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_db, get_discovery, get_light_monitor, light_index

router = APIRouter()


@router.get("/lights")
async def list_lights(request: Request) -> list[api.Light]:
    monitor = get_light_monitor(request)
    monitor.refresh()  # picks up lights found since the last poll
    devices = request.app.state.device_manager
    stats = {entry.device_id: entry for entry in request.app.state.scheduler.get_device_stats()}
    index = light_index(request.app)
    home_map = request.app.state.home_map
    states = {state.device_id: state for state in monitor.light_states(index)}
    lights: list[api.Light] = []
    for entry in index.entries:
        state = states.get(entry.id)
        parts = [m for d in entry.devices if (m := devices.get_by_stable_id(d)) is not None]
        if state is None or not parts:
            continue
        lights.append(api.light_out(entry, parts, state, stats, home_map=home_map))
    return lights


@router.get("/lights/{light_id}/output")
async def get_lamp_output(request: Request, light_id: str) -> api.LampOutput:
    """A Govee lamp's output: how it plays now (razer segments or one colour, and how many
    segments), and its own setting, which the config and its model fill in."""
    row = await _lamp_row(request, light_id)
    managed = request.app.state.device_manager.get_by_stable_id(light_id)
    online = managed is not None and managed.status == "online"
    return _lamp_output(request, row, GoveeOutput.from_extra(row.get("extra")), online)


@router.put("/lights/{light_id}/output")
async def set_lamp_output(
    request: Request, light_id: str, body: api.LampOutputSetting
) -> api.LampOutput:
    """Set a Govee lamp's own output; a field left null goes back to the default. The lamp
    is reconnected at once to take it. One that doesn't answer goes offline (online is
    false) and takes the output when a scan finds it."""
    discovery = get_discovery(request)
    row = await _lamp_row(request, light_id)
    own = GoveeOutput(mode=body.mode, segments=body.segments)
    await get_db(request).set_device_extra(light_id, OUTPUT_KEY, own.to_extra())
    online = await discovery.reconnect(light_id)
    return _lamp_output(request, row, own, online)


async def _lamp_row(request: Request, light_id: str) -> dict[str, Any]:
    row = await get_db(request).load_device(light_id)
    if row is None or row.get("backend") != "govee":
        raise HTTPException(404, f"No Govee lamp '{light_id}'")
    return row


def _lamp_output(
    request: Request, row: dict[str, Any], own: GoveeOutput, online: bool
) -> api.LampOutput:
    override = request.app.state.config.devices.govee.segment_override
    return api.lamp_output_out(row["id"], row.get("sku") or "", own, override, online)
```

In `src/dj_ledfx/main.py`, pass the orchestrator to `create_app`: add `discovery_orchestrator=discovery_orchestrator,` after `listening=listening,`.

In `src/dj_ledfx/devices/discovery.py`, scans take turns. In `DiscoveryOrchestrator.__init__`, after `self._task: asyncio.Task[None] | None = None`:

```python
        # One scan at a time: a Govee scan has one reply handler, so two at once would cut
        # each other short (POST /api/devices/scan beside the loop)
        self._scan_lock = asyncio.Lock()
```

and in `run_scan`, the gather runs under it:

```python
        async with self._scan_lock:
            results = await asyncio.gather(
                *(self._discover_backend(b) for b in self._backends),
                return_exceptions=True,
            )
```

Run: `uv run pytest tests/web/test_light_output_api.py tests/web/test_router_devices.py tests/devices/test_discovery.py -q`
Expected: all pass.

- [ ] **Step 3: Regenerate the web app's API types**

```bash
(cd web && npm run api:types)
git status --short web/src/api/generated
uv run pytest tests/web/test_openapi_types.py -q
```

Expected: the generated schema and types change (the two routes and the two models), and the test passes.

- [ ] **Step 4: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/web src/dj_ledfx/main.py src/dj_ledfx/devices/discovery.py web/src/api/generated tests/web tests/devices/test_discovery.py
git commit -m "feat(api): GET and PUT /api/lights/{id}/output for a Govee lamp"
```

---

### Task 11: Placements fitted to each light's form

Cause 7's first half, ruling 19. An unconfirmed placement that hides its light's form (many LEDs on a point, an upright lamp lying down) is fitted again when the light is online: an upright lamp stands as a vertical line from 0.1 m, a strip lies along its length, a matrix stands as a grid the size of its tiles. Guesses for new lights come out in form too. Confirmed placements, offline lights, one-LED lights, forms nobody knows and the PC are left alone.

**Files:**
- Modify: `src/dj_ledfx/home/guess.py`, `src/dj_ledfx/home/map.py`, `src/dj_ledfx/main.py`
- Test: `tests/home/test_guess.py`, `tests/home/test_map.py`

**Interfaces:**
- Consumes: the adapters' `geometry`: Task 6's upright lamps `StripGeometry((0, ±1, 0), UPRIGHT_HEIGHT_M)` and strips `StripGeometry((1, 0, 0), length)`; LIFX matrices' `MatrixGeometry` (unchanged). `StripGeometry.direction` is in the scene's axes (y up); `_to_map` turns it into the map's (x east, y south, z up).
- Produces:
  - `home/guess.py`: `UPRIGHT_BASE_M = 0.1`, `UPRIGHT_GRID = (0.0, -90.0, 0.0)`; `placed_in_form(at: Vec3, leds: int, geometry: DeviceGeometry | None) -> Placement`; `in_form(shape: LightShape, leds: int, geometry: DeviceGeometry | None) -> bool`; `guess_placements(..., geometry_of: Callable[[LightEntry], DeviceGeometry | None] = ...)`.
  - `HomeMap.refit() -> dict[str, Placement]`: the placements it changed, saved, with the listeners told once.

- [ ] **Step 1: Write the failing guess tests**

In `tests/home/test_guess.py`, add to the imports:

```python
from dj_ledfx.home.guess import UPRIGHT_BASE_M, in_form, placed_in_form
from dj_ledfx.home.shapes import led_positions
from dj_ledfx.spatial.geometry import MatrixGeometry, PointGeometry, StripGeometry, TileLayout
```

merged into the existing imports, one name per line as ruff formats them: `from dj_ledfx.home.guess import (GUESS_HEIGHT_M, SPREAD_RADIUS_M, UPRIGHT_BASE_M, first_placements, guess_placements, in_form, largest_room, moved_scene_placements, placed_in_form, seed_matches)` and `from dj_ledfx.home.shapes import (CylinderShape, GridShape, LineShape, Placement, PointShape, led_positions)`; and at the end:

```python
UP = StripGeometry((0.0, 1.0, 0.0), 1.4)  # an upright lamp, its first LED at the bottom
DOWN = StripGeometry((0.0, -1.0, 0.0), 1.4)  # its first LED at the top
ALONG = StripGeometry((1.0, 0.0, 0.0), 1.0)  # a strip, running east
TILE = MatrixGeometry((TileLayout(0.0, 0.0, 5, 6),), pixel_pitch=0.03)
AT = (2.0, 2.0, 1.0)


def _many(light_id: str, leds: int) -> LightEntry:
    return LightEntry(
        light_id, light_id, (light_id,), leds, (LightPart(light_id, light_id, leds),)
    )


def test_an_upright_lamp_stands_on_the_floor_below_its_spot() -> None:
    top = UPRIGHT_BASE_M + 1.4
    up = placed_in_form(AT, 15, UP)
    assert up == Placement(LineShape(((2.0, 2.0, UPRIGHT_BASE_M), (2.0, 2.0, top))), "along-path")
    assert placed_in_form(AT, 15, DOWN).led_order == "reverse-path"
    assert not up.confirmed


def test_a_strip_lies_through_its_spot_along_its_length() -> None:
    strip = placed_in_form(AT, 30, ALONG)
    assert strip == Placement(LineShape(((1.5, 2.0, 1.0), (2.5, 2.0, 1.0))), "along-path")


def test_a_matrix_stands_as_a_grid_with_its_first_row_at_the_top() -> None:
    matrix = placed_in_form(AT, 30, TILE)
    assert isinstance(matrix.shape, GridShape) and matrix.led_order == "rows"
    assert (matrix.shape.width, matrix.shape.depth) == pytest.approx((0.15, 0.18))
    leds = led_positions(matrix.shape, 30, matrix.led_order).pos
    assert leds[0][2] > leds[-1][2]  # LED 1 on top, as a matrix's own frame has it
    assert np.allclose(leds[:, 1], AT[1])  # standing: every LED at one depth


def test_a_light_of_one_led_or_of_no_known_form_is_a_point() -> None:
    for leds, geometry in ((1, UP), (15, None), (15, PointGeometry())):
        assert placed_in_form(AT, leds, geometry) == Placement(PointShape(AT), "")


def test_only_many_leds_on_a_point_or_an_upright_lamp_lying_down_hide_a_form() -> None:
    point = PointShape(AT)
    lying = LineShape(((1.0, 2.0, 1.0), (2.4, 2.0, 1.0)))
    standing = LineShape(((2.0, 2.0, 0.1), (2.0, 2.0, 1.5)))
    assert not in_form(point, 15, UP) and not in_form(point, 30, TILE)
    assert not in_form(lying, 15, UP) and in_form(standing, 15, UP)
    assert in_form(lying, 30, ALONG) and in_form(point, 1, UP) and in_form(point, 15, None)


def test_a_guess_puts_each_loose_light_in_its_form() -> None:
    guesses = guess_placements(
        tiny_home(),
        [_many("lamp", 15), _light("bulb")],
        set(),
        [],
        geometry_of=lambda light: UP if light.id == "lamp" else None,
    )
    lamp = guesses["lamp"].shape
    assert isinstance(lamp, LineShape) and lamp.path[0][2] == UPRIGHT_BASE_M
    assert isinstance(guesses["bulb"].shape, PointShape)
```

`test_guess.py` needs `import numpy as np` too, in the third-party group before `import pytest` (a blank line after `import math`).

Run: `uv run pytest tests/home/test_guess.py -q`
Expected: an import error for `UPRIGHT_BASE_M`.

- [ ] **Step 2: Placements in form**

In `src/dj_ledfx/home/guess.py`, add `BentLineShape` to the `dj_ledfx.home.shapes` import and `from dj_ledfx.spatial.geometry import DeviceGeometry, MatrixGeometry, StripGeometry` to the imports; under `STANDING`:

```python
UPRIGHT_BASE_M = 0.1  # an upright lamp's LEDs start this far off the floor
# A grid stood up with its first row at the top, as a matrix's own frame has it.
UPRIGHT_GRID = (0.0, -90.0, 0.0)
```

after `_vec`:

```python
def _rise(geometry: StripGeometry) -> float:
    """How far up the map a strip runs per metre along it: near ±1 for an upright lamp."""
    return float(_to_map(geometry.direction)[2])


def _matrix_size(geometry: MatrixGeometry) -> tuple[float, float]:
    """The width and height the matrix's tiles cover, in metres."""
    pitch = geometry.pixel_pitch
    left = min(tile.offset_x for tile in geometry.tiles)
    right = max(tile.offset_x + tile.width * pitch for tile in geometry.tiles)
    top = min(tile.offset_y for tile in geometry.tiles)
    bottom = max(tile.offset_y + tile.height * pitch for tile in geometry.tiles)
    return right - left, bottom - top


def placed_in_form(at: Vec3, leds: int, geometry: DeviceGeometry | None) -> Placement:
    """An unconfirmed placement at `at` that shows the light's form (the light-output plan's
    ruling 19). An upright lamp stands on the floor below `at`, a vertical line as long as
    its geometry; a strip lies through `at` along its direction; a matrix stands at `at` as
    a grid of its tiles' size, first row at the top (a chain of tiles is one grid, in rows).
    A light of one LED, or of no known form, is a point."""
    if leds > 1 and isinstance(geometry, StripGeometry):
        x, y, _ = at
        if abs(_rise(geometry)) > 0.9:
            path = ((x, y, UPRIGHT_BASE_M), (x, y, UPRIGHT_BASE_M + geometry.length))
            order = "along-path" if _rise(geometry) > 0 else "reverse-path"
            return Placement(LineShape(path), order)
        half = _to_map(geometry.direction) * geometry.length / 2.0
        centre = np.asarray(at, dtype=np.float64)
        return Placement(LineShape((_vec(centre - half), _vec(centre + half))), "along-path")
    if leds > 1 and isinstance(geometry, MatrixGeometry) and geometry.tiles:
        width, height = _matrix_size(geometry)
        return Placement(GridShape(at, width, height, UPRIGHT_GRID), "rows")
    return Placement(PointShape(at), check_led_order("point", None))


def in_form(shape: LightShape, leds: int, geometry: DeviceGeometry | None) -> bool:
    """Whether a placement shows the light's form. Two things hide it: many LEDs on a
    point, and an upright lamp lying down. A light of one LED, or of no known form, is
    always in form."""
    if leds <= 1 or not isinstance(geometry, StripGeometry | MatrixGeometry):
        return True
    if isinstance(shape, PointShape):
        return False
    if isinstance(geometry, StripGeometry) and abs(_rise(geometry)) > 0.9:
        if isinstance(shape, LineShape | BentLineShape):
            path = np.asarray(shape.path, dtype=np.float64)
            height = float(path[:, 2].max() - path[:, 2].min())
            spread = float(np.linalg.norm(path[:, :2].max(axis=0) - path[:, :2].min(axis=0)))
            return height >= spread
    return True
```

and replace `guess_placements` with:

```python
def _no_form(light: LightEntry) -> DeviceGeometry | None:
    return None


def guess_placements(
    home: Home,
    lights: Sequence[LightEntry],
    placed: Collection[str],
    seeds: Sequence[SeedLight],
    geometry_of: Callable[[LightEntry], DeviceGeometry | None] = _no_form,
) -> dict[str, Placement]:
    """A guess for each light not in `placed`: its seed's placement, or a spot round the
    largest room, in the light's form there (geometry_of gives a light's geometry)."""
    matches = seed_matches(lights, seeds)
    guesses: dict[str, Placement] = {}
    loose: list[LightEntry] = []
    for light in lights:
        if light.id in placed:
            continue
        seed = matches.get(light.id)
        if seed is not None:
            guesses[light.id] = seed.placement
        else:
            loose.append(light)
    for light, point in zip(loose, _spread(home, len(loose)), strict=True):
        guesses[light.id] = placed_in_form(point, light.leds, geometry_of(light))
    return guesses
```

Run: `uv run pytest tests/home/test_guess.py -q`
Expected: all pass, the old tests too: with no geometry, a loose light is the point it was.

- [ ] **Step 3: Write the failing map tests**

In `tests/home/test_map.py`, add `from map_home import DESK_CORNER, devices_of, open_map, tiny_home` (in place of the `map_home` import) and `from dj_ledfx.spatial.geometry import MatrixGeometry, StripGeometry, TileLayout`, and at the end:

```python
UPRIGHT_LAMP = StripGeometry((0.0, 1.0, 0.0), 1.4)
SMALL_MATRIX = MatrixGeometry((TileLayout(0.0, 0.0, 5, 6),), pixel_pitch=0.03)
ON_THE_DESK = Placement(PointShape(DESK_CORNER), "")


async def test_online_lights_on_points_are_fitted_to_their_forms(db: StateDB) -> None:
    lamp = FakeLight("lamp", led_count=15, geometry=UPRIGHT_LAMP)
    matrix = FakeLight("matrix", led_count=30, geometry=SMALL_MATRIX)
    placements = {"lamp": ON_THE_DESK, "matrix": ON_THE_DESK}
    home_map = await _map(db, [lamp, matrix], placements=placements, seeded=True)
    changes: list[str] = []

    async def changed() -> None:
        changes.append("map")

    home_map.on_change(changed)

    fitted = await home_map.refit()

    lamp_shape = fitted["lamp"].shape
    assert isinstance(lamp_shape, LineShape) and not fitted["lamp"].confirmed
    (x0, y0, z0), (x1, y1, z1) = lamp_shape.path
    assert (x0, y0) == (x1, y1) == DESK_CORNER[:2] and z0 < z1
    assert isinstance(fitted["matrix"].shape, GridShape)
    assert dict(home_map.placements) == fitted
    assert await HomeStore(db).load_placements() == fitted
    assert changes == ["map"]  # told once
    assert await home_map.refit() == {}  # they fit now


async def test_confirmed_offline_fitting_one_led_and_pc_placements_are_left_alone(
    db: StateDB,
) -> None:
    lights = [
        FakeLight("standing", led_count=15, geometry=UPRIGHT_LAMP),
        FakeLight("confirmed", led_count=15, geometry=UPRIGHT_LAMP),
        FakeLight("offline", led_count=15, geometry=UPRIGHT_LAMP),
        FakeLight("bulb", led_count=1),
        *pc_lights(*KEYBOARD_AND_MOUSE),
    ]
    devices = devices_of(lights)
    devices.demote_device("offline")
    standing = Placement(LineShape(((1.0, 3.5, 0.1), (1.0, 3.5, 1.5))), "along-path")
    placements = {
        "standing": standing,
        "confirmed": Placement(PointShape(DESK_CORNER), "", confirmed=True),
        "offline": ON_THE_DESK,
        "bulb": ON_THE_DESK,
        SERVER: ON_THE_DESK,
    }
    home_map = await _map(db, devices, placements=placements, seeded=True)

    assert await home_map.refit() == {}
    assert dict(home_map.placements) == placements


async def test_a_guess_places_a_light_in_its_form(db: StateDB) -> None:
    lamp = FakeLight("lamp", led_count=15, geometry=UPRIGHT_LAMP)
    home_map = await _map(db, [lamp], seeded=True)

    guesses = await home_map.guess()

    assert isinstance(guesses["lamp"].shape, LineShape)
```

Run: `uv run pytest tests/home/test_map.py -q`
Expected: the new tests fail: `HomeMap` has no `refit`, and the guess is a point.

- [ ] **Step 4: The map fits placements**

In `src/dj_ledfx/home/map.py`, make the imports:

```python
from dj_ledfx.devices.lights import LightEntry, LightIndex
```

```python
from dj_ledfx.home.guess import (
    GUESS_HEIGHT_M,
    first_placements,
    guess_placements,
    in_form,
    placed_in_form,
)
```

and `from dj_ledfx.spatial.geometry import DeviceGeometry`. In `guess()`, pass the lights' geometry:

```python
            guesses = guess_placements(
                self._home,
                self.lights().entries,
                set(self._placements),
                self._seeds(),
                geometry_of=self._geometry,
            )
```

Add after `guess()`:

```python
    async def refit(self) -> dict[str, Placement]:
        """Fit each online light's unconfirmed placement to its form where it hides it
        (the light-output plan's ruling 19): many LEDs on a point, an upright lamp lying
        down. Confirmed placements, offline lights, forms nobody knows and the PC are left
        alone. Returns the placements it changed."""
        fitted: dict[str, Placement] = {}
        async with self._lock:
            for light in self.lights().entries:
                old = self._placements.get(light.id)
                geometry = self._geometry(light)
                if old is None or old.confirmed or in_form(old.shape, light.leds, geometry):
                    continue
                placement = placed_in_form(shape_centre(old.shape), light.leds, geometry)
                await self._store.save_placement(light.id, placement)
                self._placements[light.id] = placement
                fitted[light.id] = placement
        if fitted:
            logger.info("Fitted {} placement(s) to their lights' forms", len(fitted))
            await self._changed()
        return fitted
```

and among the internals:

```python
    def _geometry(self, light: LightEntry) -> DeviceGeometry | None:
        """An online light's geometry: what form it has. None for the PC, whose parts are
        placed by hand, and for a light that's offline."""
        if light.is_pc:
            return None
        managed = self._devices.get_by_stable_id(light.id)
        if managed is None or managed.status != "online":
            return None
        return managed.adapter.geometry
```

`in_form` returns True for a geometry of None, so the PC and offline lights are skipped by it.

In `src/dj_ledfx/main.py`, refit when a light comes online: before `def _on_device_back`, add

```python
    async def _fit_placements() -> None:
        await home_map.refit()  # a light back online shows its form (ruling 19)
```

and at the end of `_on_device_back`, after `light_monitor.refresh()`, add `_spawn(_fit_placements())`. At start-up, `connect_known_devices` brings the known lights online, so the first start with this code fits every placement that hides its light's form.

Run: `uv run pytest tests/home tests/test_main.py -q`
Expected: all pass.

- [ ] **Step 5: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/home src/dj_ledfx/main.py tests/home
git commit -m "fix(home): fit unconfirmed placements to each light's form"
```

---

### Task 12: Aurora's curtains reach the floor

Rulings O1 and 20. Aurora's band becomes the room's whole height, so lights at every height join in. A curtain still fades in from the band's foot to its middle, so the lowest lights glow dimly. The copy in `looks.json` changes to match, in the handoff's file and its byte copies, under O1.

**Files:**
- Modify: `src/dj_ledfx/effects/aurora_curtains.py`
- Modify: `docs/design/web-app/looks.json`, `docs/design/web-app/HANDOFF.sha256` (its `looks.json` line), `src/dj_ledfx/looks/data/looks.json` and `web/src/api/mocks/looks.json` (the byte copies), `docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md` (the prompt the design was made from)
- Test: `tests/effects/test_aurora_curtains.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `DEFAULT_BAND = (0.0, 1.0)` in `effects/aurora_curtains.py`.

- [ ] **Step 1: Write the failing test**

In `tests/effects/test_aurora_curtains.py`, replace `test_the_curtains_hang_near_the_ceiling` with:

```python
def test_the_curtains_reach_down_to_the_floor() -> None:
    frame = AuroraCurtains().render(render_ctx(t=100.0), leds_at(LOW_AND_HIGH))

    assert 0.0 < frame[0].max() < frame[1].max()  # dim low in the room, brighter up high
```

Run: `uv run pytest tests/effects/test_aurora_curtains.py -q`
Expected: 1 failed, 2 passed. The new test fails on `0.0 < 0.0`: the LED 0.3 m up is below the old band, so it's dark.

- [ ] **Step 2: Lower the band**

In `src/dj_ledfx/effects/aurora_curtains.py`, the module docstring becomes:

```python
"""Aurora's field (looks.json "aurora"): curtains that hang from the ceiling to the floor.

Folds run across the room and wander with seeded 3D noise; the colour climbs the palette
with height, green low in the curtain to violet at its top. A curtain fades in from the
band's foot to its middle, so the lights lowest in the room glow dimly.
"""
```

and `DEFAULT_BAND`:

```python
DEFAULT_BAND = (0.0, 1.0)  # floor to ceiling (the owner's ruling O1, light-output plan)
```

Run: `uv run pytest tests/effects/test_aurora_curtains.py tests/looks -q`
Expected: all pass. Nothing else pins the band: `test_the_band_says_where_they_hang` sets its own, and no look stores one.

- [ ] **Step 3: Change the copy, under O1**

The handoff's `looks.json` and its two byte copies change together, so they stay equal, and so does the prompt the design was made from. Only the phrase changes:

```bash
sed -i 's/curtains drift near the ceiling/curtains hang from the ceiling to the floor/' \
  docs/design/web-app/looks.json src/dj_ledfx/looks/data/looks.json \
  web/src/api/mocks/looks.json docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md
sum=$(sha256sum docs/design/web-app/looks.json | cut -d' ' -f1)
sed -i "s/^[0-9a-f]\{64\}  looks.json$/$sum  looks.json/" docs/design/web-app/HANDOFF.sha256
grep -c 'curtains hang from the ceiling to the floor' docs/design/web-app/looks.json \
  src/dj_ledfx/looks/data/looks.json web/src/api/mocks/looks.json \
  docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md
cmp docs/design/web-app/looks.json src/dj_ledfx/looks/data/looks.json \
  && cmp docs/design/web-app/looks.json web/src/api/mocks/looks.json && echo "copies equal"
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256 | grep -v ': OK$' || echo "all pins OK")
git diff --stat
```

Expected: each of the four files `:1`, then `copies equal` and `all pins OK`; `git diff --stat` lists those four files with one line changed each, `HANDOFF.sha256` with one, and Steps 1–2's two files.

- [ ] **Step 4: Run the copies' tests**

```bash
uv run pytest tests/looks/test_builtin.py tests/effects -q
(cd web && npx vitest run src/design/payload.node.test.ts src/api/mocks/fixtures.test.ts)
```

Expected: all pass. `test_vendored_looks_json_is_a_byte_copy_of_the_handoff` and the web app's payload test check the copies and the pin.

- [ ] **Step 5: Gates and commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/effects/aurora_curtains.py tests/effects/test_aurora_curtains.py \
  docs/design/web-app/looks.json docs/design/web-app/HANDOFF.sha256 \
  src/dj_ledfx/looks/data/looks.json web/src/api/mocks/looks.json \
  docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md
git commit -m "fix(effects): Aurora's curtains reach the floor"
```

Tell the owner (ruling 20): the Claude Design project still has the old copy, and the next handoff brings it back unless it changes there too.

---

### Task 13: The specs say what the fixes do

Rulings O1–O3 and 1–22. The brief asks for the specs' text to match the owner's rulings, and the engine spec's §3, §4.1, §4.3, §6.1, §6.3 and §8 describe what this plan changes. The Govee spec was written when `ptReal` was the plan and razer was out of scope, so its decisions table, file layout, components, error handling and future extensions change too; its `ptReal` sections stay as the record, marked. The engine spec's §6.6 is left alone.

**Files:**
- Modify: `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`, `docs/superpowers/specs/2026-03-13-govee-lan-protocol-design.md`

**Interfaces:**
- Consumes: the names Tasks 1–12 made (`HORIZON_CAP_S`, `MATRIX_DISPLAY_MS`, `scripts/govee_razer_check.py`, `GET` and `PUT /api/lights/{id}/output`, `output.py`, `LampPlan`).
- Produces: both specs amended, each with a dated note at its top.

- [ ] **Step 1: Apply the edits**

If Task 8 changed `RAZER_IDLE_S`, first change "after 2 s without one" in the script below to its value. The script checks that each passage it replaces is there exactly once, so a spec that moved on since this plan was written stops it with the passage's first words; then edit that passage by hand to say the same.

```bash
uv run python - <<'EOF'
from pathlib import Path

PLAN = "[the light-output plan](../plans/2026-10-01-light-output-fixes.md)"
ENGINE = Path("docs/superpowers/specs/2026-09-23-home-effects-engine-design.md")
GOVEE = Path("docs/superpowers/specs/2026-03-13-govee-lan-protocol-design.md")

ENGINE_EDITS = [
    (
        "\n\n## 1. Goals and Scope",
        f"\n\n**Amended 2026-10-01** by {PLAN} (the owner's rulings O1–O3 and the plan's"
        " rulings 1–22): a zone renders at most 120 ms ahead; latency is one way, measured"
        " while a device streams, plus its display delay; each device is sent at its own rate,"
        " and an unchanged frame isn't sent again; brightness applies at send; placements fit"
        " each light's form; Govee lamps stream per segment by razer, and each lamp keeps its"
        " own output; Aurora's curtains reach the floor. §3, §4.1, §4.3, §6.1, §6.3 and §8"
        " say how.\n\n## 1. Goals and Scope",
    ),
    (
        "the horizon is the zone's slowest device latency plus one frame (~100–150 ms)",
        "the horizon is the zone's slowest device latency plus one frame, at most 120 ms",
    ),
    (
        "The horizon is the zone's largest device latency plus one frame, so reactive looks"
        " stay responsive while slow devices still get their frames in time.",
        "The horizon is the zone's largest device latency plus one frame, at most 120 ms"
        " (`HORIZON_CAP_S`), so reactive looks stay responsive: a device slower than that"
        " gets the newest frame and runs late by the difference.",
    ),
    (
        "takes its slice, converts float RGB to the device format and sends it. Devices"
        " claimed by a firmware layer skip streaming.",
        "takes its slice, scales it by the zone's brightness, converts float RGB to the"
        " device format and sends it, at the device's own rate: LIFX strips and matrices at"
        " most 20 a second (LIFX's documented ceiling), a Govee lamp 30 a second by razer and"
        " 10 by `colorwc`. A frame equal to the last one sent on the same route isn't sent"
        " again for up to a second; a new route always sends. Devices claimed by a firmware"
        " layer skip streaming.\n"
        "- A device's latency is one way: half of each probe's round trip, counted only"
        " within 0.5 s of a frame sent to that device (idle round trips run long under Wi-Fi"
        " power save), in a windowed median of 9, plus the device's display delay: half a"
        " LIFX fade, and for a matrix `MATRIX_DISPLAY_MS` more, measured on the real lights.",
    ),
    (
        "that scales its streamed frames and its firmware effects.",
        "that scales its streamed frames, at send (the zone's ring holds its frames before"
        " brightness), and its firmware effects.",
    ),
    (
        "Placement guessing spreads unplaced devices around their rooms, unconfirmed.",
        "Placement guessing spreads unplaced devices around their rooms, unconfirmed, each in"
        " its light's form: an upright lamp stands as a vertical line from 0.1 m, a strip"
        " lies along its length, a matrix stands as a grid, and anything else is a point."
        " When a light comes online, an unconfirmed placement that hides its form (many LEDs"
        " on a point, an upright lamp lying down) is fitted again.",
    ),
    (
        "Matrix size comes from `StateDeviceChain` instead of 64 LEDs per tile.",
        "Matrix size comes from `StateDeviceChain` instead of 64 LEDs per tile. Every"
        " streamed frame fades over the gap to the next one, less 2 ms. Discovery skips a"
        " known online light before asking it anything, and a light silent to a setup query"
        " gives no record that scan, so a silent light is never set up from defaults.",
    ),
    (
        "- **Govee:** streamed only.",
        "- **Govee:** streamed only. A lamp whose model takes razer (Govee's DreamView"
        " protocol) gets one colour per segment by razer; another gets one colour by"
        " `colorwc`, at most 10 a second. Each lamp can set its own output (segments or one"
        " colour, and a segment count) through `GET` and `PUT /api/lights/{id}/output`; it's"
        " kept in the lamp's device row, carried by backups and applied by reconnecting the"
        " lamp. A lamp that misses three status reads goes offline and gets no frames until"
        " a scan finds it.",
    ),
    (
        "measured, estimated and overridden latency with a 60 s history",
        "measured (one way, with the display delay), estimated and overridden latency with a"
        " 60 s history",
    ),
    (
        "offline devices become ghosts and rejoin on rediscovery, as today.",
        "offline devices become ghosts and rejoin on rediscovery, as today. A Govee lamp that"
        " stops answering is taken offline after three missed reads, rather than flooded"
        " with frames it can't take.",
    ),
]

GOVEE_EDITS = [
    (
        "per-segment color control (`ptReal` BLE-over-LAN)",
        "per-segment color control (razer, Govee's DreamView protocol; `ptReal`"
        " BLE-over-LAN until the light-output fixes)",
    ),
    (
        "\n\n## Hardware Targets",
        f"\n\n> **Amended 2026-10-01** by {PLAN} (the owner's ruling O2): per-segment colour"
        " goes by razer (DreamView) to UDP 4003, which sends no replies, instead of `ptReal`,"
        " which is removed; `colorwc` is the fallback, at most 10 a second; latency is a"
        " windowed median of one-way samples; a lamp that stops answering goes offline; each"
        " lamp can set its own output. The `ptReal` sections below are kept as the record of"
        " what was built first.\n\n## Hardware Targets",
    ),
    (
        "| Protocols | Core (`colorwc`) + Segment (`ptReal`) | Covers all current hardware."
        " Razer/DreamView deferred — user's devices don't support it. |",
        "| Protocols | Core (`colorwc`) + Segment (razer, DreamView) | The owner's ruling O2"
        " (light-output fixes): a razer frame carries one colour per segment and gets no"
        " reply. `ptReal` is removed. `colorwc`, at most 10 a second, is the fallback for a"
        " model without razer. The SKU registry says which models take razer, and"
        " `scripts/govee_razer_check.py` checks a lamp by eye. |",
    ),
    (
        "| Segment detection | SKU registry + config override | SKU from discovery lookup."
        " User can override segment count in TOML config. Unknown SKU falls back to solid"
        " adapter. |",
        "| Segment detection | Lamp's own output + config override + SKU registry | A lamp's"
        " own output (its device row, set by `PUT /api/lights/{id}/output`) first, then the"
        " TOML config's segment override, then the SKU registry, which also says whether a"
        " model takes razer, its form and which end its first segment is at. Unknown SKU"
        " falls back to solid adapter. |",
    ),
    (
        "| Latency strategy | EMA default, seeded at 100ms | Matches WiFi jitter profile. Same"
        " approach as LIFX. User can switch to windowed_mean or static. |",
        "| Latency strategy | Windowed median of 9, seeded at 100 ms | One way: half of each"
        " `devStatus` round trip measured while frames stream. Same as LIFX. User can switch"
        " to ema, windowed_mean or static. |",
    ),
    (
        "| Default FPS cap | 40 | Conservative for WiFi UDP with batched ptReal payloads."
        " User-configurable. |",
        "| Default FPS cap | 30 by razer, 10 by `colorwc` | Measured: `colorwc` at 40 a second"
        " ran 9 commands behind, and may have hung two lamps for about ten minutes; at 10, 1"
        " behind. The `colorwc` cap holds whatever the config says. |",
    ),
    (
        "| Reconnection | None in MVP | Device rediscovered on restart. WiFi UDP rarely fails"
        " at socket level. |",
        "| Reconnection | Ghosts and scans | A lamp that misses three status reads goes"
        " offline; a scan (every 30 s) brings it back. Setting a lamp's own output reconnects"
        " it. |",
    ),
    (
        "### Per-Segment Control via ptReal (BLE-over-LAN)\n",
        "### Per-Segment Control via ptReal (BLE-over-LAN)\n\n> Removed by the light-output"
        " fixes: razer replaced it. Kept as the record of what was built first.\n",
    ),
    (
        "| 15-segment ptReal | 15 × 28B base64 | ~800 bytes | Yes (MTU 1472) |\n",
        "| 15-segment ptReal | 15 × 28B base64 | ~800 bytes | Yes (MTU 1472) |\n"
        "| 255-segment razer frame | 772 bytes, 1032 as base64 | ~1.1 KB | Yes (MTU 1472) |\n",
    ),
    (
        "├── protocol.py          # Pure functions: BLE encoding, base64, checksums, JSON"
        " builders",
        "├── protocol.py          # Pure functions: razer frames, base64, checksums, JSON"
        " builders",
    ),
    (
        "├── segment.py           # GoveeSegmentAdapter — per-segment color via ptReal",
        "├── segment.py           # GoveeSegmentAdapter — per-segment color via razer\n"
        "├── output.py            # GoveeOutput (a lamp's own output), lamp_plan(), lamp_fps()",
    ),
    (
        "├── test_protocol.py     # BLE encoding, checksum, base64 (pure function tests)",
        "├── test_protocol.py     # Razer frames, checksum, base64 (pure function tests)",
    ),
    (
        "├── test_segment.py      # Segment adapter color mapping + ptReal",
        "├── test_segment.py      # Segment adapter: razer frames, one colour\n"
        "├── test_output.py       # Lamp plans, rates and stored outputs",
    ),
    (
        "Zero I/O. All BLE-over-LAN encoding logic.",
        "Zero I/O. All packet encoding: razer frames and the JSON commands.",
    ),
    (
        "def build_ble_packet(command_type: int, sub_command: int, payload: bytes) -> bytes\n"
        "def encode_segment_mask(segment_indices: Sequence[int], total_segments: int = 15)"
        " -> bytes\n"
        "def build_segment_color_packet(r: int, g: int, b: int, segment_mask: bytes) -> bytes\n",
        "def build_razer_switch(on: bool) -> dict\n"
        "def build_razer_frame(colors: NDArray[np.uint8]) -> dict  # 1 to 255 segments\n",
    ),
    (
        "def build_pt_real_message(ble_packets: Sequence[bytes]) -> dict\n"
        "def map_colors_to_segments(colors: NDArray[np.uint8], num_segments: int)"
        " -> list[tuple[int, int, int]]\n",
        "",
    ),
    (
        "- `map_colors_to_segments()` downsamples the global `(n_leds, 3)` array to"
        " `num_segments` RGB tuples by averaging LED ranges per segment.\n"
        "- `build_pt_real_message()` accepts multiple BLE packets for batching into a single"
        " UDP send.",
        "- `build_razer_frame()` packs a header, the segment count, one RGB triple per segment"
        " and an XOR checksum, base64-encoded; `build_razer_switch()` turns razer on or off.\n"
        "- The light-output fixes removed `ptReal`'s builders (`build_ble_packet`,"
        " `encode_segment_mask`, `build_segment_color_packet`, `build_pt_real_message`) and"
        " `map_colors_to_segments()`: a lamp's frame already has one colour per segment.",
    ),
    (
        "For RGBIC devices. Per-segment color via ptReal.",
        "For RGBIC devices. Per-segment color via razer, or one colour by `colorwc` for a"
        " model without it (its `LampPlan`).",
    ),
    (
        "    #   1. Downsample global LED array to segment count via map_colors_to_segments()\n"
        "    #   2. Build one BLE packet per segment with color + segment mask\n"
        "    #   3. Batch all into single ptReal message, one UDP send via transport\n",
        "    #   1. The frame has one colour per segment (led_count is the segment count)\n"
        "    #   2. Razer: razer on before the first frame and after 2 s without one, then\n"
        "    #      one razer frame (an RGB triple per segment, XOR checksum) to port 4003\n"
        "    #   3. One colour: the frame's average as one colorwc command\n",
    ),
    (
        "- Create `LatencyTracker` (EMA, seeded from heuristic 100ms).",
        "- Create `LatencyTracker` (windowed median, seeded at 100 ms one way).",
    ),
    (
        'govee_latency_strategy: str = "ema"',
        'govee_latency_strategy: str = "windowed_median"',
    ),
    (
        "govee_max_fps: int = 40",
        "govee_max_fps: int = 30  # razer; colorwc is capped at 10 whatever this says",
    ),
    ("govee_latency_window_size: int = 60", "govee_latency_window_size: int = 9"),
    (
        '`govee_latency_strategy in {"static", "ema", "windowed_mean"}`',
        '`govee_latency_strategy in {"static", "ema", "windowed_mean", "windowed_median"}`',
    ),
    (
        "| Device goes offline mid-session | Frames silently drop (UDP fire-and-forget). No"
        " explicit detection in MVP. |",
        "| Device goes offline mid-session | Its status reads go unanswered: three missed"
        " reads (about 15 s) take it offline, and it gets no frames until a scan finds it."
        " While another program holds UDP 4002 no reply arrives at all, so this can't be"
        " told and frames keep going. |",
    ),
    (
        "| ptReal batch exceeds MTU | Not possible — 15 segments × 28B base64 = ~800 bytes,"
        " well within 1472-byte MTU. |",
        "| Razer frame exceeds MTU | Not possible — at most 255 segments: 772 bytes, about"
        " 1.1 KB as base64 in JSON, within the 1472-byte MTU. |",
    ),
    (
        "| `test_protocol.py` | BLE encoding, checksums, base64, JSON builders, segment"
        " downsampling |",
        "| `test_protocol.py` | Razer frames and switches, checksums, base64, JSON builders |",
    ),
    (
        "| `test_segment.py` | Segment adapter color mapping, ptReal batching | Mock transport."
        " Verify downsampling, BLE packet count, segment masks. |",
        "| `test_segment.py` | Segment adapter: razer frames and arming, one colour | Mock"
        " transport. Verify razer on and off, frame bytes, the colour fallback. |\n"
        "| `test_output.py` | Lamp plans, rates and stored outputs | Pure logic. Razer or one"
        " colour, segment counts, the colour cap, a stored output read as far as it can be"
        " used. |",
    ),
    (
        '- **Razer/DreamView protocol** (`cmd:"razer"`): Per-LED direct control for'
        " DreamView-compatible devices. Would add a third adapter type"
        " (`GoveeDirectAdapter`).",
        '- **Razer/DreamView protocol** (`cmd:"razer"`): built by the light-output fixes, in'
        " `GoveeSegmentAdapter` rather than a third adapter type, one colour per segment.",
    ),
    (
        "- **Reconnection logic**: Auto-reconnect on device reappearance without full"
        " restart.",
        "- **Reconnection logic**: built: a lamp back from a drop-out rejoins at the next"
        " scan, and setting a lamp's own output reconnects it.",
    ),
    (
        "- **Per-device config overrides**: Different segment counts, FPS caps, or latency"
        " strategies per device (requires config schema change).",
        "- **Per-device config overrides**: a lamp's own output (razer or one colour, and a"
        " segment count) is built, kept in its device row; per-device FPS caps and latency"
        " strategies are not.",
    ),
]

for path, edits in ((ENGINE, ENGINE_EDITS), (GOVEE, GOVEE_EDITS)):
    text = path.read_text()
    for old, new in edits:
        assert text.count(old) == 1, f"{path.name}: {old[:60]!r} isn't there once"
        text = text.replace(old, new)
    path.write_text(text)
    print(f"{path.name}: {len(edits)} edits")
EOF
```

Expected: `2026-09-23-home-effects-engine-design.md: 10 edits` and `2026-03-13-govee-lan-protocol-design.md: 31 edits`.

- [ ] **Step 2: Read the result**

```bash
git diff --stat
grep -c 'ptReal' docs/superpowers/specs/2026-03-13-govee-lan-protocol-design.md
```

Expected: the two specs changed. The `ptReal` count is 7: the overview's "until the light-output fixes", the amendment note, the protocols row, the marked section's heading and its message example, the packet-size row, and the protocol module's note of what was removed. Read the two diffs through once: each changed passage reads as a sentence, and nothing names a light, an address or a model number.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-09-23-home-effects-engine-design.md docs/superpowers/specs/2026-03-13-govee-lan-protocol-design.md
git commit -m "docs: the specs say what the light-output fixes do"
```

---

### Task 14: CLAUDE.md and the README

CLAUDE.md asks for the claude-md skill to revise Claude's context after each plan. This plan changes the latency strategies, the horizon, the scheduler's rates, LIFX discovery and fades, the Govee protocol and its outputs, placement guessing and a route, and it makes the 4002 gotcha wrong, so several lines of CLAUDE.md are now wrong. The README describes the latency strategies, the old lookahead and Govee's segment control.

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Run the skills**

Run the `claude-md-management:claude-md-improver` skill (audit and targeted updates), then `/claude-md-management:revise-claude-md` for what this branch taught. Both show their changes before writing. Accept what Step 2 lists and what's true of this branch, nothing else.

- [ ] **Step 2: Check the facts this plan changed are in CLAUDE.md**

Whatever the skills propose, CLAUDE.md must end up saying these, and nothing that contradicts them. No addresses, light names or model numbers (Global Constraints). If Task 8 changed `RAZER_IDLE_S` or Task 15 changed `MATRIX_DISPLAY_MS`, name the constant, not a number.

- **Commands:** `uv run python scripts/govee_razer_check.py --ip ADDRESS --segments N --pattern whole --restore-colour RRGGBB --restore-power on` plays a razer pattern (`whole`, `ends`, `stripes`, `chase`, `gaps` or `status`) on one Govee lamp for the owner to judge by eye, then puts the lamp back as the two `--restore-` options say; only `status` binds UDP 4002, so it runs only while the deployed app is stopped.
- **Architecture:**
  - `latency/`: ProbeStrategy protocol + StaticLatency, EMA (three outliers in a row are a new level), WindowedMean and WindowedMedian (the default, a window of `LATENCY_WINDOW`); `make_strategy()` and `STRATEGIES`. `LatencyTracker` counts a probe's round trip, halved, only within `STREAMING_WINDOW_S` of a frame sent (`note_send`, `update_rtt`), and adds the device's `display_ms`.
  - `scheduling/`: each device at its own rate (`stream_fps` for a LIFX kind, `lamp_fps` for a Govee lamp), a frame equal to the last one sent on the same route skipped for up to `KEEPALIVE_S` (a new route or adapter always sends), and `note_send` after each send. `scheduling/route.py`: the route applies the zone's brightness at send.
  - `zones/runtime.py`: the horizon is capped at `HORIZON_CAP_S` (120 ms), and the ring holds frames before brightness; `zones/frames.py` scales the web app's frames.
  - `devices/lifx/`: streamed frames fade over the gap to the next (`stream_fade_ms`); strips and matrices at most `LIFX_STRIP_FPS` and `LIFX_MATRIX_FPS` (20); a matrix's `display_ms` adds `MATRIX_DISPLAY_MS`. Discovery skips a known online light before `GetVersion`, and a light silent to `GetVersion` or a setup query gives no record that scan (`FakeLifxTransport(quiet=...)` in tests).
  - `devices/govee/`: razer frames (one colour per segment, UDP 4003, no replies) or one `colorwc` colour at most `GOVEE_COLOUR_FPS` (10); `output.py` (`GoveeOutput`, a lamp's own output in its row's `extra`; `LampPlan`, `lamp_plan()`, `lamp_fps()`); the SKU table's `razer`, `form` and `segments_from_top`; a lamp that doesn't answer a read raises `NoAnswer`.
  - `devices/discovery.py`: `reconnect(stable_id)` sets a known light up again from its row.
  - `home/guess.py`: `placed_in_form()` and `in_form()`; `home/map.py`: `HomeMap.refit()` fits unconfirmed placements to their lights' forms, and `main.py` runs it when a light comes online.
  - `web/router_lights.py`: `GET` and `PUT /lights/{id}/output`; the discovery orchestrator is in `app.state` (`get_discovery`), so `POST /devices/scan` runs a real scan.
  - `config.py`: the rate constants (`LIFX_STRIP_FPS`, `LIFX_MATRIX_FPS`, `GOVEE_RAZER_FPS`, `GOVEE_COLOUR_FPS`) and `LATENCY_WINDOW`.
- **Key design decisions:**
  - Replace the horizon line: each zone renders at `now + horizon`, its lights' largest latency plus a frame, at most 120 ms (`HORIZON_CAP_S`); a light slower than that gets the newest frame and runs late by the difference.
  - Replace "each device runs at its natural FPS (bounded by configurable cap)": LIFX bulbs at the config's cap, strips and matrices at most 20 a second, a Govee lamp 30 by razer and 10 by `colorwc` whatever the config says; unchanged frames are skipped for up to a second.
  - Replace the heuristic latency line: latency is one way, a windowed median seeded at the config's `latency_ms` (LIFX 10 ms, Govee 100 ms), plus the device's display delay (half a LIFX fade; a matrix's `MATRIX_DISPLAY_MS` more). Idle round trips are ignored: Wi-Fi power save makes them long. OpenRGB adapters keep the device-type heuristics (USB 5 ms).
  - Brightness applies at send: rings hold frames before brightness; routes and the frame feed scale them.
  - A Govee lamp's output: its own (`PUT /api/lights/{id}/output`, JSON in its device row's `extra` under `output`), else the config's `segment_override`, else the SKU table; setting one reconnects the lamp, and a restored backup's outputs apply at the next start.
  - Razer is switched on before a lamp's first frame and after `RAZER_IDLE_S` without one, and again after a prepare, restore or power switch; a restore of a lamp that's on sends razer-off first.
  - A Govee lamp that misses three reads goes offline and gets no frames until a scan finds it.
  - Placement guessing puts each light in its form (an upright lamp stands from 0.1 m, a strip lies along its length, a matrix stands as a grid), and an unconfirmed placement that hides its light's form is fitted again when the light comes online.
- **Testing:** `tests/conftest.py`'s `RingSource` and `ring_route()` take `brightness`; `tests/lifx_fakes.py`'s `FakeLifxTransport` takes `quiet` (the messages a light never answers).
- **Gotchas:**
  - Replace the 4002 line: UDP 4002 (Govee replies) belongs to whichever program binds it first. The deployed app holds it; Home Assistant's `govee_light_local` retries every 10 minutes, at about :x8 past the hour, and takes it if dj-ledfx is down then, which leaves dj-ledfx deaf to Govee replies (the log warns `could not bind port 4002`): it can't read a lamp or tell one stopped answering, and keeps sending. Stop the app well clear of :x8, and after a restart check that `ss -ulne 'sport = :4002'` shows `uid:10001` (`ss -p` needs root).
  - A run beside the deployed app can't hear Govee replies, so it can't capture a lamp, and Off can't restore one: keep Govee lamps out of such a run (Task 15 deletes their rows from its copy of the database).
  - Govee `colorwc` at 40 a second ran 9 commands behind, and two lamps flooded that way were unreachable for about ten minutes; `GOVEE_COLOUR_FPS` caps it at 10 whatever the config says.
  - A LIFX matrix queues `SetTileState64` above about 30 a second; matrices are capped at 20.
  - A lamp streaming razer may not answer status queries (Task 8's finding says whether it does).

- [ ] **Step 3: Fix the README**

```bash
uv run python - <<'EOF'
from pathlib import Path

README = Path("README.md")
EDITS = [
    (
        "now + device_latency (static / EMA / windowed-mean strategies)",
        "now + device_latency (one way, measured while streaming)",
    ),
    (
        "The engine renders at `now + max_lookahead`;",
        "Each zone renders at `now + horizon` (its slowest light's latency plus a frame, at"
        " most 120 ms);",
    ),
    (
        "per-device send loops run at each device's natural FPS; latency is estimated by"
        " static, EMA, or windowed-mean strategies, seeded with device-type heuristics.",
        "per-device send loops run at each device's own rate (LIFX strips and matrices at"
        " most 20 a second, a Govee lamp 30 by razer or 10 in one colour) and skip a frame"
        " the device already shows; latency is one way, half the probe round trips measured"
        " while a device streams, in a windowed median (static, EMA and windowed-mean"
        " strategies remain), plus the device's display delay.",
    ),
    (
        "Govee LAN (UDP segment control with SKU registry)",
        "Govee LAN (one colour per segment by razer, or one colour, with an SKU registry and"
        " each lamp's own output)",
    ),
]
text = README.read_text()
for old, new in EDITS:
    assert text.count(old) == 1, f"{old[:60]!r} isn't there once"
    text = text.replace(old, new)
README.write_text(text)
print(f"README.md: {len(EDITS)} edits")
EOF
```

Expected: `README.md: 4 edits`.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: CLAUDE.md and the README for the light-output fixes"
```

---

### Task 15: The lag readout after the fixes (orchestrator, Owner's go)

Rulings 1, 3, 5 and 6. The orchestrator plays the baseline's look on this branch, run beside the deployed app, and measures the same three lights the same way. The deployed app keeps running, idle, and is never stopped. The Govee lamps sit this out: UDP 4002 is the deployed app's, so the branch can't hear them, and a lamp it can't capture it can't restore. Ruling 3's matrix display delay is provisional, and this task corrects it. Write the numbers down for the PR by kind of light: no names, addresses or model numbers, which stay in the terminal.

**Files** (only if Step 7 corrects the delay):
- Modify: `src/dj_ledfx/devices/lifx/tile_chain.py` (`MATRIX_DISPLAY_MS`)

**Interfaces:**
- Consumes: the investigation's `measure.py`, at `~/code/private/dj-ledfx/.superpowers/light-output/measure.py` on this host (the main checkout's git-ignored workspace) (its `look` command, with its defaults: they are the baseline's look, lights and length). If it's gone, ask the orchestrator who ran the baseline for it; don't write a new one.
- Produces: the after-fix table for the PR, and `MATRIX_DISPLAY_MS` as measured.

- [ ] **Step 1: Check the preconditions (Owner's go)**

Ask the owner: "May I run the lag readout now? The branch plays the classic rainbow wave on the whole home for a minute, without the Govee lamps, then turns it off, and every light goes back as it was. A light that's off comes on for that minute. The deployed app keeps running." The preconditions, verbatim: "dj-ledfx is idle: `GET http://127.0.0.1:8080/api/running` shows no zones and no overlays; LedFx is paused; each light's state is captured before and restored after; no state.db changes and no deploys."

```bash
curl -s http://127.0.0.1:8080/api/running; echo
curl -s http://127.0.0.1:8888/api/virtuals | uv run python -c 'import json, sys; print("LedFx paused:", json.load(sys.stdin)["paused"])'
ss -ltn 'sport = :8099' | tail -n +2 | grep -q . && echo "8099 is taken" || echo "8099 is free"
```

Expected: `{"zones":[],"overlays":[]}`, `LedFx paused: True` and `8099 is free`. If a zone runs or LedFx plays, stop and ask the owner; don't stop either yourself. If 8099 is taken, pick another free port and use it in every step below.

- [ ] **Step 2: Capture the lights and build the branch's database**

The branch runs on a copy of the deployed app's database, made with SQLite's backup from a read-only connection, as the app's user, so the deployed `state.db` is never written. The backup export can't be used, since it answers 500 on that database (What exists). The copy leaves out the Govee lamps.

```bash
R=$(mktemp -d)
echo "$R"
curl -s http://127.0.0.1:8080/api/lights -o "$R/lights-before.json"
docker exec -u 10001 dj-ledfx-app-1 python -c "import sqlite3; src = sqlite3.connect('file:/app/state/state.db?mode=ro', uri=True); dst = sqlite3.connect('/tmp/light-output-copy.db'); src.backup(dst); dst.close(); src.close()"
docker cp -q dj-ledfx-app-1:/tmp/light-output-copy.db "$R/state.db"
docker exec -u 10001 dj-ledfx-app-1 rm /tmp/light-output-copy.db
cp ~/code/private/dj-ledfx/.superpowers/light-output/measure.py "$R/"
sed -i 's/127\.0\.0\.1:8080/127.0.0.1:8099/g' "$R/measure.py"
grep -c '127.0.0.1:8099' "$R/measure.py"
uv run python - "$R" <<'EOF'
import asyncio
import sys
from pathlib import Path

from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.store import ZoneStore

R = Path(sys.argv[1])


async def main() -> None:
    db = StateDB(R / "state.db")
    await db.open()
    try:
        if await ZoneStore(db).load_assignments():
            raise SystemExit("a look runs on the deployed app: stop and ask the owner")
        await db.write("DELETE FROM devices WHERE backend = ?", ("govee",))
        rows = await db.fetch_all("SELECT backend, COUNT(*) FROM devices GROUP BY backend")
    finally:
        await db.close()
    print("the branch's devices:", dict(rows))


asyncio.run(main())
EOF
```

Expected: the directory's path, `2` (the script's API and socket addresses, now the branch's port), and the branch's devices by backend, with no `govee`. The container's `/tmp` is left as it was. Keep `$R` for the rest of the task: every step below uses it.

- [ ] **Step 3: Start the branch beside the deployed app**

Run it in the background (the Bash tool's `run_in_background`, or `&` as here). A nonexistent `--config` means nothing is migrated: the config comes from the copied database, and `devices.*` from this branch's defaults (ruling 21). `--dj-listen` keeps it off the deployed app's UDP 50001 (CLAUDE.md's gotcha). It warns that it can't bind UDP 4002, as expected.

```bash
uv run -m dj_ledfx --dj-listen 127.0.0.1:0 --web --web-host 127.0.0.1 --web-port 8099 \
  --config "$R/none.toml" --db "$R/state.db" > "$R/app.log" 2>&1 &
echo $! > "$R/app.pid"
until curl -sf http://127.0.0.1:8099/api/running >/dev/null; do sleep 1; done
uv run python - <<'EOF'
import json
import time
import urllib.request


def get(port: int, path: str) -> object:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/{path}") as answer:
        return json.load(answer)


def lifx_online(port: int) -> set[str]:
    lights = get(port, "lights")
    assert isinstance(lights, list)
    return {
        light["id"]
        for light in lights
        if light["protocol"] == "LIFX" and light["status"] != "offline"
    }


config = get(8099, "config")
assert isinstance(config, dict)
devices = config["devices"]
print("preview only:", config["engine"]["preview_only"])
lifx, govee = devices["lifx"], devices["govee"]
print("LIFX strategy:", lifx["latency_strategy"], "| Govee max fps:", govee["max_fps"])
want = lifx_online(8080)
for _ in range(90):
    if lifx_online(8099) >= want:
        break
    time.sleep(1)
print(f"the branch has {len(lifx_online(8099) & want)} of the {len(want)} LIFX lights online")
EOF
```

Expected: `preview only: False`, `LIFX strategy: windowed_median | Govee max fps: 30`, and every LIFX light online on the branch (`N of the N`). If preview only is True, the deployed app's database has it on: stop here and ask the owner. If a light is missing after 90 s, check `"$R/app.log"`, and stop and tell the owner if it doesn't turn up.

- [ ] **Step 4: Play the look and measure**

From the main checkout, which has master's LIFX code that `measure.py` was written against:

```bash
(cd /home/anirudhlath/code/private/dj-ledfx && uv run --no-sync --with websockets --with httpx python "$R/measure.py" look)
```

It refuses to start if a look already runs on the branch, plays the classic rainbow wave on the whole home for 60 s, and turns it off in a `finally`. It prints one line per measured light and writes `"$R/results-look-classic-rainbow-wave.json"`. Expected: three lines, each with `matched` in the hundreds. A `KeyError` naming a light means that light is offline: tell the owner and stop.

- [ ] **Step 5: Read the results**

```bash
uv run python - "$R" <<'EOF'
import json
import sys
import urllib.request
from pathlib import Path

R = Path(sys.argv[1])
results = json.loads((R / "results-look-classic-rainbow-wave.json").read_text())
with urllib.request.urlopen("http://127.0.0.1:8099/api/lights") as answer:
    latency = {light["name"]: light["latency"]["measuredMs"] for light in json.load(answer)}
kinds = ("first bulb", "second bulb", "matrix")
for kind, (name, r) in zip(kinds, results.items(), strict=True):
    print(
        f"| {kind} | {r['late_med_ms']} ms | {r['late_p95_ms']} ms | {r['rtt_med']} ms"
        f" | {latency.get(name)} ms |"
    )
EOF
```

Expected: one table row per light, in the baseline's order: median lateness, p95 lateness, median round trip, and the app's latency for that light. The baseline (What exists) had the bulbs' medians within 7 ms of zero and the matrix's at 93 ms, p95 290 ms. The bulbs should stay within ±10 ms with a lower p95 (they fade now); the matrix should be within ±25 ms with a much lower p95 (20 a second, no queue). Write the table down with the baseline's beside it.

- [ ] **Step 6: Stop the branch and check the lights came back**

```bash
kill -TERM "$(cat "$R/app.pid")"
while kill -0 "$(cat "$R/app.pid")" 2>/dev/null; do sleep 1; done
grep -c Traceback "$R/app.log"
```

Expected: `0`. Then give the deployed app 40 s to read every idle light again (it reads them every 30 s): wait with a background timer or the Monitor tool, not a foreground `sleep`. Then:

```bash
curl -s http://127.0.0.1:8080/api/lights -o "$R/lights-after.json"
uv run python - "$R" <<'EOF'
import json
import sys
from pathlib import Path

R = Path(sys.argv[1])
before, after = (
    {light["id"]: light for light in json.loads((R / f"lights-{when}.json").read_text())}
    for when in ("before", "after")
)
changed = [
    (light["name"], (light["power"], light["colour"]), (after[i]["power"], after[i]["colour"]))
    for i, light in before.items()
    if i in after and (light["power"], light["colour"]) != (after[i]["power"], after[i]["colour"])
]
print(len(before), "lights;", len(changed), "not as they were")
for name, was, now in changed:
    print(f"  {name}: was {was}, now {now}")
EOF
```

Expected: `0 not as they were`. A light listed there didn't get its state back: tell the owner which, with its before and after.

- [ ] **Step 7: Correct the matrix's display delay, if it's off**

If the matrix's median lateness is within ±25 ms, skip this step. Otherwise its display delay isn't 40 ms: the delay becomes 40 plus the median, rounded to 10 ms, within 0–150.

```bash
NEW=$(uv run python -c "import json, sys; r = list(json.load(open(sys.argv[1])).values())[2]; print(min(150, max(0, round((40 + r['late_med_ms']) / 10) * 10)))" "$R/results-look-classic-rainbow-wave.json")
echo "$NEW"
sed -i "s/^MATRIX_DISPLAY_MS = 40$/MATRIX_DISPLAY_MS = $NEW/" src/dj_ledfx/devices/lifx/tile_chain.py
uv run pytest tests/devices/lifx -q
```

Expected: the new value, and the LIFX tests pass (they read the constant). If the app's latency for the matrix plus the change comes to more than about 100 ms, the horizon cap (ruling 1) holds the matrix back and it runs late by the excess whatever the value: say so in the PR. Then the gates and a commit:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ 2>&1 | tail -1 && uv run pytest -q 2>&1 | tail -1
git add src/dj_ledfx/devices/lifx/tile_chain.py
git commit -m "fix(lifx): a matrix's display delay, as measured"
```

Then, with the owner's go, run Steps 3 to 6 once more on the same `$R` (its `lights-before.json` stays; Step 6 compares with it), and keep that run's table. Correct the delay only once: if the second run's median is still off, report both runs.

- [ ] **Step 8: Write down the readout for the PR**

In words and numbers only: the table by kind of light, before and after; the matrix's display delay as set; whether every light came back. No light names, addresses or model numbers. `$R` holds a copy of the home's database: leave it out of the repo.

---

### Task 16: Catch up with master and open the PR

CLAUDE.md ends every plan with a pull request. Master may have moved since this branch started.

**Files:**
- Modify: `web/src/api/generated/*` only if the rebase changed the backend's API
- Create: `/tmp/light-output-pr/` (not committed): the diff's added lines, the private words to grep for, the PR description

- [ ] **Step 1: Rebase onto `master`**

```bash
git fetch origin
git rebase origin/master
git log --oneline -8 origin/master
```

The branch hasn't been pushed, so rebasing is safe. Under `web/`, the branch changes only the generated API types (Task 10) and the mock's `looks.json` (Task 12). A conflict in the generated types means master's API changed too: if `web/package-lock.json` changed on master, run `(cd web && npm ci)` first; then regenerate from the merged code, `(cd web && npm run api:types)`, and `git add web/src/api/generated && git rebase --continue`. A conflict in a `looks.json` or `HANDOFF.sha256` means a new handoff landed: take master's files and run Task 12's Step 3 again. A conflict anywhere else under `web/` means something unexpected changed: stop and tell the owner. If a conflict touches `CLAUDE.md`, `README.md`, `config.toml` or a spec, keep both sides.

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

- [ ] **Step 3: Run every gate**

```bash
uv run ruff check . && uv run pytest -q
uv run ruff format --check . ; uv run mypy src/ 2>&1 | tail -1   # compare with the baseline
uv run pytest -m perf -q
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256 | grep -v ': OK$' || echo "all pins OK")
(cd web && npm run api:check && npm test && npx tsc -b && npm run lint && npm run build)
(cd web && npx playwright install chromium && npm run e2e)
```

Expected:
- ruff is clean and every test passes: Before Task 1's count plus 78 (Tasks 1–11's new tests; Task 12 replaces one), plus whatever master added.
- No format findings, and mypy's 16 errors in the same 4 files as Before Task 1.
- The perf run as Before Task 1 (this plan adds no perf test).
- `all pins OK`.
- Every web step passes, with Before Task 1's web test count plus whatever master added. e2e serves on 4174 and 4175, so only one worktree runs it at a time (CLAUDE.md's gotcha).

- [ ] **Step 4: Check that nothing private is in the branch**

The diff's added lines are checked for addresses, MACs, light names, model names, Govee model numbers, product words and AI model names. The names and model numbers are read at run time from `home.json`, the deployed app and the SKU table, and the product and AI model words come from the orchestrator's list (`words.txt` in the main checkout's git-ignored `.superpowers/light-output/`, named below; if it's gone, ask the orchestrator for it), so none of them is typed here, and the greps print counts only. The handoff's own files and their byte copies are left out, and so is the design prompt, whose one changed line is the handoff's description (Task 12): the `--stat` line checks that.

```bash
B=/tmp/light-output-pr
mkdir -p "$B"
cp ~/code/private/dj-ledfx/.superpowers/light-output/words.txt "$B/"
git diff --stat origin/master -- docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md | tail -1
git diff origin/master -- . ':!docs/design' ':!src/dj_ledfx/home/data' ':!src/dj_ledfx/looks/data' \
  ':!web/src/api/mocks/looks.json' ':!docs/superpowers/specs/2026-09-23-dashboard-claude-design-prompt.md' \
  | grep '^+' > "$B/added.txt"
uv run python - "$B" <<'EOF'
import json
import sys
import urllib.request
from pathlib import Path

from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY

out = Path(sys.argv[1])
home = json.loads(Path("docs/design/web-app/home.json").read_text())
words = {light[key] for light in home["lights"] for key in ("name", "model") if light.get(key)}
with urllib.request.urlopen("http://127.0.0.1:8080/api/lights") as answer:
    lights = json.load(answer)
words |= {light[key] for light in lights for key in ("name", "model") if light.get(key)}
# the code's own words: the PC, the backends and device types such as govee_segment
words = {word for word in words if word.lower() not in {"pc", "lifx", "govee", "openrgb"}}
words = {word for word in words if "_" not in word} | set(SKU_REGISTRY)
(out / "private.txt").write_text("\n".join(sorted(words)) + "\n")
print(len(words), "names, models and model numbers to look for")
EOF
grep -nE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' "$B/added.txt" | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
grep -ciwFf "$B/private.txt" "$B/added.txt" || echo "no names or models"
grep -ciwFf "$B/words.txt" "$B/added.txt" || echo "no product or AI model words"
```

Expected: `1 file changed, 1 insertion(+), 1 deletion(-)`, a count of words to look for, `no addresses`, `0` and `no names or models`, and `0` and `no product or AI model words`. Loopback and `0.0.0.0` are allowed. Anything found goes: replace it with `127.0.0.1`, a kind of light ("the matrix", "an upright lamp"), or a value read at run time. If a count comes from a line this branch only moved (an existing CLAUDE.md line the skills rewrote), tell the owner instead.

- [ ] **Step 5: Write the PR description**

Write `$B/body.md` with these sections, in this order.

**Summary.** Fixes for what the owner saw on the real lights: Aurora lit only about four lights, every look lagged, and the Govee lamps acted as single points. Seven causes, one PR (O3). Plan: `docs/superpowers/plans/2026-10-01-light-output-fixes.md`.

**What changed**, one bullet per area:

- Latency: one way, half the probe round trips measured while a light streams, in a windowed median of 9 (the new default), plus each light's display delay; the EMA follows a new level after three outliers in a row.
- Frames: a zone renders at most 120 ms ahead, and brightness applies at send.
- Rates: LIFX strips and matrices at most 20 a second, with every frame fading to the next; Govee 30 a second by razer, `colorwc` capped at 10; an unchanged frame isn't sent again for up to a second; nothing waits for an acknowledgement.
- LIFX discovery: a known online light is skipped before it's asked anything, and a silent light is never set up from defaults.
- Govee: razer frames, one colour per segment, where the SKU table says the model takes them; `ptReal` is gone; a lamp that stops answering goes offline instead of being flooded; the model shows as `Govee <model number>`; each lamp's own output, kept in its device row and applied by reconnecting it; a razer check script.
- API: `GET` and `PUT /api/lights/{id}/output`; `POST /api/devices/scan` runs a real scan, and scans take turns.
- Backups: a lamp's own output travels in them, and an unset config value no longer breaks the export (the deployed app's answered 500).
- The home map: unconfirmed placements fitted to each light's form.
- Aurora: its band is the room's whole height, and its copy says so (`looks.json` and its copies, under O1).
- Docs: both specs, CLAUDE.md and the README.

**API.** `GET /api/lights/{id}/output` answers a Govee lamp's output (`mode`, `segments`, `own`, `online`); `PUT` takes `mode` (`segments` or `colour`) and `segments` (2–255), either or both null to give it back to the model, and reconnects the lamp. 404 for anything that isn't a known Govee lamp, 422 for a mode or count no lamp plays. Outside the web spec's contract until a design handoff adds it (ruling 17); the web app doesn't change beyond its generated types.

**Migration.** None. A lamp's own output is JSON in the `devices` table's `extra` column (migration 001).

**Deployment.** After the merge, from the main checkout, at a time well clear of :x8 past the hour: `git pull && docker compose up -d --build`, then `ss -ulne 'sport = :4002'` shows `uid:10001`. On its first start the app fits unconfirmed placements to their lights' forms as the lights come online, and the Govee lamps whose model takes razer play per segment.

**Spec rulings.** O1–O3 and rulings 1–22 from the plan, one line each, with what Task 8 and Task 15 settled.

**Review Focus.** The plan's six items, each with its test.

**Real lights.** Task 8's findings, in words: what each pattern showed on each lamp, by its table entry, and whether a streaming lamp answered status queries. Task 15's table before and after, by kind of light, and the matrix's display delay as set. No names, addresses or model numbers.

**Known issues.** The lowest lights glow dimly in Aurora (a curtain fades in up to its band's middle). A run beside the deployed app can't hear Govee replies, so it can't capture or restore a lamp. A restored backup's lamp outputs apply at the next start. The web app shows LIFX and Govee latency as estimated, because `estimated` follows `supports_latency_probing`, which is False on every real adapter. The Claude Design project still has Aurora's old copy (ruling 20). The Govee outage's cause is unproven.
*Note, 2026-10-02 (review):* the review's fixes ended two of these. `estimated` now says whether a round trip has been measured, and a restored backup's outputs apply at once.

**Test plan.** Step 3's gates with their counts, the perf run, the web gate, Task 8 and Task 15.

End the description with:

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Then check the description as Step 4 checked the diff:

```bash
grep -nE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' "$B/body.md" | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
grep -ciwFf "$B/private.txt" "$B/body.md" || echo "no names or models"
grep -ciwFf "$B/words.txt" "$B/body.md" || echo "no product or AI model words"
```

Expected: `no addresses`, `0` and `no names or models`, and `0` and `no product or AI model words`.

- [ ] **Step 6: Push and open the PR**

```bash
git push -u origin fix/light-output
gh pr create --base master --head fix/light-output \
  --title "Light output: one-way latency, a 120 ms horizon, rates per light, Govee razer, placements in form, Aurora to the floor" \
  --body-file "$B/body.md"
gh pr view --json url --jq .url
```

Give the owner the URL. Don't merge: the owner does, after review. CLAUDE.md's code-architect review and `/simplify` run on the open PR, outside this plan.
