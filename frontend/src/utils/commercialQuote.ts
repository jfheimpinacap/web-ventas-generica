import type { QuoteCurrency, QuoteEditorItem } from '../types/commercialQuote'

export const emptyQuoteItem = (): QuoteEditorItem => ({ key: crypto.randomUUID(), source: '', product_id: null, product_name: '', brand_name: '', model_name: '', quantity: '', unit_net_amount: '', discount_percent: '' })
export const isEmptyItem = (item: QuoteEditorItem) => !item.product_name && !item.quantity && !item.unit_net_amount && !item.discount_percent
export function finalUnitNet(item: QuoteEditorItem, currency: QuoteCurrency) {
  const value = Number(item.unit_net_amount) || 0; const discount = Number(item.discount_percent) || 0
  return round(value * (1 - discount / 100), currency)
}
export function quoteTotals(items: QuoteEditorItem[], currency: QuoteCurrency) {
  const net = round(items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * finalUnitNet(item, currency), 0), currency)
  const tax = round(net * .19, currency); return { net, tax, total: round(net + tax, currency) }
}
export function round(value: number, currency: QuoteCurrency) { const factor = currency === 'CLP' ? 1 : 100; return Math.round((value + Number.EPSILON) * factor) / factor }
export function money(value: number, currency: QuoteCurrency) { return new Intl.NumberFormat('es-CL', { style: 'currency', currency, minimumFractionDigits: currency === 'CLP' ? 0 : 2, maximumFractionDigits: currency === 'CLP' ? 0 : 2 }).format(value) }
