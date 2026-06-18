import type { Category, ProductCondition, ProductListItem, ProductType, StockStatus } from '../types/catalog'

export function normalizeChileanPriceInput(value: string | null | undefined) {
  if (value === null || value === undefined) return null

  const trimmedValue = value.trim()
  if (!trimmedValue) return null
  if (!/^[0-9.]+$/.test(trimmedValue)) return null

  const normalizedValue = trimmedValue.replace(/\./g, '')
  if (!normalizedValue || !/^[0-9]+$/.test(normalizedValue)) return null

  return normalizedValue
}

export function isValidChileanPriceInput(value: string | null | undefined) {
  if (value === null || value === undefined || value.trim() === '') return true
  return normalizeChileanPriceInput(value) !== null
}

export function formatPriceValue(price: string | null | undefined, priceVisible = true) {
  const normalizedPrice = normalizeChileanPriceInput(price)
  if (!priceVisible || !normalizedPrice) return 'Consultar'

  const amount = Number(normalizedPrice)
  if (Number.isNaN(amount)) return 'Consultar'

  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatPrice(product: ProductListItem) {
  return formatPriceValue(product.price, product.price_visible)
}

const conditionMap: Record<ProductCondition, string> = {
  new: 'Nuevo',
  used: 'Usado',
  refurbished: 'Reacondicionado',
  not_applicable: 'No aplica',
}

export function formatCondition(condition: ProductCondition) {
  return conditionMap[condition] ?? condition
}

const stockMap: Record<StockStatus, string> = {
  available: 'Disponible',
  on_request: 'A pedido',
  sold: 'Vendido',
  reserved: 'Reservado',
}

export function formatStockStatus(stock: StockStatus) {
  return stockMap[stock] ?? stock
}

const productTypeMap: Record<ProductType, string> = {
  machinery: 'Maquinaria',
  spare_part: 'Repuesto',
  service: 'Servicio',
}

export function formatProductType(type: ProductType) {
  return productTypeMap[type] ?? type
}

export function buildSidebarMenuFromCategories(categories: Category[]) {
  const grouped = new Map<number | null, Category[]>()

  categories.forEach((category) => {
    const key = category.parent
    if (!grouped.has(key)) {
      grouped.set(key, [])
    }
    grouped.get(key)?.push(category)
  })

  const buildNode = (category: Category): { label: string; to: string; children?: { label: string; to: string }[] } => {
    const children = (grouped.get(category.id) ?? []).map((child) => ({
      label: child.name,
      to: `/catalogo?category=${child.id}`,
    }))

    return {
      label: category.name,
      to: `/catalogo?category=${category.id}`,
      ...(children.length > 0 ? { children } : {}),
    }
  }

  return (grouped.get(null) ?? []).map(buildNode)
}
