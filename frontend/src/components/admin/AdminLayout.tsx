import type { PropsWithChildren } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { logout } from '../../services/authApi'

const adminMenu = [
  { to: '/admin', label: 'Dashboard' },
  { to: '/admin/productos', label: 'Productos' },
  { to: '/admin/cotizaciones', label: 'Cotizaciones' },
  { to: '/admin/promociones', label: 'Promociones' },
]

export function AdminLayout({ children }: PropsWithChildren) {
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <h2>Panel vendedor</h2>
        <nav>
          {adminMenu.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/admin'} className="admin-nav-link">
              {item.label}
            </NavLink>
          ))}
          <NavLink to="/" className="admin-nav-link">
            Volver al sitio
          </NavLink>
        </nav>
      </aside>

      <section className="admin-main">
        <header className="admin-topbar">
          <p>Administración comercial</p>
          <button type="button" className="btn btn--accent" onClick={handleLogout}>
            Cerrar sesión
          </button>
        </header>
        <main className="admin-content">{children}</main>
      </section>
    </div>
  )
}
