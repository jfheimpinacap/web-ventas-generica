import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'

import type { Brand, Category, ProductCondition, ProductFormValues, ProductPowerSource, ProductPriceCurrency, ProductPriceTaxMode, ProductTerrainType, ProductType, StockStatus, SupplierSummary, TechnicalSheet } from '../../types/catalog'
import { getRootCategory, inferProductTypeFromRootCategory, isValidChileanPriceInput, normalizeChileanPriceInput } from '../../utils/formatters'
import { ProductEditorActions } from './ProductEditorActions'

interface ProductFormProps {
  initialValues: ProductFormValues
  categories: Category[]
  brands: Brand[]
  suppliers: SupplierSummary[]
  technicalSheets: TechnicalSheet[]
  onSubmit: (values: ProductFormValues) => Promise<void>
  isSubmitting: boolean
  error: string | null
  onValuesChange?: (values: ProductFormValues) => void
  beforeActions?: ReactNode
  formId: string
  onCancel: () => void
}

const PRODUCT_CONDITIONS: Array<{ value: ProductCondition; label: string }> = [
  { value: 'new', label: 'Nuevo' },
  { value: 'used', label: 'Usado' },
  { value: 'refurbished', label: 'Reacondicionado' },
  { value: 'not_applicable', label: 'No aplica' },
]

const STOCK_STATUSES: Array<{ value: StockStatus; label: string }> = [
  { value: 'available', label: 'Disponible' },
  { value: 'on_request', label: 'A pedido' },
  { value: 'reserved', label: 'Reservado' },
  { value: 'sold', label: 'Vendido' },
]

export const TERRAIN_TYPE_OPTIONS: Array<{ value: ProductTerrainType; label: string }> = [
  { value: 'indoor_smooth', label: 'Interior liso' },
  { value: 'outdoor', label: 'Exterior' },
  { value: 'outdoor_slopes_and_ramps', label: 'Exterior con pendientes y rampas' },
]

function formatDecimalInput(value: number | null) {
  return value === null ? '' : String(value).replace('.', ',')
}

function parseWorkingHeight(value: string) {
  const normalized = value.trim().replace(',', '.')
  if (!normalized) return { value: null, error: null }
  if (!/^-?\d+(?:[.,]\d{1,2})?$/.test(value.trim())) {
    return { value: null, error: 'Ingresa una altura válida con hasta dos decimales.' }
  }
  const parsed = Number(normalized)
  if (parsed <= 0) {
    return { value: null, error: 'La altura de trabajo debe ser mayor que cero.' }
  }
  return { value: parsed, error: null }
}

