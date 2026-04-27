import { useEffect, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getAdminPromotions } from '../../services/adminApi'
import type { Promotion } from '../../types/catalog'

export function AdminPromotionsPage() {
  const [items, setItems] = useState<Promotion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const response = await getAdminPromotions()
        setItems(response)
      } catch {
        setError('No se pudieron cargar las promociones.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [])

  return (
    <AdminLayout>
      <h1>Promociones</h1>
      {loading ? <p className="ui-note">Cargando promociones...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && !error ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Título</th>
                <th>Producto</th>
                <th>Activo</th>
                <th>Orden</th>
                <th>Inicio</th>
                <th>Fin</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.title}</td>
                  <td>{item.product?.name ?? '-'}</td>
                  <td>{item.is_active ? 'Sí' : 'No'}</td>
                  <td>{item.order}</td>
                  <td>{item.starts_at ? new Date(item.starts_at).toLocaleDateString() : '-'}</td>
                  <td>{item.ends_at ? new Date(item.ends_at).toLocaleDateString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  )
}
