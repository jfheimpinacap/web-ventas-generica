import { useEffect, useMemo, useState } from 'react'

import { getProducts } from '../services/catalogApi'
import type { ProductListItem, ProductQueryParams } from '../types/catalog'

export function useCatalogProducts(params: ProductQueryParams) {
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const paramsKey = useMemo(() => JSON.stringify(params), [params])

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        setProducts(await getProducts(params))
      } catch {
        setError('No fue posible cargar productos desde la API.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [paramsKey])

  return { products, loading, error }
}
