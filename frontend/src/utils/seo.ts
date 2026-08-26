import { resolveMediaUrl } from '../services/api'
import type { ProductCondition, ProductDetail, ProductListItem, StockStatus } from '../types/catalog'

export const PUBLIC_SITE_URL = 'https://jem-nexus.cl'
export const ORGANIZATION_ID = `${PUBLIC_SITE_URL}/#organization`
export const WEBSITE_ID = `${PUBLIC_SITE_URL}/#website`

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
  '/repuestos': {
    title: 'Repuestos para maquinaria industrial | JEM Nexus',
    description: 'Revisa repuestos industriales publicados, consulta la información de cada producto y envía una solicitud de cotización.',
  },
  '/servicios': {
    title: 'Servicios de reparación y mantención | JEM Nexus',
    description: 'Consulta servicios publicados de reparación y mantención industrial y solicita información mediante el flujo de cotización.',
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
  return PUBLIC_SITE_URL
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
  const mapping: Partial<Record<StockStatus, string>> = {
    available: 'https://schema.org/InStock',
    reserved: 'https://schema.org/LimitedAvailability',
    sold: 'https://schema.org/SoldOut',
  }
  return mapping[stockStatus]
}

export function buildBreadcrumbJsonLd(items: Array<{ label: string; to?: string }>, canonicalUrl: string) {
  if (items.length < 2) return null
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    '@id': `${canonicalUrl}#breadcrumb`,
    itemListElement: items.map((item, index) => {
      const listItem: Record<string, unknown> = {
        '@type': 'ListItem',
        position: index + 1,
        name: item.label,
      }
      listItem.item = item.to ? buildPublicUrl(item.to) : canonicalUrl
      return listItem
    }),
  }
}

export function buildProductJsonLd(product: ProductDetail, canonicalUrl: string) {
  const image = getProductImageUrl(product)
  const isService = product.product_type === 'service'
  const entityId = `${canonicalUrl}#${isService ? 'service' : 'product'}`
  const payload: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': isService ? 'Service' : 'Product',
    '@id': entityId,
    name: product.name,
    description: (product.description || product.short_description || product.name).replace(/\s+/g, ' ').trim(),
    url: canonicalUrl,
    [isService ? 'provider' : 'seller']: { '@id': ORGANIZATION_ID },
  }

  if (image) payload.image = image
  if (product.brand?.name) payload.brand = { '@type': 'Brand', name: product.brand.name }
  if (product.category?.name) payload.category = product.category.name
  if (product.model?.trim()) payload.model = product.model.trim()
  if (product.sku?.trim()) payload.sku = product.sku.trim()

  const condition = !isService ? getConditionSchema(product.condition) : undefined
  if (condition) payload.itemCondition = condition

  const price = product.price?.trim()
  const numericPrice = price && /^\d+(?:\.\d+)?$/.test(price) ? Number(price) : 0
  const currency = product.price_currency
  if (product.price_visible === true && product.stock_status !== 'sold' && numericPrice > 0 && (currency === 'CLP' || currency === 'USD')) {
    const offer: Record<string, unknown> = {
      '@type': 'Offer', '@id': `${canonicalUrl}#offer`, url: canonicalUrl, price, priceCurrency: currency,
      seller: { '@id': ORGANIZATION_ID },
    }
    if (condition && !isService) offer.itemCondition = condition
    const availability = !isService ? getAvailabilitySchema(product.stock_status) : undefined
    if (availability) offer.availability = availability
    if (product.price_tax_mode === 'vat_included' || product.price_tax_mode === 'plus_vat') {
      offer.priceSpecification = {
        '@type': 'PriceSpecification', price, priceCurrency: currency,
        valueAddedTaxIncluded: product.price_tax_mode === 'vat_included',
      }
    }
    payload.offers = offer
  }

  return payload
}

export function getConditionSchema(condition: ProductCondition) {
  const mapping: Partial<Record<ProductCondition, string>> = {
    new: 'https://schema.org/NewCondition', used: 'https://schema.org/UsedCondition',
    refurbished: 'https://schema.org/RefurbishedCondition',
  }
  return mapping[condition]
}

export function buildPageJsonLd(path: StaticSeoPath, type: 'WebPage' | 'CollectionPage' | 'ContactPage' | 'AboutPage', breadcrumb = true) {
  const seo = getStaticSeo(path)
  return {
    '@context': 'https://schema.org', '@type': type, '@id': `${seo.canonical}#webpage`, url: seo.canonical,
    name: seo.title, description: seo.description, inLanguage: 'es-CL',
    isPartOf: { '@id': WEBSITE_ID }, about: { '@id': ORGANIZATION_ID },
    ...(breadcrumb ? { breadcrumb: { '@id': `${seo.canonical}#breadcrumb` } } : {}),
  }
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
