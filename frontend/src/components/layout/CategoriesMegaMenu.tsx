import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import type { Category } from '../../types/catalog'

interface CategoriesMegaMenuProps {
  isOpen: boolean
  categories: Category[]
  activeCategoryId?: number | null
  onClose: () => void
}

type MenuCategory = {
  id: number | string
  name: string
  href: string
  order: number
  source: 'api' | 'fallback'
}

const FALLBACK_ROOTS: MenuCategory[] = [
  { id: 'machinery', name: 'Maquinaria', href: '/catalogo?product_type=machinery', order: 1, source: 'fallback' },
  { id: 'spare_part', name: 'Repuestos', href: '/catalogo?product_type=spare_part', order: 2, source: 'fallback' },
  { id: 'service', name: 'Servicios', href: '/catalogo?product_type=service', order: 3, source: 'fallback' },
]

function normalizeLabel(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
}

function categoryHref(category: Category) {
  return `/catalogo?category=${category.id}`
}

function chunkByCount<T>(items: T[], columns: number) {
  if (items.length === 0) return []
  const safeColumns = Math.max(1, columns)
  const chunkSize = Math.ceil(items.length / safeColumns)
  return Array.from({ length: safeColumns }, (_, columnIndex) =>
    items.slice(columnIndex * chunkSize, columnIndex * chunkSize + chunkSize),
  ).filter((column) => column.length > 0)
}

export function CategoriesMegaMenu({ isOpen, categories, activeCategoryId = null, onClose }: CategoriesMegaMenuProps) {
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | string | null>(activeCategoryId)
  const [expandedMobileCategoryIds, setExpandedMobileCategoryIds] = useState<Array<number | string>>([])

  const roots = useMemo<MenuCategory[]>(() => {
    const apiRoots = categories
      .filter((category) => category.parent === null && category.is_active !== false)
      .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name))
      .map((category) => ({
        id: category.id,
        name: category.name,
        href: categoryHref(category),
        order: category.order,
        source: 'api' as const,
      }))

    if (apiRoots.length === 0) return FALLBACK_ROOTS

    const existingLabels = new Set(apiRoots.map((category) => normalizeLabel(category.name)))
    const missingFallbacks = FALLBACK_ROOTS.filter((category) => !existingLabels.has(normalizeLabel(category.name)))

    return [...apiRoots, ...missingFallbacks].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name))
  }, [categories])

  const childrenByParent = useMemo(() => {
    const map = new Map<number, Category[]>()
    categories
      .filter((category) => category.parent !== null && category.is_active !== false)
      .forEach((category) => {
        const parentId = category.parent as number
        const existing = map.get(parentId) ?? []
        existing.push(category)
        map.set(parentId, existing)
      })

    map.forEach((items, key) => {
      map.set(
        key,
        [...items].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)),
      )
    })

    return map
  }, [categories])

  useEffect(() => {
    if (!isOpen) return

    const fallbackCategory = roots[0]?.id ?? null
    const nextCategoryId = activeCategoryId && roots.some((category) => category.id === activeCategoryId) ? activeCategoryId : fallbackCategory
    setSelectedCategoryId(nextCategoryId)
    setExpandedMobileCategoryIds(nextCategoryId ? [nextCategoryId] : [])
  }, [activeCategoryId, isOpen, roots])

  if (!isOpen) return null

  const selectedCategory = roots.find((category) => category.id === selectedCategoryId) ?? roots[0] ?? null
  const subcategories = typeof selectedCategory?.id === 'number' ? childrenByParent.get(selectedCategory.id) ?? [] : []
  const columns = chunkByCount(subcategories, subcategories.length > 18 ? 3 : subcategories.length > 8 ? 2 : 1)
  const toggleMobileCategory = (categoryId: number | string) => {
    setExpandedMobileCategoryIds((current) =>
      current.includes(categoryId) ? current.filter((id) => id !== categoryId) : [...current, categoryId],
    )
  }

  return (
    <div className="categories-modal" role="presentation" onClick={onClose}>
      <section
        id="categories-mega-menu" className="categories-modal__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Navegación de categorías"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="categories-modal__close" onClick={onClose} aria-label="Cerrar categorías">
          ✕
        </button>

        <div className="categories-modal__content">
          <nav className="categories-modal__roots" aria-label="Categorías principales">
            {roots.map((category) => {
              const isSelected = selectedCategory?.id === category.id
              return (
                <Link
                  key={category.id}
                  to={category.href}
                  className={`categories-modal__root-link ${isSelected ? 'categories-modal__root-link--active' : ''}`.trim()}
                  onMouseEnter={() => setSelectedCategoryId(category.id)}
                  onFocus={() => setSelectedCategoryId(category.id)}
                  onClick={onClose}
                >
                  <span>{category.name}</span>
                  <span aria-hidden="true">›</span>
                </Link>
              )
            })}
          </nav>

          <div className="categories-modal__subs" aria-live="polite">
            {columns.length > 0 ? (
              <div className="categories-modal__sub-grid">
                {columns.map((column, index) => (
                  <ul key={`${selectedCategory?.id ?? 'none'}-${index}`}>
                    {column.map((subcategory) => (
                      <li key={subcategory.id}>
                        <Link to={categoryHref(subcategory)} onClick={onClose}>
                          {subcategory.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ))}
              </div>
            ) : selectedCategory ? (
              <p className="ui-note">Sin subcategorías disponibles</p>
            ) : null}
          </div>
        </div>

        <nav className="categories-modal__mobile-accordion" aria-label="Categorías principales para móvil">
          {roots.map((category) => {
            const subcategoriesForCategory = typeof category.id === 'number' ? childrenByParent.get(category.id) ?? [] : []
            const isExpanded = expandedMobileCategoryIds.includes(category.id)

            return (
              <div className="categories-modal__mobile-item" key={`mobile-${category.id}`}>
                <div className="categories-modal__mobile-header">
                  <Link
                    to={category.href}
                    className="categories-modal__mobile-link"
                    onClick={onClose}
                  >
                    {category.name}
                  </Link>
                  {subcategoriesForCategory.length > 0 ? (
                    <button
                      type="button"
                      className="categories-modal__mobile-toggle"
                      aria-expanded={isExpanded}
                      aria-controls={`mobile-subs-${category.id}`}
                      onClick={() => toggleMobileCategory(category.id)}
                    >
                      <span aria-hidden="true">{isExpanded ? '▾' : '▸'}</span>
                    </button>
                  ) : null}
                </div>

                {subcategoriesForCategory.length > 0 ? (
                  <ul
                    id={`mobile-subs-${category.id}`}
                    className={`categories-modal__mobile-subs ${isExpanded ? 'is-expanded' : ''}`.trim()}
                    aria-hidden={!isExpanded}
                  >
                    {subcategoriesForCategory.map((subcategory) => (
                      <li key={subcategory.id}>
                        <Link to={categoryHref(subcategory)} onClick={onClose}>
                          {subcategory.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            )
          })}
        </nav>
      </section>
    </div>
  )
}
