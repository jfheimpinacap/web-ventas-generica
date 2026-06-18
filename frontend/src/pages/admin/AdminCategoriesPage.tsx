import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getSafeApiErrorMessage } from '../../services/api'
import { deleteCategory, getAdminCategories } from '../../services/adminApi'
import type { Category } from '../../types/catalog'

export function AdminCategoriesPage() {
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
    if (!window.confirm(`¿Inactivar categoría "${item.name}"?`)) return
    try {
      await deleteCategory(item.id)
      setSuccess('Categoría inactivada.')
      await load()
    } catch (error) {
      setError(getSafeApiErrorMessage(error, 'No se pudo inactivar la categoría.'))
    }
  }

  const renderStatus = (item: Category) => (
    <span className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}>{item.is_active ? 'Activa' : 'Inactiva'}</span>
  )

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Categorías</h1>
        <div className="admin-list-toolbar">
          <select className="admin-search" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as 'active' | 'inactive' | 'all')} aria-label="Filtrar por estado">
            <option value="active">Solo activas</option>
            <option value="inactive">Solo inactivas</option>
            <option value="all">Todas</option>
          </select>
          <Link to="/admin/categorias/nueva" className="btn btn--accent">Crear categoría principal</Link>
        </div>
      </div>

      {loading ? <p className="ui-note">Cargando categorías...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {success ? <p className="ui-note ui-note--success">{success}</p> : null}

      {!loading && !error ? (
        <div className="admin-form-panel">
          <section>
            <h3>Categorías principales</h3>
            {rootCategories.length === 0 ? <p className="ui-note">Sin categorías principales.</p> : null}
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead><tr><th>Nombre</th><th>Estado</th><th>Acciones</th></tr></thead>
                <tbody>{rootCategories.map((item) => (
                  <tr key={item.id} className={item.id === selectedRootId ? 'admin-table__row--selected' : ''}>
                    <td><button type="button" className="table-action table-action--button" onClick={() => setSelectedRootId(item.id)}>{item.name}</button></td>
                    <td>{renderStatus(item)}</td>
                    <td><Link className="table-action" to={`/admin/categorias/${item.id}/editar`}>Editar</Link>{' '}<button type="button" className="table-action table-action--button" onClick={() => void handleDelete(item)}>Inactivar</button></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>

          <section>
            <div className="admin-products-header">
              <h3>Subcategorías{selectedRoot ? ` de ${selectedRoot.name}` : ''}</h3>
              {selectedRoot ? <Link to={`/admin/categorias/nueva?parent=${selectedRoot.id}`} className="btn btn--accent">Crear subcategoría</Link> : null}
            </div>
            {!selectedRoot ? <p className="ui-note">Selecciona una categoría principal para administrar sus subcategorías.</p> : null}
            {selectedRoot && subcategories.length === 0 ? <p className="ui-note">Sin subcategorías para esta categoría principal.</p> : null}
            {selectedRoot && subcategories.length > 0 ? (
              <div className="admin-table-wrapper"><table className="admin-table"><thead><tr><th>Nombre</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{subcategories.map((item) => (
                <tr key={item.id}><td>{item.name}</td><td>{renderStatus(item)}</td><td><Link className="table-action" to={`/admin/categorias/${item.id}/editar`}>Editar</Link>{' '}<button type="button" className="table-action table-action--button" onClick={() => void handleDelete(item)}>Inactivar</button></td></tr>
              ))}</tbody></table></div>
            ) : null}
          </section>
        </div>
      ) : null}
    </AdminLayout>
  )
}
