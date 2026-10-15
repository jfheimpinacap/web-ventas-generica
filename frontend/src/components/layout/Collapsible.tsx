import type { ReactNode } from 'react'

// A fractional grid track follows the intrinsic height without a height cap.
// Keep children mounted through closing and remove closed content from tab order.
export function Collapsible({ id, expanded, children }: { id: string; expanded: boolean; children: ReactNode }) {
  return <div id={id} className={`sidebar-collapse${expanded ? ' is-expanded' : ''}`} aria-hidden={!expanded} {...{ inert: expanded ? undefined : '' }}>
    <div className="sidebar-collapse__inner">{children}</div>
  </div>
}
