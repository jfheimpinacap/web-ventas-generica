import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import type { Category } from '../../types/catalog'
import { publicCategories } from '../../utils/publicCategories'

interface CategoriesMegaMenuProps {
  isOpen: boolean
  categories: Category[]
  activeCategoryId?: number | null
  onClose: () => void
}

function categoryHref(category: Category) {
  return `/catalogo?category=${category.id}`
}

function Descendants({ parentId, childrenByParent, onClose, level = 0 }: {
  parentId: number
  childrenByParent: Map<number, Category[]>
  onClose: () => void
  level?: number
}) {
  const children = childrenByParent.get(parentId) ?? []
  if (!children.length) return null
  return (
    <ul className="categories-modal__branch" data-level={level}>
      {children.map((category) => (
        <li key={category.id}>
          <Link to={categoryHref(category)} onClick={onClose}>{category.name}</Link>
          <Descendants parentId={category.id} childrenByParent={childrenByParent} onClose={onClose} level={level + 1} />
        </li>
      ))}
    </ul>
  )
}

export function CategoriesMegaMenu({ isOpen, categories, activeCategoryId = null, onClose }: CategoriesMegaMenuProps) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(activeCategoryId)
  const [expandedMobileCategoryIds, setExpandedMobileCategoryIds] = useState<number[]>([])
  const visibleCategories = useMemo(
    () => publicCategories(categories).filter((category) => category.is_active !== false),
    [categories],
  )
  const roots = useMemo(
    () => visibleCategories.filter((category) => category.parent === null)
      .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)),
    [visibleCategories],
  )
  const childrenByParent = useMemo(() => {
    const map = new Map<number, Category[]>()
    visibleCategories.forEach((category) => {
      if (category.parent === null) return
      map.set(category.parent, [...(map.get(category.parent) ?? []), category])
    })
    map.forEach((items) => items.sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)))
    return map
  }, [visibleCategories])

  useEffect(() => {
    if (!isOpen) return
    const next = roots.some((root) => root.id === activeCategoryId) ? activeCategoryId : roots[0]?.id ?? null
    setSelectedCategoryId(next)
    setExpandedMobileCategoryIds(next ? [next] : [])
  }, [activeCategoryId, isOpen, roots])

  if (!isOpen) return null
  const selected = roots.find((root) => root.id === selectedCategoryId) ?? roots[0] ?? null
  const toggleMobile = (id: number) => setExpandedMobileCategoryIds((current) =>
    current.includes(id) ? current.filter((item) => item !== id) : [...current, id])

  return (
    <div className="categories-modal" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section id="categories-mega-menu" className="categories-modal__panel" aria-label="Navegación de categorías">
        <button type="button" className="categories-modal__close" onClick={onClose} aria-label="Cerrar categorías">✕</button>
        {roots.length ? (
          <>
            <div className="categories-modal__content">
              <nav className="categories-modal__roots" aria-label="Categorías principales">
                {roots.map((category) => {
                  const hasChildren = Boolean(childrenByParent.get(category.id)?.length)
                  const isSelected = selected?.id === category.id
                  return (
                    <div className={`categories-modal__root-row${isSelected ? ' is-active' : ''}`} key={category.id} onMouseEnter={() => setSelectedCategoryId(category.id)}>
                      <Link to={categoryHref(category)} onClick={onClose}>{category.name}</Link>
                      {hasChildren ? <button type="button" aria-expanded={isSelected} aria-controls={`mega-children-${category.id}`} aria-label={`Mostrar subcategorías de ${category.name}`} onClick={() => setSelectedCategoryId(category.id)}>›</button> : null}
                    </div>
                  )
                })}
              </nav>
              <div className="categories-modal__subs" id={selected ? `mega-children-${selected.id}` : undefined}>
                {selected ? <><h2>{selected.name}</h2><Descendants parentId={selected.id} childrenByParent={childrenByParent} onClose={onClose} /></> : null}
              </div>
            </div>
            <nav className="categories-modal__mobile-accordion" aria-label="Categorías principales">
              {roots.map((category) => {
                const hasChildren = Boolean(childrenByParent.get(category.id)?.length)
                const expanded = expandedMobileCategoryIds.includes(category.id)
                return <section className="categories-modal__mobile-item" key={category.id}>
                  <div className="categories-modal__mobile-header">
                    <Link to={categoryHref(category)} onClick={onClose}>{category.name}</Link>
                    {hasChildren ? <button type="button" aria-expanded={expanded} aria-controls={`mobile-subs-${category.id}`} aria-label={`${expanded ? 'Contraer' : 'Expandir'} subcategorías de ${category.name}`} onClick={() => toggleMobile(category.id)}>{expanded ? '−' : '+'}</button> : null}
                  </div>
                  {hasChildren && expanded ? <div id={`mobile-subs-${category.id}`}><Descendants parentId={category.id} childrenByParent={childrenByParent} onClose={onClose} /></div> : null}
                </section>
              })}
            </nav>
          </>
        ) : <p className="categories-modal__empty">No hay categorías disponibles.</p>}
      </section>
    </div>
  )
}
