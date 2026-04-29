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
  const showSidebar = location.pathname.startsWith('/catalogo')

  return (
    <div className="app-shell">
      <Topbar />
      <div className={`app-shell__body ${showSidebar ? "" : "app-shell__body--full"}`.trim()}>
        <main className="main-content">{children}</main>
        {showSidebar ? <Sidebar /> : null}
      </div>
      <Footer />
    </div>
  )
}