function toNullableNumber(value: string) {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function withBenefitsForProductType(values: ProductFormValues, productType: ProductType) {
  if (productType === values.product_type) return values
  const includesBenefits = productType === 'machinery'
  return {
    ...values,
    product_type: productType,
    includes_technical_review: includesBenefits,
    includes_commercial_technical_advice: includesBenefits,
    includes_coordinated_delivery: includesBenefits,
  }
}

export function ProductForm({
  initialValues,
  categories,
  brands,
  suppliers,
  technicalSheets,
  onSubmit,
  isSubmitting,
  error,
  onValuesChange,
  beforeActions,
  formId,
  onCancel,
}: ProductFormProps) {
  const [values, setValues] = useState<ProductFormValues>(initialValues)
  const [priceError, setPriceError] = useState<string | null>(null)
  const [workingHeightInput, setWorkingHeightInput] = useState(() => formatDecimalInput(initialValues.working_height_m))
  const [workingHeightError, setWorkingHeightError] = useState<string | null>(null)
  const [primaryCategoryId, setPrimaryCategoryId] = useState<number | null>(null)

  useEffect(() => {
    setValues(initialValues)
    setPrimaryCategoryId(null)
    setPriceError(null)
    setWorkingHeightInput(formatDecimalInput(initialValues.working_height_m))
    setWorkingHeightError(null)
  }, [initialValues])

  useEffect(() => {
    onValuesChange?.(values)
  }, [onValuesChange, values])

  const rootCategories = useMemo(() => categories.filter((item) => item.is_active && item.parent === null).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)), [categories])
  const selectedCategory = useMemo(() => categories.find((item) => item.id === values.category) ?? null, [categories, values.category])
  const categoryRoot = useMemo(() => getRootCategory(selectedCategory, categories), [categories, selectedCategory])
  const selectedRootId = categoryRoot?.id ?? primaryCategoryId
  const selectedRoot = useMemo(() => categories.find((item) => item.id === selectedRootId) ?? categoryRoot, [categories, categoryRoot, selectedRootId])
  const subcategoryOptions = useMemo(() => selectedRootId ? categories.filter((item) => item.is_active && item.parent === selectedRootId).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)) : [], [categories, selectedRootId])
  const brandsOptions = useMemo(() => brands.filter((item) => item.is_active), [brands])
  const suppliersOptions = useMemo(() => suppliers.filter((item) => item.is_active), [suppliers])
  const technicalSheetOptions = useMemo(() => [...technicalSheets].sort((a, b) => a.name.localeCompare(b.name, 'es')), [technicalSheets])

  const setField = <K extends keyof ProductFormValues>(field: K, nextValue: ProductFormValues[K]) => {
    setValues((prev) => {
      if (field === 'product_type') return prev
      if (field === 'category') {
        const selected = categories.find((item) => item.id === nextValue) ?? null
        const root = getRootCategory(selected, categories) ?? selected
        if (selected?.parent === null) {
          setPrimaryCategoryId(selected.id)
          return { ...withBenefitsForProductType(prev, inferProductTypeFromRootCategory(selected)), category: 0 }
        }
        setPrimaryCategoryId(root?.id ?? null)
        return { ...withBenefitsForProductType(prev, inferProductTypeFromRootCategory(root)), category: Number(nextValue) }
      }
      return { ...prev, [field]: nextValue }
    })
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!isValidChileanPriceInput(values.price)) {
      setPriceError('Ingresa un precio válido usando solo números y puntos como separador de miles.')
      return
    }

    const workingHeight = parseWorkingHeight(workingHeightInput)
    if (workingHeight.error) {
      setWorkingHeightError(workingHeight.error)
      return
    }

    setPriceError(null)
    await onSubmit({
      ...values,
      working_height_m: workingHeight.value,
      product_type: inferProductTypeFromRootCategory(selectedRoot),
      short_description: values.short_description || values.description.trim().slice(0, 280),
      price: normalizeChileanPriceInput(values.price),
    })
  }

  const maximumYear = new Date().getFullYear() + 1

  return (
    <form id={formId} className="admin-product-form admin-product-editor-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__notice">{error}</p> : null}

      <div className="admin-product-information-grid">
        <section className="admin-form-panel admin-form-panel--product-grid">
        <h3>Información general</h3>

        <label className="admin-form-panel__span-2 admin-product-name-field">
          Nombre
          <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
        </label>

        <label>
          Categoría principal
          <select value={selectedRootId ?? ''} onChange={(e) => setField('category', Number(e.target.value))} required>
            <option value="">Selecciona categoría principal</option>
            {rootCategories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Subcategoría
          <select value={selectedCategory?.parent ? values.category : ''} onChange={(e) => setField('category', Number(e.target.value))} required disabled={!selectedRootId || subcategoryOptions.length === 0}>
            <option value="">Selecciona subcategoría</option>
            {subcategoryOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          {selectedRootId && subcategoryOptions.length === 0 ? (
            <span className="ui-note">No hay subcategorías activas para esta categoría principal. Puedes crearlas desde Categorías.</span>
          ) : null}
        </label>

        <label>
          Marca
          <select value={values.brand ?? ''} onChange={(e) => setField('brand', toNullableNumber(e.target.value))}>
            <option value="">Sin marca</option>
            {brandsOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Proveedor
          <select value={values.supplier ?? ''} onChange={(e) => setField('supplier', toNullableNumber(e.target.value))}>
            <option value="">Sin proveedor</option>
            {suppliersOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <div className="admin-form-panel__full admin-product-condition-row">
          <label>
            Condición
            <select value={values.condition} onChange={(e) => setField('condition', e.target.value as ProductCondition)} required>
              {PRODUCT_CONDITIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            Stock
            <select value={values.stock_status} onChange={(e) => setField('stock_status', e.target.value as StockStatus)} required>
              {STOCK_STATUSES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="admin-form-panel__full admin-price-row">
          <label>
            Moneda
            <select value={values.price_currency} onChange={(e) => setField('price_currency', e.target.value as ProductPriceCurrency)} required>
              <option value="CLP">CLP / $</option>
              <option value="USD">USD</option>
            </select>
          </label>

          <label>
            Precio
            <input
              inputMode="numeric"
              value={values.price ?? ''}
              onChange={(e) => {
                setField('price', e.target.value || null)
                if (priceError) setPriceError(null)
              }}
              aria-invalid={Boolean(priceError)}
              aria-describedby={priceError ? 'product-price-error' : undefined}
            />
            {priceError ? <span id="product-price-error" className="ui-note ui-note--error">{priceError}</span> : null}
          </label>

          <label>
            IVA
            <select value={values.price_tax_mode} onChange={(e) => setField('price_tax_mode', e.target.value as ProductPriceTaxMode)} required>
              <option value="plus_vat">+ IVA</option>
              <option value="vat_included">IVA incluido</option>
            </select>
          </label>
        </div>

        <div className="admin-form-switches">
          <label className="admin-checkbox">
            <input
              type="checkbox"
              checked={values.price_visible}
              onChange={(e) => setField('price_visible', e.target.checked)}
            />
            Mostrar precio
          </label>

          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_published} onChange={(e) => setField('is_published', e.target.checked)} />
            Publicado
          </label>

          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_featured} onChange={(e) => setField('is_featured', e.target.checked)} />
            Destacado
          </label>
        </div>
        </section>

        <section className="admin-form-panel admin-product-technical-grid">
        <h3>Información técnica / comercial</h3>

        <label>
          Modelo
          <input value={values.model} onChange={(e) => setField('model', e.target.value)} />
        </label>

        <label>
          Altura de trabajo
          <span className="admin-product-unit-input">
            <input
              inputMode="decimal"
              value={workingHeightInput}
              onChange={(e) => {
                const nextInput = e.target.value
                const parsed = parseWorkingHeight(nextInput)
                setWorkingHeightInput(nextInput)
                setWorkingHeightError(parsed.error)
                setField('working_height_m', parsed.value)
              }}
              aria-invalid={Boolean(workingHeightError)}
              aria-describedby={workingHeightError ? 'working-height-error' : undefined}
            />
            <span aria-hidden="true">m</span>
          </span>
          {workingHeightError ? <span id="working-height-error" className="ui-note ui-note--error">{workingHeightError}</span> : null}
        </label>

        <label>
          Año
          <input
            type="number"
            min={1900}
            max={maximumYear}
            step={1}
            value={values.year ?? ''}
            onChange={(e) => setField('year', toNullableNumber(e.target.value))}
          />
        </label>

        <label>
          Horómetro
          <input
            type="number"
            min={0}
            step={1}
            value={values.hours_meter ?? ''}
            onChange={(e) => setField('hours_meter', toNullableNumber(e.target.value))}
          />
        </label>

        <label>
          Capacidad máxima de carga (kg)
          <input
            type="number"
            inputMode="decimal"
            min={0.01}
            step="0.01"
            value={values.maximum_load_capacity_kg ?? ''}
            onChange={(e) => setField('maximum_load_capacity_kg', toNullableNumber(e.target.value))}
          />
        </label>

        <label>
          Fuente de energía
          <select
            value={values.power_source ?? ''}
            onChange={(e) => setField('power_source', (e.target.value || null) as ProductPowerSource | null)}
          >
            <option value="">Sin especificar</option>
            <option value="diesel">Diésel</option>
            <option value="electric_24v">Eléctrica 24 V</option>
            <option value="electric_lithium">Eléctrica de litio</option>
          </select>
        </label>

        <label>
          Tipo de terreno
          <select value={values.terrain_type ?? ''} onChange={(e) => setField('terrain_type', (e.target.value || null) as ProductTerrainType | null)}>
            <option value="">Seleccione una opción</option>
            {TERRAIN_TYPE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>

        <label>
          Ficha técnica
          <select value={values.technical_sheet ?? ''} onChange={(e) => setField('technical_sheet', toNullableNumber(e.target.value))}>
            <option value="">Sin ficha técnica</option>
            {technicalSheetOptions.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.original_file_name}</option>)}
          </select>
        </label>

        <label className="admin-form-panel__full">
          Descripción
          <textarea value={values.description} onChange={(e) => setField('description', e.target.value)} rows={4} />
        </label>

        <fieldset className="admin-product-benefits admin-form-panel__full">
          <legend>Incluye</legend>
          <label className="admin-checkbox">
            <input type="checkbox" checked={values.includes_technical_review} onChange={(e) => setField('includes_technical_review', e.target.checked)} />
            Incluye revisión técnica
          </label>
          <label className="admin-checkbox">
            <input type="checkbox" checked={values.includes_commercial_technical_advice} onChange={(e) => setField('includes_commercial_technical_advice', e.target.checked)} />
            Incluye asesoría técnico-comercial
          </label>
          <label className="admin-checkbox">
            <input type="checkbox" checked={values.includes_coordinated_delivery} onChange={(e) => setField('includes_coordinated_delivery', e.target.checked)} />
            Incluye entrega coordinada
          </label>
        </fieldset>

        </section>
      </div>

      {beforeActions}

      <ProductEditorActions formId={formId} isSubmitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
