import { isRentalProduct, parseRentalPriceInput, RENTAL_RATE_FIELDS } from '../../utils/rental'
import { RentalRates } from '../catalog/RentalRates'
import { ProductTechnicalData } from '../catalog/ProductTechnicalData'
import type { Brand, Category, ProductFormValues } from '../../types/catalog'
import { formatCondition, formatPriceValue, formatStockStatus } from '../../utils/formatters'
import { useAdminProductImageUrl } from '../../hooks/useAdminProductImageUrl'

interface Props { values: ProductFormValues; categories: Category[]; brands: Brand[]; imageUrl: string; imageAlt: string; existingImageId?: number | null }

export function ProductAdminPreview({ values, categories, brands, imageUrl, imageAlt, existingImageId = null }: Props) {
  const { url: authenticatedImageUrl } = useAdminProductImageUrl(existingImageId)
  const isRental = isRentalProduct(values)
  const rentalPreview = { ...values, ...Object.fromEntries(RENTAL_RATE_FIELDS.map(({ key }) => {
    const parsed = parseRentalPriceInput(values[key])
    return [key, parsed.value === null ? null : String(parsed.value)]
  })) }
  const isService = values.product_type === 'service'
  const selectedSubcategory = categories.find((category) => category.id === values.category && category.parent !== null)
  const usesShortSummary = values.product_type === 'service' || values.product_type === 'spare_part'
  const shortSummary = values.short_description.trim()
  return <article className="product-card admin-product-preview-card">
    <div className="product-card__image-area"><img src={authenticatedImageUrl || imageUrl} alt={imageAlt} /></div>
    <div className="product-card__content">
      <div className="product-card__badges">
        {isRental ? <span className="badge badge--condition">Maquinaria para arriendo</span> : !isService ? <span className="badge badge--condition">{formatCondition(values.condition)}</span> : null}
        {!isRental ? <span className="badge badge--stock">{isService ? `Disponibilidad: ${formatStockStatus(values.stock_status)}` : formatStockStatus(values.stock_status)}</span> : null}
      </div>
      <h3>{values.name || (isService ? 'Servicio sin nombre' : values.product_type === 'spare_part' ? 'Repuesto sin nombre' : 'Producto sin nombre')}</h3>
      {isService && selectedSubcategory ? <p className="product-card__model">{selectedSubcategory.name}</p> : null}
      {!isService && !isRental && values.model.trim() ? <p className="product-card__model">{values.model.trim()}</p> : null}
      {values.product_type === 'machinery' ? <ProductTechnicalData productType="machinery" condition={values.condition} commercialMode={values.commercial_mode} brandName={brands.find(brand => brand.id === values.brand)?.name} model={values.model} machineWeightKg={values.machine_weight_kg} platformHeightM={values.platform_height_m} workingHeightM={values.working_height_m} maximumLoadCapacityKg={values.maximum_load_capacity_kg} powerSource={values.power_source} terrainType={values.terrain_type} /> : null}
      {usesShortSummary ? <p className="admin-product-preview__summary">{shortSummary || 'Sin descripción para vista previa'}</p> : null}
      <div className="product-card__pricing">
        {isRental ? <RentalRates product={rentalPreview} /> : <p className="product-card__price">{formatPriceValue(values.price, values.price_visible, values.price_currency, values.price_tax_mode)}</p>}
      </div>
    </div>
    <div className="product-card__actions"><button type="button" className="btn btn--accent" disabled>Ver detalle</button></div>
  </article>
}
