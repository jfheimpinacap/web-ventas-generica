import { useNavigate } from 'react-router-dom'

import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'

export function HomePage() {
  const navigate = useNavigate()

  return (
    <Layout onSearch={(term) => navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/catalogo')}>
      <HeroSection />
      <FeaturedProducts />
    </Layout>
  )
}
