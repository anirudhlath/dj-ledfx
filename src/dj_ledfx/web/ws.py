"""Multiplexed WebSocket hub stub — full implementation in Task 23."""
from __future__ import annotations

from fastapi import WebSocket


async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.close()
