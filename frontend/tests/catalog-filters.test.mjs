import assert from 'node:assert/strict'
import test from 'node:test'

import {
  catalogFacets, catalogRequestParams, catalogSelections, categoryDescendants,
  clearCatalogFilters, contextCategories, contextProducts, filterCatalogProducts,
  readFacetValues, resolveCatalogContext, rootCategory, toggleCatalogFacet,
} from '../src/utils/catalogFilters.ts'
import { buildSidebarMenuFromCategories } from '../src/utils/formatters.ts'
import { createSidebarAccordionState, sidebarAccordionReducer } from '../src/utils/sidebarAccordion.ts'

const category = (id, name, parent = null, product_type = 'machinery', extra = {}) => ({
  id, name, slug: `category-${id}`, parent, product_type, order: id, is_active: true, ...extra,
})
const categories = [
  category(6, 'Maquinaria'), category(61, 'Elevación', 6),
  category(611, 'Brazos', 61), category(612, 'Tijeras', 61), category(62, 'Movimiento', 6),
  category(7, 'Otra familia'), category(71, 'Otra máquina', 7),
  category(9, 'Repuestos', null, 'spare_part'), category(91, 'Filtros', 9, 'spare_part'),
  category(10, 'Servicios', null, 'service'), category(101, 'Mantención', 10, 'service'),
  category(619, 'Inactiva', 61, 'machinery', { is_active: false }),
]
const brands = [
  { id: 1, name: 'EP', slug: 'ep', is_active: true },
  { id: 2, name: 'LGMG', slug: 'lgmg', is_active: true },
  { id: 3, name: 'Otra', slug: 'otra', is_active: true },
]
const product = (id, categoryId, brandId, condition = 'new', stock_status = 'available', extra = {}) => ({
  id, name: `Producto ${id}`, category: categories.find((item) => item.id === categoryId),
  brand: brands.find((item) => item.id === brandId) ?? null,
  product_type: categories.find((item) => item.id === categoryId).product_type,
  condition, stock_status, price_visible: true, price: String(id * 100), is_published: true, ...extra,
})
const products = [
  product(1, 611, 1), product(2, 612, 2, 'new', 'on_request'),
  product(3, 62, 1, 'new', 'on_request'), product(4, 611, 2, 'used'),
  product(5, 91, 3), product(6, 101, 3, 'not_applicable'),
]
const newConfig = { title: 'Maquinaria nueva', canonicalPath: '/maquinaria-nueva', fixedProductType: 'machinery', fixedCondition: 'new' }
const usedConfig = { ...newConfig, title: 'Maquinaria usada', canonicalPath: '/maquinaria-usada', fixedCondition: 'used' }
const selections = (extra = {}) => ({ category: [], brand: [], condition: [], stock_status: [], ...extra })

function model(search = '', config = newConfig, input = products) {
  const params = new URLSearchParams(search)
  const context = resolveCatalogContext(categories, params, config)
  const scoped = contextCategories(categories, context)
  const selected = catalogSelections(params, scoped, brands, context)
  const base = contextProducts(input, categories, context)
  return {
    params, context, scoped, selected, base,
    results: filterCatalogProducts(base, scoped, selected, params),
    facets: catalogFacets(base, scoped, brands, selected, params),
  }
}
const ids = (items) => items.map((item) => item.id)
const count = (m, key, value) => m.facets[key].find((item) => item.value === value)?.count

test('la configuración comercial prevalece sobre tipo, condición y raíz de la URL', () => {
  const m = model('product_type=service&condition=used&catalog_root=9&category=91')
  assert.equal(m.context.title, 'Maquinarias nuevas')
  assert.equal(m.context.productType, 'machinery')
  assert.equal(m.context.fixedCondition, 'new')
  assert.deepEqual(ids(m.results), [1, 2, 3])
  assert.deepEqual(ids(model('condition=new', usedConfig).results), [4])
  for (const [type, path, expected] of [['spare_part', '/repuestos', [5]], ['service', '/servicios', [6]]]) {
    const config = { title: type, canonicalPath: path, fixedProductType: type }
    assert.deepEqual(ids(model('product_type=machinery', config).results), expected)
  }
})

