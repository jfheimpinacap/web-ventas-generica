import { ApiError, getSafeApiErrorMessage } from '../services/api'

export function commercialQuotePdfFilename(id: number, folio?: string | null) {
  const normalizedFolio = folio?.trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '')
  return `cotizacion-${normalizedFolio || id}.pdf`
}

export function commercialQuotePdfErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return 'Se alcanzó temporalmente el límite de descargas. Intenta nuevamente en unos minutos.'
  }
  if (error instanceof ApiError && error.status === 404) {
    return 'La cotización no existe o su PDF no está disponible.'
  }
  return getSafeApiErrorMessage(error, 'No se pudo descargar el PDF. Intenta nuevamente.')
}

export function downloadCommercialQuotePdf(objectUrl: string, id: number, folio?: string | null) {
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = commercialQuotePdfFilename(id, folio)
  document.body.appendChild(link)
  try {
    link.click()
  } finally {
    link.remove()
  }
}
