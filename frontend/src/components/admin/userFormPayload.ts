import type { UserPermissionCatalog, ManagedUserWrite } from '../../services/adminUsersApi'
import type { UserFormFields, UserFormMode } from './UserForm'

export function buildManagedUserPayload(fields: UserFormFields, catalog: UserPermissionCatalog, mode: UserFormMode): ManagedUserWrite {
  const allowed = new Set(catalog.seller_grantable)
  const payload: ManagedUserWrite = {
    username: fields.username.trim(),
    email: fields.email.trim() || null,
    // These values remain in form state, although their controls are intentionally hidden.
    // Re-sending them preserves existing profile data with the current API contract.
    full_name: fields.fullName.trim() || null,
    phone: fields.phone.trim() || null,
    role: fields.role,
    permissions: fields.role === 'seller' ? fields.permissions.filter((item) => allowed.has(item)) : [],
  }
  if (fields.password) payload.password = fields.password
  if (mode === 'reactivate') payload.is_active = true
  return payload
}
