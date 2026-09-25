"""Multiplexed WebSocket hub with beat, stats, status, and frame channels."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from dj_ledfx.devices.lights import LightIndex
from dj_ledfx.web import contract
from dj_ledfx.web.frames import encode_frame_v1, encode_frame_v2, light_frames
from dj_ledfx.web.state import ClientSubscription
from dj_ledfx.zones.frames import STREAMS
from dj_ledfx.zones.model import AttentionChanged, LightsChanged, PreviewOnlyChanged, ZonesChanged

_GOING_AWAY = 1001  # RFC 6455 close code: the server is going down


class Session:
    """An open /ws connection: pushed channels go to its websocket, close_all can end it,
    and it says when it has ended."""

    def __init__(self, websocket: WebSocket) -> None:
        loop = asyncio.get_running_loop()
        self.websocket = websocket
        self.stop: asyncio.Future[None] = loop.create_future()
        self.ended: asyncio.Future[None] = loop.create_future()


async def close_all(app: Any, *, timeout: float = 1.0) -> None:
    """Close every open /ws session (going away) and refuse new ones, before the web server stops.

    granian's Server.stop() leaves an open websocket waiting on its receive, and the loop's
    final cancel then logs a traceback, so each session ends itself here first.
    """
    app.state.ws_closing = True
    sessions: set[Session] = app.state.ws_sessions
    for session in sessions:
        if not session.stop.done():
            session.stop.set_result(None)
    if not sessions:
        return
    _, still_open = await asyncio.wait([s.ended for s in sessions], timeout=timeout)
    if still_open:
        logger.warning("{} websocket(s) still open {} s after closing", len(still_open), timeout)


async def _receive_unless_stopped(websocket: WebSocket, stop: asyncio.Future[None]) -> str | None:
    """The client's next message, or None once close_all has stopped the session."""
    receive = asyncio.ensure_future(websocket.receive_text())
    either: list[asyncio.Future[Any]] = [receive, stop]
    try:
        await asyncio.wait(either, return_when=asyncio.FIRST_COMPLETED)
    except BaseException:
        # Cancelled: pass the cancellation on as it came. Awaiting the receive here could
        # replace it with the receive's own, which anyio's cancel scopes don't recognise.
        receive.cancel()
        raise
    if receive.done():
        return receive.result()
    # granian holds back a close while a receive is pending, so end the receive first.
    receive.cancel()
    await asyncio.wait([receive])
    return None


async def ws_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint handler."""
    app = websocket.app
    if app.state.ws_closing:
        await websocket.close(code=_GOING_AWAY)  # refused: the server is stopping
        return
    await websocket.accept()
    sub = ClientSubscription()
    tasks: list[asyncio.Task[None]] = []
    session = Session(websocket)
    sessions: set[Session] = app.state.ws_sessions
    sessions.add(session)

    try:
        for message in initial_messages(app):
            await _send_json(websocket, message)

        # Start polling tasks
        tasks.append(asyncio.create_task(_beat_poll(websocket, app, sub)))
        tasks.append(asyncio.create_task(_stats_poll(websocket, app)))
        tasks.append(asyncio.create_task(_status_poll(websocket, app)))

        # Handle incoming commands until the client leaves or the server stops
        while (data := await _receive_unless_stopped(websocket, session.stop)) is not None:
            try:
                msg = json.loads(data)
                await _handle_command(websocket, app, sub, tasks, msg)
            except json.JSONDecodeError:
                await _send_json(websocket, {"channel": "error", "detail": "Invalid JSON"})
        await websocket.close(code=_GOING_AWAY)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket error: {}", e)
    finally:
        sessions.discard(session)
        _watch(app, sub, [])  # a closed tab watches nothing: its preview can end
        session.ended.set_result(None)
        for t in tasks:
            t.cancel()
        if tasks:
            # wait, not gather: a gather cancelled with the session would raise the poll
            # tasks' CancelledError instead of the session's own
            await asyncio.wait(tasks)


async def _send_json(ws: WebSocket, data: dict[str, Any]) -> None:
    """Send JSON message, silently drop if connection closed."""
    try:
        await ws.send_text(json.dumps(data))
    except Exception:
        pass


async def _broadcast_json(app: Any, data: dict[str, Any]) -> None:
    """Broadcast JSON message to all connected WebSocket clients."""
    sessions: set[Session] = app.state.ws_sessions
    clients = [session.websocket for session in sessions]
    if clients:
        await asyncio.gather(*(_send_json(ws, data) for ws in clients))


def _running_message(app: Any) -> dict[str, Any] | None:
    zones = getattr(app.state, "zone_manager", None)
    if zones is None:
        return None
    running = contract.running_out(zones.running())
    return {"channel": "running", **running.model_dump(mode="json", by_alias=True)}


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


def _transport_message(app: Any) -> dict[str, Any] | None:
    """Preview-only in the contract's transport terms (web spec §12.4)."""
    zones = getattr(app.state, "zone_manager", None)
    if zones is None:
        return None
    return {"channel": "transport", "state": "simulating" if zones.preview_only else "playing"}


