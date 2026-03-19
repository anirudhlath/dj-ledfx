from __future__ import annotations

from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray


class SpatialMapping(Protocol):
    """Maps 3D positions to [0.0, 1.0] strip indices.

    Normalization is relative to the input set: pass ALL positions together
    for global normalization. The SpatialCompositor does this automatically.
    """

    def map_positions(
        self,
        positions: NDArray[np.float64],
    ) -> NDArray[np.float64]: ...


class LinearMapping:
    """Projects positions onto a direction vector."""

    def __init__(
        self,
        direction: tuple[float, float, float] = (1.0, 0.0, 0.0),
        origin: tuple[float, float, float] | None = None,
    ) -> None:
        d = np.array(direction, dtype=np.float64)
        mag = np.linalg.norm(d)
        if mag < 1e-9:
            msg = "LinearMapping direction must be non-zero"
            raise ValueError(msg)
        self._direction = d / mag
        self._origin = np.array(origin, dtype=np.float64) if origin is not None else None

    def map_positions(
        self,
        positions: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        if self._origin is not None:
            relative = positions - self._origin
        else:
            relative = positions
        projections = relative @ self._direction
        p_min = projections.min()
        p_max = projections.max()
        span = p_max - p_min
        if span < 1e-12:
            return np.zeros(len(positions), dtype=np.float64)
        result = (projections - p_min) / span
        return cast(NDArray[np.float64], np.clip(result, 0.0, 1.0))


def mapping_from_config(
    scene_config: dict[str, object],
) -> LinearMapping | RadialMapping:
    """Build a mapping instance from scene config dict."""
    mapping_name = scene_config.get("mapping", "linear")
    mapping_params: dict[str, object] = scene_config.get("mapping_params", {})  # type: ignore[assignment]
    if mapping_name == "radial":
        center = mapping_params.get("center", [0.0, 0.0, 0.0])
        max_radius = mapping_params.get("max_radius")
        return RadialMapping(
            center=(float(center[0]), float(center[1]), float(center[2])),  # type: ignore[index]
            max_radius=float(max_radius) if max_radius is not None else None,
        )
    direction = mapping_params.get("direction", [1.0, 0.0, 0.0])
    origin = mapping_params.get("origin")
    origin_tuple = (
        (float(origin[0]), float(origin[1]), float(origin[2])) if origin else None  # type: ignore[index]
    )
    return LinearMapping(
        direction=(float(direction[0]), float(direction[1]), float(direction[2])),  # type: ignore[index]
        origin=origin_tuple,
    )


class RadialMapping:
    """Maps positions by distance from a center point."""

    def __init__(
        self,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        max_radius: float | None = None,
    ) -> None:
        self._center = np.array(center, dtype=np.float64)
        self._max_radius = max_radius

    def map_positions(
        self,
        positions: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        distances = np.linalg.norm(positions - self._center, axis=1)
        if self._max_radius is not None:
            radius = self._max_radius
        else:
            radius = distances.max()
        if radius < 1e-12:
            return np.zeros(len(positions), dtype=np.float64)
        result = distances / radius
        return cast(NDArray[np.float64], np.clip(result, 0.0, 1.0))
