import type { ReactNode } from 'react'
import { AttentionButton } from '@/chrome/attention-button'
import { ConnectionIndicator } from '@/chrome/connection-indicator'
import type { ChromeState } from '@/chrome/state'
import { PreviewOnlySwitch } from '@/chrome/preview-only-switch'
import { TempoModule } from '@/chrome/tempo-module'

export interface TopBarProps {
  title: string
  context?: ReactNode
  chrome: ChromeState
}

/** §4.1 top bar (Main.png): title and context, then the always-within-reach cluster (§6.2). */
export function TopBar({ title, context, chrome }: TopBarProps) {
  return (
    <header className="flex h-(--topbar-h) min-w-0 items-center justify-between gap-4 border-b border-line-soft bg-bg pr-5 pl-6">
      <div className="flex min-w-0 items-baseline gap-3">
        <h1 className="truncate text-title font-semibold tracking-[-0.005em]">{title}</h1>
        {context && <span className="text-data whitespace-nowrap text-text-3 tablet:hidden">{context}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-3.5 tablet:gap-2.5">
        <TempoModule variant="bar" {...chrome.tempo} />
        <span aria-hidden="true" className="h-6 w-px bg-line tablet:hidden" />
        <PreviewOnlySwitch variant="bar" on={chrome.previewOnly} />
        <AttentionButton variant="bar" count={chrome.attention.total} />
        <ConnectionIndicator variant="bar" connection={chrome.connection} />
      </div>
    </header>
  )
}
