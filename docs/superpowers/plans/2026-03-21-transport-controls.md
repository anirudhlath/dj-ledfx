# Transport Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add play/stop/simulate transport controls so effects don't auto-start and users can preview without sending to devices.

**Architecture:** TransportState enum on EffectEngine, gated by asyncio.Event. Scheduler subscribes via EventBus. DeviceAdapter gets capture/restore for device state. REST + WS API. Frontend buttons + keyboard shortcuts.

**Tech Stack:** Python asyncio, FastAPI, EventBus, SQLite migrations, React + shadcn/ui + TypeScript

**Spec:** `docs/superpowers/specs/2026-03-21-transport-controls-design.md`

---

## File Structure

### New files
- `src/dj_ledfx/transport.py` — `TransportState` enum + `TransportStateChangedEvent` dataclass
- `src/dj_ledfx/web/router_transport.py` — REST endpoints for transport state
- `src/dj_ledfx/persistence/migrations/003_device_saved_state.sql` — new table
- `tests/test_transport.py` — transport state unit tests
- `tests/effects/test_engine_transport.py` — engine transport gating tests
- `tests/scheduling/test_scheduler_transport.py` — scheduler transport gating tests
- `tests/web/test_router_transport.py` — REST endpoint tests
- `tests/web/test_ws_transport.py` — WS transport channel tests
- `frontend/src/hooks/use-transport.ts` — transport state hook

### Modified files
- `src/dj_ledfx/events.py` — add `TransportStateChangedEvent`
- `src/dj_ledfx/effects/engine.py` — add `RingBuffer.clear()`, transport gating in `run()`, `set_transport_state()`
- `src/dj_ledfx/scheduling/scheduler.py` — subscribe to transport events, gate distributor + send loops
- `src/dj_ledfx/devices/adapter.py` — add `capture_state()` and `restore_state()` with defaults
- `src/dj_ledfx/devices/manager.py` — call `capture_state()` on connect when stopped
- `src/dj_ledfx/persistence/state_db.py` — add `save_device_state()`, `load_device_state()`, `load_all_device_states()`
- `src/dj_ledfx/web/app.py` — include transport router, add `event_bus` param to `create_app`, start transport broadcast task
- `src/dj_ledfx/web/ws.py` — add `_transport_broadcast` task (EventBus-driven), `set_transport` action, transport in `_status_poll`, `connected_websockets` registry
- `src/dj_ledfx/main.py` — wire up transport state, pass event_bus to engine and create_app
- `frontend/src/lib/types.ts` — add `TransportState` type
- `frontend/src/lib/api-client.ts` — add `getTransport()`, `setTransport()` methods
- `frontend/src/lib/ws-client.ts` — add `onTransport` callback support
- `frontend/src/components/transport-section.tsx` — add play/stop/simulate buttons + keyboard shortcuts
- `frontend/src/hooks/use-ws-connection.ts` — subscribe to transport channel
- `frontend/src/pages/live.tsx` — pass transport state to TransportSection

---

### Task 1: TransportState Enum and Event

**Files:**
- Create: `src/dj_ledfx/transport.py`
- Modify: `src/dj_ledfx/events.py:45-46` (add event after SceneDeactivatedEvent)
- Create: `tests/test_transport.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_transport.py
from dj_ledfx.transport import TransportState


def test_transport_state_values():
    assert TransportState.STOPPED.value == "stopped"
    assert TransportState.PLAYING.value == "playing"
    assert TransportState.SIMULATING.value == "simulating"


def test_transport_state_from_string():
    assert TransportState("stopped") == TransportState.STOPPED
    assert TransportState("playing") == TransportState.PLAYING
    assert TransportState("simulating") == TransportState.SIMULATING


def test_transport_state_is_active():
    assert not TransportState.STOPPED.is_active
    assert TransportState.PLAYING.is_active
    assert TransportState.SIMULATING.is_active
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_transport.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dj_ledfx.transport'`

- [ ] **Step 3: Create transport module**

```python
# src/dj_ledfx/transport.py
from __future__ import annotations

from enum import Enum


class TransportState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    SIMULATING = "simulating"

    @property
    def is_active(self) -> bool:
        return self is not TransportState.STOPPED
```

- [ ] **Step 4: Add TransportStateChangedEvent to events.py**

In `src/dj_ledfx/events.py`, add after `SceneDeactivatedEvent` (line 46):

```python
from dj_ledfx.transport import TransportState


@dataclass(frozen=True, slots=True)
class TransportStateChangedEvent:
    old_state: TransportState
    new_state: TransportState
```

Note: add the import at the top with the other imports.

- [ ] **Step 5: Add event test**

Append to `tests/test_transport.py`:

```python
from dj_ledfx.events import TransportStateChangedEvent


def test_transport_state_changed_event():
    event = TransportStateChangedEvent(
        old_state=TransportState.STOPPED,
        new_state=TransportState.PLAYING,
    )
    assert event.old_state == TransportState.STOPPED
    assert event.new_state == TransportState.PLAYING
```

- [ ] **Step 6: Run tests to verify all pass**

Run: `uv run pytest tests/test_transport.py -v`
Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/transport.py src/dj_ledfx/events.py tests/test_transport.py
git commit -m "feat: add TransportState enum and TransportStateChangedEvent"
```

---

### Task 2: RingBuffer.clear() and Engine Transport Gating

**Files:**
- Modify: `src/dj_ledfx/effects/engine.py:16-63` (RingBuffer — add clear method), `65-167` (EffectEngine — add transport state, gate run loop)
- Create: `tests/effects/test_engine_transport.py`

- [ ] **Step 1: Write RingBuffer.clear() test**

```python
# tests/effects/test_engine_transport.py
import time

import numpy as np

from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.types import RenderedFrame


