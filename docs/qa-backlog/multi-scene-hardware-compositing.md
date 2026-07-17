# Multi-Scene Rendering on Real Hardware (LIFX + Govee)

**Feature:** multi-pipeline rendering — compositor display-name keying
**Priority:** high
**Type:** e2e

## Prerequisites
- App running on the LAN with real devices discovered: at least one LIFX device and one Govee strip (both have MAC-based `stable_id` != display name — this is the case the fix targets)
- Two DB scenes created: Scene A containing the LIFX device(s), Scene B containing the Govee strip(s)
- Each scene has placements positioned in the 3D editor and a mapping configured
- Transport set to PLAYING (demo beat or XDJ-AZ on the network)

## Test Steps
1. Activate Scene A and Scene B from the Scenes panel.
2. On the Live page, set Scene A's effect to something visually distinct (e.g. red beat pulse) and Scene B's to something clearly different (e.g. blue/rainbow chase).
3. Observe the physical LIFX and Govee devices side by side for ~30 seconds.
4. Move a device's placement in the 3D editor (active scene re-applies) and confirm the spatial gradient/sweep direction on the physical strip changes accordingly.
5. Deactivate Scene B and confirm its Govee devices fall back to the default pipeline's effect.

## Expected Result
- LIFX devices show Scene A's effect only; Govee devices show Scene B's effect only — no cross-bleed, and neither shows the default deck's effect while assigned.
- Strips show spatially composited output (per-LED variation that follows the 3D placement/mapping), not a raw uncomposited full-strip effect.
- After deactivating Scene B, its devices resume rendering from the default pipeline within a beat or two.

## Notes
- This exercises the compositor keying fix: `_build_pipeline` previously keyed placements by DB `stable_id` while the scheduler composites by `device_info.name`, so any device with a real MAC-based stable_id got `composite() -> None` and received the raw strip. Real LIFX/Govee hardware is the only place this manifests (mock adapters often have name == id).
- Watch logs for the new "Duplicate device display name" warning — if two devices share a display name, one placement silently wins; verify behavior matches the warning.
- Ring buffer needs ~1s warm-up after activation; brief darkness on high-latency (Govee ~100ms) devices right after activate is expected.
