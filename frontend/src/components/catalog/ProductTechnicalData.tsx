import type { ProductCondition, ProductPowerSource, ProductTerrainType, ProductType } from '../../types/catalog'
import {
  formatMaximumLoadCapacityKg,
  formatProductPowerSource,
  formatProductTerrainType,
  formatWorkingHeightM,
} from '../../utils/formatters'

interface ProductTechnicalDataProps {
  productType: ProductType
  condition: ProductCondition
  workingHeightM?: number | null
  maximumLoadCapacityKg?: number | null
  powerSource?: ProductPowerSource | null
  terrainType?: ProductTerrainType | null
}

export function ProductTechnicalData({
  productType,
  condition,
  workingHeightM,
  maximumLoadCapacityKg,
  powerSource,
  terrainType,
}: ProductTechnicalDataProps) {
  if (productType !== 'machinery' || (condition !== 'new' && condition !== 'used')) return null

  const items = [
    { label: 'Altura de trabajo', value: formatWorkingHeightM(workingHeightM) },
    { label: 'Capacidad de carga', value: formatMaximumLoadCapacityKg(maximumLoadCapacityKg) },
    { label: 'Fuente de energía', value: formatProductPowerSource(powerSource) },
    { label: 'Tipo de terreno', value: formatProductTerrainType(terrainType) },
  ].filter((item): item is { label: string; value: string } => Boolean(item.value))

  if (!items.length) return null

  return (
    <dl className="product-card__technical-data">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}
