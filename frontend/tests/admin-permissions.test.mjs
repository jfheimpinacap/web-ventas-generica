import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { APP_PERMISSIONS, can, PERMISSIONS } from '../src/auth/permissions.ts'
import { getPermissionMetadata, GRANTABLE_PERMISSION_METADATA, PERMISSION_GROUPS } from '../src/auth/permissionMetadata.ts'
import { buildManagedUserPayload } from '../src/components/admin/userFormPayload.ts'

const support = { role: 'support_admin', permissions: [] }
const seller = (permissions) => ({ role: 'seller', permissions })

test('support_admin obtiene cualquier permiso conocido aunque su arreglo esté vacío', () => {
  assert.equal(APP_PERMISSIONS.every(permission => can(support, permission)), true)
})

test('seller requiere exactamente un permiso conocido y users.manage permanece reservado', () => {
  assert.equal(can(seller([PERMISSIONS.productsCreate]), PERMISSIONS.productsCreate), true)
  assert.equal(can(seller([]), PERMISSIONS.productsCreate), false)
  assert.equal(can(seller(undefined), PERMISSIONS.productsCreate), false)
  assert.equal(can(seller(['unknown']), PERMISSIONS.productsCreate), false)
  assert.equal(can(seller([PERMISSIONS.usersManage]), PERMISSIONS.usersManage), false)
})

test('las claves frontend coinciden con AppPermissions', async () => {
  const backend = await readFile(new URL('../../backend-dotnet/JemNexus.Api/Models/AppPermissions.cs', import.meta.url), 'utf8')
  const backendValues = [...backend.matchAll(/const string \w+ = "([a-z_.]+)";/g)].map(match => match[1]).sort()
  assert.deepEqual([...APP_PERMISSIONS].sort(), backendValues)
})

test('menú conserva módulos principales y Usuarios depende de users.manage', async () => {
  const layout = await readFile(new URL('../src/components/admin/AdminLayout.tsx', import.meta.url), 'utf8')
  for (const label of ['Productos', 'Fichas técnicas', 'Categorías', 'Marcas', 'Proveedores', 'Clientes', 'Cotizaciones', 'Promociones', 'Ofertas en Hero section', 'Volver al sitio']) assert.match(layout, new RegExp(label))
  assert.match(layout, /can\(currentUser \?\? undefined, PERMISSIONS\.usersManage\)/)
})

test('rutas mutables usan guardas y 403 no limpia la sesión', async () => {
  const router = await readFile(new URL('../src/router/AppRouter.tsx', import.meta.url), 'utf8')
  assert.match(router, /PermissionRoute permission=\{PERMISSIONS\.productsCreate\}/)
  assert.match(router, /PermissionRoute permission=\{PERMISSIONS\.productsUpdate\}/)
  const guard = await readFile(new URL('../src/components/admin/ProtectedRoute.tsx', import.meta.url), 'utf8')
  assert.match(guard, /status === 403\).*setStatus\('forbidden'\)/)
  assert.match(guard, /status === 401\) clearSession\(\)/)
})

test('los 29 permisos concedibles tienen metadata amigable y exhaustiva', () => {
  const entries = Object.entries(GRANTABLE_PERMISSION_METADATA)
  assert.equal(entries.length, 29)
  assert.equal(PERMISSIONS.usersManage in GRANTABLE_PERMISSION_METADATA, false)
  for (const [permission, metadata] of entries) {
    assert.ok(PERMISSION_GROUPS.includes(metadata.group))
    assert.ok(metadata.label.trim())
    assert.ok(metadata.description.trim())
    assert.notEqual(metadata.description, permission)
  }
})

test('el fallback futuro es seguro y no expone la clave técnica', () => {
  const futurePermission = 'future.secret_operation'
  const metadata = getPermissionMetadata(futurePermission)
  assert.equal(metadata.group, 'Otros permisos')
  assert.equal(metadata.description, 'Permiso administrativo adicional.')
  assert.equal(Object.values(metadata).includes(futurePermission), false)
})

test('el formulario usa textos amigables, integra el rol y conserva datos ocultos', async () => {
  const form = await readFile(new URL('../src/components/admin/UserForm.tsx', import.meta.url), 'utf8')
  assert.match(form, /<h2>Permisos de la cuenta<\/h2>/)
  assert.doesNotMatch(form, /field\('fullName', 'Nombre completo/)
  assert.doesNotMatch(form, /field\('phone', 'Teléfono/)
  assert.match(form, /<section className="admin-block admin-access-block"><h2>Datos de acceso<\/h2>[\s\S]*htmlFor="role"/)

  const fields = { username: 'soporte', email: '', fullName: 'Nombre existente', phone: '+56 9 1234 5678', password: '', confirmation: '', role: 'seller', permissions: [] }
  const payload = buildManagedUserPayload(fields, { roles: ['seller'], seller_grantable: [], reserved: [] }, 'edit')
  assert.equal(payload.full_name, fields.fullName)
  assert.equal(payload.phone, fields.phone)
})

test('listado mantiene datos, acciones y estructura responsive', async () => {
  const page = await readFile(new URL('../src/pages/admin/AdminUsersPage.tsx', import.meta.url), 'utf8')
  for (const value of ['admin-user-card__status', 'admin-user-card__role', 'admin-user-card__dates', 'Último acceso', 'Creación', 'admin-table-actions']) assert.match(page, new RegExp(value))
  const styles = await readFile(new URL('../src/styles/admin-users.css', import.meta.url), 'utf8')
  assert.match(styles, /\.admin-users-content \{ width: 100%; max-width: 1180px;/)
  assert.match(styles, /@media \(max-width: 1040px\)/)
  assert.match(styles, /@media \(max-width: 780px\)/)
  assert.match(styles, /@media \(max-width: 480px\)/)
})
