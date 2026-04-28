import { useMemo, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { useBrands } from '../../hooks/useBrands'
import { useCategories } from '../../hooks/useCategories'
import { sidebarMenu } from '../../data/sidebarMenu'
import { buildSidebarMenuFromCategories } from '../../utils/formatters'
import { SidebarMenu } from './SidebarMenu'

const PRODUCT_TYPE_OPTIONS = [
  { value: 'machinery', label: 'Maquinaria' },
  { value: 'spare_part', label: 'Repuestos' },
  { value: 'service', label: 'Servicios' },
  { value: 'other', label: 'Otros' },
]

const CONDITION_OPTIONS = [
  { value: 'new', label: 'Nuevo' },
  { value: 'used', label: 'Usado' },
  { value: 'refurbished', label: 'Reacondicionado' },
  { value: 'not_applicable', label: 'No aplica' },
]

const STOCK_OPTIONS = [
  { value: 'available', label: 'Disponible' },
  { value: 'on_request', label: 'A pedido' },
  { value: 'reserved', label: 'Reservado' },
  { value: 'sold', label: 'Vendido' },
]

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(false)
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { categories, error } = useCategories()
  const { brands } = useBrands()

  const isCatalogPage = location.pathname.startsWith('/catalogo')

  const menuItems = useMemo(() => {
    if (categories.length === 0 || error) return sidebarMenu
    return buildSidebarMenuFromCategories(categories)
  }, [categories, error])

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value) {
      next.delete(key)
    } else {
      next.set(key, value)
    }
    setSearchParams(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
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
        {isCatalogPage ? (
          <div className="sidebar-filters">
            <h3>Filtros</h3>
            <select value={searchParams.get('category') ?? ''} onChange={(event) => updateFilter('category', event.target.value)}>
              <option value="">Categoría / subcategoría</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>

            <select value={searchParams.get('brand') ?? ''} onChange={(event) => updateFilter('brand', event.target.value)}>
              <option value="">Marca</option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>

            <select value={searchParams.get('product_type') ?? ''} onChange={(event) => updateFilter('product_type', event.target.value)}>
              <option value="">Tipo</option>
              {PRODUCT_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <select value={searchParams.get('condition') ?? ''} onChange={(event) => updateFilter('condition', event.target.value)}>
              <option value="">Condición</option>
              {CONDITION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <select value={searchParams.get('stock_status') ?? ''} onChange={(event) => updateFilter('stock_status', event.target.value)}>
              <option value="">Stock</option>
              {STOCK_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {error ? <p className="ui-note">Mostrando categorías de respaldo.</p> : null}
        <SidebarMenu items={menuItems} />
      </div>
    </aside>
  )
}
