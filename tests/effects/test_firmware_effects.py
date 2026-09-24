from __future__ import annotations

import struct
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from lifx_fakes import FakeLifxTransport

from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.packet import (
    SET_COLOR,
    SET_EXTENDED_COLOR_ZONES,
    SET_MULTIZONE_EFFECT,
    SET_TILE_EFFECT,
    SET_WAVEFORM,
    MultiZoneEffectType,
    TileEffectType,
    Waveform,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import TileInfo
from dj_ledfx.devices.openrgb import HAS_BRIGHTNESS, OpenRGBAdapter
from dj_ledfx.effects.context import NO_SIGNALS, RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.firmware_lifx import LifxFlame, LifxMorph, LifxMove, LifxWaveform
from dj_ledfx.effects.firmware_openrgb import OpenrgbMode
from dj_ledfx.effects.ledset import LedSource, build_ledset
from dj_ledfx.effects.registry import get_effect_class, get_effect_schemas
from dj_ledfx.spatial.geometry import MatrixGeometry, TileLayout
from dj_ledfx.types import DeviceInfo

MAC = b"\xd0\x73\xd5\x00\x00\x01"
CANDLE = DeviceCapabilities(protocol="LIFX", model="LIFX Candle C", matrix=True)
NEON = DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True)
BULB = DeviceCapabilities(protocol="LIFX")
WHITE_BULB = DeviceCapabilities(protocol="LIFX", colour=False)
GOVEE = DeviceCapabilities(protocol="Govee")
PC = DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("Direct", "Static", "Rainbow Wave"))
PC_PLAIN = DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("Direct", "Static"))
KINDS = ["lifx_flame", "lifx_morph", "lifx_move", "lifx_waveform", "openrgb_mode"]


def _info(kind: str, leds: int) -> DeviceInfo:
    return DeviceInfo(
        "Light", f"lifx_{kind}", leds, "10.0.0.5:56700", stable_id="lifx:1", backend="lifx"
    )


def _candle(transport: FakeLifxTransport) -> LifxTileChainAdapter:
    tile = TileInfo(user_x=0.0, user_y=0.0, width=5, height=6, accel_x=0, accel_y=0, accel_z=0)
    return LifxTileChainAdapter(transport, _info("tile", 30), MAC, tiles=[tile])  # type: ignore[arg-type]


def _strip(transport: FakeLifxTransport) -> LifxStripAdapter:
    return LifxStripAdapter(transport, _info("strip", 12), MAC, zone_count=12)  # type: ignore[arg-type]


def _bulb(transport: FakeLifxTransport) -> LifxBulbAdapter:
    return LifxBulbAdapter(transport, _info("bulb", 1), MAC)  # type: ignore[arg-type]


def _ctx(t: float) -> RenderContext:
    return RenderContext(
        t=t,
        dt=1 / 60,
        beat_phase=0.0,
        bar_phase=0.0,
        bpm=120.0,
        beat_index=0,
        bar_index=0,
        signals=NO_SIGNALS,
    )


def test_firmware_kinds_are_registered_but_not_offered_as_strip_effects() -> None:
    for kind in KINDS:
        assert issubclass(get_effect_class(kind), FirmwareEffect)
    assert not set(KINDS) & set(get_effect_schemas())


@pytest.mark.parametrize(
    ("effect", "supported", "unsupported"),
    [
        (LifxFlame(), [CANDLE], [NEON, BULB, GOVEE, PC]),
        (LifxMorph(), [CANDLE], [NEON, BULB, GOVEE, PC]),
        (LifxMove(), [NEON], [CANDLE, BULB, GOVEE, PC]),
        (LifxWaveform(), [CANDLE, NEON, BULB], [WHITE_BULB, GOVEE, PC]),
        (OpenrgbMode(), [PC], [PC_PLAIN, CANDLE, GOVEE]),
    ],
)
def test_supports(
    effect: FirmwareEffect,
    supported: list[DeviceCapabilities],
    unsupported: list[DeviceCapabilities],
) -> None:
    assert all(effect.supports(caps) for caps in supported)
    assert not any(effect.supports(caps) for caps in unsupported)


def test_openrgb_mode_can_ask_for_one_mode() -> None:
    effect = OpenrgbMode(mode="Breathing")
    assert not effect.supports(PC)
    assert effect.supports(DeviceCapabilities(protocol="OpenRGB", openrgb_modes=("breathing",)))


async def test_flame_sets_a_warm_colour_at_the_zone_brightness_then_starts() -> None:
    transport = FakeLifxTransport()
    candle = _candle(transport)
    flame = LifxFlame(period=5.0)

    await flame.start(candle, flame.start_params(0.5))

    assert transport.types() == [SET_COLOR, SET_TILE_EFFECT]
    _reserved, *_hs, brightness, _kelvin, _duration = struct.unpack(
        "<B4HI", transport.last(SET_COLOR).payload
    )
    assert brightness == pytest.approx(65535 * 0.5, abs=2)
    assert transport.tile_effect[:2] == (TileEffectType.FLAME, 5000)
    assert await flame.is_running(candle) is True

    await flame.stop(candle)
    assert await flame.is_running(candle) is False


