import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { Placement, Device } from "@/lib/types"

interface DeviceListPanelProps {
  placements: Placement[]
  allDevices: Device[]
  selectedDeviceId: string | null
  onSelectDevice: (deviceId: string) => void
  onAddDevice: (deviceName: string, ledCount: number) => void
}

export default function DeviceListPanel({
  placements,
  allDevices,
  selectedDeviceId,
  onSelectDevice,
  onAddDevice,
}: DeviceListPanelProps) {
  const placedIds = new Set(placements.map((p) => p.device_id))
  const unplacedDevices = allDevices.filter((d) => !placedIds.has(d.name))

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Devices</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        <ScrollArea className="h-full px-3 pb-3">
          {placements.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-muted-foreground font-medium mb-1.5 px-1">
                In Scene
              </p>
              {placements.map((p) => (
                <button
                  key={p.device_id}
                  onClick={() => onSelectDevice(p.device_id)}
                  className={cn(
                    "w-full text-left px-2 py-1.5 rounded text-sm transition-colors",
                    selectedDeviceId === p.device_id
                      ? "bg-primary/15 text-primary"
                      : "hover:bg-muted"
                  )}
                >
                  <span className="flex items-center justify-between">
                    <span className="truncate">{p.device_id}</span>
                    <Badge variant="outline" className="text-[10px] ml-1 shrink-0">
                      {p.geometry.type}
                    </Badge>
                  </span>
                </button>
              ))}
            </div>
          )}

          {unplacedDevices.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1.5 px-1">
                Unplaced
              </p>
              {unplacedDevices.map((d) => (
                <div
                  key={d.name}
                  className="px-2 py-1.5 text-sm text-muted-foreground flex items-center justify-between"
                >
                  <span className="truncate">{d.name}</span>
                  <div className="flex items-center gap-1">
                    <Badge variant="outline" className="text-[10px] shrink-0 opacity-50">
                      {d.device_type}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-5 w-5 p-0 text-xs"
                      onClick={() => onAddDevice(d.name, d.led_count)}
                    >
                      +
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {placements.length === 0 && unplacedDevices.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">
              No devices found
            </p>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
