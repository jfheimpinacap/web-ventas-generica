import { authFetch } from './authApi'
import type { CommercialQuoteDetail, CommercialQuoteDraftInput, CommercialQuoteSummary, CustomerProfile } from '../types/commercialQuote'

const json = (body: unknown) => ({ 'Content-Type': 'application/json', body: JSON.stringify(body) })

export async function searchCustomers(search: string, signal?: AbortSignal) {
  return authFetch<{ results: CustomerProfile[]; count: number }>('/api/admin/customers', { params: { search, page_size: 10 }, signal })
}
export function saveCustomer(customer: Omit<CustomerProfile, 'id' | 'created_at' | 'updated_at'>, id?: number) {
  return authFetch<CustomerProfile>(id ? `/api/admin/customers/${id}` : '/api/admin/customers', { method: id ? 'PUT' : 'POST', ...json(customer) })
}
export function getCommercialQuotes() {
  return authFetch<{ results: CommercialQuoteSummary[] }>('/api/admin/commercial-quotes')
}
export function getCommercialQuote(id: number) { return authFetch<CommercialQuoteDetail>(`/api/admin/commercial-quotes/${id}`) }
export function saveCommercialQuote(payload: CommercialQuoteDraftInput, id?: number) {
  return authFetch<CommercialQuoteDetail>(id ? `/api/admin/commercial-quotes/${id}` : '/api/admin/commercial-quotes', { method: id ? 'PUT' : 'POST', ...json(payload) })
}
export function issueCommercialQuote(id: number) { return authFetch<CommercialQuoteDetail>(`/api/admin/commercial-quotes/${id}/issue`, { method: 'POST' }) }
