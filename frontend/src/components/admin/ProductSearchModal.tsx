import { useEffect, useRef, useState } from 'react'
import { getAdminProducts } from '../../services/adminApi'
import type { ProductListItem } from '../../types/catalog'

export function ProductSearchModal({ onSelect, onManual, onClose }: { onSelect: (p: ProductListItem) => void; onManual: () => void; onClose: () => void }) {
  const [query, setQuery] = useState(''); const [items, setItems] = useState<ProductListItem[]>([]); const [loading, setLoading] = useState(false); const input = useRef<HTMLInputElement>(null)
  useEffect(() => { input.current?.focus(); const close = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close) }, [onClose])
  const search = async () => { setLoading(true); try { setItems(await getAdminProducts({ search: query })) } finally { setLoading(false) } }
  return <div className="commercial-modal" role="dialog" aria-modal="true" aria-labelledby="product-modal-title"><div className="commercial-modal__panel"><div className="commercial-section__heading"><h2 id="product-modal-title">Buscar producto</h2><button type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
    <form onSubmit={e => { e.preventDefault(); void search() }}><label htmlFor="product-search">Nombre, marca o modelo</label><div className="commercial-inline"><input ref={input} id="product-search" value={query} onChange={e => setQuery(e.target.value)} /><button className="btn btn--accent" type="submit">Buscar</button></div></form>
    {loading ? <p>Cargando productos…</p> : null}<ul className="product-results">{items.map(p => <li key={p.id}><div><strong>{p.name}</strong><span>{p.brand?.name ?? 'Sin marca'} · {p.model ?? 'Sin modelo'}</span></div><button type="button" onClick={() => onSelect(p)}>Seleccionar</button></li>)}</ul>{!loading && items.length === 0 ? <p className="ui-note">Sin resultados.</p> : null}
    <button className="btn btn--secondary" type="button" onClick={onManual}>Ingresar producto manualmente</button></div></div>
}
