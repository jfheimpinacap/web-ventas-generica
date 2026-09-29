import { useCallback, useEffect, useRef, useState } from 'react'
import { searchTechnicalSheets } from '../../services/adminApi'
import type { TechnicalSheet } from '../../types/catalog'
import { AdminIcon } from './AdminIcon'

export function TechnicalSheetSearchModal({ onSelect, onClose }: { onSelect: (sheet: TechnicalSheet) => void; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<TechnicalSheet[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [status, setStatus] = useState<'initial' | 'loading' | 'results' | 'empty' | 'error'>('initial')
  const inputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const openerRef = useRef<HTMLElement | null>(document.activeElement instanceof HTMLElement ? document.activeElement : null)
  const sequenceRef = useRef(0)
  const close = useCallback(onClose, [onClose])

  useEffect(() => {
    inputRef.current?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close(); return }
      if (event.key !== 'Tab' || !panelRef.current) return
      const controls = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)'))
      const first = controls[0], last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => { sequenceRef.current += 1; document.body.style.overflow = overflow; document.removeEventListener('keydown', keydown); window.setTimeout(() => openerRef.current?.focus(), 0) }
  }, [close])

  useEffect(() => {
    const term = query.trim()
    if (term.length < 2) { sequenceRef.current += 1; setItems([]); setStatus('initial'); return }
    const sequence = ++sequenceRef.current
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setStatus('loading')
      searchTechnicalSheets(term, page, controller.signal).then((response) => {
        if (controller.signal.aborted || sequence !== sequenceRef.current) return
        setItems(response.results); setTotalPages(response.total_pages); setStatus(response.results.length ? 'results' : 'empty')
      }).catch(() => { if (!controller.signal.aborted && sequence === sequenceRef.current) setStatus('error') })
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [page, query])

  const message = status === 'initial' ? 'Escribe al menos 2 caracteres del modelo o nombre de la ficha.' : status === 'loading' ? 'Buscando fichas técnicas…' : status === 'empty' ? 'No se encontraron fichas técnicas.' : status === 'error' ? 'No fue posible realizar la búsqueda. Intenta nuevamente.' : null
  return <div className="commercial-modal" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close() }}>
    <div ref={panelRef} className="commercial-modal__panel product-search-modal" role="dialog" aria-modal="true" aria-labelledby="technical-sheet-search-title">
      <header className="product-search-modal__header"><h2 id="technical-sheet-search-title">Buscar ficha técnica</h2><button className="product-search-modal__close" type="button" onClick={close} aria-label="Cerrar búsqueda"><AdminIcon name="close" /></button></header>
      <label className="product-search-modal__search" htmlFor="technical-sheet-search">Modelo de la máquina o nombre de la ficha<input ref={inputRef} id="technical-sheet-search" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} autoComplete="off" /></label>
      {message ? <div className="product-search-modal__status" role={status === 'error' ? 'alert' : 'status'}>{message}</div> : null}
      {status === 'results' ? <ul className="technical-sheet-search__results">{items.map((sheet) => <li key={sheet.id}><button type="button" onClick={() => onSelect(sheet)}><strong>{sheet.name || 'Ficha sin nombre'}</strong><span>ID {sheet.id}</span></button></li>)}</ul> : null}
      {status === 'results' && totalPages > 1 ? <nav className="commercial-pagination" aria-label="Páginas de fichas"><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Anterior</button><span>Página {page} de {totalPages}</span><button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Siguiente</button></nav> : null}
      <footer className="product-search-modal__actions"><button className="btn btn--secondary" type="button" onClick={close}>Cancelar</button></footer>
    </div>
  </div>
}
