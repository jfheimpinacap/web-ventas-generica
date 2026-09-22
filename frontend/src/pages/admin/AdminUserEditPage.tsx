import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { useAdminUser } from '../../components/admin/ProtectedRoute'
import { UserForm, type UserFormFields } from '../../components/admin/UserForm'
import { ApiError } from '../../services/api'
import { clearSession } from '../../services/authApi'
import { getManagedUser, updateManagedUser, type ManagedUser, type ManagedUserWrite } from '../../services/adminUsersApi'
import { useToast } from '../../toasts/ToastContext'
import { ADMIN_TOASTS } from '../../toasts/adminToastMessages'

function formatDate(value: string | null) { if (!value) return 'Nunca'; const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).format(date) }
export function AdminUserEditPage() {
  const { userId } = useParams<{ userId: string }>(); const navigate = useNavigate(); const toast = useToast(); const session = useAdminUser(); const id = userId && /^\d+$/.test(userId) ? Number(userId) : null
  const [user, setUser] = useState<ManagedUser | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(false); const [reload, setReload] = useState(0); const load = useCallback(() => setReload((value) => value + 1), [])
  useEffect(() => { if (!id) { setError(true); setLoading(false); return } const controller = new AbortController(); setLoading(true); getManagedUser(id, controller.signal).then(setUser).catch((reason) => { if (reason instanceof DOMException && reason.name === 'AbortError') return; if (reason instanceof ApiError && reason.status === 401) { clearSession(); navigate('/login', { replace: true }); return } setError(true) }).finally(() => { if (!controller.signal.aborted) setLoading(false) }); return () => controller.abort() }, [id, navigate, reload])
  const back = () => navigate('/admin/usuarios'); if (loading) return <AdminLayout><p className="ui-note">Cargando usuario…</p></AdminLayout>
  if (!user || error) return <AdminLayout><div className="admin-users-empty" role="alert"><h1>No fue posible cargar el usuario</h1><button className="btn btn--secondary" onClick={back}>Volver</button><button className="btn btn--accent" onClick={load}>Reintentar</button></div></AdminLayout>
  const currentSession = session?.id === user.id; const reactivating = !user.is_active
  const initial: UserFormFields = { username: user.username, email: user.email ?? '', fullName: user.full_name ?? '', phone: user.phone ?? '', password: '', confirmation: '', role: user.role, permissions: user.permissions }
  const submit = async (payload: ManagedUserWrite, clearSensitive: () => void) => { try { await updateManagedUser(user.id, payload) } catch (reason) { if (reason instanceof ApiError && reason.status === 401) { clearSensitive(); clearSession(); navigate('/login', { replace: true }); return } toast.error(reactivating ? ADMIN_TOASTS.user.reactivate.error : ADMIN_TOASTS.user.update.error); throw reason } clearSensitive(); if (currentSession && payload.password) { toast.success(ADMIN_TOASTS.user.password.success); clearSession(); navigate('/login', { replace: true }); return } toast.success(reactivating ? ADMIN_TOASTS.user.reactivate.success : ADMIN_TOASTS.user.update.success); navigate('/admin/usuarios', { replace: true }) }
  const summary = <section className="admin-user-summary admin-block"><dl><div><dt>Rol</dt><dd>{user.role === 'support_admin' ? 'Superadministrador' : 'Vendedor'}</dd></div>{user.seller_code ? <div><dt>Código vendedor</dt><dd>{user.seller_code}</dd></div> : null}<div><dt>Estado</dt><dd>{user.is_active ? 'Activo' : 'Inactivo'}</dd></div><div><dt>Creación</dt><dd>{formatDate(user.created_at)}</dd></div><div><dt>Último acceso</dt><dd>{formatDate(user.last_login_at)}</dd></div></dl></section>
  return <AdminLayout><AdminEditorLayout title={reactivating ? 'Reactivar usuario' : 'Editar usuario'} onBack={back} sidebar={summary} headerActions={reactivating ? <p className="ui-note ui-note--warning">Para reactivar esta cuenta debes establecer una contraseña nueva.</p> : undefined} form={<UserForm initialFields={initial} passwordRequired={reactivating} mode={reactivating ? 'reactivate' : 'edit'} currentSession={currentSession} onSubmit={submit} onCancel={back} />} /></AdminLayout>
}
