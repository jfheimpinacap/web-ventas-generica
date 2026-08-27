import { access, readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)))
const distDir = join(frontendDir, 'dist')
const server = await import(pathToFileURL(join(frontendDir, '.prerender-server', 'entry-server.js')).href)
const failures = []
const fail = (message) => failures.push(message)
const occurrences = (source, pattern) => source.match(pattern)?.length ?? 0

async function load(relativePath) {
  try { return await readFile(join(distDir, relativePath), 'utf8') } catch { fail(`Falta ${relativePath}`); return '' }
}

for (const route of server.PRERENDER_ROUTES) {
  const relativePath = server.prerenderOutputParts(route).join('/')
  const html = await load(relativePath)
  if (!html) continue
  if (!html.includes('data-prerendered="true"') || !html.includes(`data-prerender-path="${route}"`)) fail(`${route}: marcadores inválidos`)
  if (!/<div id="root"[^>]*>\s*\S[\s\S]*?<\/div>/i.test(html)) fail(`${route}: root vacío`)
  if (occurrences(html, /<h1(?:\s|>)/gi) !== 1) fail(`${route}: debe contener un H1`)
  if (occurrences(html, /<title>[^<]+<\/title>/gi) !== 1) fail(`${route}: title inválido`)
  if (occurrences(html, /<meta name="description" content="[^"]+"/gi) !== 1) fail(`${route}: description inválida`)
  const canonicals = [...html.matchAll(/<link rel="canonical" href="([^"]+)"/gi)]
  if (canonicals.length !== 1 || !canonicals[0][1].startsWith('https://jem-nexus.cl') || /[?#]/.test(canonicals[0][1])) fail(`${route}: canonical inválido`)
  if (/noindex/i.test(html) || !/<meta name="robots" content="index,follow/i.test(html)) fail(`${route}: robots no indexable`)
  for (const token of ['og:title', 'og:description', 'og:type', 'og:url', 'og:site_name', 'og:locale', 'twitter:card', 'twitter:title', 'twitter:description']) {
    if (occurrences(html, new RegExp(`["']${token}["']`, 'gi')) !== 1) fail(`${route}: etiqueta ${token} ausente o duplicada`)
  }
  const jsonLdIds = [...html.matchAll(/<script type="application\/ld\+json" data-jsonld-id="([^"]+)">([\s\S]*?)<\/script>/gi)]
  if (jsonLdIds.length === 0 || new Set(jsonLdIds.map((match) => match[1])).size !== jsonLdIds.length) fail(`${route}: JSON-LD ausente o duplicado`)
  for (const match of jsonLdIds) { try { JSON.parse(match[2]) } catch { fail(`${route}: JSON-LD inválido (${match[1]})`) } }
  if (/access_token|refresh_token|authorization|customer_(?:name|phone|email)|[A-Z]:\\|\/workspace\//i.test(html)) fail(`${route}: contenido sensible o ruta física`)
  if (/Maquinaria promocional \d|Repuesto en oferta \d|Servicio de reparación \d|mockProducts/i.test(html)) fail(`${route}: producto ficticio detectado`)
}

for (const [name, noindex] of [['_spa.html', false], ['_noindex.html', true]]) {
  const html = await load(name)
  if (!html) continue
  if (!/<div id="root"><\/div>/.test(html) || /data-prerender(?:ed|-path)/.test(html)) fail(`${name}: root o marcadores inválidos`)
  if (!/<script[^>]+type="module"[^>]+src="[^"]+"/i.test(html)) fail(`${name}: bundle Vite ausente`)
  if (/rel="canonical"|application\/ld\+json/i.test(html)) fail(`${name}: canonical o JSON-LD inesperado`)
  const noindexCount = occurrences(html, /<meta name="robots" content="noindex,nofollow"/gi)
  if ((noindex && noindexCount !== 1) || (!noindex && noindexCount !== 0)) fail(`${name}: robots inválido`)
}

for (const file of ['robots.txt', 'sitemap.xml', 'llms.txt', 'web.config', 'favicon.ico', 'site.webmanifest', 'icons/favicon-96x96.png', 'icons/apple-touch-icon.png']) {
  try { await access(join(distDir, file)) } catch { fail(`Falta archivo público ${file}`) }
}

if (failures.length) throw new Error(`Validación de prerender fallida:\n- ${failures.join('\n- ')}`)
