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

const formatQuoteFolio = (id: number) => `COT-${String(id).padStart(6, '0')}`

export function AdminQuoteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [item, setItem] = useState<QuoteRequestAdmin | null>(null)
  const [status, setStatus] = useState<QuoteStatus>('new')
  const [internalNotes, setInternalNotes] = useState('')
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
        seller_response: item?.seller_response ?? '',
      })
      setItem(updated)
      setSuccess('Cotización actualizada correctamente.')
    } catch {
      setError('No se pudieron guardar los cambios.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AdminLayout>
      <div className="admin-products-header">
        <h1>{item ? `Cotización ${formatQuoteFolio(item.id)}` : 'Detalle de cotización'}</h1>
        <button className="btn btn--ghost" onClick={() => navigate('/admin/cotizaciones')} type="button">
          Volver
        </button>
      </div>

      {loading ? <p className="ui-note">Cargando detalle...</p> : null}
      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      {!loading && item ? (
        <form className="admin-block quote-detail-form" onSubmit={onSave}>
          <div className="quote-detail-grid">
            <div className="quote-detail-column">
              <p className="quote-detail-row"><strong>Folio:</strong> <span>{formatQuoteFolio(item.id)}</span></p>
              <p className="quote-detail-row"><strong>Empresa:</strong> <span>{item.company_name || '-'}</span></p>
              <p className="quote-detail-row"><strong>Nombre:</strong> <span>{item.customer_name}</span></p>
              <p className="quote-detail-row"><strong>Teléfono:</strong> <span>{item.customer_phone}</span></p>
              <p className="quote-detail-row"><strong>Email:</strong> <span>{item.customer_email || '-'}</span></p>
              <p className="quote-detail-row"><strong>Mensaje:</strong> <span>{item.message}</span></p>
            </div>

            <div className="quote-detail-column">
              <p className="quote-detail-row"><strong>Fecha:</strong> <span>{new Date(item.created_at).toLocaleDateString()}</span></p>
              <p className="quote-detail-row"><strong>Ciudad:</strong> <span>{item.city || '-'}</span></p>
              <p className="quote-detail-row">
                <strong>Tipo contacto:</strong>
                <span>{item.preferred_contact_method ? PREFERRED_CONTACT_METHOD_LABELS[item.preferred_contact_method] : '-'}</span>
              </p>
              <p className="quote-detail-row">
                <strong>Producto:</strong>
                <span>
                  {item.product_name ? (
                    <Link className="table-action" to={`/catalogo?search=${encodeURIComponent(item.product_name)}`}>
                      {item.product_name}
                    </Link>
                  ) : (
                    'Sin producto asociado'
                  )}
                </span>
              </p>
              <p className="quote-detail-row">
                <strong>Estado actual:</strong>
                <span><span className={`badge quote-status quote-status--${item.status}`}>{QUOTE_STATUS_LABELS[item.status]}</span></span>
              </p>
            </div>
          </div>

          <div className="admin-inline-form quote-detail-edit-form">
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
          </div>

          {success ? <p className="ui-note ui-note--success">{success}</p> : null}
          <div className="quote-detail-actions">
            <button className="btn btn--accent" type="submit" disabled={saving}>
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        </form>
      ) : null}
    </AdminLayout>
  )
}
