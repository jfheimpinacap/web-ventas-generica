import { Link } from 'react-router-dom'

import { Seo } from '../components/common/Seo'
import { JsonLd } from '../components/common/JsonLd'
import { Layout } from '../components/layout/Layout'
import { trackQuoteClick, trackWhatsAppClick } from '../utils/analytics'
import { buildPublicUrl } from '../utils/seo'
import { buildWhatsAppUrl } from '../utils/whatsapp'

const CONTACT_EMAIL = import.meta.env.VITE_CONTACT_EMAIL

export function ContactPage() {
  const contactJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'ContactPage',
    name: 'Contacto | JEM Nexus',
    url: buildPublicUrl('/contacto'),
    description:
      'Contacta a JEM Nexus para cotizar maquinaria, repuestos y servicios industriales con atención comercial personalizada.',
  }

  return (
    <Layout>
      <Seo
        title="Contacto | JEM Nexus"
        description="Contacta a JEM Nexus para cotizar maquinaria, repuestos y servicios industriales con atención comercial personalizada."
        canonical={buildPublicUrl('/contacto')}
        ogType="website"
        ogUrl={buildPublicUrl('/contacto')}
        robots="index,follow"
      />
      <JsonLd id="contact-page" data={contactJsonLd} />

      <section className="simple-page trust-page">
        <h1>Contacto</h1>
        <p>
          Comunícate con JEM Nexus para solicitar información sobre maquinaria, repuestos o servicios industriales. Un vendedor
          revisará tu solicitud y te orientará según disponibilidad, precio y requerimiento técnico.
        </p>

        <div className="trust-page__grid">
          <article className="trust-page__card">
            <h2>WhatsApp</h2>
            <p>Atención comercial directa para resolver dudas y coordinar tu cotización.</p>
            <a className="btn btn--whatsapp" href={buildWhatsAppUrl('Hola, quiero solicitar información comercial.')} target="_blank" rel="noreferrer" onClick={() => trackWhatsAppClick({ location: 'contact' })}>
              Escribir por WhatsApp
            </a>
          </article>

          <article className="trust-page__card">
            <h2>Formulario de cotización</h2>
            <p>Completa la solicitud con tu requerimiento técnico para una respuesta personalizada.</p>
            <Link className="btn btn--accent" to="/cotizar" onClick={() => trackQuoteClick({ location: 'contact' })}>
              Cotizar ahora
            </Link>
          </article>

          <article className="trust-page__card">
            <h2>Correo</h2>
            <p>{CONTACT_EMAIL ? CONTACT_EMAIL : 'Pendiente de publicación de canal de correo comercial.'}</p>
          </article>
        </div>
      </section>
    </Layout>
  )
}
