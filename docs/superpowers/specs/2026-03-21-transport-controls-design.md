# Transport Controls Design

Add play, stop, and simulate transport controls to dj-ledfx. The app starts in stopped state — effects don't run until the user explicitly plays. Simulate renders effects on the web UI without sending to physical devices.

## Transport State Model

```python
class TransportState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    SIMULATING = "simulating"
```

- Lives on `EffectEngine` as a `transport_state` property, defaults to `STOPPED`
- State changes emit `TransportStateChangedEvent(old_state, new_state)` via EventBus
- Not persisted — always starts as `STOPPED`

## Engine Behavior

The engine's `run()` method is launched once via `asyncio.create_task()` at startup and runs for the app's lifetime. It is never terminated and recreated. The `_resume_event` gates the inner render loop — when STOPPED, the task stays alive but blocked on the event.

`EffectEngine.run()` loop structure:

```python
while self._running:          # outer loop — lifetime of app
    await self._resume_event.wait()  # blocks when STOPPED
    # inner render loop — runs while not STOPPED
    while self._resume_event.is_set():
        self.tick(now)
        # ... FPS sleep logic ...
```

- **STOPPED** — blocks on `_resume_event.wait()`. Zero CPU. Instant wake on state change.
- **PLAYING / SIMULATING** — renders normally, calls `tick()` at configured FPS

The engine does not distinguish between Playing and Simulating — it always renders when not stopped. The distinction is handled by the scheduler.

On transition to `STOPPED`, the engine clears the ring buffer via a new `RingBuffer.clear()` method (resets `_write_index`, `_count`, fills `_frames` with `None`).

### State Transition API

```python
def set_transport_state(self, state: TransportState) -> None
```

- Sets `_transport_state`
- If transitioning away from `STOPPED`: sets `_resume_event`
- If transitioning to `STOPPED`: clears `_resume_event`, clears ring buffers (all pipelines)
- Emits `TransportStateChangedEvent` via EventBus

## Scheduler Behavior

The scheduler subscribes to `TransportStateChangedEvent` via the EventBus and maintains its own `_transport_state` and `_resume_event`. It does **not** read from the engine directly — no coupling between scheduler and engine.

- **STOPPED** — distributor loop blocks on `_resume_event.wait()` (same gating pattern as engine). Does not distribute frame slots. Send loops also gate on the event.
- **PLAYING** — normal operation. Distributes frame slots, send loops call `device.adapter.send_frame()`, writes to `frame_snapshots`.
- **SIMULATING** — send loops resolve frames from ring buffer and write to `frame_snapshots` (for web UI) but **skip `device.adapter.send_frame()`**. No physical device output. Metrics: `DEVICE_FPS` and frame snapshot sequencing still update. `DEVICE_SEND_DURATION` and latency probing are skipped (no actual send).

The scheduler receives `TransportStateChangedEvent` and sets/clears its `_resume_event` accordingly. On `→ STOPPED`, it also triggers device state restore (see below).

## Device State Capture & Restore

### Capture

- **Who calls it:** `DeviceManager` calls `capture_state()` during its device connection lifecycle (after `adapter.connect()` succeeds), then persists the result to `state.db`
- **When:** On device connect, only if transport state is `STOPPED`. If a device reconnects while `PLAYING`/`SIMULATING`, skip capture (the saved state from before effects started is still valid)
- DeviceManager checks transport state via the EventBus (subscribes to `TransportStateChangedEvent` to track current state)
- If the protocol doesn't support state capture: persist "50% white" as the fallback

### Restore

- On `PLAYING → STOPPED` or `SIMULATING → STOPPED`: restore each device to its persisted state
- Scheduler calls `restore_state(saved_bytes)` on each connected device after stopping frame distribution

### Adapter Interface

```python
class DeviceAdapter(ABC):
    # ... existing methods ...

    async def capture_state(self) -> bytes:
        """Capture current device state. Default: 50% white."""
        ...

    async def restore_state(self, state: bytes) -> None:
        """Restore device to a previously captured state. Default: send as RGB frame."""
        ...
```

- `capture_state()` returns adapter-specific bytes (raw RGB, LIFX HSBK, etc.)
- `restore_state()` interprets those bytes and applies them
- Default implementation: `capture_state()` returns 50% white RGB array; `restore_state()` calls `send_frame()` with the bytes interpreted as RGB
- Individual adapters override as protocol support is added

### Persistence

New table in `state.db`:

```sql
CREATE TABLE device_saved_state (
    stable_id TEXT PRIMARY KEY,
    state_bytes BLOB NOT NULL,
    captured_at TEXT NOT NULL
);
```

Updated on device connect (when transport is `STOPPED`). Read on `PLAYING → STOPPED` transition.

## REST API

New router: `router_transport.py`

```
GET  /api/transport  → { "state": "stopped" }
PUT  /api/transport  → { "state": "playing" }  → 200 { "state": "playing" }
```

Accepts body `{ "state": "stopped" | "playing" | "simulating" }`.

## WebSocket API

- New channel `"transport"` — broadcasts `{ "channel": "transport", "state": "..." }` to all connected clients on every state change
- New action `"set_transport"` — clients can change state via WS: `{ "action": "set_transport", "state": "playing" }`
- `_status_poll` heartbeat includes `"transport": "stopped"` field so new clients get current state on connect

## Frontend

### Transport Section (`transport-section.tsx`)

Replace the current read-only play/stop badge with three interactive buttons:

- **Play** (triangle icon) — sets `playing`, highlighted green when active
- **Simulate** (eye icon) — sets `simulating`, highlighted amber when active
- **Stop** (square icon) — sets `stopped`, highlighted red when active

The current badge shows DJ deck play state (from BeatClock). This becomes a small secondary text indicator since transport state and deck play state are now separate concepts.

### Keyboard Shortcuts

- `Space` — toggle Play ↔ Stop
- `S` — toggle Simulate ↔ Stop
- Only active when no input/textarea is focused

### New Hook: `use-transport.ts`

- Subscribes to WS `transport` channel for real-time state
- Exposes `state: TransportState` and `setState(newState)` via REST PUT
- Used by `transport-section.tsx`

### Types (`types.ts`)

```typescript
export type TransportState = "stopped" | "playing" | "simulating"
```

## Backlog (out of scope)

- Push-based frame delivery: replace `_frame_poll` polling with event-driven push from scheduler to WS hub
