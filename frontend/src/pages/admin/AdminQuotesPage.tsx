import { useEffect, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getAdminQuoteRequests } from '../../services/adminApi'
import type { QuoteRequest } from '../../types/catalog'

export function AdminQuotesPage() {
  const [items, setItems] = useState<QuoteRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const response = await getAdminQuoteRequests()
        setItems(response)
      } catch {
        setError('No se pudieron cargar las cotizaciones.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [])

  return (
    <AdminLayout>
      <h1>Cotizaciones</h1>
      {loading ? <p className="ui-note">Cargando cotizaciones...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && !error ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Nombre</th>
                <th>Teléfono</th>
                <th>Email</th>
                <th>Estado</th>
                <th>Mensaje</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{new Date(item.created_at).toLocaleDateString()}</td>
                  <td>{item.product_name ?? item.product ?? '-'}</td>
                  <td>{item.customer_name}</td>
                  <td>{item.customer_phone}</td>
                  <td>{item.customer_email || '-'}</td>
                  <td>{item.status}</td>
                  <td>{item.message.slice(0, 60)}{item.message.length > 60 ? '…' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  )
}
