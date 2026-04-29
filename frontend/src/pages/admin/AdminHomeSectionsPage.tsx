import { useEffect, useMemo, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { createHomeSectionItem, deleteHomeSectionItem, getAdminHomeSectionItems, getAdminProducts } from '../../services/adminApi'
import { ApiError } from '../../services/api'
import { resolveMediaUrl } from '../../services/api'
import type { HomeSection, HomeSectionItem, ProductListItem } from '../../types/catalog'
import { formatPrice, formatStockStatus } from '../../utils/formatters'

type SectionConfig = {
  key: HomeSection
  title: string
  limit: number
  description: string
  selectPlaceholder: string
  emptyProductsText: string
}

const SECTION_CONFIG: SectionConfig[] = [
  { key: 'machinery_promotions', title: 'Promociones en maquinarias', limit: 12, description: 'Productos tipo maquinaria para destacar en la Home pública.', selectPlaceholder: 'Seleccionar maquinaria...', emptyProductsText: 'No hay maquinarias compatibles disponibles.' },
  { key: 'spare_parts_offers', title: 'Oferta en repuestos', limit: 6, description: 'Repuestos publicados para mostrar como ofertas destacadas.', selectPlaceholder: 'Seleccionar repuesto...', emptyProductsText: 'No hay repuestos compatibles disponibles.' },
  { key: 'repair_services', title: 'Servicios de reparación', limit: 12, description: 'Servicios para destacar capacidades de reparación en Home.', selectPlaceholder: 'Seleccionar servicio...', emptyProductsText: 'No hay servicios compatibles disponibles.' },
]
const PREVIEW_PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const payload = error.payload as Record<string, string[] | string> | null
    if (payload && typeof payload === 'object') {
      const firstKey = Object.keys(payload)[0]
      const firstValue = firstKey ? payload[firstKey] : undefined
      if (Array.isArray(firstValue) && firstValue.length > 0) return firstValue[0]
      if (typeof firstValue === 'string') return firstValue
    }
  }
  return fallback
}

