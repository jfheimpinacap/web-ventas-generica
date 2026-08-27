import type { PropsWithChildren } from 'react'
import { useLocation } from 'react-router-dom'

import { Footer } from './Footer'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { MobileConversionBar } from './MobileConversionBar'

interface LayoutProps extends PropsWithChildren {
  onSearch?: (term: string) => void
  mobileProduct?: { id: number; name: string; product_type: string } | null
  suppressMobileConversion?: boolean
}

export function Layout({ children, mobileProduct, suppressMobileConversion = false }: LayoutProps) {
  const location = useLocation()
  const showSidebar = ['/catalogo', '/maquinaria-nueva', '/maquinaria-usada', '/repuestos', '/servicios'].includes(location.pathname)
  const generalRoutes = ['/', '/catalogo', '/maquinaria-nueva', '/maquinaria-usada', '/repuestos', '/servicios', '/sobre-nosotros', '/preguntas-frecuentes']
  const showMobileConversion = !suppressMobileConversion && (generalRoutes.includes(location.pathname) || (location.pathname.startsWith('/producto/') && Boolean(mobileProduct)))

  return (
    <div className={`app-shell${showMobileConversion ? ' app-shell--mobile-conversion' : ''}`}>
      <Topbar />
      <div className={`app-shell__body ${showSidebar ? "" : "app-shell__body--full"}`.trim()}>
        {showSidebar ? <Sidebar /> : null}
        <main id="main-content" className="main-content" tabIndex={-1}>{children}</main>
      </div>
      <Footer />
      {showMobileConversion ? <MobileConversionBar product={mobileProduct ?? undefined} /> : null}
    </div>
  )
}
