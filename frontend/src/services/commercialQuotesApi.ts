import { authBlobFetch, authFetch } from './authApi'
import type { CommercialQuoteDetail, CommercialQuoteIssueInput, CommercialQuotePage, CommercialQuoteValidityDays, CustomerProfile } from '../types/commercialQuote'

const json = (body: unknown) => ({ 'Content-Type': 'application/json', body: JSON.stringify(body) })

export async function searchCustomers(search: string, signal?: AbortSignal) {
  return authFetch<{ results: CustomerProfile[]; count: number }>('/api/admin/customers', { params: { search, page_size: 10 }, signal })
}
export function saveCustomer(customer: Omit<CustomerProfile, 'id' | 'created_at' | 'updated_at'>, id?: number) {
  return authFetch<CustomerProfile>(id ? `/api/admin/customers/${id}` : '/api/admin/customers', { method: id ? 'PUT' : 'POST', ...json(customer) })
}
export function getCommercialQuotes({ search, page, pageSize = 20, signal }: { search?: string; page: number; pageSize?: number; signal?: AbortSignal }) {
  return authFetch<CommercialQuotePage>('/api/admin/commercial-quotes', { params: { search, page, page_size: pageSize }, signal })
}
type RawCommercialQuoteDetail = Omit<CommercialQuoteDetail, 'responsibleSellerName' | 'responsibleSellerCode' | 'responsibleSellerEmail' | 'responsibleSellerPhone' | 'validityDays'> & {
  responsible_seller_name?: string
  responsible_seller_code?: string
  responsible_seller_email?: string | null
  responsible_seller_phone?: string | null
  seller_email?: string | null
  seller_phone?: string | null
  validity_days?: CommercialQuoteValidityDays
  validityDays?: CommercialQuoteValidityDays
}

function normalizeCommercialQuoteDetail(quote: RawCommercialQuoteDetail): CommercialQuoteDetail {
  return {
    ...quote,
    responsibleSellerName: quote.responsible_seller_name ?? quote.seller_name,
    responsibleSellerCode: quote.responsible_seller_code ?? quote.seller_code,
    responsibleSellerEmail: quote.responsible_seller_email ?? quote.seller_email ?? null,
    responsibleSellerPhone: quote.responsible_seller_phone ?? quote.seller_phone ?? null,
    validityDays: quote.validity_days ?? quote.validityDays ?? 15,
  }
}

export async function getCommercialQuote(id: number) {
  return normalizeCommercialQuoteDetail(await authFetch<RawCommercialQuoteDetail>(`/api/admin/commercial-quotes/${id}`))
}
export async function getCommercialQuotePdf(id: number): Promise<Blob> {
  if (!Number.isInteger(id) || id <= 0) throw new Error('La cotización indicada no es válida.')

  const blob = await authBlobFetch(`/api/admin/commercial-quotes/${id}/pdf`)
  const mime = blob.type.split(';', 1)[0].trim().toLowerCase()
  if (blob.size <= 0 || mime !== 'application/pdf') {
    throw new Error('El archivo PDF recibido no es válido.')
  }

  const signature = new TextDecoder('ascii').decode(await blob.slice(0, 5).arrayBuffer())
  if (signature !== '%PDF-') throw new Error('El archivo PDF recibido no es válido.')

  return blob
}
export function issueCommercialQuote(payload: CommercialQuoteIssueInput, idempotencyKey: string) {
  return authFetch<RawCommercialQuoteDetail>('/api/admin/commercial-quotes/issue', { method: 'POST', ...json(payload), headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey } }).then(normalizeCommercialQuoteDetail)
}
