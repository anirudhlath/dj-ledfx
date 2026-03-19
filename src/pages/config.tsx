import { useState, useEffect, useRef } from "react"
import { toast } from "sonner"
import { getConfig, updateConfig, exportConfig, importConfig } from "@/lib/api-client"
import type { AppConfig } from "@/lib/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4">
      <Label className="text-xs text-muted-foreground w-40 shrink-0">{label}</Label>
      <div className="flex-1">{children}</div>
    </div>
  )
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit?: string
  onChange: (v: number) => void
}) {
  return (
    <FieldRow label={label}>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <Slider
            min={min}
            max={max}
            step={step}
            value={value}
            onValueChange={(v: number | readonly number[]) => {
              const num = Array.isArray(v) ? (v as readonly number[])[0] : (v as number)
              onChange(num)
            }}
          />
        </div>
        <span className="text-xs font-mono text-foreground w-16 text-right tabular-nums">
          {value}
          {unit && <span className="text-muted-foreground ml-0.5">{unit}</span>}
        </span>
      </div>
    </FieldRow>
  )
}

function SwitchField({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <FieldRow label={label}>
      <Switch checked={checked} onCheckedChange={onChange} />
    </FieldRow>
  )
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
  note,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  note?: string
}) {
  return (
    <div className="space-y-1">
      <FieldRow label={label}>
        <Input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="text-sm h-7"
        />
      </FieldRow>
      {note && (
        <p className="text-[10px] text-muted-foreground/60 pl-44">{note}</p>
      )}
    </div>
  )
}

function ConfigSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <h3 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function JsonCard({ label, data }: { label: string; data: Record<string, unknown> }) {
  return (
    <Card className="bg-muted/20">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-all leading-relaxed">
          {Object.keys(data).length === 0
            ? "(no settings)"
            : JSON.stringify(data, null, 2)}
        </pre>
      </CardContent>
    </Card>
  )
}

export default function ConfigPage() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [draft, setDraft] = useState<AppConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        setConfig(cfg)
        setDraft(cfg)
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to load config"
        toast.error(msg)
      })
      .finally(() => setLoading(false))
  }, [])

  function patchDraft<K extends keyof AppConfig>(
    section: K,
    updates: Partial<AppConfig[K]>
  ) {
    setDraft((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        [section]: { ...(prev[section] as object), ...updates },
      }
    })
  }

  async function handleApply() {
    if (!draft) return
    setSaving(true)
    try {
      const updated = await updateConfig(draft)
      setConfig(updated)
      setDraft(updated)
      toast.success("Configuration saved")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save config"
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  async function handleExport() {
    try {
      const toml = await exportConfig()
      const blob = new Blob([toml], { type: "text/plain" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "dj-ledfx-config.toml"
      a.click()
      URL.revokeObjectURL(url)
      toast.success("Config exported")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Export failed"
      toast.error(msg)
    }
  }

  function handleImportClick() {
    fileInputRef.current?.click()
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const updated = await importConfig(text)
      setConfig(updated)
      setDraft(updated)
      toast.success("Config imported successfully")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Import failed"
      toast.error(msg)
    } finally {
      // Reset input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const isDirty = JSON.stringify(config) !== JSON.stringify(draft)

  if (loading || !draft) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-1/2" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          Configuration
        </h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs px-3"
            onClick={handleExport}
          >
            Export TOML
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs px-3"
            onClick={handleImportClick}
          >
            Import TOML
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".toml,text/plain"
            className="hidden"
            onChange={handleFileChange}
          />
          <Button
            size="sm"
            className="h-7 text-xs px-4"
            onClick={handleApply}
            disabled={saving || !isDirty}
          >
            {saving ? "Saving…" : "Apply"}
          </Button>
        </div>
      </div>

      <Separator />

      {/* Tabs */}
      <Tabs defaultValue="engine">
        <TabsList>
          <TabsTrigger value="engine">Engine</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
          <TabsTrigger value="web">Web</TabsTrigger>
          <TabsTrigger value="devices">Devices</TabsTrigger>
        </TabsList>

        {/* Engine tab */}
        <TabsContent value="engine">
          <Card>
            <CardContent className="pt-6 space-y-6">
              <ConfigSection title="Render Engine">
                <SliderField
                  label="Frame Rate"
                  value={draft.engine.fps}
                  min={30}
                  max={120}
                  step={1}
                  unit="fps"
                  onChange={(v) => patchDraft("engine", { fps: v })}
                />
                <SliderField
                  label="Max Lookahead"
                  value={draft.engine.max_lookahead_ms}
                  min={500}
                  max={2000}
                  step={50}
                  unit="ms"
                  onChange={(v) => patchDraft("engine", { max_lookahead_ms: v })}
                />
              </ConfigSection>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Network tab */}
        <TabsContent value="network">
          <Card>
            <CardContent className="pt-6 space-y-6">
              <ConfigSection title="Pro DJ Link">
                <TextField
                  label="Interface"
                  value={draft.network.interface}
                  onChange={(v) => patchDraft("network", { interface: v })}
                  note="Network interface to bind (e.g. en0, eth0)"
                />
                <SwitchField
                  label="Passive Mode"
                  checked={draft.network.passive_mode}
                  onChange={(v) => patchDraft("network", { passive_mode: v })}
                />
              </ConfigSection>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Web tab */}
        <TabsContent value="web">
          <Card>
            <CardContent className="pt-6 space-y-6">
              <ConfigSection title="API Server">
                <p className="text-[10px] text-amber-400/80 uppercase tracking-wider font-semibold -mt-1">
                  Changes to host/port require a restart
                </p>
                <SwitchField
                  label="Enabled"
                  checked={draft.web.enabled}
                  onChange={(v) => patchDraft("web", { enabled: v })}
                />
                <TextField
                  label="Host"
                  value={draft.web.host}
                  onChange={(v) => patchDraft("web", { host: v })}
                  note="Requires restart"
                />
                <TextField
                  label="Port"
                  value={String(draft.web.port)}
                  type="number"
                  onChange={(v) => patchDraft("web", { port: parseInt(v, 10) || draft.web.port })}
                  note="Requires restart"
                />
              </ConfigSection>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Devices tab */}
        <TabsContent value="devices">
          <div className="space-y-3 pt-1">
            <JsonCard label="OpenRGB" data={draft.devices.openrgb} />
            <JsonCard label="LIFX" data={draft.devices.lifx} />
            <JsonCard label="Govee" data={draft.devices.govee} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
