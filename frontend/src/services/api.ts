const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8001/api'
const DEFAULT_API_PROVIDER: ApiProvider = 'django'

type ApiProvider = 'django' | 'dotnet'

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL)
export const API_PROVIDER = normalizeApiProvider(import.meta.env.VITE_API_PROVIDER)

export class ApiError extends Error {
  status: number
  payload?: unknown

  constructor(message: string, status: number, payload?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

function normalizeApiProvider(provider?: string): ApiProvider {
  return provider === 'dotnet' ? 'dotnet' : DEFAULT_API_PROVIDER
}

function normalizeBaseUrl(url: string) {
  return url.trim().replace(/\/+$/, '')
}

function normalizeEndpointPath(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  if (API_PROVIDER === 'dotnet' && normalizedPath.length > 1) {
    return normalizedPath.replace(/\/+$/, '')
  }

  return normalizedPath
}

function shouldPrefixApi(path: string) {
  const basePath = new URL(API_BASE_URL).pathname.replace(/\/+$/, '')

  if (API_PROVIDER === 'dotnet' && path === '/health') {
    return false
  }

  return basePath !== '/api' && !path.startsWith('/api/') && path !== '/api'
}

export function buildApiUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const normalizedPath = normalizeEndpointPath(path)
  const apiPath = shouldPrefixApi(normalizedPath) ? `/api${normalizedPath}` : normalizedPath
  const url = new URL(`${API_BASE_URL}${apiPath}`)

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }

  return url
}

function extractErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>
    const detail = record.detail ?? record.message ?? record.error
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }

  return fallback
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const { params, headers, ...rest } = options
  const url = buildApiUrl(path, params)

  const isFormData = typeof FormData !== 'undefined' && rest.body instanceof FormData
  const requestHeaders = new Headers(headers ?? undefined)
  if (!isFormData && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }

  const response = await fetch(url, {
    ...rest,
    headers: requestHeaders,
  })

  const rawText = await response.text()
  let payload: unknown = null

  if (rawText) {
    try {
      payload = JSON.parse(rawText) as unknown
    } catch {
      payload = rawText
    }
  }

  if (!response.ok) {
    throw new ApiError(extractErrorMessage(payload, `API error (${response.status})`), response.status, payload)
  }

  return payload as T
}

export function resolveMediaUrl(path?: string | null) {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://')) return path

  try {
    const origin = new URL(API_BASE_URL).origin
    return `${origin}${path.startsWith('/') ? path : `/${path}`}`
  } catch {
    return path
  }
}
