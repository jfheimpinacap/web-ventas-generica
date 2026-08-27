import { createContext, useContext, type PropsWithChildren } from 'react'

export interface CollectedSeo {
  title: string
  description: string
  robots: string
  canonical?: string
  ogTitle: string
  ogDescription: string
  ogType: string
  ogImage?: string
  imageAlt?: string
  twitterCard: string
}

export interface CollectedJsonLd { id: string; serialized: string }

export interface HeadCollector {
  seo?: CollectedSeo
  jsonLd: Map<string, CollectedJsonLd>
}

const HeadCollectorContext = createContext<HeadCollector | null>(null)

export function createHeadCollector(): HeadCollector {
  return { jsonLd: new Map() }
}

export function HeadCollectorProvider({ collector, children }: PropsWithChildren<{ collector: HeadCollector }>) {
  return <HeadCollectorContext.Provider value={collector}>{children}</HeadCollectorContext.Provider>
}

export function useHeadCollector() {
  return useContext(HeadCollectorContext)
}
