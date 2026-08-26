import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PropsWithChildren } from 'react'
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
  { to: '/admin/clientes', label: 'Clientes', icon: 'users' },
  { to: '/admin/cotizaciones', label: 'Cotizaciones', icon: 'clipboard' },
  { to: '/admin/promociones', label: 'Promociones', icon: 'megaphone' },
  { to: '/admin/ofertas-hero', label: 'Ofertas en Hero section', icon: 'star' },
]

export function AdminLayout({ children }: PropsWithChildren) {
  const currentUser = useAdminUser()
  const navigate = useNavigate()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const menuTriggerRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)

  const closeMobileMenu = () => setIsMobileMenuOpen(false)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 992px)')
    const updateViewport = () => setIsNarrowViewport(media.matches)
    updateViewport()
    media.addEventListener('change', updateViewport)
    return () => media.removeEventListener('change', updateViewport)
  }, [])

  useEffect(() => {
    const sidebar = sidebarRef.current
    if (!sidebar) return
    if (isNarrowViewport && !isMobileMenuOpen) sidebar.setAttribute('inert', '')
    else sidebar.removeAttribute('inert')
    return () => sidebar.removeAttribute('inert')
  }, [isMobileMenuOpen, isNarrowViewport])

  useEffect(() => {
    if (!isMobileMenuOpen || !isNarrowViewport) return
    const scrollY = window.scrollY
    const previous = {
      overflow: document.body.style.overflow,
      position: document.body.style.position,
      top: document.body.style.top,
      width: document.body.style.width,
    }
    document.body.style.overflow = 'hidden'
    document.body.style.position = 'fixed'
    document.body.style.top = `-${scrollY}px`
    document.body.style.width = '100%'

    const focusable = sidebarRef.current?.querySelector<HTMLElement>('a[href], button:not([disabled])')
    focusable?.focus()
    return () => {
      document.body.style.overflow = previous.overflow
      document.body.style.position = previous.position
      document.body.style.top = previous.top
      document.body.style.width = previous.width
      window.scrollTo(0, scrollY)
      menuTriggerRef.current?.focus()
    }
  }, [isMobileMenuOpen, isNarrowViewport])

  const trapMenuFocus = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeMobileMenu()
      return
    }
    if (event.key !== 'Tab') return
    const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'))
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const handleLogout = () => {
    closeMobileMenu()
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="admin-shell">
      <button ref={menuTriggerRef} type="button" className="admin-mobile-menu-trigger" aria-label="Abrir menú del panel" aria-expanded={isMobileMenuOpen} aria-controls="admin-navigation" onClick={() => setIsMobileMenuOpen(true)}>
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

      <aside ref={sidebarRef} id="admin-navigation" className={`admin-sidebar ${isMobileMenuOpen ? 'admin-sidebar--mobile-open' : ''}`} aria-hidden={isNarrowViewport && !isMobileMenuOpen ? true : undefined} onKeyDown={trapMenuFocus}>
        <div className="admin-sidebar__mobile-header">
          <h2>Panel de administración</h2>
          <button type="button" className="admin-sidebar__mobile-close" onClick={closeMobileMenu} aria-label="Cerrar menú">
            <AdminIcon name="close" />
          </button>
        </div>
        <h2 className="admin-sidebar__title">Panel de administración</h2>
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
