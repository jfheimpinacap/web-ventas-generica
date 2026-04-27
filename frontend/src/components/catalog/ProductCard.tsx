import { Link } from 'react-router-dom'

import { resolveMediaUrl } from '../../services/api'
import type { ProductListItem } from '../../types/catalog'
import { formatCondition, formatPrice, formatStockStatus } from '../../utils/formatters'
import { buildProductWhatsAppMessage, buildWhatsAppUrl } from '../../utils/whatsapp'

interface ProductCardProps {
  product: ProductListItem
}

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'

export function ProductCard({ product }: ProductCardProps) {
  const imageUrl = resolveMediaUrl(product.main_image?.image) || PLACEHOLDER_IMAGE

  return (
    <article className="product-card">
      <img src={imageUrl} alt={product.main_image?.alt_text || product.name} loading="lazy" />
      <div className="product-card__content">
        <div className="product-card__badges">
          <span className="badge badge--condition">{formatCondition(product.condition)}</span>
          <span className="badge badge--stock">{formatStockStatus(product.stock_status)}</span>
        </div>
        <h3>{product.name}</h3>
        <p>
          <strong>Marca:</strong> {product.brand?.name ?? 'Sin marca'}
        </p>
        <p>
          <strong>Categoría:</strong> {product.category.name}
        </p>
        <p>{product.short_description || 'Sin descripción breve.'}</p>
        <p className="product-card__price">{formatPrice(product)}</p>
      </div>
      <div className="product-card__actions">
        <Link className="btn btn--ghost" to={`/producto/${product.slug}`}>
          Ver detalle
        </Link>
        <Link className="btn btn--accent" to={`/cotizar?product=${product.id}`}>
          Cotizar
        </Link>
        <a className="btn btn--ghost" href={buildWhatsAppUrl(buildProductWhatsAppMessage(product.name))} target="_blank" rel="noreferrer">
          WhatsApp
        </a>
      </div>
    </article>
  )
}
