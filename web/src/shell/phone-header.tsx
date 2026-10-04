import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ChromeAttention, ChromeConnection, ChromePreviewOnly } from '@/chrome/live'
import { Icon } from '@/design/icon'

export interface PhoneHeaderProps {
  title: ReactNode
  /** Phone-Zone: a Back link before the title, to this path. */
  back?: string
  context?: ReactNode
  /** Drawn under the title row, inside the banner: the tempo strip on Live. */
  children?: ReactNode
}

/** §4.2 phone header (Phone-Live.png, Phone-Zone.png): Back, the serif title and context; reconnect, eye and attention. */
export function PhoneHeader({ title, back, context, children }: PhoneHeaderProps) {
  return (
    <header className="shrink-0">
      <div className="flex h-(--phone-header-h) items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 items-center gap-1">
          {back !== undefined && (
            <Link to={back} aria-label="Back" className="-ml-3 inline-flex size-11 shrink-0 items-center justify-center text-text-2">
              <Icon name="left" size={22} />
            </Link>
          )}
          <div className="flex min-w-0 flex-col">
            <h1 className="truncate font-serif text-display-md leading-none">{title}</h1>
            {context && <span className="mt-0.75 truncate text-meta text-text-3">{context}</span>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ChromeConnection variant="header" />
          <ChromePreviewOnly variant="header" />
          <ChromeAttention variant="header" />
        </div>
      </div>
      {children}
    </header>
  )
}
