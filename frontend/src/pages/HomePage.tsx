import { useNavigate } from 'react-router-dom'

import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { Seo } from '../components/common/Seo'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'
import { buildPublicUrl } from '../utils/seo'

export function HomePage() {
  const navigate = useNavigate()
  return (
    <Layout onSearch={(term) => navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/')}>
      <Seo
        title="JEM Nexus | Maquinaria, repuestos y servicios industriales"
        description="Cotiza maquinaria, repuestos y servicios industriales con atención comercial rápida. Revisa promociones, disponibilidad y productos destacados."
        canonical={buildPublicUrl('/')}
        ogType="website"
        ogUrl={buildPublicUrl('/')}
        robots="index,follow"
      />
      <HeroSection />

      <FeaturedProducts />
    </Layout>
  )
}
