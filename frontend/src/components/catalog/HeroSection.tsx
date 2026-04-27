import { Link } from 'react-router-dom'

import { usePromotions } from '../../hooks/usePromotions'
import { buildWhatsAppUrl } from '../../utils/whatsapp'

const fallbackHero = {
  tag: 'Soluciones para trabajo en altura',
  title: 'Maquinaria, elevadores y repuestos para trabajos en altura',
  subtitle:
    'Conecta directo con un vendedor especializado y cotiza equipos, repuestos o soluciones para tu operación.',
}

export function HeroSection() {
  const { promotion, error } = usePromotions()

  const content = promotion
    ? {
        tag: 'Promoción activa',
        title: promotion.title,
        subtitle: promotion.subtitle || fallbackHero.subtitle,
      }
    : fallbackHero

  return (
    <section className="hero-section">
      <p className="hero-section__tag">{content.tag}</p>
      <h1>{content.title}</h1>
      <p>{content.subtitle}</p>
      {error ? <p className="ui-note">No se pudo cargar promoción. Mostrando contenido base.</p> : null}
      <div className="hero-section__actions">
        <Link to="/" className="btn btn--accent">
          Ver catálogo
        </Link>
        <Link to="/cotizar" className="btn btn--ghost">
          Cotizar ahora
        </Link>
        <a
          className="btn btn--ghost"
          href={buildWhatsAppUrl('Hola, quiero más información sobre sus promociones vigentes.')}
          target="_blank"
          rel="noreferrer"
        >
          WhatsApp
        </a>
      </div>
    </section>
  )
}
