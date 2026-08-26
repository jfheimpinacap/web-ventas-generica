import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useSystemDialog } from '../../context/SystemDialogContext'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminIcon } from '../../components/admin/AdminIcon'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { getSafeApiErrorMessage } from '../../services/api'
import { deleteCategory, getAdminCategories } from '../../services/adminApi'
import type { Category } from '../../types/catalog'

export function AdminCategoriesPage() {
  const { requestConfirmation } = useSystemDialog()
  const [items, setItems] = useState<Category[]>([])
  const [selectedRootId, setSelectedRootId] = useState<number | null>(null)
  const [activeFilter, setActiveFilter] = useState<'active' | 'inactive' | 'all'>('active')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      const data = await getAdminCategories()
      setItems(data)
    } catch (error) {
      setError(getSafeApiErrorMessage(error, 'No se pudieron cargar las categorías.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const matchesStatus = (item: Category) =>
    activeFilter === 'all' || (activeFilter === 'active' ? item.is_active : !item.is_active)

  const rootCategories = useMemo(
    () => items.filter((item) => item.parent === null && matchesStatus(item)).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)),
    [activeFilter, items],
  )

  useEffect(() => {
    if (selectedRootId && rootCategories.some((item) => item.id === selectedRootId)) return
    setSelectedRootId(rootCategories[0]?.id ?? null)
  }, [rootCategories, selectedRootId])

  const selectedRoot = items.find((item) => item.id === selectedRootId) ?? null
  const subcategories = useMemo(
    () => items.filter((item) => item.parent === selectedRootId && matchesStatus(item)).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)),
    [activeFilter, items, selectedRootId],
  )

  const handleDelete = async (item: Category) => {
    if (!await requestConfirmation({ title: 'Eliminar categoría', message: '¿Seguro que deseas borrar esta categoría? Esta acción no se puede deshacer.', confirmLabel: 'Eliminar', variant: 'danger' })) return
    try {
      await deleteCategory(item.id)
      setSuccess('Categoría borrada.')
      await load()
    } catch (error) {
      setError(getSafeApiErrorMessage(error, 'No se pudo borrar la categoría.'))
    }
  }

  const renderStatus = (item: Category) => (
    <span className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}>{item.is_active ? 'Activa' : 'Inactiva'}</span>
  )

  return (
    <AdminLayout>
      <AdminPageHeader title="Categorías" actions={
        <div className="admin-page-header__toolbar">
          <Link to="/admin/categorias/nueva" className="btn btn--accent">Crear categoría principal</Link>
          <select className="admin-search" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as 'active' | 'inactive' | 'all')} aria-label="Filtrar por estado">
            <option value="active">Solo activas</option>
            <option value="inactive">Solo inactivas</option>
            <option value="all">Todas</option>
          </select>
        </div>
      } />

      {loading ? <p className="ui-note">Cargando categorías...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {success ? <p className="ui-note ui-note--success">{success}</p> : null}

      {!loading && !error ? (
        <div className="admin-categories-lists">
          <section className="admin-compact-list admin-compact-list--categories">
            <h3>Categorías principales</h3>
            {rootCategories.length === 0 ? <p className="ui-note">Sin categorías principales.</p> : null}
            <div className="admin-table-wrapper admin-table-wrapper--compact">
              <table className="admin-table admin-table--compact">
                <thead><tr><th scope="col">Nombre</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead>
                <tbody>{rootCategories.map((item) => (
                  <tr key={item.id} className={item.id === selectedRootId ? 'admin-table__row--selected' : ''}>
                    <td><button type="button" className="admin-category-selector" onClick={() => setSelectedRootId(item.id)}>{item.name}</button></td>
                    <td>{renderStatus(item)}</td>
                    <td><div className="admin-table-actions"><Link className="table-action" to={`/admin/categorias/${item.id}/editar`}><AdminIcon name="edit" />Editar</Link><button type="button" className="table-action table-action--button table-action--danger" onClick={() => void handleDelete(item)}><AdminIcon name="trash" />Borrar</button></div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>

          <section className="admin-compact-list admin-compact-list--categories">
            <AdminPageHeader className="admin-page-header--section" title={<>Subcategorías{selectedRoot ? ` de ${selectedRoot.name}` : ''}</>} actions={selectedRoot ? <Link to={`/admin/categorias/nueva?parent=${selectedRoot.id}`} className="btn btn--accent">Crear subcategoría</Link> : undefined} />
            {!selectedRoot ? <p className="ui-note">Selecciona una categoría principal para administrar sus subcategorías.</p> : null}
            {selectedRoot && subcategories.length === 0 ? <p className="ui-note">Sin subcategorías para esta categoría principal.</p> : null}
            {selectedRoot && subcategories.length > 0 ? (
              <div className="admin-table-wrapper admin-table-wrapper--compact"><table className="admin-table admin-table--compact"><thead><tr><th scope="col">Nombre</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead><tbody>{subcategories.map((item) => (
                <tr key={item.id}><td>{item.name}</td><td>{renderStatus(item)}</td><td><div className="admin-table-actions"><Link className="table-action" to={`/admin/categorias/${item.id}/editar`}><AdminIcon name="edit" />Editar</Link><button type="button" className="table-action table-action--button table-action--danger" onClick={() => void handleDelete(item)}><AdminIcon name="trash" />Borrar</button></div></td></tr>
              ))}</tbody></table></div>
            ) : null}
          </section>
        </div>
      ) : null}
    </AdminLayout>
  )
}
