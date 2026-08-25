export type QuoteCurrency = 'CLP' | 'USD'
export type SaleCondition = 'Cash' | 'Credit30Days' | 'Credit60Days' | 'HalfCashBalance30' | 'Documented' | 'CashPayment'
export type CommercialQuoteValidityDays = 15 | 30 | 45 | 60

export const SALE_CONDITION_OPTIONS: ReadonlyArray<{ value: SaleCondition; label: string }> = [
  { value: 'Cash', label: 'Contado' },
  { value: 'Credit30Days', label: 'Crédito a 30 días' },
  { value: 'Credit60Days', label: 'Crédito a 60 días' },
  { value: 'HalfCashBalance30', label: '50% contado saldo a 30 días' },
  { value: 'Documented', label: 'Documentado' },
  { value: 'CashPayment', label: 'Efectivo' },
]

export const COMMERCIAL_QUOTE_VALIDITY_OPTIONS: ReadonlyArray<{ value: CommercialQuoteValidityDays; label: string }> = [
  { value: 15, label: '15 días' },
  { value: 30, label: '30 días' },
  { value: 45, label: '45 días' },
  { value: 60, label: '60 días' },
]
export type QuoteItemSource = 'Catalog' | 'FreeText'

export interface CustomerProfile {
  id: number; business_name: string; rut: string; business_activity: string; address: string
  phone: string; city_or_commune: string; contact_name: string; email: string | null
  created_at: string; updated_at: string
}

export interface CustomerSnapshot {
  customer_profile_id: number | null; customer_business_name: string; customer_rut: string
  customer_business_activity: string; customer_address: string; customer_phone: string
  customer_city_or_commune: string; customer_contact_name: string; customer_email: string
}

export interface CommercialQuoteItemInput {
  source: QuoteItemSource; product_id?: number; product_name: string; brand_name?: string
  model_name?: string; quantity: number; unit_net_amount: number; discount_percent?: number
}

export interface CommercialQuoteIssueInput extends CustomerSnapshot {
  currency: QuoteCurrency; sale_condition: SaleCondition; validity_days: CommercialQuoteValidityDays
  detailed_description?: string; items: CommercialQuoteItemInput[]
}

export interface CommercialQuoteItem extends CommercialQuoteItemInput {
  id: number; position: number; discount_percent: number; final_unit_net_amount: number; line_net_amount: number
}

export interface CommercialQuoteDetail extends CustomerSnapshot {
  id: number; status: 'Draft' | 'Issued'; folio: string | null; issued_at: string | null; issued_on: string | null
  seller_name: string; seller_code: string; currency: QuoteCurrency; sale_condition: SaleCondition
  responsibleSellerName: string; responsibleSellerCode: string
  responsibleSellerEmail: string | null; responsibleSellerPhone: string | null
  validityDays: CommercialQuoteValidityDays; detailed_description: string | null; tax_rate_percent: number
  net_amount: number; tax_amount: number; total_amount: number; created_at: string; updated_at: string
  items: CommercialQuoteItem[]
}

export interface CommercialQuoteSummary {
  id: number; status: 'Draft' | 'Issued'; folio: string | null; issued_at: string | null; issued_on: string | null
  currency: QuoteCurrency; customer_business_name: string; customer_rut: string; customer_contact_name: string
  seller_name: string; seller_code: string; net_amount: number; tax_amount: number; total_amount: number
  item_count: number; created_at: string; updated_at: string
}

export interface CommercialQuotePage {
  results: CommercialQuoteSummary[]; page: number; page_size: number; count: number
}

export interface QuoteEditorItem {
  key: string; source: QuoteItemSource | ''; product_id: number | null; product_name: string
  brand_name: string; model_name: string; quantity: string; unit_net_amount: string; discount_percent: string
}
