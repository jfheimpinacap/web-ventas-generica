import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { getSafeApiErrorMessage } from '../../services/api'
import { deleteBrand, getAdminBrands } from '../../services/adminApi'
import type { Brand } from '../../types/catalog'

export function AdminBrandsPage() {
  const [items, setItems] = useState<Brand[]>([])
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<'active' | 'inactive' | 'all'>('active')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setItems(await getAdminBrands())
    } catch (error) {
      setError(
        getSafeApiErrorMessage(error, 'No se pudieron cargar las marcas.'),
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
        const matchesSearch = `${item.name} ${item.slug}`
          .toLowerCase()
          .includes(search.toLowerCase())

        return matchesStatus && matchesSearch
      }),
    [items, search, activeFilter],
  )

  const handleDelete = async (item: Brand) => {
    if (!window.confirm(`¿Eliminar marca "${item.name}"?`)) return
    try {
      await deleteBrand(item.id)
      await load()
    } catch (error) {
      setError(getSafeApiErrorMessage(error, 'No se pudo eliminar la marca.'))
    }
  }

  return (
    <AdminLayout>
      <AdminPageHeader title="Marcas" actions={
        <div className="admin-page-header__toolbar">
          <Link className="btn btn--accent" to="/admin/marcas/nueva">Nueva marca</Link>
          <input
            className="admin-search"
            placeholder="Buscar marca"
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
      {loading ? <p className="ui-note">Cargando marcas...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {!loading && !error ? (
        <div className="admin-table-wrapper admin-table-wrapper--compact admin-compact-list--brands">
          <table className="admin-table admin-table--compact">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Activa</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>
                    <span
                      className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}
                    >
                      {item.is_active ? 'Sí' : 'No'}
                    </span>
                  </td>
                  <td>
                    <Link
                      className="table-action"
                      to={`/admin/marcas/${item.id}/editar`}
                    >
                      Editar
                    </Link>{' '}
                    <button
                      type="button"
                      className="table-action table-action--button"
                      onClick={() => void handleDelete(item)}
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  )
}
