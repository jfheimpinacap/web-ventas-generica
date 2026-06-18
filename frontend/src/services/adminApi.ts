import type {
  Brand,
  BrandFormValues,
  Category,
  CategoryFormValues,
  HomeSection,
  HomeSectionItem,
  HomeSectionItemFormValues,
  ProductCondition,
  ProductDetail,
  ProductFormValues,
  ProductImage,
  ProductImageWritePayload,
  ProductListItem,
  ProductSpec,
  ProductSpecWritePayload,
  ProductType,
  Promotion,
  PromotionFormValues,
  QuoteRequestAdmin,
  QuoteStatus,
  StockStatus,
  SupplierFormValues,
  SupplierSummary,
} from '../types/catalog'
import { API_PROVIDER, ApiError } from './api'
import { normalizeChileanPriceInput } from '../utils/formatters'
import { authFetch } from './authApi'

type ApiRecord = Record<string, unknown>
type ApiListResponse<T> = T[] | { results?: T[]; items?: T[]; data?: T[] }

const EMPTY_DATE = ''

function isRecord(value: unknown): value is ApiRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function pick<T = unknown>(record: ApiRecord, ...keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (value !== undefined) return value as T
  }

  return undefined
}

function toNumber(value: unknown, fallback = 0) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }

  return fallback
}

function toStringValue(value: unknown, fallback = '') {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean')
    return String(value)
  return fallback
}

function toBoolean(value: unknown, fallback = false) {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') return value.toLowerCase() === 'true'
  if (typeof value === 'number') return value === 1
  return fallback
}

function toNullableString(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  return toStringValue(value)
}

function normalizeListResponse<T, R>(
  response: ApiListResponse<T>,
  normalizer: (item: T) => R,
): R[] {
  if (Array.isArray(response)) return response.map(normalizer)

  const values = response.results ?? response.items ?? response.data ?? []
  return values.map(normalizer)
}

