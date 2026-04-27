import { Link } from 'react-router-dom'

export function HeroSection() {
  return (
    <section className="hero-section">
      <p className="hero-section__tag">Soluciones para trabajo en altura</p>
      <h1>Maquinaria, elevadores y repuestos para trabajos en altura</h1>
      <p>
        Conecta directo con un vendedor especializado y cotiza equipos, repuestos o soluciones para tu operación.
      </p>
      <div className="hero-section__actions">
        <Link to="/" className="btn btn--accent">
          Ver catálogo
        </Link>
        <Link to="/cotizar" className="btn btn--ghost">
          Cotizar ahora
        </Link>
      </div>
    </section>
  )
}
