import { Layout } from '../components/layout/Layout'
import { JsonLd } from '../components/common/JsonLd'
import { Seo } from '../components/common/Seo'
import { buildPublicUrl } from '../utils/seo'

const FAQS = [
  {
    q: '¿Cómo solicito una cotización?',
    a: 'Puedes ingresar al detalle de un producto y presionar “Cotizar”, o completar el formulario general de cotización indicando el equipo, repuesto o servicio que necesitas.',
  },
  {
    q: '¿Los precios publicados son finales?',
    a: 'Los precios pueden estar sujetos a disponibilidad, condición del producto, plazo de entrega y validación comercial. Cuando un producto aparece como “Consultar”, el vendedor confirmará el precio al responder la solicitud.',
  },
  {
    q: '¿Puedo cotizar repuestos específicos?',
    a: 'Sí. Puedes buscar repuestos por categoría, marca o nombre, y enviar una solicitud indicando el modelo o equipo asociado.',
  },
  {
    q: '¿Qué tipo de maquinaria puedo cotizar?',
    a: 'Puedes cotizar maquinaria para trabajos en altura y operación industrial, como elevadores tipo tijera, brazos articulados y otros equipos publicados.',
  },
  {
    q: '¿Ofrecen servicios de reparación?',
    a: 'Sí. La plataforma incluye servicios asociados a reparación y mantención de componentes industriales, según disponibilidad y evaluación técnica.',
  },
  {
    q: '¿Cómo me contactarán después de enviar una solicitud?',
    a: 'El vendedor podrá responder por teléfono, WhatsApp o correo electrónico, según el método de contacto indicado en el formulario.',
  },
]

export function FaqPage() {
  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQS.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.a,
      },
    })),
  }

  return (
    <Layout>
      <Seo
        title="Preguntas frecuentes | JEM Nexus"
        description="Resuelve dudas sobre cotización de maquinaria, repuestos, servicios industriales, precios, disponibilidad y contacto con JEM Nexus."
        canonical={buildPublicUrl('/preguntas-frecuentes')}
        ogType="website"
        ogUrl={buildPublicUrl('/preguntas-frecuentes')}
        robots="index,follow"
      />
      <JsonLd id="faq-page" data={faqJsonLd} />

      <section className="simple-page trust-page">
        <h1>Preguntas frecuentes</h1>
        <div className="trust-page__faq-list">
          {FAQS.map((item) => (
            <article className="trust-page__faq-item" key={item.q}>
              <h2>{item.q}</h2>
              <p>{item.a}</p>
            </article>
          ))}
        </div>
      </section>
    </Layout>
  )
}
