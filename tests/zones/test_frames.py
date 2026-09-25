from __future__ import annotations

from functools import partial

import numpy as np
from conftest import FakeLight
from zone_home import BREATHE_AND_GLOW, GLOW, TILE, HomeFactory, zone_record

from dj_ledfx.scheduling.route import to_device_colors
from dj_ledfx.zones.frames import FrameFeed, Watchers
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
    frame = runtime.ring.find_nearest(100.0)
    assert frame is not None and set(live) == {"lamp", "tile"}
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
    assert feed.frames("live")["tile"].min() == 128  # Glow's level, 0.5, drawn for the stage
