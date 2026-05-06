import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '../components/admin/ProtectedRoute'
import { CatalogPage } from '../pages/CatalogPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { ProductDetailPage } from '../pages/ProductDetailPage'
import { QuotePage } from '../pages/QuotePage'
import { AdminBrandFormPage } from '../pages/admin/AdminBrandFormPage'
import { AdminBrandsPage } from '../pages/admin/AdminBrandsPage'
import { AdminCategoriesPage } from '../pages/admin/AdminCategoriesPage'
import { AdminCategoryFormPage } from '../pages/admin/AdminCategoryFormPage'
import { AdminProductCreatePage } from '../pages/admin/AdminProductCreatePage'
import { AdminProductEditPage } from '../pages/admin/AdminProductEditPage'
import { AdminProductsPage } from '../pages/admin/AdminProductsPage'
import { AdminHomeSectionsPage } from '../pages/admin/AdminHomeSectionsPage'
import { AdminPromotionFormPage } from '../pages/admin/AdminPromotionFormPage'
import { AdminPromotionsPage } from '../pages/admin/AdminPromotionsPage'
import { AdminQuoteDetailPage } from '../pages/admin/AdminQuoteDetailPage'
import { AdminQuotesPage } from '../pages/admin/AdminQuotesPage'
import { AdminSupplierFormPage } from '../pages/admin/AdminSupplierFormPage'
import { AdminSuppliersPage } from '../pages/admin/AdminSuppliersPage'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/catalogo" element={<CatalogPage />} />
      <Route path="/producto/:slug" element={<ProductDetailPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/cotizar" element={<QuotePage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/admin" element={<Navigate to="/admin/productos" replace />} />
        <Route path="/admin/productos" element={<AdminProductsPage />} />
        <Route path="/admin/productos/nuevo" element={<AdminProductCreatePage />} />
        <Route path="/admin/productos/:slug/editar" element={<AdminProductEditPage />} />
        <Route path="/admin/categorias" element={<AdminCategoriesPage />} />
        <Route path="/admin/categorias/nueva" element={<AdminCategoryFormPage />} />
        <Route path="/admin/categorias/:id/editar" element={<AdminCategoryFormPage />} />
        <Route path="/admin/marcas" element={<AdminBrandsPage />} />
        <Route path="/admin/marcas/nueva" element={<AdminBrandFormPage />} />
        <Route path="/admin/marcas/:id/editar" element={<AdminBrandFormPage />} />
        <Route path="/admin/proveedores" element={<AdminSuppliersPage />} />
        <Route path="/admin/proveedores/nuevo" element={<AdminSupplierFormPage />} />
        <Route path="/admin/proveedores/:id/editar" element={<AdminSupplierFormPage />} />
        <Route path="/admin/cotizaciones" element={<AdminQuotesPage />} />
        <Route path="/admin/cotizaciones/:id" element={<AdminQuoteDetailPage />} />
        <Route path="/admin/promociones" element={<AdminHomeSectionsPage />} />
        <Route path="/admin/home-secciones" element={<Navigate to="/admin/promociones" replace />} />
        <Route path="/admin/ofertas-hero" element={<AdminPromotionsPage />} />
        <Route path="/admin/ofertas-hero/nueva" element={<AdminPromotionFormPage />} />
        <Route path="/admin/ofertas-hero/:id/editar" element={<AdminPromotionFormPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
