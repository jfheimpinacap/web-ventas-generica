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

test('el formulario integra nombre visible en Datos de acceso y conserva teléfono oculto', async () => {
  const form = await readFile(new URL('../src/components/admin/UserForm.tsx', import.meta.url), 'utf8')
  assert.match(form, /<h2>Permisos de la cuenta<\/h2>/)
  assert.doesNotMatch(form, /Información del usuario/)
  assert.doesNotMatch(form, /field\('phone', 'Teléfono/)
  const accessStart = form.indexOf('<section className="admin-block admin-access-block">')
  const accessEnd = form.indexOf('</section>', accessStart)
  const accessBlock = form.slice(accessStart, accessEnd)
  assert.notEqual(accessStart, -1)
  assert.match(accessBlock, /<h2>Datos de acceso<\/h2>/)
  assert.match(accessBlock, /field\('fullName', 'Nombre visible \(opcional\)'\)/)
  assert.match(form, /value=\{String\(fields\[key\]\)\}/)
  assert.match(form, /onChange=\{\(event\) => setText\(key, event\.target\.value\)\}/)
  assert.ok(accessBlock.indexOf('htmlFor="role"') < accessBlock.indexOf("field('fullName'"), 'Rol y nombre visible deben formar la tercera fila lógica')
  const formStartMarker = 'return <form className="admin-user-form-page"'
  const accessBlockMarker = '<section className="admin-block admin-access-block">'
  const formStart = form.indexOf(formStartMarker)
  assert.notEqual(formStart, -1, 'No se encontró el comienzo del formulario de usuarios')
  const firstAccessBlock = form.indexOf(accessBlockMarker, formStart + formStartMarker.length)
  assert.notEqual(firstAccessBlock, -1, 'No se encontró el bloque Datos de acceso dentro del formulario')
  assert.ok(firstAccessBlock > formStart, 'Datos de acceso debe aparecer después del comienzo del formulario')
  const contentBeforeAccessBlock = form.slice(formStart + formStartMarker.length, firstAccessBlock)
  assert.doesNotMatch(contentBeforeAccessBlock, /<section\b/, 'Datos de acceso debe ser la primera sección del formulario')
  assert.doesNotMatch(contentBeforeAccessBlock, /className="[^"]*\badmin-block\b/, 'Ningún bloque administrativo debe preceder a Datos de acceso')

  const fields = { username: 'soporte', email: '', fullName: 'Nombre existente', phone: '+56 9 1234 5678', password: '', confirmation: '', role: 'seller', permissions: [] }
  const payload = buildManagedUserPayload(fields, { roles: ['seller'], seller_grantable: [], reserved: [] }, 'edit')
  assert.equal(payload.full_name, fields.fullName)
  assert.equal(payload.phone, fields.phone)
  assert.equal(buildManagedUserPayload({ ...fields, fullName: '   ' }, { roles: ['seller'], seller_grantable: [], reserved: [] }, 'edit').full_name, null)
})

test('listado continuo mantiene columnas, acciones y estructura responsive', async () => {
  const page = await readFile(new URL('../src/pages/admin/AdminUsersPage.tsx', import.meta.url), 'utf8')
  for (const value of ['admin-user-card__status', 'admin-user-card__role', 'admin-user-card__dates', 'Último acceso', 'Creación', 'admin-table-actions']) assert.match(page, new RegExp(value))
  assert.match(page, /const fullName = user\.full_name\?\.trim\(\)/)
  assert.match(page, /user\.is_active && !current \? <button/)
  assert.match(page, /useToast\(\)/)
  assert.match(page, /ADMIN_TOASTS\.user\.deactivate/)
  const styles = await readFile(new URL('../src/styles/admin-users.css', import.meta.url), 'utf8')
  assert.match(styles, /\.admin-users-content \{ width: 100%; max-width: 1180px;/)
  const listRule = styles.slice(styles.indexOf('.admin-users-list'), styles.indexOf('.admin-user-card {'))
  const cardRule = styles.slice(styles.indexOf('.admin-user-card {'), styles.indexOf('.admin-user-card__identity'))
  assert.match(listRule, /gap: 0/)
  assert.match(listRule, /border: 1px solid var\(--admin-border\)/)
  assert.match(listRule, /border-radius: var\(--admin-radius\)/)
  assert.match(cardRule, /grid-template-columns:[^;]*190px/)
  assert.match(cardRule, /border: 0/)
  assert.match(styles, /\.admin-user-card:last-child \{ border-bottom: 0; \}/)
  assert.match(styles, /\.admin-user-card > \.admin-table-actions \{ justify-content: flex-end; flex-wrap: nowrap;/)
  assert.match(styles, /@media \(max-width: 1040px\)/)
  assert.match(styles, /@media \(max-width: 780px\)/)
  assert.match(styles, /@media \(max-width: 480px\)/)
  assert.doesNotMatch(page, /style=\{/)
  assert.doesNotMatch(styles, /\.admin-user-field input[^}]*42px/)
  assert.match(styles, /\.admin-user-field input\[type="text"\][^}]*min-height: 36px[^}]*padding: \.4rem \.55rem/)
  assert.doesNotMatch(styles, /margin-(?:top|block-start):\s*-/)
  assert.doesNotMatch(styles, /\.admin-user-summary[^}]*position:\s*absolute/)
})

