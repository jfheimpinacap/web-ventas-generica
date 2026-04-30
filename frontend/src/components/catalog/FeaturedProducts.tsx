import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { mockProducts } from '../../data/mockProducts'
import { useProducts } from '../../hooks/useProducts'
import { getHomeSectionItems } from '../../services/catalogApi'
import { resolveMediaUrl } from '../../services/api'
import type { HomeSectionItem, ProductListItem, ProductType } from '../../types/catalog'
import { formatPrice } from '../../utils/formatters'

const PLACEHOLDER_IMAGE = 'https://placehold.co/600x400/111827/F3F4F6?text=Producto'
const CAROUSEL_GROUP_SIZE = 4

function buildFallbackProducts(type: ProductType, count: number, titleBase: string): ProductListItem[] {
  return Array.from({ length: count }, (_, index) => {
    const template = mockProducts[index % mockProducts.length]

    return {
      ...template,
      id: 9000 + index,
      slug: `${titleBase.toLowerCase().replace(/\s+/g, '-')}-${index + 1}`,
      name: `${titleBase} ${index + 1}`,
      product_type: type,
      category: {
        ...template.category,
        id: 8000 + index,
      },
      brand: template.brand
        ? {
            ...template.brand,
            id: 7000 + index,
          }
        : null,
    }
  })
}

function pickProducts(source: ProductListItem[], type: ProductType, count: number, titleBase: string) {
  const filtered = source.filter((product) => product.product_type === type)

  if (filtered.length >= count) {
    return filtered.slice(0, count)
  }

  const fallback = buildFallbackProducts(type, count - filtered.length, titleBase)
  return [...filtered, ...fallback]
}

function fromSection(items: HomeSectionItem[], section: HomeSectionItem['section']) {
  return items.filter((item) => item.section === section).sort((a, b) => a.position - b.position).map((item) => item.product)
}

export function FeaturedProducts() {
  const { products, loading, error } = useProducts()
  const [homeItems, setHomeItems] = useState<HomeSectionItem[]>([])
  const [homeConfigError, setHomeConfigError] = useState(false)
  const [carouselIndex, setCarouselIndex] = useState(0)

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

  const sourceProducts = !loading && !error && products.length > 0 ? products : mockProducts

  const machineryConfigured = useMemo(() => fromSection(homeItems, 'machinery_promotions'), [homeItems])
  const sparePartsConfigured = useMemo(() => fromSection(homeItems, 'spare_parts_offers'), [homeItems])
  const servicesConfigured = useMemo(() => fromSection(homeItems, 'repair_services'), [homeItems])

  const machineryProducts = useMemo(
    () => (machineryConfigured.length > 0 ? machineryConfigured.slice(0, 12) : pickProducts(sourceProducts, 'machinery', 12, 'Maquinaria promocional')),
    [machineryConfigured, sourceProducts],
  )
  const sparePartProducts = useMemo(
    () => (sparePartsConfigured.length > 0 ? sparePartsConfigured.slice(0, 6) : pickProducts(sourceProducts, 'spare_part', 6, 'Repuesto en oferta')),
    [sparePartsConfigured, sourceProducts],
  )

  const serviceProducts = useMemo(
    () => (servicesConfigured.length > 0 ? servicesConfigured : pickProducts(sourceProducts, 'service', 4, 'Servicio de reparación')),
    [servicesConfigured, sourceProducts],
  )

  const machineryGroups = useMemo(() => {
    return Array.from({ length: Math.ceil(machineryProducts.length / CAROUSEL_GROUP_SIZE) }, (_, index) =>
      machineryProducts.slice(index * CAROUSEL_GROUP_SIZE, index * CAROUSEL_GROUP_SIZE + CAROUSEL_GROUP_SIZE),
    )
  }, [machineryProducts])

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
        {!loading && error ? <p className="ui-note ui-note--error">{error} Mostrando respaldo local.</p> : null}
        {homeConfigError ? <p className="ui-note">Usando selección automática para la Home.</p> : null}

        <div className="machinery-carousel" aria-label="Carrusel manual de maquinarias en promoción">
          <button className="carousel-control carousel-control--prev" type="button" onClick={goPrev} aria-label="Ver maquinarias anteriores">
            ‹
          </button>

          <div className="machinery-carousel__viewport">
            <div className="machinery-carousel__track" style={{ transform: `translateX(-${carouselIndex * 100}%)` }}>
              {machineryGroups.map((group, groupIndex) => (
                <div className="machinery-carousel__slide" key={`machinery-group-${groupIndex}`}>
                  {group.map((product) => {
                    const imageUrl = resolveMediaUrl(product.main_image?.image) || PLACEHOLDER_IMAGE
                    return (
                      <article className="promo-product-card" key={product.id}>
                        <img src={imageUrl} alt={product.main_image?.alt_text || product.name} loading="lazy" />
                        <div className="promo-product-card__content">
                          <p className="promo-product-card__tag">Maquinaria destacada</p>
                          <h3>{product.name}</h3>
                          <p className="promo-product-card__price home-product-price">{formatPrice(product)}</p>
                          {product.slug ? (
                            <Link className="btn btn--accent" to={`/producto/${product.slug}`}>
                              Ver detalle
                            </Link>
                          ) : (
                            <span className="btn btn--accent btn--disabled" aria-disabled="true">
                              Ver detalle
                            </span>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>

          <button className="carousel-control carousel-control--next" type="button" onClick={goNext} aria-label="Ver más maquinarias">
            ›
          </button>
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
                <img src={imageUrl} alt={product?.main_image?.alt_text || product.name} loading="lazy" />
                <div className="spare-offer-card__content">
                  <span>Oferta destacada</span>
                  <h3>{product.name}</h3>
                  <p className="home-product-price">{formatPrice(product) || 'Consulta precio y disponibilidad'}</p>
                  {product.slug ? (
                    <Link className="btn btn--accent" to={`/producto/${product.slug}`}>
                      Ver detalle
                    </Link>
                  ) : null}
                </div>
              </article>
            )
          })}
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
                <img src={imageUrl} alt={product.name} loading="lazy" />
                <div>
                  <h3>{product.name}</h3>
                  <p>{product.short_description || 'Servicio técnico especializado para equipos de elevación.'}</p>
                  <p className="home-product-price">{formatPrice(product) || 'Consulta precio y disponibilidad'}</p>
                  {product.slug ? (
                    <Link className="btn btn--accent" to={`/producto/${product.slug}`}>
                      Ver detalle
                    </Link>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
      </section>
    </div>
  )
}
