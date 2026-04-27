import { FormEvent, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'
import { createQuoteRequest } from '../services/catalogApi'
import type { QuoteRequestPayload } from '../types/catalog'

interface QuoteFormState {
  customer_name: string
  customer_phone: string
  customer_email: string
  message: string
}

const initialForm: QuoteFormState = {
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  message: '',
}

export function QuotePage() {
  const [searchParams] = useSearchParams()
  const productFromQuery = useMemo(() => {
    const value = searchParams.get('product')
    if (!value) return undefined
    const id = Number(value)
    return Number.isFinite(id) ? id : undefined
  }, [searchParams])

  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const validate = () => {
    if (!form.customer_name.trim()) return 'El nombre es obligatorio.'
    if (!form.customer_phone.trim()) return 'El teléfono es obligatorio.'
    if (!form.message.trim()) return 'El mensaje es obligatorio.'
    return null
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSuccess(null)

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    const payload: QuoteRequestPayload = {
      ...form,
      customer_email: form.customer_email.trim(),
      ...(productFromQuery ? { product: productFromQuery } : {}),
    }

    try {
      setLoading(true)
      await createQuoteRequest(payload)
      setSuccess('Solicitud enviada correctamente. Te contactaremos pronto.')
      setForm(initialForm)
    } catch {
      setError('No se pudo enviar la cotización. Intenta nuevamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <section className="simple-page">
        <h1>Cotizar</h1>
        <p>Completa el formulario y nuestro equipo comercial responderá a la brevedad.</p>
        {productFromQuery ? <p>Producto preseleccionado: #{productFromQuery}</p> : null}

        <form className="quote-form" onSubmit={onSubmit}>
          <label>
            Nombre
            <input
              value={form.customer_name}
              onChange={(event) => setForm((prev) => ({ ...prev, customer_name: event.target.value }))}
            />
          </label>
          <label>
            Teléfono
            <input
              value={form.customer_phone}
              onChange={(event) => setForm((prev) => ({ ...prev, customer_phone: event.target.value }))}
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={form.customer_email}
              onChange={(event) => setForm((prev) => ({ ...prev, customer_email: event.target.value }))}
            />
          </label>
          <label>
            Mensaje
            <textarea
              rows={5}
              value={form.message}
              onChange={(event) => setForm((prev) => ({ ...prev, message: event.target.value }))}
            />
          </label>

          {error ? <p className="ui-note ui-note--error">{error}</p> : null}
          {success ? <p className="ui-note ui-note--success">{success}</p> : null}

          <button className="btn btn--accent" type="submit" disabled={loading}>
            {loading ? 'Enviando...' : 'Enviar cotización'}
          </button>
        </form>
      </section>
    </Layout>
  )
}
