"""The light-sync spec's §8: the device settings load from state.db, after a run-once step
drops the rows saved before any start applied them, and a backup from before that step
restores none of its own (the owner's decision: the plan's ruling 22)."""

from __future__ import annotations

import tomllib
from typing import Any

import pytest
from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.main import _load_config_from_db, _reset_device_settings_once
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import DEVICES_CONFIG_RESET, export_toml, import_toml


async def _save(db: StateDB, section: str, **settings: str) -> None:
    """Settings as state.db keeps them: JSON text."""
    for key, value in settings.items():
        await db.save_config_key(section, key, value)


async def test_device_settings_load_from_the_database(db: StateDB) -> None:
    await _save(db, "engine", fps="60")
    await _save(db, "devices.govee", probe_interval_s="0.8", max_fps="20")
    await _save(db, "devices.lifx", latency_ms="12.0")
    await _save(db, "devices.openrgb", latency_strategy='"static"')

    config = await _load_config_from_db(db)

    assert config is not None
    govee = config.devices.govee
    assert (govee.probe_interval_s, govee.max_fps, govee.latency_ms) == (0.8, 20, 100.0)
    assert config.devices.lifx.latency_ms == 12.0
    assert config.devices.openrgb.latency_strategy == "static"


async def test_device_settings_alone_are_a_config(db: StateDB) -> None:
    """A config.toml with only device tables, migrated into state.db, still applies."""
    await _save(db, "devices.govee", max_fps="20")
    config = await _load_config_from_db(db)
    assert config is not None and config.devices.govee.max_fps == 20


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("probe_interval_s", "0", "govee probe_interval_s must be positive"),
        ("max_fps", '"fast"', "not supported between instances"),
    ],
)
async def test_device_settings_the_config_refuses_leave_the_lights_on_their_defaults(
    db: StateDB, key: str, value: str, reason: str
) -> None:
    await _save(db, "engine", fps="42")
    await _save(db, "devices.govee", **{key: value})
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        config = await _load_config_from_db(db)
    finally:
        logger.remove(sink)

    assert config is not None
    assert config.devices == AppConfig().devices
    assert config.engine.fps == 42  # the rest loads as before
    [warning] = records
    assert warning["message"].startswith("Saved device settings refused")
    assert reason in warning["message"]


async def test_the_old_device_settings_go_once_and_a_setting_saved_after_stays(
    db: StateDB,
) -> None:
    await _save(db, "engine", fps="60")
    await _save(db, "devices.govee", max_fps="40", latency_strategy='"ema"')
    await _save(db, "devices.lifx", latency_ms="50")
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        await _reset_device_settings_once(db)
    finally:
        logger.remove(sink)

    assert await db.load_all_config() == {("engine", "fps"): 60}
    assert await db.has_mark(DEVICES_CONFIG_RESET)
    assert [record["message"] for record in records] == [
        "Dropped device settings that never applied: devices.govee.latency_strategy, "
        "devices.govee.max_fps, devices.lifx.latency_ms"
    ]

    await _save(db, "devices.govee", max_fps="20")  # saved after the step
    await _reset_device_settings_once(db)  # the next start

    assert await db.load_all_config() == {("engine", "fps"): 60, ("devices.govee", "max_fps"): 20}


async def test_the_step_logs_nothing_when_no_device_setting_is_saved(db: StateDB) -> None:
    await _save(db, "engine", fps="60")
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        await _reset_device_settings_once(db)
    finally:
        logger.remove(sink)

    assert records == []
    assert await db.has_mark(DEVICES_CONFIG_RESET)
    assert await db.load_all_config() == {("engine", "fps"): 60}


# A backup exported before light sync: its devices.* rows are the old ones, and no [marks]
OLD_BACKUP = """\
[config.engine]
fps = 50

[config."devices.govee"]
max_fps = 40
latency_strategy = "ema"

[config."devices.lifx"]
latency_ms = 50
"""


async def test_a_backup_from_before_light_sync_restores_no_device_setting(db: StateDB) -> None:
    await _reset_device_settings_once(db)  # the app that restores has run the step
    await _save(db, "devices.govee", max_fps="20")  # and saved a setting since
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        await import_toml(db, OLD_BACKUP)
    finally:
        logger.remove(sink)

    assert await db.load_all_config() == {("engine", "fps"): 50, ("devices.govee", "max_fps"): 20}
    assert [record["message"] for record in records] == [
        "Dropped a backup's device settings from before light sync: "
        "devices.govee.latency_strategy, devices.govee.max_fps, devices.lifx.latency_ms"
    ]
    config = await _load_config_from_db(db)
    assert config is not None
    assert (config.devices.govee.latency_strategy, config.devices.lifx.latency_ms) == (
        "windowed_median",
        10.0,
    )


async def test_a_backup_from_after_light_sync_restores_its_device_settings(db: StateDB) -> None:
    await _reset_device_settings_once(db)
    await _save(db, "devices.govee", max_fps="20")
    backup = await export_toml(db)
    assert tomllib.loads(backup).get("marks") == {DEVICES_CONFIG_RESET: True}
    await _save(db, "devices.govee", max_fps="25")  # changed after the backup

    await import_toml(db, backup)

    config = await _load_config_from_db(db)
    assert config is not None and config.devices.govee.max_fps == 20
