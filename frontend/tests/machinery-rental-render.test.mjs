import assert from 'node:assert/strict'
import { after, test } from 'node:test'
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createHash } from 'node:crypto'
import { build } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

// Use the same SSR build path as prerender, then load through Node's normal module resolver.
const cacheRoot = fileURLToPath(new URL('../node_modules/.cache/', import.meta.url))
mkdirSync(cacheRoot, { recursive: true })
const temp = mkdtempSync(join(cacheRoot, 'rental-render-'))
after(() => rmSync(temp, { recursive: true, force: true }))
const result = await build({ logLevel: 'error', build: { ssr: fileURLToPath(new URL('./machinery-rental-render-entry.ts', import.meta.url)), write: false, rollupOptions: { output: { format: 'es' } } } })
const bundlePath = join(temp, 'rental-test.mjs')
writeFileSync(bundlePath, result.output.find(item => item.type === 'chunk' && item.isEntry).code)
const api = await import(pathToFileURL(bundlePath).href)
const { getAdditionalProductSpecs, ProductAdminPreview, MachineryDetailFacts, ProductIncludedServices, MemoryRouter, RentalRates, ProductCard, ProductForm, convertProductType, MachinerySalesSection, buildProductJsonLd } = api
const category = { id: 2, name: 'Brazos', slug: 'brazos', parent: 1, product_type: 'machinery', is_active: true }
const root = { ...category, id: 1, name: 'Maquinaria', slug: 'maquinaria', parent: null }
const product = { id: 1, name: 'Modelo de prueba aislado', slug: 'arriendo-prueba', category, brand: { id: 1, name: 'Marca prueba' }, commercial_mode: 'rental', product_type: 'machinery', condition: 'not_applicable', stock_status: 'on_request', model: 'Modelo', machine_weight_kg: 6200, working_height_m: 14.5, platform_height_m: 12.5, maximum_load_capacity_kg: 230, power_source: 'diesel', price: null, price_visible: true, price_currency: 'CLP', price_tax_mode: 'plus_vat', rental_price_day: '18999', rental_price_week: '250000', rental_price_month: null, images: [], specs: [] }
const values = { ...product, name: '', category: 2, brand: 1, supplier: null, technical_sheet: null, year: null, hours_meter: null, description: '', short_description: '', sku: '', terrain_type: null, includes_technical_review: false, includes_commercial_technical_advice: false, includes_coordinated_delivery: false }
const render = node => renderToStaticMarkup(React.createElement(MemoryRouter, null, node))

test('tarifas legibles: tres filas, Consultar por tarifa ausente y sin importes ocultos', () => {
  const html = render(React.createElement(RentalRates, { product }))
  assert.match(html, /Precio día/); assert.match(html, /Precio semana/); assert.match(html, /Precio mes/)
  assert.match(html, /\$18.999/); assert.match(html, /\$250.000/)
  assert.match(html, /<strong>Consultar<\/strong>/)
  assert.doesNotMatch(html, /Consultar.*?IVA<\/span>.*?Precio/s)
  assert.doesNotMatch(html, /\$0/)
  const hidden = render(React.createElement(RentalRates, { product: { ...product, price_visible: false } }))
  assert.match(hidden, /Consultar tarifas/); assert.doesNotMatch(hidden, /18.999|250.000|\$|\+ IVA/)
  assert.match(hidden, /Traslado se cotiza por separado/); assert.match(hidden, /Disponibilidad sujeta a confirmación/)
})

test('tarjeta arriendo presenta siete características antes de tarifas sin stock/condición', () => {
  const html = render(React.createElement(ProductCard, { product }))
  for (const label of ['Marca', 'Peso de la máquina', 'Modelo', 'Fuente de energía', 'Capacidad de carga', 'Altura de plataforma', 'Altura de trabajo']) assert.ok(html.includes(label), label)
  assert.ok(html.indexOf('Altura de trabajo') < html.indexOf('Precio día'))
  assert.doesNotMatch(html, /badge--stock|Condición|Stock/)
  assert.match(html, /Maquinaria para arriendo/)
})

test('formulario arriendo omite condición, stock, moneda e IVA editables y mantiene pestañas ordenadas', () => {
  const html = render(React.createElement(ProductForm, { initialValues: values, categories: [root, category], brands: [], suppliers: [], technicalSheets: [], formId: 'test-form', onCancel() {}, onSubmit: async () => {}, isSubmitting: false, error: null }))
  assert.doesNotMatch(html, />Condición|>Stock|>Moneda|<option value="USD"/)
  assert.equal((html.match(/\+ IVA/g) ?? []).length, 3)
  assert.match(html, /Servicio técnico en caso de falla en obra/)
  assert.match(html, /Coordinación del traslado/)
  assert.match(html, /Asesoría técnica/)
  const tabs = ['Maquinarias para venta', 'Maquinaria para arriendo', 'Servicio técnico', 'Repuestos'].map(label => html.indexOf(label))
  assert.ok(tabs.every((position, i) => i === 0 || position > tabs[i - 1]))
  assert.match(html, /product-tab-machinery_rental[^>]*aria-selected="true"/)
  assert.doesNotMatch(html, /Revisión técnica/)
})

