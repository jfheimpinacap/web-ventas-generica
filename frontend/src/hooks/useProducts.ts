import { useEffect, useState } from 'react'

import { getFeaturedProducts, searchProducts } from '../services/catalogApi'
import type { ProductListItem } from '../types/catalog'

export function useProducts(searchTerm?: string) {
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = searchTerm ? await searchProducts(searchTerm) : await getFeaturedProducts()
        setProducts(data)
      } catch {
        setError('No fue posible cargar productos desde la API.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [searchTerm])

  return { products, loading, error }
}
