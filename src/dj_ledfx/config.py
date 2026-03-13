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

    # LIFX
    lifx_enabled: bool = True
    lifx_discovery_timeout_s: float = 10.0
    lifx_default_kelvin: int = 3500
    lifx_echo_probe_interval_s: float = 2.0
    lifx_latency_strategy: str = "ema"
    lifx_latency_ms: float = 50.0
    lifx_manual_offset_ms: float = 0.0
    lifx_max_fps: int = 60
    lifx_latency_window_size: int = 60

    # Govee
    govee_enabled: bool = True
    govee_discovery_timeout_s: float = 5.0
    govee_latency_strategy: str = "ema"
    govee_latency_ms: float = 100.0
    govee_manual_offset_ms: float = 0.0
    govee_max_fps: int = 40
    govee_latency_window_size: int = 60
    govee_probe_interval_s: float = 5.0
    govee_segment_override: int | None = None

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
        if self.lifx_max_fps <= 0:
            errors.append("lifx_max_fps must be positive")
        if self.lifx_latency_window_size <= 0:
            errors.append("lifx_latency_window_size must be positive")
        if self.lifx_latency_strategy not in {"static", "ema", "windowed_mean"}:
            errors.append("lifx_latency_strategy must be one of: static, ema, windowed_mean")
        if self.lifx_discovery_timeout_s <= 0:
            errors.append("lifx_discovery_timeout_s must be positive")
        if self.lifx_echo_probe_interval_s <= 0:
            errors.append("lifx_echo_probe_interval_s must be positive")
        if not (2500 <= self.lifx_default_kelvin <= 9000):
            errors.append("lifx_default_kelvin must be between 2500 and 9000")
        if self.lifx_latency_ms < 0:
            errors.append("lifx_latency_ms must be non-negative")
        if self.govee_max_fps <= 0:
            errors.append("govee_max_fps must be positive")
        if self.govee_latency_window_size <= 0:
            errors.append("govee_latency_window_size must be positive")
        if self.govee_latency_strategy not in {"static", "ema", "windowed_mean"}:
            errors.append("govee_latency_strategy must be one of: static, ema, windowed_mean")
        if self.govee_discovery_timeout_s <= 0:
            errors.append("govee_discovery_timeout_s must be positive")
        if self.govee_probe_interval_s <= 0:
            errors.append("govee_probe_interval_s must be positive")
        if self.govee_latency_ms < 0:
            errors.append("govee_latency_ms must be non-negative")
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

    if "devices" in raw and "lifx" in raw["devices"]:
        lifx = raw["devices"]["lifx"]
        if "enabled" in lifx:
            kwargs["lifx_enabled"] = lifx["enabled"]
        if "discovery_timeout_s" in lifx:
            kwargs["lifx_discovery_timeout_s"] = lifx["discovery_timeout_s"]
        if "default_kelvin" in lifx:
            kwargs["lifx_default_kelvin"] = lifx["default_kelvin"]
        if "echo_probe_interval_s" in lifx:
            kwargs["lifx_echo_probe_interval_s"] = lifx["echo_probe_interval_s"]
        if "latency_strategy" in lifx:
            kwargs["lifx_latency_strategy"] = lifx["latency_strategy"]
        if "latency_ms" in lifx:
            kwargs["lifx_latency_ms"] = lifx["latency_ms"]
        if "manual_offset_ms" in lifx:
            kwargs["lifx_manual_offset_ms"] = lifx["manual_offset_ms"]
        if "max_fps" in lifx:
            kwargs["lifx_max_fps"] = lifx["max_fps"]
        if "latency_window_size" in lifx:
            kwargs["lifx_latency_window_size"] = lifx["latency_window_size"]

    if "devices" in raw and "govee" in raw["devices"]:
        govee = raw["devices"]["govee"]
        if "enabled" in govee:
            kwargs["govee_enabled"] = govee["enabled"]
        if "discovery_timeout_s" in govee:
            kwargs["govee_discovery_timeout_s"] = govee["discovery_timeout_s"]
        if "latency_strategy" in govee:
            kwargs["govee_latency_strategy"] = govee["latency_strategy"]
        if "latency_ms" in govee:
            kwargs["govee_latency_ms"] = govee["latency_ms"]
        if "manual_offset_ms" in govee:
            kwargs["govee_manual_offset_ms"] = govee["manual_offset_ms"]
        if "max_fps" in govee:
            kwargs["govee_max_fps"] = govee["max_fps"]
        if "latency_window_size" in govee:
            kwargs["govee_latency_window_size"] = govee["latency_window_size"]
        if "probe_interval_s" in govee:
            kwargs["govee_probe_interval_s"] = govee["probe_interval_s"]
        if "segment_override" in govee:
            kwargs["govee_segment_override"] = govee["segment_override"]

    return AppConfig(**kwargs)  # type: ignore[arg-type]
