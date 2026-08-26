import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useSystemDialog } from '../../context/SystemDialogContext'
import type { CustomerProfile } from '../../types/commercialQuote'
import type { CustomerProfileInput } from '../../services/customerProfilesApi'
import { formatChileanRutInput, normalizeChileanRut } from '../../utils/chileanRut'

type Values = Omit<CustomerProfileInput, 'email'> & { email: string }
export const EMPTY_CUSTOMER: Values = { business_name: '', rut: '', phone: '', city_or_commune: '', business_activity: '', address: '', contact_name: '', email: '' }
const fields: Array<{ key: keyof Values; label: string; max: number; type?: string; required?: boolean }> = [
  { key: 'business_name', label: 'Razón social', max: 200, required: true }, { key: 'rut', label: 'RUT', max: 12, required: true }, { key: 'phone', label: 'Teléfono', max: 30, type: 'tel', required: true }, { key: 'city_or_commune', label: 'Comuna o ciudad', max: 120, required: true },
  { key: 'business_activity', label: 'Giro', max: 200, required: true }, { key: 'address', label: 'Dirección', max: 300, required: true }, { key: 'contact_name', label: 'Nombre de contacto', max: 200, required: true }, { key: 'email', label: 'Correo electrónico', max: 254, type: 'email' },
]
export function customerToValues(value: CustomerProfile): Values { return { business_name: value.businessName, rut: formatChileanRutInput(value.rut), phone: value.phone, city_or_commune: value.cityOrCommune, business_activity: value.businessActivity, address: value.address, contact_name: value.contactName, email: value.email ?? '' } }

export function CustomerForm({ initial, isActive, submitLabel, submitting, serverError, onSubmit, onCancel }: { initial: Values; isActive?: boolean; submitLabel: string; submitting: boolean; serverError: string; onSubmit: (value: CustomerProfileInput) => Promise<void>; onCancel: () => void }) {
  const { requestConfirmation } = useSystemDialog()
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({})
  const leaving = useRef(false)
  useEffect(() => setValues(initial), [initial])
  const dirty = useMemo(() => JSON.stringify(values) !== JSON.stringify(initial), [initial, values])
  useEffect(() => { if (!dirty || submitting) return; const handler = (event: BeforeUnloadEvent) => event.preventDefault(); window.addEventListener('beforeunload', handler); return () => window.removeEventListener('beforeunload', handler) }, [dirty, submitting])
  const cancel = async () => { if (leaving.current) return; if (dirty) { leaving.current = true; const confirmed = await requestConfirmation({ title: 'Cambios sin guardar', message: 'Los cambios realizados se perderán.', confirmLabel: 'Salir sin guardar', cancelLabel: 'Continuar editando', variant: 'danger' }); leaving.current = false; if (!confirmed) return } onCancel() }
  const submit = async (event: FormEvent) => {
    event.preventDefault(); const next: Partial<Record<keyof Values, string>> = {}
    fields.forEach(field => { const value = values[field.key].trim(); if (field.required && !value) next[field.key] = `${field.label} es obligatorio.`; else if (value.length > field.max) next[field.key] = `${field.label} supera el máximo de ${field.max} caracteres.` })
    const rut = normalizeChileanRut(values.rut); if (!rut) next.rut = 'El RUT ingresado no es válido. Revise el número y el dígito verificador.'
    if (values.email.trim() && !/^\S+@\S+\.\S+$/.test(values.email.trim())) next.email = 'Ingrese un correo electrónico válido.'
    setErrors(next); const first = fields.find(field => next[field.key]); if (first) { document.getElementById(`customer-${first.key}`)?.focus(); return }
    await onSubmit({ ...values, rut: rut!, business_name: values.business_name.trim(), business_activity: values.business_activity.trim(), address: values.address.trim(), phone: values.phone.trim(), city_or_commune: values.city_or_commune.trim(), contact_name: values.contact_name.trim(), email: values.email.trim() || null })
  }
  return <form className="admin-customer-form" onSubmit={submit} noValidate aria-busy={submitting}>
    <section className="admin-form-panel admin-form-panel--columns-4"><h3 className="admin-form-panel__full">Datos del cliente</h3>{isActive !== undefined ? <p className="admin-form-panel__full">Estado: <span className={`badge ${isActive ? 'badge--ok' : 'badge--muted'}`}>{isActive ? 'Activo' : 'Inactivo'}</span></p> : null}
      {fields.map(field => { const error = errors[field.key]; return <label key={field.key} htmlFor={`customer-${field.key}`}>{field.label}{field.required ? ' *' : ''}<input id={`customer-${field.key}`} name={field.key} type={field.type ?? 'text'} value={values[field.key]} maxLength={field.max} disabled={submitting} required={field.required} aria-invalid={Boolean(error)} aria-describedby={error ? `customer-${field.key}-error` : undefined} onChange={event => { let value = event.target.value; if (field.key === 'rut') { if (/[^0-9kK.\s-]/.test(value)) return; value = formatChileanRutInput(value) } setValues(current => ({ ...current, [field.key]: value })); setErrors(current => ({ ...current, [field.key]: undefined })) }} />{error ? <span className="admin-field-error" id={`customer-${field.key}-error`}>{error}</span> : null}</label> })}
    </section>
    {Object.keys(errors).length ? <p className="ui-note ui-note--error" role="alert">Revise los campos destacados antes de guardar.</p> : null}{serverError ? <p className="ui-note ui-note--error" role="alert">{serverError}</p> : null}
    <div className="admin-product-form__actions"><button type="button" className="btn btn--secondary" disabled={submitting} onClick={() => void cancel()}>Volver</button><button type="submit" className="btn btn--accent" disabled={submitting}>{submitting ? (submitLabel === 'Crear cliente' ? 'Creando…' : 'Guardando…') : submitLabel}</button></div>
  </form>
}
