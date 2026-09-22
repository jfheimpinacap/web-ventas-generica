import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = path => readFile(new URL(`../${path}`, import.meta.url), 'utf8')
const pages = [
  'src/pages/admin/AdminProductCreatePage.tsx', 'src/pages/admin/AdminProductEditPage.tsx',
  'src/pages/admin/AdminTechnicalSheetsPage.tsx', 'src/pages/admin/AdminCategoryFormPage.tsx',
  'src/pages/admin/AdminCategoriesPage.tsx', 'src/pages/admin/AdminBrandFormPage.tsx',
  'src/pages/admin/AdminBrandsPage.tsx', 'src/pages/admin/AdminSupplierFormPage.tsx',
  'src/pages/admin/AdminSuppliersPage.tsx', 'src/pages/admin/AdminCustomerFormPage.tsx',
  'src/pages/admin/AdminCustomersPage.tsx', 'src/pages/admin/AdminQuoteDetailPage.tsx',
  'src/pages/admin/AdminQuotesPage.tsx', 'src/pages/admin/CommercialQuoteEditorPage.tsx',
  'src/pages/admin/AdminPromotionFormPage.tsx', 'src/pages/admin/AdminPromotionsPage.tsx',
  'src/pages/admin/AdminHomeSectionsPage.tsx', 'src/pages/admin/AdminUserCreatePage.tsx',
  'src/pages/admin/AdminUserEditPage.tsx', 'src/pages/admin/AdminUsersPage.tsx',
]

test('define cuatro variantes con semántica visual consistente', async () => {
  const [model, css] = await Promise.all([source('src/toasts/toastModel.ts'), source('src/styles/toasts.css')])
  assert.match(model, /\['success', 'error', 'warning', 'info'\]/)
  assert.match(css, /toast--success[^}]+#15803d/); assert.match(css, /toast--error[^}]+#b91c1c/)
  assert.match(css, /toast--warning[^}]+#b45309/); assert.match(css, /toast--info[^}]+#1d4ed8/)
})

test('centraliza mensajes amigables y distingue eliminar de desactivar', async () => {
  const messages = await source('src/toasts/adminToastMessages.ts')
  assert.match(messages, /Producto eliminado correctamente/)
  assert.match(messages, /Proveedor desactivado correctamente/)
  assert.doesNotMatch(messages, /seller_user_id|Authorization|\/api\/|stack|token/i)
})

test('monta el provider sobre el router para sobrevivir a navigate', async () => {
  const app = await source('src/App.tsx')
  assert.match(app, /<ToastProvider><SystemDialogProvider><AppRouter \/><\/SystemDialogProvider><\/ToastProvider>/)
})

test('ofrece región viva, alertas de error y cierre accesible', async () => {
  const context = await source('src/toasts/ToastContext.tsx')
  assert.match(context, /aria-live="polite"/); assert.match(context, /role=\{toast\.variant === 'error' \? 'alert' : 'status'\}/)
  assert.match(context, /aria-label=\{`Cerrar notificación:/)
})

test('limpia temporizadores, limita la cola y evita identidad aleatoria', async () => {
  const [context, model] = await Promise.all([source('src/toasts/ToastContext.tsx'), source('src/toasts/toastModel.ts')])
  assert.match(context, /timers\.current\.forEach\(clearTimeout\)/); assert.match(model, /TOAST_QUEUE_LIMIT = 4/)
  assert.match(model, /slice\(-limit\)/); assert.doesNotMatch(context, /Math\.random|window|document|localStorage|sessionStorage/)
})

test('integra éxito y error en cada módulo administrativo con mutaciones', async () => {
  for (const page of pages) {
    const code = await source(page)
    assert.match(code, /useToast/, page); assert.match(code, /toast\.success/, page); assert.match(code, /toast\.error/, page)
  }
})

test('emite éxitos después de esperar la API', async () => {
  for (const page of pages) {
    const code = await source(page)
    const firstAwait = code.search(/await (create|update|delete|deactivate|reactivate|rename|replace|issue|save)/)
    const firstSuccess = code.indexOf('toast.success')
    assert.ok(firstAwait >= 0 && firstSuccess > firstAwait, page)
  }
})

test('no agrega toasts a cargas GET, filtros o búsquedas', async () => {
  const quotes = await source('src/pages/admin/AdminQuotesPage.tsx')
  assert.doesNotMatch(quotes.slice(quotes.indexOf('function GeneratedQuotesView')), /toast\./)
})

test('preserva los flujos diferenciados de 401 y no redirige 403 al login', async () => {
  const files = await Promise.all(['src/pages/admin/AdminUserCreatePage.tsx', 'src/pages/admin/AdminUserEditPage.tsx'].map(source))
  for (const code of files) { assert.match(code, /status === 401/); assert.doesNotMatch(code, /status === 403[\s\S]{0,100}\/login/) }
})

test('no cambia dependencias y mantiene compatibilidad SSR', async () => {
  const [pkg, context] = await Promise.all([source('package.json'), source('src/toasts/ToastContext.tsx')])
  assert.doesNotMatch(pkg, /toastify|hot-toast|sonner/i); assert.doesNotMatch(context, /window|document/)
})
