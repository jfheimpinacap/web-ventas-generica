import type {
  Brand,
  Category,
  ProductDetail,
  ProductListItem,
  ProductQueryParams,
  Promotion,
  QuoteRequestPayload,
} from '../types/catalog'
import { apiRequest } from './api'

type ApiListResponse<T> = T[] | { results: T[] }

function normalizeListResponse<T>(response: ApiListResponse<T>): T[] {
  return Array.isArray(response) ? response : response.results
}

export async function getProducts(params?: ProductQueryParams) {
  const response = await apiRequest<ApiListResponse<ProductListItem>>('/products/', { params })
  return normalizeListResponse(response)
}

export async function getFeaturedProducts() {
  return getProducts({ is_featured: true })
}

export async function searchProducts(search: string) {
  return getProducts({ search })
}

export async function getProductBySlug(slug: string) {
  return apiRequest<ProductDetail>(`/products/${slug}/`)
}

export async function getCategories() {
  const response = await apiRequest<ApiListResponse<Category>>('/categories/')
  return normalizeListResponse(response)
}

export async function getBrands() {
  const response = await apiRequest<ApiListResponse<Brand>>('/brands/')
  return normalizeListResponse(response)
}

export async function getPromotions() {
  const response = await apiRequest<ApiListResponse<Promotion>>('/promotions/')
  return normalizeListResponse(response)
}

export async function createQuoteRequest(payload: QuoteRequestPayload) {
  return apiRequest('/quote-requests/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
