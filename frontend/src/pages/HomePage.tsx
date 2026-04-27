import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'

export function HomePage() {
  return (
    <Layout>
      <HeroSection />
      <FeaturedProducts />
    </Layout>
  )
}
