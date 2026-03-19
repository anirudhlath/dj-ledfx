import { useState, useEffect } from "react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { identifyDevice } from "@/lib/api-client"
import type { Placement, Device } from "@/lib/types"

interface PropertiesPanelProps {
  placement: Placement | null
  deviceInfo: Device | null
  onPositionChange: (deviceId: string, position: [number, number, number]) => void
  onRemove: (deviceId: string) => void
}

export default function PropertiesPanel({
  placement,
  deviceInfo,
  onPositionChange,
  onRemove,
}: PropertiesPanelProps) {
  const [pos, setPos] = useState<[string, string, string]>(["0", "0", "0"])

  useEffect(() => {
    if (placement) {
      setPos([
        placement.position[0].toFixed(2),
        placement.position[1].toFixed(2),
        placement.position[2].toFixed(2),
      ])
    }
  }, [placement])

  if (!placement) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full">
          <p className="text-sm text-muted-foreground">Select a device</p>
        </CardContent>
      </Card>
    )
  }

  const commitPosition = () => {
    const parsed: [number, number, number] = [
      parseFloat(pos[0]) || 0,
      parseFloat(pos[1]) || 0,
      parseFloat(pos[2]) || 0,
    ]
    onPositionChange(placement.device_id, parsed)
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">{placement.device_id}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 flex-1">
        {/* Geometry info */}
        <div>
          <Label className="text-xs text-muted-foreground">Geometry</Label>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">{placement.geometry.type}</Badge>
            <span className="text-xs text-muted-foreground">
              {placement.led_count} LEDs
            </span>
          </div>
        </div>

        {/* Position */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">Position (meters)</Label>
          {(["X", "Y", "Z"] as const).map((axis, i) => (
            <div key={axis} className="flex items-center gap-2">
              <Label className="text-xs w-4 text-center">{axis}</Label>
              <Input
                type="number"
                step="0.1"
                value={pos[i]}
                onChange={(e) => {
                  const next = [...pos] as [string, string, string]
                  next[i] = e.target.value
                  setPos(next)
                }}
                onBlur={commitPosition}
                onKeyDown={(e) => e.key === "Enter" && commitPosition()}
                className="h-7 text-xs"
              />
            </div>
          ))}
        </div>

        {/* Strip-specific info */}
        {placement.geometry.type === "strip" && placement.geometry.direction && (
          <div>
            <Label className="text-xs text-muted-foreground">Direction</Label>
            <p className="text-xs mt-1">
              [{placement.geometry.direction.map((v: number) => v.toFixed(1)).join(", ")}]
            </p>
            {placement.geometry.length && (
              <>
                <Label className="text-xs text-muted-foreground mt-2 block">Length</Label>
                <p className="text-xs mt-1">{placement.geometry.length.toFixed(2)}m</p>
              </>
            )}
          </div>
        )}

        {/* Group & Latency */}
        {deviceInfo && (
          <div className="space-y-2">
            {deviceInfo.group && (
              <div>
                <Label className="text-xs text-muted-foreground">Group</Label>
                <p className="text-xs mt-1">{deviceInfo.group}</p>
              </div>
            )}
            <div>
              <Label className="text-xs text-muted-foreground">Latency</Label>
              <p className="text-xs mt-1">{deviceInfo.effective_latency_ms.toFixed(1)} ms</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Send FPS</Label>
              <p className="text-xs mt-1">{deviceInfo.send_fps.toFixed(0)}</p>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              try {
                await identifyDevice(placement.device_id)
                toast.success(`Identifying ${placement.device_id}`)
              } catch {
                toast.error("Failed to identify device")
              }
            }}
          >
            Identify
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={() => onRemove(placement.device_id)}
          >
            Remove from Scene
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
