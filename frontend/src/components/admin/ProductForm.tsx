import { useEffect, useMemo, useState, type FormEvent } from 'react'

import type { Brand, Category, ProductCondition, ProductFormValues, StockStatus, SupplierSummary } from '../../types/catalog'
import { getRootCategory, inferProductTypeFromRootCategory, isValidChileanPriceInput, normalizeChileanPriceInput } from '../../utils/formatters'

interface ProductFormProps {
  initialValues: ProductFormValues
  categories: Category[]
  brands: Brand[]
  suppliers: SupplierSummary[]
  onSubmit: (values: ProductFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
  onValuesChange?: (values: ProductFormValues) => void
}

const PRODUCT_CONDITIONS: Array<{ value: ProductCondition; label: string }> = [
  { value: 'new', label: 'Nuevo' },
  { value: 'used', label: 'Usado' },
  { value: 'refurbished', label: 'Reacondicionado' },
  { value: 'not_applicable', label: 'No aplica' },
]

const STOCK_STATUSES: Array<{ value: StockStatus; label: string }> = [
  { value: 'available', label: 'Disponible' },
  { value: 'on_request', label: 'A pedido' },
  { value: 'reserved', label: 'Reservado' },
  { value: 'sold', label: 'Vendido' },
]

function toNullableNumber(value: string) {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isNaN(parsed) ? null : parsed
}

export function ProductForm({
  initialValues,
  categories,
  brands,
  suppliers,
  onSubmit,
  submitLabel,
  isSubmitting,
  error,
  onValuesChange,
}: ProductFormProps) {
  const [values, setValues] = useState<ProductFormValues>(initialValues)
  const [priceError, setPriceError] = useState<string | null>(null)
  const [primaryCategoryId, setPrimaryCategoryId] = useState<number | null>(null)

  useEffect(() => {
    setValues(initialValues)
    setPrimaryCategoryId(null)
    setPriceError(null)
  }, [initialValues])

  useEffect(() => {
    onValuesChange?.(values)
  }, [onValuesChange, values])

  const rootCategories = useMemo(() => categories.filter((item) => item.is_active && item.parent === null).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)), [categories])
  const selectedCategory = useMemo(() => categories.find((item) => item.id === values.category) ?? null, [categories, values.category])
  const categoryRoot = useMemo(() => getRootCategory(selectedCategory, categories), [categories, selectedCategory])
  const selectedRootId = categoryRoot?.id ?? primaryCategoryId
  const selectedRoot = useMemo(() => categories.find((item) => item.id === selectedRootId) ?? categoryRoot, [categories, categoryRoot, selectedRootId])
  const subcategoryOptions = useMemo(() => selectedRootId ? categories.filter((item) => item.is_active && item.parent === selectedRootId).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)) : [], [categories, selectedRootId])
  const brandsOptions = useMemo(() => brands.filter((item) => item.is_active), [brands])
  const suppliersOptions = useMemo(() => suppliers.filter((item) => item.is_active), [suppliers])

  const setField = <K extends keyof ProductFormValues>(field: K, nextValue: ProductFormValues[K]) => {
    setValues((prev) => {
      if (field === 'product_type') return prev
      if (field === 'category') {
        const selected = categories.find((item) => item.id === nextValue) ?? null
        const root = getRootCategory(selected, categories) ?? selected
        if (selected?.parent === null) {
          setPrimaryCategoryId(selected.id)
          return { ...prev, category: 0, product_type: inferProductTypeFromRootCategory(selected) }
        }
        setPrimaryCategoryId(root?.id ?? null)
        return { ...prev, category: Number(nextValue), product_type: inferProductTypeFromRootCategory(root) }
      }
      return { ...prev, [field]: nextValue }
    })
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!isValidChileanPriceInput(values.price)) {
      setPriceError('Ingresa un precio válido usando solo números y puntos como separador de miles.')
      return
    }

    setPriceError(null)
    await onSubmit({
      ...values,
      product_type: inferProductTypeFromRootCategory(selectedRoot),
      price: normalizeChileanPriceInput(values.price),
    })
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__notice">{error}</p> : null}

      <section className="admin-form-panel admin-form-panel--columns-2">
        <h3>Información general</h3>

        <label>
          Nombre
          <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
        </label>

        <label>
          Categoría principal
          <select value={selectedRootId ?? ''} onChange={(e) => setField('category', Number(e.target.value))} required>
            <option value="">Selecciona categoría principal</option>
            {rootCategories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Subcategoría
          <select value={selectedCategory?.parent ? values.category : ''} onChange={(e) => setField('category', Number(e.target.value))} required disabled={!selectedRootId || subcategoryOptions.length === 0}>
            <option value="">Selecciona subcategoría</option>
            {subcategoryOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          {selectedRootId && subcategoryOptions.length === 0 ? (
            <span className="ui-note">No hay subcategorías activas para esta categoría principal. Puedes crearlas desde Categorías.</span>
          ) : null}
        </label>

        <label>
          Marca
          <select value={values.brand ?? ''} onChange={(e) => setField('brand', toNullableNumber(e.target.value))}>
            <option value="">Sin marca</option>
            {brandsOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Proveedor
          <select value={values.supplier ?? ''} onChange={(e) => setField('supplier', toNullableNumber(e.target.value))}>
            <option value="">Sin proveedor</option>
            {suppliersOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>


        <label>
          Condición
          <select value={values.condition} onChange={(e) => setField('condition', e.target.value as ProductCondition)} required>
            {PRODUCT_CONDITIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Stock
          <select value={values.stock_status} onChange={(e) => setField('stock_status', e.target.value as StockStatus)} required>
            {STOCK_STATUSES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Precio
          <input
            inputMode="numeric"
            value={values.price ?? ''}
            onChange={(e) => {
              setField('price', e.target.value || null)
              if (priceError) setPriceError(null)
            }}
            aria-invalid={Boolean(priceError)}
            aria-describedby={priceError ? 'product-price-error' : undefined}
          />
          {priceError ? <span id="product-price-error" className="ui-note ui-note--error">{priceError}</span> : null}
        </label>
      </section>

      <section className="admin-form-panel admin-form-panel--columns-2">
        <h3>Información técnica / comercial</h3>

        <label>
          Modelo
          <input value={values.model} onChange={(e) => setField('model', e.target.value)} />
        </label>

        <label>
          SKU
          <input value={values.sku} onChange={(e) => setField('sku', e.target.value)} />
        </label>

        <label>
          Año
          <input
            type="number"
            value={values.year ?? ''}
            onChange={(e) => setField('year', toNullableNumber(e.target.value))}
          />
        </label>

        <label>
          Horómetro
          <input
            type="number"
            value={values.hours_meter ?? ''}
            onChange={(e) => setField('hours_meter', toNullableNumber(e.target.value))}
          />
        </label>

        <label className="admin-form-panel__full">
          Descripción corta
          <input value={values.short_description} onChange={(e) => setField('short_description', e.target.value)} />
        </label>

        <label className="admin-form-panel__full">
          Descripción completa
          <textarea value={values.description} onChange={(e) => setField('description', e.target.value)} rows={4} />
        </label>

        <div className="admin-form-switches">
          <label className="admin-checkbox">
            <input
              type="checkbox"
              checked={values.price_visible}
              onChange={(e) => setField('price_visible', e.target.checked)}
            />
            Mostrar precio
          </label>

          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_published} onChange={(e) => setField('is_published', e.target.checked)} />
            Publicado
          </label>

          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_featured} onChange={(e) => setField('is_featured', e.target.checked)} />
            Destacado
          </label>
        </div>
      </section>

      <div className="admin-product-form__actions">
        <button type="submit" className="btn btn--accent" disabled={isSubmitting}>
          {isSubmitting ? 'Guardando...' : submitLabel}
        </button>
      </div>
    </form>
  )
}
