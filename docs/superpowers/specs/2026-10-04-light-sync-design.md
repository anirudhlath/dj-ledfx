# Light Sync Design

Keep every light in step with every other, as closely as the network allows, and keep it there without supervision. Each light gets a model of its link, learned from probes while it streams. The model says when to send the light's frames and which moment each frame shows.

**Status:** design approved in brainstorming (2026-10-04). One implementation plan. This spec replaces how the [engine spec](2026-09-23-home-effects-engine-design.md)'s §4.1 measures latency and paces each device; the rest of §4.1 stands. The web app shows none of this until a design handoff does (issue #37).

## 1. Goal

- **In step with each other.** A flash on every light at once looks like one flash. Lining the lights up with the music is a separate question (§12); the owner chose the lights' agreement first.
- **From the network alone.** Nothing manual and no calibration step. Calibration from a phone video is issue #35, deferred.
- **Self-healing.** A light's Wi-Fi may change how it behaves: it may doze, roam to another access point, or queue. The light's round trips show the change, and the model handles it with nobody watching.

Success:

1. While a dozing light (§2) streams, its round trips stay under one wake period plus its floor: p90 under about 110 ms, against 258–345 ms today.
2. In simulation (§11), once settled, every light shows 95% of its frames within ±10 ms of the moment each was worked out for. This holds for awake lights and for locked dozing lights alike.
3. On the lamps, at 5% brightness and for at most 15 s, a strobe shows as one flash on every lamp.

## 2. What Happens Today

**How it works.**

- **Latency.** A light's latency is half its round trips, counted only within 0.5 s of a frame sent. The round trips come from two sources:
  - LIFX echo probes, every 2 s while a light streams;
  - the light monitor's Govee status reads, every 5 s. Govee has no probe of its own.
- **Strategy.** The configured strategy turns the round trips into one number. The code's default is a windowed median of 9. The deployed database still holds `ema` for LIFX and Govee, saved from an old config file.
- **Rate.** Each light is sent at its own fixed rate.
- **Moment.** A frame's moment is `now + latency`, taken at the distributor's tick before the send. So a frame shows colours from up to one engine tick before its moment (17 ms at 60 a second). The lag is fixed for each light but differs between lights.

**What the lights do.** The run, on 2026-10-04:

- Four Govee lights streamed razer frames at 30 a second.
- For 12.5 s, each was asked for its status every 0.15–0.25 s, at random moments.
- The recording is `tests/fixtures/latency/doze-replay-2026-10-04.json`, with relative times only.

| Light | Replies | Round trip p10 / p50 / p90 / max | Arrivals bunch (R) | Sends bunch (R) |
|---|---|---|---|---|
| a | 16 | 219 / 260 / 345 / 433 ms | 0.67 | 0.20 |
| b | 26 | 190 / 233 / 258 / 282 ms | 0.70 | 0.23 |
| c | 62 | 16 / 29 / 40 / 56 ms | 0.13 | 0.08 |
| d | 62 | 16 / 26 / 36 / 43 ms | 0.13 | 0.08 |

R measures how tightly a set of times bunches within a 102.4 ms cycle. It is the mean resultant length of the times' phases: 0 for times spread evenly, 1 for times all at one phase. "Arrivals" are when the replies landed, "sends" when the queries that drew them went out.

**Why.**

- **Power save.** Lights a and b use Wi-Fi power save; their Wi-Fi chip is a different maker's from c's and d's.
- **Beacons.** The access point holds a dozing light's packets until the light's next wake, at a beacon every 102.4 ms (100 TU, DTIM 1).
- **The evidence.** The two lights' replies bunch at one phase of the beacon cycle, although the queries went out at random phases.
- **The queue.** At 30 frames a second, about three frames wait for each wake, and they queue: round trips run at 190–430 ms. That is past the 120 ms horizon cap, so those lights run late by an amount that varies.
- **The estimate.** Any one-number latency for those lights wanders: 86–172 ms over a day.
- **The awake lights.** Lights c and d answer in 26–29 ms at the median.

**What didn't help.**

- Moving every Govee light to a second, plain WPA2 network: a and b still doze, because power save is the chip's.
- Setting a's and b's latency by hand to c's, 11 ms: they got worse.

## 3. Overview

