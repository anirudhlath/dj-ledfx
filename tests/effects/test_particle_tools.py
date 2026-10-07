from __future__ import annotations

import math
import statistics
import time

import numpy as np
import pytest
from map_home import ROW, leds_at, lights_at

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import (
    CEILING_OVER_M,
    GRID_FROM_LEDS,
    MIN_RADIUS_M,
    NO_PARTICLES,
    REACH,
    SAME_STOP_M,
    WANDER_DRAWS,
    Ground,
    _densely,
    arc,
    around,
    draws,
    joined,
    lamps_of,
    lit,
    recent,
    spread_over,
    swarm,
    tour,
    wander,
)
from dj_ledfx.zones.runtime import FRAME_BUDGET_S


def _scattered(count: int, seed: int) -> LedSet:
    """`count` LEDs scattered through a 15 x 15 x 3 m home, as one light."""
    points = np.random.default_rng(seed).uniform((0.0, 0.0, 0.0), (15.0, 15.0, 3.0), (count, 3))
    return lights_at([tuple(point) for point in points])


def test_a_particle_lights_each_led_by_a_gaussian_falloff_out_to_its_reach() -> None:
    ground = Ground.of(leds_at(ROW))  # 0.5 m apart along x
    one = swarm([[0.0, 0.0, 1.0]], [1.0, 0.0, 0.0], 0.5)

    reds = lit(ground, one)[:, 0]

    expected = [
        math.exp(-((d / 0.5) ** 2)) if d <= REACH * 0.5 else 0.0 for d in np.arange(9) * 0.5
    ]
    np.testing.assert_allclose(reds, expected, atol=1e-6)
    assert reds[2] > 0.0 and reds[3] == 0.0  # 1 m is two radii; 1.5 m is past REACH


def test_light_adds_up_and_stays_at_most_1() -> None:
    ground = Ground.of(leds_at(ROW))
    two = swarm([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]], [0.6, 0.6, 0.6], 0.5)

    frame = lit(ground, two)

    assert frame.dtype == np.float32
    np.testing.assert_allclose(frame[0], 1.0)  # 1.2, held at 1
    np.testing.assert_allclose(frame[1], 1.2 * math.exp(-1.0), rtol=1e-5)


def test_no_particles_or_no_leds_light_nothing() -> None:
    ground = Ground.of(leds_at(ROW))
    assert not lit(ground, NO_PARTICLES).any()
    empty = Ground.of(lights_at())
    assert lit(empty, swarm([[0.0, 0.0, 0.0]], [1.0, 1.0, 1.0], 1.0)).shape == (0, 3)


def test_a_radius_is_never_below_the_floor() -> None:
    particles = swarm([[0.0, 0.0, 0.0]], [1.0, 1.0, 1.0], 0.0)
    assert particles.radius[0] == pytest.approx(MIN_RADIUS_M)
    assert np.isfinite(lit(Ground.of(leds_at(ROW)), particles)).all()


# Spec §4.1: past about 2k LEDs, particles switch to a spatial grid. It must light the
# LEDs as the dense sum would, particles outside the frame and of every size included.
def test_the_grid_lights_the_leds_as_every_led_against_every_particle_does() -> None:
    ground = Ground.of(_scattered(GRID_FROM_LEDS + 500, seed=1))
    rng = np.random.default_rng(2)
    particles = swarm(
        rng.uniform((-2.0, -2.0, -1.0), (17.0, 17.0, 4.0), (300, 3)),
        rng.uniform(0.0, 1.0, (300, 3)),
        rng.uniform(0.05, 0.6, 300),
    )

    by_grid = lit(ground, particles)
    dense = np.zeros_like(by_grid)
    _densely(ground, particles, dense)

    assert by_grid.any()
    np.testing.assert_allclose(by_grid, np.minimum(dense, 1.0), atol=1e-4)


