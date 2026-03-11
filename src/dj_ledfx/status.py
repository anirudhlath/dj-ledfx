from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SystemStatus:
    prodjlink_connected: bool = False
    active_player_count: int = 0
    current_bpm: float | None = None
    connected_devices: list[str] = field(default_factory=list)
    device_errors: dict[str, str] = field(default_factory=dict)
    buffer_fill_level: float = 0.0
    avg_frame_render_time_ms: float = 0.0

    def summary(self) -> str:
        bpm_str = f"{self.current_bpm:.1f}" if self.current_bpm else "N/A"
        devices = ", ".join(self.connected_devices) or "none"
        return (
            f"BPM={bpm_str} | "
            f"players={self.active_player_count} | "
            f"devices=[{devices}] | "
            f"buffer={self.buffer_fill_level:.0%} | "
            f"render={self.avg_frame_render_time_ms:.1f}ms"
        )
