import { useEffect, useRef, useState } from 'react'

import { getProducts } from '../services/catalogApi'
import type { ProductListItem, ProductQueryParams } from '../types/catalog'

interface CatalogSnapshot {
  key: string
  products: ProductListItem[]
  error: string | null
}

// One public dataset feeds both the list and facets. The bounded, mount-local
// cache also shares in-flight requests when revisiting a context or search.
export function useCatalogProducts(params: ProductQueryParams, enabled = true) {
  const paramsKey = JSON.stringify(params)
  const requests = useRef(new Map<string, Promise<ProductListItem[]>>())
  const [snapshot, setSnapshot] = useState<CatalogSnapshot | null>(null)

  useEffect(() => {
    if (!enabled) return
    let active = true
    let request = requests.current.get(paramsKey)
    if (!request) {
      request = getProducts(JSON.parse(paramsKey) as ProductQueryParams)
      requests.current.set(paramsKey, request)
      if (requests.current.size > 8) requests.current.delete(requests.current.keys().next().value!)
    }
    request.then(
      (products) => { if (active) setSnapshot({ key: paramsKey, products, error: null }) },
      () => {
        requests.current.delete(paramsKey)
        if (active) setSnapshot({ key: paramsKey, products: [], error: 'No fue posible cargar productos desde la API.' })
      },
    )
    return () => { active = false }
  }, [paramsKey, enabled])

  // Suppress the old context synchronously, including the render before effects.
  const current = enabled && snapshot?.key === paramsKey ? snapshot : null
  return { products: current?.products ?? [], loading: enabled && current === null, error: current?.error ?? null }
}