def test_the_grid_lights_a_few_far_larger_particles_as_the_dense_sum_does() -> None:
    ground = Ground.of(_scattered(GRID_FROM_LEDS, seed=4))
    rng = np.random.default_rng(5)
    small = swarm(rng.uniform(0.0, 15.0, (200, 3)), rng.uniform(0.0, 1.0, (200, 3)), 0.2)
    large = swarm(rng.uniform(0.0, 15.0, (3, 3)), rng.uniform(0.0, 1.0, (3, 3)), [2.0, 2.5, 3.0])
    particles = joined(small, large)

    dense = np.zeros((ground.leds.count, 3), dtype=np.float32)
    _densely(ground, particles, dense)

    np.testing.assert_allclose(lit(ground, particles), np.minimum(dense, 1.0), atol=1e-4)


def test_a_ground_keeps_a_few_grids_and_reuses_one_for_close_sizes() -> None:
    ground = Ground.of(_scattered(100, seed=3))

    assert ground.grid(0.9) is ground.grid(0.95)  # one size in √2 steps: 2^(1/2) m
    for size in np.linspace(0.05, 20.0, 40):
        ground.grid(float(size))
    assert len(ground._grids) <= 8


def test_draws_repeat_for_a_seed_and_key_and_differ_for_another() -> None:
    first = draws(7, [1, 2, 3], 4)
    assert first.shape == (3, 4)
    np.testing.assert_array_equal(first, draws(7, [1, 2, 3], 4))
    np.testing.assert_array_equal(first[1:2], draws(7, [2], 4))  # each key on its own
    assert not np.array_equal(first, draws(8, [1, 2, 3], 4))
    assert not np.array_equal(first[0], first[1])
    many = draws(7, np.arange(-5000, 5000), 2)  # negative keys too
    assert many.min() >= 0.0 and many.max() < 1.0
    assert abs(float(many.mean()) - 0.5) < 0.01


def test_each_stream_draws_its_own_numbers() -> None:
    assert not np.array_equal(draws(7, [1, 2], 3), draws(7, [1, 2], 3, stream=1))
    np.testing.assert_array_equal(draws(7, [1, 2], 3, stream=1), draws(7, [1, 2], 3, stream=1))


def test_recent_events_hold_every_event_alive_now() -> None:
    every, life = 0.5, 1.2
    for now in (0.0, 3.1, 10.3, 1e6 + 0.25):
        events = set(recent(now, every, life).tolist())
        for n in range(math.floor(now / every) - 10, math.floor(now / every) + 10):
            for u in (0.0, 0.5, 0.999):  # event n comes at (n + u) * every
                if (n + u) * every <= now < (n + u) * every + life:
                    assert n in events
        assert len(events) <= life / every + 3


def test_wanderers_stay_in_their_box_and_move_smoothly() -> None:
    u = draws(3, np.arange(20), WANDER_DRAWS)
    low, high = np.array([0.0, 1.0, 0.5]), np.array([4.0, 3.0, 2.5])
    speed = 0.5
    times = 1000.0 + np.arange(600) / 60  # ten seconds at 60 frames a second
    path = np.array([wander(u, float(t), speed, low, high) for t in times])  # (T, 20, 3)

    assert (path >= low - 1e-9).all() and (path <= high + 1e-9).all()
    steps = np.linalg.norm(np.diff(path, axis=0), axis=2)
    assert steps.max() <= 1.4 * speed * math.sqrt(3.0) / 60  # never a jump
    assert np.ptp(path[:, :, 0], axis=0).min() > 0.1  # each of them moves
    assert len({tuple(p) for p in np.round(path[0], 3)}) == 20  # each where it alone is


def test_each_wanderer_keeps_to_a_box_of_its_own() -> None:
    u = draws(5, np.arange(3), WANDER_DRAWS)
    low = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0]])
    for t in np.arange(0.0, 60.0, 0.5):
        where = wander(u, float(t), 1.0, low, low + 1.0)
        assert (where >= low - 1e-9).all() and (where <= low + 1.0 + 1e-9).all()


