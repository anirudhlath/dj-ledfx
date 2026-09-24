"""Pushed WebSocket channels (web spec §12.4): the current state on connect, then changes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest_asyncio
from api_home import Api, api_home
from conftest import FakeLight

from dj_ledfx.web.ws import event_broadcast, initial_messages
from dj_ledfx.zones.model import ZoneRecord, ZonesChanged


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_text(self, text: str) -> None:
        self.messages.append(json.loads(text))

    def on(self, channel: str) -> list[dict[str, Any]]:
        return [message for message in self.messages if message["channel"] == channel]


async def until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(1.0):
        while not condition():
            await asyncio.sleep(0.01)


@pytest_asyncio.fixture
async def api(tmp_path: Path) -> AsyncIterator[Api]:
    zones = [ZoneRecord(id="desk", name="Desk", lights=("a",))]
    async with api_home(tmp_path, [FakeLight("a")], zones) as api:
        yield api


@pytest_asyncio.fixture
async def socket(api: Api) -> AsyncIterator[FakeSocket]:
    """A connected client, with the app's event broadcaster running."""
    fake = FakeSocket()
    api.app.state.connected_websockets.add(fake)
    task = asyncio.create_task(event_broadcast(api.app))
    await asyncio.sleep(0)  # let it subscribe
    yield fake
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_running_zones_are_pushed_when_they_change(api: Api, socket: FakeSocket) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})
    await until(lambda: bool(socket.on("running")))

    [message] = socket.on("running")
    assert [zone["zoneId"] for zone in message["zones"]] == ["desk"]
    assert message["zones"][0]["lookName"] == "Breathe"
    assert message["overlays"] == []


async def test_changes_that_arrive_together_are_pushed_once(api: Api, socket: FakeSocket) -> None:
    api.home.bus.emit(ZonesChanged())
    api.home.bus.emit(ZonesChanged())
    await until(lambda: bool(socket.on("running")))
    await asyncio.sleep(0.05)

    assert len(socket.on("running")) == 1


async def test_a_client_that_connects_gets_the_current_state(api: Api) -> None:
    await api.client.post("/api/zones/desk/start", json={"lookId": "classic-breathe"})

    messages = {message["channel"]: message for message in initial_messages(api.app)}

    assert [zone["zoneId"] for zone in messages["running"]["zones"]] == ["desk"]
