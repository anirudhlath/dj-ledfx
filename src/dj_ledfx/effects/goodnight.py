"""Goodnight's field (looks.json "goodnight", M6 ruling 9): a warm glow walks through the home,
switching rooms off behind it, and leaves the night room on a night light.

At the start every room glows warm at `level`. The rooms the zone's LEDs are in, but for the
night room, switch off one by one, farthest first from the night room (by the distance between
the rooms' centres), room `i` of `n` at `walk_s * (i + 1) / (n + 1)`. Each brightens as the
walk reaches it, by FRONT_BOOST over the FRONT_S before its switch with its colour moving from
the palette's first stop to its last, then fades to black over FADE_S. LEDs in no room go with
the first room (a zone with none of its LEDs in a room treats them as the one room to switch
off). After the last room's switch the night room eases from `level` to `night_level` over one
room's share of the walk, and stays there. A night room that isn't on the map, or has none of
the zone's LEDs, leaves every room to switch off.

Every frame is a function of the look's elapsed time (RenderContext.elapsed_s) alone, never of
the tempo clock, so a resume after a restart picks the walk up where it was.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, NamedTuple

import numpy as np

from dj_ledfx.effects.color import palette_at
from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.ledset import NO_ROOM
from dj_ledfx.effects.params import EffectParam, level_param
from dj_ledfx.home.geometry import polygon_centre

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

FRONT_BOOST = 1.4  # how much brighter a room glows as the walk reaches it (clipped to full)
FRONT_S = 3.0  # how long before its switch a room starts to brighten
FADE_S = 2.0  # how long a room takes to go from its brightest to black
# A room glows with the first stop; the walk lights it with the last, the brighter.
GOODNIGHT_PALETTE = ("#ff8a3c", "#ffd9a0")


class _Walk(NamedTuple):
    """What the walk makes of a set of LEDs: when each switches off, and the night room's."""

    switch: NDArray[np.float64]  # each LED's moment of switching off; inf in the night room
    night: NDArray[np.bool_]  # each LED in the night room
    settle_from: float  # when the night room starts to ease to its night light
    settle_s: float  # how long it eases for


class Goodnight(ParamField):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "walk_s": EffectParam(
                type="float",
                default=60.0,
                min=10.0,
                max=600.0,
                step=5.0,
                label="Walk",
                description="Seconds for the glow to walk the home",
            ),
            "night_room": EffectParam(
                type="zone",
                default="",
                label="Night room",
                description="Left on a night light; none: every room switches off",
            ),
            "night_level": EffectParam(
                type="float",
                default=0.12,
                min=0.0,
                max=1.0,
                step=0.01,
                label="Night light",
                description="How bright the night room is left",
            ),
            "palette": EffectParam(
                type="color_list",
                default=list(GOODNIGHT_PALETTE),
                label="Palette",
                description="The glow, then the walk's front",
            ),
            "level": level_param(0.7),
        }

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        walk = self._per_leds(leds, self._walk)
        values = self._values
        elapsed = max(0.0, ctx.elapsed_s)  # a look that hasn't begun draws its start
        level, night_level = float(values["level"]), float(values["night_level"])
        switch = walk.switch
        # Each LED's share of the way through its room's front, then of its fade. Both are
        # exact at their ends (0 and 1), so a room is black from FADE_S after its switch.
        front = ease_in_out(np.clip((elapsed - (switch - FRONT_S)) / FRONT_S, 0.0, 1.0))
        fade = 1.0 - ease_in_out(np.clip((elapsed - switch) / FADE_S, 0.0, 1.0))
        settled = ease_in_out(min(1.0, max(0.0, (elapsed - walk.settle_from) / walk.settle_s)))
        glow = np.where(
            walk.night,
            level + (night_level - level) * settled,
            level * (1.0 + (FRONT_BOOST - 1.0) * front) * fade,
        )
        colours = palette_at(self._palette, front.astype(np.float32))
        return np.minimum(colours * glow[:, None], 1.0).astype(np.float32)

    def _walk(self, leds: LedSet) -> _Walk:
        """When each LED switches off, and which are the night room's."""
        space = leds.space
        rooms = leds.room
        night_id = str(self._values["night_room"])
        night_index = space.rooms.index(night_id) if night_id in space.rooms else NO_ROOM
        night = (rooms == night_index) if night_index != NO_ROOM else np.zeros(leds.count, bool)
        present = {int(room) for room in np.unique(rooms)} - {NO_ROOM, night_index}
        night_outline = space.room_outlines.get(night_id)  # known even if it has no LEDs here
        centre = polygon_centre(night_outline) if night_outline else None

        def farthest_first(room: int) -> tuple[float, int]:
            far = 0.0
            outline = space.room_outlines.get(space.rooms[room])
            if centre is not None and outline:
                far = math.dist(centre, polygon_centre(outline))
            return -far, room  # equal distances (or none known) keep the map's order

        order = sorted(present, key=farthest_first)
        unplaced = rooms == NO_ROOM
        count = len(order) if order or not unplaced.any() else 1  # the unplaced alone: one room
        share = float(self._values["walk_s"]) / (count + 1)
        switch = np.full(leds.count, math.inf)
        for position, room in enumerate(order):
            switch[rooms == room] = share * (position + 1)
        if unplaced.any():
            switch[unplaced] = share  # with the first room
        return _Walk(switch, night, share * count, share)
