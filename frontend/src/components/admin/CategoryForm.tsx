import { useState, type FormEvent } from 'react'

import type { Category, CategoryFormValues } from '../../types/catalog'

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

  const setField = <K extends keyof CategoryFormValues>(field: K, value: CategoryFormValues[K]) => {
    setValues((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__full">{error}</p> : null}
      <label>
        Nombre
        <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
      </label>
      <label>
        Slug (opcional)
        <input value={values.slug ?? ''} onChange={(e) => setField('slug', e.target.value)} />
      </label>
      <label>
        Categoría padre
        <select value={values.parent ?? ''} onChange={(e) => setField('parent', e.target.value ? Number(e.target.value) : null)}>
          <option value="">Sin padre</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </label>
      <label>
        Orden
        <input type="number" value={values.order} onChange={(e) => setField('order', Number(e.target.value) || 0)} />
      </label>
      <label className="admin-product-form__full">
        Descripción
        <textarea rows={4} value={values.description} onChange={(e) => setField('description', e.target.value)} />
      </label>
      <label className="admin-checkbox">
        <input type="checkbox" checked={values.is_active} onChange={(e) => setField('is_active', e.target.checked)} />
        Activa
      </label>
      <div className="admin-product-form__actions">
        <button className="btn btn--accent" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Guardando...' : submitLabel}</button>
      </div>
    </form>
  )
}
