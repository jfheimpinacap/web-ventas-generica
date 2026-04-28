import { useState, type FormEvent } from 'react'

import type { BrandFormValues } from '../../types/catalog'

interface BrandFormProps {
  initialValues: BrandFormValues
  onSubmit: (values: BrandFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
}

export function BrandForm({ initialValues, onSubmit, submitLabel, isSubmitting, error }: BrandFormProps) {
  const [values, setValues] = useState(initialValues)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__full">{error}</p> : null}
      <label>Nombre<input value={values.name} onChange={(e) => setValues((p) => ({ ...p, name: e.target.value }))} required /></label>
      <label>Slug (opcional)<input value={values.slug ?? ''} onChange={(e) => setValues((p) => ({ ...p, slug: e.target.value }))} /></label>
      <label className="admin-product-form__full">Descripción<textarea rows={4} value={values.description} onChange={(e) => setValues((p) => ({ ...p, description: e.target.value }))} /></label>
      <label>Logo (opcional)<input type="file" accept="image/*" onChange={(e) => setValues((p) => ({ ...p, logo: e.target.files?.[0] ?? null }))} /></label>
      <label className="admin-checkbox"><input type="checkbox" checked={values.is_active} onChange={(e) => setValues((p) => ({ ...p, is_active: e.target.checked }))} />Activa</label>
      <div className="admin-product-form__actions"><button className="btn btn--accent" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Guardando...' : submitLabel}</button></div>
    </form>
  )
}
