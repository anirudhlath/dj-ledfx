# Light Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (CLAUDE.md's choice for this repo) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep every light in step with every other without supervision: the Govee lamps are probed about every 0.5 s while they stream, a light whose Wi-Fi dozes is recognised by when its replies land and gets its whole round trip as its latency, the horizon cap rises to 500 ms, each light's latency and mode are remembered across restarts, and the device settings in state.db apply at last, those saved in the app included.

**Architecture:** A new `latency/doze.py` holds a light's last 40 round trips with their arrival times and works out the Rayleigh statistic of the arrivals' phases in the 102.4 ms beacon cycle, and their median. `LatencyTracker` feeds its strategy the whole round trip of a light the check calls dozing and half of an awake one's, restarting the strategy from the held round trips when the mode changes. `GoveeTransport` gains a probe loop like LIFX's, asking each lamp that streams for its status after random waits of 75–125% of the interval, and the zone runtime's `HORIZON_CAP_S` becomes 0.5 s. `latency/memory.py`'s `LinkMemory` keeps each light's latency and mode in a new `link_memory` table (migration 010): the discovery orchestrator recalls a light's row as it takes the light in, and a task writes what changed every 30 s and at shutdown. `main.py` builds `DevicesConfig` from state.db, after a run-once step deletes the `devices.*` rows that never applied, and `PUT /api/config` saves there the device settings a request names.

**Tech Stack:** Python 3.11+ (3.14 in the venv and the container), asyncio, SQLite through `StateDB`, loguru, numpy (the replay test's quartiles), pytest with pytest-asyncio. No new dependency: the doze check uses only `math` and `statistics`, and the probe loop `random`. Context7 is unavailable here (its server needs authorizing), and no outside library's API is new to the repo, so no outside docs were needed.

**Spec:** `docs/superpowers/specs/2026-10-04-light-sync-design.md`, revised 2026-10-06, all of it. The engine spec's §4.1 latency bullet is already amended at that spec's top. Read the light-sync spec before starting.

**What exists** (master at `1d6ed22`, plus the docs PR that brings the spec, both recordings and this plan):

- `LatencyTracker` halves every round trip that lands within `STREAMING_WINDOW_S` (0.5 s) of a frame sent, feeds it to its strategy (a windowed median of 9 by default) and adds the device's `display_ms`. `reset()` (a light that came back) starts the strategy again from the config's seed. `tracker_for(cfg, seed_ms=, display_ms=)` builds every backend's tracker.
- The LIFX transport echo-probes each light that streams every 2 s (`register_device(..., streaming=)`). The Govee transport times each status query to its reply (`register_device(record, rtt_callback)`; the light monitor's reads, every 5 s, are what it times today), and its docstring says there's no probe loop. `GoveeConfig.probe_interval_s` (5 s) is kept only so old config files load.
- `zones/runtime.py` has `HORIZON_CAP_S = 0.12`, which `tests/zones/test_runtime.py::test_the_horizon_is_capped` pins.
- `main.py`'s `_load_config_from_db` builds every section but `DevicesConfig`, so no `devices.*` row has ever applied. The deployed database holds rows from an old config file (spec §2): `ema` over 60 samples, Govee at 40 frames a second with probes every 5 s, a LIFX seed of 50 ms.
- `PUT /api/config` (`web/router_config.py`) saves each flat section of the merged config to state.db's config table, whole, and no device setting: `devices` holds only tables, which its loop skips. `POST /api/config/import` saves nothing there. A backup (`GET /api/state/export`) carries the config table but not its run-once marks (`load_all_config` leaves `_meta` out), and a restore upserts its rows.
- Migrations 001–009. `StateDB.write_many` (one transaction), `fetch_all`, and the run-once marks' `has_mark` and `mark_statement`; `tests/conftest.py`'s `db` fixture and `as_schema()`.
- `tests/fixtures/latency/doze-replay-2026-10-04.json` and `doze-replay-2026-10-05.json`: the spike's replies from lamps a–d in relative times, `{"about", "beacon_ms", "lights": {label: {"expect", "replies": [[arrived_s, rtt_ms], ...]}}}`.

**Execution:** /executing-plans in a new worktree, `~/code/.worktrees/dj-ledfx/light-sync-build`, on branch `feature/light-sync`, from `origin/master` after the docs PR with the spec and this plan has merged (Before Task 1). Tasks 1–8 need no one. After Task 8 opens the PR, /executing-plans' own final review of the whole branch runs: fix every finding it raises and push the fixes to the PR. Then stop. Task 9, on the lamps, is the owner's.

**How to read the code.** A new file is given whole after "Create". A change to an existing file is a unified diff, in a `diff` block, against the file as master at `1d6ed22` and the earlier tasks leave it; apply the blocks in the order given. Save a block to a file and run `git apply` on it (`git apply /tmp/ls-step.diff`), or make the same edit by hand. If master has moved past `1d6ed22` and a block no longer applies, make the edit by hand: its hunks say where. Every block was applied, and every count below measured, on a copy of `1d6ed22` with the docs; a newer master may add tests.

---


## Global Constraints

Every task's requirements include these. Quotes are verbatim from the spec.

- Success (§1): "On the lamps, the branch's build alone, with no test patches, does what spike runs 7 and 8 did." "In that run the log names the two dozing lamps as dozing within 20 s of the start, and no other light." "On both recordings (§9), the doze check calls a and b dozing and c and d awake." "A light's latency follows a step in its round trips within 5 s. The first look after a restart starts each light at the latency it last had."
- The doze check (§5): "The last 40 round trips that counted, those that landed while the light streamed. Each is kept with its arrival, on the tracker's clock." Over them, "once there are at least 10", z = n·R² "of the arrivals' phases in a 102.4 ms cycle" and the median. "a light turns dozing when z ≥ 7 and the median is at least 50 ms"; "it stays dozing while z ≥ 2 and the median is at least 50 ms"; "otherwise it is awake. A light starts awake, or in the mode it had last (§7)."
- Latency (§5): "The strategy is fed a dozing light's whole round trip, and half of an awake light's. When the mode changes, the strategy restarts from the round trips the tracker holds, at the new share, so the latency is right at once. A `static` strategy ignores round trips, as it does now." "Each change of mode is logged at INFO, with z and the median."
- Probes (§4): "Each round waits a random 75–125% of `devices.govee.probe_interval_s`, which defaults to 0.5 s." It asks "each registered lamp that streams for its status, unless a status query to that lamp is already in flight". "Only a lamp that streams is probed." "Nothing is probed while another program holds UDP 4002 (`can_receive`)". "The monitor's reads every 5 s go on, and their round trips count the same." "LIFX echo probes stay at every 2 s." `probe_interval_s` "must be positive, and its default drops from 5 s to 0.5 s."
- Horizon (§6): "`HORIZON_CAP_S` goes from 120 ms to 500 ms." "Brightness is applied at send, so a brightness change isn't delayed."
- Memory (§7): "`stable_id`, `latency_ms` (the strategy's latency, before display and offset), `dozing` and `updated_at`." "A task writes every 30 s, and once at shutdown. It writes the rows of lights whose mode changed, or whose latency moved by more than 5 ms, since their row was last written." "A light with no row starts at the config's seed, awake." "Not in backups." A reset "restarts it from the latency and mode it had, not from the config's seed. It drops the round trips the tracker held".
- Settings (§8): `_load_config_from_db` "builds `DevicesConfig` too, from sections `devices.openrgb`, `devices.lifx` and `devices.govee`, through `filter_fields` like the other sections." The run-once step "deletes the database's `devices.*` rows. It uses `has_mark` and `mark_statement`, with the mark `devices_config_reset`." "A setting saved after the step is kept". "The other strategies stay selectable." The owner's decisions of 2026-10-06 (rulings 20 and 22): `PUT /api/config` saves device settings to state.db as config.toml's migration writes them, so one changed in the app survives a restart; and a restored backup brings back whatever device settings it holds, old ones included, and they apply.
- Unchanged (§3): "each light's rate (a Govee razer lamp at 30 a second), the send loops, a frame's moment (`now + latency`), the ring and its reads."
- Out of scope (§10): wake-timed sends, rate back-off, a view of each light's link (the web app shows none of this until a design handoff does, #37), calibration and lining up with the music (#35), probing OpenRGB, other beacon intervals, router tuning.
- The web API doesn't change. `PUT /api/config` saves more (Task 6) with the same request and response, and `LightLatency.estimated` gets a new comment and nothing else, so there's no `api:types` step and `tests/web/test_openapi_types.py` stays green.
- The repo is public: no LAN address, MAC, light name, model number, room name or SSID in code, tests, commits, the PR or this plan. A test address is `127.0.0.1`, a test Govee device `test-lamp`, and the recordings' lamps are `a` to `d`. The app's own log names lights (the doze and recall lines); that log stays on the machine, and the PR gives counts.
- Code style (CLAUDE.md): `uv` for everything, loguru for logging, mypy strict, device I/O async on the one event loop, event-bus callbacks non-blocking. A migration's comments hold no `;` (the SQL is split on it), a row is upserted with `INSERT ... ON CONFLICT DO UPDATE`, never `INSERT OR REPLACE`, and cancelled tasks are awaited with `asyncio.wait`, not `gather`.
- Gates, per task before its commit: `uv run ruff check .` clean, `uv run ruff format --check .` with no findings, `uv run mypy src/` no worse than the baseline (16 errors in 4 files on `1d6ed22`), and `uv run pytest -q` green. During a task, run only its test files; run the full gate once, before the commit. If `ruff format --check` names a file the task touched, run `uv run ruff format` on that file only.
- The live system: no task before Task 9 touches the deployed `dj-ledfx-app-1`, UDP 4002 or a real light. Every test runs on fakes and loopback. Task 9 is the owner's, each step with the owner's go.
- No code-architect review or `/simplify` runs as part of this plan. The run ends with /executing-plans' own final review.

## Spec Rulings

The spec is silent, or loose against the code, in a few places. These rulings are what the plan builds. Task 8 lists them in the PR. Rulings 20 and 22 carry the owner's decisions of 2026-10-06.

1. **The run-once step runs before config.toml's migration.** §8 puts it "before the config is read". It runs before `migrate_from_toml` too, so a new database still takes config.toml's device tables, which the step would otherwise delete at once.
2. **Device settings count as a config.** `_load_config_from_db` returns None only while state.db holds none of the app's sections, and the three device sections now count: a database holding only device settings (a config.toml with only device tables, migrated) applies them.
3. **A device setting the config refuses** (a rate of 0, a strategy it doesn't know, text where a number goes) logs one WARNING with the reason, and every kind of light runs on its defaults. The other sections load as before, and an error in one of them still stops the start, as it did. A stored row the app can't use mustn't stop it starting, as the engine spec's §8 has it for a bad map or look.
4. **The step logs what it drops**, in one INFO line naming each `section.key`, and logs nothing when there were none.
5. **A probe waits 1 s for its reply** (`PROBE_TIMEOUT_S`), asked once. The monitor's reads keep their own timeout and two tries. A dozing lamp's round trips ran to about 0.7 s at p90 (§10), and a probe that times out costs only its round trip.
6. **A lamp with a status query in flight is skipped for that round.** That query's reply is timed and counts anyway, and `query_status` already shares a query in flight between its callers, so none is doubled (§4).
7. **`streaming=` is a required keyword** of Govee's `register_device`, as it is of LIFX's, so no lamp is registered without saying when it streams.
8. **The loop starts once lamps are found**: after a scan or a `connect_known` with results, `start_probing(config.devices.govee.probe_interval_s)`. Starting it again keeps the one loop, and `close()` ends it and every probe in flight.
9. **A tracker carries its light's name** (`name=`, "A light" by default), for its log lines. The Govee and LIFX backends pass the device's name. OpenRGB's trackers keep the default: nothing probes them, so they never log a mode.
10. **A strategy restarts from a given latency.** `ProbeStrategy.reset(latency_ms=None)`: given a latency, the strategy holds it until its next sample; given none, it starts from its seed, as `reset()` did. A static strategy keeps its configured latency either way.
11. **The restart at a change of mode replays every held round trip** (up to 40), oldest first, into the reset strategy at the new share; a windowed strategy keeps the newest of them.
12. **A reset is a recall of what the tracker has now.** The latency and the mode stay; the held round trips and the last send go, so the doze check starts again from the next 10 and the light isn't `streaming` until a frame goes out.
13. **A recalled latency is unmeasured.** `measured` stays false after a recall or a reset until a round trip measured while the light streams lands. So the API's `estimated` is true for a remembered latency (the contract's comment says so), and a light that hasn't streamed since it came online never writes its row back.
14. **Where the memory is recalled.** Only in the discovery orchestrator's `_merge`, for a new light and for a ghost promoted, before it's added. A light set up again for an output change (`_play`) keeps its live tracker. The rows are read once, at start, and never deleted. The table has no foreign key, so a device row deleted before a write can't fail it.
15. **Only measured trackers are written**, so a seed or a recalled latency is never written as if measured. The last write runs as the writer is cancelled at shutdown, before state.db closes. A write that fails is logged at ERROR, and the next one retries.
16. **The recall is logged** at INFO: "<light> starts from the latency it last had: N ms, dozing" (or "awake").
17. **The config files.** `config.toml`'s `probe_interval_s` becomes 0.5 (the deployed app doesn't read it: its state.db holds the config). `config.example.toml` gains a `[devices.govee]` table, and its LIFX table follows the code's defaults (windowed median, 10 ms), since a config made from it now applies.
18. **The recordings check every strategy but static** (windowed median, windowed mean and EMA), since §8 keeps them selectable: a dozing lamp ends between its round trips' quartiles under each.
19. **The horizon tests** put the light past the cap at 600 ms.
20. **`PUT /api/config` saves the device settings it's sent** (the owner's decision), each in its kind's section of state.db (`devices.govee`) as JSON, as config.toml's migration writes them, so one changed in the app applies from the next start. It saves only the device settings a request names, as the migration writes only what the file holds (a ruling): preview only's switch names none, so it pins no default (a default the code changes later still reaches each setting no one set) and doesn't write over a restored backup's settings before they apply, while the old UI's Config page sends back the whole config it read, so its Save saves every device setting it shows. The flat sections are still saved whole. A value the config refuses gets a 400 and saves nothing. `POST /api/config/import` still saves nothing to state.db, as before.
21. **The README follows CLAUDE.md** (Task 7): its horizon and latency lines are stale once this lands, though §11 doesn't list it.
22. **A restored backup's device settings apply** (the owner's decision): a backup brings back whatever `devices.*` rows it holds, old ones included, and they apply from the next start (a restore leaves the running config alone, as before). One exported before light sync brings back the rows the run-once step dropped, and the step doesn't drop them again: it has run, and backups carry no run-once marks. No code changes for this; CLAUDE.md's Gotchas say it (Task 7).

## Review Focus

These are the five inputs the spec implies that are most likely to bite someone using this, most likely first. Each has a test in the task that owns the code.

1. **The deployed database's first start.** It holds `devices.*` rows that never applied (EMA over 60, Govee at 40 a second, a 50 ms LIFX seed, probes every 5 s) and no `link_memory`. That start drops the rows once and logs them, runs on the defaults, creates the table and starts every light at its seed, awake. A setting saved after applies from the next start, one saved in the app included (`PUT /api/config` saves only the device settings it names, and nothing it refuses), a new database still takes config.toml's device tables, and a stored device setting the config refuses leaves the lights on their defaults with a warning, never stopping the app. Tests: Task 5, `test_a_database_from_before_light_sync_gains_the_table`; Task 6, `test_the_old_device_settings_go_once_and_a_setting_saved_after_stays`, `test_device_settings_the_config_refuses_leave_the_lights_on_their_defaults`, `test_device_settings_no_start_applied_go_and_one_saved_after_applies`, `test_a_new_database_takes_config_toml_s_device_settings`, `test_a_device_setting_saved_in_the_app_applies_from_the_next_start`, `test_a_save_that_names_no_device_setting_pins_no_default` and `test_a_device_setting_the_config_refuses_saves_nothing`.
2. **An awake light with slow or ragged round trips** (a busy access point, a LIFX light, a lamp far from the router) is never called dozing, or its latency would double and it would run early. Replies at random moments, replies spread round the cycle at 300 ms, and bunched replies at 25 ms all stay awake, and the recordings' c and d never doze. Tests: Task 1, `test_replies_at_random_moments_are_awake`, `test_replies_spread_round_the_cycle_are_awake` and `test_bunched_replies_with_a_25_ms_median_are_awake`; Task 2, `test_a_and_b_turn_dozing_and_stay_dozing_and_c_and_d_never_do`.
3. **A lamp the app can't hear**: Home Assistant holding UDP 4002, a lamp switched off at the wall mid-look, a reply that never comes. Nothing is probed while the app is deaf, a silent lamp holds up no round, a query in flight is never doubled, and the loop and its probes stop at close. Tests: Task 3, `test_nothing_is_probed_while_another_program_holds_the_reply_port`, `test_a_silent_lamp_holds_up_no_round`, `test_a_query_in_flight_is_shared_never_doubled` and `test_the_loop_and_its_probes_stop_at_close`.
4. **A light that comes and goes**: it drops out and comes back, comes back as a ghost promoted after a restart, has its output changed, or is new. It keeps or recalls its latency and mode, a stale latency is never written over a measured one, and a new light starts at its seed, awake. Tests: Task 2, `test_a_reset_keeps_the_latency_and_the_mode_and_drops_the_round_trips_held` and `test_recall_sets_the_latency_and_the_mode`; Task 5, `test_a_lamp_taken_in_starts_from_the_latency_and_mode_it_last_had` (new and ghost), `test_a_lamp_with_no_row_starts_at_the_config_s_seed_awake`, `test_an_output_change_keeps_the_latency_the_lamp_has_now` and `test_a_light_not_measured_since_it_came_online_writes_nothing`.
5. **Shutdown, and a write that fails.** The writer writes once more as it's cancelled at shutdown, before state.db closes; a failed write is logged and retried, never stopping the app; backups leave the table out. Tests: Task 5, `test_the_writer_writes_every_period_and_once_more_at_shutdown`, `test_a_write_that_fails_is_logged_and_the_next_one_retries` and `test_backups_leave_the_link_memory_out`.

---

## File Structure

New backend files (paths under `src/dj_ledfx/`):

| File | Responsibility |
|---|---|
| `latency/doze.py` | The doze check: `DozeCheck` (the last 40 round trips with their arrivals, the mode and its two thresholds), `DozeReading` (z, the median, the count) and `rayleigh_z()` |
| `latency/memory.py` | Each light's link memory: `LinkMemory` (`load()`, `recall()`, `save()` and the writer, `run()`), `Link`, `LINK_MEMORY_EVERY_S` and `MOVED_MS` |
| `persistence/migrations/010_link_memory.sql` | The `link_memory` table |

Modified: `latency/{strategies,tracker}.py` (Task 2), `devices/govee/{backend,transport}.py` (Tasks 2 and 3), `devices/lifx/discovery.py` and `web/contract.py` (Task 2), `config.py`, `config.toml` and `config.example.toml` (Task 3), `zones/runtime.py` (Task 4), `devices/discovery.py` (Task 5), `main.py` (Tasks 5 and 6), `web/router_config.py` (Task 6), `CLAUDE.md` and `README.md` (Task 7).

Shared test helpers: `tests/doze_fakes.py` (new, Task 1): reply moments for the doze check (`on_beat()`, `bunched()`, `spread()`, `half_bunched()`, `random_moments()`, from `START`); Task 2 adds `SEED_MS` and `Lamp`, a tracker named `test-lamp` on a fake clock whose light streams.

New test files: `tests/latency/test_doze.py` (Task 1), `tests/latency/test_doze_replay.py` (Task 2), `tests/latency/test_memory.py` (Task 5), and `tests/test_device_settings.py` and `tests/web/test_config_device_settings.py` (Task 6).

---

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/light-sync /home/anirudhlath/code/.worktrees/dj-ledfx/light-sync-build origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/light-sync-build
cd "$W"
test -f docs/superpowers/plans/2026-10-06-light-sync.md && test -f docs/superpowers/specs/2026-10-04-light-sync-design.md && echo "plan and spec present"
ls tests/fixtures/latency/
grep -n "HORIZON_CAP_S = 0.12" src/dj_ledfx/zones/runtime.py
ls src/dj_ledfx/persistence/migrations/ | tail -1
git log --oneline -3 origin/master
```

Expected: `plan and spec present`; the two recordings, `doze-replay-2026-10-04.json` and `doze-replay-2026-10-05.json`; the 0.12 cap; and `009_placement_source.sql` the last migration. If anything differs (a migration 010 already there, say), stop and tell the owner. Every command in this plan runs from `$W`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
```

Without the `web` extra, the web tests skip silently and mypy reports dozens of extra errors. No step here needs the web app's packages: the API doesn't change.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tee /tmp/ls-baseline-mypy.txt | tail -1
```

Expected on `1d6ed22` with the docs: `1819 passed, 1 skipped, 42 deselected`; ruff clean and `331 files already formatted`; `Found 16 errors in 4 files (checked 151 source files)`. Every gate compares with these. If ruff isn't clean, or the counts are far off, tell the owner before starting.

---


### Task 1: The doze check

`latency/doze.py` tells a dozing light from an awake one by when its replies land (spec §5). It holds the last 40 round trips with their arrival times and works out z and the median; it's pure, with no clock of its own, and Task 2 puts it in the tracker. `tests/doze_fakes.py` makes the reply moments its tests feed it: at one phase of the beacon cycle, bunched near it, spread round it, half at one phase, or at random.

**Files:**
- Create: `src/dj_ledfx/latency/doze.py`, `tests/doze_fakes.py`
- Test: `tests/latency/test_doze.py` (new)

**Interfaces:**
- Consumes: nothing new.
- Produces (`dj_ledfx.latency.doze`):
  - `BEACON_S = 0.1024`, `KEPT = 40`, `MIN_REPLIES = 10`, `DOZE_Z = 7.0`, `STAY_Z = 2.0`, `DOZE_MEDIAN_MS = 50.0`.
  - `DozeReading(z: float, median_ms: float, replies: int)`, frozen.
  - `rayleigh_z(arrivals: Sequence[float], cycle_s: float = BEACON_S) -> float`.
  - `DozeCheck(*, dozing: bool = False)`: `dozing: bool`; `round_trips: list[float]`, oldest first; `reading() -> DozeReading | None` (None under `MIN_REPLIES`); `add(arrived_s: float, rtt_ms: float) -> bool`, True when the mode changed.
- Produces (`tests/doze_fakes.py`): `START = 1000.0`, `PHI`, and the moments `on_beat(k)`, `bunched(k)`, `spread(k)`, `half_bunched(k)` and `random_moments(seed, count=40)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/doze_fakes.py`:

```python
"""Replies for the doze check, on a fake clock: landing at a dozing light's wakes (`on_beat`,
`bunched`), spread evenly round the beacon cycle (`spread`), half at the wakes
(`half_bunched`), or at random moments (`random_moments`)."""

from __future__ import annotations

import math
import random

from dj_ledfx.latency.doze import BEACON_S