test('el árbol de maquinarias excluye Repuestos, Servicios, inactivos y sus ramas', () => {
  const m = model()
  assert.deepEqual(ids(m.scoped), [6, 61, 611, 612, 62, 7, 71])
  assert.equal(m.facets.brand.some((option) => option.value === '3'), false)
})

test('una entrada profunda conserva la raíz principal y alternativas hermanas al desmarcar', () => {
  const params = new URLSearchParams('category=category-611&brand=ep')
  const context = resolveCatalogContext(categories, params)
  assert.equal(context.root.id, 6)
  const scoped = contextCategories(categories, context)
  assert.equal(scoped.some((item) => item.id === 612), true)
  assert.equal(scoped.some((item) => item.id === 71), false)
  const selected = catalogSelections(params, scoped, brands, context)
  const next = toggleCatalogFacet(params, context, selected, 'category', '611')
  assert.equal(next.has('category'), false)
  assert.equal(next.get('catalog_root'), '6')
  const restored = resolveCatalogContext(categories, new URLSearchParams(next.toString()))
  assert.equal(restored.key, context.key)
  assert.equal(restored.title, 'Maquinaria')
  assert.deepEqual(catalogSelections(params, scoped, brands, context).brand, ['1'])
})

test('/catalogo sin contexto y enlaces legados por tipo conservan navegación general', () => {
  const general = resolveCatalogContext(categories, new URLSearchParams())
  assert.equal(general.title, 'Catálogo')
  assert.equal(general.productType, '')
  assert.equal(contextCategories(categories, general).some((item) => item.id === 9), true)
  assert.equal(resolveCatalogContext(categories, new URLSearchParams('product_type=spare_part')).title, 'Repuestos')
  const multiple = resolveCatalogContext(categories, new URLSearchParams('category=611,612'))
  assert.equal(multiple.root.id, 6)
  assert.equal(resolveCatalogContext(categories, new URLSearchParams('category=611,91')).root, null)
})

test('OR dentro del grupo y AND entre grupos, incluidos condición y stock', () => {
  const m = model('category=61,62&brand=1,2&stock_status=on_request')
  assert.deepEqual(ids(m.results), [2, 3])
  const all = contextProducts(products, categories, resolveCatalogContext(categories, new URLSearchParams()))
  const selected = selections({ category: ['61'], brand: ['1', '2'], condition: ['new', 'used'], stock_status: ['available', 'on_request'] })
  assert.deepEqual(ids(filterCatalogProducts(all, categories, selected, new URLSearchParams())), [1, 2, 4])
  assert.deepEqual(ids(filterCatalogProducts(all, categories, selections(), new URLSearchParams())), [1, 2, 3, 4, 5, 6])
})

test('URL individual, comas y claves repetidas se normalizan sin perder compatibilidad por slug', () => {
  assert.deepEqual(readFacetValues(new URLSearchParams('brand=1'), 'brand'), ['1'])
  assert.deepEqual(readFacetValues(new URLSearchParams('brand=1,2&brand=2,1&brand='), 'brand'), ['1', '2'])
  assert.deepEqual(ids(model('brand=EP&category=category-611').results), [1])
  const m = model('brand=1&stock_status=available&min_price=100&max_price=900&ordering=price&utm_source=review&page=8')
  const next = toggleCatalogFacet(m.params, m.context, m.selected, 'brand', '2')
  assert.equal(next.get('brand'), '1,2')
  assert.equal(next.has('page'), false)
  for (const key of ['stock_status', 'min_price', 'max_price', 'ordering', 'utm_source']) assert.equal(next.get(key), m.params.get(key))
  assert.equal(m.params.get('brand'), '1')
  const reloaded = model(next.toString())
  assert.deepEqual(reloaded.selected.brand, ['1', '2'])
  assert.deepEqual(model(m.params.toString()).selected.brand, ['1'])
})

