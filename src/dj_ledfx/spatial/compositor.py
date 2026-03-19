from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.spatial.mapping import SpatialMapping
    from dj_ledfx.spatial.scene import SceneModel


class SpatialCompositor:
    """Maps 1D effect strips onto 3D device positions via cached indices.

    IMPORTANT: Mapping is called ONCE with ALL LED positions from ALL devices
    combined, ensuring global normalization. The results are then split back
    per-device. This means a PointGeometry device at x=0 gets a different
    strip index than one at x=10, even though each has only 1 LED.
    """

    def __init__(self, scene: SceneModel, mapping: SpatialMapping) -> None:
        self._strip_indices: dict[str, NDArray[np.float64]] = {}

        # Collect all positions globally, map once, then distribute
        device_ids: list[str] = []
        position_arrays: list[NDArray[np.float64]] = []
        counts: list[int] = []

        for device_id in scene.placements:
            positions = scene.get_led_positions(device_id)
            device_ids.append(device_id)
            position_arrays.append(positions)
            counts.append(len(positions))

        if not position_arrays:
            return

        all_positions = np.concatenate(position_arrays)
        all_indices = mapping.map_positions(all_positions)

        # Split results back per-device
        offset = 0
        for device_id, count in zip(device_ids, counts, strict=True):
            self._strip_indices[device_id] = all_indices[offset : offset + count]
            offset += count

    def get_strip_indices(self) -> dict[str, NDArray[np.float64]]:
        """Return a copy of the per-device strip index mapping."""
        return dict(self._strip_indices)

    def composite(
        self,
        effect_strip: NDArray[np.uint8],
        device_id: str,
    ) -> NDArray[np.uint8] | None:
        """Sample effect strip for a device. Returns None if device not in scene."""
        indices = self._strip_indices.get(device_id)
        if indices is None:
            return None
        strip_len = len(effect_strip)
        pixel_idx = (indices * (strip_len - 1)).astype(np.intp)
        np.clip(pixel_idx, 0, strip_len - 1, out=pixel_idx)
        return effect_strip[pixel_idx]
