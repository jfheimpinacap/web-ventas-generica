import { Link, useLocation } from 'react-router-dom'
import { useState } from 'react'

import type { SidebarMenuItem } from '../../types/catalog'

interface SidebarMenuProps {
  items: SidebarMenuItem[]
}

function SidebarMenuNode({
  item,
  activeCategoryId,
  level = 0,
}: {
  item: SidebarMenuItem
  activeCategoryId: string | null
  level?: number
}) {
  const hasChildren = Boolean(item.children?.length)
  const [isOpen, setIsOpen] = useState(level === 0)
  const categoryMatch = item.to?.match(/[?&]category=(\d+)/)
  const categoryId = categoryMatch?.[1] ?? null
  const isActive = Boolean(categoryId && activeCategoryId && categoryId === activeCategoryId)
  const handleNavigate = () => window.scrollTo({ top: 0, behavior: 'smooth' })

  if (!hasChildren) {
    return (
      <li className="sidebar-menu__leaf">
        {item.to ? (
          <Link to={item.to} className={isActive ? 'sidebar-menu__link sidebar-menu__link--active' : 'sidebar-menu__link'} onClick={handleNavigate}>
            {item.label}
          </Link>
        ) : (
          item.label
        )}
      </li>
    )
  }

  return (
    <li>
      <div className="sidebar-menu__group">
        <span className="sidebar-menu__group-label">
          {item.to ? (
            <Link
              to={item.to}
              className={isActive ? 'sidebar-menu__link sidebar-menu__link--active' : 'sidebar-menu__link'}
              onClick={handleNavigate}
            >
              {item.label}
            </Link>
          ) : (
            item.label
          )}
        </span>
        <button
          className="sidebar-menu__toggle"
          onClick={() => setIsOpen((prev) => !prev)}
          type="button"
          aria-expanded={isOpen}
          aria-label={`${isOpen ? 'Contraer' : 'Expandir'} subcategorías de ${item.label}`}
        >
          <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
        </button>
      </div>
      {isOpen && (
        <ul className="sidebar-menu sidebar-menu--nested">
          {item.children?.map((child) => (
            <SidebarMenuNode key={`${item.label}-${child.label}`} item={child} activeCategoryId={activeCategoryId} level={level + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function SidebarMenu({ items }: SidebarMenuProps) {
  const location = useLocation()
  const activeCategoryId = new URLSearchParams(location.search).get('category')

  return (
    <ul className="sidebar-menu">
      {items.map((item) => (
        <SidebarMenuNode key={item.label} item={item} activeCategoryId={activeCategoryId} />
      ))}
    </ul>
  )
}
