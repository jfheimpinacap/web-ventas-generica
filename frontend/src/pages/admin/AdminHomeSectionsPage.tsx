import { useEffect, useMemo, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import {
  createHomeSectionItem,
  deleteHomeSectionItem,
  getAdminHomeSectionItems,
  getAdminProducts,
  updateHomeSectionItem,
} from '../../services/adminApi'
import type { HomeSection, HomeSectionItem, ProductListItem } from '../../types/catalog'

const SECTION_CONFIG: Array<{ key: HomeSection; title: string; limit: number }> = [
  { key: 'machinery_promotions', title: 'Promociones en maquinarias', limit: 12 },
  { key: 'spare_parts_offers', title: 'Oferta en repuestos', limit: 6 },
  { key: 'repair_services', title: 'Servicios de reparación', limit: 12 },
]

const DEFAULT_SECTION_BY_TYPE: Partial<Record<ProductListItem['product_type'], HomeSection>> = {
  machinery: 'machinery_promotions',
  spare_part: 'spare_parts_offers',
  service: 'repair_services',
}

export function AdminHomeSectionsPage() {
  const [items, setItems] = useState<HomeSectionItem[]>([])
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      const [homeItems, catalogProducts] = await Promise.all([getAdminHomeSectionItems(), getAdminProducts()])
      setItems(homeItems)
      setProducts(catalogProducts)
      if (catalogProducts.length > 0) {
        setSelectedProductId((current) => current ?? catalogProducts[0].id)
      }
    } catch {
      setError('No se pudo cargar la configuración de Home.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const grouped = useMemo(() => {
    return SECTION_CONFIG.reduce(
      (acc, section) => {
        acc[section.key] = items.filter((item) => item.section === section.key).sort((a, b) => a.position - b.position)
        return acc
      },
      {
        machinery_promotions: [] as HomeSectionItem[],
        spare_parts_offers: [] as HomeSectionItem[],
        repair_services: [] as HomeSectionItem[],
      },
    )
  }, [items])

  const addProductToSection = async (section: HomeSection) => {
    if (!selectedProductId) return
    const sectionItems = grouped[section]
    const alreadyExists = sectionItems.some((item) => item.product.id === selectedProductId)
    if (alreadyExists) {
      window.alert('El producto ya está asignado en esa sección.')
      return
    }

    const position = sectionItems.length + 1
    try {
      await createHomeSectionItem({ section, product: selectedProductId, position, is_active: true })
      await load()
    } catch {
      window.alert('No fue posible agregar el producto. Revisa los límites de la sección.')
    }
  }

  const moveItem = async (section: HomeSection, item: HomeSectionItem, direction: -1 | 1) => {
    const sectionItems = grouped[section]
    const index = sectionItems.findIndex((entry) => entry.id === item.id)
    const target = sectionItems[index + direction]
    if (!target) return

    try {
      await Promise.all([
        updateHomeSectionItem(item.id, { position: target.position }),
        updateHomeSectionItem(target.id, { position: item.position }),
      ])
      await load()
    } catch {
      window.alert('No fue posible reordenar el bloque.')
    }
  }

  const toggleActive = async (item: HomeSectionItem) => {
    try {
      await updateHomeSectionItem(item.id, { is_active: !item.is_active })
      await load()
    } catch {
      window.alert('No fue posible actualizar el estado del bloque.')
    }
  }

  const removeItem = async (item: HomeSectionItem) => {
    if (!window.confirm(`¿Quitar "${item.product.name}" de la Home?`)) return
    await deleteHomeSectionItem(item.id)
    await load()
  }

  const selectedProduct = products.find((product) => product.id === selectedProductId)
  const suggestedSection = selectedProduct ? DEFAULT_SECTION_BY_TYPE[selectedProduct.product_type] : undefined

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Secciones Home</h1>
      </div>

      <div className="home-sections-toolbar">
        <select value={selectedProductId ?? ''} onChange={(event) => setSelectedProductId(Number(event.target.value))}>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </select>
        <span className="ui-note">Sugerido: {suggestedSection ?? '-'}</span>
      </div>

      {loading ? <p className="ui-note">Cargando configuración...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && !error ? (
        <div className="home-sections-grid">
          {SECTION_CONFIG.map((section) => {
            const sectionItems = grouped[section.key]
            return (
              <section className="home-section-card" key={section.key}>
                <div className="home-section-card__header">
                  <h2>{section.title}</h2>
                  <p>
                    {sectionItems.length} / {section.limit}
                  </p>
                </div>
                <button className="btn btn--accent" type="button" onClick={() => void addProductToSection(section.key)}>
                  Agregar producto
                </button>

                {sectionItems.length === 0 ? <p className="ui-note">Sin productos asignados.</p> : null}

                {sectionItems.map((item, index) => (
                  <article className="home-section-item" key={item.id}>
                    <div>
                      <strong>#{item.position}</strong> {item.product.name}
                    </div>
                    <div className="home-section-item__actions">
                      <button type="button" className="table-action table-action--button" onClick={() => void moveItem(section.key, item, -1)} disabled={index === 0}>
                        ↑
                      </button>
                      <button
                        type="button"
                        className="table-action table-action--button"
                        onClick={() => void moveItem(section.key, item, 1)}
                        disabled={index === sectionItems.length - 1}
                      >
                        ↓
                      </button>
                      <button type="button" className="table-action table-action--button" onClick={() => void toggleActive(item)}>
                        {item.is_active ? 'Desactivar' : 'Activar'}
                      </button>
                      <button type="button" className="table-action table-action--button" onClick={() => void removeItem(item)}>
                        Quitar
                      </button>
                    </div>
                  </article>
                ))}
              </section>
            )
          })}
        </div>
      ) : null}
    </AdminLayout>
  )
}
