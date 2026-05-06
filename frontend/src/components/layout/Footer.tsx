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
        <p>WhatsApp: +51 987 654 321</p>
        <p>Correo: ventas@alturacomercial.com</p>
        <p>Dirección: Av. Industrial 1234, Lima</p>
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
            <a href="#">Contacto</a>
          </li>
          <li>
            <Link to="/login">Login vendedor</Link>
          </li>
        </ul>
      </div>

      <div>
        <h4>Redes</h4>
        <p>LinkedIn · Facebook · Instagram</p>
      </div>
    </footer>
  )
}
