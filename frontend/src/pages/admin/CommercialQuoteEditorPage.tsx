import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminPageHeader } from '../../components/admin/AdminPageHeader'
import { CommercialQuotePdfModal } from '../../components/admin/CommercialQuotePdfModal'
import { useAdminUser } from '../../components/admin/ProtectedRoute'
import { CustomerSearch } from '../../components/admin/CustomerSearch'
import { ConfirmDialog } from '../../components/admin/ConfirmDialog'
import { useSystemDialog } from '../../context/SystemDialogContext'
import { QuoteItemsEditor } from '../../components/admin/QuoteItemsEditor'
import { useCommercialQuotePdfDownload } from '../../hooks/useCommercialQuotePdfDownload'
import { getSafeApiErrorMessage } from '../../services/api'
import { isSeller } from '../../services/authApi'
import { getCommercialQuote, issueCommercialQuote, saveCustomer } from '../../services/commercialQuotesApi'
import { COMMERCIAL_QUOTE_VALIDITY_OPTIONS, SALE_CONDITION_OPTIONS } from '../../types/commercialQuote'
import type { CommercialQuoteDetail, CommercialQuoteValidityDays, CustomerProfile, CustomerSnapshot, QuoteCurrency, QuoteEditorItem, SaleCondition } from '../../types/commercialQuote'
import { emptyQuoteItem, isEmptyItem, money, quoteTotals } from '../../utils/commercialQuote'
import { formatChileanRutInput, normalizeChileanRut } from '../../utils/chileanRut'

const emptyCustomer: CustomerSnapshot = { customer_profile_id: null, customer_business_name: '', customer_rut: '', customer_business_activity: '', customer_address: '', customer_phone: '', customer_city_or_commune: '', customer_contact_name: '', customer_email: '' }
const customerFields: Array<[keyof CustomerSnapshot, string, number, boolean, string]> = [['customer_business_name','Razón social',200,true,'business'],['customer_rut','RUT',12,true,'rut'],['customer_phone','Teléfono',30,true,'phone'],['customer_city_or_commune','Comuna o ciudad',120,true,'city'],['customer_business_activity','Giro',200,true,'activity'],['customer_address','Dirección',300,true,'address'],['customer_contact_name','Nombre de contacto',200,true,'contact'],['customer_email','Correo electrónico',254,false,'email']]
const fromDetail = (q: CommercialQuoteDetail): QuoteEditorItem[] => [...q.items].sort((a,b) => a.position-b.position).map<QuoteEditorItem>(i => ({ key: String(i.id), source: i.source, product_id: i.product_id ?? null, product_name: i.product_name, brand_name: i.brand_name ?? '', model_name: i.model_name ?? '', quantity: String(i.quantity), unit_net_amount: String(i.unit_net_amount), discount_percent: i.discount_percent ? String(i.discount_percent) : '' })).concat([emptyQuoteItem()])

