import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { ProductForm } from '../../components/admin/ProductForm'
import { getAdminProduct, updateProduct } from '../../services/adminApi'
import { getBrands, getCategories, getSuppliers } from '../../services/catalogApi'
import type { Brand, Category, ProductFormValues, SupplierSummary } from '../../types/catalog'

function mapProductToFormValues(product: Awaited<ReturnType<typeof getAdminProduct>>): ProductFormValues {
  return {
    name: product.name,
    category: product.category.id,
    brand: product.brand?.id ?? null,
    supplier: product.supplier?.id ?? null,
    product_type: product.product_type,
    condition: product.condition,
    short_description: product.short_description,
    description: product.description,
    model: product.model,
    sku: product.sku,
    year: product.year,
    hours_meter: product.hours_meter,
    price: product.price,
    price_visible: product.price_visible,
    stock_status: product.stock_status,
    is_featured: product.is_featured,
    is_published: product.is_published,
  }
}

export function AdminProductEditPage() {
  const navigate = useNavigate()
  const { slug } = useParams<{ slug: string }>()
  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([])
  const [initialValues, setInitialValues] = useState<ProductFormValues | null>(null)
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!slug) {
      setError('Producto no encontrado.')
      setLoading(false)
      return
    }

    const load = async () => {
      try {
        setError(null)
        const [product, categoriesData, brandsData, suppliersData] = await Promise.all([
          getAdminProduct(slug),
          getCategories(),
          getBrands(),
          getSuppliers(),
        ])
        setInitialValues(mapProductToFormValues(product))
        setCategories(categoriesData)
        setBrands(brandsData)
        setSuppliers(suppliersData)
      } catch {
        setError('No fue posible cargar el producto para edición.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [slug])

  const handleSubmit = async (values: ProductFormValues) => {
    if (!slug) return

    try {
      setIsSubmitting(true)
      setError(null)
      await updateProduct(slug, values)
      navigate('/admin/productos?status=updated')
    } catch {
      setError('No se pudo actualizar el producto.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AdminLayout>
      <h1>Editar producto</h1>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}
      {!loading && initialValues ? (
        <ProductForm
          initialValues={initialValues}
          categories={categories}
          brands={brands}
          suppliers={suppliers}
          onSubmit={handleSubmit}
          submitLabel="Guardar cambios"
          isSubmitting={isSubmitting}
          error={error}
        />
      ) : null}
      {!loading && !initialValues && error ? <p className="ui-note ui-note--error">{error}</p> : null}
    </AdminLayout>
  )
}