def test_ring_buffer_clear():
    buf = RingBuffer(capacity=10, led_count=3)
    frame = RenderedFrame(
        colors=np.zeros((3, 3), dtype=np.uint8),
        target_time=time.monotonic(),
        beat_phase=0.0,
        bar_phase=0.0,
    )
    buf.write(frame)
    assert buf.count == 1

    buf.clear()
    assert buf.count == 0
    assert buf.find_nearest(time.monotonic()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/effects/test_engine_transport.py::test_ring_buffer_clear -v`
Expected: FAIL — `AttributeError: 'RingBuffer' object has no attribute 'clear'`

- [ ] **Step 3: Implement RingBuffer.clear()**

In `src/dj_ledfx/effects/engine.py`, add after `fill_level` property (line 62):

```python
    def clear(self) -> None:
        self._frames = [None] * self._capacity
        self._write_index = 0
        self._count = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/effects/test_engine_transport.py::test_ring_buffer_clear -v`
Expected: PASS

- [ ] **Step 5: Write engine transport gating tests**

Append to `tests/effects/test_engine_transport.py`:

```python
import asyncio

import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.transport import TransportState


@pytest.fixture
def clock():
    c = BeatClock()
    c.update(bpm=120.0, beat_position=1, next_beat_ms=500, device_number=1,
             device_name="test", pitch_percent=0.0)
    return c


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def engine(clock, event_bus):
    from dj_ledfx.effects.registry import get_effect_classes
    effect_classes = get_effect_classes()
    effect = list(effect_classes.values())[0]()
    deck = EffectDeck(effect)
    return EffectEngine(clock, deck, led_count=10, fps=60, event_bus=event_bus)


def test_engine_starts_stopped(engine):
    assert engine.transport_state == TransportState.STOPPED


def test_engine_set_transport_state(engine):
    engine.set_transport_state(TransportState.PLAYING)
    assert engine.transport_state == TransportState.PLAYING


def test_engine_set_transport_emits_event(engine, event_bus):
    received = []
    event_bus.subscribe(TransportStateChangedEvent, received.append)
    engine.set_transport_state(TransportState.PLAYING)
    assert len(received) == 1
    assert received[0].old_state == TransportState.STOPPED
    assert received[0].new_state == TransportState.PLAYING


def test_engine_no_event_on_same_state(engine, event_bus):
    engine.set_transport_state(TransportState.PLAYING)
    received = []
    event_bus.subscribe(TransportStateChangedEvent, received.append)
    engine.set_transport_state(TransportState.PLAYING)
    assert len(received) == 0


@pytest.mark.asyncio
async def test_engine_run_blocks_when_stopped(engine):
    """Engine run loop should block on _resume_event when STOPPED."""
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    # Engine is stopped — ring buffer should be empty (no ticks called)
    assert engine.ring_buffer.count == 0
    engine.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_engine_run_renders_when_playing(engine):
    """Engine should render frames when set to PLAYING."""
    engine.set_transport_state(TransportState.PLAYING)
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count > 0
    engine.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_engine_clears_buffer_on_stop(engine):
    """Transition to STOPPED should clear ring buffers."""
    engine.set_transport_state(TransportState.PLAYING)
    task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count > 0
    engine.set_transport_state(TransportState.STOPPED)
    assert engine.ring_buffer.count == 0
    engine.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
```

- [ ] **Step 6: Implement engine transport gating**

Modify `src/dj_ledfx/effects/engine.py`:

1. Add imports at top:

```python
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.transport import TransportState
```

2. Update `EffectEngine.__init__` — add `event_bus` parameter and transport state:

```python
class EffectEngine:
    def __init__(
        self,
        clock: BeatClock,
        deck: EffectDeck,
        led_count: int,
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        pipelines: list[ScenePipeline] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._clock = clock
        self._deck = deck
        self._led_count = led_count
        self._fps = fps
        self._frame_period = 1.0 / fps
        self._max_lookahead_s = max_lookahead_s
        self.ring_buffer = RingBuffer(capacity=fps, led_count=led_count)
        self._running = False
        self._last_tick_time = 0.0
        self._render_times: deque[float] = deque(maxlen=fps * 10)
        self._event_bus = event_bus
        self._transport_state = TransportState.STOPPED
        self._resume_event = asyncio.Event()

        # pipelines setup unchanged...
```

3. Add transport state property and setter:

```python
    @property
    def transport_state(self) -> TransportState:
        return self._transport_state

    def set_transport_state(self, state: TransportState) -> None:
        old = self._transport_state
        if old == state:
            return
        self._transport_state = state
        if state.is_active:
            self._resume_event.set()
        else:
            self._resume_event.clear()
            for pipeline in self.pipelines:
                pipeline.ring_buffer.clear()
            self.ring_buffer.clear()
        if self._event_bus is not None:
            self._event_bus.emit(TransportStateChangedEvent(old_state=old, new_state=state))
        logger.info("Transport: {} → {}", old.value, state.value)
```

4. Replace `run()` method with gated version:

```python
    async def run(self) -> None:
        self._running = True
        metrics.RENDER_FPS.set(self._fps)
        logger.info(
            "EffectEngine started: {}fps, {}ms lookahead, {} LEDs",
            self._fps,
            int(self._max_lookahead_s * 1000),
            self._led_count,
        )

        while self._running:
            await self._resume_event.wait()
            self._last_tick_time = time.monotonic()
            while self._running and self._resume_event.is_set():
                now = time.monotonic()
                self.tick(now)

                self._last_tick_time += self._frame_period
                sleep_time = self._last_tick_time - time.monotonic()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    self._last_tick_time = time.monotonic()
                    await asyncio.sleep(0)

        logger.info("EffectEngine stopped")
```

- [ ] **Step 7: Run all engine transport tests**

Run: `uv run pytest tests/effects/test_engine_transport.py -v`
Expected: All PASS

- [ ] **Step 8: Run existing engine tests to verify no regressions**

Run: `uv run pytest tests/effects/test_engine.py -v`
Expected: All PASS (existing tests don't use transport state so default STOPPED won't interfere — but `test_engine_render_tick_populates_buffer` calls `tick()` directly, not `run()`, so it should still work)

- [ ] **Step 9: Commit**

```bash
git add src/dj_ledfx/effects/engine.py tests/effects/test_engine_transport.py
git commit -m "feat: add transport state gating to EffectEngine"
```

---

### Task 3: Scheduler Transport Gating

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py:67-308`
- Create: `tests/scheduling/test_scheduler_transport.py`

- [ ] **Step 1: Write scheduler transport tests**

```python
# tests/scheduling/test_scheduler_transport.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import numpy as np
import pytest

from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.transport import TransportState
from dj_ledfx.types import DeviceInfo, RenderedFrame


def _mock_managed(name="test-device", stable_id="mac:aa:bb:cc"):
    adapter = AsyncMock()
    adapter.device_info = DeviceInfo(name=name, device_type="test", led_count=3, address="", stable_id=stable_id)
    adapter.is_connected = True
    adapter.send_frame = AsyncMock()
    tracker = MagicMock()
    tracker.effective_latency_s = 0.01
    tracker.effective_latency_ms = 10.0
    managed = MagicMock()
    managed.adapter = adapter
    managed.tracker = tracker
    managed.max_fps = 60
    return managed


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def ring_buffer():
    buf = RingBuffer(capacity=60, led_count=3)
    import time
    for i in range(10):
        t = time.monotonic() + i * 0.016
        frame = RenderedFrame(
            colors=np.full((3, 3), i, dtype=np.uint8),
            target_time=t,
            beat_phase=0.0,
            bar_phase=0.0,
        )
        buf.write(frame)
    return buf


def test_scheduler_starts_stopped(ring_buffer, event_bus):
    device = _mock_managed()
    scheduler = LookaheadScheduler(ring_buffer, [device], event_bus=event_bus)
    assert scheduler.transport_state == TransportState.STOPPED


def test_scheduler_responds_to_transport_event(ring_buffer, event_bus):
    device = _mock_managed()
    scheduler = LookaheadScheduler(ring_buffer, [device], event_bus=event_bus)
    event_bus.emit(TransportStateChangedEvent(
        old_state=TransportState.STOPPED,
        new_state=TransportState.PLAYING,
    ))
    assert scheduler.transport_state == TransportState.PLAYING


@pytest.mark.asyncio
async def test_scheduler_blocks_when_stopped(ring_buffer, event_bus):
    device = _mock_managed()
    scheduler = LookaheadScheduler(ring_buffer, [device], event_bus=event_bus)
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)
    # Stopped — no frames sent
    device.adapter.send_frame.assert_not_called()
    scheduler.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_scheduler_sends_when_playing(ring_buffer, event_bus):
    device = _mock_managed()
    scheduler = LookaheadScheduler(ring_buffer, [device], event_bus=event_bus)
    event_bus.emit(TransportStateChangedEvent(
        old_state=TransportState.STOPPED,
        new_state=TransportState.PLAYING,
    ))
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    assert device.adapter.send_frame.call_count > 0
    scheduler.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_scheduler_skips_send_when_simulating(ring_buffer, event_bus):
    device = _mock_managed()
    scheduler = LookaheadScheduler(ring_buffer, [device], event_bus=event_bus)
    event_bus.emit(TransportStateChangedEvent(
        old_state=TransportState.STOPPED,
        new_state=TransportState.SIMULATING,
    ))
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    # No send_frame calls in simulate mode
    device.adapter.send_frame.assert_not_called()
    # But frame_snapshots should be populated
    assert len(scheduler.frame_snapshots) > 0
    scheduler.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scheduling/test_scheduler_transport.py -v`
Expected: FAIL — `AttributeError: 'LookaheadScheduler' object has no attribute 'transport_state'`

- [ ] **Step 3: Implement scheduler transport gating**

Modify `src/dj_ledfx/scheduling/scheduler.py`:

1. Add imports:

```python
from dj_ledfx.events import DeviceOfflineEvent, EventBus, TransportStateChangedEvent
from dj_ledfx.transport import TransportState
```

2. Update `__init__` — add transport state and subscribe:

After `self._frame_seq: dict[str, int] = {}` (line 85), add:

```python
        self._transport_state = TransportState.STOPPED
        self._resume_event = asyncio.Event()
        if event_bus is not None:
            event_bus.subscribe(TransportStateChangedEvent, self._on_transport_changed)
```

3. Add transport handler and property:

```python
    @property
    def transport_state(self) -> TransportState:
        return self._transport_state

    def _on_transport_changed(self, event: TransportStateChangedEvent) -> None:
        self._transport_state = event.new_state
        if event.new_state.is_active:
            self._resume_event.set()
        else:
            self._resume_event.clear()
```

4. Gate the `run()` distributor loop — replace the `while self._running:` inner loop (lines 157-177) with:

```python
        try:
            while self._running:
                await self._resume_event.wait()
                last_tick = time.monotonic()
                while self._running and self._resume_event.is_set():
                    now = time.monotonic()
                    for state in self._device_state.values():
                        slot = state.slot
                        device = state.managed
                        if slot.has_pending:
                            logger.trace(
                                "Frame overwritten for '{}' — device draining slower than engine",
                                device.adapter.device_info.name,
                            )
                            metrics.FRAMES_DROPPED.labels(device=device.adapter.device_info.name).inc()
                        target_time = now + device.tracker.effective_latency_s
                        slot.put(target_time)

                    last_tick += self._frame_period
                    sleep_time = last_tick - time.monotonic()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    else:
                        last_tick = time.monotonic()
                        await asyncio.sleep(0)
```

5. Gate `_send_loop` — add resume_event wait after the connection check and modify the send section. Replace the section from `send_start = time.monotonic()` through `device.tracker.update(rtt_ms)` (lines 252-278) with:

```python
            send_start = time.monotonic()
            if self._transport_state == TransportState.PLAYING:
                try:
                    await device.adapter.send_frame(colors)
                except Exception:
                    logger.warning(
                        "Send failed for '{}'",
                        device.adapter.device_info.name,
                    )
                    continue

                send_elapsed = time.monotonic() - send_start
                device_name = device.adapter.device_info.name
                metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(send_elapsed)

                if device.adapter.supports_latency_probing:
                    rtt_ms = (time.monotonic() - send_start) * 1000.0
                    device.tracker.update(rtt_ms)
            else:
                device_name = device.adapter.device_info.name
```

The remaining code after this block (`state.send_count += 1`, snapshot update, `DEVICE_LATENCY`/`DEVICE_FPS` metrics, FPS cap) stays the same — it runs in both PLAYING and SIMULATING.

Also add a `_resume_event.wait()` at the start of the `_send_loop` while loop, right after the `while self._running and key in self._device_state:` line:

```python
            await self._resume_event.wait()
```

This blocks cleanly until the transport state becomes active — no polling, no timeout. The `_resume_event` is set/cleared by `_on_transport_changed`, so the send loop wakes instantly on state change.

- [ ] **Step 4: Run scheduler transport tests**

Run: `uv run pytest tests/scheduling/test_scheduler_transport.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing scheduler tests**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v`
Expected: All PASS (existing tests will need the scheduler to be in PLAYING state to pass — check and fix if needed. Existing tests likely call `run()` directly and expect frames to flow. The scheduler now starts STOPPED. Fix by having existing test fixtures emit a `TransportStateChangedEvent(STOPPED, PLAYING)` before calling `run()`, or set `_resume_event` directly.)

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler_transport.py
git commit -m "feat: add transport state gating to LookaheadScheduler"
```

---

### Task 4: Device State Capture & Restore

**Files:**
- Modify: `src/dj_ledfx/devices/adapter.py:12-47`
- Modify: `src/dj_ledfx/persistence/state_db.py`
- Create: `src/dj_ledfx/persistence/migrations/003_device_saved_state.sql`
- Modify: `src/dj_ledfx/devices/manager.py`
- Modify: `src/dj_ledfx/scheduling/scheduler.py` (restore on STOPPED transition)

- [ ] **Step 1: Write adapter capture/restore test**

```python
# tests/devices/test_adapter_state.py
import asyncio

import numpy as np
import pytest

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.types import DeviceInfo


class FakeAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(self, led_count: int = 3):
        self._led_count = led_count
        self._connected = True
        self._last_frame: bytes | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(name="fake", device_type="test", led_count=self._led_count, address="")

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

    async def send_frame(self, colors: np.ndarray) -> None:
        self._last_frame = colors.tobytes()


def test_default_capture_state_returns_half_white():
    adapter = FakeAdapter(led_count=3)
    state = asyncio.run(adapter.capture_state())
    colors = np.frombuffer(state, dtype=np.uint8).reshape(-1, 3)
    assert colors.shape == (3, 3)
    assert np.all(colors == 128)


def test_default_restore_state_sends_frame():
    adapter = FakeAdapter(led_count=3)
    state_bytes = np.full((3, 3), 128, dtype=np.uint8).tobytes()
    asyncio.run(adapter.restore_state(state_bytes))
    assert adapter._last_frame == state_bytes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/devices/test_adapter_state.py -v`
Expected: FAIL — `AttributeError: 'FakeAdapter' object has no attribute 'capture_state'`

- [ ] **Step 3: Add capture_state and restore_state to DeviceAdapter**

In `src/dj_ledfx/devices/adapter.py`, add after `send_frame` (line 46):

```python
    async def capture_state(self) -> bytes:
        """Capture current device state. Default: 50% white."""
        return np.full((self.led_count, 3), 128, dtype=np.uint8).tobytes()

    async def restore_state(self, state: bytes) -> None:
        """Restore device to a previously captured state. Default: send as RGB frame."""
        colors = np.frombuffer(state, dtype=np.uint8).reshape(-1, 3)
        await self.send_frame(colors)
```

- [ ] **Step 4: Run adapter state tests**

Run: `uv run pytest tests/devices/test_adapter_state.py -v`
Expected: All PASS

- [ ] **Step 5: Create migration file**

```sql
-- src/dj_ledfx/persistence/migrations/003_device_saved_state.sql
CREATE TABLE IF NOT EXISTS device_saved_state (
    stable_id TEXT PRIMARY KEY,
    state_bytes BLOB NOT NULL,
    captured_at TEXT NOT NULL
);
```

- [ ] **Step 6: Add StateDB methods for device saved state**

In `src/dj_ledfx/persistence/state_db.py`, add after the presets section (near end of file):

```python
    # ── device saved state ──────────────────────────────────────────

    async def save_device_state(self, stable_id: str, state_bytes: bytes) -> None:
        await self._execute_write(
            "INSERT INTO device_saved_state (stable_id, state_bytes, captured_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(stable_id) DO UPDATE SET state_bytes=excluded.state_bytes, "
            "captured_at=excluded.captured_at",
            (stable_id, state_bytes),
        )

    async def load_device_state(self, stable_id: str) -> bytes | None:
        rows = await self._execute_read(
            "SELECT state_bytes FROM device_saved_state WHERE stable_id = ?",
            (stable_id,),
        )
        return rows[0][0] if rows else None

    async def load_all_device_states(self) -> dict[str, bytes]:
        rows = await self._execute_read(
            "SELECT stable_id, state_bytes FROM device_saved_state", ()
        )
        return {row[0]: row[1] for row in rows}
```

- [ ] **Step 7: Write StateDB device state test**

```python
# tests/persistence/test_device_saved_state.py
from pathlib import Path

import pytest
import pytest_asyncio

from dj_ledfx.persistence.state_db import StateDB


@pytest_asyncio.fixture
async def db(tmp_path: Path):
    db = StateDB(tmp_path / "state.db")
    await db.open()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_save_and_load_device_state(db):
    state_bytes = b"\x80\x80\x80" * 3
    await db.save_device_state("mac:aa:bb:cc", state_bytes)
    loaded = await db.load_device_state("mac:aa:bb:cc")
    assert loaded == state_bytes


@pytest.mark.asyncio
async def test_load_missing_device_state(db):
    loaded = await db.load_device_state("nonexistent")
    assert loaded is None


@pytest.mark.asyncio
async def test_load_all_device_states(db):
    await db.save_device_state("id1", b"\x01")
    await db.save_device_state("id2", b"\x02")
    all_states = await db.load_all_device_states()
    assert all_states == {"id1": b"\x01", "id2": b"\x02"}


@pytest.mark.asyncio
async def test_save_device_state_upserts(db):
    await db.save_device_state("id1", b"\x01")
    await db.save_device_state("id1", b"\x02")
    loaded = await db.load_device_state("id1")
    assert loaded == b"\x02"
```

- [ ] **Step 8: Run persistence tests**

Run: `uv run pytest tests/persistence/test_device_saved_state.py -v`
Expected: All PASS

- [ ] **Step 9: Add device state capture to DeviceManager**

Modify `src/dj_ledfx/devices/manager.py`:

1. Add transport state tracking to `__init__`:

```python
from dj_ledfx.events import EventBus, TransportStateChangedEvent
from dj_ledfx.transport import TransportState

class DeviceManager:
    def __init__(self, event_bus: EventBus) -> None:
        # ... existing init ...
        self._transport_state = TransportState.STOPPED
        self._state_db: StateDB | None = None
        event_bus.subscribe(TransportStateChangedEvent, self._on_transport_changed)

    def set_state_db(self, db: StateDB) -> None:
        self._state_db = db

    def _on_transport_changed(self, event: TransportStateChangedEvent) -> None:
        self._transport_state = event.new_state
```

2. In the device connection flow (inside `connect_all` or wherever `adapter.connect()` is called), add state capture when transport is STOPPED:

After a successful `adapter.connect()`, add:

```python
        if self._transport_state == TransportState.STOPPED and self._state_db is not None:
            try:
                state_bytes = await adapter.capture_state()
                sid = adapter.device_info.effective_id
                await self._state_db.save_device_state(sid, state_bytes)
            except Exception:
                logger.warning("Failed to capture state for '{}'", adapter.device_info.name)
```

- [ ] **Step 10: Add device state restore to scheduler**

In `src/dj_ledfx/scheduling/scheduler.py`, update `_on_transport_changed`:

```python
    def _on_transport_changed(self, event: TransportStateChangedEvent) -> None:
        self._transport_state = event.new_state
        if event.new_state.is_active:
            self._resume_event.set()
        else:
            self._resume_event.clear()
            if event.old_state.is_active:
                asyncio.create_task(self._restore_device_states())

    async def _restore_device_states(self) -> None:
        if self._state_db is None:
            return
        # Yield to let in-flight send loops drain before restoring
        await asyncio.sleep(0)
        saved = await self._state_db.load_all_device_states()
        for key, state in self._device_state.items():
            device = state.managed
            if not device.adapter.is_connected:
                continue
            sid = device.adapter.device_info.effective_id
            state_bytes = saved.get(sid)
            if state_bytes is not None:
                try:
                    await device.adapter.restore_state(state_bytes)
                except Exception:
                    logger.warning("Failed to restore state for '{}'", device.adapter.device_info.name)
```

Also add `state_db` parameter to scheduler `__init__`:

```python
    def __init__(
        self,
        ring_buffer: RingBuffer,
        devices: list[ManagedDevice],
        fps: int = 60,
        disconnect_backoff_s: float = 1.0,
        compositor: SpatialCompositor | None = None,
        event_bus: EventBus | None = None,
        state_db: StateDB | None = None,
    ) -> None:
        # ... existing init ...
        self._state_db = state_db
```

- [ ] **Step 11: Run all tests**

Run: `uv run pytest tests/devices/test_adapter_state.py tests/persistence/test_device_saved_state.py tests/scheduling/test_scheduler_transport.py -v`
Expected: All PASS

- [ ] **Step 12: Commit**

```bash
git add src/dj_ledfx/devices/adapter.py src/dj_ledfx/devices/manager.py \
  src/dj_ledfx/persistence/state_db.py \
  src/dj_ledfx/persistence/migrations/003_device_saved_state.sql \
  src/dj_ledfx/scheduling/scheduler.py \
  tests/devices/test_adapter_state.py tests/persistence/test_device_saved_state.py
git commit -m "feat: add device state capture/restore with SQLite persistence"
```

---

### Task 5: REST API — Transport Router

**Files:**
- Create: `src/dj_ledfx/web/router_transport.py`
- Modify: `src/dj_ledfx/web/app.py:80-90` (include new router)
- Create: `tests/web/test_router_transport.py`

- [ ] **Step 1: Write REST endpoint tests**

```python
# tests/web/test_router_transport.py
pytest.importorskip("fastapi")

from unittest.mock import MagicMock

from starlette.testclient import TestClient

from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.transport import TransportState
from dj_ledfx.web.app import create_app


def _make_app():
    bus = EventBus()
    clock = MagicMock()
    deck = MagicMock()
    engine = MagicMock(spec=EffectEngine)
    engine.transport_state = TransportState.STOPPED
    engine.set_transport_state = MagicMock()
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    scheduler.frame_snapshots = {}
    manager = MagicMock()
    manager.devices = []
    preset_store = MagicMock()
    preset_store.list_presets.return_value = []
    app = create_app(
        beat_clock=clock,
        effect_deck=deck,
        effect_engine=engine,
        device_manager=manager,
        scheduler=scheduler,
        preset_store=preset_store,
        scene_model=None,
        compositor=None,
        config=MagicMock(),
        config_path="config.toml",
        event_bus=bus,
    )
    return app, engine


def test_get_transport():
    app, engine = _make_app()
    client = TestClient(app)
    resp = client.get("/api/transport")
    assert resp.status_code == 200
    assert resp.json() == {"state": "stopped"}


def test_put_transport_playing():
    app, engine = _make_app()
    client = TestClient(app)
    resp = client.put("/api/transport", json={"state": "playing"})
    assert resp.status_code == 200
    assert resp.json() == {"state": "playing"}
    engine.set_transport_state.assert_called_once_with(TransportState.PLAYING)


def test_put_transport_invalid():
    app, engine = _make_app()
    client = TestClient(app)
    resp = client.put("/api/transport", json={"state": "invalid"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_router_transport.py -v`
Expected: FAIL — import or 404 errors

- [ ] **Step 3: Create router_transport.py**

```python
# src/dj_ledfx/web/router_transport.py
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from dj_ledfx.transport import TransportState

router = APIRouter()


class TransportBody(BaseModel):
    state: str

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        try:
            TransportState(v)
        except ValueError:
            raise ValueError(f"Invalid transport state: {v}. Must be one of: stopped, playing, simulating")
        return v


class TransportResponse(BaseModel):
    state: str


@router.get("/transport", response_model=TransportResponse)
async def get_transport(request: Request) -> TransportResponse:
    engine = request.app.state.effect_engine
    return TransportResponse(state=engine.transport_state.value)


@router.put("/transport", response_model=TransportResponse)
async def set_transport(request: Request, body: TransportBody) -> TransportResponse:
    engine = request.app.state.effect_engine
    new_state = TransportState(body.state)
    engine.set_transport_state(new_state)
    return TransportResponse(state=new_state.value)
```

- [ ] **Step 4: Register router in app.py**

In `src/dj_ledfx/web/app.py`, after the scene router imports (line 84), add:

```python
    from dj_ledfx.web.router_transport import router as transport_router
```

And after the last `app.include_router` (line 90), add:

```python
    app.include_router(transport_router, prefix="/api")
```

- [ ] **Step 5: Run REST transport tests**

Run: `uv run pytest tests/web/test_router_transport.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/web/router_transport.py src/dj_ledfx/web/app.py tests/web/test_router_transport.py
git commit -m "feat: add REST API for transport state (GET/PUT /api/transport)"
```

---

### Task 6: WebSocket Transport Channel

**Files:**
- Modify: `src/dj_ledfx/web/ws.py:113-126` (add transport to status), `151-189` (add set_transport command, add broadcast registry)
- Modify: `src/dj_ledfx/web/state.py` (add connected_websockets set for broadcast)
- Create: `tests/web/test_ws_transport.py`

- [ ] **Step 1: Write WS transport tests**

```python
# tests/web/test_ws_transport.py
pytest.importorskip("fastapi")

import json
from unittest.mock import MagicMock

from starlette.testclient import TestClient

from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.transport import TransportState
from dj_ledfx.web.app import create_app


def _make_app():
    bus = EventBus()
    clock = MagicMock()
    state_mock = MagicMock()
    state_mock.bpm = 120.0
    state_mock.beat_phase = 0.0
    state_mock.bar_phase = 0.0
    state_mock.is_playing = False
    state_mock.pitch_percent = 0.0
    state_mock.deck_number = None
    state_mock.deck_name = None
    clock.get_state.return_value = state_mock
    deck = MagicMock()
    engine = MagicMock(spec=EffectEngine)
    engine.transport_state = TransportState.STOPPED
    engine.set_transport_state = MagicMock()
    engine.avg_render_time_ms = 0.5
    scheduler = MagicMock()
    scheduler.get_device_stats.return_value = []
    scheduler.frame_snapshots = {}
    manager = MagicMock()
    manager.devices = []
    preset_store = MagicMock()
    app = create_app(
        beat_clock=clock,
        effect_deck=deck,
        effect_engine=engine,
        device_manager=manager,
        scheduler=scheduler,
        preset_store=preset_store,
        scene_model=None,
        compositor=None,
        config=MagicMock(),
        config_path="config.toml",
        event_bus=bus,
    )
    return app, engine


def test_ws_set_transport():
    app, engine = _make_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"action": "set_transport", "state": "playing", "id": "1"}))
        # Read messages until we get the ack
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "ack" and msg.get("id") == "1":
                break
        assert msg["channel"] == "ack"
        assert msg["action"] == "set_transport"
        engine.set_transport_state.assert_called_with(TransportState.PLAYING)


def test_ws_set_transport_invalid():
    app, engine = _make_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"action": "set_transport", "state": "bad", "id": "2"}))
        for _ in range(10):
            data = ws.receive_text()
            msg = json.loads(data)
            if msg.get("channel") == "error" and msg.get("id") == "2":
                break
        assert msg["channel"] == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_ws_transport.py -v`
Expected: FAIL — `set_transport` action not recognized

- [ ] **Step 3: Add transport to WebSocket hub**

In `src/dj_ledfx/web/ws.py`:

1. Add import at top:

```python
from dj_ledfx.transport import TransportState
```

2. Add `transport_state` to `_status_poll` payload (after line 124, inside `status_data` dict):

```python
            "transport": engine.transport_state.value,
