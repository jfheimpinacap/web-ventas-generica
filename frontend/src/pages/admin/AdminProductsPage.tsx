import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { deleteProduct, getAdminProducts } from '../../services/adminApi'
import type { ProductListItem } from '../../types/catalog'

function stockLabel(stock: ProductListItem['stock_status']) {
  if (stock === 'available') return 'Disponible'
  if (stock === 'on_request') return 'A pedido'
  if (stock === 'reserved') return 'Reservado'
  return 'Vendido'
}

export function AdminProductsPage() {
  const [searchParams] = useSearchParams()
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
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
      setError(null)
      const response = await getAdminProducts()
      setProducts(response)
    } catch {
      setError('No se pudo cargar el listado de productos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadProducts()
  }, [])

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return products

    return products.filter((product) => {
      return [product.name, product.slug, product.brand?.name ?? '', product.category?.name ?? '']
        .join(' ')
        .toLowerCase()
        .includes(query)
    })
  }, [products, search])

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
        <Link className="btn btn--accent" to="/admin/productos/nuevo">
          Nuevo producto
        </Link>
      </div>

      <input
        className="admin-search"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Buscar por nombre, marca, categoría o SKU"
      />

      {loading ? <p className="ui-note">Cargando productos...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {success ? <p className="ui-note ui-note--success">{success}</p> : null}

      {!loading && !error && filteredProducts.length === 0 ? (
        <p className="ui-note">No hay productos para mostrar.</p>
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
                    {product.is_published ? (
                      <Link className="table-action" to={`/producto/${product.slug}`}>
                        Ver público
                      </Link>
                    ) : null}{' '}
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
