import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { ProductTechnicalSheetModal } from '../components/catalog/ProductTechnicalSheetModal'
import { Breadcrumb, type BreadcrumbItem } from '../components/common/Breadcrumb'
import { JsonLd } from '../components/common/JsonLd'
import { Seo } from '../components/common/Seo'
import { Layout } from '../components/layout/Layout'
import { buildPublicTechnicalSheetUrl, getProductBySlug, getProducts } from '../services/catalogApi'
import { useCategories } from '../hooks/useCategories'
import { ApiError, resolveMediaUrl } from '../services/api'
import type { Category, ProductDetail, ProductImage, ProductListItem } from '../types/catalog'
import { formatMachineWeightKg, formatMaximumLoadCapacityKg, formatProductCondition, formatPrice, formatProductPowerSource, formatProductTerrainType, formatProductType, formatStockStatus } from '../utils/formatters'
import { trackProductView, trackQuoteClick, trackTechnicalSheetDownload, trackTechnicalSheetView } from '../utils/analytics'
import { buildBreadcrumbJsonLd, buildProductJsonLd, buildPublicUrl } from '../utils/seo'

const PLACEHOLDER_IMAGE = 'https://placehold.co/900x700/111827/F3F4F6?text=Producto'

type GalleryImage = Pick<ProductImage, 'id' | 'alt_text' | 'is_main' | 'order'> & {
  url: string
}

