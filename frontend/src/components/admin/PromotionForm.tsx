import { useState, type FormEvent } from 'react'

import type { ProductListItem, PromotionFormValues } from '../../types/catalog'

interface PromotionFormProps {
  initialValues: PromotionFormValues
  products: ProductListItem[]
  onSubmit: (values: PromotionFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
}

function datetimeLocalToIso(value: string) {
  if (!value) return null
  return new Date(value).toISOString()
}

function isoToDatetimeLocal(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

export function PromotionForm({ initialValues, products, onSubmit, submitLabel, isSubmitting, error }: PromotionFormProps) {
  const [values, setValues] = useState(initialValues)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__full">{error}</p> : null}
      <label>Título<input value={values.title} onChange={(e) => setValues((p) => ({ ...p, title: e.target.value }))} required /></label>
      <label>Subtítulo<input value={values.subtitle} onChange={(e) => setValues((p) => ({ ...p, subtitle: e.target.value }))} /></label>
      <label>Producto asociado<select value={values.product ?? ''} onChange={(e) => setValues((p) => ({ ...p, product: e.target.value ? Number(e.target.value) : null }))}><option value="">Sin producto</option>{products.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Orden<input type="number" value={values.order} onChange={(e) => setValues((p) => ({ ...p, order: Number(e.target.value) || 0 }))} /></label>
      <label>Texto botón<input value={values.button_text} onChange={(e) => setValues((p) => ({ ...p, button_text: e.target.value }))} /></label>
      <label>URL botón<input value={values.button_url} onChange={(e) => setValues((p) => ({ ...p, button_url: e.target.value }))} /></label>
      <label>Fecha inicio<input type="datetime-local" value={isoToDatetimeLocal(values.starts_at)} onChange={(e) => setValues((p) => ({ ...p, starts_at: datetimeLocalToIso(e.target.value) }))} /></label>
      <label>Fecha fin<input type="datetime-local" value={isoToDatetimeLocal(values.ends_at)} onChange={(e) => setValues((p) => ({ ...p, ends_at: datetimeLocalToIso(e.target.value) }))} /></label>
      <label>Imagen (opcional)<input type="file" accept="image/*" onChange={(e) => setValues((p) => ({ ...p, image: e.target.files?.[0] ?? null }))} /></label>
      <label className="admin-checkbox"><input type="checkbox" checked={values.is_active} onChange={(e) => setValues((p) => ({ ...p, is_active: e.target.checked }))} />Activa</label>
      <div className="admin-product-form__actions"><button className="btn btn--accent" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Guardando...' : submitLabel}</button></div>
    </form>
  )
}