```

3. Add `set_transport` action in `_handle_command` (before the `else` branch at line 186):

```python
    elif action == "set_transport":
        engine = app.state.effect_engine
        state_str = msg.get("state", "")
        try:
            new_state = TransportState(state_str)
            engine.set_transport_state(new_state)
            await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})
        except (ValueError, KeyError) as e:
            await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": str(e)})
```

4. Add a WS client registry and EventBus-driven transport broadcast.

In `src/dj_ledfx/web/ws.py`, add a module-level set to track connected websockets:

```python
connected_websockets: set[WebSocket] = set()
```

In `ws_endpoint()`, register/unregister the websocket:

```python
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_websockets.add(websocket)
    # ... existing code ...
    # In the finally block:
    finally:
        connected_websockets.discard(websocket)
        # ... existing cleanup ...
```

Add a broadcast helper:

```python
async def _broadcast_json(data: dict[str, Any]) -> None:
    """Broadcast JSON message to all connected WS clients."""
    msg = json.dumps(data)
    for ws in list(connected_websockets):
        try:
            await ws.send_text(msg)
        except Exception:
            pass
```

Add an EventBus-driven transport broadcast task (no polling — uses `asyncio.Queue` as an event bridge):

```python
async def _transport_broadcast(app: Any) -> None:
    """Listen for transport state changes via EventBus and broadcast instantly."""
    event_bus = app.state.event_bus
    queue: asyncio.Queue[str] = asyncio.Queue()

    def on_change(event: TransportStateChangedEvent) -> None:
        queue.put_nowait(event.new_state.value)

    event_bus.subscribe(TransportStateChangedEvent, on_change)
    try:
        while True:
            state_value = await queue.get()
            await _broadcast_json({"channel": "transport", "state": state_value})
    finally:
        event_bus.unsubscribe(TransportStateChangedEvent, on_change)
