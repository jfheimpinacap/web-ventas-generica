import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react'

import type { ProductImage } from '../../types/catalog'
import type { PendingProductImage } from '../../hooks/usePendingProductImages'
import { AdminProductImage } from './AdminProductImage'

interface ProductImageManagerProps {
  existingImages?: ProductImage[]
  pendingImages: PendingProductImage[]
  selectedPendingId: string | null
  disabled: boolean
  status: string | null
  error: string | null
  uploadLabel?: string
  isProcessing: boolean
  processingMessage: string | null
  onAddFiles: (files: File[]) => Promise<void>
  onAltTextChange: (id: string, value: string) => void
  onSelectPending: (id: string) => void
  onRemovePending: (id: string) => void
  onSelectExisting?: (id: number) => void
  onDeleteExisting?: (id: number) => void
  onUpload?: () => void
}

const ACCEPTED_IMAGES = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 KB'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toLocaleString('es-CL', { maximumFractionDigits: 1 })} MB`
}

export function ProductImageManager({
  existingImages = [], pendingImages, selectedPendingId, disabled, status, error, uploadLabel, isProcessing, processingMessage,
  onAddFiles, onAltTextChange, onSelectPending, onRemovePending, onSelectExisting, onDeleteExisting, onUpload,
}: ProductImageManagerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const totalCards = existingImages.length + pendingImages.length + 1
  const placeholderCount = Math.max(0, 10 - totalCards)

  const incorporate = (files: FileList | null) => {
    if (!files || disabled || isProcessing) return
    void onAddFiles(Array.from(files))
  }
  const openPicker = () => {
    if (!disabled && !isProcessing) inputRef.current?.click()
  }
  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setDragActive(false)
    incorporate(event.dataTransfer.files)
  }
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openPicker()
    }
  }

  return (
    <section className="admin-form-panel admin-form-panel--media admin-image-manager" aria-busy={isProcessing ? 'true' : undefined}>
      <h3>Imágenes</h3>
      <input
        ref={inputRef}
        className="admin-image-manager__input"
        type="file"
        multiple
        accept={ACCEPTED_IMAGES}
        aria-label="Seleccionar imágenes del producto"
        aria-describedby="product-images-help"
        disabled={disabled || isProcessing}
        onChange={(event) => {
          incorporate(event.currentTarget.files)
          event.currentTarget.value = ''
        }}
      />
      <div className="admin-image-manager__body">
        <div
          className={`admin-image-dropzone${dragActive ? ' is-drag-active' : ''}`}
          role="button"
          tabIndex={disabled || isProcessing ? -1 : 0}
          aria-disabled={disabled || isProcessing}
          aria-describedby="product-images-help"
          onClick={openPicker}
          onKeyDown={handleKeyDown}
          onDragEnter={(event) => { event.preventDefault(); if (!disabled && !isProcessing) setDragActive(true) }}
          onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = disabled || isProcessing ? 'none' : 'copy' }}
          onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragActive(false) }}
          onDrop={handleDrop}
        >
          <strong>{dragActive ? 'Suelta las imágenes para agregarlas' : 'Arrastra imágenes aquí'}</strong>
          <span>o selecciónalas desde tu equipo</span>
          <span className="admin-image-dropzone__picker">Seleccionar archivo</span>
          <span id="product-images-help" className="ui-note">JPG, PNG o WebP. Las imágenes se optimizan automáticamente a WebP, con un máximo de 1920 px. Archivo original máximo: 20 MB.</span>
        </div>

        <div className="admin-image-gallery">
          <div className="admin-image-gallery__grid">
            {existingImages.map((image) => (
              <article key={image.id} className={`admin-image-card${image.is_main ? ' admin-image-card--main' : ''}`}>
                <div className="admin-image-card__media">
                  <AdminProductImage imageId={image.id} alt={image.alt_text || 'Imagen de producto'} />
                  {image.is_main ? <span className="admin-image-main-badge">Principal actual</span> : null}
                </div>
                <div className="admin-image-card__actions">
                  <button type="button" className="btn btn--ghost" aria-pressed={image.is_main} aria-label={`Establecer imagen ${image.id} como principal`} disabled={disabled || image.is_main} onClick={() => onSelectExisting?.(image.id)}>Principal</button>
                  <button type="button" className="btn btn--ghost" aria-label={`Eliminar imagen ${image.id}`} disabled={disabled} onClick={() => onDeleteExisting?.(image.id)}>Eliminar</button>
                </div>
              </article>
            ))}

            {pendingImages.map((image) => {
              const selected = image.id === selectedPendingId
              const stateText = image.status === 'uploading' ? 'Subiendo' : image.status === 'error' ? 'No se pudo cargar' : selected ? 'Será principal' : 'Pendiente'
              return (
                <article key={image.id} className={`admin-image-card admin-image-card--pending${selected ? ' admin-image-card--main' : ''}`}>
                  <div className="admin-image-card__media">
                    <img src={image.previewUrl} alt={image.altText.trim() || image.file.name} />
                    {selected ? <span className="admin-image-main-badge">Será principal</span> : null}
                  </div>
                  <p className="admin-image-card__filename" title={image.originalFileName}>{image.originalFileName} · {formatBytes(image.originalSize)} → WebP {image.width} × {image.height} · {formatBytes(image.file.size)}</p>
                  <p className="admin-image-card__state">{stateText}</p>
                  <label>
                    Texto alternativo (opcional)
                    <input maxLength={220} value={image.altText} aria-label={`Texto alternativo para ${image.file.name}`} disabled={disabled} onKeyDown={(event) => { if (event.key === 'Enter') event.preventDefault() }} onChange={(event) => onAltTextChange(image.id, event.target.value)} />
                  </label>
                  {image.error ? <p className="admin-image-card__error" role="alert">{image.error}</p> : null}
                  <div className="admin-image-card__actions">
                    <button type="button" className="btn btn--ghost" aria-pressed={selected} aria-label={`Establecer ${image.file.name} como imagen principal`} disabled={disabled || selected} onClick={() => onSelectPending(image.id)}>Principal</button>
                    <button type="button" className="btn btn--ghost" aria-label={`Quitar ${image.file.name}`} disabled={disabled} onClick={() => onRemovePending(image.id)}>Quitar</button>
                  </div>
                </article>
              )
            })}

            <button type="button" className="admin-image-add-card" aria-label="Agregar más imágenes" disabled={disabled || isProcessing} onClick={openPicker} onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
              <span aria-hidden="true">+</span>
              Agregar
            </button>
            {Array.from({ length: placeholderCount }, (_, index) => <div key={`placeholder-${index}`} className="admin-image-placeholder" aria-hidden="true" />)}
          </div>
          {onUpload ? (
            <button type="button" className="btn btn--accent admin-image-gallery__upload" disabled={disabled || isProcessing || pendingImages.length === 0} onClick={onUpload}>{uploadLabel}</button>
          ) : <p className="ui-note">Las imágenes seleccionadas se cargarán después de crear el producto.</p>}
          <div className="admin-image-manager__status" role="status" aria-live="polite">
            {processingMessage ? <p className="ui-note">{processingMessage}</p> : null}
            {status ? <p className="ui-note ui-note--success">{status}</p> : null}
            {error ? <p className="ui-note ui-note--error">{error}</p> : null}
          </div>
        </div>
      </div>
    </section>
  )
}
