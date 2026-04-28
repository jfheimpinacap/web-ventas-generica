import { useEffect, useState } from 'react'

import { AdminLayout } from '../../components/admin/AdminLayout'
import { getAdminProducts, getAdminPromotions, getAdminQuotes } from '../../services/adminApi'

interface DashboardStats {
  publishedProducts: number
  featuredProducts: number
  quotes: number
  activePromotions: number
}

export function AdminDashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadData = async () => {
      try {
        setError(null)
        const [products, quotes, promotions] = await Promise.all([
          getAdminProducts(),
          getAdminQuotes(),
          getAdminPromotions(),
        ])
        setStats({
          publishedProducts: products.filter((item) => item.is_published).length,
          featuredProducts: products.filter((item) => item.is_featured).length,
          quotes: quotes.length,
          activePromotions: promotions.filter((item) => item.is_active).length,
        })
      } catch {
        setError('No fue posible cargar el dashboard.')
      }
    }

    void loadData()
  }, [])

  return (
    <AdminLayout>
      <section>
        <h1>Dashboard vendedor</h1>
        <p>Resumen rápido de catálogo y oportunidades comerciales.</p>
      </section>

      {error ? <p className="ui-note ui-note--error">{error}</p> : null}

      <section className="admin-cards">
        <article className="admin-card">
          <h3>Productos publicados</h3>
          <strong>{stats?.publishedProducts ?? '-'}</strong>
        </article>
        <article className="admin-card">
          <h3>Productos destacados</h3>
          <strong>{stats?.featuredProducts ?? '-'}</strong>
        </article>
        <article className="admin-card">
          <h3>Cotizaciones recibidas</h3>
          <strong>{stats?.quotes ?? '-'}</strong>
        </article>
        <article className="admin-card">
          <h3>Promociones activas</h3>
          <strong>{stats?.activePromotions ?? '-'}</strong>
        </article>
      </section>
    </AdminLayout>
  )
}
