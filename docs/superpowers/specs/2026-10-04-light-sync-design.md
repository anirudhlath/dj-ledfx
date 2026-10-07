# Light Sync Design

Keep every light in step with every other, as closely as the network allows, and keep it there without supervision. Each light's latency is measured again and again while it streams. A light whose Wi-Fi dozes is recognised by when its replies land, and its frames go out early by its whole round trip.

**Status:** revised 2026-10-06 after the doze spike (issue #39, runs 1–8). With a throwaway build doing what this spec describes, the owner judged the lights in step and self-healing. This revision replaces the 2026-10-04 design: one frame per wake and a link model per light, which is in this file's history. One implementation plan. This spec replaces how the [engine spec](2026-09-23-home-effects-engine-design.md)'s §4.1 measures latency; the rest of §4.1 stands. The web app shows none of this until a design handoff does (issue #37).

## 1. Goal

- **In step with each other.** A flash on every light at once looks like one flash. Lining the lights up with the music is a separate question (§10); the owner chose the lights' agreement first.
- **From the network alone.** Nothing manual and no calibration step. Calibration from a phone video is issue #35, deferred. Nothing may depend on tuning the owner's routers: the software has to work on any network.
- **Self-healing.** A light's Wi-Fi may change how it behaves: it may doze, roam to another access point, or queue. The light's round trips show the change, and its latency follows with nobody watching.

Success:

1. On the lamps, the branch's build alone, with no test patches, does what spike runs 7 and 8 did. With the owner's go, every light in one room, LIFX and Govee, plays Beat pulse at full brightness for 30 s, and the owner judges them in step.
2. In that run the log names the two dozing lamps as dozing within 20 s of the start, and no other light.
3. On both recordings (§9), the doze check calls a and b dozing and c and d awake.
4. A light's latency follows a step in its round trips within 5 s. The first look after a restart starts each light at the latency it last had.

## 2. What Happens Today

**How it works** (master at 1d6ed22).

- **Latency.** Half a light's round trip, counted only within 0.5 s of a frame sent, kept as a windowed median of 9, plus the light's display delay. The round trips come from two sources:
  - LIFX echo probes, every 2 s while a light streams;
  - the light monitor's Govee status reads, every 5 s. Govee has no probe of its own.
- **Settings.** The code's defaults: a windowed median of 9, seeds of 10 ms for LIFX and 100 ms for Govee, a Govee razer lamp at 30 frames a second.
  - `_load_config_from_db` in `main.py` never builds `DevicesConfig`, so no `devices.*` row in state.db has ever applied.
  - The deployed database's rows come from an old config file: `ema` over 60 samples, Govee at 40 frames a second, a LIFX seed of 50 ms and Govee probes every 5 s.
- **Horizon.** A zone renders ahead by its lights' largest latency plus a frame, at most 120 ms (`HORIZON_CAP_S`). A light slower than that runs late by the difference.

**What the lamps do.** The spike, on 2026-10-05, measured four Govee lamps and later the room's seven LIFX lights too. Each lamp was asked for its status every 0.375–0.625 s while it streamed; issue #39's comments hold every run's numbers. The 2026-10-04 recording, `tests/fixtures/latency/doze-replay-2026-10-04.json`, agrees.

- **Two lamps doze.** Lamps a and b use Wi-Fi power save, so the access point holds their packets until they wake, at every beacon: 102.4 ms (100 TU, DTIM 1). Their replies land bunched at one phase of the beacon cycle; c's and d's don't.
  - Power save is the lamp firmware's. a and b carry another maker's Wi-Fi chip than c and d. Neither the LAN API nor the lamps' app can switch it off, and moving the lamps to another network didn't stop it.
- **A standing queue.** At 30 frames a second, about three frames wait for each wake. a and b hold a steady queue: round trips of 230–360 ms at the median, flat through a run. c and d answer in 23–36 ms.
- **Half is too little.** A dozing lamp's wait is all on the way in: the frame waits for the wake and the queue, and the reply comes straight back. So half its round trip, today's latency, is about half its real delay. That half is the 86–172 ms seen on 2026-10-04.
- **Slower rates look worse.** A slower rate shrinks the queue: about 110 ms at 9 frames a second, 150 at 20. But by the owner's eye 9 looked stepped and 20 uneven, because razer has no fade between frames. 30 looked smooth.
- **What worked.** The throwaway build took a and b's latency as their whole round trip, capped the horizon at 400 ms and probed every Govee lamp about every 0.5 s. The owner judged that "smoother", then "they synced up eventually" (runs 5–6). With the room's LIFX lights in the same zone, it was "working pretty well, it self heals" (runs 7–8).
- **The probes do the healing.** A median of 9 follows a change within about 5 s at a round trip every 0.5 s. At today's one read every 5 s it takes about 25 s.
- **The first seconds were off.** A fresh tracker starts at the config's 100 ms seed. It needed about 5 s of probes to reach a dozing lamp's ~250 ms.

## 3. Overview

```
Govee status probes (new: about every 0.5 s while a lamp streams), LIFX echo probes (every 2 s, as today)
        │ round trips, each stamped as it lands
        ▼
LatencyTracker ── doze check (§5) ── the whole round trip if dozing, else half ── windowed median of 9
        │ latency, remembered in state.db (§7)
        ▼
zone runtime: renders ahead by its largest latency plus a frame, at most 500 ms (§6) ──► send loops, as today
```

These don't change: each light's rate (a Govee razer lamp at 30 a second), the send loops, a frame's moment (`now + latency`), the ring and its reads.

## 4. Probes

- **Govee.** `GoveeTransport.start_probing(interval_s)` runs a probe loop, as LIFX's transport does.
  - Each round waits a random 75–125% of `devices.govee.probe_interval_s`, which defaults to 0.5 s.
  - Then it asks each registered lamp that streams for its status, unless a status query to that lamp is already in flight. It asks through `query_status`, so a query is shared, never doubled.
  - The random waits put the queries at every phase of a dozing lamp's beacon cycle.
- **Only while streaming.** `register_device(record, rtt_callback, streaming=)` takes the lamp's `streaming()`, as LIFX's does. Only a lamp that streams is probed.
- **Not while deaf.** Nothing is probed while another program holds UDP 4002 (`can_receive`), because no reply could reach the app.
- **The monitor's reads** every 5 s go on, and their round trips count the same.
- **LIFX** echo probes stay at every 2 s. The LIFX lights were in step at that rate, and none of them dozes here.
- **The setting.** `probe_interval_s` is read now: until this change it was kept only so old config files still load. It must be positive, and its default drops from 5 s to 0.5 s.

## 5. Dozing

The tracker tells a dozing light from an awake one by when its replies land.

- **What it keeps.** The last 40 round trips that counted, those that landed while the light streamed. Each is kept with its arrival, on the tracker's clock.
- **What it works out.** Over those round trips, once there are at least 10:
  - the Rayleigh statistic `z = n·R²` of the arrivals' phases in a 102.4 ms cycle. R is the mean resultant length: 0 for phases spread evenly, 1 for phases all at one point. For random arrivals, the chance that z ≥ k is about e^(−k);
  - the median round trip.
- **Dozing:**
  - a light turns dozing when z ≥ 7 and the median is at least 50 ms;
  - it stays dozing while z ≥ 2 and the median is at least 50 ms;
  - otherwise it is awake. A light starts awake, or in the mode it had last (§7).
- **Why both conditions:**
  - A dozing light's replies land at its wakes, so they bunch.
  - Its queries wait for a wake, on average half a beacon (51 ms), even with nothing queued.
  - Bunching alone is too weak. In a simulation, random arrivals at one every 0.5 s crossed z = 7 about three times an hour.
  - The median rules those out: on this network, no awake light's median passed 37 ms.
- **Wake intervals.** A light that wakes at every second or fourth beacon bunches at 102.4 ms too. A dozing light behind an access point whose beacon interval isn't a multiple of 100 TU isn't recognised, and keeps half its round trip (§10).
- **On every recording** (§9), checked over the last 40 replies:
  - a and b turn dozing at their 10th to 20th reply and never leave; after that, z stays at 6.9 or more and the median at 102 ms or more;
  - c and d are never called dozing; z stays under 4.4 and the median at 15–37 ms.
- **Latency.** The strategy is fed a dozing light's whole round trip, and half of an awake light's. When the mode changes, the strategy restarts from the round trips the tracker holds, at the new share, so the latency is right at once. A `static` strategy ignores round trips, as it does now.
- **Log.** Each change of mode is logged at INFO, with z and the median.

## 6. Horizon

- **The cap.** `HORIZON_CAP_S` goes from 120 ms to 500 ms. The lookahead is 1 s, so the ring holds it.
- **Which zones it touches.** A zone still renders ahead by its largest latency plus a frame. Only a zone with a dozing light, or another light as slow, renders further ahead. The spike tracked its dozing lamps at up to 411 ms.
- **The cost.**
  - A zone's first frame is rendered a horizon ahead. A light whose moment comes sooner holds that frame until its moment reaches it: the "start freeze" of the light-output plan's ruling 1.
  - In a zone with a dozing lamp, that freeze is up to about 0.4 s, against a frame or two today.
  - The spike's runs had it at every start.
  - Brightness is applied at send, so a brightness change isn't delayed.
- **The LIFX matrix ruling.** That ruling kept the cap at 120 ms, which left a LIFX matrix (about 123 ms with its display delay) 3 ms late. Now a matrix's zone renders about 140 ms ahead, and the matrix is in step.

## 7. Remembering

- **Within a run.** A light that drops out and comes back has its tracker reset. The reset now restarts it from the latency and mode it had, not from the config's seed. It drops the round trips the tracker held, so the doze check starts again from the next 10.
- **Across restarts.**
  - A new table, `link_memory` (migration 010), holds each light's last latency and mode: `stable_id`, `latency_ms` (the strategy's latency, before display and offset), `dozing` and `updated_at`.
  - A task writes every 30 s, and once at shutdown. It writes the rows of lights whose mode changed, or whose latency moved by more than 5 ms, since their row was last written.
  - When the discovery orchestrator takes a light in, it hands the light's tracker its row before the first frame (`recall(latency_ms, dozing)`).
  - A light with no row starts at the config's seed, awake.
