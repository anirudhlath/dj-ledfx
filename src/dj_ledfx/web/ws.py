"""Multiplexed WebSocket hub with beat, stats, status, and frame channels."""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from dj_ledfx.web.state import ClientSubscription


async def ws_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint handler."""
    await websocket.accept()
    app = websocket.app
    sub = ClientSubscription()
    tasks: list[asyncio.Task] = []

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
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _send_json(ws: WebSocket, data: dict[str, Any]) -> None:
    """Send JSON message, silently drop if connection closed."""
    try:
        await ws.send_text(json.dumps(data))
    except Exception:
        pass


async def _beat_poll(ws: WebSocket, app: Any, sub: ClientSubscription) -> None:
    """Poll beat state at client-requested rate."""
    while True:
        interval = 1.0 / max(sub.beat_fps, 1.0)
        await asyncio.sleep(interval)
        clock = app.state.beat_clock
        try:
            beat_data = {
                "channel": "beat",
                "bpm": clock.bpm,
                "beat_phase": clock.beat_phase,
                "bar_phase": clock.bar_phase,
                "is_playing": clock.is_playing,
                "beat_pos": clock.beat_position,
                "pitch_percent": clock.pitch_percent,
                "deck_number": clock.last_deck_number,
                "deck_name": clock.last_deck_name,
            }
        except AttributeError:
            beat_data = {
                "channel": "beat",
                "bpm": getattr(clock, "bpm", 0),
                "beat_phase": getattr(clock, "beat_phase", 0),
                "bar_phase": getattr(clock, "bar_phase", 0),
                "is_playing": getattr(clock, "is_playing", False),
            }
        await _send_json(ws, beat_data)


async def _stats_poll(ws: WebSocket, app: Any) -> None:
    """Poll device stats at ~1fps."""
    while True:
        await asyncio.sleep(1.0)
        scheduler = app.state.scheduler
        try:
            stats = scheduler.get_device_stats()
            stats_data = {
                "channel": "stats",
                "devices": [
                    {
                        "name": s.device_name,
                        "fps": s.send_fps,
                        "latency_ms": s.effective_latency_ms,
                        "frames_dropped": s.frames_dropped,
                        "connected": s.connected,
                    }
                    for s in stats
                ],
            }
        except Exception:
            stats_data = {"channel": "stats", "devices": []}
        await _send_json(ws, stats_data)


async def _status_poll(ws: WebSocket, app: Any) -> None:
    """Poll system status at ~0.1fps."""
    while True:
        await asyncio.sleep(10.0)
        await _send_json(ws, {"channel": "status", "ok": True})


async def _frame_poll(ws: WebSocket, app: Any, sub: ClientSubscription) -> None:
    """Poll frame snapshots at client-requested rate, sending binary frames."""
    while True:
        if sub.frame_fps <= 0:
            await asyncio.sleep(0.5)
            continue
        interval = 1.0 / sub.frame_fps
        await asyncio.sleep(interval)
        scheduler = app.state.scheduler
        snapshots = scheduler.frame_snapshots
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
    tasks: list[asyncio.Task],
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
        deck = app.state.effect_deck
        params = msg.get("params", {})
        try:
            if "effect" in msg and msg["effect"] != deck.effect_name:
                from dj_ledfx.effects.registry import create_effect

                new_effect = create_effect(msg["effect"], **params)
                deck.swap_effect(new_effect)
            elif params:
                deck.effect.set_params(**params)
            await _send_json(ws, {"channel": "ack", "id": cmd_id, "action": action})
        except (KeyError, ValueError) as e:
            await _send_json(ws, {"channel": "error", "id": cmd_id, "detail": str(e)})

    else:
        await _send_json(
            ws, {"channel": "error", "id": cmd_id, "detail": f"Unknown action: {action}"}
        )
