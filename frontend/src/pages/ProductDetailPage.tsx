import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { Breadcrumb, type BreadcrumbItem } from '../components/common/Breadcrumb'
import { Layout } from '../components/layout/Layout'
import { getProductBySlug, getProducts } from '../services/catalogApi'
import { useCategories } from '../hooks/useCategories'
import { resolveMediaUrl } from '../services/api'
import type { Category, ProductDetail, ProductListItem } from '../types/catalog'
import { formatCondition, formatPrice, formatProductType, formatStockStatus } from '../utils/formatters'
import { buildProductWhatsAppMessage, buildWhatsAppUrl } from '../utils/whatsapp'

const PLACEHOLDER_IMAGE = 'https://placehold.co/800x500/111827/F3F4F6?text=Producto'

export function ProductDetailPage() {
  const { slug = '' } = useParams()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [relatedProducts, setRelatedProducts] = useState<ProductListItem[]>([])
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

  const imageUrls = useMemo(() => {
    if (!product) return []
    return [...product.images]
      .sort((a, b) => Number(b.is_main) - Number(a.is_main) || a.order - b.order || a.id - b.id)
      .map((image) => resolveMediaUrl(image.image))
      .filter(Boolean)
  }, [product])

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

            <h1>{product.name}</h1>
            <p>{product.short_description}</p>

            <div className="product-card__badges">
              <span className="badge badge--condition">{formatCondition(product.condition)}</span>
              <span className="badge badge--stock">{formatStockStatus(product.stock_status)}</span>
            </div>

            <div className="product-detail__images">
              {(imageUrls.length > 0 ? imageUrls : [PLACEHOLDER_IMAGE]).map((imageUrl) => (
                <img key={imageUrl} src={imageUrl} alt={product.name} />
              ))}
            </div>

            <div className="product-detail__cols">
              <div>
                <h2>Descripción y datos clave</h2>
                <p>{product.description || 'Sin descripción ampliada.'}</p>
                <ul>
                  <li>
                    <strong>Marca:</strong> {product.brand?.name ?? 'Sin marca'}
                  </li>
                  <li>
                    <strong>Categoría:</strong> {product.category?.name ?? 'Sin categoría'}
                  </li>
                  <li>
                    <strong>Tipo:</strong> {formatProductType(product.product_type)}
                  </li>
                  <li>
                    <strong>Modelo:</strong> {product.model || 'No informado'}
                  </li>
                  <li>
                    <strong>SKU:</strong> {product.sku || 'No informado'}
                  </li>
                  <li>
                    <strong>Precio:</strong> {formatPrice(product)}
                  </li>
                </ul>
              </div>
              <div className="product-detail__contact">
                <h2>Contacto rápido</h2>
                <p>¿Necesitas asesoría inmediata? Te ayudamos por WhatsApp o cotización directa.</p>
                <div className="product-detail__contact-actions">
                  <Link className="btn btn--accent" to={`/cotizar?product=${product.id}`}>
                    Cotizar este producto
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
              </div>
            </div>

            <div>
              <h2>Especificaciones técnicas</h2>
              {product.specs.length === 0 ? (
                <p>Sin especificaciones cargadas.</p>
              ) : (
                <ul className="product-detail__specs">
                  {[...product.specs]
                    .sort((a, b) => a.order - b.order || a.id - b.id)
                    .map((spec) => (
                    <li key={spec.id}>
                      <span>{spec.name}</span>
                      <strong>
                        {spec.value} {spec.unit}
                      </strong>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {relatedProducts.length > 0 ? (
              <div>
                <h2>Productos relacionados</h2>
                <div className="featured-products__grid">
                  {relatedProducts.map((related) => (
                    <ProductCard key={related.id} product={related} />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </Layout>
  )
}
