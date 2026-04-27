import type { AuthUser } from '../types/catalog'
import { apiRequest, ApiError } from './api'

const ACCESS_TOKEN_KEY = 'ventas_access_token'
const REFRESH_TOKEN_KEY = 'ventas_refresh_token'

interface AuthTokens {
  access: string
  refresh: string
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

function saveTokens(tokens: AuthTokens) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh)
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function isAuthenticated() {
  return Boolean(getAccessToken())
}

export async function login(username: string, password: string) {
  const tokens = await apiRequest<AuthTokens>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
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
    const response = await apiRequest<{ access: string }>('/auth/refresh/', {
      method: 'POST',
      body: JSON.stringify({ refresh }),
    })
    localStorage.setItem(ACCESS_TOKEN_KEY, response.access)
    return response.access
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
