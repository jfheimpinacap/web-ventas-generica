export type AnalyticsParams = Record<string, string | number | boolean | null | undefined>

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

  if (import.meta.env.DEV) {
    console.debug('[analytics]', payload)
  }
}

export function trackQuoteClick(params?: AnalyticsParams) {
  trackEvent('quote_click', params)
}

export function trackQuoteSubmit(params?: AnalyticsParams) {
  trackEvent('quote_submit', { source: 'quote_form', ...params })
}

export function trackWhatsAppClick(params?: AnalyticsParams) {
  trackEvent('whatsapp_click', params)
}

export function trackProductView(params?: AnalyticsParams) {
  trackEvent('product_view', params)
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
