from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import bulbs, lights_at, upright
from stray_lamps import (
    STRAYS,
    moves,
    on_the_beat,
    run_frames,
    run_places,
    stays_in_band,
    unpassed,
)

from dj_ledfx.effects import fountain as fountain_module
from dj_ledfx.effects import particle_tools
from dj_ledfx.effects.fountain import BURST_UP, GRAVITY, Fountain
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import F64, Ground, Particles
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn

ANCHOR_ID = "anchor-a"
ANCHOR = np.array([2.0, 2.0, 0.45], dtype=np.float32)


def _room(anchor: np.ndarray = ANCHOR) -> LedSet:
    """Four upright lamps round a 4 x 4 m room under a 3 m ceiling, with an anchor (in its
    middle, 0.45 m up, unless it is put elsewhere)."""
    corners = (upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))
    return lights_at(*corners, anchors={ANCHOR_ID: anchor})


def _fountain(**settings: object) -> Fountain:
    fountain = Fountain(anchor=ANCHOR_ID, **settings)
    fountain.reseed(1)
    return fountain


def _spray(fountain: Fountain, seconds: float = 4.0, room: LedSet | None = None) -> np.ndarray:
    """Every drop's place over some seconds at 120 BPM, 30 times a second."""
    leds = _room() if room is None else room
    seen = []
    for step in range(int(seconds * 30)):
        drawn(fountain, tempo_ctx(2000.0 + step / 15), leds)
        seen.append(fountain.particles.pos)
    return np.concatenate(seen)


def _watched(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[tuple[Particles, F64], ...]]:
    """The spray's and the bursts' particles and birth times that each frame merges, kept in
    a list that grows as the fountain draws."""
    seen: list[tuple[tuple[Particles, F64], ...]] = []

    def merging(*parts: tuple[Particles, F64]) -> Particles:
        seen.append(parts)
        return particle_tools.in_birth_order(*parts)

    monkeypatch.setattr(fountain_module, "in_birth_order", merging)
    return seen


def _burst_drops(
    monkeypatch: pytest.MonkeyPatch, leds: LedSet, frames: int = 192, **settings: object
) -> tuple[np.ndarray, np.ndarray]:
    """Every drop of the bursts over a run seen sixteen times a beat (12 beats): where it is
    (N, 3), and the beats since it was thrown (N,), so that a test can set aside a drop's first
    instant, when it is at the anchor whatever its arc."""
    fountain = _fountain(**settings)
    seen = _watched(monkeypatch)
    places, since = [], []
    for step in range(frames):
        ctx = tempo_ctx(2000.0 + step / 16)
        drawn(fountain, ctx, leds)
        drops, thrown = seen[-1][1]  # the bursts' part of the merge
        places.append(drops.pos.astype(np.float64))
        since.append((ctx.t - thrown) * ctx.bpm / 60.0)
    return np.concatenate(places), np.concatenate(since)


def test_the_spray_rises_to_its_height_and_never_falls_under_the_floor() -> None:
    where = _spray(_fountain(burst=0, height_m=1.2))
    assert where[:, 2].min() >= 0.0
    assert 0.85**2 * 1.2 < where[:, 2].max() - ANCHOR[2] <= 1.2 + 1e-4


def test_the_spray_comes_down_within_its_spread() -> None:
    where = _spray(_fountain(burst=0, spread_m=1.5))
    above = where[where[:, 2] >= ANCHOR[2]]  # before a drop falls past the anchor
    away = np.linalg.norm(above[:, :2] - ANCHOR[:2], axis=1)
    assert away.max() <= 1.5 + 1e-4
    assert away.max() > 1.0
    np.testing.assert_allclose(where[:, :2].mean(axis=0), ANCHOR[:2], atol=0.3)


def test_every_beat_fires_a_burst_of_drops() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=40)
    drawn(fountain, tempo_ctx(2000.999), room)
    before = fountain.particles.count
    drawn(fountain, tempo_ctx(2001.001), room)
    assert fountain.particles.count - before in (39, 40, 41)  # a spray drop may come or go


def test_a_burst_goes_higher_than_the_spray() -> None:
    sprayed = _spray(_fountain(burst=0))[:, 2].max()
    burst = _spray(_fountain(rate=5.0, burst=60))[:, 2].max()
    assert burst > sprayed + 0.3


