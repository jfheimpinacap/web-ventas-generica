import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useCategories } from '../../hooks/useCategories'
import { trackQuoteClick, trackWhatsAppClick } from '../../utils/analytics'
import { buildWhatsAppUrl } from '../../utils/whatsapp'
import { CategoriesMegaMenu } from './CategoriesMegaMenu'

const WHATSAPP_PHONE = '+56 9 4611 5064'

export function Topbar() {
  const [isCategoriesOpen, setIsCategoriesOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const navigate = useNavigate()
  const { categories } = useCategories()

  useEffect(() => {
    if (!isCategoriesOpen) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsCategoriesOpen(false)
      }
    }

    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKeyDown)

    return () => {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [isCategoriesOpen])

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    const term = searchValue.trim()
    navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/')
  }

  return (
    <header className="topbar" aria-label="Barra principal">
      <div className="topbar__row">
        <Link className="topbar__brand" to="/" aria-label="Ir al inicio">
          <img className="topbar__logo" src="/logos/jem-nexus.png" alt="JEM Nexus" loading="eager" decoding="async" />
        </Link>

        <button
          className="topbar__categories-btn"
          type="button"
          aria-expanded={isCategoriesOpen}
          aria-label="Abrir categorías"
          onClick={() => setIsCategoriesOpen((prev) => !prev)}
          aria-controls="categories-mega-menu"
        >
          <span className="topbar__categories-icon" aria-hidden="true">☰</span>
          <span className="topbar__categories-label">Categorías</span>
        </button>

        <form className="topbar__search" role="search" onSubmit={handleSearch}>
          <input
            type="search"
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder="Busca maquinaria, repuestos y servicios"
            aria-label="Buscar productos"
          />
          <button type="submit" aria-label="Buscar">
            🔍
          </button>
        </form>

        <Link className="topbar__top-link topbar__top-link--contact" to="/contacto">
          Contacto
        </Link>

        <Link className="topbar__top-link topbar__top-link--quote" to="/cotizar" onClick={() => trackQuoteClick({ location: 'topbar' })}>
          Cotizar
        </Link>

        <a
          className="topbar__whatsapp-contact"
          href={buildWhatsAppUrl('Hola, quiero consultar por una cotización en JEM Nexus.')}
          target="_blank"
          rel="noreferrer"
          aria-label="Abrir WhatsApp con asesor comercial"
          onClick={() => trackWhatsAppClick({ location: 'topbar' })}
        >
          <span className="topbar__whatsapp-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24c1.12.37 2.33.57 3.57.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1C10.61 21 3 13.39 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.24.2 2.45.57 3.57a1 1 0 0 1-.24 1.02l-2.21 2.2Z" />
            </svg>
          </span>
          <span className="topbar__phone">{WHATSAPP_PHONE}</span>
          <span className="topbar__phone-compact" aria-hidden="true">9 4611 5064</span>
        </a>

      </div>
      <CategoriesMegaMenu isOpen={isCategoriesOpen} categories={categories} onClose={() => setIsCategoriesOpen(false)} />
    </header>
  )
}
