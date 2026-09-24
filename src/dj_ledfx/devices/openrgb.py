from __future__ import annotations

import asyncio
import copy
import json
from typing import Any

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities, FirmwareRejected, LightReading
from dj_ledfx.types import DeviceInfo

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:
    OpenRGBClient = None
    RGBColor = None

HAS_BRIGHTNESS = 1 << 4  # openrgb.utils.ModeFlags.HAS_BRIGHTNESS
HAS_PER_LED_COLOR = 1 << 5  # openrgb.utils.ModeFlags.HAS_PER_LED_COLOR


class OpenRGBAdapter(DeviceAdapter):
    supports_latency_probing = False

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6742,
        device_index: int = 0,
    ) -> None:
        self._host = host
        self._port = port
        self._device_index = device_index
        self._client: Any = None
        self._device: Any = None
        self._is_connected = False
        self._led_count = 0
        self._device_name = ""
        self._modes: tuple[str, ...] = ()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._device_name or f"OpenRGB:{self._device_index}",
            device_type="openrgb",
            led_count=self._led_count,
            address=f"{self._host}:{self._port}",
            stable_id=f"openrgb:{self._host}:{self._port}:{self._device_index}",
            backend="openrgb",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        def _connect() -> None:
            if OpenRGBClient is None:
                raise ImportError("openrgb-python is not installed")
            client = OpenRGBClient(self._host, self._port)
            if self._device_index >= len(client.devices):
                raise ConnectionError(
                    f"Device index {self._device_index} not found "
                    f"(server has {len(client.devices)} devices)"
                )
            device = client.devices[self._device_index]
            self._client = client
            self._device = device
            self._modes = tuple(str(mode.name) for mode in device.modes)
            self._led_count = len(device.colors)
            self._device_name = getattr(device, "name", f"Device {self._device_index}")

        for attempt in range(2):
            try:
                await asyncio.wait_for(asyncio.to_thread(_connect), timeout=5.0)
                break
            except TimeoutError:
                if attempt == 0:
                    logger.warning(
                        "OpenRGB connection to {}:{} timed out (attempt 1), retrying…",
                        self._host,
                        self._port,
                    )
                else:
                    raise ConnectionError(
                        f"OpenRGB connection to {self._host}:{self._port}"
                        " timed out after 2 attempts"
                    ) from None
        self._is_connected = True
        logger.info(
            "Connected to OpenRGB device '{}' ({} LEDs) at {}:{}",
            self._device_name,
            self._led_count,
            self._host,
            self._port,
        )

    async def disconnect(self) -> None:
        if self._client is not None:

            def _disconnect() -> None:
                self._client.disconnect()

            await asyncio.to_thread(_disconnect)

        self._is_connected = False
        self._client = None
        self._device = None
        logger.info("Disconnected from OpenRGB device '{}'", self._device_name)

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        if not self._is_connected or self._device is None:
            return

        device = self._device
        led_count = self._led_count

        frame = colors[:led_count]

        rgb_colors = [
            RGBColor(int(frame[i, 0]), int(frame[i, 1]), int(frame[i, 2]))
            for i in range(len(frame))
        ]

        def _send() -> None:
            device.set_colors(rgb_colors, fast=True)

        try:
            await asyncio.to_thread(_send)
        except (ConnectionError, OSError):
            self._is_connected = False
            raise
        logger.trace("Sent {} colors to '{}'", len(rgb_colors), self._device_name)

    @property
    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            protocol="OpenRGB", model=self._device_name, openrgb_modes=self._modes
        )

    def _find_mode(self, name: str) -> Any:
        device = self._device
        if device is None:
            return None
        return next((m for m in device.modes if str(m.name).lower() == name.lower()), None)

    async def prepare_stream(self) -> None:
        device = self._device
        direct = self._find_mode("direct")
        if device is not None and direct is not None:
            await asyncio.to_thread(device.set_mode, str(direct.name))

    async def set_mode(self, name: str, brightness: float) -> None:
        """Start one of the device's own modes, scaled to the zone's brightness."""
        device = self._device
        mode = self._find_mode(name)
        if device is None or mode is None:
            raise FirmwareRejected(f"{self._device_name} has no mode '{name}'")
        chosen = copy.copy(mode)
        if int(chosen.flags) & HAS_BRIGHTNESS and chosen.brightness_max is not None:
            low = int(chosen.brightness_min or 0)
            high = int(chosen.brightness_max)
            chosen.brightness = round(low + (high - low) * max(0.0, min(1.0, brightness)))
        try:
            await asyncio.to_thread(device.set_mode, chosen)
        except (ValueError, ConnectionError, OSError) as exc:
            raise FirmwareRejected(f"{self._device_name} refused mode '{name}': {exc}") from exc

    async def _read(self) -> tuple[str, list[tuple[int, int, int]]] | None:
        """The active mode's name and the LED colours, fresh from the server."""
        device = self._device
        if device is None:
            return None

        def _update() -> tuple[str, list[tuple[int, int, int]]]:
            device.update()
            colours = [(int(c.red), int(c.green), int(c.blue)) for c in device.colors]
            return str(device.modes[device.active_mode].name), colours

        try:
            return await asyncio.to_thread(_update)
        except (IndexError, ConnectionError, OSError):
            return None

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
        device = self._device
        try:
            snapshot = json.loads(state)
            mode = self._find_mode(str(snapshot["mode"]))
            colours = [RGBColor(int(r), int(g), int(b)) for r, g, b in snapshot["colors"]]
        except (ValueError, KeyError, TypeError):
            logger.warning("OpenRGB '{}': captured state is unreadable", self._device_name)
            return
        if device is None or mode is None:
            return

        def _restore() -> None:
            device.set_mode(str(mode.name))
            if colours and int(mode.flags) & HAS_PER_LED_COLOR:
                device.set_colors(colours)

        try:
            await asyncio.to_thread(_restore)
        except (ValueError, ConnectionError, OSError):
            logger.warning("OpenRGB '{}': couldn't restore its mode", self._device_name)

    @staticmethod
    async def discover(host: str = "127.0.0.1", port: int = 6742) -> list[DeviceInfo]:
        def _discover() -> list[DeviceInfo]:
            if OpenRGBClient is None:
                return []
            try:
                client = OpenRGBClient(host, port)
                devices = []
                for i, dev in enumerate(client.devices):
                    devices.append(
                        DeviceInfo(
                            name=getattr(dev, "name", f"Device {i}"),
                            device_type="openrgb",
                            led_count=len(dev.colors),
                            address=f"{host}:{port}",
                            stable_id=f"openrgb:{host}:{port}:{i}",
                            backend="openrgb",
                        )
                    )
                client.disconnect()
                return devices
            except Exception:
                logger.debug("OpenRGB discovery failed at {}:{}", host, port)
                return []

        return await asyncio.to_thread(_discover)
