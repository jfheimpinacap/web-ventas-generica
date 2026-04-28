import { useState, type FormEvent } from 'react'

import type { SupplierFormValues } from '../../types/catalog'

interface SupplierFormProps {
  initialValues: SupplierFormValues
  onSubmit: (values: SupplierFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
}

export function SupplierForm({ initialValues, onSubmit, submitLabel, isSubmitting, error }: SupplierFormProps) {
  const [values, setValues] = useState(initialValues)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__full">{error}</p> : null}
      <label>Nombre<input value={values.name} onChange={(e) => setValues((p) => ({ ...p, name: e.target.value }))} required /></label>
      <label>Contacto<input value={values.contact_name} onChange={(e) => setValues((p) => ({ ...p, contact_name: e.target.value }))} /></label>
      <label>Teléfono<input value={values.phone} onChange={(e) => setValues((p) => ({ ...p, phone: e.target.value }))} /></label>
      <label>Email<input type="email" value={values.email} onChange={(e) => setValues((p) => ({ ...p, email: e.target.value }))} /></label>
      <label className="admin-product-form__full">Notas<textarea rows={4} value={values.notes} onChange={(e) => setValues((p) => ({ ...p, notes: e.target.value }))} /></label>
      <label className="admin-checkbox"><input type="checkbox" checked={values.is_active} onChange={(e) => setValues((p) => ({ ...p, is_active: e.target.checked }))} />Activo</label>
      <div className="admin-product-form__actions"><button className="btn btn--accent" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Guardando...' : submitLabel}</button></div>
    </form>
  )
}
