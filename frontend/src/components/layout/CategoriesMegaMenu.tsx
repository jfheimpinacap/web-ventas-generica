import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import type { Category } from '../../types/catalog'

interface CategoriesMegaMenuProps {
  isOpen: boolean
  categories: Category[]
  activeCategoryId?: number | null
  onClose: () => void
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
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(activeCategoryId)

  const roots = useMemo(
    () => categories.filter((category) => category.parent === null).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)),
    [categories],
  )

  const childrenByParent = useMemo(() => {
    const map = new Map<number, Category[]>()
    categories
      .filter((category) => category.parent !== null)
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
  }, [activeCategoryId, isOpen, roots])

  if (!isOpen) return null

  const selectedCategory = roots.find((category) => category.id === selectedCategoryId) ?? roots[0] ?? null
  const subcategories = selectedCategory ? childrenByParent.get(selectedCategory.id) ?? [] : []
  const columns = chunkByCount(subcategories, subcategories.length > 18 ? 3 : subcategories.length > 8 ? 2 : 1)

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
                  to={`/catalogo?category=${category.id}`}
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
                        <Link to={`/catalogo?category=${subcategory.id}`} onClick={onClose}>
                          {subcategory.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ))}
              </div>
            ) : (
              <p className="categories-modal__empty">No hay subcategorías para esta categoría.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
