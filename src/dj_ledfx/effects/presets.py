"""Named effect presets with TOML persistence."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dj_ledfx.config import atomic_toml_write

if TYPE_CHECKING:
    from dj_ledfx.persistence.state_db import StateDB


@dataclass(frozen=True)
class Preset:
    name: str
    effect_class: str
    params: dict[str, Any]


class PresetStore:
    """Persists effect presets to a TOML file or SQLite StateDB."""

    def __init__(
        self,
        path: Path | None = None,
        state_db: StateDB | None = None,
    ) -> None:
        self._path = path
        self._state_db = state_db
        self._presets: dict[str, Preset] = {}
        if path is not None and path.exists():
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
        if self._path is None:
            return
        data: dict[str, Any] = {"presets": {}}
        for name, preset in self._presets.items():
            data["presets"][name] = {
                "effect_class": preset.effect_class,
                "params": preset.params,
            }
        atomic_toml_write(data, self._path)

    async def load_from_db(self) -> None:
        """Load presets from StateDB into memory."""
        if self._state_db is None:
            return
        rows = await self._state_db.load_presets()
        for row in rows:
            params = json.loads(row["params"]) if row["params"] else {}
            self._presets[row["name"]] = Preset(
                name=row["name"],
                effect_class=row["effect_class"],
                params=params,
            )

    async def save_async(self, preset: Preset) -> None:
        """Save a preset to memory and StateDB."""
        self._presets[preset.name] = preset
        if self._state_db is not None:
            await self._state_db.save_preset(
                name=preset.name,
                effect_class=preset.effect_class,
                params=json.dumps(preset.params),
            )

    async def delete_async(self, name: str) -> None:
        """Delete a preset from memory and StateDB."""
        if name not in self._presets:
            raise KeyError(f"Preset not found: {name}")
        del self._presets[name]
        if self._state_db is not None:
            await self._state_db.delete_preset(name)

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
