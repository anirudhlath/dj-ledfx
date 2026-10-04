// §8.1 top left: `3D | Plan` and the Labels switch. "Effects in space" waits for the fx stream
// (§7.4: "until that exists the toggle is hidden"). Live's preview-only label takes the stage's top and
// sets `--stage-top-shift` to its foot, so the tools start under it.
import { Segmented } from '@/design/segmented'
import { Switch } from '@/design/switch'
import type { ViewMode } from '../camera'
import { RENDER } from '../design-numbers'

const MODES = [
  { value: '3d', label: '3D', icon: 'cube' },
  { value: 'plan', label: 'Plan', icon: 'plan' },
] as const

export interface StageToolsProps {
  mode: ViewMode
  onMode: (mode: ViewMode) => void
  labels: boolean
  onLabels: (labels: boolean) => void
}

export function StageTools({ mode, onMode, labels, onLabels }: StageToolsProps) {
  const { leftPx, topPx, gapPx } = RENDER.tools
  return (
    <div className="absolute flex items-center" style={{ left: leftPx, top: `calc(var(--stage-top-shift, 0px) + ${topPx}px)`, gap: gapPx }}>
      <Segmented label="View" value={mode} options={MODES} onValueChange={onMode} />
      <Switch label="Labels" checked={labels} onCheckedChange={onLabels} />
    </div>
  )
}
