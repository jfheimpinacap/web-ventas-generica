import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { Breadcrumb, type BreadcrumbItem } from '../components/common/Breadcrumb'
import { JsonLd } from '../components/common/JsonLd'
import { Seo } from '../components/common/Seo'
import { Layout } from '../components/layout/Layout'
import { useBrands } from '../hooks/useBrands'
import { useCatalogProducts } from '../hooks/useCatalogProducts'
import { useCategories } from '../hooks/useCategories'
import type { Category, ProductListItem, ProductQueryParams } from '../types/catalog'
import { trackCategoryView } from '../utils/analytics'
import { buildBreadcrumbJsonLd, buildItemListJsonLd, buildPublicUrl } from '../utils/seo'

const ORDER_OPTIONS = [
  { value: 'recommended', label: 'Recomendados' },
  { value: 'price', label: 'Precio: menor a mayor' },
  { value: '-price', label: 'Precio: mayor a menor' },
]

const FILTER_LABELS: Record<string, Record<string, string>> = {
  product_type: {
    machinery: 'Maquinaria',
    spare_part: 'Repuestos',
    service: 'Servicios',
    other: 'Otros',
  },
  condition: {
    new: 'Nuevo',
    used: 'Usado',
    refurbished: 'Reacondicionado',
    not_applicable: 'No aplica',
  },
  stock_status: {
    available: 'Stock disponible',
    on_request: 'Stock a pedido',
    reserved: 'Stock reservado',
    sold: 'Stock vendido',
  },
}


const MAIN_CATEGORY_SEO_CONTENT: Record<'maquinaria' | 'repuestos' | 'servicios', { title: string; description: string; metaDescription: string }> = {
  maquinaria: {
    title: 'Maquinaria',
    description:
      'Encuentra maquinaria para trabajos en altura y operación industrial, incluyendo elevadores tipo tijera, brazos articulados y equipos seleccionados para cotización comercial. Revisa disponibilidad, características y solicita precio con atención personalizada.',
    metaDescription:
      'Cotiza maquinaria para trabajos en altura, elevadores tipo tijera y brazos articulados con atención comercial personalizada.',
  },
  repuestos: {
    title: 'Repuestos',
    description:
      'Cotiza repuestos industriales para equipos de elevación y maquinaria, como baterías, ruedas, controles, cargadores y componentes críticos. Te ayudamos a identificar disponibilidad y alternativas compatibles.',
    metaDescription:
      'Cotiza repuestos industriales para maquinaria de elevación: baterías, ruedas, controles, cargadores y componentes críticos.',
  },
  servicios: {
    title: 'Servicios',
    description:
      'Solicita servicios de reparación y mantención para componentes industriales, motores eléctricos, bombas y equipos asociados. Revisa opciones disponibles y envía una solicitud de cotización.',
    metaDescription:
      'Solicita servicios de reparación y mantención industrial para motores eléctricos, bombas y equipos asociados.',
  },
}

function normalizeLabel(value: string) {
  return value
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim()
    .toLowerCase()
}

function getNumericPrice(product: ProductListItem) {
  if (!product.price_visible || !product.price) return null
  const parsedPrice = Number(product.price)
  return Number.isNaN(parsedPrice) ? null : parsedPrice
}

