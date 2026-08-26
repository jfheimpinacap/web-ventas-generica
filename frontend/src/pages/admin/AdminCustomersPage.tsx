import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminIcon } from '../../components/admin/AdminIcon'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { useSystemDialog } from '../../context/SystemDialogContext'
import { getSafeApiErrorMessage } from '../../services/api'
import { deactivateCustomer, listCustomers, reactivateCustomer, type CustomerStatus } from '../../services/customerProfilesApi'
import type { CustomerProfile } from '../../types/commercialQuote'
import { formatChileanRutInput } from '../../utils/chileanRut'

const PAGE_SIZE = 20
const statusValues = new Set<CustomerStatus>(['active', 'inactive', 'all'])

export function AdminCustomersPage() {
  const { requestConfirmation } = useSystemDialog()
  const [params, setParams] = useSearchParams()
  const search = params.get('search')?.trim() ?? ''
  const rawStatus = params.get('status') as CustomerStatus | null
  const status: CustomerStatus = rawStatus && statusValues.has(rawStatus) ? rawStatus : 'active'
  const rawPage = Number(params.get('page'))
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1
  const [query, setQuery] = useState(search)
  const [data, setData] = useState<{ results: CustomerProfile[]; count: number }>({ results: [], count: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState(params.get('result') === 'created' ? 'Cliente creado correctamente.' : params.get('result') === 'updated' ? 'Cliente actualizado correctamente.' : '')
  const [busy, setBusy] = useState<Set<number>>(new Set())
  const generation = useRef(0)

  const updateParams = useCallback((values: { search?: string; status?: CustomerStatus; page?: number }) => {
    const next = new URLSearchParams()
    const nextSearch = values.search ?? search
    const nextStatus = values.status ?? status
    const nextPage = values.page ?? page
    if (nextSearch) next.set('search', nextSearch)
    if (nextStatus !== 'active') next.set('status', nextStatus)
    if (nextPage > 1) next.set('page', String(nextPage))
    setParams(next)
  }, [page, search, setParams, status])

  const load = useCallback(async () => {
    const current = ++generation.current
    const controller = new AbortController()
    setLoading(true); setError('')
    try {
      const response = await listCustomers({ search, status, page, pageSize: PAGE_SIZE, signal: controller.signal })
      if (current !== generation.current) return
      if (response.count && page > Math.ceil(response.count / PAGE_SIZE)) { updateParams({ page: Math.max(1, Math.ceil(response.count / PAGE_SIZE)) }); return }
      setData(response)
    } catch (caught) {
      if (current === generation.current && !controller.signal.aborted) setError(getSafeApiErrorMessage(caught, 'No se pudo cargar el listado de clientes.'))
    } finally { if (current === generation.current) setLoading(false) }
    return () => controller.abort()
  }, [page, search, status, updateParams])
  useEffect(() => { void load(); return () => { generation.current += 1 } }, [load])
  useEffect(() => setQuery(search), [search])

  const returnQuery = params.toString()
  const mutate = async (customer: CustomerProfile, activate: boolean) => {
    if (busy.has(customer.id)) return
    if (!activate && !await requestConfirmation({ title: 'Desactivar cliente', message: 'El cliente dejará de estar disponible para nuevas cotizaciones, pero sus cotizaciones históricas se conservarán.', confirmLabel: 'Desactivar', cancelLabel: 'Cancelar', variant: 'danger' })) return
    setBusy(current => new Set(current).add(customer.id)); setError(''); setFeedback('')
    try {
      const changed = activate ? await reactivateCustomer(customer.id) : await deactivateCustomer(customer.id)
      if (status === 'all') setData(current => ({ ...current, results: current.results.map(item => item.id === changed.id ? changed : item) }))
      else {
        const remaining = data.results.filter(item => item.id !== customer.id)
        setData(current => ({ results: remaining, count: Math.max(0, current.count - 1) }))
        if (!remaining.length && page > 1) updateParams({ page: page - 1 })
      }
      setFeedback(activate ? 'Cliente reactivado correctamente.' : 'Cliente desactivado correctamente.')
    } catch (caught) { setError(getSafeApiErrorMessage(caught, activate ? 'No se pudo reactivar el cliente.' : 'No se pudo desactivar el cliente.')) }
    finally { setBusy(current => { const next = new Set(current); next.delete(customer.id); return next }) }
  }
  const pages = Math.ceil(data.count / PAGE_SIZE)

  return <AdminLayout>
    <AdminPageHeader title="Clientes" actions={<Link className="btn btn--accent" to={`/admin/clientes/nuevo${returnQuery ? `?return=${encodeURIComponent(returnQuery)}` : ''}`}>Crear cliente</Link>} />
    <section className="admin-customer-filters admin-block" aria-label="Filtros de clientes">
      <form className="admin-inline-search" role="search" onSubmit={event => { event.preventDefault(); updateParams({ search: query.trim(), page: 1 }) }}>
        <label><span>Buscar clientes</span><span className="admin-inline-search"><input className="admin-search" value={query} maxLength={200} placeholder="Razón social o RUT" onChange={event => setQuery(event.target.value)} /><button className="btn btn--accent admin-icon-button" type="submit" aria-label="Buscar clientes" title="Buscar"><AdminIcon name="search" /></button></span></label>
      </form>
      <label>Estado<select className="admin-search admin-customer-status" value={status} onChange={event => updateParams({ status: event.target.value as CustomerStatus, page: 1 })}><option value="all">Todos</option><option value="active">Activos</option><option value="inactive">Inactivos</option></select></label>
    </section>
    {feedback ? <p className="ui-note ui-note--success" role="status" aria-live="polite">{feedback}</p> : null}
    {error ? <div className="ui-note ui-note--error" role="alert"><p>{error}</p><button className="btn btn--secondary" type="button" onClick={() => void load()}>Reintentar</button></div> : null}
    {loading ? <p className="ui-note" aria-busy="true">Cargando clientes…</p> : null}
    {!loading && !error && !data.results.length ? <div className="admin-block"><p>{search || status !== 'all' ? 'No existen coincidencias para los filtros actuales.' : 'No existen clientes registrados.'}</p>{!search && status === 'all' ? <Link className="btn btn--accent" to="/admin/clientes/nuevo">Crear cliente</Link> : null}</div> : null}
    {!loading && !error && data.results.length ? <div className="admin-table-wrapper"><table className="admin-table admin-table--customers"><thead><tr><th>Razón social</th><th>RUT</th><th>Nombre de contacto</th><th>Correo</th><th>Teléfono</th><th>Comuna o ciudad</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{data.results.map(customer => <tr key={customer.id}><td>{customer.businessName}</td><td>{formatChileanRutInput(customer.rut)}</td><td>{customer.contactName || 'No informado'}</td><td className="admin-customer-email">{customer.email || 'No informado'}</td><td>{customer.phone || 'No informado'}</td><td>{customer.cityOrCommune || 'No informado'}</td><td><span className={`badge ${customer.isActive ? 'badge--ok' : 'badge--muted'}`}>{customer.isActive ? 'Activo' : 'Inactivo'}</span></td><td><div className="admin-table-actions"><Link className="table-action" aria-disabled={busy.has(customer.id)} to={`/admin/clientes/${customer.id}/editar${returnQuery ? `?return=${encodeURIComponent(returnQuery)}` : ''}`}><AdminIcon name="edit" />Editar</Link><button className={`table-action table-action--button ${customer.isActive ? 'table-action--danger' : ''}`} type="button" disabled={busy.has(customer.id)} onClick={() => void mutate(customer, !customer.isActive)}>{customer.isActive ? 'Desactivar' : 'Reactivar'}</button></div></td></tr>)}</tbody></table></div> : null}
    {pages > 1 ? <nav className="admin-pagination" aria-label="Paginación de clientes"><button className="btn btn--secondary" disabled={page <= 1 || loading} onClick={() => updateParams({ page: page - 1 })}>Anterior</button><span>Página {page} de {pages}</span><button className="btn btn--secondary" disabled={page >= pages || loading} onClick={() => updateParams({ page: page + 1 })}>Siguiente</button></nav> : null}
  </AdminLayout>
}
