import { useState, type PropsWithChildren } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { logout } from '../../services/authApi'
import { AdminIcon, type AdminIconName } from './AdminIcon'
import { useAdminUser } from './ProtectedRoute'
import { isSupportAdmin } from '../../services/authApi'

const adminMenu: { to: string; label: string; icon: AdminIconName }[] = [
  { to: '/admin/productos', label: 'Productos', icon: 'box' },
  { to: '/admin/fichas-tecnicas', label: 'Fichas técnicas', icon: 'file' },
  { to: '/admin/categorias', label: 'Categorías', icon: 'folder' },
  { to: '/admin/marcas', label: 'Marcas', icon: 'tag' },
  { to: '/admin/proveedores', label: 'Proveedores', icon: 'truck' },
  { to: '/admin/cotizaciones', label: 'Cotizaciones', icon: 'clipboard' },
  { to: '/admin/promociones', label: 'Promociones', icon: 'megaphone' },
  { to: '/admin/ofertas-hero', label: 'Ofertas en Hero section', icon: 'star' },
]

export function AdminLayout({ children }: PropsWithChildren) {
  const currentUser = useAdminUser()
  const navigate = useNavigate()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const closeMobileMenu = () => setIsMobileMenuOpen(false)

  const handleLogout = () => {
    closeMobileMenu()
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="admin-shell">
      <button type="button" className="admin-mobile-menu-trigger" onClick={() => setIsMobileMenuOpen(true)}>
        <AdminIcon name="menu" /> Panel
      </button>

      {isMobileMenuOpen ? (
        <button
          type="button"
          className="admin-mobile-drawer-backdrop"
          onClick={closeMobileMenu}
          aria-label="Cerrar menú del panel"
        />
      ) : null}

      <aside className={`admin-sidebar ${isMobileMenuOpen ? 'admin-sidebar--mobile-open' : ''}`}>
        <div className="admin-sidebar__mobile-header">
          <h2>Panel vendedor</h2>
          <button type="button" className="admin-sidebar__mobile-close" onClick={closeMobileMenu} aria-label="Cerrar menú">
            <AdminIcon name="close" />
          </button>
        </div>
        <h2 className="admin-sidebar__title">Panel vendedor</h2>
        <nav>
          {adminMenu.map((item) => (
            <NavLink key={item.to} to={item.to} className="admin-nav-link" onClick={closeMobileMenu}>
              <AdminIcon name={item.icon} /><span>{item.label}</span>
            </NavLink>
          ))}
          {isSupportAdmin(currentUser ?? undefined) ? (
            <NavLink to="/admin/usuarios" className="admin-nav-link" onClick={closeMobileMenu}>
              <AdminIcon name="users" /><span>Usuarios</span>
            </NavLink>
          ) : null}
          <div className="admin-nav-divider" aria-hidden="true" />
          <NavLink to="/" className="admin-nav-link" onClick={closeMobileMenu}>
            <AdminIcon name="external" /><span>Volver al sitio</span>
          </NavLink>
        </nav>
        <div className="admin-sidebar__footer">
          <button type="button" className="admin-logout-button" onClick={handleLogout}>
            <AdminIcon name="logout" /><span>Cerrar sesión</span>
          </button>
        </div>
      </aside>

      <section className="admin-main">
        <main className="admin-content">{children}</main>
      </section>
    </div>
  )
}
