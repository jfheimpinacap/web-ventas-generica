import { createRoot, hydrateRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { App } from './App'
import { isPrerenderRoute, normalizePrerenderPath } from './config/prerenderRoutes'
import './styles.css'
import { initializeGtm } from './utils/analytics'

initializeGtm()

const root = document.getElementById('root')
if (!root) throw new Error('No se encontró #root.')

const pathname = normalizePrerenderPath(window.location.pathname)
const markedPath = root.dataset.prerenderPath
const canHydrate = root.dataset.prerendered === 'true'
  && markedPath === pathname
  && isPrerenderRoute(pathname)
  && window.location.search === ''
  && window.location.hash === ''
const app = <App Router={BrowserRouter} />

if (canHydrate) hydrateRoot(root, app)
else {
  root.replaceChildren()
  root.removeAttribute('data-prerendered')
  root.removeAttribute('data-prerender-path')
  createRoot(root).render(app)
}
