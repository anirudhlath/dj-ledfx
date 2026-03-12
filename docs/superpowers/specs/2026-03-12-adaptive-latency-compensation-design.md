# Adaptive Per-Device Latency Compensation

## Problem

Govee WiFi lights miss beats and go out of sync when driven through OpenRGB. Three root causes:

1. **Single static latency for all devices**: All 8 devices (2 Govee WiFi, 5 LIFX, 1 custom) share `StaticLatency(10ms)`. Govee WiFi actual latency is 50-200ms. The scheduler picks frames targeted 10ms in the future, but they don't reach the Govee until 100ms+ later — ~20% phase error at 128 BPM.

2. **Scheduler blocks on slowest device**: `LookaheadScheduler._dispatch_all()` uses `asyncio.gather` across all 8 devices. One slow Govee WiFi send stalls the entire dispatch cycle, reducing effective FPS for all devices.

3. **Stale frame queuing**: Frames queue up for slow devices. The device draws frame N while frames N+1 through N+5 are already queued. The device can never catch up — it skips beats and shows choppy visuals.

## Solution Overview

Per-device send loops with depth-1 frame slots, device-type heuristic latency estimation, and infrastructure for RTT-based adaptive latency (activated when direct Govee/LIFX adapters are added).

## Architecture

```
EffectEngine (60fps) --> RingBuffer (60 frames, 1s future)
                              |
                    LookaheadScheduler.run()
                    (distributor tick at 60fps)
                              |
              +---------------+---------------+--- ...
              |               |               |
       FrameSlot[0]     FrameSlot[1]     FrameSlot[2]
       (target_time)    (target_time)    (target_time)
              |               |               |
      _send_loop(dev0) _send_loop(dev1) _send_loop(dev2)
       find_nearest()    find_nearest()   find_nearest()
              |               |               |
          OpenRGB USB    Govee WiFi     LIFX WiFi
          (~5ms heur.)  (~100ms heur.) (~50ms heur.)
          ~60fps real    ~10fps real    ~20fps real
```

Each device runs at its natural framerate (bounded by configurable FPS cap). The distributor writes a `target_time` (float) into each device's slot every tick — no numpy copies. The send loop calls `ring_buffer.find_nearest(target_time)` only when it is ready to send, so only one copy happens per actual device send. Slow devices that get overwritten 5-6 times between sends waste zero allocations.

## Component Design

### FrameSlot (new class in `scheduler.py`)

Depth-1 slot encapsulating `asyncio.Event` + single `float` target time. The slot stores a **target_time**, not a frame — the send loop resolves it to a frame via `ring_buffer.find_nearest()` only when ready to send. This eliminates wasted numpy copies for slow devices that get overwritten multiple times between sends.

- **`put(target_time: float)`**: Called by distributor. Overwrites any pending target time. Signals event. Increments `put_count: int` (used for `frames_dropped` stats). Must not await anything — correctness depends on this being a single synchronous step.
- **`take(timeout: float = 1.0) -> float`**: Called by send loop. Awaits event with timeout, clears it, returns target time. Uses a while loop (not recursion). Raises `asyncio.TimeoutError` if no frame arrives within `timeout` — this is the escape hatch that lets the send loop periodically re-evaluate `is_connected` and `_running` state.
- **`has_pending: bool`**: Property for diagnostics.
- **`put_count: int`**: Read-only counter for stats.

The distributor computes `target_time = now + device.tracker.effective_latency_s` and writes it to the slot. It **skips `put()`** only if `effective_latency_s` is invalid (should not happen in practice).

Thread safety note: Both `put()` and `take()` run on the same single-threaded asyncio event loop. Safety relies on the GIL + single event loop — there is no preemption between synchronous Python statements. The "must not await" constraint on `put()` ensures it cannot yield control between writing the target time and signaling the event. The `RingBuffer` is also safe to read from multiple send loop tasks because `find_nearest()` is purely synchronous (no await) and does not mutate the buffer.

