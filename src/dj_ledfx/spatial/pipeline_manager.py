"""PipelineManager — orchestrates multi-pipeline lifecycle."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from dj_ledfx.config import AppConfig
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.events import EventBus
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import StripGeometry
from dj_ledfx.spatial.mapping import mapping_from_config
from dj_ledfx.spatial.pipeline import ScenePipeline
from dj_ledfx.spatial.scene import DevicePlacement, SceneModel

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
    from dj_ledfx.effects.engine import EffectEngine
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.scheduling.scheduler import LookaheadScheduler


class PipelineManager:
    """Orchestrates ScenePipeline lifecycle between DB/web and engine/scheduler."""

    def __init__(
        self,
        device_manager: DeviceManager,
        state_db: StateDB,
        event_bus: EventBus,
        config: AppConfig,
    ) -> None:
        self._device_manager = device_manager
        self._state_db = state_db
        self._event_bus = event_bus
        self._config = config

        self._pipelines: dict[str, ScenePipeline] = {}
        self._default_pipeline: ScenePipeline | None = None

        # Shared mode state
        self._shared_deck: EffectDeck | None = None
        self._shared_buffer: RingBuffer | None = None

        # Late-bound references
        self._engine: EffectEngine | None = None
        self._scheduler: LookaheadScheduler | None = None

    def bind(self, engine: EffectEngine, scheduler: LookaheadScheduler) -> None:
        """Bind engine and scheduler after they are created."""
        self._engine = engine
        self._scheduler = scheduler

    def _require_bound(self) -> None:
        if self._engine is None or self._scheduler is None:
            msg = "PipelineManager.bind() must be called before runtime operations"
            raise RuntimeError(msg)

    # ── Properties ──────────────────────────────────────────────

    @property
    def all_pipelines(self) -> list[ScenePipeline]:
        """All pipelines including default."""
        pipelines = list(self._pipelines.values())
        if self._default_pipeline is not None:
            pipelines.append(self._default_pipeline)
        return pipelines

    @property
    def default_deck(self) -> EffectDeck | None:
        """The default pipeline's effect deck (for backward compat)."""
        if self._default_pipeline is not None:
            return self._default_pipeline.deck
        return None

    @property
    def default_pipeline(self) -> ScenePipeline | None:
        return self._default_pipeline

    # ── Startup ─────────────────────────────────────────────────

    async def load_active_scenes(self) -> None:
        """Load all active scenes from DB and build pipelines."""
        scenes = await self._state_db.load_scenes()
        active_scenes = [s for s in scenes if s.get("is_active")]

        for scene_row in active_scenes:
            placements = await self._state_db.load_scene_placements(scene_row["id"])
            pipeline = self._build_pipeline(scene_row, placements)
            if pipeline is not None:
                self._pipelines[scene_row["id"]] = pipeline

        self._rebuild_default_pipeline()

    # ── Runtime lifecycle ───────────────────────────────────────

    async def activate_scene(self, scene_id: str) -> ScenePipeline:
        """Build and register a pipeline for a newly activated scene."""
        self._require_bound()
        assert self._engine is not None  # for type narrowing
        assert self._scheduler is not None

        scene_row = await self._state_db.load_scene_by_id(scene_id)
        if scene_row is None:
            msg = f"Scene {scene_id} not found"
            raise ValueError(msg)

        placements = await self._state_db.load_scene_placements(scene_id)
        pipeline = self._build_pipeline(scene_row, placements)
        if pipeline is None:
            msg = f"Could not build pipeline for scene {scene_id}"
            raise ValueError(msg)

        self._pipelines[scene_id] = pipeline
        self._engine.add_pipeline(pipeline)

        # Assign devices to this pipeline in the scheduler
        for managed in pipeline.devices:
            sid = managed.adapter.device_info.effective_id
            if sid in self._scheduler._device_state:
                self._scheduler.set_device_pipeline(sid, pipeline)
            else:
                self._scheduler.add_device(managed, pipeline=pipeline)

        self._rebuild_default_pipeline()
        logger.info("Activated scene pipeline: {} ({} devices)", scene_id, len(pipeline.devices))
        return pipeline

    async def deactivate_scene(self, scene_id: str) -> None:
        """Tear down and unregister a scene's pipeline."""
        self._require_bound()
        assert self._engine is not None
        assert self._scheduler is not None

        pipeline = self._pipelines.pop(scene_id, None)
        if pipeline is None:
            return

        self._engine.remove_pipeline(scene_id)
        self._scheduler.remove_pipeline_refs(scene_id)

        # Clean up shared mode state if this was the last shared scene
        if self._shared_buffer is not None and pipeline.ring_buffer is self._shared_buffer:
            has_shared = any(
                p.ring_buffer is self._shared_buffer for p in self._pipelines.values()
            )
            if not has_shared:
                self._shared_deck = None
                self._shared_buffer = None

        self._rebuild_default_pipeline()
        logger.info("Deactivated scene pipeline: {}", scene_id)

    # ── Effect control ──────────────────────────────────────────

    def set_scene_effect(self, scene_id: str, effect_name: str, params: dict[str, Any]) -> None:
        """Set the effect for a scene's pipeline."""
        pipeline = self._pipelines.get(scene_id)
        if pipeline is None:
            msg = f"No active pipeline for scene {scene_id}"
            raise ValueError(msg)
        pipeline.deck.apply_update(effect_name, params)
        import asyncio

        asyncio.create_task(
            self._state_db.save_scene_effect_state(scene_id, effect_name, json.dumps(params))
        )

    def get_scene_effect(self, scene_id: str) -> dict[str, Any]:
        """Get the current effect info for a scene's pipeline."""
        pipeline = self._pipelines.get(scene_id)
        if pipeline is None:
            msg = f"No active pipeline for scene {scene_id}"
            raise ValueError(msg)
        return {
            "effect_name": pipeline.deck.effect_name,
            "params": pipeline.deck.effect.get_params(),
        }

    # ── Device assignment ───────────────────────────────────────

    def reassign_devices(self) -> None:
        """Recompute device assignments across all pipelines."""
        if self._scheduler is None:
            return

        assigned_ids: set[str] = set()
        for pipeline in self._pipelines.values():
            for managed in pipeline.devices:
                sid = managed.adapter.device_info.effective_id
                assigned_ids.add(sid)
                if sid in self._scheduler._device_state:
                    self._scheduler.set_device_pipeline(sid, pipeline)
                else:
                    self._scheduler.add_device(managed, pipeline=pipeline)

        self._rebuild_default_pipeline()

    # ── Pipeline construction ───────────────────────────────────

    def _build_pipeline(
        self, scene_row: dict[str, Any], placements: list[dict[str, Any]]
    ) -> ScenePipeline | None:
        """Build a ScenePipeline from DB scene data and placements."""
        scene_id = scene_row["id"]
        effect_mode = scene_row.get("effect_mode", "independent")

        # Resolve devices from placements
        devices: list[ManagedDevice] = []
        scene_placements: dict[str, DevicePlacement] = {}
        for p in placements:
            managed = self._device_manager.get_by_stable_id(p["device_id"])
            if managed is None:
                continue
            devices.append(managed)
            geometry = StripGeometry(
                direction=(
                    p.get("direction_x", 1.0),
                    p.get("direction_y", 0.0),
                    p.get("direction_z", 0.0),
                ),
                length=p.get("length", 1.0),
            )
            placement = DevicePlacement(
                device_id=p["device_id"],
                position=(
                    p.get("position_x", 0.0),
                    p.get("position_y", 0.0),
                    p.get("position_z", 0.0),
                ),
                geometry=geometry,
                led_count=managed.adapter.device_info.led_count,
            )
            scene_placements[p["device_id"]] = placement

        led_count = max(
            (d.adapter.device_info.led_count for d in devices),
            default=self._device_manager.max_led_count or 60,
        )

        # Build spatial components
        scene_model = SceneModel(scene_placements)
        mapping_config = {
            "mapping": scene_row.get("mapping_type", "linear"),
            "mapping_params": json.loads(scene_row.get("mapping_params", "{}") or "{}"),
        }
        mapping = mapping_from_config(mapping_config)
        compositor: SpatialCompositor | None = None
        if scene_placements:
            compositor = SpatialCompositor(scene_model, mapping)

        # Build effect deck and ring buffer based on mode
        if effect_mode == "shared":
            deck, ring_buffer = self._get_or_create_shared(led_count)
        else:
            deck = self._build_deck_for_scene(scene_id)
            ring_buffer = RingBuffer(
                capacity=self._config.engine.fps,
                led_count=led_count,
            )

        return ScenePipeline(
            scene_id=scene_id,
            deck=deck,
            ring_buffer=ring_buffer,
            compositor=compositor,
            mapping=mapping,
            devices=devices,
            led_count=led_count,
        )

    def _get_or_create_shared(self, led_count: int) -> tuple[EffectDeck, RingBuffer]:
        """Get or create the shared deck and buffer for shared-mode scenes."""
        if self._shared_deck is None:
            self._shared_deck = EffectDeck(BeatPulse())
        if self._shared_buffer is None:
            self._shared_buffer = RingBuffer(
                capacity=self._config.engine.fps,
                led_count=led_count,
            )
        elif self._shared_buffer._led_count < led_count:
            old_buffer = self._shared_buffer
            new_buffer = RingBuffer(
                capacity=self._config.engine.fps,
                led_count=led_count,
            )
            self._shared_buffer = new_buffer
            for p in self._pipelines.values():
                if p.ring_buffer is old_buffer:
                    p.ring_buffer = new_buffer
                    p.led_count = led_count
        return self._shared_deck, self._shared_buffer

    def _build_deck_for_scene(self, scene_id: str) -> EffectDeck:
        """Build an EffectDeck for an independent scene, restoring saved state."""
        return EffectDeck(BeatPulse())

    def _rebuild_default_pipeline(self) -> None:
        """Create or update the default pipeline for unassigned devices."""
        if self._config.engine.unassigned_device_mode == "idle":
            if self._default_pipeline is not None:
                if self._engine is not None:
                    self._engine.remove_pipeline("__default__")
                if self._scheduler is not None:
                    for managed in self._default_pipeline.devices:
                        sid = managed.adapter.device_info.effective_id
                        self._scheduler.remove_device(sid)
                self._default_pipeline = None
            return

        # Find unassigned devices
        assigned_ids: set[str] = set()
        for pipeline in self._pipelines.values():
            for managed in pipeline.devices:
                assigned_ids.add(managed.adapter.device_info.effective_id)

        unassigned = [
            d
            for d in self._device_manager.devices
            if d.adapter.device_info.effective_id not in assigned_ids
        ]

        led_count = max(
            (d.adapter.device_info.led_count for d in unassigned),
            default=self._device_manager.max_led_count or 60,
        )

        if self._default_pipeline is None:
            deck = EffectDeck(BeatPulse())
            ring_buffer = RingBuffer(
                capacity=self._config.engine.fps,
                led_count=led_count,
            )
            self._default_pipeline = ScenePipeline(
                scene_id="__default__",
                deck=deck,
                ring_buffer=ring_buffer,
                compositor=None,
                mapping=None,
                devices=unassigned,
                led_count=led_count,
            )
        else:
            self._default_pipeline.devices = unassigned

        # Update scheduler: assign unassigned devices to default pipeline
        if self._scheduler is not None:
            for managed in unassigned:
                sid = managed.adapter.device_info.effective_id
                if sid in self._scheduler._device_state:
                    self._scheduler.set_device_pipeline(sid, self._default_pipeline)
