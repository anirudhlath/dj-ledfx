// A browser without WebGL 2, or with it switched off or blocked, can't draw the home. It says so where
// the stage would be (EmptyState centres and pads itself); the room links (room-links.tsx) and the
// Running panel still work.
import { EmptyState } from '@/pages/empty-state'

export function NoWebGL() {
  return (
    <div className="absolute inset-0">
      <EmptyState title="The home can't be drawn here">This browser can't draw the 3D home. Everything else still works.</EmptyState>
    </div>
  )
}
