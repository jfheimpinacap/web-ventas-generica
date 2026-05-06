import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { usePromotions } from '../../hooks/usePromotions'
import { resolveMediaUrl } from '../../services/api'
import type { Promotion } from '../../types/catalog'

const AUTO_ADVANCE_MS = 6000
const FALLBACK_IMAGE = 'https://placehold.co/1200x700/111827/F3F4F6?text=Promociones+Industriales'

const fallbackSlides: Promotion[] = [
  {
    id: 0,
    title: 'Maquinaria y repuestos para operación continua',
    subtitle:
      'Conecta con un vendedor especializado para cotizar equipos, repuestos y soluciones en altura de forma rápida.',
    product: null,
    image: null,
    button_text: 'Ver productos',
    button_url: '/catalogo',
    is_active: true,
    order: 0,
    starts_at: null,
    ends_at: null,
    created_at: '',
    updated_at: '',
  },
]

function resolvePromotionUrl(promotion: Promotion) {
  if (promotion.button_url?.trim()) return promotion.button_url.trim()
  if (promotion.product) return `/producto/${promotion.product.slug}`
  return '/catalogo'
}

function isExternalUrl(url: string) {
  return /^https?:\/\//i.test(url)
}

export function HeroSection() {
  const { promotions, error } = usePromotions()
  const slides = promotions.length > 0 ? promotions : fallbackSlides
  const [currentIndex, setCurrentIndex] = useState(0)

  useEffect(() => {
    setCurrentIndex(0)
  }, [slides.length])

  useEffect(() => {
    if (slides.length <= 1) return

    const timer = window.setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % slides.length)
    }, AUTO_ADVANCE_MS)

    return () => window.clearInterval(timer)
  }, [slides.length])

  const currentSlide = slides[currentIndex]
  const imageUrl = resolveMediaUrl(currentSlide.image) || FALLBACK_IMAGE
  const ctaUrl = resolvePromotionUrl(currentSlide)
  const externalCta = isExternalUrl(ctaUrl)

  const badges = useMemo(() => {
    const tags = ['Oferta vigente', 'Cotización rápida']
    if (currentSlide.product) {
      tags.unshift('Producto destacado')
    }
    return tags
  }, [currentSlide.product])

  return (
    <section className="hero-section" aria-label="Promociones destacadas">
      <div className="hero-section__content">
        <div className="hero-section__badges" aria-label="Etiquetas de promoción">
          {badges.map((badge) => (
            <span key={badge} className="hero-badge">
              {badge}
            </span>
          ))}
        </div>
        <p className="hero-section__tag">Promociones comerciales</p>
        <h1>{currentSlide.title}</h1>
        <p className="hero-section__subtitle">
          {currentSlide.subtitle || 'Consulta disponibilidad y tiempos de entrega con nuestro equipo comercial.'}
        </p>
        {currentSlide.product ? (
          <p className="hero-section__product">Producto asociado: {currentSlide.product.name}</p>
        ) : null}
        {error ? <p className="ui-note">No se pudo cargar la API de promociones. Mostrando contenido base.</p> : null}

        <div className="hero-section__actions">
          <Link to="/catalogo" className="btn btn--accent">
            Ver productos
          </Link>
          <Link to="/cotizar" className="btn btn--ghost">
            Cotizar ahora
          </Link>
          {externalCta ? (
            <a className="btn btn--ghost" href={ctaUrl} target="_blank" rel="noreferrer">
              {currentSlide.button_text || 'Ver promoción'}
            </a>
          ) : (
            <Link className="btn btn--ghost" to={ctaUrl}>
              {currentSlide.button_text || 'Ver promoción'}
            </Link>
          )}
        </div>
      </div>

      <div className="hero-section__media">
        <img src={imageUrl} alt={currentSlide.title} />
      </div>

      {slides.length > 1 ? (
        <>
          <button
            type="button"
            className="hero-control hero-control--prev"
            aria-label="Promoción anterior"
            onClick={() => setCurrentIndex((prev) => (prev - 1 + slides.length) % slides.length)}
          >
            ‹
          </button>
          <button
            type="button"
            className="hero-control hero-control--next"
            aria-label="Promoción siguiente"
            onClick={() => setCurrentIndex((prev) => (prev + 1) % slides.length)}
          >
            ›
          </button>
          <div className="hero-section__dots" role="tablist" aria-label="Indicadores de promociones">
            {slides.map((slide, index) => (
              <button
                key={slide.id}
                type="button"
                className={`hero-dot ${currentIndex === index ? 'hero-dot--active' : ''}`}
                aria-label={`Ver promoción ${index + 1}`}
                aria-selected={currentIndex === index}
                onClick={() => setCurrentIndex(index)}
              />
            ))}
          </div>
        </>
      ) : null}
    </section>
  )
}
