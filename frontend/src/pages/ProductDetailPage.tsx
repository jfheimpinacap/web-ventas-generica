import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'
import { getProductBySlug } from '../services/catalogApi'
import { resolveMediaUrl } from '../services/api'
import type { ProductDetail } from '../types/catalog'
import { formatCondition, formatPrice, formatStockStatus } from '../utils/formatters'
import { buildProductWhatsAppMessage, buildWhatsAppUrl } from '../utils/whatsapp'

const PLACEHOLDER_IMAGE = 'https://placehold.co/800x500/111827/F3F4F6?text=Producto'

export function ProductDetailPage() {
  const { slug = '' } = useParams()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
        setProduct(await getProductBySlug(slug))
      } catch {
        setError('No se pudo cargar el detalle del producto.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [slug])

  const imageUrls = useMemo(() => {
    if (!product) return []
    return product.images.map((image) => resolveMediaUrl(image.image)).filter(Boolean)
  }, [product])

  return (
    <Layout>
      <section className="simple-page">
        {loading ? <p>Cargando detalle...</p> : null}
        {!loading && error ? <p className="ui-note ui-note--error">{error}</p> : null}

        {!loading && !error && product ? (
          <div className="product-detail">
            <h1>{product.name}</h1>
            <p>{product.short_description}</p>
            <p>
              <strong>Marca:</strong> {product.brand?.name ?? 'Sin marca'}
            </p>
            <p>
              <strong>Categoría:</strong> {product.category.name}
            </p>
            <p>
              <strong>Descripción:</strong> {product.description || 'Sin descripción ampliada.'}
            </p>
            <p>
              <strong>Condición:</strong> {formatCondition(product.condition)}
            </p>
            <p>
              <strong>Stock:</strong> {formatStockStatus(product.stock_status)}
            </p>
            <p>
              <strong>Precio:</strong> {formatPrice(product)}
            </p>

            <div className="product-detail__images">
              {(imageUrls.length > 0 ? imageUrls : [PLACEHOLDER_IMAGE]).map((imageUrl) => (
                <img key={imageUrl} src={imageUrl} alt={product.name} />
              ))}
            </div>

            <div>
              <h2>Especificaciones técnicas</h2>
              {product.specs.length === 0 ? (
                <p>Sin especificaciones cargadas.</p>
              ) : (
                <ul>
                  {product.specs.map((spec) => (
                    <li key={spec.id}>
                      <strong>{spec.name}:</strong> {spec.value} {spec.unit}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="hero-section__actions">
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
          </div>
        ) : null}
      </section>
    </Layout>
  )
}