```
probes (LIFX echo, Govee status), at random moments while a light streams
        │ round trips
        ▼
LatencyTracker ── LinkModel, one per light: learning → awake | dozing
        │ next_send(now), moment_for(sent_at), span, rate, lead
        ▼
LookaheadScheduler send loop ── the ring's frames over the span around the moment ──► adapter
```

Borrowed ideas:

- From Sendspin's multi-room audio sync: a Kalman filter on offset and drift that inflates its covariance ×4 when the residuals jump.
- From WebRTC's congestion control (GCC): a rate cut to 0.85 on over-use, and growth of at most 8% a second.
- From LEDBAT: the base delay as the fastest round trip over a window of time.

## 4. Probes

- **LIFX lights:** echo probes, as today, but about every 0.5 s. A light on a fixed link stays at 2 s (§5).
- **Govee lights:** a new probe loop in the Govee transport asks each streaming lamp for its status about every 0.5 s.
  - It goes through `query_status`, so a query already in flight to a lamp is shared, never doubled.
  - The light monitor's 5 s reads time round trips as before, and they count the same.
- **Random intervals:** each interval is drawn at random from 75–125% of its base, so probes land at every phase of a dozing light's cycle.
- **Faster probes:** the base is 0.2 s while a light is learning (§5) or a dozing light's phase is unlocked (§7).
- **Only while streaming:** only a light that streams is probed, and only round trips that land while it streams count (the tracker's `streaming`, as today).

## 5. The Link Model

Each light's tracker holds one link model, which turns round trips into what the scheduler asks for:

- when the next frame should leave (`next_send(now)`);
- the moment a frame that leaves at a given time reaches the light (`moment_for(sent_at)`);
- how long that frame stays up (its span);
- how often the light is sent (its rate).

The model's lead is the moment minus the send, for a frame sent now. It is the light's latency for its zone's horizon.

```python
class LinkModel(Protocol):
    def observe(self, sent_at: float, arrived_at: float) -> None: ...  # one round trip
    def note_send(self, planned_at: float, sent_at: float) -> None: ...  # one frame out, and how late
    def next_send(self, now: float) -> float: ...
    def moment_for(self, sent_at: float) -> float: ...  # when the light gets the frame
    @property
    def span_s(self) -> float: ...
    @property
    def rate_fps(self) -> float: ...
    @property
    def lead_s(self) -> float: ...
    @property
    def probe_interval_s(self) -> float: ...
    def stats(self) -> LinkStats: ...
    def reset(self) -> None: ...
```

**What the model covers.**

- The link model covers only the network: `moment_for` is when the light gets the frame. The tracker adds the light's display delay and the owner's offset, as it does today. `effective_latency_s` is `lead_s` plus both.
- Transports report round trips as today (`update_rtt(rtt_ms)`, called as the reply lands). The tracker stamps the arrival on its own clock and passes both times to `observe`.

**Modes.**

- `learning`, until the model has heard enough to tell the light's kind (16 replies);
- then `awake` (§6) or `dozing` (§7);
- `fixed`, for a light on any other strategy (`static`, `ema`, `windowed_mean`, `windowed_median`). The latency comes from that strategy, as today, and the light is sent at its own rate and probed every 2 s.

**Learning.**

- A learning light gets at most 10 frames a second. That is about one per beacon, so a dozing light can't build a queue before it's told apart.
- Its lead is the awake one (§6), from the config's `latency_ms` until a round trip lands.
- A light's last mode stays known while the app runs. A light that streams again, or comes back from a drop-out, starts in that mode and is checked again as before. A light that dozed starts at its last period, with its phase learned again.

**Telling them apart**, over the last 20 replies (at least 16):

- **Slow:** a reply is slow when its round trip is more than 15 ms over the floor (§6).
- **Dozing:** a light dozes when all three of these hold:
  - at least 60% of its replies are slow;
  - their arrival phases in a 102.4 ms cycle bunch (R ≥ 0.5);
  - the send phases of the queries that drew them don't (R < 0.35). This shows the bunching is the light's, not the probes'.
- **Awake:** any light that doesn't pass that test.
- **Leaving dozing:** a dozing light becomes awake again only after its arrivals have stopped bunching (R < 0.3) for 10 s. It then restarts at 5 frames a second and grows back (§6). This is the fallback for a light that stopped dozing, or that never matched a beacon period the model knows.
- **Log:** each change of mode logs at INFO.

On the recorded run, lights a and b are dozing: 81% and 96% of their replies are slow, their arrivals bunch at R 0.67 and 0.70, and their sends at only 0.20 and 0.23. Lights c and d are awake: 45% and 42% slow, R 0.13.

## 6. Awake Lights

- **Floor.** The fastest round trip in the last 10 s: the path with nothing queued. This is LEDBAT's base delay.
- **Lead.** Half the median of the last 5 round trips. The tracker adds the display delay, as it does today. The measure is today's, but the probes come four to ten times as often, and the window is about 2.5 s.
- **Jitter**, for the stats: the median absolute deviation of the last 20 one-way delays (half round trips).
- **Back-off.**
  - A light's round trips are queueing when the median of its last 4 (about 2 s) is more than 30 ms over the floor.
  - For each second that holds, the light's rate is cut to 0.85 of itself, down to 5 frames a second.
  - Once it hasn't held for a second, the rate grows back by at most 8% a second, up to the light's own rate (its `max_fps`).
- **Why 30 ms, not 15.** The healthy lights c and d sit 14–15 ms over their floor at the median, and 24–26 ms over it at p90 (§2). A 15 ms threshold would cut their rate all the time. A real queue adds a whole frame interval or more.
- **Rate and fade.** A LIFX light fades each frame over the gap to the next. The fade, and the display delay that is half of it, follow the rate the light is sent at now, not the rate the light was built with.
- **Send times.** One frame every 1/rate, as today. The span is 1/rate.

## 7. Dozing Lights

A dozing light gets one frame per wake, sent just before it, and each frame carries the moment it will be shown.

- **Period.**
  - The period is the beacon interval, 102.4 ms, times k. Take k as the largest value from 1 to 4 at which the arrivals' phases still bunch: R ≥ 0.5, and at least 0.8 of R at k = 1.
  - Why the largest bunched k works:
    - Arrivals at one phase of 204.8 ms are at one phase of 102.4 ms too.
    - Arrivals at one phase of 102.4 ms split evenly between two phases of 204.8 ms, which cancel.
  - The period is searched again whenever the light re-locks.
  - On the recorded run, k = 1 for both dozing lights; R at k = 2–4 is at most 0.41.
- **Deadline.**
  - Each reply gives one deadline: its arrival minus the floor round trip.
  - That is the latest a frame could have left and still made the wake the reply came from. A query that only just made its wake waited for nothing, so it travels the floor's path, and the fastest replies are queries sent just before a deadline.
- **Phase.** A Kalman filter tracks the deadline's phase within the period, and its drift: the server's clock against the access point's, tens of ppm.
  - It is seeded from the circular mean of the replies that classified the light.
  - Each new deadline is unwrapped to the nearest predicted deadline.
  - A residual over 3σ is skipped. Three in a row mean the phase has moved: the light roamed to another access point, or the access point restarted. Then the covariance is inflated ×4, the residual applied, and the light is re-locking until σ is under 3 ms again (`locked`).
  - The measurement noise starts at the classifying replies' spread.
- **Send.**
  - The next frame leaves a guard ahead of the next predicted deadline.
  - Guard = 10 ms + 3σ + the send loop's lateness, at most half a period. The lateness is its 95th percentile over the last 10 s, from `note_send`.
  - Leaving early costs only lookahead: the frame waits at the access point for the wake either way. Missing a deadline costs a whole period.
- **Moment.** The deadline plus half the floor. Once the frame is at the access point, it reaches the light at the wake as an awake light's frame would. The tracker adds display and offset, as for any light.
- **Span.** One period: the frame stays up until the next wake.
- **Rate.** One frame per period, about 9.8 a second at k = 1, never above the light's own rate.
- **Drain.**
  - When the last 5 round trips are all over a period plus 15 ms, frames are queued somewhere. They may be left from before the light was classified, or follow a missed deadline.
  - The light then gets no frame at its next wake, and again each second while that holds.

## 8. Sending

- **When and which moment.** The send loop asks the tracker when the light's next frame leaves (`next_send`), not 1/rate after the last one. The scheduler works out a frame's moment as the frame goes out: `moment_for(sent_at)`, plus display and offset. Today the moment is taken at the distributor's tick before the send. The distributor still writes each light's slot from the tick before it's due, and still counts drops as today.
- **Span read.**
  - A light sent slower than the engine renders reads the ring's average over its frame's span, centred on its moment, instead of the blend at one moment. So a flash shorter than the span reaches the light dimmer rather than not at all.
  - Without it, a dozing light at about 10 a second would miss about a quarter of Strobe's 75 ms flashes (at 120 BPM).
  - A light sent at the engine's rate reads as today.
  - `RingBuffer` gains the window read beside `colors_at`, and routes take the span.
- **Horizon.**
  - The form doesn't change: a zone's largest latency plus a rendered frame, at most 120 ms.
  - A dozing light's latency becomes its guard plus half its floor, tens of milliseconds, instead of its queue, hundreds.
  - So a zone with dozing lights renders less far ahead and reacts sooner.
- **`send_now()`**, for a light leaving its own effect, still sends at once. Its moment is `moment_for(now)`, which for a dozing light is its next wake.
- **OpenRGB devices** stay as they are: a fixed link, and nothing probes them.

## 9. Self-Healing

| What changes | How it's noticed | What happens |
|---|---|---|
| A light starts dozing, or stops | The classifier, over the last 20 replies | Its mode switches, logged at INFO. Stopping takes 10 s of unbunched replies; then it climbs back from 5 frames a second |
| A dozing light's wakes move (a roam, an access point restart) | Three residuals over 3σ in a row | Covariance ×4. While re-locking it's probed every 0.2 s and sent with a wider guard, until σ < 3 ms |
| The server's and the access point's clocks drift apart | The filter's drift term | Followed continuously |
| A path gets slower or faster (a new channel, a busier network) | The floor (10 s) and the median of the last 5 | The lead follows within seconds |
| Frames queue on an awake light | The median of the last 4 is 30 ms over the floor | Rate ×0.85 each second, down to 5; it grows at most 8% a second once clear |
| Frames queue on a dozing light | The last 5 all over a period plus 15 ms | A wake skipped each second until they clear |
| The send loop runs late (a busy event loop) | `note_send`'s lateness | A dozing light's guard grows by it |
| A light drops out and comes back | The tracker's reset | It starts in its last mode and is checked again |
| An access point's beacon isn't 102.4 ms × 1–4 | No period bunches | The light is treated as awake; the back-off keeps it from queueing |

## 10. Visibility and Config

**API.** `DeviceStats` gains `link`. `GET /api/devices`, and the `stats` channel's `devices` entries, carry it:

| Field | Meaning |
|---|---|
| `mode` | `learning`, `awake`, `dozing` or `fixed` |
| `lead_ms` | How far ahead of its moment a frame leaves |
| `jitter_ms` | The spread of the one-way delay |
| `floor_ms` | The fastest round trip in the last 10 s; null before one lands |
| `rate_fps`, `max_fps` | How often the light is sent now, and the most it takes |
| `period_ms` | Dozing only: how often the light wakes |
| `lock_ms` | Dozing only: σ of the next wake |
| `locked` | Dozing only: `lock_ms` under 3 ms |

- The dozing-only fields are null in the other modes.
- The web app's contract (`/api/lights`, and the `stats` channel's `lights`) doesn't change; a design handoff will add the link to the web app (#37).
- `cd web && npm run api:types` regenerates the generated types with this change.

