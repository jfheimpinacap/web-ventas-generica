import { useEffect, useState, type FormEvent } from 'react'

import type { Category, CategoryFormValues } from '../../types/catalog'

interface CategoryFormProps {
  initialValues: CategoryFormValues
  onSubmit: (values: CategoryFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
  parentName?: string | null
  categories?: Category[]
  currentCategoryId?: number | null
}

export function CategoryForm({ initialValues, onSubmit, submitLabel, isSubmitting, error, parentName = null, categories = [], currentCategoryId = null }: CategoryFormProps) {
  const [values, setValues] = useState(initialValues)

  useEffect(() => {
    setValues(initialValues)
  }, [initialValues])

  const setField = <K extends keyof CategoryFormValues>(field: K, value: CategoryFormValues[K]) => {
    setValues((prev) => ({ ...prev, [field]: value }))
  }

  const rootOptions = categories
    .filter((category) => category.parent === null && category.id !== currentCategoryId)
    .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name))

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__notice">{error}</p> : null}

      <section className="admin-form-panel admin-form-panel--stack">
        <h3>{parentName ? `Subcategoría de ${parentName}` : 'Categoría principal'}</h3>
        <p className="ui-note">
          {parentName
            ? 'Crea o edita una subcategoría dentro de la categoría principal seleccionada.'
            : 'Crea o edita una categoría principal. Las subcategorías se administran desde el listado de Categorías.'}
        </p>

        <label>
          Nombre
          <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
        </label>

        <label>
          Ubicación
          <select value={values.parent ?? ''} onChange={(e) => setField('parent', e.target.value ? Number(e.target.value) : null)}>
            <option value="">Categoría principal</option>
            {rootOptions.map((category) => (
              <option key={category.id} value={category.id}>Subcategoría de: {category.name}</option>
            ))}
          </select>
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