def test_a_bursts_drops_land_on_leds_on_the_next_beat() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=8)
    drawn(fountain, tempo_ctx(2001.0), room)
    pos = fountain.particles.pos
    gaps = np.linalg.norm(pos[:, None, :] - room.pos[None, :, :], axis=2).min(axis=1)
    assert (gaps < 1e-4).sum() == 8  # beat 2000's burst, on its LEDs
    # Oldest first: the spray drops thrown since beat 2000's burst come before beat 2001's.
    np.testing.assert_allclose(pos[-8:], np.repeat([ANCHOR], 8, axis=0), atol=1e-5)  # 2001's


def test_a_bursts_drops_go_to_every_lamp_and_to_leds_all_along_them() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=30)
    lamps: set[int] = set()
    leds: set[int] = set()
    for beat in range(2001, 2010):
        drawn(fountain, tempo_ctx(float(beat)), room)  # the last beat's burst, as it lands
        gaps = np.linalg.norm(fountain.particles.pos[:, None, :] - room.pos[None, :, :], axis=2)
        landed = gaps.argmin(axis=1)[gaps.min(axis=1) < 1e-4]
        assert len(landed) == 30
        lamps |= set((landed // 14).tolist())
        leds |= set(landed.tolist())
    assert lamps == {0, 1, 2, 3}
    assert len(leds) > 45  # of the room's 56 LEDs


def test_the_spray_and_the_bursts_are_listed_together_oldest_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each drop is listed by when it was thrown: the spray's in seconds, a burst's on its beat
    (worked out here from the beat count and the tempo, at 90 BPM, where a beat is not the half
    second it is at 120)."""
    room = _room()
    bpm, size, rate = 90.0, 16, 30.0
    fountain = _fountain(rate=rate, burst=size)
    seen = _watched(monkeypatch)
    mixed = 0
    for step in range(120):
        beats = 2000.0 + step / 10
        ctx = tempo_ctx(beats, bpm=bpm)
        drawn(fountain, ctx, room)
        (spray, sprayed), (bursts, thrown) = seen[-1]
        # Beat j's burst is in the air for a beat and a half from the beat: the last whole
        # beat's, and the one before's while it is not yet that old.
        in_the_air = [j for j in (math.floor(beats) - 1, math.floor(beats)) if beats - j < 1.5]
        expected = np.repeat([ctx.t - (beats - j) * 60.0 / bpm for j in in_the_air], size)
        np.testing.assert_allclose(thrown, expected, rtol=0.0, atol=1e-9)
        assert ((ctx.t - sprayed >= 0.0) & (ctx.t - sprayed < 2.0)).all()  # seconds, in the air
        assert len(np.unique(np.floor(sprayed * rate))) == len(sprayed)  # one in each 1 / rate s
        order = np.argsort(np.concatenate([sprayed, expected]), kind="stable")
        merged = particle_tools.joined(spray, bursts).pick(order)
        np.testing.assert_array_equal(fountain.particles.pos, merged.pos)
        kinds = order < len(sprayed)
        mixed += int(np.count_nonzero(np.diff(kinds.astype(int))) > 1)  # not all of one kind first
    assert mixed > 100


def test_the_spray_is_timed_in_seconds_whatever_the_tempo() -> None:
    room = _room()
    slow, fast = _fountain(burst=0), _fountain(burst=0)
    drawn(slow, tempo_ctx(1503.0, bpm=90.0), room)  # 1002 s in
    drawn(fast, tempo_ctx(2004.0, bpm=120.0), room)  # 1002 s in
    assert slow.particles.count > 20
    np.testing.assert_array_equal(slow.particles.pos, fast.particles.pos)


def test_a_burst_fades_over_the_half_beat_after_it_lands() -> None:
    room = _room()
    fountain = _fountain(rate=5.0, burst=8, palette=["#ffffff"])

    def landed_glow(beats: float) -> np.ndarray:
        drawn(fountain, tempo_ctx(beats), room)
        pos, colour = fountain.particles.pos, fountain.particles.colour
        on_an_led = (
            np.linalg.norm(pos[:, None, :] - room.pos[None, :, :], axis=2).min(axis=1) < 1e-4
        )
        return colour[on_an_led, 0]

    np.testing.assert_allclose(landed_glow(2001.0), np.ones(8))  # beat 2000's, as it lands
    np.testing.assert_allclose(landed_glow(2001.25), np.full(8, 0.5), atol=1e-6)  # half faded
    assert len(landed_glow(2001.5)) == 0  # gone


@pytest.mark.parametrize("anchor", ["", "gone"], ids=["none set", "not on the map"])
def test_with_no_anchor_the_fountain_sprays_from_the_middle_of_the_zone(anchor: str) -> None:
    room = _room()
    fountain = Fountain(anchor=anchor, rate=5.0, burst=8)
    fountain.reseed(1)
    drawn(fountain, tempo_ctx(2001.0), room)
    leaving = fountain.particles.pos[-8:]  # beat 2001's burst, as it leaves
    np.testing.assert_allclose(leaving, np.repeat([room.centre], 8, axis=0), atol=1e-5)


def test_the_spray_has_as_many_drops_in_the_air_as_its_rate_says() -> None:
    def in_the_air(rate: float) -> float:
        counts = []
        fountain = _fountain(burst=0, rate=rate)
        for step in range(150):
            drawn(fountain, tempo_ctx(2000.0 + step / 7), _room())
            counts.append(fountain.particles.count)
        return float(np.mean(counts))

    assert in_the_air(60.0) == pytest.approx(2.0 * in_the_air(30.0), rel=0.05)
    assert in_the_air(5.0) < 0.25 * in_the_air(30.0)


def test_the_spray_lands_evenly_over_its_disc_not_bunched_at_its_middle() -> None:
    """A drop's glow gives how far through its flight it is (1.5 - glow, once it is past the
    top), and its distance from the fountain is that share of where it lands: so each drop
    says where it lands, as a share of the spread. Evenly over a disc is a share squared that
    is evenly spread over 0 to 1, a mean of a half; bunched at the middle (a plain share of
    the spread) would have a mean of a third."""
    room = _room()
    fountain = _fountain(burst=0, rate=120.0, spread_m=2.0, palette=["#ffffff"])
    shares = []
    for step in range(300):
        drawn(fountain, tempo_ctx(2000.0 + step / 15), room)
        glow = fountain.particles.colour[:, 0].astype(np.float64)
        falling = (glow > 0.02) & (glow < 0.98)
        away = np.linalg.norm(fountain.particles.pos[falling, :2] - ANCHOR[:2], axis=1)
        shares.append(away / (1.5 - glow[falling]) / 2.0)
    landing = np.concatenate(shares)
    assert len(landing) > 5000 and landing.max() <= 1.0 + 1e-4
    assert np.mean(landing**2) == pytest.approx(0.5, abs=0.03)
    assert np.mean(landing**2 < 0.25) == pytest.approx(0.25, abs=0.03)


def test_the_settings_reach_the_drops() -> None:
    fountain = _fountain(palette=["#ff0000"], size=0.35)
    drawn(fountain, tempo_ctx(2000.5), _room())
    assert fountain.particles.count > 0
    np.testing.assert_allclose(fountain.particles.radius, 0.35)
    assert (
        not fountain.particles.colour[:, 1:].any() and fountain.particles.colour[:, 0].max() > 0.5
    )


@pytest.mark.parametrize(
    ("burst", "rate"), [(0, 30.0), (60, 5.0)], ids=["the spray", "the bursts"]
)
def test_nothing_rises_through_the_ceiling_however_high_it_is_set(burst: int, rate: float) -> None:
    """Set to 3 m from an anchor at 0.45 m, the spray goes up to the 3 m ceiling and its
    highest drops come within a few cm of it (so do the tops of the bursts' arcs, which fit
    under it), and none goes through."""
    where = _spray(_fountain(burst=burst, rate=rate, height_m=3.0))
    assert where[:, 2].min() >= 0.0
    assert 3.0 - 0.05 < where[:, 2].max() <= 3.0


def test_the_drops_are_not_flattened_against_the_ceiling_at_the_largest_settings() -> None:
    """The arcs fit under the ceiling instead of running into it: not one drop sits at the
    ceiling, and few are within a centimetre of it. That is the tops of the bursts' arcs,
    which at these settings all rise as far as the ceiling lets them (rise_under): an arc
    spends about 6% of its flight within a centimetre of its top, so 1.6% of all the drops
    are there, against 0.05% of the spray's alone."""
    z = _spray(_fountain(rate=120.0, height_m=3.0, burst=60))[:, 2]
    assert z.max() <= 3.0
    assert np.mean(z >= 3.0) == 0.0
    assert np.mean(z > 3.0 - 0.01) < 0.03
    assert np.mean(_spray(_fountain(rate=120.0, height_m=3.0, burst=0))[:, 2] > 3.0 - 0.01) < 0.01


def test_a_bursts_arcs_fit_under_the_ceiling_at_the_largest_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    room = _room()
    fountain = _fountain(rate=5.0, height_m=3.0, burst=60)
    seen = _watched(monkeypatch)
    heights = []
    for step in range(120):
        drawn(fountain, tempo_ctx(2000.0 + step / 15), room)
        heights.append(seen[-1][1][0].pos[:, 2].astype(np.float64))  # the bursts' drops
    z = np.concatenate(heights)
    assert np.mean(z >= 3.0) == 0.0  # none against the ceiling
    assert 2.9 < z.max() < 3.0  # and they go well up to it


def test_a_burst_from_an_anchor_near_the_ceiling_still_arcs_up_to_it_before_coming_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The anchor is 10 cm under the ceiling and the drops land on LEDs 0.1 to 1.4 m up, so the
    room over the higher end is 10 cm. A burst rises as far as an arc between those can with
    its top at the ceiling instead, 0.6 to 1 m over the line: it goes up from the anchor and
    comes down on its LED, rather than falling most of the way straight."""
    room = _room(np.array([2.0, 2.0, 2.9], dtype=np.float32))
    fountain = _fountain(rate=5.0, height_m=3.0, burst=60)
    seen = _watched(monkeypatch)
    heights = []
    for step in range(1200):  # every hundredth of a second, eight seconds
        drawn(fountain, tempo_ctx(2000.0 + step / 75), room)
        heights.append(seen[-1][1][0].pos[:, 2].astype(np.float64))
    z = np.concatenate(heights)
    assert z.max() <= 3.0
    assert z.max() > 3.0 - 0.01  # up to the ceiling, not the anchor's 2.9


def test_a_burst_rises_burst_up_times_the_height_when_there_is_room_for_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With 10 m of room the fit never binds: a burst's arc rises height_m x BURST_UP, give
    or take a fifth, over the line between its ends, so no drop tops that over its higher end."""
    corners = (upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))
    room = lights_at(*corners, anchors={ANCHOR_ID: ANCHOR}, ceiling=10.0)
    fountain = _fountain(rate=5.0, height_m=0.5, burst=60)
    seen = _watched(monkeypatch)
    tops = []
    for step in range(120):
        drawn(fountain, tempo_ctx(2000.0 + step / 15), room)
        tops.append(seen[-1][1][0].pos[:, 2].astype(np.float64))
    z = np.concatenate(tops)
    assert z.max() <= 1.4 + 0.5 * BURST_UP * 1.2 + 1e-4  # the highest LED, and the longest rise
    assert z.max() > 1.4 + 0.5 * BURST_UP * 0.8 - 0.3  # and they do go up that far, a little less


