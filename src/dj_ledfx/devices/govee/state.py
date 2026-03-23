from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GoveeDeviceState:
    """Captured state of a Govee device for restore on transport stop."""

    on_off: int  # 0 or 1
    brightness: int  # 0-100
    r: int
    g: int
    b: int

    def to_bytes(self) -> bytes:
        return json.dumps({
            "onOff": self.on_off,
            "brightness": self.brightness,
            "color": {"r": self.r, "g": self.g, "b": self.b},
        }).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> GoveeDeviceState:
        d = json.loads(data)
        color = d.get("color", {})
        return cls(
            on_off=d.get("onOff", 1),
            brightness=d.get("brightness", 100),
            r=color.get("r", 255),
            g=color.get("g", 255),
            b=color.get("b", 255),
        )

    @classmethod
    def from_status(cls, status: dict[str, Any]) -> GoveeDeviceState:
        color = status.get("color", {})
        return cls(
            on_off=status.get("onOff", 1),
            brightness=status.get("brightness", 100),
            r=color.get("r", 255),
            g=color.get("g", 255),
            b=color.get("b", 255),
        )
