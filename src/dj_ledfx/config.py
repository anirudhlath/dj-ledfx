from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class EngineConfig:
    fps: int = 60
    max_lookahead_ms: int = 1000


@dataclass
class EffectConfig:
    active_effect: str = "beat_pulse"
    beat_pulse_palette: list[str] = field(
        default_factory=lambda: ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
    )
    beat_pulse_gamma: float = 2.0


@dataclass
class NetworkConfig:
    interface: str = "auto"
    passive_mode: bool = True


@dataclass
class WebConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8080
    static_dir: str | None = None
    cors_origins: list[str] = field(
        default_factory=lambda: [
            "http://localhost:5173",  # SvelteKit dev
            "http://localhost:4173",  # SvelteKit preview
            "http://localhost:8080",  # production self-serve
        ]
    )


@dataclass
class OpenRGBConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 6742
    latency_strategy: str = "windowed_mean"
    latency_ms: float = 10.0
    manual_offset_ms: float = 0.0
    max_fps: int = 60
    latency_window_size: int = 60


@dataclass
class LIFXConfig:
    enabled: bool = True
    discovery_timeout_s: float = 10.0
    default_kelvin: int = 3500
    echo_probe_interval_s: float = 2.0
    latency_strategy: str = "ema"
    latency_ms: float = 50.0
    manual_offset_ms: float = 0.0
    max_fps: int = 60
    latency_window_size: int = 60


@dataclass
class GoveeConfig:
    enabled: bool = True
    discovery_timeout_s: float = 5.0
    latency_strategy: str = "ema"
    latency_ms: float = 100.0
    manual_offset_ms: float = 0.0
    max_fps: int = 40
    latency_window_size: int = 60
    probe_interval_s: float = 5.0
    segment_override: int | None = None


@dataclass
class DevicesConfig:
    openrgb: OpenRGBConfig = field(default_factory=OpenRGBConfig)
    lifx: LIFXConfig = field(default_factory=LIFXConfig)
    govee: GoveeConfig = field(default_factory=GoveeConfig)


@dataclass
class AppConfig:
    engine: EngineConfig = field(default_factory=EngineConfig)
    effect: EffectConfig = field(default_factory=EffectConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    web: WebConfig = field(default_factory=WebConfig)
    devices: DevicesConfig = field(default_factory=DevicesConfig)
    scene_config: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.engine.fps <= 0:
            raise ValueError("engine_fps must be positive")
        if self.engine.max_lookahead_ms < 0:
            raise ValueError("max_lookahead_ms must be non-negative")
        if self.effect.beat_pulse_gamma <= 0:
            raise ValueError("beat_pulse_gamma must be positive")
        for name, dev_cfg in [
            ("openrgb", self.devices.openrgb),
            ("lifx", self.devices.lifx),
            ("govee", self.devices.govee),
        ]:
            if hasattr(dev_cfg, "max_fps") and dev_cfg.max_fps <= 0:
                raise ValueError(f"{name} max_fps must be positive")
            if hasattr(dev_cfg, "latency_strategy"):
                valid = {"static", "ema", "windowed_mean"}
                if dev_cfg.latency_strategy not in valid:
                    raise ValueError(f"{name} latency_strategy must be one of {valid}")
            if hasattr(dev_cfg, "latency_ms") and dev_cfg.latency_ms < 0:
                raise ValueError(f"{name} latency_ms must be non-negative")
            if hasattr(dev_cfg, "latency_window_size") and dev_cfg.latency_window_size <= 0:
                raise ValueError(f"{name} latency_window_size must be positive")
        lifx = self.devices.lifx
        if not (2500 <= lifx.default_kelvin <= 9000):
            raise ValueError("lifx default_kelvin must be between 2500 and 9000")
        if lifx.discovery_timeout_s <= 0:
            raise ValueError("lifx discovery_timeout_s must be positive")
        if lifx.echo_probe_interval_s <= 0:
            raise ValueError("lifx echo_probe_interval_s must be positive")
        govee = self.devices.govee
        if govee.discovery_timeout_s <= 0:
            raise ValueError("govee discovery_timeout_s must be positive")
        if govee.probe_interval_s <= 0:
            raise ValueError("govee probe_interval_s must be positive")
        if self.web.port < 0 or self.web.port > 65535:
            raise ValueError("web port must be 0-65535")


def _filter_fields(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    import dataclasses

    valid = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - valid
    if unknown:
        logger.warning("Ignoring unknown config keys for {}: {}", cls.__name__, unknown)
    return {k: v for k, v in data.items() if k in valid}


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        logger.info("No config file found at {}, using defaults", path)
        return AppConfig()

    logger.info("Loading config from {}", path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    engine = EngineConfig(**_filter_fields(EngineConfig, data.get("engine", {})))

    effect_data = dict(data.get("effect", {}))
    if "active" in effect_data and "active_effect" not in effect_data:
        effect_data["active_effect"] = effect_data.pop("active")
    elif "active" in effect_data:
        effect_data.pop("active")
    beat_pulse_sub = effect_data.pop("beat_pulse", {})
    if isinstance(beat_pulse_sub, dict):
        if "palette" in beat_pulse_sub:
            effect_data["beat_pulse_palette"] = beat_pulse_sub["palette"]
        if "gamma" in beat_pulse_sub:
            effect_data["beat_pulse_gamma"] = beat_pulse_sub["gamma"]
    effect = EffectConfig(**_filter_fields(EffectConfig, effect_data))

    network_data = dict(data.get("network", {}))
    prodjlink_data = data.get("prodjlink", {})
    if prodjlink_data:
        logger.warning("[prodjlink] config section is deprecated, use [network] instead")
        if "passive_mode" in prodjlink_data and "passive_mode" not in network_data:
            network_data["passive_mode"] = prodjlink_data["passive_mode"]
    network = NetworkConfig(**_filter_fields(NetworkConfig, network_data))

    web = WebConfig(**_filter_fields(WebConfig, data.get("web", {})))

    devices_data = data.get("devices", {})
    devices = DevicesConfig(
        openrgb=OpenRGBConfig(**_filter_fields(OpenRGBConfig, devices_data.get("openrgb", {}))),
        lifx=LIFXConfig(**_filter_fields(LIFXConfig, devices_data.get("lifx", {}))),
        govee=GoveeConfig(**_filter_fields(GoveeConfig, devices_data.get("govee", {}))),
    )

    scene_config = data.get("scene")

    return AppConfig(
        engine=engine,
        effect=effect,
        network=network,
        web=web,
        devices=devices,
        scene_config=scene_config,
    )


def strip_none(d: dict[str, Any]) -> None:
    for key in list(d.keys()):
        if isinstance(d[key], dict):
            strip_none(d[key])
        elif d[key] is None:
            del d[key]


def save_config(config: AppConfig, path: Path) -> None:
    import dataclasses

    import tomli_w

    data = dataclasses.asdict(config)
    strip_none(data)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(tomli_w.dumps(data).encode())
    os.replace(tmp, path)
