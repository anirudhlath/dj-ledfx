import { useState } from "react"
import type { LookSummary, RunningZone, Zone } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface LookPickerProps {
  zones: Zone[]
  looks: LookSummary[]
  running: RunningZone[]
  previewOnly: boolean
  zoneId: string | null
  onZoneChange: (zoneId: string) => void
  onStart: (zoneId: string, lookId: string) => Promise<void>
  onOff: (zoneId: string) => Promise<void>
  onPreviewOnlyChange: (on: boolean) => Promise<void>
}

function describe(zone: RunningZone): string {
  const since = new Date(zone.since).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  switch (zone.state) {
    case "crashed":
      return `${zone.lookName} crashed: ${zone.error?.message ?? "no details"}`
    case "waiting":
      return `${zone.lookName} is waiting for ${(zone.waitingFor ?? []).join(", ")}`
    case "slow":
      return `${zone.lookName} since ${since}, running slow`
    default:
      return `${zone.lookName} since ${since}`
  }
}

/** What starting a look here would take from other running zones (web spec §11.3). */
function consequence(zone: Zone, zones: Zone[], running: RunningZone[]): string | null {
  const parts: string[] = []
  for (const other of running) {
    if (other.zoneId === zone.id) continue
    const shared = other.lights.filter((light) => zone.lights.includes(light)).length
    if (shared === 0) continue
    const name = zones.find((z) => z.id === other.zoneId)?.name ?? other.zoneId
    const what = shared === other.lights.length ? name : `${shared} of ${name}'s lights`
    parts.push(`${what} from ${other.lookName}`)
  }
  return parts.length > 0 ? `Takes over ${parts.join(" and ")}` : null
}

export function LookPicker({
  zones,
  looks,
  running,
  previewOnly,
  zoneId,
  onZoneChange,
  onStart,
  onOff,
  onPreviewOnlyChange,
}: LookPickerProps) {
  const [lookChoice, setLookChoice] = useState<string | null>(null)
  const zone = zones.find((z) => z.id === zoneId) ?? null
  const playing = running.find((r) => r.zoneId === zoneId) ?? null
  const lookId = lookChoice ?? playing?.lookId ?? looks[0]?.id ?? null
  const note = zone ? consequence(zone, zones, running) : null

  return (
    <div className="flex items-center gap-3 p-3 bg-card ring-1 ring-foreground/10 rounded-xl">
      <Select
        items={Object.fromEntries(zones.map((z) => [z.id, z.name]))}
        value={zoneId}
        onValueChange={(v: string | null) => {
          if (v === null) return
          setLookChoice(null)
          onZoneChange(v)
        }}
      >
        <SelectTrigger className="h-8 w-44 text-sm">
          <SelectValue placeholder="Zone" />
        </SelectTrigger>
        <SelectContent>
          {zones.map((z) => (
            <SelectItem key={z.id} value={z.id} className="text-sm">
              {z.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        items={Object.fromEntries(looks.map((look) => [look.id, look.name]))}
        value={lookId}
        onValueChange={(v: string | null) => {
          if (v !== null) setLookChoice(v)
        }}
      >
        <SelectTrigger className="h-8 w-52 text-sm">
          <SelectValue placeholder="Look" />
        </SelectTrigger>
        <SelectContent>
          {looks.map((look) => (
            <SelectItem key={look.id} value={look.id} className="text-sm">
              {look.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        size="sm"
        disabled={zone === null || lookId === null}
        onClick={() => {
          if (zone !== null && lookId !== null) void onStart(zone.id, lookId)
        }}
      >
        Start
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={playing === null}
        onClick={() => {
          if (playing !== null) void onOff(playing.zoneId)
        }}
      >
        Off
      </Button>

      <div className="flex flex-col gap-0.5 min-w-0 flex-1 text-xs">
        <span className="truncate">{playing ? describe(playing) : "No look on"}</span>
        {note && <span className="truncate text-muted-foreground">{note}</span>}
      </div>

      <Label className="text-xs shrink-0">
        <Switch
          checked={previewOnly}
          onCheckedChange={(on: boolean) => {
            void onPreviewOnlyChange(on)
          }}
        />
        Preview only
      </Label>
    </div>
  )
}
