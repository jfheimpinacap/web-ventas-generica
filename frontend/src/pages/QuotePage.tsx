import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'
import { INDEX_ROBOTS, Seo } from '../components/common/Seo'
import { Breadcrumb } from '../components/common/Breadcrumb'
import { JsonLd } from '../components/common/JsonLd'
import { createQuoteRequest, getProducts } from '../services/catalogApi'
import { resolveMediaUrl } from '../services/api'
import type { PreferredContactMethod, ProductListItem, QuoteRequestPublicPayload, ProductCondition, StockStatus } from '../types/catalog'
import { formatPrice } from '../utils/formatters'
import { trackGenerateLead } from '../utils/analytics'
import { buildBreadcrumbJsonLd, buildPageJsonLd, getStaticSeo } from '../utils/seo'

interface QuoteFormState {
  customer_name: string
  customer_phone: string
  customer_email: string
  company_name: string
  city: string
  preferred_contact_method: PreferredContactMethod | ''
  message: string
}


const CONDITION_LABELS: Record<ProductCondition, string> = {
  new: 'Nuevo',
  used: 'Usado',
  refurbished: 'Reacondicionado',
  not_applicable: 'No aplica',
}

const STOCK_LABELS: Record<StockStatus, string> = {
  available: 'Disponible',
  on_request: 'Bajo consulta',
  sold: 'Vendido',
  reserved: 'Reservado',
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
  const quoteSeo = getStaticSeo('/cotizar')
  const breadcrumbItems = [{ label: 'Inicio', to: '/' }, { label: 'Cotizar' }]
  const [searchParams] = useSearchParams()
  const productFromQuery = useMemo(() => {
    const value = searchParams.get('product')
    if (!value) return undefined
    if (!/^[1-9]\d*$/.test(value)) return null
    const id = Number(value)
    return Number.isSafeInteger(id) ? id : null
  }, [searchParams])

  const [selectedProduct, setSelectedProduct] = useState<ProductListItem | null>(null)
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [submittedContactMethod, setSubmittedContactMethod] = useState<PreferredContactMethod | ''>('')
  const [productSelectionError, setProductSelectionError] = useState(false)
  const [imageLoadFailed, setImageLoadFailed] = useState(false)
  const inFlightRef = useRef(false)
  const mountedRef = useRef(true)
  const confirmationHeadingRef = useRef<HTMLHeadingElement>(null)
  const formHeadingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false } }, [])
  useEffect(() => { if (submitted) confirmationHeadingRef.current?.focus() }, [submitted])

  const selectedProductImageUrl = useMemo(
    () => resolveMediaUrl(selectedProduct?.main_image?.image),
    [selectedProduct],
  )

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [productFromQuery])

  useEffect(() => {
    let active = true

    setSelectedProduct(null)
    setProductSelectionError(false)
    if (productFromQuery === undefined) {
      return () => {
        active = false
      }
    }

    if (productFromQuery === null) { setProductSelectionError(true); return () => { active = false } }

    const run = async () => {
      try {
        const products = await getProducts()
        if (active) { const match = products.find((product) => product.id === productFromQuery) ?? null; setSelectedProduct(match); setProductSelectionError(!match) }
      } catch {
        if (active) { setSelectedProduct(null); setProductSelectionError(true) }
      }
    }

    void run()

    return () => {
      active = false
    }
  }, [productFromQuery])

  useEffect(() => {
    setImageLoadFailed(false)
  }, [selectedProduct?.id, selectedProductImageUrl])

  const validate = () => {
    if (!form.customer_name.trim()) return 'El nombre es obligatorio.'
    if (!form.customer_phone.trim()) return 'El teléfono es obligatorio.'
    if (!form.message.trim()) return 'El mensaje es obligatorio.'
    return null
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    if (inFlightRef.current || submitted) return

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
      ...(selectedProduct ? { product: selectedProduct.id } : {}),
    }

    inFlightRef.current = true
    try {
      setLoading(true)
      await createQuoteRequest(payload)
      if (!mountedRef.current) return
      trackGenerateLead({
        product_id: selectedProduct?.id,
        product_name: selectedProduct?.name,
        preferred_contact_method: form.preferred_contact_method || undefined,
      })
      setSubmittedContactMethod(form.preferred_contact_method)
      setForm(initialForm)
      setSubmitted(true)
    } catch {
      if (mountedRef.current) setError('No se pudo enviar la solicitud en este momento. Conservamos los datos ingresados para que puedas intentarlo nuevamente.')
    } finally {
      inFlightRef.current = false
      if (mountedRef.current) setLoading(false)
    }
  }

  return (
    <Layout>
      <Seo
        {...getStaticSeo('/cotizar')}
        ogType="website"
        robots={INDEX_ROBOTS}
      />
      <JsonLd id="quote-page" data={buildPageJsonLd('/cotizar', 'WebPage')} />
      <JsonLd id="quote-breadcrumb" data={buildBreadcrumbJsonLd(breadcrumbItems, quoteSeo.canonical)!} />
      <section className="simple-page quote-page">
        <Breadcrumb items={breadcrumbItems} />
        <h1 ref={formHeadingRef} className="quote-page__title" tabIndex={-1}>Cotizar</h1>
        <p className="quote-page__subtitle">Completa el formulario para que el equipo comercial revise los antecedentes de tu solicitud.</p>

        <div className="quote-layout">
          <aside className="quote-preview" aria-label="Resumen del producto a cotizar">
            <h2>Producto a cotizar</h2>
            {selectedProduct ? (
              <>
                <div className="quote-preview__image-wrap">
                  {selectedProductImageUrl && !imageLoadFailed ? (
                    <img
                      className="quote-preview__image"
                      src={selectedProductImageUrl}
                      alt={selectedProduct.main_image?.alt_text?.trim() || selectedProduct.name}
                      loading="lazy"
                      onError={() => setImageLoadFailed(true)}
                    />
                  ) : (
                    <div className="quote-preview__placeholder">Sin imagen disponible</div>
                  )}
                </div>
                <div className="quote-preview__meta">
                  <h3>{selectedProduct.name}</h3>
                  <p><strong>Marca:</strong> {selectedProduct.brand?.name ?? 'Sin marca'}</p>
                  <p><strong>Categoría:</strong> {selectedProduct.category?.name ?? 'Sin categoría'}</p>
                  <p><strong>Condición:</strong> {CONDITION_LABELS[selectedProduct.condition]}</p>
                  <p><strong>Disponibilidad:</strong> {STOCK_LABELS[selectedProduct.stock_status]}</p>
                  <p><strong>Precio:</strong> {selectedProduct.price_visible ? formatPrice(selectedProduct) : 'Consultar'}</p>
                  <Link className="btn btn--ghost" to={`/producto/${selectedProduct.slug}`}>
                    Ver detalle
                  </Link>
                </div>
              </>
            ) : (
              <div className="quote-preview__empty">
                {productSelectionError ? <p className="ui-note ui-note--error" role="alert">No fue posible cargar el producto seleccionado. Puedes continuar con una solicitud general.</p> : null}
                <p><strong>No hay producto seleccionado.</strong></p>
                <p>Puedes enviar una solicitud general de cotización.</p>
                {productSelectionError ? <Link to="/catalogo">Volver al catálogo</Link> : null}
              </div>
            )}
          </aside>

          {submitted ? (
            <section className="quote-confirmation" role="status" aria-labelledby="quote-confirmation-title">
              <h2 id="quote-confirmation-title" ref={confirmationHeadingRef} tabIndex={-1}>Solicitud recibida</h2>
              <p>Recibimos tu solicitud de cotización. El equipo comercial revisará los antecedentes enviados{submittedContactMethod ? ' y utilizará el medio de contacto indicado' : ''}.</p>
              {selectedProduct ? <p>Producto solicitado: <strong>{selectedProduct.name}</strong></p> : null}
              <div className="quote-confirmation__actions">
                <Link className="btn btn--ghost" to="/catalogo">Volver al catálogo</Link>
                {selectedProduct ? <Link className="btn btn--ghost" to={`/producto/${selectedProduct.slug}`}>Volver al producto</Link> : null}
                <button className="btn btn--accent" type="button" onClick={() => { setSubmitted(false); setSubmittedContactMethod(''); setError(null); setForm(initialForm); requestAnimationFrame(() => formHeadingRef.current?.focus()) }}>Enviar otra solicitud</button>
              </div>
            </section>
          ) : (
          <form className="quote-form" onSubmit={onSubmit} aria-busy={loading}>
          <label>
            Nombre
            <input
              type="text"
              autoComplete="name"
              aria-invalid={Boolean(error && !form.customer_name.trim())}
              aria-describedby={error ? 'quote-form-message' : undefined}
              value={form.customer_name}
              onChange={(event) => setForm((prev) => ({ ...prev, customer_name: event.target.value }))}
            />
          </label>
          <label>
            Teléfono
            <input
              type="tel"
              autoComplete="tel"
              inputMode="tel"
              aria-invalid={Boolean(error && !form.customer_phone.trim())}
              aria-describedby={error ? 'quote-form-message' : undefined}
              value={form.customer_phone}
              onChange={(event) => setForm((prev) => ({ ...prev, customer_phone: event.target.value }))}
            />
          </label>
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={form.customer_email}
              onChange={(event) => setForm((prev) => ({ ...prev, customer_email: event.target.value }))}
            />
          </label>
          <label>
            Empresa (opcional)
            <input
              type="text"
              autoComplete="organization"
              value={form.company_name}
              onChange={(event) => setForm((prev) => ({ ...prev, company_name: event.target.value }))}
            />
          </label>
          <label>
            Ciudad / comuna (opcional)
            <input type="text" autoComplete="address-level2" value={form.city} onChange={(event) => setForm((prev) => ({ ...prev, city: event.target.value }))} />
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
              aria-invalid={Boolean(error && !form.message.trim())}
              aria-describedby={error ? 'quote-form-message' : undefined}
            />
          </label>

          {error ? <p id="quote-form-message" className="ui-note ui-note--error" role="alert">{error}</p> : null}

            <button className="btn btn--accent" type="submit" disabled={loading}>
              {loading ? 'Enviando...' : 'Enviar'}
            </button>
          </form>
          )}
        </div>
      </section>
    </Layout>
  )
}
