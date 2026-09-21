import { authFetch } from './authApi'

export type ManagedRole = 'seller' | 'support_admin'
export interface ManagedUser {
  id: number; username: string; seller_code: string | null; email: string | null; full_name: string | null; phone: string | null
  role: ManagedRole; is_active: boolean; is_staff: boolean; is_superuser: boolean; permissions: string[]
  last_login_at: string | null; created_at: string; updated_at: string
}
export interface ManagedUserWrite {
  username: string; email: string | null; full_name: string | null; phone: string | null
  password?: string; is_active?: boolean; role?: ManagedRole; permissions?: string[] | null
}
export interface UserPermissionCatalog { roles: ManagedRole[]; seller_grantable: string[]; reserved: string[] }

export function listManagedUsers(params: { search?: string; is_active?: boolean; role?: ManagedRole }, signal?: AbortSignal) { return authFetch<ManagedUser[]>('/admin/users', { params, signal }) }
export function getManagedUser(id: number, signal?: AbortSignal) { return authFetch<ManagedUser>(`/admin/users/${id}`, { signal }) }
export function getUserPermissionCatalog(signal?: AbortSignal) { return authFetch<UserPermissionCatalog>('/admin/users/permission-catalog', { signal }) }
export function createManagedUser(payload: ManagedUserWrite, signal?: AbortSignal) { return authFetch<ManagedUser>('/admin/users', { method: 'POST', body: JSON.stringify(payload), signal }) }
export function updateManagedUser(id: number, payload: ManagedUserWrite, signal?: AbortSignal) { return authFetch<ManagedUser>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload), signal }) }
export function deactivateManagedUser(id: number) { return authFetch<void>(`/admin/users/${id}`, { method: 'DELETE' }) }
