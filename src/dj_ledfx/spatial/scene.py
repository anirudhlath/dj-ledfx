from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.spatial.geometry import (
    DeviceGeometry,
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
    expand_positions,
)

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter


@dataclass(frozen=True, slots=True)
class DevicePlacement:
    """A device placed in 3D space."""

    device_id: str
    position: tuple[float, float, float]
    geometry: DeviceGeometry
    led_count: int


class SceneModel:
    """Central registry of device placements with cached LED positions."""

    def __init__(self, placements: dict[str, DevicePlacement]) -> None:
        self.placements = placements
        self._position_cache: dict[str, NDArray[np.float64]] = {}

    def get_led_positions(self, device_id: str) -> NDArray[np.float64]:
        """Returns (N, 3) world-space positions, cached after first call."""
        if device_id in self._position_cache:
            return self._position_cache[device_id]
        placement = self.placements[device_id]
        positions = expand_positions(placement.geometry, placement.position, placement.led_count)
        self._position_cache[device_id] = positions
        return positions

    def add_placement(self, placement: DevicePlacement) -> None:
        """Add a device to the scene. Raises ValueError if device_id already exists."""
        if placement.device_id in self.placements:
            raise ValueError(f"Device '{placement.device_id}' already exists in scene")
        self.placements[placement.device_id] = placement

    def update_placement(
        self,
        device_id: str,
        position: tuple[float, float, float] | None = None,
        geometry: DeviceGeometry | None = None,
    ) -> None:
        """Update an existing placement. Raises KeyError if device_id not found."""
        old = self.placements[device_id]  # raises KeyError if missing
        self.placements[device_id] = DevicePlacement(
            device_id=device_id,
            position=position if position is not None else old.position,
            geometry=geometry if geometry is not None else old.geometry,
            led_count=old.led_count,
        )
        self._position_cache.pop(device_id, None)

    def remove_placement(self, device_id: str) -> None:
        """Remove a device from the scene. Raises KeyError if device_id not found."""
        del self.placements[device_id]  # raises KeyError if missing
        self._position_cache.pop(device_id, None)

    def get_bounds(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Returns (min_xyz, max_xyz) bounding box of all LED positions."""
        all_positions: list[NDArray[np.float64]] = []
        for device_id in self.placements:
            all_positions.append(self.get_led_positions(device_id))
        if not all_positions:
            zeros = np.zeros(3, dtype=np.float64)
            return zeros, zeros
        combined = np.concatenate(all_positions)
        return combined.min(axis=0), combined.max(axis=0)

    @staticmethod
    def from_config(
        scene_config: dict[str, Any],
        adapters: list[DeviceAdapter],
    ) -> SceneModel:
        """Build SceneModel from TOML config + discovered adapters."""
        adapter_lookup: dict[str, DeviceAdapter] = {}
        for adapter in adapters:
            adapter_lookup[adapter.device_info.name] = adapter

        placements: dict[str, DevicePlacement] = {}
        for entry in scene_config.get("devices", []):
            name = entry.get("name", "")

            # Resolve adapter: exact match first, then backend-prefix strip
            resolved: DeviceAdapter | None = adapter_lookup.get(name)
            if resolved is None and ":" in name:
                raw_name = name.split(":", 1)[1]
                resolved = adapter_lookup.get(raw_name)
            if resolved is None:
                logger.warning("Scene device '{}' not found in discovered devices, skipping", name)
                continue
            adapter = resolved

            # Validate position
            pos = entry.get("position", [])
            if not isinstance(pos, list) or len(pos) != 3:
                logger.warning("Scene device '{}' has invalid position, skipping", name)
                continue
            position = (float(pos[0]), float(pos[1]), float(pos[2]))

            # Resolve geometry
            geometry = _resolve_geometry(entry, adapter)
            if geometry is None:
                continue

            device_id = adapter.device_info.name
            placements[device_id] = DevicePlacement(
                device_id=device_id,
                position=position,
                geometry=geometry,
                led_count=adapter.led_count,
            )

        logger.info("Scene loaded with {} devices", len(placements))
        return SceneModel(placements=placements)


def _resolve_geometry(
    entry: dict[str, Any],
    adapter: DeviceAdapter,
) -> DeviceGeometry | None:
    """Resolve geometry: config > adapter > fallback."""
    geo_type = entry.get("geometry")

    if geo_type == "point":
        return PointGeometry()

    if geo_type == "strip":
        direction = entry.get("direction", [1.0, 0.0, 0.0])
        if not isinstance(direction, list) or len(direction) != 3:
            logger.warning(
                "Scene device '{}' has invalid direction, skipping",
                entry.get("name"),
            )
            return None
        length = float(entry.get("length", 1.0))
        if "length" not in entry:
            logger.warning(
                "Scene device '{}': strip missing length, defaulting to 1.0m",
                entry.get("name"),
            )
        return StripGeometry(
            direction=(float(direction[0]), float(direction[1]), float(direction[2])),
            length=length,
        )

    if geo_type == "matrix":
        if adapter.geometry is not None and isinstance(adapter.geometry, MatrixGeometry):
            return adapter.geometry
        logger.warning(
            "Scene device '{}': matrix geometry requested but adapter has no tile layout, "
            "falling back to strip",
            entry.get("name"),
        )
        return StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)

    # No geometry specified in config — try adapter, then fallback
    if geo_type is None:
        if adapter.geometry is not None:
            return adapter.geometry
        if adapter.led_count <= 1:
            return PointGeometry()
        return StripGeometry(direction=(1.0, 0.0, 0.0), length=1.0)

    logger.warning("Scene device '{}': unknown geometry type '{}'", entry.get("name"), geo_type)
    return None
