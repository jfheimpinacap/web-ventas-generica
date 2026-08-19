import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'

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

function parseMachineWeight(value: string) {
  const normalized = value.trim().replace(',', '.')
  if (!normalized) return { value: null, error: null }
  if (!/^-?\d+(?:[.,]\d+)?$/.test(value.trim()) || !Number.isFinite(Number(normalized))) {
    return { value: null, error: 'Ingresa un peso válido con hasta dos decimales.' }
  }
  const parsed = Number(normalized)
  if (parsed <= 0) return { value: null, error: 'El peso de la máquina debe ser mayor que cero.' }
  if (Math.round(parsed * 100) / 100 !== parsed) {
    return { value: null, error: 'El peso de la máquina admite hasta dos decimales.' }
  }
  return { value: parsed, error: null }
}

function toNullableNumber(value: string) {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function convertProductType(values: ProductFormValues, productType: ProductType): ProductFormValues {
  const machinery = productType === 'machinery'
  return {
    ...values,
    category: 0,
    product_type: productType,
    condition: productType === 'service' ? 'not_applicable' : values.condition === 'not_applicable' ? 'new' : values.condition,
    stock_status: productType === 'service' && !['available', 'on_request'].includes(values.stock_status) ? 'on_request' : values.stock_status,
    brand: productType === 'service' ? null : values.brand,
    model: productType === 'service' ? '' : values.model,
    sku: '',
    technical_sheet: productType === 'service' ? null : values.technical_sheet,
    working_height_m: machinery ? values.working_height_m : null,
    terrain_type: machinery ? values.terrain_type : null,
    year: machinery ? values.year : null,
    hours_meter: machinery ? values.hours_meter : null,
    maximum_load_capacity_kg: machinery ? values.maximum_load_capacity_kg : null,
    machine_weight_kg: machinery ? values.machine_weight_kg : null,
    power_source: machinery ? values.power_source : null,
    includes_technical_review: machinery,
    includes_commercial_technical_advice: machinery,
    includes_coordinated_delivery: machinery,
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
  const [machineWeightInput, setMachineWeightInput] = useState(() => formatDecimalInput(initialValues.machine_weight_kg))
  const [machineWeightError, setMachineWeightError] = useState<string | null>(null)
  const [primaryCategoryId, setPrimaryCategoryId] = useState<number | null>(null)
  const [categoryError, setCategoryError] = useState<string | null>(null)
  const [shortDescriptionError, setShortDescriptionError] = useState<string | null>(null)
  const shortDescriptionRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setValues(initialValues)
    const initialCategory = categories.find((item) => item.id === initialValues.category) ?? null
    setPrimaryCategoryId(getRootCategory(initialCategory, categories)?.id ?? null)
    setPriceError(null)
    setWorkingHeightInput(formatDecimalInput(initialValues.working_height_m))
    setWorkingHeightError(null)
    setMachineWeightInput(formatDecimalInput(initialValues.machine_weight_kg))
    setMachineWeightError(null)
    setShortDescriptionError(null)
  }, [initialValues])

  useEffect(() => {
    onValuesChange?.(values)
  }, [onValuesChange, values])

  const supportedTypes: Array<{ type: ProductType; label: string }> = [
    { type: 'machinery', label: 'Maquinarias' },
    { type: 'spare_part', label: 'Repuestos' },
    { type: 'service', label: 'Servicios' },
  ]
  const rootsByType = useMemo(() => new Map(supportedTypes.map(({ type }) => [type, categories.filter((item) => item.is_active && item.parent === null && item.product_type === type)])), [categories])
  useEffect(() => {
    if (initialValues.category || primaryCategoryId !== null || categories.length === 0) return
    const machineryRoots = rootsByType.get('machinery') ?? []
    if (machineryRoots.length === 1) setPrimaryCategoryId(machineryRoots[0].id)
  }, [categories.length, initialValues.category, primaryCategoryId, rootsByType])

  const selectedCategory = useMemo(() => categories.find((item) => item.id === values.category) ?? null, [categories, values.category])
  const categoryRoot = useMemo(() => getRootCategory(selectedCategory, categories), [categories, selectedCategory])
  const selectedRootId = categoryRoot?.id ?? primaryCategoryId
  const selectedRoot = useMemo(() => categories.find((item) => item.id === selectedRootId) ?? categoryRoot, [categories, categoryRoot, selectedRootId])
  const subcategoryOptions = useMemo(() => selectedRootId ? categories.filter((item) => item.is_active && item.parent === selectedRootId).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name)) : [], [categories, selectedRootId])
  const usesOptionalSubcategory = values.product_type === 'spare_part' || values.product_type === 'service'
  const hasNoSubcategories = usesOptionalSubcategory && Boolean(selectedRoot) && subcategoryOptions.length === 0
  const isExistingRootSelection = usesOptionalSubcategory && selectedCategory?.id === selectedRoot?.id
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
          const productType = inferProductTypeFromRootCategory(selected)
          if (productType !== 'machinery') {
            setMachineWeightInput('')
            setMachineWeightError(null)
          }
          return { ...convertProductType(prev, productType), category: 0 }
        }
        setPrimaryCategoryId(root?.id ?? null)
        const productType = inferProductTypeFromRootCategory(root)
        if (productType !== 'machinery') {
          setMachineWeightInput('')
          setMachineWeightError(null)
        }
        return { ...prev, product_type: productType, category: Number(nextValue) }
      }
      return { ...prev, [field]: nextValue }
    })
  }

  const handleTabChange = (productType: ProductType) => {
    if (productType === values.product_type) return
    const roots = rootsByType.get(productType) ?? []
    if (roots.length !== 1) {
      setCategoryError(roots.length === 0 ? 'No existe una categoría raíz activa para este tipo de producto.' : 'Existe más de una categoría raíz activa para este tipo de producto.')
      return
    }
    if (!window.confirm('Al cambiar el tipo se limpiarán la subcategoría y los campos incompatibles. ¿Deseas continuar?')) return
    setCategoryError(null)
    setPrimaryCategoryId(roots[0].id)
    setWorkingHeightInput('')
    setWorkingHeightError(null)
    setMachineWeightInput('')
    setMachineWeightError(null)
    setValues((current) => convertProductType(current, productType))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const matchingRoots = rootsByType.get(values.product_type) ?? []
    const matchingRoot = matchingRoots.length === 1 && selectedRoot?.id === matchingRoots[0].id
    const validRootFallback = usesOptionalSubcategory && matchingRoot && (hasNoSubcategories || isExistingRootSelection)
    const validSubcategory = matchingRoot && selectedCategory?.parent === matchingRoots[0].id
    if (!validSubcategory && !validRootFallback) {
      setCategoryError('Selecciona una subcategoría válida para el tipo de producto.')
      return
    }
    if (values.product_type === 'service' && values.stock_status !== 'available' && values.stock_status !== 'on_request') {
      setCategoryError('Selecciona una disponibilidad válida para el servicio.')
      return
    }

    if (usesOptionalSubcategory && values.is_published && !values.short_description.trim()) {
      setShortDescriptionError('Ingresa una descripción para vista previa antes de publicar.')
      shortDescriptionRef.current?.focus()
      return
    }

    if (!isValidChileanPriceInput(values.price)) {
      setPriceError('Ingresa un precio válido usando solo números y puntos como separador de miles.')
      return
    }

    const workingHeight = values.product_type === 'machinery' ? parseWorkingHeight(workingHeightInput) : { value: null, error: null }
    if (workingHeight.error) {
      setWorkingHeightError(workingHeight.error)
      return
    }
    const machineWeight = parseMachineWeight(machineWeightInput)
    if (values.product_type === 'machinery' && machineWeight.error) {
      setMachineWeightError(machineWeight.error)
      return
    }

    setPriceError(null)
    await onSubmit({
      ...values,
      category: validRootFallback ? matchingRoots[0].id : values.category,
      working_height_m: workingHeight.value,
      machine_weight_kg: values.product_type === 'machinery' ? machineWeight.value : null,
      product_type: values.product_type,
      condition: values.product_type === 'service' ? 'not_applicable' : values.condition,
      brand: values.product_type === 'service' ? null : values.brand,
      model: values.product_type === 'service' ? '' : values.model,
      sku: values.product_type === 'spare_part' ? values.sku.trim() : '',
      technical_sheet: values.product_type === 'service' ? null : values.technical_sheet,
      terrain_type: values.product_type === 'machinery' ? values.terrain_type : null,
      year: values.product_type === 'machinery' ? values.year : null,
      hours_meter: values.product_type === 'machinery' ? values.hours_meter : null,
      maximum_load_capacity_kg: values.product_type === 'machinery' ? values.maximum_load_capacity_kg : null,
      power_source: values.product_type === 'machinery' ? values.power_source : null,
      includes_technical_review: values.product_type === 'machinery' && values.includes_technical_review,
      includes_commercial_technical_advice: values.product_type === 'machinery' && values.includes_commercial_technical_advice,
      includes_coordinated_delivery: values.product_type === 'machinery' && values.includes_coordinated_delivery,
      short_description: usesOptionalSubcategory ? values.short_description.trim() : values.short_description,
      price: normalizeChileanPriceInput(values.price),
    })
  }

  const maximumYear = new Date().getFullYear() + 1

  return (
    <form id={formId} className="admin-product-form admin-product-editor-form" onSubmit={handleSubmit}>
      {error ? <p className="ui-note ui-note--error admin-product-form__notice">{error}</p> : null}
      <div className="quote-view-tabs admin-product-type-tabs" role="tablist" aria-label="Tipo de producto">
        {supportedTypes.map(({ type, label }) => {
          const rootCount = (rootsByType.get(type) ?? []).length
          return <button key={type} id={`product-tab-${type}`} type="button" role="tab" aria-selected={values.product_type === type} aria-disabled={rootCount !== 1} aria-controls="product-editor-panels" className={`quote-view-tab${values.product_type === type ? ' quote-view-tab--active' : ''}`} onClick={() => handleTabChange(type)}>{label}</button>
        })}
      </div>
      {categoryError ? <p className="ui-note ui-note--error admin-product-form__notice">{categoryError}</p> : null}

      <div id="product-editor-panels" className="admin-product-information-grid" role="tabpanel" aria-labelledby={`product-tab-${values.product_type}`}>
        <section className="admin-form-panel admin-form-panel--product-grid">
        <h3>Información general</h3>

        <label className="admin-form-panel__span-2 admin-product-name-field">
          Nombre
          <input value={values.name} onChange={(e) => setField('name', e.target.value)} required />
        </label>

        <label>
          Subcategoría
          <select value={selectedCategory?.parent ? values.category : (hasNoSubcategories || isExistingRootSelection) ? selectedRoot?.id : ''} onChange={(e) => setField('category', Number(e.target.value))} required disabled={!selectedRootId || hasNoSubcategories}>
            {hasNoSubcategories || isExistingRootSelection ? <option value={selectedRoot?.id}>Sin subcategoría</option> : <option value="">Selecciona subcategoría</option>}
            {subcategoryOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        {values.product_type !== 'service' ? (
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
        ) : null}

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
          {values.product_type !== 'service' ? <label>
            Condición
            <select value={values.condition} onChange={(e) => setField('condition', e.target.value as ProductCondition)} required>
              {PRODUCT_CONDITIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label> : null}

          <label>
            {values.product_type === 'service' ? 'Disponibilidad' : 'Stock'}
            <select value={values.stock_status} onChange={(e) => setField('stock_status', e.target.value as StockStatus)} required>
              {STOCK_STATUSES.filter((item) => values.product_type !== 'service' || item.value === 'available' || item.value === 'on_request').map((item) => (
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
            <input type="checkbox" checked={values.is_published} onChange={(e) => { setField('is_published', e.target.checked); if (!e.target.checked) setShortDescriptionError(null) }} />
            Publicado
          </label>

          <label className="admin-checkbox">
            <input type="checkbox" checked={values.is_featured} onChange={(e) => setField('is_featured', e.target.checked)} />
            Destacado
          </label>
        </div>
        {values.product_type === 'machinery' ? <fieldset className="admin-product-benefits admin-form-panel__full">
          <legend>Incluye</legend>
          <label className="admin-checkbox"><input type="checkbox" checked={values.includes_technical_review} onChange={(e) => setField('includes_technical_review', e.target.checked)} />Incluye revisión técnica</label>
          <label className="admin-checkbox"><input type="checkbox" checked={values.includes_commercial_technical_advice} onChange={(e) => setField('includes_commercial_technical_advice', e.target.checked)} />Incluye asesoría técnico-comercial</label>
          <label className="admin-checkbox"><input type="checkbox" checked={values.includes_coordinated_delivery} onChange={(e) => setField('includes_coordinated_delivery', e.target.checked)} />Incluye entrega coordinada</label>
        </fieldset> : null}
        </section>

        <section className="admin-form-panel admin-product-technical-grid">
        <h3>Información técnica / comercial</h3>

        {values.product_type !== 'service' ? (
        <label>
          Modelo
          <input value={values.model} onChange={(e) => setField('model', e.target.value)} />
        </label>
        ) : null}

        {values.product_type === 'spare_part' ? <label>
          Código/SKU
          <input value={values.sku} onChange={(e) => setField('sku', e.target.value)} />
        </label> : null}

        {values.product_type === 'machinery' ? <>
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

        {values.product_type === 'machinery' ? (
          <label>
            Peso de la máquina (kg)
            <input
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              value={machineWeightInput}
              onChange={(e) => {
                const nextInput = e.target.value
                const parsed = parseMachineWeight(nextInput)
                setMachineWeightInput(nextInput)
                setMachineWeightError(parsed.error)
                setField('machine_weight_kg', parsed.value)
              }}
              aria-invalid={Boolean(machineWeightError)}
              aria-describedby={machineWeightError ? 'machine-weight-error' : undefined}
            />
            {machineWeightError ? <span id="machine-weight-error" className="ui-note ui-note--error">{machineWeightError}</span> : null}
          </label>
        ) : null}

        <label>
          Fuente de energía
          <select
            value={values.power_source ?? ''}
            onChange={(e) => setField('power_source', (e.target.value || null) as ProductPowerSource | null)}
          >
            <option value="">Sin especificar</option>
            <option value="diesel">Diésel</option>
            <option value="electric_24v">Baterías 24 V</option>
            <option value="electric_lithium">Batería de litio</option>
          </select>
        </label>

        <label>
          Tipo de terreno
          <select value={values.terrain_type ?? ''} onChange={(e) => setField('terrain_type', (e.target.value || null) as ProductTerrainType | null)}>
            <option value="">Seleccione una opción</option>
            {TERRAIN_TYPE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        </> : null}

        {values.product_type !== 'service' ? (
        <label>
          Ficha técnica
          <select value={values.technical_sheet ?? ''} onChange={(e) => setField('technical_sheet', toNullableNumber(e.target.value))}>
            <option value="">Sin ficha técnica</option>
            {technicalSheetOptions.map((item) => <option key={item.id} value={item.id}>{item.name} — {item.original_file_name}</option>)}
          </select>
        </label>
        ) : null}

        <label className="admin-form-panel__full">
          {usesOptionalSubcategory ? 'Descripción detallada' : 'Descripción'}
          <textarea className={usesOptionalSubcategory ? 'admin-product-detailed-description' : undefined} value={values.description} onChange={(e) => setField('description', e.target.value)} rows={usesOptionalSubcategory ? 8 : 4} />
        </label>

        {usesOptionalSubcategory ? <label className="admin-form-panel__full admin-product-short-description">
          <span>Descripción para vista previa pública {values.is_published ? <span aria-hidden="true">*</span> : null}</span>
          <textarea ref={shortDescriptionRef} value={values.short_description} onChange={(e) => { setField('short_description', e.target.value); if (shortDescriptionError) setShortDescriptionError(null) }} onInvalid={(e) => { e.preventDefault(); setShortDescriptionError('Ingresa una descripción para vista previa antes de publicar.') }} rows={3} maxLength={280} required={values.is_published} aria-required={values.is_published} aria-invalid={Boolean(shortDescriptionError)} aria-describedby={shortDescriptionError ? 'short-description-error' : 'short-description-counter'} />
          <span id="short-description-counter" className="admin-product-character-count">{values.short_description.length}/280</span>
          {shortDescriptionError ? <span id="short-description-error" className="ui-note ui-note--error">{shortDescriptionError}</span> : null}
        </label> : null}

        </section>
      </div>

      {beforeActions}

      <ProductEditorActions formId={formId} isSubmitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
