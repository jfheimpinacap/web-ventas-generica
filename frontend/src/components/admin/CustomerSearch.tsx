import { type FormEvent, useEffect, useRef, useState } from 'react'
import { AdminIcon } from './AdminIcon'
import { searchCustomers } from '../../services/commercialQuotesApi'
import type { CustomerProfile } from '../../types/commercialQuote'

export function CustomerSearch({ disabled, selectedId, onSelect, onUnlink }: { disabled: boolean; selectedId: number | null; onSelect: (value: CustomerProfile) => void; onUnlink: () => void }) {
  const [query, setQuery] = useState(''); const [results, setResults] = useState<CustomerProfile[]>([]); const [loading, setLoading] = useState(false); const [searched, setSearched] = useState(false)
  const request = useRef(0); const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  const submit = async (event: FormEvent) => {
    event.preventDefault(); const value = query.trim()
    if (disabled || loading || value.length < 2 || value.length > 200) return
    controller.current?.abort(); const current = ++request.current; const nextController = new AbortController(); controller.current = nextController; setLoading(true)
    try { const response = await searchCustomers(value, nextController.signal); if (current === request.current) { setResults(response.results); setSearched(true) } }
    catch { if (!nextController.signal.aborted && current === request.current) { setResults([]); setSearched(true) } }
    finally { if (current === request.current) setLoading(false) }
  }
  return <div className="commercial-customer-search"><div className="commercial-customer-search__bar"><form onSubmit={submit} role="search"><input id="customer-search" aria-label="Buscar por razón social o RUT" placeholder="Buscar por razón social o RUT" value={query} maxLength={200} disabled={disabled} onChange={e => { setQuery(e.target.value); setSearched(false) }} aria-controls="customer-results" /><button className="btn btn--accent admin-icon-button" type="submit" disabled={disabled || loading} title="Buscar cliente" aria-label="Buscar cliente"><AdminIcon name="search" /></button></form>{selectedId ? <button className="btn btn--ghost" type="button" onClick={onUnlink} disabled={disabled}>Desvincular perfil</button> : null}</div>
    {loading ? <p className="ui-note">Buscando clientes…</p> : null}<ul id="customer-results" className="customer-results">{results.map(customer => <li key={customer.id}><button type="button" onClick={() => { onSelect(customer); setQuery(customer.business_name); setResults([]); setSearched(false) }}><strong>{customer.business_name}</strong><span>{customer.rut}</span></button></li>)}</ul>
    {searched && !loading && results.length === 0 ? <p className="ui-note">No se encontraron clientes. Puede continuar con ingreso manual.</p> : null}
  </div>
}
