import { useRef, useState, useCallback } from "react"
import { toast } from "sonner"
import * as THREE from "three"
import { useScene } from "@/hooks/use-scene"
import { useDevices } from "@/hooks/use-devices"
import SceneViewport from "@/components/scene/scene-viewport"
import DeviceMesh from "@/components/scene/device-mesh"
import BoundsBox from "@/components/scene/bounds-box"
import DeviceListPanel from "@/components/scene/device-list-panel"
import PropertiesPanel from "@/components/scene/properties-panel"
import SceneToolbar from "@/components/scene/scene-toolbar"
import MappingPreview from "@/components/scene/mapping-preview"
import {
  LinearMappingHelpers,
  RadialMappingHelpers,
  type MappingHandleId,
} from "@/components/scene/mapping-helpers"
import type { Placement } from "@/lib/types"

type CameraPreset = "Perspective" | "Top" | "Front" | "Side"

function getMappingParams(scene: { mapping?: { type: string; params: Record<string, unknown> } | null } | null) {
  const params = scene?.mapping?.params ?? {}
  return {
    origin: (params.origin as [number, number, number]) ?? [0, 0, 0],
    direction: (params.direction as [number, number, number]) ?? [1, 0, 0],
    center: (params.center as [number, number, number]) ?? [0, 0, 0],
  }
}

function computeEndpoint(
  origin: [number, number, number],
  direction: [number, number, number],
): [number, number, number] {
  return [origin[0] + direction[0], origin[1] + direction[1], origin[2] + direction[2]]
}

function clampToBounds(
  pos: [number, number, number],
  bounds: [[number, number, number], [number, number, number]] | null,
): [number, number, number] {
  if (!bounds) return pos
  const [min, max] = bounds
  return [
    Math.max(min[0], Math.min(max[0], pos[0])),
    Math.max(min[1], Math.min(max[1], pos[1])),
    Math.max(min[2], Math.min(max[2], pos[2])),
  ]
}

