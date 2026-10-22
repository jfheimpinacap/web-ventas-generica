import { isRentalProduct } from '../utils/rental'
import { RentalRates } from '../components/catalog/RentalRates'
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'
import { INDEX_ROBOTS, Seo } from '../components/common/Seo'
import { Breadcrumb } from '../components/common/Breadcrumb'
import { JsonLd } from '../components/common/JsonLd'
import { resolveMediaUrl } from '../services/api'
import type { PreferredContactMethod, ProductDetail, ProductCondition, StockStatus } from '../types/catalog'
import { formatPrice } from '../utils/formatters'
import { trackGenerateLead } from '../utils/analytics'
import { buildBreadcrumbJsonLd, buildPageJsonLd, getStaticSeo } from '../utils/seo'
import { currentQuoteProductSelection, initialQuoteProductSelection, loadQuoteProductSelection, parseQuoteProductId, QUOTE_PRODUCT_LOADING_MESSAGE, submitQuoteRequest, type QuoteFormState, type QuoteProductSelection } from '../utils/quoteRequest'

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

export function QuoteProductPreview({ selection }: { selection: QuoteProductSelection }) {
  const product = selection.product
  const imageUrl = resolveMediaUrl(product?.main_image?.image)
  const [imageLoadFailed, setImageLoadFailed] = useState(false)
  useEffect(() => { setImageLoadFailed(false) }, [product?.id, imageUrl])

  return <aside className="quote-preview" aria-label="Resumen del producto a cotizar" aria-busy={selection.status === 'loading'}>
    <h2>Producto a cotizar</h2>
    {selection.status === 'loading' ? <p role="status">Cargando producto seleccionado...</p> : product ? <>
      <div className="quote-preview__image-wrap">
        {imageUrl && !imageLoadFailed ? <img className="quote-preview__image" src={imageUrl} alt={product.main_image?.alt_text?.trim() || product.name} loading="lazy" onError={() => setImageLoadFailed(true)} /> : <div className="quote-preview__placeholder">Sin imagen disponible</div>}
      </div>
      <div className="quote-preview__meta">
        <h3>{product.name}</h3>
        <p><strong>Marca:</strong> {product.brand?.name ?? 'Sin marca'}</p>
        <p><strong>Categoría:</strong> {product.category?.name ?? 'Sin categoría'}</p>
        {isRentalProduct(product) ? <><p>Solicitud de arriendo</p><RentalRates product={product} /></> : <>
          <p><strong>Condición:</strong> {CONDITION_LABELS[product.condition]}</p>
          <p><strong>Disponibilidad:</strong> {STOCK_LABELS[product.stock_status]}</p>
          <p><strong>Precio:</strong> {product.price_visible ? formatPrice(product) : 'Consultar'}</p>
        </>}
        <Link className="btn btn--ghost" to={`/producto/${product.slug}`}>Ver detalle</Link>
      </div>
    </> : <div className="quote-preview__empty">
      {selection.status === 'unavailable' ? <p className="ui-note ui-note--error" role="alert">No fue posible cargar el producto seleccionado. Puedes continuar con una solicitud general.</p> : null}
      <p><strong>No hay producto seleccionado.</strong></p>
      <p>Puedes enviar una solicitud general de cotización.</p>
      {selection.status === 'unavailable' ? <Link to="/catalogo">Volver al catálogo</Link> : null}
    </div>}
  </aside>
}

export function QuotePage() {
  const quoteSeo = getStaticSeo('/cotizar')
  const breadcrumbItems = [{ label: 'Inicio', to: '/' }, { label: 'Cotizar' }]
  const [searchParams] = useSearchParams()
  const productFromQuery = useMemo(() => parseQuoteProductId(searchParams.get('product')), [searchParams])

  const [loadedSelection, setLoadedSelection] = useState(() => initialQuoteProductSelection(productFromQuery))
  const productSelection = currentQuoteProductSelection(productFromQuery, loadedSelection)
  const selectedProduct = productSelection.product
  const productLoading = productSelection.status === 'loading'
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [submittedProduct, setSubmittedProduct] = useState<ProductDetail | null>(null)
  const [submittedContactMethod, setSubmittedContactMethod] = useState<PreferredContactMethod | ''>('')
  const inFlightRef = useRef(false)
  const mountedRef = useRef(true)
  const confirmationHeadingRef = useRef<HTMLHeadingElement>(null)
  const formHeadingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false } }, [])
  useEffect(() => { if (submitted) confirmationHeadingRef.current?.focus() }, [submitted])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [productFromQuery])

  useEffect(() => loadQuoteProductSelection(productFromQuery, setLoadedSelection), [productFromQuery])

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
    if (productLoading) { setError(QUOTE_PRODUCT_LOADING_MESSAGE); return }

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    inFlightRef.current = true
    try {
      setLoading(true)
      await submitQuoteRequest(form, productSelection)
      if (!mountedRef.current) return
      trackGenerateLead({
        product_id: selectedProduct?.id,
        product_name: selectedProduct?.name,
        preferred_contact_method: form.preferred_contact_method || undefined,
      })
      setSubmittedContactMethod(form.preferred_contact_method)
      setSubmittedProduct(selectedProduct)
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
          <QuoteProductPreview selection={productSelection} />

          {submitted ? (
            <section className="quote-confirmation" role="status" aria-labelledby="quote-confirmation-title">
              <h2 id="quote-confirmation-title" ref={confirmationHeadingRef} tabIndex={-1}>Solicitud recibida</h2>
              <p>Recibimos tu solicitud de cotización. El equipo comercial revisará los antecedentes enviados{submittedContactMethod ? ' y utilizará el medio de contacto indicado' : ''}.</p>
              {submittedProduct ? <p>Producto solicitado: <strong>{submittedProduct.name}</strong></p> : null}
              <div className="quote-confirmation__actions">
                <Link className="btn btn--ghost" to="/catalogo">Volver al catálogo</Link>
                {submittedProduct ? <Link className="btn btn--ghost" to={`/producto/${submittedProduct.slug}`}>Volver al producto</Link> : null}
                <button className="btn btn--accent" type="button" onClick={() => { setSubmitted(false); setSubmittedProduct(null); setSubmittedContactMethod(''); setError(null); setForm(initialForm); requestAnimationFrame(() => formHeadingRef.current?.focus()) }}>Enviar otra solicitud</button>
              </div>
            </section>
          ) : (
          <form className="quote-form" onSubmit={onSubmit} aria-busy={loading || productLoading}>
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

            <button className="btn btn--accent" type="submit" disabled={loading || productLoading}>
              {loading ? 'Enviando...' : productLoading ? 'Cargando producto...' : 'Enviar'}
            </button>
          </form>
          )}
        </div>
      </section>
    </Layout>
  )
}
