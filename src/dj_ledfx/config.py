from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class AppConfig:
    # Network
    network_interface: str = "auto"

    # Pro DJ Link
    passive_mode: bool = True

    # Engine
    engine_fps: int = 60
    max_lookahead_ms: int = 1000

    # Effect
    active_effect: str = "beat_pulse"
    beat_pulse_palette: list[str] = field(
        default_factory=lambda: ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
    )
    beat_pulse_gamma: float = 2.0

    # OpenRGB
    openrgb_enabled: bool = True
    openrgb_host: str = "127.0.0.1"
    openrgb_port: int = 6742
    openrgb_latency_strategy: str = "windowed_mean"
    openrgb_latency_ms: float = 10.0
    openrgb_manual_offset_ms: float = 0.0
    openrgb_max_fps: int = 60
    openrgb_latency_window_size: int = 60

    def __post_init__(self) -> None:
        errors: list[str] = []
        if self.engine_fps <= 0:
            errors.append("fps must be positive")
        if self.max_lookahead_ms < 0:
            errors.append("max_lookahead_ms must be non-negative")
        if self.beat_pulse_gamma <= 0:
            errors.append("beat_pulse gamma must be positive")
        if self.openrgb_max_fps <= 0:
            errors.append("openrgb_max_fps must be positive")
        if self.openrgb_latency_window_size <= 0:
            errors.append("openrgb_latency_window_size must be positive")
        if self.openrgb_latency_strategy not in {"static", "ema", "windowed_mean"}:
            errors.append("openrgb_latency_strategy must be one of: static, ema, windowed_mean")
        if errors:
            raise ValueError(f"Config validation failed: {'; '.join(errors)}")


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        logger.info("No config file at {}, using defaults", path)
        return AppConfig()

    logger.info("Loading config from {}", path)
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    kwargs: dict[str, object] = {}

    if "network" in raw:
        if "interface" in raw["network"]:
            kwargs["network_interface"] = raw["network"]["interface"]

    if "prodjlink" in raw:
        if "passive_mode" in raw["prodjlink"]:
            kwargs["passive_mode"] = raw["prodjlink"]["passive_mode"]

    if "engine" in raw:
        if "fps" in raw["engine"]:
            kwargs["engine_fps"] = raw["engine"]["fps"]
        if "max_lookahead_ms" in raw["engine"]:
            kwargs["max_lookahead_ms"] = raw["engine"]["max_lookahead_ms"]

    if "effect" in raw:
        if "active" in raw["effect"]:
            kwargs["active_effect"] = raw["effect"]["active"]
        bp = raw["effect"].get("beat_pulse", {})
        if "palette" in bp:
            kwargs["beat_pulse_palette"] = bp["palette"]
        if "gamma" in bp:
            kwargs["beat_pulse_gamma"] = bp["gamma"]

    if "devices" in raw and "openrgb" in raw["devices"]:
        orgb = raw["devices"]["openrgb"]
        if "enabled" in orgb:
            kwargs["openrgb_enabled"] = orgb["enabled"]
        if "host" in orgb:
            kwargs["openrgb_host"] = orgb["host"]
        if "port" in orgb:
            kwargs["openrgb_port"] = orgb["port"]
        if "latency_strategy" in orgb:
            kwargs["openrgb_latency_strategy"] = orgb["latency_strategy"]
        if "latency_ms" in orgb:
            kwargs["openrgb_latency_ms"] = orgb["latency_ms"]
        if "manual_offset_ms" in orgb:
            kwargs["openrgb_manual_offset_ms"] = orgb["manual_offset_ms"]
        if "max_fps" in orgb:
            kwargs["openrgb_max_fps"] = orgb["max_fps"]
        if "latency_window_size" in orgb:
            kwargs["openrgb_latency_window_size"] = orgb["latency_window_size"]

    return AppConfig(**kwargs)  # type: ignore[arg-type]
