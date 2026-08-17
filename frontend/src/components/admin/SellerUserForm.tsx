import { useRef, useState, type FormEvent } from 'react'

import { ApiError } from '../../services/api'
import type { SellerUserWrite } from '../../services/adminUsersApi'

export interface SellerFormFields { username: string; email: string; fullName: string; password: string; confirmation: string }
type FieldErrors = Partial<Record<keyof SellerFormFields, string>>

export const EMPTY_SELLER_FORM: SellerFormFields = { username: '', email: '', fullName: '', password: '', confirmation: '' }
const usernamePattern = /^[\p{L}\p{N}._-]+$/u
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(fields: SellerFormFields, passwordRequired: boolean): FieldErrors {
  const errors: FieldErrors = {}
  const username = fields.username.trim()
  const email = fields.email.trim()
  if (!username) errors.username = 'El nombre de usuario es obligatorio.'
  else if (username.length < 3 || username.length > 150 || !usernamePattern.test(username)) errors.username = 'Debe tener entre 3 y 150 caracteres y solo letras, números, punto, guion o guion bajo.'
  if (email && (email.length > 254 || !emailPattern.test(email))) errors.email = 'Ingresa un correo válido de hasta 254 caracteres.'
  if (fields.fullName.trim().length > 180) errors.fullName = 'El nombre completo no puede superar los 180 caracteres.'
  if (passwordRequired && !fields.password) errors.password = 'La contraseña es obligatoria.'
  else if (fields.password && (fields.password.length < 12 || fields.password.length > 128 || !/[A-Z]/.test(fields.password) || !/[a-z]/.test(fields.password) || !/\d/.test(fields.password) || !/[^\p{L}\p{N}]/u.test(fields.password))) errors.password = 'Usa entre 12 y 128 caracteres, con mayúscula, minúscula, número y símbolo.'
  if ((passwordRequired || fields.password) && fields.confirmation !== fields.password) errors.confirmation = 'Las contraseñas no coinciden.'
  return errors
}

export function safeSellerMutationError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 400 || error.status === 409) {
      const details = JSON.stringify(error.payload ?? '').toLowerCase()
      if (details.includes('username') || details.includes('nombre de usuario')) return 'Ya existe una cuenta con ese nombre de usuario.'
      if (details.includes('email') || details.includes('correo')) return 'Ya existe una cuenta con ese correo.'
      return 'Revisa los datos ingresados e intenta nuevamente.'
    }
    if (error.status === 403) return 'No tienes permisos para administrar usuarios.'
    if (error.status === 404) return 'La cuenta ya no está disponible.'
  }
  return 'No fue posible completar la operación. Intenta nuevamente.'
}

interface Props {
  initialFields: SellerFormFields
  passwordRequired: boolean
  mode: 'create' | 'edit' | 'reactivate'
  onSubmit: (payload: SellerUserWrite, clearSensitive: () => void) => Promise<void>
  onCancel: () => void
}

