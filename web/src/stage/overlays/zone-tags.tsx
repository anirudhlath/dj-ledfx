// State-Problems' and State-Transition's tags on the stage (F3 decision 18), F0's Tag: signal for a
// crashed or slow zone, solid for a transition, whose percentage moves on by itself (decision 16). The
// cards say the same, so assistive technology skips the tags.
import { useRef } from 'react'
import { Tag } from '@/design/chip'
import { useMovingProgress } from '@/zones/use-moving-progress'
import { projectPoint, type CameraPose } from '../camera'
import type { ZoneTag } from '../tags'

export function ZoneTags({ tags, pose }: { tags: readonly ZoneTag[]; pose: CameraPose }) {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0">
      {tags.map((tag) => {
        const [x, y] = projectPoint(pose, tag.at)
        return (
          <div key={tag.zoneId} className="absolute -translate-1/2" style={{ left: x, top: y }}>
            {tag.kind === 'transition' ? (
              <TransitionTag text={tag.text} progress={tag.progress} durationS={tag.durationS} />
            ) : (
              <Tag variant="signal" icon={tag.kind === 'crashed' ? 'alert' : 'clock'}>
                {tag.text}
              </Tag>
            )}
          </div>
        )
      })}
    </div>
  )
}

function TransitionTag({ text, progress, durationS }: { text: string; progress: number; durationS: number | null }) {
  const percent = useRef<HTMLSpanElement>(null)
  useMovingProgress(progress, durationS, percent)
  return (
    <Tag variant="solid" icon="refresh">
      {text} <span ref={percent} />
    </Tag>
  )
}
