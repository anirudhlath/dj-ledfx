from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GoveeDeviceState:
    """A Govee lamp as captured, to put it back. On a white its colour means nothing (black
    from one lamp, white from another): the white is its colour temperature, `kelvin`."""

    on_off: int  # 0 or 1
    brightness: int  # 0-100
    r: int
    g: int
    b: int
    kelvin: int = 0  # 0: the lamp shows its colour

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "onOff": self.on_off,
                "brightness": self.brightness,
                "color": {"r": self.r, "g": self.g, "b": self.b},
                "colorTemInKelvin": self.kelvin,
            }
        ).encode("utf-8")

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> GoveeDeviceState:
        color = d.get("color", {})
        return cls(
            on_off=d.get("onOff", 1),
            brightness=d.get("brightness", 100),
            r=color.get("r", 255),
            g=color.get("g", 255),
            b=color.get("b", 255),
            kelvin=d.get("colorTemInKelvin", 0),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> GoveeDeviceState:
        return cls._from_dict(json.loads(data))

    @classmethod
    def from_status(cls, status: dict[str, Any]) -> GoveeDeviceState:
        return cls._from_dict(status)
