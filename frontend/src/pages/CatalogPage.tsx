import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { ProductCard } from '../components/catalog/ProductCard'
import { Breadcrumb, type BreadcrumbItem } from '../components/common/Breadcrumb'
import { Layout } from '../components/layout/Layout'
import { useBrands } from '../hooks/useBrands'
import { useCatalogProducts } from '../hooks/useCatalogProducts'
import { useCategories } from '../hooks/useCategories'
import type { Category, ProductListItem, ProductQueryParams } from '../types/catalog'

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

function getNumericPrice(product: ProductListItem) {
  if (!product.price_visible || !product.price) return null
  const parsedPrice = Number(product.price)
  return Number.isNaN(parsedPrice) ? null : parsedPrice
}

export function CatalogPage() {
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
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 560px)').matches)
  const headingRef = useRef<HTMLDivElement | null>(null)

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (!value || value === 'recommended') next.delete(key)
    else next.set(key, value)
    setSearchParams(next)
  }


  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 560px)')

    const updateIsMobile = (event: MediaQueryListEvent) => {
      setIsMobile(event.matches)
    }

    setIsMobile(mediaQuery.matches)
    mediaQuery.addEventListener('change', updateIsMobile)

    return () => mediaQuery.removeEventListener('change', updateIsMobile)
  }, [])

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



  const itemsPerPage = isMobile ? 10 : displayedProducts.length
  const totalPages = isMobile ? Math.max(1, Math.ceil(displayedProducts.length / itemsPerPage)) : 1
  const paginatedProducts = isMobile
    ? displayedProducts.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    : displayedProducts

  const goToPage = (page: number) => {
    setCurrentPage(page)
    headingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <Layout>
      <section className="simple-page catalog-page">
        <Breadcrumb items={breadcrumbItems} ariaLabel="Ruta de productos" />

        <div className="section-heading catalog-page__heading" ref={headingRef}>
          <h1>{pageTitle}</h1>
        </div>

        <div className="catalog-toolbar">
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

        {!loading && !error && isMobile && totalPages > 1 ? (
          <nav className="catalog-pagination" aria-label="Paginación de productos">
            {Array.from({ length: totalPages }, (_, index) => {
              const page = index + 1
              return (
                <button
                  key={page}
                  type="button"
                  className={`catalog-pagination__button${page === currentPage ? ' is-active' : ''}`}
                  onClick={() => goToPage(page)}
                  aria-current={page === currentPage ? 'page' : undefined}
                >
                  {page}
                </button>
              )
            })}
          </nav>
        ) : null}
      </section>
    </Layout>
  )
}
