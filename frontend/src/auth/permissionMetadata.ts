import { PERMISSIONS, type AppPermission } from './permissions'

export const PERMISSION_GROUPS = [
  'Productos', 'Imágenes de productos', 'Especificaciones', 'Fichas técnicas',
  'Categorías y subcategorías', 'Marcas', 'Proveedores', 'Clientes',
  'Solicitudes de cotización', 'Cotizaciones comerciales', 'Notificaciones',
  'Promociones', 'Secciones de la portada', 'Otros permisos',
] as const

export type PermissionGroup = typeof PERMISSION_GROUPS[number]
export type GrantablePermission = Exclude<AppPermission, typeof PERMISSIONS.usersManage>
export interface PermissionMetadata { label: string; description: string; group: PermissionGroup }

export const GRANTABLE_PERMISSION_METADATA: Readonly<Record<GrantablePermission, PermissionMetadata>> = Object.freeze({
  [PERMISSIONS.productsCreate]: { label: 'Crear', description: 'Permite crear productos.', group: 'Productos' },
  [PERMISSIONS.productsUpdate]: { label: 'Editar', description: 'Permite modificar productos existentes.', group: 'Productos' },
  [PERMISSIONS.productsDelete]: { label: 'Eliminar', description: 'Permite eliminar productos.', group: 'Productos' },
  [PERMISSIONS.productImagesManage]: { label: 'Administrar', description: 'Permite agregar, ordenar y eliminar imágenes de productos.', group: 'Imágenes de productos' },
  [PERMISSIONS.productSpecsManage]: { label: 'Administrar', description: 'Permite modificar las especificaciones técnicas de los productos.', group: 'Especificaciones' },
  [PERMISSIONS.technicalSheetsCreate]: { label: 'Crear', description: 'Permite cargar nuevas fichas técnicas.', group: 'Fichas técnicas' },
  [PERMISSIONS.technicalSheetsUpdate]: { label: 'Editar', description: 'Permite modificar y asociar fichas técnicas.', group: 'Fichas técnicas' },
  [PERMISSIONS.technicalSheetsDelete]: { label: 'Eliminar', description: 'Permite eliminar fichas técnicas.', group: 'Fichas técnicas' },
  [PERMISSIONS.categoriesCreate]: { label: 'Crear', description: 'Permite crear categorías y subcategorías.', group: 'Categorías y subcategorías' },
  [PERMISSIONS.categoriesUpdate]: { label: 'Editar', description: 'Permite modificar categorías y subcategorías.', group: 'Categorías y subcategorías' },
  [PERMISSIONS.categoriesDelete]: { label: 'Eliminar', description: 'Permite eliminar categorías y subcategorías.', group: 'Categorías y subcategorías' },
  [PERMISSIONS.brandsCreate]: { label: 'Crear', description: 'Permite crear marcas.', group: 'Marcas' },
  [PERMISSIONS.brandsUpdate]: { label: 'Editar', description: 'Permite modificar marcas y sus logotipos.', group: 'Marcas' },
  [PERMISSIONS.brandsDelete]: { label: 'Eliminar', description: 'Permite eliminar marcas.', group: 'Marcas' },
  [PERMISSIONS.suppliersCreate]: { label: 'Crear', description: 'Permite crear proveedores.', group: 'Proveedores' },
  [PERMISSIONS.suppliersUpdate]: { label: 'Editar', description: 'Permite modificar proveedores.', group: 'Proveedores' },
  [PERMISSIONS.suppliersDelete]: { label: 'Desactivar', description: 'Permite desactivar proveedores conservando sus datos.', group: 'Proveedores' },
  [PERMISSIONS.customersCreate]: { label: 'Crear', description: 'Permite crear clientes.', group: 'Clientes' },
  [PERMISSIONS.customersUpdate]: { label: 'Editar', description: 'Permite modificar los datos de clientes.', group: 'Clientes' },
  [PERMISSIONS.customersSetStatus]: { label: 'Cambiar estado', description: 'Permite activar o desactivar clientes.', group: 'Clientes' },
  [PERMISSIONS.quoteRequestsUpdate]: { label: 'Editar', description: 'Permite actualizar solicitudes de cotización.', group: 'Solicitudes de cotización' },
  [PERMISSIONS.commercialQuotesIssue]: { label: 'Emitir', description: 'Permite emitir cotizaciones comerciales.', group: 'Cotizaciones comerciales' },
  [PERMISSIONS.quoteNotificationsTest]: { label: 'Enviar prueba', description: 'Permite enviar una notificación de cotización de prueba.', group: 'Notificaciones' },
  [PERMISSIONS.promotionsCreate]: { label: 'Crear', description: 'Permite crear promociones.', group: 'Promociones' },
  [PERMISSIONS.promotionsUpdate]: { label: 'Editar', description: 'Permite modificar y ordenar promociones.', group: 'Promociones' },
  [PERMISSIONS.promotionsDelete]: { label: 'Desactivar', description: 'Permite desactivar promociones conservando sus datos.', group: 'Promociones' },
  [PERMISSIONS.homeSectionsCreate]: { label: 'Crear', description: 'Permite crear secciones y ofertas de la portada.', group: 'Secciones de la portada' },
  [PERMISSIONS.homeSectionsUpdate]: { label: 'Editar', description: 'Permite modificar y ordenar secciones de la portada.', group: 'Secciones de la portada' },
  [PERMISSIONS.homeSectionsDelete]: { label: 'Eliminar', description: 'Permite eliminar secciones de la portada.', group: 'Secciones de la portada' },
})

const FALLBACK_PERMISSION_METADATA: PermissionMetadata = Object.freeze({
  label: 'Permiso adicional',
  description: 'Permiso administrativo adicional.',
  group: 'Otros permisos',
})

export function getPermissionMetadata(permission: string): PermissionMetadata {
  return GRANTABLE_PERMISSION_METADATA[permission as GrantablePermission] ?? FALLBACK_PERMISSION_METADATA
}
