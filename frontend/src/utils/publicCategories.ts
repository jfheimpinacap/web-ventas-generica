import type { Category } from '../types/catalog'

export function isPublicCategory(category: Pick<Category, 'slug' | 'product_type'>) {
  return category.product_type !== 'spare_part' && category.slug.trim().toLowerCase() !== 'repuestos'
}

export function publicCategories(categories: Category[]) {
  const hiddenRootIds = new Set(categories.filter((category) => category.parent === null && !isPublicCategory(category)).map((category) => category.id))
  return categories.filter((category) => isPublicCategory(category) && (category.parent === null || !hiddenRootIds.has(category.parent)))
}
