import { useCallback, useEffect, useId, useRef, useState, type RefObject } from 'react'
import { createPortal } from 'react-dom'

import { getCommercialQuotePdf } from '../../services/commercialQuotesApi'
import { commercialQuotePdfErrorMessage, downloadCommercialQuotePdf } from '../../utils/commercialQuotePdf'

interface Props {
  quoteId: number
  folio?: string | null
  onClose: () => void
  returnFocusRef: RefObject<HTMLButtonElement | null>
}

export function CommercialQuotePdfModal({ quoteId, folio, onClose, returnFocusRef }: Props) {
  const titleId = useId()
  const descriptionId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const objectUrlRef = useRef('')
  const generationRef = useRef(0)
  const mountedRef = useRef(true)
  const requestRef = useRef<Promise<Blob> | null>(null)
  const [objectUrl, setObjectUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const revokeCurrentUrl = useCallback(() => {
    if (!objectUrlRef.current) return
    URL.revokeObjectURL(objectUrlRef.current)
    objectUrlRef.current = ''
  }, [])

  const loadPdf = useCallback(async () => {
    const generation = ++generationRef.current
    const request = requestRef.current ?? getCommercialQuotePdf(quoteId)
    requestRef.current = request
    revokeCurrentUrl()
    setObjectUrl('')
    setError('')
    setLoading(true)
    try {
      const blob = await request
      if (!mountedRef.current || generation !== generationRef.current) return
      const nextUrl = URL.createObjectURL(blob)
      if (!mountedRef.current || generation !== generationRef.current) {
        URL.revokeObjectURL(nextUrl)
        return
      }
      objectUrlRef.current = nextUrl
      setObjectUrl(nextUrl)
    } catch (loadError) {
      if (mountedRef.current && generation === generationRef.current) {
        setError(commercialQuotePdfErrorMessage(loadError))
      }
    } finally {
      if (requestRef.current === request) requestRef.current = null
      if (mountedRef.current && generation === generationRef.current) {
        setLoading(false)
      }
    }
  }, [quoteId, revokeCurrentUrl])

  useEffect(() => {
    mountedRef.current = true
    void loadPdf()
    return () => {
      mountedRef.current = false
      generationRef.current += 1
      revokeCurrentUrl()
    }
  }, [loadPdf, revokeCurrentUrl])

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
      if (event.key !== 'Tab') return
      const controls = dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), iframe, [tabindex]:not([tabindex="-1"])')
      if (!controls?.length) return
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      returnFocusRef.current?.focus()
    }
  }, [onClose, returnFocusRef])

  const folioLabel = folio?.trim() || String(quoteId)
  return createPortal(
    <div className="commercial-pdf-modal__backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <div ref={dialogRef} className="commercial-pdf-modal__dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId} aria-busy={loading || undefined}>
        <header className="commercial-pdf-modal__header">
          <div><h2 id={titleId}>Cotización emitida</h2><p id={descriptionId}>La cotización {folio ? `con folio ${folio}` : ''} fue emitida correctamente.</p></div>
          <button ref={closeRef} type="button" className="btn btn--ghost commercial-pdf-modal__close" onClick={onClose} aria-label="Cerrar visor de cotización">×</button>
        </header>
        <div className="commercial-pdf-modal__viewer">
          {loading ? <div className="commercial-pdf-modal__status" role="status"><span className="commercial-pdf-modal__spinner" aria-hidden="true" />Preparando PDF…</div> : null}
          {!loading && error ? <div className="commercial-pdf-modal__status"><p className="ui-note ui-note--error" role="alert">{error}</p><button type="button" className="btn btn--secondary" onClick={() => void loadPdf()}>Reintentar</button></div> : null}
          {objectUrl ? <iframe src={objectUrl} title={`PDF de la cotización ${folioLabel}`} /> : null}
        </div>
        <footer className="commercial-pdf-modal__actions">
          <button type="button" className="btn btn--accent" disabled={!objectUrl || loading} onClick={() => downloadCommercialQuotePdf(objectUrl, quoteId, folio)}>Descargar PDF</button>
          <button type="button" className="btn btn--ghost" onClick={onClose}>Cerrar</button>
        </footer>
      </div>
    </div>, document.body,
  )
}