### LookaheadScheduler Rewrite

Split into two responsibilities:

**Frame Distributor** (runs at engine FPS, single async loop):
- Each tick: for each device, compute `target_time = now + device.tracker.effective_latency_s`, write it into that device's FrameSlot via `put(target_time)`.
- Just writes a float per device — no `find_nearest()`, no numpy copies. Completes in microseconds per tick.

**Device Send Loop** (one async task per device, spawned by `scheduler.run()`):
```
while self._running:
    1. Check adapter.is_connected — if disconnected, backoff-wait 1s, continue.
    2. try:
           target_time = await slot.take(timeout=1.0)
       except TimeoutError:
           continue  # re-evaluate _running and is_connected
    3. frame = ring_buffer.find_nearest(target_time)  # numpy copy happens here
       if frame is None: continue  # buffer not warmed up
    4. send_start = time.monotonic()
    5. await adapter.send_frame(frame.colors)
    6. Increment _send_count
    7. If adapter.supports_latency_probing:
           rtt_ms = (time.monotonic() - send_start) * 1000.0
           device.tracker.update(rtt_ms)
    8. FPS cap: compute remaining = last_send_time + min_frame_interval - now
       if remaining > 0: await asyncio.sleep(remaining)
       last_send_time = time.monotonic()
    9. On send exception (step 5): log warning, skip RTT update, continue loop.
```

Key details:
- **Step 2 timeout**: `slot.take(timeout=1.0)` raises `TimeoutError` if no frame arrives within 1 second. This is the escape hatch — without it, a disconnected device whose distributor stops writing would block the send loop indefinitely. The timeout lets the loop re-evaluate `_running` (for shutdown) and `is_connected` (for disconnect backoff).
- **Step 3 copy**: The numpy array copy happens here, not in the distributor. Only one copy per actual device send. Slow devices that get overwritten 5-6 times between sends waste zero allocations.
- **Step 8 FPS cap**: Tracks `last_send_time` (like `EffectEngine._last_tick_time`) rather than measuring elapsed from `send_start`. This prevents accumulated timing drift over many iterations.

**Constructor signature**:
```python
def __init__(
    self,
    ring_buffer: RingBuffer,
    devices: list[ManagedDevice],
    fps: int = 60,
    max_fps: int = 60,
) -> None:
```
`fps` controls the distributor tick rate (matches engine FPS). `max_fps` is the per-device send loop cap — a separate knob from the distributor rate.

**Shutdown sequence**: `scheduler.stop()` sets `_running = False` (lets send loops exit naturally via the `slot.take()` timeout) and cancels all spawned send loop tasks as a safety net. `scheduler.run()` uses `try/finally` to guarantee child task cleanup:

```python
async def run(self) -> None:
    self._running = True
    # Spawn per-device send loops
    for device, slot in zip(self._devices, self._slots):
        task = asyncio.create_task(self._send_loop(device, slot))
        self._send_tasks.append(task)
    try:
        # Run distributor loop
        while self._running:
            ...
    finally:
        # Clean up child tasks — runs on both normal exit and CancelledError
        for task in self._send_tasks:
            task.cancel()
        await asyncio.gather(*self._send_tasks, return_exceptions=True)
        self._send_tasks.clear()
```

This handles both graceful shutdown (`stop()` sets `_running = False`) and external cancellation (`main.py` calls `task.cancel()` on the scheduler task, raising `CancelledError` which triggers the `finally` block).

### Latency Estimation

**For OpenRGB (current)**: Device-type heuristics based on device name from OpenRGB discovery:
- Name contains "Govee" → 100ms
- Name contains "LIFX" → 50ms
- Everything else → 5ms (USB/wired assumed)

These seed the `WindowedMeanLatency` via a new `initial_value_ms` constructor parameter. When the window is empty (no RTT samples yet, or after `reset()`), `get_latency()` returns `initial_value_ms` instead of 0.0. This solves both the cold-start problem and the reconnect problem (see Disconnect Handling).

