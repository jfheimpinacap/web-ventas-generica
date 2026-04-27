import { useState } from 'react'

import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'

export function HomePage() {
  const [searchTerm, setSearchTerm] = useState('')

  return (
    <Layout onSearch={setSearchTerm}>
      <HeroSection />
      <FeaturedProducts searchTerm={searchTerm} />
    </Layout>
  )
}
