import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '../components/admin/ProtectedRoute'
import { AboutPage } from '../pages/AboutPage'
import { ApiDiagnostics } from '../pages/ApiDiagnostics'
import { CatalogPage, type CommercialCatalogConfig } from '../pages/CatalogPage'
import { ContactPage } from '../pages/ContactPage'
import { FaqPage } from '../pages/FaqPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
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
import { CommercialQuoteEditorPage } from '../pages/admin/CommercialQuoteEditorPage'
import { AdminSupplierFormPage } from '../pages/admin/AdminSupplierFormPage'
import { AdminSuppliersPage } from '../pages/admin/AdminSuppliersPage'
import { AdminTechnicalSheetsPage } from '../pages/admin/AdminTechnicalSheetsPage'
import { AdminUsersPage } from '../pages/admin/AdminUsersPage'
import { AdminUserCreatePage } from '../pages/admin/AdminUserCreatePage'
import { AdminUserEditPage } from '../pages/admin/AdminUserEditPage'
import { AdminCustomersPage } from '../pages/admin/AdminCustomersPage'
import { AdminCustomerFormPage } from '../pages/admin/AdminCustomerFormPage'

const newMachineryConfig: CommercialCatalogConfig = {
  title: 'Maquinaria nueva',
  description: 'Revisa equipos publicados como nuevos, consulta su información técnica y prepara una solicitud de cotización.',
  canonicalPath: '/maquinaria-nueva',
  fixedProductType: 'machinery',
  fixedCondition: 'new',
}

const usedMachineryConfig: CommercialCatalogConfig = {
  title: 'Maquinaria usada',
  description: 'Compara los equipos publicados como usados y revisa los antecedentes disponibles antes de solicitar una cotización.',
  canonicalPath: '/maquinaria-usada',
  fixedProductType: 'machinery',
  fixedCondition: 'used',
}

const sparePartsConfig: CommercialCatalogConfig = {
  title: 'Repuestos',
  description: 'Encuentra repuestos publicados y revisa sus datos antes de enviar una consulta o solicitud de cotización.',
  canonicalPath: '/repuestos', fixedProductType: 'spare_part',
}

const servicesConfig: CommercialCatalogConfig = {
  title: 'Servicios',
  description: 'Revisa los servicios publicados de reparación o mantención y consulta la información de cada ficha.',
  canonicalPath: '/servicios', fixedProductType: 'service',
}

export function AppRouter() {
  return (
    <>
      <a className="skip-link" href="#main-content">Saltar al contenido</a>
      <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/catalogo" element={<CatalogPage />} />
      <Route path="/maquinaria-nueva" element={<CatalogPage commercialConfig={newMachineryConfig} />} />
      <Route path="/maquinaria-usada" element={<CatalogPage commercialConfig={usedMachineryConfig} />} />
      <Route path="/repuestos" element={<CatalogPage commercialConfig={sparePartsConfig} />} />
      <Route path="/servicios" element={<CatalogPage commercialConfig={servicesConfig} />} />
      <Route path="/producto/:slug" element={<ProductDetailPage />} />
      <Route path="/login" element={<LoginPage />} />
      {import.meta.env.DEV ? <Route path="/diagnostico-api" element={<ApiDiagnostics />} /> : null}
      <Route path="/cotizar" element={<QuotePage />} />
      <Route path="/contacto" element={<ContactPage />} />
      <Route path="/sobre-nosotros" element={<AboutPage />} />
      <Route path="/preguntas-frecuentes" element={<FaqPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/admin" element={<Navigate to="/admin/productos" replace />} />
        <Route path="/admin/productos" element={<AdminProductsPage />} />
        <Route path="/admin/fichas-tecnicas" element={<AdminTechnicalSheetsPage />} />
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
        <Route path="/admin/clientes" element={<AdminCustomersPage />} />
        <Route path="/admin/clientes/nuevo" element={<AdminCustomerFormPage />} />
        <Route path="/admin/clientes/:id/editar" element={<AdminCustomerFormPage />} />
        <Route path="/admin/cotizaciones" element={<AdminQuotesPage />} />
        <Route path="/admin/cotizaciones-comerciales" element={<Navigate to="/admin/cotizaciones?vista=generadas" replace />} />
        <Route path="/admin/cotizaciones/nueva" element={<CommercialQuoteEditorPage />} />
        <Route path="/admin/cotizaciones/:id/editar" element={<CommercialQuoteEditorPage />} />
        <Route path="/admin/cotizaciones/:id" element={<AdminQuoteDetailPage />} />
        <Route path="/admin/promociones" element={<AdminHomeSectionsPage />} />
        <Route path="/admin/home-secciones" element={<Navigate to="/admin/promociones" replace />} />
        <Route path="/admin/ofertas-hero" element={<AdminPromotionsPage />} />
        <Route path="/admin/ofertas-hero/nueva" element={<AdminPromotionFormPage />} />
        <Route path="/admin/ofertas-hero/:id/editar" element={<AdminPromotionFormPage />} />
      </Route>
      <Route element={<ProtectedRoute supportAdminOnly />}>
        <Route path="/admin/usuarios" element={<AdminUsersPage />} />
        <Route path="/admin/usuarios/nuevo" element={<AdminUserCreatePage />} />
        <Route path="/admin/usuarios/:userId/editar" element={<AdminUserEditPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  )
}
