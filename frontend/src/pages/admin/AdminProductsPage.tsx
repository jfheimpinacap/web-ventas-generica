import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { deleteProduct, getAdminProducts } from '../../services/adminApi'
import type { ProductListItem } from '../../types/catalog'


const PRODUCT_FILTERS_STORAGE_KEY = 'admin-products-filters'

type ProductFiltersState = {
  search: string
  categoryFilter: string
  brandFilter: string
  typeFilter: string
  conditionFilter: string
  stockFilter: string
  publishedFilter: string
}

const defaultFilters: ProductFiltersState = {
  search: '',
  categoryFilter: '',
  brandFilter: '',
  typeFilter: '',
  conditionFilter: '',
  stockFilter: '',
  publishedFilter: '',
}

function readStoredFilters(): ProductFiltersState {
  if (typeof window === 'undefined') return defaultFilters

  const rawFilters = window.sessionStorage.getItem(PRODUCT_FILTERS_STORAGE_KEY)
  if (!rawFilters) return defaultFilters

  try {
    const parsed = JSON.parse(rawFilters) as Partial<ProductFiltersState>
    return {
      search: parsed.search ?? '',
      categoryFilter: parsed.categoryFilter ?? '',
      brandFilter: parsed.brandFilter ?? '',
      typeFilter: parsed.typeFilter ?? '',
      conditionFilter: parsed.conditionFilter ?? '',
      stockFilter: parsed.stockFilter ?? '',
      publishedFilter: parsed.publishedFilter ?? '',
    }
  } catch {
    return defaultFilters
  }
}

function stockLabel(stock: ProductListItem['stock_status']) {
  if (stock === 'available') return 'Disponible'
  if (stock === 'on_request') return 'A pedido'
  if (stock === 'reserved') return 'Reservado'
  return 'Vendido'
}

