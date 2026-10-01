"""The tempo clock (spec §7.2): one clock, always running.

Sources, highest first: Pro DJ Link while a DJ plays, the music's beat (M7), then the
internal clock, whose BPM is set, tapped or nudged. A lock pins one source; Auto lets the
highest available one drive. The render loop samples the clock at each frame's target
time, so its read methods are synchronous and lock-free.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.events import BeatEvent, EventBus
from dj_ledfx.tempo.decks import DeckTracker
from dj_ledfx.tempo.model import (
    BEATS_PER_BAR,
    LOCKS,
    MAX_BPM,
    MAX_NUDGE_BEATS,
    MIN_BPM,
    SET_GAP_S,
    SOURCE_NAMES,
    UNLOCKED,
    DecksChanged,
    DeckView,
    DjSet,
    InternalHow,
    InternalTempo,
    TempoChanged,
    TempoError,
    TempoLock,
    TempoLockedError,
    TempoSample,
    TempoSettings,
    TempoSource,
    check_bpm,
)
from dj_ledfx.tempo.tap import TapTempo
from dj_ledfx.tempo.timeline import Timeline, nearest_beat
from dj_ledfx.timing import utcnow

if TYPE_CHECKING:
    from dj_ledfx.tempo.store import TempoStore

DRIFT_HARD_SNAP_S = 0.005  # today's drift correction: soft under 5 ms, a hard snap above
SOFT_GAIN = 0.1
SETTLE_S = 0.25  # how often run() lets the sources change hands and saves


class TempoClock:
    def __init__(
        self,
        *,
        settings: TempoSettings | None = None,
        store: TempoStore | None = None,
        event_bus: EventBus | None = None,
        now: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] = utcnow,
    ) -> None:
        settings = settings or TempoSettings()
        self._now, self._wall, self._bus, self._store = now, wall, event_bus, store
        self._lock: TempoLock = settings.lock
        self._internal = settings.internal
        self._last_set = settings.last_set
        self._held = False  # the internal clock holds against a DJ until one starts again
        self._decks = DeckTracker()
        self._taps = TapTempo()
        self._tap_origin = 0  # the beat a run's first tap landed on: a downbeat
        self._bpm = self._internal.bpm  # what the source says: the line may be soft-corrected
        self._pitch = 0.0
        start = now()
        self._line = Timeline(start, 0.0, 60.0 / self._bpm)
        self._source, self._stale = self._choose(start)
        self._snap = True  # the next beat from a source that took over snaps the phase
        self._saved = settings  # what state.db holds, as far as the clock knows
        self._running = False
        self._set_started: datetime | None = None  # the DJ set going on, if any
        self._last_beat_wall = wall()  # when the last beat was heard, for the set's end
        self.listening_on: str | None = None  # where Pro DJ Link is heard (main sets it)
        self._published = (self._tempo_state(start), self._decks.views(start, master=None))

    # --- reading: the render loop and the web app ---------------------------------------

    @property
    def lock(self) -> TempoLock:
        return self._lock

    @property
    def source(self) -> TempoSource:
        return self._source

    @property
    def stale(self) -> bool:
        """The locked source has nothing to say: the clock carries on at the last tempo."""
        return self._stale

    @property
    def held(self) -> bool:
        return self._held

    @property
    def bpm(self) -> float:
        return self._bpm

    @property
    def internal(self) -> InternalTempo:
        return self._internal

    @property
    def last_set(self) -> DjSet | None:
        return self._last_set

    def settings(self) -> TempoSettings:
        return TempoSettings(lock=self._lock, internal=self._internal, last_set=self._last_set)

    def sample_at(self, t: float) -> TempoSample:
        """The clock at time t (time.monotonic()), a frame's target time."""
        return self._line.sample(
            t, bpm=self._bpm, pitch_percent=self._pitch, source=self._source, stale=self._stale
        )

    def sample(self) -> TempoSample:
        return self.sample_at(self._now())

    def dj_playing(self) -> bool:
        return self._decks.any_playing(self._now())

    def decks(self) -> tuple[DeckView, ...]:
        return self._decks.views(self._now(), master=self._master())

    def followed_deck(self) -> DeckView | None:
        """The deck the clock follows now, if a DJ drives it."""
        return next((deck for deck in self.decks() if deck.master), None)

    # --- the internal controls (web spec §12.3) -----------------------------------------

    def set_tempo(self, lock: TempoLock, bpm: float | None = None) -> None:
        """Choose the lock, and with a BPM set the internal clock (Auto or Internal only).
        Without a BPM it releases a hold, so Auto goes back to the highest source."""
        if lock not in LOCKS:
            raise TempoError(f"No tempo lock {lock!r}")
        if bpm is not None:
            bpm = check_bpm(bpm)
            if lock not in UNLOCKED:  # 409 only for a lock that's already on
                if lock == self._lock:
                    raise TempoLockedError(lock)
                raise TempoError("A BPM can only be set with Auto or Internal")
        now = self._now()
        self._lock = lock
        if bpm is None:
            self._held = False
            self._settle(now)
        else:
            self._take_internal(now, bpm, "set")
        self._publish(now)

    def tap(self, client_time: float | None = None) -> None:
        """A tap: the run's first is a downbeat, each one after it the next beat, and from
        the third the run's tempo is the internal BPM (web spec §6.2)."""
        if self._lock not in UNLOCKED:
            raise TempoLockedError(self._lock)
        now = self._now()
        tap = self._taps.tap(now, client_time)
        if tap is None:
            return  # a double tap, or one stamped before the last
        self._take_internal(now, self._bpm if tap.bpm is None else tap.bpm, "tapped")
        if tap.index == 0:
            self._tap_origin = nearest_beat(self._line.position(tap.at), 1)
        self._line = Timeline(tap.at, float(self._tap_origin + tap.index), 60.0 / self._bpm)
        self._publish(now)

    def nudge(self, delta: float) -> None:
        """Move the beat by `delta` beats, -1 to 1: positive brings it sooner. The BPM stays."""
        if isinstance(delta, bool) or not math.isfinite(delta) or abs(delta) > MAX_NUDGE_BEATS:
            raise TempoError(f"A nudge is -{MAX_NUDGE_BEATS:g} to {MAX_NUDGE_BEATS:g} beats")
        if self._lock not in UNLOCKED:
            raise TempoLockedError(self._lock)
        now = self._now()
        if self._source != "internal":
            self._take_internal(now, self._bpm, "kept")
        elif self._lock == "auto":
            self._held = True
        beat = self._line.position(now) + delta
        self._line = self._line.moved(now, beat=beat if beat >= 0 else beat + BEATS_PER_BAR)
        self._publish(now)

    def settle(self) -> None:
        """Let the sources change hands as time passes, and keep the BPM gauge on whatever
        drives the clock (TempoClock.run calls it)."""
        now = self._now()
        self._settle(now)
        self._publish(now)
        metrics.BEAT_BPM.set(self._bpm)

    # --- Pro DJ Link ----------------------------------------------------------------------

    def on_beat(self, event: BeatEvent) -> None:
        """A player's beat (main subscribes this to BeatEvent). The clock follows one deck
        at a time; the others' beats only update their decks."""
        if not _believable(event):
            return  # a player with no track loaded, or a broken packet
        now = self._now()
        started = not self._decks.any_playing(now)
        changed = self._decks.hear(event)
        self._last_beat_wall = self._wall()
        if started:
            self._dj_started()
        self._settle(now)
        if self._source == "prodjlink" and event.device_number == self._decks.followed:
            self._follow(event, snap=self._snap or changed)
        self._publish(now)

    def _follow(self, event: BeatEvent, *, snap: bool) -> None:
        """Line the clock up with the followed deck's beat. The phase snaps once when a
        source takes over; after that, soft correction under 5 ms of drift and a hard
        snap above, as BeatClock did (spec §7.2)."""
        period = 60.0 / event.bpm
        beat = nearest_beat(self._line.position(event.timestamp), event.beat_position)
        if not snap:
            drift = event.timestamp - self._line.time_of(beat)
            if abs(drift) < DRIFT_HARD_SNAP_S:
                period *= 1.0 + (drift / period) * SOFT_GAIN
                logger.trace("Beat drift {:.1f} ms: soft correction", drift * 1000.0)
            else:
                logger.debug("Beat drift {:.1f} ms: hard snap", drift * 1000.0)
        self._line = Timeline(event.timestamp, float(beat), period)
        self._bpm, self._pitch, self._snap = event.bpm, event.pitch_percent, False
        metrics.BEAT_BPM.set(event.bpm)
        metrics.BEAT_PHASE.set((event.beat_position - 1) / BEATS_PER_BAR)

    def _dj_started(self) -> None:
        """A DJ starts playing: a hold ends ("until a higher source starts again"), and a
        set begins, or goes on if the last one ended less than SET_GAP_S ago."""
        self._held = False
        wall, last = self._wall(), self._last_set
        if last is not None and (wall - last.ended).total_seconds() < SET_GAP_S:
            self._set_started = last.started
        else:
            self._set_started = wall

    def _dj_quiet(self, now: float) -> None:
        """The last deck went quiet: the set so far is the last set."""
        if self._set_started is not None and not self._decks.any_playing(now):
            self._last_set = DjSet(self._set_started, self._last_beat_wall)
            self._set_started = None
        self._decks.forget(now)

    # --- keeping time, and the settings ---------------------------------------------------

    async def run(self) -> None:
        """Let the sources change hands as time passes, and save what changed."""
        self._running = True
        while self._running:
            await asyncio.sleep(SETTLE_S)
            self.settle()
            await self.save()

    def stop(self) -> None:
        self._running = False

    async def save(self) -> None:
        """Write the settings to state.db if they aren't what it holds. They count as saved
        only once the write is done, so a save cancelled or failing part-way leaves them
        for the next."""
        settings = self.settings()
        if self._store is None or settings == self._saved:
            return
        try:
            await self._store.save(settings)
        except Exception as exc:  # a full disk never stops the clock
            logger.warning("Couldn't save the tempo settings: {}", exc)
            return
        self._saved = settings

    async def reload(self) -> None:
        """Take what state.db holds now: a restored backup's lock, internal BPM and set."""
        if self._store is None:
            return
        settings = await self._store.load()
        now = self._now()
        self._saved = settings
        self._lock, self._internal, self._last_set = (
            settings.lock,
            settings.internal,
            settings.last_set,
        )
        self._held = False
        if self._choose(now)[0] == "internal":  # the backup's BPM drives, without a jump
            self._bpm, self._pitch = self._internal.bpm, 0.0
            self._line = self._line.moved(now, period=60.0 / self._bpm)
        self._settle(now)
        self._publish(now)

    # --- inside ---------------------------------------------------------------------------

    def _take_internal(self, now: float, bpm: float, how: InternalHow) -> None:
        """The internal clock drives from now at this BPM, without a jump. Under Auto it
        holds until a DJ starts again."""
        self._internal = InternalTempo(bpm, how, self._wall())
        self._held = self._lock == "auto"
        self._bpm, self._pitch = bpm, 0.0
        self._line = self._line.moved(now, period=60.0 / bpm)
        self._settle(now)

    def _choose(self, now: float) -> tuple[TempoSource, bool]:
        """The source that drives, and whether it's stale (locked, with nothing to say)."""
        dj = self._decks.any_playing(now)
        if self._lock == "prodjlink":
            return "prodjlink", not dj
        if self._lock == "music":
            return "music", True  # the music's beat arrives in M7
        if self._lock == "auto" and dj and not self._held:
            return "prodjlink", False
        return "internal", False

    def _settle(self, now: float) -> None:
        self._dj_quiet(now)
        source, self._stale = self._choose(now)
        if source == self._source:
            return
        logger.info("Tempo source: {} to {}", SOURCE_NAMES[self._source], SOURCE_NAMES[source])
        self._source = source
        if source != "internal":
            self._snap = True  # the phase snaps once, to the new source's next beat
            self._taps.reset()
            return
        # Hand-back: the clock carries on at the last BPM and phase, without a jump.
        if self._bpm != self._internal.bpm:
            self._internal = InternalTempo(self._bpm, "kept", self._wall())
        self._pitch = 0.0
        self._line = self._line.moved(now, period=60.0 / self._bpm)

    def _master(self) -> int | None:
        return self._decks.followed if self._source == "prodjlink" and not self._stale else None

    def _tempo_state(self, now: float) -> tuple[object, ...]:
        return (
            self._source,
            self._lock,
            self._bpm,
            self._stale,
            self._held,
            self._internal,
            self._last_set,
            self._decks.any_playing(now),
        )

    def _publish(self, now: float) -> None:
        """Tell the web app's channels what changed: inputs and decks (web spec §12.4)."""
        tempo = self._tempo_state(now)
        decks = self._decks.views(now, master=self._master())
        published_tempo, published_decks = self._published
        self._published = (tempo, decks)
        if self._bus is None:
            return
        if tempo != published_tempo:
            self._bus.emit(TempoChanged())
        if decks != published_decks:
            self._bus.emit(DecksChanged())


def _believable(event: BeatEvent) -> bool:
    return (
        math.isfinite(event.timestamp)
        and math.isfinite(event.pitch_percent)
        and math.isfinite(event.bpm)
        and MIN_BPM <= event.bpm <= MAX_BPM
    )
