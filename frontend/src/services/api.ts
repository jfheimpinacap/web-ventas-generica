const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8001/api'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL

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
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(`${API_BASE_URL}${normalizedPath}`)

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }

  return url
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const { params, headers, ...rest } = options
  const url = buildUrl(path, params)

  const response = await fetch(url, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
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
    throw new ApiError(`API error (${response.status})`, response.status, payload)
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
