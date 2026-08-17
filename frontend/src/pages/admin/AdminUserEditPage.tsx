import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { SellerUserForm, type SellerFormFields } from '../../components/admin/SellerUserForm'
import { ApiError } from '../../services/api'
import { clearSession } from '../../services/authApi'
import { getSellerUser, updateSellerUser, type SellerUser, type SellerUserWrite } from '../../services/adminUsersApi'

function formatDate(value: string | null) { if (!value) return 'Nunca'; const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).format(date) }

export function AdminUserEditPage() {
  const { userId } = useParams<{ userId: string }>(); const navigate = useNavigate()
  const id = userId && /^\d+$/.test(userId) && Number(userId) > 0 ? Number(userId) : null
  const [user, setUser] = useState<SellerUser | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState<'not-found' | 'forbidden' | 'recoverable' | null>(null); const [reload, setReload] = useState(0)
  const load = useCallback(() => setReload((value) => value + 1), [])
  useEffect(() => {
    if (!id) { setError('not-found'); setLoading(false); return }
    const controller = new AbortController(); setLoading(true); setError(null); setUser(null)
    getSellerUser(id, controller.signal).then(setUser).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      if (reason instanceof ApiError && reason.status === 401) { clearSession(); navigate('/login', { replace: true }); return }
      if (reason instanceof ApiError && reason.status === 404) setError('not-found')
      else if (reason instanceof ApiError && reason.status === 403) setError('forbidden')
      else setError('recoverable')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [id, navigate, reload])
  const back = () => navigate('/admin/usuarios')
  if (loading) return <AdminLayout><p className="ui-note">Cargando vendedor…</p></AdminLayout>
  if (!user || error) return <AdminLayout><div className="admin-users-empty" role="alert"><h1>{error === 'not-found' ? 'Vendedor no encontrado' : error === 'forbidden' ? 'Acceso no disponible' : 'No fue posible cargar el vendedor'}</h1><p>{error === 'not-found' ? 'La cuenta solicitada no existe o ya no está disponible.' : error === 'forbidden' ? 'No tienes permisos para consultar esta información.' : 'Intenta nuevamente.'}</p><div className="admin-user-form__actions"><button className="btn btn--secondary" onClick={back}>Volver a usuarios</button>{error === 'recoverable' ? <button className="btn btn--accent" onClick={load}>Reintentar</button> : null}</div></div></AdminLayout>
  const reactivating = !user.is_active
  const initial: SellerFormFields = { username: user.username, email: user.email ?? '', fullName: user.full_name ?? '', password: '', confirmation: '' }
  const submit = async (payload: SellerUserWrite, clearSensitive: () => void) => {
    try { await updateSellerUser(user.id, payload) }
    catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) { clearSensitive(); clearSession(); navigate('/login', { replace: true }); return }
      throw reason
    }
    clearSensitive(); navigate('/admin/usuarios', { replace: true, state: { notice: reactivating ? 'Vendedor reactivado correctamente.' : 'Vendedor actualizado correctamente.' } })
  }
  const summary = <section className="admin-user-summary admin-block" aria-label="Resumen del vendedor"><dl><div><dt>Código vendedor</dt><dd>{user.seller_code ?? 'Código no disponible'}</dd></div><div><dt>Estado</dt><dd><span className={`badge ${user.is_active ? 'badge--ok' : 'badge--muted'}`}>{user.is_active ? 'Activo' : 'Inactivo'}</span></dd></div><div><dt>Creación</dt><dd>{formatDate(user.created_at)}</dd></div><div><dt>Último acceso</dt><dd>{formatDate(user.last_login_at)}</dd></div></dl></section>
  return <AdminLayout><AdminEditorLayout title={reactivating ? 'Reactivar vendedor' : 'Editar vendedor'} onBack={back} sidebar={summary} headerActions={reactivating ? <p className="ui-note ui-note--warning">Esta cuenta está inactiva. Para reactivarla debes establecer una contraseña nueva.</p> : undefined} form={<SellerUserForm initialFields={initial} passwordRequired={reactivating} mode={reactivating ? 'reactivate' : 'edit'} onSubmit={submit} onCancel={back} />} /></AdminLayout>
}
