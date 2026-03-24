"""Tests for PipelineManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from dj_ledfx.config import AppConfig, EngineConfig
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.spatial.pipeline_manager import PipelineManager
from dj_ledfx.types import DeviceInfo
from tests.conftest import MockDeviceAdapter


class _StableIdAdapter(MockDeviceAdapter):
    """MockDeviceAdapter subclass with stable_id support (avoids class-level property pollution)."""

    def __init__(self, name: str, led_count: int, stable_id: str) -> None:
        super().__init__(name=name, led_count=led_count)
        self._stable_id = stable_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._name, device_type="mock", led_count=self._led_count,
            address="mock", stable_id=self._stable_id,
        )


def _make_managed(name: str, led_count: int = 10, stable_id: str | None = None) -> ManagedDevice:
    if stable_id:
        adapter = _StableIdAdapter(name=name, led_count=led_count, stable_id=stable_id)
    else:
        adapter = MockDeviceAdapter(name=name, led_count=led_count)
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    return ManagedDevice(adapter=adapter, tracker=tracker)


def _make_db_mock(scenes=None, placements=None, effect_state=None):
    """Create a mock StateDB with scene data."""
    db = AsyncMock()
    db.load_scenes = AsyncMock(return_value=scenes or [])
    db.load_scene_placements = AsyncMock(return_value=placements or [])
    db.load_scene_by_id = AsyncMock(return_value=None)
    db.load_scene_effect_state = AsyncMock(return_value=effect_state)
    db.save_scene_effect_state = AsyncMock()
    db.set_scene_active = AsyncMock()
    db.set_scene_inactive = AsyncMock()
    return db


def _make_manager(
    config: AppConfig | None = None,
    scenes=None,
    placements=None,
    devices: list[ManagedDevice] | None = None,
):
    """Create PipelineManager with mocked dependencies."""
    config = config or AppConfig()
    event_bus = EventBus()
    device_manager = DeviceManager(event_bus)
    for d in (devices or []):
        device_manager._devices.append(d)
    db = _make_db_mock(scenes=scenes, placements=placements)
    pm = PipelineManager(
        device_manager=device_manager,
        state_db=db,
        event_bus=event_bus,
        config=config,
    )
    return pm, db, device_manager


class TestPipelineManagerConstruction:
    def test_initial_state(self):
        pm, _, _ = _make_manager()
        assert pm.all_pipelines == []
        assert pm.default_deck is None

    def test_not_bound_raises_on_activate(self):
        pm, _, _ = _make_manager()
        with pytest.raises(RuntimeError, match="bind"):
            asyncio.run(pm.activate_scene("test"))


class TestLoadActiveScenes:
    async def test_no_active_scenes_creates_default_pipeline(self):
        pm, db, _ = _make_manager(
            devices=[_make_managed("Dev1", stable_id="dev1")],
        )
        db.load_scenes.return_value = []

        await pm.load_active_scenes()

        assert len(pm.all_pipelines) == 1
        assert pm.all_pipelines[0].scene_id == "__default__"
        assert pm.default_deck is not None

    async def test_no_active_scenes_idle_mode_no_default(self):
        config = AppConfig(engine=EngineConfig(unassigned_device_mode="idle"))
        pm, db, _ = _make_manager(config=config)
        db.load_scenes.return_value = []

        await pm.load_active_scenes()

        assert len(pm.all_pipelines) == 0
        assert pm.default_deck is None

    async def test_loads_active_independent_scene(self):
        scenes = [{"id": "s1", "name": "Scene1", "mapping_type": "linear",
                    "mapping_params": "{}", "effect_mode": "independent",
                    "effect_source": None, "is_active": 1}]
        placements = [{"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
                        "position_z": 0.0, "geometry_type": "strip",
                        "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                        "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}]
        managed = _make_managed("Dev1", led_count=20, stable_id="dev1")
        pm, db, _ = _make_manager(scenes=scenes, placements=placements, devices=[managed])
        db.load_scene_placements.return_value = placements

        await pm.load_active_scenes()

        scene_pipelines = [p for p in pm.all_pipelines if p.scene_id != "__default__"]
        assert len(scene_pipelines) == 1
        assert scene_pipelines[0].scene_id == "s1"
        assert scene_pipelines[0].led_count == 20
        assert scene_pipelines[0].compositor is not None


class TestActivateDeactivate:
    async def test_activate_scene_creates_pipeline(self):
        scenes = [{"id": "s1", "name": "Scene1", "mapping_type": "linear",
                    "mapping_params": "{}", "effect_mode": "independent",
                    "effect_source": None, "is_active": 0}]
        managed = _make_managed("Dev1", led_count=10, stable_id="dev1")
        pm, db, _ = _make_manager(devices=[managed])
        db.load_scene_by_id.return_value = scenes[0]
        db.load_scene_placements.return_value = [
            {"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
             "position_z": 0.0, "geometry_type": "strip",
             "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
             "length": 1.0, "width": 0.0, "rows": 1, "cols": 1},
        ]

        engine = MagicMock()
        scheduler = MagicMock()
        scheduler._device_state = {}
        pm.bind(engine, scheduler)

        pipeline = await pm.activate_scene("s1")

        assert pipeline.scene_id == "s1"
        assert len(pipeline.devices) == 1
        engine.add_pipeline.assert_called_once_with(pipeline)
        scheduler.add_device.assert_called_once()

    async def test_deactivate_scene_removes_pipeline(self):
        managed = _make_managed("Dev1", led_count=10, stable_id="dev1")
        pm, db, _ = _make_manager(devices=[managed])
        db.load_scene_by_id.return_value = {
            "id": "s1", "name": "Scene1", "mapping_type": "linear",
            "mapping_params": "{}", "effect_mode": "independent",
            "effect_source": None, "is_active": 1,
        }
        db.load_scene_placements.return_value = [
            {"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
             "position_z": 0.0, "geometry_type": "strip",
             "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
             "length": 1.0, "width": 0.0, "rows": 1, "cols": 1},
        ]

        engine = MagicMock()
        scheduler = MagicMock()
        scheduler._device_state = {}
        pm.bind(engine, scheduler)

        await pm.activate_scene("s1")
        assert "s1" in pm._pipelines

        await pm.deactivate_scene("s1")
        assert "s1" not in pm._pipelines
        engine.remove_pipeline.assert_called_once_with("s1")
        scheduler.remove_pipeline_refs.assert_called_once_with("s1")


class TestEffectControl:
    async def test_set_scene_effect(self):
        scenes = [{"id": "s1", "name": "Scene1", "mapping_type": "linear",
                    "mapping_params": "{}", "effect_mode": "independent",
                    "effect_source": None, "is_active": 1}]
        managed = _make_managed("Dev1", led_count=10, stable_id="dev1")
        pm, db, _ = _make_manager(
            scenes=scenes, devices=[managed],
            placements=[{"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
                          "position_z": 0.0, "geometry_type": "strip",
                          "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                          "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}],
        )
        db.load_scene_placements.return_value = pm._state_db.load_scene_placements.return_value

        await pm.load_active_scenes()

        pm.set_scene_effect("s1", "rainbow_wave", {})
        info = pm.get_scene_effect("s1")
        assert info["effect_name"] == "rainbow_wave"

    def test_set_effect_no_active_pipeline_raises(self):
        pm, _, _ = _make_manager()
        with pytest.raises(ValueError, match="No active pipeline"):
            pm.set_scene_effect("nonexistent", "beat_pulse", {})


class TestSharedMode:
    async def test_shared_scenes_use_same_deck_and_buffer(self):
        scenes = [
            {"id": "s1", "name": "Scene1", "mapping_type": "linear",
             "mapping_params": "{}", "effect_mode": "shared",
             "effect_source": None, "is_active": 1},
            {"id": "s2", "name": "Scene2", "mapping_type": "linear",
             "mapping_params": "{}", "effect_mode": "shared",
             "effect_source": None, "is_active": 1},
        ]
        d1 = _make_managed("Dev1", led_count=10, stable_id="dev1")
        d2 = _make_managed("Dev2", led_count=10, stable_id="dev2")
        pm, db, _ = _make_manager(scenes=scenes, devices=[d1, d2])

        async def load_placements(scene_id):
            if scene_id == "s1":
                return [{"device_id": "dev1", "position_x": 0.0, "position_y": 0.0,
                          "position_z": 0.0, "geometry_type": "strip",
                          "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                          "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}]
            return [{"device_id": "dev2", "position_x": 1.0, "position_y": 0.0,
                      "position_z": 0.0, "geometry_type": "strip",
                      "direction_x": 1.0, "direction_y": 0.0, "direction_z": 0.0,
                      "length": 1.0, "width": 0.0, "rows": 1, "cols": 1}]
        db.load_scene_placements = AsyncMock(side_effect=load_placements)

        await pm.load_active_scenes()

        p1 = pm._pipelines["s1"]
        p2 = pm._pipelines["s2"]
        assert p1.deck is p2.deck  # same shared deck
        assert p1.ring_buffer is p2.ring_buffer  # same shared buffer
        assert p1.compositor is not p2.compositor  # different compositors