export default function ScenePage() {
  const { scene, loading, movePlacement, removePlacement, changeMapping, addPlacement } = useScene()
  const { devices, frameData } = useDevices()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedHandle, setSelectedHandle] = useState<MappingHandleId | null>(null)
  const [transformMode, setTransformMode] = useState<"translate" | "rotate">("translate")
  const cameraKeyRef = useRef(0)
  const [cameraPreset, setCameraPreset] = useState<{ name: CameraPreset; key: number } | null>(null)
  const [snapEnabled, setSnapEnabled] = useState(false)
  const [snapIncrement, setSnapIncrement] = useState(0.5)
  const [showBounds, setShowBounds] = useState(true)

  const deviceRefs = useRef<Map<string, THREE.Group>>(new Map())
  const linearOriginRef = useRef<THREE.Group>(null)
  const linearEndRef = useRef<THREE.Group>(null)
  const radialCenterRef = useRef<THREE.Group>(null)

  const getTransformTarget = (): THREE.Object3D | null => {
    if (selectedHandle === "linear-origin") return linearOriginRef.current
    if (selectedHandle === "linear-end") return linearEndRef.current
    if (selectedHandle === "radial-center") return radialCenterRef.current
    if (selectedId) return deviceRefs.current.get(selectedId) ?? null
    return null
  }
  const transformTarget = getTransformTarget()

  const selectedPlacement: Placement | null =
    scene?.placements.find((p) => p.device_id === selectedId) ?? null
  const selectedDevice = devices.find((d) => d.name === selectedId) ?? null

  const mappingType = (scene?.mapping?.type ?? "linear") as "linear" | "radial"
  const mappingParams = getMappingParams(scene)

  const handlePositionChange = useCallback(
    async (deviceId: string, position: [number, number, number]) => {
      await movePlacement(deviceId, position)
      toast.success(`Moved ${deviceId}`)
    },
    [movePlacement],
  )

  const handleRemove = useCallback(
    async (deviceId: string) => {
      await removePlacement(deviceId)
      setSelectedId(null)
      toast.success(`Removed ${deviceId}`)
    },
    [removePlacement],
  )

  const handleMappingChange = useCallback(
    async (type: "linear" | "radial") => {
      const bounds = scene?.bounds
      const params: Record<string, unknown> = {}
      if (bounds) {
        const [min, max] = bounds
        if (type === "linear") {
          params.origin = [...min]
          params.direction = [max[0] - min[0], max[1] - min[1], max[2] - min[2]]
        } else {
          params.center = [
            (min[0] + max[0]) / 2,
            (min[1] + max[1]) / 2,
            (min[2] + max[2]) / 2,
          ]
        }
      }
      await changeMapping(type, params)
      toast.success(`Mapping set to ${type}`)
    },
    [changeMapping, scene?.bounds],
  )

  const handleTransformEnd = useCallback(
    async (position: [number, number, number]) => {
      if (selectedHandle) {
        const clamped = clampToBounds(position, scene?.bounds ?? null)
        const currentParams = scene?.mapping?.params ?? {}
        if (selectedHandle === "radial-center") {
          await changeMapping("radial", { ...currentParams, center: clamped })
          toast.success("Radial center updated")
        } else if (selectedHandle === "linear-origin") {
          const dir = (currentParams.direction as number[]) ?? [1, 0, 0]
          await changeMapping("linear", { ...currentParams, origin: clamped, direction: dir })
          toast.success("Linear origin updated")
        } else if (selectedHandle === "linear-end") {
          const origin = (currentParams.origin as number[]) ?? [0, 0, 0]
          const newDir = [clamped[0] - origin[0], clamped[1] - origin[1], clamped[2] - origin[2]]
          await changeMapping("linear", { ...currentParams, origin, direction: newDir })
          toast.success("Linear direction updated")
        }
      } else if (selectedId) {
        await movePlacement(selectedId, position)
      }
    },
    [selectedId, selectedHandle, movePlacement, changeMapping, scene?.mapping?.params, scene?.bounds],
  )

  const handleSelectDevice = useCallback((deviceId: string | null) => {
    setSelectedId(deviceId)
    setSelectedHandle(null)
  }, [])

  const handleSelectHandle = useCallback((id: MappingHandleId, e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    setSelectedHandle(id)
    setSelectedId(null)
  }, [])

  // Clamp mapping handles to bounds during drag
  const handleTransformChange = useCallback(
    (target: THREE.Object3D) => {
      if (!selectedHandle || !scene?.bounds) return
      const [min, max] = scene.bounds
      const p = target.position
      p.x = Math.max(min[0], Math.min(max[0], p.x))
      p.y = Math.max(min[1], Math.min(max[1], p.y))
      p.z = Math.max(min[2], Math.min(max[2], p.z))
    },
    [selectedHandle, scene?.bounds],
  )

  const handleAddDevice = useCallback(
    async (deviceName: string, ledCount: number) => {
      await addPlacement(deviceName, ledCount)
      setSelectedId(deviceName)
      setSelectedHandle(null)
      toast.success(`Added ${deviceName} to scene`)
    },
    [addPlacement],
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Loading scene...</p>
      </div>
    )
  }

  const placements = scene?.placements ?? []
  const endpoint = computeEndpoint(
    mappingParams.origin as [number, number, number],
    mappingParams.direction as [number, number, number],
  )

  return (
    <div className="flex flex-col h-full gap-0">
      <SceneToolbar
        transformMode={transformMode}
        onTransformModeChange={setTransformMode}
        mappingType={mappingType}
        onMappingTypeChange={handleMappingChange}
        onCameraPreset={(name) => setCameraPreset({ name, key: ++cameraKeyRef.current })}
        snapEnabled={snapEnabled}
        onSnapToggle={setSnapEnabled}
        snapIncrement={snapIncrement}
        onSnapIncrementChange={setSnapIncrement}
        showBounds={showBounds}
        onToggleBounds={() => setShowBounds((v) => !v)}
      />

      <div className="flex-1 flex gap-2 min-h-0 p-2">
        <div className="w-52 shrink-0">
          <DeviceListPanel
            placements={placements}
            allDevices={devices}
            selectedDeviceId={selectedId}
            onSelectDevice={handleSelectDevice}
            onAddDevice={handleAddDevice}
          />
        </div>

        <div className="flex-1 min-w-0 rounded-lg border border-border overflow-hidden">
          <SceneViewport
            onPointerMissed={() => {
              setSelectedId(null)
              setSelectedHandle(null)
            }}
            transformTarget={transformTarget}
            transformMode={transformMode}
            onTransformEnd={handleTransformEnd}
            onTransformChange={handleTransformChange}
            cameraPreset={cameraPreset}
            snapEnabled={snapEnabled}
            snapIncrement={snapIncrement}
          >
            {placements.map((p) => (
              <DeviceMesh
                ref={(el) => {
                  if (el) deviceRefs.current.set(p.device_id, el)
                  else deviceRefs.current.delete(p.device_id)
                }}
                key={p.device_id}
                position={p.position}
                geometry={p.geometry}
                ledCount={p.led_count}
                frameData={frameData.get(p.device_id) ?? null}
                selected={selectedId === p.device_id}
                onClick={(e) => {
                  e.stopPropagation()
                  handleSelectDevice(p.device_id)
                }}
              />
            ))}

            {showBounds && scene?.bounds && (
              <BoundsBox min={scene.bounds[0]} max={scene.bounds[1]} />
            )}

            {mappingType === "linear" && (
              <LinearMappingHelpers
                origin={mappingParams.origin as [number, number, number]}
                endpoint={endpoint}
                selectedHandle={selectedHandle}
                onSelectHandle={handleSelectHandle}
                originRef={linearOriginRef}
                endRef={linearEndRef}
              />
            )}

            {mappingType === "radial" && (
              <RadialMappingHelpers
                center={mappingParams.center as [number, number, number]}
                selectedHandle={selectedHandle}
                onSelectHandle={handleSelectHandle}
                centerRef={radialCenterRef}
              />
            )}
          </SceneViewport>
        </div>

        <div className="w-56 shrink-0">
          <PropertiesPanel
            placement={selectedPlacement}
            deviceInfo={selectedDevice}
            onPositionChange={handlePositionChange}
            onRemove={handleRemove}
          />
        </div>
      </div>

      <MappingPreview
        placements={placements}
        frameData={frameData}
        selectedDeviceId={selectedId}
        onSelectDevice={handleSelectDevice}
      />
    </div>
  )
}
