import type { RentalProductFields } from '../../types/catalog'
import { formatRentalAmount, RENTAL_RATE_FIELDS } from '../../utils/rental'

export function RentalRates({ product }: { product: RentalProductFields & { price_visible: boolean } }) {
  return <div className="rental-commercial">
    {product.price_visible ? <dl className="rental-rates" aria-label="Tarifas de arriendo en pesos chilenos">
      {RENTAL_RATE_FIELDS.map(({ key, label }) => {
        const amount = formatRentalAmount(product[key])
        return <div className="rental-rates__row" key={key}>
          <dt>{label}:</dt>
          <dd>{amount ? <><strong>{amount}</strong> <span>+ IVA</span></> : <strong>Consultar</strong>}</dd>
        </div>
      })}
    </dl> : <p className="rental-rates__hidden">Consultar tarifas</p>}
    <div className="rental-commercial__notes">
      <p>Traslado se cotiza por separado.</p>
      <p>Disponibilidad sujeta a confirmación.</p>
    </div>
  </div>
}
