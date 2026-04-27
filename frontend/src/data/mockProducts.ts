import type { ProductListItem } from '../types/catalog'

function buildFallbackCategory(id: number, name: string, parent: number | null = null) {
  return {
    id,
    name,
    slug: name.toLowerCase().replace(/\s+/g, '-'),
    parent,
    description: '',
    is_active: true,
    order: id,
    created_at: '',
    updated_at: '',
  }
}

function buildFallbackBrand(id: number, name: string) {
  return {
    id,
    name,
    slug: name.toLowerCase(),
    logo: null,
    description: '',
    is_active: true,
    created_at: '',
    updated_at: '',
  }
}

export const mockProducts: ProductListItem[] = [
  {
    id: 1,
    slug: 'elevador-tijera-genie-gs-1930',
    name: 'Elevador tijera Genie GS-1930',
    brand: buildFallbackBrand(1, 'Genie'),
    category: buildFallbackCategory(1, 'Elevadores tipo tijera'),
    product_type: 'machinery',
    condition: 'new',
    short_description: 'Equipo compacto para trabajo en interiores.',
    price: null,
    price_visible: false,
    stock_status: 'on_request',
    is_featured: true,
    main_image: null,
  },
  {
    id: 2,
    slug: 'brazo-articulado-jlg-450aj',
    name: 'Brazo articulado JLG 450AJ',
    brand: buildFallbackBrand(2, 'JLG'),
    category: buildFallbackCategory(2, 'Brazos articulados'),
    product_type: 'machinery',
    condition: 'used',
    short_description: 'Excelente alcance horizontal y vertical.',
    price: '42500.00',
    price_visible: true,
    stock_status: 'available',
    is_featured: true,
    main_image: null,
  },
  {
    id: 3,
    slug: 'elevador-tijera-haulotte-compact-12',
    name: 'Elevador tijera Haulotte Compact 12',
    brand: buildFallbackBrand(3, 'Haulotte'),
    category: buildFallbackCategory(1, 'Elevadores tipo tijera'),
    product_type: 'machinery',
    condition: 'refurbished',
    short_description: 'Versión reacondicionada y lista para despacho.',
    price: '28900.00',
    price_visible: true,
    stock_status: 'reserved',
    is_featured: true,
    main_image: null,
  },
]
