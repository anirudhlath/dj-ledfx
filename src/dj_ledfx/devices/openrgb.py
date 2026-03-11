from __future__ import annotations

import asyncio

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.types import DeviceInfo

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:
    OpenRGBClient = None  # type: ignore[assignment,misc]
    RGBColor = None  # type: ignore[assignment,misc]


class OpenRGBAdapter:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6742,
        device_index: int = 0,
    ) -> None:
        self._host = host
        self._port = port
        self._device_index = device_index
        self._client: object | None = None
        self._device: object | None = None
        self._is_connected = False
        self._led_count = 0
        self._device_name = ""

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._device_name or f"OpenRGB:{self._device_index}",
            device_type="openrgb",
            led_count=self._led_count,
            address=f"{self._host}:{self._port}",
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
            self._led_count = len(device.colors)
            self._device_name = getattr(device, "name", f"Device {self._device_index}")

        await asyncio.to_thread(_connect)
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
                self._client.disconnect()  # type: ignore[union-attr]

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
            device.set_colors(rgb_colors, fast=True)  # type: ignore[union-attr]

        await asyncio.to_thread(_send)
        logger.trace("Sent {} colors to '{}'", len(rgb_colors), self._device_name)
