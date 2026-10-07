from __future__ import annotations

from collections.abc import Iterable
from itertools import pairwise

import pytest
from doze_fakes import START, bunched, half_bunched, on_beat, random_moments, spread

from dj_ledfx.latency.doze import (
    BEACON_S,
    DOZE_Z,
    KEPT,
    STAY_Z,
    DozeCheck,
    rayleigh_z,
)


def fed(check: DozeCheck, arrivals: Iterable[float], rtt_ms: float) -> list[bool]:
    """Whether the check calls the light dozing after each reply, each `add` saying whether
    the reply changed the mode."""
    modes: list[bool] = []
    for arrived in arrivals:
        was = check.dozing
        changed = check.add(arrived, rtt_ms)
        assert changed is (check.dozing != was)
        modes.append(check.dozing)
    return modes


def test_z_is_n_at_one_phase_and_near_0_for_phases_spread_evenly() -> None:
    assert rayleigh_z([START + BEACON_S * k for k in range(12)]) == pytest.approx(12.0)
    evenly = [START + BEACON_S * (k + k / 12) for k in range(12)]  # a twelfth further each
    assert rayleigh_z(evenly) == pytest.approx(0.0, abs=1e-9)
    assert rayleigh_z([]) == 0.0


def test_replies_bunched_at_the_wakes_with_a_60_ms_median_are_dozing_at_the_10th() -> None:
    check = DozeCheck()
    assert fed(check, map(bunched, range(12)), 60.0) == [False] * 9 + [True] * 3
    reading = check.reading()
    assert reading is not None
    assert reading.z >= DOZE_Z and reading.median_ms == 60.0 and reading.replies == 12


def test_replies_bunched_at_every_second_beacon_are_dozing_too() -> None:
    every_other = [START + 2 * BEACON_S * 3 * k for k in range(10)]  # 204.8 ms wakes
    assert fed(DozeCheck(), every_other, 60.0) == [False] * 9 + [True]


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_replies_at_random_moments_are_awake(seed: int) -> None:
    assert not any(fed(DozeCheck(), random_moments(seed), 60.0))


def test_replies_spread_round_the_cycle_are_awake() -> None:
    assert not any(fed(DozeCheck(), map(spread, range(KEPT)), 300.0))


def test_bunched_replies_with_a_25_ms_median_are_awake() -> None:
    assert not any(fed(DozeCheck(), map(bunched, range(KEPT)), 25.0))


def test_a_slow_awake_light_is_now_and_then_called_dozing_and_a_quicker_one_never() -> None:
    """Random replies bunch past DOZE_Z now and then, and an awake light whose median round
    trip is 50 ms or more passes the median's test, so it's called dozing for some seconds
    (spec §10: over 200 simulated hours at a 60 ms median, about 3.3 times an hour, about
    1% of the time). Ten hours of replies 0.375–0.625 s apart at random, as the Govee probe
    loop's waits put them: a light at 60 ms is called dozing 33 times, 0.98% of the time,
    which the caps allow with headroom, and one at 45 ms never. Without the median's guard
    the 45 ms light turns too; turning at STAY_Z, the 60 ms light dozes about a fifth of the
    time, and staying only above DOZE_Z, it turns 52 times."""
    moments = random_moments(10, count=72_000)
    slow, quick = DozeCheck(), DozeCheck()
    turns, dozing_s = 0, 0.0
    for arrived, following in pairwise(moments):
        was = slow.dozing
        slow.add(arrived, 60.0)
        quick.add(arrived, 45.0)
        assert not quick.dozing
        turns += slow.dozing and not was
        if slow.dozing:
            dozing_s += following - arrived
    span_s = moments[-1] - moments[0]
    assert 9.9 * 3600 < span_s < 10.1 * 3600
    assert 0 < turns <= 40  # 4 an hour
    assert dozing_s / span_s <= 0.015


def test_a_dozing_light_stays_dozing_while_z_is_at_least_2() -> None:
    """Ten to 20 replies half at the wakes bunch less than an awake light needs to turn
    dozing, and as much as a dozing light needs to stay dozing. Their z grows at about n/4,
    so from about 27 they turn an awake light dozing."""
    arrivals = [half_bunched(k) for k in range(20)]
    zs = [rayleigh_z(arrivals[:n]) for n in range(10, 21)]
    assert all(STAY_Z <= z < DOZE_Z for z in zs)
    assert not any(fed(DozeCheck(), arrivals, 60.0))  # an awake light stays awake
    assert all(fed(DozeCheck(dozing=True), arrivals, 60.0))  # and a dozing one dozing


def test_a_dozing_light_turns_awake_when_its_median_drops_under_50_ms() -> None:
    check = DozeCheck()
    assert fed(check, map(on_beat, range(20)), 60.0)[-1]
    quicker = fed(check, map(on_beat, range(20, 40)), 20.0)  # bunched as much as before
    assert quicker == [True] * 19 + [False]  # 20 of its 40 at 20 ms: a median of 40 ms
    assert all(fed(DozeCheck(dozing=True), map(on_beat, range(KEPT)), 50.0))  # 50 isn't under


def test_a_dozing_light_turns_awake_when_its_replies_stop_bunching() -> None:
    check = DozeCheck()
    assert fed(check, map(on_beat, range(20)), 60.0)[-1]
    later = fed(check, map(spread, range(20, 60)), 60.0)
    turned = later.index(False)
    assert turned > 10 and not any(later[turned:])  # it stays awake
    reading = check.reading()
    assert reading is not None and reading.z < STAY_Z


def test_the_check_reads_nothing_under_10_round_trips_and_holds_the_last_40() -> None:
    check = DozeCheck(dozing=True)
    for k in range(9):
        assert check.add(spread(k), 30.0) is False
    assert check.reading() is None and check.dozing  # too few to change the mode
    for k in range(9, 50):
        check.add(spread(k), float(k))
    assert check.round_trips == [float(k) for k in range(10, 50)]
    reading = check.reading()
    assert reading is not None and reading.replies == KEPT