def test_a_burst_to_a_lamp_over_the_ceiling_rises_over_the_ceiling_under_that_lamps_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fit is under the ceiling of the lamp the burst goes to (ceiling_for): half-way, the
    drops that go east, to a lamp whose LEDs are 3.2 to 3.5 m up, rise over the zone's 3 m
    ceiling (those to its lower LEDs, 3.1 m up) and none over the lamp's 3.5; those that go
    west, to a lamp in the band, are never over 3."""
    room = lights_at(
        upright(1.0, 2.0),
        upright(3.0, 2.0, 3.2, 3.5),
        anchors={ANCHOR_ID: ANCHOR},
        ceiling=3.0,
    )
    fountain = _fountain(rate=5.0, height_m=3.0, burst=60)
    seen = _watched(monkeypatch)
    east, west = [], []
    for beat in range(2000, 2010):
        drawn(fountain, tempo_ctx(beat + 0.5), room)
        drops = seen[-1][1][0].pos.astype(np.float64)
        flying = (
            np.linalg.norm(drops[:, None, :] - room.pos[None, :, :], axis=2).min(axis=1) > 0.05
        )
        east.append(drops[flying & (drops[:, 0] > 2.0), 2])
        west.append(drops[flying & (drops[:, 0] < 2.0), 2])
    east_z, west_z = np.concatenate(east), np.concatenate(west)
    assert len(east_z) > 100 and len(west_z) > 100
    assert 3.1 < east_z.max() <= 3.5 + 1e-6
    assert west_z.max() <= 3.0 + 1e-6


@pytest.mark.parametrize("anchor_z", [2.5, 2.9], ids=["half a metre", "10 cm"])
def test_a_fountain_near_the_ceiling_throws_no_higher_than_the_room_over_it(
    anchor_z: float,
) -> None:
    room_over = 3.0 - anchor_z
    spread = 2.0
    anchor = np.array([2.0, 2.0, anchor_z], dtype=np.float32)
    where = _spray(_fountain(burst=0, height_m=3.0, spread_m=spread), room=_room(anchor))
    z = where[:, 2]
    assert np.mean(z >= 3.0) == 0.0  # none flattened against the ceiling
    assert anchor_z + 0.97 * room_over < z.max() <= 3.0  # thrown right up to it
    above = where[z >= anchor_z]  # before a drop falls past the anchor's height
    away = np.linalg.norm(above[:, :2] - anchor[:2], axis=1)
    assert (
        0.9 * spread < away.max() <= spread + 1e-4
    )  # the spread is the same however short a flight


@pytest.mark.parametrize("anchor_z", [3.0, 3.5, 40.0], ids=["at it", "over it", "far over it"])
def test_a_fountain_with_its_anchor_at_or_over_the_ceiling_stays_finite_and_in_the_room(
    anchor_z: float,
) -> None:
    anchor = np.array([2.0, 2.0, anchor_z], dtype=np.float32)
    where = _spray(_fountain(), room=_room(anchor))
    assert np.isfinite(where).all()
    assert where[:, 2].min() >= 0.0 and where[:, 2].max() <= 3.0


@pytest.mark.parametrize("anchor_z", [0.45, 2.7, 4.0, -1.0])
def test_a_bursts_drops_land_on_their_leds_on_the_next_beat_however_their_arc_is_fitted(
    anchor_z: float,
) -> None:
    room = _room(np.array([2.0, 2.0, anchor_z], dtype=np.float32))
    fountain = _fountain(rate=5.0, height_m=3.0, burst=60)
    drawn(fountain, tempo_ctx(2001.0), room)
    gaps = np.linalg.norm(fountain.particles.pos[:, None, :] - room.pos[None, :, :], axis=2)
    assert (gaps.min(axis=1) < 1e-4).sum() == 60  # beat 2000's burst, as it lands


@pytest.mark.parametrize("where", STRAYS)
def test_a_fountains_bursts_reach_every_led_of_a_lamp_outside_the_floor_and_ceiling(
    where: str,
) -> None:
    leds = STRAYS[where]
    fountain = Fountain()
    fountain.reseed(1)
    frames = run_frames(fountain, leds, moment=on_the_beat)
    z = np.concatenate(frames)
    assert moves(frames)  # thrown from frame to frame, not just spread over heights
    assert unpassed(z, leds) == []  # thrown to the lamp's whole length
    assert stays_in_band(z, leds)  # the spray and the throws stop at the ceiling and the floor


@pytest.mark.parametrize("anchor_z", [4.0, -1.0], ids=["over the ceiling", "under the floor"])
def test_a_fountain_from_an_anchor_outside_the_floor_and_ceiling_keeps_between_them(
    anchor_z: float,
) -> None:
    leds = _room(np.array([2.0, 2.0, anchor_z], dtype=np.float32))
    frames = run_frames(_fountain(), leds, seconds=20.0, moment=on_the_beat)
    z = np.concatenate(frames)
    assert z.min() >= 0.0 and z.max() <= 3.0  # the spray and the throws, the whole way
    assert unpassed(z, leds) == []  # and the bursts still land along the lamps' whole length
    assert moves(frames)


def test_a_fountains_bursts_from_the_middle_of_a_zone_keep_to_the_band_of_their_lamp() -> None:
    """A second lamp 6-7 m up puts the zone's middle 3.55 m up, over the 3 m ceiling that the
    lamp in the band (where the drops that go west land) keeps to the whole way."""
    leds = lights_at(upright(1.0, 1.0), upright(3.0, 1.0, 6.0, 7.0), ceiling=3.0)
    assert leds.centre[0] == 2.0 and leds.centre[2] > 3.0
    fountain = Fountain(rate=5.0, burst=60)
    fountain.reseed(1)
    # Seen every hundredth of a second: the flight over the ceiling is its first tenth.
    where = np.concatenate(run_places(fountain, leds, seconds=10.0, step=0.01, moment=on_the_beat))
    west = where[where[:, 0] < 2.0 - 1e-3]  # left the middle, for the lamp in the band
    assert len(west) > 1000
    assert west[:, 2].max() <= 3.0 + 1e-5


AT_THE_EDGE = 1e-6  # a drop this near the ceiling or the floor is held there by the clip


@pytest.mark.parametrize(
    ("anchor_z", "edge"),
    [(3.2, 3.0), (4.0, 3.0), (-1.0, 0.0), (-3.0, 0.0)],
    ids=["20 cm over the ceiling", "a metre over", "a metre under the floor", "3 m under"],
)
def test_a_burst_from_an_anchor_outside_the_band_leaves_the_edge_at_once_not_along_it(
    monkeypatch: pytest.MonkeyPatch, anchor_z: float, edge: float
) -> None:
    """The anchor is outside the band of the lamps the drops go to, so the clip shows it at the
    edge: the arc starts there, not at the anchor, and leaves the edge at once instead of being
    held along it. Once past its first instant, at the largest settings, no drop is held at
    either edge: none is, where before 16% of the drops were from 20 cm over the ceiling, 32%
    from a metre over, 4% from a metre under the floor and 12% from 3 m under. (The old cap on
    the rise held 4% and 20% of them, from 20 cm and a metre over.)"""
    room = _room(np.array([2.0, 2.0, anchor_z], dtype=np.float32))
    places, since = _burst_drops(monkeypatch, room, rate=5.0, height_m=3.0, burst=60)
    z = places[since > 1e-3, 2]  # past the first instant
    assert len(z) > 5000
    assert z.min() >= 0.0 and z.max() <= 3.0  # and in the band the whole way
    assert np.mean(np.abs(z - edge) < AT_THE_EDGE) < 0.001  # none held at the edge it came from
    other = 3.0 - edge
    assert np.mean(np.abs(z - other) < AT_THE_EDGE) < 0.001  # and the fit holds none at the other


@pytest.mark.parametrize(
    ("anchor_z", "edge"),
    [(3.2, 3.0), (4.0, 3.0), (40.0, 3.0), (-0.5, 0.0), (-1.0, 0.0)],
    ids=["20 cm over", "a metre over", "far over", "half a metre under", "a metre under"],
)
def test_a_burst_from_an_anchor_outside_the_band_flies_as_one_from_the_nearest_edge(
    monkeypatch: pytest.MonkeyPatch, anchor_z: float, edge: float
) -> None:
    """For its flight to a lamp, an anchor outside the lamp's band is at the nearest edge of it:
    the drops fly exactly as they do from an anchor there."""
    outside = _burst_drops(
        monkeypatch, _room(np.array([2.0, 2.0, anchor_z], dtype=np.float32)), rate=5.0, burst=60
    )
    at_the_edge = _burst_drops(
        monkeypatch, _room(np.array([2.0, 2.0, edge], dtype=np.float32)), rate=5.0, burst=60
    )
    np.testing.assert_array_equal(outside[0], at_the_edge[0])
    np.testing.assert_array_equal(outside[1], at_the_edge[1])


def test_a_burst_from_an_anchor_over_the_zone_starts_at_the_ceiling_of_each_lamp_it_goes_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The band is the lamp's own: from an anchor 4 m up, the drops that go west, to a lamp in the
    zone's 3 m, start at 3 m, those that go east, to a lamp whose LEDs are 3.2 to 3.5 m up, at
    3.5 m, and each leaves its ceiling at once (before, 49% of the west drops in the air were held
    at 3 m and 84% of the east ones at 3.5 m). The east ones held at 3.5 m now (5%) are the
    flights to the lamp's top LED, which is at its ceiling: they fly level."""
    room = lights_at(
        upright(1.0, 2.0),
        upright(3.0, 2.0, 3.2, 3.5),
        anchors={ANCHOR_ID: np.array([2.0, 2.0, 4.0], dtype=np.float32)},
        ceiling=3.0,
    )
    places, since = _burst_drops(monkeypatch, room, rate=5.0, height_m=3.0, burst=60)
    first = places[since == 0.0, 2]
    assert len(first) > 300
    assert set(np.unique(first)) == {np.float32(3.0), np.float32(3.5)}  # each at its lamp's own
    flying = (since > 1e-3) & (since < 1.0 - 1e-6)
    west, east = flying & (places[:, 0] < 2.0), flying & (places[:, 0] > 2.0)
    assert west.sum() > 1000 and east.sum() > 1000
    assert np.mean(places[west, 2] > 3.0 - AT_THE_EDGE) < 0.001
    assert np.mean(places[east, 2] > 3.5 - AT_THE_EDGE) < 0.1  # 1 LED of 14 is at the ceiling
    assert np.mean(places[east, 2] > 3.0 + AT_THE_EDGE) > 0.5  # over the zone's, under the lamp's


