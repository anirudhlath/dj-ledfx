import { useState } from "react"
import type { EffectParamSchema, Preset } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"

interface EffectDeckProps {
  schemas: Record<string, Record<string, EffectParamSchema>>
  activeEffect: string
  activeParams: Record<string, unknown>
  presets: Preset[]
  loading: boolean
  switchEffect: (name: string) => Promise<void>
  updateParam: (key: string, value: unknown) => Promise<void>
  loadPreset: (name: string) => Promise<void>
  savePreset: (name: string) => Promise<void>
}

function ParamControl({
  paramKey,
  schema,
  value,
  onUpdate,
}: {
  paramKey: string
  schema: EffectParamSchema
  value: unknown
  onUpdate: (key: string, value: unknown) => void
}) {
  const label = schema.label ?? paramKey

  if (schema.type === "float" || schema.type === "int") {
    const min = schema.min ?? 0
    const max = schema.max ?? 1
    const step = schema.step ?? (schema.type === "int" ? 1 : 0.01)
    const numVal = typeof value === "number" ? value : ((schema.default as number) ?? min)

    return (
      <div className="flex items-center gap-3">
        <Label className="text-xs text-muted-foreground w-28 shrink-0">{label}</Label>
        <div className="flex-1">
          <Slider
            min={min}
            max={max}
            step={step}
            value={numVal}
            onValueChange={(v: number | readonly number[]) => {
              const num = Array.isArray(v) ? (v as readonly number[])[0] : (v as number)
              onUpdate(paramKey, schema.type === "int" ? Math.round(num) : num)
            }}
          />
        </div>
        <span className="text-xs font-mono text-foreground w-12 text-right">
          {schema.type === "int" ? String(Math.round(numVal)) : numVal.toFixed(2)}
        </span>
      </div>
    )
  }

  if (schema.type === "bool") {
    const boolVal = typeof value === "boolean" ? value : Boolean(schema.default)
    return (
      <div className="flex items-center gap-3">
        <Label className="text-xs text-muted-foreground w-28 shrink-0">{label}</Label>
        <Switch
          checked={boolVal}
          onCheckedChange={(v: boolean) => onUpdate(paramKey, v)}
          className="scale-90"
        />
      </div>
    )
  }

  if (schema.type === "choice" && schema.choices) {
    const strVal = typeof value === "string" ? value : String(schema.default ?? "")
    return (
      <div className="flex items-center gap-3">
        <Label className="text-xs text-muted-foreground w-28 shrink-0">{label}</Label>
        <Select
          value={strVal}
          onValueChange={(v: string | null) => { if (v !== null) onUpdate(paramKey, v) }}
        >
          <SelectTrigger className="h-7 text-xs flex-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {schema.choices.map((c) => (
              <SelectItem key={c} value={c} className="text-xs">
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  }

  if (schema.type === "color_list") {
    const colors = Array.isArray(value) ? (value as string[]) : []
    return (
      <div className="flex items-start gap-3">
        <Label className="text-xs text-muted-foreground w-28 shrink-0 pt-1">{label}</Label>
        <div className="flex flex-wrap gap-1.5">
          {colors.map((color, i) => (
            <input
              key={i}
              type="color"
              value={color}
              onChange={(e) => {
                const next = [...colors]
                next[i] = e.target.value
                onUpdate(paramKey, next)
              }}
              className="h-6 w-8 rounded cursor-pointer border border-border bg-transparent p-0"
              title={`Color ${i + 1}`}
            />
          ))}
        </div>
      </div>
    )
  }

  return null
}

export function EffectDeck({
  schemas,
  activeEffect,
  activeParams,
  presets,
  loading,
  switchEffect,
  updateParam,
  loadPreset,
  savePreset,
}: EffectDeckProps) {
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [presetName, setPresetName] = useState("")

  const effectNames = Object.keys(schemas)
  const currentSchema = activeEffect ? (schemas[activeEffect] ?? {}) : {}

  const handleSavePreset = async () => {
    if (!presetName.trim()) return
    await savePreset(presetName.trim())
    setSaveDialogOpen(false)
    setPresetName("")
  }

  return (
    <Card className="flex flex-col h-full overflow-hidden">
      <CardHeader className="pb-3 pt-4 px-4">
        <CardTitle className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          Effect Deck
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 flex-1 px-4 pb-4 overflow-y-auto min-h-0">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-6 w-1/2" />
          </div>
        ) : (
          <>
            {/* Effect selector */}
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase tracking-wider">Effect</Label>
              <Select
                value={activeEffect}
                onValueChange={(v: string | null) => { if (v !== null) switchEffect(v) }}
              >
                <SelectTrigger className="h-8 text-sm font-medium w-full">
                  <SelectValue placeholder="Select effect..." />
                </SelectTrigger>
                <SelectContent>
                  {effectNames.map((name) => (
                    <SelectItem key={name} value={name} className="text-sm">
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* Param controls */}
            {Object.keys(currentSchema).length > 0 ? (
              <div className="space-y-3">
                <Label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Parameters
                </Label>
                {Object.entries(currentSchema).map(([key, schema]) => (
                  <ParamControl
                    key={key}
                    paramKey={key}
                    schema={schema}
                    value={activeParams[key]}
                    onUpdate={updateParam}
                  />
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic">No parameters</p>
            )}

            <Separator />

            {/* Presets */}
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground uppercase tracking-wider">Presets</Label>
              <div className="flex gap-2">
                <Select onValueChange={(v: string | null) => { if (v !== null) loadPreset(v) }}>
                  <SelectTrigger className="h-7 text-xs flex-1">
                    <SelectValue placeholder="Load preset..." />
                  </SelectTrigger>
                  <SelectContent>
                    {presets.length === 0 ? (
                      <div className="px-2 py-1.5 text-xs text-muted-foreground">No presets saved</div>
                    ) : (
                      presets.map((p) => (
                        <SelectItem key={p.name} value={p.name} className="text-xs">
                          {p.name}
                          <span className="ml-1 text-muted-foreground opacity-60">({p.effect_class})</span>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs px-3"
                  onClick={() => setSaveDialogOpen(true)}
                  disabled={!activeEffect}
                >
                  Save
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>

      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-xs">
          <DialogHeader>
            <DialogTitle className="text-sm">Save Preset</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <Input
              placeholder="Preset name"
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSavePreset()}
              className="text-sm"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSaveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={handleSavePreset} disabled={!presetName.trim()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