**Logs.**

- INFO when a light's mode changes.
- DEBUG when a dozing light locks or re-locks, and at each back-off.
- TRACE for each reply.

**Config.**

- `adaptive` joins the strategies a config can name.
- It becomes LIFX's and Govee's default, in `config.py`, `config.toml` and `config.example.toml`.
- OpenRGB keeps `windowed_mean`, since nothing probes it.
- `latency_ms` seeds learning.
- `windowed_median` and the other strategies stay selectable, as the fallback if the link models misbehave.
- **The deployed database** saved `ema` for LIFX and Govee from an old config file. A run-once step (`has_mark` and `mark_statement`, mark `latency_adaptive`) sets both to `adaptive` at the first start. A strategy saved after that is kept.

## 11. Testing

1. **Units, on a fake clock** (`tests/latency/`):
   - classification on synthetic replies: dozing against awake, the 16-reply minimum and the 10 s exit;
   - the period, for k = 1–4, including a light that wakes every second beacon;
   - the filter: it locks within 20 replies, follows 50 ppm of drift, skips a lone outlier, and re-locks within 5 s of a 40 ms phase jump;
   - the awake lead and the floor;
   - the back-off and the growth;
   - the guard and its cap;
   - the drain;
   - learning's cap of 10 a second;
   - the last mode surviving a reset.
