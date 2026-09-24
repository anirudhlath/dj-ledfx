"""Shutting dj-ledfx down with a browser connected: the web server stops through granian's
Server.stop(), so the ASGI lifespan shutdown runs and an open /ws closes cleanly."""

from __future__ import annotations

import asyncio
import base64
import os
import signal
import socket
import struct
import sys
from pathlib import Path

import pytest

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


async def _close_code(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int | None:
    """Read frames until the server closes, answering its close frame as a browser does.

    Returns the close code, or None if the connection ended without one."""
    try:
        while True:
            head = await reader.readexactly(2)
            length = head[1] & 0x7F
            if length == 126:
                (length,) = struct.unpack(">H", await reader.readexactly(2))
            elif length == 127:
                (length,) = struct.unpack(">Q", await reader.readexactly(8))
            payload = await reader.readexactly(length)
            if head[0] & 0x0F == 0x8:  # close
                mask = os.urandom(4)
                echo = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload[:2]))
                writer.write(bytes([0x88, 0x80 | len(echo)]) + mask + echo)
                await writer.drain()
                return int(struct.unpack(">H", payload[:2])[0]) if len(payload) >= 2 else None
    except (asyncio.IncompleteReadError, ConnectionError):
        return None
    finally:
        writer.close()


async def test_shutdown_with_a_browser_connected_is_clean(tmp_path: Path) -> None:
    port = _free_port()
    app = await asyncio.create_subprocess_exec(
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
