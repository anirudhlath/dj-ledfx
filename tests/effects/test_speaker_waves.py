from __future__ import annotations

from collections import Counter

import numpy as np
from conftest import builtin_look, tempo_ctx
from map_home import leds_at, seeded_ledset, seeded_space, seeded_zone_lights

from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.field_tools import distances, height01
from dj_ledfx.effects.ledset import LedSet, LedSource, build_ledset
from dj_ledfx.effects.speaker_waves import KICK_COLOUR, REST_COLOUR, SNARE_COLOUR, SpeakerWaves

# Two speakers 4 m apart, and LEDs 1, 2 and 3 m along the line between them.
PAIR = {"speakers": [(0.0, 0.0, 1.0), (4.0, 0.0, 1.0)]}
BETWEEN = [(1.0, 0.0, 1.0), (2.0, 0.0, 1.0), (3.0, 0.0, 1.0)]
KICK, SNARE, REST = palette_float([KICK_COLOUR, SNARE_COLOUR, REST_COLOUR]) * 0.9  # level 0.9


def test_kicks_send_a_wavefront_out_from_each_speaker() -> None:
    effect = SpeakerWaves(anchor="speakers")
    leds = leds_at(BETWEEN, anchor_points=PAIR)

    # Each speaker's farthest LED is 3 m away, which its front reaches three quarters
    # into the beat: a quarter in, each front is 1 m out.
    frame = effect.render(tempo_ctx(4.25), leds)

    near_kick = np.linalg.norm(frame - KICK, axis=1)
    assert near_kick[0] < near_kick[1] and near_kick[2] < near_kick[1]
    assert np.allclose(frame[0], frame[2])  # one front from each speaker


def test_snares_bloom_between_the_speakers_on_the_second_and_fourth_beats() -> None:
    effect = SpeakerWaves(anchor="speakers")
    leds = leds_at(BETWEEN, anchor_points=PAIR)

    first, second = (effect.render(tempo_ctx(beats), leds) for beats in (4.0, 5.0))

    assert np.allclose(first[1], REST, atol=1e-3)
    assert np.allclose(second[1], SNARE, atol=1e-3)


def test_hats_sparkle_up_high_on_the_off_beat() -> None:
    effect = SpeakerWaves(anchor="speakers", sparkle=0.5)
    effect.reseed(3)
    no_hats = SpeakerWaves(anchor="speakers", sparkle=0.0)
    low = [(float(x), 9.0, 0.3) for x in range(40)]
    high = [(float(x), 9.0, 2.9) for x in range(40)]
    leds = leds_at(low + high, ceiling=3.0, anchor_points={"speakers": [(80.0, 0.0, 1.0)]})

    def sparkling(beats: float) -> set[int]:
        frame, kicks_and_snares = (e.render(tempo_ctx(beats), leds) for e in (effect, no_hats))
        return {i for i in range(80) if not np.allclose(frame[i], kicks_and_snares[i], atol=1e-3)}

    assert sparkling(4.25) == set()  # on the beat
    assert sparkling(4.6) and sparkling(4.6) <= set(range(40, 80))  # the off-beat, high only
    assert sparkling(5.6) != sparkling(4.6)  # other LEDs each beat


def _busiest_room() -> LedSet:
    """This home's room with the most lights, as its zone sees them."""
    lights = seeded_zone_lights()
    room = Counter(light.room for light in lights).most_common(1)[0][0]
    sources = [
        LedSource(light.device_id, light.led_count, placed=light.placed, room=light.room)
        for light in lights
        if light.room == room
    ]
    return build_ledset(sources, seeded_space())


def test_the_kicks_reach_the_far_and_low_lights_of_a_room() -> None:
    # Task 15's dry run: in the room with the most lights, two of eleven never moved.
    look = builtin_look("speakers")
    effect = SpeakerWaves(**look.layers[0].settings)
    leds = _busiest_room()
    speakers = leds.space.anchor_points[look.layers[0].settings["anchor"]]
    near = np.min([distances(leds, point) for point in speakers], axis=0)
    height = height01(leds)
    far = max(leds.slices, key=lambda part: near[part.start : part.stop].min())
    low = min(leds.slices, key=lambda part: height[part.start : part.stop].max())

    bar = np.stack([effect.render(tempo_ctx(4.0 + k / 120), leds) for k in range(4 * 120)])

    for part in (far, low):
        light = bar[:, part.start : part.stop]
        assert (light.max(axis=0) - light.min(axis=0)).max() > 0.1, part.device_id


def test_frame_after_frame_it_draws_what_a_new_one_draws() -> None:
    """What a beat keeps (its sparkles) and the blends it skips never change a frame: one
    effect across beats, a new sparkle share and a new seed draws what a new one would."""
    leds = seeded_ledset()
    effect = SpeakerWaves(anchor="speakers", sparkle=0.3)
    effect.reseed(5)

    for k in range(8 * 30):  # eight beats at 30 frames a beat
        sparkle, seed = (0.3 if k < 120 else 0.6), (5 if k < 180 else 6)
        if k == 120:
            effect.set_params(sparkle=sparkle)
        if k == 180:
            effect.reseed(seed)
        fresh = SpeakerWaves(anchor="speakers", sparkle=sparkle)
        fresh.reseed(seed)
        ctx = tempo_ctx(4.0 + k / 30)
        assert np.array_equal(effect.render(ctx, leds), fresh.render(ctx, leds)), k
