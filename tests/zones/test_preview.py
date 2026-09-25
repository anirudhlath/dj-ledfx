from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest
from conftest import FakeLight
from zone_home import FakeHome, Home, HomeFactory, zone_record

from dj_ledfx.looks.model import LookError
from dj_ledfx.zones.model import ZoneError, ZoneNotFoundError
from dj_ledfx.zones.preview import PreviewManager, PreviewNotFoundError


class Watch:
    """Whether anyone watches the preview stream, and the preview manager's clock."""

    def __init__(self) -> None:
        self.watching = True
        self.now = 0.0


def _previews(home: Home, watch: Watch, **kwargs: Any) -> PreviewManager:
    return PreviewManager(home.manager, lambda: watch.watching, clock=lambda: watch.now, **kwargs)


# M1 review, constraint 1: a preview must never collide with its zone's own runtime.
async def test_a_preview_runs_beside_its_zone_and_never_touches_the_lights(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    home = await make_home([a, b], [zone_record("z", "a", "b")])
    await home.manager.start("z", home.look("classic-breathe"))
    zone_runtime = home.host.runtimes["z"]
    routes = dict(home.routes.routes)
    a.calls.clear()
    b.calls.clear()
    previews = _previews(home, Watch())

    preview_id = previews.start("z", home.look("classic-strobe"))

    [runtime] = previews.runtimes()
    assert runtime.zone_id == "z" and home.manager.preview_runtimes() == [runtime]
    assert home.host.hosted == [zone_runtime, runtime]  # beside the zone's own
    runtime.tick(100.0)
    assert runtime.ring.count == 1 and runtime.leds.count == 8
    assert home.routes.routes == routes  # no route: nothing it renders reaches a light
    assert a.calls == [] and b.calls == []  # never captured, switched on or sent to
    info = home.manager.running_info("z")
    assert info is not None and info.look_id == "classic-breathe"

    previews.stop(preview_id)

    assert home.host.hosted == [zone_runtime] and previews.runtimes() == []


# Review Focus 1: a browser tab closed mid-preview sends no DELETE /preview.
async def test_a_preview_nobody_watches_ends_by_itself(make_home: HomeFactory) -> None:
    a = FakeLight("a")
    home = await make_home([a], [zone_record("z", "a")])
    watch = Watch()
    previews = _previews(home, watch, idle_s=10.0, check_s=0.01)
    preview_id = previews.start("z", home.look("classic-strobe"))

    watch.now = 5.0
    previews.check()  # watched: the idle time starts again
    watch.watching = False
    watch.now = 14.0
    previews.check()
    assert len(previews.runtimes()) == 1  # nine seconds unwatched: it keeps going

    watch.now = 15.5
    task = asyncio.create_task(previews.run())
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.wait([task])

    assert previews.runtimes() == [] and home.host.hosted == []
    with pytest.raises(PreviewNotFoundError):
        previews.update(preview_id, home.look("classic-breathe"))
    assert a.calls == []  # the light was never touched


async def test_a_new_preview_replaces_the_last_and_a_bad_request_changes_nothing(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("a")], [zone_record("z", "a"), zone_record("empty")])
    previews = _previews(home, Watch())
    first = previews.start("z", home.look("classic-strobe"))

    second = previews.start("z", home.look("classic-breathe"))

    [runtime] = previews.runtimes()
    assert home.host.hosted == [runtime]
    with pytest.raises(PreviewNotFoundError):
        previews.stop(first)
    previews.update(second, home.look("classic-color-chase"))
    assert runtime.look.id == "classic-color-chase"
    with pytest.raises(ZoneNotFoundError):
        previews.start("nope", home.look("classic-strobe"))
    with pytest.raises(ZoneError, match="has no lights"):
        previews.start("empty", home.look("classic-strobe"))
    with pytest.raises(LookError):
        previews.update(second, replace(home.look("classic-strobe"), scope="whole-home"))
    assert previews.runtimes() == [runtime]  # the failed requests left it running


# M2 review A2 + E7: the preview follows the map inside the zone manager's own redraw.
async def test_a_preview_follows_the_map_and_ends_with_its_zone(make_home: HomeFactory) -> None:
    view = FakeHome(rooms={"west": ["a"], "east": ["c"]})
    home = await make_home([FakeLight("a"), FakeLight("b"), FakeLight("c")], [], view=view)
    previews = _previews(home, Watch())
    preview_id = previews.start("west", home.look("classic-strobe"))
    [runtime] = previews.runtimes()
    leds = runtime.leds

    view.rooms["east"].append("b")  # nothing the preview shows
    await home.manager.home_changed()
    assert previews.runtimes() == [runtime] and runtime.leds is leds

    view.rooms["east"].remove("b")
    view.rooms["west"].append("b")
    await home.manager.home_changed()
    assert previews.runtimes() == [runtime] and runtime.leds.count == 8
    assert home.host.hosted == [runtime]

    del view.rooms["west"]
    await home.manager.home_changed()

    assert previews.runtimes() == [] and home.host.hosted == []
    with pytest.raises(PreviewNotFoundError):
        previews.stop(preview_id)


async def test_a_preview_of_a_group_ends_when_the_group_is_deleted(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("a")], [zone_record("shelf", "a")])
    previews = _previews(home, Watch())
    previews.start("shelf", home.look("classic-strobe"))

    await home.manager.delete_group("shelf")

    assert previews.runtimes() == [] and home.host.hosted == []


async def test_a_preview_follows_the_map_a_backup_brings(make_home: HomeFactory) -> None:
    view = FakeHome(rooms={"west": ["a"]})
    home = await make_home([FakeLight("a")], [], view=view)
    previews = _previews(home, Watch())
    previews.start("west", home.look("classic-strobe"))

    async def restore() -> None:
        del view.rooms["west"]  # the backup's map has no west room

    await home.manager.replace_state(restore)

    assert previews.runtimes() == [] and home.host.hosted == []
