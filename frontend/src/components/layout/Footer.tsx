import { Link } from 'react-router-dom'

export function Footer() {
  return (
    <footer className="footer">
      <div>
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
            <Link to="/">Catálogo</Link>
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
