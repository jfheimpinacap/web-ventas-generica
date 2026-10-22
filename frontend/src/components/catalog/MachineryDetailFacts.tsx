import type { ProductDetail } from '../../types/catalog'
import { formatMachineWeightKg, formatMaximumLoadCapacityKg, formatProductCondition, formatProductPowerSource, formatProductTerrainType, formatStockStatus, formatWorkingHeightM } from '../../utils/formatters'
import { isRentalProduct } from '../../utils/rental'

export function getMachineryFacts(product: ProductDetail) {
  const rental = isRentalProduct(product)
  const items = [
    { label: 'Marca', value: product.brand?.name },
    { label: 'Peso de la máquina', value: formatMachineWeightKg(product.machine_weight_kg) },
    { label: 'Modelo', value: product.model?.trim() },
    { label: 'Fuente de energía', value: formatProductPowerSource(product.power_source) },
    { label: 'Capacidad máxima de carga', value: formatMaximumLoadCapacityKg(product.maximum_load_capacity_kg) },
    { label: 'Altura de plataforma', value: formatWorkingHeightM(product.platform_height_m) },
    { label: 'Altura de trabajo', value: formatWorkingHeightM(product.working_height_m) },
    { label: 'Tipo de terreno', value: formatProductTerrainType(product.terrain_type) },
    { label: 'Año', value: product.year == null ? null : String(product.year) },
    { label: 'Horómetro', value: product.hours_meter == null ? null : product.hours_meter + ' h' },
    ...(!rental ? [
      { label: 'Condición', value: formatProductCondition(product) },
      { label: 'Stock', value: formatStockStatus(product.stock_status) },
    ] : []),
  ].filter(item => item.value)
  return items
}

// Keep existing free-form technical data when its structured counterpart is absent.
function factKey(name: string) {
  const key = name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/^[a-z]\s*[-:]\s*/, '').replace(/\([^)]*\)/g, '').replace(/[^a-z0-9]/g, '')
  const aliases: Record<string, string> = {
    alturamaximadetrabajo: 'alturadetrabajo', alturaplataformalevantada: 'alturadeplataforma',
    capacidaddeplataforma: 'capacidadmaximadecarga', capacidaddelaplataforma: 'capacidadmaximadecarga',
    capacidaddecarga: 'capacidadmaximadecarga', fuentedepotencia: 'fuentedeenergia', modele: 'modelo',
    peso: 'pesodelamaquina', horometroh: 'horometro',
  }
  return aliases[key] ?? key
}

export function getAdditionalProductSpecs(product: ProductDetail) {
  if (product.product_type !== 'machinery') return product.specs
  const present = new Set(getMachineryFacts(product).map(item => factKey(item.label)))
  if (isRentalProduct(product)) { present.add('condicion'); present.add('stock') }
  return product.specs.filter(spec => !present.has(factKey(spec.name)))
}

export function MachineryDetailFacts({ product }: { product: ProductDetail }) {
  const items = getMachineryFacts(product)
  return <dl className="product-detail__facts">
    {items.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
  </dl>
}
