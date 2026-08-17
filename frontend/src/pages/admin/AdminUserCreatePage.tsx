import { useNavigate } from 'react-router-dom'
import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { EMPTY_SELLER_FORM, SellerUserForm } from '../../components/admin/SellerUserForm'
import { createSellerUser, type SellerUserWrite } from '../../services/adminUsersApi'
import { ApiError } from '../../services/api'
import { clearSession } from '../../services/authApi'

export function AdminUserCreatePage() {
  const navigate = useNavigate()
  const back = () => navigate('/admin/usuarios')
  const submit = async (payload: SellerUserWrite, clearSensitive: () => void) => {
    let created
    try { created = await createSellerUser(payload) }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) { clearSession(); navigate('/login', { replace: true }); return }
      throw error
    }
    clearSensitive()
    navigate('/admin/usuarios', { replace: true, state: { notice: `Vendedor creado correctamente. Código: ${created.seller_code ?? 'Código no disponible'}.` } })
  }
  return <AdminLayout><AdminEditorLayout title="Crear vendedor" onBack={back} headerActions={<p className="admin-user-header-description">Crea una cuenta para acceder al panel de ventas.</p>} form={<SellerUserForm initialFields={EMPTY_SELLER_FORM} passwordRequired mode="create" onSubmit={submit} onCancel={back} />} /></AdminLayout>
}
