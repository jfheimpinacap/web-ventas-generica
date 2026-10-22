import type { ProductDetail } from '../../types/catalog'
import { isRentalProduct } from '../../utils/rental'

export function ProductIncludedServices({ product }: { product: ProductDetail }) {
  if (product.product_type !== 'machinery') return null
  const services = (isRentalProduct(product) ? [
    { label: 'Asesoría técnica', included: product.rental_includes_technical_advice },
    { label: 'Servicio técnico en caso de falla en obra', included: product.rental_includes_onsite_service },
    { label: 'Coordinación del traslado', included: product.rental_includes_transport_coordination },
  ] : [
    { label: 'Revisión técnica', included: product.includes_technical_review },
    { label: 'Asesoría técnico-comercial', included: product.includes_commercial_technical_advice },
    { label: 'Entrega coordinada', included: product.includes_coordinated_delivery },
  ]).filter(item => item.included === true)
  if (!services.length) return null
  return <section className="product-detail__included-services" aria-labelledby="included-services-title">
    <h2 id="included-services-title">Servicios incluidos</h2>
    <ul className="product-detail__included-services-list">
      {services.map(service => <li className="product-detail__included-service" key={service.label}>
        <span className="product-detail__included-service-icon" aria-hidden="true">✓</span>
        <span>{service.label}</span>
      </li>)}
    </ul>
  </section>
}
