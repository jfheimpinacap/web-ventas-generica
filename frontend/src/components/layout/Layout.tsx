import type { PropsWithChildren } from 'react'

import { Footer } from './Footer'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

interface LayoutProps extends PropsWithChildren {
  onSearch?: (term: string) => void
}

export function Layout({ children, onSearch }: LayoutProps) {
  return (
    <div className="app-shell">
      <Topbar />
      <div className="app-shell__body">
        <Sidebar onSearch={onSearch} />
        <main className="main-content">{children}</main>
      </div>
      <Footer />
    </div>
  )
}
