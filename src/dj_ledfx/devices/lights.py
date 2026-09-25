"""Lights as the web app sees them (spec §6.3): every device is a light, except the PC's
OpenRGB devices, which are one light with parts.

An OpenRGB device's stable id is openrgb:<host>:<port>:<index>, so the devices of one
OpenRGB server share openrgb:<host>:<port>: that is the PC's light id. Each part keeps its
own device, adapter, latency and LED order. A device with no LEDs stays in the light's
devices (so zones and attention still find it) but is no part. Every other light has one
part: itself.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_ledfx.types import DeviceInfo

PC_NAME = "PC"


def _is_openrgb(info: DeviceInfo) -> bool:
    # A ghost registered from state.db has its backend in device_type (main.py).
    return (info.backend or info.device_type).lower() == "openrgb"


def _split(device_id: str) -> tuple[str, int] | None:
    """(server id, device index) for an OpenRGB stable id, else None."""
    head, _, tail = device_id.rpartition(":")
    if not tail.isdigit() or head.count(":") < 2:
        return None
    return head, int(tail)


def light_id_of(info: DeviceInfo) -> str:
    device_id = info.effective_id
    split = _split(device_id) if _is_openrgb(info) else None
    return split[0] if split is not None else device_id


@dataclass(frozen=True, slots=True)
class LightPart:
    id: str  # the part's device id, which places it on its own (ruling 4)
    name: str
    leds: int


@dataclass(frozen=True, slots=True)
class LightEntry:
    id: str
    name: str
    devices: tuple[str, ...]  # device ids, in part order; one for a plain light
    leds: int
    parts: tuple[LightPart, ...]  # a plain light's one part is itself

    @property
    def is_pc(self) -> bool:
        return self.devices != (self.id,)

    def part_slices(self) -> tuple[tuple[LightPart, int, int], ...]:
        """Each part, and where its LEDs sit among the light's: start, stop."""
        out: list[tuple[LightPart, int, int]] = []
        start = 0
        for part in self.parts:
            out.append((part, start, start + part.leds))
            start += part.leds
        return tuple(out)


class LightIndex:
    """Which devices make which light. DeviceManager.lights keeps one, rebuilt whenever
    its devices change."""

    def __init__(self, entries: Sequence[LightEntry]) -> None:
        self._entries = tuple(entries)
        self._by_id = {entry.id: entry for entry in self._entries}
        self._light_of = {device: entry.id for entry in self._entries for device in entry.devices}

    @classmethod
    def from_infos(cls, infos: Iterable[DeviceInfo]) -> LightIndex:
        """Entries in device order, each PC where its first device is."""
        order: list[str] = []
        plain: dict[str, LightEntry] = {}
        servers: dict[str, list[tuple[int, DeviceInfo]]] = {}
        for info in infos:
            device_id = info.effective_id
            split = _split(device_id) if _is_openrgb(info) else None
            if split is None:
                if device_id not in plain:
                    order.append(device_id)
                    leds = max(0, info.led_count)
                    plain[device_id] = LightEntry(
                        device_id,
                        info.name,
                        (device_id,),
                        leds,
                        (LightPart(device_id, info.name, leds),),
                    )
                continue
            server, device_index = split
            if server not in servers:
                order.append(server)
                servers[server] = []
            servers[server].append((device_index, info))
        names = {
            server: PC_NAME if number == 1 else f"{PC_NAME} {number}"
            for number, server in enumerate(sorted(servers), start=1)
        }
        entries: list[LightEntry] = []
        for light_id in order:
            if light_id in plain:
                entries.append(plain[light_id])
                continue
            members = [info for _, info in sorted(servers[light_id], key=lambda item: item[0])]
            parts = tuple(
                LightPart(info.effective_id, info.name, info.led_count)
                for info in members
                if info.led_count > 0
            )
            entries.append(
                LightEntry(
                    id=light_id,
                    name=names[light_id],
                    devices=tuple(info.effective_id for info in members),
                    leds=sum(part.leds for part in parts),
                    parts=parts,
                )
            )
        return cls(entries)

    @property
    def entries(self) -> tuple[LightEntry, ...]:
        return self._entries

    def get(self, light_id: str) -> LightEntry | None:
        return self._by_id.get(light_id)

    def light_of(self, device_id: str) -> str:
        return self._light_of.get(device_id, device_id)

    def parts_of(self, light_id: str) -> tuple[str, ...]:
        entry = self._by_id.get(light_id)
        return entry.devices if entry is not None else ()

    def expand(self, ids: Iterable[str]) -> tuple[str, ...]:
        """Light ids (or device ids) as device ids, in order, each once. An id the index
        doesn't know passes through as it is."""
        seen: dict[str, None] = {}
        for item in ids:
            for device_id in self.parts_of(item) or (item,):
                seen.setdefault(device_id, None)
        return tuple(seen)

    def collapse(self, device_ids: Iterable[str]) -> tuple[str, ...]:
        """Device ids as light ids, in order of first appearance, each once."""
        return tuple(dict.fromkeys(self.light_of(device_id) for device_id in device_ids))
