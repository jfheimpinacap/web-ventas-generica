import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'

import { App } from './App'
import { createHeadCollector, HeadCollectorProvider, type HeadCollector } from './components/common/HeadCollector'
import { isPrerenderRoute, normalizePrerenderPath, PRERENDER_ROUTES, prerenderOutputParts, type PrerenderRoute } from './config/prerenderRoutes'

function escapeHtml(value: string) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

function serializeHead(collector: HeadCollector) {
  const seo = collector.seo
  if (!seo?.title || !seo.description || !seo.canonical) throw new Error('La ruta no registró metadatos SEO completos.')
  const tags = [
    `<title>${escapeHtml(seo.title)}</title>`,
    `<meta name="description" content="${escapeHtml(seo.description)}" data-jem-seo="true" />`,
    `<meta name="robots" content="${escapeHtml(seo.robots)}" data-jem-seo="true" />`,
    `<link rel="canonical" href="${escapeHtml(seo.canonical)}" data-jem-seo="true" />`,
    `<meta property="og:title" content="${escapeHtml(seo.ogTitle)}" data-jem-seo="true" />`,
    `<meta property="og:description" content="${escapeHtml(seo.ogDescription)}" data-jem-seo="true" />`,
    `<meta property="og:type" content="${escapeHtml(seo.ogType)}" data-jem-seo="true" />`,
    `<meta property="og:url" content="${escapeHtml(seo.canonical)}" data-jem-seo="true" />`,
    '<meta property="og:site_name" content="JEM Nexus" data-jem-seo="true" />',
    '<meta property="og:locale" content="es_CL" data-jem-seo="true" />',
    `<meta name="twitter:card" content="${escapeHtml(seo.twitterCard)}" data-jem-seo="true" />`,
    `<meta name="twitter:title" content="${escapeHtml(seo.ogTitle)}" data-jem-seo="true" />`,
    `<meta name="twitter:description" content="${escapeHtml(seo.ogDescription)}" data-jem-seo="true" />`,
  ]
  if (seo.ogImage) {
    tags.push(`<meta property="og:image" content="${escapeHtml(seo.ogImage)}" data-jem-seo="true" />`)
    tags.push(`<meta name="twitter:image" content="${escapeHtml(seo.ogImage)}" data-jem-seo="true" />`)
  }
  if (seo.ogImage && seo.imageAlt) {
    tags.push(`<meta property="og:image:alt" content="${escapeHtml(seo.imageAlt)}" data-jem-seo="true" />`)
    tags.push(`<meta name="twitter:image:alt" content="${escapeHtml(seo.imageAlt)}" data-jem-seo="true" />`)
  }
  collector.jsonLd.forEach(({ id, serialized }) => tags.push(`<script type="application/ld+json" data-jsonld-id="${escapeHtml(id)}">${serialized}</script>`))
  return tags.join('\n    ')
}

export function render(routeInput: string) {
  const route = normalizePrerenderPath(routeInput)
  if (!isPrerenderRoute(route) || routeInput.includes('?') || routeInput.includes('#')) throw new Error(`Ruta no permitida: ${routeInput}`)
  const collector = createHeadCollector()
  const html = renderToString(
    <HeadCollectorProvider collector={collector}>
      <App Router={MemoryRouter} routerProps={{ initialEntries: [route] }} />
    </HeadCollectorProvider>,
  )
  if (!html.trim() || !/<h1(?:\s|>)/i.test(html)) throw new Error(`La ruta ${route} no produjo root y H1.`)
  return { route, html, head: serializeHead(collector) }
}

export { PRERENDER_ROUTES, prerenderOutputParts }
export type { PrerenderRoute }