Since OpenRGB's `set_colors` is fire-and-forget (the server processes commands asynchronously via an internal `DeviceCallThread`), TCP RTT measurements are meaningless (~1ms for all devices). The `supports_latency_probing = False` flag on `OpenRGBAdapter` prevents useless RTT samples from overwriting the heuristic seed — the window stays empty and `get_latency()` permanently returns the heuristic value.

**For future direct adapters (Govee LAN, LIFX LAN)**: The send loop's RTT measurement captures real network round-trip time. `supports_latency_probing = True` (the default) enables `tracker.update(rtt_ms)`, and the `WindowedMeanLatency(60)` window fills with real samples, providing true adaptive latency compensation. Zero code changes needed in the scheduler — the same send loop works for all adapter types.

**Why OpenRGB can't probe**: The OpenRGB server's `UpdateLEDs()` sets a flag and returns instantly. A background `DeviceCallThread` picks up the flag and calls the device-specific `DeviceUpdateLEDs()` asynchronously. Neither `fast=True` nor `fast=False` on the SDK client reflects actual hardware update time. This is a fundamental limitation of the SDK's fire-and-forget architecture.

`manual_offset_ms` on `LatencyTracker` remains as the fine-tuning escape hatch on top of any latency estimation method.

### FPS Cap

- Global `openrgb_max_fps: int = 60` in config.
- Send loop computes `min_frame_interval = 1.0 / max_fps`.
- After send + optional RTT measurement, if elapsed < `min_frame_interval`, sleep the remainder.
- Fast devices (USB, ~2ms send): hit the cap, run at exactly 60fps.
- Slow devices (Govee WiFi, ~100ms effective): never hit the cap, naturally settle at ~10fps.
- Medium devices (LIFX, ~30ms effective): naturally ~33fps; cap only matters if set below natural rate.

### Disconnect Handling

**Send loop states:**

1. **Disconnected**: Check `adapter.is_connected` before waiting on slot. If disconnected, backoff-wait 1s. Don't consume frames (they get overwritten by distributor with fresher frames).
2. **Send failure**: Log warning, skip RTT update, continue loop. Let adapter manage its own connection state.
3. **Reconnection**: Track `was_connected` as local state in send loop. When `is_connected` flips from False to True, call `tracker.reset()` to clear stale latency samples. Since `WindowedMeanLatency.reset()` clears the window, `get_latency()` falls back to `initial_value_ms` (the heuristic seed) — the device returns to its initial estimate rather than 0ms. For adapters with `supports_latency_probing = True`, the window refills with fresh RTT samples from the new connection.

**OpenRGBAdapter change**: `send_frame` wraps the `asyncio.to_thread` call in a try/except. On exception: sets `self._is_connected = False` and re-raises. Only catch SDK/socket exceptions (e.g., `ConnectionError`, `OSError`) — not broad `Exception`, since `RuntimeError` from event loop shutdown should propagate unmodified. This ensures the send loop's exception handler triggers (logs warning, skips RTT) AND the adapter's connection state is updated so the reconnection backoff path activates on the next iteration.

### DeviceAdapter: Protocol → ABC

Convert `DeviceAdapter` from `typing.Protocol` to `abc.ABC`:

- The Protocol is not enforced anywhere (no isinstance checks, no structural matching).
- The current `discover()` has a silent signature mismatch (Protocol declares no args, OpenRGBAdapter takes `host`/`port`) that an ABC would catch.
- An ABC provides a natural location for `supports_latency_probing` class attribute and future shared behavior (connection retry, frame validation, logging lifecycle).

**Changes:**
- `DeviceAdapter` becomes ABC with `@abstractmethod` on `connect`, `disconnect`, `send_frame`, and all properties.
- `supports_latency_probing: bool = True` as a class attribute with default.
- `discover()` removed from base class — each adapter owns its own discovery as a concrete `@staticmethod` (fundamentally different mechanisms: OpenRGB=TCP, Govee=UDP broadcast, LIFX=UDP broadcast).
- `OpenRGBAdapter` explicitly inherits from `DeviceAdapter`, overrides `supports_latency_probing = False`.

