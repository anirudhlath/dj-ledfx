"""Named effect presets with TOML persistence."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w


@dataclass(frozen=True)
class Preset:
    name: str
    effect_class: str
    params: dict[str, Any]


class PresetStore:
    """Persists effect presets to a TOML file with atomic writes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._presets: dict[str, Preset] = {}
        if path.exists():
            self._load()

    def _load(self) -> None:
        with open(self._path, "rb") as f:
            data = tomllib.load(f)
        for name, entry in data.get("presets", {}).items():
            self._presets[name] = Preset(
                name=name,
                effect_class=entry["effect_class"],
                params=entry.get("params", {}),
            )

    def _persist(self) -> None:
        data: dict[str, Any] = {"presets": {}}
        for name, preset in self._presets.items():
            data["presets"][name] = {
                "effect_class": preset.effect_class,
                "params": preset.params,
            }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_bytes(tomli_w.dumps(data).encode())
        os.replace(tmp, self._path)

    def list(self) -> list[Preset]:
        return list(self._presets.values())

    def save(self, preset: Preset) -> None:
        self._presets[preset.name] = preset
        self._persist()

    def delete(self, name: str) -> None:
        if name not in self._presets:
            raise KeyError(f"Preset not found: {name}")
        del self._presets[name]
        self._persist()

    def load(self, name: str) -> Preset:
        if name not in self._presets:
            raise KeyError(f"Preset not found: {name}")
        return self._presets[name]
