import type {
  Brand,
  Category,
  ProductDetail,
  HomeSectionItem,
  ProductListItem,
  ProductQueryParams,
  Promotion,
  QuoteRequestPublicPayload,
  SupplierSummary,
} from '../types/catalog'
import { API_PROVIDER, apiRequest } from './api'
import {
  normalizeBrandListResponse,
  normalizeCategoryListResponse,
  normalizeHomeSectionItemListResponse,
  normalizeProductDetail,
  normalizeProductListResponse,
  normalizePromotionListResponse,
  normalizeSupplierListResponse,
} from './adminApi'

type ApiListResponse<T> = T[] | { results: T[] }

function publicReadPath(path: string) {
  if (API_PROVIDER !== 'dotnet') return path

  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `/public${normalizedPath}`
}

export async function getProducts(params?: ProductQueryParams) {
  const response = await apiRequest<ApiListResponse<unknown>>(publicReadPath('/products/'), { params })
  return normalizeProductListResponse(response) as ProductListItem[]
}

export async function getFeaturedProducts() {
  return getProducts({ is_featured: true })
}

export async function searchProducts(search: string) {
  return getProducts({ search })
}

export async function getProductBySlug(slug: string) {
  const response = await apiRequest<unknown>(publicReadPath(`/products/${slug}/`))
  return normalizeProductDetail(response) as ProductDetail
}

export async function getCategories() {
  const response = await apiRequest<ApiListResponse<unknown>>(publicReadPath('/categories/'))
  return normalizeCategoryListResponse(response) as Category[]
}

export async function getBrands() {
  const response = await apiRequest<ApiListResponse<unknown>>(publicReadPath('/brands/'))
  return normalizeBrandListResponse(response) as Brand[]
}

export async function getSuppliers() {
  const response = await apiRequest<ApiListResponse<unknown>>('/suppliers/')
  return normalizeSupplierListResponse(response) as SupplierSummary[]
}

export async function getPromotions() {
  const response = await apiRequest<ApiListResponse<unknown>>(publicReadPath('/promotions/'))
  return normalizePromotionListResponse(response) as Promotion[]
}

export async function createQuoteRequest(payload: QuoteRequestPublicPayload) {
  return apiRequest(publicReadPath('/quote-requests/'), {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getHomeSectionItems(section?: string) {
  const response = await apiRequest<ApiListResponse<unknown>>(publicReadPath('/home-section-items/'), {
    params: section ? { section } : undefined,
  })
  return normalizeHomeSectionItemListResponse(response) as HomeSectionItem[]
}
