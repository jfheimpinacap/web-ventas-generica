import type { RentalProductFields } from '../types/catalog.ts'

export const RENTAL_RATE_FIELDS = [
  { key: 'rental_price_day', label: 'Precio día' },
  { key: 'rental_price_week', label: 'Precio semana' },
  { key: 'rental_price_month', label: 'Precio mes' },
] as const

export function isRentalProduct(product: RentalProductFields | null | undefined) {
  return product?.commercial_mode === 'rental'
}

// Dots are accepted only as Chilean thousands separators, never as decimals.
export function parseRentalPriceInput(input: string | null | undefined): { value: number | null; error: string | null } {
  const text = input?.trim() ?? ''
  if (!text) return { value: null, error: null }
  if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)$/.test(text)) return { value: null, error: 'Ingresa pesos enteros, sin negativos ni decimales.' }
  const value = Number(text.replace(/\./g, ''))
  if (!Number.isSafeInteger(value) || value > 999999999999) return { value: null, error: 'El importe excede el máximo permitido.' }
  return { value, error: null }
}

export function formatRentalAmount(value: string | null | undefined) {
  if (value === null || value === undefined || value.trim() === '') return null
  const amount = Number(value)
  if (!Number.isSafeInteger(amount) || amount < 0) return null
  return '$' + new Intl.NumberFormat('es-CL', { maximumFractionDigits: 0 }).format(amount)
}

export function catalogPrice(product: RentalProductFields & { price: string | null; price_visible: boolean }) {
  const raw = isRentalProduct(product) ? product.rental_price_day : product.price
  if (!product.price_visible || raw === null || raw === undefined || raw === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}
