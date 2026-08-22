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
  onAddFiles: (files: File[]) => void
  onAltTextChange: (id: string, value: string) => void
  onSelectPending: (id: string) => void
  onRemovePending: (id: string) => void
  onSelectExisting?: (id: number) => void
  onDeleteExisting?: (id: number) => void
  onUpload?: () => void
}

const ACCEPTED_IMAGES = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'

export function ProductImageManager({
  existingImages = [], pendingImages, selectedPendingId, disabled, status, error, uploadLabel,
  onAddFiles, onAltTextChange, onSelectPending, onRemovePending, onSelectExisting, onDeleteExisting, onUpload,
}: ProductImageManagerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const totalCards = existingImages.length + pendingImages.length + 1
  const placeholderCount = Math.max(0, 10 - totalCards)

  const incorporate = (files: FileList | null) => {
    if (!files || disabled) return
    onAddFiles(Array.from(files))
  }
  const openPicker = () => {
    if (!disabled) inputRef.current?.click()
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
    <section className="admin-form-panel admin-form-panel--media admin-image-manager" aria-busy={disabled}>
      <h3>Imágenes</h3>
      <input
        ref={inputRef}
        className="admin-image-manager__input"
        type="file"
        multiple
        accept={ACCEPTED_IMAGES}
        aria-label="Seleccionar imágenes del producto"
        aria-describedby="product-images-help"
        disabled={disabled}
        onChange={(event) => {
          incorporate(event.currentTarget.files)
          event.currentTarget.value = ''
        }}
      />
      <div className="admin-image-manager__body">
        <div
          className={`admin-image-dropzone${dragActive ? ' is-drag-active' : ''}`}
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-disabled={disabled}
          aria-describedby="product-images-help"
          onClick={openPicker}
          onKeyDown={handleKeyDown}
          onDragEnter={(event) => { event.preventDefault(); if (!disabled) setDragActive(true) }}
          onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = disabled ? 'none' : 'copy' }}
          onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragActive(false) }}
          onDrop={handleDrop}
        >
          <strong>{dragActive ? 'Suelta las imágenes para agregarlas' : 'Arrastra imágenes aquí'}</strong>
          <span>o selecciónalas desde tu equipo</span>
          <span className="admin-image-dropzone__picker">Seleccionar archivo</span>
          <span id="product-images-help" className="ui-note">Formatos permitidos: JPG, PNG y WebP.</span>
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
                  <p className="admin-image-card__filename" title={image.file.name}>{image.file.name}</p>
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

            <button type="button" className="admin-image-add-card" aria-label="Agregar más imágenes" disabled={disabled} onClick={openPicker} onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
              <span aria-hidden="true">+</span>
              Agregar
            </button>
            {Array.from({ length: placeholderCount }, (_, index) => <div key={`placeholder-${index}`} className="admin-image-placeholder" aria-hidden="true" />)}
          </div>
          {onUpload ? (
            <button type="button" className="btn btn--accent admin-image-gallery__upload" disabled={disabled || pendingImages.length === 0} onClick={onUpload}>{uploadLabel}</button>
          ) : <p className="ui-note">Las imágenes seleccionadas se cargarán después de crear el producto.</p>}
          <div className="admin-image-manager__status" role="status" aria-live="polite">
            {status ? <p className="ui-note ui-note--success">{status}</p> : null}
            {error ? <p className="ui-note ui-note--error">{error}</p> : null}
          </div>
        </div>
      </div>
    </section>
  )
}