export function CatalogPage() {
  const PRODUCTS_PER_PAGE = 12
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const { categories } = useCategories()
  const { brands } = useBrands()

  const query = useMemo<ProductQueryParams>(
    () => ({
      search: searchParams.get('search') ?? '',
      category: searchParams.get('category') ?? '',
      brand: searchParams.get('brand') ?? '',
      product_type: (searchParams.get('product_type') as ProductQueryParams['product_type']) ?? '',
      condition: (searchParams.get('condition') as ProductQueryParams['condition']) ?? '',
      stock_status: (searchParams.get('stock_status') as ProductQueryParams['stock_status']) ?? '',
      ordering: (searchParams.get('ordering') as ProductQueryParams['ordering']) ?? '',
    }),
    [searchParams],
  )

  const { products, loading, error } = useCatalogProducts(query)
  const [currentPage, setCurrentPage] = useState(1)
  const headingRef = useRef<HTMLDivElement | null>(null)

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value || value === 'recommended') next.delete(key)
    else next.set(key, value)
    setSearchParams(next)
  }

  useEffect(() => {
    setCurrentPage(1)
  }, [query.search, query.category, query.brand, query.product_type, query.condition, query.stock_status, query.ordering])
  const selectedCategory = useMemo(() => {
    const categoryId = Number(query.category)
    if (!categoryId) return null
    return categories.find((category) => category.id === categoryId) ?? null
  }, [categories, query.category])

  const categoryPath = useMemo(() => {
    if (!selectedCategory) return [] as Category[]

    const categoryById = new Map(categories.map((category) => [category.id, category]))
    const path: Category[] = []
    let current: Category | null = selectedCategory

    while (current) {
      path.unshift(current)
      current = current.parent ? categoryById.get(current.parent) ?? null : null
    }

    return path
  }, [categories, selectedCategory])

  const selectedBrand = useMemo(() => {
    const brandId = Number(query.brand)
    if (!brandId) return null
    return brands.find((brand) => brand.id === brandId) ?? null
  }, [brands, query.brand])

  const extraFilterTrail = useMemo(() => {
    const trail: string[] = []
    ;(['product_type', 'condition', 'stock_status'] as const).forEach((key) => {
      const value = query[key]
      if (value) {
        trail.push(FILTER_LABELS[key][value] ?? value)
      }
    })

    if (query.search) {
      trail.push(`Búsqueda: ${query.search}`)
    }

    return trail
  }, [query])


  const mainCategorySeo = useMemo(() => {
    const rootCategory = categoryPath[0]
    const normalizedRoot = rootCategory ? normalizeLabel(rootCategory.name) : ''

    if (normalizedRoot === 'maquinaria') return MAIN_CATEGORY_SEO_CONTENT.maquinaria
    if (normalizedRoot === 'repuestos') return MAIN_CATEGORY_SEO_CONTENT.repuestos
    if (normalizedRoot === 'servicios') return MAIN_CATEGORY_SEO_CONTENT.servicios

    if (query.product_type === 'machinery') return MAIN_CATEGORY_SEO_CONTENT.maquinaria
    if (query.product_type === 'spare_part') return MAIN_CATEGORY_SEO_CONTENT.repuestos
    if (query.product_type === 'service') return MAIN_CATEGORY_SEO_CONTENT.servicios

    return null
  }, [categoryPath, query.product_type])

  const hasSearch = Boolean((query.search ?? '').trim())
  const hasSpecificFilters = Boolean(query.brand || query.condition || query.stock_status || query.ordering)
  const searchOnlyView = hasSearch && !query.category && !query.product_type && !hasSpecificFilters
  const seoTitle = selectedCategory ? `${selectedCategory.name} | JEM Nexus` : 'Productos industriales | JEM Nexus'
  const seoDescription = mainCategorySeo
    ? mainCategorySeo.metaDescription
    : selectedCategory
      ? `Ver productos disponibles en ${selectedCategory.name}. Cotiza maquinaria, repuestos y servicios industriales con atención comercial personalizada.`
      : 'Explora maquinaria, repuestos y servicios industriales disponibles para cotización.'
  const canonicalPath = selectedCategory
    ? `/catalogo?category=${selectedCategory.id}`
    : '/catalogo'
  const seoRobots = hasSearch ? 'noindex,follow' : 'index,follow'
  const canonicalUrl = buildPublicUrl(canonicalPath)

  const buildCatalogHref = (categoryId?: number) => {
    const next = new URLSearchParams(searchParams)
    if (categoryId) next.set('category', String(categoryId))
    else next.delete('category')

    const queryString = next.toString()
    return queryString ? `/catalogo?${queryString}` : '/catalogo'
  }

  const breadcrumbItems = useMemo<BreadcrumbItem[]>(() => {
    const trail: BreadcrumbItem[] = [
      { label: 'Inicio', to: '/' },
      ...categoryPath.map((category) => ({
        label: category.name,
        to: buildCatalogHref(category.id),
      })),
    ]

    if (selectedBrand?.name) trail.push({ label: selectedBrand.name })
    extraFilterTrail.forEach((item) => trail.push({ label: item }))

    return trail
  }, [categoryPath, selectedBrand, extraFilterTrail, searchParams])

  const pageTitle = useMemo(() => {
    const categoryName = categoryPath[categoryPath.length - 1]?.name
    const brandName = selectedBrand?.name

    if (categoryName && brandName) return `${brandName} en ${categoryName}`
    if (categoryName) return categoryName
    if (brandName) return brandName

    if (query.product_type) return FILTER_LABELS.product_type[query.product_type] ?? 'Productos'
    if (query.search) return `Resultados para "${query.search}"`
    return 'Productos'
  }, [categoryPath, selectedBrand, query.product_type, query.search])

  const sortValue = query.ordering ? query.ordering : 'recommended'

  useEffect(() => {
    const root = categoryPath[0]
    if (!root || root.parent !== null) return
    const normalized = normalizeLabel(root.name)
    if (!['maquinaria', 'repuestos', 'servicios'].includes(normalized)) return
    trackCategoryView({ category_id: root.id, category_name: root.name })
  }, [categoryPath])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [location.pathname, location.search])

  const displayedProducts = useMemo(() => {
    if (!query.ordering || (query.ordering !== 'price' && query.ordering !== '-price')) {
      return products
    }

    const productsWithPrice: ProductListItem[] = []
    const productsWithoutPrice: ProductListItem[] = []

    products.forEach((product) => {
      if (getNumericPrice(product) === null) {
        productsWithoutPrice.push(product)
      } else {
        productsWithPrice.push(product)
      }
    })

    productsWithPrice.sort((a, b) => {
      const priceA = getNumericPrice(a) ?? 0
      const priceB = getNumericPrice(b) ?? 0
      return query.ordering === 'price' ? priceA - priceB : priceB - priceA
    })

    return [...productsWithPrice, ...productsWithoutPrice]
  }, [products, query.ordering])



  const itemsPerPage = PRODUCTS_PER_PAGE
  const totalPages = Math.max(1, Math.ceil(displayedProducts.length / itemsPerPage))
  const paginatedProducts = displayedProducts.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)

  const shouldRenderItemList = !hasSearch
  const visiblePublishedProducts = useMemo(
    () => paginatedProducts.filter((product) => product.is_published !== false),
    [paginatedProducts],
  )

  const breadcrumbJsonLd = useMemo(() => buildBreadcrumbJsonLd(breadcrumbItems), [breadcrumbItems])
  const itemListJsonLd = useMemo(() => buildItemListJsonLd(visiblePublishedProducts), [visiblePublishedProducts])


  const paginationItems = useMemo(() => {
    if (totalPages <= 1) return [1]
    if (totalPages <= 5) return Array.from({ length: totalPages }, (_, index) => index + 1)

    const pages = [1]
    if (currentPage > 3) pages.push(-1)
    for (let page = Math.max(2, currentPage - 1); page <= Math.min(totalPages - 1, currentPage + 1); page += 1) {
      pages.push(page)
    }
    if (currentPage < totalPages - 2) pages.push(-2)
    pages.push(totalPages)
    return pages
  }, [currentPage, totalPages])

  const goToPage = (page: number) => {
    setCurrentPage(page)
    headingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <Layout>
      <Seo
        title={seoTitle}
        description={seoDescription}
        canonical={canonicalUrl}
        ogType="website"
        ogUrl={canonicalUrl}
        robots={seoRobots}
      />
      <JsonLd id="catalog-breadcrumb" data={breadcrumbJsonLd} />
      {shouldRenderItemList && visiblePublishedProducts.length > 0 ? <JsonLd id="catalog-itemlist" data={itemListJsonLd} /> : null}
      <section className="simple-page catalog-page">
        <Breadcrumb items={breadcrumbItems} ariaLabel="Ruta de productos" />

        <div className="section-heading catalog-page__heading" ref={headingRef}>
          <h1>{searchOnlyView ? 'Resultados de búsqueda' : pageTitle}</h1>
          {mainCategorySeo ? (
            <div className="catalog-seo-intro" aria-label={`Resumen comercial de ${mainCategorySeo.title}`}>
              <p>{mainCategorySeo.description}</p>
            </div>
          ) : null}
        </div>

        <div className="catalog-toolbar">
          {totalPages > 1 ? (
            <nav className="catalog-pagination catalog-pagination--inline" aria-label="Paginación de productos">
              {paginationItems.map((item, index) => {
                if (item < 0) {
                  return (
                    <span key={`ellipsis-${index}`} className="catalog-pagination__ellipsis" aria-hidden="true">
                      ...
                    </span>
                  )
                }
                return (
                  <button
                    key={item}
                    type="button"
                    className={`catalog-pagination__button${item === currentPage ? ' is-active' : ''}`}
                    onClick={() => goToPage(item)}
                    aria-current={item === currentPage ? 'page' : undefined}
                  >
                    {item}
                  </button>
                )
              })}
              <button
                type="button"
                className="catalog-pagination__button catalog-pagination__button--next"
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage >= totalPages}
                aria-label="Siguiente página"
              >
                &gt;
              </button>
            </nav>
          ) : null}
          <label className="catalog-toolbar__sort">
            <span>Ordenar por</span>
            <select value={sortValue} onChange={(event) => updateFilter('ordering', event.target.value)}>
              {ORDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? <p className="ui-note">Cargando productos...</p> : null}
        {!loading && error ? <p className="ui-note ui-note--error">{error} Usa el menú lateral o vuelve más tarde.</p> : null}
        {!loading && !error && displayedProducts.length === 0 ? <p className="ui-note">No hay productos con estos filtros.</p> : null}

        {!loading && !error && displayedProducts.length > 0 ? (
          <div className="featured-products__grid">
            {paginatedProducts.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        ) : null}
      </section>
    </Layout>
  )
}
