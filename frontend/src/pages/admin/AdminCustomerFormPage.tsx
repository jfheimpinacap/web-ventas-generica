import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AdminEditorLayout } from '../../components/admin/AdminEditorLayout'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { CustomerForm, EMPTY_CUSTOMER, customerToValues } from '../../components/admin/CustomerForm'
import { ApiError, getSafeApiErrorMessage } from '../../services/api'
import { createCustomer, getCustomer, updateCustomer } from '../../services/customerProfilesApi'
import type { CustomerProfile } from '../../types/commercialQuote'

export function AdminCustomerFormPage() {
  const { id } = useParams(); const [params] = useSearchParams(); const navigate = useNavigate()
  const customerId = Number(id); const editing = id !== undefined
  const [customer, setCustomer] = useState<CustomerProfile | null>(null); const [loading, setLoading] = useState(editing); const [submitting, setSubmitting] = useState(false); const [error, setError] = useState('')
  const returnTo = `/admin/clientes${params.get('return') ? `?${params.get('return')}` : ''}`
  useEffect(() => { if (!editing) return; if (!Number.isInteger(customerId) || customerId <= 0) { setError('El cliente indicado no es válido.'); setLoading(false); return } let active = true; void getCustomer(customerId).then(value => { if (active) setCustomer(value) }).catch(caught => { if (active) setError(getSafeApiErrorMessage(caught, 'No se pudo cargar el cliente.')) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [customerId, editing])
  const save = async (values: Parameters<typeof createCustomer>[0]) => { if (submitting) return; setSubmitting(true); setError(''); try { if (editing) await updateCustomer(customerId, values); else await createCustomer(values); navigate(`${returnTo}${returnTo.includes('?') ? '&' : '?'}result=${editing ? 'updated' : 'created'}`, { replace: true }) } catch (caught) { setError(caught instanceof ApiError && caught.status === 409 ? 'Ya existe un cliente con ese RUT. Puede ser necesario reactivarlo desde el listado de clientes.' : getSafeApiErrorMessage(caught, 'No se pudo guardar el cliente.')) } finally { setSubmitting(false) } }
  return <AdminLayout>{loading ? <p className="ui-note" aria-busy="true">Cargando formulario…</p> : <AdminEditorLayout title={editing ? 'Editar cliente' : 'Crear cliente'} onBack={() => navigate(returnTo)} hideDefaultBackAction form={editing && !customer ? <p className="ui-note ui-note--error" role="alert">{error}</p> : <CustomerForm initial={customer ? customerToValues(customer) : EMPTY_CUSTOMER} isActive={customer?.isActive} submitLabel={editing ? 'Guardar cambios' : 'Crear cliente'} submitting={submitting} serverError={error} onSubmit={save} onCancel={() => navigate(returnTo)} />} />}</AdminLayout>
}
