import { Link, useNavigate } from 'react-router-dom'

import { MachinerySalesSection } from '../components/catalog/MachinerySalesSection'
import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { JsonLd } from '../components/common/JsonLd'
import { INDEX_ROBOTS, Seo } from '../components/common/Seo'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'
import { buildPageJsonLd, ORGANIZATION_ID, PUBLIC_SITE_URL, WEBSITE_ID, getStaticSeo } from '../utils/seo'

const CONTACT_EMAIL = import.meta.env.VITE_CONTACT_EMAIL?.trim() || 'jmateluna@jem-nexus.cl'

export function HomePage() {
  const navigate = useNavigate()
  const homeSeo = getStaticSeo('/')
  const organizationJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': ORGANIZATION_ID,
    name: 'JEM Nexus',
    url: `${PUBLIC_SITE_URL}/`,
    logo: { '@type': 'ImageObject', '@id': `${PUBLIC_SITE_URL}/#logo`, url: `${PUBLIC_SITE_URL}/logos/jem-nexus.png`, contentUrl: `${PUBLIC_SITE_URL}/logos/jem-nexus.png` },
    description: homeSeo.description,
    contactPoint: { '@type': 'ContactPoint', contactType: 'sales', email: CONTACT_EMAIL, availableLanguage: 'es' },
  }

  const websiteJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': WEBSITE_ID,
    name: 'JEM Nexus',
    url: `${PUBLIC_SITE_URL}/`,
    inLanguage: 'es-CL',
    publisher: { '@id': ORGANIZATION_ID },
  }
  const pageJsonLd = buildPageJsonLd('/', 'WebPage', false)

  return (
    <Layout onSearch={(term) => navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/')}>
      <Seo
        {...getStaticSeo('/')}
        ogType="website"
        robots={INDEX_ROBOTS}
      />
      <JsonLd id="home-organization" data={organizationJsonLd} />
      <JsonLd id="home-website" data={websiteJsonLd} />
      <JsonLd id="home-page" data={pageJsonLd} />
      <section className="home-introduction">
        <h1>Maquinaria, repuestos y servicios industriales para cotización</h1>
        <p>Revisa las soluciones publicadas por JEM Nexus y accede a la información disponible para preparar tu solicitud.</p>
        <h2>En pocas palabras</h2>
        <ul><li>Explora maquinaria nueva y usada.</li><li>Consulta publicaciones de repuestos y servicios.</li><li>Envía una solicitud con los antecedentes de tu requerimiento.</li></ul>
        <div className="home-introduction__actions"><Link className="btn btn--ghost" to="/catalogo">Ver catálogo</Link><Link className="btn btn--accent" to="/cotizar">Solicitar cotización</Link></div>
        <nav className="home-introduction__links" aria-label="Soluciones principales"><Link to="/maquinaria-nueva">Maquinaria nueva</Link><Link to="/maquinaria-usada">Maquinaria usada</Link><Link to="/repuestos">Repuestos</Link><Link to="/servicios">Servicios</Link><Link to="/preguntas-frecuentes">Preguntas frecuentes</Link></nav>
      </section>
      <HeroSection />
      <MachinerySalesSection />
      <FeaturedProducts />
    </Layout>
  )
}
