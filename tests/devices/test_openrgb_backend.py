from __future__ import annotations

from typing import Any

import pytest
from conftest import colours
from loguru import logger
from openrgb_fakes import PC, FakeServer, Listed, orgb_row, serve

from dj_ledfx.config import AppConfig, DevicesConfig, EngineConfig, OpenRGBConfig
from dj_ledfx.devices.backend import DiscoveredDevice
from dj_ledfx.devices.openrgb_backend import OpenRGBBackend


def test_is_enabled_checks_config() -> None:
    backend = OpenRGBBackend()
    assert (
        backend.is_enabled(AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(enabled=True))))
        is True
    )
    assert (
        backend.is_enabled(AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(enabled=False))))
        is False
    )


def _by_id(found: list[DiscoveredDevice]) -> dict[str, DiscoveredDevice]:
    return {device.adapter.device_info.stable_id or "": device for device in found}


def _names(found: list[DiscoveredDevice]) -> dict[str, str]:
    return {device_id: d.adapter.device_info.name for device_id, d in _by_id(found).items()}


async def _driven(device: DiscoveredDevice, server: FakeServer) -> Listed:
    """The device on the server that a frame sent through the adapter reaches."""
    before = [len(listed.frames) for listed in server.devices]
    await device.adapter.send_frame(colours(2, 7))
    [reached] = [d for d, n in zip(server.devices, before, strict=True) if len(d.frames) > n]
    return reached


def _warnings() -> tuple[list[Any], int]:
    """Every record logged at WARNING or above from now on, and the sink to remove."""
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="WARNING")
    return records, sink


async def test_a_scan_sets_each_device_up_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, Listed("Keyboard", leds=10))
    config = AppConfig()

    (device,) = await OpenRGBBackend().discover(config)

    assert device.adapter.is_connected and device.adapter.led_count == 10
    assert device.adapter.device_info.stable_id == f"{PC}:0"
    assert device.max_fps == device.adapter.stream_fps == config.devices.openrgb.max_fps


async def test_an_adapter_is_built_at_the_engine_s_rate_when_that_is_lower(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Keyboard"))
    (device,) = await OpenRGBBackend().discover(AppConfig(engine=EngineConfig(fps=30)))
    assert device.max_fps == device.adapter.stream_fps == 30


async def test_the_devices_of_a_server_share_one_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = serve(monkeypatch, Listed("Keyboard"), Listed("Mouse"), Listed("Strip"))
    backend = OpenRGBBackend()
    rows = [orgb_row(0, "Keyboard"), orgb_row(1, "Mouse"), orgb_row(2, "Strip")]

    found = await backend.connect_known(rows, AppConfig())
    await backend.discover(AppConfig(), skip_ids=set(_by_id(found)), known=rows)

    assert len(found) == 3
    assert len(server.clients) == 1


async def test_shutdown_closes_the_server_s_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    server = serve(monkeypatch, Listed("Keyboard"), Listed("Mouse"))
    backend = OpenRGBBackend()
    await backend.connect_known([orgb_row(0, "Keyboard"), orgb_row(1, "Mouse")], AppConfig())

    await backend.shutdown()

    assert server.clients and server.open_clients == []


async def test_a_known_device_is_found_where_it_sits_now(monkeypatch: pytest.MonkeyPatch) -> None:
    keyboard, mouse = Listed("Keyboard"), Listed("Mouse")
    server = serve(monkeypatch, mouse, keyboard)  # found the other way round
    rows = [orgb_row(0, "Keyboard"), orgb_row(1, "Mouse")]

    found = _by_id(await OpenRGBBackend().connect_known(rows, AppConfig()))

    assert await _driven(found[f"{PC}:0"], server) is keyboard
    assert await _driven(found[f"{PC}:1"], server) is mouse


async def test_a_row_is_never_connected_to_another_device(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, Listed("Keyboard"), Listed("Fan"))  # the fan sits where the headset was
    rows = [orgb_row(0, "Keyboard"), orgb_row(1, "Headset")]

    found = await OpenRGBBackend().connect_known(rows, AppConfig())

    assert _names(found) == {f"{PC}:0": "Keyboard"}


async def test_a_device_the_server_does_not_list_is_one_warning_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Keyboard"))
    records, sink = _warnings()
    try:
        found = await OpenRGBBackend().connect_known(
            [orgb_row(0, "Keyboard"), orgb_row(8, "Headset")], AppConfig()
        )
    finally:
        logger.remove(sink)

    assert _names(found) == {f"{PC}:0": "Keyboard"}
    [warning] = records
    assert warning["level"].name == "WARNING" and warning["exception"] is None
    assert "Headset" in warning["message"]


async def test_a_server_that_does_not_answer_is_one_warning_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch).reachable = False
    records, sink = _warnings()
    try:
        found = await OpenRGBBackend().connect_known(
            [orgb_row(0, "Keyboard"), orgb_row(1, "Mouse")], AppConfig()
        )
    finally:
        logger.remove(sink)

    assert found == []
    [warning] = records
    assert warning["level"].name == "WARNING" and warning["exception"] is None


