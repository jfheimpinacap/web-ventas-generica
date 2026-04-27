const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export function HomePage() {
  return (
    <main className="home-layout">
      <h1>Base Comercial Full Stack</h1>
      <p>Proyecto inicial para catálogo de maquinaria, elevadores y repuestos.</p>
      <p>
        Backend API esperado en: <code>{apiBaseUrl}/api/health/</code>
      </p>
      <section>
        <h2>Próximas fases</h2>
        <ul>
          <li>Catálogo de productos y categorías con subcategorías</li>
          <li>Productos destacados</li>
          <li>Módulo de cotizaciones</li>
          <li>Login de vendedor</li>
          <li>Panel de administración personalizado</li>
        </ul>
      </section>
    </main>
  )
}
