"""ScenePipeline — bundles per-scene rendering state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_ledfx.devices.manager import ManagedDevice
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import RingBuffer
    from dj_ledfx.spatial.compositor import SpatialCompositor
    from dj_ledfx.spatial.mapping import SpatialMapping


@dataclass
class ScenePipeline:
    """One per active scene. Bundles all rendering state."""

    scene_id: str
    deck: EffectDeck
    ring_buffer: RingBuffer
    compositor: SpatialCompositor | None
    mapping: SpatialMapping | None
    devices: list[ManagedDevice]
    led_count: int