```

This is event-driven: the EventBus callback puts the state into a queue (sync, non-blocking), the broadcast task awaits the queue and sends instantly. No polling.

5. Start the broadcast task globally via `create_app()`.

In `src/dj_ledfx/web/app.py`:

Add `event_bus` parameter to `create_app()`:

```python
def create_app(
    # ... existing params ...
    event_bus: EventBus | None = None,
) -> FastAPI:
    # ... existing code ...
    app.state.event_bus = event_bus
```

Add a startup event to launch the broadcast task:

```python
    @app.on_event("startup")
    async def _start_transport_broadcast() -> None:
        if app.state.event_bus is not None:
            from dj_ledfx.web.ws import _transport_broadcast
            asyncio.create_task(_transport_broadcast(app))
```

This ensures any transport state change from ANY source (REST, WS, or future CLI) broadcasts instantly to all clients.

- [ ] **Step 4: Run WS transport tests**

Run: `uv run pytest tests/web/test_ws_transport.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing WS tests**

Run: `uv run pytest tests/web/test_ws.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/web/ws.py tests/web/test_ws_transport.py
git commit -m "feat: add WebSocket transport channel and set_transport action"
```

---

### Task 7: Wire Up in main.py

**Files:**
- Modify: `src/dj_ledfx/main.py:291-305` (pass event_bus to engine), `299-305` (pass state_db to scheduler), `176-196` (set state_db on manager)

