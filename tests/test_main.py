"""The real entry point in a subprocess. Shutting dj-ledfx down with a browser connected:
the web server stops through granian's Server.stop(), so the ASGI lifespan shutdown runs
and an open /ws closes cleanly. Browser tabs closing their sockets never freeze the app.
And the app serves the home map, its zones and previews."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import signal
import socket
import struct
import sys
from pathlib import Path

import httpx
import pytest

from dj_ledfx.home.seed import seed_home

pytest.importorskip("fastapi")  # the web extra

# The real entry point with discovery switched off, so the test never reaches a light.
_DRIVER = """
import sys

import dj_ledfx.main
from dj_ledfx.devices.backend import DeviceBackend

DeviceBackend._registry.clear()
sys.argv = ["dj_ledfx", *sys.argv[1:]]
dj_ledfx.main.main()
"""


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def _open_websocket(port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    key = base64.b64encode(os.urandom(16)).decode()
    writer.write(
        f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n".encode()
    )
    await writer.drain()
    status = (await reader.readuntil(b"\r\n\r\n")).split(b"\r\n", 1)[0]
    assert status == b"HTTP/1.1 101 Switching Protocols", status
    return reader, writer


async def _open_websocket_when_up(
    port: int, app: asyncio.subprocess.Process
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    async with asyncio.timeout(30):
        while True:
            try:
                return await _open_websocket(port)
            except ConnectionError:
                if app.returncode is not None:
                    output = await app.stdout.read() if app.stdout else b""
                    pytest.fail(f"dj-ledfx exited on start:\n{output.decode()}")
                await asyncio.sleep(0.1)


_CLOSE = 0x8  # the close frame's opcode


def _client_frame(opcode: int, payload: bytes) -> bytes:
    """One masked frame, as a browser sends it (a payload under 126 bytes)."""
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked


async def _read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    """The server's next frame: its opcode and payload."""
    head = await reader.readexactly(2)
    length = head[1] & 0x7F
    if length == 126:
        (length,) = struct.unpack(">H", await reader.readexactly(2))
    elif length == 127:
        (length,) = struct.unpack(">Q", await reader.readexactly(8))
    return head[0] & 0x0F, await reader.readexactly(length)


async def _close_code(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int | None:
    """Read frames until the server closes, answering its close frame as a browser does.

    Returns the close code, or None if the connection ended without one."""
    try:
        while True:
            opcode, payload = await _read_frame(reader)
            if opcode == _CLOSE:
                writer.write(_client_frame(_CLOSE, payload[:2]))
                await writer.drain()
                return int(struct.unpack(">H", payload[:2])[0]) if len(payload) >= 2 else None
    except (asyncio.IncompleteReadError, ConnectionError):
        return None
    finally:
        writer.close()


async def _start_app(tmp_path: Path, port: int) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _DRIVER,
        "--demo",
        "--web",
        "--web-host",
        "127.0.0.1",
        "--web-port",
        str(port),
        "--config",
        str(tmp_path / "config.toml"),
        "--db",
        str(tmp_path / "state.db"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


async def test_shutdown_with_a_browser_connected_is_clean(tmp_path: Path) -> None:
    port = _free_port()
    app = await _start_app(tmp_path, port)
    try:
        reader, writer = await _open_websocket_when_up(port, app)
        browser = asyncio.create_task(_close_code(reader, writer))
        app.send_signal(signal.SIGTERM)  # what `docker stop` sends
        output = (await asyncio.wait_for(app.communicate(), 30))[0].decode()
        close_code = await asyncio.wait_for(browser, 5)
    finally:
        if app.returncode is None:
            app.kill()
            await app.wait()

    assert "Traceback" not in output, output
    assert "Unexpected exit" not in output, output
    assert "dj-ledfx stopped" in output, output
    assert close_code == 1001  # going away
    assert app.returncode == 0


async def _read_until_closed(reader: asyncio.StreamReader, seconds: float) -> None:
    """Read the server's frames for up to `seconds`, stopping early at its close frame."""
    try:
        async with asyncio.timeout(seconds):
            while (await _read_frame(reader))[0] != _CLOSE:
                pass
    except (TimeoutError, asyncio.IncompleteReadError, ConnectionError):
        pass


async def _open_and_close_a_tab(port: int) -> None:
    """A tab of the web app: it subscribes to the beat at web/'s rate (live-client.ts's
    BEAT_FPS), reads it for a moment, then closes its socket as a closing tab does."""
    reader, writer = await _open_websocket(port)
    try:
        subscribe = {"action": "subscribe_beat", "id": "beat", "fps": 30}
        writer.write(_client_frame(0x1, json.dumps(subscribe).encode()))  # a text frame
        await writer.drain()
        await _read_until_closed(reader, 0.1)
        writer.write(_client_frame(_CLOSE, struct.pack(">H", 1001)))  # going away
        await writer.drain()
        await _read_until_closed(reader, 1.0)  # the server's close, as a browser waits for it
    finally:
        writer.close()


async def test_tabs_closing_their_sockets_never_freeze_the_app(tmp_path: Path) -> None:
    port = _free_port()
    app = await _start_app(tmp_path, port)
    try:
        # httpx's own timeout is off: the 5 s timeout below says which tab froze the app.
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}/api", timeout=None
        ) as client:
            await _get_when_up(client, "/running", app)
            for tab in range(1, 31):  # granian 2.7.2 froze within the first three
                try:
                    async with asyncio.timeout(5):  # a frozen app never answers again
                        await _open_and_close_a_tab(port)
                        running = await client.get("/running")
                except TimeoutError:
                    pytest.fail(f"dj-ledfx stopped answering after {tab} tab(s) closed")
                assert running.status_code == 200
        app.send_signal(signal.SIGTERM)
        output = (await asyncio.wait_for(app.communicate(), 30))[0].decode()
    finally:
        if app.returncode is None:
            app.kill()
            await app.wait()

    assert "Traceback" not in output, output
    assert app.returncode == 0


async def _get_when_up(
    client: httpx.AsyncClient, path: str, app: asyncio.subprocess.Process
) -> httpx.Response:
    async with asyncio.timeout(30):
        while True:
            try:
                return await client.get(path)
            except httpx.TransportError:
                if app.returncode is not None:
                    output = await app.stdout.read() if app.stdout else b""
                    pytest.fail(f"dj-ledfx exited on start:\n{output.decode()}")
                await asyncio.sleep(0.1)


async def test_the_app_serves_the_home_map_its_zones_and_previews(tmp_path: Path) -> None:
    port = _free_port()
    app = await _start_app(tmp_path, port)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}/api") as client:
            home = (await _get_when_up(client, "/home", app)).json()
            zones = (await client.get("/zones")).json()
            preview = await client.post("/preview", json={"zoneId": "home", "lookId": "sunset"})
        app.send_signal(signal.SIGTERM)
        output = (await asyncio.wait_for(app.communicate(), 30))[0].decode()
    finally:
        if app.returncode is None:
            app.kill()
            await app.wait()

    assert [room["id"] for room in home["rooms"]] == [room.id for room in seed_home().rooms]
    assert (zones[0]["id"], zones[0]["kind"]) == ("home", "home")
    # The previews are wired: the whole home is refused for having no lights, not a 503.
    assert preview.status_code == 400 and "has no lights" in preview.json()["detail"]
    assert "Traceback" not in output, output
    assert app.returncode == 0
