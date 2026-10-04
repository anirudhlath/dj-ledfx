from __future__ import annotations

import asyncio
import copy
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import (
    DeviceCapabilities,
    FirmwareRejected,
    LightReading,
    NoAnswer,
)
from dj_ledfx.types import RGB, DeviceInfo, clamp01

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:
    OpenRGBClient = None
    RGBColor = None

HAS_BRIGHTNESS = 1 << 4  # openrgb.utils.ModeFlags.HAS_BRIGHTNESS
HAS_PER_LED_COLOR = 1 << 5  # openrgb.utils.ModeFlags.HAS_PER_LED_COLOR
READ_FRESH_S = 1.0  # a poll's read and its effect check share one device.update()
CONNECT_TIMEOUT_S = 5.0  # each of a connection's two tries
IDENTITY_KEY = "identity"  # where a device's serial and location sit in its row's extra

T = TypeVar("T")


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class OpenRGBIdentity:
    """What an OpenRGB device is, as its server reports it: its name, and the serial and
    location (a bus and address, or a USB path) that tell devices of one name apart, as the
    PC's four RAM sticks share one. A known device is found by it wherever it now sits in
    the server's list."""

    name: str
    serial: str = ""
    location: str = ""

    @classmethod
    def of(cls, device: Any) -> OpenRGBIdentity:
        """An openrgb-python device's, as its connection last read it."""
        metadata = getattr(device, "metadata", None)
        return cls(
            _text(getattr(device, "name", None)),
            _text(getattr(metadata, "serial", None)),
            _text(getattr(metadata, "location", None)),
        )

    @classmethod
    def of_row(cls, row: Mapping[str, Any]) -> OpenRGBIdentity:
        """A known device's: its row's name, and the serial and location its extra keeps (a
        row from before they were kept has neither, nor has one whose extra can't be read)."""
        try:
            extra = json.loads(row.get("extra") or "null")
        except (TypeError, ValueError):
            extra = None
        kept = extra.get(IDENTITY_KEY) if isinstance(extra, dict) else None
        if not isinstance(kept, dict):
            kept = {}
        return cls(_text(row.get("name")), _text(kept.get("serial")), _text(kept.get("location")))

    def to_extra(self) -> dict[str, str]:
        """What the row's extra keeps under IDENTITY_KEY: the name has a column of its own."""
        return {"serial": self.serial, "location": self.location}

    def likeness(self, listed: OpenRGBIdentity) -> tuple[bool, bool] | None:
        """How a device the server lists now compares with this known one. None: it's
        another device (another name, or another serial where both have one). Else whether
        their serials agree and whether their locations do; a location may change (a USB
        device's path can, from one boot to the next), so it never rules a device out."""
        if listed.name != self.name:
            return None
        if self.serial and listed.serial and listed.serial != self.serial:
            return None
        return (
            bool(self.serial) and listed.serial == self.serial,
            bool(self.location) and listed.location == self.location,
        )


