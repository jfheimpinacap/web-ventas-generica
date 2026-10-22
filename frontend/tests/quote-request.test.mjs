import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

// Exercise the loader, submission and components used by QuotePage, with the
// existing SSR toolchain. Every HTTP request is intercepted; no real API is used.
const cacheRoot = fileURLToPath(new URL('../node_modules/.cache/', import.meta.url))
mkdirSync(cacheRoot, { recursive: true })
const temp = mkdtempSync(join(cacheRoot, 'quote-request-'))
after(() => {
  if (!temp.startsWith(join(cacheRoot, 'quote-request-'))) throw new Error('Unexpected test directory')
  rmSync(temp, { recursive: true, force: true })
})
const result = await build({ logLevel: 'error', build: { ssr: fileURLToPath(new URL('./quote-request-entry.ts', import.meta.url)), write: false, rollupOptions: { output: { format: 'es' } } } })
const bundlePath = join(temp, 'quote-request.mjs')
writeFileSync(bundlePath, result.output.find(item => item.type === 'chunk' && item.isEntry).code)
const api = await import(pathToFileURL(bundlePath).href)
const render = (component, props, path = '/cotizar') => renderToStaticMarkup(React.createElement(api.MemoryRouter, { initialEntries: [path] }, React.createElement(component, props)))
const preview = selection => render(api.QuoteProductPreview, { selection })
const form = {
  customer_name: ' Cliente ', customer_phone: ' +56912345678 ', customer_email: ' cliente@example.test ',
  company_name: ' Empresa ', city: ' Santiago ', preferred_contact_method: 'whatsapp', message: ' Consultar equipo ',
}
const expectedForm = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()]))
const sale = {
  id: 7, name: 'Equipo venta', slug: 'equipo-venta', product_type: 'machinery', commercial_mode: 'sale',
  category: { id: 1, name: 'Maquinaria' }, brand: { id: 1, name: 'Marca' },
  condition: 'used', stock_status: 'available', price: '15500000', price_visible: true,
  price_currency: 'CLP', price_tax_mode: 'plus_vat',
}
const rentalDto = {
  ...sale, id: 8, name: 'Equipo arriendo', slug: 'equipo-arriendo', commercial_mode: 'rental', price: null,
  condition: undefined, stock_status: undefined, rental_price_day: 18999, rental_price_week: 250000, rental_price_month: 650000,
}
const rental = api.normalizeProductDetail(rentalDto)
const response = (data, status = 200) => new Response(JSON.stringify(data), { status })
function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}
function startSelection(id) {
  let current
  const history = []
  let finish
  const done = new Promise(resolve => { finish = resolve })
  const cancel = api.loadQuoteProductSelection(id, value => {
    current = value
    history.push(value)
    if (value.status !== 'loading') finish(value)
  })
  return { get current() { return current }, history, done, cancel }
}
function mockRequests(t, getResponse) {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options = {}) => {
    const path = new URL(url).pathname
    const method = options.method ?? 'GET'
    calls.push({ path, method, body: options.body ? JSON.parse(options.body) : undefined })
    if (method === 'POST') {
      assert.equal(path, '/api/public/quote-requests/')
      return response({ id: 1 })
    }
    return getResponse(path)
  })
  return calls
}

for (const product of [sale, rentalDto]) {
  test(`carga directa por ID y envío de ${product.commercial_mode} conservan producto y formulario`, async t => {
    const calls = mockRequests(t, path => {
      assert.equal(path, `/api/public/products/${product.id}/`)
      return response(product)
    })
    const load = startSelection(api.parseQuoteProductId(String(product.id)))
    assert.equal(load.current.status, 'loading')
    const selected = await load.done
    assert.equal(selected.status, 'ready')
    assert.equal(selected.product.commercial_mode, product.commercial_mode)
    assert.match(preview(selected), new RegExp(product.name))
    await api.submitQuoteRequest(form, selected)
    assert.deepEqual(calls, [
      { path: `/api/public/products/${product.id}/`, method: 'GET', body: undefined },
      { path: '/api/public/quote-requests/', method: 'POST', body: { ...expectedForm, product: product.id } },
    ])
    // The existing backend adds the rental identification; no totals or dates.
    assert.equal(calls[1].body.message, 'Consultar equipo')
    load.cancel()
  })
}

