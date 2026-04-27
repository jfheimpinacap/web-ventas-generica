import { mockProducts } from '../../data/mockProducts'
import { ProductCard } from './ProductCard'

export function FeaturedProducts() {
  return (
    <section className="featured-products">
      <div className="section-heading">
        <h2>Productos destacados</h2>
        <p>Selección inicial para venta rápida de equipos y repuestos.</p>
      </div>

      <div className="featured-products__grid">
        {mockProducts.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </section>
  )
}
