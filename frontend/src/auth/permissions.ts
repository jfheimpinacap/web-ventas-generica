import type { AuthUser } from '../types/catalog'

// Mirror exacto de AppPermissions. El backend sigue siendo la autoridad.
export const PERMISSIONS = {
  productsCreate: 'products.create', productsUpdate: 'products.update', productsDelete: 'products.delete',
  productImagesManage: 'product_images.manage', productSpecsManage: 'product_specs.manage',
  technicalSheetsCreate: 'technical_sheets.create', technicalSheetsUpdate: 'technical_sheets.update', technicalSheetsDelete: 'technical_sheets.delete',
  categoriesCreate: 'categories.create', categoriesUpdate: 'categories.update', categoriesDelete: 'categories.delete',
  brandsCreate: 'brands.create', brandsUpdate: 'brands.update', brandsDelete: 'brands.delete',
  suppliersCreate: 'suppliers.create', suppliersUpdate: 'suppliers.update', suppliersDelete: 'suppliers.delete',
  customersCreate: 'customers.create', customersUpdate: 'customers.update', customersSetStatus: 'customers.set_status',
  quoteRequestsUpdate: 'quote_requests.update', commercialQuotesIssue: 'commercial_quotes.issue', quoteNotificationsTest: 'quote_notifications.test',
  promotionsCreate: 'promotions.create', promotionsUpdate: 'promotions.update', promotionsDelete: 'promotions.delete',
  homeSectionsCreate: 'home_sections.create', homeSectionsUpdate: 'home_sections.update', homeSectionsDelete: 'home_sections.delete',
  usersManage: 'users.manage',
} as const

export type AppPermission = typeof PERMISSIONS[keyof typeof PERMISSIONS]
export const APP_PERMISSIONS = Object.freeze(Object.values(PERMISSIONS)) as readonly AppPermission[]

function roles(user?: AuthUser) {
  if (!user) return []
  if (Array.isArray(user.roles)) return user.roles.map(String).map(value => value.toLowerCase())
  if (typeof user.roles === 'string') return [user.roles.toLowerCase()]
  return typeof user.role === 'string' ? [user.role.toLowerCase()] : []
}

export function isEffectiveSupportAdmin(user?: AuthUser) { return roles(user).includes('support_admin') }

export function can(user: AuthUser | undefined, permission: AppPermission) {
  if (!user || !APP_PERMISSIONS.includes(permission)) return false
  if (isEffectiveSupportAdmin(user)) return true
  if (!roles(user).includes('seller') || permission === PERMISSIONS.usersManage) return false
  return Array.isArray(user.permissions) && user.permissions.includes(permission)
}

export function canAny(user: AuthUser | undefined, permissions: readonly AppPermission[]) {
  return permissions.some(permission => can(user, permission))
}