# Each pushed channel's snapshot, and the events that make a channel stale.
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


async def _beat_poll(ws: WebSocket, app: Any, sub: ClientSubscription) -> None:
    """Poll beat state at client-requested rate."""
    last_sent: dict[str, Any] = {}
    while True:
        interval = 1.0 / max(sub.beat_fps, 1.0)
        await asyncio.sleep(interval)
        clock = app.state.beat_clock
        state = clock.get_state()
        beat_data = {
            "channel": "beat",
            "bpm": state.bpm,
            "beat_phase": state.beat_phase,
            "bar_phase": state.bar_phase,
            "is_playing": state.is_playing,
            "beat_pos": int(state.bar_phase * 4) % 4 + 1,
            "pitch_percent": state.pitch_percent,
            "deck_number": state.deck_number,
            "deck_name": state.deck_name,
        }
        if beat_data != last_sent:
            await _send_json(ws, beat_data)
            last_sent = beat_data


async def _stats_poll(ws: WebSocket, app: Any) -> None:
    """Poll device stats at ~1fps."""
    while True:
        await asyncio.sleep(1.0)
        await _send_json(ws, stats_message(app))


def stats_message(app: Any) -> dict[str, Any]:
    """The stats channel's message: each device's send statistics."""
    scheduler = app.state.scheduler
    try:
        stats = scheduler.get_device_stats()
        # Each device's status by stable id: lights may share a name (the RAM sticks)
        manager = app.state.device_manager
        status_by_id: dict[str, str] = {}
        try:
            for d in manager.devices:
                status_by_id[d.adapter.device_info.effective_id] = d.status
        except Exception:
            pass
        return {
            "channel": "stats",
            "devices": [
                {
                    "id": s.device_id,
                    "name": s.device_name,
                    "send_fps": s.send_fps,
                    "latency_ms": s.effective_latency_ms,
                    "frames_dropped": s.frames_dropped,
                    "dropped_pct": s.dropped_pct,
                    "connected": s.connected,
                    "status": status_by_id.get(s.device_id, "online"),
                }
                for s in stats
            ],
        }
    except Exception:
        return {"channel": "stats", "devices": []}


async def _status_poll(ws: WebSocket, app: Any) -> None:
    """Poll system status at ~0.1fps — heartbeat with health info."""
    while True:
        await asyncio.sleep(10.0)
        engine = app.state.effect_engine
        transport = _transport_message(app)
        scheduler = app.state.scheduler
        stats = scheduler.get_device_stats()
        status_data: dict[str, Any] = {
            "channel": "status",
            "ok": True,
            "device_count": len(stats),
            "avg_render_ms": engine.avg_render_time_ms,
            "transport": transport["state"] if transport is not None else "playing",
        }
        await _send_json(ws, status_data)


