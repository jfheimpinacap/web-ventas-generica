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



type FilterOption = { value: string; label: string }
type MobileFilterSection = {
  key: string
  label: string
  value: string
  options: FilterOption[]
}

const STOCK_OPTIONS = [
  { value: 'available', label: 'Disponible' },
  { value: 'on_request', label: 'A pedido' },
  { value: 'reserved', label: 'Reservado' },
  { value: 'sold', label: 'Vendido' },
]

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(false)
  const [openMobileFilterKey, setOpenMobileFilterKey] = useState<string | null>(null)
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

  const clearFilters = () => {
    const next = new URLSearchParams(searchParams)
    ;['category', 'brand', 'product_type', 'condition', 'stock_status'].forEach((key) => next.delete(key))
    setSearchParams(next)
  }

  const mobileFilterSections = useMemo<MobileFilterSection[]>(() => [
    {
      key: 'category',
      label: 'Categoría',
      value: searchParams.get('category') ?? '',
      options: [{ value: '', label: 'Todas' }, ...categories.map((category) => ({ value: String(category.id), label: category.name }))],
    },
    {
      key: 'brand',
      label: 'Marca',
      value: searchParams.get('brand') ?? '',
      options: [{ value: '', label: 'Todas' }, ...brands.map((brand) => ({ value: String(brand.id), label: brand.name }))],
    },
    {
      key: 'product_type',
      label: 'Tipo',
      value: searchParams.get('product_type') ?? '',
      options: [{ value: '', label: 'Todos' }, ...PRODUCT_TYPE_OPTIONS],
    },
    {
      key: 'condition',
      label: 'Condición',
      value: searchParams.get('condition') ?? '',
      options: [{ value: '', label: 'Todos' }, ...CONDITION_OPTIONS],
    },
    {
      key: 'stock_status',
      label: 'Stock',
      value: searchParams.get('stock_status') ?? '',
      options: [{ value: '', label: 'Todos' }, ...STOCK_OPTIONS],
    },
  ], [brands, categories, searchParams])

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}>
      <button className="sidebar__mobile-toggle" type="button" onClick={() => setIsOpen(true)} aria-expanded={isOpen} aria-controls="sidebar-panel">
        Filtro
      </button>

      {isOpen ? <button className="sidebar__mobile-backdrop" type="button" aria-label="Cerrar panel de filtros" onClick={() => setIsOpen(false)} /> : null}

      <div className="sidebar__panel" id="sidebar-panel">
        <div className="sidebar__panel-header">
          <h3>Filtros y categorías</h3>
          <button type="button" className="sidebar__panel-close" onClick={() => setIsOpen(false)} aria-label="Cerrar panel de filtros">
            ✕
          </button>
        </div>

        {isCatalogPage ? (
          <>
            <div className="sidebar-filters sidebar-filters--desktop">
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

              <button type="button" className="btn btn--ghost sidebar-filters__clear" onClick={clearFilters}>
                Limpiar filtros
              </button>
            </div>

            <div className="sidebar-filters-mobile" role="list" aria-label="Filtros móviles del catálogo">
              {mobileFilterSections.map((section) => {
                const isExpanded = openMobileFilterKey === section.key
                return (
                  <section className="sidebar-filters-mobile__item" key={section.key}>
                    <button type="button" className="sidebar-filters-mobile__trigger" aria-expanded={isExpanded} onClick={() => setOpenMobileFilterKey(isExpanded ? null : section.key)}>
                      <span>{section.label}</span>
                      <span>{isExpanded ? '−' : '+'}</span>
                    </button>
                    {isExpanded ? (
                      <div className="sidebar-filters-mobile__options" role="list">
                        {section.options.map((option) => (
                          <button key={`${section.key}-${option.value || 'all'}`} type="button" className={`sidebar-filters-mobile__option ${section.value === option.value ? 'is-active' : ''}`.trim()} onClick={() => updateFilter(section.key, option.value)}>
                            {option.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </section>
                )
              })}
              <button type="button" className="btn btn--ghost sidebar-filters__clear" onClick={clearFilters}>Limpiar filtros</button>
            </div>
          </>
        ) : null}

        <div className="sidebar-categories-desktop">
          {error ? <p className="ui-note">Mostrando categorías de respaldo.</p> : null}
          <SidebarMenu items={menuItems} />
        </div>
      </div>
    </aside>
  )
}