2. **A simulated network** (`tests/latency/link_sim.py`).
   - The setup:
     - an access point that beacons every 102.4 ms, drifting, and holds a dozing light's packets until a wake;
     - an awake path with jitter, and a bottleneck queue of a set capacity;
     - lights that record when each frame lands.
   - The scheduler, a tracker with the adaptive link and a fake transport run on fake time. Once settled:
     - a dozing light gets at most one frame per wake, misses fewer than 1% of its deadlines and never builds a queue;
     - every light shows 95% of its frames within ±10 ms of their moments;
     - a 40 ms phase jump is re-locked within 5 s;
     - with a bottleneck below the light's rate, the rate settles under it and the queue stays under 30 ms.
3. **Replay.** The recorded run, fed to the classifier: a and b dozing at 102.4 ms, c and d awake.
4. **Span read.**
   - A flash shorter than a span reaches a light at a level in proportion to the share of the span it fills.
   - A light at the engine's rate reads exactly today's blend.
5. **API and config.**
   - `link` in `GET /api/devices` and in the `stats` channel.
   - The run-once step sets LIFX's and Govee's saved strategies to `adaptive`, once, whatever they held, and leaves a strategy saved after it.
6. **On the lamps**, with the owner's go for each step, at 5% brightness and for at most 15 s, the four Govee lamps play Strobe. It succeeds when:
   - the dozing lamps' round trips while streaming are under about 110 ms at p90 (258–345 ms today);
   - the awake lamps' round trips are unchanged;
   - the strobe shows as one flash on all four, by eye.

