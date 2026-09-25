// The REST client (spec §12.3). Every request the app makes goes through here; components never
// call fetch (§12). Paths are checked against the backend's schema (ApiPath) or §12.3 (PendingPath).
import type {
  Anchor, AnchorInput, ApiPath, AttentionItem, CreateGroup, Home, HomeUpdate, Id, Inputs, Light, Look,
  PendingPath, Placement, PlacementState, PreviewRequest, PreviewResponse, Running, RunningZone, Signal, StartRequest,
  StartResponse, SubZone, SubZoneInput, UpdateGroup, Zone,
} from './contract'

/** A request that failed. `status` 0 means no answer at all: the server is down, or the network. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly path: string

  constructor(status: number, detail: string, path: string) {
    super(`${path}: ${status === 0 ? 'no answer' : status} ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.path = path
  }
}

/** A path template with its parameters filled in and encoded. */
export function apiPath(template: ApiPath | PendingPath, params: Record<string, string> = {}): string {
  return template.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = params[name]
    if (value === undefined) throw new Error(`${template} needs {${name}}`)
    return encodeURIComponent(value)
  })
}

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

// Absolute: Node's fetch (Vitest, MSW's Node server) rejects a relative URL (decision 13).
function url(path: string): URL {
  return new URL(path, globalThis.location?.origin ?? 'http://localhost')
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(url(path), {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    throw new ApiError(0, error instanceof Error ? error.message : String(error), path)
  }
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response), path)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** FastAPI's `detail`: a sentence, or a 422's list of problems. */
async function errorDetail(response: Response): Promise<string> {
  try {
    const { detail } = (await response.json()) as { detail?: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((problem) => (problem as { msg?: unknown }).msg)
        .filter((msg): msg is string => typeof msg === 'string')
        .join('; ')
    }
  } catch {
    // Not JSON: a proxy's error page, say.
  }
  return response.statusText || `HTTP ${response.status}`
}

const zone = (id: Id) => ({ zone_id: id })
const look = (id: Id) => ({ look_id: id })
const light = (id: Id) => ({ light_id: id })

export const api = {
  // Engine M1
  looks: () => request<Look[]>('GET', apiPath('/api/looks')),
  look: (id: Id) => request<Look>('GET', apiPath('/api/looks/{look_id}', look(id))),
  saveLook: (body: Look) => request<Look>('POST', apiPath('/api/looks'), body),
  updateLook: (id: Id, body: Look) => request<Look>('PUT', apiPath('/api/looks/{look_id}', look(id)), body),
  deleteLook: (id: Id) => request<void>('DELETE', apiPath('/api/looks/{look_id}', look(id))),
  setStarred: (id: Id, starred: boolean) =>
    request<Look>('PUT', apiPath('/api/looks/{look_id}/starred', look(id)), { starred }),
  zones: () => request<Zone[]>('GET', apiPath('/api/zones')),
  createGroup: (body: CreateGroup) => request<Zone>('POST', apiPath('/api/zones/groups'), body),
  updateGroup: (id: Id, body: UpdateGroup) =>
    request<Zone>('PUT', apiPath('/api/zones/groups/{zone_id}', zone(id)), body),
  deleteGroup: (id: Id) => request<void>('DELETE', apiPath('/api/zones/groups/{zone_id}', zone(id))),
  running: () => request<Running>('GET', apiPath('/api/running')),
  start: (zoneId: Id, body: StartRequest) =>
    request<StartResponse>('POST', apiPath('/api/zones/{zone_id}/start', zone(zoneId)), body),
  setBrightness: (zoneId: Id, value: number) =>
    request<RunningZone>('PUT', apiPath('/api/zones/{zone_id}/brightness', zone(zoneId)), { value }),
  off: (zoneId: Id) => request<void>('POST', apiPath('/api/zones/{zone_id}/off', zone(zoneId))),
  restart: (zoneId: Id) => request<RunningZone>('POST', apiPath('/api/zones/{zone_id}/restart', zone(zoneId))),
  stopAll: () => request<void>('POST', apiPath('/api/running/stop-all')),
  lights: () => request<Light[]>('GET', apiPath('/api/lights')),
  attention: () => request<AttentionItem[]>('GET', apiPath('/api/attention')),
  /** Preview only (§5.6) is the engine's `preview_only` setting today. */
  setPreviewOnly: (on: boolean) => request<unknown>('PUT', apiPath('/api/config'), { engine: { preview_only: on } }),

  // Pending: engine M2 (mocked until it lands)
  home: () => request<Home>('GET', apiPath('/api/home')),
  updateHome: (body: HomeUpdate) => request<Home>('PUT', apiPath('/api/home'), body),
  addAnchor: (body: AnchorInput) => request<Anchor>('POST', apiPath('/api/home/anchors'), body),
  updateAnchor: (id: Id, body: Partial<AnchorInput>) =>
    request<Anchor>('PUT', apiPath('/api/home/anchors/{anchor_id}', { anchor_id: id }), body),
  deleteAnchor: (id: Id) => request<void>('DELETE', apiPath('/api/home/anchors/{anchor_id}', { anchor_id: id })),
  addSubZone: (body: SubZoneInput) => request<SubZone>('POST', apiPath('/api/home/subzones'), body),
  updateSubZone: (id: Id, body: Partial<SubZoneInput>) =>
    request<SubZone>('PUT', apiPath('/api/home/subzones/{subzone_id}', { subzone_id: id }), body),
  deleteSubZone: (id: Id) => request<void>('DELETE', apiPath('/api/home/subzones/{subzone_id}', { subzone_id: id })),
  setPlacement: (lightId: Id, body: Placement) =>
    request<PlacementState>('PUT', apiPath('/api/lights/{light_id}/placement', light(lightId)), body),
  confirmPlacement: (lightId: Id) =>
    request<PlacementState>('POST', apiPath('/api/lights/{light_id}/placement/confirm', light(lightId))),
  guessPlacements: () => request<Light[]>('POST', apiPath('/api/lights/placement/guess')),
  startPreview: (body: PreviewRequest) => request<PreviewResponse>('POST', apiPath('/api/preview'), body),
  updatePreview: (id: Id, draft: Look) =>
    request<void>('PUT', apiPath('/api/preview/{preview_id}', { preview_id: id }), { look: draft }),
  stopPreview: (id: Id) => request<void>('DELETE', apiPath('/api/preview/{preview_id}', { preview_id: id })),

  // Pending: engine M3, M6 and M7 (mocked until they land)
  inputs: () => request<Inputs>('GET', apiPath('/api/inputs')),
  signals: () => request<Signal[]>('GET', apiPath('/api/signals')),
}
