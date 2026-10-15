import { useId } from 'react'
import { Link, useLocation } from 'react-router-dom'

import type { SidebarMenuItem } from '../../types/catalog'
import { sidebarCategoryHref, sidebarCategoryId, sidebarMenuKey } from '../../utils/sidebarAccordion'

interface SidebarMenuProps {
  items: SidebarMenuItem[]
  expandedPath: string[]
  onToggle: (path: string[]) => void
}

interface SidebarMenuNodeProps {
  item: SidebarMenuItem
  ancestors: string[]
  activeCategoryId: string | null
  expandedPath: string[]
  onToggle: (path: string[]) => void
  pathname: string
  search: string
}

function SidebarMenuNode({ item, ancestors, activeCategoryId, expandedPath, onToggle, pathname, search }: SidebarMenuNodeProps) {
  const panelId = useId()
  const path = [...ancestors, sidebarMenuKey(item)]
  const hasChildren = Boolean(item.children?.length)
  const isOpen = path.every((key, index) => expandedPath[index] === key)
  const categoryId = sidebarCategoryId(item)
  const isActive = Boolean(categoryId && categoryId === activeCategoryId)
  const href = sidebarCategoryHref(item, pathname, search)
  const handleNavigate = () => window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })

  return (
    <li>
      <div className="sidebar-menu__group">
        <span className="sidebar-menu__group-label">
          {href ? (
            <Link
              to={href}
              className={`sidebar-menu__link${ancestors.length === 0 ? ' sidebar-menu__link--parent' : ''}${isActive ? ' sidebar-menu__link--active' : ''}`}
              aria-current={isActive ? 'page' : undefined}
              onClick={handleNavigate}
            >
              {item.label}
            </Link>
          ) : (
            <span className={`sidebar-menu__label${ancestors.length === 0 ? ' sidebar-menu__label--parent' : ''}`}>{item.label}</span>
          )}
        </span>
        {hasChildren ? (
          <button
            className="sidebar-menu__toggle"
            onClick={() => onToggle(path)}
            type="button"
            aria-expanded={isOpen}
            aria-controls={panelId}
            aria-label={`${isOpen ? 'Contraer' : 'Expandir'} subcategorías de ${item.label}`}
          >
            <span className="sidebar-chevron" aria-hidden="true" />
          </button>
        ) : null}
      </div>
      {hasChildren ? (
        <ul id={panelId} className="sidebar-menu sidebar-menu--nested" hidden={!isOpen}>
          {item.children?.map((child) => (
            <SidebarMenuNode key={sidebarMenuKey(child)} item={child} ancestors={path} activeCategoryId={activeCategoryId} expandedPath={expandedPath} onToggle={onToggle} pathname={pathname} search={search} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export function SidebarMenu({ items, expandedPath, onToggle }: SidebarMenuProps) {
  const location = useLocation()
  const activeCategoryId = new URLSearchParams(location.search).get('category')

  return (
    <ul className="sidebar-menu">
      {items.map((item) => (
        <SidebarMenuNode key={sidebarMenuKey(item)} item={item} ancestors={[]} activeCategoryId={activeCategoryId} expandedPath={expandedPath} onToggle={onToggle} pathname={location.pathname} search={location.search} />
      ))}
    </ul>
  )
}
