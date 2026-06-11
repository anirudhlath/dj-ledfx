import { memo, useState, useRef } from "react"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { SceneListItem } from "@/lib/types"

interface ScenesPanelProps {
  scenes: SceneListItem[]
  selectedSceneId: string | null
  onSelectScene: (sceneId: string | null) => void
  onCreate: (name: string) => Promise<SceneListItem>
  onRename: (sceneId: string, name: string) => Promise<void>
  onDelete: (sceneId: string) => Promise<boolean>
  onActivate: (sceneId: string) => Promise<boolean>
  onDeactivate: (sceneId: string) => Promise<boolean>
  onEffectModeChange: (sceneId: string, mode: "independent" | "shared") => Promise<void>
}

export default memo(function ScenesPanel({
  scenes,
  selectedSceneId,
  onSelectScene,
  onCreate,
  onRename,
  onDelete,
  onActivate,
  onDeactivate,
  onEffectModeChange,
}: ScenesPanelProps) {
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)
  const [newSceneName, setNewSceneName] = useState("")
  // Guards the Enter→blur sequence from committing a rename twice
  const committingRef = useRef(false)

  const selected = scenes.find((s) => s.id === selectedSceneId) ?? null

  const startRename = (s: SceneListItem) => {
    setEditing({ id: s.id, name: s.name })
  }

  const commitRename = async (scene: SceneListItem) => {
    if (committingRef.current) return
    const trimmed = editing?.name.trim() ?? ""
    if (!trimmed || trimmed === scene.name) {
      setEditing(null)
      return
    }
    committingRef.current = true
    try {
      await onRename(scene.id, trimmed)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to rename scene")
    } finally {
      setEditing(null)
      committingRef.current = false
    }
  }

  const handleCreate = async () => {
    const trimmed = newSceneName.trim()
    if (!trimmed) return
    try {
      const created = await onCreate(trimmed)
      setNewSceneName("")
      onSelectScene(created.id)
      toast.success(`Scene "${created.name}" created`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to create scene")
    }
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Scenes</CardTitle>
      </CardHeader>
      <CardContent className="p-0 flex flex-col gap-0">
        <div className="max-h-56 overflow-y-auto px-3">
          {/* Default pseudo-scene row */}
          <button
            className={cn(
              "w-full flex items-center gap-1 px-2 py-1.5 rounded transition-colors text-left",
              selectedSceneId === null ? "bg-primary/15 text-primary" : "hover:bg-muted",
            )}
            onClick={() => onSelectScene(null)}
          >
            <span className="flex-1 truncate text-xs">Default</span>
            <Badge variant="outline" className="text-[10px] shrink-0">
              active
            </Badge>
          </button>

          {/* DB scene rows */}
          {scenes.map((s) => (
            <div
              key={s.id}
              className={cn(
                "flex items-center gap-1 px-2 py-1.5 rounded transition-colors",
                selectedSceneId === s.id ? "bg-primary/15 text-primary" : "hover:bg-muted",
              )}
            >
              {editing?.id === s.id ? (
                <Input
                  autoFocus
                  value={editing.name}
                  onChange={(e) => setEditing({ id: s.id, name: e.target.value })}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      void commitRename(s)
                    } else if (e.key === "Escape") {
                      setEditing(null)
                    }
                  }}
                  onBlur={() => void commitRename(s)}
                  className="h-6 text-xs flex-1 min-w-0 px-1"
                />
              ) : (
                <button
                  className="flex-1 text-left text-xs truncate min-w-0 bg-transparent border-0 p-0 cursor-pointer"
                  onClick={() => onSelectScene(s.id)}
                  onDoubleClick={() => startRename(s)}
                >
                  {s.name}
                </button>
              )}

              {s.is_active && (
                <Badge variant="outline" className="text-[10px] shrink-0">
                  active
                </Badge>
              )}

              <Button
                variant="outline"
                size="sm"
                className="h-6 px-1.5 text-[10px] shrink-0"
                onClick={async () => {
                  const ok = s.is_active
                    ? await onDeactivate(s.id)
                    : await onActivate(s.id)
                  if (ok) {
                    toast.success(
                      s.is_active ? `Stopped "${s.name}"` : `Activated "${s.name}"`,
                    )
                  }
                }}
              >
                {s.is_active ? "Stop" : "Go"}
              </Button>

              <button
                className="h-6 w-5 text-xs text-muted-foreground opacity-50 hover:opacity-100 hover:text-destructive transition-opacity bg-transparent border-0 cursor-pointer shrink-0"
                onClick={async () => {
                  const ok = await onDelete(s.id)
                  if (ok) {
                    toast.success(`Deleted "${s.name}"`)
                    if (selectedSceneId === s.id) {
                      onSelectScene(null)
                    }
                  }
                }}
                aria-label={`Delete ${s.name}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        {/* Effect mode selector for selected non-default scene */}
        {selected !== null && (
          <div className="flex items-center gap-2 px-3 py-2 border-t border-border">
            <span className="text-xs text-muted-foreground shrink-0">Effect mode</span>
            <div
              className="flex-1"
              title={selected.is_active ? "Deactivate the scene to change effect mode" : undefined}
            >
              <Select
                value={selected.effect_mode ?? "independent"}
                onValueChange={(v) => {
                  if (v === "independent" || v === "shared") {
                    void onEffectModeChange(selected.id, v).catch((e: unknown) => {
                      toast.error(e instanceof Error ? e.message : "Failed to change effect mode")
                    })
                  }
                }}
                disabled={selected.is_active}
              >
                <SelectTrigger size="sm" className="h-7 w-full text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="independent">Independent</SelectItem>
                  <SelectItem value="shared">Shared</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {/* New scene creation row */}
        <div className="flex items-center gap-1.5 px-3 py-2 border-t border-border">
          <Input
            placeholder="New scene name"
            value={newSceneName}
            onChange={(e) => setNewSceneName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                void handleCreate()
              }
            }}
            className="h-7 text-xs flex-1 min-w-0"
          />
          <Button
            variant="outline"
            size="sm"
            className="h-7 w-7 p-0 text-sm shrink-0"
            onClick={() => void handleCreate()}
          >
            +
          </Button>
        </div>
      </CardContent>
    </Card>
  )
})
