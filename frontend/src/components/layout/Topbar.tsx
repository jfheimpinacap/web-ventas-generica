import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { buildWhatsAppUrl } from '../../utils/whatsapp'

export function Topbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  return (
    <header className="topbar" aria-label="Barra principal">
      <div className="topbar__row">
        <Link className="topbar__brand" to="/" aria-label="Ir al inicio">
          <span className="topbar__logo" aria-hidden="true">
            ▲
          </span>
          <div>
            <strong>Altura Comercial</strong>
            <small>Equipos y repuestos industriales</small>
          </div>
        </Link>

        <button
          className="topbar__menu-toggle"
          type="button"
          aria-label={isMenuOpen ? 'Cerrar navegación' : 'Abrir navegación'}
          onClick={() => setIsMenuOpen((prev) => !prev)}
        >
          {isMenuOpen ? '✕' : '☰'}
        </button>

        <nav className={`topbar__nav ${isMenuOpen ? 'topbar__nav--open' : ''}`} aria-label="Navegación pública">
          <NavLink to="/" onClick={() => setIsMenuOpen(false)}>
            Inicio
          </NavLink>
          <NavLink to="/catalogo" onClick={() => setIsMenuOpen(false)}>
            Catálogo
          </NavLink>
          <NavLink className="btn btn--accent" to="/cotizar" onClick={() => setIsMenuOpen(false)}>
            Cotizar
          </NavLink>
        </nav>

        <div className={`topbar__actions ${isMenuOpen ? 'topbar__actions--open' : ''}`}>
          <a className="topbar__phone" href="tel:+51987654321" aria-label="Llamar al asesor comercial">
            +51 987 654 321
          </a>
          <a
            className="btn btn--whatsapp"
            href={buildWhatsAppUrl('Hola, quiero asesoría comercial.')}
            target="_blank"
            rel="noreferrer"
          >
            WhatsApp
          </a>
          <Link className="btn btn--ghost" to="/login" onClick={() => setIsMenuOpen(false)}>
            Login
          </Link>
        </div>
      </div>
    </header>
  )
}
