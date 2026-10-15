import { type ReactNode, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { Category } from '../../types/catalog'
import { clearCatalogFilters, toggleCatalogFacet, type CatalogContext, type CatalogSelections, type FacetKey, type FacetOption } from '../../utils/catalogFilters'
import { buildSidebarMenuFromCategories } from '../../utils/formatters'
import { createSidebarAccordionState, sidebarAccordionReducer, sidebarCategoryId } from '../../utils/sidebarAccordion'
import { Collapsible } from './Collapsible'
import { SidebarMenu } from './SidebarMenu'

export interface CatalogSidebarData {
  context: CatalogContext
  categories: Category[]
  selections: CatalogSelections
  facets: Record<FacetKey, FacetOption[]>
  loading: boolean
  error: string | null
}

function Accordion({ sectionKey, label, openSection, onToggle, children }: { sectionKey: string; label: string; openSection: string | null; onToggle: (key: string) => void; children: ReactNode }) {
  const expanded = openSection === sectionKey
  const panelId = `catalog-filter-${sectionKey}`
  return <section className="catalog-accordion">
    <button type="button" className="catalog-accordion__trigger" aria-expanded={expanded} aria-controls={panelId} onClick={() => onToggle(sectionKey)}>
      <span>{label}</span><span className="sidebar-chevron" aria-hidden="true" />
    </button>
    <Collapsible id={panelId} expanded={expanded}><div className="catalog-accordion__panel">{children}</div></Collapsible>
  </section>
}

export function Sidebar({ data }: { data: CatalogSidebarData }) {
  const { context, categories, selections, facets, loading, error } = data
  const [isOpen, setIsOpen] = useState(false)
  const [isDesktop, setIsDesktop] = useState(false)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [accordion, dispatchAccordion] = useReducer(sidebarAccordionReducer, selections.category[0] ?? null, createSidebarAccordionState)
  const countsReady = !loading && !error
  const menuItems = useMemo(() => {
    const roots = buildSidebarMenuFromCategories(categories)
    // The contextual title already names the root. Start at its children.
    const items = context.productType ? roots.flatMap((root) => root.children?.length ? root.children : [root]) : roots
    // Legacy commercial links may explicitly select a root. Keep it removable.
    const selectedRoots = roots.filter((root) => {
      const id = sidebarCategoryId(root)
      return id && selections.category.includes(id) && !items.includes(root)
    }).map((root) => ({ label: root.label, to: root.to }))
    return [...selectedRoots, ...items]
  }, [categories, context.productType, selections.category])

  useEffect(() => {
    if (!loading && !error) dispatchAccordion({ type: 'initializeCategories', items: menuItems, categoryId: selections.category[0] })
  }, [loading, error, menuItems, selections.category])

  useEffect(() => {
    const media = window.matchMedia('(min-width: 901px)')
    const update = () => setIsDesktop(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  const closePanel = () => { setIsOpen(false); toggleRef.current?.focus() }
  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setIsOpen(false); toggleRef.current?.focus() }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen])

  const updateFilter = (key: FacetKey, value: string) => setSearchParams(toggleCatalogFacet(searchParams, context, selections, key, value))
  const toggleAccordion = (key: string) => dispatchAccordion({ type: 'toggleSection', key })
  const options = (key: FacetKey) => <div className="catalog-filter-options">{facets[key].map((option) => {
    const selected = selections[key].includes(option.value)
    const inputId = `catalog-${key}-${encodeURIComponent(option.value)}`
    return <label key={option.value} htmlFor={inputId} className={`catalog-filter-option${selected ? ' is-active' : ''}`}>
      <input id={inputId} type="checkbox" checked={selected} onChange={() => updateFilter(key, option.value)} />
      <span>{option.label}</span>
      <span className="catalog-filter-option__count" aria-label={countsReady ? `${option.count} productos` : 'Cantidad pendiente'}>({countsReady ? option.count : '…'})</span>
    </label>
  })}{countsReady && !facets[key].length ? <p className="ui-note">Sin opciones en este contexto.</p> : null}</div>

  return <aside className={`sidebar${isOpen ? ' sidebar--open' : ''}`} aria-label={`Filtros de ${context.title}`}>
    <button ref={toggleRef} className="sidebar__mobile-toggle" type="button" onClick={() => setIsOpen((value) => !value)} aria-expanded={isOpen} aria-controls="sidebar-panel">Filtros y categorías</button>
    {isOpen ? <button className="sidebar__mobile-backdrop" type="button" aria-label="Cerrar filtros" onClick={closePanel} /> : null}
    <div className="sidebar__panel" id="sidebar-panel" {...{ inert: !isDesktop && !isOpen ? '' : undefined }}>
      <div className="sidebar__panel-header"><h2>{context.title}</h2><button type="button" className="sidebar__panel-close" onClick={closePanel} aria-label="Cerrar filtros">✕</button></div>
      <div role="status" aria-live="polite">
        {loading ? <p className="ui-note">Cargando filtros y cantidades…</p> : null}
        {error ? <p className="ui-note ui-note--error">{error} Cantidades no disponibles.</p> : null}
      </div>
      <Accordion sectionKey="categories" label={context.productType === 'machinery' ? 'Tipo de maquinaria' : 'Categorías'} openSection={accordion.openSection} onToggle={toggleAccordion}>
        {countsReady && !menuItems.length ? <p className="ui-note">No hay categorías disponibles.</p> : null}
        <SidebarMenu items={menuItems} expandedPath={accordion.categoryPath} onToggle={(path) => dispatchAccordion({ type: 'toggleCategory', path })} selected={selections.category} options={facets.category} countsReady={countsReady} onSelect={(value) => updateFilter('category', value)} />
      </Accordion>
      <Accordion sectionKey="brand" label="Marca" openSection={accordion.openSection} onToggle={toggleAccordion}>{options('brand')}</Accordion>
      {!context.fixedCondition ? <Accordion sectionKey="condition" label="Condición" openSection={accordion.openSection} onToggle={toggleAccordion}>{options('condition')}</Accordion> : null}
      <Accordion sectionKey="stock" label="Stock" openSection={accordion.openSection} onToggle={toggleAccordion}>{options('stock_status')}</Accordion>
      <button type="button" className="sidebar-filters__clear" onClick={() => setSearchParams(clearCatalogFilters(searchParams, context))}>Limpiar filtros</button>
    </div>
  </aside>
}
