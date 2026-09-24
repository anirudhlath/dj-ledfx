"""Record replies from the LIFX lights on this LAN as test fixtures (M1 plan, Task 28).

Read-only: it sends Get messages and writes each reply's payload to
tests/fixtures/lifx/recorded/<pid>-<product>-<message>.hex. Run from the repo root:

    uv run python scripts/lifx_record_fixtures.py
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path

from dj_ledfx.devices.lifx.packet import (
    GET_DEVICE_CHAIN,
    GET_HOST_FIRMWARE,
    GET_MULTIZONE_EFFECT,
    GET_TILE_EFFECT,
    GET_VERSION,
    STATE_DEVICE_CHAIN,
    STATE_HOST_FIRMWARE,
    STATE_MULTIZONE_EFFECT,
    STATE_TILE_EFFECT,
    STATE_VERSION,
    build_get_tile_effect,
)
from dj_ledfx.devices.lifx.products import LifxProduct, lifx_product
from dj_ledfx.devices.lifx.transport import LifxTransport
from dj_ledfx.devices.lifx.types import LifxDeviceRecord

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "lifx" / "recorded"
NAMES = {
    STATE_HOST_FIRMWARE: "state_host_firmware",
    STATE_VERSION: "state_version",
    STATE_DEVICE_CHAIN: "state_device_chain",
    STATE_TILE_EFFECT: "state_tile_effect",
    STATE_MULTIZONE_EFFECT: "state_multizone_effect",
}


def _queries(product: LifxProduct) -> list[tuple[int, bytes, int]]:
    queries = [(GET_HOST_FIRMWARE, b"", STATE_HOST_FIRMWARE), (GET_VERSION, b"", STATE_VERSION)]
    if product.matrix:
        queries.append((GET_DEVICE_CHAIN, b"", STATE_DEVICE_CHAIN))
        queries.append((GET_TILE_EFFECT, build_get_tile_effect(), STATE_TILE_EFFECT))
    if product.multizone:
        queries.append((GET_MULTIZONE_EFFECT, b"", STATE_MULTIZONE_EFFECT))
    return queries


async def _record(transport: LifxTransport, record: LifxDeviceRecord) -> None:
    firmware = await transport.query_host_firmware(record.mac, record.ip, record.port)
    product = lifx_product(record.product, firmware, record.vendor)
    if product is None:
        print(f"skipped unknown product {record.product}")
        return
    slug = re.sub(r"[^a-z0-9]+", "-", product.name.lower()).strip("-")
    version = f"{firmware[0]}.{firmware[1]}" if firmware else "unknown"
    for get, payload, state in _queries(product):
        request = transport.make_request(record.mac, get, payload)
        reply = await transport.request_response(request, (record.ip, record.port), state)
        if reply is None or reply.msg_type != state:
            got = "nothing" if reply is None else f"type {reply.msg_type}"
            print(f"{product.name}: no {NAMES[state]} ({got})")
            continue
        path = OUT / f"{product.pid}-{slug}-{NAMES[state]}.hex"
        path.write_text(
            f"# {NAMES[state]} ({state}) from {product.name} (pid {product.pid}), "
            f"firmware {version}, recorded {date.today()}.\n{reply.payload.hex()}\n"
        )
        print(f"wrote {path.relative_to(ROOT)}")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    transport = LifxTransport()
    await transport.open()
    try:
        for record in await transport.discover(timeout_s=3.0):
            await _record(transport, record)
    finally:
        await transport.close()


if __name__ == "__main__":
    asyncio.run(main())
