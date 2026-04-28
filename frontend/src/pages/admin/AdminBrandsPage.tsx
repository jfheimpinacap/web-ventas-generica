import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { deleteBrand, getAdminBrands } from '../../services/adminApi'
import type { Brand } from '../../types/catalog'

export function AdminBrandsPage() {
  const [items, setItems] = useState<Brand[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setItems(await getAdminBrands())
    } catch {
      setError('No se pudieron cargar las marcas.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const filtered = useMemo(() => items.filter((item) => `${item.name} ${item.slug}`.toLowerCase().includes(search.toLowerCase())), [items, search])

  const handleDelete = async (item: Brand) => {
    if (!window.confirm(`¿Eliminar marca "${item.name}"?`)) return
    await deleteBrand(item.id)
    await load()
  }

  return <AdminLayout>
    <div className="admin-products-header"><h1>Marcas</h1><Link className="btn btn--accent" to="/admin/marcas/nueva">Nueva marca</Link></div>
    <input className="admin-search" placeholder="Buscar marca" value={search} onChange={(e) => setSearch(e.target.value)} />
    {loading ? <p className="ui-note">Cargando marcas...</p> : null}
    {error ? <p className="ui-note ui-note--error">{error}</p> : null}
    {!loading && !error ? <div className="admin-table-wrapper"><table className="admin-table"><thead><tr><th>Nombre</th><th>Activa</th><th>Acciones</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id}><td>{item.name}</td><td><span className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}>{item.is_active ? 'Sí' : 'No'}</span></td><td><Link className="table-action" to={`/admin/marcas/${item.id}/editar`}>Editar</Link>{' '}<button type="button" className="table-action table-action--button" onClick={() => void handleDelete(item)}>Eliminar</button></td></tr>)}</tbody></table></div> : null}
  </AdminLayout>
}
