import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { Layout } from '../components/layout/Layout'
import { useBrands } from '../hooks/useBrands'
import { useCatalogProducts } from '../hooks/useCatalogProducts'
import { useCategories } from '../hooks/useCategories'
import type { ProductQueryParams } from '../types/catalog'

const ORDER_OPTIONS = [
  { value: 'name', label: 'Nombre A-Z' },
  { value: '-created_at', label: 'Más recientes' },
  { value: 'price', label: 'Precio menor a mayor' },
  { value: '-price', label: 'Precio mayor a menor' },
]

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { categories } = useCategories()
  const { brands } = useBrands()

  const query = useMemo<ProductQueryParams>(
    () => ({
      search: searchParams.get('search') ?? '',
      category: searchParams.get('category') ?? '',
      brand: searchParams.get('brand') ?? '',
      product_type: (searchParams.get('product_type') as ProductQueryParams['product_type']) ?? '',
      condition: (searchParams.get('condition') as ProductQueryParams['condition']) ?? '',
      stock_status: (searchParams.get('stock_status') as ProductQueryParams['stock_status']) ?? '',
      ordering: (searchParams.get('ordering') as ProductQueryParams['ordering']) ?? '',
    }),
    [searchParams],
  )

  const { products, loading, error } = useCatalogProducts(query)

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value) next.delete(key)
    else next.set(key, value)
    setSearchParams(next)
  }

  return (
    <Layout>
      <section className="simple-page catalog-page">
        <div className="section-heading">
          <h1>Catálogo de productos</h1>
          <p>Explora maquinaria, repuestos y servicios listos para tu operación. Filtra y cotiza en minutos.</p>
        </div>

        <div className="catalog-filters">
          <input
            type="search"
            placeholder="Buscar por nombre, modelo o SKU"
            value={query.search ?? ''}
            onChange={(event) => updateFilter('search', event.target.value)}
          />
          <select value={query.category ?? ''} onChange={(event) => updateFilter('category', event.target.value)}>
            <option value="">Todas las categorías</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
          <select value={query.brand ?? ''} onChange={(event) => updateFilter('brand', event.target.value)}>
            <option value="">Todas las marcas</option>
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>
                {brand.name}
              </option>
            ))}
          </select>
          <select value={query.product_type ?? ''} onChange={(event) => updateFilter('product_type', event.target.value)}>
            <option value="">Todos los tipos</option>
            <option value="machinery">Maquinaria</option>
            <option value="spare_part">Repuesto</option>
            <option value="service">Servicio</option>
            <option value="other">Otro</option>
          </select>
          <select value={query.condition ?? ''} onChange={(event) => updateFilter('condition', event.target.value)}>
            <option value="">Todas las condiciones</option>
            <option value="new">Nuevo</option>
            <option value="used">Usado</option>
            <option value="refurbished">Reacondicionado</option>
            <option value="not_applicable">No aplica</option>
          </select>
          <select value={query.stock_status ?? ''} onChange={(event) => updateFilter('stock_status', event.target.value)}>
            <option value="">Todo el stock</option>
            <option value="available">Disponible</option>
            <option value="on_request">A pedido</option>
            <option value="reserved">Reservado</option>
            <option value="sold">Vendido</option>
          </select>
          <select value={query.ordering ?? ''} onChange={(event) => updateFilter('ordering', event.target.value)}>
            <option value="">Orden predeterminado</option>
            {ORDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {loading ? <p className="ui-note">Cargando catálogo...</p> : null}
        {!loading && error ? <p className="ui-note ui-note--error">{error} Usa el menú lateral o vuelve más tarde.</p> : null}
        {!loading && !error && products.length === 0 ? <p className="ui-note">No hay productos con estos filtros.</p> : null}

        {!loading && !error && products.length > 0 ? (
          <div className="featured-products__grid">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        ) : null}
      </section>
    </Layout>
  )
}
