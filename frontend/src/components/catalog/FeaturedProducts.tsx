import { mockProducts } from '../../data/mockProducts'
import { useProducts } from '../../hooks/useProducts'
import { ProductCard } from './ProductCard'

export function FeaturedProducts() {
  const { products, loading, error } = useProducts()

  return (
    <section className="featured-products">
      <div className="section-heading">
        <h2>Productos destacados</h2>
        <p>Selección inicial para venta rápida de equipos y repuestos.</p>
      </div>

      {loading ? <p className="ui-note">Cargando productos...</p> : null}

      {!loading && error ? (
        <>
          <p className="ui-note ui-note--error">{error} Mostrando respaldo local.</p>
          <div className="featured-products__grid">
            {mockProducts.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </>
      ) : null}

      {!loading && !error && products.length === 0 ? <p className="ui-note">No hay productos destacados por ahora.</p> : null}

      {!loading && !error && products.length > 0 ? (
        <div className="featured-products__grid">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      ) : null}
    </section>
  )
}
