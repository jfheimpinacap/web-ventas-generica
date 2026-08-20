import type { QuoteCurrency, QuoteEditorItem } from '../types/commercialQuote'

export const emptyQuoteItem = (): QuoteEditorItem => ({ key: crypto.randomUUID(), source: '', product_id: null, product_name: '', brand_name: '', model_name: '', quantity: '', unit_net_amount: '', discount_percent: '' })
export const isEmptyItem = (item: QuoteEditorItem) => !item.product_name && !item.quantity && !item.unit_net_amount && !item.discount_percent
export function finalUnitNet(item: QuoteEditorItem, currency: QuoteCurrency) {
  const value = Number(item.unit_net_amount) || 0; const discount = Math.min(100, Math.max(0, Number(item.discount_percent) || 0))
  return round(value * (1 - discount / 100), currency)
}
export function lineNetAmount(item: QuoteEditorItem, currency: QuoteCurrency) {
  return round((Number(item.quantity) || 0) * finalUnitNet(item, currency), currency)
}
export function quoteTotals(items: QuoteEditorItem[], currency: QuoteCurrency) {
  const net = round(items.reduce((sum, item) => sum + lineNetAmount(item, currency), 0), currency)
  const tax = round(net * .19, currency); return { net, tax, total: round(net + tax, currency) }
}
export function round(value: number, currency: QuoteCurrency) { const factor = currency === 'CLP' ? 1 : 100; return Math.round((value + Number.EPSILON) * factor) / factor }
export function money(value: number, currency: QuoteCurrency) { return new Intl.NumberFormat('es-CL', { style: 'currency', currency, minimumFractionDigits: currency === 'CLP' ? 0 : 2, maximumFractionDigits: currency === 'CLP' ? 0 : 2 }).format(value) }

const withoutLeadingZeroes = (value: string) => value.replace(/^0+(?=\d)/, '')

export function normalizeNetAmountInput(value: string, currency: QuoteCurrency) {
  if (currency === 'CLP') return /[-+eE]/.test(value) ? null : withoutLeadingZeroes(value.replace(/\D/g, ''))
  if (!value || /[-+eE]/.test(value)) return value ? null : ''
  const commaIndex = value.lastIndexOf(',')
  const dotIndex = value.lastIndexOf('.')
  const decimalIndex = commaIndex >= 0 ? commaIndex : (dotIndex >= 0 && !/^\d{1,3}(\.\d{3})+$/.test(value) ? dotIndex : -1)
  const integer = withoutLeadingZeroes(value.slice(0, decimalIndex < 0 ? undefined : decimalIndex).replace(/\D/g, ''))
  const decimals = decimalIndex < 0 ? '' : value.slice(decimalIndex + 1).replace(/\D/g, '').slice(0, 2)
  if (!integer && decimalIndex < 0) return ''
  return `${integer || '0'}${decimalIndex < 0 ? '' : `.${decimals}`}`
}

export function formatNetAmountInput(value: string, currency: QuoteCurrency) {
  if (!value) return ''
  const [integer = '0', decimals] = value.split('.')
  const grouped = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 }).format(Number(integer) || 0)
  return currency === 'USD' && decimals !== undefined ? `${grouped},${decimals}` : grouped
}

export function normalizeDiscountInput(value: string) {
  if (!value) return ''
  if (/[-+eE]/.test(value) || !/^\d+(?:[.,]\d{0,2})?$/.test(value)) return null
  const normalized = value.replace(',', '.')
  return Number(normalized) > 100 ? '100' : normalized
}