export function ProductDetailPage() {
  const { slug = '' } = useParams()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [relatedProducts, setRelatedProducts] = useState<ProductListItem[]>([])
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [technicalSheetOpen, setTechnicalSheetOpen] = useState(false)
  const technicalSheetButtonRef = useRef<HTMLButtonElement>(null)
  const { categories } = useCategories()

  useEffect(() => {
    setTechnicalSheetOpen(false)
    if (!slug) {
      setError('Slug inválido de producto.')
      setLoading(false)
      return
    }

    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        const detail = await getProductBySlug(slug)
        setProduct(detail)
        setSelectedImageId(null)
        if (detail.category?.id) {
          const related = await getProducts({
            category: String(detail.category.id), ordering: '-created_at',
            ...(detail.product_type === 'machinery' ? { product_type: 'machinery', condition: detail.condition } : {}),
          })
          setRelatedProducts(related.filter((item) => item.id !== detail.id).slice(0, 4))
        } else {
          setRelatedProducts([])
        }
      } catch (error) {
        setProduct(null)
        setRelatedProducts([])
        setError(error instanceof ApiError && error.status === 404 ? 'Producto no disponible.' : 'Producto no disponible.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [slug])

  const technicalSheet = product?.technical_sheet
  const hasTechnicalSheet = Boolean(technicalSheet?.file_url.trim() && ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'].includes(technicalSheet.content_type.trim().toLowerCase()))
  const inlineTechnicalSheetUrl = hasTechnicalSheet ? buildPublicTechnicalSheetUrl(technicalSheet!.file_url) : ''
  const downloadTechnicalSheetUrl = hasTechnicalSheet ? buildPublicTechnicalSheetUrl(technicalSheet!.file_url, true) : ''

  const categoryPath = useMemo(() => {
    if (!product?.category) return [] as Category[]

    const categoryById = new Map(categories.map((category) => [category.id, category]))
    const path: Category[] = []
    let current: Category | null = categoryById.get(product.category.id) ?? product.category

    while (current) {
      path.unshift(current)
      current = current.parent ? categoryById.get(current.parent) ?? null : null
    }

    return path
  }, [categories, product])

  const rootCategory = categoryPath[0]?.parent === null ? categoryPath[0] : null
  const commercialPath = product?.product_type === 'machinery' && product.condition === 'new' ? '/maquinaria-nueva'
    : product?.product_type === 'machinery' && product.condition === 'used' ? '/maquinaria-usada' : null
  const backHref = commercialPath ?? (rootCategory ? `/catalogo?category=${rootCategory.id}` : '/')

  useEffect(() => {
    if (!product) return
    trackProductView({
      product_id: product.id,
      product_name: product.name,
      category: product.category?.name,
      brand: product.brand?.name,
      price: product.price_visible ? product.price : undefined,
    })
  }, [product])

  const breadcrumbItems = useMemo<BreadcrumbItem[]>(() => {
    if (!product) return []

    return [
      { label: 'Inicio', to: '/' },
      ...(commercialPath ? [{ label: product.condition === 'new' ? 'Venta de maquinaria nueva' : 'Venta de maquinaria usada', to: commercialPath }] : []),
      ...categoryPath.map((category) => ({
        label: category.name,
        to: `/catalogo?category=${category.id}`,
      })),
      { label: product.name },
    ]
  }, [categoryPath, commercialPath, product])

  const galleryImages = useMemo<GalleryImage[]>(() => {
    if (!product) return []

    const productImages = [...product.images]
      .sort((a, b) => Number(b.is_main) - Number(a.is_main) || a.order - b.order || a.id - b.id)
      .map((image) => ({
        id: image.id,
        url: resolveMediaUrl(image.image),
        alt_text: image.alt_text,
        is_main: image.is_main,
        order: image.order,
      }))
      .filter((image): image is GalleryImage => Boolean(image.url))

    if (productImages.length > 0) return productImages

    return [{ id: 0, url: PLACEHOLDER_IMAGE, alt_text: product.name, is_main: true, order: 0 }]
  }, [product])

  const selectedImage = useMemo(() => {
    return galleryImages.find((image) => image.id === selectedImageId) ?? galleryImages[0]
  }, [galleryImages, selectedImageId])

  const seoTitle = product ? `${product.name} | JEM Nexus` : 'Producto | JEM Nexus'
  const seoDescription = product
    ? product.brand?.name
      ? `Cotiza ${product.name} de marca ${product.brand.name} para operaciones industriales. Revisa precio, disponibilidad y especificaciones técnicas.`
      : `Cotiza ${product.name} para operaciones industriales. Revisa precio, disponibilidad y especificaciones técnicas.`
    : 'Cotiza maquinaria, repuestos y servicios industriales.'
  const canonicalUrl = buildPublicUrl(`/producto/${slug}`)
  const robots = !loading && (!product || error) ? 'noindex,nofollow' : 'index,follow'
  const ogImage = selectedImage?.url

  const breadcrumbJsonLd = useMemo(
    () => (product ? buildBreadcrumbJsonLd(breadcrumbItems) : null),
    [breadcrumbItems, product],
  )
  const productJsonLd = useMemo(
    () => (product ? buildProductJsonLd(product, canonicalUrl) : null),
    [canonicalUrl, product],
  )

  const isMachinery = product?.product_type === 'machinery'
  const maximumLoadCapacity = isMachinery
    ? formatMaximumLoadCapacityKg(product.maximum_load_capacity_kg)
    : null
  const machineWeight = isMachinery ? formatMachineWeightKg(product.machine_weight_kg) : null
  const powerSource = isMachinery ? formatProductPowerSource(product.power_source) : null
  const terrainType = isMachinery ? formatProductTerrainType(product.terrain_type) : null
  const includedServices = isMachinery
    ? [
        { label: 'Revisión técnica', included: product.includes_technical_review === true },
        { label: 'Asesoría técnico-comercial', included: product.includes_commercial_technical_advice === true },
        { label: 'Entrega coordinada', included: product.includes_coordinated_delivery === true },
      ].filter((service) => service.included)
    : []


  return (
    <Layout>
      <Seo
        title={seoTitle}
        description={seoDescription}
        canonical={canonicalUrl}
        ogType="product"
        ogUrl={canonicalUrl}
        ogImage={ogImage}
        twitterCard={ogImage ? 'summary_large_image' : 'summary'}
        twitterImage={ogImage}
        robots={robots}
      />
      {breadcrumbJsonLd ? <JsonLd id="product-breadcrumb" data={breadcrumbJsonLd} /> : null}
      {productJsonLd ? <JsonLd id="product-main" data={productJsonLd} /> : null}
      <section className="simple-page">
        {loading ? <p>Cargando detalle...</p> : null}
        {!loading && error ? (
          <div className="ui-note ui-note--error product-detail__unavailable">
            <p>{error}</p>
            <div className="product-detail__unavailable-actions">
              <Link className="btn btn--ghost" to="/catalogo">
                Volver al catálogo
              </Link>
              <Link className="btn btn--accent" to="/">
                Volver al inicio
              </Link>
            </div>
          </div>
        ) : null}

        {!loading && !error && product ? (
          <div className="product-detail">
            <Breadcrumb items={breadcrumbItems} ariaLabel="Ruta del producto" />

            <div className="product-detail__top-actions">
              <Link className="btn btn--ghost" to={backHref}>
                ← Volver
              </Link>
            </div>

            <div className="product-detail__summary">
              <section className="product-detail__gallery" aria-label={`Galería de imágenes de ${product.name}`}>
                <div className="product-detail__main-image">
                  <img src={selectedImage?.url ?? PLACEHOLDER_IMAGE} alt={selectedImage?.alt_text || product.name} />
                </div>

                {galleryImages.length > 1 ? (
                  <div className="product-detail__thumbs" aria-label="Miniaturas del producto">
                    {galleryImages.map((image, index) => {
                      const isSelected = image.id === selectedImage?.id

                      return (
                        <button
                          type="button"
                          className={`product-detail__thumb${isSelected ? ' product-detail__thumb--active' : ''}`}
                          key={image.id}
                          onClick={() => setSelectedImageId(image.id)}
                          aria-label={`Ver imagen ${index + 1} de ${product.name}`}
                          aria-pressed={isSelected}
                        >
                          <img src={image.url} alt={image.alt_text || `${product.name} miniatura ${index + 1}`} />
                        </button>
                      )
                    })}
                  </div>
                ) : null}
              </section>

              <section className="product-detail__commercial" aria-label="Información comercial del producto">
                <div className="product-detail__title-block">
                  <p className="product-detail__eyebrow">{formatProductType(product.product_type)}</p>
                  <h1>{product.name}</h1>
                </div>

                <div className="product-detail__price-box">
                  <span>Precio</span>
                  <strong>{formatPrice(product)}</strong>
                  {!product.price_visible || !product.price ? <small>Solicita una cotización para recibir precio actualizado.</small> : null}
                </div>

                {isMachinery ? (
                  <dl className="product-detail__facts">
                    {product.brand?.name ? <div><dt>Marca</dt><dd>{product.brand.name}</dd></div> : null}
                    {machineWeight ? <div><dt>Peso</dt><dd>{machineWeight}</dd></div> : null}
                    {product.model?.trim() ? <div><dt>Modelo</dt><dd>{product.model.trim()}</dd></div> : null}
                    {powerSource ? <div><dt>Fuente de energía</dt><dd>{powerSource}</dd></div> : null}
                    {maximumLoadCapacity ? <div><dt>Capacidad máxima de carga</dt><dd>{maximumLoadCapacity}</dd></div> : null}
                    <div><dt>Condición</dt><dd>{formatProductCondition(product)}</dd></div>
                    {terrainType ? <div><dt>Tipo de terreno</dt><dd>{terrainType}</dd></div> : null}
                    <div><dt>Stock</dt><dd>{formatStockStatus(product.stock_status)}</dd></div>
                  </dl>
                ) : (
                  <dl className="product-detail__facts">
                    {product.brand?.name ? <div><dt>Marca</dt><dd>{product.brand.name}</dd></div> : null}
                    {product.category?.name ? <div><dt>Categoría</dt><dd>{product.category.name}</dd></div> : null}
                    <div><dt>Condición</dt><dd>{formatProductCondition(product)}</dd></div>
                    <div><dt>Stock</dt><dd>{formatStockStatus(product.stock_status)}</dd></div>
                    {product.model?.trim() ? <div><dt>Modelo</dt><dd>{product.model.trim()}</dd></div> : null}
                    {product.product_type === 'spare_part' && product.sku?.trim() ? <div><dt>SKU</dt><dd>{product.sku.trim()}</dd></div> : null}
                  </dl>
                )}

                <div className="product-detail__contact-actions">
                  <button
                    ref={technicalSheetButtonRef}
                    type="button"
                    className="btn btn--ghost product-detail__technical-sheet-button"
                    disabled={!hasTechnicalSheet}
                    onClick={hasTechnicalSheet ? () => {
                      setTechnicalSheetOpen(true)
                      trackTechnicalSheetView({ location: 'product_detail', product_id: product.id, product_name: product.name, technical_sheet_id: technicalSheet!.id, content_type: technicalSheet!.content_type })
                    } : undefined}
                  >
                    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>
                    Ver ficha técnica
                  </button>
                  <Link
                    className="btn btn--accent"
                    to={`/cotizar?product=${product.id}`}
                    onClick={() => trackQuoteClick({ location: 'product_detail', product_id: product.id, product_name: product.name })}
                  >
                    Cotizar
                  </Link>
                </div>

                {product.supplier?.name ? (
                  <p className="product-detail__supplier">
                    <strong>Proveedor:</strong> {product.supplier.name}
                  </p>
                ) : null}
              </section>
            </div>

            {isMachinery && includedServices.length > 0 ? (
              <section className="product-detail__included-services" aria-labelledby="included-services-title">
                <h2 id="included-services-title">Servicios incluidos</h2>
                <ul className="product-detail__included-services-list">
                  {includedServices.map((service) => (
                    <li className="product-detail__included-service" key={service.label}>
                      <span className="product-detail__included-service-icon" aria-hidden="true">✓</span>
                      <span>{service.label}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section className="product-detail__description-card">
              <h2>Descripción</h2>
              <p>{product.description || 'Sin descripción ampliada.'}</p>
            </section>

            <section className="product-detail__spec-section">
              <h2>Especificaciones técnicas</h2>
              {product.specs.length === 0 ? (
                <p className="product-detail__empty-specs">Sin especificaciones técnicas cargadas por el momento.</p>
              ) : (
                <dl className="product-detail__specs">
                  {[...product.specs]
                    .sort((a, b) => a.order - b.order || a.id - b.id)
                    .map((spec) => (
                      <div key={spec.id} className="product-detail__spec-row">
                        <dt>{spec.name}</dt>
                        <dd>
                          {spec.value} {spec.unit}
                        </dd>
                      </div>
                    ))}
                </dl>
              )}
            </section>

            {relatedProducts.length > 0 ? (
              <section>
                <h2>Productos relacionados</h2>
                <div className="featured-products__grid">
                  {relatedProducts.map((related) => (
                    <ProductCard key={related.id} product={related} />
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        ) : null}
        {product && hasTechnicalSheet ? <ProductTechnicalSheetModal
          open={technicalSheetOpen} productName={product.name} sheet={technicalSheet!}
          inlineUrl={inlineTechnicalSheetUrl} downloadUrl={downloadTechnicalSheetUrl}
          onClose={() => setTechnicalSheetOpen(false)} returnFocusRef={technicalSheetButtonRef}
          onDownload={() => trackTechnicalSheetDownload({ location: 'product_detail', product_id: product.id, product_name: product.name, technical_sheet_id: technicalSheet!.id, content_type: technicalSheet!.content_type })}
        /> : null}
      </section>
    </Layout>
  )
}
