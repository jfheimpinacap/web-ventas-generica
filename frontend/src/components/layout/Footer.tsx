import { Link } from 'react-router-dom'

import { useCategories } from '../../hooks/useCategories'

const CATEGORY_FALLBACKS = {
  maquinaria: '/catalogo?product_type=machinery',
  repuestos: '/catalogo?product_type=spare_part',
  servicios: '/catalogo?product_type=service',
}

export function Footer() {
  const { categories } = useCategories()
  const getCategoryHref = (name: keyof typeof CATEGORY_FALLBACKS) => {
    const category = categories.find((item) => item.parent === null && item.name.trim().toLowerCase() === name)
    return category ? `/catalogo?category=${category.id}` : CATEGORY_FALLBACKS[name]
  }

  return (
    <footer className="footer">
      <div id="contacto">
        <h4>Contacto</h4>
        <p>WhatsApp: +56 9 4611 5064</p>
        <p>
          Correo:{' '}
          <a href="mailto:jmateluna@jem-nexus.cl">jmateluna@jem-nexus.cl</a>
        </p>
        <div className="footer__social">
          <h4>Redes</h4>
          <p>
            <a href="https://www.facebook.com/jem.gestion.5" target="_blank" rel="noreferrer">
              <span aria-hidden="true">f</span> Facebook
            </a>
          </p>
          <p>
            <span aria-hidden="true">◎</span> Instagram
          </p>
        </div>
      </div>

      <div>
        <h4>Links rápidos</h4>
        <ul>
          <li>
            <Link to="/">Inicio</Link>
          </li>
          <li>
            <Link to={getCategoryHref('maquinaria')}>Maquinaria</Link>
          </li>
          <li>
            <Link to={getCategoryHref('repuestos')}>Repuestos</Link>
          </li>
          <li>
            <Link to={getCategoryHref('servicios')}>Servicios</Link>
          </li>
          <li>
            <Link to="/cotizar">Cotizar</Link>
          </li>
          <li>
            <Link to="/contacto">Contacto</Link>
          </li>
          <li>
            <Link to="/sobre-nosotros">Sobre nosotros</Link>
          </li>
          <li>
            <Link to="/preguntas-frecuentes">Preguntas frecuentes</Link>
          </li>
        </ul>
      </div>

      <div>
        <h4>Diseño Web y aplicaciones</h4>
        <p>
          Correo:{' '}
          <a href="mailto:fheim@jem-nexus.cl">fheim@jem-nexus.cl</a>
        </p>
        <p>WhatsApp: +56 9 9994 2951</p>
      </div>
    </footer>
  )
}
