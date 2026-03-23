import type {
  ActiveEffect,
  AppConfig,
  Device,
  DeviceGroup,
  EffectParamSchema,
  Preset,
  SceneData,
  TransportState,
} from "./types"

const BASE = "/api"

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`)
  }
  return resp.json() as Promise<T>
}

// Effects
export async function getEffects(): Promise<
  Record<string, Record<string, EffectParamSchema>>
> {
  return fetchJson("/effects")
}

export async function getActiveEffect(): Promise<ActiveEffect> {
  return fetchJson("/effects/active")
}

export async function setActiveEffect(req: {
  effect?: string
  params?: Record<string, unknown>
}): Promise<ActiveEffect> {
  return fetchJson("/effects/active", {
    method: "PUT",
    body: JSON.stringify(req),
  })
}

// Presets
export async function getPresets(): Promise<Preset[]> {
  return fetchJson("/presets")
}

export async function savePreset(name: string): Promise<Preset> {
  return fetchJson("/presets", {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export async function loadPreset(name: string): Promise<ActiveEffect> {
  return fetchJson(`/presets/${encodeURIComponent(name)}/load`, {
    method: "POST",
  })
}

export async function updatePreset(
  name: string,
  params: Record<string, unknown>
): Promise<Preset> {
  return fetchJson(`/presets/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify({ params }),
  })
}

export async function deletePreset(name: string): Promise<void> {
  await fetchJson(`/presets/${encodeURIComponent(name)}`, {
    method: "DELETE",
  })
}

// Devices
export async function getDevices(): Promise<Device[]> {
  return fetchJson("/devices")
}

export async function discoverDevices(): Promise<{ discovered: string[] }> {
  return fetchJson("/devices/discover", { method: "POST" })
}

export async function identifyDevice(name: string): Promise<void> {
  await fetchJson(`/devices/${encodeURIComponent(name)}/identify`, {
    method: "POST",
  })
}

export async function updateDeviceLatency(
  name: string,
  opts: { strategy?: string; manual_offset_ms?: number }
): Promise<void> {
  await fetchJson(`/devices/${encodeURIComponent(name)}/latency`, {
    method: "PUT",
    body: JSON.stringify(opts),
  })
}

export async function assignDeviceGroup(
  deviceName: string,
  groupName: string
): Promise<void> {
  await fetchJson(`/devices/${encodeURIComponent(deviceName)}/group`, {
    method: "PUT",
    body: JSON.stringify({ group: groupName }),
  })
}

// Groups
export async function getGroups(): Promise<Record<string, DeviceGroup>> {
  return fetchJson("/devices/groups")
}

export async function createGroup(
  name: string,
  color: string
): Promise<DeviceGroup> {
  return fetchJson("/devices/groups", {
    method: "POST",
    body: JSON.stringify({ name, color }),
  })
}

export async function updateGroup(
  name: string,
  updates: { name?: string; color?: string }
): Promise<DeviceGroup> {
  return fetchJson(`/devices/groups/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  })
}

export async function deleteGroup(name: string): Promise<void> {
  await fetchJson(`/devices/groups/${encodeURIComponent(name)}`, {
    method: "DELETE",
  })
}

// Config
export async function getConfig(): Promise<AppConfig> {
  return fetchJson("/config")
}

export async function updateConfig(
  partial: Partial<AppConfig>
): Promise<AppConfig> {
  return fetchJson("/config", {
    method: "PUT",
    body: JSON.stringify(partial),
  })
}

export async function exportConfig(): Promise<string> {
  const resp = await fetch(`${BASE}/config/export`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.text()
}

export async function importConfig(toml: string): Promise<AppConfig> {
  const resp = await fetch(`${BASE}/config/import`, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: toml,
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`)
  }
  return resp.json() as Promise<AppConfig>
}

// Scene
export async function getScene(): Promise<SceneData> {
  return fetchJson("/scene")
}

export async function updateSceneDevice(
  deviceId: string,
  opts: {
    position?: [number, number, number]
    geometry?: string
    direction?: number[]
    length?: number
    led_count?: number
  }
): Promise<void> {
  await fetchJson(`/scene/devices/${encodeURIComponent(deviceId)}`, {
    method: "PUT",
    body: JSON.stringify(opts),
  })
}

export async function deleteSceneDevice(deviceId: string): Promise<void> {
  await fetchJson(`/scene/devices/${encodeURIComponent(deviceId)}`, {
    method: "DELETE",
  })
}

export async function updateSceneMapping(
  type: "linear" | "radial",
  params: Record<string, unknown>,
): Promise<void> {
  await fetchJson("/scene/mapping", {
    method: "PUT",
    body: JSON.stringify({ type, params }),
  })
}

// Transport
export async function getTransport(): Promise<{ state: TransportState }> {
  return fetchJson<{ state: TransportState }>("/transport")
}

export async function setTransport(
  state: TransportState,
): Promise<{ state: TransportState }> {
  return fetchJson<{ state: TransportState }>("/transport", {
    method: "PUT",
    body: JSON.stringify({ state }),
  })
}

