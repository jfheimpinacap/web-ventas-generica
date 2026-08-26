import { resolveMediaUrl } from '../services/api'
import type { ProductDetail, ProductListItem, StockStatus } from '../types/catalog'

export const STATIC_PAGE_SEO = {
  '/': {
    title: 'JEM Nexus | Maquinaria, repuestos y servicios industriales',
    description: 'Explora maquinaria, repuestos y servicios industriales publicados por JEM Nexus y solicita información para tu cotización.',
  },
  '/catalogo': {
    title: 'Catálogo de productos industriales | JEM Nexus',
    description: 'Revisa el catálogo de maquinaria, repuestos y servicios industriales publicados por JEM Nexus para solicitar una cotización.',
  },
  '/maquinaria-nueva': {
    title: 'Maquinaria nueva para cotización | JEM Nexus',
    description: 'Consulta maquinaria nueva publicada por JEM Nexus, revisa sus características y envía una solicitud de cotización.',
  },
  '/maquinaria-usada': {
    title: 'Maquinaria usada para cotización | JEM Nexus',
    description: 'Consulta maquinaria usada publicada por JEM Nexus, revisa su información comercial y solicita una cotización.',
  },
  '/cotizar': {
    title: 'Solicitar una cotización | JEM Nexus',
    description: 'Envía una solicitud de cotización de maquinaria, repuestos o servicios industriales al equipo comercial de JEM Nexus.',
  },
  '/contacto': {
    title: 'Contacto comercial | JEM Nexus',
    description: 'Contacta a JEM Nexus para consultar por maquinaria, repuestos, servicios industriales o el estado de una cotización.',
  },
  '/sobre-nosotros': {
    title: 'Conoce JEM Nexus | Maquinaria y servicios industriales',
    description: 'Conoce la plataforma comercial JEM Nexus y su catálogo para cotizar maquinaria, repuestos y servicios industriales.',
  },
  '/preguntas-frecuentes': {
    title: 'Preguntas sobre cotizaciones y productos | JEM Nexus',
    description: 'Resuelve preguntas frecuentes sobre productos publicados, solicitudes de cotización, precios, disponibilidad y contacto con JEM Nexus.',
  },
} as const

export type StaticSeoPath = keyof typeof STATIC_PAGE_SEO

export function getStaticSeo(path: StaticSeoPath) {
  return { ...STATIC_PAGE_SEO[path], canonical: buildPublicUrl(path) }
}

export function getPublicSiteUrl() {
  const envUrl = import.meta.env.VITE_PUBLIC_SITE_URL?.trim()
  if (envUrl) {
    try {
      return new URL(envUrl).origin
    } catch {
      // An invalid optional value must not prevent the document metadata from updating.
    }
  }
  return window.location.origin
}

export function buildPublicUrl(path: string) {
  const url = new URL(path.startsWith('/') ? path : `/${path}`, `${getPublicSiteUrl()}/`)
  url.search = ''
  url.hash = ''
  return url.toString().replace(/\/$/, url.pathname === '/' ? '/' : '')
}

export function buildAbsoluteUrl(pathOrUrl: string) {
  return new URL(pathOrUrl, `${getPublicSiteUrl()}/`).toString()
}

export function truncateSeoDescription(value: string, maximumLength = 160) {
  const normalized = value.replace(/\s+/g, ' ').trim()
  if (normalized.length <= maximumLength) return normalized
  const candidate = normalized.slice(0, maximumLength + 1)
  const lastSpace = candidate.lastIndexOf(' ')
  return `${candidate.slice(0, lastSpace > 0 ? lastSpace : maximumLength).replace(/[,:;.!?]+$/, '')}…`
}

export function getProductImageUrl(product: Pick<ProductDetail, 'images' | 'main_image'>) {
  const mainImage = product.images.find((image) => image.is_main) ?? product.images[0] ?? product.main_image
  if (!mainImage?.image) return null
  const resolvedImage = resolveMediaUrl(mainImage.image)
  return resolvedImage ? buildAbsoluteUrl(resolvedImage) : null
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
