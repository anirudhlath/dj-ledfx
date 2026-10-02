"""LIFX rates per kind, fades between frames, and the delay a light shows a frame with."""

from __future__ import annotations

import asyncio
import struct

import numpy as np
from lifx_fakes import MAC, FakeLifxTransport, lifx_info

from dj_ledfx.config import LIFX_MATRIX_FPS, LIFX_STRIP_FPS
from dj_ledfx.devices.lifx.base import stream_fade_ms, stream_fps
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import SET_COLOR, SET_EXTENDED_COLOR_ZONES, SET_TILE_STATE_64
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import MATRIX_DISPLAY_MS, LifxTileChainAdapter


def test_each_kind_streams_within_its_cap() -> None:
    assert stream_fps(LifxBulbAdapter, 60) == 60
    assert stream_fps(LifxStripAdapter, 60) == LIFX_STRIP_FPS
    assert stream_fps(LifxTileChainAdapter, 60) == LIFX_MATRIX_FPS
    assert stream_fps(LifxTileChainAdapter, 10) == 10  # a lower configured rate wins


def test_a_fade_ends_just_before_the_next_frame() -> None:
    assert stream_fade_ms(20) == 48
    assert stream_fade_ms(60) == 15
    assert stream_fade_ms(1000) == 0


async def test_every_frame_fades_for_the_adapter_s_fade() -> None:
    transport = FakeLifxTransport()
    bulb = LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC, fade_ms=15)
    await bulb.send_frame(np.full((1, 3), 200, dtype=np.uint8))
    *_, duration = struct.unpack("<B4HI", transport.last(SET_COLOR).payload)
    assert duration == 15

    strip = LifxStripAdapter(transport, lifx_info("strip", 4), MAC, zone_count=4, fade_ms=48)
    await strip.send_frame(np.full((4, 3), 200, dtype=np.uint8))
    assert struct.unpack_from("<I", transport.last(SET_EXTENDED_COLOR_ZONES).payload)[0] == 48

    matrix = LifxTileChainAdapter(
        transport, lifx_info("matrix", 64), MAC, tile_count=1, fade_ms=48
    )
    await matrix.send_frame(np.full((64, 3), 200, dtype=np.uint8))
    assert struct.unpack_from("<6BI", transport.last(SET_TILE_STATE_64).payload)[6] == 48


def test_a_light_shows_a_frame_half_way_through_its_fade() -> None:
    transport = FakeLifxTransport()
    bulb = LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC, fade_ms=48)
    matrix = LifxTileChainAdapter(
        transport, lifx_info("matrix", 64), MAC, tile_count=1, fade_ms=48
    )
    assert bulb.display_ms == 24.0
    assert matrix.display_ms == 24.0 + MATRIX_DISPLAY_MS


# Review Focus 6: a light that never acks or answers. Frames are fire and forget.
async def test_a_light_that_never_answers_still_takes_every_frame() -> None:
    transport = FakeLifxTransport(silent=True)
    bulb = LifxBulbAdapter(transport, lifx_info("bulb", 1), MAC, fade_ms=15)
    for level in (50, 100, 150):
        frame = np.full((1, 3), level, dtype=np.uint8)
        await asyncio.wait_for(bulb.send_frame(frame), timeout=0.05)  # waits for nothing
    assert transport.types().count(SET_COLOR) == 3