**ProbeStrategy stays as Protocol** — minimal interface (3 methods), no shared behavior, pure computation with no I/O. Textbook structural subtyping.

### Config Changes

| Field | Change |
|-------|--------|
| `openrgb_latency_strategy` | Default changes from `"static"` to `"windowed_mean"` |
| `openrgb_latency_ms` | Stays (used when strategy is `"static"`) |
| `openrgb_manual_offset_ms` | Stays (fine-tuning escape hatch) |
| `openrgb_max_fps` | **New**, default `60` |
| `openrgb_latency_window_size` | **New**, default `60` |

**Validation additions** in `__post_init__`:
- `openrgb_max_fps > 0`
- `openrgb_latency_window_size > 0`
- `openrgb_latency_strategy in {"static", "ema", "windowed_mean"}`

**TOML parsing**: Add `max_fps` and `latency_window_size` under `[devices.openrgb]`.

**Strategy wiring in `main.py`** (both demo and normal mode). Note: heuristic seeding requires the device name, which is only available after `adapter.connect()` populates `_device_name`. The current `main.py` already creates the tracker after `connect()`, so this ordering is preserved:

```python
await adapter.connect()  # populates device name
heuristic_ms = _estimate_device_latency_ms(adapter.device_info.name)

if config.openrgb_latency_strategy == "static":
    strategy = StaticLatency(config.openrgb_latency_ms)
elif config.openrgb_latency_strategy == "ema":
    strategy = EMALatency(initial_value_ms=heuristic_ms)
else:  # "windowed_mean"
    strategy = WindowedMeanLatency(
        window_size=config.openrgb_latency_window_size,
        initial_value_ms=heuristic_ms,
    )
```

`main.py` calls `OpenRGBAdapter.discover()` directly as a concrete static method — this is unaffected by the ABC migration since `discover()` is removed from the base class.

### Device-Type Heuristic Seeding

A function in `src/dj_ledfx/devices/heuristics.py` (new file) maps device names to initial latency estimates. This lives in its own module because it will grow as device types are added (corsair, razer, nanoleaf, etc.):

```python
def estimate_device_latency_ms(device_name: str) -> float:
    name_lower = device_name.lower()
    if "govee" in name_lower:
        return 100.0
    if "lifx" in name_lower:
        return 50.0
    return 5.0
```

All three strategies (`static`, `ema`, `windowed_mean`) receive the heuristic as `initial_value_ms`. For OpenRGB adapters (where `supports_latency_probing = False`), this heuristic is the permanent latency value — no RTT updates will overwrite it. For future direct adapters, real RTT samples will quickly replace the heuristic.

### SystemStatus Updates

Add per-device stats to the 10s status log:
- Effective latency (ms)
- Actual send rate (fps)

**Data flow**: The scheduler exposes a `get_device_stats() -> list[DeviceStats]` method. Each send loop maintains a `_send_count: int` incremented on each successful send and a `_last_stats_time: float`. The `DeviceStats` dataclass (defined in `scheduler.py`) holds `device_name`, `effective_latency_ms`, `send_fps`, and `frames_dropped` (put count - send count). The `_status_loop` in `main.py` calls `scheduler.get_device_stats()` and includes the results in the `SystemStatus` summary.

## Files Modified

