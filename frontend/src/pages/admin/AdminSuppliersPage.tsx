import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { deleteSupplier, getAdminSuppliers } from '../../services/adminApi'
import type { SupplierSummary } from '../../types/catalog'

export function AdminSuppliersPage() {
  const [items, setItems] = useState<SupplierSummary[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setItems(await getAdminSuppliers())
    } catch {
      setError('No se pudieron cargar los proveedores.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const filtered = useMemo(() => items.filter((item) => `${item.name} ${item.contact_name} ${item.email}`.toLowerCase().includes(search.toLowerCase())), [items, search])

  const handleDelete = async (item: SupplierSummary) => {
    if (!window.confirm(`¿Eliminar proveedor "${item.name}"?`)) return
    await deleteSupplier(item.id)
    await load()
  }

  return <AdminLayout>
    <div className="admin-products-header"><h1>Proveedores</h1><Link className="btn btn--accent" to="/admin/proveedores/nuevo">Nuevo proveedor</Link></div>
    <input className="admin-search" placeholder="Buscar proveedor" value={search} onChange={(e) => setSearch(e.target.value)} />
    {loading ? <p className="ui-note">Cargando proveedores...</p> : null}
    {error ? <p className="ui-note ui-note--error">{error}</p> : null}
    {!loading && !error ? <div className="admin-table-wrapper"><table className="admin-table"><thead><tr><th>Nombre</th><th>Contacto</th><th>Teléfono</th><th>Email</th><th>Activo</th><th>Acciones</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.contact_name || '-'}</td><td>{item.phone || '-'}</td><td>{item.email || '-'}</td><td><span className={`badge ${item.is_active ? 'badge--ok' : 'badge--muted'}`}>{item.is_active ? 'Sí' : 'No'}</span></td><td><Link className="table-action" to={`/admin/proveedores/${item.id}/editar`}>Editar</Link>{' '}<button type="button" className="table-action table-action--button" onClick={() => void handleDelete(item)}>Eliminar</button></td></tr>)}</tbody></table></div> : null}
  </AdminLayout>
}
