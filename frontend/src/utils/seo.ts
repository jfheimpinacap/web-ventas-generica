export function getPublicSiteUrl() {
  const envUrl = import.meta.env.VITE_PUBLIC_SITE_URL?.trim()
  if (envUrl) return envUrl.replace(/\/+$/, '')
  return window.location.origin
}

export function buildPublicUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${getPublicSiteUrl()}${normalizedPath}`
}
