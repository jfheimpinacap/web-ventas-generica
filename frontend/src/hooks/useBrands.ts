import { useEffect, useState } from 'react'

import { getBrands } from '../services/catalogApi'
import type { Brand } from '../types/catalog'

export function useBrands() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        setBrands(await getBrands())
      } catch {
        setError('No fue posible cargar marcas.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [])

  return { brands, loading, error }
}
