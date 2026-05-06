import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { Breadcrumb, type BreadcrumbItem } from '../components/common/Breadcrumb'
import { Layout } from '../components/layout/Layout'
import { getProductBySlug, getProducts } from '../services/catalogApi'
import { useCategories } from '../hooks/useCategories'
import { resolveMediaUrl } from '../services/api'
import type { Category, ProductDetail, ProductImage, ProductListItem } from '../types/catalog'
import { formatCondition, formatPrice, formatProductType, formatStockStatus } from '../utils/formatters'
import { buildProductWhatsAppMessage, buildWhatsAppUrl } from '../utils/whatsapp'

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
  const { categories } = useCategories()

  useEffect(() => {
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
          const related = await getProducts({ category: String(detail.category.id), ordering: '-created_at' })
          setRelatedProducts(related.filter((item) => item.id !== detail.id).slice(0, 4))
        } else {
          setRelatedProducts([])
        }
      } catch {
        setError('No se pudo cargar el detalle del producto.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [slug])

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

  const breadcrumbItems = useMemo<BreadcrumbItem[]>(() => {
    if (!product) return []

    return [
      { label: 'Inicio', to: '/' },
      { label: 'Catálogo', to: '/catalogo' },
      ...categoryPath.map((category) => ({
        label: category.name,
        to: `/catalogo?category=${category.id}`,
      })),
      { label: product.name },
    ]
  }, [categoryPath, product])

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

  return (
    <Layout>
      <section className="simple-page">
        {loading ? <p>Cargando detalle...</p> : null}
        {!loading && error ? <p className="ui-note ui-note--error">{error}</p> : null}

        {!loading && !error && product ? (
          <div className="product-detail">
            <Breadcrumb items={breadcrumbItems} ariaLabel="Ruta del producto" />

            <div className="product-detail__top-actions">
              <Link className="btn btn--ghost" to="/catalogo">
                ← Volver al catálogo
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
                  {product.short_description ? <p className="product-detail__lead">{product.short_description}</p> : null}
                </div>

                <div className="product-card__badges product-detail__badges">
                  <span className="badge badge--condition">{formatCondition(product.condition)}</span>
                  <span className="badge badge--stock">{formatStockStatus(product.stock_status)}</span>
                </div>

                <div className="product-detail__price-box">
                  <span>Precio</span>
                  <strong>{formatPrice(product)}</strong>
                  {!product.price_visible || !product.price ? <small>Solicita una cotización para recibir precio actualizado.</small> : null}
                </div>

                <dl className="product-detail__facts">
                  <div>
                    <dt>Marca</dt>
                    <dd>{product.brand?.name ?? 'Sin marca'}</dd>
                  </div>
                  <div>
                    <dt>Categoría</dt>
                    <dd>{product.category?.name ?? 'Sin categoría'}</dd>
                  </div>
                  <div>
                    <dt>Condición</dt>
                    <dd>{formatCondition(product.condition)}</dd>
                  </div>
                  <div>
                    <dt>Disponibilidad</dt>
                    <dd>{formatStockStatus(product.stock_status)}</dd>
                  </div>
                  <div>
                    <dt>Modelo</dt>
                    <dd>{product.model || 'No informado'}</dd>
                  </div>
                  <div>
                    <dt>SKU</dt>
                    <dd>{product.sku || 'No informado'}</dd>
                  </div>
                </dl>

                <div className="product-detail__payment-box">
                  <h2>Formas de pago</h2>
                  <ul>
                    <li>Transferencia / Débito.</li>
                    <li>Otros medios de pago según cotización.</li>
                    <li>Cotización directa con un ejecutivo.</li>
                  </ul>
                </div>

                {product.supplier?.name ? (
                  <p className="product-detail__supplier">
                    <strong>Proveedor:</strong> {product.supplier.name}
                  </p>
                ) : null}

                <div className="product-detail__contact-actions">
                  <Link className="btn btn--accent" to={`/cotizar?product=${product.id}`}>
                    Cotizar
                  </Link>
                  <a
                    className="btn btn--ghost"
                    href={buildWhatsAppUrl(buildProductWhatsAppMessage(product.name))}
                    target="_blank"
                    rel="noreferrer"
                  >
                    WhatsApp
                  </a>
                </div>
              </section>
            </div>

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
      </section>
    </Layout>
  )
}
