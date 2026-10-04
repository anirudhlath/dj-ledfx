"""OpenRGB stand-ins: an SDK server's list of devices, and openrgb-python's client of it.

The client keeps its own copy of the list, as openrgb-python does: it reads the list when it
opens and on update(). A list as long as the one it holds is read into the devices it holds,
place by place, each taking whatever device sits at its place now; a list of another length
is read into new devices. A device's update() reads its place again. What a device is sent
goes to whatever sits at its place on the server: the SDK addresses a device by its place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from dj_ledfx.devices.openrgb import HAS_PER_LED_COLOR, OpenRGBAdapter, OpenRGBServer

PC = "openrgb:127.0.0.1:6742"  # the test server's devices' ids start with it (the config's)


@dataclass(eq=False)
class Listed:
    """A device on the SDK server, and what it was sent."""

    name: str
    serial: str = ""
    location: str = ""
    leds: int = 2
    colour: tuple[int, int, int] = (0, 0, 0)  # each LED's, as a read gives it
    frames: list[list[tuple[int, int, int]]] = field(default_factory=list)
    modes_set: list[str] = field(default_factory=list)


class FakeServer:
    def __init__(self, *devices: Listed) -> None:
        self.devices = list(devices)
        self.clients: list[FakeClient] = []
        self.reachable = True

    def client(self, host: str, port: int, *args: Any, **kwargs: Any) -> FakeClient:
        """openrgb.OpenRGBClient(host, port): a new connection to this server."""
        if not self.reachable:
            raise ConnectionRefusedError(f"nothing listens at {host}:{port}")
        client = FakeClient(self)
        self.clients.append(client)
        return client

    @property
    def open_clients(self) -> list[FakeClient]:
        return [client for client in self.clients if client.comms.connected]


class FakeClient:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.devices: list[FakeDevice] = []
        self.comms = SimpleNamespace(connected=True)
        self.update()

    def update(self) -> None:
        if not self.comms.connected:
            raise ConnectionError("not connected")
        if len(self.devices) != len(self.server.devices):
            self.devices = [FakeDevice(self, place) for place in range(len(self.server.devices))]
        for device in self.devices:
            device.read()

    def disconnect(self) -> None:
        self.comms.connected = False


class FakeDevice:
    """openrgb's Device: a place in its client's list, and what was last read there."""

    def __init__(self, client: FakeClient, place: int) -> None:
        self.client = client
        self.id = place
        self.read()

    @property
    def sitting(self) -> Listed:
        """What sits at the device's place on the server now; a place past the end of the
        list fails as a lost connection does."""
        if self.id >= len(self.client.server.devices):
            raise ConnectionError(f"no reply for device {self.id}")
        return self.client.server.devices[self.id]

    def read(self) -> None:
        listed = self.sitting
        red, green, blue = listed.colour
        self.name = listed.name
        self.metadata = SimpleNamespace(serial=listed.serial, location=listed.location)
        self.colors = [SimpleNamespace(red=red, green=green, blue=blue)] * listed.leds
        self.modes = [
            SimpleNamespace(name="Direct", flags=HAS_PER_LED_COLOR),
            SimpleNamespace(name="Static", flags=HAS_PER_LED_COLOR),
        ]
        self.active_mode = 1

    def update(self) -> None:
        """openrgb-python reads the place again into its client's device there."""
        self.client.devices[self.id].read()

    def set_colors(self, colors: list[Any], fast: bool = False) -> None:
        self.sitting.frames.append([(c.red, c.green, c.blue) for c in colors])

    def set_mode(self, mode: Any) -> None:
        self.sitting.modes_set.append(mode if isinstance(mode, str) else str(mode.name))
        self.update()


def serve(monkeypatch: pytest.MonkeyPatch, *devices: Listed) -> FakeServer:
    """An SDK server listing devices, which every new OpenRGBClient connects to."""
    server = FakeServer(*devices)
    monkeypatch.setattr("dj_ledfx.devices.openrgb.OpenRGBClient", server.client)
    return server


def orgb_row(
    number: int, name: str, *, serial: str | None = None, location: str | None = None
) -> dict[str, Any]:
    """A known device's row, first found at place `number`, as state.db holds it; with the
    serial and location it was last found with when either is given (rows from before those
    were kept have neither)."""
    row: dict[str, Any] = {
        "id": f"{PC}:{number}",
        "name": name,
        "backend": "openrgb",
        "led_count": 2,
        "ip": "127.0.0.1",
        "device_type": "openrgb",
    }
    if serial is not None or location is not None:
        identity = {"serial": serial or "", "location": location or ""}
        row["extra"] = json.dumps({"identity": identity})
    return row


async def adapter_of(device: Any) -> OpenRGBAdapter:
    """A connected adapter over a stand-in for openrgb's device that a test shapes itself (a
    MagicMock), the one device its server lists."""
    device.id = 0  # its place in the server's list
    server = OpenRGBServer("127.0.0.1", 6742)
    client = MagicMock(devices=[device])
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient", return_value=client):
        (listed,) = await server.devices()
    adapter = OpenRGBAdapter(server, listed, f"{PC}:0")
    await adapter.connect()
    return adapter
