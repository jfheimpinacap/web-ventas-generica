import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { useAdminUser } from '../../components/admin/ProtectedRoute'
import { getCommercialQuotes } from '../../services/commercialQuotesApi'
import { isSeller } from '../../services/authApi'
import type { CommercialQuoteSummary } from '../../types/commercialQuote'
import { money } from '../../utils/commercialQuote'

export function CommercialQuotesPage() {
  const user=useAdminUser(); const [items,setItems]=useState<CommercialQuoteSummary[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState('')
  useEffect(()=>{getCommercialQuotes().then(r=>setItems(r.results)).catch(()=>setError('No se pudieron cargar las cotizaciones comerciales.')).finally(()=>setLoading(false))},[])
  return <AdminLayout><AdminPageHeader title="Cotizaciones comerciales" actions={isSeller(user??undefined)?<Link className="button" to="/admin/cotizaciones/nueva">Crear cotización</Link>:undefined}/>{loading?<p>Cargando…</p>:null}{error?<p className="ui-note ui-note--error">{error}</p>:null}<div className="admin-table-wrapper"><table className="admin-table"><thead><tr><th>Folio</th><th>Cliente</th><th>Estado</th><th>Vendedor</th><th>Total</th><th /></tr></thead><tbody>{items.map(q=><tr key={q.id}><td>{q.folio??'Pendiente'}</td><td>{q.customer_business_name}</td><td>{q.status==='Issued'?'Emitida':'Borrador'}</td><td>{q.seller_code}</td><td>{money(q.total_amount,q.currency)}</td><td><Link to={`/admin/cotizaciones/${q.id}/editar`}>{q.status==='Issued'?'Ver':'Editar'}</Link></td></tr>)}</tbody></table></div></AdminLayout>
}
