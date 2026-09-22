export const TOAST_VARIANTS = ['success', 'error', 'warning', 'info'] as const
export type ToastVariant = typeof TOAST_VARIANTS[number]

export const TOAST_DEFAULT_DURATION = 5_000
export const TOAST_QUEUE_LIMIT = 4

export type Toast = {
  id: number
  variant: ToastVariant
  message: string
  duration: number
  dismissible: boolean
}

export function appendToast(queue: Toast[], toast: Toast, limit = TOAST_QUEUE_LIMIT) {
  return [...queue, toast].slice(-limit)
}
