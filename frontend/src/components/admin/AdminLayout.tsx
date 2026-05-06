import { useState, type PropsWithChildren } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { logout } from '../../services/authApi'

const adminMenu = [
  { to: '/admin/productos', label: 'Productos' },
  { to: '/admin/categorias', label: 'Categorías' },
  { to: '/admin/marcas', label: 'Marcas' },
  { to: '/admin/proveedores', label: 'Proveedores' },
  { to: '/admin/cotizaciones', label: 'Cotizaciones' },
  { to: '/admin/promociones', label: 'Promociones' },
  { to: '/admin/ofertas-hero', label: 'Ofertas en Hero section' },
]

export function AdminLayout({ children }: PropsWithChildren) {
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
        ☰ Panel
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
            ×
          </button>
        </div>
        <h2 className="admin-sidebar__title">Panel vendedor</h2>
        <nav>
          {adminMenu.map((item) => (
            <NavLink key={item.to} to={item.to} className="admin-nav-link" onClick={closeMobileMenu}>
              {item.label}
            </NavLink>
          ))}
          <NavLink to="/" className="admin-nav-link" onClick={closeMobileMenu}>
            Volver al sitio
          </NavLink>
          <button type="button" className="admin-logout-button" onClick={handleLogout}>
            Cerrar sesión
          </button>
        </nav>
      </aside>

      <section className="admin-main">
        <main className="admin-content">{children}</main>
      </section>
    </div>
  )
}
