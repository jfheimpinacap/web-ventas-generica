import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'

import { appendToast, TOAST_DEFAULT_DURATION, type Toast, type ToastVariant } from './toastModel'

type ToastOptions = { duration?: number; dismissible?: boolean }
type ToastApi = Record<ToastVariant, (message: string, options?: ToastOptions) => void> & { dismiss: (id: number) => void }

const ToastContext = createContext<ToastApi | null>(null)
const LABELS: Record<ToastVariant, string> = { success: 'Éxito', error: 'Error', warning: 'Advertencia', info: 'Información' }
const ICONS: Record<ToastVariant, string> = { success: '✓', error: '!', warning: '!', info: 'i' }

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())
  const mounted = useRef(true)

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) clearTimeout(timer)
    timers.current.delete(id)
    if (mounted.current) setToasts(current => current.filter(toast => toast.id !== id))
  }, [])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      timers.current.forEach(clearTimeout)
      timers.current.clear()
    }
  }, [])

  const notify = useCallback((variant: ToastVariant, message: string, options: ToastOptions = {}) => {
    const id = ++nextId.current
    const duration = options.duration ?? TOAST_DEFAULT_DURATION
    const toast: Toast = { id, variant, message, duration, dismissible: options.dismissible ?? true }
    setToasts(current => appendToast(current, toast))
    if (duration > 0) timers.current.set(id, setTimeout(() => dismiss(id), duration))
  }, [dismiss])

  const api = useMemo<ToastApi>(() => ({
    success: (message, options) => notify('success', message, options),
    error: (message, options) => notify('error', message, options),
    warning: (message, options) => notify('warning', message, options),
    info: (message, options) => notify('info', message, options),
    dismiss,
  }), [dismiss, notify])

  return <ToastContext.Provider value={api}>{children}<div className="toast-region" aria-live="polite" aria-label="Notificaciones" aria-relevant="additions">
    {toasts.map(toast => <div className={`toast toast--${toast.variant}`} key={toast.id} role={toast.variant === 'error' ? 'alert' : 'status'} aria-atomic="true">
      <span className="toast__icon" aria-hidden="true">{ICONS[toast.variant]}</span>
      <div className="toast__content"><strong>{LABELS[toast.variant]}</strong><span>{toast.message}</span></div>
      {toast.dismissible ? <button className="toast__close" type="button" aria-label={`Cerrar notificación: ${toast.message}`} onClick={() => dismiss(toast.id)}>×</button> : null}
    </div>)}
  </div></ToastContext.Provider>
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast debe usarse dentro de ToastProvider')
  return context
}
