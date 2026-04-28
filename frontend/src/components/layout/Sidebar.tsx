import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

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
  const navigate = useNavigate()
  const { categories, error } = useCategories()

  const menuItems = useMemo(() => {
    if (categories.length === 0 || error) return sidebarMenu
    return buildSidebarMenuFromCategories(categories)
  }, [categories, error])

  const handleSearch = (term: string) => {
    if (onSearch) {
      onSearch(term)
    } else {
      navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/catalogo')
    }
    setIsOpen(false)
  }

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}>
      <button
        className="sidebar__mobile-toggle"
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-controls="sidebar-panel"
      >
        {isOpen ? 'Cerrar categorías' : 'Explorar categorías'}
      </button>

      <div className="sidebar__panel" id="sidebar-panel">
        <div className="sidebar__heading">
          <h2>Buscador comercial</h2>
          <p>Encuentra maquinaria, repuestos y servicios por nombre o categoría.</p>
        </div>
        <SearchBox onSearch={handleSearch} />
        {error ? <p className="ui-note">Mostrando categorías de respaldo.</p> : null}
        <p className="sidebar__meta">Categorías visibles: {menuItems.length}</p>
        <SidebarMenu items={menuItems} />
      </div>
    </aside>
  )
}
