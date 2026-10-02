"""How a Govee lamp plays: its segments, razer or one colour, and its rate."""

from __future__ import annotations

import pytest
from govee_fakes import NO_RAZER, UPRIGHT
from loguru import logger

from dj_ledfx.config import GOVEE_COLOUR_FPS, GOVEE_RAZER_FPS
from dj_ledfx.devices.govee.output import (
    MAX_SEGMENTS,
    MIN_SEGMENTS,
    GoveeOutput,
    LampPlan,
    lamp_fps,
    lamp_plan,
)
from dj_ledfx.devices.govee.types import GoveeDeviceCapability

PLAIN = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


@pytest.mark.parametrize(
    ("capability", "output", "override", "plan"),
    [
        (UPRIGHT, GoveeOutput(), None, LampPlan(15, razer=True)),
        (NO_RAZER, GoveeOutput(), None, LampPlan(15, razer=False)),
        (UPRIGHT, GoveeOutput(), 10, LampPlan(10, razer=True)),
        (PLAIN, GoveeOutput(), 10, LampPlan(1, razer=False)),  # the override is for RGBIC
        (UPRIGHT, GoveeOutput(), MIN_SEGMENTS, LampPlan(MIN_SEGMENTS, razer=True)),
        (UPRIGHT, GoveeOutput(), MAX_SEGMENTS, LampPlan(MAX_SEGMENTS, razer=True)),
        (UPRIGHT, GoveeOutput(mode="colour"), None, LampPlan(15, razer=False)),
        (NO_RAZER, GoveeOutput(mode="segments", segments=20), 10, LampPlan(20, razer=True)),
        (PLAIN, GoveeOutput(mode="segments"), None, LampPlan(1, razer=False)),  # none to light
    ],
)
def test_a_lamp_s_own_output_then_the_config_then_the_table(
    capability: GoveeDeviceCapability, output: GoveeOutput, override: int | None, plan: LampPlan
) -> None:
    assert lamp_plan(capability, output, override) == plan


@pytest.mark.parametrize("override", [300, MAX_SEGMENTS + 1, MIN_SEGMENTS - 1, 0])
def test_a_segment_override_no_lamp_plays_is_ignored_with_a_warning(override: int) -> None:
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        plan = lamp_plan(UPRIGHT, GoveeOutput(), override)
    finally:
        logger.remove(sink)
    assert plan == LampPlan(15, razer=True)  # the table's
    assert len(warnings) == 1 and "segment_override" in warnings[0]


def test_a_plan_names_its_mode() -> None:
    assert (LampPlan(15, razer=True).mode, LampPlan(15, razer=False).mode) == (
        "segments",
        "colour",
    )


def test_razer_streams_at_the_configured_rate_and_one_colour_at_ten_at_most() -> None:
    assert lamp_fps(LampPlan(15, razer=True), GOVEE_RAZER_FPS) == GOVEE_RAZER_FPS
    assert lamp_fps(LampPlan(15, razer=False), GOVEE_RAZER_FPS) == GOVEE_COLOUR_FPS
    assert lamp_fps(LampPlan(1, razer=False), 5) == 5


@pytest.mark.parametrize(
    ("extra", "output"),
    [
        (None, GoveeOutput()),
        ('{"output": {"mode": "colour", "segments": 10}}', GoveeOutput("colour", 10)),
        ('{"output": {"segments": 20}, "other": 1}', GoveeOutput(segments=20)),
        ('{"output": {"mode": "rainbow", "segments": 1}}', GoveeOutput()),
        ('{"output": {"segments": 256}}', GoveeOutput()),
        ('{"output": {"segments": true}}', GoveeOutput()),
        ('{"output": "colour"}', GoveeOutput()),
        ("[1, 2]", GoveeOutput()),
        ("not JSON", GoveeOutput()),
    ],
)
def test_a_stored_output_is_read_as_far_as_it_can_be_used(
    extra: str | None, output: GoveeOutput
) -> None:
    assert GoveeOutput.from_extra(extra) == output


def test_an_output_is_stored_without_its_unset_parts() -> None:
    assert GoveeOutput().to_extra() is None
    assert GoveeOutput(mode="colour").to_extra() == {"mode": "colour"}
    assert GoveeOutput("segments", 10).to_extra() == {"mode": "segments", "segments": 10}