## 12. Out of Scope and Limits

- **Lining the lights up with the music.** The owner chose the lights' agreement with each other first. Every round trip includes the lights' own processing; that bias is common to every light, so it shifts them all alike.
- **Calibration by phone video:** #35.
- **OpenRGB.** Nothing probes it, and its fixed latency stays.
- **The web app's view of the link:** #37, a design handoff.
- **Keeping the link models across restarts.** Learning takes seconds.
- **A dozing light changes colour only at its wakes.** What it shows lands up to half a period (about 51 ms) either side of when the look has it. The span read keeps a flash from vanishing between wakes; it can't make the flash land between them.
- **Other beacon intervals.** A beacon interval that isn't 100 TU isn't recognised. Such a light is handled as awake, with the back-off. Every access point here uses 100 TU.

## 13. Where It Lives

**New, in `src/dj_ledfx/latency/`:**

- `link.py`: `LinkModel`, `LinkStats`, `FixedLink` (today's strategies behind the new interface), and `make_link()`, which builds a link from a kind of device's config.
- `adaptive.py`: `AdaptiveLink`, which holds learning, the classifier, the awake model and the back-off, and runs dozing through `doze.py`.
- `doze.py`: the period search and the deadline filter.
- `probes.py`: the random probe intervals both transports draw.

**Changed:**

- `latency/tracker.py`: holds a link model, with `next_send`, `moment_for`, `span_s`, `rate_fps` and `stats`, and `note_send(planned_at)`. The display delay becomes a callable, so a LIFX fade can follow the rate.
- `scheduling/scheduler.py`, `scheduling/route.py` and `effects/ring_buffer.py`: send times and moments from the tracker, the moment at send, and the span read.
- `devices/govee/transport.py` and `devices/govee/backend.py`: the probe loop.
- `devices/lifx/transport.py` and `devices/lifx/base.py`: probe intervals, and a fade that follows the rate.
- `types.py`, `web/schemas.py`, `web/router_devices.py`, `web/ws.py` and `web/src/api/generated/`: `link`.
- `config.py`, `config.toml`, `config.example.toml` and persistence: `adaptive`, and the run-once step.
- `CLAUDE.md`, and the engine spec's §4.1 latency bullet, which is amended at the spec's top.
