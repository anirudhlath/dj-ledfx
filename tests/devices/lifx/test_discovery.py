from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from lifx_fakes import FakeLifxTransport

from dj_ledfx.config import AppConfig, DevicesConfig, LIFXConfig
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.discovery import LifxBackend
from dj_ledfx.devices.lifx.packet import GET_DEVICE_CHAIN
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import LifxDeviceRecord

MAC = b"\xd0\x73\xd5\x00\x00\x01"


def _record(product: int, mac: bytes = MAC) -> LifxDeviceRecord:
    return LifxDeviceRecord(mac=mac, ip="10.0.0.5", port=56700, vendor=1, product=product)


def _backend(transport: FakeLifxTransport) -> LifxBackend:
    backend = LifxBackend()
    backend._transport = transport  # type: ignore[assignment]
    return backend


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"lifx:{MAC.hex()}",
        "name": "LIFX Tile (10.0.0.5)",
        "backend": "lifx",
        "device_type": "lifx_tile",
        "led_count": 64,
        "ip": "10.0.0.5",
        "mac": MAC.hex(),
    }
    row.update(overrides)
    return row


def test_is_enabled_checks_config() -> None:
    backend = LifxBackend()
    assert backend.is_enabled(AppConfig(devices=DevicesConfig(lifx=LIFXConfig(enabled=True))))
    assert not backend.is_enabled(AppConfig(devices=DevicesConfig(lifx=LIFXConfig(enabled=False))))


async def test_candle_is_a_matrix_sized_from_its_device_chain() -> None:
    transport = FakeLifxTransport(product=57, label="Candle 1", chain=[(5, 6)], firmware=(3, 90))
    adapter = await _backend(transport)._create_adapter(_record(57), AppConfig())
    assert isinstance(adapter, LifxTileChainAdapter)
    assert adapter.led_count == 30
    assert adapter.device_info.led_count == 30
    assert adapter.device_info.name == "Candle 1"
    assert adapter.device_info.device_type == "lifx_tile"
    assert adapter.capabilities.model == "LIFX Candle C"
    assert adapter.capabilities.firmware_version == "3.90"


async def test_tile_without_a_chain_reply_falls_back_to_five_8x8_tiles() -> None:
    transport = FakeLifxTransport(product=55, unhandled={GET_DEVICE_CHAIN})
    adapter = await _backend(transport)._create_adapter(_record(55), AppConfig())
    assert isinstance(adapter, LifxTileChainAdapter)
    assert adapter.led_count == 5 * 64


async def test_neon_is_a_strip_sized_from_its_zones() -> None:
    zones = [(0, 0, 65535, 3500)] * 36
    transport = FakeLifxTransport(product=141, label="Neon Indoor", zones=zones, firmware=(4, 10))
    adapter = await _backend(transport)._create_adapter(_record(141), AppConfig())
    assert isinstance(adapter, LifxStripAdapter)
    assert adapter.led_count == 36
    assert adapter.device_info.led_count == 36


@pytest.mark.parametrize(
    ("firmware", "kind"), [((2, 76), LifxBulbAdapter), ((2, 77), LifxStripAdapter)]
)
async def test_lifx_z_is_a_strip_from_firmware_2_77(firmware: tuple[int, int], kind: type) -> None:
    transport = FakeLifxTransport(product=32, zones=[(0, 0, 65535, 3500)] * 16, firmware=firmware)
    adapter = await _backend(transport)._create_adapter(_record(32), AppConfig())
    assert type(adapter) is kind


@pytest.mark.parametrize("product", [1, 90, 9999])
async def test_bulbs_and_unknown_products_are_bulbs(product: int) -> None:
    transport = FakeLifxTransport(product=product)
    adapter = await _backend(transport)._create_adapter(_record(product), AppConfig())
    assert type(adapter) is LifxBulbAdapter


async def test_switches_are_skipped() -> None:
    transport = FakeLifxTransport(product=70)
    assert await _backend(transport)._create_adapter(_record(70), AppConfig()) is None


async def test_unlabelled_light_is_named_after_its_model() -> None:
    transport = FakeLifxTransport(product=27, label="")
    adapter = await _backend(transport)._create_adapter(_record(27), AppConfig())
    assert adapter is not None
    assert adapter.device_info.name == "LIFX (A19) (10.0.0.5)"


async def test_duplicate_labels_get_a_suffix() -> None:
    backend = _backend(FakeLifxTransport(product=1, label="Lamp"))
    first = await backend._create_adapter(_record(1, b"\xd0\x73\xd5\x00\x00\x01"), AppConfig())
    second = await backend._create_adapter(_record(1, b"\xd0\x73\xd5\x00\x00\x02"), AppConfig())
    again = await backend._create_adapter(_record(1, b"\xd0\x73\xd5\x00\x00\x01"), AppConfig())
    assert first is not None and first.device_info.name == "Lamp"
    assert second is not None and second.device_info.name == "Lamp (0002)"
    assert again is not None and again.device_info.name == "Lamp"


async def test_discover_returns_discovered_devices() -> None:
    transport = FakeLifxTransport(product=1, label="Right Lamp")
    record = _record(1)

    async def _fake_discover(
        timeout_s: float = 1.0, on_record: Callable[[LifxDeviceRecord], None] | None = None
    ) -> list[LifxDeviceRecord]:
        if on_record is not None:
            on_record(record)
        return [record]

    transport.discover = _fake_discover  # type: ignore[attr-defined]
    config = AppConfig()
    devices = await _backend(transport).discover(config)

    (device,) = devices
    assert isinstance(device.adapter, LifxBulbAdapter)
    assert device.adapter.device_info.name == "Right Lamp"
    assert device.adapter.is_connected
    assert device.max_fps == config.devices.lifx.max_fps


async def test_connect_known_asks_the_light_instead_of_trusting_the_row() -> None:
    transport = FakeLifxTransport(product=57, label="Candle 2", chain=[(5, 6)])
    (device,) = await _backend(transport).connect_known([_row()], AppConfig())
    assert isinstance(device.adapter, LifxTileChainAdapter)
    assert device.adapter.led_count == 30
    assert device.adapter.device_info.name == "Candle 2"
    assert device.adapter.device_info.stable_id == f"lifx:{MAC.hex()}"


async def test_connect_known_leaves_silent_lights_offline() -> None:
    transport = FakeLifxTransport(silent=True)
    assert await _backend(transport).connect_known([_row()], AppConfig()) == []


async def test_connect_known_skips_rows_without_an_address() -> None:
    transport = FakeLifxTransport()
    assert await _backend(transport).connect_known([_row(ip=None)], AppConfig()) == []
    assert transport.sent == []
