import type { PropsWithChildren } from 'react'
import { useLocation } from 'react-router-dom'

import { Footer } from './Footer'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

interface LayoutProps extends PropsWithChildren {
  onSearch?: (term: string) => void
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const showSidebar = ['/catalogo', '/maquinaria-nueva', '/maquinaria-usada', '/repuestos', '/servicios'].includes(location.pathname)

  return (
    <div className="app-shell">
      <Topbar />
      <div className={`app-shell__body ${showSidebar ? "" : "app-shell__body--full"}`.trim()}>
        {showSidebar ? <Sidebar /> : null}
        <main id="main-content" className="main-content" tabIndex={-1}>{children}</main>
      </div>
      <Footer />
    </div>
  )
}
