import type {
  Brand,
  BrandFormValues,
  Category,
  CategoryFormValues,
  HomeSection,
  HomeSectionItem,
  HomeSectionItemFormValues,
  ProductDetail,
  ProductFormValues,
  ProductImage,
  ProductImageWritePayload,
  ProductListItem,
  ProductSpec,
  ProductSpecWritePayload,
  Promotion,
  PromotionFormValues,
  QuoteRequestAdmin,
  QuoteStatus,
  SupplierFormValues,
  SupplierSummary,
} from '../types/catalog'
import { authFetch } from './authApi'

type ApiListResponse<T> = T[] | { results: T[] }

function normalizeListResponse<T>(response: ApiListResponse<T>): T[] {
  return Array.isArray(response) ? response : response.results
}

export async function getAdminProducts(params?: Record<string, string | number | boolean | undefined>) {
  const response = await authFetch<ApiListResponse<ProductListItem>>('/products/', {
    params: { include_unpublished: true, ...(params ?? {}) },
  })
  return normalizeListResponse(response)
}

export async function getAdminProduct(slug: string) {
  return authFetch<ProductDetail>(`/products/${slug}/`)
}

export async function createProduct(payload: ProductFormValues) {
  return authFetch<ProductDetail>('/products/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateProduct(slug: string, payload: Partial<ProductFormValues>) {
  return authFetch<ProductDetail>(`/products/${slug}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteProduct(slug: string) {
  return authFetch<void>(`/products/${slug}/`, {
    method: 'DELETE',
  })
}

export async function getProductImages(productId: number) {
  const response = await authFetch<ApiListResponse<ProductImage>>('/product-images/', {
    params: { product: productId },
  })
  return normalizeListResponse(response)
}

export async function createProductImage(payload: ProductImageWritePayload) {
  const formData = new FormData()
  formData.append('product', String(payload.product))
  if (payload.image) {
    formData.append('image', payload.image)
  }
  if (payload.alt_text !== undefined) {
    formData.append('alt_text', payload.alt_text)
  }
  if (payload.order !== undefined) {
    formData.append('order', String(payload.order))
  }
  if (payload.is_main !== undefined) {
    formData.append('is_main', String(payload.is_main))
  }

  return authFetch<ProductImage>('/product-images/', {
    method: 'POST',
    body: formData,
  })
}

export async function updateProductImage(id: number, payload: Partial<ProductImageWritePayload>) {
  return authFetch<ProductImage>(`/product-images/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteProductImage(id: number) {
  return authFetch<void>(`/product-images/${id}/`, {
    method: 'DELETE',
  })
}

export async function getProductSpecs(productId: number) {
  const response = await authFetch<ApiListResponse<ProductSpec>>('/product-specs/', {
    params: { product: productId },
  })
  return normalizeListResponse(response)
}

export async function createProductSpec(payload: ProductSpecWritePayload) {
  return authFetch<ProductSpec>('/product-specs/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateProductSpec(id: number, payload: Partial<ProductSpecWritePayload>) {
  return authFetch<ProductSpec>(`/product-specs/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteProductSpec(id: number) {
  return authFetch<void>(`/product-specs/${id}/`, {
    method: 'DELETE',
  })
}

type AdminQuotesParams = Record<string, string | number | boolean | undefined> & {
  status?: QuoteStatus | ''
  search?: string
  ordering?: 'created_at' | '-created_at' | 'updated_at' | '-updated_at' | 'status' | '-status' | ''
  product?: number
}

export async function getAdminQuotes(params?: AdminQuotesParams) {
  const response = await authFetch<ApiListResponse<QuoteRequestAdmin>>('/quote-requests/', { params })
  return normalizeListResponse(response)
}

export async function getAdminQuote(id: number) {
  return authFetch<QuoteRequestAdmin>(`/quote-requests/${id}/`)
}

export async function updateQuote(id: number, payload: Partial<QuoteRequestAdmin>) {
  return authFetch<QuoteRequestAdmin>(`/quote-requests/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteQuote(id: number) {
  return authFetch<void>(`/quote-requests/${id}/`, {
    method: 'DELETE',
  })
}

const includeInactiveParams = { include_inactive: true }

export async function getAdminCategories() {
  const response = await authFetch<ApiListResponse<Category>>('/categories/', { params: includeInactiveParams })
  return normalizeListResponse(response)
}

export async function getAdminCategory(id: number) {
  return authFetch<Category>(`/categories/${id}/`, { params: includeInactiveParams })
}

export async function createCategory(payload: CategoryFormValues) {
  return authFetch<Category>('/categories/', { method: 'POST', body: JSON.stringify(payload) })
}

export async function updateCategory(id: number, payload: Partial<CategoryFormValues>) {
  return authFetch<Category>(`/categories/${id}/`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export async function deleteCategory(id: number) {
  return authFetch<void>(`/categories/${id}/`, { method: 'DELETE' })
}

export async function getAdminBrands() {
  const response = await authFetch<ApiListResponse<Brand>>('/brands/', { params: includeInactiveParams })
  return normalizeListResponse(response)
}

export async function getAdminBrand(id: number) {
  return authFetch<Brand>(`/brands/${id}/`, { params: includeInactiveParams })
}

export async function createBrand(payload: BrandFormValues) {
  const formData = new FormData()
  formData.append('name', payload.name)
  if (payload.slug) formData.append('slug', payload.slug)
  if (payload.description) formData.append('description', payload.description)
  formData.append('is_active', String(payload.is_active))
  if (payload.logo) formData.append('logo', payload.logo)

  return authFetch<Brand>('/brands/', { method: 'POST', body: formData })
}

export async function updateBrand(id: number, payload: Partial<BrandFormValues>) {
  const formData = new FormData()
  if (payload.name !== undefined) formData.append('name', payload.name)
  if (payload.slug !== undefined) formData.append('slug', payload.slug)
  if (payload.description !== undefined) formData.append('description', payload.description)
  if (payload.is_active !== undefined) formData.append('is_active', String(payload.is_active))
  if (payload.logo instanceof File) formData.append('logo', payload.logo)

  return authFetch<Brand>(`/brands/${id}/`, { method: 'PATCH', body: formData })
}

export async function deleteBrand(id: number) {
  return authFetch<void>(`/brands/${id}/`, { method: 'DELETE' })
}

export async function getAdminSuppliers() {
  const response = await authFetch<ApiListResponse<SupplierSummary>>('/suppliers/', { params: includeInactiveParams })
  return normalizeListResponse(response)
}

export async function getAdminSupplier(id: number) {
  return authFetch<SupplierSummary>(`/suppliers/${id}/`, { params: includeInactiveParams })
}

export async function createSupplier(payload: SupplierFormValues) {
  return authFetch<SupplierSummary>('/suppliers/', { method: 'POST', body: JSON.stringify(payload) })
}

export async function updateSupplier(id: number, payload: Partial<SupplierFormValues>) {
  return authFetch<SupplierSummary>(`/suppliers/${id}/`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export async function deleteSupplier(id: number) {
  return authFetch<void>(`/suppliers/${id}/`, { method: 'DELETE' })
}

export async function getAdminPromotions() {
  const response = await authFetch<ApiListResponse<Promotion>>('/promotions/', { params: includeInactiveParams })
  return normalizeListResponse(response)
}

export async function getAdminPromotion(id: number) {
  return authFetch<Promotion>(`/promotions/${id}/`, { params: includeInactiveParams })
}

function toPromotionBody(payload: PromotionFormValues | Partial<PromotionFormValues>) {
  const formData = new FormData()
  if (payload.title !== undefined) formData.append('title', payload.title)
  if (payload.subtitle !== undefined) formData.append('subtitle', payload.subtitle)
  if (payload.product !== undefined) formData.append('product', payload.product === null ? '' : String(payload.product))
  if (payload.button_text !== undefined) formData.append('button_text', payload.button_text)
  if (payload.button_url !== undefined) formData.append('button_url', payload.button_url)
  if (payload.is_active !== undefined) formData.append('is_active', String(payload.is_active))
  if (payload.order !== undefined) formData.append('order', String(payload.order))
  if (payload.starts_at !== undefined) formData.append('starts_at', payload.starts_at || '')
  if (payload.ends_at !== undefined) formData.append('ends_at', payload.ends_at || '')
  if (payload.image) formData.append('image', payload.image)
  return formData
}

export async function createPromotion(payload: PromotionFormValues) {
  return authFetch<Promotion>('/promotions/', {
    method: 'POST',
    body: toPromotionBody(payload),
  })
}

export async function updatePromotion(id: number, payload: Partial<PromotionFormValues>) {
  return authFetch<Promotion>(`/promotions/${id}/`, {
    method: 'PATCH',
    body: toPromotionBody(payload),
  })
}

export async function deletePromotion(id: number) {
  return authFetch<void>(`/promotions/${id}/`, { method: 'DELETE' })
}


export async function getProductsForHomeSection(section: HomeSection) {
  const sectionParams: Record<HomeSection, Record<string, string | boolean>> = {
    machinery_promotions: { product_type: 'machinery', is_published: true },
    spare_parts_offers: { product_type: 'spare_part', is_published: true },
    repair_services: { product_type: 'service', is_published: true },
  }

  return getAdminProducts(sectionParams[section])
}

export async function getAdminHomeSectionItems(section?: HomeSection) {
  const response = await authFetch<ApiListResponse<HomeSectionItem>>('/home-section-items/', {
    params: {
      include_inactive: true,
      ...(section ? { section } : {}),
    },
  })
  return normalizeListResponse(response)
}

export async function createHomeSectionItem(payload: HomeSectionItemFormValues) {
  return authFetch<HomeSectionItem>('/home-section-items/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateHomeSectionItem(id: number, payload: Partial<HomeSectionItemFormValues>) {
  return authFetch<HomeSectionItem>(`/home-section-items/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteHomeSectionItem(id: number) {
  return authFetch<void>(`/home-section-items/${id}/`, { method: 'DELETE' })
}
