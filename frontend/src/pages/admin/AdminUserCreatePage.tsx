import { useNavigate } from 'react-router-dom'
import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { EMPTY_USER_FORM, UserForm } from '../../components/admin/UserForm'
import { createManagedUser, type ManagedUserWrite } from '../../services/adminUsersApi'
import { ApiError } from '../../services/api'
import { clearSession } from '../../services/authApi'
import { useToast } from '../../toasts/ToastContext'
import { ADMIN_TOASTS } from '../../toasts/adminToastMessages'

export function AdminUserCreatePage() {
  const navigate = useNavigate(); const toast = useToast(); const back = () => navigate('/admin/usuarios')
  const submit = async (payload: ManagedUserWrite, clearSensitive: () => void) => {
    try { await createManagedUser(payload) } catch (error) { if (error instanceof ApiError && error.status === 401) { clearSensitive(); clearSession(); navigate('/login', { replace: true }); return } toast.error(ADMIN_TOASTS.user.create.error); throw error }
    clearSensitive(); toast.success(ADMIN_TOASTS.user.create.success); navigate('/admin/usuarios', { replace: true })
  }
  return <AdminLayout><AdminEditorLayout title="Crear usuario" onBack={back} headerActions={<p className="admin-user-header-description">Crea una cuenta y define su rol y acceso al panel.</p>} form={<UserForm initialFields={EMPTY_USER_FORM} passwordRequired mode="create" onSubmit={submit} onCancel={back} />} /></AdminLayout>
}
