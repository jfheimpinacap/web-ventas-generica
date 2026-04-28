import { Link, useNavigate } from 'react-router-dom'

import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'

export function HomePage() {
  const navigate = useNavigate()
  return (
    <Layout onSearch={(term) => navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/catalogo')}>
      <HeroSection />

      <section className="quote-cta">
        <div>
          <h2>¿Necesitas precio y disponibilidad hoy?</h2>
          <p>Envíanos los detalles y un vendedor te responde para cerrar tu cotización.</p>
        </div>
        <div className="quote-cta__actions">
          <Link to="/cotizar" className="btn btn--accent">
            Cotizar ahora
          </Link>
          <Link to="/catalogo" className="btn btn--ghost">
            Ver catálogo
          </Link>
        </div>
      </section>

      <FeaturedProducts />
    </Layout>
  )
}
