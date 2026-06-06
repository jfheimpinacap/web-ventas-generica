import type { AuthUser } from '../types/catalog'
import { apiRequest, ApiError } from './api'

const ACCESS_TOKEN_KEY = 'ventas_access_token'
const REFRESH_TOKEN_KEY = 'ventas_refresh_token'

interface AuthTokens {
  accessToken: string
  refreshToken: string
  user?: AuthUser
}

type AuthResponse = Partial<{
  access: string
  accessToken: string
  access_token: string
  token: string
  refresh: string
  refreshToken: string
  refresh_token: string
  user: AuthUser
}>

export function normalizeAuthResponse(response: AuthResponse): AuthTokens {
  const accessToken = response.access ?? response.accessToken ?? response.access_token ?? response.token
  const refreshToken = response.refresh ?? response.refreshToken ?? response.refresh_token

  if (!accessToken || !refreshToken) {
    throw new ApiError('La respuesta de autenticación no incluyó tokens válidos.', 500, {
      hasAccessToken: Boolean(accessToken),
      hasRefreshToken: Boolean(refreshToken),
      hasUser: Boolean(response.user),
    })
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

function saveTokens(tokens: AuthTokens) {
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
  const response = await apiRequest<AuthResponse>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  const tokens = normalizeAuthResponse(response)
  saveTokens(tokens)
  return tokens
}

export async function refreshToken() {
  const refresh = getRefreshToken()
  if (!refresh) {
    clearSession()
    return null
  }

  try {
    const response = await apiRequest<AuthResponse>('/auth/refresh/', {
      method: 'POST',
      body: JSON.stringify({ refresh }),
    })
    const tokens = normalizeAuthResponse({ ...response, refresh })
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken)
    return tokens.accessToken
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
    return await apiRequest<T>(path, {
      ...options,
      headers: {
        ...(options.headers ?? {}),
        Authorization: `Bearer ${token}`,
      },
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const nextAccess = await refreshToken()
      if (!nextAccess) {
        clearSession()
        throw error
      }

      return apiRequest<T>(path, {
        ...options,
        headers: {
          ...(options.headers ?? {}),
          Authorization: `Bearer ${nextAccess}`,
        },
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