test('los contadores omiten su grupo, conservando las restricciones de los otros', () => {
  const m = model('brand=1')
  assert.equal(count(m, 'brand', '1'), 2)
  assert.equal(count(m, 'brand', '2'), 1)
  assert.equal(count(m, 'category', '61'), 1)
  assert.equal(count(m, 'stock_status', 'on_request'), 1)
  const narrow = model('brand=1&category=61')
  assert.equal(count(narrow, 'brand', '2'), 1)
  assert.equal(count(narrow, 'category', '62'), 1)
})

test('cada grupo se omite a sí mismo, también condición editable y stock', () => {
  const m = model('condition=new&stock_status=available', null)
  assert.equal(count(m, 'condition', 'used'), 1)
  assert.equal(count(m, 'stock_status', 'on_request'), 2)
})

test('los contadores reciben el conjunto completo antes de paginar', () => {
  const many = Array.from({ length: 29 }, (_, index) => product(index + 100, 611, 1))
  const m = model('brand=1', newConfig, many)
  assert.equal(m.results.slice(0, 12).length, 12)
  assert.equal(count(m, 'brand', '1'), 29)
  assert.equal(count(m, 'category', '61'), 29)
})

test('padres incluyen todos los descendientes, con productos e IDs deduplicados', () => {
  const m = model('category=61,611', newConfig, [...products, products[0], products[1]])
  assert.deepEqual(ids(m.results), [1, 2])
  assert.equal(count(m, 'category', '61'), 2)
  assert.deepEqual([...categoryDescendants(61, categories)].sort(), [61, 611, 612].sort())
  const params = new URLSearchParams('category=6,611')
  const context = resolveCatalogContext(categories, params)
  const scoped = contextCategories(categories, context)
  const selected = catalogSelections(params, scoped, brands, context)
  assert.deepEqual(selected.category, ['6', '611'])
  assert.deepEqual(ids(filterCatalogProducts(contextProducts(products, categories, context), scoped, selected, params)), [1, 2, 3, 4])
})

test('los recorridos terminan ante ciclos, padres ausentes e IDs repetidos', () => {
  const cyclic = [category(1, 'Uno', 2), category(2, 'Dos', 1), category(2, 'Repetida', 1)]
  assert.deepEqual([...categoryDescendants(1, cyclic)].sort(), [1, 2])
  assert.equal(rootCategory(cyclic[0], cyclic), null)
  assert.equal(rootCategory(category(3, 'Huérfana', 999), categories), null)
})

test('cero resultados mantiene las selecciones desmarcables y permite recuperar resultados', () => {
  const m = model('brand=2&stock_status=available')
  assert.equal(m.results.length, 0)
  assert.equal(count(m, 'brand', '2'), 0)
  assert.equal(count(m, 'stock_status', 'available'), 0)
  assert.equal(count(m, 'brand', '1'), 1)
  const next = toggleCatalogFacet(m.params, m.context, m.selected, 'stock_status', 'available')
  assert.deepEqual(ids(model(next.toString()).results), [2])
})

test('selecciones sin productos en la base siguen visibles con cero', () => {
  const m = model('brand=3&condition=refurbished&stock_status=reserved', null)
  assert.equal(count(m, 'brand', '3'), 0)
  assert.equal(count(m, 'condition', 'refurbished'), 0)
  assert.equal(count(m, 'stock_status', 'reserved'), 0)
  assert.deepEqual(m.selected.condition, ['refurbished'])
})

