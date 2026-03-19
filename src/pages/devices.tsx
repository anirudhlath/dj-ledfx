import { useState } from "react"
import { useDevices } from "@/hooks/use-devices"
import type { Device, DeviceGroup } from "@/lib/types"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

// ─── Device type badge ──────────────────────────────────────────────────────

function DeviceTypeBadge({ type }: { type: string }) {
  return (
    <Badge variant="outline" className="text-[10px] font-mono uppercase tracking-wider">
      {type}
    </Badge>
  )
}

// ─── Expandable row detail ──────────────────────────────────────────────────

interface RowDetailProps {
  device: Device
  onIdentify: (name: string) => Promise<void>
}

function RowDetail({ device, onIdentify }: RowDetailProps) {
  const [identifying, setIdentifying] = useState(false)

  const handleIdentify = async () => {
    setIdentifying(true)
    try {
      await onIdentify(device.name)
      toast.success(`Identifying ${device.name}…`, {
        description: "Device should flash its LEDs.",
      })
    } catch {
      toast.error(`Failed to identify ${device.name}`)
    } finally {
      setIdentifying(false)
    }
  }

  return (
    <div className="px-4 py-3 bg-muted/20 border-t border-border flex flex-wrap items-center gap-6">
      {/* Identify */}
      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs"
        onClick={handleIdentify}
        disabled={identifying}
      >
        {identifying ? "Identifying…" : "Identify"}
      </Button>

      <Separator orientation="vertical" className="h-5" />

      {/* Frames dropped */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
          Frames Dropped
        </span>
        <span
          className={[
            "text-xs font-mono",
            device.frames_dropped > 0 ? "text-yellow-400" : "text-muted-foreground",
          ].join(" ")}
        >
          {device.frames_dropped}
        </span>
      </div>

      {/* Latency detail */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
          Effective Latency
        </span>
        <span className="text-xs font-mono text-foreground/80">
          {device.effective_latency_ms > 0
            ? `${Math.round(device.effective_latency_ms)} ms`
            : "—"}
        </span>
      </div>

      {/* Address detail */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
          Address
        </span>
        <span className="text-xs font-mono text-foreground/70">{device.address || "—"}</span>
      </div>

      {/* LED count */}
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
          LEDs
        </span>
        <span className="text-xs font-mono text-foreground/70">{device.led_count}</span>
      </div>
    </div>
  )
}

// ─── Device table row ────────────────────────────────────────────────────────

interface DeviceRowProps {
  device: Device
  expanded: boolean
  onToggle: () => void
  onIdentify: (name: string) => Promise<void>
}

function DeviceRow({ device, expanded, onToggle, onIdentify }: DeviceRowProps) {
  return (
    <>
      <TableRow
        className="cursor-pointer select-none"
        onClick={onToggle}
        data-state={expanded ? "selected" : undefined}
      >
        {/* Status dot */}
        <TableCell className="w-8 pl-4">
          <span
            className={[
              "block size-2 rounded-full",
              device.connected ? "bg-green-500" : "bg-red-500/60",
            ].join(" ")}
            title={device.connected ? "Connected" : "Disconnected"}
          />
        </TableCell>

        {/* Name */}
        <TableCell className="font-medium text-sm max-w-[200px] truncate">
          {device.name}
        </TableCell>

        {/* Type */}
        <TableCell>
          <DeviceTypeBadge type={device.device_type} />
        </TableCell>

        {/* LED count */}
        <TableCell className="font-mono text-xs text-muted-foreground text-right">
          {device.led_count}
        </TableCell>

        {/* Address */}
        <TableCell className="font-mono text-xs text-muted-foreground max-w-[140px] truncate">
          {device.address || "—"}
        </TableCell>

        {/* Group */}
        <TableCell>
          {device.group ? (
            <span className="text-xs text-foreground/70">{device.group}</span>
          ) : (
            <span className="text-xs text-muted-foreground/40">—</span>
          )}
        </TableCell>

        {/* FPS */}
        <TableCell className="font-mono text-xs text-right">
          {device.send_fps > 0 ? `${Math.round(device.send_fps)}` : "—"}
        </TableCell>

        {/* Latency */}
        <TableCell className="font-mono text-xs text-right pr-4">
          {device.effective_latency_ms > 0
            ? `${Math.round(device.effective_latency_ms)} ms`
            : "—"}
        </TableCell>
      </TableRow>

      {expanded && (
        <tr className="border-b border-border">
          <td colSpan={8} className="p-0">
            <RowDetail device={device} onIdentify={onIdentify} />
          </td>
        </tr>
      )}
    </>
  )
}

// ─── Devices table section ───────────────────────────────────────────────────

interface DeviceTableSectionProps {
  devices: Device[]
  loading: boolean
  identify: (name: string) => Promise<void>
}

function DeviceTableSection({ devices, loading, identify }: DeviceTableSectionProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  const toggleRow = (name: string) => {
    setExpandedRow((prev) => (prev === name ? null : name))
  }

  return (
    <Card>
      <CardHeader className="pb-3 pt-4 px-4">
        <div className="flex items-center gap-3">
          <CardTitle className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
            Devices
          </CardTitle>
          {!loading && (
            <span className="text-xs text-muted-foreground">
              {devices.filter((d) => d.connected).length}/{devices.length} online
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="px-4 pb-4 space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-3/4" />
          </div>
        ) : devices.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-xs text-muted-foreground">
              No devices found. Click "Scan for Devices" to discover.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-8 pl-4" />
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">LEDs</TableHead>
                <TableHead>Address</TableHead>
                <TableHead>Group</TableHead>
                <TableHead className="text-right">FPS</TableHead>
                <TableHead className="text-right pr-4">Latency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {devices.map((device) => (
                <DeviceRow
                  key={device.name}
                  device={device}
                  expanded={expandedRow === device.name}
                  onToggle={() => toggleRow(device.name)}
                  onIdentify={identify}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

// ─── New group dialog ────────────────────────────────────────────────────────

interface NewGroupDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (name: string, color: string) => Promise<void>
}

function NewGroupDialog({ open, onOpenChange, onAdd }: NewGroupDialogProps) {
  const [name, setName] = useState("")
  const [color, setColor] = useState("#7c3aed")
  const [saving, setSaving] = useState(false)

  const handleCreate = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await onAdd(name.trim(), color)
      toast.success(`Group "${name.trim()}" created`)
      setName("")
      setColor("#7c3aed")
      onOpenChange(false)
    } catch {
      toast.error("Failed to create group")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xs">
        <DialogHeader>
          <DialogTitle className="text-sm">New Group</DialogTitle>
        </DialogHeader>
        <div className="py-2 space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Name</Label>
            <Input
              placeholder="e.g. Stage Left"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="text-sm"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Color</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="h-8 w-12 rounded cursor-pointer border border-border bg-transparent p-0.5"
              />
              <span className="text-xs font-mono text-muted-foreground">{color}</span>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleCreate} disabled={!name.trim() || saving}>
            {saving ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Groups section ──────────────────────────────────────────────────────────

interface GroupsSectionProps {
  groups: Record<string, DeviceGroup>
  addGroup: (name: string, color: string) => Promise<void>
  removeGroup: (name: string) => Promise<void>
}

function GroupsSection({ groups, addGroup, removeGroup }: GroupsSectionProps) {
  const [dialogOpen, setDialogOpen] = useState(false)

  const handleDelete = async (name: string) => {
    try {
      await removeGroup(name)
      toast.success(`Group "${name}" deleted`)
    } catch {
      toast.error(`Failed to delete group "${name}"`)
    }
  }

  const groupList = Object.values(groups)

  return (
    <>
      <Card>
        <CardHeader className="pb-3 pt-4 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
              Groups
            </CardTitle>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => setDialogOpen(true)}
            >
              + New Group
            </Button>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {groupList.length === 0 ? (
            <p className="text-xs text-muted-foreground py-3 text-center">
              No groups defined. Create a group to organize devices.
            </p>
          ) : (
            <div className="space-y-1.5">
              {groupList.map((group) => (
                <div
                  key={group.name}
                  className="flex items-center gap-3 px-2 py-2 rounded-md hover:bg-muted/30 transition-colors"
                >
                  {/* Color dot */}
                  <span
                    className="size-3 rounded-full shrink-0 border border-border/50"
                    style={{ backgroundColor: group.color }}
                  />
                  {/* Name */}
                  <span className="text-sm flex-1">{group.name}</span>
                  {/* Color swatch label */}
                  <span className="text-[10px] font-mono text-muted-foreground/60">
                    {group.color}
                  </span>
                  {/* Delete */}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => handleDelete(group.name)}
                    title={`Delete group "${group.name}"`}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 16 16"
                      fill="currentColor"
                      className="size-3.5"
                    >
                      <path
                        fillRule="evenodd"
                        d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.711Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <NewGroupDialog open={dialogOpen} onOpenChange={setDialogOpen} onAdd={addGroup} />
    </>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function DevicesPage() {
  const { devices, groups, loading, discover, identify, addGroup, removeGroup } = useDevices()
  const [scanning, setScanning] = useState(false)

  const handleScan = async () => {
    setScanning(true)
    try {
      const discovered = await discover()
      const count = discovered.length
      toast.success(`Scan complete`, {
        description:
          count === 1
            ? "1 new device discovered."
            : `${count} new devices discovered.`,
      })
    } catch {
      toast.error("Scan failed", {
        description: "Could not reach the backend. Is the engine running?",
      })
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Devices</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage connected LED devices and groups
          </p>
        </div>
        <Button
          size="sm"
          onClick={handleScan}
          disabled={scanning || loading}
          className="gap-1.5"
        >
          {scanning ? (
            <>
              <span className="size-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
              Scanning…
            </>
          ) : (
            "Scan for Devices"
          )}
        </Button>
      </div>

      <Separator />

      {/* Device table */}
      <DeviceTableSection devices={devices} loading={loading} identify={identify} />

      {/* Groups */}
      <GroupsSection groups={groups} addGroup={addGroup} removeGroup={removeGroup} />
    </div>
  )
}
