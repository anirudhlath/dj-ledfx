"""The tempo clock (spec §7.2): one clock, always running.

Sources, highest first: Pro DJ Link while a DJ plays, the music's beat (M7), then the
internal clock, whose BPM is set, tapped or nudged. A lock pins one source; Auto lets the
highest available one drive. The render loop samples the clock at each frame's target
time, so its read methods are synchronous and lock-free.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import datetime

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.events import EventBus
from dj_ledfx.tempo.decks import DeckTracker
from dj_ledfx.tempo.model import (
    BEATS_PER_BAR,
    LOCKS,
    MAX_NUDGE_BEATS,
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


class TempoClock:
    def __init__(
        self,
        *,
        settings: TempoSettings | None = None,
        event_bus: EventBus | None = None,
        now: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] = utcnow,
    ) -> None:
        settings = settings or TempoSettings()
        self._now, self._wall, self._bus = now, wall, event_bus
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
        self._dirty = False  # settings changed since they were saved
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
            if lock not in UNLOCKED:
                raise TempoLockedError(lock)
        now = self._now()
        if lock != self._lock:
            self._lock, self._dirty = lock, True
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

    # --- inside ---------------------------------------------------------------------------

    def _take_internal(self, now: float, bpm: float, how: InternalHow) -> None:
        """The internal clock drives from now at this BPM, without a jump. Under Auto it
        holds until a DJ starts again."""
        self._internal = InternalTempo(bpm, how, self._wall())
        self._held = self._lock == "auto"
        self._dirty = True
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
            self._internal, self._dirty = InternalTempo(self._bpm, "kept", self._wall()), True
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
