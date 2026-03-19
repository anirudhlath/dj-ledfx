import type { Device, FrameData } from "@/lib/types"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"

interface DeviceMonitorProps {
  devices: Device[]
  frameData: Map<string, FrameData>
}

const MAX_LED_PREVIEW = 40

function LedPreview({ frame, ledCount }: { frame: FrameData | undefined; ledCount: number }) {
  if (!frame || frame.rgb.length === 0) {
    return (
      <div className="flex gap-px h-3">
        {Array.from({ length: Math.min(ledCount, MAX_LED_PREVIEW) }).map((_, i) => (
          <div key={i} className="flex-1 rounded-full bg-muted/40" />
        ))}
      </div>
    )
  }

  const totalLeds = Math.floor(frame.rgb.length / 3)
  const previewCount = Math.min(totalLeds, MAX_LED_PREVIEW)
  // Sample evenly across actual LEDs
  const step = totalLeds / previewCount

  const swatches: string[] = []
  for (let i = 0; i < previewCount; i++) {
    const idx = Math.floor(i * step) * 3
    const r = frame.rgb[idx]
    const g = frame.rgb[idx + 1]
    const b = frame.rgb[idx + 2]
    swatches.push(`rgb(${r},${g},${b})`)
  }

  return (
    <div className="flex gap-px h-3">
      {swatches.map((color, i) => (
        <div
          key={i}
          className="flex-1 rounded-full"
          style={{ backgroundColor: color }}
        />
      ))}
    </div>
  )
}

function DeviceCard({ device, frame }: { device: Device; frame: FrameData | undefined }) {
  const { name, device_type, led_count, send_fps, effective_latency_ms, connected } = device

  return (
    <div className="flex flex-col gap-1.5 bg-card border border-border rounded-md p-2.5 min-w-[160px] max-w-[220px] shrink-0">
      {/* Header row */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span
          className={[
            "size-2 rounded-full shrink-0",
            connected ? "bg-green-500" : "bg-red-500/60",
          ].join(" ")}
        />
        <span className="text-xs font-medium text-foreground truncate flex-1" title={name}>
          {name}
        </span>
      </div>

      {/* LED preview strip */}
      <LedPreview frame={frame} ledCount={led_count} />

      {/* Stats row */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground uppercase truncate">{device_type}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] font-mono text-foreground/70">
            {send_fps > 0 ? `${Math.round(send_fps)}fps` : "--fps"}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground">
            {effective_latency_ms > 0 ? `${Math.round(effective_latency_ms)}ms` : "--ms"}
          </span>
        </div>
      </div>
    </div>
  )
}

export function DeviceMonitor({ devices, frameData }: DeviceMonitorProps) {
  if (devices.length === 0) {
    return (
      <div className="flex items-center justify-center h-16 border border-dashed border-border rounded-lg">
        <p className="text-xs text-muted-foreground">No devices connected</p>
      </div>
    )
  }

  return (
    <div className="border border-border rounded-lg">
      <div className="px-3 py-1.5 border-b border-border flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">
          Devices
        </span>
        <span className="text-[10px] text-muted-foreground">
          {devices.filter((d) => d.connected).length}/{devices.length} online
        </span>
      </div>
      <ScrollArea className="w-full">
        <div className="flex gap-2 p-2">
          {devices.map((device) => (
            <DeviceCard
              key={device.name}
              device={device}
              frame={frameData.get(device.name)}
            />
          ))}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
    </div>
  )
}