test('cotización general no carga listados ni envía product', async t => {
  const calls = mockRequests(t, () => assert.fail('General quotes must not fetch a product'))
  const load = startSelection(api.parseQuoteProductId(null))
  const selection = await load.done
  assert.equal(selection.status, 'general')
  const html = preview(selection)
  assert.match(html, /solicitud general de cotización/)
  assert.doesNotMatch(html, /role="alert"|Cargando/)
  await api.submitQuoteRequest(form, selection)
  assert.deepEqual(calls, [{ path: '/api/public/quote-requests/', method: 'POST', body: expectedForm }])
})

test('ID inválido muestra aviso explícito y conserva la solicitud general', async t => {
  const calls = mockRequests(t, () => assert.fail('Invalid IDs must not trigger a GET'))
  for (const input of ['0', '-1', 'abc', '1.5', '9007199254740992']) {
    const id = api.parseQuoteProductId(input)
    assert.equal(id, null)
    const selection = await startSelection(id).done
    assert.equal(selection.status, 'unavailable')
    assert.match(preview(selection), /role="alert"[^>]*>No fue posible cargar/)
    assert.deepEqual(api.buildQuoteRequestPayload(form, selection), expectedForm)
  }
  await api.submitQuoteRequest(form, await startSelection(null).done)
  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0].body, expectedForm)
})

for (const status of [403, 404, 'network']) {
  test(`producto inaccesible (${status}) muestra aviso y permite envío general explícito`, async t => {
    const calls = mockRequests(t, () => {
      if (status === 'network') throw new TypeError('Isolated network failure')
      return response({ detail: 'Unavailable' }, status)
    })
    const selection = await startSelection(8).done
    assert.equal(selection.status, 'unavailable')
    assert.match(preview(selection), /No fue posible cargar el producto seleccionado/)
    assert.match(preview(selection), /href="\/catalogo"/)
    await api.submitQuoteRequest(form, selection)
    assert.deepEqual(calls[1].body, expectedForm)
  })
}

test('enviar durante la carga no hace POST; después envía el ID solicitado', async t => {
  const pending = deferred()
  const calls = mockRequests(t, () => pending.promise)
  const load = startSelection(8)
  const html = preview(load.current)
  assert.match(html, /Cargando producto seleccionado/)
  assert.doesNotMatch(html, /No hay producto|solicitud general/)
  await assert.rejects(api.submitQuoteRequest(form, load.current), { message: api.QUOTE_PRODUCT_LOADING_MESSAGE })
  assert.equal(calls.length, 1)
  assert.equal(calls[0].method, 'GET')
  pending.resolve(response(rental))
  await api.submitQuoteRequest(form, await load.done)
  assert.equal(calls[1].body.product, 8)
})

test('cambio de URL bloquea el ID anterior antes del efecto e ignora respuestas atrasadas', async t => {
  const pending = deferred()
  mockRequests(t, path => path.endsWith('/7/') ? pending.promise : response(rental))
  const old = startSelection(7)
  const changed = api.currentQuoteProductSelection(8, old.current)
  assert.equal(changed.status, 'loading')
  assert.equal(changed.requestedId, 8)
  await assert.rejects(api.submitQuoteRequest(form, changed), { message: api.QUOTE_PRODUCT_LOADING_MESSAGE })
  old.cancel()
  const selected = await startSelection(8).done
  pending.resolve(response(sale))
  await new Promise(setImmediate)
  assert.equal(old.history.length, 1)
  assert.equal(selected.product.id, 8)
  assert.equal(api.currentQuoteProductSelection(7, selected).status, 'loading')
  assert.equal(api.currentQuoteProductSelection(undefined, selected).status, 'general')
  assert.equal(api.currentQuoteProductSelection(null, selected).status, 'unavailable')
})

