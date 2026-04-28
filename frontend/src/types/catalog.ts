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
  product?: number
  image: string
  alt_text: string
  is_main: boolean
  order: number
  created_at: string
}

export interface ProductSpec {
  id: number
  product?: number
  name: string
  value: string
  unit: string
  order: number
}


export interface ProductImageWritePayload {
  product: number
  image?: File
  alt_text?: string
  is_main?: boolean
  order?: number
}

export interface ProductSpecWritePayload {
  product: number
  name: string
  value: string
  unit?: string
  order?: number
}

export type ProductCondition = 'new' | 'used' | 'refurbished' | 'not_applicable'
export type StockStatus = 'available' | 'on_request' | 'sold' | 'reserved'
export type ProductType = 'machinery' | 'spare_part' | 'service' | 'other'

export interface ProductListItem {
  id: number
  name: string
  slug: string
  category: Category
  brand: Brand | null
  product_type: ProductType
  condition: ProductCondition
  short_description: string
  price: string | null
  price_visible: boolean
  stock_status: StockStatus
  is_featured: boolean
  is_published?: boolean
  main_image: ProductImage | null
  updated_at?: string
}

export interface ProductDetail extends ProductListItem {
  supplier: SupplierSummary | null
  description: string
  model: string
  sku: string
  year: number | null
  hours_meter: number | null
  is_published?: boolean
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

export type HomeSection = 'machinery_promotions' | 'spare_parts_offers' | 'repair_services'

export interface HomeSectionItem {
  id: number
  section: HomeSection
  section_label: string
  position: number
  product: ProductListItem
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface HomeSectionItemFormValues {
  section: HomeSection
  position?: number
  product: number
  is_active?: boolean
}

export type QuoteStatus = 'new' | 'contacted' | 'quoted' | 'closed' | 'discarded'
export type PreferredContactMethod = 'phone' | 'email' | 'whatsapp'

export const QUOTE_STATUS_LABELS: Record<QuoteStatus, string> = {
  new: 'Nueva',
  contacted: 'Contactada',
  quoted: 'Cotizada',
  closed: 'Cerrada',
  discarded: 'Descartada',
}

export const PREFERRED_CONTACT_METHOD_LABELS: Record<PreferredContactMethod, string> = {
  phone: 'Teléfono',
  email: 'Email',
  whatsapp: 'WhatsApp',
}

export interface QuoteRequestPublicPayload {
  product?: number
  customer_name: string
  customer_phone: string
  customer_email?: string
  company_name?: string
  city?: string
  preferred_contact_method?: PreferredContactMethod | ''
  message: string
}

export interface QuoteRequestAdmin {
  id: number
  product: number | null
  product_name?: string
  customer_name: string
  customer_phone: string
  customer_email: string
  company_name: string
  city: string
  preferred_contact_method: PreferredContactMethod | ''
  message: string
  status: QuoteStatus
  internal_notes: string
  seller_response: string
  created_at: string
  updated_at: string
  contacted_at: string | null
  quoted_at: string | null
  closed_at: string | null
}

export interface AuthUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  is_superuser: boolean
}

export interface ProductQueryParams {
  [key: string]: string | boolean | undefined

  search?: string
  category?: string
  brand?: string
  product_type?: ProductType | ''
  condition?: ProductCondition | ''
  stock_status?: StockStatus | ''
  ordering?: 'name' | '-created_at' | 'price' | '-price' | ''
  is_featured?: boolean
}

export interface SidebarMenuItem {
  label: string
  to?: string
  children?: SidebarMenuItem[]
}


export interface CategoryFormValues {
  name: string
  slug?: string
  parent: number | null
  description: string
  is_active: boolean
  order: number
}

export interface BrandFormValues {
  name: string
  slug?: string
  logo?: File | null
  description: string
  is_active: boolean
}

export interface SupplierFormValues {
  name: string
  contact_name: string
  phone: string
  email: string
  notes: string
  is_active: boolean
}

export interface PromotionFormValues {
  title: string
  subtitle: string
  product: number | null
  image?: File | null
  button_text: string
  button_url: string
  is_active: boolean
  order: number
  starts_at: string | null
  ends_at: string | null
}

export interface ProductFormValues {
  name: string
  category: number
  brand: number | null
  supplier: number | null
  product_type: ProductType
  condition: ProductCondition
  short_description: string
  description: string
  model: string
  sku: string
  year: number | null
  hours_meter: number | null
  price: string | null
  price_visible: boolean
  stock_status: StockStatus
  is_featured: boolean
  is_published?: boolean
}