@pytest.mark.parametrize(
    ("anchor_z", "start"),
    [(-1.0, 0.0), (0.0, 0.0), (0.45, 0.45), (2.9, 2.9), (3.0, 3.0), (4.0, 3.0)],
    ids=["a metre under", "at the floor", "0.45 m", "2.9 m", "at the ceiling", "a metre over"],
)
def test_a_burst_starts_at_the_height_of_its_anchor_held_in_the_band(
    monkeypatch: pytest.MonkeyPatch, anchor_z: float, start: float
) -> None:
    """In the band the anchor is where the burst starts; outside it, at the edge."""
    room = _room(np.array([2.0, 2.0, anchor_z], dtype=np.float32))
    places, since = _burst_drops(monkeypatch, room, frames=32, rate=5.0, burst=60)
    first = places[since == 0.0, 2]
    assert len(first) == 2 * 60  # the bursts of beats 2000 and 2001
    np.testing.assert_array_equal(first, np.float32(start))


def _drops_in_the_air(fountain: Fountain, leds: LedSet) -> list[int]:
    ground = Ground.of(leds)
    return [
        fountain.positions(tempo_ctx(2000.0 + step * 0.093, bpm=bpm), ground).count
        for step in range(250)
        for bpm in (30.0, 300.0)
    ]


