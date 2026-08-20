import { useEffect, useRef, type ReactNode } from 'react'

interface ConfirmDialogProps {
  title: string
  children: ReactNode
  cancelLabel?: string
  confirmLabel?: string
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmDialog({ title, children, cancelLabel = 'Cancelar', confirmLabel = 'Continuar', onCancel, onConfirm }: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    cancelRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onCancel(); return }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const controls = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled)'))
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', handleKeyDown) }
  }, [onCancel])

  return (
    <div className="admin-confirm-dialog" role="presentation">
      <div ref={dialogRef} className="admin-confirm-dialog__panel" role="dialog" aria-modal="true" aria-labelledby="admin-confirm-title" aria-describedby="admin-confirm-description">
        <header className="admin-confirm-dialog__header">
          <h2 id="admin-confirm-title">{title}</h2>
          <button className="admin-confirm-dialog__close" type="button" onClick={onCancel} aria-label="Cerrar">×</button>
        </header>
        <div id="admin-confirm-description" className="admin-confirm-dialog__content">{children}</div>
        <footer className="admin-confirm-dialog__actions">
          <button ref={cancelRef} className="btn btn--secondary" type="button" onClick={onCancel}>{cancelLabel}</button>
          <button className="btn btn--accent" type="button" onClick={onConfirm}>{confirmLabel}</button>
        </footer>
      </div>
    </div>
  )
}
