import { Link } from 'react-router-dom'

const salesOptions = [
  {
    label: 'Ver catálogo de maquinaria nueva',
    to: '/maquinaria-nueva',
    image: 'https://jem-nexus.cl/imagenes-home/maquinaria-nueva.png',
  },
  {
    label: 'Ver catálogo de maquinaria usada',
    to: '/maquinaria-usada',
    image: 'https://jem-nexus.cl/imagenes-home/maquinaria-usada.png',
  },
] as const

export function MachinerySalesSection() {
  return (
    <section className="machinery-sales-section" aria-label="Soluciones de maquinaria">
      <div className="machinery-sales-section__grid">
        {salesOptions.map((option) => (
          <article className="machinery-sales-card" key={option.to}>
            <Link className="machinery-sales-card__link" to={option.to} aria-label={option.label}>
              <img className="machinery-sales-card__image" src={option.image} alt="" />
            </Link>
          </article>
        ))}
      </div>
    </section>
  )
}
