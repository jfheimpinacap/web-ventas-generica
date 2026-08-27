export type AnalyticsParams = Partial<Record<'source' | 'location' | 'product_id' | 'product_name' | 'product_type' | 'preferred_contact_method' | 'method' | 'content_type' | 'category' | 'brand' | 'price' | 'technical_sheet_id', string | number | boolean | null>>

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>
  }
}

function sanitizeParams(params?: AnalyticsParams) {
  if (!params) return {}
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined))
}

export function trackEvent(eventName: string, params?: AnalyticsParams) {
  if (typeof window === 'undefined') return

  const payload = { event: eventName, ...sanitizeParams(params) }

  if (Array.isArray(window.dataLayer)) {
    window.dataLayer.push(payload)
  }
}

export function trackQuoteClick(params?: AnalyticsParams) {
  trackEvent('quote_click', params)
}

export function trackGenerateLead(params?: AnalyticsParams) {
  trackEvent('generate_lead', { source: 'quote_form', ...params })
}

export function trackShare(params?: AnalyticsParams) { trackEvent('share', params) }

export function trackWhatsAppClick(params?: AnalyticsParams) {
  trackEvent('whatsapp_click', params)
}

export function trackProductView(params?: AnalyticsParams) {
  trackEvent('product_view', params)
}

export function trackTechnicalSheetView(params?: AnalyticsParams) {
  trackEvent('technical_sheet_view', params)
}

export function trackTechnicalSheetDownload(params?: AnalyticsParams) {
  trackEvent('technical_sheet_download', params)
}

export function trackProductDetailClick(params?: AnalyticsParams) {
  trackEvent('product_detail_click', params)
}

export function trackCategoryView(params?: AnalyticsParams) {
  trackEvent('category_view', params)
}

export function trackHeroOfferClick(params?: AnalyticsParams) {
  trackEvent('hero_offer_click', params)
}

export function initializeGtm() {
  if (typeof window === 'undefined') return

  const gtmId = import.meta.env.VITE_GTM_ID?.trim()
  if (!gtmId) return

  window.dataLayer = window.dataLayer ?? []

  const existingScript = document.querySelector<HTMLScriptElement>(`script[data-gtm-id="${gtmId}"]`)
  if (existingScript) return

  window.dataLayer.push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' })

  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(gtmId)}`
  script.dataset.gtmId = gtmId
  document.head.appendChild(script)
}
