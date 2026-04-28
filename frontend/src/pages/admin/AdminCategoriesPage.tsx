import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { deleteCategory, getAdminCategories } from '../../services/adminApi'
import type { Category } from '../../types/catalog'

export function AdminCategoriesPage() {
  const [items, setItems] = useState<Category[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      const data = await getAdminCategories()
      setItems(data)
    } catch {
      setError('No se pudieron cargar las categorías.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const filtered = useMemo(() => items.filter((i) => `${i.name} ${i.slug}`.toLowerCase().includes(search.toLowerCase())), [items, search])

  const handleDelete = async (item: Category) => {
    if (!window.confirm(`¿Eliminar categoría "${item.name}"?`)) return
    try {
      await deleteCategory(item.id)
      setSuccess('Categoría eliminada.')
      await load()
    } catch {
      setError('No se pudo eliminar la categoría.')
    }
  }

  return <AdminLayout>
    <div className="admin-products-header"><h1>Categorías</h1><Link to="/admin/categorias/nueva" className="btn btn--accent">Nueva categoría</Link></div>
    <input className="admin-search" placeholder="Buscar por nombre o slug" value={search} onChange={(e) => setSearch(e.target.value)} />
    {loading ? <p className="ui-note">Cargando categorías...</p> : null}
    {error ? <p className="ui-note ui-note--error">{error}</p> : null}
    {success ? <p className="ui-note ui-note--success">{success}</p> : null}
    {!loading && !error && filtered.length === 0 ? <p className="ui-note">Sin categorías.</p> : null}
    {!loading && !error && filtered.length > 0 ? <div className="admin-table-wrapper"><table className="admin-table"><thead><tr><th>Nombre</th><th>Padre</th><th>Activa</th><th>Orden</th><th>Acciones</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id}><td>{item.name}</td><td>{items.find((i) => i.id === item.parent)?.name ?? '-'}</td><td><span className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}>{item.is_active ? 'Sí' : 'No'}</span></td><td>{item.order}</td><td><Link className="table-action" to={`/admin/categorias/${item.id}/editar`}>Editar</Link>{' '}<button type="button" className="table-action table-action--button" onClick={() => void handleDelete(item)}>Eliminar</button></td></tr>)}</tbody></table></div> : null}
  </AdminLayout>
}
