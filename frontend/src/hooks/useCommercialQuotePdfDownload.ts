import { useCallback, useEffect, useRef, useState } from 'react'

import { getSafeApiErrorMessage, ApiError } from '../services/api'
import { getCommercialQuotePdf } from '../services/commercialQuotesApi'

interface CommercialQuotePdfDownload {
  downloadPdf: (id: number, folio?: string | null) => Promise<void>
  isDownloading: (id: number) => boolean
  error: string
  clearError: () => void
}

const safeFilename = (id: number, folio?: string | null) => {
  const normalizedFolio = folio?.trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '')
  return `cotizacion-${normalizedFolio || id}.pdf`
}

const downloadErrorMessage = (error: unknown) => {
  if (error instanceof ApiError && error.status === 429) {
    return 'Se alcanzó temporalmente el límite de descargas. Intenta nuevamente en unos minutos.'
  }
  if (error instanceof ApiError && error.status === 404) {
    return 'La cotización no existe o su PDF no está disponible.'
  }
  return getSafeApiErrorMessage(error, 'No se pudo descargar el PDF. Intenta nuevamente.')
}

export function useCommercialQuotePdfDownload(): CommercialQuotePdfDownload {
  const activeIds = useRef<Set<number>>(new Set())
  const objectUrls = useRef<Set<string>>(new Set())
  const mounted = useRef(true)
  const [downloadingIds, setDownloadingIds] = useState<Set<number>>(new Set())
  const [error, setError] = useState('')

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      objectUrls.current.forEach((url) => URL.revokeObjectURL(url))
      objectUrls.current.clear()
      activeIds.current.clear()
    }
  }, [])

  const downloadPdf = useCallback(async (id: number, folio?: string | null) => {
    if (activeIds.current.has(id)) return
    activeIds.current.add(id)
    if (mounted.current) {
      setError('')
      setDownloadingIds(new Set(activeIds.current))
    }

    let objectUrl = ''
    try {
      const blob = await getCommercialQuotePdf(id)
      objectUrl = URL.createObjectURL(blob)
      objectUrls.current.add(objectUrl)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = safeFilename(id, folio)
      document.body.appendChild(link)
      try {
        link.click()
      } finally {
        link.remove()
      }
      window.setTimeout(() => {
        if (objectUrls.current.delete(objectUrl)) URL.revokeObjectURL(objectUrl)
      }, 0)
    } catch (downloadError) {
      if (objectUrl && objectUrls.current.delete(objectUrl)) URL.revokeObjectURL(objectUrl)
      if (mounted.current) setError(downloadErrorMessage(downloadError))
    } finally {
      activeIds.current.delete(id)
      if (mounted.current) setDownloadingIds(new Set(activeIds.current))
    }
  }, [])

  const clearError = useCallback(() => {
    if (mounted.current) setError('')
  }, [])

  return {
    downloadPdf,
    isDownloading: (id) => downloadingIds.has(id),
    error,
    clearError,
  }
}
