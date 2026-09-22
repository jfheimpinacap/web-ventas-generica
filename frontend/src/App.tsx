import React, { type ComponentType, type PropsWithChildren } from 'react'

import { SystemDialogProvider } from './context/SystemDialogContext'
import { AppRouter } from './router/AppRouter'
import { ToastProvider } from './toasts/ToastContext'

export function App({ Router, routerProps }: { Router: ComponentType<PropsWithChildren<any>>; routerProps?: Record<string, unknown> }) {
  return (
    <React.StrictMode>
      <Router {...routerProps}>
        <ToastProvider><SystemDialogProvider><AppRouter /></SystemDialogProvider></ToastProvider>
      </Router>
    </React.StrictMode>
  )
}
