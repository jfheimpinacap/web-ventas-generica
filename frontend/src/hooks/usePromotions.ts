import { useEffect, useState } from 'react'

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
  const [promotion, setPromotion] = useState<Promotion | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        const promotions = await getPromotions()
        setPromotion(promotions.find(isActiveNow) ?? promotions[0] ?? null)
      } catch {
        setError('No fue posible cargar promociones.')
      } finally {
        setLoading(false)
      }
    }

    void run()
  }, [])

  return { promotion, loading, error }
}
