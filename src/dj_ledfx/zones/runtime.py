"""One running zone: its look, its LEDs and the frames it renders ahead (spec §4.1, §8)."""

from __future__ import annotations

import itertools
import math
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Literal, NamedTuple

import numpy as np
from loguru import logger

from dj_ledfx.effects.blend import blend_into
from dj_ledfx.effects.context import render_context
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.ledset import (
    NO_ROOM,
    NO_SPACE,
    LedSet,
    LedSource,
    PlacedLeds,
    Space,
    build_ledset,
)
from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.looks.model import (
    Layer,
    Look,
    LookError,
    Transition,
    TransitionKind,
    firmware_layers,
    make_effect,
    visible_field_layers,
)
from dj_ledfx.looks.selectors import selects
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.timing import trim_window, utcnow
from dj_ledfx.types import RenderedFrame, clamp01
from dj_ledfx.zones.layer_view import LayerView, layer_view
from dj_ledfx.zones.look_modifiers import Trails, capped, flashed, warmed
from dj_ledfx.zones.model import CrashInfo, TransitionInfo
from dj_ledfx.zones.transition import new_share, switch_order

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.devices.capabilities import DeviceCapabilities
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.field import FieldEffect
    from dj_ledfx.spatial.geometry import DeviceGeometry
    from dj_ledfx.tempo.clock import TempoClock
    from dj_ledfx.types import FloatRGB

FRAME_BUDGET_S = 0.005
SLOW_RATIO = 0.8
SLOW_AFTER_S = 30.0
CRASH_LOG_INTERVAL_S = 60.0
ALWAYS_AVAILABLE = frozenset({"tempo"})  # the internal clock at worst (spec §5.2)
# How far ahead a zone renders at most. A light slower than this gets the newest frame and
# runs late by the difference. A look starts within a frame or two, and a change to a
# running look shows within the horizon (≤120 ms).
HORIZON_CAP_S = 0.12

# Process-wide, so a light applied for one runtime always sees another look as new; only a
# twin shares its runtime's generation, on purpose (twin()).
_GENERATIONS = itertools.count(1)

ZoneState = Literal["running", "slow", "crashed", "waiting", "transition"]
LightMode = Literal["streaming", "own-effect", "streamed-copy"]
# What a light was last given: the generation of the look it follows (twins share their
# runtime's), and the firmware layer it runs with the brightness that started it (both None:
# it streams).
AppliedKey = tuple[int, str | None, float | None]


def _finite(colors: FloatRGB) -> FloatRGB:
    if not np.isfinite(colors).all():
        raise FloatingPointError("the layer produced NaN or infinite colours")
    return colors


def _opacity(layer: Layer, view: LayerView) -> float | NDArray[np.float32]:
    """How much of a field layer shows: its opacity, by each LED's weight in its mask."""
    if view.weight is None:
        return layer.opacity
    return view.weight if layer.opacity == 1.0 else view.weight * np.float32(layer.opacity)


def _layout(look: Look) -> list[tuple[str, str, str, bool, object]]:
    """What can't change in place: the layers, and which lights each one picks."""
    return [
        (layer.id, layer.type, layer.kind, layer.visible, layer.lights) for layer in look.layers
    ]


class _Drawn(NamedTuple):
    """Where a look a transition replaces drew the zone's lights: how many of them, and
    their rows in this zone's frame (`mine`) and in that look's (`theirs`), a slice where
    they follow on in order."""

    source: ZoneRuntime
    lights: int
    mine: NDArray[np.intp] | slice
    theirs: NDArray[np.intp] | slice


def _rows(pieces: list[NDArray[np.intp]]) -> NDArray[np.intp] | slice:
    """The rows of a look's lights, a piece for each: a slice when they follow on in order
    (a zone replacing its own look), else each row's index."""
    rows = np.concatenate(pieces)
    start = int(rows[0])
    if np.array_equal(rows, np.arange(start, start + len(rows))):
        return slice(start, start + len(rows))
    return rows


def _whole(rows: list[_Drawn], count: int) -> bool:
    """Whether one look drew every row of the frame, as the frame has them."""
    if len(rows) != 1 or rows[0].source.leds.count != count:
        return False
    return all(
        isinstance(part, slice) and (part.start, part.stop) == (0, count)
        for part in (rows[0].mine, rows[0].theirs)
    )