export function normalizeCategory(value: unknown): Category {
  const record = isRecord(value) ? value : {}

  return {
    id: toNumber(pick(record, 'id', 'categoryId', 'category_id')),
    name: toStringValue(pick(record, 'name'), 'Sin categoría'),
    slug: toStringValue(pick(record, 'slug')),
    parent:
      pick(record, 'parent') === null
        ? null
        : toNumber(pick(record, 'parent', 'parentId', 'parent_id'), 0) || null,
    product_type: toStringValue(pick(record, 'product_type', 'productType'), 'machinery') as ProductType,
    description: toStringValue(pick(record, 'description')),
    is_active: toBoolean(pick(record, 'is_active', 'isActive'), true),
    order: toNumber(pick(record, 'order')),
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

export function normalizeBrand(value: unknown): Brand {
  const record = isRecord(value) ? value : {}

  return {
    id: toNumber(pick(record, 'id', 'brandId', 'brand_id')),
    name: toStringValue(pick(record, 'name'), 'Sin marca'),
    slug: toStringValue(pick(record, 'slug')),
    logo: toNullableString(pick(record, 'logo')),
    description: toStringValue(pick(record, 'description')),
    is_active: toBoolean(pick(record, 'is_active', 'isActive'), true),
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

export function normalizeSupplier(value: unknown): SupplierSummary {
  const record = isRecord(value) ? value : {}

  return {
    id: toNumber(pick(record, 'id', 'supplierId', 'supplier_id')),
    name: toStringValue(pick(record, 'name')),
    contact_name: toStringValue(pick(record, 'contact_name', 'contactName')),
    phone: toStringValue(pick(record, 'phone')),
    email: toStringValue(pick(record, 'email')),
    notes: toStringValue(pick(record, 'notes')),
    is_active: toBoolean(pick(record, 'is_active', 'isActive'), true),
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

function normalizeProductImage(value: unknown): ProductImage | null {
  if (!isRecord(value)) return null

  return {
    id: toNumber(pick(value, 'id')),
    product:
      pick(value, 'product') === undefined
        ? toNumber(pick(value, 'productId', 'product_id')) || undefined
        : toNumber(pick(value, 'product')),
    image: toStringValue(pick(value, 'image', 'imageUrl', 'image_url')),
    alt_text: toStringValue(pick(value, 'alt_text', 'altText')),
    is_main: toBoolean(pick(value, 'is_main', 'isMain')),
    order: toNumber(pick(value, 'order')),
    created_at: toStringValue(
      pick(value, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
  }
}

function normalizeProductSpec(value: unknown): ProductSpec {
  const record = isRecord(value) ? value : {}

  return {
    id: toNumber(pick(record, 'id')),
    product:
      pick(record, 'product') === undefined
        ? toNumber(pick(record, 'productId', 'product_id')) || undefined
        : toNumber(pick(record, 'product')),
    name: toStringValue(pick(record, 'name')),
    value: toStringValue(pick(record, 'value')),
    unit: toStringValue(pick(record, 'unit')),
    order: toNumber(pick(record, 'order')),
  }
}

export function normalizeProductListItem(value: unknown): ProductListItem {
  const record = isRecord(value) ? value : {}
  const rawImages = pick<unknown[]>(record, 'images')
  const images = Array.isArray(rawImages)
    ? rawImages
        .map(normalizeProductImage)
        .filter((image): image is ProductImage => Boolean(image))
    : []
  const mainImage =
    normalizeProductImage(pick(record, 'main_image', 'mainImage')) ??
    images.find((image) => image.is_main) ??
    images[0] ??
    null
  const categoryValue = pick(record, 'category') ?? {
    id: pick(record, 'categoryId', 'category_id'),
  }
  const brandValue = pick(record, 'brand')

  return {
    id: toNumber(pick(record, 'id')),
    name: toStringValue(pick(record, 'name')),
    slug: toStringValue(pick(record, 'slug')),
    category: normalizeCategory(categoryValue),
    brand:
      brandValue === null || brandValue === undefined
        ? null
        : normalizeBrand(brandValue),
    product_type: toStringValue(
      pick(record, 'product_type', 'productType'),
      'machinery',
    ) as ProductType,
    condition: toStringValue(
      pick(record, 'condition'),
      'not_applicable',
    ) as ProductCondition,
    short_description: toStringValue(
      pick(record, 'short_description', 'shortDescription'),
    ),
    price: toNullableString(pick(record, 'price')),
    price_visible: toBoolean(
      pick(record, 'price_visible', 'priceVisible'),
      true,
    ),
    stock_status: toStringValue(
      pick(record, 'stock_status', 'stockStatus'),
      'on_request',
    ) as StockStatus,
    is_featured: toBoolean(pick(record, 'is_featured', 'isFeatured')),
    is_published: toBoolean(pick(record, 'is_published', 'isPublished'), true),
    main_image: mainImage,
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

export function normalizeProductDetail(value: unknown): ProductDetail {
  const record = isRecord(value) ? value : {}
  const rawImages = pick<unknown[]>(record, 'images')
  const rawSpecs = pick<unknown[]>(record, 'specs')

  return {
    ...normalizeProductListItem(record),
    supplier: pick(record, 'supplier')
      ? normalizeSupplier(pick(record, 'supplier'))
      : null,
    description: toStringValue(pick(record, 'description')),
    model: toStringValue(pick(record, 'model')),
    sku: toStringValue(pick(record, 'sku')),
    year:
      pick(record, 'year') === null
        ? null
        : toNumber(pick(record, 'year')) || null,
    hours_meter:
      pick(record, 'hours_meter', 'hoursMeter') === null
        ? null
        : toNumber(pick(record, 'hours_meter', 'hoursMeter')) || null,
    images: Array.isArray(rawImages)
      ? rawImages
          .map((image) => normalizeProductImage(image))
          .filter((image): image is ProductImage => Boolean(image))
      : [],
    specs: Array.isArray(rawSpecs) ? rawSpecs.map(normalizeProductSpec) : [],
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

export function normalizePromotion(value: unknown): Promotion {
  const record = isRecord(value) ? value : {}
  const product = pick(record, 'product')

  return {
    id: toNumber(pick(record, 'id')),
    title: toStringValue(pick(record, 'title')),
    subtitle: toStringValue(pick(record, 'subtitle')),
    product:
      product && isRecord(product) ? normalizeProductListItem(product) : null,
    image: toNullableString(pick(record, 'image')),
    button_text: toStringValue(pick(record, 'button_text', 'buttonText')),
    button_url: toStringValue(pick(record, 'button_url', 'buttonUrl')),
    is_active: toBoolean(pick(record, 'is_active', 'isActive'), true),
    order: toNumber(pick(record, 'order')),
    starts_at: toNullableString(pick(record, 'starts_at', 'startsAt')),
    ends_at: toNullableString(pick(record, 'ends_at', 'endsAt')),
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

function normalizeQuoteRequest(value: unknown): QuoteRequestAdmin {
  const record = isRecord(value) ? value : {}
  const product = pick(record, 'product')
  const productRecord = isRecord(product) ? product : null

  return {
    id: toNumber(pick(record, 'id')),
    product: productRecord
      ? toNumber(pick(productRecord, 'id'))
      : pick(record, 'product') === null
        ? null
        : toNumber(pick(record, 'product', 'productId', 'product_id')) || null,
    product_name: toStringValue(
      pick(record, 'product_name', 'productName') ??
        (productRecord ? pick(productRecord, 'name') : undefined),
    ),
    customer_name: toStringValue(pick(record, 'customer_name', 'customerName')),
    customer_phone: toStringValue(
      pick(record, 'customer_phone', 'customerPhone'),
    ),
    customer_email: toStringValue(
      pick(record, 'customer_email', 'customerEmail'),
    ),
    company_name: toStringValue(pick(record, 'company_name', 'companyName')),
    city: toStringValue(pick(record, 'city')),
    preferred_contact_method: toStringValue(
      pick(record, 'preferred_contact_method', 'preferredContactMethod'),
    ) as QuoteRequestAdmin['preferred_contact_method'],
    message: toStringValue(pick(record, 'message')),
    status: toStringValue(pick(record, 'status'), 'new') as QuoteStatus,
    internal_notes: toStringValue(
      pick(record, 'internal_notes', 'internalNotes'),
    ),
    seller_response: toStringValue(
      pick(record, 'seller_response', 'sellerResponse'),
    ),
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
    contacted_at: toNullableString(pick(record, 'contacted_at', 'contactedAt')),
    quoted_at: toNullableString(pick(record, 'quoted_at', 'quotedAt')),
    closed_at: toNullableString(pick(record, 'closed_at', 'closedAt')),
  }
}

function sectionLabel(section: HomeSection) {
  if (section === 'machinery_promotions') return 'Promociones en maquinarias'
  if (section === 'spare_parts_offers') return 'Oferta en repuestos'
  return 'Servicios de reparación'
}

export function normalizeHomeSectionItem(value: unknown): HomeSectionItem {
  const record = isRecord(value) ? value : {}
  const section = toStringValue(
    pick(record, 'section'),
    'machinery_promotions',
  ) as HomeSection

  return {
    id: toNumber(pick(record, 'id')),
    section,
    section_label: toStringValue(
      pick(record, 'section_label', 'sectionLabel'),
      sectionLabel(section),
    ),
    position: toNumber(pick(record, 'position'), 1),
    product: normalizeProductListItem(pick(record, 'product')),
    is_active: toBoolean(pick(record, 'is_active', 'isActive'), true),
    created_at: toStringValue(
      pick(record, 'created_at', 'createdAt'),
      EMPTY_DATE,
    ),
    updated_at: toStringValue(
      pick(record, 'updated_at', 'updatedAt'),
      EMPTY_DATE,
    ),
  }
}

export function normalizeProductListResponse(
  response: ApiListResponse<unknown>,
) {
  return normalizeListResponse(response, normalizeProductListItem)
}

export function normalizeCategoryListResponse(
  response: ApiListResponse<unknown>,
) {
  return normalizeListResponse(response, normalizeCategory)
}

export function normalizeBrandListResponse(response: ApiListResponse<unknown>) {
  return normalizeListResponse(response, normalizeBrand)
}

export function normalizeSupplierListResponse(
  response: ApiListResponse<unknown>,
) {
  return normalizeListResponse(response, normalizeSupplier)
}

export function normalizePromotionListResponse(
  response: ApiListResponse<unknown>,
) {
  return normalizeListResponse(response, normalizePromotion)
}

export function normalizeQuoteRequestListResponse(
  response: ApiListResponse<unknown>,
) {
  return normalizeListResponse(response, normalizeQuoteRequest)
}

export function normalizeHomeSectionItemListResponse(
  response: ApiListResponse<unknown>,
) {
  return normalizeListResponse(response, normalizeHomeSectionItem)
}

function jsonBody(payload: unknown) {
  return JSON.stringify(payload)
}

function toDotnetBrandPayload(payload: BrandFormValues | Partial<BrandFormValues>) {
  const { logo: _logo, ...rest } = payload
  return rest
}

function toDotnetPromotionPayload(
  payload: PromotionFormValues | Partial<PromotionFormValues>,
) {
  const { image: _image, ...rest } = payload
  return rest
}

function normalizeProductWritePayload<T extends Partial<ProductFormValues>>(payload: T): T {
  if (!Object.prototype.hasOwnProperty.call(payload, 'price')) return payload

  return {
    ...payload,
    price: normalizeChileanPriceInput(payload.price),
  }
}

function normalizeCategoryWritePayload(payload: CategoryFormValues | Partial<CategoryFormValues>) {
  return {
    name: payload.name,
    slug: payload.slug || undefined,
    parent: payload.parent ?? null,
    product_type: payload.product_type ?? 'machinery',
    is_active: payload.is_active,
  }
}

function dotnetUploadPending(): never {
  throw new ApiError(
    'La carga de imágenes todavía no está implementada en la API .NET.',
    501,
  )
}

export async function getAdminProducts(
  params?: Record<string, string | number | boolean | undefined>,
) {
  const response = await authFetch<ApiListResponse<unknown>>('/products/', {
    params: { include_unpublished: true, ...(params ?? {}) },
  })
  return normalizeProductListResponse(response)
}

export async function getAdminProduct(slug: string) {
  const response = await authFetch<unknown>(`/products/${slug}/`)
  return normalizeProductDetail(response)
}

export async function createProduct(payload: ProductFormValues) {
  const response = await authFetch<unknown>('/products/', {
    method: 'POST',
    body: jsonBody(normalizeProductWritePayload(payload)),
  })
  return normalizeProductDetail(response)
}

export async function updateProduct(
  slug: string,
  payload: Partial<ProductFormValues>,
) {
  const response = await authFetch<unknown>(`/products/${slug}/`, {
    method: 'PATCH',
    body: jsonBody(normalizeProductWritePayload(payload)),
  })
  return normalizeProductDetail(response)
}

export async function deleteProduct(slug: string) {
  return authFetch<void>(`/products/${slug}/`, {
    method: 'DELETE',
  })
}

export async function getProductImages(productId: number) {
  const response = await authFetch<ApiListResponse<unknown>>(
    '/product-images/',
    {
      params: { product: productId },
    },
  )
  return normalizeListResponse(
    response,
    (item) => normalizeProductImage(item) as ProductImage,
  )
}

export async function createProductImage(payload: ProductImageWritePayload) {
  if (API_PROVIDER === 'dotnet') dotnetUploadPending()

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

export async function updateProductImage(
  id: number,
  payload: Partial<ProductImageWritePayload>,
) {
  if (API_PROVIDER === 'dotnet') dotnetUploadPending()

  return authFetch<ProductImage>(`/product-images/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteProductImage(id: number) {
  if (API_PROVIDER === 'dotnet') dotnetUploadPending()

  return authFetch<void>(`/product-images/${id}/`, {
    method: 'DELETE',
  })
}

export async function getProductSpecs(productId: number) {
  const response = await authFetch<ApiListResponse<unknown>>(
    '/product-specs/',
    {
      params: { product: productId },
    },
  )
  return normalizeListResponse(response, normalizeProductSpec)
}

export async function createProductSpec(payload: ProductSpecWritePayload) {
  const response = await authFetch<unknown>('/product-specs/', {
    method: 'POST',
    body: jsonBody(payload),
  })
  return normalizeProductSpec(response)
}

export async function updateProductSpec(
  id: number,
  payload: Partial<ProductSpecWritePayload>,
) {
  const response = await authFetch<unknown>(`/product-specs/${id}/`, {
    method: 'PATCH',
    body: jsonBody(payload),
  })
  return normalizeProductSpec(response)
}

export async function deleteProductSpec(id: number) {
  return authFetch<void>(`/product-specs/${id}/`, {
    method: 'DELETE',
  })
}

type AdminQuotesParams = Record<
  string,
  string | number | boolean | undefined
> & {
  status?: QuoteStatus | ''
  search?: string
  ordering?:
    | 'created_at'
    | '-created_at'
    | 'updated_at'
    | '-updated_at'
    | 'status'
    | '-status'
    | ''
  product?: number
}

export async function getAdminQuotes(params?: AdminQuotesParams) {
  const response = await authFetch<ApiListResponse<unknown>>(
    '/quote-requests/',
    { params },
  )
  return normalizeQuoteRequestListResponse(response)
}

export async function getAdminQuote(id: number) {
  const response = await authFetch<unknown>(`/quote-requests/${id}/`)
  return normalizeQuoteRequest(response)
}

export async function updateQuote(
  id: number,
  payload: Partial<QuoteRequestAdmin>,
) {
  const response = await authFetch<unknown>(`/quote-requests/${id}/`, {
    method: 'PATCH',
    body: jsonBody(payload),
  })
  return normalizeQuoteRequest(response)
}

export async function deleteQuote(id: number) {
  return authFetch<void>(`/quote-requests/${id}/`, {
    method: 'DELETE',
  })
}

const includeInactiveParams = { include_inactive: true }

export async function getAdminCategories() {
  const response = await authFetch<ApiListResponse<unknown>>('/categories/', {
    params: includeInactiveParams,
  })
  return normalizeCategoryListResponse(response)
}

export async function getAdminCategory(id: number) {
  const response = await authFetch<unknown>(`/categories/${id}/`, {
    params: includeInactiveParams,
  })
  return normalizeCategory(response)
}

export async function createCategory(payload: CategoryFormValues) {
  const response = await authFetch<unknown>('/categories/', {
    method: 'POST',
    body: jsonBody(normalizeCategoryWritePayload(payload)),
  })
  return normalizeCategory(response)
}

export async function updateCategory(
  id: number,
  payload: Partial<CategoryFormValues>,
) {
  const response = await authFetch<unknown>(`/categories/${id}/`, {
    method: 'PATCH',
    body: jsonBody(normalizeCategoryWritePayload(payload)),
  })
  return normalizeCategory(response)
}

export async function deleteCategory(id: number) {
  return authFetch<void>(`/categories/${id}/`, { method: 'DELETE' })
}

export async function getAdminBrands() {
  const response = await authFetch<ApiListResponse<unknown>>('/brands/', {
    params: includeInactiveParams,
  })
  return normalizeBrandListResponse(response)
}

export async function getAdminBrand(id: number) {
  const response = await authFetch<unknown>(`/brands/${id}/`, {
    params: includeInactiveParams,
  })
  return normalizeBrand(response)
}

export async function createBrand(payload: BrandFormValues) {
  if (API_PROVIDER === 'dotnet') {
    const response = await authFetch<unknown>('/brands/', {
      method: 'POST',
      body: jsonBody(toDotnetBrandPayload(payload)),
    })
    return normalizeBrand(response)
  }

  const formData = new FormData()
  formData.append('name', payload.name)
  if (payload.slug) formData.append('slug', payload.slug)
  if (payload.description) formData.append('description', payload.description)
  formData.append('is_active', String(payload.is_active))
  if (payload.logo) formData.append('logo', payload.logo)

  const response = await authFetch<unknown>('/brands/', { method: 'POST', body: formData })
  return normalizeBrand(response)
}

export async function updateBrand(
  id: number,
  payload: Partial<BrandFormValues>,
) {
  if (API_PROVIDER === 'dotnet') {
    const response = await authFetch<unknown>(`/brands/${id}/`, {
      method: 'PATCH',
      body: jsonBody(toDotnetBrandPayload(payload)),
    })
    return normalizeBrand(response)
  }

  const formData = new FormData()
  if (payload.name !== undefined) formData.append('name', payload.name)
  if (payload.slug !== undefined) formData.append('slug', payload.slug)
  if (payload.description !== undefined)
    formData.append('description', payload.description)
  if (payload.is_active !== undefined)
    formData.append('is_active', String(payload.is_active))
  if (payload.logo instanceof File) formData.append('logo', payload.logo)

  const response = await authFetch<unknown>(`/brands/${id}/`, {
    method: 'PATCH',
    body: formData,
  })
  return normalizeBrand(response)
}

export async function deleteBrand(id: number) {
  return authFetch<void>(`/brands/${id}/`, { method: 'DELETE' })
}

export async function getAdminSuppliers() {
  const response = await authFetch<ApiListResponse<unknown>>('/suppliers/', {
    params: includeInactiveParams,
  })
  return normalizeSupplierListResponse(response)
}

export async function getAdminSupplier(id: number) {
  const response = await authFetch<unknown>(`/suppliers/${id}/`, {
    params: includeInactiveParams,
  })
  return normalizeSupplier(response)
}

export async function createSupplier(payload: SupplierFormValues) {
  const response = await authFetch<unknown>('/suppliers/', {
    method: 'POST',
    body: jsonBody(payload),
  })
  return normalizeSupplier(response)
}

export async function updateSupplier(
  id: number,
  payload: Partial<SupplierFormValues>,
) {
  const response = await authFetch<unknown>(`/suppliers/${id}/`, {
    method: 'PATCH',
    body: jsonBody(payload),
  })
  return normalizeSupplier(response)
}

export async function deleteSupplier(id: number) {
  return authFetch<void>(`/suppliers/${id}/`, { method: 'DELETE' })
}

export async function getAdminPromotions() {
  const response = await authFetch<ApiListResponse<unknown>>('/promotions/', {
    params: includeInactiveParams,
  })
  return normalizePromotionListResponse(response)
}

export async function getAdminPromotion(id: number) {
  const response = await authFetch<unknown>(`/promotions/${id}/`, {
    params: includeInactiveParams,
  })
  return normalizePromotion(response)
}

function toPromotionBody(
  payload: PromotionFormValues | Partial<PromotionFormValues>,
) {
  const formData = new FormData()
  if (payload.title !== undefined) formData.append('title', payload.title)
  if (payload.subtitle !== undefined)
    formData.append('subtitle', payload.subtitle)
  if (payload.product !== undefined)
    formData.append(
      'product',
      payload.product === null ? '' : String(payload.product),
    )
  if (payload.button_text !== undefined)
    formData.append('button_text', payload.button_text)
  if (payload.button_url !== undefined)
    formData.append('button_url', payload.button_url)
  if (payload.is_active !== undefined)
    formData.append('is_active', String(payload.is_active))
  if (payload.order !== undefined)
    formData.append('order', String(payload.order))
  if (payload.starts_at !== undefined)
    formData.append('starts_at', payload.starts_at || '')
  if (payload.ends_at !== undefined)
    formData.append('ends_at', payload.ends_at || '')
  if (payload.image) formData.append('image', payload.image)
  return formData
}

export async function createPromotion(payload: PromotionFormValues) {
  const response = await authFetch<unknown>('/promotions/', {
    method: 'POST',
    body: API_PROVIDER === 'dotnet'
      ? jsonBody(toDotnetPromotionPayload(payload))
      : toPromotionBody(payload),
  })
  return normalizePromotion(response)
}

export async function updatePromotion(
  id: number,
  payload: Partial<PromotionFormValues>,
) {
  const response = await authFetch<unknown>(`/promotions/${id}/`, {
    method: 'PATCH',
    body: API_PROVIDER === 'dotnet'
      ? jsonBody(toDotnetPromotionPayload(payload))
      : toPromotionBody(payload),
  })
  return normalizePromotion(response)
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
  const response = await authFetch<ApiListResponse<unknown>>(
    '/home-section-items/',
    {
      params: {
        include_inactive: true,
        ...(section ? { section } : {}),
      },
    },
  )
  return normalizeHomeSectionItemListResponse(response)
}

export async function createHomeSectionItem(
  payload: HomeSectionItemFormValues,
) {
  const response = await authFetch<unknown>('/home-section-items/', {
    method: 'POST',
    body: jsonBody(payload),
  })
  return normalizeHomeSectionItem(response)
}

export async function updateHomeSectionItem(
  id: number,
  payload: Partial<HomeSectionItemFormValues>,
) {
  const response = await authFetch<unknown>(`/home-section-items/${id}/`, {
    method: 'PATCH',
    body: jsonBody(payload),
  })
  return normalizeHomeSectionItem(response)
}

export async function deleteHomeSectionItem(id: number) {
  return authFetch<void>(`/home-section-items/${id}/`, { method: 'DELETE' })
}
