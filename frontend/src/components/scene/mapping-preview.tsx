import { useMemo } from "react"
import type { Placement, FrameData } from "@/lib/types"
import { cn } from "@/lib/utils"

interface MappingPreviewProps {
  placements: Placement[]
  frameData: Map<string, FrameData>
  selectedDeviceId: string | null
  onSelectDevice: (deviceId: string) => void
}

export default function MappingPreview({
  placements,
  frameData,
  selectedDeviceId,
  onSelectDevice,
}: MappingPreviewProps) {
  const devicePositions = useMemo(() => {
    if (placements.length === 0) return []
    const xs = placements.map((p) => p.position[0])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const span = maxX - minX
    return placements.map((p) => ({
      deviceId: p.device_id,
      normalized: span > 0.001 ? (p.position[0] - minX) / span : 0.5,
    }))
  }, [placements])

  if (placements.length === 0) return null

  return (
    <div className="h-10 border-t border-border px-3 py-1.5 flex items-center gap-2">
      <span className="text-[10px] text-muted-foreground shrink-0">Mapping</span>
      <div className="relative flex-1 h-5 rounded bg-muted overflow-hidden">
        <GradientBar frameData={frameData} placements={placements} />
        {devicePositions.map(({ deviceId, normalized }) => (
          <button
            key={deviceId}
            onClick={() => onSelectDevice(deviceId)}
            className={cn(
              "absolute top-0 h-full w-1 -translate-x-1/2 transition-colors",
              selectedDeviceId === deviceId
                ? "bg-primary"
                : "bg-foreground/50 hover:bg-foreground/80"
            )}
            style={{ left: `${normalized * 100}%` }}
            title={deviceId}
          />
        ))}
      </div>
    </div>
  )
}

function GradientBar({
  frameData,
  placements,
}: {
  frameData: Map<string, FrameData>
  placements: Placement[]
}) {
  const gradient = useMemo(() => {
    for (const p of placements) {
      const frame = frameData.get(p.device_id)
      if (!frame?.rgb || frame.rgb.length < 3) continue

      const ledCount = frame.rgb.length / 3
      const samples = Math.min(ledCount, 32)
      const stops: string[] = []
      for (let i = 0; i < samples; i++) {
        const idx = Math.floor((i / samples) * ledCount)
        const r = frame.rgb[idx * 3]
        const g = frame.rgb[idx * 3 + 1]
        const b = frame.rgb[idx * 3 + 2]
        const pct = (i / (samples - 1)) * 100
        stops.push(`rgb(${r},${g},${b}) ${pct.toFixed(1)}%`)
      }
      return `linear-gradient(to right, ${stops.join(", ")})`
    }
    return "linear-gradient(to right, hsl(var(--muted)), hsl(var(--muted)))"
  }, [frameData, placements])

  return (
    <div className="absolute inset-0" style={{ background: gradient }} />
  )
}
