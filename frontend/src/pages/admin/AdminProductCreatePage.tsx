import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { ProductEditorLayout } from '../../components/admin/ProductEditorLayout'
import { ProductForm } from '../../components/admin/ProductForm'
import { createProduct, createProductImage } from '../../services/adminApi'
import { getAdminBrands, getAdminCategories, getAdminSuppliers } from '../../services/adminApi'
import type { Brand, Category, ProductFormValues, SupplierSummary } from '../../types/catalog'
import { formatCondition, formatPriceValue, formatStockStatus } from '../../utils/formatters'

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
  price_currency: 'CLP',
  price_tax_mode: 'plus_vat',
  price_visible: true,
  stock_status: 'on_request',
  is_featured: false,
  is_published: false,
}

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'

export function AdminProductCreatePage() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formValues, setFormValues] = useState<ProductFormValues>(INITIAL_VALUES)
  const [imageFile, setImageFile] = useState<File | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const [categoriesData, brandsData, suppliersData] = await Promise.all([
          getAdminCategories(),
          getAdminBrands(),
          getAdminSuppliers(),
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

  const localImagePreview = useMemo(() => {
    if (!imageFile) return null
    return URL.createObjectURL(imageFile)
  }, [imageFile])

  useEffect(() => {
    return () => {
      if (localImagePreview) URL.revokeObjectURL(localImagePreview)
    }
  }, [localImagePreview])

  const handleSubmit = async (values: ProductFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      const createdProduct = await createProduct(values)
      if (imageFile) {
        try {
          await createProductImage({
            product: createdProduct.id,
            image: imageFile,
            alt_text: values.name,
            order: 0,
            is_main: true,
          })
        } catch {
          navigate(`/admin/productos/${createdProduct.slug}/editar`, {
            state: {
              imageError: 'El producto fue creado, pero la imagen no pudo cargarse. Puedes reintentar la carga desde esta sección.',
            },
          })
          return
        }
      }
      navigate('/admin/productos?status=created')
    } catch {
      setError('No se pudo crear el producto.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const previewCategoryName = categories.find((item) => item.id === formValues.category)?.name ?? 'Sin categoría'
  const previewBrandName = brands.find((item) => item.id === formValues.brand)?.name ?? 'Sin marca'

  return (
    <AdminLayout>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}
      {!loading ? (
        <ProductEditorLayout
          title="Nuevo producto"
          onBack={() => navigate('/admin/productos')}
          form={
            <ProductForm
              initialValues={INITIAL_VALUES}
              categories={categories}
              brands={brands}
              suppliers={suppliers}
              onSubmit={handleSubmit}
              submitLabel="Crear producto"
              isSubmitting={isSubmitting}
              error={error}
              onValuesChange={setFormValues}
              beforeActions={
                <section className="admin-form-panel admin-form-panel--media" aria-busy={isSubmitting}>
                  <h3>Imágenes</h3>
                  <p className="ui-note admin-form-panel__full">Selecciona una imagen principal opcional. Se cargará automáticamente después de crear el producto.</p>
                  <label className="admin-image-upload-field admin-form-panel__full">
                    Archivo
                    <input key={imageFile?.name ?? "empty"} type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] ?? null)} disabled={isSubmitting} />
                  </label>
                  {imageFile ? (
                    <div className="admin-mini-preview admin-form-panel__full">
                      <span>Archivo seleccionado: {imageFile.name}</span>
                      <img src={localImagePreview || PLACEHOLDER_IMAGE} alt={formValues.name || imageFile.name} />
                      <button type="button" className="btn btn--ghost" onClick={() => setImageFile(null)} disabled={isSubmitting}>
                        Quitar selección
                      </button>
                    </div>
                  ) : null}
                </section>
              }
            />
          }
          sidebar={
            <section className="admin-block admin-block--compact admin-product-preview">
              <h2>Vista previa pública</h2>
                <article className="product-card admin-product-preview-card">
                  <img src={localImagePreview || PLACEHOLDER_IMAGE} alt={formValues.name || 'Producto'} />
                  <div className="product-card__content">
                    <div className="product-card__badges">
                      <span className="badge badge--condition">{formatCondition(formValues.condition)}</span>
                      <span className="badge badge--stock">{formatStockStatus(formValues.stock_status)}</span>
                    </div>
                    <h3>{formValues.name || 'Producto sin nombre'}</h3>
                    <p className="product-card__meta">
                      <strong>Marca:</strong> {previewBrandName}
                    </p>
                    <p className="product-card__meta">
                      <strong>Categoría:</strong> {previewCategoryName}
                    </p>
                    <p className="product-card__meta">
                      <strong>Condición:</strong> {formatCondition(formValues.condition)}
                    </p>
                    <p className="product-card__meta">
                      <strong>Stock:</strong> {formatStockStatus(formValues.stock_status)}
                    </p>
                    <p className="product-card__price">{formatPriceValue(formValues.price, formValues.price_visible, formValues.price_currency, formValues.price_tax_mode)}</p>
                  </div>
                  <div className="product-card__actions">
                    <button type="button" className="btn btn--accent" disabled>
                      Ver detalle
                    </button>
                  </div>
                </article>
            </section>
          }
        />
      ) : null}
    </AdminLayout>
  )
}
