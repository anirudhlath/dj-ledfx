import type { ReactNode } from 'react'

export interface EmptyStateProps {
  title: string
  /** The title's element. The error pages make it the heading; the other pages have their own. */
  as?: 'p' | 'h1' | 'h2'
  /** The line under the title. */
  children: ReactNode
  action?: ReactNode
}

/** A calm message in the middle of <main>: the placeholders, not-found and the error pages. */
export function EmptyState({ title, as: Title = 'p', children, action }: EmptyStateProps) {
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <Title className="font-serif text-display-lg">{title}</Title>
        <p className="text-body text-text-2">{children}</p>
        {action}
      </div>
    </div>
  )
}
