import { useEffect, useMemo, useState } from 'react'

import { getPromotions } from '../services/catalogApi'
import type { Promotion } from '../types/catalog'

function isActiveNow(promotion: Promotion) {
  const now = new Date()
  if (promotion.starts_at && new Date(promotion.starts_at) > now) {
    return false
  }
  if (promotion.ends_at && new Date(promotion.ends_at) < now) {
    return false
  }
  return promotion.is_active
}

export function usePromotions() {
  const [promotions, setPromotions] = useState<Promotion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        setPromotions(await getPromotions())
      } catch {
        setError('No fue posible cargar promociones.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [])

  const activePromotions = useMemo(() => {
    const current = promotions.filter(isActiveNow)
    return current.length > 0 ? current : promotions
  }, [promotions])

  return { promotions: activePromotions, loading, error }
}
