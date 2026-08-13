import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import { createPortal } from 'react-dom'

import type { TechnicalSheet } from '../../types/catalog'

interface Props {
  open: boolean
  productName: string
  sheet: TechnicalSheet
  inlineUrl: string
  downloadUrl: string
  onClose: () => void
  onDownload: () => void
  returnFocusRef: RefObject<HTMLButtonElement | null>
}

export function ProductTechnicalSheetModal({ open, productName, sheet, inlineUrl, downloadUrl, onClose, onDownload, returnFocusRef }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
      if (event.key !== 'Tab') return
      const controls = dialogRef.current?.querySelectorAll<HTMLElement>('button, a[href], iframe, [tabindex]:not([tabindex="-1"])')
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
  }, [onClose, open, returnFocusRef])

  if (!open) return null
  const isPdf = sheet.content_type.trim().toLowerCase() === 'application/pdf'

  return createPortal(
    <div className="product-technical-sheet-modal__backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div ref={dialogRef} className="product-technical-sheet-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="technical-sheet-title">
        <header className="product-technical-sheet-modal__header">
          <h2 id="technical-sheet-title" className="product-technical-sheet-modal__accessible-title">Ficha técnica de {productName}</h2>
          <button ref={closeRef} type="button" className="btn btn--ghost product-technical-sheet-modal__close" onClick={onClose} aria-label="Cerrar ficha técnica">×</button>
        </header>
        <div className={`product-technical-sheet-modal__viewer${isPdf ? '' : ' product-technical-sheet-modal__viewer--image'}`}>
          {isPdf ? <iframe src={inlineUrl} title={`Ficha técnica de ${productName}`} /> : <img src={inlineUrl} alt={`Ficha técnica ${sheet.name} de ${productName}`} />}
        </div>
        <footer className="product-technical-sheet-modal__actions">
          <a className="btn btn--ghost" href={inlineUrl} target="_blank" rel="noopener noreferrer">Abrir en nueva pestaña</a>
          <a className="btn btn--accent" href={downloadUrl} onClick={onDownload}>Descargar</a>
          <button type="button" className="btn btn--ghost" onClick={onClose}>Cerrar</button>
        </footer>
      </div>
    </div>, document.body,
  )
}