@dataclass(eq=False)
class _Transition:
    """A transition while it plays (spec §5.3). `rows` says where each look it replaces
    drew the zone's lights. `held` lights run a firmware effect in one of the two looks,
    so they stay with the look they had until the midpoint and then switch whole;
    `held_rows` are their rows in the frame."""

    kind: TransitionKind
    duration_s: float
    rows: list[_Drawn]
    whole: bool  # one look drew every row, as the frame has them: its frame is the old one
    order: NDArray[np.float64] | None  # each LED's place in the switch; None: all at once
    held: dict[str, ZoneRuntime]  # light -> the runtime whose look it keeps until then
    held_rows: dict[str, slice]
    started: float | None = None  # the first frame's time: the transition runs from it
    progress: float = 0.0  # of the newest frame, 0..1
    switched: bool = False  # the held lights went over to the new look

    def past_midpoint(self, t: float) -> bool:
        return self.started is not None and t >= self.started + self.duration_s / 2.0


@dataclass(frozen=True, slots=True)
class ZoneLight:
    """One light as its zone sees it: where the home map puts its LEDs (None: not placed)
    and its room's index in the zone's Space.rooms."""

    device_id: str
    led_count: int
    caps: DeviceCapabilities
    geometry: DeviceGeometry | None = None
    placed: PlacedLeds | None = None
    room: int = NO_ROOM
    light_id: str = ""  # its light's id: the PC's for a PC part (devices/lights.py)
    name: str = ""


@dataclass(frozen=True, slots=True)
class RuntimeEnv:
    """What every zone's runtime reads from the app around it. The zone manager makes one
    and hands it to each runtime it makes; a preview and a twin each change a field or two
    (dataclasses.replace)."""

    clock: TempoClock
    latency_s: Callable[[str], float | None]  # a light's latency; None: not connected
    fps: int = 60
    max_lookahead_s: float = 1.0
    timer: Callable[[], float] = time.perf_counter  # times each render
    now: Callable[[], datetime] = utcnow  # when a zone crashed or turned slow
    # Whether anyone watches the zone's frames (Task 13). Lights that run their own effect
    # are drawn only for the preview, so only while someone watches.
    watched: Callable[[], bool] = lambda: True
    # How far into the evening it is now, 0..1 (home/sun.py), for looks that follow it.
    evening: Callable[[], float] = lambda: 0.0
    # Called when the zone crashes, turns slow, recovers by itself or its transition
    # starts, passes the midpoint or ends: the zone manager tells the running channel.
    on_state_change: Callable[[ZoneRuntime], None] | None = None
    # Called when lights went over to the zone's new look (its transition passed the
    # midpoint, or ended before it, holding lights): the zone manager applies them.
    on_switch: Callable[[ZoneRuntime], None] | None = None


