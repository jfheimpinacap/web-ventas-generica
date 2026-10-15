import assert from 'node:assert/strict'
import test from 'node:test'

import { buildSidebarMenuFromCategories } from '../src/utils/formatters.ts'
import { createSidebarAccordionState, sidebarAccordionReducer, sidebarCategoryHref } from '../src/utils/sidebarAccordion.ts'

const category = (id, name, parent, order = 0, overrides = {}) => ({
  id,
  name,
  slug: `category-${id}`,
  parent,
  product_type: 'machinery',
  description: '',
  is_active: true,
  order,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

test('construye varias raíces y tres niveles sin lanzar, conservando orden, activos y destinos por ID', () => {
  const categories = [
    category(9, 'Repuestos', null, 2, { product_type: 'spare_part' }),
    category(612, 'Tijeras', 61, 2),
    category(62, 'Movimiento', 6, 1),
    category(6, 'Maquinaria', null, 1),
    category(61, 'Elevación', 6, 1),
    category(611, 'Brazos', 61, 1),
    category(91, 'Elevación', 9, 1, { product_type: 'spare_part' }),
    category(90, 'Raíz inactiva', null, 0, { is_active: false }),
    category(619, 'Hija inactiva', 61, 0, { is_active: false }),
  ]

  let menu
  assert.doesNotThrow(() => { menu = buildSidebarMenuFromCategories(categories) })
  assert.deepEqual(menu, [
    {
      label: 'Maquinaria', to: '/catalogo?category=6', children: [
        {
          label: 'Elevación', to: '/catalogo?category=61', children: [
            { label: 'Brazos', to: '/catalogo?category=611' },
            { label: 'Tijeras', to: '/catalogo?category=612' },
          ],
        },
        { label: 'Movimiento', to: '/catalogo?category=62' },
      ],
    },
    {
      label: 'Repuestos', to: '/catalogo?category=9', children: [
        { label: 'Elevación', to: '/catalogo?category=91' },
      ],
    },
  ])
})

test('termina un ciclo alcanzable sin perder las otras ramas ni la siguiente raíz', () => {
  // Un ID repetido bajo un descendiente hace alcanzable el ciclo 6 -> 61 -> 6.
  // Con IDs únicos y un solo padre, un ciclo no puede alcanzarse desde una raíz.
  const categories = [
    category(6, 'Maquinaria', null, 1),
    category(61, 'Elevación', 6, 1),
    category(6, 'Referencia a maquinaria', 61, 1),
    category(62, 'Movimiento', 6, 2),
    category(621, 'Transporte', 62, 1),
    category(9, 'Repuestos', null, 2, { product_type: 'spare_part' }),
    category(91, 'Filtros', 9, 1, { product_type: 'spare_part' }),
  ]

  let menu
  assert.doesNotThrow(() => { menu = buildSidebarMenuFromCategories(categories) })
  assert.deepEqual(menu, [
    {
      label: 'Maquinaria', to: '/catalogo?category=6', children: [
        {
          label: 'Elevación', to: '/catalogo?category=61', children: [
            { label: 'Referencia a maquinaria', to: '/catalogo?category=6' },
          ],
        },
        {
          label: 'Movimiento', to: '/catalogo?category=62', children: [
            { label: 'Transporte', to: '/catalogo?category=621' },
          ],
        },
      ],
    },
    {
      label: 'Repuestos', to: '/catalogo?category=9', children: [
        { label: 'Filtros', to: '/catalogo?category=91' },
      ],
    },
  ])
})

const accordionMenu = () => buildSidebarMenuFromCategories([
  category(6, 'Maquinaria', null),
  category(61, 'Elevación', 6),
  category(611, 'Brazos', 61),
  category(62, 'Movimiento', 6),
  category(621, 'Transporte', 62),
  category(9, 'Repuestos', null),
  category(91, 'Filtros', 9),
])
const machinery = '/catalogo?category=6'
const lifting = '/catalogo?category=61'
const movement = '/catalogo?category=62'
const spares = '/catalogo?category=9'

test('Categorías → Marca → Condición → Stock: solo queda abierta la última sección y puede cerrarse', () => {
  let state = createSidebarAccordionState(null)
  assert.equal(state.openSection, 'categories')
  for (const key of ['brand', 'condition', 'stock', 'categories', 'another-filter']) {
    state = sidebarAccordionReducer(state, { type: 'toggleSection', key })
    assert.equal(state.openSection, key)
  }
  state = sidebarAccordionReducer(state, { type: 'toggleSection', key: 'another-filter' })
  assert.equal(state.openSection, null)
})

test('la entrada profunda revela solo sus ancestros; una entrada sin categoría no expande raíces', () => {
  const items = accordionMenu()
  const deep = sidebarAccordionReducer(createSidebarAccordionState('611'), { type: 'initializeCategories', items })
  assert.deepEqual(deep.categoryPath, [machinery, lifting])
  for (const categoryId of [null, '9999']) {
    const state = sidebarAccordionReducer(createSidebarAccordionState(categoryId), { type: 'initializeCategories', items })
    assert.deepEqual(state.categoryPath, [])
  }
})

test('alternar ramas hermanas conserva los ancestros y cambiar de raíz cierra la anterior', () => {
  let state = sidebarAccordionReducer(createSidebarAccordionState('611'), { type: 'initializeCategories', items: accordionMenu() })
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: [machinery, movement] })
  assert.deepEqual(state.categoryPath, [machinery, movement])
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: [machinery, movement] })
  assert.deepEqual(state.categoryPath, [machinery])
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: [spares] })
  assert.deepEqual(state.categoryPath, [spares])
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: [spares] })
  assert.deepEqual(state.categoryPath, [])
})

