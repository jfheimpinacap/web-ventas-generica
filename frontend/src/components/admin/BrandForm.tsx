import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { resolveMediaUrl } from '../../services/api'
import type { BrandFormValues } from '../../types/catalog'

interface BrandFormProps {
  initialValues: BrandFormValues
  initialLogoUrl?: string | null
  onSubmit: (values: BrandFormValues) => Promise<void>
  submitLabel: string
  isSubmitting: boolean
  error: string | null
}

export function BrandForm({
  initialValues,
  initialLogoUrl,
  onSubmit,
  submitLabel,
  isSubmitting,
  error,
}: BrandFormProps) {
  const [values, setValues] = useState(initialValues)

  const localPreview = useMemo(() => (values.logo ? URL.createObjectURL(values.logo) : null), [values.logo])

  useEffect(() => {
    return () => {
      if (localPreview) URL.revokeObjectURL(localPreview)
    }
  }, [localPreview])

  const logoPreview = localPreview || resolveMediaUrl(initialLogoUrl)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="admin-product-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__notice">{error}</p> : null}

      <section className="admin-form-panel admin-form-panel--columns-3">
        <h3>Datos de marca</h3>

        <label>
          Nombre
          <input value={values.name} onChange={(e) => setValues((p) => ({ ...p, name: e.target.value }))} required />
        </label>

        <label>
          Slug (opcional)
          <input value={values.slug ?? ''} onChange={(e) => setValues((p) => ({ ...p, slug: e.target.value }))} />
        </label>

        <label>
          Logo (opcional)
          <input type="file" accept="image/*" onChange={(e) => setValues((p) => ({ ...p, logo: e.target.files?.[0] ?? null }))} />
        </label>

        {logoPreview ? (
          <div className="admin-form-panel__full admin-mini-preview">
            <span>Vista previa logo</span>
            <img src={logoPreview} alt={values.name || 'Logo marca'} />
          </div>
        ) : null}

        <label className="admin-form-panel__full">
          Descripción
          <textarea rows={4} value={values.description} onChange={(e) => setValues((p) => ({ ...p, description: e.target.value }))} />
        </label>

        <div className="admin-form-panel__full admin-form-switches">
          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_active} onChange={(e) => setValues((p) => ({ ...p, is_active: e.target.checked }))} />
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
