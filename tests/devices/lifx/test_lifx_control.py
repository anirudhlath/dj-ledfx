from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from lifx_fakes import MAC, FakeLifxTransport, lifx_bulb, lifx_candle, lifx_info, lifx_strip

from dj_ledfx.devices.capabilities import (
    DeviceCapabilities,
    FirmwareRejected,
    LightReading,
    NoAnswer,
)
from dj_ledfx.devices.lifx.packet import (
    GET_COLOR,
    HSBK,
    SET_COLOR,
    SET_EXTENDED_COLOR_ZONES,
    SET_LIGHT_POWER,
    SET_MULTIZONE_EFFECT,
    SET_TILE_EFFECT,
    SET_TILE_STATE_64,
    MultiZoneEffectType,
    TileEffectType,
    hsbk_to_rgb,
)
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.spatial.geometry import MatrixGeometry

RED: HSBK = (0, 65535, 65535, 3500)
WHITE: HSBK = (0, 0, 65535, 3500)


def test_hsbk_to_rgb() -> None:
    assert hsbk_to_rgb(RED) == (255, 0, 0)
    assert hsbk_to_rgb(WHITE) == (255, 255, 255)
    assert hsbk_to_rgb((21845, 65535, 32768, 3500)) == (0, 128, 0)


async def test_read_light_reports_power_and_colour() -> None:
    transport = FakeLifxTransport(power=False, hsbk=RED)
    assert await lifx_bulb(transport).read_light() == LightReading(power=False, colour=(255, 0, 0))
    assert transport.types() == [GET_COLOR]


async def test_read_light_raises_when_the_light_is_silent() -> None:
    transport = FakeLifxTransport(silent=True)
    with pytest.raises(NoAnswer):
        await lifx_bulb(transport).read_light()


async def test_set_power_sends_set_light_power() -> None:
    transport = FakeLifxTransport(power=False)
    await lifx_bulb(transport).set_power(True)
    assert transport.power is True
    assert struct.unpack("<HI", transport.last(SET_LIGHT_POWER).payload) == (65535, 0)


async def test_bulb_capture_and_restore_round_trip() -> None:
    transport = FakeLifxTransport(power=False, hsbk=RED)
    bulb = lifx_bulb(transport)
    captured = await bulb.capture_state()
    assert captured is not None
    assert json.loads(captured) == {"v": 1, "power": False, "hsbk": list(RED)}

    transport.power, transport.hsbk = True, WHITE  # the look ran
    transport.sent.clear()
    await bulb.restore_state(captured)

    assert transport.types() == [SET_COLOR, SET_LIGHT_POWER]
    assert transport.hsbk == RED
    assert transport.power is False


async def test_restore_without_power_leaves_a_switched_off_bulb_off() -> None:
    transport = FakeLifxTransport(power=True, hsbk=RED)
    bulb = lifx_bulb(transport)
    captured = await bulb.capture_state()
    assert captured is not None
    transport.hsbk, transport.power = WHITE, False  # the look ran; then it was switched off
    transport.sent.clear()

    await bulb.restore_state(captured, power=False)

    assert transport.types() == [SET_COLOR]
    assert transport.hsbk == RED
    assert transport.power is False


async def test_capture_is_none_when_the_light_is_silent() -> None:
    assert await lifx_bulb(FakeLifxTransport(silent=True)).capture_state() is None


async def test_unreadable_capture_leaves_the_light_alone() -> None:
    transport = FakeLifxTransport()
    await lifx_bulb(transport).restore_state(b"\x80\x80\x80")
    assert transport.sent == []


async def test_strip_captures_zones_and_its_move_effect() -> None:
    zones: list[HSBK] = [(i * 1000, 65535, 65535, 3500) for i in range(8)]
    transport = FakeLifxTransport(zones=zones)
    transport.multizone_effect = (int(MultiZoneEffectType.MOVE), 4000, True)
    strip = lifx_strip(transport)

    captured = await strip.capture_state()
    assert captured is not None
    snapshot = json.loads(captured)
    assert snapshot["zones"] == [list(z) for z in zones]
    assert snapshot["multizone_effect"] == {"effect": 1, "speed_ms": 4000, "reverse": True}

    await strip.prepare_stream()
    assert transport.multizone_effect[0] == MultiZoneEffectType.OFF

    transport.zones = [(0, 0, 0, 3500)] * 8
    transport.sent.clear()
    await strip.restore_state(captured)

    assert transport.types() == [SET_EXTENDED_COLOR_ZONES, SET_MULTIZONE_EFFECT, SET_LIGHT_POWER]
    assert transport.zones == zones
    assert transport.multizone_effect == (1, 4000, True)