async def test_flame_is_rejected_by_a_bulb_and_by_a_refusing_light() -> None:
    flame = LifxFlame()
    with pytest.raises(FirmwareRejected):
        await flame.start(_bulb(FakeLifxTransport()), flame.start_params(1.0))
    with pytest.raises(FirmwareRejected):
        await flame.start(
            _candle(FakeLifxTransport(unhandled={SET_TILE_EFFECT})), flame.start_params(1.0)
        )


async def test_morph_sends_its_palette_scaled_by_brightness() -> None:
    transport = FakeLifxTransport()
    morph = LifxMorph(period=6.0, palette=["#ff0000", "#0000ff"])
    await morph.start(_candle(transport), morph.start_params(0.25))
    effect, speed, palette = transport.tile_effect
    assert (effect, speed) == (TileEffectType.MORPH, 6000)
    assert [colour[2] for colour in palette] == [pytest.approx(65535 * 0.25, abs=2)] * 2


async def test_move_paints_a_gradient_then_starts_moving() -> None:
    transport = FakeLifxTransport(zones=[(0, 0, 0, 3500)] * 12)
    move = LifxMove(period=8.0, reverse=True)
    strip = _strip(transport)
    await move.start(strip, move.start_params(1.0))
    assert transport.types() == [SET_EXTENDED_COLOR_ZONES, SET_MULTIZONE_EFFECT]
    assert transport.multizone_effect == (MultiZoneEffectType.MOVE, 8000, True)
    assert len(set(transport.zones)) > 1
    assert await move.is_running(strip) is True
    await move.stop(strip)
    assert await move.is_running(strip) is False


async def test_waveform_sets_the_base_then_runs_a_transient_waveform() -> None:
    transport = FakeLifxTransport()
    wave = LifxWaveform(period=4.0, waveform="triangle")
    bulb = _bulb(transport)
    await wave.start(bulb, wave.start_params(1.0))
    assert transport.types() == [SET_COLOR, SET_WAVEFORM]
    payload = transport.last(SET_WAVEFORM).payload
    _r, transient, _h, _s, _b, _k, period, cycles, _skew, waveform = struct.unpack(
        "<BB4HIfhB", payload
    )
    assert (transient, period, waveform) == (1, 4000, Waveform.TRIANGLE)
    assert cycles >= 1e6
    assert await wave.is_running(bulb) is None


def _pc_device() -> MagicMock:
    device = MagicMock()
    device.name = "PC"
    device.modes = [
        SimpleNamespace(
            name="Direct", flags=0, brightness=None, brightness_min=None, brightness_max=None
        ),
        SimpleNamespace(
            name="Static", flags=0, brightness=None, brightness_min=None, brightness_max=None
        ),
        SimpleNamespace(
            name="Rainbow Wave",
            flags=HAS_BRIGHTNESS,
            brightness=100,
            brightness_min=0,
            brightness_max=100,
        ),
    ]
    device.active_mode = 1
    device.colors = [SimpleNamespace(red=0, green=0, blue=0)]
    return device


async def test_openrgb_mode_starts_checks_and_stops() -> None:
    device = _pc_device()
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as client_cls:
        client_cls.return_value = MagicMock(devices=[device])
        pc = OpenRGBAdapter(device_index=0)
        await pc.connect()
    effect = OpenrgbMode()

    await effect.start(pc, effect.start_params(0.4))
    (sent,) = device.set_mode.call_args.args
    assert (sent.name, sent.brightness) == ("Rainbow Wave", 40)

    assert await effect.is_running(pc) is False
    device.active_mode = 2
    assert await effect.is_running(pc) is True

    await effect.stop(pc)
    device.set_mode.assert_called_with("Direct")


@pytest.mark.parametrize("kind", KINDS)
def test_emulations_are_finite_in_range_and_repeatable(kind: str) -> None:
    effect = get_effect_class(kind)()
    leds = build_ledset(
        [
            LedSource("candle", 30, MatrixGeometry(tiles=(TileLayout(0.0, 0.0, 5, 6),))),
            LedSource("bulb", 1),
            LedSource("neon", 12),
        ]
    )
    first = effect.emulate(_ctx(10.0), leds)  # type: ignore[attr-defined]
    again = effect.emulate(_ctx(10.0), leds)  # type: ignore[attr-defined]
    later = effect.emulate(_ctx(11.3), leds)  # type: ignore[attr-defined]
    assert first.shape == (leds.count, 3)
    assert first.dtype == np.float32
    assert np.isfinite(first).all()
    assert first.min() >= 0.0 and first.max() <= 1.0
    assert np.array_equal(first, again)
    assert not np.array_equal(first, later)


def test_flame_copy_is_hotter_at_the_bottom() -> None:
    leds = build_ledset([LedSource("lamp", 20)])  # a vertical strip, first LED at the bottom
    flame = LifxFlame()
    frames = [flame.emulate(_ctx(t / 7), leds) for t in range(30)]
    heat = np.mean([frame.sum(axis=1) for frame in frames], axis=0)
    assert heat[:5].mean() > heat[-5:].mean()
