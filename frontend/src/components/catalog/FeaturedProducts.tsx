import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { ProductCard } from './ProductCard'
import { useProducts } from '../../hooks/useProducts'
import { getHomeSectionItems } from '../../services/catalogApi'
import { resolveMediaUrl } from '../../services/api'
import type { HomeSectionItem } from '../../types/catalog'
import { formatPrice } from '../../utils/formatters'
import { trackProductDetailClick } from '../../utils/analytics'

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'
const DESKTOP_CAROUSEL_GROUP_SIZE = 4
const MOBILE_CAROUSEL_GROUP_SIZE = 2
const MOBILE_BREAKPOINT = 768

function fromSection(items: HomeSectionItem[], section: HomeSectionItem['section']) {
  return items.filter((item) => item.section === section).sort((a, b) => a.position - b.position).map((item) => item.product)
}

export function FeaturedProducts() {
  const { products, loading, error } = useProducts()
  const [homeItems, setHomeItems] = useState<HomeSectionItem[]>([])
  const [homeConfigError, setHomeConfigError] = useState(false)
  const [carouselIndex, setCarouselIndex] = useState(0)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const run = async () => {
      try {
        setHomeItems(await getHomeSectionItems())
      } catch {
        setHomeConfigError(true)
      }
    }

    void run()
  }, [])

  const sourceProducts = !loading && !error ? products : []

  const carouselGroupSize = isMobile ? MOBILE_CAROUSEL_GROUP_SIZE : DESKTOP_CAROUSEL_GROUP_SIZE

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT)

    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])


  const machineryConfigured = useMemo(() => fromSection(homeItems, 'machinery_promotions'), [homeItems])
  const sparePartsConfigured = useMemo(() => fromSection(homeItems, 'spare_parts_offers'), [homeItems])
  const servicesConfigured = useMemo(() => fromSection(homeItems, 'repair_services'), [homeItems])

  const machineryProducts = useMemo(
    () => (machineryConfigured.length > 0 ? machineryConfigured.slice(0, 12) : sourceProducts.filter((product) => product.product_type === 'machinery').slice(0, 12)),
    [machineryConfigured, sourceProducts],
  )
  const sparePartsDisplayCount = isMobile ? 4 : 6

  const sparePartProducts = useMemo(() => {
    const automaticProducts = sourceProducts.filter((product) => product.product_type === 'spare_part').slice(0, sparePartsDisplayCount)

    if (sparePartsConfigured.length === 0) {
      return automaticProducts
    }

    const configuredIds = new Set(sparePartsConfigured.map((product) => product.id))
    const fallbackProducts = automaticProducts.filter((product) => !configuredIds.has(product.id))

    return [...sparePartsConfigured, ...fallbackProducts].slice(0, sparePartsDisplayCount)
  }, [sparePartsConfigured, sourceProducts, sparePartsDisplayCount])

  const serviceProducts = useMemo(
    () => (servicesConfigured.length > 0 ? servicesConfigured.slice(0, 4) : sourceProducts.filter((product) => product.product_type === 'service').slice(0, 4)),
    [servicesConfigured, sourceProducts],
  )

  const machineryGroups = useMemo(() => {
    return Array.from({ length: Math.ceil(machineryProducts.length / carouselGroupSize) }, (_, index) =>
      machineryProducts.slice(index * carouselGroupSize, index * carouselGroupSize + carouselGroupSize),
    )
  }, [carouselGroupSize, machineryProducts])

  useEffect(() => {
    setCarouselIndex((current) => Math.min(current, Math.max(0, machineryGroups.length - 1)))
  }, [machineryGroups.length])

  useEffect(() => {
    if (machineryGroups.length <= 1) return

    const intervalId = window.setInterval(() => {
      setCarouselIndex((prev) => (prev + 1) % machineryGroups.length)
    }, 5000)

    return () => window.clearInterval(intervalId)
  }, [machineryGroups.length])

  const goPrev = () => {
    if (machineryGroups.length === 0) return
    setCarouselIndex((prev) => (prev - 1 + machineryGroups.length) % machineryGroups.length)
  }
  const goNext = () => {
    if (machineryGroups.length === 0) return
    setCarouselIndex((prev) => (prev + 1) % machineryGroups.length)
  }

  return (
    <div className="home-commercial-sections">
      <section className="featured-products">
        <div className="section-heading">
          <h2>Promociones en maquinarias</h2>
        </div>

        {loading ? <p className="ui-note">Cargando productos...</p> : null}
        {!loading && error ? <p className="ui-note ui-note--error">{error}</p> : null}
        {homeConfigError ? <p className="ui-note">Usando selección automática para la Home.</p> : null}

        <div className="machinery-carousel" aria-label="Carrusel manual de maquinarias en promoción">
          <button className="carousel-control carousel-control--prev" type="button" onClick={goPrev} aria-label="Ver maquinarias anteriores">
            ‹
          </button>

          <div className="machinery-carousel__viewport">
            <div className="machinery-carousel__track" style={{ transform: `translateX(-${carouselIndex * 100}%)` }}>
              {machineryGroups.map((group, groupIndex) => (
                <div className="machinery-carousel__slide" key={`machinery-group-${groupIndex}`}>
                  {group.map((product) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      promotionalLabel="Destacada"
                      trackingLocation="machinery_promotions"
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>

          <button className="carousel-control carousel-control--next" type="button" onClick={goNext} aria-label="Ver más maquinarias">
            ›
          </button>
        </div>

        <div className="home-section__more">
          <Link className="btn btn--outline" to="/maquinaria-nueva">
            Ver maquinaria nueva
          </Link>
        </div>
      </section>

      <section className="spare-offers">
        <div className="section-heading">
          <h2>Oferta en repuestos</h2>
        </div>

        <div className="spare-offers__grid">
          {sparePartProducts.map((product, index) => {
            const imageUrl = resolveMediaUrl(product?.main_image?.image) || PLACEHOLDER_IMAGE
            return (
              <article key={product.id} className={`spare-offer-card ${index === 0 || index === 5 ? 'spare-offer-card--large' : ''}`}>
                <Link className="spare-offer-card__image-link" to={`/producto/${product.slug}`} aria-label={`Ver detalle de ${product.name}`}>
                  <img src={imageUrl} alt={product?.main_image?.alt_text || product.name} loading="lazy" />
                </Link>
                <div className="spare-offer-card__content">
                  <span>Oferta destacada</span>
                  <h3>{product.name}</h3>
                  <p className="home-product-price">{formatPrice(product) || 'Consulta precio y disponibilidad'}</p>
                  {product.slug ? (
                    <Link className="btn btn--accent" to={`/producto/${product.slug}`} onClick={() => trackProductDetailClick({ product_id: product.id, product_name: product.name, location: 'spare_offers' })}>
                      Ver detalle
                    </Link>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
        <div className="home-section__more">
          <Link className="btn btn--outline" to="/repuestos">
            Ver repuestos
          </Link>
        </div>
      </section>

      <section className="repair-services">
        <div className="section-heading">
          <h2>Servicios de reparación</h2>
        </div>

        <div className="repair-services__grid">
          {serviceProducts.map((product, index) => {
            const imageUrl = resolveMediaUrl(product.main_image?.image) || PLACEHOLDER_IMAGE

            return (
              <article className="repair-service-card" key={`${product.slug}-${index}`}>
                <Link className="repair-service-card__image-link" to={`/producto/${product.slug}`} aria-label={`Ver detalle de ${product.name}`}>
                  <img src={imageUrl} alt={product.main_image?.alt_text || product.name} loading="lazy" />
                </Link>
                <div>
                  <h3>{product.name}</h3>
                  <p>{product.short_description || 'Servicio técnico especializado para equipos de elevación.'}</p>
                  <p className="home-product-price">{formatPrice(product) || 'Consulta precio y disponibilidad'}</p>
                  {product.slug ? (
                    <Link className="btn btn--accent" to={`/producto/${product.slug}`} onClick={() => trackProductDetailClick({ product_id: product.id, product_name: product.name, location: 'repair_services' })}>
                      Ver detalle
                    </Link>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
        <div className="home-section__more">
          <Link className="btn btn--outline" to="/servicios">
            Ver servicios
          </Link>
        </div>
      </section>
    </div>
  )
}
