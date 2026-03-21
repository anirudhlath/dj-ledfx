"""WebSocket subscription state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from dj_ledfx.persistence.state_db import StateDB


@dataclass
class ClientSubscription:
    """Per-client subscription state."""

    beat_fps: float = 10.0
    frame_fps: float = 0.0  # 0 = not subscribed
    frame_devices: list[str] = field(default_factory=list)  # empty = all


def get_db(request: Request) -> StateDB:
    """Return StateDB from request app state or raise 503."""
    from fastapi import HTTPException

    db = getattr(request.app.state, "state_db", None)
    if db is None:
        raise HTTPException(503, "StateDB not available")
    return db  # type: ignore[return-value]