test('cambiar modalidad limpia precios e indicadores incompatibles y mantiene alturas independientes', () => {
  const rental = convertProductType({ ...values, commercial_mode: 'sale', price: '900000', price_currency: 'USD', price_tax_mode: 'vat_included', includes_technical_review: true }, 'machinery', 'rental')
  assert.equal(rental.price, null); assert.equal(rental.rental_price_day, null)
  assert.equal(rental.price_currency, 'CLP'); assert.equal(rental.price_tax_mode, 'plus_vat')
  assert.equal(rental.condition, 'not_applicable'); assert.equal(rental.includes_technical_review, false)
  assert.equal(rental.platform_height_m, 12.5); assert.equal(rental.working_height_m, 14.5)
})

test('contrato frontend normaliza modalidad y envía tres importes numéricos o null', async () => {
  const normalized = api.normalizeProductDetail({ ...product, rental_includes_onsite_service: true })
  assert.equal(normalized.rental_price_day, '18999'); assert.equal(normalized.commercial_mode, 'rental')
  assert.equal(normalized.rental_includes_onsite_service, true)
  const originalFetch = globalThis.fetch
  const originalStorage = globalThis.localStorage
  globalThis.localStorage = { getItem: () => 'isolated-test-token' }
  let sent
  globalThis.fetch = async (_, options) => { sent = JSON.parse(options.body); return new Response(JSON.stringify(product), { status: 200 }) }
  try {
    await api.createProduct({ ...values, rental_price_day: '18.999', rental_price_week: '250000', rental_price_month: '' })
    assert.equal(sent.rental_price_day, 18999); assert.equal(sent.rental_price_week, 250000); assert.equal(sent.rental_price_month, null)
    assert.equal(sent.price, null)
  } finally { globalThis.fetch = originalFetch; if (originalStorage === undefined) delete globalThis.localStorage; else globalThis.localStorage = originalStorage }
})

test('datos estructurados arriendo no publican ofertas de compra ni condición ficticia', () => {
  const json = buildProductJsonLd({ ...product, condition: 'new', price: '18999', supplier: { name: 'Interno' } }, 'http://localhost/producto/arriendo-prueba')
  assert.equal(json.offers, undefined); assert.equal(json.itemCondition, undefined)
  assert.doesNotMatch(JSON.stringify(json), /Interno|18999|RentalPrice/)
})

