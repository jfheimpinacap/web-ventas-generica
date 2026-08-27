import { useEffect } from 'react'

import { buildAbsoluteUrl } from '../../utils/seo'
import { useHeadCollector } from './HeadCollector'

type OgType = 'website' | 'product' | 'article'
type TwitterCard = 'summary' | 'summary_large_image'

interface SeoProps {
  title: string
  description: string
  canonical?: string
  robots?: string
  ogTitle?: string
  ogDescription?: string
  ogType?: OgType
  ogImage?: string | null
  imageAlt?: string
  twitterCard?: TwitterCard
}

export const INDEX_ROBOTS = 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1'
export const NOINDEX_ROBOTS = 'noindex,nofollow'

const MANAGED_ATTRIBUTE = 'data-jem-seo'

function upsertHeadElement<T extends HTMLElement>(selector: string, tagName: string, attributes: Record<string, string>) {
  const matches = Array.from(document.head.querySelectorAll<T>(selector))
  const element = matches.shift() ?? document.createElement(tagName) as T
  matches.forEach((duplicate) => duplicate.remove())
  element.setAttribute(MANAGED_ATTRIBUTE, 'true')
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value))
  if (!element.isConnected) document.head.appendChild(element)
}

function removeHeadElements(selector: string) {
  document.head.querySelectorAll(selector).forEach((element) => element.remove())
}

export function Seo({
  title,
  description,
  canonical,
  robots = INDEX_ROBOTS,
  ogTitle = title,
  ogDescription = description,
  ogType = 'website',
  ogImage,
  imageAlt,
  twitterCard = ogImage ? 'summary_large_image' : 'summary',
}: SeoProps) {
  const collector = useHeadCollector()
  const absoluteImage = ogImage?.trim() ? buildAbsoluteUrl(ogImage) : undefined
  if (collector) {
    collector.seo = { title, description, robots, canonical, ogTitle, ogDescription, ogType, ogImage: absoluteImage, imageAlt: imageAlt?.trim() || undefined, twitterCard }
  }

  useEffect(() => {
    document.title = title

    upsertHeadElement<HTMLMetaElement>('meta[name="description"]', 'meta', { name: 'description', content: description })
    upsertHeadElement<HTMLMetaElement>('meta[name="robots"]', 'meta', { name: 'robots', content: robots })
    upsertHeadElement<HTMLMetaElement>('meta[property="og:title"]', 'meta', { property: 'og:title', content: ogTitle })
    upsertHeadElement<HTMLMetaElement>('meta[property="og:description"]', 'meta', { property: 'og:description', content: ogDescription })
    upsertHeadElement<HTMLMetaElement>('meta[property="og:type"]', 'meta', { property: 'og:type', content: ogType })
    upsertHeadElement<HTMLMetaElement>('meta[property="og:site_name"]', 'meta', { property: 'og:site_name', content: 'JEM Nexus' })
    upsertHeadElement<HTMLMetaElement>('meta[property="og:locale"]', 'meta', { property: 'og:locale', content: 'es_CL' })
    upsertHeadElement<HTMLMetaElement>('meta[name="twitter:card"]', 'meta', { name: 'twitter:card', content: twitterCard })
    upsertHeadElement<HTMLMetaElement>('meta[name="twitter:title"]', 'meta', { name: 'twitter:title', content: ogTitle })
    upsertHeadElement<HTMLMetaElement>('meta[name="twitter:description"]', 'meta', { name: 'twitter:description', content: ogDescription })

    if (canonical) {
      upsertHeadElement<HTMLLinkElement>('link[rel="canonical"]', 'link', { rel: 'canonical', href: canonical })
      upsertHeadElement<HTMLMetaElement>('meta[property="og:url"]', 'meta', { property: 'og:url', content: canonical })
    } else {
      removeHeadElements('link[rel="canonical"], meta[property="og:url"]')
    }

    if (absoluteImage) {
      upsertHeadElement<HTMLMetaElement>('meta[property="og:image"]', 'meta', { property: 'og:image', content: absoluteImage })
      upsertHeadElement<HTMLMetaElement>('meta[name="twitter:image"]', 'meta', { name: 'twitter:image', content: absoluteImage })
      if (imageAlt?.trim()) {
        upsertHeadElement<HTMLMetaElement>('meta[property="og:image:alt"]', 'meta', { property: 'og:image:alt', content: imageAlt.trim() })
        upsertHeadElement<HTMLMetaElement>('meta[name="twitter:image:alt"]', 'meta', { name: 'twitter:image:alt', content: imageAlt.trim() })
      } else {
        removeHeadElements('meta[property="og:image:alt"], meta[name="twitter:image:alt"]')
      }
    } else {
      removeHeadElements('meta[property="og:image"], meta[property="og:image:alt"], meta[name="twitter:image"], meta[name="twitter:image:alt"]')
    }
  }, [canonical, description, imageAlt, ogDescription, ogImage, ogTitle, ogType, robots, title, twitterCard])

  return null
}
