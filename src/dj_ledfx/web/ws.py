"""Multiplexed WebSocket hub with beat, stats, status, and frame channels."""

from __future__ import annotations

import asyncio
import json
import struct
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from dj_ledfx.web import contract
from dj_ledfx.web.state import ClientSubscription
from dj_ledfx.zones.model import AttentionChanged, LightsChanged, PreviewOnlyChanged, ZonesChanged


def _get_connected(app: Any) -> set[WebSocket]:
    """Return the per-app connected websockets set (initialized in create_app)."""
    return app.state.connected_websockets


async def ws_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint handler."""
    await websocket.accept()
    app = websocket.app
    sub = ClientSubscription()
    tasks: list[asyncio.Task[None]] = []
    _get_connected(app).add(websocket)

    try:
        for message in initial_messages(app):
            await _send_json(websocket, message)

        # Start polling tasks
        tasks.append(asyncio.create_task(_beat_poll(websocket, app, sub)))
        tasks.append(asyncio.create_task(_stats_poll(websocket, app)))
        tasks.append(asyncio.create_task(_status_poll(websocket, app)))

        # Handle incoming commands
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await _handle_command(websocket, app, sub, tasks, msg)
            except json.JSONDecodeError:
                await _send_json(websocket, {"channel": "error", "detail": "Invalid JSON"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket error: {}", e)
    finally:
        _get_connected(app).discard(websocket)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _send_json(ws: WebSocket, data: dict[str, Any]) -> None:
    """Send JSON message, silently drop if connection closed."""
    try:
        await ws.send_text(json.dumps(data))
    except Exception:
        pass


async def _broadcast_json(app: Any, data: dict[str, Any]) -> None:
    """Broadcast JSON message to all connected WebSocket clients."""
    clients = list(_get_connected(app))
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


def _transport_state(zones: Any) -> str:
    """Preview-only in the contract's transport terms (web spec §12.4)."""
    return "simulating" if zones.preview_only else "playing"


def _transport_message(app: Any) -> dict[str, Any] | None:
    zones = getattr(app.state, "zone_manager", None)
    if zones is None:
        return None
    return {"channel": "transport", "state": _transport_state(zones)}


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
        scheduler = app.state.scheduler
        try:
            stats = scheduler.get_device_stats()
            # Build name -> status map from device manager for status field
            manager = app.state.device_manager
            status_by_name: dict[str, str] = {}
            try:
                for d in manager.devices:
                    status_by_name[d.adapter.device_info.name] = d.status
            except Exception:
                pass
            stats_data = {
                "channel": "stats",
                "devices": [
                    {
                        "name": s.device_name,
                        "id": s.device_id,
                        "fps": s.send_fps,
                        "latency_ms": s.effective_latency_ms,
                        "frames_dropped": s.frames_dropped,
                        "dropped_pct": s.dropped_pct,
                        "connected": s.connected,
                        "status": status_by_name.get(s.device_name, "online"),
                    }
                    for s in stats
                ],
            }
        except Exception:
            stats_data = {"channel": "stats", "devices": []}
        await _send_json(ws, stats_data)


async def _status_poll(ws: WebSocket, app: Any) -> None:
    """Poll system status at ~0.1fps — heartbeat with health info."""
    while True:
        await asyncio.sleep(10.0)
        engine = app.state.effect_engine
        zones = getattr(app.state, "zone_manager", None)
        scheduler = app.state.scheduler
        stats = scheduler.get_device_stats()
        status_data: dict[str, Any] = {
            "channel": "status",
            "ok": True,
            "device_count": len(stats),
            "avg_render_ms": engine.avg_render_time_ms,
            "transport": _transport_state(zones) if zones is not None else "playing",
        }
        await _send_json(ws, status_data)


async def _frame_poll(ws: WebSocket, app: Any, sub: ClientSubscription) -> None:
    """Poll frame snapshots at client-requested rate, sending binary frames."""
    while True:
        if sub.frame_fps <= 0:
            await asyncio.sleep(0.5)
            continue
        interval = 1.0 / sub.frame_fps
        await asyncio.sleep(interval)
        scheduler = app.state.scheduler
        snapshots = dict(scheduler.frame_snapshots)
        for name, (colors, seq) in snapshots.items():
            if sub.frame_devices and name not in sub.frame_devices:
                continue
            # Binary format: [2B name_len LE][N name UTF-8][4B seq LE][RGB data]
            name_bytes = name.encode("utf-8")
            header = struct.pack("<H", len(name_bytes)) + name_bytes + struct.pack("<I", seq)
            try:
                await ws.send_bytes(header + colors.tobytes())
            except Exception:
                return


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
        sub.frame_fps = min(float(msg.get("fps", 10)), 30.0)
        sub.frame_devices = msg.get("devices", [])
        # Start frame polling if not already running
        has_frame_task = any(not t.done() and t.get_name() == "frame_poll" for t in tasks)
        if not has_frame_task and sub.frame_fps > 0:
            task = asyncio.create_task(_frame_poll(ws, app, sub))
            task.set_name("frame_poll")
            tasks.append(task)
        await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})

    else:
        await _send_json(
            ws, {"channel": "error", "id": cmd_id, "detail": f"Unknown action: {action}"}
        )
