import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { ProductForm } from '../../components/admin/ProductForm'
import { createProduct } from '../../services/adminApi'
import { getBrands, getCategories, getSuppliers } from '../../services/catalogApi'
import type { Brand, Category, ProductFormValues, SupplierSummary } from '../../types/catalog'

const INITIAL_VALUES: ProductFormValues = {
  name: '',
  category: 0,
  brand: null,
  supplier: null,
  product_type: 'machinery',
  condition: 'new',
  short_description: '',
  description: '',
  model: '',
  sku: '',
  year: null,
  hours_meter: null,
  price: null,
  price_visible: true,
  stock_status: 'on_request',
  is_featured: false,
  is_published: false,
}

export function AdminProductCreatePage() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const [categoriesData, brandsData, suppliersData] = await Promise.all([
          getCategories(),
          getBrands(),
          getSuppliers(),
        ])
        setCategories(categoriesData)
        setBrands(brandsData)
        setSuppliers(suppliersData)
      } catch {
        setError('No fue posible cargar datos del formulario.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [])

  const handleSubmit = async (values: ProductFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      await createProduct(values)
      navigate('/admin/productos?status=created')
    } catch {
      setError('No se pudo crear el producto.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AdminLayout>
      <h1>Nuevo producto</h1>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}
      {!loading ? (
        <ProductForm
          initialValues={INITIAL_VALUES}
          categories={categories}
          brands={brands}
          suppliers={suppliers}
          onSubmit={handleSubmit}
          submitLabel="Crear producto"
          isSubmitting={isSubmitting}
          error={error}
        />
      ) : null}
    </AdminLayout>
  )
}
