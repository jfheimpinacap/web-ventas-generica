import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { AppRouter } from './router/AppRouter'
import { SystemDialogProvider } from './context/SystemDialogContext'
import './styles.css'
import { initializeGtm } from './utils/analytics'

initializeGtm()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <SystemDialogProvider><AppRouter /></SystemDialogProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
