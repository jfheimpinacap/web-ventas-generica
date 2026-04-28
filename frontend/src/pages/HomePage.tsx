import { Link, useNavigate } from 'react-router-dom'

import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'
import { useCategories } from '../hooks/useCategories'

const commercialBenefits = [
  'Atención directa con vendedor especializado.',
  'Productos de distintos proveedores del rubro industrial.',
  'Cotización rápida para compras técnicas.',
  'Cobertura en repuestos y maquinaria para operación continua.',
]

export function HomePage() {
  const navigate = useNavigate()
  const { categories } = useCategories()
  const highlightedCategories = categories.slice(0, 6)

  return (
    <Layout onSearch={(term) => navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/catalogo')}>
      <HeroSection />

      <section className="home-block">
        <div className="section-heading">
          <h2>Categorías destacadas</h2>
          <p>Accesos rápidos a líneas comerciales con mayor demanda.</p>
        </div>
        <div className="category-grid">
          {(highlightedCategories.length > 0
            ? highlightedCategories.map((category) => ({ id: category.id, name: category.name }))
            : [
                { id: 1, name: 'Plataformas elevadoras' },
                { id: 2, name: 'Repuestos hidráulicos' },
                { id: 3, name: 'Sistemas de seguridad' },
              ]
          ).map((category) => (
            <Link key={category.id} className="category-card" to={`/catalogo?category=${category.id}`}>
              <h3>{category.name}</h3>
              <span>Ver productos →</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="home-block home-block--light">
        <div className="section-heading">
          <h2>¿Por qué cotizar con nosotros?</h2>
          <p>Estructura comercial enfocada en respuesta rápida y asesoría técnica.</p>
        </div>
        <ul className="benefits-grid">
          {commercialBenefits.map((benefit) => (
            <li key={benefit}>{benefit}</li>
          ))}
        </ul>
      </section>

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