test('una respuesta con otro ID no asocia un producto distinto', async t => {
  mockRequests(t, () => response(sale))
  const selection = await startSelection(8).done
  assert.equal(selection.status, 'unavailable')
  assert.equal(selection.product, null)
})

test('el payload conserva el producto durante un POST pendiente', async t => {
  const pending = deferred()
  let sent
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(new URL(url).pathname, '/api/public/quote-requests/')
    sent = JSON.parse(options.body)
    return pending.promise
  })
  const selection = { requestedId: 8, status: 'ready', product: rental }
  const submitting = api.submitQuoteRequest(form, selection)
  const changed = api.currentQuoteProductSelection(7, selection)
  assert.equal(changed.status, 'loading')
  assert.deepEqual(sent, { ...expectedForm, product: 8 })
  pending.resolve(response({ id: 1 }))
  await submitting
})

test('resumen arriendo identifica equipo, tres tarifas y notas sin condición ni stock', () => {
  const html = preview({ requestedId: 8, status: 'ready', product: rental })
  for (const value of ['Equipo arriendo', 'Marca', 'Maquinaria', 'Solicitud de arriendo', 'Precio día', 'Precio semana', 'Precio mes', '$18.999', '$250.000', '$650.000', 'Traslado se cotiza por separado.', 'Disponibilidad sujeta a confirmación.']) assert.ok(html.includes(value), value)
  assert.equal((html.match(/\+ IVA/g) ?? []).length, 3)
  assert.match(html, /href="\/producto\/equipo-arriendo"/)
  assert.doesNotMatch(html, /Condición:|Disponibilidad:|Stock|Bajo consulta|No aplica/)
})

test('Mostrar precio desactivado no filtra importes y una tarifa ausente muestra Consultar', () => {
  const hidden = preview({ requestedId: 8, status: 'ready', product: { ...rental, price_visible: false } })
  assert.match(hidden, /Consultar tarifas/)
  assert.match(hidden, /Traslado se cotiza por separado/)
  assert.match(hidden, /Disponibilidad sujeta a confirmación/)
  assert.doesNotMatch(hidden, /18[.,]999|250[.,]000|650[.,]000|\$|\+ IVA|Condición:|Disponibilidad:/)
  const missing = preview({ requestedId: 8, status: 'ready', product: { ...rental, rental_price_week: null } })
  assert.match(missing, /Precio semana:<\/dt><dd><strong>Consultar<\/strong>/)
  assert.match(missing, /\$18.999/)
})

test('resumen de venta conserva condición, disponibilidad y precio', () => {
  const html = preview({ requestedId: 7, status: 'ready', product: sale })
  for (const value of ['Condición:', 'Usado', 'Disponibilidad:', 'Disponible', '$15.500.000 + IVA']) assert.ok(html.includes(value), value)
  assert.doesNotMatch(html, /Solicitud de arriendo|Precio día|Traslado se cotiza/)
})

test('QuotePage deshabilita Enviar desde el primer render con ID y mantiene la cotización general', () => {
  const pending = render(api.QuotePage, {}, '/cotizar?product=8')
  assert.match(pending, /<form class="quote-form" aria-busy="true"/)
  assert.match(pending, /type="submit" disabled="">Cargando producto/)
  const general = render(api.QuotePage, {}, '/cotizar')
  assert.match(general, /<form class="quote-form" aria-busy="false"/)
  assert.match(general, /type="submit">Enviar/)
  const invalid = render(api.QuotePage, {}, '/cotizar?product=invalid')
  assert.match(invalid, /No fue posible cargar el producto seleccionado/)
  assert.match(invalid, /type="submit">Enviar/)
})
