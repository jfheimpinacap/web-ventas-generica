import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError } from '../../services/api'
import { getUserPermissionCatalog, type ManagedRole, type ManagedUserWrite, type UserPermissionCatalog } from '../../services/adminUsersApi'
import { getPermissionMetadata, PERMISSION_GROUPS } from '../../auth/permissionMetadata'
import { buildManagedUserPayload } from './userFormPayload'

export interface UserFormFields { username: string; email: string; fullName: string; phone: string; password: string; confirmation: string; role: ManagedRole; permissions: string[] }
export const EMPTY_USER_FORM: UserFormFields = { username: '', email: '', fullName: '', phone: '', password: '', confirmation: '', role: 'seller', permissions: [] }
const usernamePattern = /^[\p{L}\p{N}._-]+$/u
type Errors = Partial<Record<'username' | 'email' | 'fullName' | 'phone' | 'password' | 'confirmation', string>>

export function safeUserMutationError(error: unknown) {
  if (error instanceof ApiError) {
    const detail = JSON.stringify(error.payload ?? '').toLowerCase()
    if (error.status === 401) return 'La sesión expiró. Ingresa nuevamente.'
    if (error.status === 403) return 'No tienes permisos para administrar usuarios.'
    if (error.status === 404) return 'La cuenta ya no está disponible.'
    if (error.status === 409) {
      if (detail.includes('otro superadministrador')) return 'Debe existir al menos otro superadministrador activo.'
      if (detail.includes('sesión actual')) return 'No puedes desactivar ni cambiar el rol de tu sesión actual.'
      if (detail.includes('correo')) return 'Ya existe una cuenta con ese correo.'
      return 'Ya existe una cuenta con ese nombre de usuario.'
    }
    if (error.status === 400) {
      if (detail.includes('permiso')) return 'La selección contiene un permiso no permitido.'
      if (detail.includes('rol')) return 'Selecciona un rol válido.'
      return 'Revisa los datos ingresados e intenta nuevamente.'
    }
  }
  return 'No fue posible completar la operación. Intenta nuevamente.'
}

