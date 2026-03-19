import { useRef, useState, forwardRef, useImperativeHandle } from "react"
import * as THREE from "three"
import { type ThreeEvent, useFrame } from "@react-three/fiber"
import { Line } from "@react-three/drei"

const HANDLE_RADIUS = 0.15
const HANDLE_SEGMENTS = 16

const LINEAR_COLOR = "#ffaa00"
const LINEAR_EMISSIVE = "#664400"
const RADIAL_COLOR = "#ff44ff"
const RADIAL_EMISSIVE = "#662266"
const SELECTED_EMISSIVE = "#ffffff"

export type MappingHandleId = "linear-origin" | "linear-end" | "radial-center"

const Handle = forwardRef<THREE.Group, {
  position: [number, number, number]
  color: string
  emissive: string
  selected: boolean
  onClick: (e: ThreeEvent<MouseEvent>) => void
}>(({ position, color, emissive, selected, onClick }, ref) => {
  const groupRef = useRef<THREE.Group>(null!)
  useImperativeHandle(ref, () => groupRef.current)

  return (
    <group ref={groupRef} position={position}>
      <mesh onClick={onClick}>
        <sphereGeometry args={[HANDLE_RADIUS, HANDLE_SEGMENTS, HANDLE_SEGMENTS]} />
        <meshStandardMaterial
          color={color}
          emissive={selected ? SELECTED_EMISSIVE : emissive}
          emissiveIntensity={selected ? 0.5 : 0.2}
          roughness={0.3}
          transparent
          opacity={0.9}
        />
      </mesh>
    </group>
  )
})
Handle.displayName = "Handle"

/** Line + arrow that follows two group refs every frame. */
function LiveConnector({
  originRef,
  endRef,
  color,
}: {
  originRef: React.RefObject<THREE.Group | null>
  endRef: React.RefObject<THREE.Group | null>
  color: string
}) {
  const coneRef = useRef<THREE.Mesh>(null!)
  const [points, setPoints] = useState<[THREE.Vector3, THREE.Vector3]>([
    new THREE.Vector3(), new THREE.Vector3(),
  ])

  useFrame(() => {
    const a = originRef.current
    const b = endRef.current
    if (!a || !b) return

    const ap = a.position
    const bp = b.position

    // Only update state if positions actually changed (avoids re-render flood)
    const [prevA, prevB] = points
    if (
      prevA.x !== ap.x || prevA.y !== ap.y || prevA.z !== ap.z ||
      prevB.x !== bp.x || prevB.y !== bp.y || prevB.z !== bp.z
    ) {
      setPoints([ap.clone(), bp.clone()])
    }

    // Update arrow cone
    const cone = coneRef.current
    if (cone) {
      const dir = new THREE.Vector3().subVectors(bp, ap)
      const len = dir.length()
      if (len > 0.01) {
        dir.normalize()
        cone.position.copy(bp)
        cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir)
        cone.visible = true
      } else {
        cone.visible = false
      }
    }
  })

  return (
    <>
      <Line
        points={[points[0], points[1]]}
        color={color}
        lineWidth={1.5}
      />
      <mesh ref={coneRef}>
        <coneGeometry args={[0.08, 0.2, 8]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.3} />
      </mesh>
    </>
  )
}

interface LinearHelpersProps {
  origin: [number, number, number]
  endpoint: [number, number, number]
  selectedHandle: MappingHandleId | null
  onSelectHandle: (id: MappingHandleId, e: ThreeEvent<MouseEvent>) => void
  originRef: React.RefObject<THREE.Group | null>
  endRef: React.RefObject<THREE.Group | null>
}

export function LinearMappingHelpers({
  origin,
  endpoint,
  selectedHandle,
  onSelectHandle,
  originRef,
  endRef,
}: LinearHelpersProps) {
  return (
    <>
      <Handle
        ref={originRef}
        position={origin}
        color={LINEAR_COLOR}
        emissive={LINEAR_EMISSIVE}
        selected={selectedHandle === "linear-origin"}
        onClick={(e) => onSelectHandle("linear-origin", e)}
      />
      <Handle
        ref={endRef}
        position={endpoint}
        color={LINEAR_COLOR}
        emissive={LINEAR_EMISSIVE}
        selected={selectedHandle === "linear-end"}
        onClick={(e) => onSelectHandle("linear-end", e)}
      />
      <LiveConnector originRef={originRef} endRef={endRef} color={LINEAR_COLOR} />
    </>
  )
}

interface RadialHelpersProps {
  center: [number, number, number]
  selectedHandle: MappingHandleId | null
  onSelectHandle: (id: MappingHandleId, e: ThreeEvent<MouseEvent>) => void
  centerRef: React.Ref<THREE.Group>
}

export function RadialMappingHelpers({
  center,
  selectedHandle,
  onSelectHandle,
  centerRef,
}: RadialHelpersProps) {
  return (
    <>
      <Handle
        ref={centerRef}
        position={center}
        color={RADIAL_COLOR}
        emissive={RADIAL_EMISSIVE}
        selected={selectedHandle === "radial-center"}
        onClick={(e) => onSelectHandle("radial-center", e)}
      />
      <mesh position={center} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.4, 0.45, 32]} />
        <meshStandardMaterial
          color={RADIAL_COLOR}
          emissive={RADIAL_EMISSIVE}
          transparent
          opacity={0.4}
          side={THREE.DoubleSide}
        />
      </mesh>
    </>
  )
}
