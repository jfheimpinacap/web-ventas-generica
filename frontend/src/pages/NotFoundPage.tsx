import { Link } from 'react-router-dom'

import { Seo } from '../components/common/Seo'
import { Layout } from '../components/layout/Layout'

export function NotFoundPage() {
  return (
    <Layout>
      <Seo
        title="Página no encontrada | JEM Nexus"
        description="La página solicitada no existe o ya no está disponible."
        robots="noindex,nofollow"
        ogType="website"
      />

      <section className="not-found-page" aria-labelledby="not-found-title">
        <div className="not-found-page__content">
          <p className="not-found-page__code" aria-hidden="true">
            404
          </p>
          <p className="not-found-page__eyebrow">Error 404</p>
          <h1 id="not-found-title">Página no encontrada</h1>
          <p className="not-found-page__description">
            La dirección que intentaste abrir no existe, fue movida o ya no está disponible.
          </p>
          <div className="not-found-page__actions">
            <Link className="btn btn--accent" to="/">
              Volver al inicio
            </Link>
            <Link className="btn btn--ghost" to="/catalogo">
              Ver catálogo
            </Link>
          </div>
        </div>
      </section>
    </Layout>
  )
}
