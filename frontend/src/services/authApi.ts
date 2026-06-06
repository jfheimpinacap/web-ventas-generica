import type { AuthUser } from '../types/catalog'
import { apiEndpoint, apiRequest, ApiError } from './api'

const ACCESS_TOKEN_KEY = 'ventas_access_token'
const REFRESH_TOKEN_KEY = 'ventas_refresh_token'

interface AuthResponseShape {
  access?: string
  accessToken?: string
  access_token?: string
  token?: string
  refresh?: string
  refreshToken?: string
  refresh_token?: string
  user?: AuthUser
}

export interface NormalizedAuthResponse {
  accessToken: string
  refreshToken: string
  user?: AuthUser
}

export function normalizeAuthResponse(response: AuthResponseShape): NormalizedAuthResponse {
  const accessToken = response.access ?? response.accessToken ?? response.access_token ?? response.token
  const refreshToken = response.refresh ?? response.refreshToken ?? response.refresh_token

  if (!accessToken || !refreshToken) {
    throw new ApiError('Invalid auth response', 500)
  }

  return {
    accessToken,
    refreshToken,
    user: response.user,
  }
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

function saveTokens(tokens: NormalizedAuthResponse) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken)
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function isAuthenticated() {
  return Boolean(getAccessToken())
}

export async function login(username: string, password: string) {
  const response = await apiRequest<AuthResponseShape>(apiEndpoint('/auth/login/'), {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  const normalizedAuth = normalizeAuthResponse(response)
  saveTokens(normalizedAuth)
  return normalizedAuth
}

export async function refreshToken() {
  const refresh = getRefreshToken()
  if (!refresh) {
    clearSession()
    return null
  }

  try {
    const response = await apiRequest<AuthResponseShape>(apiEndpoint('/auth/refresh/'), {
      method: 'POST',
      body: JSON.stringify({ refresh }),
    })
    const responseWithRefresh = response.refresh || response.refreshToken || response.refresh_token
      ? response
      : { ...response, refresh }
    const normalizedAuth = normalizeAuthResponse(responseWithRefresh)
    localStorage.setItem(ACCESS_TOKEN_KEY, normalizedAuth.accessToken)
    if (normalizedAuth.refreshToken !== refresh) {
      localStorage.setItem(REFRESH_TOKEN_KEY, normalizedAuth.refreshToken)
    }
    return normalizedAuth.accessToken
  } catch {
    clearSession()
    return null
  }
}

export async function authFetch<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const token = getAccessToken()
  if (!token) {
    clearSession()
    throw new ApiError('Unauthorized', 401)
  }

  try {
    return await apiRequest<T>(apiEndpoint(path), {
      ...options,
      token,
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const nextAccess = await refreshToken()
      if (!nextAccess) {
        clearSession()
        throw error
      }

      return apiRequest<T>(apiEndpoint(path), {
        ...options,
        token: nextAccess,
      })
    }

    throw error
  }
}

export async function getMe() {
  return authFetch<AuthUser>('/auth/me/')
}

export function logout() {
  clearSession()
}
