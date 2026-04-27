import { useEffect, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getAdminProducts } from '../../services/adminApi'
import type { ProductListItem } from '../../types/catalog'

export function AdminProductsPage() {
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
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

    void loadProducts()
  }, [])

  return (
    <AdminLayout>
      <h1>Productos</h1>
      {loading ? <p className="ui-note">Cargando productos...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && !error ? (
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
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td>{product.name}</td>
                  <td>{product.category?.name ?? '-'}</td>
                  <td>{product.brand?.name ?? '-'}</td>
                  <td>{product.product_type}</td>
                  <td>{product.condition}</td>
                  <td>{product.stock_status}</td>
                  <td>{product.is_featured ? 'Sí' : 'No'}</td>
                  <td>{product.is_published ? 'Sí' : 'No'}</td>
                  <td>
                    <span className="table-action">Ver</span> / <span className="table-action">Editar</span>
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
