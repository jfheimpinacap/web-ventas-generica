import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { useAdminUser } from '../../components/admin/ProtectedRoute'
import { isSeller } from '../../services/authApi'
import { getSafeApiErrorMessage } from '../../services/api'
import { getAdminQuotes, updateQuote } from '../../services/adminApi'
import { getCommercialQuotes } from '../../services/commercialQuotesApi'
import type { CommercialQuoteSummary } from '../../types/commercialQuote'
import { money } from '../../utils/commercialQuote'
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

function QuoteRequestsView() {
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
    <>
      <div className="admin-page-header__toolbar quote-request-filters">
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

      {loading ? <p className="ui-note">Cargando solicitudes recibidas...</p> : null}
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
    </>
  )
}

function GeneratedQuotesView() {
  const [items, setItems] = useState<CommercialQuoteSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getCommercialQuotes()
      .then((response) => setItems(response.results))
      .catch(() => setError('No se pudieron cargar las cotizaciones generadas.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="ui-note">Cargando cotizaciones generadas...</p>
  if (error) return <p className="ui-note ui-note--error">{error}</p>

  return (
    <div className="admin-table-wrapper" tabIndex={0} aria-label="Tabla de cotizaciones generadas con desplazamiento horizontal">
      <table className="admin-table commercial-quotes-table">
        <thead><tr><th>Folio</th><th>Cliente</th><th>Estado</th><th>Vendedor</th><th>Total</th><th>Acción</th></tr></thead>
        <tbody>
          {items.length === 0 ? <tr><td colSpan={6}><p className="ui-note">Aún no hay cotizaciones generadas.</p></td></tr> : null}
          {items.map((quote) => (
            <tr key={quote.id}>
              <td>{quote.folio ?? 'Pendiente'}</td>
              <td>{quote.customer_business_name}</td>
              <td>{quote.status === 'Issued' ? 'Emitida' : 'Borrador'}</td>
              <td>{quote.seller_code}</td>
              <td>{money(quote.total_amount, quote.currency)}</td>
              <td><Link to={`/admin/cotizaciones/${quote.id}/editar`}>{quote.status === 'Issued' ? 'Ver' : 'Editar'}</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function AdminQuotesPage() {
  const currentUser = useAdminUser()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedView = searchParams.get('vista')
  const activeView = requestedView === 'generadas' ? 'generadas' : 'solicitudes'

  useEffect(() => {
    if (requestedView && requestedView !== 'generadas') setSearchParams({}, { replace: true })
  }, [requestedView, setSearchParams])

  return (
    <AdminLayout>
      <AdminPageHeader
        title="Cotizaciones"
        actions={isSeller(currentUser ?? undefined) ? <Link className="button" to="/admin/cotizaciones/nueva">Crear cotización</Link> : undefined}
      />
      <nav className="quote-view-tabs" aria-label="Vistas de cotizaciones" role="tablist">
        <Link className={activeView === 'solicitudes' ? 'quote-view-tab quote-view-tab--active' : 'quote-view-tab'} to="/admin/cotizaciones" role="tab" aria-selected={activeView === 'solicitudes'}>Solicitudes recibidas</Link>
        <Link className={activeView === 'generadas' ? 'quote-view-tab quote-view-tab--active' : 'quote-view-tab'} to="/admin/cotizaciones?vista=generadas" role="tab" aria-selected={activeView === 'generadas'}>Cotizaciones generadas</Link>
      </nav>
      <section className="quote-view-panel" role="tabpanel" aria-label={activeView === 'solicitudes' ? 'Solicitudes recibidas' : 'Cotizaciones generadas'}>
        {activeView === 'solicitudes' ? <QuoteRequestsView /> : <GeneratedQuotesView />}
      </section>
    </AdminLayout>
  )
}
