import { useId } from 'react'

import type { SidebarMenuItem } from '../../types/catalog'
import type { FacetOption } from '../../utils/catalogFilters'
import { sidebarCategoryId, sidebarMenuKey } from '../../utils/sidebarAccordion'
import { Collapsible } from './Collapsible'

interface SidebarMenuProps {
  items: SidebarMenuItem[]
  expandedPath: string[]
  onToggle: (path: string[]) => void
  selected: string[]
  options: FacetOption[]
  countsReady: boolean
  onSelect: (value: string) => void
}

function SidebarMenuNode({ item, ancestors, ...props }: Omit<SidebarMenuProps, 'items'> & { item: SidebarMenuItem; ancestors: string[] }) {
  const panelId = useId()
  const inputId = useId()
  const path = [...ancestors, sidebarMenuKey(item)]
  const hasChildren = Boolean(item.children?.length)
  const isOpen = path.every((key, index) => props.expandedPath[index] === key)
  const categoryId = sidebarCategoryId(item)
  const isActive = Boolean(categoryId && props.selected.includes(categoryId))
  const option = props.options.find((candidate) => candidate.value === categoryId)

  return <li>
    <div className="sidebar-menu__group">
      <label htmlFor={inputId} className={`catalog-filter-option${isActive ? ' is-active' : ''}`}>
        <input id={inputId} type="checkbox" checked={isActive} disabled={!categoryId} onChange={() => categoryId && props.onSelect(categoryId)} />
        <span>{item.label}</span>
        <span className="catalog-filter-option__count" aria-label={props.countsReady ? `${option?.count ?? 0} productos` : 'Cantidad pendiente'}>({props.countsReady ? option?.count ?? 0 : '…'})</span>
      </label>
      {hasChildren ? <button className="sidebar-menu__toggle" onClick={() => props.onToggle(path)} type="button" aria-expanded={isOpen} aria-controls={panelId} aria-label={`${isOpen ? 'Contraer' : 'Expandir'} subcategorías de ${item.label}`}>
        <span className="sidebar-chevron" aria-hidden="true" />
      </button> : null}
    </div>
    {hasChildren ? <Collapsible id={panelId} expanded={isOpen}>
      <ul className="sidebar-menu sidebar-menu--nested">
        {item.children?.map((child) => <SidebarMenuNode key={sidebarMenuKey(child)} item={child} ancestors={path} {...props} />)}
      </ul>
    </Collapsible> : null}
  </li>
}

export function SidebarMenu({ items, ...props }: SidebarMenuProps) {
  return <ul className="sidebar-menu">{items.map((item) => <SidebarMenuNode key={sidebarMenuKey(item)} item={item} ancestors={[]} {...props} />)}</ul>
}
