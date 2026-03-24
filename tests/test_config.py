import textwrap
from pathlib import Path

import pytest

from dj_ledfx.config import (
    AppConfig,
    DevicesConfig,
    DiscoveryConfig,
    EngineConfig,
    GoveeConfig,
    LIFXConfig,
    OpenRGBConfig,
    WebConfig,
    load_config,
    save_config,
)


def test_default_config() -> None:
    config = AppConfig()
    assert config.network.interface == "auto"
    assert config.engine.fps == 60
    assert config.engine.max_lookahead_ms == 1000
    assert config.effect.active_effect == "beat_pulse"
    assert config.devices.openrgb.host == "127.0.0.1"
    assert config.devices.openrgb.port == 6742


def test_load_config_from_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        textwrap.dedent("""\
        [network]
        interface = "eth0"

        [engine]
        fps = 30
        max_lookahead_ms = 500

        [effect]
        active = "beat_pulse"

        [effect.beat_pulse]
        gamma = 3.0

        [devices.openrgb]
        host = "192.168.1.100"
        port = 6742
        latency_ms = 20
    """)
    )
    config = load_config(toml_file)
    assert config.network.interface == "eth0"
    assert config.engine.fps == 30
    assert config.engine.max_lookahead_ms == 500
    assert config.devices.openrgb.host == "192.168.1.100"
    assert config.effect.beat_pulse_gamma == 3.0
    assert config.devices.openrgb.latency_ms == 20


def test_load_config_missing_file_returns_defaults() -> None:
    config = load_config(Path("/nonexistent/config.toml"))
    assert config.engine.fps == 60


def test_config_validation_bad_fps() -> None:
    with pytest.raises(ValueError, match="engine_fps"):
        AppConfig(engine=EngineConfig(fps=0))


def test_config_validation_bad_lookahead() -> None:
    with pytest.raises(ValueError, match="max_lookahead_ms"):
        AppConfig(engine=EngineConfig(max_lookahead_ms=-1))


def test_default_config_new_fields() -> None:
    config = AppConfig()
    assert config.devices.openrgb.max_fps == 60
    assert config.devices.openrgb.latency_window_size == 60
    assert config.devices.openrgb.latency_strategy == "windowed_mean"


def test_config_validation_bad_max_fps() -> None:
    with pytest.raises(ValueError, match="openrgb max_fps"):
        AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(max_fps=0)))


def test_config_validation_bad_window_size() -> None:
    with pytest.raises(ValueError, match="openrgb latency_window_size"):
        AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(latency_window_size=0)))


def test_config_validation_bad_strategy() -> None:
    with pytest.raises(ValueError, match="openrgb latency_strategy"):
        AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(latency_strategy="invalid")))


def test_load_config_new_toml_fields(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        textwrap.dedent("""\
        [devices.openrgb]
        max_fps = 30
        latency_window_size = 120
        latency_strategy = "ema"
    """)
    )
    config = load_config(toml_file)
    assert config.devices.openrgb.max_fps == 30
    assert config.devices.openrgb.latency_window_size == 120
    assert config.devices.openrgb.latency_strategy == "ema"


def test_lifx_config_defaults() -> None:
    config = AppConfig()
    assert config.devices.lifx.enabled is True
    assert config.devices.lifx.default_kelvin == 3500
    assert config.devices.lifx.max_fps == 60
    assert config.devices.lifx.latency_strategy == "ema"
    assert config.devices.lifx.echo_probe_interval_s == 2.0


def test_lifx_config_validation_bad_kelvin() -> None:
    with pytest.raises(ValueError, match="lifx default_kelvin"):
        AppConfig(devices=DevicesConfig(lifx=LIFXConfig(default_kelvin=1000)))


def test_lifx_config_validation_bad_strategy() -> None:
    with pytest.raises(ValueError, match="lifx latency_strategy"):
        AppConfig(devices=DevicesConfig(lifx=LIFXConfig(latency_strategy="invalid")))


def test_lifx_config_negative_offset_allowed() -> None:
    config = AppConfig(devices=DevicesConfig(lifx=LIFXConfig(manual_offset_ms=-10.0)))
    assert config.devices.lifx.manual_offset_ms == -10.0


def test_lifx_config_from_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("[devices.lifx]\nenabled = false\nmax_fps = 20\ndefault_kelvin = 4000\n")
    config = load_config(toml_file)
    assert config.devices.lifx.enabled is False
    assert config.devices.lifx.max_fps == 20
    assert config.devices.lifx.default_kelvin == 4000


class TestGoveeConfigValidation:
    def test_govee_defaults(self) -> None:
        config = AppConfig()
        assert config.devices.govee.enabled is True
        assert config.devices.govee.max_fps == 40
        assert config.devices.govee.latency_strategy == "ema"
        assert config.devices.govee.latency_ms == 100.0
        assert config.devices.govee.segment_override is None

    def test_govee_max_fps_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="govee max_fps"):
            AppConfig(devices=DevicesConfig(govee=GoveeConfig(max_fps=0)))

    def test_govee_invalid_strategy(self) -> None:
        with pytest.raises(ValueError, match="govee latency_strategy"):
            AppConfig(devices=DevicesConfig(govee=GoveeConfig(latency_strategy="invalid")))

    def test_govee_discovery_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="govee discovery_timeout_s"):
            AppConfig(devices=DevicesConfig(govee=GoveeConfig(discovery_timeout_s=0)))

    def test_govee_probe_interval_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="govee probe_interval_s"):
            AppConfig(devices=DevicesConfig(govee=GoveeConfig(probe_interval_s=0)))

    def test_govee_latency_ms_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="govee latency_ms"):
            AppConfig(devices=DevicesConfig(govee=GoveeConfig(latency_ms=-1)))

    def test_govee_config_from_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            "[devices.govee]\n"
            "enabled = false\nmax_fps = 30\n"
            "latency_ms = 80\nprobe_interval_s = 10.0\n"
        )
        config = load_config(toml_file)
        assert config.devices.govee.enabled is False
        assert config.devices.govee.max_fps == 30
        assert config.devices.govee.latency_ms == 80.0
        assert config.devices.govee.probe_interval_s == 10.0


