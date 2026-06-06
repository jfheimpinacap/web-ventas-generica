import type { AuthUser } from '../types/catalog'
import { apiRequest, ApiError } from './api'

const ACCESS_TOKEN_KEY = 'ventas_access_token'
const REFRESH_TOKEN_KEY = 'ventas_refresh_token'

export interface AuthTokens {
  accessToken: string
  refreshToken: string
  user?: AuthUser
}

type RawAuthUser = Partial<AuthUser> &
  Record<string, unknown> &
  Partial<{
    firstName: string
    lastName: string
    isStaff: boolean
    isSuperuser: boolean
    isSuperUser: boolean
    userRole: string
    user_role: string
  }>

type AuthResponse = Partial<{
  access: string
  accessToken: string
  access_token: string
  token: string
  refresh: string
  refreshToken: string
  refresh_token: string
  user: RawAuthUser
}>

function normalizeBoolean(value: unknown) {
  return value === true || value === 'true' || value === 1 || value === '1'
}

export function normalizeAuthUser(user?: RawAuthUser | null): AuthUser | undefined {
  if (!user) return undefined

  return {
    ...user,
    id: typeof user.id === 'number' ? user.id : Number(user.id ?? 0),
    username: typeof user.username === 'string' ? user.username : '',
    email: typeof user.email === 'string' ? user.email : '',
    first_name: typeof user.first_name === 'string' ? user.first_name : typeof user.firstName === 'string' ? user.firstName : '',
    last_name: typeof user.last_name === 'string' ? user.last_name : typeof user.lastName === 'string' ? user.lastName : '',
    is_staff: normalizeBoolean(user.is_staff ?? user.isStaff),
    is_superuser: normalizeBoolean(user.is_superuser ?? user.isSuperuser ?? user.isSuperUser),
    role: typeof user.role === 'string' ? user.role : typeof user.userRole === 'string' ? user.userRole : user.user_role,
    roles: user.roles,
  }
}

function getUserRoles(user?: AuthUser) {
  if (!user) return []

  const roles = user.roles
  if (Array.isArray(roles)) {
    return roles.map((role) => String(role).toLowerCase())
  }

  if (typeof roles === 'string') {
    return [roles.toLowerCase()]
  }

  if (typeof user.role === 'string') {
    return [user.role.toLowerCase()]
  }

  return []
}

function requireAuthUser(user?: AuthUser) {
  if (!user) {
    throw new ApiError('La respuesta no incluyó un usuario válido.', 500)
  }

  return user
}

export function canAccessSellerPanel(user?: AuthUser) {
  if (!user) return false
  if (user.is_staff || user.is_superuser) return true

  const roles = getUserRoles(user)
  return roles.some((role) => ['seller', 'support_admin', 'admin', 'staff'].includes(role))
}

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
    user: normalizeAuthUser(response.user),
  }
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

function saveTokens(tokens: AuthTokens) {
  // Claves históricas del panel vendedor: mantenerlas evita invalidar sesiones existentes.
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

export async function loginWithoutPersistingSession(username: string, password: string) {
  const response = await apiRequest<AuthResponse>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

  return normalizeAuthResponse(response)
}

export async function login(username: string, password: string) {
  const tokens = await loginWithoutPersistingSession(username, password)
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
  const user = await authFetch<RawAuthUser>('/auth/me/')
  return requireAuthUser(normalizeAuthUser(user))
}

export async function getMeWithAccessToken(accessToken: string) {
  if (!accessToken) {
    throw new ApiError('Unauthorized', 401)
  }

  const user = await apiRequest<RawAuthUser>('/auth/me/', {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  return requireAuthUser(normalizeAuthUser(user))
}

export function logout() {
  clearSession()
}
