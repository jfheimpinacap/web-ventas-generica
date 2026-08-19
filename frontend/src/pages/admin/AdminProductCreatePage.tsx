import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { ProductEditorLayout } from '../../components/admin/ProductEditorLayout'
import { ProductForm } from '../../components/admin/ProductForm'
import { ProductImageManager } from '../../components/admin/ProductImageManager'
import { ProductAdminPreview } from '../../components/admin/ProductAdminPreview'
import { usePendingProductImages } from '../../hooks/usePendingProductImages'
import { createProduct, createProductImage, getTechnicalSheets } from '../../services/adminApi'
import { getAdminBrands, getAdminCategories, getAdminSuppliers } from '../../services/adminApi'
import { getSafeApiErrorMessage } from '../../services/api'
import type { Brand, Category, ProductFormValues, SupplierSummary, TechnicalSheet } from '../../types/catalog'

const INITIAL_VALUES: ProductFormValues = {
  name: '',
  category: 0,
  brand: null,
  supplier: null,
  technical_sheet: null,
  product_type: 'machinery',
  condition: 'new',
  short_description: '',
  description: '',
  model: '',
  sku: '',
  working_height_m: null,
  terrain_type: null,
  year: null,
  hours_meter: null,
  maximum_load_capacity_kg: null,
  machine_weight_kg: null,
  power_source: null,
  includes_technical_review: true,
  includes_commercial_technical_advice: true,
  includes_coordinated_delivery: true,
  price: null,
  price_currency: 'CLP',
  price_tax_mode: 'plus_vat',
  price_visible: true,
  stock_status: 'on_request',
  is_featured: false,
  is_published: false,
}

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'
const PRODUCT_CREATE_FORM_ID = 'admin-product-create-form'

export function AdminProductCreatePage() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([])
  const [technicalSheets, setTechnicalSheets] = useState<TechnicalSheet[]>([])
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formValues, setFormValues] = useState<ProductFormValues>(INITIAL_VALUES)
  const pending = usePendingProductImages()
  const [selectedPendingId, setSelectedPendingId] = useState<string | null>(null)
  const [imageStatus, setImageStatus] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setError(null)
        const [categoriesData, brandsData, suppliersData, technicalSheetsData] = await Promise.all([
          getAdminCategories(),
          getAdminBrands(),
          getAdminSuppliers(),
          getTechnicalSheets(),
        ])
        setCategories(categoriesData)
        setBrands(brandsData)
        setSuppliers(suppliersData)
        setTechnicalSheets(technicalSheetsData)
      } catch {
        setError('No fue posible cargar datos del formulario.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [])

  useEffect(() => {
    if (pending.images.length > 0 && !pending.images.some((image) => image.id === selectedPendingId)) {
      setSelectedPendingId(pending.images[0].id)
    } else if (pending.images.length === 0 && selectedPendingId) {
      setSelectedPendingId(null)
    }
  }, [pending.images, selectedPendingId])

  const handleSubmit = async (values: ProductFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      const createdProduct = await createProduct(values)
      const queuedImages = pending.images
      let uploaded = 0
      for (let index = 0; index < queuedImages.length; index += 1) {
        const image = queuedImages[index]
        pending.updateImage(image.id, { status: 'uploading', error: null })
        setImageStatus(`Subiendo ${index + 1} de ${queuedImages.length} imágenes…`)
        try {
          await createProductImage({
            product: createdProduct.id,
            image: image.file,
            alt_text: image.altText.trim() || values.name.trim(),
            is_main: image.id === selectedPendingId,
          })
          uploaded += 1
          pending.updateImage(image.id, { status: 'pending', error: null })
        } catch (uploadError) {
          pending.updateImage(image.id, { status: 'error', error: getSafeApiErrorMessage(uploadError, 'No se pudo cargar esta imagen.') })
        }
      }
      if (uploaded < queuedImages.length) {
        const failed = queuedImages.length - uploaded
        navigate(`/admin/productos/${createdProduct.slug}/editar`, { state: { imageError: `El producto fue creado. Se cargaron ${uploaded} de ${queuedImages.length} imágenes; ${failed} no ${failed === 1 ? 'pudo' : 'pudieron'} cargarse. Puedes volver a seleccionarlas y reintentar desde esta sección.` } })
        return
      }
      pending.clearImages()
      navigate('/admin/productos?status=created')
    } catch (submitError) {
      setError(getSafeApiErrorMessage(submitError, 'No se pudo crear el producto.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const selectedPending = pending.images.find((image) => image.id === selectedPendingId) ?? pending.images[0] ?? null

  return (
    <AdminLayout>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}
      {!loading ? (
        <ProductEditorLayout
          title="Nuevo producto"
          onBack={() => navigate('/admin/productos')}
          formId={PRODUCT_CREATE_FORM_ID}
          isSubmitting={isSubmitting}
          showHeaderActions={false}
          form={
            <ProductForm
              formId={PRODUCT_CREATE_FORM_ID}
              onCancel={() => navigate('/admin/productos')}
              initialValues={INITIAL_VALUES}
              categories={categories}
              brands={brands}
              suppliers={suppliers}
              technicalSheets={technicalSheets}
              onSubmit={handleSubmit}
              isSubmitting={isSubmitting}
              error={error}
              onValuesChange={setFormValues}
              beforeActions={
                <ProductImageManager pendingImages={pending.images} selectedPendingId={selectedPendingId} disabled={isSubmitting} status={imageStatus} error={pending.selectionError} onAddFiles={pending.addFiles} onAltTextChange={(id, altText) => pending.updateImage(id, { altText })} onSelectPending={setSelectedPendingId} onRemovePending={pending.removeImage} />
              }
            />
          }
          sidebar={
            <section className="admin-block admin-block--compact admin-product-preview">
              <h2>Vista previa pública</h2>
                <ProductAdminPreview values={formValues} categories={categories} imageUrl={selectedPending?.previewUrl || PLACEHOLDER_IMAGE} imageAlt={selectedPending?.altText.trim() || formValues.name || 'Producto'} />
            </section>
          }
        />
      ) : null}
    </AdminLayout>
  )
}