def test_load_config_with_scene(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        textwrap.dedent("""\
        [scene]
        mapping = "linear"

        [scene.mapping_params]
        direction = [1.0, 0.0, 0.0]

        [[scene.devices]]
        name = "lamp"
        position = [1.0, 2.0, 0.0]
        geometry = "point"
    """)
    )
    config = load_config(toml_file)
    assert config.scene_config is not None
    assert config.scene_config["mapping"] == "linear"
    assert len(config.scene_config["devices"]) == 1


def test_load_config_without_scene(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("[engine]\nfps = 30\n")
    config = load_config(toml_file)
    assert config.scene_config is None


def test_default_config_no_scene() -> None:
    config = AppConfig()
    assert config.scene_config is None


# New tests for Task 2


def test_nested_config_defaults() -> None:
    """Nested dataclasses have correct defaults."""
    config = AppConfig()
    assert config.engine.fps == 60
    assert config.engine.max_lookahead_ms == 1000
    assert config.effect.active_effect == "beat_pulse"
    assert config.network.interface == "auto"
    assert config.network.passive_mode is True
    assert config.web.enabled is False
    assert config.web.host == "127.0.0.1"
    assert config.web.port == 8080
    assert "http://localhost:5173" in config.web.cors_origins
    assert config.devices.openrgb.enabled is True
    assert config.devices.lifx.enabled is True
    assert config.devices.govee.enabled is True


def test_nested_config_validation() -> None:
    """Validation still works on nested fields."""
    with pytest.raises(ValueError, match="engine_fps"):
        AppConfig(engine=EngineConfig(fps=0))
    with pytest.raises(ValueError, match="max_lookahead_ms"):
        AppConfig(engine=EngineConfig(max_lookahead_ms=-1))


def test_load_nested_config(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("""
[engine]
fps = 90
max_lookahead_ms = 500

[effect]
active_effect = "rainbow_wave"

[network]
interface = "eth0"

[web]
enabled = true
port = 9090

[devices.openrgb]
enabled = false
host = "10.0.0.1"

[devices.lifx]
max_fps = 30

[devices.govee]
max_fps = 20
""")
    config = load_config(p)
    assert config.engine.fps == 90
    assert config.engine.max_lookahead_ms == 500
    assert config.effect.active_effect == "rainbow_wave"
    assert config.network.interface == "eth0"
    assert config.web.enabled is True
    assert config.web.port == 9090
    assert config.devices.openrgb.enabled is False
    assert config.devices.openrgb.host == "10.0.0.1"
    assert config.devices.lifx.max_fps == 30
    assert config.devices.govee.max_fps == 20


def test_load_config_backward_compat_prodjlink(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("""
[prodjlink]
passive_mode = false
""")
    config = load_config(p)
    assert config.network.passive_mode is False


def test_load_config_backward_compat_effect_subtable(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("""
[effect]
active_effect = "rainbow_wave"

[effect.beat_pulse]
gamma = 3.5
palette = ["#ff0000", "#00ff00"]
""")
    config = load_config(p)
    assert config.effect.beat_pulse_gamma == 3.5
    assert config.effect.beat_pulse_palette == ["#ff0000", "#00ff00"]


def test_load_config_backward_compat_effect_active_key(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("""
[effect]
active = "rainbow_wave"
""")
    config = load_config(p)
    assert config.effect.active_effect == "rainbow_wave"


def test_load_config_ignores_unknown_keys(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("""
[engine]
fps = 90
future_field = true
""")
    config = load_config(p)
    assert config.engine.fps == 90


# Task 3 tests


def test_save_config_roundtrip(tmp_path: Path) -> None:
    config = AppConfig(
        engine=EngineConfig(fps=90),
        web=WebConfig(enabled=True, port=9090),
        devices=DevicesConfig(
            openrgb=OpenRGBConfig(enabled=False),
        ),
    )
    path = tmp_path / "config.toml"
    save_config(config, path)
    loaded = load_config(path)
    assert loaded.engine.fps == 90
    assert loaded.web.enabled is True
    assert loaded.web.port == 9090
    assert loaded.devices.openrgb.enabled is False
    assert loaded.devices.lifx.enabled is True


def test_save_config_atomic(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    save_config(AppConfig(), path)
    assert path.exists()
    assert not (tmp_path / "config.tmp").exists()


# Task 3 — DiscoveryConfig tests


def test_discovery_config_defaults():
    dc = DiscoveryConfig()
    assert dc.broadcast_interval_s == 30.0
    assert dc.unicast_concurrency == 50
    assert dc.unicast_timeout_s == 0.5
    assert dc.subnet_mask == 24


def test_app_config_has_discovery():
    config = AppConfig()
    assert isinstance(config.discovery, DiscoveryConfig)
    assert config.discovery.broadcast_interval_s == 30.0


def test_engine_config_unassigned_device_mode_default():
    cfg = EngineConfig()
    assert cfg.unassigned_device_mode == "default_effect"


def test_engine_config_unassigned_device_mode_idle():
    cfg = EngineConfig(unassigned_device_mode="idle")
    assert cfg.unassigned_device_mode == "idle"
