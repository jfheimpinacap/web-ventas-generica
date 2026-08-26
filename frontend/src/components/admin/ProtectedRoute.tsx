import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { AdminIdleSessionTimeout } from './AdminIdleSessionTimeout'
import { NOINDEX_ROBOTS, Seo } from '../common/Seo'
import { canAccessSellerPanel, clearSession, getMe, isAuthenticated, isSupportAdmin } from '../../services/authApi'
import type { AuthUser } from '../../types/catalog'

type AuthGuardStatus = 'checking' | 'authorized' | 'anonymous' | 'forbidden'

const AdminUserContext = createContext<AuthUser | null>(null)

function AdminSeo() {
  return (
    <Seo
      title="Panel de administración | JEM Nexus"
      description="Panel interno de gestión comercial."
      ogType="website"
      robots={NOINDEX_ROBOTS}
    />
  )
}

export function useAdminUser() {
  return useContext(AdminUserContext)
}

export function ProtectedRoute({ supportAdminOnly = false }: { supportAdminOnly?: boolean }) {
  const location = useLocation()
  const [status, setStatus] = useState<AuthGuardStatus>(() => (isAuthenticated() ? 'checking' : 'anonymous'))
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    let isMounted = true

    if (!isAuthenticated()) {
      setStatus('anonymous')
      return () => {
        isMounted = false
      }
    }

    setStatus('checking')
    getMe()
      .then((user) => {
        if (!isMounted) return
        setUser(user)
        setStatus(canAccessSellerPanel(user) && (!supportAdminOnly || isSupportAdmin(user)) ? 'authorized' : 'forbidden')
      })
      .catch(() => {
        if (!isMounted) return
        clearSession()
        setStatus('anonymous')
      })

    return () => {
      isMounted = false
    }
  }, [location.pathname, supportAdminOnly])

  if (status === 'anonymous') {
    return <><AdminSeo /><Navigate to="/login" replace state={{ from: location.pathname }} /></>
  }

  if (status === 'forbidden') {
    return <><AdminSeo /><Navigate to="/login" replace state={{ from: location.pathname, reason: 'forbidden' }} /></>
  }

  if (status === 'checking') {
    return <><AdminSeo /><p className="ui-note">Validando sesión…</p></>
  }

  return (
    <>
      <AdminIdleSessionTimeout />
      <AdminSeo />
      <AdminUserContext.Provider value={user}><Outlet /></AdminUserContext.Provider>
    </>
  )
}
