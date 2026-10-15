from __future__ import annotations

from functools import partial
from types import SimpleNamespace

import numpy as np
from conftest import FakeLight, nearest_frame
from runtime_fakes import TILE
from zone_home import BREATHE_AND_GLOW, GLOW, HomeFactory, zone_record

from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.scheduling.route import to_device_colors
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.frames import FrameFeed, Watchers, ZoneFx
from dj_ledfx.zones.preview import PreviewManager


def test_watchers_say_who_watches_which_stream() -> None:
    watchers, tab, other = Watchers(), object(), object()
    assert not watchers.watching("live") and not watchers.watching("preview")

    watchers.set(tab, ["live", "nonsense"])
    watchers.set(other, ["preview"])
    assert watchers.watching("live") and watchers.watching("preview")

    watchers.set(tab, [])
    assert not watchers.watching("live") and watchers.watching("preview")
    watchers.set(other, [])
    watchers.set(other, [])  # twice is fine: a session sets none as it ends
    assert not watchers.watching("preview")


# M1 review, constraint 2: the web app's frames come from the rings, not the send loops.
async def test_the_live_stream_has_every_zone_light_and_the_preview_stream_its_own(
    make_home: HomeFactory,
) -> None:
    home = await make_home(
        [FakeLight("lamp"), FakeLight("tile", caps=TILE)], [zone_record("z", "lamp", "tile")]
    )
    await home.manager.start("z", BREATHE_AND_GLOW)  # the tile runs Glow itself
    previews = PreviewManager(home.manager, lambda: True)
    feed = FrameFeed(
        home.manager.live_runtimes, home.manager.preview_runtimes, clock=lambda: 100.0
    )
    runtime = home.host.runtimes["z"]
    assert feed.frames("live") == {} and feed.frames("preview") == {}  # nothing rendered yet

    runtime.tick(100.0)

    live = feed.frames("live")
    frame = nearest_frame(runtime.ring, 100.0)
    assert set(live) == {"lamp", "tile"}
    assert np.array_equal(live["lamp"], to_device_colors(frame.colors[:4], 4))
    assert home.routes.routes["tile"].streaming is False  # never sent to the tile...
    assert np.array_equal(live["tile"], to_device_colors(frame.colors[4:], 4))  # ...but shown
    assert set(feed.frames("live", {"tile"})) == {"tile"}  # a session asks for some lights
    assert feed.frames("live", {"elsewhere"}) == {}

    previews.start("z", home.look("classic-strobe"))
    [preview] = previews.runtimes()
    preview.tick(100.0)

    assert set(feed.frames("preview")) == {"lamp", "tile"}
    assert np.array_equal(feed.frames("live")["lamp"], live["lamp"])  # the zone's own, still


# M1 review, constraint 3: while nobody watches, a light running its own effect isn't drawn.
async def test_a_zone_draws_lights_running_their_own_effect_only_while_live_is_watched(
    make_home: HomeFactory,
) -> None:
    watchers, tab = Watchers(), object()
    home = await make_home(
        [FakeLight("tile", caps=TILE)],
        [zone_record("z", "tile")],
        frames_watched=partial(watchers.watching, "live"),
    )
    await home.manager.start("z", GLOW)
    runtime = home.host.runtimes["z"]
    now = [100.0]
    feed = FrameFeed(home.manager.live_runtimes, clock=lambda: now[0])

    runtime.tick(100.0)
    assert not feed.frames("live")["tile"].any()

    watchers.set(tab, ["preview"])
    now[0] = 100.1
    runtime.tick(100.1)
    assert not feed.frames("live")["tile"].any()  # watching the preview doesn't count

    watchers.set(tab, ["live"])
    now[0] = 100.2
    runtime.tick(100.2)
    now[0] = 100.2 + runtime.horizon_s  # the moment that frame is for
    assert feed.frames("live")["tile"].min() == 128  # Glow's level, 0.5, drawn for the stage


# The live stream is what each light shows now: blended from the frames either side of
# now, as the lights are sent them.
async def test_the_web_app_sees_a_zone_blended_between_its_frames(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [zone_record("z", "lamp")])
    await home.manager.start("z", GLOW)
    feed = FrameFeed(
        home.manager.live_runtimes, home.manager.preview_runtimes, clock=lambda: 100.25
    )
    runtime = home.host.runtimes["z"]
    count = runtime.leds.count
    for t, level in ((100.0, 0.0), (101.0, 1.0)):
        runtime.ring.write(RenderedFrame(np.full((count, 3), level, np.float32), t, 0.0, 0.0))
    assert feed.frames("live")["lamp"].tolist() == [[64, 64, 64]] * count  # a quarter of 255


async def test_the_web_app_sees_a_zone_at_its_brightness(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("lamp")], [zone_record("z", "lamp")])
    await home.manager.start("z", GLOW)  # this lamp can't run Glow: a streamed copy
    await home.manager.set_brightness("z", 0.5)
    feed = FrameFeed(
        home.manager.live_runtimes, home.manager.preview_runtimes, clock=lambda: 100.0
    )
    runtime = home.host.runtimes["z"]
    runtime.tick(100.0)
    frame = nearest_frame(runtime.ring, 100.0)
    assert np.allclose(frame.colors, 0.5)  # Glow's level, at full brightness
    count = runtime.leds.count
    expected = to_device_colors(frame.colors[:count] * np.float32(0.5), count)
    assert np.array_equal(feed.frames("live")["lamp"], expected)


# M8: what each zone draws in space, read from the rings at now.


def _ring_of(*frames: tuple[float, Fx | None]) -> RingBuffer:
    ring = RingBuffer(8)
    for t, fx in frames:
        ring.write(
            RenderedFrame(
                colors=np.zeros((1, 3), dtype=np.float32),
                target_time=t,
                beat_phase=0.0,
                bar_phase=0.0,
                fx=fx,
            )
        )
    return ring


def _drawn() -> Fx:
    return Fx(particles=swarm([[1.0, 2.0, 1.0]], (1.0, 1.0, 1.0), 0.2))


def test_the_feed_reads_each_zones_fx_from_the_newest_frame_at_or_before_now() -> None:
    early, late = _drawn(), _drawn()
    live = SimpleNamespace(
        zone_id="z", brightness=0.5, ring=_ring_of((99.0, early), (100.5, late))
    )
    dark = SimpleNamespace(zone_id="dark", brightness=1.0, ring=_ring_of((99.0, None)))
    preview = SimpleNamespace(zone_id="z", brightness=1.0, ring=_ring_of((99.0, late)))
    now = [100.0]
    feed = FrameFeed(lambda: [live, dark], lambda: [preview], clock=lambda: now[0])  # type: ignore[list-item, return-value]

    assert feed.fx() == [ZoneFx("live", "z", early, 0.5), ZoneFx("preview", "z", late, 1.0)]
    now[0] = 100.4  # nearer the next frame: still the one before, never a blend
    assert feed.fx()[0].fx is early
    now[0] = 100.5
    assert feed.fx()[0].fx is late
    assert FrameFeed(lambda: [], clock=lambda: 100.0).fx() == []
