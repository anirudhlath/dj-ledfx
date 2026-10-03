"""How a Govee lamp plays (the light-output plan's rulings 10 and 13): razer segments or
one colour, how many segments, and how many frames a second. A lamp's own output comes
first, then the config's segment override, then the SKU table."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, get_args

from loguru import logger

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import MAX_RAZER_SEGMENTS
from dj_ledfx.devices.govee.sku_registry import get_device_capability
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

if TYPE_CHECKING:
    from dj_ledfx.devices.adapter import DeviceAdapter

GoveeMode = Literal["segments", "colour"]  # razer, one colour per segment; or colorwc
MODES: tuple[GoveeMode, ...] = get_args(GoveeMode)
OUTPUT_KEY = "output"  # where a lamp's own output sits in its device row's extra (JSON)
MIN_SEGMENTS = 2  # fewer has no segments to light: the lamp plays one colour
MAX_SEGMENTS = MAX_RAZER_SEGMENTS  # razer's limit; one colour keeps to it too


def _segment_count(value: object) -> int | None:
    """A segment count a lamp can use, or None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if MIN_SEGMENTS <= value <= MAX_SEGMENTS else None


@dataclass(frozen=True, slots=True)
class GoveeOutput:
    """A lamp's own output. None leaves that part to the config and the SKU table."""

    mode: GoveeMode | None = None
    segments: int | None = None

    @classmethod
    def from_extra(cls, extra: str | None) -> GoveeOutput:
        """The output kept in a device row's extra. What it can't use (JSON it can't read,
        a mode or a segment count no lamp plays) is left to the config and the table."""
        try:
            stored = json.loads(extra) if extra else None
        except ValueError:
            return cls()
        output = stored.get(OUTPUT_KEY) if isinstance(stored, dict) else None
        if not isinstance(output, dict):
            return cls()
        mode = output.get("mode")
        return cls(
            mode=mode if mode in MODES else None,
            segments=_segment_count(output.get("segments")),
        )

    def to_extra(self) -> dict[str, Any] | None:
        """What goes under extra's OUTPUT_KEY: None when the lamp has no output of its own."""
        stored = {"mode": self.mode, "segments": self.segments}
        return {key: value for key, value in stored.items() if value is not None} or None


@dataclass(frozen=True, slots=True)
class LampPlan:
    segments: int  # 1: a lamp of one segment, which plays one colour
    razer: bool

    @property
    def mode(self) -> GoveeMode:
        return "segments" if self.razer else "colour"


def lamp_plan(
    capability: GoveeDeviceCapability, output: GoveeOutput, segment_override: int | None
) -> LampPlan:
    """The lamp's segments (its own count, else the config's override for an RGBIC lamp,
    else the table's) and whether it plays razer (its own mode, else the table's). Fewer
    than MIN_SEGMENTS plays one colour. An override no lamp plays is ignored, with a
    warning, as a stored count is."""
    override = _segment_count(segment_override)
    if segment_override is not None and override is None:
        logger.warning(
            "Govee segment_override {} isn't {} to {}: ignored",
            segment_override,
            MIN_SEGMENTS,
            MAX_SEGMENTS,
        )
    if output.segments is not None:
        segments = output.segments
    elif override is not None and capability.is_rgbic:
        segments = override
    else:
        segments = capability.segment_count
    if segments < MIN_SEGMENTS:
        return LampPlan(1, razer=False)
    razer = capability.razer if output.mode is None else output.mode == "segments"
    return LampPlan(segments, razer)


def planned(row: Mapping[str, Any], segment_override: int | None) -> LampPlan:
    """How a lamp will play when it's set up from its device row: its own output, the
    config's override and its model's entry in the SKU table."""
    capability = get_device_capability(row.get("sku") or "")
    return lamp_plan(capability, GoveeOutput.from_extra(row.get("extra")), segment_override)


@dataclass(frozen=True, slots=True)
class LampOutputReport:
    """A lamp's own output, and how it plays: as its live adapter plays while it's online,
    else as it will be set up from its row when a scan finds it."""

    light_id: str
    own: GoveeOutput
    plays: LampPlan
    online: bool


def lamp_report(
    row: Mapping[str, Any], live: DeviceAdapter | None, segment_override: int | None
) -> LampOutputReport:
    """The report for a lamp's row; live is its adapter while it's online, else None."""
    if isinstance(live, GoveeAdapterBase):
        plays = LampPlan(live.led_count, razer=live.razer)
    else:
        plays = planned(row, segment_override)
    own = GoveeOutput.from_extra(row.get("extra"))
    return LampOutputReport(light_id=row["id"], own=own, plays=plays, online=live is not None)