async def test_candle_size_geometry_and_frames_follow_its_device_chain() -> None:
    transport = FakeLifxTransport()
    candle = lifx_candle(transport)
    assert candle.led_count == 30
    geometry = candle.geometry
    assert isinstance(geometry, MatrixGeometry)
    assert [(t.width, t.height) for t in geometry.tiles] == [(5, 6)]

    await candle.send_frame(np.zeros((30, 3), dtype=np.uint8))
    (frame,) = transport.sent
    assert frame.msg_type == SET_TILE_STATE_64
    tile_index, length, _reserved, x, y, width = struct.unpack("<6B", frame.payload[:6])
    assert (tile_index, length, x, y, width) == (0, 1, 0, 0, 5)


# B16: frames count their own sequence, so the 8-bit request counter wraps only after 256
# requests, and a late reply can't be taken for the answer to a newer request.
async def test_streamed_frames_leave_the_request_sequence_alone() -> None:
    transport = FakeLifxTransport()
    candle = lifx_candle(transport)
    before = transport.next_sequence()

    for _ in range(300):
        await candle.send_frame(np.zeros((30, 3), dtype=np.uint8))

    assert transport.next_sequence() == before + 1
    assert [packet.sequence for packet in transport.sent[254:258]] == [255, 0, 1, 2]


async def test_tiles_wider_than_64_pixels_are_sent_in_row_bands() -> None:
    transport = FakeLifxTransport()
    wide = TileInfo(user_x=0.0, user_y=0.0, width=16, height=8, accel_x=0, accel_y=0, accel_z=0)
    adapter = LifxTileChainAdapter(transport, lifx_info("tile", 128), MAC, tiles=[wide])
    await adapter.send_frame(np.zeros((128, 3), dtype=np.uint8))
    rows = [struct.unpack("<6B", p.payload[:6])[4] for p in transport.sent]
    assert rows == [0, 4]


async def test_candle_captures_and_restores_its_flame() -> None:
    transport = FakeLifxTransport()
    candle = lifx_candle(transport)
    await candle.start_tile_effect(TileEffectType.FLAME, 5000)
    captured = await candle.capture_state()
    assert captured is not None
    assert json.loads(captured)["tile_effect"] == {"effect": 3, "speed_ms": 5000, "palette": []}

    await candle.start_tile_effect(TileEffectType.MORPH, 3000)  # the look's own effect

    transport.sent.clear()
    await candle.restore_state(captured)
    assert transport.types() == [SET_COLOR, SET_TILE_EFFECT, SET_LIGHT_POWER]
    assert transport.tile_effect[:2] == (3, 5000)


async def test_restoring_a_candle_without_an_effect_ends_the_looks_effect() -> None:
    transport = FakeLifxTransport()
    candle = lifx_candle(transport)
    captured = await candle.capture_state()
    assert captured is not None and "tile_effect" not in json.loads(captured)
    await candle.start_tile_effect(TileEffectType.FLAME, 5000)  # the look runs Flame

    transport.sent.clear()
    await candle.restore_state(captured)

    assert transport.types() == [SET_TILE_EFFECT, SET_COLOR, SET_LIGHT_POWER]
    assert transport.tile_effect[0] == TileEffectType.OFF


async def test_restoring_a_strip_without_an_effect_ends_the_looks_effect() -> None:
    transport = FakeLifxTransport(zones=[RED] * 8)
    strip = lifx_strip(transport)
    captured = await strip.capture_state()
    assert captured is not None and "multizone_effect" not in json.loads(captured)
    await strip.start_multizone_effect(MultiZoneEffectType.MOVE, 4000)  # the look runs Move

    transport.sent.clear()
    await strip.restore_state(captured, power=False)

    assert transport.types() == [SET_MULTIZONE_EFFECT, SET_EXTENDED_COLOR_ZONES]
    assert transport.multizone_effect[0] == MultiZoneEffectType.OFF
    assert transport.zones == [RED] * 8


async def test_firmware_command_rejected_by_the_light() -> None:
    transport = FakeLifxTransport(unhandled={SET_TILE_EFFECT})
    with pytest.raises(FirmwareRejected):
        await lifx_candle(transport).start_tile_effect(TileEffectType.FLAME, 5000)


async def test_firmware_command_without_an_answer_is_no_answer_not_a_refusal() -> None:
    transport = FakeLifxTransport(silent=True)
    with pytest.raises(NoAnswer) as raised:
        await lifx_candle(transport).start_tile_effect(TileEffectType.FLAME, 5000)
    assert not isinstance(raised.value, FirmwareRejected)
    assert transport.types() == [SET_TILE_EFFECT, SET_TILE_EFFECT]  # asked twice


async def test_prepare_stream_tolerates_lights_without_effects() -> None:
    transport = FakeLifxTransport(unhandled={SET_TILE_EFFECT})
    await lifx_candle(transport).prepare_stream()
    assert transport.types() == [SET_TILE_EFFECT]


def test_adapters_report_their_capabilities() -> None:
    transport = FakeLifxTransport()
    caps = DeviceCapabilities(protocol="LIFX", model="LIFX Tube", matrix=True)
    assert lifx_candle(transport, caps).capabilities is caps
    assert lifx_strip(transport).capabilities.extended_multizone
    assert lifx_bulb(transport).capabilities == DeviceCapabilities(protocol="LIFX")
