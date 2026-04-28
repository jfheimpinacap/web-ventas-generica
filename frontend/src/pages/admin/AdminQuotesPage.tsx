import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getAdminQuotes } from '../../services/adminApi'
import {
  PREFERRED_CONTACT_METHOD_LABELS,
  QUOTE_STATUS_LABELS,
  type QuoteRequestAdmin,
  type QuoteStatus,
} from '../../types/catalog'

const STATUS_OPTIONS: Array<{ value: QuoteStatus; label: string }> = [
  { value: 'new', label: 'Nuevas' },
  { value: 'contacted', label: 'Contactadas' },
  { value: 'quoted', label: 'Cotizadas' },
  { value: 'closed', label: 'Cerradas' },
  { value: 'discarded', label: 'Descartadas' },
]

export function AdminQuotesPage() {
  const [items, setItems] = useState<QuoteRequestAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<QuoteStatus | ''>('')
  const [search, setSearch] = useState('')
  const [ordering, setOrdering] = useState<'-created_at' | 'created_at' | '-updated_at' | 'status'>('-created_at')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await getAdminQuotes({
          status: statusFilter,
          search,
          ordering,
        })
        setItems(response)
      } catch {
        setError('No se pudieron cargar las cotizaciones.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [ordering, search, statusFilter])

  const summary = useMemo(() => {
    return STATUS_OPTIONS.reduce(
      (acc, current) => ({ ...acc, [current.value]: items.filter((item) => item.status === current.value).length }),
      { new: 0, contacted: 0, quoted: 0, closed: 0, discarded: 0 } as Record<QuoteStatus, number>,
    )
  }, [items])

  return (
    <AdminLayout>
      <h1>Cotizaciones</h1>

      <div className="admin-inline-form">
        <label>
          Estado
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as QuoteStatus | '')}>
            <option value="">Todos</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Búsqueda
          <input
            placeholder="Nombre, email, teléfono, empresa..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label>
          Orden
          <select
            value={ordering}
            onChange={(event) => setOrdering(event.target.value as '-created_at' | 'created_at' | '-updated_at' | 'status')}
          >
            <option value="-created_at">Más recientes</option>
            <option value="created_at">Más antiguas</option>
            <option value="-updated_at">Última actualización</option>
            <option value="status">Estado</option>
          </select>
        </label>
      </div>

      <div className="admin-cards">
        {STATUS_OPTIONS.map((status) => (
          <article key={status.value} className="admin-card">
            <p>{status.label}</p>
            <strong>{summary[status.value]}</strong>
          </article>
        ))}
      </div>

      {loading ? <p className="ui-note">Cargando cotizaciones...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && !error ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Cliente</th>
                <th>Teléfono</th>
                <th>Email</th>
                <th>Empresa</th>
                <th>Ciudad</th>
                <th>Método preferido</th>
                <th>Estado</th>
                <th>Acciones</th>
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
                  <td>{item.company_name || '-'}</td>
                  <td>{item.city || '-'}</td>
                  <td>
                    {item.preferred_contact_method
                      ? PREFERRED_CONTACT_METHOD_LABELS[item.preferred_contact_method]
                      : '-'}
                  </td>
                  <td>
                    <span className={`badge quote-status quote-status--${item.status}`}>{QUOTE_STATUS_LABELS[item.status]}</span>
                  </td>
                  <td>
                    <Link className="table-action" to={`/admin/cotizaciones/${item.id}`}>
                      Ver / Editar
                    </Link>
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
