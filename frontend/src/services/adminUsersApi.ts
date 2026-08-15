import { authFetch } from './authApi'

export interface SellerUser {
  id: number
  username: string
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

export function createSellerUser(payload: SellerUserWrite) {
  return authFetch<SellerUser>('/admin/users', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateSellerUser(id: number, payload: SellerUserWrite) {
  return authFetch<SellerUser>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function deactivateSellerUser(id: number) {
  return authFetch<void>(`/admin/users/${id}`, { method: 'DELETE' })
}

export function reactivateSellerUser(id: number, password: string) {
  return authFetch<SellerUser>(`/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active: true, password }),
  })
}
