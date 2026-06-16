import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { AdminIdleSessionTimeout } from './AdminIdleSessionTimeout'
import { Seo } from '../common/Seo'
import { canAccessSellerPanel, clearSession, getMe, isAuthenticated } from '../../services/authApi'
import { buildPublicUrl } from '../../utils/seo'

type AuthGuardStatus = 'checking' | 'authorized' | 'anonymous' | 'forbidden'

export function ProtectedRoute() {
  const location = useLocation()
  const [status, setStatus] = useState<AuthGuardStatus>(() => (isAuthenticated() ? 'checking' : 'anonymous'))

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
        setStatus(canAccessSellerPanel(user) ? 'authorized' : 'forbidden')
      })
      .catch(() => {
        if (!isMounted) return
        clearSession()
        setStatus('anonymous')
      })

    return () => {
      isMounted = false
    }
  }, [location.pathname])

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
        title="Panel vendedor | JEM Nexus"
        description="Panel interno de gestión comercial."
        canonical={buildPublicUrl(location.pathname)}
        ogType="website"
        ogUrl={buildPublicUrl(location.pathname)}
        robots="noindex,nofollow"
      />
      <Outlet />
    </>
  )
}
