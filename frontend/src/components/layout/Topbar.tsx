import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useCategories } from '../../hooks/useCategories'
import { isAuthenticated } from '../../services/authApi'
import { buildWhatsAppUrl } from '../../utils/whatsapp'
import { CategoriesMegaMenu } from './CategoriesMegaMenu'

const WHATSAPP_PHONE = '+51 987 654 321'

export function Topbar() {
  const [isCategoriesOpen, setIsCategoriesOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const navigate = useNavigate()
  const hasSession = isAuthenticated()
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
    navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/catalogo')
  }

  return (
    <header className="topbar" aria-label="Barra principal">
      <div className="topbar__row">
        <Link className="topbar__brand" to="/" aria-label="Ir al inicio">
          <span className="topbar__logo" aria-hidden="true">
            ▲
          </span>
          <div>
            <strong>Altura Comercial</strong>
            <small>Maquinaria, repuestos y servicios</small>
          </div>
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
            aria-label="Buscar en el catálogo"
          />
          <button type="submit" aria-label="Buscar">
            🔍
          </button>
        </form>

        <Link className="topbar__top-link topbar__top-link--quote" to="/cotizar">
          Cotizar
        </Link>

        <a
          className="topbar__whatsapp-contact"
          href={buildWhatsAppUrl('Hola, quiero asesoría comercial.')}
          target="_blank"
          rel="noreferrer"
          aria-label="Abrir WhatsApp con asesor comercial"
        >
          <span className="topbar__whatsapp-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path d="M6.62 10.79a15.05 15.05 0 0 0 6.59 6.59l2.2-2.2a1 1 0 0 1 1.02-.24c1.12.37 2.33.57 3.57.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1C10.61 21 3 13.39 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.24.2 2.45.57 3.57a1 1 0 0 1-.24 1.02l-2.21 2.2Z" />
            </svg>
          </span>
          <span className="topbar__phone">{WHATSAPP_PHONE}</span>
          <span className="topbar__phone-compact" aria-hidden="true">987 654 321</span>
        </a>

        {hasSession ? (
          <Link className="topbar__panel-link topbar__seller-link" to="/admin">
            Panel
          </Link>
        ) : (
          <Link className="topbar__user-link topbar__seller-link" to="/login" title="Acceso vendedor" aria-label="Acceso vendedor">
            <span aria-hidden="true">👤</span>
          </Link>
        )}
      </div>
      <CategoriesMegaMenu isOpen={isCategoriesOpen} categories={categories} onClose={() => setIsCategoriesOpen(false)} />
    </header>
  )
}
