import { Link } from 'react-router-dom'

import type { CatalogProduct } from '../../types/catalog'

interface ProductCardProps {
  product: CatalogProduct
}

export function ProductCard({ product }: ProductCardProps) {
  return (
    <article className="product-card">
      <img src={product.imageUrl} alt={product.name} loading="lazy" />
      <div className="product-card__content">
        <h3>{product.name}</h3>
        <p>
          <strong>Marca:</strong> {product.brand}
        </p>
        <p>
          <strong>Categoría:</strong> {product.category}
        </p>
        <p>
          <strong>Estado:</strong> {product.condition}
        </p>
        <p className="product-card__price">{product.priceLabel}</p>
      </div>
      <div className="product-card__actions">
        <Link className="btn btn--ghost" to={`/producto/${product.slug}`}>
          Ver detalle
        </Link>
        <Link className="btn btn--accent" to="/cotizar">
          Cotizar
        </Link>
      </div>
    </article>
  )
}
