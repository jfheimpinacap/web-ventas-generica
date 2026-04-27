import { mockProducts } from '../../data/mockProducts'
import { useProducts } from '../../hooks/useProducts'
import { ProductCard } from './ProductCard'

interface FeaturedProductsProps {
  searchTerm?: string
}

export function FeaturedProducts({ searchTerm }: FeaturedProductsProps) {
  const { products, loading, error } = useProducts(searchTerm)
  const hasSearch = Boolean(searchTerm)

  const title = hasSearch ? 'Resultados de búsqueda' : 'Productos destacados'
  const subtitle = hasSearch
    ? `Mostrando coincidencias para "${searchTerm}".`
    : 'Selección inicial para venta rápida de equipos y repuestos.'

  const fallbackProducts = hasSearch ? [] : mockProducts

  return (
    <section className="featured-products">
      <div className="section-heading">
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>

      {loading ? <p className="ui-note">Cargando productos...</p> : null}

      {!loading && error ? (
        <>
          <p className="ui-note ui-note--error">{error} Mostrando respaldo local.</p>
          <div className="featured-products__grid">
            {fallbackProducts.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </>
      ) : null}

      {!loading && !error && products.length === 0 ? (
        <p className="ui-note">No se encontraron productos para esta búsqueda.</p>
      ) : null}

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