async def test_devices_of_one_name_are_told_apart_by_their_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sticks = [Listed("RAM", location=f"bus-0 slot-{n}") for n in range(4)]
    server = serve(monkeypatch, sticks[2], sticks[0], sticks[3], sticks[1])
    rows = [orgb_row(n, "RAM", location=f"bus-0 slot-{n}") for n in range(4)]

    found = _by_id(await OpenRGBBackend().connect_known(rows, AppConfig()))

    for n, stick in enumerate(sticks):
        assert await _driven(found[f"{PC}:{n}"], server) is stick


async def test_rows_from_before_identities_take_devices_of_their_name_in_list_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Found as keyboard, headset and four sticks; the headset went, and the sticks moved up."""
    sticks = [Listed("RAM", location=f"bus-0 slot-{n}") for n in range(4)]
    server = serve(monkeypatch, Listed("Keyboard"), *sticks)
    rows = [orgb_row(0, "Keyboard"), orgb_row(1, "Headset")]
    rows += [orgb_row(n + 2, "RAM") for n in range(4)]

    found = _by_id(await OpenRGBBackend().connect_known(rows, AppConfig()))

    for n, stick in enumerate(sticks):
        assert await _driven(found[f"{PC}:{n + 2}"], server) is stick


async def test_a_device_whose_location_changed_is_still_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyboard = Listed("Keyboard", location="hid-7")
    server = serve(monkeypatch, Listed("Mouse"), keyboard)

    (found,) = await OpenRGBBackend().connect_known(
        [orgb_row(0, "Keyboard", location="hid-3")], AppConfig()
    )

    assert await _driven(found, server) is keyboard


async def test_a_device_with_another_serial_is_another_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Keyboard", serial="serial-2"))
    rows = [orgb_row(0, "Keyboard", serial="serial-1")]

    assert await OpenRGBBackend().connect_known(rows, AppConfig()) == []
    assert _names(await OpenRGBBackend().discover(AppConfig(), known=rows)) == {
        f"{PC}:1": "Keyboard"
    }


async def test_a_scan_finds_a_device_that_moved_under_its_row_s_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Fan"), Listed("Mouse"), Listed("Keyboard"))
    rows = [orgb_row(0, "Keyboard"), orgb_row(1, "Mouse")]  # both offline

    found = await OpenRGBBackend().discover(AppConfig(), known=rows)

    assert _names(found) == {f"{PC}:0": "Keyboard", f"{PC}:1": "Mouse", f"{PC}:2": "Fan"}


async def test_a_scan_leaves_out_a_moved_device_that_is_online(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Mouse"), Listed("Keyboard"))
    rows = [orgb_row(0, "Keyboard"), orgb_row(1, "Mouse")]

    found = await OpenRGBBackend().discover(AppConfig(), skip_ids={f"{PC}:0"}, known=rows)

    assert _names(found) == {f"{PC}:1": "Mouse"}


async def test_a_new_device_never_takes_a_number_a_known_row_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Fan"), Listed("Strip"))
    rows = [orgb_row(0, "Headset"), orgb_row(1, "Keyboard")]  # neither is listed now

    found = await OpenRGBBackend().discover(AppConfig(), known=rows)

    assert _names(found) == {f"{PC}:2": "Fan", f"{PC}:3": "Strip"}
