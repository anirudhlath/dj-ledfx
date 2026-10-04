"""OpenRGB's devices: one connection to each server, and each device known by what it is.

A device's stable id is openrgb:<host>:<port>:<number>, the number being the place in the
server's list it was first found at. That place changes whenever a device before it comes or
goes, so a known device is found again by its identity (`OpenRGBIdentity`: its name, serial
and location, which its row keeps), wherever it sits now, and keeps its id.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from loguru import logger

from dj_ledfx.config import AppConfig, OpenRGBConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice, configured_fps
from dj_ledfx.devices.heuristics import estimate_device_latency_ms
from dj_ledfx.devices.openrgb import OpenRGBAdapter, OpenRGBIdentity, OpenRGBServer
from dj_ledfx.latency.tracker import LatencyTracker, tracker_for

Address = tuple[str, int]  # an OpenRGB server's host and port


def _tracker(cfg: OpenRGBConfig, adapter: OpenRGBAdapter) -> LatencyTracker:
    """A static strategy keeps the configured latency; the others start from the heuristic
    for the device's name (OpenRGB can't be probed)."""
    static = cfg.latency_strategy == "static"
    seed = None if static else estimate_device_latency_ms(adapter.device_info.name)
    return tracker_for(cfg, seed_ms=seed, display_ms=adapter.display_ms)


def _split(stable_id: str) -> tuple[Address, int] | None:
    """An OpenRGB stable id's server and number; None for any other id."""
    kind, _, rest = stable_id.partition(":")
    head, _, number = rest.rpartition(":")
    host, _, port = head.rpartition(":")
    if kind != "openrgb" or not host or not port.isdigit() or not number.isdigit():
        return None
    return (host, int(port)), int(number)


def _first_place(row: Mapping[str, Any]) -> tuple[int, str]:
    """Where a known device was first found: the number in its id (rows with other ids last)."""
    split = _split(row["id"])
    return (split[1] if split is not None else sys.maxsize, row["id"])


def place_known(
    rows: Sequence[Mapping[str, Any]], listed: Sequence[OpenRGBIdentity]
) -> dict[str, int]:
    """Where each known device of a server sits in its list now, by row id; a row whose
    device isn't listed is left out.

    A listed device can be a row's when their names agree and their serials don't differ
    (`OpenRGBIdentity.likeness`). Pairs whose serials agree are settled first, then those
    whose locations agree, then the rest, which a row from before identities were kept only
    has. Among pairs alike, rows in the order they were first found take the devices in list
    order: devices of one name keep their order when others come or go. Each device is one
    row's at most."""
    pairs: list[tuple[bool, bool, int, int, str]] = []
    for rank, row in enumerate(sorted(rows, key=_first_place)):
        known = OpenRGBIdentity.of_row(row)
        for place, device in enumerate(listed):
            likeness = known.likeness(device)
            if likeness is not None:
                serial, location = likeness
                pairs.append((not serial, not location, rank, place, row["id"]))
    placed: dict[str, int] = {}
    taken: set[int] = set()
    for *_, place, row_id in sorted(pairs):
        if row_id not in placed and place not in taken:
            placed[row_id] = place
            taken.add(place)
    return placed


def device_ids(
    address: Address, rows: Sequence[Mapping[str, Any]], listed: Sequence[OpenRGBIdentity]
) -> list[str]:
    """Each listed device's stable id, in list order: its known row's, else a new one whose
    number is its place, or the next one up that no known row's id holds (a row may hold a
    number for a device that has since moved)."""
    placed = {place: row_id for row_id, place in place_known(rows, listed).items()}
    held = {split[1] for row in rows if (split := _split(row["id"])) is not None}
    host, port = address
    ids: list[str] = []
    for place in range(len(listed)):
        if place in placed:
            ids.append(placed[place])
            continue
        number = place
        while number in held:
            number += 1
        held.add(number)
        ids.append(f"openrgb:{host}:{port}:{number}")
    return ids


