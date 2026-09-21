import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { APP_PERMISSIONS, can, PERMISSIONS } from '../src/auth/permissions.ts'

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
