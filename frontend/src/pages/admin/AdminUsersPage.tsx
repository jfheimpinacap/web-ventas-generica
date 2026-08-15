import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { AdminIcon } from '../../components/admin/AdminIcon'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { ApiError } from '../../services/api'
import { clearSession } from '../../services/authApi'
import {
  createSellerUser, deactivateSellerUser, listSellerUsers, reactivateSellerUser, updateSellerUser,
  type SellerUser, type SellerUserWrite,
} from '../../services/adminUsersApi'

type StatusFilter = 'all' | 'active' | 'inactive'
type DialogState = { kind: 'create' } | { kind: 'edit'; user: SellerUser } | { kind: 'deactivate'; user: SellerUser } | { kind: 'reactivate'; user: SellerUser }
type FormFields = { username: string; email: string; fullName: string; password: string; confirmation: string }
type FieldErrors = Partial<Record<keyof FormFields, string>>

const emptyForm: FormFields = { username: '', email: '', fullName: '', password: '', confirmation: '' }
const usernamePattern = /^[\p{L}\p{N}._-]+$/u
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function formatDate(value: string | null) {
  if (!value) return 'Nunca'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function validate(fields: FormFields, passwordRequired: boolean): FieldErrors {
  const errors: FieldErrors = {}
  const username = fields.username.trim()
  const email = fields.email.trim()
  const fullName = fields.fullName.trim()
  if (!username) errors.username = 'El nombre de usuario es obligatorio.'
  else if (username.length < 3 || username.length > 150) errors.username = 'El nombre de usuario debe tener entre 3 y 150 caracteres.'
  else if (!usernamePattern.test(username)) errors.username = 'El nombre de usuario solo puede contener letras, números, punto, guion y guion bajo.'
  if (email && (email.length > 254 || !emailPattern.test(email))) errors.email = 'Ingresa un correo válido de hasta 254 caracteres.'
  if (fullName.length > 180) errors.fullName = 'El nombre completo no puede superar los 180 caracteres.'
  if (passwordRequired && !fields.password) errors.password = 'La contraseña es obligatoria.'
  if (fields.password && (fields.password.length < 12 || fields.password.length > 128 || !/[A-Z]/.test(fields.password) || !/[a-z]/.test(fields.password) || !/\d/.test(fields.password) || !/[^\p{L}\p{N}]/u.test(fields.password))) {
    errors.password = 'Usa entre 12 y 128 caracteres, con mayúscula, minúscula, número y símbolo.'
  }
  if ((passwordRequired || fields.password) && fields.confirmation !== fields.password) errors.confirmation = 'Las contraseñas no coinciden.'
  return errors
}

function safeMutationError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 400 || error.status === 409) {
      const serialized = JSON.stringify(error.payload ?? '').toLowerCase()
      if (serialized.includes('username') || serialized.includes('nombre de usuario')) return 'Ya existe una cuenta con ese nombre de usuario.'
      if (serialized.includes('email') || serialized.includes('correo')) return 'Ya existe una cuenta con ese correo.'
      return 'Revisa los datos ingresados e intenta nuevamente.'
    }
    if (error.status === 403) return 'No tienes permisos para administrar usuarios.'
    if (error.status === 404) return 'La cuenta ya no está disponible. Actualiza el listado.'
  }
  return 'No fue posible completar la operación. Intenta nuevamente.'
}

