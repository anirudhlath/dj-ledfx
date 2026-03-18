/**
 * Typed REST API client for dj-ledfx backend.
 */

const BASE = '/api';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

// Types
export interface EffectParamSchema {
  type: string;
  default: unknown;
  min?: number;
  max?: number;
  step?: number;
  choices?: string[];
  label?: string;
  description?: string;
}

export interface ActiveEffect {
  effect: string;
  params: Record<string, unknown>;
}

export interface SetEffectRequest {
  effect?: string;
  params?: Record<string, unknown>;
}

export interface Preset {
  name: string;
  effect_class: string;
  params: Record<string, unknown>;
}

export interface Device {
  name: string;
  device_type: string;
  led_count: number;
  address: string;
  group: string | null;
  send_fps: number;
  effective_latency_ms: number;
  frames_dropped: number;
  connected: boolean;
}

export interface Group {
  name: string;
  color: string;
}

export interface AppConfig {
  engine: { fps: number; max_lookahead_ms: number };
  effect: { active_effect: string; beat_pulse_palette: string[]; beat_pulse_gamma: number };
  network: { interface: string; passive_mode: boolean };
  web: { enabled: boolean; host: string; port: number; cors_origins: string[] };
  devices: {
    openrgb: Record<string, unknown>;
    lifx: Record<string, unknown>;
    govee: Record<string, unknown>;
  };
}

// Effects
export async function getEffects(): Promise<Record<string, Record<string, EffectParamSchema>>> {
  return fetchJson('/effects');
}

export async function getActiveEffect(): Promise<ActiveEffect> {
  return fetchJson('/effects/active');
}

export async function setActiveEffect(req: SetEffectRequest): Promise<ActiveEffect> {
  return fetchJson('/effects/active', {
    method: 'PUT',
    body: JSON.stringify(req),
  });
}

// Presets
export async function getPresets(): Promise<Preset[]> {
  return fetchJson('/presets');
}

export async function savePreset(name: string): Promise<Preset> {
  return fetchJson('/presets', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export async function updatePreset(name: string, params: Record<string, unknown>): Promise<Preset> {
  return fetchJson(`/presets/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify({ params }),
  });
}

export async function loadPreset(name: string): Promise<ActiveEffect> {
  return fetchJson(`/presets/${encodeURIComponent(name)}/load`, {
    method: 'POST',
  });
}

export async function deletePreset(name: string): Promise<void> {
  await fetchJson(`/presets/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

// Devices
export async function getDevices(): Promise<Device[]> {
  return fetchJson('/devices');
}

export async function discoverDevices(): Promise<{ discovered: string[] }> {
  return fetchJson('/devices/discover', { method: 'POST' });
}

export async function identifyDevice(name: string): Promise<void> {
  await fetchJson(`/devices/${encodeURIComponent(name)}/identify`, {
    method: 'POST',
  });
}

export async function updateDeviceLatency(
  name: string,
  opts: { manual_offset_ms?: number }
): Promise<void> {
  await fetchJson(`/devices/${encodeURIComponent(name)}/latency`, {
    method: 'PUT',
    body: JSON.stringify(opts),
  });
}

export async function assignDeviceGroup(deviceName: string, groupName: string): Promise<void> {
  await fetchJson(`/devices/${encodeURIComponent(deviceName)}/group`, {
    method: 'PUT',
    body: JSON.stringify({ group: groupName }),
  });
}

// Groups
export async function getGroups(): Promise<Record<string, Group>> {
  return fetchJson('/devices/groups');
}

export async function createGroup(name: string, color: string): Promise<Group> {
  return fetchJson('/devices/groups', {
    method: 'POST',
    body: JSON.stringify({ name, color }),
  });
}

export async function deleteGroup(name: string): Promise<void> {
  await fetchJson(`/devices/groups/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

// Config
export async function getConfig(): Promise<AppConfig> {
  return fetchJson('/config');
}

export async function updateConfig(partial: Partial<AppConfig>): Promise<AppConfig> {
  return fetchJson('/config', {
    method: 'PUT',
    body: JSON.stringify(partial),
  });
}

export async function exportConfig(): Promise<string> {
  const resp = await fetch(`${BASE}/config/export`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.text();
}

export async function importConfig(toml: string): Promise<AppConfig> {
  const resp = await fetch(`${BASE}/config/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: toml,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<AppConfig>;
}
