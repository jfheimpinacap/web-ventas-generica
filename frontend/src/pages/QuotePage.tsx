import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'
import { createQuoteRequest, getProducts } from '../services/catalogApi'
import type { PreferredContactMethod, ProductListItem, QuoteRequestPublicPayload } from '../types/catalog'
import { formatPrice } from '../utils/formatters'

interface QuoteFormState {
  customer_name: string
  customer_phone: string
  customer_email: string
  company_name: string
  city: string
  preferred_contact_method: PreferredContactMethod | ''
  message: string
}

const initialForm: QuoteFormState = {
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  company_name: '',
  city: '',
  preferred_contact_method: '',
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

  const [selectedProduct, setSelectedProduct] = useState<ProductListItem | null>(null)
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (!productFromQuery) {
      setSelectedProduct(null)
      return
    }

    const run = async () => {
      try {
        const products = await getProducts()
        setSelectedProduct(products.find((product) => product.id === productFromQuery) ?? null)
      } catch {
        setSelectedProduct(null)
      }
    }

    void run()
  }, [productFromQuery])

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

    const payload: QuoteRequestPublicPayload = {
      customer_name: form.customer_name.trim(),
      customer_phone: form.customer_phone.trim(),
      customer_email: form.customer_email.trim(),
      company_name: form.company_name.trim(),
      city: form.city.trim(),
      preferred_contact_method: form.preferred_contact_method,
      message: form.message.trim(),
      ...(productFromQuery ? { product: productFromQuery } : {}),
    }

    try {
      setLoading(true)
      await createQuoteRequest(payload)
      setSuccess('¡Solicitud enviada! Un vendedor te contactará pronto para continuar con tu cotización.')
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

        {productFromQuery ? (
          <div className="quote-product-banner">
            <p>
              <strong>Producto seleccionado:</strong>{' '}
              {selectedProduct ? `${selectedProduct.name} · ${formatPrice(selectedProduct)}` : `#${productFromQuery}`}
            </p>
            {selectedProduct ? (
              <Link className="btn btn--ghost" to={`/producto/${selectedProduct.slug}`}>
                Ver detalle del producto
              </Link>
            ) : null}
          </div>
        ) : null}

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
            Empresa (opcional)
            <input
              value={form.company_name}
              onChange={(event) => setForm((prev) => ({ ...prev, company_name: event.target.value }))}
            />
          </label>
          <label>
            Ciudad / comuna (opcional)
            <input value={form.city} onChange={(event) => setForm((prev) => ({ ...prev, city: event.target.value }))} />
          </label>
          <label>
            Método de contacto preferido (opcional)
            <select
              value={form.preferred_contact_method}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, preferred_contact_method: event.target.value as PreferredContactMethod | '' }))
              }
            >
              <option value="">Selecciona una opción</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="phone">Teléfono</option>
              <option value="email">Email</option>
            </select>
          </label>
          <label>
            Mensaje libre
            <textarea
              rows={5}
              value={form.message}
              onChange={(event) => setForm((prev) => ({ ...prev, message: event.target.value }))}
              placeholder="Cuéntanos qué necesitas, plazos de entrega, ubicación o datos técnicos adicionales."
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
