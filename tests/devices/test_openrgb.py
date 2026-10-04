from __future__ import annotations

from typing import Any

import pytest
from conftest import colours
from openrgb_fakes import PC, FakeDevice, Listed, orgb_row, serve

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.devices.openrgb import OpenRGBAdapter, OpenRGBServer
from dj_ledfx.devices.openrgb_backend import OpenRGBBackend

ROWS = [orgb_row(0, "Keyboard"), orgb_row(1, "Mouse")]


async def _found(backend: OpenRGBBackend) -> dict[str, DeviceAdapter]:
    """The keyboard's and the mouse's adapters, by their rows' ids, as a start sets them up."""
    found = await backend.connect_known(ROWS, AppConfig())
    return {device.adapter.device_info.stable_id or "": device.adapter for device in found}


async def _scan(backend: OpenRGBBackend, adapters: dict[str, DeviceAdapter]) -> None:
    """A scan while both are online: it reads the server's list again."""
    await backend.discover(AppConfig(), skip_ids=set(adapters), known=ROWS)


async def test_a_device_found_is_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, Listed("Keyboard", leds=10))
    (found,) = await OpenRGBBackend().discover(AppConfig())
    assert found.adapter.is_connected is True
    assert found.adapter.led_count == 10


async def test_a_frame_reaches_the_device(monkeypatch: pytest.MonkeyPatch) -> None:
    keyboard = Listed("Keyboard", leds=3)
    serve(monkeypatch, keyboard)
    (found,) = await OpenRGBBackend().discover(AppConfig())

    await found.adapter.send_frame(colours(3, 128))

    assert keyboard.frames == [[(128, 128, 128)] * 3]


async def test_a_frame_is_cut_to_the_device_s_leds(monkeypatch: pytest.MonkeyPatch) -> None:
    keyboard = Listed("Keyboard", leds=5)
    serve(monkeypatch, keyboard)
    (found,) = await OpenRGBBackend().discover(AppConfig())

    await found.adapter.send_frame(colours(10, 128))

    assert keyboard.frames == [[(128, 128, 128)] * 5]


async def test_an_adapter_streams_at_the_rate_it_was_built_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, Listed("Keyboard"))
    server = OpenRGBServer("127.0.0.1", 6742)
    (device,) = await server.devices()
    assert OpenRGBAdapter(server, device, f"{PC}:0", max_fps=30).stream_fps == 30
    unset = OpenRGBAdapter(server, device, f"{PC}:0")
    assert unset.stream_fps is None  # the scheduler's rate
    assert unset.display_ms == 0.0


async def test_disconnecting_one_device_leaves_the_others_their_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mouse = Listed("Mouse")
    server = serve(monkeypatch, Listed("Keyboard"), mouse)
    adapters = await _found(OpenRGBBackend())

    await adapters[f"{PC}:0"].disconnect()
    await adapters[f"{PC}:1"].send_frame(colours(2, 5))

    assert adapters[f"{PC}:0"].is_connected is False
    assert mouse.frames == [[(5, 5, 5)] * 2]
    assert server.open_clients


@pytest.mark.parametrize("error", [ConnectionError("broken pipe"), OSError("unreachable")])
async def test_a_send_that_fails_leaves_the_adapter_disconnected(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    serve(monkeypatch, Listed("Keyboard"))
    (found,) = await OpenRGBBackend().discover(AppConfig())

    def refuse(self: FakeDevice, colors: list[Any], fast: bool = False) -> None:
        raise error

    monkeypatch.setattr(FakeDevice, "set_colors", refuse)
    with pytest.raises(type(error)):
        await found.adapter.send_frame(colours(2, 1))
    assert found.adapter.is_connected is False


async def test_a_device_that_moves_in_the_list_is_sent_nothing_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyboard, mouse = Listed("Keyboard"), Listed("Mouse")
    server = serve(monkeypatch, keyboard, mouse)
    backend = OpenRGBBackend()
    adapters = await _found(backend)

    server.devices = [mouse, keyboard]  # the server's list changed
    await _scan(backend, adapters)
    with pytest.raises(ConnectionError):
        await adapters[f"{PC}:0"].send_frame(colours(2, 7))

    assert adapters[f"{PC}:0"].is_connected is False  # offline until a scan finds it
    assert mouse.frames == []


async def test_a_device_that_moved_when_the_list_grew_is_sent_nothing_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyboard, mouse, fan = Listed("Keyboard"), Listed("Mouse"), Listed("Fan")
    server = serve(monkeypatch, keyboard, mouse)
    backend = OpenRGBBackend()
    adapters = await _found(backend)

    server.devices = [fan, mouse, keyboard]  # a new list, with both devices moved
    await _scan(backend, adapters)
    with pytest.raises(ConnectionError):
        await adapters[f"{PC}:0"].send_frame(colours(2, 7))

    assert fan.frames == [] and mouse.frames == []


async def test_a_device_that_stays_put_while_the_list_grows_streams_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyboard = Listed("Keyboard")
    server = serve(monkeypatch, keyboard, Listed("Mouse"))
    backend = OpenRGBBackend()
    adapters = await _found(backend)

    server.devices.append(Listed("Fan"))  # a device came: the client reads a new list
    await _scan(backend, adapters)
    await adapters[f"{PC}:0"].send_frame(colours(2, 7))

    assert adapters[f"{PC}:0"].is_connected is True
    assert keyboard.frames == [[(7, 7, 7)] * 2]


async def test_a_read_that_finds_another_device_in_its_place_reads_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mouse = Listed("Mouse", colour=(9, 9, 9))
    server = serve(monkeypatch, Listed("Keyboard", colour=(1, 2, 3)), mouse)
    adapters = await _found(OpenRGBBackend())
    keyboard = adapters[f"{PC}:0"]

    server.devices = [mouse]  # the keyboard went, and the mouse moved into its place
    reading = await keyboard.read_light()

    assert reading == LightReading(power=None, colour=None)
    assert await keyboard.capture_state() is None
    assert keyboard.is_connected is False
