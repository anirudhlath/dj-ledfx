import textwrap
from pathlib import Path

import pytest

from dj_ledfx.config import AppConfig, load_config


def test_default_config() -> None:
    config = AppConfig()
    assert config.network_interface == "auto"
    assert config.engine_fps == 60
    assert config.max_lookahead_ms == 1000
    assert config.active_effect == "beat_pulse"
    assert config.openrgb_host == "127.0.0.1"
    assert config.openrgb_port == 6742


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
    assert config.network_interface == "eth0"
    assert config.engine_fps == 30
    assert config.max_lookahead_ms == 500
    assert config.openrgb_host == "192.168.1.100"
    assert config.beat_pulse_gamma == 3.0
    assert config.openrgb_latency_ms == 20


def test_load_config_missing_file_returns_defaults() -> None:
    config = load_config(Path("/nonexistent/config.toml"))
    assert config.engine_fps == 60


def test_config_validation_bad_fps() -> None:
    with pytest.raises(ValueError, match="fps"):
        AppConfig(engine_fps=0)


def test_config_validation_bad_lookahead() -> None:
    with pytest.raises(ValueError, match="max_lookahead_ms"):
        AppConfig(max_lookahead_ms=-1)


def test_default_config_new_fields() -> None:
    config = AppConfig()
    assert config.openrgb_max_fps == 60
    assert config.openrgb_latency_window_size == 60
    assert config.openrgb_latency_strategy == "windowed_mean"


def test_config_validation_bad_max_fps() -> None:
    with pytest.raises(ValueError, match="openrgb_max_fps"):
        AppConfig(openrgb_max_fps=0)


def test_config_validation_bad_window_size() -> None:
    with pytest.raises(ValueError, match="openrgb_latency_window_size"):
        AppConfig(openrgb_latency_window_size=0)


def test_config_validation_bad_strategy() -> None:
    with pytest.raises(ValueError, match="openrgb_latency_strategy"):
        AppConfig(openrgb_latency_strategy="invalid")


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
    assert config.openrgb_max_fps == 30
    assert config.openrgb_latency_window_size == 120
    assert config.openrgb_latency_strategy == "ema"
