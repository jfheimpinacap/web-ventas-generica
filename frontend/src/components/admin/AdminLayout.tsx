import type { PropsWithChildren } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { logout } from '../../services/authApi'

const adminMenu = [
  { to: '/admin/productos', label: 'Productos' },
  { to: '/admin/categorias', label: 'Categorías' },
  { to: '/admin/marcas', label: 'Marcas' },
  { to: '/admin/proveedores', label: 'Proveedores' },
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
            <NavLink key={item.to} to={item.to} className="admin-nav-link">
              {item.label}
            </NavLink>
          ))}
          <NavLink to="/" className="admin-nav-link">
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
