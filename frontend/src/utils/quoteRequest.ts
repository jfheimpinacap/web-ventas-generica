import type { PreferredContactMethod, ProductDetail, QuoteRequestPublicPayload } from '../types/catalog'
import { createQuoteRequest, getProductById } from '../services/catalogApi'

export interface QuoteFormState {
  customer_name: string
  customer_phone: string
  customer_email: string
  company_name: string
  city: string
  preferred_contact_method: PreferredContactMethod | ''
  message: string
}

export type QuoteProductId = number | null | undefined
export type QuoteProductSelection =
  | { requestedId: undefined; status: 'general'; product: null }
  | { requestedId: number | null; status: 'unavailable'; product: null }
  | { requestedId: number; status: 'loading'; product: null }
  | { requestedId: number; status: 'ready'; product: ProductDetail }

export const QUOTE_PRODUCT_LOADING_MESSAGE = 'Espera a que termine de cargar el producto antes de enviar la solicitud.'

export function parseQuoteProductId(value: string | null): QuoteProductId {
  if (!value) return undefined
  if (!/^[1-9]\d*$/.test(value)) return null
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : null
}

export function initialQuoteProductSelection(requestedId: QuoteProductId): QuoteProductSelection {
  if (requestedId === undefined) return { requestedId, status: 'general', product: null }
  if (requestedId === null) return { requestedId, status: 'unavailable', product: null }
  return { requestedId, status: 'loading', product: null }
}

// A URL change must take effect before the next effect runs, including on submit.
export function currentQuoteProductSelection(requestedId: QuoteProductId, selection: QuoteProductSelection): QuoteProductSelection {
  return selection.requestedId === requestedId ? selection : initialQuoteProductSelection(requestedId)
}

export function loadQuoteProductSelection(requestedId: QuoteProductId, onChange: (selection: QuoteProductSelection) => void) {
  let active = true
  const initial = initialQuoteProductSelection(requestedId)
  onChange(initial)
  if (initial.status === 'loading') {
    void getProductById(initial.requestedId).then(
      product => {
        if (active) onChange(product.id === initial.requestedId
          ? { requestedId: initial.requestedId, status: 'ready', product }
          : { requestedId: initial.requestedId, status: 'unavailable', product: null })
      },
      () => { if (active) onChange({ requestedId: initial.requestedId, status: 'unavailable', product: null }) },
    )
  }
  return () => { active = false }
}

export function buildQuoteRequestPayload(form: QuoteFormState, selection: QuoteProductSelection): QuoteRequestPublicPayload {
  if (selection.status === 'loading') throw new Error(QUOTE_PRODUCT_LOADING_MESSAGE)
  return {
    customer_name: form.customer_name.trim(),
    customer_phone: form.customer_phone.trim(),
    customer_email: form.customer_email.trim(),
    company_name: form.company_name.trim(),
    city: form.city.trim(),
    preferred_contact_method: form.preferred_contact_method,
    message: form.message.trim(),
    ...(selection.status === 'ready' ? { product: selection.product.id } : {}),
  }
}

export async function submitQuoteRequest(form: QuoteFormState, selection: QuoteProductSelection) {
  return createQuoteRequest(buildQuoteRequestPayload(form, selection))
}
