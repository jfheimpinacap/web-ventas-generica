import React, { type ComponentType, type PropsWithChildren } from 'react'

import { SystemDialogProvider } from './context/SystemDialogContext'
import { AppRouter } from './router/AppRouter'

export function App({ Router, routerProps }: { Router: ComponentType<PropsWithChildren<any>>; routerProps?: Record<string, unknown> }) {
  return (
    <React.StrictMode>
      <Router {...routerProps}>
        <SystemDialogProvider><AppRouter /></SystemDialogProvider>
      </Router>
    </React.StrictMode>
  )
}
