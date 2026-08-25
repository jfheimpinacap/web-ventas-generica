import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type DialogVariant = 'default' | 'danger'
interface ConfirmationOptions { title: string; message: string; confirmLabel: string; cancelLabel?: string; variant?: DialogVariant }
interface PromptOptions { title: string; message?: string; label: string; initialValue?: string; confirmLabel?: string; cancelLabel?: string }
type Request =
  | ({ kind: 'confirm'; options: ConfirmationOptions; resolve: (value: boolean) => void })
  | ({ kind: 'prompt'; options: PromptOptions; resolve: (value: string | null) => void })
interface DialogApi {
  requestConfirmation: (options: ConfirmationOptions) => Promise<boolean>
  requestText: (options: PromptOptions) => Promise<string | null>
}

const SystemDialogContext = createContext<DialogApi | null>(null)

export function SystemDialogProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<Request | null>(null)
  const [inputValue, setInputValue] = useState('')
  const queue = useRef<Request[]>([])
  const activeRef = useRef<Request | null>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  const present = useCallback((request: Request, captureFocus = true) => {
    if (captureFocus) returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    activeRef.current = request
    setInputValue(request.kind === 'prompt' ? request.options.initialValue ?? '' : '')
    setActive(request)
  }, [])
  const enqueue = useCallback((request: Request) => {
    if (activeRef.current) queue.current.push(request)
    else present(request)
  }, [present])
  const requestConfirmation = useCallback((options: ConfirmationOptions) => new Promise<boolean>((resolve) => enqueue({ kind: 'confirm', options, resolve })), [enqueue])
  const requestText = useCallback((options: PromptOptions) => new Promise<string | null>((resolve) => enqueue({ kind: 'prompt', options, resolve })), [enqueue])

  const finish = useCallback((value: boolean | string | null) => {
    const request = activeRef.current
    if (!request) return
    activeRef.current = null
    if (request.kind === 'confirm') request.resolve(Boolean(value))
    else request.resolve(typeof value === 'string' ? value : null)
    setActive(null)
    const next = queue.current.shift()
    window.setTimeout(() => {
      if (next) present(next, false)
      else returnFocus.current?.focus()
    }, 0)
  }, [present])

  useEffect(() => () => {
    const current = activeRef.current
    if (current?.kind === 'confirm') current.resolve(false)
    else if (current) current.resolve(null)
    queue.current.splice(0).forEach(request => {
      if (request.kind === 'confirm') request.resolve(false)
      else request.resolve(null)
    })
  }, [])

  useEffect(() => {
    if (!active) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (active.kind === 'prompt') inputRef.current?.focus()
    else cancelRef.current?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); finish(active.kind === 'confirm' ? false : null); return }
      if (event.key !== 'Tab' || !panelRef.current) return
      const controls = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)'))
      const first = controls[0]; const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', keydown) }
  }, [active, finish])

  return <SystemDialogContext.Provider value={{ requestConfirmation, requestText }}>
    {children}
    {active ? createPortal(<div className="system-dialog" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) finish(active.kind === 'confirm' ? false : null) }}>
      <div ref={panelRef} className={`system-dialog__panel${active.kind === 'confirm' && active.options.variant === 'danger' ? ' system-dialog__panel--danger' : ''}`} role={active.kind === 'confirm' ? 'alertdialog' : 'dialog'} aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}>
        <header className="system-dialog__header"><h2 id={titleId}>{active.options.title}</h2></header>
        <div className="system-dialog__content">
          {'message' in active.options && active.options.message ? <p id={descriptionId}>{active.options.message}</p> : <span id={descriptionId} className="system-dialog__sr-only">Ingrese el valor solicitado.</span>}
          {active.kind === 'prompt' ? <label className="system-dialog__field">{active.options.label}<input ref={inputRef} value={inputValue} onChange={event => setInputValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); finish(inputValue) } }} /></label> : null}
        </div>
        <footer className="system-dialog__actions">
          <button ref={cancelRef} className="btn btn--secondary" type="button" onClick={() => finish(active.kind === 'confirm' ? false : null)}>{active.options.cancelLabel ?? 'Cancelar'}</button>
          <button className={`btn ${active.kind === 'confirm' && active.options.variant === 'danger' ? 'btn--danger' : 'btn--accent'}`} type="button" onClick={() => finish(active.kind === 'confirm' ? true : inputValue)}>{active.options.confirmLabel ?? 'Guardar'}</button>
        </footer>
      </div>
    </div>, document.body) : null}
  </SystemDialogContext.Provider>
}

export function useSystemDialog() {
  const value = useContext(SystemDialogContext)
  if (!value) throw new Error('useSystemDialog debe usarse dentro de SystemDialogProvider.')
  return value
}
