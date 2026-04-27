export type ProductCondition = 'Nuevo' | 'Usado' | 'Reacondicionado'

export interface CatalogProduct {
  id: number
  slug: string
  name: string
  brand: string
  category: string
  condition: ProductCondition
  priceLabel: string
  imageUrl: string
}

export interface SidebarMenuItem {
  label: string
  children?: SidebarMenuItem[]
}
