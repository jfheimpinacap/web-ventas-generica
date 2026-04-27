import { useParams } from 'react-router-dom'

import { Layout } from '../components/layout/Layout'

export function ProductDetailPage() {
  const { slug } = useParams()

  return (
    <Layout>
      <section className="simple-page">
        <h1>Detalle de producto</h1>
        <p>Vista base preparada para: {slug}</p>
      </section>
    </Layout>
  )
}
