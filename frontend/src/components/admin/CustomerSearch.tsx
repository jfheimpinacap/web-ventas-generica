import { useEffect, useRef, useState } from 'react'
import { searchCustomers } from '../../services/commercialQuotesApi'
import type { CustomerProfile } from '../../types/commercialQuote'

export function CustomerSearch({ disabled, selectedId, onSelect, onUnlink }: { disabled: boolean; selectedId: number | null; onSelect: (value: CustomerProfile) => void; onUnlink: () => void }) {
  const [query, setQuery] = useState(''); const [results, setResults] = useState<CustomerProfile[]>([]); const [loading, setLoading] = useState(false); const [searched, setSearched] = useState(false)
  const request = useRef(0)
  useEffect(() => {
    const value = query.trim(); if (value.length < 2 || value.length > 200) { setResults([]); setSearched(false); return }
    const current = ++request.current; const controller = new AbortController()
    const timer = window.setTimeout(async () => { setLoading(true); try { const response = await searchCustomers(value, controller.signal); if (current === request.current) { setResults(response.results); setSearched(true) } } catch { if (!controller.signal.aborted && current === request.current) { setResults([]); setSearched(true) } } finally { if (current === request.current) setLoading(false) } }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [query])
  return <section className="commercial-section commercial-customer-search"><div className="commercial-section__heading"><h2>Buscar cliente</h2>{selectedId ? <button className="btn btn--ghost" type="button" onClick={onUnlink} disabled={disabled}>Desvincular perfil</button> : null}</div>
    <input id="customer-search" aria-label="Buscar por razón social o RUT" placeholder="Buscar por razón social o RUT" value={query} maxLength={200} disabled={disabled} onChange={e => setQuery(e.target.value)} aria-controls="customer-results" />
    {loading ? <p className="ui-note">Buscando clientes…</p> : null}<ul id="customer-results" className="customer-results">{results.map(customer => <li key={customer.id}><button type="button" onClick={() => { onSelect(customer); setQuery(customer.business_name); setResults([]) }}><strong>{customer.business_name}</strong><span>{customer.rut}</span></button></li>)}</ul>
    {searched && !loading && results.length === 0 ? <p className="ui-note">No se encontraron clientes. Puede continuar con ingreso manual.</p> : null}
  </section>
}
