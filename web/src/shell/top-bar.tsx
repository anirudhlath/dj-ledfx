import type { ReactNode } from 'react'
import { ChromeAttention, ChromeConnection, ChromePreviewOnly, ChromeTempo } from '@/chrome/live'

export interface TopBarProps {
  title: string
  context?: ReactNode
}

/**
 * §4.1 top bar (Main.png): title and context, then the always-within-reach cluster (§6.2). Each part
 * of the cluster reads its own slice of the live store, so the bar itself doesn't redraw for a beat.
 */
export function TopBar({ title, context }: TopBarProps) {
  return (
    <header className="flex h-(--topbar-h) min-w-0 items-center justify-between gap-4 border-b border-line-soft bg-bg pr-5 pl-6">
      <div className="flex min-w-0 items-baseline gap-3">
        <h1 className="truncate text-title font-semibold tracking-[-0.005em]">{title}</h1>
        {context && <span className="text-data whitespace-nowrap text-text-3 tablet:hidden">{context}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-3.5 tablet:gap-2.5">
        <ChromeTempo />
        <ChromePreviewOnly variant="bar" />
        <ChromeAttention variant="bar" />
        <ChromeConnection variant="bar" />
      </div>
    </header>
  )
}