- [ ] **Step 1: Update engine creation to pass event_bus**

In `src/dj_ledfx/main.py`, find where `EffectEngine` is constructed (around line 291-297). Add `event_bus=event_bus`:

```python
    engine = EffectEngine(
        clock=clock,
        deck=deck,
        led_count=led_count,
        fps=config.engine.fps,
        max_lookahead_s=config.engine.max_lookahead_ms / 1000.0,
        pipelines=pipelines if pipelines else None,
        event_bus=event_bus,
    )
```

- [ ] **Step 2: Update scheduler creation to pass state_db**

Find where `LookaheadScheduler` is constructed (around line 299-305). Add `state_db=state_db`:

```python
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=list(device_manager.devices),
        fps=config.engine.fps,
        compositor=compositor,
        event_bus=event_bus,
        state_db=state_db,
    )
```

(Note: check actual constructor call and adjust — the key change is adding `state_db=state_db`.)

- [ ] **Step 3: Set state_db on DeviceManager**

After DeviceManager is created and state_db is opened, add:

```python
    device_manager.set_state_db(state_db)
```

- [ ] **Step 4: Pass event_bus to create_app**

In the web server setup section of `main.py`, add `event_bus=event_bus` to the `create_app()` call:

```python
    app = create_app(
        # ... existing params ...
        event_bus=event_bus,
    )
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS. Fix any failures from the new STOPPED-by-default behavior breaking existing tests that assume the engine auto-renders. Likely fixes: existing tests that call `engine.run()` or `scheduler.run()` and expect frames need to set transport to PLAYING first.

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat: wire transport state through main.py startup"
```