def test_a_wanderer_in_a_flat_box_keeps_to_it() -> None:
    u = draws(4, np.arange(5), WANDER_DRAWS)
    where = wander(u, 50.0, 0.3, [1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    np.testing.assert_allclose(where, 1.0, atol=0.05 + 1e-9)


def test_an_arc_goes_from_start_to_end_rising_half_way() -> None:
    start, end = np.array([[0.0, 0.0, 1.0]]), np.array([[2.0, 0.0, 1.0]])
    np.testing.assert_allclose(arc(start, end, [0.0], 0.5), start)
    np.testing.assert_allclose(arc(start, end, [1.0], 0.5), end)
    np.testing.assert_allclose(arc(start, end, [0.5], 0.5), [[1.0, 0.0, 1.5]])
    many = arc(start, end, np.linspace(0.0, 1.0, 5), 0.5)
    assert many.shape == (5, 3) and many[:, 2].max() == 1.5


def test_a_tour_visits_every_stop_each_round_and_never_stays() -> None:
    for stops in (3, 5, 11):
        visits = [tour(1, 0, step, stops) for step in range(-stops, 12 * stops)]
        assert all(a != b for a, b in zip(visits, visits[1:], strict=False))
        for start in range(0, len(visits), stops):
            assert sorted(visits[start : start + stops]) == list(range(stops))
    assert [tour(1, 0, step, 2) for step in range(4)] == [0, 1, 0, 1]
    assert {tour(1, 0, step, 1) for step in range(4)} == {0}
    tours = [[tour(1, key, step, 5) for step in range(10)] for key in range(3)]
    assert tours[0] != tours[1] != tours[2]  # each tour its own


def test_things_spread_over_every_stop_before_any_takes_two() -> None:
    taken = spread_over(1, 12, 5)
    assert sorted(taken[:5].tolist()) == list(range(5))
    assert np.bincount(taken, minlength=5).tolist().count(3) == 2  # 12 over 5: 3, 3, 2, 2, 2
    assert spread_over(1, 3, 1).tolist() == [0, 0, 0]
    assert not np.array_equal(spread_over(1, 5, 5), spread_over(2, 5, 5))


def test_each_light_is_a_stop_at_its_middle_with_its_lowest_and_highest_led() -> None:
    lamps = lamps_of(lights_at([(1.0, 1.0, 0.1), (1.0, 1.0, 1.5)], [(4.0, 2.0, 1.0)]))

    assert lamps.count == 2
    np.testing.assert_allclose(lamps.centre, [[1.0, 1.0, 0.8], [4.0, 2.0, 1.0]], atol=1e-6)
    np.testing.assert_allclose(lamps.low, [0.1, 1.0])
    np.testing.assert_allclose(lamps.high, [1.5, 1.0])
    assert lamps.members.tolist() == [0, 1, 2] and lamps.starts.tolist() == [0, 2, 3]


def test_a_stop_and_an_led_of_it_are_picked_alike() -> None:
    ground = Ground.of(lights_at([(0.0, 0.0, 1.0), (1.0, 0.0, 1.0)], [(5.0, 0.0, 1.0)]))
    lamps = ground.lamps

    assert lamps.pick([0.0, 0.49, 0.5, 0.999]).tolist() == [0, 0, 1, 1]
    assert lamps.led([0, 0, 1], [0.2, 0.7, 0.9]).tolist() == [0, 1, 2]
    np.testing.assert_allclose(ground.on([0, 1], [0.7, 0.0]), [[1.0, 0.0, 1.0], [5.0, 0.0, 1.0]])


def test_a_foot_is_under_an_led_at_its_lamps_lowest() -> None:
    ground = Ground.of(lights_at([(1.0, 1.0, 0.1), (1.0, 1.0, 1.5)], [(3.0, 0.0, 2.0)]))
    np.testing.assert_allclose(
        ground.foot([0, 0, 1], [0.9, 0.1, 0.5]), [[1.0, 1.0, 0.1]] * 2 + [[3.0, 0.0, 2.0]]
    )
    np.testing.assert_allclose(ground.foot(0, 0.9), [1.0, 1.0, 0.1])


def test_lights_at_one_spot_make_one_stop() -> None:
    near = SAME_STOP_M * 0.5
    parts = [[(2.0, 2.0, 0.8)], [(2.0 + near, 2.0, 0.9)], [(2.0, 2.0, 1.1)], [(6.0, 2.0, 1.0)]]

    lamps = lamps_of(lights_at(*parts))

    assert lamps.count == 2  # a device's parts share its placement: one stop
    np.testing.assert_allclose(lamps.low, [0.8, 1.0])
    np.testing.assert_allclose(lamps.high, [1.1, 1.0])
    assert lamps.members.tolist() == [0, 1, 2, 3] and lamps.starts.tolist() == [0, 3, 4]


def test_a_zone_with_no_leds_has_no_lamps() -> None:
    assert lamps_of(lights_at()).count == 0
    assert Ground.of(lights_at()).lamps.count == 0


def test_around_goes_round_the_middle() -> None:
    points = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]])
    assert list(around(points.astype(np.float32), np.zeros(3))) == [2, 1, 0, 3]


