import { useCallback, useEffect, useRef, useState } from 'react'

import { getCommercialQuotePdf } from '../services/commercialQuotesApi'
import { commercialQuotePdfErrorMessage, downloadCommercialQuotePdf } from '../utils/commercialQuotePdf'

interface CommercialQuotePdfDownload {
  downloadPdf: (id: number, folio?: string | null) => Promise<void>
  isDownloading: (id: number) => boolean
  error: string
  clearError: () => void
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
      downloadCommercialQuotePdf(objectUrl, id, folio)
      window.setTimeout(() => {
        if (objectUrls.current.delete(objectUrl)) URL.revokeObjectURL(objectUrl)
      }, 0)
    } catch (downloadError) {
      if (objectUrl && objectUrls.current.delete(objectUrl)) URL.revokeObjectURL(objectUrl)
      if (mounted.current) setError(commercialQuotePdfErrorMessage(downloadError))
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
