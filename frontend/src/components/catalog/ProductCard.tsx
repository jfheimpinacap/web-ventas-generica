import { Link } from 'react-router-dom'

import { resolveMediaUrl } from '../../services/api'
import type { ProductListItem } from '../../types/catalog'
import { trackProductDetailClick } from '../../utils/analytics'
import { formatProductCondition, formatPrice, formatStockStatus } from '../../utils/formatters'
import { ProductTechnicalData } from './ProductTechnicalData'

interface ProductCardProps {
  product: ProductListItem
  promotionalLabel?: string
  trackingLocation?: string
}

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'

export function ProductCard({ product, promotionalLabel, trackingLocation = 'catalog' }: ProductCardProps) {
  const imageUrl = resolveMediaUrl(product.main_image?.image) || PLACEHOLDER_IMAGE
  const model = product.model?.trim() || null
  const hasUsedMachineryYear = product.product_type === 'machinery'
    && product.condition === 'used'
    && Number.isInteger(product.year)
    && product.year !== null
    && product.year >= 1000
    && product.year <= 9999

  return (
    <article className="product-card">
      <Link
        className="product-card__image-link"
        to={`/producto/${product.slug}`}
        aria-label={`Ver detalle de ${product.name}`}
        onClick={() => trackProductDetailClick({ product_id: product.id, product_name: product.name, location: trackingLocation })}
      >
        <img src={imageUrl} alt={product.main_image?.alt_text || product.name} loading="lazy" />
        {promotionalLabel ? <span className="product-card__image-badge product-card__image-badge--promotion">{promotionalLabel}</span> : null}
        {hasUsedMachineryYear ? <span className="product-card__image-badge product-card__image-badge--year">Año {product.year}</span> : null}
      </Link>
      <div className="product-card__content">
        <div className="product-card__badges">
          <span className="badge badge--condition">{formatProductCondition(product)}</span>
          <span className="badge badge--stock">{formatStockStatus(product.stock_status)}</span>
        </div>
        <h3>{product.name}</h3>
        {model ? <p className="product-card__model">{model}</p> : null}
        <ProductTechnicalData
          productType={product.product_type}
          condition={product.condition}
          workingHeightM={product.working_height_m}
          maximumLoadCapacityKg={product.maximum_load_capacity_kg}
          powerSource={product.power_source}
          terrainType={product.terrain_type}
        />
        <p className="product-card__price home-product-price">{formatPrice(product)}</p>
      </div>
      <div className="product-card__actions">
        <Link className="btn btn--accent" to={`/producto/${product.slug}`} onClick={() => trackProductDetailClick({ product_id: product.id, product_name: product.name, location: trackingLocation })}>
          Ver detalle
        </Link>
      </div>
    </article>
  )
}
