import assert from 'node:assert/strict'
import test from 'node:test'

import { buildSidebarMenuFromCategories } from '../src/utils/formatters.ts'

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
