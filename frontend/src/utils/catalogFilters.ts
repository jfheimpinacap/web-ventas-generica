import type { Brand, Category, ProductCondition, ProductListItem, ProductQueryParams, ProductType } from '../types/catalog'

export interface CommercialCatalogConfig {
  title: string
  description: string
  canonicalPath: '/maquinaria-nueva' | '/maquinaria-usada' | '/repuestos' | '/servicios'
  fixedProductType: ProductType
  fixedCondition?: 'new' | 'used'
}

export interface CatalogContext {
  key: string
  title: string
  productType: ProductType | ''
  fixedCondition?: ProductCondition
  root: Category | null
}

export const FACET_KEYS = ['category', 'brand', 'condition', 'stock_status'] as const
export type FacetKey = typeof FACET_KEYS[number]
export type CatalogSelections = Record<FacetKey, string[]>
export interface FacetOption { value: string; label: string; count: number }

const TYPE_LABELS: Record<ProductType, string> = { machinery: 'Maquinarias', spare_part: 'Repuestos', service: 'Servicios' }
const CONDITION_LABELS: Record<string, string> = { new: 'Nuevo', used: 'Usado', refurbished: 'Reacondicionado', not_applicable: 'No aplica' }
const STOCK_LABELS: Record<string, string> = { available: 'Disponible', on_request: 'A pedido', reserved: 'Reservado', sold: 'Vendido' }

export function readFacetValues(params: URLSearchParams, key: FacetKey): string[] {
  // Repeated keys are accepted too; writes use a single comma-separated value.
  return [...new Set(params.getAll(key).flatMap((value) => value.split(',')).map((value) => value.trim()).filter(Boolean))]
}

function findCategory(categories: Category[], value: string) {
  return categories.find((category) => String(category.id) === value || category.slug.toLowerCase() === value.toLowerCase())
}

export function rootCategory(category: Category | undefined, categories: Category[]): Category | null {
  const seen = new Set<number>()
  let current = category
  while (current) {
    if (current.is_active === false || seen.has(current.id)) return null
    seen.add(current.id)
    if (current.parent === null) return current
    current = categories.find((item) => item.id === current?.parent)
  }
  return null
}

export function resolveCatalogContext(categories: Category[], params: URLSearchParams, config?: CommercialCatalogConfig): CatalogContext {
  if (config) return {
    key: config.canonicalPath,
    title: config.fixedProductType === 'machinery' && config.fixedCondition ? `Maquinarias ${config.fixedCondition === 'used' ? 'usadas' : 'nuevas'}` : config.title,
    productType: config.fixedProductType,
    fixedCondition: config.fixedCondition,
    root: null,
  }
  const pinned = rootCategory(findCategory(categories, params.get('catalog_root') ?? ''), categories)
  const selectedRoots = readFacetValues(params, 'category').map((value) => rootCategory(findCategory(categories, value), categories))
  const commonRoot = selectedRoots.length && selectedRoots.every((root) => root && root.id === selectedRoots[0]?.id) ? selectedRoots[0] : null
  const root = pinned ?? commonRoot
  const legacyType = params.get('product_type') ?? ''
  const productType = root?.product_type ?? (Object.prototype.hasOwnProperty.call(TYPE_LABELS, legacyType) ? legacyType as ProductType : '')
  return { key: root ? `root:${root.id}` : `catalog:${productType}`, title: root?.name ?? (productType ? TYPE_LABELS[productType] : 'Catálogo'), productType, root }
}

export function contextCategories(categories: Category[], context: CatalogContext): Category[] {
  const unique = [...new Map(categories.map((category) => [category.id, category])).values()]
  return unique.filter((category) => {
    if (!category.slug.trim() || category.is_active === false || (context.productType && category.product_type !== context.productType)) return false
    const root = rootCategory(category, unique)
    return Boolean(root && (!context.root || root.id === context.root.id))
  })
}

export function categoryDescendants(categoryId: number, categories: Category[]): Set<number> {
  const visited = new Set<number>()
  const pending = [categoryId]
  while (pending.length) {
    const id = pending.pop()!
    if (visited.has(id)) continue
    visited.add(id)
    categories.forEach((category) => { if (category.parent === id && category.is_active !== false && !visited.has(category.id)) pending.push(category.id) })
  }
  return visited
}

export function catalogSelections(params: URLSearchParams, categories: Category[], brands: Brand[], context: CatalogContext): CatalogSelections {
  const normalize = (key: 'category' | 'brand') => readFacetValues(params, key).map((value) => {
    const item = key === 'category' ? findCategory(categories, value) : brands.find((brand) => String(brand.id) === value || brand.slug.toLowerCase() === value.toLowerCase())
    return item ? String(item.id) : key === 'category' ? '' : value
  })
  const categoryValues = [...new Set(normalize('category'))].filter(Boolean)
  return {
    // A lone legacy root denotes the context. In a multi-value URL it must
    // remain an OR option, including all its descendants alongside its siblings.
    category: categoryValues.length === 1 && categoryValues[0] === String(context.root?.id) ? [] : categoryValues,
    brand: [...new Set(normalize('brand'))],
    condition: context.fixedCondition ? [] : readFacetValues(params, 'condition'),
    stock_status: readFacetValues(params, 'stock_status'),
  }
}