export type UserFormMode = 'create' | 'edit' | 'reactivate'
interface Props { initialFields: UserFormFields; passwordRequired: boolean; mode: UserFormMode; currentSession?: boolean; onSubmit: (payload: ManagedUserWrite, clearSensitive: () => void) => Promise<void>; onCancel: () => void }
export function UserForm({ initialFields, passwordRequired, mode, currentSession = false, onSubmit, onCancel }: Props) {
  const [fields, setFields] = useState(initialFields); const [catalog, setCatalog] = useState<UserPermissionCatalog | null>(null)
  const [errors, setErrors] = useState<Errors>({}); const [generalError, setGeneralError] = useState<string | null>(null); const [submitting, setSubmitting] = useState(false)
  const refs = useRef<Partial<Record<keyof Errors, HTMLInputElement | null>>>({}); const initialized = useRef(mode !== 'create')
  useEffect(() => { const controller = new AbortController(); getUserPermissionCatalog(controller.signal).then((value) => { setCatalog(value); if (!initialized.current) { initialized.current = true; setFields((current) => ({ ...current, permissions: value.seller_grantable })) } }).catch((error) => { if (!(error instanceof DOMException && error.name === 'AbortError')) setGeneralError('No fue posible cargar el catálogo de permisos.') }); return () => controller.abort() }, [mode])
  const setText = (key: keyof Errors, value: string) => setFields((current) => ({ ...current, [key]: value }))
  const toggle = (permission: string) => setFields((current) => ({ ...current, permissions: current.permissions.includes(permission) ? current.permissions.filter((item) => item !== permission) : [...current.permissions, permission].sort() }))
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (submitting || !catalog) return
    const next: Errors = {}; const username = fields.username.trim(); const email = fields.email.trim()
    if (!username || username.length < 3 || username.length > 150 || !usernamePattern.test(username)) next.username = 'Usa entre 3 y 150 caracteres válidos.'
    if (email && (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254)) next.email = 'Ingresa un correo válido de hasta 254 caracteres.'
    if (fields.fullName.trim().length > 180) next.fullName = 'El nombre completo no puede superar los 180 caracteres.'
    if (fields.phone.trim().length > 32) next.phone = 'El teléfono no puede superar los 32 caracteres.'
    if (passwordRequired && !fields.password) next.password = 'La contraseña es obligatoria.'
    else if (fields.password && (fields.password.length < 12 || fields.password.length > 128 || !/[A-Z]/.test(fields.password) || !/[a-z]/.test(fields.password) || !/\d/.test(fields.password) || !/[^\p{L}\p{N}]/u.test(fields.password))) next.password = 'Usa entre 12 y 128 caracteres, con mayúscula, minúscula, número y símbolo.'
    if ((passwordRequired || fields.password) && fields.confirmation !== fields.password) next.confirmation = 'Las contraseñas no coinciden.'
    setErrors(next); const first = Object.keys(next)[0] as keyof Errors | undefined; if (first) { refs.current[first]?.focus(); return }
    const payload = buildManagedUserPayload(fields, catalog, mode)
    setSubmitting(true); setGeneralError(null)
    try { await onSubmit(payload, () => setFields((current) => ({ ...current, password: '', confirmation: '' }))) }
    catch (error) { setFields((current) => ({ ...current, password: '', confirmation: '' })); setGeneralError(safeUserMutationError(error)) }
    finally { setSubmitting(false) }
  }
  const field = (key: keyof Errors, label: string, type = 'text') => <div className="admin-user-field"><label htmlFor={key}>{label}</label><input ref={(node) => { refs.current[key] = node }} id={key} type={type} autoComplete={type === 'password' ? 'new-password' : undefined} value={String(fields[key])} onChange={(event) => setText(key, event.target.value)} aria-invalid={Boolean(errors[key])} />{errors[key] ? <span className="admin-field-error">{errors[key]}</span> : null}</div>
  return <form className="admin-user-form-page" onSubmit={(event) => void submit(event)} noValidate>
    <div aria-live="assertive">{generalError ? <p className="ui-note ui-note--error">{generalError}</p> : null}</div>
    <section className="admin-block admin-access-block"><h2>Datos de acceso</h2><div className="admin-user-form-grid">{field('username', 'Nombre de usuario')}{field('email', 'Correo electrónico (opcional)', 'email')}{field('password', mode === 'edit' ? 'Nueva contraseña (opcional)' : 'Contraseña nueva', 'password')}{field('confirmation', 'Confirmar contraseña', 'password')}<div className="admin-user-field"><label htmlFor="role">Rol de acceso</label><select id="role" value={fields.role} disabled={currentSession} onChange={(event) => setFields((current) => ({ ...current, role: event.target.value as ManagedRole }))}><option value="seller">Vendedor</option><option value="support_admin">Superadministrador</option></select></div></div>{currentSession ? <p className="ui-note">No puedes desactivar ni cambiar el rol de tu sesión actual.</p> : null}</section>
    {fields.role === 'support_admin' ? <section className="admin-block"><h2>Permisos de la cuenta</h2><p className="ui-note">El superadministrador posee acceso total y puede administrar usuarios.</p></section> : <section className="admin-block admin-permissions"><div className="admin-permissions__header"><div><h2>Permisos de la cuenta</h2><p>{fields.permissions.length} de {catalog?.seller_grantable.length ?? 29} seleccionados</p></div><div><button type="button" className="btn btn--secondary" onClick={() => setFields((current) => ({ ...current, permissions: catalog?.seller_grantable ?? [] }))}>Seleccionar todos</button><button type="button" className="btn btn--secondary" onClick={() => setFields((current) => ({ ...current, permissions: [] }))}>Quitar todos</button></div></div>{!catalog ? <p className="ui-note">Cargando permisos…</p> : <div className="admin-permission-grid">{PERMISSION_GROUPS.map((group) => { const permissions = catalog.seller_grantable.filter((permission) => getPermissionMetadata(permission).group === group); return permissions.length ? <fieldset key={group}><legend>{group}</legend>{permissions.map((permission, index) => { const metadata = getPermissionMetadata(permission); const descriptionId = `permission-${PERMISSION_GROUPS.indexOf(group)}-${index}-description`; return <label key={permission}><input type="checkbox" checked={fields.permissions.includes(permission)} onChange={() => toggle(permission)} aria-describedby={descriptionId} /><span><strong>{metadata.label}</strong><small id={descriptionId}>{metadata.description}</small></span></label> })}</fieldset> : null })}</div>}</section>}
    <div className="admin-user-form__actions"><button className="btn btn--secondary" type="button" onClick={onCancel} disabled={submitting}>Cancelar</button><button className="btn btn--accent" type="submit" disabled={submitting || !catalog}>{submitting ? 'Guardando…' : mode === 'create' ? 'Crear usuario' : mode === 'reactivate' ? 'Guardar y reactivar' : 'Guardar cambios'}</button></div>
  </form>
}
