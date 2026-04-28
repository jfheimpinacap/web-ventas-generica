import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '../components/admin/ProtectedRoute'
import { AdminDashboardPage } from '../pages/admin/AdminDashboardPage'
import { AdminProductCreatePage } from '../pages/admin/AdminProductCreatePage'
import { AdminProductEditPage } from '../pages/admin/AdminProductEditPage'
import { AdminProductsPage } from '../pages/admin/AdminProductsPage'
import { AdminPromotionsPage } from '../pages/admin/AdminPromotionsPage'
import { AdminQuotesPage } from '../pages/admin/AdminQuotesPage'
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

      <Route element={<ProtectedRoute />}>
        <Route path="/admin" element={<AdminDashboardPage />} />
        <Route path="/admin/productos" element={<AdminProductsPage />} />
        <Route path="/admin/productos/nuevo" element={<AdminProductCreatePage />} />
        <Route path="/admin/productos/:slug/editar" element={<AdminProductEditPage />} />
        <Route path="/admin/cotizaciones" element={<AdminQuotesPage />} />
        <Route path="/admin/promociones" element={<AdminPromotionsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
