import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface SceneToolbarProps {
  transformMode: "translate" | "rotate"
  onTransformModeChange: (mode: "translate" | "rotate") => void
  mappingType: string
  onMappingTypeChange: (type: string) => void
  onCameraPreset: (preset: string) => void
  snapEnabled: boolean
  onSnapToggle: (enabled: boolean) => void
  snapIncrement: number
  onSnapIncrementChange: (value: number) => void
}

export default function SceneToolbar({
  transformMode,
  onTransformModeChange,
  mappingType,
  onMappingTypeChange,
  onCameraPreset,
  snapEnabled,
  onSnapToggle,
  snapIncrement,
  onSnapIncrementChange,
}: SceneToolbarProps) {
  return (
    <div className="flex items-center gap-3 px-3 py-1.5 border-b border-border">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Tool</span>
        <ToggleGroup
          value={[transformMode]}
          onValueChange={(values) => {
            const v = values[0]
            if (v === "translate" || v === "rotate") onTransformModeChange(v)
          }}
        >
          <ToggleGroupItem value="translate" className="text-xs h-7 px-2">
            Move
          </ToggleGroupItem>
          <ToggleGroupItem value="rotate" className="text-xs h-7 px-2">
            Rotate
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div className="w-px h-5 bg-border" />

      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Mapping</span>
        <Select
          value={mappingType}
          onValueChange={(v) => {
            if (v !== null) onMappingTypeChange(v)
          }}
        >
          <SelectTrigger className="h-7 w-24 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="linear">Linear</SelectItem>
            <SelectItem value="radial">Radial</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="w-px h-5 bg-border" />

      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground mr-1">View</span>
        {(["Perspective", "Top", "Front", "Side"] as const).map((preset) => (
          <Button
            key={preset}
            variant="outline"
            size="sm"
            className="text-xs h-7 px-2"
            onClick={() => onCameraPreset(preset)}
          >
            {preset}
          </Button>
        ))}
      </div>

      <div className="w-px h-5 bg-border" />

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={snapEnabled}
            onChange={(e) => onSnapToggle(e.target.checked)}
            className="size-3"
          />
          Snap
        </label>
        {snapEnabled && (
          <Input
            type="number"
            step="0.1"
            min="0.1"
            value={snapIncrement}
            onChange={(e) => onSnapIncrementChange(parseFloat(e.target.value) || 0.5)}
            className="h-7 w-16 text-xs"
          />
        )}
      </div>
    </div>
  )
}