class OpenRGBBackend(DeviceBackend):
    def __init__(self) -> None:
        self._servers: dict[Address, OpenRGBServer] = {}

    def is_enabled(self, config: AppConfig) -> bool:
        return config.devices.openrgb.enabled

    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
        known: Sequence[Mapping[str, Any]] = (),
    ) -> list[DiscoveredDevice]:
        """The config's server's devices, each under its known row's id wherever it sits now,
        or a new id; those online already (skip_ids) are left out."""
        orgb = config.devices.openrgb
        address = (orgb.host, orgb.port)
        server = self._server(address)
        try:
            listed = await server.devices()
        except OSError as exc:
            logger.debug("OpenRGB discovery failed at {}: {}", server.address, exc)
            return []
        logger.info("Discovered {} OpenRGB devices", len(listed))

        rows = self._rows(known, config).get(address, [])
        ids = device_ids(address, rows, [OpenRGBIdentity.of(device) for device in listed])
        results: list[DiscoveredDevice] = []
        for device, stable_id in zip(listed, ids, strict=True):
            if skip_ids and stable_id in skip_ids:
                continue
            try:
                found = await self._set_up(server, device, stable_id, config)
            except ConnectionError as exc:
                logger.warning("{}: a later scan tries it again", exc)
                continue
            results.append(found)
            if on_found is not None:
                on_found(found)
        return results

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Each known device found on its server by what it is, wherever it sits now, and
        set up under its row's id. One the server doesn't list stays offline."""
        results: list[DiscoveredDevice] = []
        for address, rows in self._rows(device_rows, config).items():
            server = self._server(address)
            try:
                listed = await server.devices()
            except OSError as exc:
                logger.warning(
                    "OpenRGB server at {} didn't answer ({}): its {} known device(s) stay offline",
                    server.address,
                    exc,
                    len(rows),
                )
                continue
            placed = place_known(rows, [OpenRGBIdentity.of(device) for device in listed])
            for row in rows:
                name = row.get("name") or row["id"]
                place = placed.get(row["id"])
                if place is None:
                    logger.warning(
                        "Known OpenRGB device '{}' isn't on the server at {}: it stays offline",
                        name,
                        server.address,
                    )
                    continue
                try:
                    results.append(await self._set_up(server, listed[place], row["id"], config))
                except ConnectionError as exc:
                    logger.warning("{}: a later scan tries it again", exc)
                    continue
                logger.info("Reconnected known OpenRGB device '{}' at {}", name, server.address)
        return results

    async def shutdown(self) -> None:
        servers, self._servers = list(self._servers.values()), {}
        for server in servers:
            await server.close()

    def _server(self, address: Address) -> OpenRGBServer:
        """The server's one connection, which every device on it shares."""
        if address not in self._servers:
            self._servers[address] = OpenRGBServer(*address)
        return self._servers[address]

    @staticmethod
    def _rows(
        rows: Sequence[Mapping[str, Any]], config: AppConfig
    ) -> dict[Address, list[Mapping[str, Any]]]:
        """The known OpenRGB devices' rows by server: the one in the row's id, else the
        config's."""
        orgb = config.devices.openrgb
        by_server: dict[Address, list[Mapping[str, Any]]] = {}
        for row in rows:
            if row.get("backend") != "openrgb":
                continue
            split = _split(row["id"])
            address = split[0] if split is not None else (orgb.host, orgb.port)
            by_server.setdefault(address, []).append(row)
        return by_server

    async def _set_up(
        self, server: OpenRGBServer, device: Any, stable_id: str, config: AppConfig
    ) -> DiscoveredDevice:
        orgb = config.devices.openrgb
        adapter = OpenRGBAdapter(
            server, device, stable_id, max_fps=configured_fps(config, orgb.max_fps)
        )
        await adapter.connect()
        return DiscoveredDevice(
            adapter=adapter, tracker=_tracker(orgb, adapter), max_fps=adapter.stream_fps
        )
