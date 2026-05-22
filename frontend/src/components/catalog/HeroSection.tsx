import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useCategories } from '../../hooks/useCategories'
import { usePromotions } from '../../hooks/usePromotions'
import { resolveMediaUrl } from '../../services/api'
import type { Category, Promotion } from '../../types/catalog'
import { trackHeroOfferClick } from '../../utils/analytics'

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
    button_text: '',
    button_url: '',
    is_active: true,
    order: 0,
    starts_at: null,
    ends_at: null,
    created_at: '',
    updated_at: '',
  },
]

function getRootCategory(category: Category | null | undefined, categories: Category[]) {
  if (!category) return null

  const byId = new Map(categories.map((item) => [item.id, item]))
  const visited = new Set<number>()

  let current: Category | null = category
  while (current?.parent != null) {
    if (visited.has(current.id)) break
    visited.add(current.id)
    const next = byId.get(current.parent)
    if (!next) break
    current = next
  }

  return current
}

function resolveCatalogCategoryLink(promotion: Promotion, categories: Category[]) {
  if (!promotion.product?.category) {
    return { to: '/catalogo', label: 'Ver catálogo' }
  }

  const rootCategory = getRootCategory(promotion.product.category, categories)
  if (!rootCategory) {
    return { to: '/catalogo', label: 'Ver catálogo' }
  }

  return {
    to: `/catalogo?category=${rootCategory.id}`,
    label: `Ver categoría ${rootCategory.name}`,
  }
}

export function HeroSection() {
  const { promotions, error } = usePromotions()
  const { categories } = useCategories()
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
  const categoryLink = useMemo(() => resolveCatalogCategoryLink(currentSlide, categories), [currentSlide, categories])
  const isClickable = Boolean(currentSlide.product)

  return (
    <section className="hero-section" aria-label="Promociones destacadas">
      <div className="hero-section__content">
        <h1>{currentSlide.title}</h1>
        <p className="hero-section__subtitle">
          {currentSlide.subtitle || 'Consulta disponibilidad y tiempos de entrega con nuestro equipo comercial.'}
        </p>
        {currentSlide.product ? (
          <p className="hero-section__product">Producto asociado: {currentSlide.product.name}</p>
        ) : null}
        {error ? <p className="ui-note">No se pudo cargar la API de promociones. Mostrando contenido base.</p> : null}
      </div>

      <div className="hero-section__media">
        {isClickable ? (
          <Link
            to={categoryLink.to}
            aria-label={categoryLink.label}
            className="hero-section__media-link"
            onClick={() =>
              trackHeroOfferClick({
                promotion_id: currentSlide.id,
                product_id: currentSlide.product?.id,
                category_name: currentSlide.product?.category?.name,
              })
            }
          >
            <img src={imageUrl} alt={currentSlide.title || 'Imagen de promoción'} />
          </Link>
        ) : (
          <img src={imageUrl} alt={currentSlide.title || 'Imagen de promoción'} />
        )}
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
