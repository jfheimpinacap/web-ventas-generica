import { useMemo, useState, type FormEvent } from 'react'

import type { Category, CategoryFormValues, ProductType } from '../../types/catalog'

const PRODUCT_TYPES: Array<{ value: ProductType; label: string }> = [
  { value: 'machinery', label: 'Maquinaria' },
  { value: 'spare_part', label: 'Repuestos' },
  { value: 'service', label: 'Servicios' },
]

interface CategoryFormProps {
  initialValues: CategoryFormValues
  categories: Category[]
  onSubmit: (values: CategoryFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
}

export function CategoryForm({ initialValues, categories, onSubmit, submitLabel, isSubmitting, error }: CategoryFormProps) {
  const [values, setValues] = useState(initialValues)

  const parentOptions = useMemo(
    () => categories.filter((item) => item.product_type === values.product_type && (item.is_active === true || item.id === values.parent)),
    [categories, values.parent, values.product_type],
  )

  const setField = <K extends keyof CategoryFormValues>(field: K, value: CategoryFormValues[K]) => {
    setValues((prev) => {
      if (field === 'product_type') {
        return { ...prev, product_type: value as ProductType, parent: null }
      }
      return { ...prev, [field]: value }
    })
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__notice">{error}</p> : null}

      <section className="admin-form-panel admin-form-panel--stack">
        <h3>Datos de categoría</h3>

        <label>
          Nombre
          <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
        </label>

        <label>
          Slug (opcional)
          <input value={values.slug ?? ''} onChange={(e) => setField('slug', e.target.value)} />
        </label>

        <label>
          Tipo
          <select value={values.product_type} onChange={(e) => setField('product_type', e.target.value as ProductType)} required>
            {PRODUCT_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Categoría padre
          <select value={values.parent ?? ''} onChange={(e) => setField('parent', e.target.value ? Number(e.target.value) : null)}>
            <option value="">Sin padre</option>
            {parentOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Orden
          <input type="number" value={values.order} onChange={(e) => setField('order', Number(e.target.value) || 0)} />
        </label>

        <label className="admin-form-panel__full">
          Descripción
          <textarea rows={4} value={values.description} onChange={(e) => setField('description', e.target.value)} />
        </label>

        <div className="admin-form-panel__full admin-form-switches">
          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_active} onChange={(e) => setField('is_active', e.target.checked)} />
            Activa
          </label>
        </div>
      </section>

      <div className="admin-product-form__actions">
        <button className="btn btn--accent" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Guardando...' : submitLabel}
        </button>
      </div>
    </form>
  )
}