---

### Task 8: Frontend — Types, API Client, WS Client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/ws-client.ts`

- [ ] **Step 1: Add TransportState type**

In `frontend/src/lib/types.ts`, add at the end:

```typescript
export type TransportState = "stopped" | "playing" | "simulating"
```

- [ ] **Step 2: Add REST methods to api-client.ts**

In `frontend/src/lib/api-client.ts`, add:

```typescript
  async getTransport(): Promise<{ state: TransportState }> {
    return this.fetchJson<{ state: TransportState }>("/api/transport")
  },

  async setTransport(state: TransportState): Promise<{ state: TransportState }> {
    return this.fetchJson<{ state: TransportState }>("/api/transport", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    })
  },
```

(Add import for `TransportState` from types if needed.)

- [ ] **Step 3: Add transport callback to ws-client.ts**

In `frontend/src/lib/ws-client.ts`, add to the WsClient class:

1. Add callback storage:

```typescript
  private transportCallbacks: ((state: TransportState) => void)[] = []
```

2. Add subscription method:

```typescript
  onTransport(cb: (state: TransportState) => void): () => void {
    this.transportCallbacks.push(cb)
    return () => {
      this.transportCallbacks = this.transportCallbacks.filter(c => c !== cb)
    }
  }
```

3. In the JSON message handler (where channels are dispatched), add:

```typescript
      case "transport":
        this.transportCallbacks.forEach(cb => cb(msg.state as TransportState))
        break
```

4. Also extract transport from `status` channel messages:

In the `status` case handler, add:

```typescript
        if (msg.transport) {
          this.transportCallbacks.forEach(cb => cb(msg.transport as TransportState))
        }
```

- [ ] **Step 4: Commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/lib/types.ts frontend/src/lib/api-client.ts frontend/src/lib/ws-client.ts
git commit -m "feat: add transport state to frontend types, API, and WS client"
```

---

### Task 9: Frontend — useTransport Hook

**Files:**
- Create: `frontend/src/hooks/use-transport.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/src/hooks/use-transport.ts
import { useCallback, useEffect, useState } from "react"
import type { TransportState } from "@/lib/types"
import { apiClient } from "@/lib/api-client"
import { wsClient } from "@/lib/ws-client"

export function useTransport() {
  const [state, setState] = useState<TransportState>("stopped")

  useEffect(() => {
    apiClient.getTransport().then(res => setState(res.state))
    const unsub = wsClient.onTransport(setState)
    return unsub
  }, [])

  const setTransportState = useCallback(async (newState: TransportState) => {
    setState(newState) // optimistic
    try {
      const res = await apiClient.setTransport(newState)
      setState(res.state)
    } catch {
      // revert on failure
      const res = await apiClient.getTransport()
      setState(res.state)
    }
  }, [])

  return { transportState: state, setTransportState }
}
```

- [ ] **Step 2: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-transport.ts
git commit -m "feat: add useTransport React hook"
```

---

### Task 10: Frontend — Transport Controls UI

**Files:**
- Modify: `frontend/src/components/transport-section.tsx`
- Modify: `frontend/src/pages/live.tsx`

- [ ] **Step 1: Update TransportSection with buttons and keyboard shortcuts**

Rewrite `frontend/src/components/transport-section.tsx`:

```tsx
import { useRef, useState, useLayoutEffect, useEffect, useCallback } from "react"
import type { BeatState, TransportState } from "@/lib/types"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Play, Square, Eye } from "lucide-react"

function BeatGrid({
  isPlaying,
  beatPos,
  beatPhase,
  barPhase,
}: {
  isPlaying: boolean
  beatPos: number
  beatPhase: number
  barPhase: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [boxSize, setBoxSize] = useState(0)
  const gap = 4
  const barH = 6
  const barGap = 6

  useLayoutEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      const available = entry.contentRect.height - barH - barGap
      setBoxSize(Math.max(0, Math.floor(available)))
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <div ref={containerRef} className="flex flex-col items-center justify-center gap-1.5 self-stretch py-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((n) => {
          const isActive = isPlaying && beatPos === n
          const fillPercent = isActive ? beatPhase * 100 : 0
          return (
            <div
              key={n}
              className="relative rounded overflow-hidden flex items-center justify-center bg-muted shrink-0"
              style={{ width: boxSize, height: boxSize }}
            >
              <div
                className="absolute top-0 bottom-0 left-0 bg-primary transition-none"
                style={{ width: `${fillPercent}%` }}
              />
              <span
                className={cn(
                  "relative z-10 text-xs font-bold",
                  isActive ? "text-primary-foreground" : "text-muted-foreground",
                )}
              >
                {n}
              </span>
            </div>
          )
        })}
      </div>
      <div
        className="relative h-1.5 rounded-full bg-muted overflow-hidden"
        style={{ width: boxSize * 4 + gap * 3 }}
      >
        <div
          className="absolute top-0 bottom-0 left-0 bg-sky-500 transition-none rounded-full"
          style={{ width: `${barPhase * 100}%` }}
        />
      </div>
    </div>
  )
}

interface TransportSectionProps {
  beat: BeatState
  transportState: TransportState
  onTransportChange: (state: TransportState) => void
}

export function TransportSection({ beat, transportState, onTransportChange }: TransportSectionProps) {
  const { bpm, beatPhase, barPhase, isPlaying, beatPos, pitchPercent, deckName } = beat

  const bpmDisplay = bpm > 0 ? bpm.toFixed(1) : "---.-"

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      const tag = el?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return

      if (e.code === "Space") {
        e.preventDefault()
        onTransportChange(transportState === "playing" ? "stopped" : "playing")
      } else if (e.key === "s" || e.key === "S") {
        e.preventDefault()
        onTransportChange(transportState === "simulating" ? "stopped" : "simulating")
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [transportState, onTransportChange])

  return (
    <div className="flex items-stretch gap-4 p-3 bg-card ring-1 ring-foreground/10 rounded-xl">
      {/* Transport controls */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onTransportChange("playing")}
          className={cn(
            "p-2 rounded-lg transition-colors",
            transportState === "playing"
              ? "bg-green-600 text-white"
              : "bg-muted text-muted-foreground hover:bg-muted/80",
          )}
          title="Play (Space)"
        >
          <Play className="w-5 h-5" />
        </button>
        <button
          onClick={() => onTransportChange("simulating")}
          className={cn(
            "p-2 rounded-lg transition-colors",
            transportState === "simulating"
              ? "bg-amber-500 text-white"
              : "bg-muted text-muted-foreground hover:bg-muted/80",
          )}
          title="Simulate (S)"
        >
          <Eye className="w-5 h-5" />
        </button>
        <button
          onClick={() => onTransportChange("stopped")}
          className={cn(
            "p-2 rounded-lg transition-colors",
            transportState === "stopped"
              ? "bg-red-600 text-white"
              : "bg-muted text-muted-foreground hover:bg-muted/80",
          )}
          title="Stop (Space)"
        >
          <Square className="w-4 h-4" />
        </button>
      </div>

      <div className="w-px bg-border self-stretch" />

      {/* BPM */}
      <div className="flex flex-col items-center justify-center min-w-[110px] px-3">
        <span className="text-5xl font-mono font-bold tracking-tight text-foreground leading-none">
          {bpmDisplay}
        </span>
        <span className="text-xs text-muted-foreground mt-1 uppercase tracking-widest">BPM</span>
      </div>

      <div className="w-px bg-border self-stretch" />

      {/* Beat grid */}
      <div className="flex-1 flex items-stretch justify-center">
        <BeatGrid
          isPlaying={isPlaying}
          beatPos={beatPos}
          beatPhase={beatPhase}
          barPhase={barPhase}
        />
      </div>

      {/* Deck info */}
      <div className="flex flex-col justify-center items-end gap-1 min-w-[80px]">
        {isPlaying && (
          <Badge variant="outline" className="text-xs font-mono text-green-500 border-green-500/30">
            LIVE
          </Badge>
        )}
        {deckName && (
          <span className="text-xs font-mono text-muted-foreground">{deckName}</span>
        )}
        {pitchPercent !== null && (
          <span
            className={cn(
              "text-xs font-mono",
              pitchPercent > 0 ? "text-amber-400" : pitchPercent < 0 ? "text-sky-400" : "text-muted-foreground",
            )}
          >
            {pitchPercent > 0 ? "+" : ""}{pitchPercent.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Update live.tsx to pass transport state**

In `frontend/src/pages/live.tsx`, add the hook and pass props:

1. Add import:

```typescript
import { useTransport } from "@/hooks/use-transport"
```

2. In the component body, add:

```typescript
const { transportState, setTransportState } = useTransport()
```

3. Update `<TransportSection>`:

```tsx
<TransportSection
  beat={beat}
  transportState={transportState}
  onTransportChange={setTransportState}
