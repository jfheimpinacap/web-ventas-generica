import { useEffect, useMemo, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { createHomeSectionItem, deleteHomeSectionItem, getAdminHomeSectionItems, getProductsForHomeSection, updateHomeSectionItem } from '../../services/adminApi'
import { ApiError, resolveMediaUrl } from '../../services/api'
import type { HomeSection, HomeSectionItem, ProductListItem } from '../../types/catalog'
import { formatPrice, formatStockStatus } from '../../utils/formatters'

type SectionConfig = {
  key: HomeSection
  title: string
  limit: number
  description: string
  selectPlaceholder: string
  emptyProductsText: string
  previewLabel: string
}

type SectionState = Record<HomeSection, { loading: boolean; error: string | null; success: string | null }>

type ProductsBySection = Record<HomeSection, ProductListItem[]>
type SelectionBySection = Record<HomeSection, number | ''>

const SECTION_CONFIG: SectionConfig[] = [
  {
    key: 'machinery_promotions',
    title: 'Promociones en maquinarias',
    limit: 12,
    description: 'Maquinarias publicadas para destacar en el carrusel de la Home.',
    selectPlaceholder: 'Seleccionar maquinaria publicada...',
    emptyProductsText: 'No hay maquinarias publicadas disponibles.',
    previewLabel: 'Carrusel de productos',
  },
  {
    key: 'spare_parts_offers',
    title: 'Oferta en repuestos',
    limit: 6,
    description: 'Repuestos publicados ordenados en el mosaico de ofertas.',
    selectPlaceholder: 'Seleccionar repuesto publicado...',
    emptyProductsText: 'No hay repuestos publicados disponibles.',
    previewLabel: 'Mosaico de slots',
  },
  {
    key: 'repair_services',
    title: 'Servicios de reparación',
    limit: 12,
    description: 'Servicios publicados para mostrar capacidades de reparación.',
    selectPlaceholder: 'Seleccionar servicio publicado...',
    emptyProductsText: 'No hay servicios publicados disponibles.',
    previewLabel: 'Fila de servicios',
  },
]

const EMPTY_PRODUCTS_BY_SECTION: ProductsBySection = {
  machinery_promotions: [],
  spare_parts_offers: [],
  repair_services: [],
}

const EMPTY_SELECTIONS: SelectionBySection = {
  machinery_promotions: '',
  spare_parts_offers: '',
  repair_services: '',
}

const EMPTY_STATUS: SectionState = {
  machinery_promotions: { loading: false, error: null, success: null },
  spare_parts_offers: { loading: false, error: null, success: null },
  repair_services: { loading: false, error: null, success: null },
}

const PREVIEW_PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'

function sortByPosition(items: HomeSectionItem[]) {
  return [...items].sort((a, b) => a.position - b.position || a.id - b.id)
}

function buildSlots(sectionItems: HomeSectionItem[], limit: number) {
  const slots: Array<HomeSectionItem | null> = Array.from({ length: limit }, () => null)

  for (const item of sectionItems) {
    if (item.position >= 1 && item.position <= limit) {
      slots[item.position - 1] = item
    }
  }

  return slots
}

function getNextAvailablePosition(sectionItems: HomeSectionItem[], limit: number) {
  const usedPositions = new Set(sectionItems.map((item) => item.position))

  for (let position = 1; position <= limit; position += 1) {
    if (!usedPositions.has(position)) return position
  }

  return null
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const payload = error.payload as Record<string, string[] | string> | null

    if (payload && typeof payload === 'object') {
      const detail = payload.detail
      if (Array.isArray(detail) && detail.length > 0) return detail[0]
      if (typeof detail === 'string') return detail

      const firstKey = Object.keys(payload)[0]
      const firstValue = firstKey ? payload[firstKey] : undefined
      if (Array.isArray(firstValue) && firstValue.length > 0) return firstValue[0]
      if (typeof firstValue === 'string') return firstValue
    }
  }

  return fallback
}

function ProductThumb({ item }: { item: HomeSectionItem }) {
  const imageUrl = resolveMediaUrl(item.product.main_image?.image) || PREVIEW_PLACEHOLDER_IMAGE

  return <img src={imageUrl} alt={item.product.main_image?.alt_text || item.product.name} loading="lazy" />
}

