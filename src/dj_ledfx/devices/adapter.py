from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.types import DeviceInfo


class DeviceAdapter(Protocol):
    @property
    def device_info(self) -> DeviceInfo: ...

    @property
    def is_connected(self) -> bool: ...

    @property
    def led_count(self) -> int: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def send_frame(self, colors: NDArray[np.uint8]) -> None: ...
