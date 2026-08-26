import { useNavigate } from 'react-router-dom'

import { MachinerySalesSection } from '../components/catalog/MachinerySalesSection'
import { FeaturedProducts } from '../components/catalog/FeaturedProducts'
import { JsonLd } from '../components/common/JsonLd'
import { INDEX_ROBOTS, Seo } from '../components/common/Seo'
import { HeroSection } from '../components/catalog/HeroSection'
import { Layout } from '../components/layout/Layout'
import { getPublicSiteUrl, getStaticSeo } from '../utils/seo'

export function HomePage() {
  const navigate = useNavigate()
  const siteUrl = getPublicSiteUrl()
  const organizationJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'JEM Nexus',
    url: siteUrl,
    logo: `${siteUrl}/logos/jem-nexus.png`,
    description: 'Maquinaria, repuestos y servicios industriales para cotización comercial.',
    contactPoint: [
      {
        '@type': 'ContactPoint',
        contactType: 'sales',
        availableLanguage: 'Spanish',
      },
    ],
  }

  const websiteJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'JEM Nexus',
    url: siteUrl,
    potentialAction: {
      '@type': 'SearchAction',
      target: `${siteUrl}/catalogo?search={search_term_string}`,
      'query-input': 'required name=search_term_string',
    },
  }

  return (
    <Layout onSearch={(term) => navigate(term ? `/catalogo?search=${encodeURIComponent(term)}` : '/')}>
      <Seo
        {...getStaticSeo('/')}
        ogType="website"
        robots={INDEX_ROBOTS}
      />
      <JsonLd id="home-organization" data={organizationJsonLd} />
      <JsonLd id="home-website" data={websiteJsonLd} />
      <HeroSection />
      <MachinerySalesSection />
      <FeaturedProducts />
    </Layout>
  )
}
