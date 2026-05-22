import { Link } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'
import { Seo } from '../components/common/Seo'
import { buildPublicUrl } from '../utils/seo'

export function AboutPage() {
  return (
    <Layout>
      <Seo
        title="Sobre JEM Nexus | Maquinaria, repuestos y servicios industriales"
        description="Conoce JEM Nexus, plataforma comercial para cotizar maquinaria, repuestos y servicios industriales con atención personalizada."
        canonical={buildPublicUrl('/sobre-nosotros')}
        ogType="website"
        ogUrl={buildPublicUrl('/sobre-nosotros')}
        robots="index,follow"
      />

      <section className="simple-page trust-page">
        <h1>Sobre JEM Nexus</h1>
        <p>
          JEM Nexus es una plataforma comercial enfocada en la cotización de maquinaria, repuestos y servicios industriales. Su
          objetivo es facilitar el acceso a información de productos, disponibilidad y atención personalizada para empresas y
          operaciones que requieren soluciones confiables.
        </p>

        <div className="trust-page__grid">
          <article className="trust-page__card"><h2>Maquinaria</h2><p>Equipos para operación industrial con información comercial y técnica.</p></article>
          <article className="trust-page__card"><h2>Repuestos</h2><p>Componentes y piezas para continuidad operativa según requerimiento.</p></article>
          <article className="trust-page__card"><h2>Servicios</h2><p>Opciones asociadas a reparación y mantención industrial, según disponibilidad.</p></article>
          <article className="trust-page__card"><h2>Atención comercial</h2><p>Acompañamiento para validar disponibilidad, precio y alternativa adecuada.</p></article>
        </div>

        <div className="trust-page__actions">
          <Link className="btn btn--ghost" to="/catalogo">Ver productos</Link>
          <Link className="btn btn--accent" to="/cotizar">Cotizar ahora</Link>
        </div>
      </section>
    </Layout>
  )
}
