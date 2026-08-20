import { useCallback, useEffect, useRef, useState } from 'react'
import { getAdminProducts } from '../../services/adminApi'
import type { ProductListItem } from '../../types/catalog'

type SearchState = 'initial' | 'loading' | 'results' | 'empty' | 'error'

export function ProductSearchModal({ onSelect, onManual, onClose }: { onSelect: (p: ProductListItem) => void; onManual: () => void; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<ProductListItem[]>([])
  const [selected, setSelected] = useState<ProductListItem | null>(null)
  const [state, setState] = useState<SearchState>('initial')
  const inputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const openerRef = useRef<HTMLElement | null>(document.activeElement instanceof HTMLElement ? document.activeElement : null)
  const requestSequence = useRef(0)
  const confirming = useRef(false)

  const close = useCallback(() => onClose(), [onClose])

  useEffect(() => {
    inputRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'Tab' || !panelRef.current) return
      const controls = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), [tabindex]:not([tabindex="-1"])'))
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      requestSequence.current += 1
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
      window.setTimeout(() => openerRef.current?.focus(), 0)
    }
  }, [close])

  useEffect(() => {
    const term = query.trim()
    setSelected(null)
    if (term.length < 2) {
      requestSequence.current += 1
      setState('initial')
      return
    }
    const sequence = ++requestSequence.current
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setState('loading')
      getAdminProducts({ search: term, page_size: 20 }, controller.signal)
        .then((products) => {
          if (controller.signal.aborted || sequence !== requestSequence.current) return
          const results = products.slice(0, 20)
          setItems(results)
          setState(results.length ? 'results' : 'empty')
        })
        .catch(() => {
          if (!controller.signal.aborted && sequence === requestSequence.current) setState('error')
        })
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [query])

  const confirmSelection = () => {
    if (!selected || confirming.current || state !== 'results') return
    confirming.current = true
    onSelect(selected)
  }

  return (
    <div className="commercial-modal" role="presentation">
      <div ref={panelRef} className="commercial-modal__panel product-search-modal" role="dialog" aria-modal="true" aria-labelledby="product-modal-title">
        <header className="product-search-modal__header">
          <h2 id="product-modal-title">Buscar producto</h2>
          <button className="product-search-modal__close" type="button" onClick={close} aria-label="Cerrar búsqueda de producto">×</button>
        </header>
        <label className="product-search-modal__search" htmlFor="product-search">
          Buscar en el catálogo
          <input ref={inputRef} id="product-search" type="search" maxLength={200} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre, marca o modelo" autoComplete="off" />
        </label>
        <div className="product-search-modal__status" aria-live="polite">
          {state === 'initial' ? 'Escribe al menos 2 caracteres para buscar.' : null}
          {state === 'loading' ? 'Buscando productos…' : null}
          {state === 'empty' ? 'No se encontraron productos, repuestos o servicios.' : null}
          {state === 'error' ? 'No fue posible realizar la búsqueda. Intenta nuevamente.' : null}
        </div>
        {items.length > 0 && state !== 'error' ? (
          <div className="product-search-modal__table-wrap">
            <table className="product-search-modal__table">
              <thead><tr><th>Nombre</th><th>Marca</th><th>Modelo</th><th>Selección</th></tr></thead>
              <tbody>{items.map((product) => {
                const service = product.product_type === 'service'
                const isSelected = selected?.id === product.id
                return (
                  <tr key={product.id} className={isSelected ? 'is-selected' : undefined} onClick={() => state === 'results' && setSelected(product)}>
                    <td>{product.name}</td>
                    <td>{service ? '—' : product.brand?.name || 'Sin marca'}</td>
                    <td>{service ? '—' : product.model || 'Sin modelo'}</td>
                    <td><input type="radio" name="catalog-product" checked={isSelected} disabled={state !== 'results'} onChange={() => setSelected(product)} aria-label={`Seleccionar ${product.name}`} /></td>
                  </tr>
                )
              })}</tbody>
            </table>
          </div>
        ) : null}
        <footer className="product-search-modal__actions">
          <button className="btn btn--secondary" type="button" onClick={onManual}>Ingresar producto manualmente</button>
          <button className="btn btn--accent" type="button" disabled={!selected || state !== 'results'} onClick={confirmSelection}>Aceptar</button>
        </footer>
      </div>
    </div>
  )
}