export function AdminUsersPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<SellerUser[]>([])
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [dialog, setDialog] = useState<DialogState | null>(null)
  const [fields, setFields] = useState<FormFields>(emptyForm)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [mutationError, setMutationError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const firstFieldRef = useRef<HTMLInputElement>(null)
  const openerRef = useRef<HTMLElement | null>(null)

  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 350); return () => window.clearTimeout(timer) }, [search])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setLoadError(false)
    listSellerUsers({ search: debouncedSearch || undefined, is_active: filter === 'all' ? undefined : filter === 'active' }, controller.signal)
      .then(setUsers)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        if (error instanceof ApiError && error.status === 401) { clearSession(); navigate('/login', { replace: true }); return }
        setLoadError(true)
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [debouncedSearch, filter, navigate, reloadKey])

  useEffect(() => {
    if (!dialog) return
    firstFieldRef.current?.focus()
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !submitting) closeDialog() }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [dialog, submitting])

  const openDialog = (next: DialogState, opener: HTMLElement) => {
    openerRef.current = opener; setDialog(next); setFieldErrors({}); setMutationError(null)
    setFields(next.kind === 'edit' ? { username: next.user.username, email: next.user.email ?? '', fullName: next.user.full_name ?? '', password: '', confirmation: '' } : emptyForm)
  }
  const closeDialog = () => {
    setFields(emptyForm); setFieldErrors({}); setMutationError(null); setDialog(null)
    window.setTimeout(() => openerRef.current?.focus(), 0)
  }
  const reload = async () => {
    const result = await listSellerUsers({ search: debouncedSearch || undefined, is_active: filter === 'all' ? undefined : filter === 'active' })
    setUsers(result)
  }
  const submitForm = async (event: FormEvent) => {
    event.preventDefault(); if (!dialog || dialog.kind === 'deactivate' || submitting) return
    const passwordRequired = dialog.kind === 'create' || dialog.kind === 'reactivate'
    const errors = validate(fields, passwordRequired)
    if (Object.keys(errors).length) { setFieldErrors(errors); return }
    setSubmitting(true); setMutationError(null)
    try {
      if (dialog.kind === 'reactivate') {
        await reactivateSellerUser(dialog.user.id, fields.password)
        setNotice('Cuenta reactivada correctamente.')
      } else {
        const payload: SellerUserWrite = { username: fields.username.trim(), email: fields.email.trim() || null, full_name: fields.fullName.trim() || null }
        if (dialog.kind === 'create') { payload.password = fields.password; await createSellerUser(payload); setNotice('Vendedor creado correctamente.') }
        else { if (fields.password) payload.password = fields.password; await updateSellerUser(dialog.user.id, payload); setNotice('Vendedor actualizado correctamente.') }
      }
      setFields(emptyForm); await reload(); closeDialog()
    } catch (error) { setMutationError(safeMutationError(error)) } finally { setSubmitting(false) }
  }
  const confirmDeactivate = async () => {
    if (!dialog || dialog.kind !== 'deactivate' || submitting) return
    setSubmitting(true); setMutationError(null)
    try { await deactivateSellerUser(dialog.user.id); setNotice('Cuenta desactivada correctamente.'); await reload(); closeDialog() }
    catch (error) { setMutationError(safeMutationError(error)) } finally { setSubmitting(false) }
  }

  const hasCriteria = Boolean(debouncedSearch) || filter !== 'all'
  return <AdminLayout>
    <AdminPageHeader title="Usuarios vendedores" description="Administra las cuentas que pueden acceder al panel de ventas." actions={<button className="btn btn--accent" type="button" onClick={(event) => openDialog({ kind: 'create' }, event.currentTarget)}><AdminIcon name="plus" /> Crear vendedor</button>} />
    <div className="admin-users-toolbar" role="search">
      <label htmlFor="seller-search">Buscar vendedores</label>
      <div className="admin-users-search"><input id="seller-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por usuario, correo o nombre" />{search ? <button type="button" className="btn btn--secondary" onClick={() => setSearch('')}>Limpiar</button> : null}</div>
      <label htmlFor="seller-status">Estado</label><select id="seller-status" value={filter} onChange={(event) => setFilter(event.target.value as StatusFilter)}><option value="all">Todos</option><option value="active">Activos</option><option value="inactive">Inactivos</option></select>
    </div>
    <div className="admin-users-announcer" aria-live="polite">{notice ? <p className="ui-note ui-note--success">{notice}</p> : null}{loading ? <p className="ui-note">Cargando usuarios…</p> : null}</div>
    {loadError ? <div className="admin-users-empty" role="alert"><p>No fue posible cargar los usuarios. Intenta nuevamente.</p><button className="btn btn--secondary" type="button" onClick={() => setReloadKey((value) => value + 1)}>Reintentar</button></div> : null}
    {!loading && !loadError && users.length === 0 ? <p className="admin-users-empty">{hasCriteria ? 'No se encontraron vendedores con los criterios seleccionados.' : 'Todavía no existen cuentas de vendedores.'}</p> : null}
    {!loadError && users.length > 0 ? <div className="admin-users-list">{users.map((user) => <article className="admin-user-card" key={user.id}>
      <div className="admin-user-card__identity"><strong>{user.username}</strong><span>{user.full_name || 'Sin nombre'}</span><span>{user.email || 'Sin correo'}</span></div>
      <div><span className={`badge ${user.is_active ? 'badge--ok' : 'badge--muted'}`}>{user.is_active ? 'Activo' : 'Inactivo'}</span></div>
      <dl><div><dt>Último acceso</dt><dd>{formatDate(user.last_login_at)}</dd></div><div><dt>Creación</dt><dd>{formatDate(user.created_at)}</dd></div></dl>
      <div className="admin-table-actions"><button className="table-action table-action--button" type="button" onClick={(event) => openDialog({ kind: 'edit', user }, event.currentTarget)}><AdminIcon name="edit" />Editar</button>{user.is_active ? <button className="table-action table-action--button table-action--danger" type="button" onClick={(event) => openDialog({ kind: 'deactivate', user }, event.currentTarget)}>Desactivar</button> : <button className="table-action table-action--button" type="button" onClick={(event) => openDialog({ kind: 'reactivate', user }, event.currentTarget)}>Reactivar</button>}</div>
    </article>)}</div> : null}
    {dialog ? <div className="admin-user-modal" role="presentation"><section className="admin-user-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="user-dialog-title">
      <h2 id="user-dialog-title">{dialog.kind === 'create' ? 'Crear vendedor' : dialog.kind === 'edit' ? `Editar ${dialog.user.username}` : dialog.kind === 'deactivate' ? 'Desactivar cuenta' : 'Reactivar cuenta'}</h2>
      {dialog.kind === 'deactivate' ? <><p>La cuenta quedará inactiva, se cerrarán sus sesiones y su contraseña anterior dejará de funcionar. Los registros históricos asociados al vendedor se conservarán.</p>{mutationError ? <p className="ui-note ui-note--error" role="alert">{mutationError}</p> : null}<div className="admin-user-form__actions"><button className="btn btn--secondary" type="button" onClick={closeDialog} disabled={submitting}>Cancelar</button><button autoFocus className="btn btn--danger" type="button" onClick={() => void confirmDeactivate()} disabled={submitting}>{submitting ? 'Desactivando…' : 'Desactivar cuenta'}</button></div></> : <form className="admin-user-form" onSubmit={(event) => void submitForm(event)}>
        {dialog.kind === 'reactivate' ? <p>Por seguridad, una cuenta desactivada debe recibir una contraseña nueva antes de volver a utilizarse.</p> : <><label htmlFor="user-username">Nombre de usuario</label><input ref={firstFieldRef} id="user-username" autoComplete="username" value={fields.username} onChange={(event) => setFields({ ...fields, username: event.target.value })} aria-invalid={Boolean(fieldErrors.username)} aria-describedby={fieldErrors.username ? 'username-error' : undefined} />{fieldErrors.username ? <span id="username-error" className="admin-field-error">{fieldErrors.username}</span> : null}<label htmlFor="user-email">Correo (opcional)</label><input id="user-email" type="email" value={fields.email} onChange={(event) => setFields({ ...fields, email: event.target.value })} aria-invalid={Boolean(fieldErrors.email)} />{fieldErrors.email ? <span className="admin-field-error">{fieldErrors.email}</span> : null}<label htmlFor="user-full-name">Nombre completo (opcional)</label><input id="user-full-name" value={fields.fullName} onChange={(event) => setFields({ ...fields, fullName: event.target.value })} aria-invalid={Boolean(fieldErrors.fullName)} />{fieldErrors.fullName ? <span className="admin-field-error">{fieldErrors.fullName}</span> : null}</>}
        <label htmlFor="user-password">{dialog.kind === 'edit' ? 'Nueva contraseña (opcional)' : 'Contraseña nueva'}</label><input ref={dialog.kind === 'reactivate' ? firstFieldRef : undefined} id="user-password" type="password" autoComplete="new-password" value={fields.password} onChange={(event) => setFields({ ...fields, password: event.target.value })} aria-invalid={Boolean(fieldErrors.password)} />{fieldErrors.password ? <span className="admin-field-error">{fieldErrors.password}</span> : null}<small>12 a 128 caracteres, con mayúscula, minúscula, número y símbolo.</small>
        <label htmlFor="user-confirmation">Confirmar contraseña</label><input id="user-confirmation" type="password" autoComplete="new-password" value={fields.confirmation} onChange={(event) => setFields({ ...fields, confirmation: event.target.value })} aria-invalid={Boolean(fieldErrors.confirmation)} />{fieldErrors.confirmation ? <span className="admin-field-error">{fieldErrors.confirmation}</span> : null}{dialog.kind === 'edit' && fields.password ? <p className="ui-note">Al cambiarla, se cerrarán las sesiones anteriores del vendedor.</p> : null}{mutationError ? <p className="ui-note ui-note--error" role="alert">{mutationError}</p> : null}<div className="admin-user-form__actions"><button className="btn btn--secondary" type="button" onClick={closeDialog} disabled={submitting}>Cancelar</button><button className="btn btn--accent" type="submit" disabled={submitting}>{submitting ? 'Guardando…' : dialog.kind === 'reactivate' ? 'Reactivar cuenta' : 'Guardar'}</button></div>
      </form>}
    </section></div> : null}
  </AdminLayout>
}
