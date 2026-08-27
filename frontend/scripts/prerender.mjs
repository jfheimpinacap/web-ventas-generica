import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)))
const distDir = join(frontendDir, 'dist')
const templatePath = join(distDir, 'index.html')
const serverEntry = join(frontendDir, '.prerender-server', 'entry-server.js')
const HEAD_START = '<!--prerender-head-start-->'
const HEAD_END = '<!--prerender-head-end-->'
const EMPTY_ROOT = '<div id="root"></div>'

function count(source, marker) {
  return source.split(marker).length - 1
}

function replaceControlled(source, start, end, replacement) {
  if (count(source, start) !== 1 || count(source, end) !== 1) throw new Error(`Marcadores inválidos: ${start} / ${end}`)
  const startIndex = source.indexOf(start) + start.length
  const endIndex = source.indexOf(end)
  if (endIndex < startIndex) throw new Error('Marcadores de head fuera de orden.')
  return `${source.slice(0, startIndex)}\n    ${replacement}\n    ${source.slice(endIndex)}`
}

function replaceRoot(source, route, rootHtml) {
  if (count(source, EMPTY_ROOT) !== 1) throw new Error('La plantilla debe contener exactamente un #root vacío controlado.')
  const escapedRoute = route.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
  return source.replace(EMPTY_ROOT, `<div id="root" data-prerendered="true" data-prerender-path="${escapedRoute}">${rootHtml}</div>`)
}

const template = await readFile(templatePath, 'utf8')
if (count(template, EMPTY_ROOT) !== 1) throw new Error('No existe exactamente un #root controlado.')
if (count(template, HEAD_START) !== 1 || count(template, HEAD_END) !== 1) throw new Error('La plantilla no contiene un bloque fallback único.')

process.env.NODE_ENV = 'production'
const server = await import(pathToFileURL(serverEntry).href)
const routes = server.PRERENDER_ROUTES
if (!Array.isArray(routes) || routes.length !== 10 || new Set(routes).size !== routes.length) throw new Error('Allowlist de prerender inválida.')

const noindexHead = '<title>JEM Nexus | Resultados filtrados</title>\n    <meta name="description" content="Explora resultados filtrados del catálogo de JEM Nexus." />\n    <meta name="robots" content="noindex,nofollow" data-jem-seo="true" />'
const stagingDir = join(frontendDir, '.prerender-output')
await rm(stagingDir, { recursive: true, force: true })
await mkdir(stagingDir, { recursive: true })

try {
  await writeFile(join(stagingDir, '_spa.html'), template, 'utf8')
  await writeFile(join(stagingDir, '_noindex.html'), replaceControlled(template, HEAD_START, HEAD_END, noindexHead), 'utf8')

  for (const route of routes) {
    const result = server.render(route)
    if (result.route !== route || !result.html?.trim() || !result.head?.trim() || !/<h1(?:\s|>)/i.test(result.html)) throw new Error(`Salida incompleta para ${route}.`)
    const outputParts = server.prerenderOutputParts(route)
    if (!Array.isArray(outputParts) || outputParts.some((part) => !/^[a-z0-9.-]+$/i.test(part) || part === '..')) throw new Error(`Destino inseguro para ${route}.`)
    const outputPath = join(stagingDir, ...outputParts)
    await mkdir(dirname(outputPath), { recursive: true })
    const withHead = replaceControlled(template, HEAD_START, HEAD_END, result.head)
    await writeFile(outputPath, replaceRoot(withHead, route, result.html), 'utf8')
  }

  for (const route of routes) {
    const parts = server.prerenderOutputParts(route)
    const sourcePath = join(stagingDir, ...parts)
    const destinationPath = join(distDir, ...parts)
    await mkdir(dirname(destinationPath), { recursive: true })
    await rm(destinationPath, { force: true })
    await rename(sourcePath, destinationPath)
  }
  for (const name of ['_spa.html', '_noindex.html']) {
    await rm(join(distDir, name), { force: true })
    await rename(join(stagingDir, name), join(distDir, name))
  }
} finally {
  await rm(stagingDir, { recursive: true, force: true })
}
