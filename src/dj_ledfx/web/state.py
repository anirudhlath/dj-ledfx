"""WebSocket subscription state management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClientSubscription:
    """Per-client subscription state."""

    beat_fps: float = 10.0
    frame_fps: float = 0.0  # 0 = not subscribed
    frame_devices: list[str] = field(default_factory=list)  # empty = all
