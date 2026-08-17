import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { AdminIcon } from '../../components/admin/AdminIcon'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { safeSellerMutationError } from '../../components/admin/SellerUserForm'
import { ApiError } from '../../services/api'
import { clearSession } from '../../services/authApi'
import { deactivateSellerUser, listSellerUsers, type SellerUser } from '../../services/adminUsersApi'

type StatusFilter = 'all' | 'active' | 'inactive'
type LocationState = { notice?: string }

function formatDate(value: string | null) {
  if (!value) return 'Nunca'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function AdminUsersPage() {
  const navigate = useNavigate(); const location = useLocation()
  const [users, setUsers] = useState<SellerUser[]>([]); const [search, setSearch] = useState(''); const [debouncedSearch, setDebouncedSearch] = useState(''); const [filter, setFilter] = useState<StatusFilter>('all')
  const [loading, setLoading] = useState(true); const [loadError, setLoadError] = useState(false); const [deactivating, setDeactivating] = useState<SellerUser | null>(null); const [mutationError, setMutationError] = useState<string | null>(null); const [submitting, setSubmitting] = useState(false); const [reloadKey, setReloadKey] = useState(0)
  const [notice, setNotice] = useState<string | null>(() => { const state = location.state as LocationState | null; return state?.notice ?? null })
  const openerRef = useRef<HTMLElement | null>(null); const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => { if ((location.state as LocationState | null)?.notice) navigate(location.pathname, { replace: true, state: null }) }, [location.pathname, location.state, navigate])
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 350); return () => window.clearTimeout(timer) }, [search])
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setLoadError(false)
    listSellerUsers({ search: debouncedSearch || undefined, is_active: filter === 'all' ? undefined : filter === 'active' }, controller.signal).then(setUsers).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (error instanceof ApiError && error.status === 401) { clearSession(); navigate('/login', { replace: true }); return }
      setLoadError(true)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [debouncedSearch, filter, navigate, reloadKey])
  useEffect(() => {
    if (!deactivating) return
    cancelRef.current?.focus()
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !submitting) closeDialog() }
    document.addEventListener('keydown', escape); return () => document.removeEventListener('keydown', escape)
  }, [deactivating, submitting])
  const closeDialog = () => { setDeactivating(null); setMutationError(null); window.setTimeout(() => openerRef.current?.focus(), 0) }
  const openDeactivate = (user: SellerUser, opener: HTMLElement) => { openerRef.current = opener; setMutationError(null); setDeactivating(user) }
  const confirmDeactivate = async () => {
    if (!deactivating || submitting) return
    setSubmitting(true); setMutationError(null)
    try { await deactivateSellerUser(deactivating.id); setNotice('Cuenta desactivada correctamente.'); closeDialog(); setReloadKey((value) => value + 1) }
    catch (error) { setMutationError(safeSellerMutationError(error)) }
    finally { setSubmitting(false) }
  }
  const hasCriteria = Boolean(debouncedSearch) || filter !== 'all'
  return <AdminLayout>
    <AdminPageHeader title="Usuarios vendedores" description="Administra las cuentas que pueden acceder al panel de ventas." actions={<button className="btn btn--accent" type="button" onClick={() => navigate('/admin/usuarios/nuevo')}><AdminIcon name="plus" /> Crear vendedor</button>} />
    <div className="admin-users-toolbar" role="search"><label htmlFor="seller-search">Buscar vendedores</label><div className="admin-users-search"><input id="seller-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por usuario, código, correo o nombre" />{search ? <button type="button" className="btn btn--secondary" onClick={() => setSearch('')}>Limpiar</button> : null}</div><label htmlFor="seller-status">Estado</label><select id="seller-status" value={filter} onChange={(event) => setFilter(event.target.value as StatusFilter)}><option value="all">Todos</option><option value="active">Activos</option><option value="inactive">Inactivos</option></select></div>
    <div className="admin-users-announcer" aria-live="polite">{notice ? <p className="ui-note ui-note--success">{notice}</p> : null}{loading ? <p className="ui-note">Cargando usuarios…</p> : null}</div>
    {loadError ? <div className="admin-users-empty" role="alert"><p>No fue posible cargar los usuarios. Intenta nuevamente.</p><button className="btn btn--secondary" type="button" onClick={() => setReloadKey((value) => value + 1)}>Reintentar</button></div> : null}
    {!loading && !loadError && users.length === 0 ? <p className="admin-users-empty">{hasCriteria ? 'No se encontraron vendedores con los criterios seleccionados.' : 'Todavía no existen cuentas de vendedores.'}</p> : null}
    {!loadError && users.length > 0 ? <div className="admin-users-list">{users.map((user) => <article className="admin-user-card" key={user.id}><div className="admin-user-card__identity"><strong>{user.username}</strong><span>{user.full_name || 'Sin nombre'}</span><span>{user.email || 'Sin correo'}</span><span className="admin-user-card__code"><b>Código vendedor:</b> {user.seller_code ?? 'Código no disponible'}</span></div><div><span className={`badge ${user.is_active ? 'badge--ok' : 'badge--muted'}`}>{user.is_active ? 'Activo' : 'Inactivo'}</span></div><dl><div><dt>Último acceso</dt><dd>{formatDate(user.last_login_at)}</dd></div><div><dt>Creación</dt><dd>{formatDate(user.created_at)}</dd></div></dl><div className="admin-table-actions">{user.is_active ? <><button className="table-action table-action--button" type="button" onClick={() => navigate(`/admin/usuarios/${user.id}/editar`)}><AdminIcon name="edit" />Editar</button><button className="table-action table-action--button table-action--danger" type="button" onClick={(event) => openDeactivate(user, event.currentTarget)}>Desactivar</button></> : <button className="table-action table-action--button" type="button" onClick={() => navigate(`/admin/usuarios/${user.id}/editar`)}>Reactivar</button>}</div></article>)}</div> : null}
    {deactivating ? <div className="admin-user-modal" role="presentation"><section className="admin-user-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="deactivate-title" aria-describedby="deactivate-description"><h2 id="deactivate-title">Desactivar cuenta</h2><p id="deactivate-description">La cuenta de {deactivating.username} quedará inactiva, no se eliminará físicamente y sus registros históricos se conservarán. Se cerrarán sus sesiones y la contraseña anterior dejará de funcionar.</p>{mutationError ? <p className="ui-note ui-note--error" role="alert">{mutationError}</p> : null}<div className="admin-user-form__actions"><button ref={cancelRef} className="btn btn--secondary" type="button" onClick={closeDialog} disabled={submitting}>Cancelar</button><button className="btn btn--danger" type="button" onClick={() => void confirmDeactivate()} disabled={submitting}>{submitting ? 'Desactivando…' : 'Desactivar cuenta'}</button></div></section></div> : null}
  </AdminLayout>
}