@pytest.mark.parametrize(
    "anchor_z", [0.3, 1.5, 2.9], ids=["low", "half way up", "near the ceiling"]
)
def test_at_its_largest_settings_the_fountain_has_at_most_a_rate_times_a_flight_in_the_air(
    anchor_z: float,
) -> None:
    """The spray's drops fly up (no higher than the ceiling) and fall to the floor from the
    anchor's height, at most `longest` seconds, so up to ceil(rate * longest) + 1 are in the
    air; two beats' bursts are, whatever the tempo (a burst lands on the next beat and fades
    for half of one)."""
    biggest = {"rate": 120.0, "height_m": 3.0, "burst": 60}
    leds = lights_at(*[upright(x, 1.0) for x in range(30)], anchors={"top": [1.0, 1.0, anchor_z]})
    up = math.sqrt(2.0 * GRAVITY * min(biggest["height_m"], 3.0 - anchor_z))
    longest = (up + math.sqrt(up * up + 2.0 * GRAVITY * anchor_z)) / GRAVITY
    bound = math.ceil(biggest["rate"] * longest) + 1 + 2 * biggest["burst"]
    assert bound <= MAX_PARTICLES
    counts = _drops_in_the_air(Fountain(anchor="top", **biggest), leds)
    assert max(counts) <= bound
    assert max(counts) > 0.6 * bound  # and the bound isn't far off


def test_a_very_high_anchor_does_not_push_the_fountain_past_the_cap() -> None:
    """A drop that falls from 100 m takes 4.6 s; at 120 a second that is 554, and the bursts
    come on top. The spray comes down to leave room for the bursts."""
    leds = lights_at(*[upright(x, 1.0) for x in range(8)], anchors={"roof": [1.0, 1.0, 100.0]})
    fountain = Fountain(anchor="roof", rate=120.0, height_m=3.0, burst=60)
    fountain.reseed(1)
    counts = _drops_in_the_air(fountain, leds)
    assert max(counts) <= MAX_PARTICLES
    assert max(counts) > 0.9 * MAX_PARTICLES  # it uses the room it has, and no more


def test_a_fountain_over_many_lamps_keeps_to_the_cap_at_its_largest_settings() -> None:
    counts = _drops_in_the_air(Fountain(rate=120.0, height_m=3.0, burst=60), bulbs(100))
    assert max(counts) <= MAX_PARTICLES