async def _frame_poll(ws: WebSocket, app: Any, sub: ClientSubscription) -> None:
    """Send frames at the client's rate, in the protocol it subscribed with."""
    seq = 0
    while True:
        if sub.frame_fps <= 0:
            await asyncio.sleep(0.5)
            continue
        await asyncio.sleep(1.0 / sub.frame_fps)
        seq += 1
        for message in frame_messages(app, sub, seq):
            try:
                await ws.send_bytes(message)
            except Exception:
                return


def frame_messages(app: Any, sub: ClientSubscription, seq: int) -> list[bytes]:
    """One tick's frames for a session: v1 by device from the live stream, or v2 by light
    for each stream it watches."""
    feed = getattr(app.state, "frame_feed", None)
    if feed is None:
        return []
    if sub.frame_protocol == 1:
        return [
            encode_frame_v1(device_id, seq, colors)
            for device_id, colors in feed.frames("live").items()
            if not sub.frame_devices or device_id in sub.frame_devices
        ]
    index = LightIndex.from_manager(app.state.device_manager)
    wanted = set(sub.frame_lights)
    return [
        encode_frame_v2(stream, light_id, seq, colors)
        for stream in sub.frame_streams
        for light_id, colors in light_frames(index, feed.frames(stream)).items()
        if not wanted or light_id in wanted
    ]


def _subscribe_frames(sub: ClientSubscription, msg: dict[str, Any]) -> None:
    """subscribe_frames: v2 with "protocol": 2 (ruling 3), else v1 as the old UI sends it.
    Everything is checked before the subscription changes."""
    protocol = msg.get("protocol", 1)
    if protocol not in (1, 2):
        raise ValueError(f"Unknown frame protocol {protocol!r}; expected 1 or 2")
    if protocol == 1:
        fps = min(float(msg.get("fps", 10)), 30.0)
        sub.frame_devices = [str(device) for device in msg.get("devices") or []]
        sub.frame_protocol, sub.frame_fps, sub.frame_streams = 1, fps, ["live"]
        return
    streams = [str(stream) for stream in msg.get("streams") or ["live"]]
    unknown = [stream for stream in streams if stream not in STREAMS]
    if unknown:
        raise ValueError(f"Unknown frame stream {unknown[0]!r}; expected live or preview")
    fps = min(float(msg.get("fps", 30)), 60.0)
    sub.frame_lights = [str(light) for light in msg.get("lights") or []]
    sub.frame_protocol, sub.frame_fps, sub.frame_streams = 2, fps, streams


def _watch(app: Any, sub: ClientSubscription, streams: list[str]) -> None:
    watchers = getattr(app.state, "frame_watchers", None)
    if watchers is not None:
        watchers.set(sub, streams)


async def _handle_command(
    ws: WebSocket,
    app: Any,
    sub: ClientSubscription,
    tasks: list[asyncio.Task[None]],
    msg: dict[str, Any],
) -> None:
    """Handle incoming WS command."""
    action = msg.get("action")
    cmd_id = msg.get("id")

    if action == "subscribe_beat":
        fps = min(float(msg.get("fps", 10)), 30.0)
        sub.beat_fps = max(fps, 1.0)
        await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})

    elif action == "subscribe_frames":
        try:
            _subscribe_frames(sub, msg)
        except (TypeError, ValueError) as exc:
            await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": str(exc)})
            return
        _watch(app, sub, sub.frame_streams if sub.frame_fps > 0 else [])
        # Start frame polling if not already running
        has_frame_task = any(not t.done() and t.get_name() == "frame_poll" for t in tasks)
        if not has_frame_task and sub.frame_fps > 0:
            task = asyncio.create_task(_frame_poll(ws, app, sub))
            task.set_name("frame_poll")
            tasks.append(task)
        await _send_json(
            ws,
            {"channel": "ack", "id": cmd_id, "action": action, "protocol": sub.frame_protocol},
        )

    else:
        await _send_json(
            ws, {"channel": "error", "id": cmd_id, "detail": f"Unknown action: {action}"}
        )