function PreviewCard({ item, tag }: { item: HomeSectionItem; tag: string }) {
  return (
    <article className="home-preview-card">
      <ProductThumb item={item} />
      <div>
        <p>{tag}</p>
        <strong>{item.product.name}</strong>
        <span>{formatPrice(item.product) || 'Consultar precio'}</span>
        <small>{formatStockStatus(item.product.stock_status)}</small>
      </div>
    </article>
  )
}

function SectionPreview({ section, items }: { section: SectionConfig; items: HomeSectionItem[] }) {
  const sortedItems = sortByPosition(items)
  const slots = buildSlots(sortedItems, section.limit)

  return (
    <aside className="home-section-preview" aria-label={`Vista previa ${section.title}`}>
      <div className="home-section-preview__header">
        <span>Vista previa</span>
        <strong>{section.previewLabel}</strong>
      </div>

      <div className={`home-preview home-preview--${section.key}`}>
        {section.key === 'machinery_promotions' ? (
          <div className="home-preview-machinery">
            <div className="home-preview-machinery__topbar">
              <h3>Promociones en maquinarias</h3>
              <div aria-hidden="true"><span>‹</span><span>›</span></div>
            </div>
            <div className="home-preview-machinery__grid">
              {sortedItems.slice(0, 4).map((item) => <PreviewCard item={item} tag="Maquinaria destacada" key={item.id} />)}
            </div>
          </div>
        ) : null}

        {section.key === 'spare_parts_offers' ? (
          <div className="home-preview-spares">
            <h3>Oferta en repuestos</h3>
            <div className="home-preview-spares__grid">
              {slots.map((item, index) => (
                <article className={`home-preview-spares__slot ${index === 0 || index === 5 ? 'is-large' : ''}`} key={index + 1}>
                  <header>Slot {index + 1}</header>
                  {item ? (
                    <div className="home-preview-spares__compact-card">
                      <ProductThumb item={item} />
                      <div>
                        <strong>{item.product.name}</strong>
                        <span>{formatPrice(item.product) || 'Consultar'}</span>
                      </div>
                    </div>
                  ) : (
                    <p>Espacio disponible</p>
                  )}
                </article>
              ))}
            </div>
          </div>
        ) : null}

        {section.key === 'repair_services' ? (
          <div className="home-preview-services">
            <h3>Servicios de reparación</h3>
            <div className="home-preview-services__grid">
              {sortedItems.slice(0, 4).map((item) => (
                <article className="home-preview-services__card" key={item.id}>
                  <ProductThumb item={item} />
                  <div>
                    <strong>{item.product.name}</strong>
                    <span>{item.product.short_description || 'Servicio técnico especializado para equipos de elevación.'}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ) : null}

        {sortedItems.length === 0 ? <span className="home-preview__empty">Agrega productos para completar esta vista previa.</span> : null}
      </div>
    </aside>
  )
}

export function AdminHomeSectionsPage() {
  const [items, setItems] = useState<HomeSectionItem[]>([])
  const [productsBySection, setProductsBySection] = useState<ProductsBySection>(EMPTY_PRODUCTS_BY_SECTION)
  const [selectedBySection, setSelectedBySection] = useState<SelectionBySection>(EMPTY_SELECTIONS)
  const [loading, setLoading] = useState(true)
  const [globalError, setGlobalError] = useState<string | null>(null)
  const [sectionStatus, setSectionStatus] = useState<SectionState>(EMPTY_STATUS)
  const [pendingRemoval, setPendingRemoval] = useState<{ section: HomeSection; item: HomeSectionItem } | null>(null)

  const grouped = useMemo(() => {
    return SECTION_CONFIG.reduce((acc, section) => {
      acc[section.key] = sortByPosition(items.filter((item) => item.section === section.key && item.is_active))
      return acc
    }, { machinery_promotions: [] as HomeSectionItem[], spare_parts_offers: [] as HomeSectionItem[], repair_services: [] as HomeSectionItem[] })
  }, [items])

  const setSectionFeedback = (section: HomeSection, next: Partial<{ loading: boolean; error: string | null; success: string | null }>) => {
    setSectionStatus((current) => ({ ...current, [section]: { ...current[section], ...next } }))
  }

  const refreshItems = async () => setItems(await getAdminHomeSectionItems())

  useEffect(() => {
    void (async () => {
      setLoading(true)
      setGlobalError(null)

      try {
        const [homeItems, machineryProducts, sparePartProducts, serviceProducts] = await Promise.all([
          getAdminHomeSectionItems(),
          getProductsForHomeSection('machinery_promotions'),
          getProductsForHomeSection('spare_parts_offers'),
          getProductsForHomeSection('repair_services'),
        ])

        setItems(homeItems)
        setProductsBySection({
          machinery_promotions: machineryProducts,
          spare_parts_offers: sparePartProducts,
          repair_services: serviceProducts,
        })
        const assignedBySection = SECTION_CONFIG.reduce((acc, section) => {
          acc[section.key] = new Set(homeItems.filter((item) => item.section === section.key).map((item) => item.product.id))
          return acc
        }, { machinery_promotions: new Set<number>(), spare_parts_offers: new Set<number>(), repair_services: new Set<number>() })

        setSelectedBySection({
          machinery_promotions: machineryProducts.find((product) => !assignedBySection.machinery_promotions.has(product.id))?.id ?? '',
          spare_parts_offers: sparePartProducts.find((product) => !assignedBySection.spare_parts_offers.has(product.id))?.id ?? '',
          repair_services: serviceProducts.find((product) => !assignedBySection.repair_services.has(product.id))?.id ?? '',
        })
      } catch {
        setGlobalError('No se pudo cargar la configuración de Promociones.')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const addProductToSection = async (section: HomeSection, limit: number) => {
    const selectedProductId = selectedBySection[section]
    if (!selectedProductId) return

    const sectionItems = grouped[section]
    const nextPosition = getNextAvailablePosition(sectionItems, limit)

    if (!nextPosition) {
      setSectionFeedback(section, { error: `Límite alcanzado: máximo ${limit} productos.`, success: null })
      return
    }

    if (sectionItems.some((item) => item.product.id === selectedProductId)) {
      setSectionFeedback(section, { error: 'El producto ya está asignado en esta sección.', success: null })
      return
    }

    setSectionFeedback(section, { loading: true, error: null, success: null })

    try {
      await createHomeSectionItem({ section, product: selectedProductId, position: nextPosition, is_active: true })
      await refreshItems()
      setSelectedBySection((current) => ({ ...current, [section]: '' }))
      setSectionFeedback(section, { success: `Producto agregado en el slot ${nextPosition}.` })
    } catch (error) {
      await refreshItems().catch(() => undefined)
      setSectionFeedback(section, { error: getErrorMessage(error, 'No fue posible agregar el producto.'), success: null })
    } finally {
      setSectionFeedback(section, { loading: false })
    }
  }

  const moveItemToPosition = async (section: HomeSection, item: HomeSectionItem, nextPosition: number) => {
    if (item.position === nextPosition) return

    setSectionFeedback(section, { loading: true, error: null, success: null })

    try {
      await updateHomeSectionItem(item.id, { position: nextPosition })
      await refreshItems()
      setSectionFeedback(section, { success: `Producto movido al slot ${nextPosition}. Si el slot estaba ocupado, se intercambiaron las posiciones.` })
    } catch (error) {
      await refreshItems().catch(() => undefined)
      setSectionFeedback(section, { error: getErrorMessage(error, 'No fue posible mover el producto. La lista se actualizó para evitar duplicados.'), success: null })
    } finally {
      setSectionFeedback(section, { loading: false })
    }
  }

  const removeItem = async (section: HomeSection, item: HomeSectionItem) => {
    setSectionFeedback(section, { loading: true, error: null, success: null })

    try {
      await deleteHomeSectionItem(item.id)
      await refreshItems()
      setPendingRemoval((current) => (current?.item.id === item.id ? null : current))
      setSectionFeedback(section, { success: `Producto quitado. El slot ${item.position} quedó disponible.` })
    } catch (error) {
      await refreshItems().catch(() => undefined)
      setPendingRemoval((current) => (current?.item.id === item.id ? null : current))
      setSectionFeedback(section, { error: getErrorMessage(error, 'No fue posible quitar el producto. La lista fue actualizada.'), success: null })
    } finally {
      setSectionFeedback(section, { loading: false })
    }
  }

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <div>
          <h1>Promociones</h1>
          <p className="ui-note">Administra los tres bloques promocionales de la Home con slots y vista previa por sección.</p>
        </div>
      </div>

      {loading ? <p className="ui-note">Cargando configuración...</p> : null}
      {globalError ? <p className="ui-note ui-note--error">{globalError}</p> : null}

      {!loading && !globalError ? (
        <div className="home-sections-rows">
          {SECTION_CONFIG.map((section) => {
            const sectionItems = grouped[section.key]
            const sectionProducts = productsBySection[section.key]
            const status = sectionStatus[section.key]
            const assignedProductIds = new Set(sectionItems.map((item) => item.product.id))
            const availableProducts = sectionProducts.filter((product) => !assignedProductIds.has(product.id))

            return (
              <section className="home-section-row" key={section.key}>
                <div className="home-section-row__main">
                  <div className="home-section-card__header">
                    <div>
                      <h2>{section.title}</h2>
                      <p className="ui-note">{section.description}</p>
                    </div>
                    <p className="home-section-count">{sectionItems.length} / {section.limit}</p>
                  </div>

                  <div className="home-section-add-row">
                    <select
                      className="home-section-select"
                      value={selectedBySection[section.key]}
                      onChange={(event) => setSelectedBySection((current) => ({ ...current, [section.key]: event.target.value ? Number(event.target.value) : '' }))}
                      disabled={availableProducts.length === 0 || status.loading}
                    >
                      {availableProducts.length > 0 ? <option value="">{section.selectPlaceholder}</option> : <option value="">{section.emptyProductsText}</option>}
                      {availableProducts.map((product) => (
                        <option key={product.id} value={product.id}>{product.name}</option>
                      ))}
                    </select>
                    <button
                      className="btn btn--accent home-section-add-button"
                      type="button"
                      onClick={() => void addProductToSection(section.key, section.limit)}
                      disabled={status.loading || availableProducts.length === 0 || !selectedBySection[section.key]}
                    >
                      Agregar
                    </button>
                  </div>

                  {status.error ? <p className="ui-note ui-note--error">{status.error}</p> : null}
                  {status.success ? <p className="ui-note ui-note--success">{status.success}</p> : null}

                  <div className="home-section-list">
                    {sectionItems.length === 0 ? <p className="ui-note">Sin productos asignados.</p> : null}
                    {sectionItems.map((item) => {
                      const isConfirmingRemoval = pendingRemoval?.item.id === item.id && pendingRemoval.section === section.key

                      return (
                        <article className="home-section-item" key={item.id}>
                          <div className="home-section-item__summary">
                            <ProductThumb item={item} />
                            <div>
                              <strong>{item.product.name}</strong>
                              <span>{item.product.brand?.name || item.product.category.name}</span>
                            </div>
                          </div>
                          <div className="home-section-item__actions">
                            <label>
                              Slot
                              <select
                                className="home-section-slot-select"
                                value={item.position}
                                onChange={(event) => void moveItemToPosition(section.key, item, Number(event.target.value))}
                                disabled={status.loading}
                              >
                                {Array.from({ length: section.limit }, (_, index) => (
                                  <option key={index + 1} value={index + 1}>Slot {index + 1}</option>
                                ))}
                              </select>
                            </label>

                            {isConfirmingRemoval ? (
                              <div className="home-section-confirm">
                                <span>¿Quitar?</span>
                                <button type="button" className="table-action table-action--button" onClick={() => setPendingRemoval(null)} disabled={status.loading}>Cancelar</button>
                                <button type="button" className="table-action table-action--button table-action--danger" onClick={() => void removeItem(section.key, item)} disabled={status.loading}>Quitar</button>
                              </div>
                            ) : (
                              <button type="button" className="table-action table-action--button" onClick={() => setPendingRemoval({ section: section.key, item })} disabled={status.loading}>Quitar</button>
                            )}
                          </div>
                        </article>
                      )
                    })}
                  </div>
                </div>

                <SectionPreview section={section} items={sectionItems} />
              </section>
            )
          })}
        </div>
      ) : null}
    </AdminLayout>
  )
}
