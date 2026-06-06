type ApiProvider = 'django' | 'dotnet'

type ApiRequestOptions = RequestInit & {
  params?: Record<string, string | number | boolean | undefined>
  token?: string | null
}

const DEFAULT_API_ROOT_URL = 'http://127.0.0.1:8001'
const API_PREFIX = '/api'

function normalizeBaseUrl(value?: string) {
  const rawValue = value?.trim() || DEFAULT_API_ROOT_URL
  return rawValue.replace(/\/+$/, '')
}

function normalizeProvider(value?: string): ApiProvider {
  return value === 'dotnet' ? 'dotnet' : 'django'
}

function joinUrl(baseUrl: string, path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${baseUrl}${normalizedPath}`
}

export const API_PROVIDER = normalizeProvider(import.meta.env.VITE_API_PROVIDER)
export const API_ROOT_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)

function getApiBaseUrl() {
  if (API_ROOT_URL.endsWith(API_PREFIX)) {
    return API_ROOT_URL
  }

  return `${API_ROOT_URL}${API_PREFIX}`
}

export const API_BASE_URL = getApiBaseUrl()

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

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(joinUrl(API_BASE_URL, path))

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }

  return url
}

function getErrorMessage(status: number, payload: unknown) {
  if (payload && typeof payload === 'object') {
    const detail = 'detail' in payload ? payload.detail : undefined
    const message = 'message' in payload ? payload.message : undefined

    if (typeof detail === 'string') return detail
    if (typeof message === 'string') return message
  }

  if (typeof payload === 'string' && payload.trim()) {
    return payload
  }

  return `API error (${status})`
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { params, headers, token, ...rest } = options
  const url = buildUrl(path, params)

  const isFormData = typeof FormData !== 'undefined' && rest.body instanceof FormData
  const requestHeaders = new Headers(headers ?? undefined)
  if (!isFormData && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }

  if (token && !requestHeaders.has('Authorization')) {
    requestHeaders.set('Authorization', `Bearer ${token}`)
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
    throw new ApiError(getErrorMessage(response.status, payload), response.status, payload)
  }

  return payload as T
}

export function apiEndpoint(path: string) {
  if (API_PROVIDER === 'django') return path

  if (path !== '/' && path.endsWith('/')) {
    return path.replace(/\/+$/, '')
  }

  return path
}

export function buildHealthUrl(path = API_PROVIDER === 'dotnet' ? '/api/health' : '/api/health/') {
  const healthPath = API_ROOT_URL.endsWith(API_PREFIX) && path.startsWith(API_PREFIX)
    ? path.slice(API_PREFIX.length) || '/'
    : path

  return new URL(joinUrl(API_ROOT_URL, healthPath)).toString()
}

export async function checkApiHealth() {
  const healthUrl = buildHealthUrl()
  const response = await fetch(healthUrl, {
    headers: {
      Accept: 'application/json',
    },
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
    throw new ApiError(getErrorMessage(response.status, payload), response.status, payload)
  }

  return {
    provider: API_PROVIDER,
    apiBaseUrl: API_ROOT_URL,
    healthUrl,
    status: response.status,
    payload,
  }
}

export function resolveMediaUrl(path?: string | null) {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://')) return path

  try {
    const mediaBaseUrl = API_ROOT_URL.endsWith(API_PREFIX) ? new URL(API_ROOT_URL).origin : API_ROOT_URL
    return `${mediaBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
  } catch {
    return path
  }
}
