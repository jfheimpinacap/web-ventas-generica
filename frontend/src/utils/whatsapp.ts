const DEFAULT_WHATSAPP_NUMBER = '56912345678'

export const WHATSAPP_NUMBER = import.meta.env.VITE_WHATSAPP_NUMBER || DEFAULT_WHATSAPP_NUMBER

export function buildWhatsAppUrl(message: string, number = WHATSAPP_NUMBER) {
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`
}

export function buildProductWhatsAppMessage(productName: string) {
  return `Hola, estoy interesado en cotizar el producto: ${productName}. ¿Me puedes enviar más información?`
}