test('emisión de cotizaciones separa el flujo seller del selector obligatorio de support_admin', async () => {
  const editor = await readFile(new URL('../src/pages/admin/CommercialQuoteEditorPage.tsx', import.meta.url), 'utf8')
  const quoteTypes = await readFile(new URL('../src/types/commercialQuote.ts', import.meta.url), 'utf8')
  const userApi = await readFile(new URL('../src/services/adminUsersApi.ts', import.meta.url), 'utf8')

  const issueStart = editor.indexOf('const issue = async')
  const issueEnd = editor.indexOf('const closePdfPreview', issueStart)
  assert.notEqual(issueStart, -1, 'No se encontró el inicio del bloque issue')
  assert.notEqual(issueEnd, -1, 'No se encontró el límite final del bloque issue')
  const issueBlock = editor.slice(issueStart, issueEnd)
  const issueCatch = issueBlock.match(/catch\(e\) \{([\s\S]*?)\} finally/)
  assert.ok(issueCatch, 'No se encontró el catch de emisión dentro del bloque issue')

  assert.match(editor, /const supportAdmin = isSupportAdmin/)
  assert.match(editor, /if \(!supportAdmin \|\| routeId\) return/)
  assert.match(editor, /listManagedUsers\(\{ role: 'seller', is_active: true \}/)
  assert.match(editor, /setSelectedSellerId\] = useState<number \| null>\(null\)/)
  assert.match(editor, /Vendedor responsable \*/)
  assert.match(editor, /<option value="">Seleccione un vendedor<\/option>/)
  assert.match(editor, /eligibleSellers\.length === 0 \|\| selectedSellerId === null/)
  assert.match(editor, /supportAdmin && selectedSellerId !== null \? \{ seller_user_id: selectedSellerId \} : \{\}/)
  assert.match(issueBlock, /const issued = await issueCommercialQuote\(issuePayload, idempotencyKey\)/)
  assert.match(issueCatch[1], /toast\.error\(ADMIN_TOASTS\.commercialQuote\.issue\.error\)/)
  assert.match(issueCatch[1], /setError\(getSafeApiErrorMessage\(/)
  assert.doesNotMatch(issueBlock, /setSelectedSellerId\(/)
  assert.match(issueBlock, /const issued = await issueCommercialQuote\([\s\S]*?apply\(issued\)[\s\S]*?toast\.success\(ADMIN_TOASTS\.commercialQuote\.issue\.success\)[\s\S]*?navigate\(`/)
  assert.match(quoteTypes, /seller_user_id\?: number/)
  assert.match(userApi, /authFetch<ManagedUser\[]>\('\/admin\/users'/)
})
