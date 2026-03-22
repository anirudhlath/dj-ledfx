from __future__ import annotations

from enum import Enum


class TransportState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    SIMULATING = "simulating"

    @property
    def is_active(self) -> bool:
        return self is not TransportState.STOPPED
