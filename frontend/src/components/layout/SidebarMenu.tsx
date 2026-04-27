import { Link } from 'react-router-dom'
import { useState } from 'react'

import type { SidebarMenuItem } from '../../types/catalog'

interface SidebarMenuProps {
  items: SidebarMenuItem[]
}

function SidebarMenuNode({ item, level = 0 }: { item: SidebarMenuItem; level?: number }) {
  const hasChildren = Boolean(item.children?.length)
  const [isOpen, setIsOpen] = useState(level === 0)

  if (!hasChildren) {
    return (
      <li className="sidebar-menu__leaf">
        {item.to ? <Link to={item.to}>{item.label}</Link> : item.label}
      </li>
    )
  }

  return (
    <li>
      <button className="sidebar-menu__toggle" onClick={() => setIsOpen((prev) => !prev)} type="button">
        <span>{item.to ? <Link to={item.to} onClick={(event) => event.stopPropagation()}>{item.label}</Link> : item.label}</span>
        <span>{isOpen ? '−' : '+'}</span>
      </button>
      {isOpen && (
        <ul className="sidebar-menu sidebar-menu--nested">
          {item.children?.map((child) => (
            <SidebarMenuNode key={`${item.label}-${child.label}`} item={child} level={level + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function SidebarMenu({ items }: SidebarMenuProps) {
  return (
    <ul className="sidebar-menu">
      {items.map((item) => (
        <SidebarMenuNode key={item.label} item={item} />
      ))}
    </ul>
  )
}
