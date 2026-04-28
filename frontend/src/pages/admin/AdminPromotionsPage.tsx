import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { deletePromotion, getAdminPromotions } from '../../services/adminApi'
import type { Promotion } from '../../types/catalog'

export function AdminPromotionsPage() {
  const [items, setItems] = useState<Promotion[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setItems(await getAdminPromotions())
    } catch {
      setError('No se pudieron cargar las promociones.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const filtered = useMemo(() => items.filter((item) => `${item.title} ${item.subtitle}`.toLowerCase().includes(search.toLowerCase())), [items, search])

  const handleDelete = async (item: Promotion) => {
    if (!window.confirm(`¿Eliminar promoción "${item.title}"?`)) return
    await deletePromotion(item.id)
    await load()
  }

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Promociones</h1>
        <Link className="btn btn--accent" to="/admin/promociones/nueva">Nueva promoción</Link>
      </div>
      <input className="admin-search" placeholder="Buscar promoción" value={search} onChange={(e) => setSearch(e.target.value)} />
      {loading ? <p className="ui-note">Cargando promociones...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}
      {!loading && !error && filtered.length === 0 ? <p className="ui-note">Sin promociones.</p> : null}
      {!loading && !error && filtered.length > 0 ? (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead><tr><th>Título</th><th>Producto</th><th>Activa</th><th>Orden</th><th>Inicio</th><th>Fin</th><th>Acciones</th></tr></thead>
            <tbody>{filtered.map((item) => <tr key={item.id}><td>{item.title}</td><td>{item.product?.name ?? '-'}</td><td><span className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}>{item.is_active ? 'Sí' : 'No'}</span></td><td>{item.order}</td><td>{item.starts_at ? new Date(item.starts_at).toLocaleDateString() : '-'}</td><td>{item.ends_at ? new Date(item.ends_at).toLocaleDateString() : '-'}</td><td><Link className="table-action" to={`/admin/promociones/${item.id}/editar`}>Editar</Link>{' '}<button type="button" className="table-action table-action--button" onClick={() => void handleDelete(item)}>Eliminar</button></td></tr>)}</tbody>
          </table>
        </div>
      ) : null}
    </AdminLayout>
  )
}
