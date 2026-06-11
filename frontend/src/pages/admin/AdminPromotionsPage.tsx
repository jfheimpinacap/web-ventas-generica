import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getSafeApiErrorMessage } from '../../services/api'
import { deletePromotion, getAdminPromotions } from '../../services/adminApi'
import type { Promotion } from '../../types/catalog'

export function AdminPromotionsPage() {
  const [items, setItems] = useState<Promotion[]>([])
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<'active' | 'inactive' | 'all'>('active')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setItems(await getAdminPromotions())
    } catch (error) {
      setError(
        getSafeApiErrorMessage(
          error,
          'No se pudieron cargar las ofertas de Hero.',
        ),
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
        const matchesSearch = `${item.title} ${item.subtitle}`
          .toLowerCase()
          .includes(search.toLowerCase())

        return matchesStatus && matchesSearch
      }),
    [items, search, activeFilter],
  )
  const handleDelete = async (item: Promotion) => {
    if (!window.confirm(`¿Eliminar oferta "${item.title}"?`)) return
    try {
      await deletePromotion(item.id)
      await load()
    } catch (error) {
      setError(
        getSafeApiErrorMessage(error, 'No se pudo eliminar la oferta de Hero.'),
      )
    }
  }

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Ofertas en Hero section</h1>
        <div className="admin-list-toolbar">
          <input
            className="admin-search"
            placeholder="Buscar oferta"
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
          <Link className="btn btn--accent" to="/admin/ofertas-hero/nueva">
            Nueva oferta
          </Link>
        </div>
      </div>
      {loading ? <p className="ui-note">Cargando ofertas...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {!loading && !error && filtered.length === 0 ? (
        <p className="ui-note">Sin ofertas.</p>
      ) : null}
      {!loading && !error && filtered.length > 0 ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Título</th>
                <th>Producto</th>
                <th>Activa</th>
                <th>Orden</th>
                <th>Inicio</th>
                <th>Fin</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id}>
                  <td>{item.title}</td>
                  <td>{item.product?.name ?? '-'}</td>
                  <td>
                    <span
                      className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}
                    >
                      {item.is_active ? 'Sí' : 'No'}
                    </span>
                  </td>
                  <td>{item.order}</td>
                  <td>
                    {item.starts_at
                      ? new Date(item.starts_at).toLocaleDateString()
                      : '-'}
                  </td>
                  <td>
                    {item.ends_at
                      ? new Date(item.ends_at).toLocaleDateString()
                      : '-'}
                  </td>
                  <td>
                    <Link
                      className="table-action"
                      to={`/admin/ofertas-hero/${item.id}/editar`}
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
