import { useEffect, useState } from 'react'

import { getCategories } from '../services/catalogApi'
import type { Category } from '../types/catalog'

export function useCategories() {
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        setCategories(await getCategories())
      } catch {
        setError('No fue posible cargar categorías.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [])

  return { categories, loading, error }
}
