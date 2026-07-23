import { Link } from 'react-router-dom'

const salesOptions = [
  {
    title: 'Venta de maquinaria nueva',
    description: 'Equipos nuevos para operaciones industriales con atención comercial especializada.',
    action: 'Ver maquinaria nueva',
    to: '/maquinaria-nueva',
    image: '/images/maquinaria-nueva.svg',
    alt: 'Ilustración de maquinaria industrial nueva',
  },
  {
    title: 'Venta de maquinaria usada',
    description: 'Equipos usados seleccionados y disponibles para cotización según tu operación.',
    action: 'Ver maquinaria usada',
    to: '/maquinaria-usada',
    image: '/images/maquinaria-usada.svg',
    alt: 'Ilustración de maquinaria industrial usada',
  },
] as const

export function MachinerySalesSection() {
  return (
    <section className="machinery-sales-section" aria-labelledby="machinery-sales-title">
      <div className="section-heading">
        <p className="section-kicker">Soluciones de maquinaria</p>
        <h2 id="machinery-sales-title">Encuentra la maquinaria que necesitas</h2>
      </div>
      <div className="machinery-sales-section__grid">
        {salesOptions.map((option) => (
          <article className="machinery-sales-card" key={option.to}>
            <Link className="machinery-sales-card__link" to={option.to} aria-label={`${option.action}: ${option.description}`}>
              <img className="machinery-sales-card__image" src={option.image} alt={option.alt} />
              <span className="machinery-sales-card__content">
                <h3>{option.title}</h3>
                <span>{option.description}</span>
                <strong>{option.action} <span aria-hidden="true">→</span></strong>
              </span>
            </Link>
          </article>
        ))}
      </div>
    </section>
  )
}