def test_the_floor_and_ceiling_are_the_maps_or_else_the_leds() -> None:
    lights = ([(1.0, 1.0, 0.5), (1.0, 1.0, 1.5)],)
    mapped = Ground.of(lights_at(*lights, ceiling=3.0))
    unmapped = Ground.of(lights_at(*lights, ceiling=None))

    assert (mapped.floor, mapped.ceiling) == (0.0, 3.0)
    assert (unmapped.floor, unmapped.ceiling) == pytest.approx((0.5, 1.5 + CEILING_OVER_M))


def test_a_box_is_the_frame_widened_and_kept_between_the_floor_and_ceiling() -> None:
    ground = Ground.of(lights_at([(1.0, 2.0, 0.2), (3.0, 4.0, 2.8)], ceiling=3.0))

    low, high = ground.box(0.5)

    np.testing.assert_allclose(low, [0.5, 1.5, 0.0])  # not below the floor
    np.testing.assert_allclose(high, [3.5, 4.5, 3.0])  # nor over the ceiling
    np.testing.assert_allclose(ground.box()[0], [1.0, 2.0, 0.2], atol=1e-6)
    low, high = ground.box(1.5, around=[2.0, 2.0, 2.0])
    np.testing.assert_allclose(low, [0.5, 0.5, 0.5])
    np.testing.assert_allclose(high, [3.5, 3.5, 3.0])
    low, high = ground.box(1.0, around=[[2.0, 2.0, 0.5], [5.0, 5.0, 2.5]])
    np.testing.assert_allclose(low, [[1.0, 1.0, 0.0], [4.0, 4.0, 1.5]])
    np.testing.assert_allclose(high, [[3.0, 3.0, 1.5], [6.0, 6.0, 3.0]])


def test_newest_keeps_the_last_particles() -> None:
    particles = swarm(np.arange(15.0).reshape(5, 3), [1.0, 1.0, 1.0], 0.2)
    newest = particles.newest(2)
    np.testing.assert_array_equal(newest.pos, particles.pos[3:])
    assert particles.newest(9) is particles


def test_joined_keeps_each_swarm_in_order_and_pick_keeps_the_marked() -> None:
    first = swarm([[0.0, 0.0, 0.0]], [1.0, 0.0, 0.0], 0.1)
    second = swarm([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], [0.0, 1.0, 0.0], [0.2, 0.3])
    both = joined(first, second)

    np.testing.assert_array_equal(both.pos[:, 0], [0.0, 1.0, 2.0])
    np.testing.assert_allclose(both.radius, [0.1, 0.2, 0.3])
    picked = both.pick(np.array([True, False, True]))
    np.testing.assert_array_equal(picked.pos[:, 0], [0.0, 2.0])
    np.testing.assert_array_equal(picked.colour, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


# Spec §4.1's budget past 2k LEDs: 500 particles of a usual size on 10k LEDs, by the grid.
@pytest.mark.perf
def test_500_particles_light_10k_leds_in_the_frame_budget() -> None:
    ground = Ground.of(_scattered(10_000, seed=6))
    rng = np.random.default_rng(7)
    particles = swarm(rng.uniform(0.0, 15.0, (500, 3)), rng.uniform(0.0, 1.0, (500, 3)), 0.2)
    lit(ground, particles)  # the grid is made once for each size
    durations = []
    for _ in range(60):
        started = time.perf_counter()
        lit(ground, particles)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < FRAME_BUDGET_S
