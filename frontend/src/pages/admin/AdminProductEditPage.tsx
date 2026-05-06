import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { ProductEditorLayout } from '../../components/admin/ProductEditorLayout'
import { ProductForm } from '../../components/admin/ProductForm'
import {
  createProductImage,
  createProductSpec,
  deleteProductImage,
  deleteProductSpec,
  getAdminProduct,
  getProductImages,
  getProductSpecs,
  updateProduct,
  updateProductImage,
  updateProductSpec,
} from '../../services/adminApi'
import { resolveMediaUrl } from '../../services/api'
import { getBrands, getCategories, getSuppliers } from '../../services/catalogApi'
import type {
  Brand,
  Category,
  ProductFormValues,
  ProductImage,
  ProductImageWritePayload,
  ProductSpec,
  ProductSpecWritePayload,
  SupplierSummary,
} from '../../types/catalog'
import { formatCondition, formatStockStatus } from '../../utils/formatters'

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

const initialSpecForm = {
  name: '',
  value: '',
  unit: '',
  order: 0,
}

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'

function formatPreviewPrice(price: string | null, priceVisible: boolean) {
  if (!priceVisible || !price) return 'Consultar'
  const amount = Number(price)
  if (Number.isNaN(amount)) return 'Consultar'

  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function AdminProductEditPage() {
  const navigate = useNavigate()
  const { slug } = useParams<{ slug: string }>()
  const [productId, setProductId] = useState<number | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [brands, setBrands] = useState<Brand[]>([])
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([])
  const [initialValues, setInitialValues] = useState<ProductFormValues | null>(null)
  const [formValues, setFormValues] = useState<ProductFormValues | null>(null)

  const [images, setImages] = useState<ProductImage[]>([])
  const [specs, setSpecs] = useState<ProductSpec[]>([])
  const [loading, setLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imageAltText, setImageAltText] = useState('')
  const [imageSaving, setImageSaving] = useState(false)
  const [imageStatus, setImageStatus] = useState<string | null>(null)
  const [imageError, setImageError] = useState<string | null>(null)

  const [specForm, setSpecForm] = useState(initialSpecForm)
  const [specSaving, setSpecSaving] = useState(false)
  const [specStatus, setSpecStatus] = useState<string | null>(null)
  const [specError, setSpecError] = useState<string | null>(null)

  const sortedImages = useMemo(() => [...images].sort((a, b) => a.order - b.order || a.id - b.id), [images])
  const sortedSpecs = useMemo(() => [...specs].sort((a, b) => a.order - b.order || a.id - b.id), [specs])
  const mainImage = useMemo(() => sortedImages.find((image) => image.is_main) ?? sortedImages[0] ?? null, [sortedImages])

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

        const [imagesData, specsData] = await Promise.all([getProductImages(product.id), getProductSpecs(product.id)])

        const mappedValues = mapProductToFormValues(product)
        setInitialValues(mappedValues)
        setFormValues(mappedValues)
        setProductId(product.id)
        setCategories(categoriesData)
        setBrands(brandsData)
        setSuppliers(suppliersData)
        setImages(imagesData)
        setSpecs(specsData)
      } catch {
        setError('No fue posible cargar el producto para edición.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [slug])

  const refreshMediaData = async (nextProductId: number) => {
    const [imagesData, specsData] = await Promise.all([getProductImages(nextProductId), getProductSpecs(nextProductId)])
    setImages(imagesData)
    setSpecs(specsData)
  }

  const handleSubmit = async (values: ProductFormValues) => {
    if (!slug) return

    try {
      setIsSubmitting(true)
      setError(null)
      await updateProduct(slug, values)
    } catch {
      setError('No se pudo actualizar el producto.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCreateImage = async (event: FormEvent) => {
    event.preventDefault()
    if (!productId || !imageFile) {
      setImageError('Debes seleccionar un archivo de imagen.')
      return
    }

    try {
      setImageSaving(true)
      setImageError(null)
      setImageStatus(null)
      await createProductImage({
        product: productId,
        image: imageFile,
        alt_text: imageAltText.trim(),
        order: sortedImages.length,
        is_main: sortedImages.length === 0,
      })
      await refreshMediaData(productId)
      setImageFile(null)
      setImageAltText('')
      setImageStatus('Imagen agregada correctamente.')
    } catch {
      setImageError('No se pudo guardar la imagen.')
    } finally {
      setImageSaving(false)
    }
  }

  const handleSetMainImage = async (imageId: number) => {
    if (!productId) return
    try {
      setImageSaving(true)
      setImageError(null)
      setImageStatus(null)
      await updateProductImage(imageId, { is_main: true })
      await refreshMediaData(productId)
      setImageStatus('Imagen principal actualizada.')
    } catch {
      setImageError('No se pudo actualizar la imagen principal.')
    } finally {
      setImageSaving(false)
    }
  }


  const handleUpdateImage = async (imageId: number, payload: Partial<ProductImageWritePayload>) => {
    if (!productId) return

    try {
      setImageSaving(true)
      setImageError(null)
      setImageStatus(null)
      await updateProductImage(imageId, payload)
      await refreshMediaData(productId)
      setImageStatus('Imagen actualizada.')
    } catch {
      setImageError('No se pudo actualizar la imagen.')
    } finally {
      setImageSaving(false)
    }
  }

  const handleDeleteImage = async (imageId: number) => {
    if (!productId) return
    if (!window.confirm('¿Eliminar esta imagen?')) return

    try {
      setImageSaving(true)
      setImageError(null)
      setImageStatus(null)
      await deleteProductImage(imageId)
      await refreshMediaData(productId)
      setImageStatus('Imagen eliminada.')
    } catch {
      setImageError('No se pudo eliminar la imagen.')
    } finally {
      setImageSaving(false)
    }
  }

  const handleCreateSpec = async (event: FormEvent) => {
    event.preventDefault()
    if (!productId) return

    try {
      setSpecSaving(true)
      setSpecError(null)
      setSpecStatus(null)
      await createProductSpec({
        product: productId,
        name: specForm.name,
        value: specForm.value,
        unit: specForm.unit,
        order: specForm.order,
      })
      await refreshMediaData(productId)
      setSpecForm(initialSpecForm)
      setSpecStatus('Especificación agregada.')
    } catch {
      setSpecError('No se pudo crear la especificación.')
    } finally {
      setSpecSaving(false)
    }
  }

  const handleUpdateSpec = async (specId: number, payload: Partial<ProductSpecWritePayload>) => {
    if (!productId) return

    try {
      setSpecSaving(true)
      setSpecError(null)
      setSpecStatus(null)
      await updateProductSpec(specId, payload)
      await refreshMediaData(productId)
      setSpecStatus('Especificación actualizada.')
    } catch {
      setSpecError('No se pudo actualizar la especificación.')
    } finally {
      setSpecSaving(false)
    }
  }

  const handleDeleteSpec = async (specId: number) => {
    if (!productId) return
    if (!window.confirm('¿Eliminar esta especificación?')) return

    try {
      setSpecSaving(true)
      setSpecError(null)
      setSpecStatus(null)
      await deleteProductSpec(specId)
      await refreshMediaData(productId)
      setSpecStatus('Especificación eliminada.')
    } catch {
      setSpecError('No se pudo eliminar la especificación.')
    } finally {
      setSpecSaving(false)
    }
  }

  const previewValues = formValues ?? initialValues
  const previewCategoryName = categories.find((item) => item.id === previewValues?.category)?.name ?? 'Sin categoría'
  const previewBrandName = brands.find((item) => item.id === previewValues?.brand)?.name ?? 'Sin marca'

  return (
    <AdminLayout>
      {loading ? <p className="ui-note">Cargando formulario...</p> : null}

      {!loading && initialValues ? (
        <ProductEditorLayout
          title="Editar producto"
          onBack={() => navigate('/admin/productos')}
          form={
            <ProductForm
              initialValues={initialValues}
              categories={categories}
              brands={brands}
              suppliers={suppliers}
              onSubmit={handleSubmit}
              submitLabel="Guardar cambios"
              isSubmitting={isSubmitting}
              error={error}
              onValuesChange={setFormValues}
            />
          }
          sidebar={
            <>
              <section className="admin-block admin-block--compact">
                <h2>Imagen principal</h2>
                {imageError ? <p className="ui-note ui-note--error">{imageError}</p> : null}
                {imageStatus ? <p className="ui-note ui-note--success">{imageStatus}</p> : null}

                <form className="admin-image-upload-form" onSubmit={handleCreateImage}>
                  <label className="admin-image-upload-field">
                    Archivo
                    <input type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] ?? null)} required />
                  </label>
                  <label className="admin-image-upload-field">
                    Texto alternativo
                    <input value={imageAltText} onChange={(e) => setImageAltText(e.target.value)} placeholder={previewValues?.name || 'Imagen de producto'} />
                  </label>
                  <button type="submit" className="btn btn--accent" disabled={imageSaving}>
                    {imageSaving ? 'Guardando...' : 'Subir imagen'}
                  </button>
                </form>
              </section>

              <section className="admin-block admin-block--compact">
                <h2>Vista previa pública</h2>
                <article className="product-card admin-product-preview-card">
                  <img src={resolveMediaUrl(mainImage?.image) || PLACEHOLDER_IMAGE} alt={mainImage?.alt_text || previewValues?.name || 'Producto'} />
                  <div className="product-card__content">
                    <div className="product-card__badges">
                      <span className="badge badge--condition">{formatCondition(previewValues?.condition ?? initialValues.condition)}</span>
                      <span className="badge badge--stock">{formatStockStatus(previewValues?.stock_status ?? initialValues.stock_status)}</span>
                    </div>
                    <h3>{previewValues?.name || 'Producto sin nombre'}</h3>
                    <p className="product-card__meta">
                      <strong>Marca:</strong> {previewBrandName}
                    </p>
                    <p className="product-card__meta">
                      <strong>Categoría:</strong> {previewCategoryName}
                    </p>
                    <p className="product-card__meta">
                      <strong>Condición:</strong> {formatCondition(previewValues?.condition ?? initialValues.condition)}
                    </p>
                    <p className="product-card__meta">
                      <strong>Stock:</strong> {formatStockStatus(previewValues?.stock_status ?? initialValues.stock_status)}
                    </p>
                    <p className="product-card__price">
                      {formatPreviewPrice(previewValues?.price ?? initialValues.price, previewValues?.price_visible ?? initialValues.price_visible)}
                    </p>
                  </div>
                  <div className="product-card__actions">
                    <button type="button" className="btn btn--accent" disabled>
                      Ver detalle
                    </button>
                  </div>
                </article>
              </section>
            </>
          }
        />
      ) : null}

      {!loading && productId ? (
        <section className="admin-block admin-block--compact">
          <h2>Galería de imágenes</h2>
          {sortedImages.length === 0 ? (
            <p className="ui-note">Aún no hay imágenes para este producto.</p>
          ) : (
            <div className="admin-image-mini-list">
              {sortedImages.map((image) => (
                <article key={image.id} className="admin-image-mini-item">
                  <img src={resolveMediaUrl(image.image)} alt={image.alt_text || 'Imagen de producto'} />
                  <div className="admin-image-mini-item__content">
                    <label>
                      Texto alternativo
                      <input
                        value={image.alt_text}
                        onChange={(e) =>
                          setImages((prev) => prev.map((item) => (item.id === image.id ? { ...item, alt_text: e.target.value } : item)))
                        }
                      />
                    </label>
                    <label>
                      Orden
                      <input
                        type="number"
                        min={0}
                        value={image.order}
                        onChange={(e) =>
                          setImages((prev) =>
                            prev.map((item) => (item.id === image.id ? { ...item, order: Number(e.target.value) || 0 } : item)),
                          )
                        }
                      />
                    </label>
                    <div className="admin-media-item__actions">
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() => handleSetMainImage(image.id)}
                        disabled={imageSaving || image.is_main}
                      >
                        {image.is_main ? 'Principal' : 'Marcar principal'}
                      </button>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() => handleUpdateImage(image.id, { alt_text: image.alt_text, order: image.order })}
                        disabled={imageSaving}
                      >
                        Guardar
                      </button>
                      <button type="button" className="btn btn--ghost" onClick={() => handleDeleteImage(image.id)} disabled={imageSaving}>
                        Eliminar
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {!loading && productId ? (
        <section className="admin-block admin-block--compact">
          <h2>Especificaciones técnicas</h2>
          {specError ? <p className="ui-note ui-note--error">{specError}</p> : null}
          {specStatus ? <p className="ui-note ui-note--success">{specStatus}</p> : null}

          <form className="admin-inline-form admin-inline-form--compact" onSubmit={handleCreateSpec}>
            <label>
              Nombre
              <input
                value={specForm.name}
                onChange={(e) => setSpecForm((prev) => ({ ...prev, name: e.target.value }))}
                required
              />
            </label>
            <label>
              Valor
              <input
                value={specForm.value}
                onChange={(e) => setSpecForm((prev) => ({ ...prev, value: e.target.value }))}
                required
              />
            </label>
            <label>
              Unidad
              <input value={specForm.unit} onChange={(e) => setSpecForm((prev) => ({ ...prev, unit: e.target.value }))} />
            </label>
            <label>
              Orden
              <input
                type="number"
                value={specForm.order}
                onChange={(e) => setSpecForm((prev) => ({ ...prev, order: Number(e.target.value) || 0 }))}
                min={0}
              />
            </label>
            <button type="submit" className="btn btn--accent" disabled={specSaving}>
              {specSaving ? 'Guardando...' : 'Agregar spec'}
            </button>
          </form>

          {sortedSpecs.length === 0 ? (
            <p className="ui-note">Este producto no tiene especificaciones aún.</p>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Valor</th>
                    <th>Unidad</th>
                    <th>Orden</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedSpecs.map((spec) => (
                    <tr key={spec.id}>
                      <td>
                        <input
                          value={spec.name}
                          onChange={(e) =>
                            setSpecs((prev) => prev.map((item) => (item.id === spec.id ? { ...item, name: e.target.value } : item)))
                          }
                        />
                      </td>
                      <td>
                        <input
                          value={spec.value}
                          onChange={(e) =>
                            setSpecs((prev) => prev.map((item) => (item.id === spec.id ? { ...item, value: e.target.value } : item)))
                          }
                        />
                      </td>
                      <td>
                        <input
                          value={spec.unit}
                          onChange={(e) =>
                            setSpecs((prev) => prev.map((item) => (item.id === spec.id ? { ...item, unit: e.target.value } : item)))
                          }
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          value={spec.order}
                          onChange={(e) =>
                            setSpecs((prev) =>
                              prev.map((item) => (item.id === spec.id ? { ...item, order: Number(e.target.value) || 0 } : item)),
                            )
                          }
                          min={0}
                        />
                      </td>
                      <td>
                        <div className="admin-media-item__actions">
                          <button
                            type="button"
                            className="btn btn--ghost"
                            onClick={() =>
                              handleUpdateSpec(spec.id, {
                                name: spec.name,
                                value: spec.value,
                                unit: spec.unit,
                                order: spec.order,
                              })
                            }
                            disabled={specSaving}
                          >
                            Guardar
                          </button>
                          <button
                            type="button"
                            className="btn btn--ghost"
                            onClick={() => handleDeleteSpec(spec.id)}
                            disabled={specSaving}
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      {!loading && !initialValues && error ? <p className="ui-note ui-note--error">{error}</p> : null}
    </AdminLayout>
  )
}
