import { Link, Outlet } from 'react-router-dom'
import { can, type AppPermission } from '../../auth/permissions'
import { AdminLayout } from './AdminLayout'
import { useAdminUser } from './ProtectedRoute'

export function PermissionRoute({ permission, backTo }: { permission: AppPermission; backTo: string }) {
  const user = useAdminUser() ?? undefined
  if (can(user, permission)) return <Outlet />
  return <AdminLayout><section className="admin-block" role="alert" aria-labelledby="permission-denied-title"><h1 id="permission-denied-title">Acceso denegado</h1><p>No tienes permiso para realizar esta acción.</p><Link className="btn btn--secondary" to={backTo}>Volver al listado</Link></section></AdminLayout>
}
