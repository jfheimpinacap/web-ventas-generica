interface PromotionPreviewCardProps {
  title: string
  subtitle: string
  productName?: string | null
  imageUrl?: string | null
  buttonText: string
  isActive: boolean
  order: number
  compact?: boolean
}

const FALLBACK_PROMOTION_IMAGE = 'https://placehold.co/960x560/0f172a/e2e8f0?text=Vista+previa+de+oferta'

export function PromotionPreviewCard({
  title,
  subtitle,
  productName,
  imageUrl,
  buttonText,
  isActive,
  order,
  compact = false,
}: PromotionPreviewCardProps) {
  return (
    <article className={`admin-promo-preview ${compact ? 'admin-promo-preview--compact' : ''}`} aria-label="Vista previa de oferta">
      <div className="admin-promo-preview__media">
        <img src={imageUrl || FALLBACK_PROMOTION_IMAGE} alt={title || 'Vista previa de oferta'} />
      </div>
      <div className="admin-promo-preview__overlay" />
      <div className="admin-promo-preview__content">
        <div className="admin-promo-preview__meta">
          <span className={`badge ${isActive ? 'badge--ok' : 'badge--muted'}`}>{isActive ? 'Activa' : 'Inactiva'}</span>
          <span className="admin-promo-preview__order">Orden #{order}</span>
        </div>
        <p className="admin-promo-preview__tag">Oferta destacada</p>
        <h3>{title.trim() || 'Título de la oferta'}</h3>
        <p>{subtitle.trim() || 'Subtítulo o mensaje comercial de apoyo para la oferta.'}</p>
        {productName ? <p className="admin-promo-preview__product">Producto asociado: {productName}</p> : null}
        <button type="button" className="btn btn--accent" disabled>
          {buttonText.trim() || 'Ver oferta'}
        </button>
        <div className="admin-promo-preview__dots" aria-hidden="true">
          <span className="is-active" />
          <span />
          <span />
        </div>
      </div>
    </article>
  )
}
