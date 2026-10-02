// The static home on the canvas (§7.1): made once per home, and set to the camera's pose (the sides
// it sees, the stage's size). React doesn't dispose a <primitive>'s three objects, so this does when
// the home changes.
import { useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo } from 'react'
import type { Home } from '@/api/contract'
import type { CameraPose } from '../camera'
import { HomeScene } from './home-scene'

export interface StaticHomeProps {
  home: Home
  pose: CameraPose
}

export function StaticHome({ home, pose }: StaticHomeProps) {
  const scene = useMemo(() => new HomeScene(home), [home])
  const pixelRatio = useThree((state) => state.viewport.dpr)
  const invalidate = useThree((state) => state.invalidate)
  useEffect(() => () => scene.dispose(), [scene])
  useLayoutEffect(() => {
    scene.setView(pose, pixelRatio)
    invalidate()
  }, [scene, pose, pixelRatio, invalidate])
  return <primitive object={scene.group} />
}
