import { Link } from 'react-router-dom'

import { buildWhatsAppUrl } from '../../utils/whatsapp'

export function Topbar() {
  return (
    <header className="topbar" aria-label="Barra principal">
      <div className="topbar__brand">
        <span className="topbar__logo">▲</span>
        <div>
          <strong>Altura Comercial</strong>
          <small>Equipos y repuestos industriales</small>
        </div>
      </div>

      <div className="topbar__actions">
        <a className="topbar__phone" href="tel:+51987654321">
          +51 987 654 321
        </a>
        <a className="whatsapp-btn" href={buildWhatsAppUrl('Hola, quiero asesoría comercial.')} target="_blank" rel="noreferrer">
          WhatsApp
        </a>
        <Link className="btn btn--ghost" to="/login">
          Login
        </Link>
        <Link className="btn btn--accent" to="/cotizar">
          Cotizar
        </Link>
      </div>
    </header>
  )
}