- **Not in backups.** The table is a cache, measured again within seconds. A backup restored on another network would carry the wrong delays.

## 8. Settings

- **The load.** `_load_config_from_db` builds `DevicesConfig` too, from sections `devices.openrgb`, `devices.lifx` and `devices.govee`, through `filter_fields` like the other sections.
- **A run-once step.** At the first start after the fix, before the config is read, a step deletes the database's `devices.*` rows. It uses `has_mark` and `mark_statement`, with the mark `devices_config_reset`.
  - So that start runs exactly what the app has always run, the code's defaults.
  - Without the step, the old rows would apply at once: Govee at 40 frames a second (never tested), EMA over 60 samples, a 50 ms LIFX seed and Govee probes every 5 s.
  - A setting saved after the step is kept, and now survives a restart.
- **Strategies.** The other strategies stay selectable. The doze check works with whichever a config names.

## 9. Testing

1. **Units, on a fake clock** (`tests/latency/`):
   - the doze check:
     - arrivals bunched at 102.4 ms with a 60 ms median are dozing at the 10th reply;
     - arrivals bunched at 204.8 ms are dozing too;
     - random arrivals are awake;
     - arrivals that bunch with a 25 ms median are awake;
     - a dozing light stays dozing while z ≥ 2, and turns awake when the median drops under 50 ms;
   - the share of the round trip, and the restart at the new share when the mode changes;
   - only round trips that land while the light streams count;
   - a reset keeps the latency and the mode, and `recall()` sets both.
