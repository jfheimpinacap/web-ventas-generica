import { authFetch } from './authApi'

export interface SellerUser {
  id: number
  username: string
  seller_code: string | null
  email: string | null
  full_name: string | null
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface SellerUserWrite {
  username: string
  email: string | null
  full_name: string | null
  password?: string
  is_active?: boolean
}

export function listSellerUsers(params: { search?: string; is_active?: boolean }, signal?: AbortSignal) {
  return authFetch<SellerUser[]>('/admin/users', { params, signal })
}

export function getSellerUser(id: number, signal?: AbortSignal) {
  return authFetch<SellerUser>(`/admin/users/${id}`, { signal })
}

export function createSellerUser(payload: SellerUserWrite, signal?: AbortSignal) {
  return authFetch<SellerUser>('/admin/users', { method: 'POST', body: JSON.stringify(payload), signal })
}

export function updateSellerUser(id: number, payload: SellerUserWrite, signal?: AbortSignal) {
  return authFetch<SellerUser>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload), signal })
}

export function deactivateSellerUser(id: number) {
  return authFetch<void>(`/admin/users/${id}`, { method: 'DELETE' })
}
