# Device State Restore on Stop Across Scene Activation Cycles

**Feature:** transport controls + multi-pipeline teardown interaction
**Priority:** low
**Type:** integration

## Prerequisites
- Real hardware (LIFX and/or Govee) with a known idle state (e.g. set bulbs to a specific color/brightness before the app connects)
- App started fresh (transport STOPPED — devices' state captured on connect)
- One DB scene containing some of the devices

## Test Steps
1. Note each device's physical state before pressing Play.
2. Press Play (transport PLAYING). Activate the scene; let it render for ~30s.
3. While still playing, deactivate and reactivate the scene a few times (pipeline teardown/rebuild).
4. Press Stop.
5. Observe all devices — both those in the scene and those on the default pipeline.
6. Repeat once more: Play → activate scene → Stop, then check again.
7. Also test SIMULATING mode: verify devices stay at their restored/captured state while the web preview animates.

## Expected Result
- On Stop, every device returns to its captured pre-play state (or the documented 50% white default where the adapter lacks capture support) — scene activation/deactivation cycles must not clobber or lose the captured state.
- Devices that moved between pipelines (scene ↔ default) restore the same as devices that never moved.
- SIMULATING renders to the web UI only; physical devices remain untouched.

## Notes
- State capture happens on connect (when stopped) and restore on stop; pipeline teardown re-routes devices in the scheduler — the risk is a teardown path overwriting or skipping the captured state.
- `capture_state()` default is 50% white; LIFX/Govee adapters may override — expected restore fidelity differs per protocol, note what you observe per device type.
- If a device disconnects mid-session (ghost/demote) and is re-promoted, its captured state may be re-captured while playing — edge case worth one ad-hoc try, log a backlog ticket if odd.
