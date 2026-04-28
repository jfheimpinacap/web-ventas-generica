import { useMemo, useState, type FormEvent } from 'react'

import type { Brand, Category, ProductCondition, ProductFormValues, ProductType, StockStatus, SupplierSummary } from '../../types/catalog'

interface ProductFormProps {
  initialValues: ProductFormValues
  categories: Category[]
  brands: Brand[]
  suppliers: SupplierSummary[]
  onSubmit: (values: ProductFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
}

const PRODUCT_TYPES: Array<{ value: ProductType; label: string }> = [
  { value: 'machinery', label: 'Maquinaria' },
  { value: 'spare_part', label: 'Repuesto' },
  { value: 'service', label: 'Servicio' },
  { value: 'other', label: 'Otro' },
]

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
}: ProductFormProps) {
  const [values, setValues] = useState<ProductFormValues>(initialValues)

  const categoriesOptions = useMemo(() => categories.filter((item) => item.is_active), [categories])
  const brandsOptions = useMemo(() => brands.filter((item) => item.is_active), [brands])
  const suppliersOptions = useMemo(() => suppliers.filter((item) => item.is_active), [suppliers])

  const setField = <K extends keyof ProductFormValues>(field: K, nextValue: ProductFormValues[K]) => {
    setValues((prev) => ({ ...prev, [field]: nextValue }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      <label>
        Nombre
        <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
      </label>

      <label>
        Categoría
        <select value={values.category} onChange={(e) => setField('category', Number(e.target.value))} required>
          <option value="">Selecciona categoría</option>
          {categoriesOptions.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
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
        Tipo de producto
        <select value={values.product_type} onChange={(e) => setField('product_type', e.target.value as ProductType)} required>
          {PRODUCT_TYPES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
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
        Descripción corta
        <input value={values.short_description} onChange={(e) => setField('short_description', e.target.value)} />
      </label>

      <label className="admin-product-form__full">
        Descripción completa
        <textarea value={values.description} onChange={(e) => setField('description', e.target.value)} rows={4} />
      </label>

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

      <label>
        Precio
        <input value={values.price ?? ''} onChange={(e) => setField('price', e.target.value || null)} />
      </label>

      <label>
        Estado stock
        <select value={values.stock_status} onChange={(e) => setField('stock_status', e.target.value as StockStatus)} required>
          {STOCK_STATUSES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>

      <label className="admin-checkbox">
        <input
          type="checkbox"
          checked={values.price_visible}
          onChange={(e) => setField('price_visible', e.target.checked)}
        />
        Mostrar precio
      </label>

      <label className="admin-checkbox">
        <input type="checkbox" checked={values.is_featured} onChange={(e) => setField('is_featured', e.target.checked)} />
        Destacado
      </label>

      <label className="admin-checkbox">
        <input type="checkbox" checked={values.is_published} onChange={(e) => setField('is_published', e.target.checked)} />
        Publicado
      </label>

      <div className="admin-product-form__actions">
        <button type="submit" className="btn btn--accent" disabled={isSubmitting}>
          {isSubmitting ? 'Guardando...' : submitLabel}
        </button>
      </div>
    </form>
  )
}
