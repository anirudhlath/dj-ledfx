# Code Improvement Backlog

Items identified during code review but deferred due to scope or complexity.

## Abstraction Leak: `getattr(adapter, "_record")` in DiscoveryOrchestrator

**File:** `src/dj_ledfx/devices/discovery.py:197`

`_persist_device()` reaches into Govee adapter internals via `getattr(adapter, "_record", None)` to extract `device_id` and `sku` for DB persistence. This breaks the adapter abstraction boundary.

**Fix:** Add `device_id: str | None` and `sku: str | None` fields to `DeviceInfo` so all adapters expose Govee-specific fields through the standard interface. Govee adapters populate them; others leave them as `None`. Then `_persist_device` reads `info.device_id` / `info.sku` instead of reaching into privates.

**Why deferred:** Requires changing the `DeviceInfo` frozen dataclass (used across 15+ files) and updating all adapter constructors.

## WebSocket `_stats_poll` redundant device status join

**File:** `src/dj_ledfx/web/ws.py:87-93`

`_stats_poll` iterates `manager.devices` every poll cycle to build a `status_by_name` dict, then merges it into stats. The `status` field is already on `ManagedDevice` and could be included in `DeviceStats` directly.

**Fix:** Add `status: str` field to `DeviceStats` (in `types.py`), populate it in `LookaheadScheduler.get_device_stats()`, and remove the separate manager iteration in `_stats_poll`.

**Why deferred:** `DeviceStats` is a frozen dataclass used by multiple consumers (scheduler, web, status loop). Adding a field requires updating all construction sites and test assertions.

## LIFX sequential version queries in `unicast_sweep()`

**File:** `src/dj_ledfx/devices/lifx/transport.py` (unicast_sweep version query loop)

After parallel unicast sweep discovers N devices, version queries run sequentially (0.5-1.0s each). For 10 devices this is 5-10 seconds of serial waiting.

**Fix:** Parallelize version queries with `asyncio.gather()`. Requires the `_query_version` method to handle concurrent handler dispatch (currently it monkey-patches `_on_packet_received` which is not safe for concurrent use). Would need a handler registry keyed by (ip, msg_type) instead of a single global handler swap.

**Why deferred:** Non-trivial refactor of the handler dispatch pattern shared by discover/sweep/probe. Risk of subtle race conditions.

## N+1 queries in `export_toml()` for scenes

**File:** `src/dj_ledfx/persistence/toml_io.py:88-99`

Inside the `for scene in scenes` loop, each scene issues two separate DB queries (`load_scene_effect_state` + `load_scene_placements`). With N scenes this is 2N+1 round-trips through `asyncio.to_thread`.

**Fix:** Add bulk-load methods to StateDB (`load_all_scene_effect_states()`, `load_all_scene_placements()`) that fetch everything in one query, then group by scene_id in Python.

**Why deferred:** Export is an infrequent user-triggered operation, not a hot path. The current approach is correct and simple.

## `import_toml()` individual awaits in loops

**File:** `src/dj_ledfx/persistence/toml_io.py:178-275`

Import awaits `upsert_device`, `save_scene`, `save_placement`, etc. one at a time in loops. Each goes through lock + thread dispatch + individual commit.

**Fix:** Add batch variants using `executemany` per entity type (similar to existing `save_config_bulk`), wrap in a single transaction.

**Why deferred:** Import is infrequent. Current approach is simple and correct. Batching adds complexity for minimal user-visible benefit.

## IP extraction from address string

**Files:** `src/dj_ledfx/devices/discovery.py:196`, `src/dj_ledfx/web/router_scene.py:438`

Both use `address.split(":")[0] if ":" in address else address` to extract IP. This is fragile with IPv6 addresses.

**Fix:** Add `DeviceInfo.ip` property that properly parses the address field, or store IP separately from port in `DeviceInfo`.

**Why deferred:** IPv6 is not a current use case for LAN device discovery. Low risk.