test('cerrar Categorías y volver desde Marca conserva la rama; reinicializar no reabre decisiones manuales', () => {
  let state = sidebarAccordionReducer(createSidebarAccordionState('611'), { type: 'initializeCategories', items: accordionMenu() })
  state = sidebarAccordionReducer(state, { type: 'toggleSection', key: 'brand' })
  assert.deepEqual(state.categoryPath, [machinery, lifting])
  state = sidebarAccordionReducer(state, { type: 'toggleSection', key: 'categories' })
  assert.deepEqual(state.categoryPath, [machinery, lifting])
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: [machinery] })
  state = sidebarAccordionReducer(state, { type: 'toggleSection', key: 'categories' })
  const closed = state
  state = sidebarAccordionReducer(state, { type: 'initializeCategories', items: accordionMenu() })
  assert.strictEqual(state, closed)
  assert.equal(state.openSection, null)
  assert.deepEqual(state.categoryPath, [])
})

test('la carga tardía de categorías respeta la sección utilizada y una rama elegida antes de inicializar', () => {
  let state = createSidebarAccordionState('611')
  state = sidebarAccordionReducer(state, { type: 'toggleSection', key: 'brand' })
  state = sidebarAccordionReducer(state, { type: 'initializeCategories', items: accordionMenu() })
  assert.equal(state.openSection, 'brand')
  assert.deepEqual(state.categoryPath, [machinery, lifting])

  state = createSidebarAccordionState('611')
  state = sidebarAccordionReducer(state, { type: 'toggleCategory', path: [spares] })
  state = sidebarAccordionReducer(state, { type: 'initializeCategories', items: accordionMenu() })
  assert.deepEqual(state.categoryPath, [spares])
})

test('navegar por ID conserva filtros, rangos y rutas comerciales sin mutar la URL de origen', () => {
  const item = accordionMenu()[0].children[0].children[0]
  const original = new URLSearchParams('category=6&brand=EP&condition=used&stock_status=available&ordering=name&search=elevacion&min_price=100&max_price=900&product_type=service')
  for (const pathname of ['/catalogo', '/maquinaria-nueva', '/maquinaria-usada', '/repuestos', '/servicios']) {
    const href = new URL(sidebarCategoryHref(item, pathname, original.toString()), 'https://example.test')
    assert.equal(href.pathname, pathname)
    assert.equal(href.searchParams.get('category'), '611')
    assert.equal(href.searchParams.has('product_type'), false)
    for (const key of ['brand', 'condition', 'stock_status', 'ordering', 'search', 'min_price', 'max_price']) {
      assert.equal(href.searchParams.get(key), original.get(key))
    }
  }
  assert.equal(original.get('category'), '6')
  assert.equal(original.get('product_type'), 'service')
})
