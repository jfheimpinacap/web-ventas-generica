export type ApiUrlParams = Record<
  string,
  string | number | boolean | undefined
>

function normalizeInternalPath(path: string) {
  const trimmed = path.trim()
  if (
    !trimmed ||
    trimmed.startsWith('//') ||
    /^[a-z][a-z\d+.-]*:/i.test(trimmed)
  ) {
    throw new TypeError('API endpoint must be a non-empty internal path')
  }

  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`
}

/** Compose an internal API endpoint against either an origin or origin/api base. */
export function composeApiUrl(
  baseUrl: string,
  path: string,
  params?: ApiUrlParams,
) {
  const base = new URL(baseUrl.trim())
  if (base.protocol !== 'http:' && base.protocol !== 'https:') {
    throw new TypeError('API base URL must use HTTP or HTTPS')
  }

  const endpoint = new URL(normalizeInternalPath(path), base.origin)
  const endpointPath = endpoint.pathname.replace(/\/{2,}/g, '/')
  const pathname =
    endpointPath === '/health'
      ? '/health'
      : endpointPath === '/api' || endpointPath.startsWith('/api/')
        ? endpointPath
        : `/api${endpointPath}`

  const url = new URL(base.origin)
  url.pathname = pathname
  url.search = endpoint.search
  url.hash = endpoint.hash

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }

  return url
}
