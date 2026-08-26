import { Link } from 'react-router-dom'

import { INDEX_ROBOTS, Seo } from '../components/common/Seo'
import { JsonLd } from '../components/common/JsonLd'
import { Breadcrumb } from '../components/common/Breadcrumb'
import { Layout } from '../components/layout/Layout'
import { trackQuoteClick, trackWhatsAppClick } from '../utils/analytics'
import { buildBreadcrumbJsonLd, buildPageJsonLd, getStaticSeo } from '../utils/seo'
import { buildWhatsAppUrl } from '../utils/whatsapp'

const CONTACT_EMAIL =
  import.meta.env.VITE_CONTACT_EMAIL?.trim() ||
  'jmateluna@jem-nexus.cl'

export function ContactPage() {
  const seo = getStaticSeo('/contacto')
  const items = [{ label: 'Inicio', to: '/' }, { label: 'Contacto' }]
  const contactJsonLd = buildPageJsonLd('/contacto', 'ContactPage')
  const breadcrumbJsonLd = buildBreadcrumbJsonLd(items, seo.canonical)

  return (
    <Layout>
      <Seo
        {...getStaticSeo('/contacto')}
        ogType="website"
        robots={INDEX_ROBOTS}
      />
      <JsonLd id="contact-page" data={contactJsonLd} />
      {breadcrumbJsonLd ? <JsonLd id="contact-breadcrumb" data={breadcrumbJsonLd} /> : null}

      <section className="simple-page trust-page">
        <Breadcrumb items={items} />
        <h1>Contacto</h1>
        <p>
          Comunícate con JEM Nexus para solicitar información sobre maquinaria, repuestos o servicios industriales. Un vendedor
          revisará tu solicitud y te orientará según disponibilidad, precio y requerimiento técnico.
        </p>

        <div className="trust-page__grid">
          <article className="trust-page__card contact-page__card">
            <h2>WhatsApp</h2>
            <p>Atención comercial directa para resolver dudas y coordinar tu cotización.</p>
            <a className="btn btn--whatsapp contact-page__action" href={buildWhatsAppUrl('Hola, quiero solicitar información comercial.')} target="_blank" rel="noreferrer" onClick={() => trackWhatsAppClick({ location: 'contact' })}>
              Escribir por WhatsApp
            </a>
          </article>

          <article className="trust-page__card contact-page__card">
            <h2>Formulario de cotización</h2>
            <p>Completa la solicitud con tu requerimiento técnico para una respuesta personalizada.</p>
            <Link className="btn btn--accent contact-page__action" to="/cotizar" onClick={() => trackQuoteClick({ location: 'contact' })}>
              Cotizar ahora
            </Link>
          </article>

          <article className="trust-page__card contact-page__card">
            <h2>Correo</h2>
            <p>
              <a className="contact-page__email" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </p>
          </article>
        </div>
      </section>
    </Layout>
  )
}
