import { useEffect } from 'react'

type OgType = 'website' | 'product' | 'article'
type TwitterCard = 'summary' | 'summary_large_image'

interface SeoProps {
  title: string
  description?: string
  canonical?: string
  robots?: string
  ogTitle?: string
  ogDescription?: string
  ogType?: OgType
  ogUrl?: string
  ogImage?: string
  twitterCard?: TwitterCard
  twitterTitle?: string
  twitterDescription?: string
  twitterImage?: string
}

const DEFAULT_TITLE = 'JEM Nexus | Maquinaria, repuestos y servicios industriales'
const DEFAULT_DESCRIPTION =
  'Cotiza maquinaria, repuestos y servicios industriales con atención comercial rápida.'

function upsertMeta(selector: string, attrs: Record<string, string>) {
  let meta = document.head.querySelector(selector) as HTMLMetaElement | null
  if (!meta) {
    meta = document.createElement('meta')
    document.head.appendChild(meta)
  }
  Object.entries(attrs).forEach(([key, value]) => {
    meta?.setAttribute(key, value)
  })
}

function upsertLink(selector: string, rel: string, href: string) {
  let link = document.head.querySelector(selector) as HTMLLinkElement | null
  if (!link) {
    link = document.createElement('link')
    document.head.appendChild(link)
  }
  link.setAttribute('rel', rel)
  link.setAttribute('href', href)
}

function removeHeadElement(selector: string) {
  document.head.querySelector(selector)?.remove()
}

export function Seo({
  title,
  description = DEFAULT_DESCRIPTION,
  canonical,
  robots = 'index,follow',
  ogTitle,
  ogDescription,
  ogType = 'website',
  ogUrl,
  ogImage,
  twitterCard = 'summary',
  twitterTitle,
  twitterDescription,
  twitterImage,
}: SeoProps) {
  useEffect(() => {
    document.title = title || DEFAULT_TITLE

    upsertMeta('meta[name="description"]', { name: 'description', content: description })
    upsertMeta('meta[name="robots"]', { name: 'robots', content: robots })

    const normalizedOgTitle = ogTitle ?? title
    const normalizedOgDescription = ogDescription ?? description
    const normalizedTwitterTitle = twitterTitle ?? normalizedOgTitle
    const normalizedTwitterDescription = twitterDescription ?? normalizedOgDescription

    upsertMeta('meta[property="og:title"]', { property: 'og:title', content: normalizedOgTitle })
    upsertMeta('meta[property="og:description"]', { property: 'og:description', content: normalizedOgDescription })
    upsertMeta('meta[property="og:type"]', { property: 'og:type', content: ogType })
    if (ogUrl) {
      upsertMeta('meta[property="og:url"]', { property: 'og:url', content: ogUrl })
    } else {
      removeHeadElement('meta[property="og:url"]')
    }
    if (ogImage) {
      upsertMeta('meta[property="og:image"]', { property: 'og:image', content: ogImage })
    } else {
      removeHeadElement('meta[property="og:image"]')
    }

    upsertMeta('meta[name="twitter:card"]', { name: 'twitter:card', content: twitterCard })
    upsertMeta('meta[name="twitter:title"]', { name: 'twitter:title', content: normalizedTwitterTitle })
    upsertMeta('meta[name="twitter:description"]', { name: 'twitter:description', content: normalizedTwitterDescription })
    if (twitterImage) {
      upsertMeta('meta[name="twitter:image"]', { name: 'twitter:image', content: twitterImage })
    } else {
      removeHeadElement('meta[name="twitter:image"]')
    }

    if (canonical) {
      upsertLink('link[rel="canonical"]', 'canonical', canonical)
    } else {
      removeHeadElement('link[rel="canonical"]')
    }
  }, [
    canonical,
    description,
    ogDescription,
    ogImage,
    ogTitle,
    ogType,
    ogUrl,
    robots,
    title,
    twitterCard,
    twitterDescription,
    twitterImage,
    twitterTitle,
  ])

  return null
}
