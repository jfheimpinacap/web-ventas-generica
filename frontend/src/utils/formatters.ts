import type { Category, ProductCondition, ProductListItem, ProductPriceCurrency, ProductPriceTaxMode, ProductType, StockStatus } from '../types/catalog'

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

export function formatPriceValue(
  price: string | null | undefined,
  priceVisible = true,
  currency: ProductPriceCurrency = 'CLP',
  taxMode: ProductPriceTaxMode = 'plus_vat',
) {
  const normalizedPrice = normalizeChileanPriceInput(price)
  if (!priceVisible || !normalizedPrice) return 'Consultar'

  const amount = Number(normalizedPrice)
  if (Number.isNaN(amount)) return 'Consultar'

  const formattedAmount = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 }).format(amount)
  const currencyLabel = currency === 'USD' ? 'USD' : '$'
  const taxLabel = taxMode === 'vat_included' ? 'IVA incluido' : '+ IVA'

  return `${currencyLabel}${currency === 'USD' ? ' ' : ''}${formattedAmount} ${taxLabel}`
}

export function formatPrice(product: ProductListItem) {
  return formatPriceValue(product.price, product.price_visible, product.price_currency, product.price_tax_mode)
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


export function getRootCategory(category: Category | null | undefined, categories: Category[]) {
  if (!category) return null
  const byId = new Map(categories.map((item) => [item.id, item]))
  let current: Category | null = byId.get(category.id) ?? category
  const visited = new Set<number>()

  while (current?.parent) {
    if (visited.has(current.id)) break
    visited.add(current.id)
    current = byId.get(current.parent) ?? null
  }

  return current
}

export function inferProductTypeFromRootCategory(category: Category | null | undefined): ProductType {
  const normalized = category?.name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()

  if (normalized === 'repuestos') return 'spare_part'
  if (normalized === 'servicios') return 'service'
  return category?.product_type ?? 'machinery'
}

export function buildSidebarMenuFromCategories(categories: Category[]) {
  const grouped = new Map<number | null, Category[]>()

  categories.filter((category) => category.is_active !== false).forEach((category) => {
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

  return (grouped.get(null) ?? [])
    .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name))
    .map(buildNode)
}
