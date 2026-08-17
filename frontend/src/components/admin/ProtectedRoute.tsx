import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { AdminIdleSessionTimeout } from './AdminIdleSessionTimeout'
import { Seo } from '../common/Seo'
import { canAccessSellerPanel, clearSession, getMe, isAuthenticated, isSupportAdmin } from '../../services/authApi'
import type { AuthUser } from '../../types/catalog'
import { buildPublicUrl } from '../../utils/seo'

type AuthGuardStatus = 'checking' | 'authorized' | 'anonymous' | 'forbidden'

const AdminUserContext = createContext<AuthUser | null>(null)

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
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (status === 'forbidden') {
    return <Navigate to="/login" replace state={{ from: location.pathname, reason: 'forbidden' }} />
  }

  if (status === 'checking') {
    return <p className="ui-note">Validando sesión…</p>
  }

  return (
    <>
      <AdminIdleSessionTimeout />
      <Seo
        title="Panel de administración | JEM Nexus"
        description="Panel interno de gestión comercial."
        canonical={buildPublicUrl(location.pathname)}
        ogType="website"
        ogUrl={buildPublicUrl(location.pathname)}
        robots="noindex,nofollow"
      />
      <AdminUserContext.Provider value={user}><Outlet /></AdminUserContext.Provider>
    </>
  )
}
