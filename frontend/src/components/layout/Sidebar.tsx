import { useMemo, useState } from 'react'

import { useCategories } from '../../hooks/useCategories'
import { sidebarMenu } from '../../data/sidebarMenu'
import { buildSidebarMenuFromCategories } from '../../utils/formatters'
import { SearchBox } from '../common/SearchBox'
import { SidebarMenu } from './SidebarMenu'

interface SidebarProps {
  onSearch?: (term: string) => void
}

export function Sidebar({ onSearch }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { categories, error } = useCategories()

  const menuItems = useMemo(() => {
    if (categories.length === 0 || error) return sidebarMenu
    return buildSidebarMenuFromCategories(categories)
  }, [categories, error])

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}>
      <button className="sidebar__mobile-toggle" type="button" onClick={() => setIsOpen((prev) => !prev)}>
        {isOpen ? 'Cerrar menú' : 'Explorar categorías'}
      </button>

      <div className="sidebar__panel">
        <SearchBox onSearch={onSearch} />
        {error ? <p className="ui-note">Mostrando categorías de respaldo.</p> : null}
        <SidebarMenu items={menuItems} />
      </div>
    </aside>
  )
}
