import type { Category, ProductCondition, ProductListItem, StockStatus } from '../types/catalog'

export function formatPrice(product: ProductListItem) {
  if (!product.price_visible || !product.price) return 'Consultar'
  const amount = Number(product.price)
  if (Number.isNaN(amount)) return 'Consultar'

  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)
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
  on_request: 'Bajo consulta',
  sold: 'Vendido',
  reserved: 'Reservado',
}

export function formatStockStatus(stock: StockStatus) {
  return stockMap[stock] ?? stock
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

  const buildNode = (category: Category): { label: string; children?: { label: string }[] } => {
    const children = (grouped.get(category.id) ?? []).map((child) => ({ label: child.name }))
    if (children.length === 0) {
      return { label: category.name }
    }

    return {
      label: category.name,
      children,
    }
  }

  return (grouped.get(null) ?? []).map(buildNode)
}
