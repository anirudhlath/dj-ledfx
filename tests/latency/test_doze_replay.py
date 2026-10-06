"""The light-sync spec's §9.2: each recording of four Govee lamps, fed to a tracker in order.
Lamps a and b doze; c and d don't (each light's `expect`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from doze_fakes import SEED_MS, Lamp

from dj_ledfx.latency.strategies import LATENCY_WINDOW, make_strategy

RECORDINGS = Path(__file__).parent.parent / "fixtures" / "latency"
DAYS = ["2026-10-04", "2026-10-05"]


def _lamps(day: str) -> dict[str, Any]:
    recording = json.loads((RECORDINGS / f"doze-replay-{day}.json").read_text())
    lamps: dict[str, Any] = recording["lights"]
    return lamps


@pytest.mark.parametrize("day", DAYS)
def test_a_and_b_turn_dozing_and_stay_dozing_and_c_and_d_never_do(day: str) -> None:
    for label, lamp in _lamps(day).items():
        replayed = Lamp()
        modes: list[bool] = []
        for arrived, rtt_ms in lamp["replies"]:
            replayed.reply(arrived, rtt_ms)
            modes.append(replayed.tracker.dozing)
        if lamp["expect"] == "dozing":
            assert True in modes, label
            turned = modes.index(True)
            assert turned < 20 and all(modes[turned:]), label  # by the 20th, for good
        else:
            assert not any(modes), label


@pytest.mark.parametrize("strategy", ["windowed_median", "windowed_mean", "ema"])
@pytest.mark.parametrize("day", DAYS)
def test_a_dozing_lamp_ends_between_its_round_trips_quartiles(day: str, strategy: str) -> None:
    for label, lamp in _lamps(day).items():
        if lamp["expect"] != "dozing":
            continue
        replayed = Lamp(make_strategy(strategy, SEED_MS, LATENCY_WINDOW))
        for arrived, rtt_ms in lamp["replies"]:
            replayed.reply(arrived, rtt_ms)
        low, high = np.percentile([rtt_ms for _, rtt_ms in lamp["replies"]], [25, 75])
        assert low <= replayed.tracker.link_latency_ms <= high, label