START = 1000.0  # when the first reply lands, on the fake clock
PHI = (math.sqrt(5) - 1) / 2  # a phase step that never repeats, so phases spread evenly


def on_beat(k: int) -> float:
    """When the k-th reply lands from a light that answers at every fifth wake."""
    return START + 5 * BEACON_S * k


def bunched(k: int) -> float:
    """As on_beat, give or take 3 ms."""
    return on_beat(k) + 0.003 * ((k % 3) - 1)


def spread(k: int) -> float:
    """About every fifth beacon, each reply at a new phase: spread evenly round the cycle."""
    return START + (5 * k + (k * PHI) % 1.0) * BEACON_S


def half_bunched(k: int) -> float:
    """Every other reply at the wake, the rest a quarter or three quarters of the way round:
    bunched less than a dozing light's replies, and more than chance's."""
    if k % 2 == 0:
        return on_beat(k)
    return START + (5 * k + (0.25 if (k // 2) % 2 == 0 else 0.75)) * BEACON_S


def random_moments(seed: int, count: int = 40) -> list[float]:
    """Replies 0.375–0.625 s apart at random, as the Govee probe loop's waits put them."""
    rng = random.Random(seed)
    moments: list[float] = []
    arrived = START
    for _ in range(count):
        arrived += rng.uniform(0.375, 0.625)
        moments.append(arrived)
    return moments
```

Create `tests/latency/test_doze.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

import pytest
from doze_fakes import START, bunched, half_bunched, on_beat, random_moments, spread

from dj_ledfx.latency.doze import (
    BEACON_S,
    DOZE_Z,
    KEPT,
    STAY_Z,
    DozeCheck,
    rayleigh_z,
)


def fed(check: DozeCheck, arrivals: Iterable[float], rtt_ms: float) -> list[bool]:
    """Whether the check calls the light dozing after each reply."""
    modes: list[bool] = []
    for arrived in arrivals:
        check.add(arrived, rtt_ms)
        modes.append(check.dozing)
    return modes


def test_z_is_n_at_one_phase_and_near_0_for_phases_spread_evenly() -> None:
    assert rayleigh_z([START + BEACON_S * k for k in range(12)]) == pytest.approx(12.0)
    evenly = [START + BEACON_S * (k + k / 12) for k in range(12)]  # a twelfth further each
    assert rayleigh_z(evenly) == pytest.approx(0.0, abs=1e-9)
    assert rayleigh_z([]) == 0.0


def test_replies_bunched_at_the_wakes_with_a_60_ms_median_are_dozing_at_the_10th() -> None:
    check = DozeCheck()
    assert fed(check, map(bunched, range(12)), 60.0) == [False] * 9 + [True] * 3
    reading = check.reading()
    assert reading is not None
    assert reading.z >= DOZE_Z and reading.median_ms == 60.0 and reading.replies == 12


def test_replies_bunched_at_every_second_beacon_are_dozing_too() -> None:
    every_other = [START + 2 * BEACON_S * 3 * k for k in range(10)]  # 204.8 ms wakes
    assert fed(DozeCheck(), every_other, 60.0) == [False] * 9 + [True]


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_replies_at_random_moments_are_awake(seed: int) -> None:
    assert not any(fed(DozeCheck(), random_moments(seed), 60.0))


def test_replies_spread_round_the_cycle_are_awake() -> None:
    assert not any(fed(DozeCheck(), map(spread, range(KEPT)), 300.0))


def test_bunched_replies_with_a_25_ms_median_are_awake() -> None:
    assert not any(fed(DozeCheck(), map(bunched, range(KEPT)), 25.0))


def test_a_dozing_light_stays_dozing_while_z_is_at_least_2() -> None:
    """Replies half at the wakes bunch less than an awake light needs to turn dozing, and
    as much as a dozing light needs to stay dozing."""
    arrivals = [half_bunched(k) for k in range(20)]
    zs = [rayleigh_z(arrivals[:n]) for n in range(10, 21)]
    assert all(STAY_Z <= z < DOZE_Z for z in zs)
    assert not any(fed(DozeCheck(), arrivals, 60.0))  # an awake light stays awake
    assert all(fed(DozeCheck(dozing=True), arrivals, 60.0))  # and a dozing one dozing


def test_a_dozing_light_turns_awake_when_its_median_drops_under_50_ms() -> None:
    check = DozeCheck()
    assert fed(check, map(on_beat, range(20)), 60.0)[-1]
    quicker = fed(check, map(on_beat, range(20, 40)), 20.0)  # bunched as much as before
    assert quicker == [True] * 19 + [False]  # 20 of its 40 at 20 ms: a median of 40 ms


def test_a_dozing_light_turns_awake_when_its_replies_stop_bunching() -> None:
    check = DozeCheck()
    assert fed(check, map(on_beat, range(20)), 60.0)[-1]
    later = fed(check, map(spread, range(20, 60)), 60.0)
    turned = later.index(False)
    assert turned > 10 and not any(later[turned:])  # it stays awake
    reading = check.reading()
    assert reading is not None and reading.z < STAY_Z


def test_the_check_reads_nothing_under_10_round_trips_and_holds_the_last_40() -> None:
    check = DozeCheck(dozing=True)
    for k in range(9):
        assert check.add(spread(k), 30.0) is False
    assert check.reading() is None and check.dozing  # too few to change the mode
    for k in range(9, 50):
        check.add(spread(k), float(k))
    assert check.round_trips == [float(k) for k in range(10, 50)]
    reading = check.reading()
    assert reading is not None and reading.replies == KEPT
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/latency/test_doze.py -q`
Expected: FAIL: a collection error, `ModuleNotFoundError: No module named 'dj_ledfx.latency.doze'`.

- [ ] **Step 3: Write the doze check**

Create `src/dj_ledfx/latency/doze.py`:

```python
"""The doze check (light-sync spec §5): a light whose Wi-Fi dozes, told by when its replies
land. The access point holds a dozing light's packets until the light wakes, at a beacon, so
its replies bunch at one phase of the beacon cycle, and its round trips run long: a query
waits for a wake, on average half a beacon, even with nothing queued."""

from __future__ import annotations

import math
import statistics
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

# The beacon interval of every access point here, 100 TU. A light that wakes at every
# second or fourth beacon bunches in this cycle too; behind an access point whose interval
# isn't a multiple of 100 TU, a dozing light isn't recognised (spec §10).
BEACON_S = 0.1024
KEPT = 40  # the round trips the check holds: the newest that counted
MIN_REPLIES = 10  # with fewer, a light keeps the mode it has
DOZE_Z = 7.0  # an awake light turns dozing when its replies bunch this much,
STAY_Z = 2.0  # and a dozing light stays dozing while they bunch this much,
DOZE_MEDIAN_MS = 50.0  # either way only with a median round trip at least this long


@dataclass(frozen=True, slots=True)
class DozeReading:
    """What the check works out over the round trips it holds."""

    z: float  # the Rayleigh statistic of their arrivals' phases in a beacon cycle
    median_ms: float  # their median
    replies: int  # how many there are


def rayleigh_z(arrivals: Sequence[float], cycle_s: float = BEACON_S) -> float:
    """The Rayleigh statistic n·R² of the arrivals' phases in a cycle of cycle_s, R being
    their mean resultant length: near 0 for phases spread evenly, n for phases all at one
    point. For random arrivals, the chance that z ≥ k is about e^(−k)."""
    if not arrivals:
        return 0.0
    cos_sum = sin_sum = 0.0
    for arrived in arrivals:
        angle = math.tau * ((arrived / cycle_s) % 1.0)
        cos_sum += math.cos(angle)
        sin_sum += math.sin(angle)
    return (cos_sum * cos_sum + sin_sum * sin_sum) / len(arrivals)


class DozeCheck:
    """Whether a light's Wi-Fi dozes, from its last KEPT round trips and when each landed.
    An awake light turns dozing when z reaches DOZE_Z, and a dozing light stays dozing
    while z is at least STAY_Z, either way only while the median round trip is at least
    DOZE_MEDIAN_MS. With fewer than MIN_REPLIES round trips, the light keeps its mode."""

    def __init__(self, *, dozing: bool = False) -> None:
        self._dozing = dozing
        self._kept: deque[tuple[float, float]] = deque(maxlen=KEPT)

    @property
    def dozing(self) -> bool:
        return self._dozing

    @property
    def round_trips(self) -> list[float]:
        """The round trips held, in ms, oldest first."""
        return [rtt for _, rtt in self._kept]

    def reading(self) -> DozeReading | None:
        """z and the median over the round trips held; None with fewer than MIN_REPLIES."""
        if len(self._kept) < MIN_REPLIES:
            return None
        z = rayleigh_z([arrived for arrived, _ in self._kept])
        return DozeReading(z, statistics.median(self.round_trips), len(self._kept))

    def add(self, arrived_s: float, rtt_ms: float) -> bool:
        """A round trip that landed at arrived_s, on the tracker's clock. True when it
        changed the light's mode."""
        self._kept.append((arrived_s, rtt_ms))
        reading = self.reading()
        if reading is None:
            return False
        bunched = reading.z >= (STAY_Z if self._dozing else DOZE_Z)
        dozing = bunched and reading.median_ms >= DOZE_MEDIAN_MS
        changed = dozing != self._dozing
        self._dozing = dozing
        return changed
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/latency/test_doze.py -q`
Expected: PASS (12 tests).

- [ ] **Step 5: Run the gate**

```bash
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: ruff clean, no format findings, mypy's 16 errors as at the baseline, and `1831 passed, 1 skipped, 42 deselected`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/latency/doze.py tests/doze_fakes.py tests/latency/test_doze.py
git commit -m "feat(latency): the doze check, from when a light's replies land"
```

---


### Task 2: The tracker's share of the round trip, reset and recall

The tracker holds a `DozeCheck` and feeds its strategy the whole round trip of a dozing light and half of an awake light's; when the mode changes, it restarts the strategy from the held round trips at the new share and logs the change (spec §5). `recall()` starts a tracker from a latency and mode the light had before (Task 5 uses it), and `reset()`, for a light that comes back, now keeps what the light had (§7, rulings 10–13). Strategies learn to restart from a given latency. Govee's and LIFX's trackers carry their light's name for the log (ruling 9). The two recordings check it all against the spike (§9.2).

**Files:**
- Modify: `src/dj_ledfx/latency/strategies.py`, `src/dj_ledfx/latency/tracker.py`, `src/dj_ledfx/devices/govee/backend.py`, `src/dj_ledfx/devices/lifx/discovery.py`, `src/dj_ledfx/web/contract.py` (a comment)
- Test: `tests/doze_fakes.py`, `tests/latency/test_tracker.py`, `tests/latency/test_strategies.py`, `tests/scheduling/test_scheduler.py`, `tests/devices/govee/test_backend.py`, `tests/devices/lifx/test_discovery.py`; `tests/latency/test_doze_replay.py` (new)

**Interfaces:**
- Consumes: Task 1's `DozeCheck`.
- Produces:
  - `ProbeStrategy.reset(self, latency_ms: float | None = None) -> None`, on every strategy (`StaticLatency` ignores it).
  - `LatencyTracker(strategy, manual_offset_ms=0.0, *, display_ms=0.0, clock=time.monotonic, name="A light")`, with `name: str`, `link_latency_ms: float` (the strategy's latency, before the display delay and the offset), `dozing: bool`, `recall(latency_ms: float, dozing: bool) -> None` and `reset()`, which keeps the latency and the mode. `measured` is False after either until a round trip measured while the light streams lands.
  - `tracker_for(cfg, *, seed_ms=None, display_ms=0.0, name="A light")`.
  - `tests/doze_fakes.py`: `SEED_MS = 100.0` and `Lamp(strategy=None, **kwargs)`, with `now`, `tracker` and `reply(arrived, rtt_ms) -> float`, which sends a frame and lands a reply at `arrived` and returns the link latency after it.

- [ ] **Step 1: Write the failing tests**

In `tests/doze_fakes.py`:

```diff
--- a/tests/doze_fakes.py
+++ b/tests/doze_fakes.py
@@ -1,15 +1,20 @@
 """Replies for the doze check, on a fake clock: landing at a dozing light's wakes (`on_beat`,
 `bunched`), spread evenly round the beacon cycle (`spread`), half at the wakes
-(`half_bunched`), or at random moments (`random_moments`)."""
+(`half_bunched`), or at random moments (`random_moments`); and `Lamp`, a tracker on that
+clock whose light streams."""
 
 from __future__ import annotations
 
 import math
 import random
+from typing import Any
 
 from dj_ledfx.latency.doze import BEACON_S
+from dj_ledfx.latency.strategies import LATENCY_WINDOW, ProbeStrategy, WindowedMedianLatency
+from dj_ledfx.latency.tracker import LatencyTracker
 
 START = 1000.0  # when the first reply lands, on the fake clock
+SEED_MS = 100.0  # a Govee lamp's seed: its config's latency_ms
 PHI = (math.sqrt(5) - 1) / 2  # a phase step that never repeats, so phases spread evenly
 
 
@@ -45,3 +50,25 @@ def random_moments(seed: int, count: int = 40) -> list[float]:
         arrived += rng.uniform(0.375, 0.625)
         moments.append(arrived)
     return moments
+
+
+class Lamp:
+    """A tracker on a fake clock, named test-lamp, whose light streams: a frame goes out as
+    each reply lands. A windowed median of 9 seeded at SEED_MS unless a strategy is given;
+    other keyword arguments go to the tracker (display_ms, manual_offset_ms)."""
+
+    def __init__(self, strategy: ProbeStrategy | None = None, **kwargs: Any) -> None:
+        self.now = START
+        self.tracker = LatencyTracker(
+            strategy or WindowedMedianLatency(LATENCY_WINDOW, SEED_MS),
+            clock=lambda: self.now,
+            name="test-lamp",
+            **kwargs,
+        )
+
+    def reply(self, arrived: float, rtt_ms: float) -> float:
+        """A round trip that lands at arrived while the light streams; the latency after it."""
+        self.now = arrived
+        self.tracker.note_send()
+        self.tracker.update_rtt(rtt_ms)
+        return self.tracker.link_latency_ms
```

In `tests/latency/test_tracker.py`:

```diff
--- a/tests/latency/test_tracker.py
+++ b/tests/latency/test_tracker.py
@@ -1,3 +1,8 @@
+from typing import Any
+
+from doze_fakes import SEED_MS, START, Lamp, bunched, on_beat, spread
+from loguru import logger
+
 from dj_ledfx.latency.strategies import LATENCY_WINDOW, StaticLatency, WindowedMedianLatency
 from dj_ledfx.latency.tracker import STREAMING_WINDOW_S, LatencyTracker
 
@@ -53,7 +58,7 @@ def test_a_latency_is_measured_once_a_streaming_round_trip_lands() -> None:
     tracker.note_send()
     tracker.update_rtt(60.0)
     assert tracker.measured
-    tracker.reset()  # the light came back: its seed again
+    tracker.reset()  # the light came back: unmeasured until it streams again
     assert not tracker.measured
 
 
@@ -76,3 +81,92 @@ def test_a_light_streams_for_the_window_after_a_send() -> None:
     tracker.note_send()
     tracker.reset()
     assert not tracker.streaming
+
+
+def test_a_dozing_light_s_latency_is_its_whole_round_trip_from_the_10th_reply() -> None:
+    lamp = Lamp()
+    latencies = [lamp.reply(bunched(k), 240.0) for k in range(10)]
+    # Half until the check calls it dozing; then all of each round trip it holds, at once.
+    assert latencies == [120.0] * 9 + [240.0]
+    assert lamp.tracker.dozing and lamp.tracker.measured
+
+
+def test_an_awake_light_s_latency_is_half_its_round_trip() -> None:
+    lamp = Lamp()
+    assert [lamp.reply(spread(k), 30.0) for k in range(20)] == [15.0] * 20
+    assert not lamp.tracker.dozing
+
+
+def test_a_change_of_mode_restarts_the_latency_at_the_new_share() -> None:
+    """A light remembered dozing whose replies say it's awake: all of each round trip until
+    the check holds 10, then half of every one it holds."""
+    lamp = Lamp()
+    lamp.tracker.recall(30.0, dozing=True)
+    assert [lamp.reply(spread(k), 30.0) for k in range(10)] == [30.0] * 9 + [15.0]
+    assert not lamp.tracker.dozing
+
+
+def test_a_light_s_latency_follows_a_step_in_its_round_trips_within_5_s() -> None:
+    lamp = Lamp()
+    for k in range(20):
+        lamp.reply(START + 0.5 * k, 20.0)  # a reply every 0.5 s, as Govee's probes come
+    after = [lamp.reply(START + 0.5 * k, 80.0) for k in range(20, 30)]
+    assert after[:4] == [10.0] * 4 and after[4:] == [40.0] * 6  # 2 s after the step
+    assert not lamp.tracker.dozing
+
+
+def test_round_trips_that_land_while_the_light_is_idle_never_reach_the_doze_check() -> None:
+    lamp = Lamp()
+    for k in range(20):
+        lamp.now = bunched(k)
+        lamp.tracker.update_rtt(240.0)  # no frame went out: an idle light's round trip
+    assert (lamp.tracker.link_latency_ms, lamp.tracker.dozing) == (SEED_MS, False)
+    assert not lamp.tracker.measured
+
+
+def test_a_reset_keeps_the_latency_and_the_mode_and_drops_the_round_trips_held() -> None:
+    lamp = Lamp()
+    for k in range(10):
+        lamp.reply(bunched(k), 240.0)
+    lamp.tracker.reset()  # the light dropped out and came back
+
+    assert (lamp.tracker.link_latency_ms, lamp.tracker.dozing) == (240.0, True)
+    assert not lamp.tracker.measured and not lamp.tracker.streaming
+    # The check starts again: dozing through 9 awake replies, awake at the 10th.
+    assert [lamp.reply(spread(k), 30.0) for k in range(10, 20)] == [30.0] * 9 + [15.0]
+
+
+def test_recall_sets_the_latency_and_the_mode() -> None:
+    lamp = Lamp(display_ms=24.0)
+    lamp.tracker.recall(250.0, dozing=True)
+    assert lamp.tracker.link_latency_ms == 250.0
+    assert lamp.tracker.effective_latency_ms == 274.0  # its display delay on top, as ever
+    assert lamp.tracker.dozing and not lamp.tracker.measured
+
+
+def test_a_static_latency_ignores_round_trips_whatever_the_mode() -> None:
+    lamp = Lamp(StaticLatency(10.0))
+    lamp.tracker.recall(250.0, dozing=False)
+    for k in range(10):
+        lamp.reply(bunched(k), 240.0)
+    assert lamp.tracker.dozing  # the check still runs
+    assert (lamp.tracker.link_latency_ms, lamp.tracker.measured) == (10.0, False)
+
+
+def test_each_change_of_mode_is_logged_with_z_and_the_median() -> None:
+    records: list[Any] = []
+    sink = logger.add(lambda message: records.append(message.record), level="INFO")
+    try:
+        lamp = Lamp()
+        for k in range(10):
+            lamp.reply(on_beat(k), 240.0)
+        for k in range(10, 30):
+            lamp.reply(on_beat(k), 20.0)
+    finally:
+        logger.remove(sink)
+    assert [record["message"] for record in records] == [
+        "test-lamp dozes (z 10.0, median round trip 240 ms over 10): its latency is its whole"
+        " round trip",
+        "test-lamp is awake (z 21.0, median round trip 20 ms over 21): its latency is half its"
+        " round trip",
+    ]
```

In `tests/latency/test_strategies.py`:

```diff
--- a/tests/latency/test_strategies.py
+++ b/tests/latency/test_strategies.py
@@ -152,3 +152,22 @@ def test_every_strategy_a_config_names_can_be_made(name: str) -> None:
 def test_make_strategy_refuses_an_unknown_name() -> None:
     with pytest.raises(ValueError, match="Unknown latency strategy 'fastest'"):
         make_strategy("fastest", 10.0, LATENCY_WINDOW)
+
+
+@pytest.mark.parametrize("name", ["ema", "windowed_mean", "windowed_median"])
+def test_a_reset_to_a_latency_starts_there_until_the_next_sample(name: str) -> None:
+    strategy = make_strategy(name, 10.0, LATENCY_WINDOW)
+    for _ in range(5):
+        strategy.update(80.0)
+    strategy.reset(250.0)
+    assert strategy.get_latency() == 250.0
+    strategy.update(40.0)
+    assert strategy.get_latency() == 40.0  # the samples before the reset are gone
+    strategy.reset()
+    assert strategy.get_latency() == 10.0  # without a latency: the seed
+
+
+def test_a_static_latency_keeps_its_own_through_a_reset_to_another() -> None:
+    static = StaticLatency(10.0)
+    static.reset(250.0)
+    assert static.get_latency() == 10.0
```

In `tests/scheduling/test_scheduler.py`, the reconnection test now expects the reset to keep the latency (ruling 12):

```diff
--- a/tests/scheduling/test_scheduler.py
+++ b/tests/scheduling/test_scheduler.py
@@ -257,8 +257,10 @@ async def test_send_loop_reconnection_resets_tracker() -> None:
     scheduler.stop()
     await task
 
-    # After reset, strategy falls back to initial_value_ms (stale samples cleared)
-    assert strategy.get_latency() == 100.0
+    # The reset keeps the latency the light had, its samples gone (light-sync spec §7)
+    assert strategy.get_latency() == 250.0
+    strategy.update(10.0)
+    assert strategy.get_latency() == 10.0
 
 
 async def test_sending_never_moves_a_light_s_latency() -> None:
```

In `tests/devices/govee/test_backend.py`:

```diff
--- a/tests/devices/govee/test_backend.py
+++ b/tests/devices/govee/test_backend.py
@@ -86,6 +86,11 @@ async def _connect(
     return device
 
 
+async def test_a_lamp_s_tracker_carries_its_name_for_the_log(config: AppConfig) -> None:
+    device = await _connect(config)
+    assert device.tracker.name == device.adapter.device_info.name
+
+
 async def test_an_upright_razer_lamp_streams_each_segment_standing(
     monkeypatch: pytest.MonkeyPatch, config: AppConfig
 ) -> None:
```

In `tests/devices/lifx/test_discovery.py`:

```diff
--- a/tests/devices/lifx/test_discovery.py
+++ b/tests/devices/lifx/test_discovery.py
@@ -181,6 +181,13 @@ async def test_a_light_fades_over_the_engine_s_gap_when_the_engine_is_slower() -
     assert duration == fade == 31
 
 
+async def test_a_light_s_tracker_carries_its_name_for_the_log() -> None:
+    transport = FakeLifxTransport(product=1)
+    record = LifxDeviceRecord(mac=MAC, ip="127.0.0.1", port=56700, vendor=1, product=1)
+    device = await _backend(transport)._setup(record, AppConfig())
+    assert device is not None and device.tracker.name == device.adapter.device_info.name
+
+
 ECHO_REQUEST = 58
 
 
```

Create `tests/latency/test_doze_replay.py`:

```python
"""The light-sync spec's §9.2: each recording of four Govee lamps, fed to a tracker in order.
Lamps a and b doze; c and d don't (each light's `expect`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from doze_fakes import SEED_MS, Lamp

from dj_ledfx.latency.strategies import LATENCY_WINDOW, make_strategy

RECORDINGS = Path(__file__).parent.parent / "fixtures" / "latency"
DAYS = ["2026-10-04", "2026-10-05"]


def _lamps(day: str) -> dict[str, Any]:
    recording = json.loads((RECORDINGS / f"doze-replay-{day}.json").read_text())
    lamps: dict[str, Any] = recording["lights"]
    return lamps


@pytest.mark.parametrize("day", DAYS)
def test_a_and_b_turn_dozing_and_stay_dozing_and_c_and_d_never_do(day: str) -> None:
    for label, lamp in _lamps(day).items():
        replayed = Lamp()
        modes: list[bool] = []
        for arrived, rtt_ms in lamp["replies"]:
            replayed.reply(arrived, rtt_ms)
            modes.append(replayed.tracker.dozing)
        if lamp["expect"] == "dozing":
            assert True in modes, label
            turned = modes.index(True)
            assert turned < 20 and all(modes[turned:]), label  # by the 20th, for good
        else:
            assert not any(modes), label


@pytest.mark.parametrize("strategy", ["windowed_median", "windowed_mean", "ema"])
@pytest.mark.parametrize("day", DAYS)
def test_a_dozing_lamp_ends_between_its_round_trips_quartiles(day: str, strategy: str) -> None:
    for label, lamp in _lamps(day).items():
        if lamp["expect"] != "dozing":
            continue
        replayed = Lamp(make_strategy(strategy, SEED_MS, LATENCY_WINDOW))
        for arrived, rtt_ms in lamp["replies"]:
            replayed.reply(arrived, rtt_ms)
        low, high = np.percentile([rtt_ms for _, rtt_ms in lamp["replies"]], [25, 75])
        assert low <= replayed.tracker.link_latency_ms <= high, label
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/latency tests/devices/govee/test_backend.py tests/devices/lifx/test_discovery.py tests/scheduling/test_scheduler.py -q`
Expected: FAIL: `24 failed, 131 passed`, most with `TypeError: LatencyTracker.__init__() got an unexpected keyword argument 'name'` (the `Lamp` fake names its tracker), two with `TypeError: WindowedLatency.reset() takes 1 positional argument but 2 were given` and two with `AttributeError: 'LatencyTracker' object has no attribute 'name'`.

- [ ] **Step 3: Write the tracker's half**

In `src/dj_ledfx/latency/strategies.py`:

```diff
--- a/src/dj_ledfx/latency/strategies.py
+++ b/src/dj_ledfx/latency/strategies.py
@@ -16,7 +16,8 @@ OUTLIERS_TO_SHIFT = 3
 class ProbeStrategy(Protocol):
     def update(self, new_sample: float) -> None: ...
     def get_latency(self) -> float: ...
-    def reset(self) -> None: ...
+    # Forget the samples and start again from latency_ms, or from the seed without one.
+    def reset(self, latency_ms: float | None = None) -> None: ...
 
 
 class StaticLatency:
@@ -29,8 +30,8 @@ class StaticLatency:
     def get_latency(self) -> float:
         return self._latency
 
-    def reset(self) -> None:
-        pass
+    def reset(self, latency_ms: float | None = None) -> None:
+        pass  # it keeps the configured latency
 
 
 class EMALatency:
@@ -72,12 +73,10 @@ class EMALatency:
         return threshold > 0 and abs(sample - mean) > threshold
 
     def get_latency(self) -> float:
-        if not self._initialized:
-            return self._initial_value_ms
-        return self._value
+        return self._value  # before its first sample, the value it starts from
 
-    def reset(self) -> None:
-        self._value = self._initial_value_ms
+    def reset(self, latency_ms: float | None = None) -> None:
+        self._value = self._initial_value_ms if latency_ms is None else latency_ms
         self._initialized = False
         self._samples.clear()
         self._outliers = 0
@@ -104,9 +103,9 @@ class WindowedLatency(ABC):
     def get_latency(self) -> float:
         return self._latency
 
-    def reset(self) -> None:
+    def reset(self, latency_ms: float | None = None) -> None:
         self._window.clear()
-        self._latency = self._initial_value_ms
+        self._latency = self._initial_value_ms if latency_ms is None else latency_ms
 
 
 class WindowedMeanLatency(WindowedLatency):
```

In `src/dj_ledfx/latency/tracker.py`:

```diff
--- a/src/dj_ledfx/latency/tracker.py
+++ b/src/dj_ledfx/latency/tracker.py
@@ -4,6 +4,9 @@ import time
 from collections.abc import Callable
 from typing import Protocol
 
+from loguru import logger
+
+from dj_ledfx.latency.doze import DozeCheck
 from dj_ledfx.latency.strategies import ProbeStrategy, StaticLatency, make_strategy
 
 # A round trip that arrives within this long of a send was measured while the light streamed.
@@ -12,7 +15,10 @@ STREAMING_WINDOW_S = 0.5
 
 class LatencyTracker:
     """A light's latency: one-way network time from its strategy, plus the time the light
-    takes to show a frame it has (display_ms), plus the owner's offset."""
+    takes to show a frame it has (display_ms), plus the owner's offset. The doze check
+    (light-sync spec §5) says how much of a round trip is one way: all of a dozing light's,
+    whose frames wait for its wakes while its replies come straight back, and half of an
+    awake light's."""
 
     def __init__(
         self,
@@ -21,13 +27,21 @@ class LatencyTracker:
         *,
         display_ms: float = 0.0,
         clock: Callable[[], float] = time.monotonic,
+        name: str = "A light",
     ) -> None:
         self._strategy = strategy
         self._manual_offset_ms = manual_offset_ms
         self._display_ms = display_ms
         self._clock = clock
+        self._name = name
         self._last_send: float | None = None
         self._measured = False
+        self._doze = DozeCheck()
+
+    @property
+    def name(self) -> str:
+        """The light's name, for the log."""
+        return self._name
 
     @property
     def manual_offset_ms(self) -> float:
@@ -37,18 +51,30 @@ class LatencyTracker:
     def manual_offset_ms(self, value: float) -> None:
         self._manual_offset_ms = value
 
+    @property
+    def link_latency_ms(self) -> float:
+        """The strategy's latency: the network's part, before the display delay and the
+        offset. A light's link memory keeps it (spec §7)."""
+        return self._strategy.get_latency()
+
     @property
     def effective_latency_ms(self) -> float:
-        return self._strategy.get_latency() + self._display_ms + self._manual_offset_ms
+        return self.link_latency_ms + self._display_ms + self._manual_offset_ms
 
     @property
     def effective_latency_s(self) -> float:
         return self.effective_latency_ms / 1000.0
 
+    @property
+    def dozing(self) -> bool:
+        """Whether the doze check calls the light's Wi-Fi dozing."""
+        return self._doze.dozing
+
     @property
     def measured(self) -> bool:
         """Whether a round trip measured while the light streamed has landed since the last
-        reset. Until one has, the latency is the seed: the config's, or the type's heuristic."""
+        reset or recall. Until one has, the latency is the seed (the config's, or the type's
+        heuristic) or the one the light had before."""
         return self._measured
 
     @property
@@ -63,18 +89,50 @@ class LatencyTracker:
         self._last_send = self._clock()
 
     def update_rtt(self, rtt_ms: float) -> None:
-        """A probe's round trip. Half of it is the one-way latency, but only while the light
-        streams: an idle light's Wi-Fi dozes, and its round trips run long."""
+        """A probe's round trip, counted only while the light streams: an idle light's Wi-Fi
+        dozes, and its round trips run long. The strategy takes all of a dozing light's round
+        trip and half of an awake light's; when the doze check changes the light's mode, the
+        strategy starts again from the round trips the check holds, at the new share."""
         if not self.streaming:
             return
-        self._strategy.update(rtt_ms / 2.0)
+        if self._doze.add(self._clock(), rtt_ms):
+            self._log_mode()
+            self._strategy.reset()
+            for held in self._doze.round_trips:
+                self._strategy.update(held * self._share)
+        else:
+            self._strategy.update(rtt_ms * self._share)
         # A static latency ignores the sample: it stays the configured one.
         self._measured = not isinstance(self._strategy, StaticLatency)
 
+    def recall(self, latency_ms: float, dozing: bool) -> None:
+        """Start from a latency and mode the light had before (spec §7): the strategy's
+        latency_ms (a static strategy keeps its own), and its mode. The round trips held
+        go, so the doze check starts again from the next."""
+        self._strategy.reset(latency_ms)
+        self._doze = DozeCheck(dozing=dozing)
+        self._measured = False
+
     def reset(self) -> None:
-        self._strategy.reset()
+        """The light came back: it starts again from the latency and mode it has now."""
+        self.recall(self.link_latency_ms, self.dozing)
         self._last_send = None
-        self._measured = False
+
+    @property
+    def _share(self) -> float:
+        """How much of a round trip is one way."""
+        return 1.0 if self._doze.dozing else 0.5
+
+    def _log_mode(self) -> None:
+        reading = self._doze.reading()
+        assert reading is not None  # the mode changes only over enough round trips
+        if self._doze.dozing:
+            message = "{} dozes (z {:.1f}, median round trip {:.0f} ms over {}): its latency is"
+            message += " its whole round trip"
+        else:
+            message = "{} is awake (z {:.1f}, median round trip {:.0f} ms over {}): its latency"
+            message += " is half its round trip"
+        logger.info(message, self._name, reading.z, reading.median_ms, reading.replies)
 
 
 class LatencyConfig(Protocol):
@@ -91,11 +149,15 @@ class LatencyConfig(Protocol):
 
 
 def tracker_for(
-    cfg: LatencyConfig, *, seed_ms: float | None = None, display_ms: float = 0.0
+    cfg: LatencyConfig,
+    *,
+    seed_ms: float | None = None,
+    display_ms: float = 0.0,
+    name: str = "A light",
 ) -> LatencyTracker:
     """A device's tracker, as its kind's config says: the strategy it names, seeded at
     seed_ms (else the config's latency_ms), its window and offset, plus how long the light
-    takes to show a frame (display_ms)."""
+    takes to show a frame (display_ms). name is the light's, for the log."""
     seed = cfg.latency_ms if seed_ms is None else seed_ms
     strategy = make_strategy(cfg.latency_strategy, seed, cfg.latency_window_size)
-    return LatencyTracker(strategy, cfg.manual_offset_ms, display_ms=display_ms)
+    return LatencyTracker(strategy, cfg.manual_offset_ms, display_ms=display_ms, name=name)
```

In `src/dj_ledfx/devices/govee/backend.py`:

```diff
--- a/src/dj_ledfx/devices/govee/backend.py
+++ b/src/dj_ledfx/devices/govee/backend.py
@@ -177,7 +177,9 @@ class GoveeBackend(DeviceBackend):
         status reads time its round trips. Raises ConnectionError when it doesn't answer."""
         adapter = self._adapter(transport, record, config, output)
         await adapter.connect()
-        tracker = tracker_for(config.devices.govee, display_ms=adapter.display_ms)
+        tracker = tracker_for(
+            config.devices.govee, display_ms=adapter.display_ms, name=adapter.device_info.name
+        )
         return DiscoveredDevice(
             adapter=adapter,
             tracker=tracker,
```

In `src/dj_ledfx/devices/lifx/discovery.py`:

```diff
--- a/src/dj_ledfx/devices/lifx/discovery.py
+++ b/src/dj_ledfx/devices/lifx/discovery.py
@@ -157,7 +157,9 @@ class LifxBackend(DeviceBackend):
             return None
         if adapter is None:
             return None
-        tracker = tracker_for(config.devices.lifx, display_ms=adapter.display_ms)
+        tracker = tracker_for(
+            config.devices.lifx, display_ms=adapter.display_ms, name=adapter.device_info.name
+        )
         await adapter.connect()
         # Probed while it streams, its echoes timed for this tracker, once the orchestrator
         # takes it in
```

In `src/dj_ledfx/web/contract.py`, only a comment: a remembered latency is `estimated` too (ruling 13). The schema doesn't change.

```diff
--- a/src/dj_ledfx/web/contract.py
+++ b/src/dj_ledfx/web/contract.py
@@ -643,7 +643,9 @@ def _placed(home_map: HomeMap | None, target_id: str) -> dict[str, Any]:
 class LightLatency(ContractModel):
     measured_ms: float | None
     override_ms: float | None = None  # overrides move to PUT /lights/{id}/latency (F6)
-    estimated: bool  # nothing measured while it streamed since it came online: the seed
+    # Nothing measured while it streamed since it came online: the seed, or the latency it
+    # had before (its link memory, or before it dropped out).
+    estimated: bool
 
 
 class LightPart(ContractModel):
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/latency tests/devices/govee/test_backend.py tests/devices/lifx/test_discovery.py tests/scheduling/test_scheduler.py -q`
Expected: PASS (155 tests).

- [ ] **Step 5: Run the gate**

```bash
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: ruff clean, no format findings, mypy's 16 errors, and `1854 passed, 1 skipped, 42 deselected`. `tests/web/test_openapi_types.py` passes among them: the contract's change is a comment.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/latency src/dj_ledfx/devices/govee/backend.py src/dj_ledfx/devices/lifx/discovery.py src/dj_ledfx/web/contract.py tests/doze_fakes.py tests/latency tests/scheduling/test_scheduler.py tests/devices/govee/test_backend.py tests/devices/lifx/test_discovery.py
git commit -m "feat(latency): a dozing light's latency is its whole round trip; a reset keeps what the light had"
```

---


### Task 3: The Govee probe loop

`GoveeTransport.start_probing(interval_s)` runs a probe loop, as LIFX's transport does (spec §4): each round waits a random 75–125% of the interval, then asks each lamp that streams for its status through `query_status`, skipping a lamp with a query in flight (ruling 6) and asking nothing while the transport can't hear UDP 4002. The waits are injectable (`sleep=`, `rng=`), so the tests hold each wait and count what each round sends. The backend registers each lamp with its tracker's `streaming` and starts the loop once lamps are found (rulings 7 and 8). `probe_interval_s` is read now: 0.5 s by default, and it must be positive.

**Files:**
- Modify: `src/dj_ledfx/devices/govee/transport.py`, `src/dj_ledfx/devices/govee/backend.py`, `src/dj_ledfx/config.py`, `config.toml`, `config.example.toml`
- Test: `tests/devices/govee/test_transport.py`, `tests/devices/govee/test_backend.py`, `tests/test_config.py`, `tests/web/test_router_config.py`

**Interfaces:**
- Consumes: Task 2's `LatencyTracker.streaming` and `update_rtt`.
- Produces (`dj_ledfx.devices.govee.transport`):
  - `PROBE_SPREAD = (0.75, 1.25)`, `PROBE_TIMEOUT_S = 1.0`.
  - `GoveeTransport(clock=time.monotonic, *, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, rng: random.Random | None = None)`.
  - `register_device(record, rtt_callback, *, streaming: Callable[[], bool])`.
  - `start_probing(interval_s: float) -> None`: starts the loop unless one runs; `close()` cancels it and its probes.
- Produces (`dj_ledfx.config`): `GoveeConfig.probe_interval_s: float = 0.5`; `AppConfig` refuses one at or below 0 ("govee probe_interval_s must be positive").

- [ ] **Step 1: Write the failing tests**

In `tests/devices/govee/test_transport.py`, the round-trip tests register with `streaming=`, the test that pinned "no probe loop" goes, and `TestProbeLoop` holds each wait on a fake sleep:

```diff
--- a/tests/devices/govee/test_transport.py
+++ b/tests/devices/govee/test_transport.py
@@ -2,6 +2,8 @@ from __future__ import annotations
 
 import asyncio
 import json
+import random
+from collections.abc import Callable
 from unittest.mock import AsyncMock, MagicMock, patch
 
 import pytest
@@ -122,7 +124,7 @@ class TestRoundTrips:
         transport = GoveeTransport(clock=lambda: now[0])
         transport._send_transport = MagicMock()
         rtts: list[float] = []
-        transport.register_device(lamp_record(), rtt_callback=rtts.append)
+        transport.register_device(lamp_record(), rtt_callback=rtts.append, streaming=lambda: True)
         return transport, now, rtts
 
     async def test_a_status_reply_feeds_the_lamp_s_round_trip(self) -> None:
@@ -151,8 +153,131 @@ class TestRoundTrips:
         _reply(transport, STATUS)  # late, or sent to another program's query
         assert rtts == []
 
-    def test_there_is_no_probe_loop(self) -> None:
-        assert not hasattr(GoveeTransport, "start_probing")
+
+class _Waits:
+    """The probe loop's sleep: each wait is held until the test lets a round run."""
+
+    def __init__(self) -> None:
+        self.asked: list[float] = []  # how long each wait was
+        self._asleep = asyncio.Event()
+        self._wake: asyncio.Future[None] | None = None
+
+    async def __call__(self, seconds: float) -> None:
+        self.asked.append(seconds)
+        self._wake = asyncio.get_running_loop().create_future()
+        self._asleep.set()
+        await self._wake
+
+    async def round(self) -> None:
+        """End the wait the loop is in, and let its round run until it waits again."""
+        await self._asleep.wait()
+        self._asleep.clear()
+        assert self._wake is not None
+        self._wake.set_result(None)
+        await self._asleep.wait()
+        await asyncio.sleep(0)  # each probe the round started has sent its query
+
+
+def _probed(
+    *, can_receive: bool = True, clock: Callable[[], float] = lambda: 100.0
+) -> tuple[GoveeTransport, _Waits, list[bool], list[float]]:
+    """A transport that probes the test lamp on held waits; whether the lamp streams, which a
+    test can change; and the lamp's round trips."""
+    waits = _Waits()
+    transport = GoveeTransport(clock, sleep=waits, rng=random.Random(7))
+    transport._is_open = True
+    transport._send_transport = MagicMock()
+    transport._recv_transport = MagicMock() if can_receive else None
+    streams = [True]
+    rtts: list[float] = []
+    transport.register_device(lamp_record(), rtts.append, streaming=lambda: streams[0])
+    return transport, waits, streams, rtts
+
+
+def _asked(transport: GoveeTransport) -> int:
+    """How many status queries went to the lamp."""
+    return transport._send_transport.sendto.call_count  # type: ignore[union-attr]
+
+
+class TestProbeLoop:
+    """The light-sync spec's §4: a lamp that streams is asked for its status about every
+    probe interval, and its reply times a round trip."""
+
+    async def test_only_a_lamp_that_streams_is_probed(self) -> None:
+        transport, waits, streams, _ = _probed()
+        streams[0] = False
+        transport.start_probing(0.5)
+        await waits.round()
+        assert _asked(transport) == 0  # idle: its round trip wouldn't count
+        streams[0] = True
+        await waits.round()
+        assert _asked(transport) == 1
+        await transport.close()
+
+    async def test_each_wait_is_75_to_125_percent_of_the_interval(self) -> None:
+        transport, waits, streams, _ = _probed()
+        streams[0] = False
+        transport.start_probing(0.5)
+        for _ in range(40):
+            await waits.round()
+        assert all(0.375 <= wait <= 0.625 for wait in waits.asked)
+        assert min(waits.asked) < 0.4 and max(waits.asked) > 0.6  # random, not one wait
+        await transport.close()
+
+    async def test_a_query_in_flight_is_shared_never_doubled(self) -> None:
+        transport, waits, _, rtts = _probed()
+        read = asyncio.create_task(transport.query_status(LAMP_IP, timeout_s=5.0))
+        await asyncio.sleep(0)  # the light monitor's read is in flight
+        transport.start_probing(0.5)
+        await waits.round()
+        assert _asked(transport) == 1  # the read's query, not a probe's
+        _reply(transport, STATUS)
+        assert await read == STATUS and len(rtts) == 1
+        await waits.round()
+        assert _asked(transport) == 2  # answered: the next round asks again
+        await transport.close()
+
+    async def test_a_silent_lamp_holds_up_no_round(self) -> None:
+        transport, waits, _, _ = _probed()
+        transport.start_probing(0.5)
+        for _ in range(5):
+            await waits.round()
+        assert len(waits.asked) == 6  # the rounds go on
+        assert _asked(transport) == 1  # while its one probe waits for the reply
+        await transport.close()
+
+    async def test_a_probe_s_reply_times_the_lamp_s_round_trip(self) -> None:
+        now = [100.0]
+        transport, waits, _, rtts = _probed(clock=lambda: now[0])
+        transport.start_probing(0.5)
+        await waits.round()
+        now[0] += 0.25
+        _reply(transport, STATUS)
+        assert rtts == [pytest.approx(250.0)]
+        await transport.close()
+
+    async def test_nothing_is_probed_while_another_program_holds_the_reply_port(self) -> None:
+        transport, waits, _, _ = _probed(can_receive=False)
+        transport.start_probing(0.5)
+        for _ in range(3):
+            await waits.round()
+        assert _asked(transport) == 0
+        await transport.close()
+
+    async def test_the_loop_and_its_probes_stop_at_close(self) -> None:
+        transport, waits, _, _ = _probed()
+        transport.start_probing(0.5)
+        loop = transport._probe_task
+        transport.start_probing(0.5)
+        assert transport._probe_task is loop  # one loop
+        await waits.round()
+        probes = set(transport._probes)
+        assert len(probes) == 1  # in flight
+
+        await transport.close()
+
+        assert loop is not None and loop.done()
+        assert all(probe.done() for probe in probes) and not transport._probes
 
 
 class TestHeardFrom:
```

In `tests/devices/govee/test_backend.py`:

```diff
--- a/tests/devices/govee/test_backend.py
+++ b/tests/devices/govee/test_backend.py
@@ -86,6 +86,28 @@ async def _connect(
     return device
 
 
+@pytest.mark.parametrize("path", ["connect_known", "discover"])
+async def test_a_lamp_set_up_is_probed_while_its_tracker_says_it_streams(
+    config: AppConfig, path: str
+) -> None:
+    backend = GoveeBackend()
+    transport = backend._transport = lamp_transport()
+    if path == "connect_known":
+        (device,) = await backend.connect_known([lamp_row()], config)
+    else:
+        (device,) = await backend.discover(config)
+    assert device.on_accepted is not None
+    device.on_accepted()  # the orchestrator takes it in
+
+    [registered] = transport.register_device.call_args_list
+    assert registered.args[1] == device.tracker.update_rtt
+    streaming = registered.kwargs["streaming"]
+    assert streaming() is False  # no frame sent yet
+    device.tracker.note_send()
+    assert streaming() is True
+    transport.start_probing.assert_called_once_with(config.devices.govee.probe_interval_s)
+
+
 async def test_a_lamp_s_tracker_carries_its_name_for_the_log(config: AppConfig) -> None:
     device = await _connect(config)
     assert device.tracker.name == device.adapter.device_info.name
```

In `tests/test_config.py`:

```diff
--- a/tests/test_config.py
+++ b/tests/test_config.py
@@ -159,6 +159,7 @@ class TestGoveeConfigValidation:
         assert config.devices.govee.latency_strategy == "windowed_median"
         assert config.devices.govee.latency_window_size == LATENCY_WINDOW
         assert config.devices.govee.latency_ms == 100.0
+        assert config.devices.govee.probe_interval_s == 0.5
         assert config.devices.govee.segment_override is None
 
     def test_govee_max_fps_must_be_positive(self) -> None:
@@ -169,6 +170,11 @@ class TestGoveeConfigValidation:
         with pytest.raises(ValueError, match="govee latency_strategy"):
             AppConfig(devices=DevicesConfig(govee=GoveeConfig(latency_strategy="invalid")))
 
+    @pytest.mark.parametrize("interval", [0.0, -0.5])
+    def test_govee_probe_interval_must_be_positive(self, interval: float) -> None:
+        with pytest.raises(ValueError, match="govee probe_interval_s must be positive"):
+            AppConfig(devices=DevicesConfig(govee=GoveeConfig(probe_interval_s=interval)))
+
     def test_govee_discovery_timeout_must_be_positive(self) -> None:
         with pytest.raises(ValueError, match="govee discovery_timeout_s"):
             AppConfig(devices=DevicesConfig(govee=GoveeConfig(discovery_timeout_s=0)))
```

In `tests/web/test_router_config.py`, `probe_interval_s` is no longer a key the app keeps without reading:

```diff
--- a/tests/web/test_router_config.py
+++ b/tests/web/test_router_config.py
@@ -58,7 +58,6 @@ def test_import_config(client):
 # fields stay until every way in ignores keys it doesn't know.
 UNREAD = {
     "discovery": {"unicast_concurrency": 50, "unicast_timeout_s": 0.5, "subnet_mask": 24},
-    "devices": {"govee": {"probe_interval_s": 5.0}},
 }
 
 
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/devices/govee/test_transport.py tests/devices/govee/test_backend.py tests/test_config.py tests/web/test_router_config.py -q`
Expected: FAIL: `15 failed, 75 passed`: the probe loop's seven with `TypeError: GoveeTransport.__init__() got an unexpected keyword argument 'sleep'`, three round-trip tests with `TypeError: GoveeTransport.register_device() got an unexpected keyword argument 'streaming'`, two backend tests with `KeyError: 'streaming'`, and the config's default and its two positive checks.

- [ ] **Step 3: Write the probe loop**

In `src/dj_ledfx/devices/govee/transport.py`:

```diff
--- a/src/dj_ledfx/devices/govee/transport.py
+++ b/src/dj_ledfx/devices/govee/transport.py
@@ -2,8 +2,9 @@ from __future__ import annotations
 
 import asyncio
 import json
+import random
 import time
-from collections.abc import Callable
+from collections.abc import Awaitable, Callable
 from dataclasses import dataclass
 from typing import Any
 
@@ -16,6 +17,12 @@ MULTICAST_ADDR = "239.255.255.250"
 DISCOVERY_PORT = 4001
 RESPONSE_PORT = 4002
 COMMAND_PORT = 4003
+# Each probe round waits a random share of the interval in this range, so the probes land at
+# every phase of a dozing lamp's beacon cycle (light-sync spec §4).
+PROBE_SPREAD = (0.75, 1.25)
+# How long a probe waits for its reply, as long as a light monitor's read does
+# (adapter_base.STATUS_TIMEOUT_S). A reply that comes later times nothing.
+PROBE_TIMEOUT_S = 1.0
 
 
 @dataclass
@@ -30,13 +37,22 @@ class _StatusQuery:
 
 class GoveeTransport:
     """Shared UDP transport for all Govee devices on the LAN. A lamp's round trips come from
-    its status reads: each query that gets its reply times one."""
+    its status queries, the probe loop's and the light monitor's reads alike: each query
+    that gets its reply times one."""
 
-    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
+    def __init__(
+        self,
+        clock: Callable[[], float] = time.monotonic,
+        *,
+        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
+        rng: random.Random | None = None,
+    ) -> None:
         self._send_transport: asyncio.DatagramTransport | None = None
         self._recv_transport: asyncio.DatagramTransport | None = None
         self._is_open = False
         self._clock = clock
+        self._sleep = sleep  # the probe loop's waits
+        self._rng = rng or random.Random()
 
         # Response routing: cmd → handler
         self._cmd_handlers: dict[str, Callable[[dict[str, Any], tuple[str, int]], None]] = {}
@@ -44,6 +60,9 @@ class GoveeTransport:
         # Status queries in flight, one per lamp: ip → query
         self._pending_status: dict[str, _StatusQuery] = {}
         self._heard: dict[str, float] = {}  # ip → when its last status reply came
+        self._streaming: dict[str, Callable[[], bool]] = {}  # ip → whether it streams now
+        self._probe_task: asyncio.Task[None] | None = None
+        self._probes: set[asyncio.Task[dict[str, Any] | None]] = set()  # probes in flight
 
     @property
     def is_open(self) -> bool:
@@ -98,12 +117,21 @@ class GoveeTransport:
         logger.debug("Govee transport opened")
 
     async def close(self) -> None:
+        stopping: list[asyncio.Task[Any]] = [*self._probes]  # the loop, and its probes
+        if self._probe_task is not None:
+            stopping.append(self._probe_task)
+        for task in stopping:
+            task.cancel()
+        if stopping:
+            await asyncio.wait(stopping)
+        self._probe_task = None
         if self._recv_transport:
             self._recv_transport.close()
         if self._send_transport:
             self._send_transport.close()
         self._is_open = False
         self._rtt_callbacks.clear()
+        self._streaming.clear()
         self._pending_status.clear()
         self._cmd_handlers.clear()
         logger.debug("Govee transport closed")
@@ -170,10 +198,39 @@ class GoveeTransport:
         return self._heard.get(ip)
 
     def register_device(
-        self, record: GoveeDeviceRecord, rtt_callback: Callable[[float], None]
+        self,
+        record: GoveeDeviceRecord,
+        rtt_callback: Callable[[float], None],
+        *,
+        streaming: Callable[[], bool],
     ) -> None:
-        """Send the lamp's round trips, in ms, to rtt_callback."""
+        """Send the lamp's round trips, in ms, to rtt_callback. The probe loop asks the lamp
+        for its status only while streaming() says it streams: an idle lamp's round trip
+        wouldn't count."""
         self._rtt_callbacks[record.ip] = rtt_callback
+        self._streaming[record.ip] = streaming
+
+    def start_probing(self, interval_s: float) -> None:
+        """Probe each lamp that streams about every interval_s, until the transport closes.
+        Called again while the loop runs, it changes nothing."""
+        if self._probe_task is None or self._probe_task.done():
+            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))
+
+    async def _probe_loop(self, interval_s: float) -> None:
+        """Each round waits a random 75–125% of interval_s, then asks each lamp that streams
+        for its status, unless a query to it is in flight already. A probe's reply times a
+        round trip as a read's does. Nothing is asked while another program holds UDP 4002:
+        no reply could reach us."""
+        while self._is_open:
+            await self._sleep(interval_s * self._rng.uniform(*PROBE_SPREAD))
+            if not self.can_receive:
+                continue
+            for ip, streaming in self._streaming.items():
+                if ip in self._pending_status or not streaming():
+                    continue
+                probe = asyncio.create_task(self.query_status(ip, timeout_s=PROBE_TIMEOUT_S))
+                self._probes.add(probe)
+                probe.add_done_callback(self._probes.discard)
 
     def _make_scan_handler(
         self,
```

In `src/dj_ledfx/devices/govee/backend.py`:

```diff
--- a/src/dj_ledfx/devices/govee/backend.py
+++ b/src/dj_ledfx/devices/govee/backend.py
@@ -106,6 +106,8 @@ class GoveeBackend(DeviceBackend):
 
         if not heard:  # not when every lamp that answered is online already
             logger.info("No Govee devices found — ensure LAN control is enabled in Govee app")
+        if results:
+            transport.start_probing(govee.probe_interval_s)
 
         return results
 
@@ -146,6 +148,8 @@ class GoveeBackend(DeviceBackend):
                 continue
             logger.info("Reconnected known Govee device '{}' at {}", name, record.ip)
 
+        if results:
+            transport.start_probing(config.devices.govee.probe_interval_s)
         return results
 
     def rebuild(
@@ -174,7 +178,8 @@ class GoveeBackend(DeviceBackend):
         output: GoveeOutput,
     ) -> DiscoveredDevice:
         """Connect a lamp as its plan says it plays; once the orchestrator takes it in, its
-        status reads time its round trips. Raises ConnectionError when it doesn't answer."""
+        status queries time its round trips, and it's probed while it streams. Raises
+        ConnectionError when it doesn't answer."""
         adapter = self._adapter(transport, record, config, output)
         await adapter.connect()
         tracker = tracker_for(
@@ -184,7 +189,12 @@ class GoveeBackend(DeviceBackend):
             adapter=adapter,
             tracker=tracker,
             max_fps=adapter.stream_fps,
-            on_accepted=partial(transport.register_device, record, tracker.update_rtt),
+            on_accepted=partial(
+                transport.register_device,
+                record,
+                tracker.update_rtt,
+                streaming=lambda: tracker.streaming,
+            ),
         )
 
     def _adapter(
```

In `src/dj_ledfx/config.py`:

```diff
--- a/src/dj_ledfx/config.py
+++ b/src/dj_ledfx/config.py
@@ -95,10 +95,9 @@ class GoveeConfig:
     manual_offset_ms: float = 0.0
     max_fps: int = GOVEE_RAZER_FPS  # one colour is capped at GOVEE_COLOUR_FPS
     latency_window_size: int = LATENCY_WINDOW
-    # Unread: a lamp's round trips come from its status reads (the light monitor's polls).
-    # Kept so config files and exports that carry it still load: PUT /config and
-    # POST /config/import refuse a key GoveeConfig doesn't have.
-    probe_interval_s: float = 5.0
+    # About how often a lamp that streams is asked for its status, its reply timing a round
+    # trip: each probe round waits a random 75–125% of it (light-sync spec §4).
+    probe_interval_s: float = 0.5
     segment_override: int | None = None
 
 
@@ -163,6 +162,8 @@ class AppConfig:
         govee = self.devices.govee
         if govee.discovery_timeout_s <= 0:
             raise ValueError("govee discovery_timeout_s must be positive")
+        if govee.probe_interval_s <= 0:
+            raise ValueError("govee probe_interval_s must be positive")
         if self.web.port < 0 or self.web.port > 65535:
             raise ValueError("web port must be 0-65535")
 
```

In `config.toml`:

```diff
--- a/config.toml
+++ b/config.toml
@@ -51,7 +51,7 @@ latency_ms = 100.0
 manual_offset_ms = 0.0
 max_fps = 30
 latency_window_size = 9
-probe_interval_s = 5.0
+probe_interval_s = 0.5
 
 [discovery]
 broadcast_interval_s = 30.0
```

In `config.example.toml` (ruling 17):

```diff
--- a/config.example.toml
+++ b/config.example.toml
@@ -28,7 +28,16 @@ enabled = true
 discovery_timeout_s = 10.0
 default_kelvin = 3500
 max_fps = 60
-latency_strategy = "ema"
-latency_ms = 50
+latency_strategy = "windowed_median"
+latency_ms = 10
 manual_offset_ms = 0
 echo_probe_interval_s = 2.0
+
+[devices.govee]
+enabled = true
+discovery_timeout_s = 5.0
+max_fps = 30
+latency_strategy = "windowed_median"
+latency_ms = 100
+manual_offset_ms = 0
+probe_interval_s = 0.5
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/devices/govee/test_transport.py tests/devices/govee/test_backend.py tests/test_config.py tests/web/test_router_config.py -q`
Expected: PASS (90 tests).

- [ ] **Step 5: Run the gate**

```bash
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: ruff clean, no format findings, mypy's 16 errors, and `1864 passed, 1 skipped, 42 deselected`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/devices/govee src/dj_ledfx/config.py config.toml config.example.toml tests/devices/govee tests/test_config.py tests/web/test_router_config.py
git commit -m "feat(govee): probe each streaming lamp about every 0.5 s"
```

---


### Task 4: The horizon cap at 500 ms

A dozing lamp's latency is its whole round trip, up to about 0.4 s, so the cap rises from 120 ms to 500 ms (spec §6). A zone still renders ahead by its largest latency plus a frame, so only a zone with a slow light renders further ahead; the comment says what that costs.

**Files:**
- Modify: `src/dj_ledfx/zones/runtime.py`
- Test: `tests/zones/test_runtime.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `zones.runtime.HORIZON_CAP_S = 0.5`.

- [ ] **Step 1: Write the failing tests**

In `tests/zones/test_runtime.py`:

```diff
--- a/tests/zones/test_runtime.py
+++ b/tests/zones/test_runtime.py
@@ -123,8 +123,16 @@ def test_frames_are_rendered_for_now_plus_the_horizon() -> None:
     assert frame.colors.dtype == np.float32 and frame.colors.shape == (8, 3)
 
 
-def test_the_horizon_is_capped() -> None:
-    runtime = runtime_of(look_of(field_layer()), latencies={"lamp": 5.0}, max_lookahead_s=1.0)
+def test_a_zone_with_a_400_ms_light_renders_400_ms_and_a_frame_ahead() -> None:
+    runtime = runtime_of(look_of(field_layer()), latencies={"lamp": 0.4})  # a dozing lamp
+    assert runtime.horizon_s == pytest.approx(0.4 + 1 / 60)
+    runtime.tick(100.0)
+    assert nearest_frame(runtime.ring, 100.5).target_time == pytest.approx(100.4 + 1 / 60)
+
+
+def test_the_horizon_is_capped_at_500_ms() -> None:
+    assert HORIZON_CAP_S == 0.5
+    runtime = runtime_of(look_of(field_layer()), latencies={"lamp": 0.6}, max_lookahead_s=1.0)
     assert runtime.horizon_s == HORIZON_CAP_S
     shorter = runtime_of(look_of(field_layer()), latencies={"lamp": 5.0}, max_lookahead_s=0.05)
     assert shorter.horizon_s == 0.05
@@ -156,10 +164,10 @@ def test_opacity_scales_the_frame_and_brightness_the_send() -> None:
 
 
 def test_a_light_slower_than_the_cap_gets_the_newest_frame() -> None:
-    runtime = runtime_of(look_of(field_layer(level=0.8)), latencies={"lamp": 0.5})
+    runtime = runtime_of(look_of(field_layer(level=0.8)), latencies={"lamp": 0.6})
     assert runtime.horizon_s == HORIZON_CAP_S
     runtime.tick(100.0)
-    assert np.all(sent(runtime, "lamp", 100.0 + 0.5, 3) == 204)  # 0.8 in 8 bits: late, not dark
+    assert np.all(sent(runtime, "lamp", 100.0 + 0.6, 3) == 204)  # 0.8 in 8 bits: late, not dark
 
 
 def test_a_crash_holds_the_last_good_frame_and_is_logged_once() -> None:
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/zones/test_runtime.py -q`
Expected: FAIL: `2 failed, 30 passed`: the 400 ms zone renders only 120 ms and a frame ahead, and the cap is 0.12.

- [ ] **Step 3: Raise the cap**

In `src/dj_ledfx/zones/runtime.py`:

```diff
--- a/src/dj_ledfx/zones/runtime.py
+++ b/src/dj_ledfx/zones/runtime.py
@@ -62,9 +62,12 @@ SLOW_AFTER_S = 30.0
 CRASH_LOG_INTERVAL_S = 60.0
 ALWAYS_AVAILABLE = frozenset({"tempo"})  # the internal clock at worst (spec §5.2)
 # How far ahead a zone renders at most. A light slower than this gets the newest frame and
-# runs late by the difference. A look starts within a frame or two, and a change to a
-# running look shows within the horizon (≤120 ms).
-HORIZON_CAP_S = 0.12
+# runs late by the difference. A dozing Govee lamp's latency is its whole round trip, up to
+# about 0.4 s, so a zone with one renders that far ahead, a LIFX matrix's zone about 140 ms
+# (light-sync spec §6). A light whose moment comes before the zone's first frame holds that
+# frame until its moment reaches it: up to about 0.4 s in a zone with a dozing lamp, a frame
+# or two in the others. A change to a running look shows within the horizon.
+HORIZON_CAP_S = 0.5
 
 # Process-wide, so a light running one runtime's firmware effect always sees another look's
 # as new; only a twin shares its runtime's generation, on purpose (twin()).
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/zones/test_runtime.py -q`
Expected: PASS (32 tests).

- [ ] **Step 5: Run the gate**

```bash
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: ruff clean, no format findings, mypy's 16 errors, and `1865 passed, 1 skipped, 42 deselected`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/zones/runtime.py tests/zones/test_runtime.py
git commit -m "feat(zones): the horizon cap rises to 500 ms, for a dozing lamp's whole round trip"
```

---


### Task 5: Link memory

Each light's latency and mode outlive a restart (spec §7). Migration 010 adds the `link_memory` table; `LinkMemory` reads it once at start, hands a light's row to its tracker when the discovery orchestrator takes the light in, and writes what changed every 30 s and once more at shutdown (rulings 13–16). Backups leave the table out: `export_toml` copies named tables only, so nothing there changes, and a test pins it.

**Files:**
- Create: `src/dj_ledfx/persistence/migrations/010_link_memory.sql`, `src/dj_ledfx/latency/memory.py`
- Modify: `src/dj_ledfx/devices/discovery.py`, `src/dj_ledfx/main.py`
- Test: `tests/latency/test_memory.py` (new), `tests/devices/test_discovery.py`; the schema version goes from 9 to 10 in `tests/persistence/test_state_db.py`, `tests/persistence/test_zones_and_looks_schema.py`, `tests/persistence/test_device_saved_state.py`, `tests/home/test_store.py` and `tests/test_integration.py`

**Interfaces:**
- Consumes: Task 2's `LatencyTracker.recall()`, `link_latency_ms`, `dozing`, `measured` and `name`; `StateDB.fetch_all`, `write_many` and `Statement`; `timing.utc_text` and `utcnow`.
- Produces (`dj_ledfx.latency.memory`):
  - `LINK_MEMORY_EVERY_S = 30.0`, `MOVED_MS = 5.0`; `Trackers = Callable[[], Iterable[tuple[str, LatencyTracker]]]`.
  - `Link(latency_ms: float, dozing: bool)`, frozen.
  - `LinkMemory(db: StateDB)`: `async load()`; `recall(stable_id: str, tracker: LatencyTracker) -> None`; `async save(trackers: Iterable[tuple[str, LatencyTracker]]) -> int` (the rows written); `async run(trackers: Trackers, every_s: float = LINK_MEMORY_EVERY_S)`.
- Produces: `DiscoveryOrchestrator(..., link_memory: LinkMemory | None = None)`; `main._trackers(devices: DeviceManager) -> list[tuple[str, LatencyTracker]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/latency/test_memory.py`:

```python
"""The light-sync spec's §7: each light's latency and mode, remembered across restarts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from conftest import as_schema
from govee_fakes import LAMP
from loguru import logger

from dj_ledfx.latency.memory import LinkMemory
from dj_ledfx.latency.strategies import LATENCY_WINDOW, StaticLatency, WindowedMedianLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import export_toml


def measured(latency_ms: float, *, dozing: bool = False) -> LatencyTracker:
    """A tracker whose light measured latency_ms while it streamed, in the mode given."""
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0), name="test-lamp")
    tracker.recall(latency_ms, dozing)
    tracker.note_send()
    tracker.update_rtt(latency_ms if dozing else 2 * latency_ms)
    assert tracker.measured and tracker.link_latency_ms == latency_ms
    return tracker


async def _rows(db: StateDB) -> list[tuple[Any, ...]]:
    return await db.fetch_all("SELECT stable_id, latency_ms, dozing FROM link_memory")


async def test_a_light_s_row_is_read_back_into_its_tracker_at_the_next_start(
    db: StateDB,
) -> None:
    assert await LinkMemory(db).save([(LAMP, measured(250.0, dozing=True))]) == 1

    memory = LinkMemory(db)  # the next start
    await memory.load()
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0), display_ms=10.0)
    memory.recall(LAMP, tracker)

    assert (tracker.link_latency_ms, tracker.dozing) == (250.0, True)
    assert tracker.effective_latency_ms == 260.0 and not tracker.measured


async def test_a_light_with_no_row_starts_at_its_seed_awake(db: StateDB) -> None:
    memory = LinkMemory(db)
    await memory.load()
    tracker = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    memory.recall(LAMP, tracker)
    assert (tracker.link_latency_ms, tracker.dozing) == (100.0, False)


async def test_a_row_is_written_when_the_mode_changes_or_the_latency_moves_over_5_ms(
    db: StateDB,
) -> None:
    memory = LinkMemory(db)
    assert await memory.save([(LAMP, measured(100.0))]) == 1
    assert await memory.save([(LAMP, measured(104.0))]) == 0  # moved 4 ms
    assert await memory.save([(LAMP, measured(105.0))]) == 0  # 5 ms: not more than 5
    assert await memory.save([(LAMP, measured(94.5))]) == 1  # 5.5 ms
    assert await _rows(db) == [(LAMP, 94.5, 0)]
    assert await memory.save([(LAMP, measured(94.5, dozing=True))]) == 1  # its mode changed
    assert await memory.save([(LAMP, measured(97.0, dozing=True))]) == 0
    assert await _rows(db) == [(LAMP, 94.5, 1)]


async def test_a_light_not_measured_since_it_came_online_writes_nothing(db: StateDB) -> None:
    seeded = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    recalled = LatencyTracker(WindowedMedianLatency(LATENCY_WINDOW, 100.0))
    recalled.recall(250.0, dozing=True)
    static = LatencyTracker(StaticLatency(5.0))
    static.note_send()
    static.update_rtt(40.0)  # a static strategy ignores it: never measured

    lights = [("govee:seeded", seeded), ("govee:recalled", recalled), ("openrgb:pc:0", static)]
    assert await LinkMemory(db).save(lights) == 0
    assert await _rows(db) == []


async def test_the_writer_writes_every_period_and_once_more_at_shutdown(db: StateDB) -> None:
    lights = [(LAMP, measured(250.0, dozing=True))]
    writer = asyncio.create_task(LinkMemory(db).run(lambda: lights, every_s=0.01))
    await asyncio.sleep(0.1)
    assert await _rows(db) == [(LAMP, 250.0, 1)]

    lights = [(LAMP, measured(120.0))]  # its mode changed since
    writer.cancel()  # shutdown
    await asyncio.wait([writer])

    assert await _rows(db) == [(LAMP, 120.0, 0)]


async def test_a_write_that_fails_is_logged_and_the_next_one_retries(
    db: StateDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_many = db.write_many
    failures = [RuntimeError("disk full")]

    async def failing_once(statements: Any) -> None:
        if failures:
            raise failures.pop()
        await write_many(statements)

    monkeypatch.setattr(db, "write_many", failing_once)
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="ERROR")
    try:
        writer = asyncio.create_task(
            LinkMemory(db).run(lambda: [(LAMP, measured(250.0))], every_s=0.01)
        )
        await asyncio.sleep(0.1)
        writer.cancel()
        await asyncio.wait([writer])
    finally:
        logger.remove(sink)

    assert [record["message"] for record in records] == [
        "Writing the lights' link memory failed; the next write retries"
    ]
    assert await _rows(db) == [(LAMP, 250.0, 0)]


async def test_backups_leave_the_link_memory_out(db: StateDB) -> None:
    await LinkMemory(db).save([(LAMP, measured(250.0, dozing=True))])
    backup = await export_toml(db)
    assert "link_memory" not in backup and LAMP not in backup


async def test_a_database_from_before_light_sync_gains_the_table(tmp_path: Path) -> None:
    db = StateDB(tmp_path / "state.db")
    await db.open()
    await db.write("DROP TABLE link_memory")
    await as_schema(db, 9)
    await db.close()

    db = StateDB(tmp_path / "state.db")
    await db.open()
    try:
        assert await db.get_schema_version() == 10
        assert await _rows(db) == []
    finally:
        await db.close()
```

In `tests/devices/test_discovery.py`:

```diff
--- a/tests/devices/test_discovery.py
+++ b/tests/devices/test_discovery.py
@@ -21,6 +21,7 @@ from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
 from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
 from dj_ledfx.devices.openrgb_backend import OpenRGBBackend
 from dj_ledfx.events import DeviceOnlineEvent, EventBus
+from dj_ledfx.latency.memory import LinkMemory
 from dj_ledfx.latency.strategies import StaticLatency
 from dj_ledfx.latency.tracker import LatencyTracker
 from dj_ledfx.persistence.state_db import StateDB
@@ -624,6 +625,64 @@ async def test_a_duplicate_a_scan_sets_up_never_takes_the_live_tracker(
     assert len(device_manager.devices) == 1
 
 
+async def _remembering(config, device_manager, event_bus, db, row=None):  # type: ignore[no-untyped-def]
+    """An orchestrator over the Govee backend, as `lamps` gives, whose link memory holds the
+    test lamp's row (latency_ms, dozing) when one is given."""
+    if row is not None:
+        await db.write(
+            "INSERT INTO link_memory (stable_id, latency_ms, dozing, updated_at) "
+            "VALUES (?, ?, ?, '2026-10-06T00:00:00+00:00')",
+            (LAMP, *row),
+        )
+    memory = LinkMemory(db)
+    await memory.load()
+    govee = GoveeBackend()
+    govee._transport = lamp_transport()
+    orchestrator = DiscoveryOrchestrator(
+        config, device_manager, event_bus, state_db=db, link_memory=memory
+    )
+    orchestrator._backends = [govee]
+    return orchestrator
+
+
+# The light-sync spec's §7: a light taken in starts from the latency and mode it last had,
+# whether it's new to this run or an offline light found again.
+@pytest.mark.parametrize("offline", [False, True], ids=["new", "offline"])
+async def test_a_lamp_taken_in_starts_from_the_latency_and_mode_it_last_had(
+    lamp_model, config, device_manager, event_bus, db, offline
+):
+    if offline:
+        _ghost(device_manager, "Test lamp", LAMP)
+    orchestrator = await _remembering(config, device_manager, event_bus, db, (250.0, 1))
+
+    managed = await _online_lamp(orchestrator, db)
+
+    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (250.0, True)
+    assert not managed.tracker.measured  # estimated until it streams
+
+
+async def test_a_lamp_with_no_row_starts_at_the_config_s_seed_awake(
+    lamp_model, config, device_manager, event_bus, db
+):
+    orchestrator = await _remembering(config, device_manager, event_bus, db)
+    managed = await _online_lamp(orchestrator, db)
+    seed = config.devices.govee.latency_ms
+    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (seed, False)
+
+
+async def test_an_output_change_keeps_the_latency_the_lamp_has_now(
+    lamp_model, config, device_manager, event_bus, db
+):
+    """The lamp is set up again with its own tracker: its row isn't read again."""
+    orchestrator = await _remembering(config, device_manager, event_bus, db, (250.0, 1))
+    managed = await _online_lamp(orchestrator, db)
+    managed.tracker.recall(180.0, dozing=False)  # what it measured since
+
+    await orchestrator.set_output(LAMP, COLOUR)
+
+    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (180.0, False)
+
+
 async def test_only_a_known_govee_lamp_takes_an_output(config, device_manager, event_bus, db):
     orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
     await db.upsert_device({"id": "lifx:test", "name": "Test bulb", "backend": "lifx"})
```

The schema version, in `tests/persistence/test_state_db.py`:

```diff
--- a/tests/persistence/test_state_db.py
+++ b/tests/persistence/test_state_db.py
@@ -23,9 +23,9 @@ async def test_creates_db_file(tmp_path):
 
 
 @pytest.mark.asyncio
-async def test_schema_version_is_9(db):
+async def test_schema_version_is_10(db):
     version = await db.get_schema_version()
-    assert version == 9
+    assert version == 10
 
 
 @pytest.mark.asyncio
@@ -54,6 +54,7 @@ async def test_tables_created(db):
         "groups",
         "home_map",
         "home_map_unreadable",
+        "link_memory",
         "look_stars",
         "looks",
         "placements",
@@ -78,7 +79,7 @@ async def test_idempotent_open(tmp_path):
     db2 = StateDB(db_path)
     await db2.open()
     version = await db2.get_schema_version()
-    assert version == 9
+    assert version == 10
     await db2.close()
 
 
```

In `tests/persistence/test_zones_and_looks_schema.py`:

```diff
--- a/tests/persistence/test_zones_and_looks_schema.py
+++ b/tests/persistence/test_zones_and_looks_schema.py
@@ -9,8 +9,8 @@ from conftest import as_schema
 from dj_ledfx.persistence.state_db import StateDB
 
 
-async def test_schema_version_is_9(db: StateDB) -> None:
-    assert await db.get_schema_version() == 9
+async def test_schema_version_is_10(db: StateDB) -> None:
+    assert await db.get_schema_version() == 10
 
 
 async def test_new_tables_exist(db: StateDB) -> None:
@@ -71,7 +71,7 @@ async def test_upgrade_clears_what_the_old_transport_left(tmp_path: Path) -> Non
     db = StateDB(path)
     await db.open()
     try:
-        assert await db.get_schema_version() == 9
+        assert await db.get_schema_version() == 10
         assert await db.load_all_device_states() == {}
         assert await db.load_config("engine") == {"fps": "60"}
     finally:
```

In `tests/persistence/test_device_saved_state.py`:

```diff
--- a/tests/persistence/test_device_saved_state.py
+++ b/tests/persistence/test_device_saved_state.py
@@ -63,7 +63,7 @@ async def test_save_device_state_upsert(db: StateDB) -> None:
 
 
 @pytest.mark.asyncio
-async def test_schema_version_is_9_after_migration(db: StateDB) -> None:
-    """Migrations up to 007 should have been applied, bumping schema to version 7."""
+async def test_schema_version_is_10_after_migration(db: StateDB) -> None:
+    """Every migration has been applied, up to 010."""
     version = await db.get_schema_version()
-    assert version == 9
+    assert version == 10
```

In `tests/home/test_store.py`:

```diff
--- a/tests/home/test_store.py
+++ b/tests/home/test_store.py
@@ -142,7 +142,7 @@ async def test_schema_9_gives_each_placement_made_before_it_a_source(
     finally:
         await db.close()
 
-    assert version == 9
+    assert version == 10
     assert {target: placement.source for target, placement in placements.items()} == sources
 
 
```

In `tests/test_integration.py`:

```diff
--- a/tests/test_integration.py
+++ b/tests/test_integration.py
@@ -135,7 +135,7 @@ async def test_startup_with_fresh_db(tmp_path: Path) -> None:
     db = StateDB(tmp_path / "state.db")
     await db.open()
     version = await db.get_schema_version()
-    assert version == 9
+    assert version == 10
     devices = await db.load_devices()
     assert devices == []
     scenes = await db.load_scenes()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/latency/test_memory.py tests/devices/test_discovery.py -q`
Expected: FAIL: two collection errors, `ModuleNotFoundError: No module named 'dj_ledfx.latency.memory'`.

Run: `uv run pytest tests/persistence tests/home/test_store.py tests/test_integration.py -q`
Expected: FAIL: `9 failed, 101 passed`, eight with `assert 9 == 10` (the schema version) and `test_tables_created` without `link_memory`.

- [ ] **Step 3: Write the memory**

Create `src/dj_ledfx/persistence/migrations/010_link_memory.sql`:

```sql
-- Light sync: each light's link memory, the latency and mode it last had, so the first look
-- after a restart starts every light where it was (light-sync spec §7). latency_ms is the
-- latency strategy's, before the display delay and the offset. dozing is 1 while the doze
-- check calls the light's Wi-Fi dozing. A cache, measured again within seconds of a start,
-- so backups leave it out

CREATE TABLE IF NOT EXISTS link_memory (
    stable_id TEXT PRIMARY KEY,
    latency_ms REAL NOT NULL,
    dozing INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
```

Create `src/dj_ledfx/latency/memory.py`:

```python
"""Each light's link memory (light-sync spec §7): the latency and mode it last had, kept in
state.db's link_memory table, so the first look after a restart starts every light where it
was. A cache, measured again within seconds of a start: backups leave it out."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB, Statement
from dj_ledfx.timing import utc_text, utcnow

LINK_MEMORY_EVERY_S = 30.0  # how often the writer writes what changed
MOVED_MS = 5.0  # a latency that moved by more than this since its row was written is written

# Each light's stable id and tracker, as the device manager has them now.
Trackers = Callable[[], Iterable[tuple[str, LatencyTracker]]]


@dataclass(frozen=True, slots=True)
class Link:
    """A light's row: its strategy's latency, before display and offset, and its mode."""

    latency_ms: float
    dozing: bool


class LinkMemory:
    """The lights' rows, read once at start and written as they change."""

    def __init__(self, db: StateDB) -> None:
        self._db = db
        self._links: dict[str, Link] = {}  # the rows as last read or written

    async def load(self) -> None:
        rows = await self._db.fetch_all("SELECT stable_id, latency_ms, dozing FROM link_memory")
        self._links = {row[0]: Link(float(row[1]), bool(row[2])) for row in rows}

    def recall(self, stable_id: str, tracker: LatencyTracker) -> None:
        """Start a light's tracker from its row, before its first frame. A light with no row
        keeps its seed, awake."""
        link = self._links.get(stable_id)
        if link is None:
            return
        tracker.recall(link.latency_ms, link.dozing)
        mode = "dozing" if link.dozing else "awake"
        logger.info(
            "{} starts from the latency it last had: {:.0f} ms, {}",
            tracker.name,
            link.latency_ms,
            mode,
        )

    async def save(self, trackers: Iterable[tuple[str, LatencyTracker]]) -> int:
        """Write the row of each light measured since it came online whose mode changed, or
        whose latency moved by more than MOVED_MS, since its row was last written. Returns
        how many rows it wrote."""
        due: dict[str, Link] = {}
        for stable_id, tracker in trackers:
            if not tracker.measured:
                continue  # its latency is still a seed or a recalled one
            link = Link(tracker.link_latency_ms, tracker.dozing)
            if _moved(self._links.get(stable_id), link):
                due[stable_id] = link
        if not due:
            return 0
        when = utc_text(utcnow())
        await self._db.write_many([_upsert(sid, link, when) for sid, link in due.items()])
        self._links.update(due)
        return len(due)

    async def run(self, trackers: Trackers, every_s: float = LINK_MEMORY_EVERY_S) -> None:
        """Write what changed every every_s, and once more when cancelled: at shutdown,
        while state.db is still open. A write that fails is logged, and the next one tries
        again."""
        try:
            while True:
                await asyncio.sleep(every_s)
                await self._save_logged(trackers)
        finally:
            await self._save_logged(trackers)

    async def _save_logged(self, trackers: Trackers) -> None:
        try:
            await self.save(trackers())
        except Exception:
            logger.exception("Writing the lights' link memory failed; the next write retries")


def _moved(row: Link | None, now: Link) -> bool:
    if row is None or row.dozing != now.dozing:
        return True
    return abs(now.latency_ms - row.latency_ms) > MOVED_MS


def _upsert(stable_id: str, link: Link, when: str) -> Statement:
    return (
        "INSERT INTO link_memory (stable_id, latency_ms, dozing, updated_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(stable_id) DO UPDATE SET "
        "latency_ms=excluded.latency_ms, dozing=excluded.dozing, updated_at=excluded.updated_at",
        (stable_id, link.latency_ms, int(link.dozing), when),
    )
```

In `src/dj_ledfx/devices/discovery.py`:

```diff
--- a/src/dj_ledfx/devices/discovery.py
+++ b/src/dj_ledfx/devices/discovery.py
@@ -18,6 +18,7 @@ from dj_ledfx.events import DeviceDiscoveredEvent, DeviceOnlineEvent, EventBus
 if TYPE_CHECKING:
     from dj_ledfx.devices.adapter import DeviceAdapter
     from dj_ledfx.devices.govee.output import GoveeOutput
+    from dj_ledfx.latency.memory import LinkMemory
     from dj_ledfx.latency.tracker import LatencyTracker
     from dj_ledfx.persistence.state_db import StateDB
 
@@ -31,11 +32,13 @@ class DiscoveryOrchestrator:
         device_manager: DeviceManager,
         event_bus: EventBus,
         state_db: StateDB | None = None,
+        link_memory: LinkMemory | None = None,
     ) -> None:
         self._config = config
         self._manager = device_manager
         self._event_bus = event_bus
         self._state_db = state_db
+        self._link_memory = link_memory  # each light's last latency and mode
         self._running = False
         self._task: asyncio.Task[None] | None = None
         # One scan at a time: a Govee scan has one reply handler, so two at once would cut
@@ -261,15 +264,23 @@ class DiscoveryOrchestrator:
             if len(named) == 1 and named[0].status == "offline":
                 existing = named[0]
         if existing is None:
+            self._recall(device)
             self._manager.add_device(device.adapter, device.tracker, device.max_fps)
             device.accepted()
             self._event_bus.emit(DeviceDiscoveredEvent(stable_id=stable_id, name=name))
             return True
         if existing.status != "offline":
             return False  # a duplicate: its tracker never gets the light's round trips
+        self._recall(device)
         self._promote(existing.adapter.device_info.effective_id, device)
         return True
 
+    def _recall(self, device: DiscoveredDevice) -> None:
+        """Start a light taken in from the latency and mode it last had (light-sync spec §7).
+        A light set up again with its own tracker (_play) keeps what that tracker has."""
+        if self._link_memory is not None:
+            self._link_memory.recall(device.adapter.device_info.effective_id, device.tracker)
+
     async def _persist_device(self, adapter: DeviceAdapter) -> None:
         if not self._state_db:
             return
```

In `src/dj_ledfx/main.py`, the memory loads before the orchestrator is built, and its writer runs with the other tasks, which shutdown cancels and awaits before state.db closes:

```diff
--- a/src/dj_ledfx/main.py
+++ b/src/dj_ledfx/main.py
@@ -32,6 +32,7 @@ from dj_ledfx.events import DeviceDiscoveredEvent, DeviceOfflineEvent, DeviceOnl
 from dj_ledfx.home.map import HomeMap
 from dj_ledfx.home.store import HomeStore
 from dj_ledfx.home.sun import Evening
+from dj_ledfx.latency.memory import LinkMemory
 from dj_ledfx.latency.strategies import StaticLatency
 from dj_ledfx.latency.tracker import LatencyTracker
 from dj_ledfx.looks.store import LookStore
@@ -204,6 +205,11 @@ def _finished(background: set[asyncio.Task[object]], task: asyncio.Task[object])
         logger.opt(exception=error).error("{} failed", task.get_name())
 
 
+def _trackers(devices: DeviceManager) -> list[tuple[str, LatencyTracker]]:
+    """Each managed light's stable id and tracker, for the link memory's writer."""
+    return [(d.adapter.device_info.effective_id, d.tracker) for d in devices.devices]
+
+
 def _switch_at_midpoints(
     bus: EventBus, zones: ZoneManager, background: set[asyncio.Task[object]]
 ) -> None:
@@ -279,11 +285,15 @@ async def _run(args: argparse.Namespace) -> None:
     if registered_devices:
         logger.info("Loaded {} registered device(s) from DB", len(registered_devices))
 
+    # Each light starts from the latency and mode it last had (light-sync spec §7).
+    link_memory = LinkMemory(state_db)
+    await link_memory.load()
     discovery_orchestrator = DiscoveryOrchestrator(
         config=config,
         device_manager=device_manager,
         event_bus=event_bus,
         state_db=state_db,
+        link_memory=link_memory,
     )
 
     # Scenes become groups once; zones that were running come back (spec §4.3, §6.5).
@@ -486,6 +496,8 @@ async def _run(args: argparse.Namespace) -> None:
     tasks.append(asyncio.create_task(light_monitor.run()))
     tasks.append(asyncio.create_task(attention_feed.run()))
     tasks.append(asyncio.create_task(previews.run()))
+    # Cancelled at shutdown, it writes once more before state.db closes.
+    tasks.append(asyncio.create_task(link_memory.run(partial(_trackers, device_manager))))
 
     discovery_orchestrator.start()
 
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/latency/test_memory.py tests/devices/test_discovery.py tests/persistence tests/home/test_store.py tests/test_integration.py -q`
Expected: PASS (147 tests).

- [ ] **Step 5: Run the gate**

```bash
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: ruff clean, no format findings, mypy's 16 errors, and `1877 passed, 1 skipped, 42 deselected`.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/persistence/migrations/010_link_memory.sql src/dj_ledfx/latency/memory.py src/dj_ledfx/devices/discovery.py src/dj_ledfx/main.py tests/latency/test_memory.py tests/devices/test_discovery.py tests/persistence tests/home/test_store.py tests/test_integration.py
git commit -m "feat(latency): remember each light's latency and mode across restarts"
```

---


### Task 6: Device settings in state.db

`_load_config_from_db` builds `DevicesConfig` from sections `devices.openrgb`, `devices.lifx` and `devices.govee` (spec §8). Before any of it, a run-once step deletes the `devices.*` rows, which no start ever applied, so the first start after this runs on the code's defaults, as every start has; it logs what it dropped (rulings 1–4). The two subprocess tests run the app for real: one on a database like the deployed one, one on a new database with a config.toml. Then `PUT /api/config` saves the device settings a request names to those sections, as config.toml's migration writes them, so one changed in the app applies from the next start (the owner's decision, ruling 20).

**Files:**
- Modify: `src/dj_ledfx/main.py`, `src/dj_ledfx/web/router_config.py`
- Test: `tests/test_device_settings.py` (new), `tests/test_main.py`, `tests/web/test_config_device_settings.py` (new)

**Interfaces:**
- Consumes: `StateDB.has_mark`, `mark_statement`, `fetch_all`, `write_many`, `load_all_config`; `config.filter_fields`; `OpenRGBConfig`, `LIFXConfig`, `GoveeConfig`, `DevicesConfig`; `StateDB.save_config_bulk` and `load_config`; `tests/api_home.py`'s `api_home`.
- Produces (`dj_ledfx.main`): `DEVICES_CONFIG_RESET = "devices_config_reset"`; `async _reset_device_settings_once(state_db: StateDB) -> None`; `_devices_config(sections: dict[str, dict[str, object]]) -> DevicesConfig`; `_load_config_from_db()` returns a config with `devices` built from state.db. (`dj_ledfx.web.router_config`): `_device_rows(body: dict[str, Any], devices: dict[str, Any]) -> dict[str, dict[str, str]]`, the device settings a request names as state.db's rows; `PUT /api/config` saves them, with the same request and response.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_device_settings.py`:

```python
"""The light-sync spec's §8: the device settings load from state.db, after a run-once step
drops the rows saved before any start applied them."""

from __future__ import annotations

from typing import Any

import pytest
from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.main import DEVICES_CONFIG_RESET, _load_config_from_db, _reset_device_settings_once
from dj_ledfx.persistence.state_db import StateDB


async def _save(db: StateDB, section: str, **settings: str) -> None:
    """Settings as state.db keeps them: JSON text."""
    for key, value in settings.items():
        await db.save_config_key(section, key, value)


async def test_device_settings_load_from_the_database(db: StateDB) -> None:
    await _save(db, "engine", fps="60")
    await _save(db, "devices.govee", probe_interval_s="0.8", max_fps="20")
    await _save(db, "devices.lifx", latency_ms="12.0")
    await _save(db, "devices.openrgb", latency_strategy='"static"')

    config = await _load_config_from_db(db)

    assert config is not None
    govee = config.devices.govee
    assert (govee.probe_interval_s, govee.max_fps, govee.latency_ms) == (0.8, 20, 100.0)
    assert config.devices.lifx.latency_ms == 12.0
    assert config.devices.openrgb.latency_strategy == "static"


async def test_device_settings_alone_are_a_config(db: StateDB) -> None:
    """A config.toml with only device tables, migrated into state.db, still applies."""
    await _save(db, "devices.govee", max_fps="20")
    config = await _load_config_from_db(db)
    assert config is not None and config.devices.govee.max_fps == 20


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("probe_interval_s", "0", "govee probe_interval_s must be positive"),
        ("max_fps", '"fast"', "not supported between instances"),
    ],
)
async def test_device_settings_the_config_refuses_leave_the_lights_on_their_defaults(
    db: StateDB, key: str, value: str, reason: str
) -> None:
    await _save(db, "engine", fps="42")
    await _save(db, "devices.govee", **{key: value})
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        config = await _load_config_from_db(db)
    finally:
        logger.remove(sink)

    assert config is not None
    assert config.devices == AppConfig().devices
    assert config.engine.fps == 42  # the rest loads as before
    [warning] = records
    assert warning["message"].startswith("Saved device settings refused")
    assert reason in warning["message"]


async def test_the_old_device_settings_go_once_and_a_setting_saved_after_stays(
    db: StateDB,
) -> None:
    await _save(db, "engine", fps="60")
    await _save(db, "devices.govee", max_fps="40", latency_strategy='"ema"')
    await _save(db, "devices.lifx", latency_ms="50")
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        await _reset_device_settings_once(db)
    finally:
        logger.remove(sink)

    assert await db.load_all_config() == {("engine", "fps"): 60}
    assert await db.has_mark(DEVICES_CONFIG_RESET)
    assert [record["message"] for record in records] == [
        "Dropped device settings that never applied: devices.govee.latency_strategy, "
        "devices.govee.max_fps, devices.lifx.latency_ms"
    ]

    await _save(db, "devices.govee", max_fps="20")  # saved after the step
    await _reset_device_settings_once(db)  # the next start

    assert await db.load_all_config() == {("engine", "fps"): 60, ("devices.govee", "max_fps"): 20}
```

In `tests/test_main.py`, beside the other subprocess tests:

```diff
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -307,6 +307,44 @@ async def test_a_setting_saved_before_config_toml_came_doesn_t_stop_its_migratio
     assert (tmp_path / "config.toml.bak").exists()
 
 
+async def _govee_settings(tmp_path: Path) -> dict[str, Any]:
+    """The Govee settings one start of the app runs with."""
+    async with _app(tmp_path) as (app, port):
+        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}/api") as client:
+            config = (await _get_when_up(client, "/config", app)).json()
+        output = await _stop(app)
+    assert "Traceback" not in output, output
+    govee: dict[str, Any] = config["devices"]["govee"]
+    return govee
+
+
+async def test_device_settings_no_start_applied_go_and_one_saved_after_applies(
+    tmp_path: Path,
+) -> None:
+    """The deployed database holds devices.* rows from an old config file, which no start
+    applied: the first start drops them and runs on the defaults, and a setting saved after
+    that applies from the next start on (light-sync spec §8)."""
+    db = StateDB(tmp_path / "state.db")
+    await db.open()
+    await db.save_config_key("engine", "fps", "60")
+    await db.save_config_key("devices.govee", "max_fps", "40")
+    await db.close()
+
+    assert (await _govee_settings(tmp_path))["max_fps"] == 30  # the default
+
+    db = StateDB(tmp_path / "state.db")
+    await db.open()
+    await db.save_config_key("devices.govee", "max_fps", "20")
+    await db.close()
+
+    assert (await _govee_settings(tmp_path))["max_fps"] == 20
+
+
+async def test_a_new_database_takes_config_toml_s_device_settings(tmp_path: Path) -> None:
+    (tmp_path / "config.toml").write_text("[engine]\nfps = 60\n\n[devices.govee]\nmax_fps = 20\n")
+    assert (await _govee_settings(tmp_path))["max_fps"] == 20
+
+
 async def test_a_tempo_set_at_start_is_kept_across_a_restart(tmp_path: Path) -> None:
     for extra in (["--bpm", "97"], []):  # the second start has no --bpm
         async with _app(tmp_path, *extra) as (app, port):
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_device_settings.py -q`
Expected: FAIL: a collection error, `ImportError: cannot import name 'DEVICES_CONFIG_RESET' from 'dj_ledfx.main'`.

Run: `uv run pytest tests/test_main.py -q -k "device_settings or config_toml_s_device"`
Expected: FAIL: `2 failed, 8 deselected`, both with `assert 30 == 20`: a saved Govee rate doesn't apply.

- [ ] **Step 3: Load the device settings**

In `src/dj_ledfx/main.py`:

```diff
--- a/src/dj_ledfx/main.py
+++ b/src/dj_ledfx/main.py
@@ -17,10 +17,14 @@ import dj_ledfx.devices  # noqa: F401  # triggers backend auto-registration
 from dj_ledfx import metrics
 from dj_ledfx.config import (
     AppConfig,
+    DevicesConfig,
     DiscoveryConfig,
     EffectConfig,
     EngineConfig,
+    GoveeConfig,
+    LIFXConfig,
     NetworkConfig,
+    OpenRGBConfig,
     WebConfig,
     filter_fields,
     load_config,
@@ -136,14 +140,50 @@ def _parse_args() -> argparse.Namespace:
     return parser.parse_args()
 
 
-_CONFIG_SECTIONS = frozenset({"engine", "network", "web", "discovery", "effect"})
+_CONFIG_SECTIONS = frozenset(
+    {"engine", "network", "web", "discovery", "effect"}
+    | {"devices.openrgb", "devices.lifx", "devices.govee"}
+)
+# The run-once step that dropped the devices.* rows saved before they ever applied.
+DEVICES_CONFIG_RESET = "devices_config_reset"
+
+
+async def _reset_device_settings_once(state_db: StateDB) -> None:
+    """Delete state.db's devices.* rows, once (light-sync spec §8). No start ever applied
+    them, and the deployed database's came from an old config file, so the first start that
+    reads them runs on the code's defaults, as every start before it did. A setting saved
+    after this step is kept."""
+    if await state_db.has_mark(DEVICES_CONFIG_RESET):
+        return
+    rows = await state_db.fetch_all(
+        "SELECT section, key FROM config WHERE section LIKE 'devices.%' ORDER BY section, key"
+    )
+    await state_db.write_many(
+        [
+            ("DELETE FROM config WHERE section LIKE 'devices.%'", ()),
+            state_db.mark_statement(DEVICES_CONFIG_RESET),
+        ]
+    )
+    if rows:
+        settings = ", ".join(f"{section}.{key}" for section, key in rows)
+        logger.info("Dropped device settings that never applied: {}", settings)
+
+
+def _devices_config(sections: dict[str, dict[str, object]]) -> DevicesConfig:
+    return DevicesConfig(
+        openrgb=OpenRGBConfig(**filter_fields(OpenRGBConfig, sections.get("devices.openrgb", {}))),
+        lifx=LIFXConfig(**filter_fields(LIFXConfig, sections.get("devices.lifx", {}))),
+        govee=GoveeConfig(**filter_fields(GoveeConfig, sections.get("devices.govee", {}))),
+    )
 
 
 async def _load_config_from_db(state_db: StateDB) -> AppConfig | None:
     """Build AppConfig from StateDB config table.
 
     Returns None if the table holds none of AppConfig's sections (a fresh DB with no
-    migrated config). Other sections, such as the tempo clock's, don't count.
+    migrated config). Other sections, such as the tempo clock's, don't count. Device
+    settings the config refuses (a rate of 0, a strategy it doesn't know) are logged, and
+    every kind of light runs on its defaults.
     """
     all_config = await state_db.load_all_config()
 
@@ -160,14 +200,23 @@ async def _load_config_from_db(state_db: StateDB) -> AppConfig | None:
     discovery = DiscoveryConfig(**filter_fields(DiscoveryConfig, sections.get("discovery", {})))
     effect = EffectConfig(**filter_fields(EffectConfig, sections.get("effect", {})))
 
+    def config_with(devices: DevicesConfig) -> AppConfig:
+        return AppConfig(
+            engine=engine,
+            effect=effect,
+            network=network,
+            web=web,
+            devices=devices,
+            discovery=discovery,
+        )
+
+    defaults = config_with(DevicesConfig())  # the other sections are checked as before
     logger.info("Config loaded from StateDB")
-    return AppConfig(
-        engine=engine,
-        effect=effect,
-        network=network,
-        web=web,
-        discovery=discovery,
-    )
+    try:
+        return config_with(_devices_config(sections))
+    except (TypeError, ValueError) as refused:
+        logger.warning("Saved device settings refused ({}): the lights run on defaults", refused)
+        return defaults
 
 
 @dataclass
@@ -227,6 +276,8 @@ async def _run(args: argparse.Namespace) -> None:
     state_db = StateDB(db_path)
     await state_db.open()
 
+    # Before config.toml's migration, so a new database still takes its device tables.
+    await _reset_device_settings_once(state_db)
     # config.toml and presets.toml move into state.db once, at the first start that finds
     # them (a run-once mark); from then on the database is the source of truth
     await migrate_from_toml(
```

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_device_settings.py tests/test_main.py -q`
Expected: PASS (15 tests).

- [ ] **Step 5: Write the failing tests for the save**

Create `tests/web/test_config_device_settings.py`:

```python
"""PUT /api/config saves the device settings a request names in state.db, where the next
start reads them (light-sync spec §8, as the owner decided: the plan's ruling 20)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.main import _load_config_from_db


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    async with api_home(tmp_path, [FakeLight("a")], []) as api:
        yield api


async def test_a_device_setting_saved_in_the_app_applies_from_the_next_start(api: Api) -> None:
    body = {"devices": {"govee": {"max_fps": 20, "probe_interval_s": 0.8}}}
    assert (await api.client.put("/api/config", json=body)).status_code == 200

    config = await _load_config_from_db(api.home.db)

    assert config is not None
    assert (config.devices.govee.max_fps, config.devices.govee.probe_interval_s) == (20, 0.8)
    assert config.devices == api.app.state.config.devices
    # As config.toml's migration writes them: in the kind's own section, as JSON
    saved = await api.home.db.load_config("devices.govee")
    assert saved == {"max_fps": "20", "probe_interval_s": "0.8"}


async def test_a_save_that_names_no_device_setting_pins_no_default(api: Api) -> None:
    """Preview only's switch saves no device setting, so a default the code changes later
    still reaches each setting no one set."""
    body = {"engine": {"preview_only": True}}
    assert (await api.client.put("/api/config", json=body)).status_code == 200

    saved = await api.home.db.load_all_config()

    assert saved[("engine", "preview_only")] is True
    assert [section for section, _ in saved if section.startswith("devices.")] == []


@pytest.mark.parametrize("refused", [{"probe_interval_s": 0}, {"max_fps": "fast"}])
async def test_a_device_setting_the_config_refuses_saves_nothing(
    api: Api, refused: dict[str, Any]
) -> None:
    await api.client.put("/api/config", json={"devices": {"govee": {"max_fps": 20}}})
    body = {"devices": {"govee": {"latency_ms": 50.0, **refused}}}

    assert (await api.client.put("/api/config", json=body)).status_code == 400
    assert await api.home.db.load_config("devices.govee") == {"max_fps": "20"}
```

- [ ] **Step 6: Run them to see them fail**

Run: `uv run pytest tests/web/test_config_device_settings.py -q`
Expected: FAIL: `3 failed, 1 passed`. No device setting reaches state.db: `assert (30, 0.5) == (20, 0.8)`, and `assert {} == {'max_fps': '20'}` for each refused value. The preview-only test passes already: it holds Step 7 to saving only what a request names.

- [ ] **Step 7: Save the device settings**

In `src/dj_ledfx/web/router_config.py`:

```diff
--- a/src/dj_ledfx/web/router_config.py
+++ b/src/dj_ledfx/web/router_config.py
@@ -100,6 +100,21 @@ def _requires_restart(old: AppConfig, new: AppConfig) -> str:
     return "true" if rest(old) != rest(new) else "false"
 
 
+def _device_rows(body: dict[str, Any], devices: dict[str, Any]) -> dict[str, dict[str, str]]:
+    """The device settings a request names, as state.db keeps them: each kind's in its own
+    section (devices.govee), as JSON, as config.toml's migration writes them (light-sync spec
+    §8). Only those named, as the migration writes only what the file holds, so a save that
+    names none (preview only's) pins no default. `devices` is the merged config's, checked."""
+    named = body.get("devices")
+    if not isinstance(named, dict):
+        return {}
+    return {
+        f"devices.{kind}": {key: json.dumps(devices[kind][key]) for key in settings}
+        for kind, settings in named.items()
+        if kind in devices and settings
+    }
+
+
 async def _apply_live(request: Request, config: AppConfig) -> None:
     zones = getattr(request.app.state, "zone_manager", None)
     if zones is not None:
@@ -136,6 +151,8 @@ async def update_config(request: Request, body: dict[str, Any]) -> JSONResponse:
                 str_kv = {k: json.dumps(v) for k, v in value.items() if not isinstance(v, dict)}
                 if str_kv:
                     await db.save_config_bulk(section, str_kv)
+        for section, rows in _device_rows(body, result["devices"]).items():
+            await db.save_config_bulk(section, rows)
     except HTTPException:
         pass
     await _apply_live(request, new_config)
```

The route keeps its signature and has no docstring, so the OpenAPI schema doesn't change: no `api:types` step.

- [ ] **Step 8: Run them to see them pass**

Run: `uv run pytest tests/web/test_config_device_settings.py tests/web/test_router_config.py tests/web/test_preview_only_config.py tests/web/test_openapi_types.py -q`
Expected: PASS (18 tests).

- [ ] **Step 9: Run the gate**

```bash
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
uv run pytest -q 2>&1 | tail -1
```

Expected: ruff clean, `339 files already formatted`, mypy `Found 16 errors in 4 files (checked 153 source files)` (the baseline's errors, two more files checked), and `1888 passed, 1 skipped, 42 deselected`.

- [ ] **Step 10: Commit**

```bash
git add src/dj_ledfx/main.py src/dj_ledfx/web/router_config.py tests/test_device_settings.py tests/test_main.py tests/web/test_config_device_settings.py
git commit -m "feat(config): device settings load from state.db, and PUT /api/config saves them" -m "A run-once step first drops the devices.* rows that no start ever applied."
```

---


### Task 7: CLAUDE.md and the README

CLAUDE.md asks for the claude-md skill after each plan, and the spec's §11 names what must change: the latency decision, the horizon and the LIFX matrix ruling, the Govee probe. This branch also changed the device settings' load and save, the tracker's API, the persistence (migration 010) and the testing fakes. The README's horizon and latency lines go stale too (ruling 21).

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Write what this branch changed**

In `CLAUDE.md`:

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -104,19 +104,19 @@ src/dj_ledfx/ layout:
 - `devices/openrgb.py`, `devices/openrgb_backend.py` — OpenRGB. `OpenRGBServer`: an SDK server and the one connection all its devices share (its list read once a scan for them all), each exchange run in a thread in the server's `turn`. `OpenRGBIdentity`: what a device is, its name, serial and location, kept in its row's `extra` under `identity`. `OpenRGBAdapter`: a device at its place in the server's list, the place it was found at; each exchange checks the place still holds it, before and after, and a place holding another device or none leaves it disconnected, so the light goes offline until a scan finds it again. The backend finds each known device by its identity wherever it sits now and keeps its id (`place_known`), and gives a new device the number of its place, or the next one up that no known row's id holds (`device_ids`); a known device the server doesn't list stays offline, one warning at start
 - `devices/capabilities.py` — `DeviceCapabilities`: what a light can do (colour, matrix, multizone, effects); `LightReading` (`UNKNOWN`: it answered but can't say) and `try_read()` (None: no answer)
 - `devices/backend.py` — DeviceBackend ABC for protocol-level adapters: `discover()` gets the known devices' rows (`known`), and `rebuild()` sets an online light up again from its row with no network; `DiscoveredDevice.on_accepted` hands the tracker the light's round trips once the orchestrator takes the device in, and its `max_fps` is the adapter's `stream_fps`; `configured_fps(config, max_fps)`, the engine's rate or a kind's `max_fps` if lower, is the rate each backend builds its adapters with
-- `devices/govee/` — Govee WiFi LED protocol: `GoveeRazerAdapter` (`razer.py`: razer frames, one colour per segment, to UDP 4003, no replies, and razer's arming) or `GoveeColourAdapter` (`colour.py`: one `colorwc` colour, the frame's average, on any number of segments, capped at `GOVEE_COLOUR_FPS` by its own `stream_fps_cap`), chosen on the plan's `razer`; `adapter_base.py` holds what both share (reads, capture, the pacing: `_command` sends each command, power, a prepare's or a restore's, `COMMAND_GAP_S` after the last one, whichever call sent it, waiting only for what's left of the gap, and `_send` sends frames and the razer-on that arms the first at once; a restore that sends razer-off first, then reads an off back; where the segments sit, and the stored device types `govee_segment` and `govee_solid`); `output.py` (`GoveeOutput`, a lamp's own output in its device row's `extra`; `LampPlan`, `lamp_plan()`, `planned()` from a row; `LampOutputReport` and `lamp_report()`, how a lamp plays: as its live adapter does while it's online); the SKU table with each model's `razer`, `form` and `segments_from_top`; the transport, which times each status query to its reply and hands the round trip to the lamp's tracker (there's no probe loop). A status read asks twice (`STATUS_TRIES`), as LIFX reads do; a lamp silent to both raises `NoAnswer`
+- `devices/govee/` — Govee WiFi LED protocol: `GoveeRazerAdapter` (`razer.py`: razer frames, one colour per segment, to UDP 4003, no replies, and razer's arming) or `GoveeColourAdapter` (`colour.py`: one `colorwc` colour, the frame's average, on any number of segments, capped at `GOVEE_COLOUR_FPS` by its own `stream_fps_cap`), chosen on the plan's `razer`; `adapter_base.py` holds what both share (reads, capture, the pacing: `_command` sends each command, power, a prepare's or a restore's, `COMMAND_GAP_S` after the last one, whichever call sent it, waiting only for what's left of the gap, and `_send` sends frames and the razer-on that arms the first at once; a restore that sends razer-off first, then reads an off back; where the segments sit, and the stored device types `govee_segment` and `govee_solid`); `output.py` (`GoveeOutput`, a lamp's own output in its device row's `extra`; `LampPlan`, `lamp_plan()`, `planned()` from a row; `LampOutputReport` and `lamp_report()`, how a lamp plays: as its live adapter does while it's online); the SKU table with each model's `razer`, `form` and `segments_from_top`; the transport, which times each status query to its reply and hands the round trip to the lamp's tracker, and its probe loop (`start_probing(interval_s)`, light-sync spec §4): each round waits a random 75–125% of the config's `probe_interval_s` (`PROBE_SPREAD`), then asks each lamp that streams (`register_device(..., streaming=)`) for its status, allowing `PROBE_TIMEOUT_S` for the reply and skipping a lamp with a status query already in flight (that query's reply is timed anyway); it asks nothing while the transport can't hear UDP 4002, and `close()` ends it. A status read asks twice (`STATUS_TRIES`), as LIFX reads do; a lamp silent to both raises `NoAnswer`
 - `devices/lifx/` — LIFX LAN protocol (bulb/strip/tile discovery, packet encoding, transport); `base.py` shared adapter, `transport.py` `ask` (retries), `answer` (the reply's type checked and parsed by `parsed()`: None when the light can't say, `NoAnswer` when it's silent; GetVersion and the setup queries use it) and `query` (None either way, for the adapters' reads), and the echo probes, sent only to a light that streams (`register_device(..., streaming=)`), `products.py` `lifx_capabilities()` from the vendored `data/products.json`, and `matrix_form()`: a candle's or a tube's matrix wraps round a cylinder (the tile-chain adapter's `MatrixGeometry.form`), the rest are flat. Streamed frames fade over the gap to the next at the rate the adapter streams at (`stream_fade_ms` of its `stream_fps`), and it shows a frame half-way through (`display_ms`); strips and matrices take at most `LIFX_STRIP_FPS` and `LIFX_MATRIX_FPS` (20), and a matrix's `display_ms` adds `MATRIX_DISPLAY_MS`. Discovery skips a known online light before `GetVersion`, and a light silent to `GetVersion` or a setup query gives no record that scan
 - `looks/` — the look model, the built-ins (the handoff's M2 and M3 looks and the Firmware showcase, in looks.json's order from the vendored `data/looks.json`, then the six classics; the `speakers` look runs on the beat until M7, `NEEDS_UNTIL_M7`), and the store (saved looks, stars). The model reads, checks and writes back the layer modifiers (`Mask`: height, room, sub-zone or anchor; `Mirror`; `Transform`) and the look modifiers (`LookModifiers`). Reading is lenient (`look_from_dict`): saved data may hold a number no request could send now, so every bounded number is clamped to its bounds and NaN or an infinity is its neutral value (a saved transition's length: not finite or not above 0, a cut; over `MAX_TRANSITION_S`, 10 s: 10 s); only what can't be mapped is refused (an unknown kind, a height range from high to low, a firmware layer with a mask, data of the wrong shape). Places and distances are bounded by `MAX_DISTANCE_M` (1000 m either way) and `rotateDeg` is kept from -180 (not included) to 180. Its readers are `readers.py`'s, which the home model shares
 - `looks/selectors.py` — which lights a layer picks: light ids, or `type:<word>`. The look model parses a layer's `lights` setting into `Layer.lights` and writes it back as a list
-- `zones/` — `model` (every light, rooms, groups), `store`, `runtime` (a running look's layer stack and ring buffer, rendered at most `HORIZON_CAP_S` ahead and before brightness; it runs the look modifiers after the layers, and plays transitions: `begin_transition()`, twins, the lights it hands over (`handing_over`, `handed_over()`); mid-transition each light's `claim_for()`, `mode_of()`, `effect_name()`, `applied_key()` and `start_brightness()` answer for the look it follows until the midpoint; `transition_info()` shows the transition only in state `transition`, named after the look that drove most of the zone's lights, while `transitioning` says one is in hand whatever the state), `manager` (take-over, capture/restore, brightness, Stop all, resume, preview-only, the sharing policy, "Start again"; `start()` takes a transition, None for the look's own, and `switch(zone_id)` applies the lights a transition hands over; a light is readied to stream once and stays ready through starts, take-overs and transitions, its `applied_key()` being `STREAMS` in every look, and `_sync` routes a ready light to its new look before it reads any light; a light leaving its own effect for streaming is routed to the new rows and sent its frame at once just before the stop and again just after, `_leave_effect()` through the scheduler's `send_now()`), `lights` (LightMonitor: status and the 5 s/30 s polls), `attention` (the feed)
+- `zones/` — `model` (every light, rooms, groups), `store`, `runtime` (a running look's layer stack and ring buffer, rendered at most `HORIZON_CAP_S` (500 ms) ahead and before brightness; it runs the look modifiers after the layers, and plays transitions: `begin_transition()`, twins, the lights it hands over (`handing_over`, `handed_over()`); mid-transition each light's `claim_for()`, `mode_of()`, `effect_name()`, `applied_key()` and `start_brightness()` answer for the look it follows until the midpoint; `transition_info()` shows the transition only in state `transition`, named after the look that drove most of the zone's lights, while `transitioning` says one is in hand whatever the state), `manager` (take-over, capture/restore, brightness, Stop all, resume, preview-only, the sharing policy, "Start again"; `start()` takes a transition, None for the look's own, and `switch(zone_id)` applies the lights a transition hands over; a light is readied to stream once and stays ready through starts, take-overs and transitions, its `applied_key()` being `STREAMS` in every look, and `_sync` routes a ready light to its new look before it reads any light; a light leaving its own effect for streaming is routed to the new rows and sent its frame at once just before the stop and again just after, `_leave_effect()` through the scheduler's `send_now()`), `lights` (LightMonitor: status and the 5 s/30 s polls), `attention` (the feed)
 - `zones/home_view.py` (`HomeView`, what the zone manager asks of the map; `MapZones`: the whole home, rooms and sub-zones as zones), `zones/preview.py` (`PreviewManager`: one preview at a time), `zones/frames.py` (`Watchers.watching(stream)`: who watches which stream; `FrameFeed(live, previews)`: the web app's frames, read from the rings at now as the lights' are (`RingBuffer.colors_at`), each runtime's colours converted once, scaled by its zone's brightness, and only for the devices asked for)
 - `zones/layer_view.py` — a layer's view of its zone's LEDs (`LayerView`, from `layer_view()`): its mask's weights (`mask_weights()`) and the positions its mirror, then its transform, move the LEDs to (`mirrored()`, `transformed()`); the runtime keeps each layer's view, by its place in the look (a saved look may give two layers one id), until its modifiers or the LEDs change
 - `zones/look_modifiers.py` — the look modifiers as steps on a frame, each leaving the frame it's given as it was: `flashed()`, `Trails`, `warmed()` (by the frame's `time.evening`, towards `EVENING_FULLEST`) and `capped()`, with their constants
 - `zones/transition.py` — the transitions' maths: `switch_order()` (where each LED switches in a wipe, spread or dissolve, in the float64 `new_share()` works in) and `new_share()` (each LED's share of the new look, over each kind's soft edge, `EDGES`; a fade's is one number for every LED)
 - `home/` — the home map: `model` (`Home`, rooms, sub-zones, anchors, walls; home.json's shape), `geometry`, `shapes` (the five light shapes, `Placement`, `led_positions()`), `seed` (the vendored `data/home.json`, a byte copy with a test, and the owner's room names over it), `store` (`state.db`; a stored map it can't read is set aside in `home_map_unreadable`, which backups carry, and the seed is used), `guess` (placement guessing, each light in its form, which one classifier `_form()` decides for both `placed_in_form()` and `in_form()`; the old scene placements moved on), `map` (`HomeMap`: queries, each target's spot and LEDs kept until they change; edits through `_edit()`; `Space`; change listeners; `refit(device_id)` fits the placement of the light that came online to its form, a seed's or a guess's but never the owner's, and `main.py` spawns it for each light that comes online; `guess()` and `refit()` save through `_put()`, one transaction)
 - `home/sun.py` — the evening: `evening_amount(lat, lon, at)`, from 0 to 1, from astral's sun times (kept per place and UTC date), and `Evening`, the amount now at the home's location (`Home.location`), worked out at most once a second; `main.py` hands one to the zone manager. It never jumps: the sunrises and sunsets astral misses at the edges of polar night and day are filled in, an evening starts no earlier than the sunrise before its sunset, the night that ends polar night fades from civil dawn to its first sunrise, and within `POLE_DEG` (89.7°) of a pole it follows the sun's height
-- `latency/` — ProbeStrategy protocol + StaticLatency, EMA (three outliers in a row are a new level), WindowedMean and WindowedMedian (the default) strategies, the windowed two on one `WindowedLatency` base that works its statistic out as a sample lands, over a window of `LATENCY_WINDOW`; `STRATEGIES` maps each name a config can use to its factory, which `make_strategy()` looks up. `LatencyTracker` counts a round trip (a LIFX echo probe's, a Govee status read's), halved, only within `STREAMING_WINDOW_S` of a frame sent (`note_send`, `update_rtt`; `streaming` says it's within that window), and adds the device's `display_ms`; `measured` says one has landed since the last reset (never for a static strategy), and the API's `estimated` is its opposite; `tracker_for(cfg, seed_ms=, display_ms=)` builds one from a kind of device's config, for the OpenRGB, LIFX and Govee backends alike
-- `config.py` — Nested dataclass config (EngineConfig, EffectConfig, NetworkConfig, WebConfig, DevicesConfig) with load/save via tomllib/tomli_w; the rate constants (`LIFX_STRIP_FPS`, `LIFX_MATRIX_FPS`, `GOVEE_RAZER_FPS`, `GOVEE_COLOUR_FPS`), and `LATENCY_WINDOW`, re-exported from `latency/strategies.py`
+- `latency/` — ProbeStrategy protocol + StaticLatency, EMA (three outliers in a row are a new level), WindowedMean and WindowedMedian (the default) strategies, the windowed two on one `WindowedLatency` base that works its statistic out as a sample lands, over a window of `LATENCY_WINDOW`; `STRATEGIES` maps each name a config can use to its factory, which `make_strategy()` looks up. A strategy's `reset(latency_ms=None)` starts it again from a latency, or from its seed (a static one keeps its own). `doze.py`'s `DozeCheck` (light-sync spec §5) holds a light's last `KEPT` (40) round trips with their arrivals and, over at least `MIN_REPLIES` (10), calls the light dozing from the Rayleigh statistic of the arrivals' phases in the beacon cycle (`BEACON_S`, 102.4 ms) and their median: z ≥ `DOZE_Z` (7) to turn dozing, z ≥ `STAY_Z` (2) to stay, either way only with a median of at least `DOZE_MEDIAN_MS` (50). `LatencyTracker` counts a round trip (a LIFX echo probe's, a Govee status read's) only within `STREAMING_WINDOW_S` of a frame sent (`note_send`, `update_rtt`; `streaming` says it's within that window): its strategy takes all of a dozing light's round trip and half of an awake light's, and when the mode changes it starts again from the held round trips at the new share, logged at INFO with z and the median. It adds the device's `display_ms`; `link_latency_ms` is the strategy's part and `dozing` the mode. `recall(latency_ms, dozing)` starts it from a latency and mode the light had before, and `reset()` (a light come back) from the ones it has, both dropping the held round trips; `measured` says one has landed since the last reset or recall (never for a static strategy), and the API's `estimated` is its opposite; `tracker_for(cfg, seed_ms=, display_ms=, name=)` builds one from a kind of device's config, for the OpenRGB, LIFX and Govee backends alike (`name`, the light's, for the log). `memory.py`'s `LinkMemory` (spec §7) keeps each light's `link_latency_ms` and mode in state.db's `link_memory` (migration 010): loaded at start, recalled by the discovery orchestrator as it takes a light in, and written by `run()` every `LINK_MEMORY_EVERY_S` (30 s) and once more when cancelled at shutdown, for each light measured since it came online whose mode changed or whose latency moved over `MOVED_MS` (5 ms)
+- `config.py` — Nested dataclass config (EngineConfig, EffectConfig, NetworkConfig, WebConfig, DevicesConfig) with load/save via tomllib/tomli_w; the rate constants (`LIFX_STRIP_FPS`, `LIFX_MATRIX_FPS`, `GOVEE_RAZER_FPS`, `GOVEE_COLOUR_FPS`), and `LATENCY_WINDOW`, re-exported from `latency/strategies.py`; Govee's `probe_interval_s` (0.5 s by default, positive) paces its probe loop
 - `effects/params.py` — EffectParam descriptor for runtime introspection
 - `effects/registry.py` — Effect auto-registry via __init_subclass__, get_effect_classes/schemas
 - `effects/presets.py` — PresetStore with TOML persistence
@@ -137,11 +137,11 @@ src/dj_ledfx/ layout:
 - `readers.py` — `Reader(error)`: the readers of stored and sent JSON that the home map and the looks share (any number, a finite one, text, a list of numbers, an object), each raising its model's error
 - `timing.py` — `utcnow()`, `as_utc()`, `utc_text()` and `parse_utc()` (a saved time as UTC text and back, for the zone and tempo stores), the one-second rate window (`RATE_WINDOW_S`, `trim_window`) and `paced()`, the fixed-period loop the engine and the scheduler run
 - `events.py` — Typed callback event bus (sync, non-blocking callbacks only) + device events; the zones' events (`ZonesChanged`, `PreviewOnlyChanged`, `LightsChanged`, `AttentionChanged`) live in `zones/model.py`, the tempo's (`TempoChanged`, `DecksChanged`) in `tempo/model.py`
-- `persistence/` — SQLite-backed state persistence (state_db.py, toml_io.py, debounced_writer.py, migrations/); `StateDB.write_many` runs statements as one transaction, and `has_mark`/`mark_statement` mark run-once steps
-- `devices/discovery.py` — DiscoveryOrchestrator: multi-wave scanning, fast reconnect, ghost promote/demote (one `_promote()`); a Govee lamp's output: `set_output()` keeps it in the row and plays it at once, `output_of()` says how the lamp plays, `apply_outputs()` plays what restored rows hold; scans and output changes take turns (`_scan_lock`: a Govee scan has one reply handler)
+- `persistence/` — SQLite-backed state persistence (state_db.py, toml_io.py, debounced_writer.py, migrations/); `StateDB.write_many` runs statements as one transaction, and `has_mark`/`mark_statement` mark run-once steps; backups leave out `link_memory` (migration 010), a cache measured again within seconds
+- `devices/discovery.py` — DiscoveryOrchestrator: multi-wave scanning, fast reconnect, ghost promote/demote (one `_promote()`); a Govee lamp's output: `set_output()` keeps it in the row and plays it at once, `output_of()` says how the lamp plays, `apply_outputs()` plays what restored rows hold; scans and output changes take turns (`_scan_lock`: a Govee scan has one reply handler); a light it takes in, new or a ghost promoted, starts from its link memory before its first frame (`_recall`), and a light set up again with its own tracker (`_play`) keeps that tracker's latency
 - `devices/ghost.py` — GhostAdapter: placeholder for offline devices (is_connected=False, send_frame no-op)
 - `status.py` — SystemStatus health tracking
-- `main.py` — Application coordinator (startup/shutdown orchestration; serves the web app with granian's embedded server, on the app's own event loop, and stops it through `_WebServer.stop()`: close the websockets, then granian's `Server.stop()`; `_spawn()` runs the event handlers' work as background tasks and logs one that fails)
+- `main.py` — Application coordinator (startup/shutdown orchestration; serves the web app with granian's embedded server, on the app's own event loop, and stops it through `_WebServer.stop()`: close the websockets, then granian's `Server.stop()`; `_spawn()` runs the event handlers' work as background tasks and logs one that fails; `_load_config_from_db` builds every section, the device kinds' (`devices.openrgb`, `devices.lifx`, `devices.govee`) included, after the run-once `_reset_device_settings_once`; it loads the link memory before the discovery orchestrator and runs its writer as a task)
 
 frontend/ (Vite + React 19 + TypeScript + shadcn/ui + Tailwind CSS v4):
 - `src/lib/ws-client.ts` — Multiplexed WS client with reconnection
@@ -197,7 +197,7 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 ## Key Design Decisions
 
 - Ring buffer stores FUTURE frames. High-latency devices read newer (further-future) frames.
-- Each zone runtime renders at `now + horizon` into its own ring buffer: its lights' largest latency plus a rendered frame (a zone over its budget renders every few ticks), at most 120 ms (`HORIZON_CAP_S`) and within the lookahead; a light slower than that gets the newest frame and runs late by the difference. A LIFX matrix sits just past the cap (about 123 ms with its display delay, so about 3 ms late, against a measured p95 lateness of 42 ms); the cap stays, since raising it delays every look change in its zone (the light-output plan's ruling 1).
+- Each zone runtime renders at `now + horizon` into its own ring buffer: its lights' largest latency plus a rendered frame (a zone over its budget renders every few ticks), at most 500 ms (`HORIZON_CAP_S`) and within the lookahead (1 s); a light slower than that gets the newest frame and runs late by the difference. The cap was 120 ms until light sync (its spec's §6): a dozing Govee lamp's latency is its whole round trip, up to about 0.4 s, so a zone with one renders that far ahead, and a LIFX matrix (about 123 ms with its display delay), 3 ms late under the old cap, is in step, its zone rendering about 140 ms ahead. That overturns the light-output plan's ruling 1; its cost, the start freeze, is in Gotchas.
 - A send loop reads its light's moment, `now + device_latency`, blended from the two frames either side of it, and the web app's feed reads now the same way. A moment that shifts by less than a frame (a latency measured again; the distributor's and the engine's ticks, each stamped with the time it ran) shifts the colours as little. Read from the nearest frame, near half-way between two frames it showed as one frame sent twice and the next skipped, which made the LIFX bulbs judder. A zone over its budget still sends each light at the light's own rate, the blend filling in between the frames it renders, so its unchanged-frame skip sheds no sends. A light past the horizon cap still gets the newest frame alone, and a flash shorter than a frame reaches a light spread over two sends at lower levels.
 - A frame in a ring buffer is never changed after it's written: the runtime renders a new array every tick, the ring hands out frames and a frame's own colours, and `lerp` and `to_device_colors` make the new arrays each send uses.
 - Passive Pro DJ Link mode for MVP (no virtual CDJ handshake needed for beat packets).
@@ -209,7 +209,7 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 - The tempo settings (the lock, the internal BPM with how and when it was set, the last DJ set) live in `state.db`'s config table under section `tempo`. They join backup and restore, and a restore applies them at once.
 - Event bus callbacks must be non-blocking (<1ms). Async work uses `create_task()`.
 - Per-device send loops, each device at its own rate: every adapter is built at the configured rate, the engine's or its kind's `max_fps` if lower, and states what it streams at (`stream_fps`): OpenRGB devices, LIFX bulbs and a Govee lamp by razer (30 by default) at the configured rate, LIFX strips and matrices at most 20 a second, and a Govee lamp by `colorwc` at most 10 whatever the config says; a frame equal to the last one sent is skipped for up to a second, unless the route was set, the adapter changed or the light dropped out since. Distributor writes target_time floats to depth-1 FrameSlots — no numpy copies until actual send — from the tick before a device is due, so a light slower than the engine isn't written frames it never takes; `frames_dropped` counts only frames still untaken a period after the device was due.
-- Latency is one way: a windowed median seeded at the config's `latency_ms` (LIFX 10 ms, Govee 100 ms), plus the device's display delay (half a LIFX fade; a matrix's `MATRIX_DISPLAY_MS` more). Idle round trips are ignored: Wi-Fi power save makes them long. So LIFX's echo probes go only to a light that streams. OpenRGB devices keep the device-type heuristics (USB 5 ms) permanently: nothing probes them, and the scheduler never times a send. A light's latency is `estimated` in the API until a round trip measured while it streams lands.
+- Latency is one way: a windowed median seeded at the config's `latency_ms` (LIFX 10 ms, Govee 100 ms), plus the device's display delay (half a LIFX fade; a matrix's `MATRIX_DISPLAY_MS` more). How much of a round trip is one way is the doze check's (light-sync spec §5): the access point holds a dozing light's frames until it wakes, at a beacon, and its replies come straight back, so its latency is its whole round trip; an awake light's is half. A dozing light's replies bunch at one phase of the 102.4 ms beacon cycle and its round trips run long (a query waits for a wake), and the check needs both. Idle round trips are ignored: Wi-Fi power save makes them long. So LIFX's echo probes (every 2 s) and the Govee probe loop (about every 0.5 s) go only to a light that streams; the light monitor's Govee reads every 5 s count too. OpenRGB devices keep the device-type heuristics (USB 5 ms) permanently: nothing probes them, and the scheduler never times a send. A light's latency is `estimated` in the API until a round trip measured while it streams lands. Each light's latency and mode are remembered in state.db (`link_memory`), so the first look after a restart starts every light where it was; backups leave them out, since a backup restored on another network would carry the wrong delays.
 - Brightness applies at send: rings hold frames before brightness; routes and the frame feed scale them.
 - Layer modifiers change where a field is drawn, never the effect: a mask weighs each LED (a soft edge of `MASK_EDGE_M` for a height band or an anchor's reach; a room or a sub-zone by its outline, in or out), and a mirror, then a transform, move the positions the effect sees. A firmware layer takes none (400).
 - The look modifiers run on each new frame in a fixed order: the downbeat flash, trails (so a flash leaves one), the evening (the frame's `time.evening` signal), the copy of what the firmware lights show, then the brightness cap. Only the cap reaches a light that runs its own effect: it starts at the zone's brightness times the cap (`start_brightness()`). A light's applied key holds that brightness beside the look's generation and the layer, so a new brightness or cap starts those effects again, and only those.
@@ -229,7 +229,7 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 - Zones replace the transport, scenes and pipelines (spec §4.3): starting a look on a zone takes its lights from other zones (newest wins); what's running persists and resumes on start; there is nothing to press play on
 - Capture/restore: a light is captured before dj-ledfx first changes it; the capture survives hand-overs between zones and restarts (in state.db) and is released on Off or Stop all. `capture_state()` returns None by default (can't capture: Off leaves it alone)
 - Sharing policy (spec §6.4): dj-ledfx switches a light on only when a look is applied. A zone light switched off elsewhere drops out and rejoins when it's back on; a stopped firmware effect is re-sent at the next 5 s poll while the light is on; idle lights are read every 30 s and never changed
-- Light status: a light whose read fails three 5 s polls in a row (no answer, or any error) is `offline` (a wall switch), whatever its protocol; `switched-off` is a power reading, not an attention item. A failed read isn't a miss when the light was heard from since its last read ended (`last_heard`: a Govee lamp's status replies, every LIFX reply, echoes included, though only a streaming light is probed), and a light set up again (`DeviceOnlineEvent`, `DeviceDiscoveredEvent`) starts counting afresh
+- Light status: a light whose read fails three 5 s polls in a row (no answer, or any error) is `offline` (a wall switch), whatever its protocol; `switched-off` is a power reading, not an attention item. A failed read isn't a miss when the light was heard from since its last read ended (`last_heard`: a Govee lamp's status replies, the probe loop's included, and every LIFX reply, echoes included; only a light that streams is probed), and a light set up again (`DeviceOnlineEvent`, `DeviceDiscoveredEvent`) starts counting afresh
 - A Govee lamp that misses three reads goes offline and gets no frames until a scan finds it.
 - Preview-only (`engine.preview_only`, `PUT /api/config`) applies at once: looks run and stream to the web preview, the lights are left alone. It's kept across restarts in state.db's config table
 - Scenes became device-group zones once (migration 004), not running; the old UI's effect endpoints take `?zone=`
@@ -261,6 +261,7 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 - OpenRGB device tests run on `tests/openrgb_fakes.py`'s SDK server: `serve()` patches openrgb-python's client with one that reads a changed list as openrgb-python does, `Listed` devices record what they're sent, `orgb_row()` is a known device's row, and `adapter_of()` connects an adapter over a device a test shapes itself
 - Integration tests drive a `TempoClock` with a DJ's beat (`beat_event()`) → full pipeline → mock DeviceAdapter
 - Shared fakes: `tests/conftest.py` (`FakeLight`, a controllable light, whose `heard` is its `last_heard`; `GlowFirmware`, a firmware effect; `device_stats()`, `render_ctx()`, `tempo_ctx()` (a moment some beats into a steady tempo) and `beat_ctx()` (that moment as a 1D effect sees it); `events()`, every event of one type a bus emits; `builtin_look()`, a built-in look by id; `Hold`, a call held part-way; the `db` fixture, an open state.db; `as_schema()`, a state.db made to look as an older schema left it, for an upgrade test (it drops `placements.source`, the one column a migration can't add twice); the PC's `SERVER`, `OPENRGB`, `pc_lights()`, `pc_part_info()`, and `lamp_info()`, `colours()`; `RingSource` and `ring_route()`, a route over a ring's frames at a `brightness`; `nearest_frame()`, the frame in a ring nearest a moment), `tests/zone_home.py` (a zone manager over fake lights, and `Home.tempo`, a real `TempoClock` over its state.db; `zone_record()`; `Home.routes`, the fake scheduler, keeps every route set in order, `history`, and sends the route's newest colours, black before the zone's first frame, down every streaming route whenever a light is asked something, and one light's at `send_now()`), `tests/api_home.py` (the same behind the web app; `discovery=` stands in for the discovery orchestrator, and `backends=` gives it a real one over those backends), `tests/lifx_fakes.py` (`FakeLifxTransport`, a LifxTransport with a faked socket, whose `quiet` lists the message types a light never answers; `lifx_bulb/strip/candle()`; `read_hex()` for hex fixtures), `tests/govee_fakes.py` (the test lamp: `lamp_record()`, its device row `lamp_row()`, and `govee_lamp()`, a `FakeLight` with Govee's caps; the SKU table's kinds `UPRIGHT` and `NO_RAZER`, registered under `TEST_MODEL`; `lamp_transport()`, a transport that hears the lamp, `sent()`, what went through it, and `send_times()`, when), `tests/openrgb_fakes.py` (`serve()`, `Listed`, `orgb_row()`, `adapter_of()`, and `PC`, the test server's id), `tests/tempo_fakes.py` (`FakeTime`, `tempo_clock()`, `beat_event()`, `beat_packet()` (raw `next_beat_ms` and `capability` too), `play()`, `PLAYER`, `START`, `START_WALL`); `pythonpath = ["tests"]` makes them importable
+- `tests/doze_fakes.py`: reply moments for the doze check, from `START` (`on_beat()`, every fifth beacon at one phase; `bunched()`, within 3 ms of it; `spread()`, phases spread evenly; `half_bunched()`, half at one phase, which neither turns a light dozing nor wakes one; `random_moments(seed)`), and `Lamp`, a tracker named `test-lamp` on a fake clock whose light streams, seeded at `SEED_MS` (100 ms); `tests/fixtures/latency/doze-replay-*.json` hold the doze spike's replies from lamps a–d, in relative times
 - `tests/runtime_fakes.py`: the zone runtime's fakes, which the runtime's, the modifiers' and the transitions' tests share: `LIGHTS` (a tile, a bulb and a lamp), `FlatField`, `PlaceField` (each LED's colour is the place the effect sees it at), `register_fields()`, `field_layer()`, `place_layer()`, `glow_layer()`, `look_of()`, `placed_light()`, `runtime_of()`, `latest()` and `sent()`, and the capabilities `TILE`, `BULB` and `LAMP` and a 2 s `FADE`, each declared only there; `tests/zones/conftest.py`'s `_fields` fixture registers the fields (`pytest.mark.usefixtures("_fields")`). `build_home()` and `assemble()` (`tests/zone_home.py`) and `make_home` (`tests/zones/conftest.py`) take `evening=`, the evening's amount as a function (0 when it's left out)
 - The repo is public: new code, tests, commits and PRs carry no LAN address, MAC, light name or model number. A test address is `127.0.0.1`, a Govee device id `test-lamp`, and a test that needs a Govee model reads one from `SKU_REGISTRY` or adds its own key (`test-model`)
 - Every test starts from the app's effect registry (an autouse fixture in conftest); a test effect defined with `register=False` never leaks
@@ -280,7 +281,7 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 - Beat packets on port 50001 are broadcast (free), but status packets on port 50002 require virtual CDJ registration
 - Phase wraps from ~1.0 to ~0.0 at each beat — effects must handle this discontinuity: one that moves across beats reads `beats`, and a BPM energy never sets a speed (it would jump wherever the phase it scales wraps)
 - Pro DJ Link requires binding to the correct network interface (not localhost)
-- A zone's ring has frames from its first tick, `horizon` ahead (at most `HORIZON_CAP_S`), and a light whose moment comes before the first frame is sent that frame, so a look reaches every light within a frame or two of its start
+- A zone's ring has frames from its first tick, `horizon` ahead (at most `HORIZON_CAP_S`), and a light whose moment comes before the first frame is sent that frame until its moment reaches it (the start freeze). In most zones a look reaches every light within a frame or two of its start, but a zone with a dozing Govee lamp holds its other lights on its first frame for up to about 0.4 s, at every start, and a change to a running look shows that late too; brightness applies at send, so it isn't delayed
 - Only CDJ-3000 generation packets (0x1F) supported in MVP; older hardware silently ignored
 - R3F: `<threeLine>` is the correct intrinsic for THREE.Line (not `<line_>`) — crashes if wrong
 - R3F: `useFrame` for live-updating geometry; drei `Line` component only updates on prop change via React state
@@ -319,7 +320,7 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 - LIFX scripts can run beside the deployed app: `LifxTransport.open()` binds an ephemeral port
 - A LIFX matrix queues `SetTileState64` above about 30 a second; matrices are capped at 20
 - OpenRGB: parts in an `Off` mode keep a stale colour buffer, so `/api/lights` shows a colour for a dark part; read the mode to know. The Corsair Commander Core reports 0 LEDs
-- UDP 4002 (Govee replies) belongs to whichever program binds it first. The deployed app holds it; Home Assistant's `govee_light_local` retries every 10 minutes, at about :x8 past the hour, and takes it if dj-ledfx is down then, which leaves dj-ledfx deaf to Govee replies (the log warns `could not bind port 4002`): it can't read a lamp or tell one stopped answering, and keeps sending. Stop the app well clear of :x8, and after a restart check that `ss -ulne 'sport = :4002'` shows `uid:10001` (`ss -p` needs root)
+- UDP 4002 (Govee replies) belongs to whichever program binds it first. The deployed app holds it; Home Assistant's `govee_light_local` retries every 10 minutes, at about :x8 past the hour, and takes it if dj-ledfx is down then, which leaves dj-ledfx deaf to Govee replies (the log warns `could not bind port 4002`): it can't read a lamp, tell one stopped answering or measure its latency (the probe loop asks nothing, so each lamp keeps the latency it started with), and keeps sending. Stop the app well clear of :x8, and after a restart check that `ss -ulne 'sport = :4002'` shows `uid:10001` (`ss -p` needs root)
 - Govee `colorwc` at 40 a second ran 9 commands behind, and two lamps flooded that way were unreachable for about ten minutes; `GOVEE_COLOUR_FPS` caps it at 10 whatever the config says
 - A Govee lamp can show nothing for a razer frame with more colours than it has segments: given 15, two of three upright lamps of 14 stayed dark and the third dropped the extra. The SKU table's count, or a lamp's own output, is the count the lamp shows. Check a new model's count by eye with `scripts/govee_razer_check.py`
 - A Govee lamp streaming razer still answers status queries (an upright lamp answered 9 of 10 while streaming, 5 of 5 before), so one that stops answering mid-look is still taken offline; a read asks twice, so one lost reply isn't a miss
@@ -328,8 +329,9 @@ web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4
 - A Govee lamp on white keeps its white LEDs lit under razer, which drives only the colour LEDs, and every streamed colour washes out. So the razer adapter's prepare sends razer-off (a lamp a run left in razer takes the white off too), then a `colorwc` of black (it can't flash) at colour temperature 0, then full brightness, each command `COMMAND_GAP_S` after the last; the capture comes before the prepare, so the restore still sends the white back
 - A run beside the deployed app can't bind UDP 50001: it warns and runs on its internal clock, with `prodjlink.state` "disconnected". To hear Pro DJ Link there, pass `--dj-listen 127.0.0.1:0` (any free loopback port; `GET /api/inputs` names it), and serve on a free `--web-port` (the deployed app holds 8080)
 - A run beside the deployed app can't hear Govee replies, so it can't capture a lamp, and Off can't restore one: keep Govee lamps out of such a run (delete their rows from its copy of the database)
-- The container mounts `config.toml` read-only (a file bind mount: saving logs `Device or resource busy`); `state.db` lives in the `dj-ledfx_state` volume. At start the app reads its config from state.db, and config.toml only while state.db holds none of `AppConfig`'s sections, so settings saved from the web app, preview-only included, survive a restart
-- `migrate_from_toml()` runs once per database: the first start that finds config.toml or presets.toml migrates them and writes the run-once mark `toml_migrated`, and a setting saved before then (preview-only, the tempo) doesn't stop it. Migration 008 gave the mark to every database that already held the app's config (any section but `tempo`), the deployed one included, so its read-only config.toml isn't migrated again
+- The container mounts `config.toml` read-only (a file bind mount: saving logs `Device or resource busy`); `state.db` lives in the `dj-ledfx_state` volume. At start the app reads its config from state.db, and config.toml only while state.db holds none of `AppConfig`'s sections, so settings saved from the web app, preview-only included, survive a restart. The device settings (sections `devices.openrgb`, `devices.lifx`, `devices.govee`) load from state.db too since light sync, and before it none ever applied; a device setting the config refuses (a rate of 0, a strategy it doesn't know) logs a warning, and every kind of light runs on its defaults. `PUT /api/config` saves the flat sections whole but only the device settings a request names, each in its kind's section as JSON, as config.toml's migration writes them: a device setting changed in the app applies from the next start, and a save that names none (preview-only's) pins no device default, so a default changed in the code still reaches each setting no one set
+- `migrate_from_toml()` runs once per database: the first start that finds config.toml or presets.toml migrates them and writes the run-once mark `toml_migrated`, and a setting saved before then (preview-only, the tempo) doesn't stop it. Migration 008 gave the mark to every database that already held the app's config (any section but `tempo`), the deployed one included, so its read-only config.toml isn't migrated again. The light-sync run-once step `devices_config_reset` runs just before it: it deleted the deployed database's `devices.*` rows, which came from an old config file and never applied (`ema` over 60 samples, Govee at 40 frames a second, a 50 ms LIFX seed, Govee probes every 5 s), and logs what it dropped; a new database still takes config.toml's device tables
+- A restored backup's device settings come back with it and apply from the next start, old ones included (the owner's decision): one exported before light sync brings back the `devices.*` rows `devices_config_reset` dropped, and the step doesn't drop them again, since backups carry no run-once marks. To keep a default, take its row out of the file before restoring it
 - `Path.resolve()` raises `ValueError` on a NUL byte (a request for `/%00`); path guards must catch it, as `_file_within` in `web/app.py` does
 - FastAPI's own 422 echoes the request's input, and JSON can't carry a NaN, so a NaN in a body gave a 500; `unprocessable` in `web/errors.py` answers it as text
 - Web app: tokens.css names both a colour and a font size `control`; `text-control` is the colour, `text-size-control` the size
```

In `README.md`:

````diff
--- a/README.md
+++ b/README.md
@@ -1,6 +1,6 @@
 # dj-ledfx
 
-Beat-synced LED lighting engine driven by Pioneer Pro DJ Link. A passive UDP listener picks beat packets straight off the DJ booth network, a 60 fps effect engine renders frames ahead of time into a future-frame ring buffer, and a lookahead scheduler sends each device the frame that matches its measured latency — so USB peripherals (~5 ms), LIFX (~20 ms a bulb, ~35 ms a strip, ~120 ms a matrix), and Govee (~100 ms) fixtures all hit the beat together. Ships with a FastAPI + WebSocket backend, a React control UI with a three.js 3D scene editor, and Prometheus/Grafana monitoring.
+Beat-synced LED lighting engine driven by Pioneer Pro DJ Link. A passive UDP listener picks beat packets straight off the DJ booth network, a 60 fps effect engine renders frames ahead of time into a future-frame ring buffer, and a lookahead scheduler sends each device the frame that matches its measured latency — so USB peripherals (~5 ms), LIFX (~20 ms a bulb, ~35 ms a strip, ~120 ms a matrix), and Govee (from ~15 ms, to ~300 ms for a lamp whose Wi-Fi dozes) fixtures all hit the beat together. Ships with a FastAPI + WebSocket backend, a React control UI with a three.js 3D scene editor, and Prometheus/Grafana monitoring.
 
 ## How it works
 
@@ -15,7 +15,7 @@ CDJ/XDJ decks ──UDP:50001──▶ Pro DJ Link listener ──▶ TempoClock
                         OpenRGB · LIFX LAN · Govee LAN adapters
 ```
 
-The key idea: the ring buffer stores *future* frames. Each zone renders at `now + horizon` (its slowest light's latency plus a frame, at most 120 ms); each device's send loop picks the frame at `now + device_latency`, so higher-latency devices simply read further into the future.
+The key idea: the ring buffer stores *future* frames. Each zone renders at `now + horizon` (its slowest light's latency plus a frame, at most 500 ms); each device's send loop picks the frame at `now + device_latency`, so higher-latency devices simply read further into the future.
 
 ## Features
 
@@ -23,7 +23,7 @@ The key idea: the ring buffer stores *future* frames. Each zone renders at `now
 - **Always-running tempo clock** — with no DJ, an internal clock keeps the tempo: set a BPM, tap it or nudge the phase from the web app, and it's kept across restarts. A DJ who starts playing takes over; when the decks go quiet, the clock carries on at the DJ's last tempo without a jump.
 - **Modifiers and transitions** — a look's layers can be masked (to a height band, a room, a sub-zone or the reach of an anchor), mirrored and moved; a look can leave trails, flash on every downbeat, stay under a brightness cap (lights running their own effects included) and turn warmer and dimmer in the evening, from an hour before sunset at the home's location. A look comes in with a cut, fade, wipe, spread or dissolve from whatever the lights showed, and lights running their own effects switch at the transition's midpoint.
 - **60 fps effect engine** — effects are pure-NumPy render functions behind an auto-registry, with a hot-swappable effect deck, runtime-introspectable parameters, and TOML presets. Built-in effects: beat_pulse, breathe, color_chase, fire_storm, rainbow_wave, strobe.
-- **Per-device latency compensation** — per-device send loops run at each device's own rate (LIFX strips and matrices at most 20 a second, a Govee lamp 30 by razer or 10 in one colour) and skip a frame the device already shows; latency is one way, half the round trips measured while a device streams (a LIFX echo probe's, a Govee status read's), in a windowed median (static, EMA and windowed-mean strategies remain), plus the device's display delay.
+- **Per-device latency compensation** — per-device send loops run at each device's own rate (LIFX strips and matrices at most 20 a second, a Govee lamp 30 by razer or 10 in one colour) and skip a frame the device already shows; latency is one way, measured while a device streams (a LIFX echo probe every 2 s, a Govee status probe about every 0.5 s): half the round trip of a light that's awake, and all of it for a light whose Wi-Fi dozes, which its replies give away by bunching at the access point's beacons. It's kept in a windowed median (static, EMA and windowed-mean strategies remain), plus the device's display delay, and remembered across restarts.
 - **Device adapters** — OpenRGB (USB/desktop RGB), LIFX LAN (bulbs, strips, tile chains), Govee LAN (one colour per segment by razer, or one colour, with an SKU registry and each lamp's own output). Discovery orchestrator with multi-wave scanning, fast reconnect, and ghost placeholders for offline devices.
 - **Multi-scene 3D spatial mapping** — place devices in 3D space, map effects spatially (linear/radial), and run independent scene pipelines with conflict detection.
 - **Web control** — FastAPI REST + WebSocket backend (binary LED frame broadcast) with a React 19 + TypeScript UI: live performance view, effect deck, transport controls, device monitor, and a react-three-fiber 3D scene editor.
````

- [ ] **Step 2: Run the skills**

Run the `claude-md-management:claude-md-improver` skill (audit and targeted updates), then `/claude-md-management:revise-claude-md` for what this branch taught. Keep Step 1's lines, keep design values and anything private out, and take only changes that match the code; the owner sees them in the PR.

- [ ] **Step 3: Check that nothing still says the old**

```bash
git grep -n -e "no probe loop" -e "at most 120 ms" -e "HORIZON_CAP_S = 0.12" -e "halved" -- . ':!docs'
```

Expected: no lines. The plans and specs under `docs/` keep their history.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: CLAUDE.md and the README for light sync"
```

---


### Task 8: Catch up with master, and the PR

CLAUDE.md ends every plan with a pull request. This task rebases, runs every gate, checks that nothing private went in, and opens the PR. It never merges, and it touches no light. After it, /executing-plans' final review of the whole branch runs; fix every finding and push the fixes to the PR. Then stop and hand Task 9 to the owner.

**Files:**
- Modify: whatever the rebase leaves in conflict
- Create: `/tmp/ls-pr-body.md` (not committed)

- [ ] **Step 1: Rebase onto `master`**

```bash
git fetch origin
git rebase origin/master
git log --oneline -8 origin/master
ls src/dj_ledfx/persistence/migrations/ | tail -2
```

The branch hasn't been pushed, so rebasing is safe. If a conflict touches `CLAUDE.md`, `README.md`, `src/dj_ledfx/main.py`, `src/dj_ledfx/config.py` or `src/dj_ledfx/devices/discovery.py`, keep both sides. If master brought a migration numbered 010 of its own, rename this branch's to the next free number, raise the schema version in Task 5's tests to match, and say so in the PR. A conflict anywhere else: stop and tell the owner.

- [ ] **Step 2: Run every gate**

```bash
uv sync --extra web
uv run ruff check . && uv run pytest -q 2>&1 | tail -1
uv run ruff format --check . 2>&1 | tail -1 ; uv run mypy src/ 2>&1 | tail -1
uv run pytest tests/web/test_openapi_types.py -q
```

Expected: ruff clean; `1888 passed, 1 skipped, 42 deselected` on `1d6ed22`, plus whatever master added; no format findings; mypy no worse than Before Task 1's baseline; and the OpenAPI test green, since the API didn't change.

- [ ] **Step 3: Check that nothing private is in the branch**

```bash
git diff origin/master -- . ':!docs/design' ':!src/dj_ledfx/home/data' > /tmp/ls-diff.txt
grep -nE '^\+.*\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|^\+.*\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/ls-diff.txt | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0|239\.255\.255\.250)\b' || echo "no addresses"
uv run python - > /tmp/ls-private.txt <<'EOF'
import json
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
from dj_ledfx.home.seed import OWNER_ROOM_NAMES
home = json.load(open("docs/design/web-app/home.json"))
words = {light["model"] for light in home["lights"] if light.get("model")}
words |= {light["name"] for light in home["lights"]}
words |= {room["name"] for room in home["rooms"]} | set(OWNER_ROOM_NAMES.values())
words |= set(SKU_REGISTRY)
print("\n".join(sorted(word for word in words if len(word) > 2)))
EOF
grep '^+' /tmp/ls-diff.txt | grep -ciwFf /tmp/ls-private.txt || echo "no names or models"
grep '^+' /tmp/ls-diff.txt | grep -ci 'ssid' || echo "no SSIDs"
```

Expected: `no addresses`, `no names or models` and `no SSIDs` (each held on the dry run's diff). `239.255.255.250` is Govee's multicast group, a protocol constant. The words come from `home.json` and the SKU table at run time, so they're never typed here, and the greps print only counts. Anything found goes: replace it with `127.0.0.1`, `test-lamp`, a recording's label or a made-up name. If a count comes from a line this branch only moved, tell the owner instead.

- [ ] **Step 4: Write the PR description**

Write `/tmp/ls-pr-body.md` with these sections, in this order.

**Summary.** Light sync, `docs/superpowers/specs/2026-10-04-light-sync-design.md`: Govee lamps probed about every 0.5 s while they stream; a light whose Wi-Fi dozes recognised by when its replies land, and given its whole round trip as its latency; the horizon cap at 500 ms; each light's latency and mode remembered across restarts; the device settings in state.db applied, after a run-once step drops the rows that never did, and saved from the app. Plan: `docs/superpowers/plans/2026-10-06-light-sync.md`.

**What changed**, one bullet per area:

- Latency: `latency/doze.py` (the doze check), the tracker's share of the round trip, the restart at a change of mode and its log line, `recall()`, a reset that keeps what the light had, strategies that restart from a latency; `latency/memory.py` (the link memory).
- Govee: the probe loop, and `streaming=` on `register_device`.
- Zones: `HORIZON_CAP_S` from 0.12 to 0.5.
- Discovery: a light taken in starts from its link memory.
- Config and start-up: `probe_interval_s` read (0.5 s, positive); `DevicesConfig` loaded from state.db; the run-once step `devices_config_reset`; `PUT /api/config` saves the device settings it names.
- Persistence: migration 010, `link_memory`, left out of backups.
- Docs: CLAUDE.md and the README.

**API.** No change to a request or a response. `PUT /api/config` now saves the device settings it names, and nothing it refuses (ruling 20). A remembered latency reads `estimated: true` until the light streams; the contract's comment says so.

**Migration and the first start.** Migration 010 creates `link_memory`. The first start runs the run-once step: it deletes the database's `devices.*` rows, which never applied, and logs them once ("Dropped device settings that never applied: …"); the lights then run on the code's defaults, as they always have, plus the probe loop and the doze check. Every light starts at its seed, awake, until it has streamed. Rolling back to the previous image is safe: it ignores the table, and the rows it loses never applied. A backup exported before this change brings the dropped rows back if it's restored, and they apply from the next start: the owner's decision (ruling 22).

**Deployment.** After the merge, from the main checkout: `git pull && docker compose up -d --build`, then check that `ss -ulne 'sport = :4002'` shows `uid:10001` (CLAUDE.md's Gotchas), and that the log holds the "Dropped device settings" line once.

**Spec rulings.** Rulings 1–22 from the plan, one line each.

**Review Focus.** The plan's five items, each with its tests.

**On the lamps.** Pending: the plan's Task 9 (spec §9.7), the owner's. Its results come as a comment.

**Test plan.** Step 2's gates with their counts.

End the description with:

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Then check the description as Step 3 checked the diff:

```bash
grep -nE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b|\b([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b' /tmp/ls-pr-body.md | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0)\b' || echo "no addresses"
grep -ciwFf /tmp/ls-private.txt /tmp/ls-pr-body.md || echo "no names or models"
grep -ci 'ssid' /tmp/ls-pr-body.md || echo "no SSIDs"
```

Expected: `no addresses`, `no names or models` and `no SSIDs`.

- [ ] **Step 5: Push and open the PR**

```bash
git push -u origin feature/light-sync
gh pr create --base master --head feature/light-sync \
  --title "Light sync: Govee probes, a dozing lamp's whole round trip, a 500 ms horizon, remembered latencies, device settings applied" \
  --body-file /tmp/ls-pr-body.md
gh pr view --json url --jq .url
```

Don't merge: the owner does, after Task 9. Now /executing-plans' final review of the whole branch runs; fix every finding it raises, push the fixes, and then stop. Give the owner the PR's URL and hand over Task 9.

---


### Task 9: On the lamps (the owner's)

**The executor stops before this task.** It's the spec's §9.7 acceptance on the real lights, and it touches the deployed container, UDP 4002 and the lights, which nothing before it does. Each step needs the owner's go. The owner's rules hold: never wait for a clock window (run now, then check UDP 4002), and nothing private (a light's name, a room, an address) goes into the PR or a commit.

The branch's build runs in place of the deployed app, as the spike's runs did, on a copy of the deployed database: every light in one room, Beat pulse at full brightness, 30 s, twice, the second run after a restart. Success is the spec's §1.

**Files:** none in the repo. `/tmp/light-sync-acceptance/` holds the database's copy and the logs, and goes at the end.

- [ ] **Step 1: Stop the deployed app and copy its state** (the owner's go)

```bash
A=/tmp/light-sync-acceptance
mkdir -p "$A"
cd /home/anirudhlath/code/private/dj-ledfx
docker compose stop app
docker cp dj-ledfx-app-1:/app/state/. "$A/state"
cp config.toml "$A/config.toml"
ls -l "$A/state"
```

Expected: `state.db` in `$A/state`, owned by you. If it isn't, `cp` it to a new file there and use that.

- [ ] **Step 2: Start the branch's build in its place** (the owner's go)

From the build worktree, in the background (`run_in_background`), logging to a file:

```bash
A=/tmp/light-sync-acceptance
cd /home/anirudhlath/code/.worktrees/dj-ledfx/light-sync-build
uv run -m dj_ledfx --web --web-host 0.0.0.0 --config "$A/config.toml" --db "$A/state/state.db" > "$A/run1.log" 2>&1
```

Wait for it with a Monitor on `until grep -q "dj-ledfx started" /tmp/light-sync-acceptance/run1.log; do sleep 1; done`, then:

```bash
A=/tmp/light-sync-acceptance
ss -ulne 'sport = :4002'
grep -nE "Dropped device settings|could not bind port 4002|Traceback" "$A/run1.log" | cut -c1-200
curl -s http://127.0.0.1:8080/api/running
```

Expected: UDP 4002 held by your uid (the branch run, not Home Assistant); one "Dropped device settings that never applied" line; no `could not bind` and no traceback; and `{"zones": []}`, nothing resumed from the copied database, since the spike's runs started only when nothing ran. If 4002 is someone else's, or a zone resumed, stop the run, put the deployed app back (Step 6) and tell the owner.

- [ ] **Step 3: The first run** (the owner's go)

Write the look's run once, and list the rooms:

```bash
A=/tmp/light-sync-acceptance
cat > "$A/look.sh" <<'EOF'
#!/bin/sh
# look.sh ZONE_ID: Beat pulse at full brightness on the zone for 30 s, then off
set -e
zone=http://127.0.0.1:8080/api/zones/$1
date +%T
curl -sf -X POST "$zone/start" -H 'content-type: application/json' -d '{"lookId": "classic-beat-pulse"}' > /dev/null
curl -sf -X PUT "$zone/brightness" -H 'content-type: application/json' -d '{"value": 1.0}' > /dev/null
sleep 30
curl -sf -X POST "$zone/off"
date +%T
EOF
chmod +x "$A/look.sh"
curl -s http://127.0.0.1:8080/api/zones | uv run python -c "import json, sys; [print(z['id'], '|', z['name'], '|', len(z['lights'])) for z in json.load(sys.stdin) if z['kind'] == 'room']"
```

The owner names the room. Run `/tmp/light-sync-acceptance/look.sh` with that room's zone id as its one argument, in the background, while the owner watches; its first line is the start's time. The id goes on that command line only, never in a file, the PR or a commit. If the start fails, `GET /api/looks` has Beat pulse's id. The owner judges: in step or not (§1.1). Then:

```bash
grep -nE " dozes \(| is awake \(" /tmp/light-sync-acceptance/run1.log | cut -c1-220
```

Expected (§1.2): two lights logged as dozing, within 20 s of the start's time, both of them lamps the owner knows as the dozing pair, and no other light. Note the counts and the seconds, never the names.

- [ ] **Step 4: The second run, after a restart** (the owner's go)

Stop the branch run with SIGTERM, matched by its database's path so nothing else is hit: `pkill -TERM -f light-sync-acceptance/state/state.db`. Then check how it ended and what it remembered:

```bash
A=/tmp/light-sync-acceptance
tail -3 "$A/run1.log"
uv run python -c "import sqlite3, sys; db = sqlite3.connect(sys.argv[1]); print(db.execute('SELECT count(*), sum(dozing) FROM link_memory').fetchone())" "$A/state/state.db"
```

Expected: `dj-ledfx stopped` and no traceback; a row for each light of the room that streamed, two of them dozing. Start the build again as in Step 2, logging to `$A/run2.log`, wait for it the same way, and run `look.sh` on the same room once more while the owner watches. Then:

```bash
grep -nE "starts from the latency it last had| dozes \(| is awake \(" /tmp/light-sync-acceptance/run2.log | cut -c1-220
```

Expected (§1.4): each light of the room starts from the latency it last had, the two dozing lamps "dozing", before the look starts; the owner judges them in step from the first seconds.

- [ ] **Step 5: Report on the PR** (the owner's go)

Write the results as counts and yes or no: the owner's verdict on each run; how many lights were logged as dozing, and how many seconds after the start; how many lights started from a remembered latency in the second run; any warning. No names, rooms, ids or addresses. Check the comment as Task 8's Step 4 checked the description, then post it with `gh pr comment --body-file`.

- [ ] **Step 6: Put the deployed app back**

Stop the branch run (`pkill -TERM -f light-sync-acceptance/state/state.db`), wait for `dj-ledfx stopped` in its log, then:

```bash
cd /home/anirudhlath/code/private/dj-ledfx
docker compose start app
ss -ulne 'sport = :4002'
```

Expected: `uid:10001`. If it isn't, Home Assistant took the port: `docker compose restart app` and check again, and tell the owner either way. Then `rm -rf /tmp/light-sync-acceptance`: it holds a copy of the deployed database.

- [ ] **Step 7: Hand off**

Tell the owner the PR is ready to merge and deploy (its Deployment section). Offer one line for the owner's auto-memory, in its dj-ledfx redesign entry: light sync built, its PR, and the acceptance's verdict. Write it only with a yes.
