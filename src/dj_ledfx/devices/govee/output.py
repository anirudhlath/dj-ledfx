"""How a Govee lamp plays (the light-output plan's rulings 10 and 13): razer segments or
one colour, how many segments, and how many frames a second. A lamp's own output comes
first, then the config's segment override, then the SKU table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dj_ledfx.config import GOVEE_COLOUR_FPS
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

GoveeMode = Literal["segments", "colour"]  # razer, one colour per segment; or colorwc


@dataclass(frozen=True, slots=True)
class GoveeOutput:
    """A lamp's own output. None leaves that part to the config and the SKU table."""

    mode: GoveeMode | None = None
    segments: int | None = None


@dataclass(frozen=True, slots=True)
class LampPlan:
    segments: int  # 1: one colour, through the solid adapter
    razer: bool


def lamp_plan(
    capability: GoveeDeviceCapability, output: GoveeOutput, segment_override: int | None
) -> LampPlan:
    """The lamp's segments (its own count, else the config's override for an RGBIC lamp,
    else the table's) and whether it plays razer (its own mode, else the table's). Fewer
    than two segments plays one colour."""
    if output.segments is not None:
        segments = output.segments
    elif segment_override is not None and capability.is_rgbic:
        segments = segment_override
    else:
        segments = capability.segment_count
    if segments < 2:
        return LampPlan(1, razer=False)
    razer = capability.razer if output.mode is None else output.mode == "segments"
    return LampPlan(segments, razer)


def lamp_fps(plan: LampPlan, max_fps: int) -> int:
    """Razer at the configured rate; one colour at GOVEE_COLOUR_FPS at most."""
    return max_fps if plan.razer else min(max_fps, GOVEE_COLOUR_FPS)
