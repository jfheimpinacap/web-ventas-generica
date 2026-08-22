import { authFetch } from './authApi'
import type { CommercialQuoteDetail, CommercialQuoteIssueInput, CommercialQuotePage, CustomerProfile } from '../types/commercialQuote'

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
export function getCommercialQuote(id: number) { return authFetch<CommercialQuoteDetail>(`/api/admin/commercial-quotes/${id}`) }
export function issueCommercialQuote(payload: CommercialQuoteIssueInput, idempotencyKey: string) {
  return authFetch<CommercialQuoteDetail>('/api/admin/commercial-quotes/issue', { method: 'POST', ...json(payload), headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey } })
}