export function AdminProductsPage() {
  const [searchParams] = useSearchParams()
  const [products, setProducts] = useState<ProductListItem[]>([])
  const storedFilters = useMemo(() => readStoredFilters(), [])
  const [search, setSearch] = useState(storedFilters.search)
  const [categoryFilter, setCategoryFilter] = useState(storedFilters.categoryFilter)
  const [brandFilter, setBrandFilter] = useState(storedFilters.brandFilter)
  const [typeFilter, setTypeFilter] = useState(storedFilters.typeFilter)
  const [conditionFilter, setConditionFilter] = useState(storedFilters.conditionFilter)
  const [stockFilter, setStockFilter] = useState(storedFilters.stockFilter)
  const [publishedFilter, setPublishedFilter] = useState(storedFilters.publishedFilter)
  const [loading, setLoading] = useState(false)
  const [hasLoadedProducts, setHasLoadedProducts] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(
    searchParams.get('status') === 'created'
      ? 'Producto creado correctamente.'
      : searchParams.get('status') === 'updated'
        ? 'Producto actualizado correctamente.'
        : null,
  )

  const loadProducts = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getAdminProducts()
      setProducts(response)
      setHasLoadedProducts(true)
    } catch {
      setError('No se pudo cargar el listado de productos.')
    } finally {
      setLoading(false)
    }
  }

  const hasCriteria = useMemo(
    () => [search, categoryFilter, brandFilter, typeFilter, conditionFilter, stockFilter, publishedFilter].some((value) => value.trim() !== ''),
    [search, categoryFilter, brandFilter, typeFilter, conditionFilter, stockFilter, publishedFilter],
  )

  useEffect(() => {
    if (hasCriteria && !hasLoadedProducts && !loading) {
      void loadProducts()
    }
  }, [hasCriteria, hasLoadedProducts, loading])

  useEffect(() => {
    if (typeof window === 'undefined') return

    const filtersToStore: ProductFiltersState = {
      search,
      categoryFilter,
      brandFilter,
      typeFilter,
      conditionFilter,
      stockFilter,
      publishedFilter,
    }

    window.sessionStorage.setItem(PRODUCT_FILTERS_STORAGE_KEY, JSON.stringify(filtersToStore))
  }, [search, categoryFilter, brandFilter, typeFilter, conditionFilter, stockFilter, publishedFilter])

  const categoryOptions = useMemo(() => Array.from(new Set(products.map((p) => p.category?.name).filter(Boolean))), [products])
  const brandOptions = useMemo(() => Array.from(new Set(products.map((p) => p.brand?.name).filter(Boolean))), [products])

  const filteredProducts = useMemo(() => {
    if (!hasCriteria) return []

    const query = search.trim().toLowerCase()

    return products.filter((product) => {
      const matchesText =
        !query ||
        [product.name, product.slug, product.brand?.name ?? '', product.category?.name ?? '']
        .join(' ')
        .toLowerCase()
        .includes(query)

      const matchesCategory = !categoryFilter || product.category?.name === categoryFilter
      const matchesBrand = !brandFilter || product.brand?.name === brandFilter
      const matchesType = !typeFilter || product.product_type === typeFilter
      const matchesCondition = !conditionFilter || product.condition === conditionFilter
      const matchesStock = !stockFilter || product.stock_status === stockFilter
      const matchesPublished =
        !publishedFilter ||
        (publishedFilter === 'published' ? product.is_published : !product.is_published)

      return matchesText && matchesCategory && matchesBrand && matchesType && matchesCondition && matchesStock && matchesPublished
    })
  }, [products, search, hasCriteria, categoryFilter, brandFilter, typeFilter, conditionFilter, stockFilter, publishedFilter])

  const clearFilters = () => {
    setSearch('')
    setCategoryFilter('')
    setBrandFilter('')
    setTypeFilter('')
    setConditionFilter('')
    setStockFilter('')
    setPublishedFilter('')
  }

  const handleDelete = async (product: ProductListItem) => {
    const confirmed = window.confirm(`¿Eliminar "${product.name}"? Esta acción no se puede deshacer.`)
    if (!confirmed) return

    try {
      await deleteProduct(product.slug)
      setSuccess(`Producto "${product.name}" eliminado.`)
      await loadProducts()
    } catch {
      setError('No se pudo eliminar el producto.')
    }
  }

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Productos</h1>
        <div className="admin-list-toolbar">
          <input
            className="admin-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por nombre, marca, categoría o SKU"
          />
          <Link className="btn btn--accent" to="/admin/productos/nuevo">
            Nuevo producto
          </Link>
        </div>
      </div>
      <div className="admin-filter-strip">
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="">Tipo</option>
          <option value="machinery">Maquinaria</option>
          <option value="spare_part">Repuesto</option>
          <option value="service">Servicio</option>
          <option value="other">Otro</option>
        </select>
        <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
          <option value="">Categoría</option>
          {categoryOptions.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        <select value={brandFilter} onChange={(event) => setBrandFilter(event.target.value)}>
          <option value="">Marca</option>
          {brandOptions.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        <select value={conditionFilter} onChange={(event) => setConditionFilter(event.target.value)}>
          <option value="">Condición</option>
          <option value="new">Nuevo</option>
          <option value="used">Usado</option>
          <option value="refurbished">Reacondicionado</option>
          <option value="not_applicable">No aplica</option>
        </select>
        <select value={stockFilter} onChange={(event) => setStockFilter(event.target.value)}>
          <option value="">Stock</option>
          <option value="available">Disponible</option>
          <option value="on_request">A pedido</option>
          <option value="reserved">Reservado</option>
          <option value="sold">Vendido</option>
        </select>
        <select value={publishedFilter} onChange={(event) => setPublishedFilter(event.target.value)}>
          <option value="">Publicación</option>
          <option value="published">Publicado</option>
          <option value="unpublished">No publicado</option>
        </select>
        <button type="button" className="btn btn--ghost" onClick={clearFilters}>
          Limpiar filtros
        </button>
      </div>

      {loading ? <p className="ui-note">Cargando productos...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {success ? <p className="ui-note ui-note--success">{success}</p> : null}

      {!loading && !error && !hasCriteria ? (
        <p className="ui-note">Usa el buscador o selecciona filtros para ver productos.</p>
      ) : null}

      {!loading && !error && hasCriteria && filteredProducts.length === 0 ? (
        <p className="ui-note">No hay productos para los criterios seleccionados.</p>
      ) : null}

      {!loading && !error && filteredProducts.length > 0 ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Categoría</th>
                <th>Marca</th>
                <th>Tipo</th>
                <th>Condición</th>
                <th>Stock</th>
                <th>Destacado</th>
                <th>Publicado</th>
                <th>Actualizado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map((product) => (
                <tr key={product.id}>
                  <td>{product.name}</td>
                  <td>{product.category?.name ?? '-'}</td>
                  <td>{product.brand?.name ?? '-'}</td>
                  <td>{product.product_type}</td>
                  <td>{product.condition}</td>
                  <td>
                    <span className="badge badge--stock">{stockLabel(product.stock_status)}</span>
                  </td>
                  <td>
                    <span className={`badge ${product.is_featured ? 'badge--ok' : 'badge--muted'}`}>
                      {product.is_featured ? 'Sí' : 'No'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${product.is_published ? 'badge--ok' : 'badge--muted'}`}>
                      {product.is_published ? 'Sí' : 'No'}
                    </span>
                  </td>
                  <td>{product.updated_at ? new Date(product.updated_at).toLocaleDateString() : '-'}</td>
                  <td>
                    <Link className="table-action" to={`/admin/productos/${product.slug}/editar`}>
                      Editar
                    </Link>{' '}
                    <button type="button" className="table-action table-action--button" onClick={() => void handleDelete(product)}>
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  )
}
