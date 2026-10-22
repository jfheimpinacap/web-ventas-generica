import { catalogPrice } from '../utils/rental'
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { Breadcrumb, type BreadcrumbItem } from '../components/common/Breadcrumb'
import { JsonLd } from '../components/common/JsonLd'
import { INDEX_ROBOTS, NOINDEX_ROBOTS, Seo } from '../components/common/Seo'
import { Layout } from '../components/layout/Layout'
import { useBrands } from '../hooks/useBrands'
import { useCatalogProducts } from '../hooks/useCatalogProducts'
import { useCategories } from '../hooks/useCategories'
import type { Category, ProductListItem } from '../types/catalog'
import { catalogFacets, catalogRequestParams, catalogSelections, contextCategories, contextProducts, filterCatalogProducts, resolveCatalogContext, type CommercialCatalogConfig } from '../utils/catalogFilters'
import { trackCategoryView } from '../utils/analytics'
import { buildBreadcrumbJsonLd, buildItemListJsonLd, buildPageJsonLd, getStaticSeo } from '../utils/seo'
import { CATALOG_FILTER_PARAMS } from '../config/prerenderRoutes'

export type { CommercialCatalogConfig } from '../utils/catalogFilters'

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


function normalizeLabel(value: string) {
  return value
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim()
    .toLowerCase()
}

function getNumericPrice(product: ProductListItem) {
  return catalogPrice(product)
}

