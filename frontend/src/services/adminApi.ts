import type { ProductListItem, Promotion, QuoteRequest } from '../types/catalog'
import { authFetch } from './authApi'

type ApiListResponse<T> = T[] | { results: T[] }

function normalizeListResponse<T>(response: ApiListResponse<T>): T[] {
  return Array.isArray(response) ? response : response.results
}

export async function getAdminProducts() {
  const response = await authFetch<ApiListResponse<ProductListItem>>('/products/', {
    params: { include_unpublished: true },
  })
  return normalizeListResponse(response)
}

export async function getAdminQuoteRequests() {
  const response = await authFetch<ApiListResponse<QuoteRequest>>('/quote-requests/')
  return normalizeListResponse(response)
}

export async function getAdminPromotions() {
  const response = await authFetch<ApiListResponse<Promotion>>('/promotions/')
  return normalizeListResponse(response)
}
