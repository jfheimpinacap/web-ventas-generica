import { useMemo, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { useBrands } from '../../hooks/useBrands'
import { useCategories } from '../../hooks/useCategories'
import { sidebarMenu } from '../../data/sidebarMenu'
import { buildSidebarMenuFromCategories } from '../../utils/formatters'
import { SidebarMenu } from './SidebarMenu'

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
  disabled?: boolean
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

  const isCatalogPage = ['/catalogo', '/maquinaria-nueva', '/maquinaria-usada', '/repuestos', '/servicios'].includes(location.pathname)

  const menuItems = useMemo(() => {
    if (categories.length === 0 || error) return sidebarMenu
    return buildSidebarMenuFromCategories(categories)
  }, [categories, error])

  const activeCategories = useMemo(
    () => categories
      .filter((category) => category.is_active !== false)
      .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)),
    [categories],
  )
  const rootCategoryOptions = useMemo(
    () => activeCategories.filter((category) => category.parent === null),
    [activeCategories],
  )
  const explicitSelectedCategory = useMemo(() => {
    const categoryId = Number(searchParams.get('category'))
    return categoryId ? activeCategories.find((category) => category.id === categoryId) ?? null : null
  }, [activeCategories, searchParams])
  const selectedRootCategory = useMemo(() => {
    if (!explicitSelectedCategory) return null
    if (explicitSelectedCategory.parent === null) return explicitSelectedCategory
    return rootCategoryOptions.find((category) => category.id === explicitSelectedCategory.parent) ?? null
  }, [explicitSelectedCategory, rootCategoryOptions])
  const legacyRootCategory = useMemo(() => {
    if (searchParams.has('category')) return null
    const productType = searchParams.get('product_type')
    if (!productType) return null
    return rootCategoryOptions.find((category) => category.product_type === productType) ?? null
  }, [rootCategoryOptions, searchParams])
  const effectiveRootCategory = selectedRootCategory ?? legacyRootCategory
  const selectedSubcategory = explicitSelectedCategory?.parent === effectiveRootCategory?.id ? explicitSelectedCategory : null
  const subcategoryOptions = useMemo(
    () => effectiveRootCategory
      ? activeCategories.filter((category) => category.parent === effectiveRootCategory.id)
      : [],
    [activeCategories, effectiveRootCategory],
  )
  const activeBrands = useMemo(() => brands.filter((brand) => brand.is_active !== false), [brands])

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (key === 'category') next.delete('product_type')
    if (!value) {
      next.delete(key)
    } else {
      next.set(key, value)
    }
    setSearchParams(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const updateSubcategory = (value: string) => {
    updateFilter('category', value || (effectiveRootCategory ? String(effectiveRootCategory.id) : ''))
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
      value: effectiveRootCategory ? String(effectiveRootCategory.id) : '',
      options: [{ value: '', label: 'Todas las categorías' }, ...rootCategoryOptions.map((category) => ({ value: String(category.id), label: category.name }))],
    },
    {
      key: 'subcategory',
      label: 'Subcategoría',
      value: selectedSubcategory ? String(selectedSubcategory.id) : '',
      options: [{ value: '', label: effectiveRootCategory ? 'Todas las subcategorías' : 'Selecciona una categoría' }, ...subcategoryOptions.map((category) => ({ value: String(category.id), label: category.name }))],
      disabled: !effectiveRootCategory,
    },
    {
      key: 'brand',
      label: 'Marca',
      value: searchParams.get('brand') ?? '',
      options: [{ value: '', label: 'Todas' }, ...activeBrands.map((brand) => ({ value: String(brand.id), label: brand.name }))],
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
  ], [activeBrands, effectiveRootCategory, rootCategoryOptions, searchParams, selectedSubcategory, subcategoryOptions])

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}>
      <button className="sidebar__mobile-toggle" type="button" onClick={() => setIsOpen(true)} aria-expanded={isOpen} aria-controls="sidebar-panel">
        Filtro
      </button>

      {isOpen ? <button className="sidebar__mobile-backdrop" type="button" aria-label="Cerrar panel de filtros" onClick={() => setIsOpen(false)} /> : null}

      <div className="sidebar__panel" id="sidebar-panel">
        <div className="sidebar__panel-header">
          <h3>{isCatalogPage ? 'Filtros' : 'Categorías'}</h3>
          <button type="button" className="sidebar__panel-close" onClick={() => setIsOpen(false)} aria-label="Cerrar panel de filtros">
            ✕
          </button>
        </div>

        {isCatalogPage ? (
          <>
            <div className="sidebar-filters sidebar-filters--desktop">
              <select aria-label="Categoría" value={effectiveRootCategory?.id ?? ''} onChange={(event) => updateFilter('category', event.target.value)}>
                <option value="">Todas las categorías</option>
                {rootCategoryOptions.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>

              <select aria-label="Subcategoría" value={selectedSubcategory?.id ?? ''} disabled={!effectiveRootCategory} onChange={(event) => updateSubcategory(event.target.value)}>
                <option value="">{effectiveRootCategory ? 'Todas las subcategorías' : 'Selecciona una categoría'}</option>
                {subcategoryOptions.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>

              <select value={searchParams.get('brand') ?? ''} onChange={(event) => updateFilter('brand', event.target.value)}>
                <option value="">Marca</option>
                {activeBrands.map((brand) => (
                  <option key={brand.id} value={brand.id}>
                    {brand.name}
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

            <div className="sidebar-filters-mobile" role="list" aria-label="Filtros móviles de productos">
              {mobileFilterSections.map((section) => {
                const isExpanded = openMobileFilterKey === section.key
                return (
                  <section className="sidebar-filters-mobile__item" key={section.key}>
                    <button type="button" className="sidebar-filters-mobile__trigger" aria-expanded={isExpanded} disabled={section.disabled} onClick={() => setOpenMobileFilterKey(isExpanded ? null : section.key)}>
                      <span>{section.label}</span>
                      <span>{isExpanded ? '−' : '+'}</span>
                    </button>
                    {isExpanded ? (
                      <div className="sidebar-filters-mobile__options" role="list">
                        {section.options.map((option) => (
                          <button key={`${section.key}-${option.value || 'all'}`} type="button" className={`sidebar-filters-mobile__option ${section.value === option.value ? 'is-active' : ''}`.trim()} onClick={() => section.key === 'subcategory' ? updateSubcategory(option.value) : updateFilter(section.key, option.value)}>
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

        {!isCatalogPage ? (
          <div className="sidebar-categories-desktop">
            {error ? <p className="ui-note">Mostrando categorías de respaldo.</p> : null}
            <SidebarMenu items={menuItems} />
          </div>
        ) : null}
      </div>
    </aside>
  )
}