| File | Change |
|------|--------|
| `src/dj_ledfx/scheduling/scheduler.py` | Complete rewrite: FrameSlot class, DeviceStats dataclass, distributor loop, per-device send loops, `get_device_stats()`, shutdown cleanup |
| `src/dj_ledfx/devices/adapter.py` | Protocol → ABC, add `supports_latency_probing`, remove `discover()` |
| `src/dj_ledfx/devices/openrgb.py` | Inherit from `DeviceAdapter`, add `supports_latency_probing = False`, wrap `send_frame` to set `_is_connected = False` on exception and re-raise |
| `src/dj_ledfx/latency/strategies.py` | Add `initial_value_ms` parameter to both `EMALatency.__init__()` and `WindowedMeanLatency.__init__()`. `get_latency()` returns `initial_value_ms` when no samples exist. `reset()` clears samples (falls back to `initial_value_ms`). ProbeStrategy stays as Protocol. |
| `src/dj_ledfx/config.py` | Add `openrgb_max_fps`, `openrgb_latency_window_size`, change default strategy, add validation, add TOML parsing |
| `src/dj_ledfx/devices/heuristics.py` | **New file**: `estimate_device_latency_ms()` function mapping device names to initial latency estimates |
| `src/dj_ledfx/main.py` | Strategy branching with heuristic seeding (imports from `devices/heuristics.py`), pass `max_fps` to scheduler, update status loop to include per-device stats |
| `src/dj_ledfx/status.py` | Per-device effective latency + actual send rate in status output |
| `tests/conftest.py` | **New or modified**: Add `MockDeviceAdapter(DeviceAdapter)` concrete test subclass to handle Protocol→ABC migration cleanly across all test files |
| `tests/scheduling/test_scheduler.py` | Rewrite for new architecture (see Test Plan section below) |
| `tests/test_integration.py` | Update scheduler constructor, add mixed-latency integration test |
| `tests/devices/test_openrgb.py` | Test `supports_latency_probing = False`, test send exception sets `_is_connected = False` and re-raises |
| `tests/devices/test_heuristics.py` | **New file**: Test `estimate_device_latency_ms()` — known names, unknown names, edge cases (empty string, mixed case, multi-keyword) |
| `tests/test_config.py` | Test new config fields, validation rules, TOML parsing |
| `tests/latency/test_strategies.py` | Test `EMALatency` and `WindowedMeanLatency` with `initial_value_ms`, test fallback on empty window and after `reset()` |
| `CLAUDE.md` | Update "DeviceAdapter protocol" → "DeviceAdapter ABC". Update Architecture and Key Design Decisions sections to reflect per-device send loops, FrameSlot, and new config fields. |

## Test Plan

### FrameSlot Tests (`tests/scheduling/test_scheduler.py`)
- **put/take basic**: put a target_time, take returns it
- **put overwrites**: put twice before take, take returns the second value
- **take timeout**: take with no put raises `asyncio.TimeoutError` after timeout
- **take blocks until put**: take starts waiting, put signals, take returns
- **put_count increments**: put N times, `put_count == N` regardless of takes
- **starvation**: send loop blocked on take does not spin-wait or consume CPU
- **concurrent overwrite stress**: rapid alternating put/take never produces stale values — frame returned by take corresponds to the most recent put

### Distributor Tests (`tests/scheduling/test_scheduler.py`)
- **writes target_time to all slots**: distributor tick writes to every device's slot
- **skips disconnected devices**: distributor still writes to disconnected slots (cheap no-op)
- **correct target_time calculation**: `target_time = now + effective_latency_s` for each device

### Send Loop Tests (`tests/scheduling/test_scheduler.py`)
- **happy path**: take target_time → find_nearest → send_frame → increment send_count
- **disconnected backoff**: when `is_connected = False`, loop waits 1s, does not call send_frame
- **reconnection resets tracker**: when `is_connected` flips True→False→True, `tracker.reset()` is called
- **send exception handling**: send_frame raises → log warning, skip RTT, continue loop
- **RTT update gated by supports_latency_probing**: True → tracker.update called; False → not called
- **FPS cap enforcement**: with max_fps=30 and instant sends, verify ~33ms between sends
- **FPS cap drift prevention**: over 100 iterations, total elapsed time matches expected (no accumulated drift)
- **buffer not ready**: `find_nearest` returns None → skip send, continue loop