class OpenRGBServer:
    """An OpenRGB SDK server, and the one connection all its devices share: its list is read
    once for them all. openrgb-python is synchronous, and it reads a reply into the list it
    holds, so each exchange on the connection runs in a thread in its turn (`turn`): a frame
    sent, a device read, the list read again."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.turn = asyncio.Lock()
        self._client: Any = None

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def listed(self) -> list[Any]:
        """The devices in the server's order, as the connection last read the list. Only in
        the server's turn: openrgb-python changes the list while it reads it."""
        return list(self._client.devices) if self._client is not None else []

    async def devices(self) -> list[Any]:
        """The server's devices, read afresh, in its order: over the connection, or a new one
        when there's none or it failed. Raises OSError (ConnectionError) when the server
        can't be reached."""
        async with self.turn:
            if self._client is not None:
                try:
                    await asyncio.to_thread(self._client.update)
                    return self.listed()
                except OSError as exc:
                    logger.debug("OpenRGB connection to {} failed ({})", self.address, exc)
                    await self._drop()
            self._client = await self._connect()
            return self.listed()

    async def close(self) -> None:
        async with self.turn:
            await self._drop()

    async def _drop(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await asyncio.to_thread(client.disconnect)

    async def _connect(self) -> Any:
        """A new connection, which reads the server's list as it opens: two tries."""

        def _open() -> Any:
            if OpenRGBClient is None:
                raise ConnectionError("openrgb-python is not installed")
            return OpenRGBClient(self.host, self.port)

        for attempt in range(2):
            try:
                return await asyncio.wait_for(asyncio.to_thread(_open), CONNECT_TIMEOUT_S)
            except TimeoutError:
                if attempt == 0:
                    logger.warning(
                        "OpenRGB connection to {} timed out (attempt 1), retrying…", self.address
                    )
        raise ConnectionError(f"OpenRGB connection to {self.address} timed out after 2 attempts")


class OpenRGBAdapter(DeviceAdapter):
    """A device on an OpenRGB server, over the server's one connection. The SDK addresses it
    by its place in the server's list: the place it was found at. openrgb-python reads a
    changed list into the devices it holds, place by place (a list of another length into new
    ones), so each exchange checks first that the place still holds this device. Once it
    holds another, or none, the adapter is disconnected: the light goes offline until a scan
    finds it again, wherever it sits."""

    def __init__(
        self,
        server: OpenRGBServer,
        device: Any,
        stable_id: str,
        max_fps: float | None = None,
    ) -> None:
        self._max_fps = max_fps
        self._server = server
        self._place: int = device.id
        self._identity = OpenRGBIdentity.of(device)
        self._stable_id = stable_id
        self._device: Any = device
        self._is_connected = False
        self._led_count = 0
        self._modes: tuple[str, ...] = ()
        self._last_read: tuple[float, tuple[str, list[RGB]]] | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._identity.name,
            device_type="openrgb",
            led_count=self._led_count,
            address=self._server.address,
            stable_id=self._stable_id,
            backend="openrgb",
        )

    @property
    def row_extra(self) -> Mapping[str, Any]:
        return {IDENTITY_KEY: self._identity.to_extra()}

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        """Take the device up at its place. Raises ConnectionError when the server's list
        changed under it since it was found."""
        async with self._server.turn:
            device = self._held()
            self._modes = tuple(str(mode.name) for mode in device.modes)
            self._led_count = len(device.colors)
        self._last_read = None
        self._is_connected = True
        logger.info(
            "Connected to OpenRGB device '{}' ({} LEDs) at {}",
            self._identity.name,
            self._led_count,
            self._server.address,
        )

    async def disconnect(self) -> None:
        """Let the device go. The connection stays open for the server's other devices; the
        backend closes it at shutdown."""
        self._is_connected = False
        self._device = None
        logger.info("Disconnected from OpenRGB device '{}'", self._identity.name)

    def _held(self) -> Any:
        """The device as the connection's list holds it now, at its place. In the server's
        turn only. Raises ConnectionError, and leaves the adapter disconnected, once the place
        holds another device or none."""
        listed = self._server.listed()
        device = listed[self._place] if self._place < len(listed) else None
        if device is None or OpenRGBIdentity.of(device) != self._identity:
            self._is_connected = False
            raise ConnectionError(
                f"OpenRGB device '{self._identity.name}' isn't at its place in the list"
            )
        self._device = device
        return device

    async def _exchange(self, work: Callable[[Any], T]) -> T:
        """Run work on the device in a thread, in the server's turn. The place is checked
        before and after: a read may bring a changed list, and then what it read isn't this
        device's. Raises ConnectionError while the adapter is disconnected."""
        if not self._is_connected:
            raise ConnectionError(f"OpenRGB device '{self._identity.name}' is disconnected")
        async with self._server.turn:
            result = await asyncio.to_thread(work, self._held())
            self._held()
        return result

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        if not self._is_connected:
            return

        frame = colors[: self._led_count]

        rgb_colors = [
            RGBColor(int(frame[i, 0]), int(frame[i, 1]), int(frame[i, 2]))
            for i in range(len(frame))
        ]

        def _send(device: Any) -> None:
            device.set_colors(rgb_colors, fast=True)

        try:
            await self._exchange(_send)
        except (ConnectionError, OSError):
            self._is_connected = False
            raise
        logger.trace("Sent {} colors to '{}'", len(rgb_colors), self._identity.name)

    @property
    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            protocol="OpenRGB", model=self._identity.name, openrgb_modes=self._modes
        )

    def _find_mode(self, name: str) -> Any:
        device = self._device
        if device is None:
            return None
        return next((m for m in device.modes if str(m.name).lower() == name.lower()), None)

    async def prepare_stream(self) -> None:
        direct = self._find_mode("direct")
        self._last_read = None
        if self._is_connected and direct is not None:
            await self._exchange(lambda device: device.set_mode(str(direct.name)))

    async def set_mode(self, name: str, brightness: float) -> None:
        """Start one of the device's own modes, scaled to the zone's brightness."""
        mode = self._find_mode(name)
        if mode is None:
            raise FirmwareRejected(f"{self._identity.name} has no mode '{name}'")
        self._last_read = None
        chosen = copy.copy(mode)
        if int(chosen.flags) & HAS_BRIGHTNESS and chosen.brightness_max is not None:
            low = int(chosen.brightness_min or 0)
            high = int(chosen.brightness_max)
            chosen.brightness = round(low + (high - low) * clamp01(brightness))
        try:
            await self._exchange(lambda device: device.set_mode(chosen))
        except ValueError as exc:
            raise FirmwareRejected(f"{self._identity.name} refused mode '{name}': {exc}") from exc
        except (ConnectionError, OSError) as exc:
            raise NoAnswer(f"{self._identity.name} didn't take mode '{name}': {exc}") from exc

    async def _read(self) -> tuple[str, list[RGB]] | None:
        """The active mode's name and the LED colours from the server, at most
        READ_FRESH_S old; any change dj-ledfx makes asks afresh. None: no answer, or the
        device isn't at its place any more."""
        now = time.monotonic()
        if self._last_read is not None and now - self._last_read[0] < READ_FRESH_S:
            return self._last_read[1]

        def _update(device: Any) -> tuple[str, list[RGB]]:
            device.update()
            colours = [(int(c.red), int(c.green), int(c.blue)) for c in device.colors]
            return str(device.modes[device.active_mode].name), colours

        try:
            read = await self._exchange(_update)
        except (IndexError, ConnectionError, OSError):
            return None
        self._last_read = (now, read)
        return read

    async def active_mode_name(self) -> str | None:
        read = await self._read()
        return read[0] if read is not None else None

    async def read_light(self) -> LightReading:
        read = await self._read()
        colour = read[1][0] if read is not None and read[1] else None
        return LightReading(power=None, colour=colour)

    async def capture_state(self) -> bytes | None:
        read = await self._read()
        if read is None:
            return None
        mode, colours = read
        return json.dumps({"mode": mode, "colors": [list(c) for c in colours]}).encode()

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """Mode and colours: OpenRGB has no power to leave alone, so power changes nothing."""
        try:
            snapshot = json.loads(state)
            mode = self._find_mode(str(snapshot["mode"]))
            colours = [RGBColor(int(r), int(g), int(b)) for r, g, b in snapshot["colors"]]
        except (ValueError, KeyError, TypeError):
            logger.warning("OpenRGB '{}': captured state is unreadable", self._identity.name)
            return
        if mode is None:
            return
        self._last_read = None

        def _restore(device: Any) -> None:
            device.set_mode(str(mode.name))
            if colours and int(mode.flags) & HAS_PER_LED_COLOR:
                device.set_colors(colours)

        try:
            await self._exchange(_restore)
        except (ValueError, ConnectionError, OSError):
            logger.warning("OpenRGB '{}': couldn't restore its mode", self._identity.name)
