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
            <small>Equipos y repuestos industriales</small>
          </div>
        </Link>
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

        <button
          className="topbar__categories-btn"
          type="button"
          aria-expanded={isCategoriesOpen}
          aria-label="Abrir categorías"
          onClick={() => setIsCategoriesOpen((prev) => !prev)}
          aria-controls="categories-mega-menu"
        >
          <span aria-hidden="true">☰</span>
          <span>Categorías</span>
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

        <div className="topbar__actions">
          <div className="topbar__actions-main">
            <a className="topbar__top-link topbar__top-link--contact" href="#contacto">
              Contacto
            </a>
            <Link className="topbar__top-link topbar__top-link--quote" to="/cotizar">
              Cotizar
            </Link>
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
        </div>
      </div>
      <CategoriesMegaMenu
        isOpen={isCategoriesOpen}
        categories={categories}
        onClose={() => setIsCategoriesOpen(false)}
      />
    </header>
  )
}