export function CatalogPage({ commercialConfig }: { commercialConfig?: CommercialCatalogConfig }) {
  const PRODUCTS_PER_PAGE = 12
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const { categories, loading: categoriesLoading, error: categoriesError } = useCategories()
  const { brands, loading: brandsLoading, error: brandsError } = useBrands()
  const context = useMemo(() => resolveCatalogContext(categories, searchParams, commercialConfig), [categories, searchParams, commercialConfig])
  const scopedCategories = useMemo(() => contextCategories(categories, context), [categories, context])
  const selections = useMemo(() => catalogSelections(searchParams, scopedCategories, brands, context), [searchParams, scopedCategories, brands, context])
  const query = useMemo(() => ({
    search: searchParams.get('search') ?? '',
    category: selections.category.join(','),
    brand: selections.brand.join(','),
    product_type: context.productType,
    condition: context.fixedCondition ?? selections.condition.join(','),
    stock_status: selections.stock_status.join(','),
    ordering: searchParams.get('ordering') ?? '',
  }), [searchParams, selections, context])
  const requestParams = useMemo(() => catalogRequestParams(context, searchParams), [context, searchParams])
  const { products: publicProducts, loading: productsLoading, error: productsError } = useCatalogProducts(requestParams, !categoriesLoading && !categoriesError)
  const loading = productsLoading || categoriesLoading || brandsLoading
  const error = productsError ?? categoriesError ?? brandsError
  const baseProducts = useMemo(() => contextProducts(publicProducts, categories, context), [publicProducts, categories, context])
  const products = useMemo(() => filterCatalogProducts(baseProducts, scopedCategories, selections, searchParams), [baseProducts, scopedCategories, selections, searchParams])
  const facets = useMemo(() => catalogFacets(baseProducts, scopedCategories, brands, selections, searchParams), [baseProducts, scopedCategories, brands, selections, searchParams])
  const catalogSidebar = { context, categories: scopedCategories, selections, facets, loading, error }
  const paginationKey = `${location.pathname}${location.search}`
  const [pagination, setPagination] = useState({ key: paginationKey, page: 1 })
  const currentPage = pagination.key === paginationKey ? pagination.page : 1

  useEffect(() => { setPagination({ key: paginationKey, page: 1 }) }, [paginationKey])

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value || value === 'recommended') next.delete(key)
    else next.set(key, value)
    next.delete('page')
    setSearchParams(next)
  }

  const explicitSelectedCategory = useMemo(() => {
    if (selections.category.length !== 1) return null
    return scopedCategories.find((category) => String(category.id) === selections.category[0]) ?? null
  }, [scopedCategories, selections.category])
  const effectiveRootCategory = context.root
    ?? scopedCategories.find((category) => category.parent === null && category.product_type === context.productType)
    ?? null
  const categoryPath = useMemo(() => {
    if (!explicitSelectedCategory) return effectiveRootCategory ? [effectiveRootCategory] : [] as Category[]

    const categoryById = new Map(categories.map((category) => [category.id, category]))
    const path: Category[] = []
    let current: Category | null = explicitSelectedCategory

    const visited = new Set<number>()
    while (current && !visited.has(current.id)) {
      visited.add(current.id)
      path.unshift(current)
      current = current.parent !== null ? categoryById.get(current.parent) ?? null : null
    }

    return path
  }, [categories, effectiveRootCategory, explicitSelectedCategory])

  const selectedBrands = useMemo(() => brands.filter((brand) => selections.brand.includes(String(brand.id))), [brands, selections.brand])

  const extraFilterTrail = useMemo(() => {
    const trail: string[] = []
    ;(['condition', 'stock_status'] as const).forEach((key) => {
      const values = key === 'condition' && context.fixedCondition ? [] : selections[key]
      values.forEach((value) => {
        const label = FILTER_LABELS[key][value]
        if (label) trail.push(label)
      })
    })

    if (query.search) {
      trail.push(`Búsqueda: ${query.search}`)
    }

    return trail
  }, [query.search, selections, context.fixedCondition])

  const hasSearch = Boolean((query.search ?? '').trim())
  const hasSpecificFilters = Boolean(query.brand || query.condition || query.stock_status || query.ordering)
  const searchOnlyView = hasSearch && !query.category && !query.product_type && !hasSpecificFilters
  const hasCatalogParameters = CATALOG_FILTER_PARAMS.some((parameter) => searchParams.has(parameter))
  const isCleanCatalogView = !commercialConfig && !hasCatalogParameters
  const isCleanCommercialView = Boolean(commercialConfig) && !hasCatalogParameters
  const isIndexableView = isCleanCatalogView || isCleanCommercialView
  const canonicalPath = commercialConfig?.canonicalPath ?? '/catalogo'
  const seoRobots = isIndexableView ? INDEX_ROBOTS : NOINDEX_ROBOTS
  const routeSeo = getStaticSeo(canonicalPath)

  const buildCatalogHref = (categoryId?: number) => {
    const next = new URLSearchParams(searchParams)
    if (context.root) next.set('catalog_root', String(context.root.id))
    if (categoryId) next.set('category', String(categoryId))
    else next.delete('category')

    const queryString = next.toString()
    const basePath = commercialConfig?.canonicalPath ?? '/catalogo'
    return queryString ? `${basePath}?${queryString}` : basePath
  }

  const breadcrumbItems = useMemo<BreadcrumbItem[]>(() => {
    const trail: BreadcrumbItem[] = [
      { label: 'Inicio', to: '/' },
      ...(commercialConfig
        ? [{ label: commercialConfig.title, to: commercialConfig.canonicalPath }]
        : [{ label: 'Catálogo', to: '/catalogo' }]),
      ...categoryPath.map((category) => ({
        label: category.name,
        to: buildCatalogHref(category.id),
      })),
    ]

    selectedBrands.forEach((brand) => trail.push({ label: brand.name }))
    extraFilterTrail.forEach((item) => trail.push({ label: item }))

    return trail
  }, [categoryPath, commercialConfig, selectedBrands, extraFilterTrail, searchParams])

  const pageTitle = context.title

  const sortValue = query.ordering ? query.ordering : 'recommended'

  useEffect(() => {
    const root = effectiveRootCategory
    if (!root || root.parent !== null) return
    const normalized = normalizeLabel(root.name)
    if (!['maquinaria', 'repuestos', 'servicios'].includes(normalized)) return
    trackCategoryView({ category_id: root.id, category: root.name })
  }, [effectiveRootCategory])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  }, [location.pathname, location.search])

  const displayedProducts = useMemo(() => {
    if (!query.ordering || (query.ordering !== 'price' && query.ordering !== '-price')) {
      if (query.ordering === 'name' || query.ordering === '-name') {
        return [...products].sort((a, b) => (query.ordering === '-name' ? -1 : 1) * a.name.localeCompare(b.name))
      }
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

  const visiblePublishedProducts = useMemo(
    () => paginatedProducts.filter((product) => product.is_published !== false),
    [paginatedProducts],
  )
  const shouldRenderStaticStructuredData = isIndexableView
  const shouldRenderItemListStructuredData = (
    isIndexableView
    && !loading
    && !error
    && visiblePublishedProducts.length > 0
  )

  const structuredBreadcrumbItems = useMemo<BreadcrumbItem[]>(() => [
    { label: 'Inicio', to: '/' },
    { label: commercialConfig?.title ?? 'Catálogo' },
  ], [commercialConfig])
  const breadcrumbJsonLd = useMemo(
    () => buildBreadcrumbJsonLd(structuredBreadcrumbItems, routeSeo.canonical),
    [routeSeo.canonical, structuredBreadcrumbItems],
  )
  const itemListJsonLd = useMemo(() => buildItemListJsonLd(visiblePublishedProducts), [visiblePublishedProducts])
  const pageJsonLd = useMemo(() => buildPageJsonLd(canonicalPath, 'CollectionPage'), [canonicalPath])


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
    setPagination({ key: paginationKey, page: Math.max(1, Math.min(totalPages, page)) })
  }

  const renderPagination = (position: 'superior' | 'inferior') => totalPages > 1 ? (
    <nav
      className={`catalog-pagination ${position === 'superior' ? 'catalog-pagination--inline' : 'catalog-pagination--bottom'}`}
      aria-label={`Paginación ${position} de productos`}
    >
      {paginationItems.map((item, index) => item < 0 ? (
        <span key={`ellipsis-${index}`} className="catalog-pagination__ellipsis" aria-hidden="true">...</span>
      ) : (
        <button
          key={item}
          type="button"
          className={`catalog-pagination__button${item === currentPage ? ' is-active' : ''}`}
          onClick={() => goToPage(item)}
          aria-current={item === currentPage ? 'page' : undefined}
        >
          {item}
        </button>
      ))}
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
  ) : null

  return (
    <Layout catalogSidebar={catalogSidebar}>
      <Seo
        {...routeSeo}
        ogType="website"
        robots={seoRobots}
      />
      {shouldRenderStaticStructuredData && breadcrumbJsonLd ? <JsonLd id="catalog-breadcrumb" data={breadcrumbJsonLd} /> : null}
      {shouldRenderStaticStructuredData ? <JsonLd id="catalog-page" data={pageJsonLd} /> : null}
      {shouldRenderItemListStructuredData ? <JsonLd id="catalog-itemlist" data={itemListJsonLd} /> : null}
      <section className="simple-page catalog-page">
        <Breadcrumb items={breadcrumbItems} ariaLabel="Ruta de productos" />

        <div className="section-heading catalog-page__heading">
          <h1>{searchOnlyView ? 'Resultados de búsqueda' : pageTitle}</h1>
          {commercialConfig?.description ? <p className="catalog-page__description">{commercialConfig.description}</p> : !commercialConfig && !searchOnlyView ? (
            <p className="catalog-page__description">Explora las publicaciones disponibles de maquinaria, repuestos y servicios.</p>
          ) : null}
        </div>

        <div className="catalog-toolbar">
          {renderPagination('superior')}
          <label className="catalog-toolbar__sort">
            <span>Ordenar por</span>
            <select value={sortValue} onChange={(event) => updateFilter('ordering', event.target.value)}>
              {ORDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {context.commercialMode === 'rental' ? option.label.replace('Precio:', 'Precio día:') : option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? <p className="ui-note">Cargando productos...</p> : null}
        {!loading && error ? <p className="ui-note ui-note--error">{error} Usa el menú lateral o vuelve más tarde.</p> : null}
        {!loading && !error && displayedProducts.length === 0 ? <p className="ui-note">No hay productos con estos filtros.</p> : null}

        {!loading && !error && displayedProducts.length > 0 ? (
          <>
            <div className="featured-products__grid">
              {paginatedProducts.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
            {renderPagination('inferior')}
          </>
        ) : null}
      </section>
    </Layout>
  )
}
