import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getAdminQuote, updateQuote } from '../../services/adminApi'
import {
  PREFERRED_CONTACT_METHOD_LABELS,
  QUOTE_STATUS_LABELS,
  type QuoteRequestAdmin,
  type QuoteStatus,
} from '../../types/catalog'

export function AdminQuoteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [item, setItem] = useState<QuoteRequestAdmin | null>(null)
  const [status, setStatus] = useState<QuoteStatus>('new')
  const [internalNotes, setInternalNotes] = useState('')
  const [sellerResponse, setSellerResponse] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      if (!id) return
      try {
        setLoading(true)
        const data = await getAdminQuote(Number(id))
        setItem(data)
        setStatus(data.status)
        setInternalNotes(data.internal_notes)
        setSellerResponse(data.seller_response)
      } catch {
        setError('No se pudo cargar la cotización.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [id])

  const onSave = async (event: FormEvent) => {
    event.preventDefault()
    if (!id) return

    try {
      setSaving(true)
      setError(null)
      const updated = await updateQuote(Number(id), {
        status,
        internal_notes: internalNotes,
        seller_response: sellerResponse,
      })
      setItem(updated)
      setSuccess('Cotización actualizada correctamente.')
    } catch {
      setError('No se pudieron guardar los cambios.')
    } finally {
      setSaving(false)
    }
  }

  const applyQuickStatus = (nextStatus: QuoteStatus) => {
    setStatus(nextStatus)
    setSuccess(null)
  }

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>Detalle de cotización</h1>
        <button className="btn btn--ghost" onClick={() => navigate('/admin/cotizaciones')} type="button">
          Volver
        </button>
      </div>

      {loading ? <p className="ui-note">Cargando detalle...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && item ? (
        <form className="admin-block" onSubmit={onSave}>
          <p>
            <strong>Cliente:</strong> {item.customer_name}
          </p>
          <p>
            <strong>Teléfono:</strong> {item.customer_phone}
          </p>
          <p>
            <strong>Email:</strong> {item.customer_email || '-'}
          </p>
          <p>
            <strong>Empresa:</strong> {item.company_name || '-'}
          </p>
          <p>
            <strong>Ciudad:</strong> {item.city || '-'}
          </p>
          <p>
            <strong>Método preferido:</strong>{' '}
            {item.preferred_contact_method ? PREFERRED_CONTACT_METHOD_LABELS[item.preferred_contact_method] : '-'}
          </p>
          <p>
            <strong>Producto:</strong>{' '}
            {item.product_name ? (
              <Link className="table-action" to={`/catalogo?search=${encodeURIComponent(item.product_name)}`}>
                {item.product_name}
              </Link>
            ) : (
              'Sin producto asociado'
            )}
          </p>
          <p>
            <strong>Mensaje:</strong> {item.message}
          </p>
          <p>
            <strong>Estado actual:</strong> <span className={`badge quote-status quote-status--${item.status}`}>{QUOTE_STATUS_LABELS[item.status]}</span>
          </p>

          <div className="admin-inline-form">
            <label>
              Estado
              <select value={status} onChange={(event) => setStatus(event.target.value as QuoteStatus)}>
                {Object.entries(QUOTE_STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="admin-product-form__full">
              Notas internas
              <textarea rows={4} value={internalNotes} onChange={(event) => setInternalNotes(event.target.value)} />
            </label>
            <label className="admin-product-form__full">
              Respuesta comercial
              <textarea rows={4} value={sellerResponse} onChange={(event) => setSellerResponse(event.target.value)} />
            </label>
          </div>

          <div className="admin-media-item__actions">
            <button className="btn btn--ghost" type="button" onClick={() => applyQuickStatus('contacted')}>
              Marcar contactado
            </button>
            <button className="btn btn--ghost" type="button" onClick={() => applyQuickStatus('quoted')}>
              Marcar cotizado
            </button>
            <button className="btn btn--ghost" type="button" onClick={() => applyQuickStatus('closed')}>
              Cerrar
            </button>
            <button className="btn btn--ghost" type="button" onClick={() => applyQuickStatus('discarded')}>
              Descartar
            </button>
          </div>

          <div>
            <p>
              <strong>Fechas:</strong> Contactado {item.contacted_at ? new Date(item.contacted_at).toLocaleString() : '-'} · Cotizado{' '}
              {item.quoted_at ? new Date(item.quoted_at).toLocaleString() : '-'} · Cerrado{' '}
              {item.closed_at ? new Date(item.closed_at).toLocaleString() : '-'}
            </p>
          </div>

          {success ? <p className="ui-note ui-note--success">{success}</p> : null}
          <button className="btn btn--accent" type="submit" disabled={saving}>
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </button>
        </form>
      ) : null}
    </AdminLayout>
  )
}