export function AdminHomeSectionsPage() {
  const [items, setItems] = useState<HomeSectionItem[]>([])
  const [productsBySection, setProductsBySection] = useState<Record<HomeSection, ProductListItem[]>>({ machinery_promotions: [], spare_parts_offers: [], repair_services: [] })
  const [selectedBySection, setSelectedBySection] = useState<Record<HomeSection, number | ''>>({ machinery_promotions: '', spare_parts_offers: '', repair_services: '' })
  const [loading, setLoading] = useState(true)
  const [globalError, setGlobalError] = useState<string | null>(null)
  const [sectionStatus, setSectionStatus] = useState<Record<HomeSection, { loading: boolean; error: string | null; success: string | null }>>({
    machinery_promotions: { loading: false, error: null, success: null }, spare_parts_offers: { loading: false, error: null, success: null }, repair_services: { loading: false, error: null, success: null },
  })
  const [pendingRemoval, setPendingRemoval] = useState<{ section: HomeSection; item: HomeSectionItem } | null>(null)

  const grouped = useMemo(() => SECTION_CONFIG.reduce((acc, section) => {
    acc[section.key] = items.filter((item) => item.section === section.key).sort((a, b) => a.position - b.position)
    return acc
  }, { machinery_promotions: [] as HomeSectionItem[], spare_parts_offers: [] as HomeSectionItem[], repair_services: [] as HomeSectionItem[] }), [items])

  const setSectionFeedback = (section: HomeSection, next: Partial<{ loading: boolean; error: string | null; success: string | null }>) => setSectionStatus((current) => ({ ...current, [section]: { ...current[section], ...next } }))
  const refreshItems = async () => setItems(await getAdminHomeSectionItems())

  useEffect(() => { void (async () => {
    setLoading(true); setGlobalError(null)
    try {
      const [homeItems, allProducts] = await Promise.all([getAdminHomeSectionItems(), getAdminProducts()])
      const machineryProducts = allProducts.filter((product) => product.product_type === 'machinery')
      const sparePartProducts = allProducts.filter((product) => product.product_type === 'spare_part')
      const serviceProducts = allProducts.filter((product) => {
        if (product.product_type === 'service') return true
        const categoryName = (product.category.name ?? '').toLowerCase()
        const categorySlug = (product.category.slug ?? '').toLowerCase()
        return categoryName.includes('servicio') || categoryName.includes('service') || categorySlug.includes('servicio') || categorySlug.includes('service')
      })
      setItems(homeItems)
      setProductsBySection({ machinery_promotions: machineryProducts, spare_parts_offers: sparePartProducts, repair_services: serviceProducts })
      setSelectedBySection({ machinery_promotions: machineryProducts[0]?.id ?? '', spare_parts_offers: sparePartProducts[0]?.id ?? '', repair_services: serviceProducts[0]?.id ?? '' })
    } catch {
      setGlobalError('No se pudo cargar la configuración de Promociones.')
    } finally { setLoading(false) }
  })() }, [])

  const addProductToSection = async (section: HomeSection, limit: number) => {
    const selectedProductId = selectedBySection[section]
    if (!selectedProductId) return
    const sectionItems = grouped[section]
    if (sectionItems.length >= limit) return setSectionFeedback(section, { error: `Límite alcanzado: máximo ${limit} productos.`, success: null })
    if (sectionItems.some((item) => item.product.id === selectedProductId)) return setSectionFeedback(section, { error: 'El producto ya está asignado en esta sección.', success: null })
    setSectionFeedback(section, { loading: true, error: null, success: null })
    try { await createHomeSectionItem({ section, product: selectedProductId, position: 1, is_active: true }); await refreshItems(); setSectionFeedback(section, { success: 'Producto agregado correctamente.' }) }
    catch (error) { setSectionFeedback(section, { error: getErrorMessage(error, 'No fue posible agregar el producto.'), success: null }) }
    finally { setSectionFeedback(section, { loading: false }) }
  }

  const removeItem = async (section: HomeSection, item: HomeSectionItem) => {
    setSectionFeedback(section, { loading: true, error: null, success: null })
    try {
      await deleteHomeSectionItem(item.id)
      await refreshItems()
      setPendingRemoval((current) => (current?.item.id === item.id ? null : current))
      setSectionFeedback(section, { success: 'Producto quitado de la sección.' })
    }
    catch (error) { setSectionFeedback(section, { error: getErrorMessage(error, 'No fue posible quitar el producto.'), success: null }) }
    finally { setSectionFeedback(section, { loading: false }) }
  }

  return <AdminLayout>
    <div className="admin-products-header"><h1>Promociones</h1><p className="ui-note">Administra cada bloque de la Home de forma independiente.</p></div>
    {loading ? <p className="ui-note">Cargando configuración...</p> : null}
    {globalError ? <p className="ui-note ui-note--error">{globalError}</p> : null}
    {!loading && !globalError ? <div className="home-sections-rows">{SECTION_CONFIG.map((section) => {
      const sectionItems = grouped[section.key]; const sectionProducts = productsBySection[section.key]; const status = sectionStatus[section.key]
      return <section className="home-section-row" key={section.key}>
        <div className="home-section-row__main">
          <div className="home-section-card__header"><div><h2>{section.title}</h2><p className="ui-note">{section.description}</p></div><p>{sectionItems.length} / {section.limit}</p></div>
          <div className="home-section-add-row">
            <select className="home-section-select" value={selectedBySection[section.key]} onChange={(event) => setSelectedBySection((current) => ({ ...current, [section.key]: Number(event.target.value) }))} disabled={sectionProducts.length === 0 || status.loading}>
              {sectionProducts.length > 0 ? <option value="">{section.selectPlaceholder}</option> : <option value="">{section.emptyProductsText}</option>}
              {sectionProducts.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
            </select>
            <button className="btn btn--accent home-section-add-button" type="button" onClick={() => void addProductToSection(section.key, section.limit)} disabled={status.loading || sectionProducts.length === 0 || !selectedBySection[section.key]}>Agregar</button>
          </div>
          {status.error ? <p className="ui-note ui-note--error">{status.error}</p> : null}
          {status.success ? <p className="ui-note">{status.success}</p> : null}
          <div className="home-section-list">{sectionItems.length === 0 ? <p className="ui-note">Sin productos asignados.</p> : sectionItems.map((item) => {
            const isConfirmingRemoval = pendingRemoval?.item.id === item.id && pendingRemoval.section === section.key
            return <article
              className="home-section-item home-section-item--compact"
              key={item.id}
            ><div className="home-section-item__summary"><strong>{item.product.name}</strong><span>Posición: {item.position}</span></div><div className="home-section-item__actions home-section-item__actions--single">{isConfirmingRemoval ? <div className="home-section-confirm"><span>¿Quitar este producto de la sección?</span><button type="button" className="table-action table-action--button" onClick={() => setPendingRemoval(null)} disabled={status.loading}>Cancelar</button><button type="button" className="table-action table-action--button table-action--danger" onClick={() => void removeItem(section.key, item)} disabled={status.loading}>Quitar</button></div> : <button type="button" className="table-action table-action--button" onClick={() => setPendingRemoval({ section: section.key, item })} disabled={status.loading}>Quitar</button>}</div></article>
          })}</div>
        </div>
        <aside className="home-section-preview" aria-label={`Vista previa ${section.title}`}>
          <h3>Vista previa</h3>
          <div className={`home-preview home-preview--${section.key}`}>
            <div className="home-preview__scale">
              {section.key === 'machinery_promotions' ? <div className="home-preview-machinery">
                <div className="home-preview-machinery__controls"><span>‹</span><span>›</span></div>
                <div className="home-preview-machinery__grid">
                  {sectionItems.slice(0, 4).map((item) => <article className="home-preview-card" key={item.id}><img src={resolveMediaUrl(item.product.main_image?.image) || PREVIEW_PLACEHOLDER_IMAGE} alt={item.product.name} /><div><p>Maquinaria destacada</p><strong>{item.product.name}</strong><span>{formatPrice(item.product) || 'Consultar precio'}</span><small>{formatStockStatus(item.product.stock_status)}</small><small>{item.product.brand?.name || item.product.category.name}</small></div></article>)}
                </div>
              </div> : null}
              {section.key === 'spare_parts_offers' ? <div className="home-preview-spares">
                <div className="home-preview-spares__grid">
                  {sectionItems.slice(0, 6).map((item, index) => <article className={`home-preview-spares__card ${index === 0 || index === 5 ? 'is-large' : ''}`} key={item.id}><img src={resolveMediaUrl(item.product.main_image?.image) || PREVIEW_PLACEHOLDER_IMAGE} alt={item.product.name} /><div><span>Oferta destacada</span><strong>{item.product.name}</strong></div></article>)}
                </div>
              </div> : null}
              {section.key === 'repair_services' ? <div className="home-preview-services">
                <div className="home-preview-services__grid">
                  {sectionItems.slice(0, 4).map((item) => <article className="home-preview-services__card" key={item.id}><img src={resolveMediaUrl(item.product.main_image?.image) || PREVIEW_PLACEHOLDER_IMAGE} alt={item.product.name} /><div><strong>{item.product.name}</strong><span>{item.product.short_description || 'Servicio técnico especializado para equipos de elevación.'}</span></div></article>)}
                </div>
              </div> : null}
              {sectionItems.length === 0 ? <span className="home-preview__empty">Sin ítems</span> : null}
            </div>
          </div>
        </aside>
      </section>
    })}</div> : null}
  </AdminLayout>
}