2. **Replay.** Each recording is fed to a tracker in order: `tests/fixtures/latency/doze-replay-2026-10-04.json`, and a new `doze-replay-2026-10-05.json` with spike run 8's replies from lamps a–d over 27 s, in relative times only.
   - a and b turn dozing and stay dozing; c and d never do.
   - At the end, a's and b's latency lies between the 25th and 75th percentiles of their round trips.
3. **The Govee probe loop**, on a fake transport and clock:
   - it probes only lamps that stream;
   - each wait is 75–125% of the interval;
   - no query is doubled;
   - nothing is probed while the transport can't receive;
   - the loop stops at close.
4. **Horizon.** A zone with a 400 ms light renders 400 ms plus a frame ahead. A light past 500 ms is capped.
5. **Memory:**
   - a row is written when the mode changes, and when the latency has moved more than 5 ms, and not otherwise;
   - rows are written at shutdown;
   - a light's row is read back into its tracker when it's taken in;
   - a light with no row starts at the seed.
6. **Settings:**
   - `devices.*` loads;
   - the run-once step deletes the old rows once and keeps a setting saved after it;
   - `probe_interval_s` must be positive.
7. **On the lamps**, with the owner's go for each step. The branch's build runs in place of the deployed app, as the spike's runs did: every light in one room, Beat pulse at full brightness, 30 s, twice. Success is as §1 says.

