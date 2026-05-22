import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Seo } from '../common/Seo'
import { isAuthenticated } from '../../services/authApi'
import { buildPublicUrl } from '../../utils/seo'

export function ProtectedRoute() {
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return (
    <>
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