test('Limpiar filtros conserva el contexto fijo y el contexto general anclado', () => {
  const m = model('brand=1&condition=used&stock_status=on_request&search=plataforma&min_price=10&product_type=service&utm_source=review')
  const cleared = clearCatalogFilters(m.params, m.context)
  assert.deepEqual(ids(model(cleared.toString()).results), [1, 2, 3])
  assert.equal(cleared.get('utm_source'), 'review')
  assert.equal(cleared.has('search'), false)
  assert.equal(cleared.has('min_price'), false)
  const params = new URLSearchParams('category=611&brand=1')
  const context = resolveCatalogContext(categories, params)
  const generalCleared = clearCatalogFilters(params, context)
  assert.equal(generalCleared.get('catalog_root'), '6')
  assert.equal(resolveCatalogContext(categories, generalCleared).root.id, 6)
})

test('listado y facetas respetan las mismas reglas públicas de visibilidad', () => {
  const hidden = [
    product(80, 611, 1, 'new', 'sold'), product(81, 619, 1),
    product(82, 611, 1, 'new', 'available', { is_published: false }),
    product(83, 611, 1, 'new', 'available', { brand: { ...brands[0], is_active: false } }),
  ]
  const m = model('', newConfig, [...products, ...hidden])
  assert.deepEqual(ids(m.results), [1, 2, 3])
  assert.equal(count(m, 'brand', '1'), 2)
})

test('rangos actúan tanto sobre resultados como contadores, sin usar precios ocultos', () => {
  const hiddenPrice = product(100, 611, 1, 'new', 'available', { price_visible: false })
  const m = model('min_price=150&max_price=300', newConfig, [...products, hiddenPrice])
  assert.deepEqual(ids(m.results), [2, 3])
  assert.equal(count(m, 'brand', '1'), 1)
  assert.equal(count(m, 'category', '61'), 1)
})

test('la consulta pública comparte búsqueda y restricciones fijas, sin filtros por opción', () => {
  const a = model('search=SKU-123&brand=1&category=611&ordering=price')
  const b = model('search=SKU-123&brand=2&category=612&stock_status=available')
  assert.deepEqual(catalogRequestParams(a.context, a.params), { search: 'SKU-123', product_type: 'machinery', condition: 'new', commercial_mode: 'sale' })
  assert.deepEqual(catalogRequestParams(a.context, a.params), catalogRequestParams(b.context, b.params))
  // The public API already applied search (including Description/SKU) to this input.
  const searched = model('search=SKU-123', newConfig, [products[1]])
  assert.deepEqual(ids(searched.results), [2])
  assert.equal(count(searched, 'brand', '2'), 1)
})

test('filtrar y recalcular cantidades conserva las decisiones manuales del acordeón', () => {
  const m = model('category=611')
  const items = buildSidebarMenuFromCategories(m.scoped)
  let state = sidebarAccordionReducer(createSidebarAccordionState('611'), { type: 'initializeCategories', items })
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: ['/catalogo?category=6'] })
  state = sidebarAccordionReducer(state, { type: 'toggleSection', key: 'categories' })
  const closed = state
  const next = toggleCatalogFacet(m.params, m.context, m.selected, 'brand', '2')
  model(next.toString())
  state = sidebarAccordionReducer(state, { type: 'initializeCategories', items })
  assert.strictEqual(state, closed)
  assert.equal(state.openSection, null)
  assert.deepEqual(state.categoryPath, [])
})

test('la carga tardía normaliza una entrada por slug y revela sus ancestros una sola vez', () => {
  const m = model('category=category-611')
  const items = buildSidebarMenuFromCategories(m.scoped)
  let state = createSidebarAccordionState(null)
  state = sidebarAccordionReducer(state, { type: 'initializeCategories', items, categoryId: m.selected.category[0] })
  assert.deepEqual(state.categoryPath, ['/catalogo?category=6', '/catalogo?category=61'])
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: ['/catalogo?category=6'] })
  const manual = state
  assert.strictEqual(sidebarAccordionReducer(state, { type: 'initializeCategories', items, categoryId: '612' }), manual)
})
