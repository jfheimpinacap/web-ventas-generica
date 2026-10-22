import assert from 'node:assert/strict'
import test from 'node:test'
import { catalogPrice, formatRentalAmount, parseRentalPriceInput } from '../src/utils/rental.ts'
import { catalogFacets, catalogRequestParams, catalogSelections, clearCatalogFilters, contextCategories, contextProducts, filterCatalogProducts, resolveCatalogContext, toggleCatalogFacet } from '../src/utils/catalogFilters.ts'

const categories = [{ id: 1, name: 'Maquinaria', slug: 'maquinaria', parent: null, product_type: 'machinery' }, { id: 2, name: 'Brazos', slug: 'brazos', parent: 1, product_type: 'machinery' }]
const brands = [{ id: 1, name: 'Marca', slug: 'marca' }]
const sale = { id: 1, name: 'Venta', category: categories[1], product_type: 'machinery', brand: brands[0], condition: 'new', stock_status: 'available', price: '50000', price_visible: true }
const rental = { ...sale, id: 2, commercial_mode: 'rental', condition: 'not_applicable', stock_status: 'on_request', price: null, rental_price_day: '18999', rental_price_week: '250000', rental_price_month: null }
const rentalConfig = { canonicalPath: '/maquinaria-arriendo', title: 'Maquinaria para arriendo', fixedProductType: 'machinery', commercialMode: 'rental' }

test('CLP entero: valida separadores chilenos, vacíos y límites sin inventar ceros', () => {
  for (const [input, expected] of [['18.999', 18999], ['250000', 250000], ['0', 0], ['', null], [null, null], ['  ', null]]) {
    assert.deepEqual(parseRentalPriceInput(input), { value: expected, error: null })
  }
  for (const input of ['-1', '18.99', '1.5', '1,5', '18.999,00', 'USD100', '1000000000000', 'Infinity', '1e3']) assert.ok(parseRentalPriceInput(input).error, input)
  assert.equal(formatRentalAmount(null), null)
  assert.equal(formatRentalAmount(''), null)
  assert.equal(formatRentalAmount('18999'), '$18.999')
  assert.equal(formatRentalAmount('250000'), '$250.000')
})

test('contexto arriendo prevalece, no hereda condición/stock y usa solo tarifa día', () => {
  const params = new URLSearchParams('commercial_mode=sale&condition=used&stock_status=sold')
  const context = resolveCatalogContext(categories, params, rentalConfig)
  const scoped = contextCategories(categories, context)
  const selected = catalogSelections(params, scoped, brands, context)
  assert.deepEqual(selected.condition, [])
  assert.deepEqual(selected.stock_status, [])
  assert.deepEqual(catalogRequestParams(context, params), { commercial_mode: 'rental', product_type: 'machinery', condition: '', search: '' })
  assert.deepEqual(contextProducts([sale, rental], categories, context).map(p => p.id), [2])
  const salesContext = resolveCatalogContext(categories, new URLSearchParams(), { ...rentalConfig, commercialMode: 'sale', fixedCondition: 'new', canonicalPath: '/maquinaria-nueva' })
  assert.deepEqual(contextProducts([sale, rental], categories, salesContext).map(p => p.id), [1])
  assert.equal(catalogPrice(rental), 18999)
  assert.equal(catalogPrice({ ...rental, price_visible: false }), null)
  assert.equal(catalogPrice({ ...rental, rental_price_day: null }), null)
})

test('contadores, rangos, limpiar y reconstruir la URL mantienen el contexto de arriendo', () => {
  const context = resolveCatalogContext(categories, new URLSearchParams(), rentalConfig)
  let params = new URLSearchParams('condition=new&stock_status=available&min_price=18000&max_price=20000')
  const selections = catalogSelections(params, categories, brands, context)
  const base = contextProducts([sale, rental], categories, context)
  assert.deepEqual(filterCatalogProducts(base, categories, selections, params).map(p => p.id), [2])
  const facets = catalogFacets(base, categories, brands, selections, params)
  assert.equal(facets.brand[0].count, 1)
  assert.equal(facets.category.find(c => c.value === '1').count, 1)
  assert.deepEqual(facets.condition, [])
  assert.deepEqual(facets.stock_status, [])
  params = toggleCatalogFacet(params, context, selections, 'brand', '1')
  params = clearCatalogFilters(params, context)
  const restored = resolveCatalogContext(categories, new URLSearchParams(params), rentalConfig)
  assert.equal(restored.commercialMode, 'rental')
  assert.equal(catalogRequestParams(restored, params).commercial_mode, 'rental')
  assert.equal(catalogPrice(sale), 50000)
})
