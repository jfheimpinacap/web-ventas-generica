import { ProductTechnicalData } from '../catalog/ProductTechnicalData'
import type { Category, ProductFormValues } from '../../types/catalog'
import { formatCondition, formatPriceValue, formatStockStatus } from '../../utils/formatters'

interface Props { values: ProductFormValues; categories: Category[]; imageUrl: string; imageAlt: string }

export function ProductAdminPreview({ values, categories, imageUrl, imageAlt }: Props) {
  const isService = values.product_type === 'service'
  const selectedSubcategory = categories.find((category) => category.id === values.category && category.parent !== null)
  const usesShortSummary = values.product_type === 'service' || values.product_type === 'spare_part'
  const shortSummary = values.short_description.trim()
  return <article className="product-card admin-product-preview-card">
    <div className="product-card__image-area"><img src={imageUrl} alt={imageAlt} /></div>
    <div className="product-card__content">
      <div className="product-card__badges">
        {!isService ? <span className="badge badge--condition">{formatCondition(values.condition)}</span> : null}
        <span className="badge badge--stock">{isService ? `Disponibilidad: ${formatStockStatus(values.stock_status)}` : formatStockStatus(values.stock_status)}</span>
      </div>
      <h3>{values.name || (isService ? 'Servicio sin nombre' : values.product_type === 'spare_part' ? 'Repuesto sin nombre' : 'Producto sin nombre')}</h3>
      {isService && selectedSubcategory ? <p className="product-card__model">{selectedSubcategory.name}</p> : null}
      {!isService && values.model.trim() ? <p className="product-card__model">{values.model.trim()}</p> : null}
      {values.product_type === 'machinery' ? <ProductTechnicalData productType="machinery" condition={values.condition} workingHeightM={values.working_height_m} maximumLoadCapacityKg={values.maximum_load_capacity_kg} powerSource={values.power_source} terrainType={values.terrain_type} /> : null}
      {usesShortSummary ? <p className="admin-product-preview__summary">{shortSummary || 'Sin descripción para vista previa'}</p> : null}
      <p className="product-card__price">{formatPriceValue(values.price, values.price_visible, values.price_currency, values.price_tax_mode)}</p>
    </div>
    <div className="product-card__actions"><button type="button" className="btn btn--accent" disabled>Ver detalle</button></div>
  </article>
}