export function contextProducts(products: ProductListItem[], categories: Category[], context: CatalogContext): ProductListItem[] {
  const eligibleIds = new Set(contextCategories(categories, context).map((category) => category.id))
  return [...new Map(products.filter((product) => (
    product.is_published !== false && product.category.is_active !== false
    && product.brand?.is_active !== false && product.stock_status !== 'sold'
    && (!context.root || eligibleIds.has(product.category.id))
    && (!context.productType || product.product_type === context.productType)
    && (!context.fixedCondition || product.condition === context.fixedCondition)
  )).map((product) => [product.id, product])).values()]
}

export function catalogRequestParams(context: CatalogContext, params: URLSearchParams): ProductQueryParams {
  // Search stays public/server-side: it also searches Description and spare-part SKU,
  // neither of which is exposed by the public list DTO. No discrete filters here.
  return { product_type: context.productType, condition: context.fixedCondition ?? '', search: params.get('search') ?? '' }
}

export function filterCatalogProducts(products: ProductListItem[], categories: Category[], selections: CatalogSelections, params: URLSearchParams, omit?: FacetKey): ProductListItem[] {
  const categoryIds = new Set(selections.category.flatMap((value) => [...categoryDescendants(Number(value), categories)]))
  const range = (key: string) => {
    const value = params.get(key)
    return value?.trim() && Number.isFinite(Number(value)) ? Number(value) : null
  }
  const min = range('min_price')
  const max = range('max_price')
  return products.filter((product) => {
    if (omit !== 'category' && selections.category.length && !categoryIds.has(product.category.id)) return false
    if (omit !== 'brand' && selections.brand.length && !selections.brand.includes(String(product.brand?.id))) return false
    if (omit !== 'condition' && selections.condition.length && !selections.condition.includes(product.condition)) return false
    if (omit !== 'stock_status' && selections.stock_status.length && !selections.stock_status.includes(product.stock_status)) return false
    if (min !== null || max !== null) {
      const price = product.price_visible && product.price !== null ? Number(product.price) : NaN
      if (!Number.isFinite(price) || (min !== null && price < min) || (max !== null && price > max)) return false
    }
    return true
  })
}

export function catalogFacets(base: ProductListItem[], categories: Category[], brands: Brand[], selections: CatalogSelections, params: URLSearchParams): Record<FacetKey, FacetOption[]> {
  const categoryOptions = categories.map((item) => ({ value: String(item.id), label: item.name }))
  const brandIds = new Set([...base.map((product) => String(product.brand?.id)), ...selections.brand])
  const brandOptions = brands.filter((brand) => brand.is_active !== false && brandIds.has(String(brand.id))).map((brand) => ({ value: String(brand.id), label: brand.name }))
  const discreteOptions = (key: 'condition' | 'stock_status', labels: Record<string, string>) => Object.entries(labels)
    .filter(([value]) => base.some((product) => product[key] === value) || selections[key].includes(value))
    .map(([value, label]) => ({ value, label }))
  const options = { category: categoryOptions, brand: brandOptions, condition: discreteOptions('condition', CONDITION_LABELS), stock_status: discreteOptions('stock_status', STOCK_LABELS) }
  const result = {} as Record<FacetKey, FacetOption[]>
  FACET_KEYS.forEach((key) => {
    // The current group is omitted; the other groups and ranges still apply.
    const candidates = filterCatalogProducts(base, categories, selections, params, key)
    const available = new Map(options[key].map((option) => [option.value, option]))
    selections[key].forEach((value) => {
      if (!available.has(value)) available.set(value, { value, label: `Selección: ${value}` })
    })
    result[key] = [...available.values()].map((option) => {
      const ids = key === 'category' ? categoryDescendants(Number(option.value), categories) : null
      const matches = candidates.filter((product) => key === 'category' ? ids!.has(product.category.id)
        : key === 'brand' ? String(product.brand?.id) === option.value : product[key] === option.value)
      return { ...option, count: new Set(matches.map((product) => product.id)).size }
    })
  })
  return result
}

function pinContext(next: URLSearchParams, context: CatalogContext) {
  if (context.root) next.set('catalog_root', String(context.root.id))
}

export function toggleCatalogFacet(params: URLSearchParams, context: CatalogContext, selections: CatalogSelections, key: FacetKey, value: string): URLSearchParams {
  const next = new URLSearchParams(params)
  pinContext(next, context)
  const values = selections[key].includes(value) ? selections[key].filter((item) => item !== value) : [...selections[key], value]
  next.delete(key)
  if (values.length) next.set(key, values.join(','))
  next.delete('page')
  return next
}

export function clearCatalogFilters(params: URLSearchParams, context: CatalogContext): URLSearchParams {
  const next = new URLSearchParams(params)
  pinContext(next, context)
  ;[...FACET_KEYS, 'search', 'min_price', 'max_price', 'page'].forEach((key) => next.delete(key))
  // product_type is a legacy context selector, not an editable checkbox group.
  return next
}