## 10. Out of Scope and Limits

- **Wake-timed sends.** This was the 2026-10-04 design: one frame just before each wake, a phase filter and a span read. It's out because a dozing lamp at about 10 frames a second looked stepped, and razer can't fade. Sending 30 a second timed to the wakes might shrink the queue and a's spread (p90 up to 705 ms in run 7). It's the next refinement if the owner sees lag.
- **Rate back-off** for awake lights. No awake light queued in any run.
- **A view of each light's link** (mode, z, round trips). This change only logs it. The web app's view is #37.
- **Lining the lights up with the music**, calibration by phone video (#35), and OpenRGB, which nothing probes.
- **Other beacon intervals.** Behind an access point whose beacon interval isn't a multiple of 100 TU, a dozing light isn't recognised and keeps half its round trip. Every access point here uses 100 TU.
- **Router tuning.** A shorter beacon interval would wake dozing lamps more often, but it helps only the network it's done on, and nothing here depends on it.
- **Still at the wakes.** A dozing lamp still takes its frames only at its wakes, about three at a time. At 30 a second it looked smooth.
- **A slow awake light, now and then called dozing.** The median rules out only an awake light under 50 ms. Simulated for 200 hours at a 60 ms median, its replies 0.375–0.625 s apart at random, an awake light was called dozing about 3.3 times an hour, for a median 11 s (the longest 44 s): about 1% of the time. While it's so called, it runs early by half its round trip, 30 ms at that median. Stricter rules call it dozing less often, but leave the 2026-10-04 recording's lamp a awake, against §1's criterion 3, so the rule stays as §5 has it, and any change to it is the owner's.
- **LIFX follows a step more slowly.** Its echo probes come every 2 s, so a LIFX light's median of 9 takes about 10 s to follow a step in its round trips. §1's 5 s is the Govee lamps', probed about every 0.5 s.

## 11. Where It Lives

**New:**

- `latency/doze.py`: the doze check, which holds the last 40 arrivals and round trips, z, the median, and the mode with its two thresholds.
- `persistence/migrations/010_link_memory.sql`, and the table's reads and writes.
- `tests/fixtures/latency/doze-replay-2026-10-05.json`.

**Changed:**

- `latency/tracker.py`: the doze check and the share of the round trip; the restart when the mode changes; `dozing`; `recall()`; a reset that keeps the latency and mode.
- `devices/govee/transport.py` and `devices/govee/backend.py`: the probe loop, and `streaming=`.
- `zones/runtime.py`: `HORIZON_CAP_S` becomes 0.5.
- `config.py`, `config.toml` and `config.example.toml`: Govee's `probe_interval_s` is read, defaults to 0.5 and is validated.
- `main.py`: `devices.*` loaded, the run-once step, and the memory's writer.
- `devices/discovery.py`: the recall when a light is taken in.
- `CLAUDE.md`: latency, the horizon and the matrix ruling, and the Govee probe. The engine spec's §4.1 latency bullet, which is amended at that spec's top.