class ZoneRuntime:
    """Renders one running zone's look ahead of time into its own ring buffer."""

    def __init__(
        self,
        zone_id: str,
        look: Look,
        lights: Sequence[ZoneLight],
        env: RuntimeEnv,
        *,
        brightness: float = 1.0,
        seed: int = 0,
        space: Space = NO_SPACE,
        leds: LedSet | None = None,
        emulated: Iterable[str] = (),
    ) -> None:
        """`leds` is the LED set the lights make in `space`, when the caller has it (a
        twin); `emulated` the lights that refused their firmware effects (mark_emulated)."""
        self.zone_id = zone_id
        self._env = env
        self.look = look
        self.brightness = brightness
        self.generation = 0  # _compile draws the first
        self.crash: CrashInfo | None = None
        self.slow_since: datetime | None = None
        self._seed = seed
        self._trails = Trails()
        self._transition: _Transition | None = None
        self._handover: set[str] = set()  # see handing_over
        self._fields: list[tuple[Layer, FieldEffect]] = []  # bottom to top
        self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
        self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
        self._copies: dict[str, int] = {}  # light -> firmware layer streamed as a copy
        self._emulated = set(emulated)  # lights that rejected their firmware effect
        # Each firmware layer's lights and their LEDs: where they sit in the zone's frame
        # and the LED set the layer's emulation is drawn on. Copies go to the lights;
        # claims only to the preview.
        self._copy_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
        self._claim_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
        self._lights: tuple[ZoneLight, ...] = ()
        # Each field layer's view of the LEDs (its mask, mirror and transform), with the
        # modifiers it was made for; a new LED set clears them (_place).
        self._views: dict[int, tuple[object, LayerView]] = {}  # by the layer's place
        self._rendering = ""
        self._last_crash_log = float("-inf")
        self._render_s = 0.0  # moving average of the render time
        self._stride = 1
        self._ticks = 0
        self._rendered: deque[float] = deque()
        self._below_since: float | None = None
        self._capacity = int(env.max_lookahead_s * env.fps) + 2
        self.ring: RingBuffer
        self.leds: LedSet
        self._space = space
        self._place(lights, leds)
        self._compile()

    # --- what the zone looks like from outside -------------------------------------

    @property
    def lights(self) -> tuple[ZoneLight, ...]:
        return self._lights

    @property
    def space(self) -> Space:
        return self._space

    @property
    def field_effect(self) -> FieldEffect | None:
        """The bottom field layer's effect: a classic look's only one."""
        return self._fields[0][1] if self._fields else None

    @property
    def waiting_for(self) -> tuple[str, ...]:
        return tuple(need for need in self.look.needs if need not in ALWAYS_AVAILABLE)

    @property
    def state(self) -> ZoneState:
        if self.crash is not None:
            return "crashed"
        if self.waiting_for:
            return "waiting"
        if self._transition is not None:
            return "transition"
        return "slow" if self.slow_since is not None else "running"

    @property
    def fps_actual(self) -> float:
        return float(len(self._rendered))

    @property
    def fps_target(self) -> int:
        return self._env.fps

    @property
    def horizon_s(self) -> float:
        """The largest latency of the zone's lights that take its frames, plus one rendered
        frame (a zone over its budget renders every few ticks), capped at HORIZON_CAP_S and
        the lookahead. A light running its own effect, or not connected (latency None), takes
        none."""
        latency = 0.0
        plain = self._transition is None  # else a light may follow the old look (_holder)
        for light in self._lights:
            device_id = light.device_id
            if device_id not in self._claims if plain else self.streams(device_id):
                light_s = self._env.latency_s(device_id)
                if light_s is not None and light_s > latency:
                    latency = light_s
        frame_s = self._stride / self._env.fps
        return min(latency + frame_s, HORIZON_CAP_S, self._env.max_lookahead_s)

    # Each light's answers come from the look it follows now (_holder): mid-transition, a
    # light that runs a firmware effect in either look keeps the look it had until the
    # midpoint (spec §5.3), so the zone manager keeps applying that look's effect.

    def claim_for(self, device_id: str) -> tuple[Layer, FirmwareEffect] | None:
        """The firmware layer the light runs itself, and its effect; None: it streams."""
        holder = self._holder(device_id)
        index = holder._claims.get(device_id)
        return None if index is None else holder._firmware[index]

    def mode_of(self, device_id: str) -> LightMode:
        holder = self._holder(device_id)
        if device_id in holder._claims:
            return "own-effect"
        if device_id in holder._copies:
            return "streamed-copy"
        return "streaming"

    def effect_name(self, device_id: str) -> str | None:
        """The firmware effect the light runs, or streams a copy of."""
        holder = self._holder(device_id)
        index = holder._claims.get(device_id, holder._copies.get(device_id))
        return None if index is None else holder._firmware[index][1].display_name

    def applied_key(self, device_id: str) -> AppliedKey:
        """What the light is given once its zone's look is applied: the generation of the
        look it follows, and the firmware layer it runs there with the brightness it starts
        at (None, None: it streams). The zone manager applies the light again whenever this
        changes, so a new brightness or cap starts the firmware effects again, and only
        those."""
        holder = self._holder(device_id)
        claim = self.claim_for(device_id)
        if claim is None:
            return holder.generation, None, None
        return holder.generation, claim[0].id, holder._firmware_brightness

    def start_brightness(self, device_id: str) -> float:
        """The brightness the light's firmware effect starts at."""
        return self._holder(device_id)._firmware_brightness

    def streams(self, device_id: str) -> bool:
        """Whether the light takes this zone's frames now: it runs no firmware effect."""
        return self.claim_for(device_id) is None

    def route_for(self, device_id: str) -> DeviceRoute | None:
        piece = self.leds.slice_for(device_id)
        if piece is None or piece.count == 0:
            return None
        return DeviceRoute(self, device_id, streaming=self.streams(device_id))

    @property
    def handing_over(self) -> frozenset[str]:
        """The lights that went over to this look (its transition passed the midpoint, or
        ended before it) that the zone manager hasn't applied yet. A light this look runs
        itself shows the old look's rows until then, so whatever reads its frames never
        sees this look's (spec §5.3)."""
        return frozenset(self._handover)

    def handed_over(self, device_ids: Iterable[str]) -> None:
        """The zone manager applied these lights: their rows show this look from now."""
        self._handover.difference_update(device_ids)

    def _holder(self, device_id: str) -> ZoneRuntime:
        """The runtime whose look the light follows now: this one, but during a transition
        a light that runs a firmware effect in either look keeps the look it had until the
        midpoint (spec §5.3), with that look's effect, brightness and generation, so it
        isn't sent its effect again."""
        transition = self._transition
        if transition is None or transition.switched:
            return self
        return transition.held.get(device_id, self)

    @property
    def _firmware_brightness(self) -> float:
        """The brightness a light running its own effect is started at: the zone's, under
        the look's brightness cap (spec §5.3: the cap also caps firmware devices). Streamed
        colours are capped in the frame and scaled by the zone's brightness at send, so both
        kinds of light end up at most brightness × cap."""
        cap = self.look.modifiers.brightness_cap
        return self.brightness if cap is None else self.brightness * cap

    @property
    def transition_sources(self) -> tuple[ZoneRuntime, ...]:
        """The runtimes whose looks this one's transition mixes in, while it plays."""
        transition = self._transition
        return () if transition is None else tuple(drawn.source for drawn in transition.rows)

    @property
    def transitioning(self) -> bool:
        """Whether a transition is under way, whatever the state shows (a zone that crashed
        or waits mid-transition still holds it)."""
        return self._transition is not None

    def transition_info(self) -> TransitionInfo | None:
        """The transition the zone shows: only while its state is `transition`. It's from
        the look that drove most of the zone's lights."""
        transition = self._transition
        if transition is None or self.state != "transition":
            return None
        rows = transition.rows
        replaced = max(rows, key=lambda drawn: drawn.lights).source.look.name if rows else ""
        return TransitionInfo(
            from_name=replaced,
            kind=transition.kind,
            progress=transition.progress,
            duration_s=transition.duration_s,
        )

    # --- changes --------------------------------------------------------------------

    def set_lights(self, lights: Sequence[ZoneLight], space: Space | None = None) -> None:
        """Rebuild the LED set, in a new space if one is given. Routes read the ring and
        the LED set at each send, so they need nothing. A new ring starts only when the
        frame's layout changed (which device's LEDs sit where): a light moved or a new
        space keeps the frames coming, with no warm-up. A change to the zone's own lights
        (which, or where) ends its transition and starts its trails afresh; a new space
        alone (an anchor or an outline edited) only redraws the layers' views."""
        if tuple(lights) != self._lights:
            self.end_transition()  # its rows were this LED set's
            self._trails.reset()
        if space is not None:
            self._space = space
        self._place(lights)
        self._plan_claims()

    def set_brightness(self, value: float) -> None:
        """The zone's brightness, for the looks a transition replaces too: the whole zone
        dims together. Lights running their own effect start it again at the new
        brightness (applied_key), the streamed ones are scaled at send."""
        self.brightness = value
        for source in self.transition_sources:
            source.set_brightness(value)

    def update_look(self, look: Look) -> None:
        """Take new settings in place when the layers are the same, else rebuild the look.

        In place keeps each effect's state, so a chase keeps its position while a slider
        moves; blend and opacity are read from the layer each frame. The generation moves
        on only when a firmware layer's settings change; a new cap reaches the lights that
        run their own effect through their applied key.
        """
        old, self.look = self.look, look
        if look.modifiers.trails_s is None:
            self._trails.reset()
        if self.crash is not None or _layout(old) != _layout(look) or old.needs != look.needs:
            self._compile()
            return
        for index, layer in enumerate(visible_field_layers(look)):
            old_layer, field_effect = self._fields[index]
            if old_layer.settings != layer.settings:
                field_effect.set_params(**layer.settings)
            self._fields[index] = (layer, field_effect)
        resend = False
        for index, layer in enumerate(reversed(firmware_layers(look))):
            old_layer, firmware = self._firmware[index]
            if old_layer.settings != layer.settings:
                firmware.set_params(**layer.settings)
                resend = True
            self._firmware[index] = (layer, firmware)
        if resend:
            self.generation = next(_GENERATIONS)

    def restart(self) -> None:
        """Re-create the look (spec §8), and give rejected firmware effects another try."""
        self.end_transition()
        self._emulated.clear()
        self._compile()

    def mark_emulated(self, device_id: str) -> None:
        """The light refused its firmware effect: stream that layer's copy to it instead."""
        holder = self._holder(device_id)
        index = holder._claims.pop(device_id, None)
        if index is not None:
            holder._emulated.add(device_id)
            holder._copies[device_id] = index
            holder._retarget()

    # --- transitions ----------------------------------------------------------------

    def begin_transition(self, transition: Transition, sources: Sequence[ZoneRuntime]) -> None:
        """Play this look in over what the zone's lights showed (spec §5.3). `sources` are
        the runtimes that drove them: the zone's own last look, and copies (twin()) of the
        zones it took lights from, each with its own transition as it is. A light keeps the
        first source that has it, with the same number of LEDs; a light none had (idle)
        fades in from black, and runs its firmware effect at once. A light held keeps the
        look it follows in its source until this transition's midpoint; the zone's own last
        look lets its held lights go over first (settle()). A cut, a transition of no time
        or a look that failed to build plays nothing."""
        if not transition.plays or self.crash is not None:
            return
        rows: list[_Drawn] = []
        held: dict[str, ZoneRuntime] = {}
        held_rows: dict[str, slice] = {}
        sourced: set[str] = set()  # the lights a look before already drew
        for source in sources:
            if source.zone_id == self.zone_id:
                source.settle()  # this transition takes its lights on from here
            mine: list[NDArray[np.intp]] = []
            theirs: list[NDArray[np.intp]] = []
            for piece in self.leds.slices:
                device_id = piece.device_id
                old = source.leds.slice_for(device_id)
                if device_id in sourced or old is None or old.count != piece.count:
                    continue
                sourced.add(device_id)
                here = np.arange(piece.start, piece.stop, dtype=np.intp)
                mine.append(here)
                theirs.append(np.arange(old.start, old.stop, dtype=np.intp))
                if source.claim_for(device_id) is not None or device_id in self._claims:
                    held[device_id] = source._holder(device_id)
                    held_rows[device_id] = slice(piece.start, piece.stop)
            if mine:  # one piece for each light, however many LEDs it has
                rows.append(_Drawn(source, len(mine), _rows(mine), _rows(theirs)))
        for source in sources:  # three looks at most in the zone's own chain: older end now
            if source.zone_id == self.zone_id:
                for older in source.transition_sources:
                    older.end_transition()
        self._transition = _Transition(
            kind=transition.kind,
            duration_s=transition.duration_s,
            rows=rows,
            whole=_whole(rows, self.leds.count),
            order=switch_order(transition.kind, self.leds, self.generation),
            held=held,
            held_rows=held_rows,
        )

    def twin(self) -> ZoneRuntime:
        """This runtime as it is now, for a zone that takes some of its lights: the same
        look on the same LEDs, so the same frames (effects are seeded alike), and the same
        firmware effects under the same generation, so a light that runs one isn't sent it
        again. It carries the mix it's in, the lights its transition holds and its trails,
        so the taken lights don't jump. It is never ticked or told about, so its own
        midpoint never passes: the new zone renders it while its transition plays."""
        twin = ZoneRuntime(
            self.zone_id,
            self.look,
            self._lights,
            replace(self._env, on_state_change=None, on_switch=None),
            brightness=self.brightness,
            seed=self._seed,
            space=self._space,
            leds=self.leds,
            emulated=self._emulated,
        )
        twin.generation = self.generation
        twin._trails = self._trails.copy()
        twin._handover = set(self._handover)
        if self._transition is not None:  # its mix, as it is (it never ticks or switches)
            twin._transition = replace(self._transition)
        return twin

    def settle(self) -> None:
        """Let the lights this runtime's transition holds go over to its look now: a newer
        start takes them on from here, and applies them. Its colours keep mixing until the
        transition ends."""
        if self._transition is not None:
            self._transition.switched = True
        self._handover.clear()

    def end_transition(self) -> None:
        """Show this look alone from the next frame: a transition ending, or cut short.
        Lights it still held go over now; the zone manager applies them."""
        transition, self._transition = self._transition, None
        if transition is None:
            return
        if not transition.switched:
            self._handover.update(transition.held)
        if self._handover:  # or a switch that hasn't applied them, tried again
            self._switch_due()
        self._state_changed()

    def _switch(self, transition: _Transition) -> None:
        """The transition passed its midpoint: the lights it held go over to this look,
        and the zone manager applies them. The running channel pushes the zone either way
        (ruling 15)."""
        transition.switched = True
        if transition.held:
            self._handover.update(transition.held)
            self._switch_due()
        self._state_changed()

    def _switch_due(self) -> None:
        if self._env.on_switch is not None:
            self._env.on_switch(self)

    # --- rendering ------------------------------------------------------------------

    def tick(self, now: float) -> None:
        """Render the frame shown at now + horizon, unless crashed or skipping for budget."""
        if self.crash is not None:
            return
        transition = self._transition
        if transition is not None and not transition.switched and transition.past_midpoint(now):
            self._switch(transition)  # the frame showing now is past it
        self._ticks += 1
        if self._ticks % self._stride:
            return
        target = now + self.horizon_s
        ctx = render_context(
            self._env.clock, target, self._stride / self._env.fps, self._env.evening()
        )
        started = self._env.timer()
        try:
            colors = self.render(ctx)
        except Exception as exc:  # a look never takes the engine down (spec §8)
            self._fail(self._rendering, f"{type(exc).__name__}: {exc}")
            return
        elapsed = self._env.timer() - started
        self.ring.write(
            RenderedFrame(
                colors=colors,
                target_time=target,
                beat_phase=ctx.beat_phase,
                bar_phase=ctx.bar_phase,
            )
        )
        self._track_speed(now, elapsed)

    def render(self, ctx: RenderContext) -> FloatRGB:
        """The zone's frame for ctx.t: its look, and while a transition plays, the looks it
        replaces under it, LED by LED (spec §5.3). Both count against the frame budget: tick
        times this whole call. A replaced look that fails ends the transition, never the
        zone."""
        frame = self._render_look(ctx)
        transition = self._transition
        if transition is None:
            return frame
        if transition.started is None:
            transition.started = ctx.t
        progress = (ctx.t - transition.started) / transition.duration_s
        transition.progress = clamp01(progress)
        if progress >= 1.0:
            self.end_transition()
            return frame
        try:
            old = self._replaced(ctx, transition)
        except Exception as exc:
            logger.warning(
                "Zone {}: the look it replaces failed ({}: {}); cutting to {}",
                self.zone_id,
                type(exc).__name__,
                exc,
                self.look.name,
            )
            self.end_transition()
            return frame
        share = new_share(transition.kind, transition.order, transition.progress)
        if transition.held_rows:  # firmware lights switch whole: a share for each LED
            each = (
                np.full((len(frame), 1), share, np.float32) if isinstance(share, float) else share
            )
            for device_id, rows in transition.held_rows.items():
                if device_id in self._claims:  # this look runs it: new once its effect started
                    new = transition.switched and device_id not in self._handover
                else:  # it streams this look once applied, which is after the midpoint
                    new = transition.switched or transition.past_midpoint(ctx.t)
                each[rows] = 1.0 if new else 0.0
            share = each
        blend_into(old, frame, "normal", share)  # the new look over the old, LED by LED
        return old

    def _replaced(self, ctx: RenderContext, transition: _Transition) -> FloatRGB:
        """What the zone's lights showed: each replaced look's rows; black where none was.
        A new array, which the mix then changes in place: when one look drew every row as
        this frame has them, its own frame."""
        if transition.whole:
            return self._as_drawn(transition.rows[0].source, ctx)
        old = np.zeros((self.leds.count, 3), dtype=np.float32)
        for source, _, mine, theirs in transition.rows:
            old[mine] = self._as_drawn(source, ctx)[theirs]
        return old

    def _as_drawn(self, source: ZoneRuntime, ctx: RenderContext) -> FloatRGB:
        """A replaced look's frame at its own brightness (frames are scaled by this zone's
        at send), scaled in place: nothing else holds it (twins and replaced looks don't
        tick)."""
        colours = source.render(ctx)
        scale = source.brightness / self.brightness if self.brightness > 0.0 else 0.0
        if scale != 1.0:
            colours *= np.float32(scale)
        return colours

    def _render_look(self, ctx: RenderContext) -> FloatRGB:
        """A new frame every tick: the ring keeps it. The look's streamed colours (its
        layers), then its modifiers on them (spec §5.3): the downbeat flash, trails (so a
        flash leaves one) and the evening. The lights that run their own effect are drawn
        after those, as they show (for the preview, while it's watched), and the brightness
        cap goes over every LED. The trails keep their own copy of what they showed.
        Waiting, it's dark."""
        count = self.leds.count
        if self.waiting_for or count == 0:
            return np.zeros((count, 3), dtype=np.float32)
        frame = self._render_layers(ctx)
        modifiers = self.look.modifiers
        if modifiers.downbeat_flash:
            frame = flashed(frame, ctx)
        if modifiers.trails_s is not None:
            frame = self._trails.apply(frame, ctx.t, modifiers.trails_s)
        if modifiers.evening:
            frame = warmed(frame, ctx)
        if self._claim_targets and self._env.watched():
            self._draw_firmware(frame, ctx, self._claim_targets)
        if modifiers.brightness_cap is not None:
            frame = capped(frame, modifiers.brightness_cap)
        return frame

    def _render_layers(self, ctx: RenderContext) -> FloatRGB:
        """The field layers blended bottom to top, then each firmware layer's copy drawn on
        the lights that stream it."""
        count = self.leds.count
        frame: FloatRGB | None = None
        for index, (layer, field_effect) in enumerate(self._fields):
            self._rendering = layer.name
            view = self._view(index, layer)
            colors = _finite(field_effect.render(ctx, view.leds))
            opacity = _opacity(layer, view)
            if frame is None and layer.blend == "normal":  # over black: its colours, weighed
                frame = np.multiply(colors, opacity, dtype=np.float32)
                continue
            if frame is None:
                frame = np.zeros((count, 3), dtype=np.float32)
            blend_into(frame, colors, layer.blend, opacity)
        if frame is None:
            frame = np.zeros((count, 3), dtype=np.float32)
        self._draw_firmware(frame, ctx, self._copy_targets)
        return frame

    def _draw_firmware(
        self,
        frame: FloatRGB,
        ctx: RenderContext,
        targets: Sequence[tuple[int, NDArray[np.intp], LedSet]],
    ) -> None:
        """Each firmware layer's emulation, in place, on the rows of the lights given."""
        for index, where, leds in targets:
            layer, firmware = self._firmware[index]
            self._rendering = layer.name
            frame[where] = _finite(firmware.emulate(ctx, leds)) * np.float32(layer.opacity)

    def _view(self, index: int, layer: Layer) -> LayerView:
        """The view of the zone's LEDs for the field layer at `index`, made again only when
        its modifiers or the LED set change, so the effect's per-LED work is kept between
        frames. Kept by place, not id: a saved look may give two layers one id."""
        modifiers = layer.modifiers
        kept = self._views.get(index)
        if kept is not None and kept[0] == modifiers:
            return kept[1]
        view = layer_view(layer, self.leds)
        self._views[index] = (modifiers, view)
        return view

    def _compile(self) -> None:
        self.generation = next(_GENERATIONS)
        self.crash = None
        self._trails.reset()
        self._fields = []
        self._firmware = []
        layers = visible_field_layers(self.look) + list(reversed(firmware_layers(self.look)))
        for position, layer in enumerate(layers):
            try:
                effect = make_effect(layer)
            except LookError as exc:
                self._fields, self._firmware = [], []
                self._fail(layer.name, str(exc))
                break
            effect.reseed(self._seed + position)
            if isinstance(effect, FirmwareEffect):
                self._firmware.append((layer, effect))
            else:
                self._fields.append((layer, effect))
        self._plan_claims()

    def _place(self, lights: Sequence[ZoneLight], leds: LedSet | None = None) -> None:
        self._lights = tuple(lights)
        before = getattr(self, "leds", None)
        if leds is None:
            leds = build_ledset(
                [
                    LedSource(
                        light.device_id, light.led_count, light.geometry, light.placed, light.room
                    )
                    for light in self._lights
                ],
                self._space,
            )
        self.leds = leds
        if before is None or before.slices != self.leds.slices:
            self.ring = RingBuffer(self._capacity)
        self._views = {}  # the layers' views follow the LED set and its space
        ids = {light.device_id for light in self._lights}
        self._emulated &= ids
        self._handover &= ids

    def _picks(self, index: int, light: ZoneLight) -> bool:
        selectors = self._firmware[index][0].lights
        if selectors is None:
            return True
        ids = {light.device_id, light.light_id}
        return selects(selectors, ids, f"{light.name} {light.caps.model}")

    def _plan_claims(self) -> None:
        """Which firmware layer each light runs itself or takes a copy of: the top layer
        that picks the light and that it supports. A light no layer claims takes the copy
        of the top layer that picks it, but only when there is no field layer to play.
        A light that refuses its effect later (mark_emulated) keeps its layer's copy."""
        self._claims = {}
        self._copies = {}
        self._copy_targets = []
        self._claim_targets = []
        if self.crash is not None or self.waiting_for or not self._firmware:
            return
        for light in self._lights:
            picked = [i for i in range(len(self._firmware)) if self._picks(i, light)]
            index = next((i for i in picked if self._firmware[i][1].supports(light.caps)), None)
            if index is None:
                if not self._fields and picked:
                    self._copies[light.device_id] = picked[0]
            elif light.device_id in self._emulated:
                self._copies[light.device_id] = index
            else:
                self._claims[light.device_id] = index
        self._retarget()

    def _retarget(self) -> None:
        """Where each firmware layer's copies and claims sit, after either changed."""
        self._copy_targets = self._targets(self._copies)
        self._claim_targets = self._targets(self._claims)

    def _targets(self, layer_of: Mapping[str, int]) -> list[tuple[int, NDArray[np.intp], LedSet]]:
        targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
        for index in sorted(set(layer_of.values())):
            where, leds = self.leds.subset({d for d, i in layer_of.items() if i == index})
            if len(where):
                targets.append((index, where, leds))
        return targets

    def _fail(self, layer: str, message: str) -> None:
        self.crash = CrashInfo(layer=layer, message=message, at=self._env.now())
        self._state_changed()
        stamp = time.monotonic()
        if stamp - self._last_crash_log >= CRASH_LOG_INTERVAL_S:
            self._last_crash_log = stamp
            logger.error(
                "Zone {}: layer '{}' crashed, holding the last frame: {}",
                self.zone_id,
                layer,
                message,
            )

    def _track_speed(self, now: float, elapsed: float) -> None:
        self._render_s = elapsed if self._render_s == 0.0 else 0.9 * self._render_s + 0.1 * elapsed
        self._stride = max(1, min(self._env.fps, math.ceil(self._render_s / FRAME_BUDGET_S)))
        self._rendered.append(now)
        trim_window(self._rendered, now)
        if len(self._rendered) < SLOW_RATIO * self._env.fps:
            if self._below_since is None:
                self._below_since = now
            if self.slow_since is None and now - self._below_since >= SLOW_AFTER_S:
                self.slow_since = self._env.now()
                self._state_changed()
        else:
            self._below_since = None
            if self.slow_since is not None:
                self.slow_since = None
                self._state_changed()

    def _state_changed(self) -> None:
        if self._env.on_state_change is not None:
            self._env.on_state_change(self)
