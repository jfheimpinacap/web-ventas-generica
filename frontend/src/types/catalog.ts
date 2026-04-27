export interface Category {
  id: number
  name: string
  slug: string
  parent: number | null
  description: string
  is_active: boolean
  order: number
  created_at: string
  updated_at: string
}

export interface Brand {
  id: number
  name: string
  slug: string
  logo: string | null
  description: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SupplierSummary {
  id: number
  name: string
  contact_name: string
  phone: string
  email: string
  notes: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProductImage {
  id: number
  image: string
  alt_text: string
  is_main: boolean
  order: number
  created_at: string
}

export interface ProductSpec {
  id: number
  name: string
  value: string
  unit: string
  order: number
}

export type ProductCondition = 'new' | 'used' | 'refurbished' | 'not_applicable'
export type StockStatus = 'available' | 'on_request' | 'sold' | 'reserved'

export interface ProductListItem {
  id: number
  name: string
  slug: string
  category: Category
  brand: Brand | null
  product_type: string
  condition: ProductCondition
  short_description: string
  price: string | null
  price_visible: boolean
  stock_status: StockStatus
  is_featured: boolean
  main_image: ProductImage | null
}

export interface ProductDetail extends ProductListItem {
  supplier: SupplierSummary | null
  description: string
  model: string
  sku: string
  year: number | null
  hours_meter: number | null
  is_published: boolean
  images: ProductImage[]
  specs: ProductSpec[]
  created_at: string
  updated_at: string
}

export interface Promotion {
  id: number
  title: string
  subtitle: string
  product: ProductListItem | null
  image: string | null
  button_text: string
  button_url: string
  is_active: boolean
  order: number
  starts_at: string | null
  ends_at: string | null
  created_at: string
  updated_at: string
}

export interface QuoteRequestPayload {
  product?: number
  customer_name: string
  customer_phone: string
  customer_email?: string
  message: string
}

export interface SidebarMenuItem {
  label: string
  children?: SidebarMenuItem[]
}
