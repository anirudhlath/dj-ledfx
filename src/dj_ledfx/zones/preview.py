"""The web app's preview (spec §4.1; web spec §12.3 /preview).

One preview at a time: a new one replaces the last (ruling 9). A preview runtime renders
for the web app's preview stream only. It has no route, so it never sends to a light,
and the zone manager never syncs it, so it never captures one. A browser tab that closes
mid-preview sends no DELETE, so a preview nobody has watched for PREVIEW_IDLE_S ends by
itself (Review Focus 1).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.looks.model import validate_look
from dj_ledfx.zones.model import ZoneError, ZoneNotFoundError

if TYPE_CHECKING:
    from dj_ledfx.looks.model import Look
    from dj_ledfx.zones.manager import RuntimeHost, ZoneManager
    from dj_ledfx.zones.runtime import ZoneRuntime

PREVIEW_IDLE_S = 10.0


class PreviewNotFoundError(KeyError):
    """No preview has that id: it ended, or a newer one replaced it."""


@dataclass
class _Preview:
    id: str
    zone_id: str
    runtime: ZoneRuntime
    watched_at: float  # the preview manager's clock


class PreviewManager:
    def __init__(
        self,
        zones: ZoneManager,
        host: RuntimeHost,
        watching: Callable[[], bool],
        *,
        idle_s: float = PREVIEW_IDLE_S,
        check_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._zones = zones
        self._host = host
        self._watching = watching  # does any client watch the preview stream?
        self._idle_s = idle_s
        self._check_s = check_s
        self._clock = clock
        self._preview: _Preview | None = None

    def runtimes(self) -> list[ZoneRuntime]:
        return [] if self._preview is None else [self._preview.runtime]

    def start(self, zone_id: str, look: Look) -> str:
        """Show a look on a zone in the web app, replacing any preview. A request that
        fails leaves the current preview as it is."""
        preview_id = f"preview-{uuid.uuid4().hex[:8]}"
        runtime = self._zones.preview_runtime(f"preview:{preview_id}", zone_id, look)
        self._end()
        self._preview = _Preview(preview_id, zone_id, runtime, self._clock())
        self._host.add_runtime(runtime)
        return preview_id

    def update(self, preview_id: str, look: Look) -> None:
        """The editor changed the look: take it in place where the layers allow."""
        preview = self._require(preview_id)
        validate_look(look)
        preview.runtime.update_look(look)

    def stop(self, preview_id: str) -> None:
        self._require(preview_id)
        self._end()

    def check(self) -> None:
        """End the preview once nobody has watched it for idle_s."""
        preview = self._preview
        if preview is None:
            return
        now = self._clock()
        if self._watching():
            preview.watched_at = now
        elif now - preview.watched_at >= self._idle_s:
            logger.info(
                "Preview {} ended: nobody watched it for {:.0f} s", preview.id, self._idle_s
            )
            self._end()

    async def run(self) -> None:
        while True:
            self.check()
            await asyncio.sleep(self._check_s)

    def close(self) -> None:
        self._end()

    async def home_changed(self) -> None:
        """The map changed: show the preview on its zone's lights as they are now, or end
        it with its zone. Registered after the zone manager's listener, so the zones
        already know the new map."""
        preview = self._preview
        if preview is None:
            return
        key = preview.runtime.key
        try:
            runtime = self._zones.preview_runtime(key, preview.zone_id, preview.runtime.look)
        except (ZoneNotFoundError, ZoneError):
            logger.info("Preview {} ended: its zone is gone or has no lights", preview.id)
            self._end()
            return
        preview.runtime = runtime
        self._host.add_runtime(runtime)  # the same key: it replaces the old one

    def _require(self, preview_id: str) -> _Preview:
        preview = self._preview
        if preview is None or preview.id != preview_id:
            raise PreviewNotFoundError(preview_id)
        return preview

    def _end(self) -> None:
        if self._preview is not None:
            self._host.remove_runtime(self._preview.runtime.key)
            self._preview = None
