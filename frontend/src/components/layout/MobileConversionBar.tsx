import { Link } from 'react-router-dom'
import { trackQuoteClick, trackWhatsAppClick } from '../../utils/analytics'
import { buildProductWhatsAppMessage, buildWhatsAppUrl } from '../../utils/whatsapp'

interface Props { product?: { id: number; name: string; product_type: string } }
export function MobileConversionBar({ product }: Props) {
  const quoteUrl = product ? `/cotizar?product=${product.id}` : '/cotizar'
  const message = product ? buildProductWhatsAppMessage(product.name) : 'Hola, quiero solicitar información para una cotización en JEM Nexus.'
  const publicProduct = product ? { product_id: product.id, product_name: product.name, product_type: product.product_type } : {}
  return <aside className="mobile-conversion-bar" aria-label="Acciones comerciales">
    <Link className="btn btn--accent" to={quoteUrl} onClick={() => trackQuoteClick({ location: 'mobile_conversion_bar', ...publicProduct })}>Solicitar cotización</Link>
    <a className="btn btn--whatsapp" href={buildWhatsAppUrl(message)} target="_blank" rel="noreferrer" onClick={() => trackWhatsAppClick({ location: 'mobile_conversion_bar', ...publicProduct })}>WhatsApp</a>
  </aside>
}
