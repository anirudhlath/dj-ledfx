"""Multiplexed WebSocket hub with beat, stats, status, and frame channels."""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from dj_ledfx.events import TransportStateChangedEvent
from dj_ledfx.transport import TransportState
from dj_ledfx.web.state import ClientSubscription


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


async def transport_broadcast(app: Any) -> None:
    """Listen for TransportStateChangedEvent and broadcast to all WS clients."""
    event_bus = app.state.event_bus
    queue: asyncio.Queue[str] = asyncio.Queue()

    def on_change(event: TransportStateChangedEvent) -> None:
        queue.put_nowait(event.new_state.value)

    event_bus.subscribe(TransportStateChangedEvent, on_change)
    try:
        while True:
            state_value = await queue.get()
            await _broadcast_json(app, {"channel": "transport", "state": state_value})
    finally:
        event_bus.unsubscribe(TransportStateChangedEvent, on_change)


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
                        "fps": s.send_fps,
                        "latency_ms": s.effective_latency_ms,
                        "frames_dropped": s.frames_dropped,
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
        scheduler = app.state.scheduler
        stats = scheduler.get_device_stats()
        status_data: dict[str, Any] = {
            "channel": "status",
            "ok": True,
            "device_count": len(stats),
            "avg_render_ms": engine.avg_render_time_ms,
            "transport": engine.transport_state.value,
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

    elif action == "set_effect":
        scene_id = msg.get("scene_id")
        try:
            if scene_id and app.state.pipeline_manager is not None:
                app.state.pipeline_manager.set_scene_effect(
                    scene_id, msg.get("effect"), msg.get("params", {})
                )
            else:
                deck = app.state.effect_deck
                deck.apply_update(msg.get("effect"), msg.get("params", {}))
            await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})
        except (KeyError, ValueError, TypeError) as e:
            await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": str(e)})

    elif action == "set_transport":
        engine = app.state.effect_engine
        state_str = msg.get("state", "")
        try:
            new_state = TransportState(state_str)
            engine.set_transport_state(new_state)
            await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})
        except (ValueError, KeyError) as e:
            await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": str(e)})

    else:
        await _send_json(
            ws, {"channel": "error", "id": cmd_id, "detail": f"Unknown action: {action}"}
        )
