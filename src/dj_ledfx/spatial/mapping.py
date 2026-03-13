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
