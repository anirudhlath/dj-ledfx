from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PointGeometry:
    """Single LED at device position."""

    pass


@dataclass(frozen=True, slots=True)
class StripGeometry:
    """LEDs along a direction vector.

    Direction is auto-normalized at construction; zero vector raises ValueError.
    led_count is NOT stored here — it comes from adapter.led_count.
    """

    direction: tuple[float, float, float]
    length: float  # meters

    def __post_init__(self) -> None:
        mag = sum(d * d for d in self.direction) ** 0.5
        if mag < 1e-9:
            raise ValueError("StripGeometry direction must be non-zero")
        if abs(mag - 1.0) > 1e-6:
            normalized = tuple(d / mag for d in self.direction)
            object.__setattr__(self, "direction", normalized)


@dataclass(frozen=True, slots=True)
class TileLayout:
    """Single tile's position and dimensions within a matrix.

    Offsets are in meters relative to device position.
    """

    offset_x: float
    offset_y: float
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MatrixGeometry:
    """W×H LED grid with tile offsets."""

    tiles: tuple[TileLayout, ...]
    pixel_pitch: float = 0.03  # meters between LED centers


DeviceGeometry = PointGeometry | StripGeometry | MatrixGeometry


def expand_positions(
    geometry: DeviceGeometry,
    position: tuple[float, float, float],
    led_count: int,
) -> NDArray[np.float64]:
    """Expand a geometry + position into per-LED world-space coordinates.

    Returns shape (N, 3) float64 array.
    """
    pos = np.array(position, dtype=np.float64)

    if isinstance(geometry, PointGeometry):
        return pos.reshape(1, 3)

    if isinstance(geometry, StripGeometry):
        direction = np.array(geometry.direction, dtype=np.float64)
        # Segment center convention: (i + 0.5) / N
        t = (np.arange(led_count, dtype=np.float64) + 0.5) / led_count
        return pos + np.outer(t * geometry.length, direction)

    if isinstance(geometry, MatrixGeometry):
        positions_list: list[NDArray[np.float64]] = []
        for tile in geometry.tiles:
            tile_offset = np.array([tile.offset_x, tile.offset_y, 0.0], dtype=np.float64)
            for row in range(tile.height):
                for col in range(tile.width):
                    led_offset = np.array(
                        [col * geometry.pixel_pitch, row * geometry.pixel_pitch, 0.0],
                        dtype=np.float64,
                    )
                    positions_list.append(pos + tile_offset + led_offset)
        return np.array(positions_list, dtype=np.float64)

    msg = f"Unknown geometry type: {type(geometry)}"
    raise TypeError(msg)