test('Home enlaza el PNG estático completo en tercer lugar sin texto superpuesto', () => {
  const html = render(React.createElement(MachinerySalesSection))
  assert.ok(html.indexOf('/maquinaria-nueva') < html.indexOf('/maquinaria-usada'))
  assert.ok(html.indexOf('/maquinaria-usada') < html.indexOf('/maquinaria-arriendo'))
  assert.match(html, /src="\/images\/maquinaria-arriendo.png"/)
  assert.match(html, /alt="Arriendo de maquinaria/)
  const png = readFileSync(new URL('../public/images/maquinaria-arriendo.png', import.meta.url))
  assert.equal(png.readUInt32BE(16), 1536); assert.equal(png.readUInt32BE(20), 1024); assert.equal(png[25], 6)
  assert.equal(createHash('sha256').update(png).digest('hex'), '7f94ab04a8584fcd0f4c612d05fb030faffe7bdee2cc3c257c9dd49eda2af596')
})

test('detalle arriendo oculta condición/stock/año/horómetro vacíos y separa servicios de venta', () => {
  const html = render(React.createElement(MachineryDetailFacts, { product: { ...product, year: null, hours_meter: null } }))
  assert.doesNotMatch(html, /Condición|Stock|Año|Horómetro/)
  assert.match(html, /Altura de plataforma/); assert.match(html, /Altura de trabajo/)
  assert.match(html, /12,5/); assert.match(html, /14,5/)
  const included = render(React.createElement(ProductIncludedServices, { product: { ...product, includes_technical_review: true, rental_includes_onsite_service: true } }))
  assert.match(included, /Servicio técnico en caso de falla en obra/)
  assert.doesNotMatch(included, /Revisión técnica|Asesoría técnica|Coordinación del traslado/)
  const sale = render(React.createElement(ProductIncludedServices, { product: { ...product, commercial_mode: 'sale', includes_technical_review: true, rental_includes_onsite_service: true } }))
  assert.match(sale, /Revisión técnica/); assert.doesNotMatch(sale, /falla en obra/)
})

test('vista previa del vendedor mantiene marca y precio chileno escrito con separadores', () => {
  const html = render(React.createElement(ProductAdminPreview, { values: { ...values, rental_price_day: '18.999' }, categories: [root, category], brands: [{ id: 1, name: 'Marca prueba' }], imageUrl: '/images/maquinaria-arriendo.png', imageAlt: 'Prueba' }))
  assert.match(html, /Marca prueba/)
  assert.match(html, /\$18.999/)
  assert.doesNotMatch(html, /badge--stock/)
})


test('venta y arriendo publican ambas alturas, año y horómetro guardados, incluido cero explícito', () => {
  for (const mode of ['sale', 'rental']) {
    for (const casing of ['snake', 'camel']) {
      const fields = casing === 'snake'
        ? { commercial_mode: mode, working_height_m: 14.3, platform_height_m: 12.3, hours_meter: 0, machine_weight_kg: 6200, maximum_load_capacity_kg: 230, power_source: 'diesel', terrain_type: 'outdoor' }
        : { commercialMode: mode, workingHeightM: 14.3, platformHeightM: 12.3, hoursMeter: 0, machineWeightKg: 6200, maximumLoadCapacityKg: 230, powerSource: 'diesel', terrainType: 'outdoor' }
      const dto = { id: 7, product_type: 'machinery', name: 'ALZA HOMBRE TIPO TIJERA DIESEL', category, model: 'Modelo completo', brand: { id: 1, name: 'Marca prueba' }, year: 2020, condition: 'used', stock_status: 'available', ...fields }
      const normalized = api.normalizeProductDetail(dto)
      assert.equal(normalized.hours_meter, 0)
      const html = render(React.createElement(MachineryDetailFacts, { product: normalized }))
      for (const text of ['Marca prueba', 'Modelo completo', '14,3', '12,3', '6.200', '230', 'Diésel', 'Exterior', '2020', '0 h']) assert.ok(html.includes(text), mode + ': ' + text)
      assert.equal((html.match(/Altura de trabajo/g) ?? []).length, 1)
      assert.equal((html.match(/Altura de plataforma/g) ?? []).length, 1)
      if (mode === 'rental') assert.doesNotMatch(html, /Condición|Stock/)
      else { assert.match(html, /Condición/); assert.match(html, /Stock/) }
    }
  }
  const empty = api.normalizeProductDetail({ ...product, year: null, hours_meter: null, working_height_m: null, platform_height_m: null })
  const html = render(React.createElement(MachineryDetailFacts, { product: empty }))
  assert.doesNotMatch(html, /Año|Horómetro|Altura de trabajo|Altura de plataforma/)
})

test('las especificaciones adicionales conservan datos previos y omiten características ya publicadas', () => {
  const specs = [
    { id: 1, name: 'Altura máxima de trabajo (m)', value: '14,3', unit: 'm' },
    { id: 2, name: 'A-Altura plataforma levantada', value: '12,3', unit: 'm' },
    { id: 3, name: 'Peso de la máquina', value: '6200', unit: 'kg' },
    { id: 4, name: 'Frenos', value: 'Multidisco', unit: '' },
    { id: 5, name: 'Tamaño de neumático', value: 'Largo completo de prueba', unit: '' },
  ]
  assert.deepEqual(getAdditionalProductSpecs({ ...product, specs }).map(item => item.id), [4, 5])
  assert.deepEqual(getAdditionalProductSpecs({ ...product, specs, working_height_m: null, platform_height_m: null, machine_weight_kg: null }).map(item => item.id), [1, 2, 3, 4, 5])
})

test('tarjetas conservan títulos y valores completos de distinta longitud y precios de venta', () => {
  const examples = [
    ['ALZA HOMBRE TIPO TIJERA DIESEL', '15500000', '$15.500.000 + IVA'],
    ['Brazo articulado diésel con título largo para comprobar todas sus palabras', '14000000', '$14.000.000 + IVA'],
    ['GRUA HORQUILLA ELECTRICA', '7500000', '$7.500.000 + IVA'],
  ]
  for (const [name, price, formatted] of examples) {
    const model = 'Modelo de longitud variable con descripción técnica íntegra'
    const html = render(React.createElement(ProductCard, { product: { ...product, name, model, commercial_mode: 'sale', price, condition: 'used' } }))
    assert.ok(html.includes(name)); assert.ok(html.includes(model)); assert.ok(html.includes(formatted))
  }
  const usd = render(React.createElement(ProductCard, { product: { ...product, commercial_mode: 'sale', price: '15500000', price_currency: 'USD', price_tax_mode: 'vat_included', condition: 'new' } }))
  assert.match(usd, /USD 15.500.000 IVA incluido/)
})