/>
```

- [ ] **Step 3: Check lucide-react has the icons**

Run: `cd frontend && grep -r "lucide-react" package.json`
Expected: lucide-react is already a dependency. Play, Square, Eye are standard icons.

- [ ] **Step 4: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/transport-section.tsx frontend/src/pages/live.tsx
git commit -m "feat: add play/stop/simulate transport controls to UI"
```

---

### Task 11: Fix Existing Tests for STOPPED-by-Default

**Files:**
- Modify: Various test files that expect auto-rendering

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -x -v`

- [ ] **Step 2: Fix any failures**

Expected failures: tests that create an `EffectEngine` or `LookaheadScheduler` and call `run()` expecting frames without setting transport state. Apply these fixes:

**Strategy A — Direct `_resume_event.set()` (preferred for existing tests):**
For tests that don't pass an `event_bus`, set the event directly before calling `run()`:
```python
engine._resume_event.set()
# or
scheduler._resume_event.set()
```

**Strategy B — Via transport state (for tests that have an event_bus):**
```python
engine.set_transport_state(TransportState.PLAYING)
# or emit via EventBus for scheduler:
event_bus.emit(TransportStateChangedEvent(
    old_state=TransportState.STOPPED,
    new_state=TransportState.PLAYING,
))
```

**No change needed:** Tests that call `tick()` directly — `tick()` is not gated, only `run()` is.

**Key files likely affected:**
- `tests/effects/test_engine.py` — any test calling `engine.run()`
- `tests/scheduling/test_scheduler.py` — all tests calling `scheduler.run()`
- `tests/test_integration.py` — full pipeline tests
- `tests/web/test_ws.py` — WS tests that depend on frame flow

- [ ] **Step 3: Run full test suite again**

Run: `uv run pytest -x -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "fix: update existing tests for stopped-by-default transport state"
```

---

### Task 12: Integration Test

**Files:**
- Create or modify: `tests/test_transport_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_transport_integration.py
import asyncio
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.transport import TransportState
from dj_ledfx.types import DeviceInfo


def _mock_managed(name="test", stable_id="mac:aa"):
    adapter = AsyncMock()
    adapter.device_info = DeviceInfo(name=name, device_type="test", led_count=3, address="", stable_id=stable_id)
    adapter.is_connected = True
    adapter.send_frame = AsyncMock()
    adapter.capture_state = AsyncMock(return_value=b"\x80" * 9)
    adapter.restore_state = AsyncMock()
    tracker = MagicMock()
    tracker.effective_latency_s = 0.01
    tracker.effective_latency_ms = 10.0
    managed = MagicMock()
    managed.adapter = adapter
    managed.tracker = tracker
    managed.max_fps = 60
    return managed


@pytest.mark.asyncio
async def test_full_transport_lifecycle():
    """Test: STOPPED → PLAYING → SIMULATING → STOPPED."""
    event_bus = EventBus()
    clock = BeatClock()
    clock.update(bpm=120.0, beat_position=1, next_beat_ms=500,
                 device_number=1, device_name="test", pitch_percent=0.0)

    from dj_ledfx.effects.registry import get_effect_classes
    effect = list(get_effect_classes().values())[0]()
    deck = EffectDeck(effect)

    engine = EffectEngine(clock, deck, led_count=3, fps=60, event_bus=event_bus)
    device = _mock_managed()
    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=[device],
        fps=60,
        event_bus=event_bus,
    )

    engine_task = asyncio.create_task(engine.run())
    scheduler_task = asyncio.create_task(scheduler.run())

    # STOPPED — nothing should happen
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count == 0
    device.adapter.send_frame.assert_not_called()

    # PLAYING — frames should render and send
    engine.set_transport_state(TransportState.PLAYING)
    await asyncio.sleep(0.1)
    assert engine.ring_buffer.count > 0
    assert device.adapter.send_frame.call_count > 0

    # SIMULATING — frames render but no sends
    send_count_before = device.adapter.send_frame.call_count
    engine.set_transport_state(TransportState.SIMULATING)
    await asyncio.sleep(0.1)
    # send_frame count should not increase
    assert device.adapter.send_frame.call_count == send_count_before

    # STOPPED — buffers clear
    engine.set_transport_state(TransportState.STOPPED)
    await asyncio.sleep(0.05)
    assert engine.ring_buffer.count == 0

    engine.stop()
    scheduler.stop()
    engine_task.cancel()
    scheduler_task.cancel()
    await asyncio.gather(engine_task, scheduler_task, return_exceptions=True)
```

- [ ] **Step 2: Run integration test**

Run: `uv run pytest tests/test_transport_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_transport_integration.py
git commit -m "test: add transport lifecycle integration test"
```

---

### Task 13: Simplify

Run the simplify skill to review all changed code for reuse, quality, and efficiency.

- [ ] **Step 1: Run simplify skill**

Invoke: `superpowers:simplify`

- [ ] **Step 2: Fix any issues found**

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All PASS

- [ ] **Step 4: Commit fixes**

---

### Task 14: Code Architect Review

Run the code architect review against the spec.

- [ ] **Step 1: Dispatch code-reviewer agent**

Review all changes against the spec at `docs/superpowers/specs/2026-03-21-transport-controls-design.md`.

- [ ] **Step 2: Fix any issues found**

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -x -v && cd frontend && npx tsc --noEmit`
Expected: All PASS

- [ ] **Step 4: Final commit**
