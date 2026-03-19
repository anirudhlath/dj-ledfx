export interface BeatState {
  bpm: number
  beatPhase: number
  barPhase: number
  isPlaying: boolean
  beatPos: number
  pitchPercent: number | null
  deckNumber: number | null
  deckName: string | null
}

export interface EffectParamSchema {
  type: string
  default: unknown
  min?: number
  max?: number
  step?: number
  choices?: string[]
  label?: string
  description?: string
}

export interface ActiveEffect {
  effect: string
  params: Record<string, unknown>
}

export interface Preset {
  name: string
  effect_class: string
  params: Record<string, unknown>
}

export interface Device {
  name: string
  device_type: string
  led_count: number
  address: string
  group: string | null
  send_fps: number
  effective_latency_ms: number
  frames_dropped: number
  connected: boolean
}

export interface DeviceGroup {
  name: string
  color: string
}

export interface SystemStatus {
  ok: boolean
  device_count: number
  avg_render_ms: number
}

export interface AppConfig {
  engine: { fps: number; max_lookahead_ms: number }
  effect: { active_effect: string; beat_pulse_palette: string[]; beat_pulse_gamma: number }
  network: { interface: string; passive_mode: boolean }
  web: { enabled: boolean; host: string; port: number; static_dir: string | null; cors_origins: string[] }
  devices: {
    openrgb: Record<string, unknown>
    lifx: Record<string, unknown>
    govee: Record<string, unknown>
  }
  scene_config: Record<string, unknown> | null
}

export interface FrameData {
  deviceName: string
  seq: number
  rgb: Uint8Array
}
