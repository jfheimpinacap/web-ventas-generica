import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { isAuthenticated } from '../../services/authApi'
import { buildWhatsAppUrl } from '../../utils/whatsapp'

const WHATSAPP_PHONE = '+51 987 654 321'

export function Topbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const hasSession = isAuthenticated()

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

        <div className={`topbar__actions ${isMenuOpen ? 'topbar__actions--open' : ''}`}>
          <div className="topbar__actions-main">
            <a
              className="topbar__whatsapp-contact"
              href={buildWhatsAppUrl('Hola, quiero asesoría comercial.')}
              target="_blank"
              rel="noreferrer"
              aria-label="Abrir WhatsApp con asesor comercial"
            >
              <span className="topbar__whatsapp-icon" aria-hidden="true">
                ✆
              </span>
              <span className="topbar__phone">{WHATSAPP_PHONE}</span>
            </a>
            <NavLink className="topbar__top-link topbar__top-link--home" to="/" onClick={() => setIsMenuOpen(false)}>
              Volver al inicio
            </NavLink>
            <a className="topbar__top-link topbar__top-link--contact" href="#contacto" onClick={() => setIsMenuOpen(false)}>
              Contacto
            </a>
            <Link className="topbar__top-link topbar__top-link--quote" to="/cotizar" onClick={() => setIsMenuOpen(false)}>
              Cotizar
            </Link>
          </div>
          <div className="topbar__seller-access">
            {hasSession ? (
              <Link className="topbar__panel-link" to="/admin" onClick={() => setIsMenuOpen(false)}>
                Volver al panel
              </Link>
            ) : (
              <Link className="topbar__user-link" to="/login" title="Acceso vendedor" aria-label="Acceso vendedor" onClick={() => setIsMenuOpen(false)}>
                <span aria-hidden="true">👤</span>
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
