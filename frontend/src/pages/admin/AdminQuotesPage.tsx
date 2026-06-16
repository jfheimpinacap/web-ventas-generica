import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getSafeApiErrorMessage } from '../../services/api'
import { getAdminQuotes, updateQuote } from '../../services/adminApi'
import {
  PREFERRED_CONTACT_METHOD_LABELS,
  QUOTE_STATUS_LABELS,
  type QuoteRequestAdmin,
  type QuoteStatus,
} from '../../types/catalog'

const formatQuoteFolio = (id: number) => `COT-${String(id).padStart(6, '0')}`

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
  const [ordering, setOrdering] = useState<
    '-created_at' | 'created_at' | '-updated_at' | 'status'
  >('-created_at')
  const [updatingId, setUpdatingId] = useState<number | null>(null)

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
      } catch (error) {
        setError(
          getSafeApiErrorMessage(
            error,
            'No se pudieron cargar las cotizaciones.',
          ),
        )
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [ordering, search, statusFilter])

  const summary = useMemo(() => {
    return STATUS_OPTIONS.reduce(
      (acc, current) => ({
        ...acc,
        [current.value]: items.filter((item) => item.status === current.value)
          .length,
      }),
      { new: 0, contacted: 0, quoted: 0, closed: 0, discarded: 0 } as Record<
        QuoteStatus,
        number
      >,
    )
  }, [items])


  const onStatusChange = async (item: QuoteRequestAdmin, nextStatus: QuoteStatus) => {
    if (item.status === nextStatus) return

    try {
      setUpdatingId(item.id)
      setError(null)
      const updated = await updateQuote(item.id, { status: nextStatus })
      setItems((current) => current.map((candidate) => (candidate.id === item.id ? updated : candidate)))
    } catch (error) {
      setError(getSafeApiErrorMessage(error, 'No se pudo actualizar el estado de la cotización.'))
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <AdminLayout>
      <h1>Cotizaciones</h1>

      <div className="admin-inline-form">
        <label>
          Estado
          <select
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as QuoteStatus | '')
            }
          >
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
            onChange={(event) =>
              setOrdering(
                event.target.value as
                  | '-created_at'
                  | 'created_at'
                  | '-updated_at'
                  | 'status',
              )
            }
          >
            <option value="-created_at">Más recientes</option>
            <option value="created_at">Más antiguas</option>
            <option value="-updated_at">Última actualización</option>
            <option value="status">Estado</option>
          </select>
        </label>
      </div>

      <div className="quote-summary-cards" aria-label="Resumen de estados de cotización">
        <article className="quote-summary-card">
          <p>Total</p>
          <strong>{items.length}</strong>
        </article>
        {STATUS_OPTIONS.map((status) => (
          <article key={status.value} className="quote-summary-card">
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
                <th>Folio</th>
                <th>Fecha</th>
                <th>Cliente</th>
                <th>Producto / asunto</th>
                <th>Email / teléfono</th>
                <th>Estado</th>
                <th>Cambiar estado</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <p className="ui-note">Aún no hay solicitudes de cotización.</p>
                  </td>
                </tr>
              ) : null}
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <span className="quote-folio">{formatQuoteFolio(item.id)}</span>
                  </td>
                  <td>{new Date(item.created_at).toLocaleDateString()}</td>
                  <td>
                    <Link className="quote-customer-link" to={`/admin/cotizaciones/${item.id}`}>
                      {item.customer_name}
                    </Link>
                    <span className="admin-table__muted">
                      {item.company_name || item.city || 'Sin empresa registrada'}
                    </span>
                  </td>
                  <td>
                    <strong>{item.product_name || (item.product ? `Producto #${item.product}` : 'Solicitud general')}</strong>
                    <span className="admin-table__muted">{item.message}</span>
                  </td>
                  <td>
                    <span>{item.customer_email || '-'}</span>
                    <span className="admin-table__muted">{item.customer_phone || '-'}</span>
                    <span className="admin-table__muted">
                      {item.preferred_contact_method ? PREFERRED_CONTACT_METHOD_LABELS[item.preferred_contact_method] : 'Sin preferencia'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge quote-status quote-status--${item.status}`}>
                      {QUOTE_STATUS_LABELS[item.status]}
                    </span>
                  </td>
                  <td>
                    <select
                      className="quote-status-select"
                      value={item.status}
                      onChange={(event) => void onStatusChange(item, event.target.value as QuoteStatus)}
                      disabled={updatingId === item.id}
                      aria-label={`Cambiar estado de cotización ${item.id}`}
                    >
                      {Object.entries(QUOTE_STATUS_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
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
