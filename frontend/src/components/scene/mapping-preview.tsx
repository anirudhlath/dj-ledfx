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
    // Use strip_index from compositor when available (reflects actual mapping)
    const hasStripIndices = placements.some((p) => p.strip_index != null)
    if (hasStripIndices) {
      return placements.map((p) => ({
        deviceId: p.device_id,
        normalized: p.strip_index ?? 0.5,
      }))
    }
    // Fallback: project onto X axis
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
        {devicePositions.map(({ deviceId, normalized }) => {
          const frame = frameData.get(deviceId)
          const color = averageColor(frame)
          return (
            <button
              key={deviceId}
              onClick={() => onSelectDevice(deviceId)}
              className={cn(
                "absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border transition-colors",
                selectedDeviceId === deviceId
                  ? "border-primary ring-1 ring-primary"
                  : "border-foreground/30 hover:border-foreground/60"
              )}
              style={{
                left: `${normalized * 100}%`,
                width: 12,
                height: 12,
                backgroundColor: color,
              }}
              title={deviceId}
            />
          )
        })}
      </div>
    </div>
  )
}

function averageColor(frame: FrameData | undefined): string {
  if (!frame?.rgb || frame.rgb.length < 3) return "hsl(var(--muted-foreground))"
  const ledCount = frame.rgb.length / 3
  let r = 0, g = 0, b = 0
  for (let i = 0; i < ledCount; i++) {
    r += frame.rgb[i * 3]
    g += frame.rgb[i * 3 + 1]
    b += frame.rgb[i * 3 + 2]
  }
  r = Math.round(r / ledCount)
  g = Math.round(g / ledCount)
  b = Math.round(b / ledCount)
  return `rgb(${r},${g},${b})`
}
