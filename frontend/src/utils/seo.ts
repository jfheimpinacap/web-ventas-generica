import { resolveMediaUrl } from '../services/api'
import type { ProductDetail, ProductListItem, StockStatus } from '../types/catalog'

export function getPublicSiteUrl() {
  const envUrl = import.meta.env.VITE_PUBLIC_SITE_URL?.trim()
  if (envUrl) return envUrl.replace(/\/+$/, '')
  return window.location.origin
}

export function buildPublicUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${getPublicSiteUrl()}${normalizedPath}`
}

export function buildAbsoluteUrl(pathOrUrl: string) {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl
  return buildPublicUrl(pathOrUrl)
}

export function getProductImageUrl(product: Pick<ProductDetail, 'images' | 'main_image'>) {
  const mainImage = product.images.find((image) => image.is_main) ?? product.images[0] ?? product.main_image
  if (!mainImage?.image) return null
  return buildAbsoluteUrl(resolveMediaUrl(mainImage.image) || '')
}

export function getAvailabilitySchema(stockStatus: StockStatus) {
  const mapping: Record<StockStatus, string> = {
    available: 'https://schema.org/InStock',
    on_request: 'https://schema.org/PreOrder',
    reserved: 'https://schema.org/LimitedAvailability',
    sold: 'https://schema.org/OutOfStock',
  }
  return mapping[stockStatus]
}

export function buildBreadcrumbJsonLd(items: Array<{ label: string; to?: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => {
      const listItem: Record<string, unknown> = {
        '@type': 'ListItem',
        position: index + 1,
        name: item.label,
      }
      if (item.to) listItem.item = buildAbsoluteUrl(item.to)
      return listItem
    }),
  }
}

export function buildProductJsonLd(product: ProductDetail, canonicalUrl: string) {
  const image = getProductImageUrl(product)
  const payload: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    description: product.description || product.short_description || product.name,
    sku: product.sku || product.slug || String(product.id),
    url: canonicalUrl,
    offers: {
      '@type': 'Offer',
      url: canonicalUrl,
      availability: getAvailabilitySchema(product.stock_status),
      priceCurrency: 'CLP',
      ...(product.price_visible && product.price ? { price: product.price } : {}),
    },
  }

  if (image) payload.image = [image]
  if (product.brand?.name) payload.brand = { '@type': 'Brand', name: product.brand.name }
  if (product.category?.name) payload.category = product.category.name

  return payload
}

export function buildItemListJsonLd(products: ProductListItem[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    itemListElement: products.map((product, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      url: buildPublicUrl(`/producto/${product.slug}`),
      name: product.name,
    })),
  }
}