### Shutdown Tests (`tests/scheduling/test_scheduler.py`)
- **graceful stop**: `stop()` → all send loops exit, `run()` returns
- **external cancellation**: cancel the scheduler task → `finally` block cleans up child tasks
- **shutdown during active send**: cancel while `asyncio.to_thread(set_colors)` is running → no crash, no inconsistent state

### Integration Tests (`tests/test_integration.py`)
- **mixed latency**: 2+ devices with different latencies (5ms, 100ms). Both receive frames. High-latency device receives frames targeted further in the future.
- **demo mode**: full pipeline with BeatSimulator and new scheduler works end-to-end

### Stats Tests (`tests/scheduling/test_scheduler.py`)
- **get_device_stats accuracy**: mock slow device, verify `frames_dropped = put_count - send_count`
- **send_fps calculation**: verify fps is computed correctly over a time window

### Heuristic Tests (`tests/devices/test_heuristics.py`)
- **known names**: "Govee H6061" → 100ms, "LIFX Strip" → 50ms, "Corsair RGB" → 5ms
- **case insensitive**: "GoVeE" → 100ms, "lifx" → 50ms
- **unknown device**: "Custom Device" → 5ms
- **empty string**: "" → 5ms
- **multi-keyword**: "Govee-LIFX-Bridge" → 100ms (first match wins)

### Strategy Tests (`tests/latency/test_strategies.py`)
- **WindowedMean initial_value_ms**: empty window returns initial value, not 0.0
- **WindowedMean reset fallback**: after reset(), returns initial_value_ms
- **WindowedMean overrides initial**: after N updates, returns mean of samples, not initial
- **EMA initial_value_ms**: before any update, returns initial value
- **EMA reset fallback**: after reset(), returns initial_value_ms

## Files Unchanged

| File | Why |
|------|-----|
| `src/dj_ledfx/latency/tracker.py` | Already has `update()`, `reset()`, `effective_latency_s`. `reset()` delegates to strategy which now correctly falls back to `initial_value_ms`. |
| `src/dj_ledfx/effects/engine.py` | RingBuffer `find_nearest` already copies frames, preventing races. Now called from send loops (not distributor), so copies only happen per actual device send (~140/sec instead of 480/sec). |
| `src/dj_ledfx/devices/manager.py` | Imports `DeviceAdapter` from `adapter.py` — import path and class name unchanged. Type annotations work the same with ABC as with Protocol. |
| `src/dj_ledfx/events.py` | No interaction with new components |
| `src/dj_ledfx/types.py` | `RenderedFrame` and `DeviceInfo` types are sufficient |

## Known Limitations

- **OpenRGB latency is heuristic-based**: The OpenRGB SDK provides no hardware completion feedback. Heuristic estimates may not match actual device latency. `manual_offset_ms` is the tuning escape hatch.
- **Thread pool RTT inflation** (future direct adapters): `asyncio.to_thread` RTT measurements include thread pool scheduling overhead. Under load with many devices, measured RTT may be inflated. This is conservative (frames arrive early rather than late, which is acceptable for beat sync).
- **No hot-plug support**: Devices are discovered at startup. Adding/removing devices requires restart.
- **WindowedMean convergence time varies by device speed**: A Govee at ~10fps fills the 60-sample window in 6 seconds. A USB device at 60fps fills it in 1 second. During convergence, estimates are based on fewer samples and will be noisier. This only matters for future direct adapters — OpenRGB devices use static heuristics.

## Future Work

- **Direct Govee LAN adapter** (UDP :4003): Own `send_frame` with real RTT measurement, `supports_latency_probing = True`. Inherits from `DeviceAdapter` ABC. The send loop RTT infrastructure activates automatically.
- **Direct LIFX LAN adapter** (UDP :56700): Same pattern as Govee. ~450ms perceived latency, 20 msg/sec max.
- **Per-device config overrides**: Match device names in TOML to override `max_fps`, `manual_offset_ms`, etc. Deferred — auto-detection should handle most cases first.
