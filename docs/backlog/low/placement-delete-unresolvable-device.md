# Placement DELETE falls back to display name when device is unknown

**Summary:** `DELETE /api/scenes/{id}/devices/{name}` resolves display name → stable_id via DeviceManager. If the device is absent entirely (not even a GhostAdapter — e.g. fresh session before discovery), the fallback uses the display name and silently no-ops for stable_id-keyed placement rows.

**Context:** Edge case noted in code review (2026-06-11). The ghost lifecycle keeps known devices resolvable, so this only bites before first discovery.

**Acceptance criteria:**
- When DeviceManager can't resolve the name, fall back to a DB `devices`-table lookup by name to find the stable_id before deleting.
- Test: placement stored under a stable_id whose device is not in DeviceManager can still be deleted by display name.
