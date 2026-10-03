"""The Govee device tests' lamps take a command 20 ms after the last, not COMMAND_GAP_S, so
a restore takes a moment."""

from __future__ import annotations

import pytest

from dj_ledfx.devices.govee import adapter_base


@pytest.fixture(autouse=True)
def quick_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter_base, "COMMAND_GAP_S", 0.02)
