import { useEffect, useState } from 'react'

import { getAdminProductImageFile } from '../services/adminApi'

export function useAdminProductImageUrl(imageId: number | null) {
  const [url, setUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null

    setUrl(null)
    setHasError(false)
    if (!imageId || imageId <= 0) {
      setIsLoading(false)
      return () => undefined
    }

    setIsLoading(true)
    void getAdminProductImageFile(imageId)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (active) setHasError(true)
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [imageId])

  return { url, isLoading, hasError }
}
