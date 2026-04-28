import type {
  ProductDetail,
  ProductFormValues,
  ProductImage,
  ProductImageWritePayload,
  ProductListItem,
  ProductSpec,
  ProductSpecWritePayload,
  Promotion,
  QuoteRequest,
} from '../types/catalog'
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

export async function getAdminQuoteRequests() {
  const response = await authFetch<ApiListResponse<QuoteRequest>>('/quote-requests/')
  return normalizeListResponse(response)
}

export async function getAdminPromotions() {
  const response = await authFetch<ApiListResponse<Promotion>>('/promotions/')
  return normalizeListResponse(response)
}