export function SellerUserForm({ initialFields, passwordRequired, mode, onSubmit, onCancel }: Props) {
  const [fields, setFields] = useState(initialFields)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const refs = useRef<Partial<Record<keyof SellerFormFields, HTMLInputElement | null>>>({})
  const setField = (key: keyof SellerFormFields, value: string) => setFields((current) => ({ ...current, [key]: value }))
  const describedBy = (key: keyof SellerFormFields, help?: boolean) => [help ? `${key}-help` : '', errors[key] ? `${key}-error` : ''].filter(Boolean).join(' ') || undefined

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (submitting) return
    const nextErrors = validate(fields, passwordRequired)
    setErrors(nextErrors)
    const firstInvalid = (Object.keys(nextErrors) as (keyof SellerFormFields)[])[0]
    if (firstInvalid) { refs.current[firstInvalid]?.focus(); return }
    const payload: SellerUserWrite = { username: fields.username.trim(), email: fields.email.trim() || null, full_name: fields.fullName.trim() || null }
    if (fields.password) payload.password = fields.password
    if (mode === 'reactivate') payload.is_active = true
    setSubmitting(true); setGeneralError(null)
    try { await onSubmit(payload, () => setFields((current) => ({ ...current, password: '', confirmation: '' }))) }
    catch (error) { setFields((current) => ({ ...current, password: '', confirmation: '' })); setGeneralError(safeSellerMutationError(error)) }
    finally { setSubmitting(false) }
  }

  const buttonText = submitting ? (mode === 'create' ? 'Creando…' : mode === 'reactivate' ? 'Reactivando…' : 'Guardando…') : mode === 'create' ? 'Crear vendedor' : mode === 'reactivate' ? 'Guardar y reactivar' : 'Guardar cambios'
  return <form className="admin-user-form-page" onSubmit={(event) => void submit(event)} noValidate>
    <div className="admin-users-announcer" aria-live="assertive">{generalError ? <p className="ui-note ui-note--error">{generalError}</p> : null}</div>
    <section className="admin-block"><h2>Datos de acceso</h2>
      <div className="admin-user-form-grid">
        <div className="admin-user-field"><label htmlFor="username">Nombre de usuario</label><input autoFocus ref={(node) => { refs.current.username = node }} id="username" autoComplete="username" value={fields.username} onChange={(e) => setField('username', e.target.value)} aria-invalid={Boolean(errors.username)} aria-describedby={describedBy('username')} />{errors.username ? <span id="username-error" className="admin-field-error">{errors.username}</span> : null}</div>
        <div className="admin-user-field"><label htmlFor="email">Correo electrónico (opcional)</label><input ref={(node) => { refs.current.email = node }} id="email" type="email" autoComplete="email" value={fields.email} onChange={(e) => setField('email', e.target.value)} aria-invalid={Boolean(errors.email)} aria-describedby={describedBy('email')} />{errors.email ? <span id="email-error" className="admin-field-error">{errors.email}</span> : null}</div>
      </div>
      <div className="admin-user-form-grid">
        <div className="admin-user-field"><label htmlFor="password">{mode === 'edit' ? 'Nueva contraseña (opcional)' : 'Contraseña nueva'}</label><input ref={(node) => { refs.current.password = node }} id="password" type="password" autoComplete="new-password" value={fields.password} onChange={(e) => setField('password', e.target.value)} aria-invalid={Boolean(errors.password)} aria-describedby={describedBy('password', true)} /><small id="password-help">12 a 128 caracteres, con mayúscula, minúscula, número y símbolo.</small>{errors.password ? <span id="password-error" className="admin-field-error">{errors.password}</span> : null}</div>
        <div className="admin-user-field"><label htmlFor="confirmation">Confirmar contraseña</label><input ref={(node) => { refs.current.confirmation = node }} id="confirmation" type="password" autoComplete="new-password" value={fields.confirmation} onChange={(e) => setField('confirmation', e.target.value)} aria-invalid={Boolean(errors.confirmation)} aria-describedby={describedBy('confirmation')} />{errors.confirmation ? <span id="confirmation-error" className="admin-field-error">{errors.confirmation}</span> : null}</div>
      </div>{mode === 'edit' && fields.password ? <p className="ui-note">Al cambiarla, se cerrarán las sesiones anteriores del vendedor.</p> : null}
    </section>
    <section className="admin-block"><h2>Información del vendedor</h2><div className="admin-user-field"><label htmlFor="fullName">Nombre completo (opcional)</label><input ref={(node) => { refs.current.fullName = node }} id="fullName" value={fields.fullName} onChange={(e) => setField('fullName', e.target.value)} aria-invalid={Boolean(errors.fullName)} aria-describedby={describedBy('fullName')} />{errors.fullName ? <span id="fullName-error" className="admin-field-error">{errors.fullName}</span> : null}</div></section>
    {mode === 'create' ? <section className="admin-block"><h2>Código vendedor</h2><p className="ui-note">El código vendedor se asignará automáticamente al crear la cuenta y no podrá modificarse.</p></section> : null}
    <div className="admin-user-form__actions"><button className="btn btn--secondary" type="button" onClick={onCancel} disabled={submitting}>Cancelar</button><button className="btn btn--accent" type="submit" disabled={submitting}>{buttonText}</button></div>
  </form>
}
