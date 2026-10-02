import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { useBrands } from '../../hooks/useBrands'
import { useCategories } from '../../hooks/useCategories'
import { buildSidebarMenuFromCategories } from '../../utils/formatters'
import { publicCategories } from '../../utils/publicCategories'
import { SidebarMenu } from './SidebarMenu'

const CONDITION_OPTIONS = [
  { value: 'new', label: 'Nuevo' },
  { value: 'used', label: 'Usado' },
  { value: 'refurbished', label: 'Reacondicionado' },
]
const STOCK_OPTIONS = [
  { value: 'available', label: 'Disponible' },
  { value: 'on_request', label: 'A pedido' },
]

type AccordionProps = {
  sectionKey: string
  label: string
  openKeys: Set<string>
  onToggle: (key: string) => void
  children: ReactNode
}

function Accordion({ sectionKey, label, openKeys, onToggle, children }: AccordionProps) {
  const expanded = openKeys.has(sectionKey)
  const panelId = `catalog-filter-${sectionKey}`
  return <section className="catalog-accordion">
    <button type="button" className="catalog-accordion__trigger" aria-expanded={expanded} aria-controls={panelId} onClick={() => onToggle(sectionKey)}>
      <span>{label}</span><span aria-hidden="true">{expanded ? '−' : '+'}</span>
    </button>
    {expanded ? <div className="catalog-accordion__panel" id={panelId}>{children}</div> : null}
  </section>
}

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(false)
  const [openKeys, setOpenKeys] = useState(() => new Set(['categories']))
  const toggleRef = useRef<HTMLButtonElement>(null)
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { categories, loading: categoriesLoading, error } = useCategories()
  const { brands } = useBrands()
  const activeCategories = useMemo(() => publicCategories(categories).filter((item) => item.is_active !== false), [categories])
  const menuItems = useMemo(() => buildSidebarMenuFromCategories(activeCategories), [activeCategories])
  const activeBrands = useMemo(() => brands.filter((brand) => brand.is_active !== false), [brands])
  const selectedCategory = searchParams.get('category')
  const fixedCondition = location.pathname === '/maquinaria-nueva' ? 'new' : location.pathname === '/maquinaria-usada' ? 'used' : ''
  const fixedProductType = location.pathname === '/repuestos' ? 'spare_part' : location.pathname === '/servicios' ? 'service' : location.pathname.startsWith('/maquinaria-') ? 'machinery' : ''

  useEffect(() => {
    setOpenKeys((current) => {
      const next = new Set(current)
      if (selectedCategory) next.add('categories')
      if (searchParams.get('brand')) next.add('brand')
      if (searchParams.get('condition') || fixedCondition) next.add('condition')
      if (searchParams.get('stock_status')) next.add('stock')
      return next
    })
  }, [fixedCondition, searchParams, selectedCategory])

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
        requestAnimationFrame(() => toggleRef.current?.focus())
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen])

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (key === 'category') next.delete('product_type')
    value ? next.set(key, value) : next.delete(key)
    setSearchParams(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const clearFilters = () => {
    const next = new URLSearchParams(searchParams)
    ;['category', 'brand', 'product_type', 'condition', 'stock_status'].forEach((key) => next.delete(key))
    setSearchParams(next)
  }
  const toggleAccordion = (key: string) => setOpenKeys((current) => {
    const next = new Set(current)
    next.has(key) ? next.delete(key) : next.add(key)
    return next
  })
  const option = (key: string, value: string, label: string, selectedValue: string) => (
    <button type="button" className={`catalog-filter-option${selectedValue === value ? ' is-active' : ''}`} aria-pressed={selectedValue === value} onClick={() => updateFilter(key, value)}>{label}</button>
  )

  return <aside className={`sidebar${isOpen ? ' sidebar--open' : ''}`} aria-label="Navegación y filtros del catálogo">
    <button ref={toggleRef} className="sidebar__mobile-toggle" type="button" onClick={() => setIsOpen((value) => !value)} aria-expanded={isOpen} aria-controls="sidebar-panel">Filtros y categorías</button>
    {isOpen ? <button className="sidebar__mobile-backdrop" type="button" aria-label="Cerrar filtros" onClick={() => setIsOpen(false)} /> : null}
    <div className="sidebar__panel" id="sidebar-panel">
      <div className="sidebar__panel-header"><h2>Catálogo</h2><button type="button" className="sidebar__panel-close" onClick={() => { setIsOpen(false); toggleRef.current?.focus() }} aria-label="Cerrar filtros">✕</button></div>
      <Accordion sectionKey="categories" label="Categorías" openKeys={openKeys} onToggle={toggleAccordion}>
        {categoriesLoading ? <p className="ui-note">Cargando categorías...</p> : null}
        {error ? <p className="ui-note ui-note--error">No fue posible cargar las categorías.</p> : null}
        {!categoriesLoading && !error && !menuItems.length ? <p className="ui-note">No hay categorías disponibles.</p> : null}
        {menuItems.length ? <SidebarMenu items={menuItems} /> : null}
      </Accordion>
      <Accordion sectionKey="brand" label="Marca" openKeys={openKeys} onToggle={toggleAccordion}>
        <div className="catalog-filter-options">{option('brand', '', 'Todas las marcas', searchParams.get('brand') ?? '')}{activeBrands.map((brand) => option('brand', String(brand.id), brand.name, searchParams.get('brand') ?? ''))}</div>
      </Accordion>
      <Accordion sectionKey="condition" label={`Condición${fixedCondition ? ' (fija)' : ''}`} openKeys={openKeys} onToggle={toggleAccordion}>
        <div className="catalog-filter-options">{fixedCondition
          ? <p className="catalog-filter-fixed">{fixedCondition === 'new' ? 'Nuevo' : 'Usado'}</p>
          : <>{option('condition', '', 'Todas', searchParams.get('condition') ?? '')}{CONDITION_OPTIONS.map((item) => option('condition', item.value, item.label, searchParams.get('condition') ?? ''))}</>}
        </div>
      </Accordion>
      <Accordion sectionKey="stock" label="Stock" openKeys={openKeys} onToggle={toggleAccordion}>
        <div className="catalog-filter-options">{option('stock_status', '', 'Todos', searchParams.get('stock_status') ?? '')}{STOCK_OPTIONS.map((item) => option('stock_status', item.value, item.label, searchParams.get('stock_status') ?? ''))}</div>
      </Accordion>
      {fixedProductType ? <p className="catalog-filter-route">Vista: {fixedProductType === 'machinery' ? 'Maquinaria' : fixedProductType === 'spare_part' ? 'Repuestos' : 'Servicios'}</p> : null}
      <button type="button" className="btn btn--ghost sidebar-filters__clear" onClick={clearFilters}>Limpiar filtros</button>
    </div>
  </aside>
}
