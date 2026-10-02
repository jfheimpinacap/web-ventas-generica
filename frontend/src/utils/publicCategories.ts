import type { Category } from '../types/catalog'

export function isPublicCategory(category: Pick<Category, 'slug' | 'product_type'>) {
  // Repuestos is part of the public catalogue navigation. Visibility continues
  // to be controlled by the API's is_active flag, just like the other roots.
  return Boolean(category.slug.trim()) && Boolean(category.product_type)
}

export function publicCategories(categories: Category[]) {
  return categories.filter(isPublicCategory)
}
