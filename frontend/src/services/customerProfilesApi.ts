import { authFetch } from './authApi'
import type { CustomerProfile } from '../types/commercialQuote'

export type CustomerStatus = 'active' | 'inactive' | 'all'
export interface CustomerProfileInput { business_name: string; rut: string; business_activity: string; address: string; phone: string; city_or_commune: string; contact_name: string; email: string | null }
export interface CustomerProfilePage { results: CustomerProfile[]; page: number; pageSize: number; count: number }
type Raw = Record<string, unknown>
const text = (value: unknown) => typeof value === 'string' ? value : ''
const positiveId = (id: number) => { if (!Number.isInteger(id) || id <= 0) throw new Error('El cliente indicado no es válido.'); return id }

export function normalizeCustomerProfile(value: unknown): CustomerProfile {
  const raw = (value ?? {}) as Raw
  return { id: Number(raw.id ?? 0), businessName: text(raw.businessName ?? raw.business_name), rut: text(raw.rut), businessActivity: text(raw.businessActivity ?? raw.business_activity), address: text(raw.address), phone: text(raw.phone), cityOrCommune: text(raw.cityOrCommune ?? raw.city_or_commune), contactName: text(raw.contactName ?? raw.contact_name), email: text(raw.email) || null, isActive: (raw.isActive ?? raw.is_active) !== false, createdAt: text(raw.createdAt ?? raw.created_at), updatedAt: text(raw.updatedAt ?? raw.updated_at) }
}

export async function listCustomers({ search, status, page, pageSize = 20, signal }: { search: string; status: CustomerStatus; page: number; pageSize?: number; signal?: AbortSignal }): Promise<CustomerProfilePage> {
  const params = new URLSearchParams({ search: search.trim(), status, page: String(page), page_size: String(pageSize) })
  const raw = await authFetch<Raw>(`/api/admin/customers?${params.toString()}`, { signal })
  return { results: Array.isArray(raw.results) ? raw.results.map(normalizeCustomerProfile) : [], page: Number(raw.page ?? page), pageSize: Number(raw.pageSize ?? raw.page_size ?? pageSize), count: Number(raw.count ?? 0) }
}
export async function getCustomer(id: number) { return normalizeCustomerProfile(await authFetch<unknown>(`/api/admin/customers/${positiveId(id)}`)) }
const json = (body: CustomerProfileInput) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export async function createCustomer(body: CustomerProfileInput) { return normalizeCustomerProfile(await authFetch<unknown>('/api/admin/customers', { method: 'POST', ...json(body) })) }
export async function updateCustomer(id: number, body: CustomerProfileInput) { return normalizeCustomerProfile(await authFetch<unknown>(`/api/admin/customers/${positiveId(id)}`, { method: 'PUT', ...json(body) })) }
export async function deactivateCustomer(id: number) { return normalizeCustomerProfile(await authFetch<unknown>(`/api/admin/customers/${positiveId(id)}/deactivate`, { method: 'POST' })) }
export async function reactivateCustomer(id: number) { return normalizeCustomerProfile(await authFetch<unknown>(`/api/admin/customers/${positiveId(id)}/reactivate`, { method: 'POST' })) }