export function CommercialQuoteEditorPage() {
  const { requestConfirmation } = useSystemDialog()
  const { downloadPdf, error: downloadError, isDownloading } = useCommercialQuotePdfDownload()
  const currentUser = useAdminUser()
  const params = useParams(); const navigate = useNavigate(); const routeId = params.id ? Number(params.id) : undefined
  const id = routeId; const [customer, setCustomer] = useState(emptyCustomer); const [currency, setCurrency] = useState<QuoteCurrency>('CLP'); const [condition, setCondition] = useState<SaleCondition>('Cash'); const [validityDays, setValidityDays] = useState<CommercialQuoteValidityDays>(15); const [description, setDescription] = useState(''); const [items, setItems] = useState<QuoteEditorItem[]>([emptyQuoteItem()]); const [persisted, setPersisted] = useState<CommercialQuoteDetail | null>(null)
  const [loading, setLoading] = useState(Boolean(routeId)); const [saving, setSaving] = useState(false); const [dirty, setDirty] = useState(false); const [message, setMessage] = useState(''); const [error, setError] = useState(''); const [rutReviewed, setRutReviewed] = useState(false); const [showIssueDialog, setShowIssueDialog] = useState(false); const firstError = useRef<HTMLDivElement>(null); const rutInput = useRef<HTMLInputElement>(null); const issueButton = useRef<HTMLButtonElement>(null); const readonly = Boolean(routeId) || !isSeller(currentUser ?? undefined)
  const [pdfPreview, setPdfPreview] = useState<{ id: number; folio: string | null } | null>(null)
  const [issuedHere, setIssuedHere] = useState(false)
  const pendingIssue = useRef<{ payloadFingerprint: string; idempotencyKey: string } | null>(null)
  const navigationConfirmationPending = useRef(false)
  const currencyConfirmationPending = useRef(false)
  const currentSellerName = currentUser?.full_name?.trim() || [currentUser?.first_name, currentUser?.last_name].filter(Boolean).join(' ').trim() || currentUser?.username || 'No informado'
  const seller = persisted ? { name: persisted.responsibleSellerName, code: persisted.responsibleSellerCode, email: persisted.responsibleSellerEmail, phone: persisted.responsibleSellerPhone } : { name: currentSellerName, code: currentUser?.seller_code, email: currentUser?.email, phone: currentUser?.phone }
  const informed = (value: string | null | undefined) => value?.trim() || 'No informado'
  const totals = useMemo(() => persisted && !dirty ? { net: persisted.net_amount, tax: persisted.tax_amount, total: persisted.total_amount } : quoteTotals(items.filter(i => !isEmptyItem(i)), currency), [currency, dirty, items, persisted])
  const apply = useCallback((quote: CommercialQuoteDetail) => { setPersisted(quote); setCustomer({ customer_profile_id: quote.customer_profile_id, customer_business_name: quote.customer_business_name, customer_rut: formatChileanRutInput(quote.customer_rut), customer_business_activity: quote.customer_business_activity, customer_address: quote.customer_address, customer_phone: quote.customer_phone, customer_city_or_commune: quote.customer_city_or_commune, customer_contact_name: quote.customer_contact_name, customer_email: quote.customer_email ?? '' }); setCurrency(quote.currency); setCondition(quote.sale_condition); setValidityDays(quote.validityDays); setDescription(quote.detailed_description ?? ''); setItems(fromDetail(quote)); setDirty(false) }, [])
  useEffect(() => { if (!routeId) return; getCommercialQuote(routeId).then(apply).catch(e => setError(getSafeApiErrorMessage(e, 'No se pudo cargar la cotización.'))).finally(() => setLoading(false)) }, [apply, routeId])
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => { e.preventDefault() }; addEventListener('beforeunload', warn); return () => removeEventListener('beforeunload', warn) }, [dirty])
  const touch = () => { setDirty(true); setMessage('') }
  const selectCustomer = (p: CustomerProfile) => { setCustomer({ customer_profile_id:p.id, customer_business_name:p.business_name, customer_rut:formatChileanRutInput(p.rut), customer_business_activity:p.business_activity, customer_address:p.address, customer_phone:p.phone, customer_city_or_commune:p.city_or_commune, customer_contact_name:p.contact_name, customer_email:p.email ?? '' }); setRutReviewed(false); touch() }
  const rutError = rutReviewed ? (!customer.customer_rut.trim() ? 'El RUT es obligatorio.' : !normalizeChileanRut(customer.customer_rut) ? 'El RUT ingresado no es válido. Revise el número y el dígito verificador.' : '') : ''
  const validate = (requireItems: boolean) => { setRutReviewed(true); const errors: string[] = []; customerFields.filter(f=>f[3] && f[0] !== 'customer_rut').forEach(([key,label]) => { if (!String(customer[key]).trim()) errors.push(`${label} es obligatorio.`) }); const normalizedRut = normalizeChileanRut(customer.customer_rut); if (customer.customer_email && !/^\S+@\S+\.\S+$/.test(customer.customer_email)) errors.push('Ingrese un correo válido.'); if (!/\d/.test(customer.customer_phone)) errors.push('El teléfono debe contener al menos un dígito.'); const filled = items.filter(i=>!isEmptyItem(i)); for (const item of filled) { const discount = Number(item.discount_percent || 0); if (!item.product_name || !Number.isInteger(Number(item.quantity)) || Number(item.quantity)<1 || !Number.isFinite(Number(item.unit_net_amount)) || Number(item.unit_net_amount)<=0 || !Number.isFinite(discount) || discount<0 || discount>100 || (item.discount_percent !== '' && !/^\d+(\.\d{0,2})?$/.test(item.discount_percent))) errors.push('Corrija o elimine las filas de productos incompletas.') } if (requireItems && !filled.length) errors.push('Agregue al menos un ítem para emitir.'); setError(errors[0] ?? ''); if (!normalizedRut) rutInput.current?.focus(); else if (errors.length) firstError.current?.focus(); return Boolean(normalizedRut) && !errors.length }
  const payload = () => ({ ...customer, customer_rut: normalizeChileanRut(customer.customer_rut)!, currency, sale_condition: condition, validity_days: validityDays, detailed_description: description || undefined, items: items.filter(i=>!isEmptyItem(i)).map(i => ({ source: i.source as 'Catalog'|'FreeText', ...(i.product_id ? { product_id:i.product_id } : {}), product_name:i.product_name, ...(i.brand_name ? {brand_name:i.brand_name}:{}), ...(i.model_name ? {model_name:i.model_name}:{}), quantity:Number(i.quantity), unit_net_amount:Number(i.unit_net_amount), ...(i.discount_percent ? {discount_percent:Math.min(100,Math.max(0,Number(i.discount_percent)))}:{}) })) })
  const requestIssue = () => { if (saving || readonly || !validate(true)) return; setShowIssueDialog(true) }
  const closeIssueDialog = () => { setShowIssueDialog(false); window.setTimeout(() => issueButton.current?.focus(), 0) }
  const issue = async () => { if (saving || readonly) return; const issuePayload = payload(); const payloadFingerprint = JSON.stringify(issuePayload); if (!pendingIssue.current || pendingIssue.current.payloadFingerprint !== payloadFingerprint) pendingIssue.current = { payloadFingerprint, idempotencyKey: crypto.randomUUID() }; const idempotencyKey = pendingIssue.current.idempotencyKey; setShowIssueDialog(false); setSaving(true); setError(''); try { const issued = await issueCommercialQuote(issuePayload, idempotencyKey); pendingIssue.current = null; apply(issued); setIssuedHere(true); setPdfPreview({ id: issued.id, folio: issued.folio }); setMessage(`Cotización emitida con folio ${issued.folio}.`); navigate(`/admin/cotizaciones/${issued.id}/editar`, { replace:true }) } catch(e) { setError(getSafeApiErrorMessage(e,'No se pudo emitir la cotización. Los datos del formulario se conservaron.')) } finally { setSaving(false) } }
  const goBack = async () => {
    if (navigationConfirmationPending.current) return
    if (!dirty) { navigate('/admin/cotizaciones?vista=generadas'); return }
    navigationConfirmationPending.current = true
    const accepted = await requestConfirmation({ title: 'Cambios sin guardar', message: 'Hay cambios sin guardar. Si vuelves ahora, se perderán.', confirmLabel: 'Volver sin guardar', cancelLabel: 'Continuar editando', variant: 'danger' })
    navigationConfirmationPending.current = false
    if (accepted) navigate('/admin/cotizaciones?vista=generadas')
  }
  const changeCurrency = async (next: QuoteCurrency) => {
    if (next === currency || currencyConfirmationPending.current) return
    if (items.some(item => Number(item.unit_net_amount) > 0)) {
      currencyConfirmationPending.current = true
      const accepted = await requestConfirmation({ title: 'Cambiar moneda', message: 'No existe conversión monetaria automática. Al cambiar la moneda se limpiarán los precios ingresados.', confirmLabel: 'Cambiar moneda', cancelLabel: 'Cancelar' })
      currencyConfirmationPending.current = false
      if (!accepted) return
    }
    setCurrency(next); setItems(current => current.map(item => ({ ...item, unit_net_amount: '', discount_percent: '' }))); touch()
  }
  if (loading) return <AdminLayout><p className="ui-note">Cargando cotización…</p></AdminLayout>
  return <AdminLayout><AdminPageHeader title={id ? 'Ver cotización' : 'Crear cotización'} /><div ref={firstError} tabIndex={-1}>{error ? <p className="ui-note ui-note--error" role="alert">{error}</p>:null}{downloadError ? <p className="ui-note ui-note--error" role="alert">{downloadError}</p>:null}{message ? <p className="ui-note ui-note--success">{message}</p>:null}</div>
    <div className="commercial-editor-grid">
      <main className="commercial-editor-main">
      <section className="commercial-section commercial-customer-panel">
        <div className="commercial-customer-heading"><h2>Datos del cliente</h2><CustomerSearch disabled={Boolean(readonly)||saving} selectedId={customer.customer_profile_id} onSelect={selectCustomer} onUnlink={() => { setCustomer(c=>({...c,customer_profile_id:null})); touch() }} navigationAction={<button type="button" className="btn btn--ghost" onClick={goBack}>{id ? 'Volver' : 'Cancelar'}</button>} /></div>
        <div className="commercial-form-grid">{customerFields.map(([key,label,max,required,area])=><label key={key} style={{gridArea:area}}>{label}{required?' *':''}<input ref={key === 'customer_rut' ? rutInput : undefined} type={key==='customer_email'?'email':'text'} value={String(customer[key]??'')} maxLength={key === 'customer_rut' ? 12 : max} disabled={readonly||saving} spellCheck={key === 'customer_rut' ? false : undefined} autoCapitalize={key === 'customer_rut' ? 'characters' : undefined} aria-invalid={key === 'customer_rut' && Boolean(rutError) ? true : undefined} aria-describedby={key === 'customer_rut' && rutError ? 'rut-error' : undefined} className={key === 'customer_rut' && rutError ? 'commercial-rut-input--invalid' : undefined} onBlur={key === 'customer_rut' ? () => setRutReviewed(true) : undefined} onChange={e=>{const value = key === 'customer_rut' ? formatChileanRutInput(e.target.value) : e.target.value;if (key === 'customer_rut' && /[^0-9kK.\s-]/.test(e.target.value)) return;setCustomer(c=>({...c,[key]:value}));touch()}} /></label>)}</div>
        <div className="commercial-customer-validation">{rutError ? <span id="rut-error" className="commercial-rut-error" role="alert">{rutError}</span> : null}</div>
        <button className="btn btn--accent commercial-primary-action" type="button" disabled={readonly||saving} onClick={async()=>{if(!validate(false))return;setSaving(true);try{const body={business_name:customer.customer_business_name,rut:normalizeChileanRut(customer.customer_rut)!,business_activity:customer.customer_business_activity,address:customer.customer_address,phone:customer.customer_phone,city_or_commune:customer.customer_city_or_commune,contact_name:customer.customer_contact_name,email:customer.customer_email||null};const saved=await saveCustomer(body,customer.customer_profile_id??undefined);selectCustomer(saved);setMessage('Cliente guardado correctamente.')}catch(e){setError(getSafeApiErrorMessage(e,'No se pudo guardar el cliente. Si el RUT ya existe, búsquelo arriba.'))}finally{setSaving(false)}}}>Guardar cliente</button>
      </section>
        <section className="commercial-section">
          <h2>Datos comerciales y productos a cotizar</h2>
          <div className="commercial-meta-row commercial-meta-row--primary">
            <label className="commercial-meta-field commercial-meta-field--condition">Condición de venta<select value={condition} disabled={readonly||saving} onChange={e=>{setCondition(e.target.value as SaleCondition);touch()}}>{SALE_CONDITION_OPTIONS.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="commercial-meta-field commercial-meta-field--currency">Moneda<select value={currency} disabled={readonly||saving} onChange={e=>void changeCurrency(e.target.value as QuoteCurrency)}><option>CLP</option><option>USD</option></select></label>
            <label className="commercial-meta-field commercial-meta-field--validity">Vigencia<select value={validityDays} disabled={readonly||saving} onChange={e=>{setValidityDays(Number(e.target.value) as CommercialQuoteValidityDays);touch()}}>{COMMERCIAL_QUOTE_VALIDITY_OPTIONS.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="commercial-meta-field commercial-meta-field--seller-name">Vendedor<input readOnly value={informed(seller.name)} /></label>
            <label className="commercial-meta-field commercial-meta-field--seller-email">Correo<input readOnly value={informed(seller.email)} /></label>
          </div>
          <div className="commercial-meta-row commercial-meta-row--secondary">
            <label className="commercial-meta-field commercial-meta-field--folio">Folio<input readOnly value={persisted?.folio ?? 'Se asignará al emitir'} /></label>
            <label className="commercial-meta-field commercial-meta-field--seller-code">Código de vendedor<input readOnly value={informed(seller.code)} /></label>
            <label className="commercial-meta-field commercial-meta-field--seller-phone">Teléfono<input readOnly value={informed(seller.phone)} /></label>
            <label className="commercial-meta-field commercial-meta-field--date">Fecha<input readOnly value={new Intl.DateTimeFormat('es-CL',{timeZone:'America/Santiago'}).format(new Date(persisted?.issued_on ?? persisted?.created_at ?? Date.now()))} /></label>
          </div>
          <h3>Productos</h3><QuoteItemsEditor currency={currency} items={items} disabled={Boolean(readonly)||saving} onChange={next=>{setItems(next);touch()}} />
        </section>
        <div className="commercial-lower-row">
          <section className="commercial-section commercial-description"><h2 id="commercial-quote-description-label">Descripción detallada opcional</h2><textarea aria-labelledby="commercial-quote-description-label" rows={10} maxLength={1000} value={description} disabled={readonly||saving} onChange={e=>{setDescription(e.target.value);touch()}} /><small>{description.length}/1000</small></section>
          <div className="commercial-summary-column"><section className="commercial-section quote-values"><h2>Valor final</h2><dl><div><dt>Neto</dt><dd>{money(totals.net,currency)}</dd></div><div><dt>IVA 19%</dt><dd>{money(totals.tax,currency)}</dd></div><div><dt>Total</dt><dd>{money(totals.total,currency)}</dd></div></dl><small>Vista previa; el cálculo definitivo lo realiza el servidor.</small></section><div className="commercial-actions"><button className="btn btn--ghost" type="button" onClick={goBack}>Volver</button>{!readonly || issuedHere ? <button ref={issueButton} className="btn btn--accent commercial-primary-action" type="button" disabled={saving} aria-disabled={readonly || undefined} aria-busy={saving || undefined} onClick={requestIssue}>{saving ? 'Emitiendo…' : 'Emitir cotización'}</button> : null}{persisted?.status === 'Issued' && persisted.folio?.trim() && Number.isInteger(persisted.id) && persisted.id > 0 ? <button className="btn btn--secondary" type="button" disabled={isDownloading(persisted.id)} aria-busy={isDownloading(persisted.id) || undefined} aria-label={`${isDownloading(persisted.id) ? 'Descargando' : 'Descargar PDF de la cotización'} ${persisted.folio}`} onClick={() => void downloadPdf(persisted.id, persisted.folio)}>{isDownloading(persisted.id) ? 'Descargando…' : 'Descargar PDF'}</button> : null}</div></div>
        </div>
      </main>
    </div>
    {showIssueDialog ? <ConfirmDialog title="Emitir cotización" cancelLabel="Cancelar" confirmLabel="Emitir cotización" onCancel={closeIssueDialog} onConfirm={() => void issue()}>La cotización no podrá editarse después de emitirla. ¿Desea continuar?</ConfirmDialog> : null}
    {pdfPreview ? <CommercialQuotePdfModal quoteId={pdfPreview.id} folio={pdfPreview.folio} onClose={() => setPdfPreview(null)} returnFocusRef={issueButton} /> : null}
  </AdminLayout>
}
