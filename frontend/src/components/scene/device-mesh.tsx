import { useMemo, forwardRef } from "react"
import * as THREE from "three"
import { type ThreeEvent } from "@react-three/fiber"
import type { GeometryInfo, FrameData } from "@/lib/types"

interface DeviceMeshProps {
  position: [number, number, number]
  geometry: GeometryInfo
  ledCount: number
  frameData?: FrameData | null
  selected?: boolean
  onClick?: (e: ThreeEvent<MouseEvent>) => void
  onPointerOver?: (e: ThreeEvent<PointerEvent>) => void
  onPointerOut?: (e: ThreeEvent<PointerEvent>) => void
}

/** Default color when no frame data — bright enough to see on dark backgrounds */
const NO_DATA_COLOR = new THREE.Color(0.6, 0.6, 0.7)
const NO_DATA_EMISSIVE = new THREE.Color(0.1, 0.1, 0.15)

/** Convert RGB byte at index to THREE.Color */
function rgbAt(rgb: Uint8Array | undefined, index: number): THREE.Color {
  if (!rgb || index * 3 + 2 >= rgb.length) return NO_DATA_COLOR
  const r = rgb[index * 3] / 255
  const g = rgb[index * 3 + 1] / 255
  const b = rgb[index * 3 + 2] / 255
  return new THREE.Color(r, g, b)
}

const SPHERE_RADIUS = 0.08
const SELECTED_EMISSIVE = new THREE.Color(0.2, 0.2, 0.5)
const DEFAULT_EMISSIVE = new THREE.Color(0, 0, 0)

function LedSphere({
  position,
  rgb,
  index,
  radius,
  segments,
  selected,
}: {
  position: [number, number, number]
  rgb?: Uint8Array
  index: number
  radius: number
  segments: number
  selected?: boolean
}) {
  const color = rgbAt(rgb, index)
  const hasData = rgb && index * 3 + 2 < rgb.length
  const emissive = selected ? SELECTED_EMISSIVE : hasData ? DEFAULT_EMISSIVE : NO_DATA_EMISSIVE
  return (
    <mesh position={position}>
      <sphereGeometry args={[radius, segments, segments]} />
      <meshStandardMaterial color={color} emissive={emissive} roughness={0.4} />
    </mesh>
  )
}

function PointDevice({ rgb, selected }: { rgb?: Uint8Array; selected?: boolean }) {
  return <LedSphere position={[0, 0, 0]} rgb={rgb} index={0} radius={SPHERE_RADIUS * 3} segments={16} selected={selected} />
}

const DEFAULT_DIRECTION: number[] = [1, 0, 0]

function StripDevice({
  geometry,
  ledCount,
  rgb,
  selected,
}: {
  geometry: GeometryInfo
  ledCount: number
  rgb?: Uint8Array
  selected?: boolean
}) {
  const direction = geometry.direction ?? DEFAULT_DIRECTION
  const length = geometry.length ?? 1.0
  const dir = useMemo(() => new THREE.Vector3(...direction).normalize(), [direction])

  const positions = useMemo(() => {
    const pts: [number, number, number][] = []
    for (let i = 0; i < ledCount; i++) {
      const t = ledCount > 1 ? (i + 0.5) / ledCount : 0.5
      pts.push([dir.x * length * t, dir.y * length * t, dir.z * length * t])
    }
    return pts
  }, [dir, length, ledCount])

  return (
    <group>
      {positions.map((pos, i) => (
        <LedSphere key={i} position={pos} rgb={rgb} index={i} radius={SPHERE_RADIUS} segments={8} selected={selected} />
      ))}
    </group>
  )
}

function MatrixDevice({
  geometry,
  ledCount,
  rgb,
  selected,
}: {
  geometry: GeometryInfo
  ledCount: number
  rgb?: Uint8Array
  selected?: boolean
}) {
  const pitch = geometry.pixel_pitch ?? 0.03

  const positions = useMemo(() => {
    const pts: [number, number, number][] = []
    if (geometry.tiles) {
      for (const tile of geometry.tiles) {
        for (let row = 0; row < tile.height; row++) {
          for (let col = 0; col < tile.width; col++) {
            pts.push([
              tile.offset_x + col * pitch,
              tile.offset_y + row * pitch,
              0,
            ])
          }
        }
      }
    } else {
      const side = Math.ceil(Math.sqrt(ledCount))
      for (let i = 0; i < ledCount; i++) {
        pts.push([(i % side) * pitch, Math.floor(i / side) * pitch, 0])
      }
    }
    return pts
  }, [geometry.tiles, ledCount, pitch])

  return (
    <group>
      {positions.map((pos, i) => (
        <LedSphere key={i} position={pos} rgb={rgb} index={i} radius={SPHERE_RADIUS * 0.8} segments={6} selected={selected} />
      ))}
    </group>
  )
}

const DeviceMesh = forwardRef<THREE.Group, DeviceMeshProps>(function DeviceMesh(
  { position, geometry, ledCount, frameData, selected, onClick, onPointerOver, onPointerOut },
  ref
) {
  const rgb = frameData?.rgb

  return (
    <group
      ref={ref}
      position={position}
      onClick={onClick}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
    >
      {geometry.type === "point" && <PointDevice rgb={rgb} selected={selected} />}
      {geometry.type === "strip" && (
        <StripDevice geometry={geometry} ledCount={ledCount} rgb={rgb} selected={selected} />
      )}
      {geometry.type === "matrix" && (
        <MatrixDevice geometry={geometry} ledCount={ledCount} rgb={rgb} selected={selected} />
      )}
    </group>
  )
})

export default DeviceMesh
