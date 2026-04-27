import { Navigate, Route, Routes } from 'react-router-dom'

import { CatalogPage } from '../pages/CatalogPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { ProductDetailPage } from '../pages/ProductDetailPage'
import { QuotePage } from '../pages/QuotePage'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/catalogo" element={<CatalogPage />} />
      <Route path="/producto/:slug" element={<ProductDetailPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/cotizar" element={<QuotePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
