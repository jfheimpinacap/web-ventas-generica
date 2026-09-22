import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useSystemDialog } from '../../context/SystemDialogContext'
import { useToast } from '../../toasts/ToastContext'
import { ADMIN_TOASTS } from '../../toasts/adminToastMessages'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminIcon } from '../../components/admin/AdminIcon'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { getSafeApiErrorMessage } from '../../services/api'
import { deleteSupplier, getAdminSuppliers } from '../../services/adminApi'
import { can, PERMISSIONS } from '../../auth/permissions'
import { useAdminUser } from '../../components/admin/ProtectedRoute'
import type { SupplierSummary } from '../../types/catalog'

export function AdminSuppliersPage() {
  const user = useAdminUser() ?? undefined
  const mayCreate = can(user, PERMISSIONS.suppliersCreate), mayUpdate = can(user, PERMISSIONS.suppliersUpdate), mayDelete = can(user, PERMISSIONS.suppliersDelete)
  const { requestConfirmation } = useSystemDialog()
  const toast = useToast()
  const [items, setItems] = useState<SupplierSummary[]>([])
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<'active' | 'inactive' | 'all'>('active')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setItems(await getAdminSuppliers())
    } catch (error) {
      setError(
        getSafeApiErrorMessage(error, 'No se pudieron cargar los proveedores.'),
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const filtered = useMemo(
    () =>
      items.filter((item) => {
        const matchesStatus =
          activeFilter === 'all' ||
          (activeFilter === 'active' ? item.is_active : !item.is_active)
        const matchesSearch = `${item.name} ${item.contact_name} ${item.email}`
          .toLowerCase()
          .includes(search.toLowerCase())

        return matchesStatus && matchesSearch
      }),
    [items, search, activeFilter],
  )

  const handleDelete = async (item: SupplierSummary) => {
    if (!await requestConfirmation({ title: 'Eliminar proveedor', message: `¿Eliminar proveedor "${item.name}"?`, confirmLabel: 'Eliminar', variant: 'danger' })) return
    try {
      await deleteSupplier(item.id)
      await load()
      toast.success(ADMIN_TOASTS.supplier.deactivate.success)
    } catch (error) {
      toast.error(ADMIN_TOASTS.supplier.deactivate.error)
      setError(
        getSafeApiErrorMessage(error, 'No se pudo eliminar el proveedor.'),
      )
    }
  }

  return (
    <AdminLayout>
      <AdminPageHeader title="Proveedores" actions={
        <div className="admin-page-header__toolbar">
          {mayCreate ? <Link className="btn btn--accent" to="/admin/proveedores/nuevo">Nuevo proveedor</Link> : null}
          <input
            className="admin-search"
            placeholder="Buscar proveedor"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="admin-search"
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value as 'active' | 'inactive' | 'all')}
            aria-label="Filtrar por estado"
          >
            <option value="active">Solo activos</option>
            <option value="inactive">Solo inactivos</option>
            <option value="all">Todos</option>
          </select>
        </div>
      } />
      {loading ? <p className="ui-note">Cargando proveedores...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {!loading && !error ? (
        <div className="admin-table-wrapper admin-table-wrapper--compact admin-compact-list--suppliers">
          <table className="admin-table admin-table--compact admin-table--suppliers">
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Contacto</th>
                <th scope="col">Teléfono</th>
                <th scope="col">Email</th>
                <th scope="col">Activo</th>
                {(mayUpdate || mayDelete) ? <th scope="col">Acciones</th> : null}
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.contact_name || '-'}</td>
                  <td>{item.phone || '-'}</td>
                  <td>{item.email || '-'}</td>
                  <td>
                    <span
                      className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}
                    >
                      {item.is_active ? 'Sí' : 'No'}
                    </span>
                  </td>
                  {(mayUpdate || mayDelete) ? <td>
                    <div className="admin-table-actions">{mayUpdate ? <Link
                      className="table-action"
                      to={`/admin/proveedores/${item.id}/editar`}
                    >
                      <AdminIcon name="edit" />Editar
                    </Link> : null}
                    {mayDelete ? <button
                      type="button"
                      className="table-action table-action--button table-action--danger"
                      onClick={() => void handleDelete(item)}
                    >
                      <AdminIcon name="trash" />Eliminar
                    </button> : null}</div>
                  </td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  )
}
