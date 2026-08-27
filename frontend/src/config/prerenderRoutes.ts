export const PRERENDER_ROUTES = [
  '/',
  '/catalogo',
  '/maquinaria-nueva',
  '/maquinaria-usada',
  '/repuestos',
  '/servicios',
  '/cotizar',
  '/contacto',
  '/sobre-nosotros',
  '/preguntas-frecuentes',
] as const

export type PrerenderRoute = (typeof PRERENDER_ROUTES)[number]

export const CATALOG_FILTER_PARAMS = ['search', 'category', 'brand', 'product_type', 'condition', 'stock_status', 'ordering'] as const

export function normalizePrerenderPath(pathname: string) {
  return pathname !== '/' && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname
}

export function isPrerenderRoute(pathname: string): pathname is PrerenderRoute {
  return (PRERENDER_ROUTES as readonly string[]).includes(pathname)
}

export function prerenderOutputParts(route: PrerenderRoute): readonly string[] {
  if (route === '/') return ['index.html']
  if (!/^\/[a-z0-9-]+$/.test(route) || route.includes('..')) throw new Error(`Ruta de prerender no segura: ${route}`)
  return [route.slice(1), 'index.html']
}
