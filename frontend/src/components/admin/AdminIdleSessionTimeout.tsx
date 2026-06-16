import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ACCESS_TOKEN_KEY, clearSession, isAuthenticated } from '../../services/authApi'

export const ADMIN_IDLE_TIMEOUT_MS = 60 * 60 * 1000
const ADMIN_LAST_ACTIVITY_KEY = 'ventas_admin_last_activity_at'
const ADMIN_IDLE_LOGOUT_KEY = 'ventas_admin_idle_logout_at'
const ACTIVITY_EVENTS = ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'] as const

function markAdminActivity() {
  localStorage.setItem(ADMIN_LAST_ACTIVITY_KEY, String(Date.now()))
}

function getLastAdminActivity() {
  const storedValue = localStorage.getItem(ADMIN_LAST_ACTIVITY_KEY)
  const timestamp = storedValue ? Number(storedValue) : 0

  return Number.isFinite(timestamp) && timestamp > 0 ? timestamp : Date.now()
}

export function AdminIdleSessionTimeout() {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isAuthenticated()) return undefined

    let idleTimer: ReturnType<typeof window.setTimeout> | null = null
    let hasExpired = false

    const redirectToIdleLogin = () => {
      navigate('/login', { replace: true, state: { from: location.pathname, reason: 'idle' } })
    }

    const expireSession = () => {
      if (hasExpired) return
      hasExpired = true
      clearSession()
      localStorage.setItem(ADMIN_IDLE_LOGOUT_KEY, String(Date.now()))
      redirectToIdleLogin()
    }

    const scheduleExpiration = () => {
      if (idleTimer) {
        window.clearTimeout(idleTimer)
      }

      if (!isAuthenticated()) return

      const elapsedMs = Date.now() - getLastAdminActivity()
      const remainingMs = ADMIN_IDLE_TIMEOUT_MS - elapsedMs

      if (remainingMs <= 0) {
        expireSession()
        return
      }

      idleTimer = window.setTimeout(expireSession, remainingMs)
    }

    const resetIdleTimer = () => {
      if (!isAuthenticated() || hasExpired) return
      markAdminActivity()
      scheduleExpiration()
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.key === ADMIN_LAST_ACTIVITY_KEY) {
        scheduleExpiration()
        return
      }

      if (event.key === ADMIN_IDLE_LOGOUT_KEY || (event.key === ACCESS_TOKEN_KEY && event.newValue === null)) {
        if (!isAuthenticated()) {
          redirectToIdleLogin()
        }
      }
    }

    markAdminActivity()

    ACTIVITY_EVENTS.forEach((eventName) => window.addEventListener(eventName, resetIdleTimer, { passive: true }))
    window.addEventListener('storage', handleStorage)
    scheduleExpiration()

    return () => {
      if (idleTimer) {
        window.clearTimeout(idleTimer)
      }
      ACTIVITY_EVENTS.forEach((eventName) => window.removeEventListener(eventName, resetIdleTimer))
      window.removeEventListener('storage', handleStorage)
    }
  }, [location.pathname, navigate])

  return null
}
