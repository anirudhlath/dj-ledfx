"""A zone's LEDs in one fixed order, with positions (spec §5.1).

M1 has no home map, so build_ledset() lays the zone's devices side by side along x,
each in its own geometry: matrices hang with row 0 at the top, strips follow their
direction, and anything else is a vertical strip with its first LED at the bottom.
M2 replaces the layout with home-map placements; the arrays stay the same.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.spatial.geometry import (
    DeviceGeometry,
    MatrixGeometry,
    StripGeometry,
    expand_positions,
)

LED_PITCH_M = 0.03
DEVICE_GAP_M = 0.5


@dataclass(frozen=True, slots=True)
class DeviceSlice:
    device_id: str
    start: int
    stop: int

    @property
    def count(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True, slots=True)
class LedSource:
    """One device's share of a zone: its id, LED count and own geometry."""

    device_id: str
    led_count: int
    geometry: DeviceGeometry | None = None


@dataclass(frozen=True, eq=False)
class LedSet:
    pos: NDArray[np.float32]  # (N, 3) metres, x east, y south, z up
    npos: NDArray[np.float32]  # (N, 3) normalised to the zone's bounds
    local: NDArray[np.float32]  # (N, 3) normalised to each device's own bounds
    local_u: NDArray[np.float32]  # (N,) position along the device's LED order
    room: NDArray[np.int32]  # (N,) room ids, all 0 until M2
    device: NDArray[np.int32]  # (N,) index into `slices`
    anchors: Mapping[str, NDArray[np.float32]]
    slices: tuple[DeviceSlice, ...]

    @property
    def count(self) -> int:
        return int(self.pos.shape[0])

    def slice_for(self, device_id: str) -> DeviceSlice | None:
        for device_slice in self.slices:
            if device_slice.device_id == device_id:
                return device_slice
        return None


def build_ledset(sources: Sequence[LedSource], gap_m: float = DEVICE_GAP_M) -> LedSet:
    positions: list[NDArray[np.float64]] = []
    locals_: list[NDArray[np.float64]] = []
    along: list[NDArray[np.float64]] = []
    owners: list[NDArray[np.int32]] = []
    slices: list[DeviceSlice] = []
    cursor_x = 0.0
    start = 0
    for index, source in enumerate(sources):
        count = max(0, source.led_count)
        if count:
            local = _local_positions(source.geometry, count)
            low = local.min(axis=0)
            high = local.max(axis=0)
            placed = local - low
            placed[:, 0] += cursor_x
            cursor_x += float(high[0] - low[0]) + gap_m
            positions.append(placed)
            locals_.append(_normalise(local, low, high))
            along.append(np.arange(count) / (count - 1) if count > 1 else np.zeros(1))
            owners.append(np.full(count, index, dtype=np.int32))
        slices.append(DeviceSlice(source.device_id, start, start + count))
        start += count

    pos = np.concatenate(positions) if positions else np.zeros((0, 3))
    npos = _normalise(pos, pos.min(axis=0), pos.max(axis=0)) if len(pos) else pos
    return LedSet(
        pos=pos.astype(np.float32),
        npos=npos.astype(np.float32),
        local=(np.concatenate(locals_) if locals_ else np.zeros((0, 3))).astype(np.float32),
        local_u=(np.concatenate(along) if along else np.zeros(0)).astype(np.float32),
        room=np.zeros(len(pos), dtype=np.int32),
        device=np.concatenate(owners) if owners else np.zeros(0, dtype=np.int32),
        anchors=MappingProxyType({}),
        slices=tuple(slices),
    )


def _normalise(
    values: NDArray[np.float64], low: NDArray[np.float64], high: NDArray[np.float64]
) -> NDArray[np.float64]:
    span = high - low
    out = np.full(values.shape, 0.5)
    spread = span > 1e-9
    out[:, spread] = (values[:, spread] - low[spread]) / span[spread]
    return out


def _local_positions(geometry: DeviceGeometry | None, count: int) -> NDArray[np.float64]:
    if isinstance(geometry, MatrixGeometry) and (
        sum(tile.width * tile.height for tile in geometry.tiles) == count
    ):
        grid = expand_positions(geometry, (0.0, 0.0, 0.0), count)
        return np.column_stack([grid[:, 0], np.zeros(count), grid[:, 1].max() - grid[:, 1]])
    if isinstance(geometry, StripGeometry):
        return expand_positions(geometry, (0.0, 0.0, 0.0), count)
    if count == 1:
        return np.zeros((1, 3))
    # No usable geometry: a point with several LEDs, a matrix whose size disagrees
    # with the LED count, or nothing at all.
    return np.column_stack([np.zeros(count), np.zeros(count), np.arange(count) * LED_PITCH_M])
