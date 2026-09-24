import { useState, type ReactNode } from 'react'
import { AttentionButton } from '@/chrome/attention-button'
import { ConnectionIndicator } from '@/chrome/connection-indicator'
import { HERO_CHROME } from '@/chrome/state'
import { PreviewOnlySwitch } from '@/chrome/preview-only-switch'
import { TempoModule } from '@/chrome/tempo-module'
import { Button, IconButton } from '@/design/button'
import { Chip, Label, Tag } from '@/design/chip'
import { Field } from '@/design/field'
import { Dialog, Popover, Sheet, Tooltip } from '@/design/overlays'
import { Segmented } from '@/design/segmented'
import { Select } from '@/design/select'
import { Slider } from '@/design/slider'
import { Switch } from '@/design/switch'
import { Toast } from '@/design/toast'

const TRANSITIONS = { cut: 'Cut', fade: 'Fade · 1 s', dissolve: 'Dissolve · 3 s' }

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <Label>{label}</Label>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </section>
  )
}

/** An unlinked specimen of the §6.1 primitives and §6.2 cluster, for comparing with System.png. */
export function SystemPage() {
  const [on, setOn] = useState(true)
  const [level, setLevel] = useState(70)
  const [view, setView] = useState<'3d' | 'plan'>('3d')
  const [transition, setTransition] = useState<keyof typeof TRANSITIONS>('dissolve')
  const tempo = HERO_CHROME.tempo

  return (
    <div className="flex flex-col gap-8 p-6">
      <Row label="Buttons">
        <Button variant="primary" icon="plus">Put a look on</Button>
        <Button>Change</Button>
        <Button variant="outline">Tweak</Button>
        <Button variant="ghost">Cancel</Button>
        <Button variant="danger" icon="power">Off</Button>
        <Button size="sm">Stop ripple</Button>
        <Button variant="primary" size="lg">Start</Button>
        <Button disabled>Restart</Button>
        <IconButton icon="refresh" label="Refresh" />
        <IconButton icon="plan" label="Plan view" active />
      </Row>
      <Row label="Controls">
        <Switch checked={on} onCheckedChange={setOn} label="Evening" />
        <Switch checked={on} onCheckedChange={setOn} label="Preview only" tape />
        <Slider className="w-55" label="Brightness" value={level} onValueChange={setLevel} format={(v) => `${v}%`} />
        <Segmented
          label="View"
          value={view}
          onValueChange={setView}
          options={[
            { value: '3d', label: '3D', icon: 'cube' },
            { value: 'plan', label: 'Plan', icon: 'plan' },
          ]}
        />
        <Select className="w-40" label="Transition" value={transition} items={TRANSITIONS} onValueChange={setTransition} />
        <Field className="w-30" label="Height" unit="m" defaultValue="1.20" />
      </Row>
      <Row label="Chips, tags and labels">
        <Chip icon="music">Music</Chip>
        <Chip variant="mod">Evening</Chip>
        <Chip variant="quiet">No DJ</Chip>
        <Chip variant="signal" icon="music">Music · 42 s</Chip>
        <Chip variant="solid">Glow</Chip>
        <Tag>Living room</Tag>
        <Tag variant="signal" icon="alert">OFFLINE</Tag>
        <Tag variant="solid">PREVIEW</Tag>
        <Label>Running</Label>
      </Row>
      <Row label="Overlays">
        <Tooltip content="Fit the home">
          <IconButton icon="crosshair" label="Fit" />
        </Tooltip>
        <Popover trigger={<Button>Popover</Button>} title="Needs attention">
          <p className="px-3.5 pb-3 text-body text-text-2">Rope is offline since 17:02.</p>
        </Popover>
        <Dialog trigger={<Button>Dialog</Button>} title="Restore from a file">
          <p className="text-body text-text-2">Everything is replaced by the file.</p>
        </Dialog>
        <Sheet trigger={<Button>Sheet</Button>} title="Put a look on">
          <p className="pb-2 text-body text-text-2">Where, then what.</p>
        </Sheet>
        <Toast
          icon="bell"
          title="Doorbell"
          detail="Front door · 19:16"
          readout="1.8 s"
          tint="#ffcf5c"
          action={<Button size="sm">Stop ripple</Button>}
        />
      </Row>
      <Row label="Always within reach">
        <TempoModule variant="bar" {...tempo} />
        <TempoModule variant="bar" source="internal" bpm={118} beat={2} bar={7} stale />
        <div className="w-89.5">
          <TempoModule variant="strip" {...tempo} />
        </div>
        <PreviewOnlySwitch variant="bar" on={false} />
        <PreviewOnlySwitch variant="bar" on />
        <PreviewOnlySwitch variant="header" on={false} />
        <PreviewOnlySwitch variant="header" on />
        <AttentionButton variant="bar" count={2} />
        <AttentionButton variant="bar" count={0} />
        <AttentionButton variant="header" count={1} />
        <ConnectionIndicator variant="bar" connection={{ status: 'live', fps: 60 }} />
        <ConnectionIndicator variant="bar" connection={{ status: 'reconnecting', attempt: 3 }} />
        <ConnectionIndicator variant="header" connection={{ status: 'reconnecting', attempt: 3 }} />
      </Row>
    </div>
  )
}
